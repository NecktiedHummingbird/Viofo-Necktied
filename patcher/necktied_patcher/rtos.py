"""NECKTIED for the RTOS models (group C, first: A119 V3): static patch of the RTOS image.

The RTOS partition (NVTPACK, BCL1/LZMA) is unpacked, our code and data are written to fixed
addresses, the RTOS checksum is set, the partition is compressed again and the container is
rebuilt; all other partitions stay byte-identical. The package contains only NECKTIED's own
bytes (code, pointers, strings, pictures) and the addresses; the stock RTOS is identified by
its sha256, so no byte of it has to be shipped or compared individually.

Patch description (package file, JSON):
    {"rtos_id": 2, "order": [1, 2, 3, 6], "layout": [[off, size, id], ...], "align": 8,
     "base": 4194304, "raw_size": n, "raw_sha256": "...", "sum_slot": 110,
     "uboot_id": 3, "uboot_guid_off": 209256, "modelext_id": 1,
     "patches": [{"name": "...", "addr": a, "data": "<hex>"}, ...],     always applied
     "pictures": {"boot": a, "shutdown": a, "len": n}}                 picture slots (len = usable bytes)
"""
import hashlib
import json
import struct

from . import bcl1
from . import nvtpack as nv
from .errors import PatchError
from .i18n import _


def spec_of(package, mod):
    return json.loads(package.file(mod["rtos"]).decode("utf-8"))


def parse_pack(d):
    ver, hsz, cnt, total = struct.unpack_from("<4I", d, 0x10)
    ents = [list(struct.unpack_from("<3I", d, nv.ENTRY_TABLE_OFF + i * nv.ENTRY_SIZE)) for i in range(cnt)]
    return {"version": ver, "count": cnt, "total": total, "entries": ents}


def build_pack(original, parts, order, align=16):
    """Container like the original: same header fields, partitions back to back (order),
    first partition 16-aligned, header checksum recomputed."""
    hdr = bytearray(original[:nv.ENTRY_TABLE_OFF])
    struct.pack_into("<I", hdr, 0x18, len(order))
    struct.pack_into("<H", hdr, nv.HDR_CHECKSUM_OFF, 0)
    out = hdr + bytearray(len(order) * nv.ENTRY_SIZE)
    out += b"\0" * (-len(out) % align)
    ents = []
    for pid in order:
        ents.append((len(out), len(parts[pid]), pid))
        out += parts[pid]
    for i, e in enumerate(ents):
        struct.pack_into("<3I", out, nv.ENTRY_TABLE_OFF + i * nv.ENTRY_SIZE, *e)
    if len(out) % 2:
        out.append(0)
    struct.pack_into("<I", out, 0x1C, len(out))
    nv.fix_sum_at(out, nv.HDR_CHECKSUM_OFF)
    return bytes(out)


def modelext_partitions(modelext):
    """Flash partition table of the MODELEXT block type 5: id -> (embtype, offset, size)."""
    o = 0
    while o + 16 <= len(modelext):
        size, typ, num, _x = struct.unpack_from("<4I", modelext, o)
        if size == 0:
            break
        if typ == 5:
            tab = {}
            for i in range(num):
                emb, _y, off, sz, _z = struct.unpack_from("<HHIII", modelext, o + 16 + 16 * i)
                tab[i] = (emb, off << 16, sz << 16)
            return tab
        o += size
    raise PatchError(_("MODELEXT without partition table"))


def uboot_check(d, spec, uboot, modelext):
    """The checks of the U-Boot before it writes (A119 V3: nvt_process_all_in_one). Returns
    a list of errors."""
    errs = []
    if bytes(d[:16]) != bytes(uboot[spec["uboot_guid_off"]:spec["uboot_guid_off"] + 16]):
        errs.append("GUID differs from the table of the U-Boot")
    if len(d) % 2 or nv.nvt_sum(d) != 0:
        errs.append("container checksum")
    pk = parse_pack(d)
    if pk["total"] != len(d):
        errs.append("total size in the header %#x != file size %#x" % (pk["total"], len(d)))
    tab = modelext_partitions(modelext)
    for off, size, pid in pk["entries"]:
        if off % 4 or off + size > len(d):
            errs.append("id%d: position %#x+%#x" % (pid, off, size))
            continue
        p = d[off:off + size]
        if nv.nvt_sum(p) != 0:
            errs.append("id%d: checksum" % pid)
        if pid not in tab or size > tab[pid][2]:
            errs.append("id%d: %#x bytes do not fit the flash partition" % (pid, size))
        if bytes(p[:4]) == bcl1.MAGIC:
            e = bcl1.check(p)
            if e:
                errs.append("id%d: BCL1 %s" % (pid, "; ".join(e)))
    return errs


def patch_list(package, mod, spec, logo, goodbye):
    """[(name, addr, bytes)] to apply: always the base patches, plus the pictures."""
    out = [(p["name"], p["addr"], bytes.fromhex(p["data"])) for p in spec["patches"]]
    pic = spec.get("pictures")
    if pic:
        def slot(name, addr, data):
            if len(data) > pic["len"]:
                raise PatchError(_("Picture %s too big for the slot (%d > %d bytes)") % (name, len(data), pic["len"]))
            return (name, addr, data + b"\0" * (pic["len"] - len(data)))
        lg = package.file(mod["logo"]) if logo and mod.get("logo") else None
        gb = package.file(mod["goodbye"]) if goodbye and mod.get("goodbye") else None
        if lg is not None:
            out.append(slot("boot logo", pic["boot"], lg))
        if gb is not None:
            out.append(slot("goodbye picture", pic["shutdown"], gb))
        elif lg is not None:
            out.append(slot("boot logo (shutdown slot)", pic["shutdown"], lg))
    return out


