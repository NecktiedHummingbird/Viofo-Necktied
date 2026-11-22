"""UBI image reader/writer (format of ubinize from mtd-utils, as used for the camera rootfs).

Reading: EC/VID headers (CRC checked), volume table, LEB map of one volume.
Writing: the image ubinize writes for one dynamic volume: layout volume in PEB 0 and 1,
then one PEB per LEB of the volume image (lnum 0..n-1), erase counter 0, sqnum 0.
"""
import struct

from .crc import crc32_raw

EC_MAGIC = b"UBI#"
VID_MAGIC = b"UBI!"
EC_HDR = struct.Struct(">4sB3xQIII32xI")           # 64 bytes
VID_HDR = struct.Struct(">4sBBBBII4xIIII4xQ12xI")  # 64 bytes
VTBL_REC = struct.Struct(">IIIBBH128sB23xI")        # 172 bytes
VTBL_REC_SIZE = 172
LAYOUT_VOL_ID = 0x7FFFEFFF
VID_DYNAMIC, VID_STATIC = 1, 2
COMPAT_REJECT = 5
MAX_VOLUMES = 128


class UbiError(ValueError):
    pass


class UbiImage:
    """Parsed UBI image: geometry + {vol_id: {lnum: (peb, data memoryview)}}."""

    def __init__(self, data, peb_size=None):
        self.data = memoryview(data)
        if bytes(self.data[:4]) != EC_MAGIC:
            raise UbiError("not a UBI image (EC header missing)")
        magic, ver, ec, self.vid_off, self.data_off, self.image_seq, crc = EC_HDR.unpack_from(self.data, 0)
        if crc32_raw(self.data[:60]) != crc:
            raise UbiError("EC header PEB 0: CRC wrong")
        self.version = ver
        if peb_size is None:
            peb_size = next((n for n in (2 ** k for k in range(14, 22))
                             if bytes(self.data[n:n + 4]) == EC_MAGIC), None)
            if peb_size is None:
                raise UbiError("PEB size not recognisable")
        self.peb_size = peb_size
        self.leb_size = peb_size - self.data_off
        if len(self.data) % peb_size:
            raise UbiError("image size is not a multiple of the PEB size")
        self.vols = {}
        self.vid = {}
        self.pebs = len(self.data) // peb_size
        for i in range(self.pebs):
            b = self.data[i * peb_size:(i + 1) * peb_size]
            if bytes(b[:4]) != EC_MAGIC:
                if bytes(b[:64]) == b"\xff" * 64:
                    continue                    # erased PEB
                raise UbiError("PEB %d: EC header missing" % i)
            f = EC_HDR.unpack_from(b, 0)
            if crc32_raw(b[:60]) != f[-1]:
                raise UbiError("PEB %d: EC header CRC wrong" % i)
            if (f[3], f[4], f[5]) != (self.vid_off, self.data_off, self.image_seq):
                raise UbiError("PEB %d: differing geometry/image_seq" % i)
            v = b[self.vid_off:self.vid_off + 64]
            if bytes(v[:4]) != VID_MAGIC:
                if bytes(v) == b"\xff" * 64:
                    continue                    # free PEB (no VID header)
                raise UbiError("PEB %d: VID header missing" % i)
            (m, vver, vol_type, copy_flag, compat, vol_id, lnum, data_size, used_ebs, data_pad,
             data_crc, sqnum, hcrc) = VID_HDR.unpack_from(v, 0)
            if crc32_raw(v[:60]) != hcrc:
                raise UbiError("PEB %d: VID header CRC wrong" % i)
            old = self.vols.setdefault(vol_id, {}).get(lnum)
            if old is not None and self.vid[(vol_id, lnum)][-1] >= sqnum:
                continue
            self.vols[vol_id][lnum] = (i, b[self.data_off:])
            self.vid[(vol_id, lnum)] = (vol_type, copy_flag, compat, data_size, used_ebs, data_pad, data_crc,
                                        sqnum)
        if LAYOUT_VOL_ID not in self.vols or 0 not in self.vols[LAYOUT_VOL_ID]:
            raise UbiError("volume table missing")
        self.vtbl = self._read_vtbl()

    def _read_vtbl(self):
        out = {}
        copies = []
        for lnum in (0, 1):
            if lnum not in self.vols[LAYOUT_VOL_ID]:
                continue
            raw = self.vols[LAYOUT_VOL_ID][lnum][1]
            copies.append(bytes(raw[:self.vtbl_size()]))
            if lnum == 0:
                for k in range(self.max_volumes()):
                    rec = raw[k * VTBL_REC_SIZE:(k + 1) * VTBL_REC_SIZE]
                    rp, al, dp, vt, upd, nl, name, flags, crc = VTBL_REC.unpack_from(rec, 0)
                    if crc32_raw(rec[:168]) != crc:
                        raise UbiError("volume table entry %d: CRC wrong" % k)
                    if rp:
                        out[k] = dict(reserved_pebs=rp, alignment=al, data_pad=dp, vol_type=vt, upd_marker=upd,
                                      name=name[:nl].decode(), flags=flags)
        if len(copies) == 2 and copies[0] != copies[1]:
            raise UbiError("the two copies of the volume table differ")
        return out

    def max_volumes(self):
        return min(MAX_VOLUMES, self.leb_size // VTBL_REC_SIZE)

    def vtbl_size(self):
        return self.max_volumes() * VTBL_REC_SIZE

    def volume_by_name(self, name):
        ids = [k for k, v in self.vtbl.items() if v["name"] == name]
        if len(ids) != 1:
            raise UbiError("volume %r not unique (%s)" % (name, ids))
        return ids[0]

    def volume_lebs(self, vol_id):
        """[memoryview of LEB data or None (unmapped)] for lnum 0..max mapped."""
        m = self.vols.get(vol_id, {})
        n = max(m) + 1 if m else 0
        return [m[i][1] if i in m else None for i in range(n)]


def ec_header(ec, vid_off, data_off, image_seq, version=1):
    h = bytearray(EC_HDR.pack(EC_MAGIC, version, ec, vid_off, data_off, image_seq, 0))
    struct.pack_into(">I", h, 60, crc32_raw(h[:60]))
    return bytes(h)


def vid_header(vol_type, compat, vol_id, lnum, data_pad=0, version=1):
    h = bytearray(VID_HDR.pack(VID_MAGIC, version, vol_type, 0, compat, vol_id, lnum, 0, 0, data_pad, 0, 0, 0))
    struct.pack_into(">I", h, 60, crc32_raw(h[:60]))
    return bytes(h)


def vtbl_record(reserved_pebs=0, alignment=0, data_pad=0, vol_type=0, name=b"", flags=0):
    r = bytearray(VTBL_REC.pack(reserved_pebs, alignment, data_pad, vol_type, 0, len(name), name, flags, 0))
    struct.pack_into(">I", r, 168, crc32_raw(r[:168]))
    return bytes(r)


def build_chunks(lebs, peb_size, vid_off, data_off, image_seq, vol, version=1):
    """UBI image as ubinize writes it for one dynamic volume, as a list of byte chunks
    (no big copy; concatenated it is the image file).

    lebs: list of LEB contents (bytes-like, each <= leb_size; padded with 0xFF)
    vol:  dict(id, name, reserved_pebs, alignment, flags) of the volume
    """
    leb_size = peb_size - data_off
    maxv = min(MAX_VOLUMES, leb_size // VTBL_REC_SIZE)
    recs = [vtbl_record() for _ in range(maxv)]
    data_pad = leb_size % vol["alignment"]
    recs[vol["id"]] = vtbl_record(vol["reserved_pebs"], vol["alignment"], data_pad, VID_DYNAMIC,
                                  vol["name"].encode(), vol.get("flags", 0))
    vtbl = b"".join(recs)
    ec = ec_header(0, vid_off, data_off, image_seq, version)
    gap1 = b"\xff" * (vid_off - len(ec))
    gap2 = b"\xff" * (data_off - vid_off - 64)
    ff = {}

    def pad(n):
        if n not in ff:
            ff[n] = b"\xff" * n
        return ff[n]

    out = []
    for lnum in (0, 1):
        vh = vid_header(VID_DYNAMIC, COMPAT_REJECT, LAYOUT_VOL_ID, lnum, 0, version)
        out += [ec + gap1 + vh + gap2, vtbl, pad(leb_size - len(vtbl))]
    for lnum, d in enumerate(lebs):
        if len(d) > leb_size:
            raise UbiError("LEB %d too large" % lnum)
        vh = vid_header(VID_DYNAMIC, 0, vol["id"], lnum, data_pad, version)
        out += [ec + gap1 + vh + gap2, d, pad(leb_size - len(d))]
    return out


def build_image(*a, **k):
    return b"".join(build_chunks(*a, **k))
