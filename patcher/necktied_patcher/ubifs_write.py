"""UBIFS writer: lays out leaf nodes and builds index, LPT, master, superblock, log and orphan
area exactly like mkfs.ubifs (mtd-utils, write_data/write_index/create_lpt/...).

The leaf nodes are passed in as finished node bytes (common header with sqnum and CRC);
unchanged nodes of the original image are passed through byte for byte.
"""
import struct

from .crc import crc16
from .ubifs_format import (MST, MST_FIELDS, SB_NODE, MST_NODE, IDX_NODE, CS_NODE, SB_NODE_SZ, MST_NODE_SZ,
                           CS_NODE_SZ, LOG_LNUM, LPROPS_INDEX, MST_NO_ORPHS, MAX_NODE_SZ, MIN_WRITE_SZ,
                           FLG_BIGLPT, align, finish_node, pad_bytes, idx_node_sz)

LPT_FANOUT = 4
LPT_FANOUT_SHIFT = 2
LPT_CRC_BITS = 16
LPT_TYPE_BITS = 4
LPT_PNODE, LPT_NNODE, LPT_LTAB, LPT_LSAVE = 0, 1, 2, 3
MIN_LPT_LEBS = 2


class UbifsWriteError(ValueError):
    pass


def fls(x):
    return x.bit_length()


def div_round_up(a, b):
    return (a + b - 1) // b


class LptGeometry:
    """do_calc_lpt_geom() / ubifs_calc_dflt_lpt_geom() of mkfs.ubifs."""

    def __init__(self, leb_size, min_io, max_leb_cnt, log_lebs, orph_lebs, lsave_cnt):
        self.leb_size, self.min_io, self.max_leb_cnt, self.lsave_cnt = leb_size, min_io, max_leb_cnt, lsave_cnt
        main_lebs = max_leb_cnt - 1 - 2 - log_lebs - orph_lebs
        self.lpt_lebs = MIN_LPT_LEBS
        self.main_lebs = main_lebs - self.lpt_lebs
        self.big_lpt = 0
        self._calc()
        if self.lpt_sz > leb_size:
            self.big_lpt = 1
            self._calc()
        for _ in range(64):
            need = div_round_up(self.lpt_sz * 4, leb_size)
            if need > self.lpt_lebs:
                self.lpt_lebs = need
                self.main_lebs = main_lebs - self.lpt_lebs
                self._calc()
                continue
            break
        else:
            raise UbifsWriteError("LPT geometry cannot be determined")
        if self.ltab_sz > leb_size:
            raise UbifsWriteError("LPT ltab too large")
        self.max_main_lebs = self.main_lebs
        self.lpt_first = LOG_LNUM + log_lebs
        self.lpt_last = self.lpt_first + self.lpt_lebs - 1
        self.main_first = self.lpt_first + self.lpt_lebs + orph_lebs

    def _calc(self):
        max_pnode_cnt = div_round_up(self.main_lebs, LPT_FANOUT)
        self.lpt_hght = 1
        n = LPT_FANOUT
        while n < max_pnode_cnt:
            self.lpt_hght += 1
            n <<= LPT_FANOUT_SHIFT
        self.pnode_cnt = div_round_up(self.main_lebs, LPT_FANOUT)
        n = div_round_up(self.pnode_cnt, LPT_FANOUT)
        self.nnode_cnt = n
        for _ in range(1, self.lpt_hght):
            n = div_round_up(n, LPT_FANOUT)
            self.nnode_cnt += n
        self.space_bits = fls(self.leb_size) - 3
        self.lpt_lnum_bits = fls(self.lpt_lebs)
        self.lpt_offs_bits = fls(self.leb_size - 1)
        self.lpt_spc_bits = fls(self.leb_size)
        self.pcnt_bits = fls(div_round_up(self.max_leb_cnt, LPT_FANOUT) - 1)
        self.lnum_bits = fls(self.max_leb_cnt - 1)
        big = self.pcnt_bits if self.big_lpt else 0
        self.pnode_sz = (LPT_CRC_BITS + LPT_TYPE_BITS + big + (self.space_bits * 2 + 1) * LPT_FANOUT + 7) // 8
        self.nnode_sz = (LPT_CRC_BITS + LPT_TYPE_BITS + big + (self.lpt_lnum_bits + self.lpt_offs_bits)
                         * LPT_FANOUT + 7) // 8
        self.ltab_sz = (LPT_CRC_BITS + LPT_TYPE_BITS + self.lpt_lebs * self.lpt_spc_bits * 2 + 7) // 8
        self.lsave_sz = (LPT_CRC_BITS + LPT_TYPE_BITS + self.lnum_bits * self.lsave_cnt + 7) // 8
        sz = self.pnode_cnt * self.pnode_sz + self.nnode_cnt * self.nnode_sz + self.ltab_sz
        if self.big_lpt:
            sz += self.lsave_sz
        self.lpt_sz = sz
        waste = max(self.pnode_sz, self.nnode_sz)
        s = sz + waste
        tot = waste
        while s > self.leb_size:
            s += waste
            s -= self.leb_size
            tot += waste
        tot += align(s, self.min_io) - s
        self.lpt_sz += tot


