"""Changes to a UBIFS image at node level.

The leaf nodes of the original are kept byte for byte (also their compressed data, LZO is never
re-encoded) in their original order. Changed files get new data nodes and a new inode node at the
place of the old inode node; new files are appended (data nodes, inode, directory entry, like
mkfs.ubifs writes them), the parent directory inode is rewritten in place with the new size.
New sequence numbers continue after the highest one of the original.
"""
import struct
import zlib

from .ubifs_format import (INO, INO_FIELDS, INO_NODE, DATA_NODE, DENT_NODE, INO_NODE_SZ, DATA_NODE_SZ,
                           DENT_NODE_SZ, BLOCK_SIZE, COMPR_NONE, COMPR_ZLIB, COMPR_FL, DATA_KEY,
                           MODE_TO_ITYPE, S_IFMT, align, finish_node, key_ino, key_data,
                           key_dent, key_bytes, key_type)
from .ubifs_read import UbifsError

MIN_COMPR_LEN = 128           # UBIFS_MIN_COMPR_LEN: shorter blocks are stored uncompressed


def dent_size(nlen):
    """CALC_DENT_SIZE(): contribution of one entry to the directory size."""
    return align(DENT_NODE_SZ + nlen + 1, 8)


def compress_block(block, compr):
    """(compr_type, payload) like mkfs.ubifs compress_data(); zlib = raw deflate, 2 KiB window
    (the kernel inflates UBIFS zlib nodes with window bits -11)."""
    if compr == COMPR_ZLIB and len(block) >= MIN_COMPR_LEN:
        c = zlib.compressobj(6, zlib.DEFLATED, -11, 8, zlib.Z_DEFAULT_STRATEGY)
        out = c.compress(block) + c.flush()
        if len(out) < len(block):
            return COMPR_ZLIB, out
    elif compr not in (COMPR_NONE, COMPR_ZLIB):
        raise UbifsError("compression %d not supported for writing" % compr)
    return COMPR_NONE, bytes(block)


class FsEdit:
    def __init__(self, tree):
        self.tree = tree
        fs = tree.fs
        self.default_compr = fs.sb["default_compr"]
        # [key, name, raw] in the order of the original image
        ordered = sorted(tree.leaves, key=lambda x: (x[1].lnum, x[1].offs))
        self.seq = [[k, nm, n.raw] for k, n, nm in ordered]      # memoryviews, no copy
        self.sqnum = max(n.sqnum for _, n, _ in tree.leaves)
        self.highest_inum = fs.mst["highest_inum"]
        self.changes = []

    def _sq(self):
        self.sqnum += 1
        return self.sqnum

    def _index_of(self, key, name=None):
        for i, (k, nm, _) in enumerate(self.seq):
            if k == key and nm == name:
                return i
        raise UbifsError("node %s not found" % (key,))

    def _inode_fields(self, inum):
        raw = self.seq[self._index_of(key_ino(inum))][2]
        return dict(zip(INO_FIELDS, INO.unpack_from(raw, 40))), raw

    def _data_nodes(self, inum, data, compr):
        out = []
        for b in range(0, len(data), BLOCK_SIZE):
            blk = data[b:b + BLOCK_SIZE]
            if blk.count(0) == len(blk):
                continue                                    # hole, like mkfs.ubifs
            ct, payload = compress_block(blk, compr)
            node = bytearray(DATA_NODE_SZ + len(payload))
            key = key_data(inum, b // BLOCK_SIZE)
            node[24:40] = key_bytes(key)
            struct.pack_into("<IHH", node, 40, len(blk), ct, 0)
            node[48:] = payload
            finish_node(node, self._sq(), DATA_NODE)
            out.append([key, None, bytes(node)])
        return out

    def _ino_node(self, inum, f, inline=b""):
        node = bytearray(INO_NODE_SZ + len(inline))
        node[24:40] = key_bytes(key_ino(inum))
        INO.pack_into(node, 40, *[f[k] for k in INO_FIELDS])
        node[INO_NODE_SZ:] = inline
        finish_node(node, self._sq(), INO_NODE)
        return [key_ino(inum), None, bytes(node)]

    def replace_file(self, path, data, compr=COMPR_NONE):
        """New content for an existing regular file (inode number, mode, owner, times kept)."""
        inum = self.tree.lookup(path)
        if inum is None:
            raise UbifsError("%s missing in the original" % path)
        f, raw = self._inode_fields(inum)
        if (f["mode"] & S_IFMT) != 0o100000 or f["nlink"] != 1 or f["data_len"]:
            raise UbifsError("%s is not a plain file" % path)
        pos = self._index_of(key_ino(inum))
        old = [i for i, (k, _, _) in enumerate(self.seq) if k[0] == inum and key_type(k) == DATA_KEY]
        new_data = self._data_nodes(inum, data, compr)
        f = dict(f, size=len(data))
        new_ino = self._ino_node(inum, f)
        old = set(old)
        keep = [e for i, e in enumerate(self.seq[:pos]) if i not in old]
        rest = [e for i, e in enumerate(self.seq[pos + 1:], pos + 1) if i not in old]
        self.seq = keep + new_data + [new_ino] + rest
        self.changes.append(("changed", path, len(data)))

    def add_file(self, path, data, mode, uid=0, gid=0, compr=COMPR_NONE, times=None):
        """New regular file (parent directory must exist, name must be new)."""
        parent, _, name = path.rstrip("/").rpartition("/")
        pinum = self.tree.lookup(parent or "/")
        if pinum is None or not self.tree.is_dir(pinum):
            raise UbifsError("directory %s missing" % parent)
        bname = name.encode()
        if bname in self.tree.dents.get(pinum, {}) or any(
                k[0] == pinum and nm == bname for k, nm, _ in self.seq):
            raise UbifsError("%s already exists" % path)
        pf, _ = self._inode_fields(pinum)
        t = times or (pf["mtime_sec"], pf["mtime_nsec"])
        self.highest_inum += 1
        inum = self.highest_inum
        creat = self._sq()                                   # creat_sqnum, like mkfs.ubifs
        nodes = self._data_nodes(inum, data, compr)
        f = dict(creat_sqnum=creat, size=len(data), atime_sec=t[0], ctime_sec=t[0], mtime_sec=t[0],
                 atime_nsec=t[1], ctime_nsec=t[1], mtime_nsec=t[1], nlink=1, uid=uid, gid=gid,
                 mode=0o100000 | mode, flags=COMPR_FL if self.default_compr != COMPR_NONE else 0, data_len=0,
                 xattr_cnt=0, xattr_size=0, xattr_names=0, compr_type=self.default_compr)
        nodes.append(self._ino_node(inum, f))
        dkey = key_dent(pinum, bname)
        dent = bytearray(DENT_NODE_SZ + len(bname) + 1)
        dent[24:40] = key_bytes(dkey)
        struct.pack_into("<QBBHI", dent, 40, inum, 0, MODE_TO_ITYPE[0o100000], len(bname), 0)
        dent[56:56 + len(bname)] = bname
        finish_node(dent, self._sq(), DENT_NODE)
        nodes.append([dkey, bname, bytes(dent)])
        self.seq += nodes
        # parent directory: size grows by the new entry (nlink unchanged for a file)
        ppos = self._index_of(key_ino(pinum))
        pf2, praw = self._inode_fields(pinum)
        pf2 = dict(pf2, size=pf2["size"] + dent_size(len(bname)))
        inline = praw[INO_NODE_SZ:INO_NODE_SZ + pf2["data_len"]]
        self.seq[ppos] = self._ino_node(pinum, pf2, inline)
        self.changes.append(("new", path, len(data)))
        return inum
