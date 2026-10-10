// Minimal Luau bytecode container reader (versions 3-14 header layout, as written by
// Luau's BytecodeBuilder). It does not decode instructions; it only locates each
// function's instruction array so we can
//   * validate that a file is structurally sound bytecode (clear errors), and
//   * undo the Roblox client's opcode encoding (opcode byte * 227 mod 256).
//
// Verified against bytecode produced by real Luau compilers (v5, v6, v7) in test/.
// The Roblox opcode decoding is derived from the known encoding and tested by
// round-trip only: no real Roblox-client dump was available when this was written.

export const OP_RETURN = 22;
const OP_ENCODE_MUL = 227; // client encoding: enc = op * 227 (mod 256)
const OP_DECODE_MUL = 203; // 227 * 203 === 1 (mod 256)

// Opcodes followed by one AUX word (Luau's getOpLength() === 2), numbered as in Luau 0.700 (v6).
const AUX_OPS = new Set([
  7, 8, 12, 15, 16, 20, 27, 28, 29, 30, 31, 32, 53, 55, 58, 66, 74, 75, 60, 77, 78, 79, 80,
]);

export class LuauBytecodeError extends Error {}

class Reader {
  constructor(bytes) {
    this.b = bytes;
    this.o = 0;
  }
  need(n) {
    if (this.o + n > this.b.length) throw new LuauBytecodeError(`truncated bytecode at offset ${this.o}`);
  }
  u8() {
    this.need(1);
    return this.b[this.o++];
  }
  skip(n) {
    this.need(n);
    this.o += n;
  }
  varint() {
    let result = 0;
    let shift = 0;
    for (let i = 0; i < 5; i++) {
      const byte = this.u8();
      result += (byte & 0x7f) * 2 ** shift;
      if ((byte & 0x80) === 0) return result;
      shift += 7;
    }
    throw new LuauBytecodeError("malformed varint");
  }
}

/**
 * Parse the container. Returns { version, typesVersion, protos: [{ codeOffset, codeWords }], mainProto }.
 * Throws LuauBytecodeError on anything inconsistent.
 */
export function parseLuauBytecode(bytes) {
  const r = new Reader(bytes);
  const version = r.u8();
  if (version === 0) throw new LuauBytecodeError("version byte 0: this is a Luau compile-error message, not bytecode");
  if (version < 3 || version > 14) throw new LuauBytecodeError(`unrecognized Luau bytecode version ${version}`);
  const typesVersion = version >= 4 ? r.u8() : 0;

  const stringCount = r.varint();
  if (stringCount > bytes.length) throw new LuauBytecodeError("string table larger than file");
  for (let i = 0; i < stringCount; i++) r.skip(r.varint());

  if (typesVersion === 3) {
    // userdata type-name mapping: (index byte, varint nameRef)* terminated by 0
    for (let guard = 0; ; guard++) {
      if (guard > 256) throw new LuauBytecodeError("malformed userdata type map");
      if (r.u8() === 0) break;
      r.varint();
    }
  }

  const protoCount = r.varint();
  if (protoCount === 0 || protoCount > bytes.length) throw new LuauBytecodeError("bad function count");
  const protos = [];
  for (let p = 0; p < protoCount; p++) {
    r.skip(4); // maxstacksize, numparams, numupvalues, isvararg
    if (version >= 4) {
      r.u8(); // flags
      r.skip(r.varint()); // type info blob (size-prefixed)
    }
    const codeWords = r.varint();
    const codeOffset = r.o;
    if (codeWords === 0) throw new LuauBytecodeError(`function ${p} has no instructions`);
    r.skip(codeWords * 4);
    protos.push({ codeOffset, codeWords });

    const constCount = r.varint();
    for (let k = 0; k < constCount; k++) {
      const tag = r.u8();
      switch (tag) {
        case 0: break; // nil
        case 1: r.skip(1); break; // boolean
        case 2: r.skip(8); break; // number
        case 3: r.varint(); break; // string
        case 4: r.skip(4); break; // import
        case 5: { const n = r.varint(); for (let i = 0; i < n; i++) r.varint(); break; } // table shape
        case 6: r.varint(); break; // closure
        case 7: r.skip(16); break; // vector (4 x f32)
        default: throw new LuauBytecodeError(`unknown constant tag ${tag} in function ${p}`);
      }
    }
    const childCount = r.varint();
    for (let c = 0; c < childCount; c++) r.varint();
    r.varint(); // linedefined
    r.varint(); // debugname
    if (r.u8()) {
      const gapLog2 = r.u8();
      const intervals = ((codeWords - 1) >> gapLog2) + 1;
      r.skip(codeWords); // per-instruction line deltas
      r.skip(intervals * 4); // absolute line anchors
    }
    if (r.u8()) {
      const locals = r.varint();
      for (let i = 0; i < locals; i++) { r.varint(); r.varint(); r.varint(); r.skip(1); }
      const upvals = r.varint();
      for (let i = 0; i < upvals; i++) r.varint();
    }
  }
  const mainProto = r.varint();
  if (mainProto >= protoCount) throw new LuauBytecodeError("main function index out of range");
  if (r.o !== bytes.length) throw new LuauBytecodeError(`unexpected ${bytes.length - r.o} trailing bytes`);
  return { version, typesVersion, protos, mainProto };
}

const opAt = (bytes, offset, word) => bytes[offset + word * 4]; // little-endian: opcode is the low byte

/** Decide whether instruction opcodes are plain, Roblox-client-encoded, or unknown. */
export function detectOpcodeEncoding(bytes, parsed) {
  const plainRet = OP_RETURN;
  const encodedRet = (OP_RETURN * OP_ENCODE_MUL) & 0xff;
  let plain = true;
  let encoded = true;
  for (const p of parsed.protos) {
    const last = opAt(bytes, p.codeOffset, p.codeWords - 1);
    if (last !== plainRet) plain = false;
    if (last !== encodedRet) encoded = false;
  }
  if (plain) return "plain";
  if (encoded) return "roblox-client";
  return "unknown";
}

/**
 * Rewrite opcode bytes on a copy. AUX words are left alone, so the walk has to
 * know the plain opcode of each word: `decoding` says whether the input is encoded.
 */
export function transformOpcodes(bytes, parsed, mul, decoding) {
  const out = Uint8Array.from(bytes);
  for (const p of parsed.protos) {
    let w = 0;
    while (w < p.codeWords) {
      const at = p.codeOffset + w * 4;
      const converted = (out[at] * mul) & 0xff;
      const plain = decoding ? converted : out[at];
      out[at] = converted;
      w += AUX_OPS.has(plain) ? 2 : 1;
    }
  }
  return out;
}

export const decodeRobloxOpcodes = (bytes, parsed) => transformOpcodes(bytes, parsed, OP_DECODE_MUL, true);
export const encodeRobloxOpcodes = (bytes, parsed) => transformOpcodes(bytes, parsed, OP_ENCODE_MUL, false);

/**
 * Validate + normalize. Returns { bytes, info } where info describes what was found.
 * Throws LuauBytecodeError for corrupted input.
 */
export function prepareLuauBytecode(bytes) {
  const parsed = parseLuauBytecode(bytes);
  const encoding = detectOpcodeEncoding(bytes, parsed);
  let out = bytes;
  if (encoding === "roblox-client") out = decodeRobloxOpcodes(bytes, parsed);
  return {
    bytes: out,
    info: {
      version: parsed.version,
      typesVersion: parsed.typesVersion,
      functions: parsed.protos.length,
      opcodeEncoding: encoding,
    },
  };
}
