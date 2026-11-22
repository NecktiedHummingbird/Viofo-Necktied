"""UBIFS reader: superblock, master node, index tree (TNC on flash), leaf nodes, file tree.

Only what the patcher needs: the image must be a committed file system with an empty journal
(as produced by mkfs.ubifs); anything else is refused, never guessed.
"""
import struct
import zlib

from . import lzo
from .crc import crc32_raw
from .ubifs_format import (CH, CH_SZ, NODE_MAGIC, SB, SB_FIELDS, MST, MST_FIELDS, INO, INO_FIELDS,
                           SB_NODE, MST_NODE, IDX_NODE, CS_NODE, INO_NODE, DATA_NODE, DENT_NODE, XENT_NODE,
                           PAD_NODE, NODE_NAMES, INO_KEY, DATA_KEY, DENT_KEY, XENT_KEY, KEY_BLOCK_BITS,
                           ROOT_INO, LOG_LNUM, MST_LNUM, COMPR_NONE, COMPR_LZO, COMPR_ZLIB, BRANCH_SZ, SK_LEN,
                           IDX_NODE_SZ, PAD_NODE_SZ, PADDING_BYTE, BLOCK_SIZE, S_IFMT, r5_hash, key_type)


class UbifsError(ValueError):
    pass


def decompress(compr, payload, size):
    if compr == COMPR_NONE:
        out = bytes(payload)
    elif compr == COMPR_LZO:
        out = lzo.decompress(payload)
    elif compr == COMPR_ZLIB:
        out = zlib.decompress(bytes(payload), -15)     # UBIFS: raw deflate stream
    else:
        raise UbifsError("compression %d not supported" % compr)
    if len(out) != size:
        raise UbifsError("data node: %d instead of %d bytes after decompression" % (len(out), size))
    return out


class Node:
    __slots__ = ("lnum", "offs", "len", "type", "sqnum", "raw")

    def __init__(self, lnum, offs, ln, typ, sqnum, raw):
        self.lnum, self.offs, self.len, self.type, self.sqnum, self.raw = lnum, offs, ln, typ, sqnum, raw

    def key(self):
        return struct.unpack_from("<II", self.raw, 24)