class BitPacker:
    """pack_bits(): fields LSB first, behind a 16-bit CRC slot."""

    def __init__(self):
        self.val = 0
        self.pos = 0

    def put(self, v, bits):
        if v >> bits:
            raise UbifsWriteError("LPT field %d does not fit in %d bits" % (v, bits))
        self.val |= v << self.pos
        self.pos += bits

    def node(self, size):
        body = self.val.to_bytes(size - 2, "little")
        return struct.pack("<H", crc16(body)) + body


def calc_nnode_num(row, col):
    num = 1
    while row:
        row -= 1
        bits = col & (LPT_FANOUT - 1)
        col >>= LPT_FANOUT_SHIFT
        num = (num << LPT_FANOUT_SHIFT) | bits
    return num


def create_lpt(g, lps, main_lebs):
    """ubifs_create_lpt() of mtd-utils 2.x: pnodes for the used main LEBs, nnodes over
    lpt_hght rows, lsave (big LPT only), ltab. Returns (lpt LEB contents, positions)."""
    lpt_lebs = []
    ltab = [[g.leb_size, 0] for _ in range(g.lpt_lebs)]
    lnum = g.lpt_first
    buf = bytearray()
    pos = {}

    def next_leb():
        nonlocal lnum, buf
        alen = align(len(buf), g.min_io)
        ltab[lnum - g.lpt_first] = [g.leb_size - alen, alen - len(buf)]
        lpt_lebs.append(bytes(buf))
        lnum += 1
        buf = bytearray()
        if lnum > g.lpt_last:
            raise UbifsWriteError("LPT does not fit in %d LEBs" % g.lpt_lebs)

    cnt = div_round_up(main_lebs, LPT_FANOUT)
    blnum, boffs, bcnt, bsz = lnum, 0, cnt, g.pnode_sz
    for i in range(cnt):
        if len(buf) + g.pnode_sz > g.leb_size:
            next_leb()
        bp = BitPacker()
        bp.put(LPT_PNODE, LPT_TYPE_BITS)
        if g.big_lpt:
            bp.put(i, g.pcnt_bits)
        for j in range(LPT_FANOUT):
            k = (i << LPT_FANOUT_SHIFT) + j
            free, dirty, flags = lps[k] if k < len(lps) else (g.leb_size, 0, 0)
            bp.put(free >> 3, g.space_bits)
            bp.put(dirty >> 3, g.space_bits)
            bp.put(1 if flags & LPROPS_INDEX else 0, 1)
        buf += bp.node(g.pnode_sz)
    row = g.lpt_hght - 1
    while True:
        cnt = div_round_up(cnt, LPT_FANOUT) or 1
        for i in range(cnt):
            if len(buf) + g.nnode_sz > g.leb_size:
                next_leb()
            if row == 0:
                pos["lpt"] = (lnum, len(buf))
            bp = BitPacker()
            bp.put(LPT_NNODE, LPT_TYPE_BITS)
            if g.big_lpt:
                bp.put(calc_nnode_num(row, i), g.pcnt_bits)
            for j in range(LPT_FANOUT):
                if bcnt:
                    if boffs + bsz > g.leb_size:
                        blnum += 1
                        boffs = 0
                    bl, bo = blnum, boffs
                    boffs += bsz
                    bcnt -= 1
                else:
                    bl, bo = 0, 0
                if bl == 0:
                    bl = g.lpt_last + 1
                bp.put(bl - g.lpt_first, g.lpt_lnum_bits)
                bp.put(bo, g.lpt_offs_bits)
            buf += bp.node(g.nnode_sz)
        if row == 0:
            break
        bcnt, bsz = cnt, g.nnode_sz
        row -= 1
    if g.big_lpt:
        if len(buf) + g.lsave_sz > g.leb_size:
            next_leb()
        pos["lsave"] = (lnum, len(buf))
        bp = BitPacker()
        bp.put(LPT_LSAVE, LPT_TYPE_BITS)
        for i in range(g.lsave_cnt):
            bp.put(g.main_first + i if i < main_lebs else g.main_first, g.lnum_bits)
        buf += bp.node(g.lsave_sz)
    else:
        pos["lsave"] = (0, 0)
    if len(buf) + g.ltab_sz > g.leb_size:
        next_leb()
    pos["ltab"] = (lnum, len(buf))
    ln = len(buf) + g.ltab_sz
    alen = align(ln, g.min_io)
    ltab[lnum - g.lpt_first] = [g.leb_size - alen, alen - ln]
    bp = BitPacker()
    bp.put(LPT_LTAB, LPT_TYPE_BITS)
    for free, dirty in ltab:
        bp.put(free, g.lpt_spc_bits)
        bp.put(dirty, g.lpt_spc_bits)
    buf += bp.node(g.ltab_sz)
    lpt_lebs.append(bytes(buf))
    pos["nhead"] = (lnum, alen)
    while len(lpt_lebs) < g.lpt_lebs:
        lpt_lebs.append(b"")
    return lpt_lebs, pos