def patch_rtos(original, package, mod, bname, logo, goodbye, verify, step):
    """Build the NECKTIED image of an RTOS model. Returns (image, report fields, checks)."""
    spec = spec_of(package, mod)
    step(0.05, _("Checking original"))
    if bytes(original[:16]) != nv.NVTPACK_GUID:
        raise PatchError(_("The file is not a Viofo firmware (Novatek container missing)."))
    pk = parse_pack(original)
    if pk["entries"] != spec["layout"]:
        raise PatchError(_("Partition layout differs from the supported firmware"))
    parts = {pid: bytes(original[off:off + size]) for off, size, pid in pk["entries"]}
    uboot, modelext = parts[spec["uboot_id"]], parts[spec["modelext_id"]]
    errs = uboot_check(original, spec, uboot, modelext)
    if errs:
        raise PatchError(_("Original fails the U-Boot check: %s") % "; ".join(errs[:3]))

    step(0.15, _("Unpacking RTOS"))
    try:
        raw = bcl1.decompress(parts[spec["rtos_id"]])
    except bcl1.Bcl1Error as e:
        raise PatchError(_("RTOS not readable: %s") % e)
    if len(raw) != spec["raw_size"] or hashlib.sha256(raw).hexdigest() != spec["raw_sha256"]:
        raise PatchError(_("RTOS differs from the supported firmware"))
    if nv.nvt_sum(raw) != 0:
        raise PatchError(_("RTOS checksum of the original is wrong"))

    step(0.3, _("Installing NECKTIED"))
    plist = patch_list(package, mod, spec, logo, goodbye)
    base = spec["base"]
    new = bytearray(raw)
    taken = set()
    for name, addr, data in plist:
        o = addr - base
        if o < 0 or o + len(data) > len(new):
            raise PatchError(_("%s: address %#x outside the RTOS") % (name, addr))
        rng = set(range(o, o + len(data)))
        if rng & taken:
            raise PatchError(_("%s: overlaps another change") % name)
        taken |= rng
        new[o:o + len(data)] = data
    slot = spec["sum_slot"]
    if {slot, slot + 1} & taken:
        raise PatchError(_("A change hits the RTOS checksum"))
    nv.fix_sum_at(new, slot)
    new = bytes(new)

    step(0.45, _("Compressing RTOS (LZMA)"))
    rpart = bcl1.compress_like(new, parts[spec["rtos_id"]], spec["align"])
    nparts = dict(parts)
    nparts[spec["rtos_id"]] = rpart
    step(0.75, _("Packing firmware"))
    image = build_pack(original, nparts, spec["order"])

    checks = []
    if verify:
        step(0.8, _("Verifying"))
        checks = verify_rtos(image, original, spec, raw, plist)
    fields = dict(changes=[n for n, _a, _d in plist], rtos_size=len(raw), rtos_partition=len(rpart))
    return image, fields, checks


def verify_rtos(image, original, spec, raw, plist):
    """Independent re-read of the finished image. Raises PatchError on any deviation."""
    checks = []
    po = {pid: bytes(original[o:o + s]) for o, s, pid in parse_pack(original)["entries"]}
    pn_ = parse_pack(image)
    pn = {pid: bytes(image[o:o + s]) for o, s, pid in pn_["entries"]}
    errs = uboot_check(image, spec, po[spec["uboot_id"]], po[spec["modelext_id"]])
    if errs:
        raise PatchError(_("U-Boot would reject the result: %s") % "; ".join(errs[:3]))
    checks.append(_("Container and all partitions pass the checks of the U-Boot (GUID, checksums, sizes, "
                    "flash partitions)"))
    if [e[2] for e in pn_["entries"]] != spec["order"]:
        raise PatchError(_("Partition list changed"))
    for pid in spec["order"]:
        if pid != spec["rtos_id"] and pn[pid] != po[pid]:
            raise PatchError(_("Partition id%d differs from the original") % pid)
    checks.append(_("All partitions except the RTOS byte-identical to the original"))
    try:
        raw2 = bcl1.decompress(pn[spec["rtos_id"]])
    except bcl1.Bcl1Error as e:
        raise PatchError(_("new RTOS not readable: %s") % e)
    if len(raw2) != len(raw) or nv.nvt_sum(raw2) != 0:
        raise PatchError(_("new RTOS: size or checksum wrong"))
    base = spec["base"]
    allowed = {spec["sum_slot"], spec["sum_slot"] + 1}
    for name, addr, data in plist:
        o = addr - base
        if raw2[o:o + len(data)] != data:
            raise PatchError(_("%s: not written as in the package") % name)
        allowed |= set(range(o, o + len(data)))
    changed = 0
    mv1, mv2 = memoryview(raw), memoryview(raw2)
    step = 1 << 16
    for i in range(0, len(raw), step):
        if mv1[i:i + step] != mv2[i:i + step]:
            for k in range(i, min(i + step, len(raw))):
                if raw[k] != raw2[k]:
                    if k not in allowed:
                        raise PatchError(_("new RTOS: unexpected change at %#x") % (base + k))
                    changed += 1
    checks.append(_("RTOS unpacked again: checksum valid, only the intended bytes changed (%d bytes in %d "
                    "changes)") % (changed, len(plist)))
    return checks
