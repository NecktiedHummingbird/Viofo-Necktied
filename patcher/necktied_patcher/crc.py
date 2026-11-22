"""CRC routines of UBI/UBIFS (Linux crc32_le without final inversion, crc16 for the LPT)."""
import zlib


def crc32_raw(data, init=0xFFFFFFFF):
    """Linux crc32_le(init, data) as used by UBI/UBIFS (UBI_CRC32_INIT = UBIFS_CRC32_INIT = 0xFFFFFFFF)."""
    # zlib.crc32(data, v) = ~crc32_le(~v, data)  ->  crc32_le(init, data) = ~zlib.crc32(data, ~init)
    return zlib.crc32(data, init ^ 0xFFFFFFFF) ^ 0xFFFFFFFF


def _crc16_table():
    tab = []
    for i in range(256):
        c = i
        for _ in range(8):
            c = (c >> 1) ^ 0xA001 if c & 1 else c >> 1
        tab.append(c)
    return tab


_T16 = _crc16_table()


def crc16(data, crc=0xFFFF):
    """Linux lib/crc16.c (poly 0x8005 reflected), used for LPT nodes with init -1."""
    t = _T16
    for b in data:
        crc = (crc >> 8) ^ t[(crc ^ b) & 0xFF]
    return crc