class Writer:
    """mkfs.ubifs layout engine. Usage: w = Writer(sb_fields, sb_raw); w.add_leaf(...)...;
    lebs = w.finish(highest_inum, next_sqnum)."""

    def __init__(self, sb, sb_raw):
        self.sb = sb
        self.sb_raw = bytes(sb_raw)
        self.leb_size = sb["leb_size"]
        self.min_io = sb["min_io_size"]
        self.fanout = sb["fanout"]
        self.g = LptGeometry(self.leb_size, self.min_io, sb["max_leb_cnt"], sb["log_lebs"], sb["orph_lebs"],
                             sb["lsave_cnt"])
        if self.g.lpt_lebs != sb["lpt_lebs"] or bool(self.g.big_lpt) != bool(sb["flags"] & FLG_BIGLPT):
            raise UbifsWriteError("LPT geometry (%d LEBs, big %d) differs from the original (%d LEBs, flags %#x)"
                                  % (self.g.lpt_lebs, self.g.big_lpt, sb["lpt_lebs"], sb["flags"]))
        self.main_first = self.g.main_first
        self.lebs = {}
        self.lprops = {}
        self.lst = dict(total_free=0, total_dirty=0, total_used=0, total_dead=0, total_dark=0, idx_lebs=0,
                        empty_lebs=0)
        self.dead_wm = align(MIN_WRITE_SZ, self.min_io)
        self.dark_wm = align(MAX_NODE_SZ, self.min_io)
        self.head_lnum = self.main_first
        self.head_offs = 0
        self.head_flags = 0
        self.buf = bytearray()
        self.idx = []           # (key, name, lnum, offs, len)
        self.max_leb_cnt = sb["max_leb_cnt"]

    # --- head handling (reserve_space / flush_nodes / set_lprops) ---

    def _calc_dark(self, spc):
        if spc < self.dark_wm:
            return spc
        if spc - self.dark_wm < MIN_WRITE_SZ:
            return spc - MIN_WRITE_SZ
        return self.dark_wm

    def _set_lprops(self, lnum, offs, flags):
        free = self.leb_size - align(offs, max(self.min_io, 8))
        dirty = self.leb_size - free - align(offs, 8)
        self.lprops[lnum] = (free, dirty, flags)
        self.lst["total_free"] += free
        self.lst["total_dirty"] += dirty
        if flags & LPROPS_INDEX:
            self.lst["idx_lebs"] += 1
        else:
            spc = free + dirty
            if spc < self.dead_wm:
                self.lst["total_dead"] += spc
            else:
                self.lst["total_dark"] += self._calc_dark(spc)
            self.lst["total_used"] += self.leb_size - spc

    def _flush(self):
        if not self.head_offs:
            return
        ln = align(self.head_offs, self.min_io)
        self.buf += pad_bytes(ln - self.head_offs)
        self._put_leb(self.head_lnum, self.buf)
        self._set_lprops(self.head_lnum, self.head_offs, self.head_flags)
        self.head_lnum += 1
        self.head_offs = 0
        self.buf = bytearray()

    def _put_leb(self, lnum, data):
        if lnum >= self.max_leb_cnt:
            raise UbifsWriteError("file system too large: more than %d LEBs needed" % self.max_leb_cnt)
        self.lebs[lnum] = bytes(data)

    def _reserve(self, ln):
        if ln > self.leb_size - self.head_offs:
            self._flush()
        lnum, offs = self.head_lnum, self.head_offs
        self.head_offs += align(ln, 8)
        return lnum, offs

    def _append(self, node):
        ln = len(node)
        lnum, offs = self._reserve(ln)
        self.buf += node
        self.buf += b"\xff" * (align(ln, 8) - ln)
        return lnum, offs

    def add_leaf(self, key, name, node):
        """Append a finished leaf node (bytes) to the main area and record it for the index."""
        lnum, offs = self._append(node)
        self.idx.append((key, name, lnum, offs, len(node)))

    # --- the rest of mkfs ---

    def _write_index(self, sqnum):
        self.head_flags = LPROPS_INDEX
        ents = sorted(self.idx, key=lambda e: (e[0], e[1] or b""))
        self.sorted_index = ents
        fan = self.fanout
        idx_sz = idx_node_sz(fan)
        index_size = 0
        root = None

        def add_idx(level, branches):
            nonlocal sqnum, index_size, root
            node = bytearray(idx_node_sz(len(branches)))
            struct.pack_into("<HH", node, 24, len(branches), level)
            o = 28
            for key, lnum, offs, ln in branches:
                struct.pack_into("<IIIII", node, o, lnum, offs, ln, key[0], key[1])
                o += 20
            sqnum += 1
            finish_node(node, sqnum, IDX_NODE)
            lnum, offs = self._append(node)
            index_size += align(len(node), 8)
            root = (lnum, offs, len(node))

        n = len(ents)
        if n == 0:
            raise UbifsWriteError("empty index")
        cnt = div_round_up(n, fan)
        blnum, boffs = self.head_lnum, self.head_offs
        p = 0
        child_cnt = 0
        for i in range(cnt):
            child_cnt = (n % fan or fan) if i == cnt - 1 else fan
            add_idx(0, [(e[0], e[2], e[3], e[4]) for e in ents[p:p + child_cnt]])
            p += child_cnt
        level = 0
        pstep = 1
        while cnt > 1:
            blast_len = idx_node_sz(child_cnt)
            bcnt = cnt
            cnt = div_round_up(cnt, fan) or 1
            level += 1
            pstep *= fan
            p = 0
            for i in range(cnt):
                child_cnt = (bcnt % fan or fan) if i == cnt - 1 else fan
                br = []
                for j in range(child_cnt):
                    bn = i * fan + j
                    blen = blast_len if bn == bcnt - 1 else idx_sz
                    if boffs + blen > self.leb_size:
                        blnum += 1
                        boffs = 0
                    br.append((ents[p][0], blnum, boffs, blen))
                    boffs += align(blen, 8)
                    p += pstep
                add_idx(level, br)
        self.ihead = (self.head_lnum, align(self.head_offs, self.min_io))
        self._flush()
        self.root = root
        self.index_size = index_size
        return sqnum

    def finish(self, highest_inum, sqnum):
        """Flush data, GC LEB, index, LPT, superblock, master, log, orphans.
        sqnum = highest sequence number used so far. Returns [LEB bytes] for lnum 0..leb_cnt-1."""
        self._flush()
        # set_gc_lnum
        self.gc_lnum = self.head_lnum
        self.head_lnum += 1
        self._put_leb(self.gc_lnum, b"")
        self._set_lprops(self.gc_lnum, 0, 0)
        self.lst["empty_lebs"] += 1
        sqnum = self._write_index(sqnum)
        # finalize_leb_cnt
        self.leb_cnt = self.head_lnum
        if self.leb_cnt > self.max_leb_cnt:
            raise UbifsWriteError("max_leb_cnt too small (%d needed)" % self.leb_cnt)
        main_lebs = self.leb_cnt - self.main_first
        g = self.g
        lps = [self.lprops[self.main_first + k] for k in range(main_lebs)]
        lpt_lebs, pos = create_lpt(g, lps, main_lebs)
        for i, d in enumerate(lpt_lebs):
            self._put_leb(g.lpt_first + i, d)
        # superblock (template of the original, leb_cnt and sqnum new)
        sqnum += 1
        sb = bytearray(self.sb_raw[:SB_NODE_SZ])
        struct.pack_into("<I", sb, 40, self.leb_cnt)
        finish_node(sb, sqnum, SB_NODE)
        self._put_leb(0, self._padded(sb))
        # master node, twice
        m = dict(highest_inum=highest_inum, cmt_no=0, flags=MST_NO_ORPHS, log_lnum=LOG_LNUM,
                 root_lnum=self.root[0], root_offs=self.root[1], root_len=self.root[2], gc_lnum=self.gc_lnum,
                 ihead_lnum=self.ihead[0], ihead_offs=self.ihead[1], index_size=self.index_size,
                 lpt_lnum=pos["lpt"][0], lpt_offs=pos["lpt"][1], nhead_lnum=pos["nhead"][0],
                 nhead_offs=pos["nhead"][1], ltab_lnum=pos["ltab"][0], ltab_offs=pos["ltab"][1],
                 lsave_lnum=pos["lsave"][0], lsave_offs=pos["lsave"][1], lscan_lnum=self.main_first,
                 leb_cnt=self.leb_cnt, **self.lst)
        self.mst = m
        for lnum in (1, 2):
            sqnum += 1
            node = bytearray(MST_NODE_SZ)
            MST.pack_into(node, 24, *[m[f] for f in MST_FIELDS])
            finish_node(node, sqnum, MST_NODE)
            self._put_leb(lnum, self._padded(node))
        # log: one commit start node, other log LEBs empty
        sqnum += 1
        cs = bytearray(CS_NODE_SZ)
        finish_node(cs, sqnum, CS_NODE)
        self._put_leb(LOG_LNUM, self._padded(cs))
        for lnum in range(LOG_LNUM + 1, LOG_LNUM + self.sb["log_lebs"]):
            self._put_leb(lnum, b"")
        for lnum in range(g.lpt_last + 1, self.main_first):
            self._put_leb(lnum, b"")                    # orphan area
        self.max_sqnum = sqnum
        missing = [i for i in range(self.leb_cnt) if i not in self.lebs]
        if missing:
            raise UbifsWriteError("LEBs without content: %s" % missing[:5])
        return [self.lebs[i] for i in range(self.leb_cnt)]

    def _padded(self, node):
        ln = len(node)
        alen = align(ln, 8)
        return bytes(node) + b"\xff" * (alen - ln) + pad_bytes(align(ln, self.min_io) - alen)
