"""NECKTIED patcher core for the Linux models (groups A, B, B2): builds the NECKTIED firmware
from the stock image the user downloaded and our own patch package. Pure Python (standard
library only), runs with CPython and in the browser with Pyodide.

    image, report = patch(original_bytes, package, variant="release", progress=callback)

What changes (and nothing else, checked after building):
  rootfs partition: + /usr/lib/necktied.so (0755), + /usr/lib/necktied_tz.bin (0644),
                    + /usr/lib/necktied_logo.jpg (0644, models with display),
                    + /usr/lib/necktied_goodbye.jpg (0644, goodbye picture; models whose
                      System_OnShutdown shows its own picture slot),
                    ~ /etc/init.d/S99_Sysctl: "cardv ..." -> "LD_PRELOAD=/usr/lib/necktied.so cardv ..."
  all other partitions byte-identical, container checksums recomputed.
"""
import hashlib
import re
import struct
import time

from . import nvtpack as nv
from . import ubi
from .check import check_ubifs
from .fsedit import FsEdit
from .i18n import _, set_lang, get_lang
from .package import Package, VARIANTS
from .ubifs_format import COMPR_NONE, COMPR_ZLIB, S_IFMT
from .ubifs_read import Ubifs, FileTree, UbifsError
from .ubifs_write import Writer

SPACE = b" \t\v\f\r"                    # [[:space:]] of sed (C locale, without newline)
COMPRESSION = {"none": COMPR_NONE, "zlib": COMPR_ZLIB}


class PatchError(Exception):
    pass


def _sha256(b):
    return hashlib.sha256(b).hexdigest()


def identify(original, package):
    """(BIN_NAME, model entry) of a supported stock image, else PatchError with the reason."""
    if bytes(original[:16]) != nv.NVTPACK_GUID:
        raise PatchError(_("The file is not a Viofo firmware (Novatek container missing)."))
    sha = _sha256(original)
    b, mod = package.model_by_sha256(sha)
    name = nv.bin_name(original)
    if mod is None:
        known = package.models().get(name)
        if known:
            raise PatchError(_("This is a different firmware version for %s. NECKTIED needs exactly %s (sha256 %s…) from "
                               "https://www.viofo.com/pages/firmware.") % (known["model"], known["version"], known["sha256"][:16]))
        raise PatchError(_("This firmware (%s, sha256 %s…) is not supported.") % (name or _("unknown"), sha[:16]))
    if name != b:
        raise PatchError(_("BIN_NAME %r does not match model %s") % (name, b))
    return b, mod


def apply_s99(text, rule):
    """sed of tools/build_patched_fw.sh: group A "s#^cardv #<prefix>cardv #", groups B/B2
    "s#^\\([[:space:]]*\\)cardv #\\1<prefix>cardv #". Returns (new text, number of starts)."""
    cmd = rule["command"].encode()
    prefix = rule["prefix"].encode()
    out = []
    for line in text.split(b"\n"):
        ws = line[:len(line) - len(line.lstrip(SPACE))] if rule["indent"] else b""
        rest = line[len(ws):]
        if rest.startswith(cmd):
            line = ws + prefix + rest
        out.append(line)
    new = b"\n".join(out)
    pat_done = re.compile(rb"^[ \t\v\f\r]*" + re.escape(prefix + cmd.rstrip()), re.M)
    n = len(pat_done.findall(new))
    if n < rule["min_count"]:
        raise PatchError(_("S99_Sysctl: expected replacements missing (%d instead of at least %d)") % (n, rule["min_count"]))
    if rule["all_starts"]:
        left = re.findall(rb"^[ \t\v\f\r]*" + re.escape(cmd), new, re.M)
        if left:
            raise PatchError(_("S99_Sysctl: cardv start without LD_PRELOAD left"))
    return new, n


def _file_sig(tree, inum):
    """Content identity of an inode without decompressing: data nodes as stored + inline data."""
    node, f, inline = tree.inodes[inum]
    h = hashlib.sha256(inline)
    for blk in sorted(tree.data.get(inum, {})):
        dn = tree.data[inum][blk]
        h.update(struct.pack("<I", blk))
        h.update(bytes(dn.raw[40:]))
    return h.hexdigest()


def tree_manifest(tree, content=True):
    """{path: (mode, uid, gid, size or None for dirs, nlink, xattrs, content signature)}."""
    out = {}
    for path, inum in tree.walk():
        node, f, inline = tree.inodes[inum]
        isdir = (f["mode"] & S_IFMT) == 0o040000
        out[path] = (f["mode"], f["uid"], f["gid"], None if isdir else f["size"], f["nlink"],
                     tuple(sorted(tree.xattrs(inum).items())), _file_sig(tree, inum) if content and not isdir else None)
    return out


