"""Strict structure check of a UBIFS volume (independent of how it was written).

Recomputes from the flash contents what the kernel relies on and compares it with the stored
metadata: index (CRC, levels, key order, first keys), every node in the main area referenced
exactly once, LEB properties in the LPT (free/dirty/index flag per LEB, CRC16 of every LPT
node), the LPT's own LEB table, master node totals, sequence numbers, and the file tree
(link counts, directory sizes, data inside the file size, xattr counts).
"""
import struct

from .crc import crc16
from .ubifs_format import (IDX_NODE, LOG_LNUM, LPROPS_INDEX, MIN_WRITE_SZ,
                           MAX_NODE_SZ, INO_NODE_SZ, S_IFMT, BLOCK_SIZE, align, key_type,
                           DENT_KEY, XENT_KEY, FLG_BIGLPT)
from .ubifs_read import Ubifs, FileTree, UbifsError
from .ubifs_write import LptGeometry, LPT_FANOUT, LPT_TYPE_BITS, LPT_PNODE, LPT_NNODE, LPT_LTAB, LPT_LSAVE
from .fsedit import dent_size


class BitReader:
    def __init__(self, data):
        self.v = int.from_bytes(bytes(data[2:]), "little")
        self.pos = 0

    def get(self, bits):
        x = (self.v >> self.pos) & ((1 << bits) - 1)
        self.pos += bits
        return x


def _lpt_node(fs, lnum, offs, size, want_type):
    b = fs.leb(lnum)
    raw = bytes(b[offs:offs + size])
    if len(raw) != size:
        raise UbifsError("LPT node %d:%d truncated" % (lnum, offs))
    if struct.unpack_from("<H", raw, 0)[0] != crc16(raw[2:]):
        raise UbifsError("LPT node %d:%d: CRC16 wrong" % (lnum, offs))
    br = BitReader(raw)
    t = br.get(LPT_TYPE_BITS)
    if t != want_type:
        raise UbifsError("LPT node %d:%d: type %d instead of %d" % (lnum, offs, t, want_type))
    return br


