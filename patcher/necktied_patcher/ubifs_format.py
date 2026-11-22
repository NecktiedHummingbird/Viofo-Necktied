"""UBIFS on-flash format (Linux fs/ubifs/ubifs-media.h), simple key format, r5 hash."""
import struct

from .crc import crc32_raw

NODE_MAGIC = 0x06101831
CH = struct.Struct("<IIQIBB2x")          # magic, crc, sqnum, len, node_type, group_type
CH_SZ = 24

INO_NODE, DATA_NODE, DENT_NODE, XENT_NODE, TRUN_NODE, PAD_NODE, SB_NODE, MST_NODE, REF_NODE, \
    IDX_NODE, CS_NODE, ORPH_NODE, AUTH_NODE, SIG_NODE = range(14)
NODE_NAMES = ["ino", "data", "dent", "xent", "trun", "pad", "sb", "mst", "ref", "idx", "cs", "orph",
              "auth", "sig"]

INO_KEY, DATA_KEY, DENT_KEY, XENT_KEY = 0, 1, 2, 3
KEY_BLOCK_BITS = 29
KEY_HASH_MASK = (1 << 29) - 1

INO_NODE_SZ = 160
DATA_NODE_SZ = 48
DENT_NODE_SZ = 56
IDX_NODE_SZ = 28
BRANCH_SZ = 12
SK_LEN = 8
PAD_NODE_SZ = 28
SB_NODE_SZ = 4096
MST_NODE_SZ = 512
CS_NODE_SZ = 32
PADDING_BYTE = 0xCE
BLOCK_SIZE = 4096
MAX_INO_DATA = 4096
MAX_NODE_SZ = INO_NODE_SZ + MAX_INO_DATA      # UBIFS_MAX_NODE_SZ (largest node: inode with data)
MIN_WRITE_SZ = DATA_NODE_SZ + 8

COMPR_NONE, COMPR_LZO, COMPR_ZLIB, COMPR_ZSTD = 0, 1, 2, 3
COMPR_NAMES = {0: "none", 1: "lzo", 2: "zlib", 3: "zstd"}
COMPR_FL = 0x01

ROOT_INO = 1
SB_LNUM, MST_LNUM, LOG_LNUM = 0, 1, 3
MST_NO_ORPHS = 2
FLG_BIGLPT = 0x02
LPROPS_INDEX = 32

# directory entry types (UBIFS_ITYPE_*)
ITYPE_REG, ITYPE_DIR, ITYPE_LNK, ITYPE_BLK, ITYPE_CHR, ITYPE_FIFO, ITYPE_SOCK = range(7)
S_IFMT = 0o170000
MODE_TO_ITYPE = {0o100000: ITYPE_REG, 0o040000: ITYPE_DIR, 0o120000: ITYPE_LNK, 0o060000: ITYPE_BLK,
                 0o020000: ITYPE_CHR, 0o010000: ITYPE_FIFO, 0o140000: ITYPE_SOCK}

# superblock fields from offset 24 (after the common header)
SB = struct.Struct("<2xBBIIIIIQIIIIIIIH2xIIQI16sI")
SB_FIELDS = ("key_hash", "key_fmt", "flags", "min_io_size", "leb_size", "leb_cnt", "max_leb_cnt",
             "max_bud_bytes", "log_lebs", "lpt_lebs", "orph_lebs", "jhead_cnt", "fanout", "lsave_cnt",
             "fmt_version", "default_compr", "rp_uid", "rp_gid", "rp_size", "time_gran", "uuid",
             "ro_compat_version")
# master node fields from offset 24
MST = struct.Struct("<QQIIIIIIIIQQQQQQIIIIIIIIIIII")
MST_FIELDS = ("highest_inum", "cmt_no", "flags", "log_lnum", "root_lnum", "root_offs", "root_len",
              "gc_lnum", "ihead_lnum", "ihead_offs", "index_size", "total_free", "total_dirty",
              "total_used", "total_dead", "total_dark", "lpt_lnum", "lpt_offs", "nhead_lnum",
              "nhead_offs", "ltab_lnum", "ltab_offs", "lsave_lnum", "lsave_offs", "lscan_lnum",
              "empty_lebs", "idx_lebs", "leb_cnt")
INO = struct.Struct("<QQQQQIIIIIIIIIII4xIH")        # from offset 40 (after ch + key)
INO_FIELDS = ("creat_sqnum", "size", "atime_sec", "ctime_sec", "mtime_sec", "atime_nsec", "ctime_nsec",
              "mtime_nsec", "nlink", "uid", "gid", "mode", "flags", "data_len", "xattr_cnt",
              "xattr_size", "xattr_names", "compr_type")


def align(x, a):
    return (x + a - 1) // a * a


def r5_hash(name):
    """key_r5_hash() of the kernel (signed chars), values 0..2 are reserved."""
    a = 0
    for c in name:
        s = c - 256 if c > 127 else c
        a = (a + (s << 4)) & 0xFFFFFFFF
        a = (a + (s >> 4)) & 0xFFFFFFFF
        a = (a * 11) & 0xFFFFFFFF
    a &= KEY_HASH_MASK
    if a <= 2:
        a += 3
    return a


def key_ino(inum):
    return (inum, INO_KEY << KEY_BLOCK_BITS)


def key_data(inum, block):
    return (inum, (DATA_KEY << KEY_BLOCK_BITS) | block)


def key_dent(inum, name):
    return (inum, (DENT_KEY << KEY_BLOCK_BITS) | r5_hash(name))


def key_type(key):
    return key[1] >> KEY_BLOCK_BITS


def key_bytes(key, size=16):
    return struct.pack("<II", key[0], key[1]) + bytes(size - 8)


def unpack_key(buf, off=0):
    return struct.unpack_from("<II", buf, off)


def finish_node(node, sqnum, node_type):
    """Fill the common header (magic, sqnum, len, type, crc) of a node in a bytearray."""
    CH.pack_into(node, 0, NODE_MAGIC, 0, sqnum, len(node), node_type, 0)
    struct.pack_into("<I", node, 4, crc32_raw(memoryview(node)[8:]))
    return node


def pad_bytes(pad):
    """ubifs_pad(): padding node (if it fits) or 0xCE bytes, `pad` bytes long."""
    if pad >= PAD_NODE_SZ:
        n = bytearray(PAD_NODE_SZ)
        CH.pack_into(n, 0, NODE_MAGIC, 0, 0, PAD_NODE_SZ, PAD_NODE, 0)
        struct.pack_into("<I", n, 24, pad - PAD_NODE_SZ)
        struct.pack_into("<I", n, 4, crc32_raw(memoryview(n)[8:]))
        return bytes(n) + bytes(pad - PAD_NODE_SZ)
    return bytes([PADDING_BYTE]) * pad


def idx_node_sz(child_cnt):
    return IDX_NODE_SZ + child_cnt * (BRANCH_SZ + SK_LEN)