def card_instructions(bname, mod):
    fw = bname + ".bin"
    status = (_("tested on a device") if mod.get("verified")
              else _("ONLY TESTED LOCALLY – not yet tested on a device for this model"))
    return _("""SD card instructions (%s, %s):
  1. Format the SD card in the camera (or FAT32/exFAT), then copy %s to the root directory
     of the card on the computer (exactly this file name, no other firmware files).
  2. Eject the card cleanly.
  3. Insert the card into the camera and switch it on. The camera installs the update while starting up.
     Do NOT disconnect the power during the update.
  4. Afterwards %s must have disappeared from the card (the camera deletes it after the start).
Way back: the same with the original from https://www.viofo.com/pages/firmware (%s, sha256 %s…).
Status of this model: %s.""") % (mod["model"], bname, fw, fw, mod["version"], mod["sha256"][:16], status)


def patch(original, package, variant="release", logo=True, compression="none", progress=None, verify=True,
          goodbye=True, lang=None):
    """Build the NECKTIED image. Returns (image bytes, report dict). Raises PatchError.
    goodbye: install the goodbye picture of the package (models with a shutdown slot only);
    False = the shutdown slot shows the boot logo (or the original without logo), as before.
    lang: "en" (default) or "de" for the texts of report and errors (else the current setting,
    i18n.set_lang / NECKTIED_LANG)."""
    if lang is not None:
        keep = get_lang()
        set_lang(lang)
        try:
            return patch(original, package, variant, logo, compression, progress, verify, goodbye)
        finally:
            set_lang(keep)
    t0 = time.time()
    times = {}
    steps = []

    def step(frac, text):
        steps.append(text)
        times[text] = round(time.time() - t0, 3)
        if progress:
            progress(frac, text)

    if not isinstance(package, Package):
        package = Package.load(package)
    if variant not in VARIANTS:
        raise PatchError(_("Unknown variant %r (allowed: %s)") % (variant, ", ".join(VARIANTS)))
    if compression not in COMPRESSION:
        raise PatchError(_("Unknown compression %r (allowed: none, zlib)") % compression)
    if not isinstance(original, (bytes, bytearray)):
        original = bytes(original)
    step(0.0, _("Checking original"))
    bname, mod = identify(original, package)
    grp = package.group(mod["group"])
    if variant not in grp["variants"]:
        raise PatchError(_("Variant %r is not contained in this package") % variant)
    pk = nv.Pack(original)
    if pk.ids() != sorted(mod["part_ids"]):
        raise PatchError(_("Partition list %s instead of %s") % (pk.ids(), mod["part_ids"]))
    errs = nv.verify(original)
    if errs:
        raise PatchError(_("Original fails the U-Boot check: %s") % "; ".join(errs[:3]))
    rid = nv.rootfs_id(original)
    if rid != mod["rootfs_id"]:
        raise PatchError(_("rootfs is partition id%d instead of id%d") % (rid, mod["rootfs_id"]))
    part = pk.part(rid)
    if bytes(part[:4]) != nv.CKSM_MAGIC or bytes(part[0x40:0x44]) != ubi.EC_MAGIC:
        raise PatchError(_("rootfs partition is not CKSM+UBI"))

    step(0.1, _("Reading rootfs (UBI/UBIFS)"))
    u, vid, vol, lebs, fs, tree = read_rootfs(part)
    comp = COMPRESSION[compression]
    if comp == COMPR_ZLIB and not any(struct.unpack_from("<H", dn.raw, 44)[0] == COMPR_ZLIB
                                      for blocks in tree.data.values() for dn in blocks.values()):
        raise PatchError(_("zlib only for models whose original itself contains zlib nodes (group A) – "
                           "use compression none here"))

    step(0.25, _("Checking cardv"))
    cinum = tree.lookup("/usr/bin/cardv")
    if cinum is None:
        raise PatchError(_("/usr/bin/cardv missing in rootfs"))
    cmd5 = hashlib.md5(tree.read_file(cinum)).hexdigest()
    if cmd5 != mod["cardv_md5"]:
        raise PatchError(_("cardv md5 %s instead of %s – the library does not know this cardv") % (cmd5, mod["cardv_md5"]))

    step(0.35, _("Installing NECKTIED"))
    rule = grp["s99"]
    s99_inum = tree.lookup(rule["path"])
    if s99_inum is None:
        raise PatchError(_("%s missing") % rule["path"])
    s99_old = tree.read_file(s99_inum)
    s99_new, n_starts = apply_s99(s99_old, rule)
    inst = package.manifest["install"]
    lib = package.file(grp["variants"][variant])
    tz = package.file(grp["tz"])
    adds = [(inst["lib"][0], lib, inst["lib"][1]), (inst["tz"][0], tz, inst["tz"][1])]
    if logo and mod.get("logo"):
        adds.append((inst["logo"][0], package.file(mod["logo"]), inst["logo"][1]))
    if goodbye and mod.get("goodbye"):
        path, mode = inst.get("goodbye", ["/usr/lib/necktied_goodbye.jpg", 0o644])
        adds.append((path, package.file(mod["goodbye"]), mode))
    ed = FsEdit(tree)
    ed.replace_file(rule["path"], s99_new, comp)
    for path, data, mode in adds:
        ed.add_file(path, data, mode, 0, 0, comp)

    step(0.45, _("Writing UBIFS"))
    image, n_new_lebs = assemble(original, pk, rid, part, u, vid, vol, fs, ed, step)
    del ed

    report = dict(bin_name=bname, file_name=bname + ".bin", model=mod["model"], firmware=mod["version"],
                  group=mod["group"], verified=mod.get("verified", False), variant=variant,
                  package_version=package.version, compression=compression,
                  original_sha256=_sha256(original), image_sha256=_sha256(image), image_size=len(image),
                  cardv_md5=cmd5, s99_starts=n_starts, goodbye=bool(goodbye and mod.get("goodbye")),
                  added=[p for p, _, _ in adds], changed=[rule["path"]],
                  lebs_original=len(lebs), lebs_new=n_new_lebs, reserved_pebs=vol["reserved_pebs"])
    if verify:
        step(0.7, _("Verifying"))
        report["checks"] = verify_result(image, original, mod, rule["path"], s99_new,
                                         {p: d for p, d, _ in adds}, {p: m for p, _, m in adds}, step)
    step(1.0, _("done"))
    report["seconds"] = round(time.time() - t0, 2)
    report["step_times"] = times
    report["instructions"] = card_instructions(bname, mod)
    return image, report


