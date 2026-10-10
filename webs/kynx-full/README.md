# KYNX — full project

Two separate Cloudflare deployments that work together:

## 1. `kynx-site-v4/` — the frontend + proxy
The public site. `_worker.js` serves `index.html` and proxies several
decompile API shapes (`/decompile`, `/v4/decompile`, `/luau/decompile`,
`/konstant/decompile`, `/bytefall/decompile`, `/x2125/decompile`,
`/api/decompile`) to whatever URL is set in the `UPSTREAM` environment
variable.

Deploy:
```
cd kynx-site-v4
wrangler pages deploy . --project-name=kynx-site
```

## 2. `upstream-worker/` — the real decompile engine
A standalone Worker backed by `unluac-js` (github.com/x3zvawq/unluac-rs),
a real Lua/Luau bytecode decompiler compiled to WASM. Exposes `POST /decompile`
taking `{"script":"<base64>"}` and returning plain-text source.

Deploy:
```
cd upstream-worker
npm install
wrangler deploy
```
Copy the URL wrangler prints (e.g. `https://kynx-upstream.<subdomain>.workers.dev`).

## Wiring them together
In the Cloudflare dashboard: **kynx-site → Settings → Environment variables**,
set:
```
UPSTREAM = https://kynx-upstream.<subdomain>.workers.dev/decompile
```
then redeploy `kynx-site-v4` so it picks up the change.

## Notes
- `upstream-worker` is a genuinely early/actively-developing decompiler —
  expect it to fail cleanly (422 "Decompilation failed: ...") on complex,
  obfuscated, or edge-case bytecode rather than always producing perfect output.
- If `UPSTREAM` is left unset, `kynx-site-v4` falls back to the default
  `https://kynx-upstream.kynxyy.workers.dev/decompile`. Set `UPSTREAM` to your own
  worker URL if yours has a different subdomain.

## Securing the upstream worker
`upstream-worker` is open to anyone who knows its URL unless a token is set.
To lock it (everything except `/health` then needs `Authorization: Bearer <token>`):
```
cd upstream-worker && npx wrangler secret put UPSTREAM_TOKEN
```
and set the same value as the `UPSTREAM_TOKEN` secret on the `kynx-site` Pages
project, which sends it automatically.

## Luau support update

The upstream worker now has an explicit Luau path:

- `POST /luau/decompile` requires detected Luau bytecode and decompiles with `dialect: "luau"`.
- `POST /luau/info` detects the bytecode dialect and returns basic metadata.
- `POST /decompile` keeps the original automatic Lua/Luau detection behavior.
- Luau decompile options can be passed as `{"options": {...}}`; only documented/safe options are accepted.
- `upstream-worker/src/luau-detect.js` contains the Luau-specific option validation and dialect detection wrapper.
- `unluac-js` is pinned to `1.4.3`, whose published WASM build supports the Luau dialect.

This does **not** claim support for private/proprietary Roblox bytecode encodings that are not understood by the bundled WASM parser. Such input must first be converted to a supported Luau bytecode format.

## Luau notes (fixes on top of the previous update)
- `unluac-js` 1.4.3 has no `detectDialect` export; `src/luau-detect.js` now sniffs the header itself
  (Luau version byte, `ESC Lua`, `ESC LJ`, source text, compile-error chunk).
- `kynx-site-v4/_worker.js` now forwards `/luau/decompile` to the upstream's `/luau/decompile`
  (before, every route hit `/decompile`, so the Luau-only mode never ran from the site).
- Roblox client-encoded opcodes (opcode multiplier) are NOT handled; that would need a normalize step before decompiling.

## Luau pipeline (current state)
- `src/luau-detect.js` sniffs the header (Luau 3-14, Lua, LuaJIT, source text, compile-error chunk) and whitelists decompiler options.
- `src/luau-bytecode.js` parses the Luau container, validates it, and undoes the Roblox client opcode encoding (op*227) when detected.
- `npm test` (in `upstream-worker/`) runs tests on bytecode produced by a real Luau 0.700 compiler (v6); fixtures in `test/fixtures/`.
- Deploy note: src/unluac_wasm.js + src/engine.js load the WASM directly; the unluac-js wrapper dynamic import fails on Cloudflare (No such module "unluac_wasm.js").
- Engine range: the bundled WASM decompiles versions 5-7 and rejects 8-14 (current Luau emits 14). Such files get a clear 422 error.
- Not verified: real Roblox-client dumps. The opcode decoding is only round-trip tested. Send a real dump to confirm.

## Lua family (5.1-5.5, LuaJIT)
- `POST /lua/decompile` (upstream and site) decompiles Lua 5.x / LuaJIT bytecode; the dialect comes from the header (`ESC Lua` + version byte, `ESC LJ`) and can be forced with `"dialect"`.
- `POST /decompile` now picks the dialect from the header for Lua too (was `auto`) and applies the same whitelisted options.
- `GET /languages` lists dialects and notes. Response header `X-KYNX-Engine-Dialect` shows what was used.
- LuaJIT 2.0 dumps (version 1) and Luau bytecode 8-14 are rejected with 422 (`X-KYNX-Error: unsupported-version`).


## Language catalog

The web UI now exposes one language selector and catalog for:

- Lua 5.1
- Lua 5.2
- Lua 5.3
- Lua 5.4
- LuaJIT 2.0
- LuaJIT 2.1
- Luau / Roblox
- MoonScript (source -> Lua)
- Teal (source -> Lua)
- eLua (embedded Lua family)

`GET /languages` on the Pages site returns the same catalog as JSON. MoonScript and Teal are not bytecode dialects, so the decompiler accepts their compiled Lua bytecode rather than pretending there is a separate MoonScript/Teal chunk format.

## Official Luau integration

KYNX now includes an integration point for the official Roblox Luau implementation:

- https://github.com/luau-lang/luau
- `node tools/fetch-luau.mjs` fetches the upstream source.
- `tools/build-luau-web.sh` builds the official Luau Web target with Emscripten.

The official Luau repository supplies the compiler/VM/bytecode definitions, not a decompiler. KYNX therefore keeps the decompiler engine separate while using the official bytecode definitions as the compatibility reference.

## Changelog: site v4

- New **About / API** page (`#/about`, old `#/api` still works): KYNX and Luau overview, supported languages, endpoint table, `POST /decompile` and `GET /health` docs, cURL / JavaScript / loader examples, tables of request headers, response headers, query parameters and response codes, limits and notes, links and alternatives.
- Navigation: About / API button in the decompiler header, About link in the footer, back link to Decompiler on the About page.
- Decompiler: three input modes (File, Hex / Base64, Raw), dialect selector (Auto, Luau, Lua 5.1 to 5.5, LuaJIT), renaming INFER / RAW, Disassemble, Wrap, Copy, Save .lua, Ctrl+Enter, size / lines / time stats.
- `_worker.js`: `GET /health` (site + upstream), `/api/health`, `/v1/decompile`, `POST /api/disassemble` (501), CORS with `OPTIONS` preflight, query parameters `dialect`, `renaming`, `mode`.
