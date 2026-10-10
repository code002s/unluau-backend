import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync, readdirSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { init, decompile } from "unluac-js";
import { sniffBytecode, buildLuauOptions } from "../src/luau-detect.js";
import {
  parseLuauBytecode, prepareLuauBytecode, encodeRobloxOpcodes, LuauBytecodeError,
} from "../src/luau-bytecode.js";

const dir = fileURLToPath(new URL("./fixtures/", import.meta.url));
const fixtures = readdirSync(dir).filter((f) => f.endsWith(".luauc"));
const load = (f) => new Uint8Array(readFileSync(dir + f));
await init(readFileSync(fileURLToPath(new URL("../src/unluac_wasm_bg.wasm", import.meta.url))));

test("fixtures exist (compiled by a real Luau 0.700 compiler, bytecode v6)", () => {
  assert.ok(fixtures.length >= 10);
});

test("sniffBytecode classifies headers", () => {
  assert.equal(sniffBytecode(load(fixtures[0])).dialect, "luau");
  assert.equal(sniffBytecode(load(fixtures[0])).engineSupported, true);
  assert.equal(sniffBytecode(Uint8Array.of(14, 3, 0)).engineSupported, true);
  assert.equal(sniffBytecode(Uint8Array.of(0x1b, 0x4c, 0x75)).dialect, "lua");
  assert.equal(sniffBytecode(Uint8Array.of(0x1b, 0x4c, 0x4a)).dialect, "luajit");
  assert.match(sniffBytecode(Uint8Array.of(0, 65)).reason, /compile-error/);
  assert.match(sniffBytecode(new TextEncoder().encode("print(1)")).reason, /source text/);
});

for (const f of fixtures) {
  test(`parse + roblox-opcode round trip: ${f}`, () => {
    const b = load(f);
    const parsed = parseLuauBytecode(b);
    assert.equal(parsed.version, 6);
    assert.equal(prepareLuauBytecode(b).info.opcodeEncoding, "plain");
    const encoded = encodeRobloxOpcodes(b, parsed);
    assert.notDeepEqual(encoded, b);
    const back = prepareLuauBytecode(encoded);
    assert.equal(back.info.opcodeEncoding, "roblox-client");
    assert.deepEqual(back.bytes, b);
  });
}

test("corrupt input is rejected with LuauBytecodeError", () => {
  const b = load("v6_basic_O1_g1.luauc");
  assert.throws(() => parseLuauBytecode(b.slice(0, b.length - 5)), LuauBytecodeError);
  assert.throws(() => parseLuauBytecode(Uint8Array.of(...b, 0)), /trailing/);
  assert.throws(() => parseLuauBytecode(Uint8Array.of(0, 1, 2)), /compile-error/);
});

test("decompiles real Luau bytecode (all opt/debug levels)", async () => {
  for (const f of fixtures.filter((x) => x.startsWith("v6_basic"))) {
    const out = await decompile(prepareLuauBytecode(load(f)).bytes, buildLuauOptions());
    assert.match(out, /game:GetService\("Players"\)/, f);
    assert.match(out, /continue/, f);
    // at -O0 the engine emits `local v = Vector3.new; v = v(1, 2, 3)`, so only require the call target
    assert.match(out, /Vector3\.new/, f);
    assert.match(out, /1, 2, 3\)/, f);
  }
});

test("roblox-encoded input decompiles identically to the plain file", async () => {
  const b = load("v6_extra_O1_g2.luauc");
  const encoded = encodeRobloxOpcodes(b, parseLuauBytecode(b));
  const a = await decompile(prepareLuauBytecode(b).bytes, buildLuauOptions());
  const c = await decompile(prepareLuauBytecode(encoded).bytes, buildLuauOptions());
  assert.equal(c, a);
});

test("buildLuauOptions only passes whitelisted values", () => {
  const o = buildLuauOptions({ generate: { indentWidth: 2, evil: 1, luauVectorConstructor: { size: 3, library: "Vector3" } }, bogus: 1 });
  assert.equal(o.generate.indentWidth, 2);
  assert.equal(o.generate.evil, undefined);
  assert.equal(o.bogus, undefined);
  assert.equal(o.generate.luauVectorConstructor.size, 3);
  assert.equal(buildLuauOptions({ generate: { luauVectorConstructor: { size: 9 } } }).generate.luauVectorConstructor, undefined);
});
