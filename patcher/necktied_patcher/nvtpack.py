"""Novatek NVTPACK container (firmware file of the Viofo Linux models), CKSM partitions and
the checksums U-Boot verifies before it flashes an update from the SD card.

Own copy of the container logic of tools/nvtpack.py (groups A, B, B2 only, no RTOS images),
so the patcher core has no dependency on tools/. The checksum is computed without big
temporary tuples (works for 100 MB images in the browser):

    nvt_sum(buf) = (sum(u16_le[i]) + sum(i)) & 0xffff, must be 0
"""
import struct

NVTPACK_GUID = bytes.fromhex("072e01d6bc10914fb28a352f82261a50")
CKSM_MAGIC = b"CKSM"
CKSM_VERSION = 0x16040719
HDR_CHECKSUM_OFF = 0x24
ENTRY_TABLE_OFF = 0x80
ENTRY_SIZE = 12
FDT_MAGIC = b"\xd0\x0d\xfe\xed"


CHUNK = 1 << 22


def word_sum(buf):
    """Sum of all little-endian u16 words of buf (bytes-like, starting at an even offset)
    modulo 0x10000. Works in 4 MiB pieces, so no big temporary copies."""
    mv = memoryview(buf)
    s = 0
    for i in range(0, len(mv), CHUNK):
        c = bytes(mv[i:i + CHUNK])
        s += sum(c[0::2]) + (sum(c[1::2]) << 8)
    return s & 0xFFFF


