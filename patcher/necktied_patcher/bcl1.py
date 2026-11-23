"""Novatek BCL1 container with LZMA payload (algorithm 11), as used for the RTOS partition of
the group C cameras (A119 V3). Standard library only (lzma), runs under Pyodide.

Header (16 bytes):
    0x00  "BCL1"
    0x04  u16 LE  checksum slot: makes nvt_sum(whole partition) == 0
    0x06  u16 BE  algorithm (11 = LZMA)
    0x08  u32 BE  uncompressed size
    0x0c  u32 BE  compressed size (payload bytes behind the header, incl. zero padding)
LZMA payload: props, dict_size u32 LE, usize u32 LE, usize u32 LE, raw LZMA1 stream.

The stock streams have no end-of-payload marker. Python's lzma module can only write raw
LZMA1 with the marker; the U-Boot LZMA routine of the A119 V3 decodes such a stream to the
same bytes (checked in emulation, tools/emu_uboot_lzma_a119v3.py).
"""
import lzma
import struct

from .nvtpack import nvt_sum, fix_sum_at

MAGIC = b"BCL1"
ALGO_LZMA = 11


class Bcl1Error(ValueError):
    pass


def parse_header(p):
    if len(p) < 16 or bytes(p[:4]) != MAGIC:
        raise Bcl1Error("no BCL1 header")
    slot, = struct.unpack_from("<H", p, 4)
    algo, usize, csize = struct.unpack_from(">HII", p, 6)
    return {"slot": slot, "algo": algo, "usize": usize, "csize": csize}


def lzma_header(payload):
    props = payload[0]
    lc, r = props % 9, props // 9
    lp, pb = r % 5, r // 5
    dict_size, s1, s2 = struct.unpack_from("<III", payload, 1)
    return {"props": props, "lc": lc, "lp": lp, "pb": pb, "dict_size": dict_size, "size1": s1, "size2": s2}


def decompress(p):
    h = parse_header(p)
    if h["algo"] != ALGO_LZMA:
        raise Bcl1Error("BCL1 algorithm %d (only LZMA 11 supported)" % h["algo"])
    payload = bytes(p[16:16 + h["csize"]])
    if len(payload) != h["csize"]:
        raise Bcl1Error("partition shorter than csize")
    lh = lzma_header(payload)
    if lh["size1"] != h["usize"]:
        raise Bcl1Error("LZMA size %#x != BCL1 usize %#x" % (lh["size1"], h["usize"]))
    f = [{"id": lzma.FILTER_LZMA1, "lc": lh["lc"], "lp": lh["lp"], "pb": lh["pb"],
          "dict_size": max(lh["dict_size"], 4096)}]
    d = lzma.LZMADecompressor(format=lzma.FORMAT_RAW, filters=f)
    try:
        out = d.decompress(payload[13:], max_length=h["usize"])
    except lzma.LZMAError as e:
        raise Bcl1Error("LZMA: %s" % e)
    if len(out) != h["usize"]:
        raise Bcl1Error("LZMA: only %#x of %#x bytes" % (len(out), h["usize"]))
    return out


def compress_like(raw, like, align=8):
    """BCL1 partition with the LZMA parameters (lc/lp/pb, dictionary) of the stock partition
    like; zero padding to a multiple of align (counted in csize, like the stock ones)."""
    lh = parse_header(like)
    if lh["algo"] != ALGO_LZMA:
        raise Bcl1Error("BCL1 algorithm %d (only LZMA 11 supported)" % lh["algo"])
    h = lzma_header(bytes(like[16:29]))
    f = [{"id": lzma.FILTER_LZMA1, "lc": h["lc"], "lp": h["lp"], "pb": h["pb"], "dict_size": h["dict_size"],
          "preset": 9}]
    stream = lzma.compress(bytes(raw), format=lzma.FORMAT_RAW, filters=f)
    payload = bytes([h["props"]]) + struct.pack("<III", h["dict_size"], len(raw), len(raw)) + stream
    payload += b"\0" * (-(16 + len(payload)) % align)
    out = bytearray(MAGIC + b"\0\0" + struct.pack(">HII", ALGO_LZMA, len(raw), len(payload)) + payload)
    fix_sum_at(out, 4)
    return bytes(out)


def check(p, raw=None):
    """Checks of a BCL1/LZMA partition; returns a list of errors (empty = fine)."""
    errs = []
    try:
        h = parse_header(p)
    except Bcl1Error as e:
        return [str(e)]
    if 16 + h["csize"] > len(p):
        errs.append("csize %#x > partition" % h["csize"])
    if len(p) % 2 or nvt_sum(p) != 0:
        errs.append("nvt_sum of the partition != 0")
    if h["algo"] == ALGO_LZMA:
        lh = lzma_header(bytes(p[16:29]))
        if lh["size1"] != h["usize"] or lh["size2"] != h["usize"]:
            errs.append("LZMA size fields %#x/%#x != usize %#x" % (lh["size1"], lh["size2"], h["usize"]))
        if p[16 + 13] != 0:
            errs.append("range coder start byte != 0")
    try:
        d = decompress(p)
        if raw is not None and d != raw:
            errs.append("decompression differs")
    except Bcl1Error as e:
        errs.append(str(e))
    return errs