def read_rootfs(part):
    """(UbiImage, vol_id, vtbl entry, LEB list, Ubifs, FileTree) of a CKSM+UBI rootfs partition."""
    try:
        u = ubi.UbiImage(part[0x40:])
        if len(u.vtbl) != 1:
            raise PatchError(_("unexpected volume table: %s") % u.vtbl)
        vid = u.volume_by_name("rootfs")
        vol = u.vtbl[vid]
        if vol["vol_type"] != ubi.VID_DYNAMIC or vol["flags"] or vol["upd_marker"]:
            raise PatchError(_("rootfs volume has unexpected properties: %s") % vol)
        lebs = u.volume_lebs(vid)
        if any(x is None for x in lebs):
            raise PatchError(_("rootfs volume with gaps (not made by ubinize)"))
        fs = Ubifs(lebs, u.leb_size)
        tree = FileTree(fs)
    except (UbifsError, ubi.UbiError) as e:
        raise PatchError(_("rootfs not readable: %s") % e)
    return u, vid, vol, lebs, fs, tree


def assemble(original, pk, rid, part, u, vid, vol, fs, ed, step=None):
    """Write UBIFS (from the node sequence of ed), UBI, CKSM and NVTPACK. Returns (image, LEB count)."""
    w = Writer(fs.sb, fs.sb_raw)
    for key, name, raw in ed.seq:
        w.add_leaf(key, name, raw)
    new_lebs = w.finish(ed.highest_inum, ed.sqnum)
    if step:
        step(0.6, _("Packing UBI image and firmware"))
    if len(new_lebs) > vol["reserved_pebs"]:
        raise PatchError(_("rootfs needs %d LEBs, the volume has %d") % (len(new_lebs), vol["reserved_pebs"]))
    new_ubi = ubi.build_chunks(new_lebs, u.peb_size, u.vid_off, u.data_off, u.image_seq,
                               dict(id=vid, name=vol["name"], reserved_pebs=vol["reserved_pebs"],
                                    alignment=vol["alignment"], flags=vol["flags"]), u.version)
    parts = {p: ([part[:0x40]] + new_ubi if p == rid else pk.part(p)) for p in pk.ids()}
    del new_ubi
    image = nv.build(original, parts, cksm=(rid,))
    return image, len(new_lebs)


def rebuild_unchanged(original):
    """Rewrite the rootfs without any change (test of the writer): reads all nodes and writes
    UBIFS, UBI, CKSM and NVTPACK anew. For an image made by mkfs.ubifs/ubinize the result is
    byte-identical to the original."""
    if not isinstance(original, (bytes, bytearray)):
        original = bytes(original)
    pk = nv.Pack(original)
    rid = nv.rootfs_id(original)
    part = pk.part(rid)
    u, vid, vol, lebs, fs, tree = read_rootfs(part)
    image, _ = assemble(original, pk, rid, part, u, vid, vol, fs, FsEdit(tree))
    return image


