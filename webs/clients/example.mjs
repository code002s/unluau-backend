// Node 18+: node example.mjs script.luauc
import { readFile } from "node:fs/promises";
const BASE = process.env.KYNX_BASE || "https://kynx-site.pages.dev";
const bytes = await readFile(process.argv[2]);
const b64 = bytes.toString("base64");

async function post(path, body, type) {
  const r = await fetch(BASE + path, { method: "POST", headers: { "Content-Type": type }, body });
  const t = await r.text();
  if (!r.ok) throw new Error(`${path} -> ${r.status}: ${t}`);
  return t;
}

console.log(await post("/konstant/decompile", bytes, "text/plain"));          // raw bytes
console.log(await post("/luau/decompile", b64, "text/plain"));                // base64 body
console.log(await post("/decompile", JSON.stringify({ script: b64 }), "application/json"));
console.log((JSON.parse(await post("/x2125/decompile", JSON.stringify({ script: b64, options: {} }), "application/json"))).data);
console.log((JSON.parse(await post("/api/decompile", JSON.stringify({ bytecodeBase64: b64 }), "application/json"))).output);