class Ubifs:
    """A UBIFS volume given as a list of LEB contents (memoryview/bytes, None = unmapped)."""

    def __init__(self, lebs, leb_size):
        self.lebs = lebs
        self.leb_size = leb_size
        sb = self.read_node(0, 0, SB_NODE)
        self.sb_raw = sb.raw
        self.sb_sqnum = sb.sqnum
        self.sb = dict(zip(SB_FIELDS, SB.unpack_from(sb.raw, 24)))
        if self.sb["leb_size"] != leb_size:
            raise UbifsError("LEB size UBIFS %d != UBI %d" % (self.sb["leb_size"], leb_size))
        if self.sb["key_hash"] != 0 or self.sb["key_fmt"] != 0:
            raise UbifsError("only key hash r5 / simple key format supported")
        if self.sb["fmt_version"] != 4 or self.sb["flags"] & ~0x02:
            raise UbifsError("UBIFS format %d / flags %#x not supported" % (self.sb["fmt_version"],
                                                                                 self.sb["flags"]))
        self.min_io = self.sb["min_io_size"]
        self.mst_nodes = [self._last_master(MST_LNUM), self._last_master(MST_LNUM + 1)]
        m1, m2 = self.mst_nodes
        if m1 is None or m2 is None:
            raise UbifsError("master node missing")
        if bytes(m1.raw[8:]) != bytes(m2.raw[8:]) and bytes(m1.raw[24:]) != bytes(m2.raw[24:]):
            raise UbifsError("the two master nodes differ")
        self.mst = dict(zip(MST_FIELDS, MST.unpack_from(m1.raw, 24)))
        self.log_lebs = self.sb["log_lebs"]
        self.lpt_first = LOG_LNUM + self.log_lebs
        self.main_first = self.lpt_first + self.sb["lpt_lebs"] + self.sb["orph_lebs"]
        self._check_journal_empty()

    # --- raw access ---

    def leb(self, lnum):
        if lnum >= len(self.lebs) or self.lebs[lnum] is None:
            return None
        return self.lebs[lnum]

    def read_node(self, lnum, offs, want_type=None, want_len=None):
        b = self.leb(lnum)
        if b is None:
            raise UbifsError("LEB %d not mapped" % lnum)
        if offs + CH_SZ > len(b):
            raise UbifsError("node %d:%d outside the LEB" % (lnum, offs))
        magic, crc, sqnum, ln, typ, grp = CH.unpack_from(b, offs)
        if magic != NODE_MAGIC:
            raise UbifsError("no node at %d:%d" % (lnum, offs))
        if offs + ln > len(b) or ln < CH_SZ:
            raise UbifsError("invalid node length %d at %d:%d" % (ln, lnum, offs))
        raw = b[offs:offs + ln]
        if crc32_raw(raw[8:]) != crc:
            raise UbifsError("CRC wrong at %d:%d" % (lnum, offs))
        if want_type is not None and typ != want_type:
            raise UbifsError("node %d:%d has type %s instead of %s" % (lnum, offs, NODE_NAMES[typ] if typ < 14 else typ,
                                                                   NODE_NAMES[want_type]))
        if want_len is not None and ln != want_len:
            raise UbifsError("node %d:%d has length %d instead of %d" % (lnum, offs, ln, want_len))
        return Node(lnum, offs, ln, typ, sqnum, raw)

    def scan_leb(self, lnum):
        """All nodes of a LEB in order (like ubifs_scan): [Node], stops at the 0xFF tail.
        Padding nodes / padding bytes are skipped, anything else raises."""
        b = self.leb(lnum)
        out = []
        if b is None:
            return out
        offs = 0
        n = len(b)
        while offs < n:
            if b[offs] == 0xFF and bytes(b[offs:]) == b"\xff" * (n - offs):
                break
            if b[offs] == PADDING_BYTE and struct.unpack_from("<I", b, offs)[0] != NODE_MAGIC:
                # padding bytes up to the next min. I/O unit
                nxt = (offs // self.min_io + 1) * self.min_io
                if bytes(b[offs:nxt]) != bytes([PADDING_BYTE]) * (nxt - offs):
                    raise UbifsError("LEB %d: unexpected bytes at %d" % (lnum, offs))
                offs = nxt
                continue
            node = self.read_node(lnum, offs)
            if node.type == PAD_NODE:
                pad_len = struct.unpack_from("<I", node.raw, 24)[0]
                offs += PAD_NODE_SZ + pad_len
                continue
            out.append(node)
            offs += (node.len + 7) & ~7
        return out

    def _last_master(self, lnum):
        nodes = [x for x in self.scan_leb(lnum) if x.type == MST_NODE]
        return nodes[-1] if nodes else None

    def _check_journal_empty(self):
        """The log must hold nothing but the commit start node (no journal to replay)."""
        nodes = self.scan_leb(self.mst["log_lnum"])
        if len(nodes) != 1 or nodes[0].type != CS_NODE:
            raise UbifsError("journal not empty (log LEB %d: %s) - image not freshly created"
                             % (self.mst["log_lnum"], [NODE_NAMES[x.type] for x in nodes]))
        for lnum in range(LOG_LNUM, LOG_LNUM + self.log_lebs):
            if lnum != self.mst["log_lnum"] and self.scan_leb(lnum):
                raise UbifsError("journal not empty (log LEB %d)" % lnum)
        self.cs_node = nodes[0]

    # --- index ---

    def walk_index(self):
        """(leaves, idx_nodes): leaves = [(key, lnum, offs, len)] in index order,
        idx_nodes = [(lnum, offs, len, level)]. Checks key order and levels."""
        leaves, idx_nodes = [], []
        # recursive in-order walk (depth = index height, a handful of levels)

        def visit(lnum, offs, ln, want_level):
            node = self.read_node(lnum, offs, IDX_NODE, ln)
            child_cnt, level = struct.unpack_from("<HH", node.raw, CH_SZ)
            if want_level is not None and level != want_level:
                raise UbifsError("index node %d:%d: level %d instead of %d" % (lnum, offs, level, want_level))
            if ln != IDX_NODE_SZ + child_cnt * (BRANCH_SZ + SK_LEN) or child_cnt == 0:
                raise UbifsError("index node %d:%d: length/child count wrong" % (lnum, offs))
            idx_nodes.append((lnum, offs, ln, level))
            for j in range(child_cnt):
                bo = IDX_NODE_SZ + j * (BRANCH_SZ + SK_LEN)
                blnum, boffs, blen = struct.unpack_from("<III", node.raw, bo)
                key = struct.unpack_from("<II", node.raw, bo + BRANCH_SZ)
                if level == 0:
                    leaves.append((key, blnum, boffs, blen))
                else:
                    first = len(leaves)
                    visit(blnum, boffs, blen, level - 1)
                    if leaves[first][0] != key:
                        raise UbifsError("index node %d:%d: key of branch %d does not match the first "
                                         "leaf" % (lnum, offs, j))
        visit(self.mst["root_lnum"], self.mst["root_offs"], self.mst["root_len"], None)
        for a, b in zip(leaves, leaves[1:]):
            if a[0] > b[0]:
                raise UbifsError("index not sorted: %s > %s" % (a[0], b[0]))
        return leaves, idx_nodes

    def leaf_nodes(self):
        """Read and check all leaf nodes referenced by the index: [(key, Node, name or None)]."""
        leaves, self.idx_nodes = self.walk_index()
        out = []
        for key, lnum, offs, ln in leaves:
            node = self.read_node(lnum, offs, want_len=ln)
            nkey = node.key()
            if nkey != key:
                raise UbifsError("leaf %d:%d: key %s in node, %s in index" % (lnum, offs, nkey, key))
            kt = key_type(key)
            want = {INO_KEY: INO_NODE, DATA_KEY: DATA_NODE, DENT_KEY: DENT_NODE, XENT_KEY: XENT_NODE}.get(kt)
            if want is None or node.type != want:
                raise UbifsError("leaf %d:%d: node type %d does not match key type %d" % (lnum, offs,
                                                                                               node.type, kt))
            name = None
            if node.type in (DENT_NODE, XENT_NODE):
                nlen = struct.unpack_from("<H", node.raw, 50)[0]
                name = bytes(node.raw[56:56 + nlen])
                if r5_hash(name) != key[1] & ((1 << KEY_BLOCK_BITS) - 1):
                    raise UbifsError("directory entry %r: hash does not match the key" % name)
            out.append((key, node, name))
        return out


class FileTree:
    """Inodes, directory entries and data nodes of a UBIFS, with path lookup."""

    def __init__(self, fs, leaves=None):
        self.fs = fs
        self.leaves = leaves if leaves is not None else fs.leaf_nodes()
        self.inodes = {}       # inum -> (Node, fields dict, inline data)
        self.dents = {}        # dir inum -> {name: (inum, type, Node)}
        self.data = {}         # inum -> {block: Node}
        self.xents = {}        # host inum -> {name: (xattr inum, Node)}
        for key, node, name in self.leaves:
            kt = key_type(key)
            inum = key[0]
            if kt == INO_KEY:
                f = dict(zip(INO_FIELDS, INO.unpack_from(node.raw, 40)))
                self.inodes[inum] = (node, f, bytes(node.raw[160:160 + f["data_len"]]))
            elif kt == DATA_KEY:
                self.data.setdefault(inum, {})[key[1] & ((1 << KEY_BLOCK_BITS) - 1)] = node
            elif kt == DENT_KEY:
                tinum, typ = struct.unpack_from("<QxB", node.raw, 40)
                d = self.dents.setdefault(inum, {})
                if name in d:
                    raise UbifsError("duplicate directory entry %r" % name)
                d[name] = (tinum, typ, node)
            elif kt == XENT_KEY:
                tinum = struct.unpack_from("<Q", node.raw, 40)[0]
                self.xents.setdefault(inum, {})[name] = (tinum, node)
        for host, xs in self.xents.items():
            for name, (tinum, _) in xs.items():
                if tinum not in self.inodes:
                    raise UbifsError("xattr %r of inum %d without inode" % (name, host))
        if ROOT_INO not in self.inodes:
            raise UbifsError("root inode missing")

    def lookup(self, path):
        inum = ROOT_INO
        for comp in [c for c in path.strip("/").split("/") if c]:
            ent = self.dents.get(inum, {}).get(comp.encode())
            if ent is None:
                return None
            inum = ent[0]
        return inum

    def read_file(self, inum):
        node, f, inline = self.inodes[inum]
        size = f["size"]
        blocks = self.data.get(inum, {})
        out = bytearray()
        nblk = (size + BLOCK_SIZE - 1) // BLOCK_SIZE
        for b in range(nblk):
            want = min(BLOCK_SIZE, size - b * BLOCK_SIZE)
            dn = blocks.get(b)
            if dn is None:
                out += bytes(want)                  # hole
                continue
            dsize, compr = struct.unpack_from("<IH", dn.raw, 40)
            chunk = decompress(compr, dn.raw[48:], dsize)
            out += chunk + bytes(want - len(chunk)) if len(chunk) < want else chunk[:want]
        if any(b >= nblk for b in blocks):
            raise UbifsError("data node beyond end of file (inum %d)" % inum)
        return bytes(out)

    def walk(self):
        """Yield (path, inum) for every directory entry, depth first, sorted by name."""
        seen = set()
        stack = [("", ROOT_INO)]
        while stack:
            path, inum = stack.pop()
            for name in sorted(self.dents.get(inum, {}), reverse=True):
                tinum, typ, _ = self.dents[inum][name]
                p = path + "/" + name.decode("utf-8", "surrogateescape")
                yield p, tinum
                if typ == 1:
                    if tinum in seen:
                        raise UbifsError("directory loop at %s" % p)
                    seen.add(tinum)
                    stack.append((p, tinum))

    def xattrs(self, inum):
        """{name: value} of an inode (value = inline data of the xattr inode)."""
        return {n: self.inodes[t][2] for n, (t, _) in sorted(self.xents.get(inum, {}).items())}

    def is_dir(self, inum):
        return (self.inodes[inum][1]["mode"] & S_IFMT) == 0o040000
