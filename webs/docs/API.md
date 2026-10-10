# KYNX API

Base: `https://kynx-site.pages.dev` — all routes are `POST`, max 4 MB bytecode.

| Route | Request body | Response |
|---|---|---|
| `/decompile`, `/v4/decompile`, `/bytefall/decompile` | JSON `{"script":"<base64>"}` | plain text |
| `/luau/decompile` | base64 text (or the JSON form); Luau only | plain text |
| `/lua/decompile` | same body; Lua 5.1–5.5 / LuaJIT 2.1 only. Optional JSON `"dialect"`: `lua5.1`…`lua5.5`, `luajit` | plain text |
| `/konstant/decompile` | raw bytes, `text/plain` | plain text |
| `/x2125/decompile` | JSON `{"script":"<base64>","options":{}}` | JSON `{"data":"<source>"}` |
| `/api/decompile` | JSON `{"bytecodeBase64":"<base64>"}` | JSON `{"ok":true,"output":"<source>"}` |

Errors: 400 bad input, 413 too large, 405 not POST, 422 decompile failed or unsupported Luau version (engine supports 5-7), 501 disassembly mode, 502 upstream unreachable.

Upstream (`kynx-upstream.kynxyy.workers.dev`): `POST /decompile` (auto-detects Lua 5.1–5.4 / LuaJIT 2.1 / Luau), `POST /luau/decompile`, `POST /lua/decompile`, `POST /luau/info`, `POST /lua/info`, `GET /languages`, `GET /health`. If `UPSTREAM_TOKEN` is set, send `Authorization: Bearer <token>` (not needed for `/health`).

Clients: `clients/KynxClient.lua` (Roblox ModuleScript), `clients/example.mjs` (Node), `clients/examples.sh` (curl).

## Supported languages

| Format | Status |
|---|---|
| Lua 5.1, 5.2, 5.3, 5.4 | supported (tested on real `string.dump` output) |
| Lua 5.5 | accepted by the engine, untested here |
| LuaJIT 2.1 (dump version 2) | supported |
| LuaJIT 2.0 (dump version 1) | rejected with 422 |
| Luau bytecode v3–7 | supported |
| Luau bytecode v8–14 (incl. v13) | rejected with 422: the bundled engine cannot read these yet (unluac-js 1.4.4 does not either) |
| MoonScript, Teal | no bytecode of their own; they compile to Lua, so you get Lua back |
| eLua | Lua 5.1/5.2, use those dialects |
