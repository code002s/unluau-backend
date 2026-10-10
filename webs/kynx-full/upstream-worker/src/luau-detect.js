// Luau-specific helpers for the KYNX upstream worker.
// unluac-js performs the authoritative bytecode detection; this wrapper keeps
// Luau requests explicit and exposes useful metadata without pretending to
// support Roblox-private opcode encodings that the bundled WASM does not know.

// The worker sniffs the Luau header before invoking the decompiler.
//   Lua 5.x / LuaJIT chunks start with 0x1B ("\x1bLua" / "\x1bLJ").
//   Luau chunks start with a single bytecode-version byte (0 = compile error
//   message follows, otherwise 3-14 for current Luau), then a types version.
// Anything we cannot classify returns null and the engine decides.
export const LUAU_MIN_VERSION = 3; // oldest version Luau itself still loads
export const LUAU_MAX_VERSION = 14; // newest version Luau itself emits (LBC_VERSION_MAX)
// Bundled unluac-rs WASM currently parses Luau bytecode versions 3-7 only.
// Versions 8-14 require the external Unluau backend (LUAU_BACKEND_URL) until
// unluac-rs gains native v8+ support.
export const ENGINE_MIN_VERSION = 3;
export const ENGINE_WASM_MAX_VERSION = 7; // hard limit of the bundled WASM parser
export const ENGINE_MAX_VERSION = 14; // max admitted when Unluau backend is configured

const LUA_VERSION_BYTES = { 0x51: "5.1", 0x52: "5.2", 0x53: "5.3", 0x54: "5.4", 0x55: "5.5" };

// Every dialect value the bundled WASM accepts (see supportedOptionValues()).
export const ENGINE_DIALECTS = ["auto", "lua5.1", "lua5.2", "lua5.3", "lua5.4", "lua5.5", "luajit", "luau"];
// Dialects a caller may request explicitly for non-Luau bytecode.
export const LUA_FAMILY_DIALECTS = ["lua5.1", "lua5.2", "lua5.3", "lua5.4", "lua5.5", "luajit"];

export function sniffBytecode(bytes) {
  if (!bytes || bytes.length < 2) return { dialect: null, reason: "too short" };
  const b0 = bytes[0];
  if (b0 === 0x1b) {
    if (bytes[1] === 0x4c && bytes[2] === 0x4a) {
      // Dump version byte: 1 = LuaJIT 2.0, 2 = LuaJIT 2.1. The bundled WASM only reads 2.1 dumps.
      const luajitVersion = bytes[3];
      return {
        dialect: "luajit",
        engineDialect: "luajit",
        reason: "ESC LJ header",
        luajitVersion,
        engineSupported: luajitVersion === 2,
      };
    }
    // "\x1bLua" + version byte (0x51 = 5.1, 0x52 = 5.2, 0x53 = 5.3, 0x54 = 5.4, 0x55 = 5.5).
    const isLua = bytes[1] === 0x4c && bytes[2] === 0x75 && bytes[3] === 0x61;
    const luaVersion = isLua ? LUA_VERSION_BYTES[bytes[4]] : undefined;
    return {
      dialect: "lua",
      engineDialect: luaVersion ? `lua${luaVersion}` : "auto",
      luaVersion: luaVersion || null,
      reason: "ESC header",
    };
  }
  if (b0 === 0) {
    return { dialect: null, reason: "Luau compile-error chunk (version byte 0), not bytecode" };
  }
  if (b0 >= LUAU_MIN_VERSION && b0 <= LUAU_MAX_VERSION) {
    return {
      dialect: "luau",
      version: b0,
      typesVersion: bytes[1],
      engineSupported: b0 >= ENGINE_MIN_VERSION && b0 <= ENGINE_WASM_MAX_VERSION,
      backendEligible: b0 >= ENGINE_MIN_VERSION && b0 <= ENGINE_MAX_VERSION,
    };
  }
  if (b0 >= 0x20 && b0 < 0x7f) {
    return { dialect: null, reason: "looks like source text, not bytecode" };
  }
  return { dialect: null, reason: `unrecognized header byte 0x${b0.toString(16)}` };
}

export async function detectBytecodeDialect(bytes) {
  return sniffBytecode(bytes).dialect;
}

export function isLuauDialect(dialect) {
  return dialect === "luau";
}

