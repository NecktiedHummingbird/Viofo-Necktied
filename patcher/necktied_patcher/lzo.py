"""LZO1X decompressor (pure Python), format as produced by liblzo2 lzo1x_* and read by
Linux lib/lzo/lzo1x_decompress_safe.c. Only used for small files (S99_Sysctl, checks)."""


class LzoError(ValueError):
    pass


def _copy_match(out, dist, n):
    start = len(out) - dist
    if start < 0:
        raise LzoError("back-reference before start of buffer")
    if dist >= n:
        out += out[start:start + n]
    else:
        pat = out[start:]
        out += (pat * (n // dist + 1))[:n]


def decompress(src, out_len=None):
    """Decompress one LZO1X block (a UBIFS data node payload)."""
    ip = 0
    src = bytes(src)
    n = len(src)
    out = bytearray()
    state = 0

    def ext(ip, base):
        # run of zero bytes = +255 each, then one byte
        z = ip
        while src[ip] == 0:
            ip += 1
        return (ip - z) * 255 + base + src[ip], ip + 1

    try:
        if src[0] > 17:
            t = src[0] - 17
            ip = 1
            out += src[ip:ip + t]
            ip += t
            state = 4 if t >= 4 else t
        while True:
            t = src[ip]
            ip += 1
            if t < 16:
                if state == 0:
                    if t == 0:
                        t, ip = ext(ip, 15)
                    t += 3
                    if ip + t > n:
                        raise LzoError("literal past end of input")
                    out += src[ip:ip + t]
                    ip += t
                    state = 4
                    continue
                if state != 4:
                    nxt = t & 3
                    dist = 1 + (t >> 2) + (src[ip] << 2)
                    ip += 1
                    _copy_match(out, dist, 2)
                else:
                    nxt = t & 3
                    dist = 1 + 0x800 + (t >> 2) + (src[ip] << 2)
                    ip += 1
                    _copy_match(out, dist, 3)
            elif t >= 64:
                nxt = t & 3
                dist = 1 + ((t >> 2) & 7) + (src[ip] << 3)
                ip += 1
                _copy_match(out, dist, (t >> 5) + 1)
            elif t >= 32:
                ln = (t & 31) + 2
                if ln == 2:
                    ln, ip = ext(ip, 31)
                    ln += 2
                v = src[ip] | (src[ip + 1] << 8)
                ip += 2
                nxt = v & 3
                _copy_match(out, 1 + (v >> 2), ln)
            else:
                hi = (t & 8) << 11
                ln = (t & 7) + 2
                if ln == 2:
                    ln, ip = ext(ip, 7)
                    ln += 2
                v = src[ip] | (src[ip + 1] << 8)
                ip += 2
                nxt = v & 3
                dist = hi + (v >> 2)
                if dist == 0:
                    break                       # end of stream
                _copy_match(out, dist + 0x4000, ln)
            state = nxt
            if nxt:
                out += src[ip:ip + nxt]
                ip += nxt
    except IndexError:
        raise LzoError("input too short")
    if ip != n:
        raise LzoError("trailing data after end marker (%d of %d bytes read)" % (ip, n))
    if out_len is not None and len(out) != out_len:
        raise LzoError("length %d instead of %d" % (len(out), out_len))
    return bytes(out)