def verify_result(image, original, mod, s99_path, s99_new, added, modes, step=None):
    """Independent re-read of the finished image. Raises PatchError on any deviation."""
    checks = []
    errs = nv.verify(image)
    if errs:
        raise PatchError(_("U-Boot would reject the result: %s") % "; ".join(errs[:3]))
    checks.append(_("Container and all partitions pass the U-Boot checks"))
    pk, po = nv.Pack(image), nv.Pack(original)
    rid = mod["rootfs_id"]
    if pk.ids() != po.ids():
        raise PatchError(_("Partition list changed"))
    for p in pk.ids():
        if p != rid and pk.part(p) != po.part(p):
            raise PatchError(_("Partition id%d differs from the original") % p)
    checks.append(_("All partitions except rootfs byte-identical to the original"))
    uo = ubi.UbiImage(po.part(rid)[0x40:])
    un = ubi.UbiImage(pk.part(rid)[0x40:])
    if (un.peb_size, un.vid_off, un.data_off, un.image_seq, un.vtbl) != (uo.peb_size, uo.vid_off, uo.data_off,
                                                                         uo.image_seq, uo.vtbl):
        raise PatchError(_("UBI geometry/volume table differs from the original"))
    checks.append(_("UBI: geometry, image_seq and volume table as in the original, all header CRCs valid"))
    if step:
        step(0.8, _("Verifying: UBIFS structure"))
    lebs = un.volume_lebs(un.volume_by_name("rootfs"))
    try:
        fsn = Ubifs(lebs, un.leb_size)
        leaves = fsn.leaf_nodes()
        serrs, stats = check_ubifs(lebs, un.leb_size, fsn, leaves)
    except UbifsError as e:
        raise PatchError(_("new UBIFS not readable: %s") % e)
    if serrs:
        raise PatchError(_("UBIFS structure check: %s") % "; ".join(serrs[:5]))
    fso = Ubifs(uo.volume_lebs(0), uo.leb_size)
    keep = ("key_hash", "key_fmt", "flags", "min_io_size", "leb_size", "max_leb_cnt", "max_bud_bytes",
            "log_lebs", "lpt_lebs", "orph_lebs", "jhead_cnt", "fanout", "lsave_cnt", "fmt_version",
            "default_compr", "rp_uid", "rp_gid", "rp_size", "time_gran", "uuid", "ro_compat_version")
    if any(fsn.sb[k] != fso.sb[k] for k in keep):
        raise PatchError(_("UBIFS superblock parameters differ from the original"))
    checks.append(_("UBIFS: superblock parameters as in the original; index, LPT, master, log, sequence numbers and "
                    "file tree consistent (%d nodes, %d LEBs)") % (stats["leaves"], stats["leb_cnt"]))
    if step:
        step(0.9, _("Verifying: file tree"))
    tn, to = FileTree(fsn, leaves), FileTree(fso)
    mn, mo = tree_manifest(tn), tree_manifest(to)
    want_added = sorted(added)
    got_added = sorted(set(mn) - set(mo))
    if got_added != want_added or set(mo) - set(mn):
        raise PatchError(_("File tree: added %s, removed %s") % (got_added, sorted(set(mo) - set(mn))))
    changed = sorted(k for k in mo if mo[k] != mn[k])
    if changed != [s99_path]:
        raise PatchError(_("File tree: changed %s instead of only %s") % (changed, s99_path))
    a, b = mo[s99_path], mn[s99_path]
    if a[:3] != b[:3] or a[4:6] != b[4:6]:
        raise PatchError(_("%s: permissions/owner changed") % s99_path)
    if tn.read_file(tn.lookup(s99_path)) != s99_new:
        raise PatchError(_("%s: content not as expected") % s99_path)
    for path, data in added.items():
        inum = tn.lookup(path)
        f = tn.inodes[inum][1]
        if (f["mode"], f["uid"], f["gid"], f["nlink"]) != (0o100000 | modes[path], 0, 0, 1):
            raise PatchError(_("%s: wrong permissions/owner") % path)
        if tn.read_file(inum) != data:
            raise PatchError(_("%s: content differs from the package") % path)
    cmd5 = hashlib.md5(tn.read_file(tn.lookup("/usr/bin/cardv"))).hexdigest()
    if cmd5 != mod["cardv_md5"]:
        raise PatchError(_("cardv changed in the result"))
    checks.append(_("File tree: %d entries, only %s new and %s changed; all other files with identical data nodes, "
                    "permissions, owners, xattrs; contents of the new files = package")
                  % (len(mn), ", ".join(want_added), s99_path))
    return checks
