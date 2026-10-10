import { test } from "node:test";
import assert from "node:assert/strict";
import {
  sniffBytecode,
  ENGINE_MAX_VERSION,
  ENGINE_WASM_MAX_VERSION,
  ENGINE_MIN_VERSION,
} from "../src/luau-detect.js";

test("WASM engine range is 3-7", () => {
  assert.equal(ENGINE_MIN_VERSION, 3);
  assert.equal(ENGINE_WASM_MAX_VERSION, 7);
  assert.equal(sniffBytecode(Uint8Array.of(6, 3, 0)).engineSupported, true);
  assert.equal(sniffBytecode(Uint8Array.of(7, 3, 0)).engineSupported, true);
  assert.equal(sniffBytecode(Uint8Array.of(8, 3, 0)).engineSupported, false);
});

test("v13/v14 are backend-eligible but not WASM-supported", () => {
  assert.equal(ENGINE_MAX_VERSION, 14);
  const v13 = sniffBytecode(Uint8Array.of(13, 3, 0));
  assert.equal(v13.dialect, "luau");
  assert.equal(v13.version, 13);
  assert.equal(v13.engineSupported, false);
  assert.equal(v13.backendEligible, true);

  const v14 = sniffBytecode(Uint8Array.of(14, 3, 0));
  assert.equal(v14.engineSupported, false);
  assert.equal(v14.backendEligible, true);
});

test("unsupported future versions remain rejected", () => {
  assert.equal(sniffBytecode(Uint8Array.of(15, 3, 0)).dialect, null);
});