def check_ubifs(lebs, leb_size, fs=None, leaves=None):
    """Returns (errors, stats). Raises UbifsError for unreadable structures.
    fs/leaves: an already parsed Ubifs of these LEBs and its leaf_nodes() (saves time)."""
    errs = []
    if fs is None or leaves is None:
        fs = Ubifs(lebs, leb_size)
        leaves = None
    sb, mst = fs.sb, fs.mst
    min_io = fs.min_io
    if sb["leb_cnt"] != len(lebs) or mst["leb_cnt"] != len(lebs):
        errs.append("leb_cnt SB %d / Master %d / Volume %d" % (sb["leb_cnt"], mst["leb_cnt"], len(lebs)))
    g = LptGeometry(leb_size, min_io, sb["max_leb_cnt"], sb["log_lebs"], sb["orph_lebs"], sb["lsave_cnt"])
    if g.lpt_lebs != sb["lpt_lebs"] or bool(g.big_lpt) != bool(sb["flags"] & FLG_BIGLPT):
        errs.append("LPT geometry does not match the superblock")
    main_first = fs.main_first
    leb_cnt = len(lebs)
    # --- index ---
    if leaves is None:
        leaves = fs.leaf_nodes()
    idx_nodes = fs.idx_nodes
    ref = {}
    for key, node, _ in leaves:
        ref[(node.lnum, node.offs)] = (node.len, "leaf", node.sqnum)
    index_size = 0
    max_sq = 0
    for lnum, offs, ln, level in idx_nodes:
        if (lnum, offs) in ref:
            errs.append("node %d:%d referenced more than once" % (lnum, offs))
        n = fs.read_node(lnum, offs, IDX_NODE, ln)
        ref[(lnum, offs)] = (ln, "idx", n.sqnum)
        index_size += align(ln, 8)
        # branch keys inside one index node must be ordered
        cnt = struct.unpack_from("<H", n.raw, 24)[0]
        keys = [struct.unpack_from("<II", n.raw, 28 + j * 20 + 12) for j in range(cnt)]
        for a, b in zip(keys, keys[1:]):
            if a > b or (a == b and key_type(a) not in (DENT_KEY, XENT_KEY)):
                errs.append("index node %d:%d: keys not ascending" % (lnum, offs))
                break
    if len(ref) != len(leaves) + len(idx_nodes):
        errs.append("nodes referenced more than once")
    if index_size != mst["index_size"]:
        errs.append("index_size %d instead of %d" % (mst["index_size"], index_size))
    # --- main area: every node referenced, LEB properties ---
    lprops = {}
    seen = set()
    idx_lebs = []
    for lnum in range(main_first, leb_cnt):
        nodes = fs.scan_leb(lnum)
        end = 0
        used = 0
        kinds = set()
        for n in nodes:
            r = ref.get((n.lnum, n.offs))
            if r is None or r[0] != n.len:
                errs.append("LEB %d: node at %d (%d) is not in the index - garbage in the main area"
                            % (lnum, n.offs, n.type))
                continue
            seen.add((n.lnum, n.offs))
            kinds.add(r[1])
            used += align(n.len, 8)
            end = n.offs + n.len
            max_sq = max(max_sq, n.sqnum)
        if len(kinds) > 1:
            errs.append("LEB %d contains both index and data nodes" % lnum)
        free = leb_size - align(end, max(min_io, 8)) if nodes else leb_size
        dirty = leb_size - free - used
        flags = LPROPS_INDEX if "idx" in kinds else 0
        if flags:
            idx_lebs.append(lnum)
        # the region behind the last node up to the next min. I/O boundary is padding, the rest 0xFF
        tail = bytes(fs.leb(lnum)[align(end, min_io):]) if fs.leb(lnum) is not None else b""
        if tail.strip(b"\xff"):
            errs.append("LEB %d: data in the free area" % lnum)
        lprops[lnum] = (free, dirty, flags)
    missing = set(ref) - seen
    if missing:
        errs.append("%d referenced nodes not found in the main area" % len(missing))
    # --- master totals ---
    dead_wm = align(MIN_WRITE_SZ, min_io)
    dark_wm = align(MAX_NODE_SZ, min_io)
    tot = dict(total_free=0, total_dirty=0, total_used=0, total_dead=0, total_dark=0, idx_lebs=0, empty_lebs=0)
    for lnum, (free, dirty, flags) in lprops.items():
        tot["total_free"] += free
        tot["total_dirty"] += dirty
        if free == leb_size:
            tot["empty_lebs"] += 1
        if flags & LPROPS_INDEX:
            tot["idx_lebs"] += 1
        else:
            spc = free + dirty
            if spc < dead_wm:
                tot["total_dead"] += spc
            else:
                tot["total_dark"] += spc if spc < dark_wm else (spc - MIN_WRITE_SZ if spc - dark_wm < MIN_WRITE_SZ
                                                                else dark_wm)
            tot["total_used"] += leb_size - spc
    for k, v in tot.items():
        if mst[k] != v:
            errs.append("master %s = %d, computed %d" % (k, mst[k], v))
    if lprops.get(mst["gc_lnum"], (0,))[0] != leb_size:
        errs.append("GC LEB %d is not empty" % mst["gc_lnum"])
    if idx_lebs and (mst["ihead_lnum"] != idx_lebs[-1]
                     or mst["ihead_offs"] != align(leb_size - lprops[idx_lebs[-1]][0], min_io)):
        errs.append("index head (ihead) %d:%d does not match" % (mst["ihead_lnum"], mst["ihead_offs"]))
    if mst["lscan_lnum"] != main_first:
        errs.append("lscan_lnum %d" % mst["lscan_lnum"])
    # --- LPT on flash ---
    main_lebs = leb_cnt - main_first
    lpt_used = {}

    def use(lnum, offs, size):
        if not (g.lpt_first <= lnum <= g.lpt_last) or offs + size > leb_size:
            raise UbifsError("LPT branch %d:%d outside the LPT area" % (lnum, offs))
        lpt_used.setdefault(lnum, []).append((offs, size))

    flash_lp = {}
    nnodes = pnodes = 0

    def read_nnode(lnum, offs, level, num):
        nonlocal nnodes, pnodes
        use(lnum, offs, g.nnode_sz)
        br = _lpt_node(fs, lnum, offs, g.nnode_sz, LPT_NNODE)
        nnodes += 1
        if g.big_lpt:
            br.get(g.pcnt_bits)
        br_list = []
        for j in range(LPT_FANOUT):
            bl = br.get(g.lpt_lnum_bits) + g.lpt_first
            bo = br.get(g.lpt_offs_bits)
            br_list.append((0 if bl == g.lpt_last + 1 else bl, bo))
        for j, (bl, bo) in enumerate(br_list):
            child = num * LPT_FANOUT + j
            if bl == 0:
                continue
            if level == 1:
                use(bl, bo, g.pnode_sz)
                pb = _lpt_node(fs, bl, bo, g.pnode_sz, LPT_PNODE)
                pnodes += 1
                if g.big_lpt:
                    pb.get(g.pcnt_bits)
                for k in range(LPT_FANOUT):
                    free = pb.get(g.space_bits) << 3
                    dirty = pb.get(g.space_bits) << 3
                    idx = pb.get(1)
                    flash_lp[main_first + child * LPT_FANOUT + k] = (free, dirty, LPROPS_INDEX if idx else 0)
            else:
                read_nnode(bl, bo, level - 1, child)

    read_nnode(mst["lpt_lnum"], mst["lpt_offs"], g.lpt_hght, 0)
    for lnum in range(main_first, main_first + g.max_main_lebs):
        want = lprops.get(lnum, (leb_size, 0, 0))
        have = flash_lp.get(lnum, (leb_size, 0, 0))
        if want != have:
            errs.append("LPT for LEB %d: %s, computed %s" % (lnum, have, want))
            if len(errs) > 50:
                break
    if g.big_lpt:
        use(mst["lsave_lnum"], mst["lsave_offs"], g.lsave_sz)
        _lpt_node(fs, mst["lsave_lnum"], mst["lsave_offs"], g.lsave_sz, LPT_LSAVE)
    use(mst["ltab_lnum"], mst["ltab_offs"], g.ltab_sz)
    tb = _lpt_node(fs, mst["ltab_lnum"], mst["ltab_offs"], g.ltab_sz, LPT_LTAB)
    for i in range(g.lpt_lebs):
        lnum = g.lpt_first + i
        free, dirty = tb.get(g.lpt_spc_bits), tb.get(g.lpt_spc_bits)
        parts = sorted(lpt_used.get(lnum, []))
        if parts:
            end = max(o + s for o, s in parts)
            size = sum(s for _, s in parts)
            want = (leb_size - align(end, min_io), align(end, min_io) - size)
            for (o1, s1), (o2, _) in zip(parts, parts[1:]):
                if o1 + s1 > o2:
                    errs.append("LPT nodes overlap in LEB %d" % lnum)
        else:
            want = (leb_size, 0)
        if (free, dirty) != want:
            errs.append("ltab LEB %d: free/dirty %d/%d, computed %d/%d" % (lnum, free, dirty) + want)
    nh = (mst["nhead_lnum"], mst["nhead_offs"])
    last = max(lpt_used)
    if nh != (last, align(max(o + s for o, s in lpt_used[last]), min_io)):
        errs.append("LPT head (nhead) %s does not match" % (nh,))
    for lnum in range(g.lpt_first, g.lpt_last + 1):
        b = bytes(fs.leb(lnum) or b"")
        end = max((o + s for o, s in lpt_used.get(lnum, [])), default=0)
        if b[end:].strip(b"\xff"):
            errs.append("LPT LEB %d: data after the LPT nodes" % lnum)
    # --- empty areas: log (except commit start), orphans ---
    for lnum in list(range(LOG_LNUM + 1, LOG_LNUM + sb["log_lebs"])) + list(range(g.lpt_last + 1, main_first)):
        if bytes(fs.leb(lnum) or b"").strip(b"\xff"):
            errs.append("LEB %d (log/orphan) not empty" % lnum)
    # --- sequence numbers ---
    top = min(fs.sb_sqnum, fs.mst_nodes[0].sqnum, fs.cs_node.sqnum)
    if max_sq >= top:
        errs.append("sequence number %d of a node >= superblock/master/CS %d" % (max_sq, top))
    # --- files ---
    tree = FileTree(fs, leaves)
    errs += check_tree(tree, mst["highest_inum"])
    stats = dict(leb_cnt=leb_cnt, main_lebs=main_lebs, idx_lebs=len(idx_lebs), leaves=len(leaves),
                 idx_nodes=len(idx_nodes), lpt_nnodes=nnodes, lpt_pnodes=pnodes, inodes=len(tree.inodes),
                 max_sqnum=max(fs.cs_node.sqnum, fs.sb_sqnum))
    return errs, stats


