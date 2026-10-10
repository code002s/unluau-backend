// KYNX v4: serves the site and mirrors several decompile API request formats on one domain.
// Every route forwards to the upstream engine (env.UPSTREAM, default kynx-upstream.kynxyy.workers.dev); only the request/response shape differs per route.
//
//   POST /decompile, /v4/decompile   JSON {"script":"<base64>"}                 -> text
//   POST /luau/decompile             body = base64 text (or the JSON form)       -> text
//   POST /lua/decompile              Lua 5.1-5.5 / LuaJIT bytecode, same body     -> text
//                                    optional JSON "dialect": lua5.1..lua5.5 | luajit
//   POST /konstant/decompile         body = raw bytecode bytes, text/plain       -> text
//   POST /bytefall/decompile         JSON {"script":"<base64>"}                  -> text
//   POST /x2125/decompile            JSON {"script":"<base64>", "options":{}}    -> JSON {"data": "<source>"}
//   POST /api/decompile              JSON {"bytecodeBase64":"<base64>"}          -> JSON {"ok":true,"output":"<source>"}
//   POST /v1/decompile               JSON {"script":"<base64>"}                  -> text
//   POST /api/disassemble            -> 501 (not supported yet)
//   GET  /health, /api/health        site + upstream status (JSON)
//   GET  /languages                  language catalog (JSON)
//
// Deploy by uploading this folder to Cloudflare Pages.

// Default engine. Override without editing code: set the UPSTREAM secret (and optionally UPSTREAM_TOKEN) on the Pages project.
const DEFAULT_UPSTREAM = "https://kynx-upstream.kynxyy.workers.dev/decompile"
const MAX_BYTES = 4 * 1024 * 1024;
const BASE64_RE = /^[A-Za-z0-9+/]+={0,2}$/;
const LANGUAGES = [
  { id: "lua5.1", name: "Lua 5.1", kind: "bytecode", status: "supported" },
  { id: "lua5.2", name: "Lua 5.2", kind: "bytecode", status: "supported" },
  { id: "lua5.3", name: "Lua 5.3", kind: "bytecode", status: "supported" },
  { id: "lua5.4", name: "Lua 5.4", kind: "bytecode", status: "supported" },
  { id: "luajit20", name: "LuaJIT 2.0", kind: "bytecode", status: "backend-dependent" },
  { id: "luajit21", name: "LuaJIT 2.1", kind: "bytecode", status: "supported" },
  { id: "luau", name: "Luau / Roblox", kind: "bytecode", status: "engine-dependent" },
  { id: "moonscript", name: "MoonScript", kind: "source", status: "catalogued" },
  { id: "teal", name: "Teal", kind: "source", status: "catalogued" },
  { id: "elua", name: "eLua", kind: "alias", status: "lua-family" },
];

const text = (body, status = 200) =>
  new Response(body, { status, headers: { "Content-Type": "text/plain; charset=utf-8" } });
const json = (obj, status = 200) =>
  new Response(JSON.stringify(obj), { status, headers: { "Content-Type": "application/json; charset=utf-8" } });

const FORMATS = {
  text:  { ok: (src) => text(src),                fail: (msg, status) => text(msg, status) },
  x2125: { ok: (src) => json({ data: src }),      fail: (msg, status) => json({ error: msg }, status) },
  sabre: { ok: (src) => json({ ok: true, output: src }), fail: (msg, status) => json({ ok: false, stage: "request", error: msg }, status) },
};

// path -> [input kind, output format]
const ROUTES = {
  "/decompile":          ["base64", "text"],
  "/v4/decompile":       ["base64", "text"],
  "/luau/decompile":     ["base64", "text"],
  "/lua/decompile":      ["base64", "text"],
  "/konstant/decompile": ["raw",    "text"],
  "/bytefall/decompile": ["base64", "text"],
  "/x2125/decompile":    ["base64", "x2125"],
  "/api/decompile":      ["base64", "sabre"],
  "/v1/decompile":       ["base64", "text"],
};

function bytesToBase64(bytes) {
  const CHUNK = 0x8000;
  let bin = "";
  for (let i = 0; i < bytes.length; i += CHUNK) {
    bin += String.fromCharCode.apply(null, bytes.subarray(i, i + CHUNK));
  }
  return btoa(bin);
}

