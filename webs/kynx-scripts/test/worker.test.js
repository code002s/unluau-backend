import { test } from "node:test";
import assert from "node:assert/strict";
import worker from "../src/index.js";
import { MAX_BYTES } from "../src/limits.js";

const kv = new Map();
const env = { SCRIPTS: {
  async get(k, t) { const v = kv.get(k); return v === undefined ? null : t === "json" ? JSON.parse(v) : v; },
  async put(k, v) { kv.set(k, v); },
  async delete(k) { kv.delete(k); },
} };
const call = (path, init) => worker.fetch(new Request("https://x.test" + path, init), env);
const post = (b) => ({ method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(b) });

test("page loads with limit filled in", async () => {
  const t = await (await call("/")).text();
  assert.match(t, /KYNX Scripts/);
  assert.ok(t.includes(String(MAX_BYTES)) && !t.includes("${MAX}"));
});

test("save, open, raw, update, delete", async () => {
  const r = await call("/api/scripts", post({ code: "print('hi')", title: "t" }));
  assert.equal(r.status, 201);
  const { id, token } = await r.json();
  assert.equal((await (await call("/api/scripts/" + id)).json()).code, "print('hi')");
  assert.equal(await (await call("/raw/" + id)).text(), "print('hi')");
  assert.ok(!JSON.stringify(await (await call("/api/scripts/" + id)).json()).includes("tokenHash"));

  const bad = await call("/api/scripts/" + id, { ...post({ code: "x" }), method: "PUT", headers: { "content-type": "application/json", authorization: "Bearer nope" } });
  assert.equal(bad.status, 403);
  const ok = await call("/api/scripts/" + id, { method: "PUT", headers: { "content-type": "application/json", authorization: "Bearer " + token }, body: JSON.stringify({ code: "v2" }) });
  assert.equal(ok.status, 200);
  assert.equal(await (await call("/raw/" + id)).text(), "v2");

  assert.equal((await call("/api/scripts/" + id, { method: "DELETE", headers: { authorization: "Bearer " + token } })).status, 200);
  assert.equal((await call("/api/scripts/" + id)).status, 404);
});

test("validation", async () => {
  assert.equal((await call("/api/scripts", post({ code: "" }))).status, 400);
  assert.equal((await call("/api/scripts", post({ code: "a".repeat(MAX_BYTES + 1) }))).status, 400);
  assert.equal((await call("/api/scripts", { method: "POST", body: "nope" })).status, 400);
  assert.equal((await call("/api/scripts/../../etc")).status, 404);
  assert.equal((await call("/raw/BAD!")).status, 404);
});