def check_tree(tree, highest_inum):
    errs = []
    links = {}
    subdirs = {}
    for dinum, ents in tree.dents.items():
        if dinum not in tree.inodes:
            errs.append("entries in missing directory %d" % dinum)
            continue
        if not tree.is_dir(dinum):
            errs.append("inum %d has entries but is not a directory" % dinum)
        f = tree.inodes[dinum][1]
        want = INO_NODE_SZ + sum(dent_size(len(n)) for n in ents)
        if f["size"] != want:
            errs.append("directory %d: size %d, entries add up to %d" % (dinum, f["size"], want))
        for name, (tinum, typ, _) in ents.items():
            if tinum not in tree.inodes:
                errs.append("entry %r points to missing inum %d" % (name, tinum))
                continue
            links[tinum] = links.get(tinum, 0) + 1
            if typ == 1:
                subdirs[dinum] = subdirs.get(dinum, 0) + 1
    xattr_inodes = {t for xs in tree.xents.values() for t, _ in xs.values()}
    for inum, (node, f, inline) in tree.inodes.items():
        if inum > highest_inum:
            errs.append("inum %d > highest_inum %d" % (inum, highest_inum))
        if f["creat_sqnum"] > node.sqnum:
            errs.append("inum %d: creat_sqnum > sqnum" % inum)
        if inum in xattr_inodes:
            continue
        isdir = (f["mode"] & S_IFMT) == 0o040000
        want = 2 + subdirs.get(inum, 0) if isdir else links.get(inum, 0)
        if inum != 1 and links.get(inum, 0) == 0:
            errs.append("inum %d without directory entry" % inum)
        if f["nlink"] != want:
            errs.append("inum %d: nlink %d, expected %d" % (inum, f["nlink"], want))
        if f["xattr_cnt"] != len(tree.xents.get(inum, {})):
            errs.append("inum %d: xattr_cnt %d does not match" % (inum, f["xattr_cnt"]))
        nblk = (f["size"] + BLOCK_SIZE - 1) // BLOCK_SIZE
        for blk, dn in tree.data.get(inum, {}).items():
            dsize = struct.unpack_from("<I", dn.raw, 40)[0]
            if blk >= nblk or dsize > BLOCK_SIZE or (blk == nblk - 1 and dsize > f["size"] - blk * BLOCK_SIZE):
                errs.append("inum %d: data block %d beyond the file size" % (inum, blk))
    for inum in tree.data:
        if inum not in tree.inodes:
            errs.append("data node without inode (inum %d)" % inum)
    return errs
