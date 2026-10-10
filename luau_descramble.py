"""Convert Roblox client opcode encoding to plain Luau opcodes (and back, for tests).

Roblox client bytecode stores each instruction's opcode byte as `op * 227 mod 256`
(decoded with `* 203`). Aux words are not scrambled. The rest of the container is
standard Luau, so we walk it only far enough to locate instruction words.
"""

# Opcodes followed by an AUX word (see Luau's getOpLength).
AUX_OPS = {7, 8, 12, 15, 16, 20, 27, 28, 29, 30, 31, 32, 53, 55, 58, 60, 66, 74, 75,
           77, 78, 79, 80, 83, 84, 85, 86, 87, 88, 90}
ENCODE_MUL = 227
DECODE_MUL = 203


class Truncated(Exception):
    pass


class _R:
    def __init__(self, data):
        self.d = data
        self.o = 0

    def byte(self):
        if self.o >= len(self.d):
            raise Truncated()
        b = self.d[self.o]
        self.o += 1
        return b

    def skip(self, n):
        if n < 0 or self.o + n > len(self.d):
            raise Truncated()
        self.o += n

    def varint(self):
        r = 0
        s = 0
        while True:
            b = self.byte()
            r |= (b & 127) << s
            s += 7
            if not b & 128:
                return r
            if s > 70:
                raise Truncated()


def transform(data, mul):
    """Return a copy of `data` with every instruction opcode byte multiplied by `mul` mod 256.

    `mul=DECODE_MUL` turns Roblox-encoded bytecode into plain bytecode.
    Raises ValueError if the container can't be walked.
    """
    d = bytearray(data)
    try:
        r = _R(d)
        ver = r.byte()
        if ver < 3 or ver > 14:
            raise ValueError("not Luau bytecode (version %d)" % ver)
        tv = r.byte() if ver >= 4 else 0
        for _ in range(r.varint()):
            r.skip(r.varint())
        if tv == 3:
            while r.byte() != 0:
                r.varint()
        for _ in range(r.varint()):
            end = None
            if ver >= 12:
                size = r.varint()
                end = r.o + size
            r.skip(3)
            r.byte()  # is_vararg
            flags = 0
            if ver >= 4:
                flags = r.byte()
                r.skip(r.varint())  # type info
            sizecode = r.varint()
            i = 0
            while i < sizecode:
                if r.o + 4 > len(d):
                    raise Truncated()
                if mul == ENCODE_MUL:
                    plain = d[r.o]
                    d[r.o] = (plain * mul) & 255
                else:
                    plain = (d[r.o] * mul) & 255
                    d[r.o] = plain
                r.o += 4
                i += 1
                if plain in AUX_OPS:
                    r.skip(4)
                    i += 1
            for _ in range(r.varint()):  # constants
                tag = r.byte()
                if tag == 1:
                    r.skip(1)
                elif tag == 2:
                    r.skip(8)
                elif tag in (3, 6):
                    r.varint()
                elif tag == 4:
                    r.skip(4)
                elif tag == 5:
                    for _ in range(r.varint()):
                        r.varint()
                elif tag == 7:
                    r.skip(16)
                elif tag == 8:
                    for _ in range(r.varint()):
                        r.varint()
                        r.skip(4)
                elif tag == 9:
                    r.skip(1)
                    r.varint()
                elif tag == 10:
                    r.varint()
                    n = r.varint() + r.varint()
                    for _ in range(n):
                        r.varint()
                elif tag == 11:
                    r.skip(32)
                elif tag != 0:
                    raise ValueError("unknown constant tag %d" % tag)
            for _ in range(r.varint()):  # child protos
                r.varint()
            r.varint()  # linedefined
            r.varint()  # debug name
            if r.byte():  # line info
                gap = r.byte()
                intervals = ((sizecode - 1) >> gap) + 1
                r.skip(sizecode + intervals * 4)
            if r.byte():  # debug info
                for _ in range(r.varint()):
                    r.varint()
                    r.varint()
                    r.varint()
                    r.byte()
                for _ in range(r.varint()):
                    r.varint()
            if ver >= 11:
                for _ in range(r.varint()):
                    r.byte()
                    r.varint()
            if ver >= 12 and flags & 8:
                r.varint()
            if end is not None:
                r.o = end
        r.varint()  # main proto
    except Truncated:
        raise ValueError("truncated Luau bytecode")
    return bytes(d)


def decode_roblox(data):
    return transform(data, DECODE_MUL)


def encode_roblox(data):
    return transform(data, ENCODE_MUL)
