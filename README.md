# unluau-backend

**Luau / Roblox bytecode decompiler (v3–v14) as an HTTP service.**
Luau / Roblox bytecode decompiler (v3–v14) as an HTTP service — the `LUAU_BACKEND_URL` for the KYNX Worker.

```
Roblox executor ──► KYNX Worker (Cloudflare) ──► unluau-backend (Render, Docker)
   bytecode              /decompile                 unluac-rs + v8–v14 parser
                                                            │
                                      readable Luau source ◄┘
```

## Features

- Reads **Luau bytecode v3–v14** (current Roblox uses v13+).
- Accepts dumps from executors with "scrambled" opcodes (`op * 227 mod 256`) — detects and decodes them automatically.
- Engine: [unluac-rs](https://github.com/x3zvawq/unluac-rs) (MIT): CFG construction → data flow analysis → structuring → code generation. Correct `for`/`while`, `and`/`or`, `continue`, strings, and `local` scopes.
- Local variable names are recovered using heuristics if debug names are missing from the bytecode.
- Vector constants are emitted as `Vector3.new(...)`.
- Complex control flows that cannot be structured are emitted as pseudocode instead of returning an error.

## Measured Quality

Validation: ~356 Luau scripts compiled with the official Luau compiler (v13), processed through the Luau parser (`luau-compile --only-parse`).

| | Unluau (previous engine) | unluac-rs + this patch |
|---|---|---|
| Files decompiled | 336 / 356 | **352 / 356** |
| Valid syntax results | ≈ 57 % | **351 / 352** |
| Versions 9, 11, 12, 13, 14 | — | **19 / 19 each** |

This is a check of **syntax and structure**, not a proof of identical behavior: the decompiler cannot recover original names, comments, or types; code without debug information receives generated names (`Parent2`, `value3`). Always verify results in Roblox Studio.

## API

`POST /decompile` (or `POST /`) — request body: raw bytecode.

```bash
curl -i --data-binary "@script.luauc" \
     -H "Content-Type: application/octet-stream" \
     https://unluau-backend.onrender.com/decompile
```

| Status | Value |
|---|---|
| `200 text/plain` | Luau source code |
| `400` | empty body |
| `401` | `Authorization: Bearer <BACKEND_TOKEN>` required (if token is set) |
| `413` | body larger than 16 MB |
| `422` | unsupported bytecode or decompiler failure (`{"error": "..."}`) |
| `500` / `504` | internal error / timeout |

`GET /health` → `{"ok": true, "engine": "unluac-rs", "luauVersions": "3-14"}`

Environment variables: `PORT`, `BACKEND_TOKEN` (optional), `MAX_CONCURRENT` (default 2), `DECOMPILE_TIMEOUT` (seconds, default 60).

## Deploy

1. Push the folder to the GitHub repository connected to the Render Docker service.
2. The first build compiles Rust (≈ 5–10 minutes).
3. In the Worker (`kynx-full/upstream-worker/wrangler.toml`):
   ```toml
   [vars]
   LUAU_BACKEND_URL = "https://unluau-backend.onrender.com/decompile"
   ```
   then `npx wrangler deploy`. Verification: the Worker's `/health` should show `"luauBackend": true`.

Render's free plan "sleeps"; the first request after inactivity may take over 30 seconds (Worker timeout) — open `/health` first.

## What the patch adds to unluac-rs

`unluac-rs/` — a copy of the upstream (MIT) with the Luau parser expanded from v7 to v14:

| Version | Support |
|---|---|
| v8 | 64-bit integer constants |
| v9 | runtime-only changes |
| v10 | "class form" constants (parsed; class opcodes are rejected) |
| v11 | `CALLFB`, feedback slot table |
| v12 | size prefix for each function, inline cost |
| v13 | double-precision vector constants |
| v14 | `FASTPCALL` |

Files: `src/parser/dialect/luau/{raw,parser}.rs`, `src/parser/reader.rs`, `src/transformer/dialect/luau/lower*`.
Roblox opcode decoding — `luau_descramble.py`.

## Local Execution

```bash
cd unluac-rs && cargo build --release -p unluac-cli      # Rust ≥ 1.94 required
UNLUAC_BIN=$PWD/target/release/unluac-cli PORT=8080 python3 ../server.py
curl --data-binary @../test/fixtures/v13_basic_O1_g1.luauc localhost:8080/decompile
```

Verification samples: `test/fixtures/` (standard v13, same file in Roblox encoding, v14, Roblox-like script).

## Limits

- Rare large scripts may fail to decompile: `FASTCALL` argument mismatch or rare upstream panics — in these cases, `422/500` with the reason is returned.
- Experimental Luau class opcodes (`NEWCLASS`, `NEWCLASSMEMBER`, `CMPPROTO`) are not supported.
- Without debug names, local variables receive generated names.
- The result is a reconstruction, not the original code.

## Licenses / Credits

- [unluac-rs](https://github.com/x3zvawq/unluac-rs) — MIT (`unluac-rs/LICENSE.txt`).
- Bytecode format — based on [Luau](https://github.com/luau-lang/luau) sources (MIT).