export function buildLuauOptions(userOptions = {}, dialect = "luau") {
  // Keep the accepted surface deliberately small. The frontend cannot inject
  // arbitrary WASM options; it can only choose documented decompiler settings.
  const out = {
    dialect,
    parse: {
      mode: "permissive",
      stringEncoding: "auto",
      stringDecodeMode: "strict",
    },
    naming: {
      mode: "debug-like",
      debugLikeIncludeFunction: true,
    },
    generate: {
      mode: "permissive",
      indentWidth: 4,
      maxLineLength: 100,
      numberFormat: "decimal",
      quoteStyle: "min-escape",
      tableStyle: "balanced",
      comment: true,
    },
  };

  if (!userOptions || typeof userOptions !== "object" || Array.isArray(userOptions)) {
    return out;
  }

  const parseMode = userOptions.parse?.mode;
  if (parseMode === "strict" || parseMode === "permissive") out.parse.mode = parseMode;

  const namingMode = userOptions.naming?.mode;
  if (["debug-like", "simple", "heuristic"].includes(namingMode)) out.naming.mode = namingMode;

  const generateMode = userOptions.generate?.mode;
  if (generateMode === "strict" || generateMode === "permissive") out.generate.mode = generateMode;

  if (Number.isInteger(userOptions.generate?.indentWidth) && userOptions.generate.indentWidth >= 1 && userOptions.generate.indentWidth <= 16) {
    out.generate.indentWidth = userOptions.generate.indentWidth;
  }
  if (Number.isInteger(userOptions.generate?.maxLineLength) && userOptions.generate.maxLineLength >= 40 && userOptions.generate.maxLineLength <= 400) {
    out.generate.maxLineLength = userOptions.generate.maxLineLength;
  }

  // Vector constants need an explicit constructor in unluac-js. Accept only
  // the documented shape and sizes 3/4; otherwise leave it unset so the
  // decompiler fails clearly instead of silently producing the wrong API call.
  const vector = dialect === "luau" ? userOptions.generate?.luauVectorConstructor : null;
  if (vector && typeof vector === "object" && !Array.isArray(vector)) {
    const constructor = typeof vector.constructor === "string" ? vector.constructor : "new";
    const size = vector.size;
    const library = vector.library;
    if ((size === 3 || size === 4) && /^[A-Za-z_$][A-Za-z0-9_$.]*$/.test(constructor)) {
      const cfg = { constructor, size };
      if (library == null || /^[A-Za-z_$][A-Za-z0-9_$.]*$/.test(library)) cfg.library = library;
      out.generate.luauVectorConstructor = cfg;
    }
  }

  return out;
}

// Options for any dialect. Lua 5.x / LuaJIT chunks use the same whitelist as Luau
// (parse / naming / generate); only the Luau vector constructor is Luau-specific.
export function buildOptions(dialect, userOptions = {}) {
  return buildLuauOptions(userOptions, dialect);
}

// Picks the dialect for a non-Luau chunk. An explicit, whitelisted request wins
// over the header sniff (useful for patched or truncated headers).
export function resolveLuaDialect(info, requested) {
  if (typeof requested === "string" && LUA_FAMILY_DIALECTS.includes(requested)) return requested;
  return info.engineDialect || "auto";
}

// Languages that compile to Lua source/bytecode: decompiling gives plain Lua back.
export const LANGUAGE_CATALOG = [
  { id: "lua5.1", name: "Lua 5.1", kind: "bytecode", supported: true },
  { id: "lua5.2", name: "Lua 5.2", kind: "bytecode", supported: true },
  { id: "lua5.3", name: "Lua 5.3", kind: "bytecode", supported: true },
  { id: "lua5.4", name: "Lua 5.4", kind: "bytecode", supported: true },
  { id: "luajit20", name: "LuaJIT 2.0", kind: "bytecode", supported: false },
  { id: "luajit21", name: "LuaJIT 2.1", kind: "bytecode", supported: true },
  { id: "luau", name: "Luau", kind: "bytecode", supported: true, note: "Official Luau bytecode definitions support v3-v14; the bundled decompiler must still be compatible with the specific bytecode version." },
  { id: "moonscript", name: "MoonScript", kind: "source", supported: false, note: "Compiles to Lua; there is no separate MoonScript bytecode format." },
  { id: "teal", name: "Teal", kind: "source", supported: false, note: "Compiles to Lua and erases type annotations." },
  { id: "elua", name: "eLua", kind: "alias", supported: true, note: "Use the matching Lua 5.x bytecode dialect." },
];

export const LANGUAGE_NOTES = {
  "lua5.1": "Lua 5.1 bytecode (luac 5.1)",
  "lua5.2": "Lua 5.2 bytecode",
  "lua5.3": "Lua 5.3 bytecode",
  "lua5.4": "Lua 5.4 bytecode",
  "lua5.5": "Lua 5.5 bytecode",
  luajit: "LuaJIT 2.1 bytecode (dump version 2). LuaJIT 2.0 dumps (version 1) are rejected by the bundled engine.",
  luau: `Luau bytecode versions ${ENGINE_MIN_VERSION}-${ENGINE_MAX_VERSION} (Roblox). Newer bytecode requires the installed WASM build to support its serialization/opcodes.`,
  moonscript: "No separate bytecode: MoonScript compiles to Lua; decompile the Lua bytecode and you get Lua.",
  teal: "No separate bytecode: Teal compiles to Lua; types are erased, you get plain Lua.",
  elua: "eLua is Lua 5.1/5.2 (embedded); use lua5.1 or lua5.2.",
};