def nvt_sum(buf):
    n = len(buf) // 2
    return (word_sum(memoryview(buf)[:2 * n]) + n * (n - 1) // 2) & 0xFFFF


def fix_sum_at(buf, word_off):
    """Adjust the u16 at word_off (bytearray) so that nvt_sum(buf) == 0."""
    assert word_off % 2 == 0
    cur = nvt_sum(buf)
    old = struct.unpack_from("<H", buf, word_off)[0]
    struct.pack_into("<H", buf, word_off, (old - cur) & 0xFFFF)


class Pack:
    def __init__(self, data):
        if bytes(data[:16]) != NVTPACK_GUID:
            raise ValueError("not a Novatek NVTPACK image (GUID missing)")
        self.raw = data
        self.data = memoryview(data)
        (self.version, self.hdr_size, self.count, self.total_size) = struct.unpack_from("<4I", data, 0x10)
        if self.count > 64:
            raise ValueError("NVTPACK: implausible partition count %d" % self.count)
        self.entries = [struct.unpack_from("<3I", data, ENTRY_TABLE_OFF + i * ENTRY_SIZE)
                        for i in range(self.count)]

    def ids(self):
        return sorted(p for _, _, p in self.entries)

    def part(self, pid):
        """Partition contents (memoryview into the image, no copy)."""
        for off, size, p in self.entries:
            if p == pid:
                if off + size > len(self.data):
                    raise ValueError("partition id%d extends past the end of the file" % pid)
                return self.data[off:off + size]
        raise KeyError(pid)


# --- flattened device tree (partition table, BIN_NAME) ---

def fdt_walk(fdt):
    fdt = bytes(fdt)
    if fdt[:4] != FDT_MAGIC:
        return
    off_struct, off_strings = struct.unpack_from(">II", fdt, 8)
    i = off_struct
    node = None
    while i + 4 <= len(fdt):
        tok = struct.unpack_from(">I", fdt, i)[0]
        i += 4
        if tok == 1:
            end = fdt.index(b"\0", i)
            node = bytes(fdt[i:end]).decode(errors="replace")
            i = (end + 4) & ~3
        elif tok == 3:
            ln, nameoff = struct.unpack_from(">II", fdt, i)
            s = off_strings + nameoff
            name = bytes(fdt[s:fdt.index(b"\0", s)]).decode(errors="replace")
            yield node, name, bytes(fdt[i + 8:i + 8 + ln])
            i = (i + 8 + ln + 3) & ~3
        elif tok in (2, 4):
            continue
        else:
            return


def fdt_partitions(fdt):
    out = {}
    for node, name, val in fdt_walk(fdt):
        if node and node.startswith("partition_") and name == "reg" and len(val) == 16:
            hi, lo, shi, slo = struct.unpack(">IIII", val)
            out.setdefault(node[len("partition_"):], ((hi << 32) | lo, (shi << 32) | slo))
    return out


def fdt_pack_labels(fdt):
    out = {}
    for node, name, val in fdt_walk(fdt):
        if node and node.startswith("id") and node[2:].isdigit() and name == "partition_name":
            out[int(node[2:])] = val.split(b"\0")[0].decode(errors="replace")
    return out


def fdt_bin_name(fdt):
    for _, name, val in fdt_walk(fdt):
        if name == "BIN_NAME":
            return val.split(b"\0")[0].decode(errors="replace")
    return None


def bin_name(data):
    """BIN_NAME of an image (U-Boot flashes <SD>/<BIN_NAME>.bin), None if unknown."""
    try:
        p1 = Pack(data).part(1)
    except (KeyError, ValueError, struct.error):
        return None
    return fdt_bin_name(p1) if bytes(p1[:4]) == FDT_MAGIC else None


def pack_labels(data):
    return fdt_pack_labels(Pack(data).part(1))


def rootfs_id(data):
    ids = [k for k, v in pack_labels(data).items() if v == "rootfs"]
    if len(ids) != 1:
        raise ValueError("rootfs partition not unique: %s" % ids)
    return ids[0]


# --- partition checks of U-Boot ---

def check_uimage(p):
    import zlib
    if bytes(p[:4]) != b"\x27\x05\x19\x56":
        return "uImage magic missing"
    hdr = bytearray(p[:64])
    hcrc = struct.unpack(">I", hdr[4:8])[0]
    hdr[4:8] = b"\0\0\0\0"
    if zlib.crc32(hdr) & 0xFFFFFFFF != hcrc:
        return "uImage header CRC wrong"
    dsize, = struct.unpack(">I", p[12:16])
    dcrc, = struct.unpack(">I", p[24:28])
    if 64 + dsize > len(p):
        return "uImage data size too large"
    if zlib.crc32(p[64:64 + dsize]) & 0xFFFFFFFF != dcrc:
        return "uImage data CRC wrong"
    return None


def check_cksm(p):
    if bytes(p[:4]) != CKSM_MAGIC:
        return "no CKSM header"
    f = struct.unpack_from("<8I", p, 0)
    if f[1] != CKSM_VERSION:
        return "CKSM version %#x != %#x" % (f[1], CKSM_VERSION)
    n = f[4] + f[5] + f[6]
    if n > len(p):
        return "CKSM length %#x > partition data %#x" % (n, len(p))
    if nvt_sum(p[:n]) != 0:
        return "CKSM checksum wrong"
    return None


def check_plain_sum(p):
    return None if nvt_sum(p) == 0 else "checksum wrong"


def checks_for(label, p):
    errs = []
    if label == "fdt" or label.startswith("fdt."):
        if bytes(p[:4]) != FDT_MAGIC:
            errs.append("FDT magic missing")
        elif struct.unpack(">I", p[4:8])[0] > len(p):
            errs.append("FDT totalsize too large")
    elif label == "kernel":
        errs.append(check_uimage(p) if bytes(p[:4]) != b"BCL1" else check_plain_sum(p))
    elif bytes(p[:4]) == CKSM_MAGIC:
        errs.append(check_cksm(p))
        errs.append(check_plain_sum(p))
    else:
        errs.append(check_plain_sum(p))
    return [e for e in errs if e]


def verify(data, unchanged=()):
    """Errors U-Boot would raise for this image ([] = accepted). Partition ids in `unchanged`
    are known to be byte-identical to a verified original and skip the expensive sums."""
    if bytes(data[:16]) != NVTPACK_GUID:
        return ["GUID wrong"]
    errs = []
    pk = Pack(data)
    data = pk.data
    if pk.total_size != len(data):
        errs.append("total_size %#x != file size %#x" % (pk.total_size, len(data)))
    if nvt_sum(data):
        errs.append("container checksum != 0")
    nand = fdt_partitions(pk.part(1))
    labels = fdt_pack_labels(pk.part(1))
    for off, size, pid in pk.entries:
        label = labels.get(pid, "?%d" % pid)
        p = data[off:off + size]
        e = [] if pid in unchanged else checks_for(label, p)
        if off + size > len(data):
            e.append("partition extends past end of file")
        if label in nand:
            eff = size - 0x40 if bytes(p[:4]) == CKSM_MAGIC else size
            if eff > nand[label][1]:
                e.append("too large for NAND partition (%#x > %#x)" % (eff, nand[label][1]))
        else:
            e.append("unknown partition ID %d" % pid)
        errs += ["id%d %s: %s" % (pid, label, x) for x in e]
    return errs


def layout(base, sizes):
    """Offsets of the partitions for {pid: size} in the order of base and the total size.
    Layout of the Novatek packer (all stock images of groups A/B/B2): every partition starts at
    an offset congruent to the end of the entry table modulo 64 (6 entries: 8 mod 64, 5 entries:
    60 mod 64), gaps zero-filled. tools/nvtpack.py always uses 8 mod 64 (also valid, but not
    the stock layout for 5 entries)."""
    pk = Pack(base)
    pos = ENTRY_TABLE_OFF + pk.count * ENTRY_SIZE
    phase = pos % 64
    for off, _size, _pid in pk.entries:
        if off % 64 != phase:
            raise ValueError("original has a different partition layout (offset %#x)" % off)
    entries = []
    for _off, _size, pid in pk.entries:
        start = pos + ((phase - pos) % 64)
        entries.append((start, sizes[pid], pid))
        pos = start + sizes[pid]
    return entries, pos + (pos % 2)


def build(base, parts, cksm=()):
    """Rebuild the container from the header of `base` and {pid: bytes-like or [chunks]}
    (layout() of the stock image).
    For pids in `cksm` the part starts with a CKSM header whose data length (0x14) and
    checksum slot (0x0c) are recomputed in place. Returns a bytearray (one allocation)."""
    pk = Pack(base)
    chunks = {pid: (p if isinstance(p, (list, tuple)) else [p]) for pid, p in parts.items()}
    sizes = {pid: sum(len(c) for c in ch) for pid, ch in chunks.items()}
    entries, total = layout(base, sizes)
    out = bytearray(total)
    hdr_len = ENTRY_TABLE_OFF + pk.count * ENTRY_SIZE
    out[:hdr_len] = pk.data[:hdr_len]
    mv = memoryview(out)
    for i, (o, s, pid) in enumerate(entries):
        struct.pack_into("<3I", out, ENTRY_TABLE_OFF + i * ENTRY_SIZE, o, s, pid)
        p = o
        for c in chunks[pid]:
            mv[p:p + len(c)] = c
            p += len(c)
        if pid in cksm:
            if bytes(out[o:o + 4]) != CKSM_MAGIC:
                raise ValueError("partition id%d without CKSM header" % pid)
            struct.pack_into("<I", out, o + 0x14, s - 0x40)
            struct.pack_into("<I", out, o + 0x0C, 0)
            f = struct.unpack_from("<8I", out, o)
            if f[4] + f[5] + f[6] != s or f[4] != 0x40:
                raise ValueError("unexpected CKSM header in id%d" % pid)
            fix_sum_at(mv[o:o + s], 0x0C)
    struct.pack_into("<I", out, 0x1C, total)
    struct.pack_into("<H", out, HDR_CHECKSUM_OFF, 0)
    fix_sum_at(mv, HDR_CHECKSUM_OFF)
    return out


def wrap_cksm(template_part, payload):
    """CKSM header of template_part + payload, length and checksum slot (0x0c) recomputed."""
    hdr = bytearray(template_part[:0x40])
    if bytes(hdr[:4]) != CKSM_MAGIC:
        raise ValueError("template without CKSM header")
    struct.pack_into("<I", hdr, 0x14, len(payload))
    struct.pack_into("<I", hdr, 0x0C, 0)
    f = struct.unpack_from("<8I", hdr, 0)
    n = f[4] + f[5] + f[6]
    if n != 0x40 + len(payload) or len(payload) % 2:
        raise ValueError("unexpected CKSM header (length %#x)" % n)
    ws = word_sum(hdr) + word_sum(payload)
    words = n // 2
    cur = (ws + words * (words - 1) // 2) & 0xFFFF
    struct.pack_into("<H", hdr, 0x0C, (-cur) & 0xFFFF)
    return bytes(hdr) + bytes(payload)
