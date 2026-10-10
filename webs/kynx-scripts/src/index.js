// kynx-scripts: save / open code snippets. Cloudflare Worker + KV.
//   GET    /                      editor page
//   POST   /api/scripts           {code,title?} -> {id,token}   (token proves ownership, kept in the browser)
//   GET    /api/scripts/:id       -> {id,title,code,created,updated}
//   PUT    /api/scripts/:id       Bearer token, {code,title?}
//   DELETE /api/scripts/:id       Bearer token
//   GET    /raw/:id               plain text
// Scripts are stored, never executed.
import { PAGE } from "./page.js";

import { MAX_BYTES } from "./limits.js";
const ID_RE = /^[a-z0-9]{8,16}$/;
const enc = new TextEncoder();

const json = (obj, status = 200) =>
  new Response(JSON.stringify(obj), { status, headers: { "content-type": "application/json; charset=utf-8", "cache-control": "no-store" } });
const err = (msg, status) => json({ error: msg }, status);

function randomId(len = 10) {
  const a = "abcdefghijklmnopqrstuvwxyz0123456789";
  const b = crypto.getRandomValues(new Uint8Array(len));
  return Array.from(b, (x) => a[x % a.length]).join("");
}
async function sha256(s) {
  const d = await crypto.subtle.digest("SHA-256", enc.encode(s));
  return Array.from(new Uint8Array(d), (x) => x.toString(16).padStart(2, "0")).join("");
}
async function readBody(request) {
  let body;
  try { body = await request.json(); } catch { return { error: "Invalid JSON" }; }
  if (typeof body?.code !== "string" || body.code.length === 0) return { error: "code is required" };
  if (enc.encode(body.code).length > MAX_BYTES) return { error: `Too large (max ${MAX_BYTES} bytes)` };
  const title = typeof body.title === "string" ? body.title.slice(0, 80) : "";
  return { code: body.code, title };
}
const bearer = (request) => (request.headers.get("authorization") || "").replace(/^Bearer\s+/i, "");

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    const path = url.pathname.replace(/\/+$/, "") || "/";

    if (path === "/") {
      return new Response(PAGE.replace("${MAX}", String(MAX_BYTES)), {
        headers: { "content-type": "text/html; charset=utf-8", "x-content-type-options": "nosniff" },
      });
    }

    let m = path.match(/^\/raw\/([^/]+)$/);
    if (m) {
      if (!ID_RE.test(m[1])) return new Response("Not found", { status: 404 });
      const rec = await env.SCRIPTS.get(m[1], "json");
      if (!rec) return new Response("Not found", { status: 404 });
      return new Response(rec.code, {
        headers: { "content-type": "text/plain; charset=utf-8", "x-content-type-options": "nosniff", "cache-control": "no-store" },
      });
    }

    if (path === "/api/scripts" && request.method === "POST") {
      const b = await readBody(request);
      if (b.error) return err(b.error, 400);
      const id = randomId();
      const token = randomId(32);
      const now = Date.now();
      await env.SCRIPTS.put(id, JSON.stringify({ code: b.code, title: b.title, created: now, updated: now, tokenHash: await sha256(token) }));
      return json({ id, token }, 201);
    }

    m = path.match(/^\/api\/scripts\/([^/]+)$/);
    if (m) {
      const id = m[1];
      if (!ID_RE.test(id)) return err("Not found", 404);
      const rec = await env.SCRIPTS.get(id, "json");
      if (!rec) return err("Not found", 404);

      if (request.method === "GET") {
        return json({ id, title: rec.title, code: rec.code, created: rec.created, updated: rec.updated });
      }
      if (request.method === "PUT" || request.method === "DELETE") {
        const t = bearer(request);
        if (!t || (await sha256(t)) !== rec.tokenHash) return err("Not allowed (you can only change scripts saved from this browser)", 403);
        if (request.method === "DELETE") {
          await env.SCRIPTS.delete(id);
          return json({ ok: true });
        }
        const b = await readBody(request);
        if (b.error) return err(b.error, 400);
        await env.SCRIPTS.put(id, JSON.stringify({ ...rec, code: b.code, title: b.title, updated: Date.now() }));
        return json({ ok: true });
      }
      return err("Method not allowed", 405);
    }

    return new Response("Not found", { status: 404 });
  },
};
