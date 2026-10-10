import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { init, decompile } from "unluac-js";
import { sniffBytecode, buildOptions, resolveLuaDialect } from "../src/luau-detect.js";

const dir = fileURLToPath(new URL("./fixtures/", import.meta.url));
const load = (f) => new Uint8Array(readFileSync(dir + f));
await init(readFileSync(fileURLToPath(new URL("../src/unluac_wasm_bg.wasm", import.meta.url))));

// Compiled by real Lua 5.1-5.4 and LuaJIT 2.0/2.1 (string.dump).
const cases = [
  ["lua51.luac", "lua", "lua5.1"],
  ["lua52.luac", "lua", "lua5.2"],
  ["lua53.luac", "lua", "lua5.3"],
  ["lua54.luac", "lua", "lua5.4"],
  ["luajit21.luac", "luajit", "luajit"],
];

for (const [file, dialect, engineDialect] of cases) {
  test(`${file}: sniff -> ${engineDialect}, decompiles`, async () => {
    const bytes = load(file);
    const info = sniffBytecode(bytes);
    assert.equal(info.dialect, dialect);
    assert.equal(resolveLuaDialect(info), engineDialect);
    const src = await decompile(bytes, buildOptions(engineDialect));
    assert.match(src, /print/);
    assert.match(src, /return/);
  });
}

test("explicit dialect overrides the header sniff; junk is ignored", () => {
  const info = sniffBytecode(load("lua51.luac"));
  assert.equal(resolveLuaDialect(info, "lua5.4"), "lua5.4");
  assert.equal(resolveLuaDialect(info, "luau"), "lua5.1");
  assert.equal(resolveLuaDialect(info, "<script>"), "lua5.1");
});

test("unknown Lua version byte falls back to auto", () => {
  const info = sniffBytecode(Uint8Array.of(0x1b, 0x4c, 0x75, 0x61, 0x99));
  assert.equal(info.engineDialect, "auto");
});

test("LuaJIT 2.0 dump (version 1) is flagged unsupported, 2.1 is supported", () => {
  assert.equal(sniffBytecode(load("luajit20.luac")).engineSupported, false);
  assert.equal(sniffBytecode(load("luajit21.luac")).engineSupported, true);
});
