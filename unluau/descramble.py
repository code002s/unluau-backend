"""Convert Roblox client opcode encoding to plain Luau opcodes (and back, for tests).

Roblox client bytecode stores every instruction's opcode byte as `op * 227 mod 256`
(decoded with `* 203`). Aux words are not scrambled and the rest of the container
is standard Luau, so we only walk it far enough to locate the instruction words.
"""

from __future__ import annotations

# Opcodes followed by an AUX word (see Luau's getOpLength).
AUX_OPCODES = frozenset({
    7, 8, 12, 15, 16, 20, 27, 28, 29, 30, 31, 32, 53, 55, 58, 60, 66, 74, 75,
    77, 78, 79, 80, 83, 84, 85, 86, 87, 88, 90,
})
ENCODE_MULTIPLIER = 227
DECODE_MULTIPLIER = 203
MIN_VERSION = 3
MAX_VERSION = 14
INSTRUCTION_SIZE = 4

_FIXED_CONSTANT_SIZES = {1: 1, 2: 8, 4: 4, 7: 16, 11: 32}  # tag -> payload bytes
_VARINT_CONSTANT_TAGS = (3, 6)
_MAX_VARINT_SHIFT = 70


class Truncated(Exception):
    """The bytecode ended in the middle of a structure."""


class ByteReader:
    def __init__(self, data: bytearray) -> None:
        self.data = data
        self.offset = 0

    def byte(self) -> int:
        if self.offset >= len(self.data):
            raise Truncated()
        value = self.data[self.offset]
        self.offset += 1
        return value

    def skip(self, count: int) -> None:
        if count < 0 or self.offset + count > len(self.data):
            raise Truncated()
        self.offset += count

    def varint(self) -> int:
        result = 0
        shift = 0
        while True:
            byte = self.byte()
            result |= (byte & 127) << shift
            shift += 7
            if not byte & 128:
                return result
            if shift > _MAX_VARINT_SHIFT:
                raise Truncated()

    def skip_varints(self, count: int) -> None:
        for _ in range(count):
            self.varint()


def transform(data: bytes, multiplier: int) -> bytes:
    """Return a copy of `data` with every opcode byte multiplied by `multiplier` mod 256.

    `DECODE_MULTIPLIER` turns Roblox-encoded bytecode into plain bytecode.
    Raises ValueError if the container cannot be walked.
    """
    buffer = bytearray(data)
    try:
        _walk_container(ByteReader(buffer), multiplier)
    except Truncated:
        raise ValueError("truncated Luau bytecode") from None
    return bytes(buffer)


def decode_roblox(data: bytes) -> bytes:
    return transform(data, DECODE_MULTIPLIER)


def encode_roblox(data: bytes) -> bytes:
    return transform(data, ENCODE_MULTIPLIER)


def _walk_container(reader: ByteReader, multiplier: int) -> None:
    version = reader.byte()
    if not MIN_VERSION <= version <= MAX_VERSION:
        raise ValueError(f"not Luau bytecode (version {version})")
    types_version = reader.byte() if version >= 4 else 0

    for _ in range(reader.varint()):  # string table
        reader.skip(reader.varint())
    if types_version == 3:
        _skip_userdata_types(reader)

    for _ in range(reader.varint()):  # protos
        _walk_proto(reader, version, multiplier)
    reader.varint()  # main proto index


def _skip_userdata_types(reader: ByteReader) -> None:
    while reader.byte() != 0:
        reader.varint()


def _walk_proto(reader: ByteReader, version: int, multiplier: int) -> None:
    end = None
    if version >= 12:
        size = reader.varint()
        end = reader.offset + size
    reader.skip(3)  # max stack, num params, num upvalues
    reader.byte()  # is_vararg
    flags = 0
    if version >= 4:
        flags = reader.byte()
        reader.skip(reader.varint())  # type info

    instruction_count = reader.varint()
    _rewrite_instructions(reader, instruction_count, multiplier)
    _skip_constants(reader)
    reader.skip_varints(reader.varint())  # child protos
    reader.varint()  # line defined
    reader.varint()  # debug name
    _skip_line_info(reader, instruction_count)
    _skip_debug_info(reader)
    if version >= 11:
        for _ in range(reader.varint()):  # feedback slots
            reader.byte()
            reader.varint()
    if version >= 12 and flags & 8:
        reader.varint()
    if end is not None:
        reader.offset = end


def _rewrite_instructions(reader: ByteReader, instruction_count: int, multiplier: int) -> None:
    data = reader.data
    index = 0
    while index < instruction_count:
        if reader.offset + INSTRUCTION_SIZE > len(data):
            raise Truncated()
        opcode = _rewrite_opcode(data, reader.offset, multiplier)
        reader.offset += INSTRUCTION_SIZE
        index += 1
        if opcode in AUX_OPCODES:
            reader.skip(INSTRUCTION_SIZE)
            index += 1


def _rewrite_opcode(data: bytearray, offset: int, multiplier: int) -> int:
    """Rewrite the opcode byte in place; return the *plain* opcode."""
    if multiplier == ENCODE_MULTIPLIER:
        plain = data[offset]
        data[offset] = (plain * multiplier) & 255
        return plain
    plain = (data[offset] * multiplier) & 255
    data[offset] = plain
    return plain


def _skip_constants(reader: ByteReader) -> None:
    for _ in range(reader.varint()):
        tag = reader.byte()
        if tag == 0:
            continue
        if tag in _FIXED_CONSTANT_SIZES:
            reader.skip(_FIXED_CONSTANT_SIZES[tag])
        elif tag in _VARINT_CONSTANT_TAGS:
            reader.varint()
        elif tag == 5:
            reader.skip_varints(reader.varint())
        elif tag == 8:
            _skip_import_table(reader)
        elif tag == 9:
            reader.skip(1)
            reader.varint()
        elif tag == 10:
            _skip_class_shape(reader)
        else:
            raise ValueError(f"unknown constant tag {tag}")


def _skip_import_table(reader: ByteReader) -> None:
    for _ in range(reader.varint()):
        reader.varint()
        reader.skip(4)


def _skip_class_shape(reader: ByteReader) -> None:
    reader.varint()
    count = reader.varint() + reader.varint()
    reader.skip_varints(count)


def _skip_line_info(reader: ByteReader, instruction_count: int) -> None:
    if not reader.byte():
        return
    gap = reader.byte()
    intervals = ((instruction_count - 1) >> gap) + 1
    reader.skip(instruction_count + intervals * INSTRUCTION_SIZE)


def _skip_debug_info(reader: ByteReader) -> None:
    if not reader.byte():
        return
    for _ in range(reader.varint()):  # local variables
        reader.varint()
        reader.varint()
        reader.varint()
        reader.byte()
    reader.skip_varints(reader.varint())  # upvalue names