// Returns { script, mode } (script is base64) or { error, status }.
async function readScript(request, input) {
  const declared = Number(request.headers.get("content-length") || 0);
  if (declared > MAX_BYTES * 1.4) return { error: "File too large (max 4 MB)", status: 413 };

  if (input === "raw") {
    const bytes = new Uint8Array(await request.arrayBuffer());
    if (bytes.length === 0) return { error: "Empty body", status: 400 };
    if (bytes.length > MAX_BYTES) return { error: "File too large (max 4 MB)", status: 413 };
    return { script: bytesToBase64(bytes) };
  }

  const body = (await request.text()).trim();
  if (!body) return { error: "Empty body", status: 400 };

  let script = body, mode, options, dialect;
  if (body.startsWith("{")) {
    let obj;
    try { obj = JSON.parse(body); } catch { return { error: "Invalid JSON", status: 400 }; }
    script = obj.script ?? obj.bytecodeBase64;
    mode = obj.mode;
    options = obj.options;
    dialect = typeof obj.dialect === "string" ? obj.dialect : undefined;
  }
  if (typeof script !== "string" || !BASE64_RE.test(script)) {
    return { error: 'Expected base64 bytecode (or JSON {"script":"<base64>"})', status: 400 };
  }
  if (script.length * 0.75 > MAX_BYTES) return { error: "File too large (max 4 MB)", status: 413 };
  return { script, mode, options, dialect };
}

async function handle(request, [input, format], env) {
  const out = FORMATS[format];
  if (request.method !== "POST") return out.fail("Use POST", 405);

  let target;
  try { target = new URL(env.UPSTREAM || DEFAULT_UPSTREAM); }
  catch { return out.fail("UPSTREAM is not a valid URL", 500); }
  if (target.host === new URL(request.url).host) {
    return out.fail("UPSTREAM points at this site. Set it to your decompiler server instead.", 500);
  }

  const parsed = await readScript(request, input);
  if (parsed.error) return out.fail(parsed.error, parsed.status);
  const q = new URL(request.url).searchParams;
  const dialect = parsed.dialect || q.get("dialect") || undefined;
  let options = parsed.options;
  const ren = (q.get("renaming") || "").toUpperCase();
  if (!options && (ren === "INFER" || ren === "RAW")) options = { naming: { mode: ren === "RAW" ? "simple" : "heuristic" } };
  if (parsed.mode === "disasm" || q.get("mode") === "disasm") return out.fail("Disassembly mode is not supported", 501);

  // /luau/decompile and /lua/decompile must reach the upstream's dialect-specific endpoints, not /decompile.
  const reqPath = new URL(request.url).pathname.replace(/\/+$/, "");
  if (reqPath === "/luau/decompile" || reqPath === "/lua/decompile") {
    target.pathname = target.pathname.replace(/\/decompile$/, reqPath);
  }

  const headers = { "Content-Type": "application/json" };
  if (env.UPSTREAM_TOKEN) headers.Authorization = `Bearer ${env.UPSTREAM_TOKEN}`;

  try {
    const upstream = await fetch(target.href, {
      method: "POST",
      headers,
      body: JSON.stringify({
        script: parsed.script,
        ...(options ? { options } : {}),
        ...(dialect ? { dialect } : {}),
      }),
    });
    const body = await upstream.text();
    return upstream.ok ? out.ok(body) : out.fail(body, upstream.status);
  } catch {
    return out.fail("Upstream unreachable", 502);
  }
}

const CORS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
  "Access-Control-Allow-Headers": "Content-Type, Authorization",
  "Access-Control-Max-Age": "86400",
};
const withCors = (res) => {
  const r = new Response(res.body, res);
  for (const [k, v] of Object.entries(CORS)) r.headers.set(k, v);
  return r;
};

// GET /health: checks this site and the upstream engine (falls back to site-only info if the engine is down).
async function health(env) {
  let target;
  try { target = new URL(env.UPSTREAM || DEFAULT_UPSTREAM); } catch { return json({ ok: false, error: "UPSTREAM is not a valid URL" }, 500); }
  target.pathname = "/health";
  try {
    const r = await fetch(target.href, { headers: { Accept: "application/json" } });
    const up = await r.json().catch(() => ({}));
    return json({ ok: r.ok && up.ok !== false, site: "kynx-site-v4", maxBytes: MAX_BYTES, upstream: up }, r.ok ? 200 : 502);
  } catch {
    return json({ ok: false, site: "kynx-site-v4", maxBytes: MAX_BYTES, error: "Upstream unreachable" }, 502);
  }
}

export default {
  async fetch(request, env) {
    const path = new URL(request.url).pathname.replace(/\/+$/, "") || "/";
    const api = path === "/health" || path === "/api/health" || path === "/languages" || path === "/api/disassemble" || ROUTES[path];
    if (api && request.method === "OPTIONS") return new Response(null, { status: 204, headers: CORS });
    if (path === "/health" || path === "/api/health") return withCors(await health(env));
    if (path === "/languages") return withCors(json({ ok: true, languages: LANGUAGES }));
    if (path === "/api/disassemble") {
      return withCors(request.method === "POST"
        ? json({ ok: false, stage: "request", error: "Disassembly mode is not supported" }, 501)
        : json({ ok: false, stage: "request", error: "Use POST" }, 405));
    }
    const route = ROUTES[path];
    if (route) return withCors(await handle(request, route, env));
    return env.ASSETS.fetch(request);
  },
};