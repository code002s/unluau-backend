# Fix: Luau bytecode version 13 is not supported

## Root cause

The bundled **unluac-rs WASM** parser only accepts Luau bytecode versions **3–7**
(`LUAU_BYTECODE_VERSION_MAX = 7` in unluac-rs). Official Luau now emits up to
version **14**. KYNX previously advertised 3–14 while still shipping the old WASM,
so v13 requests reached the engine and failed with:

```
Luau bytecode version 13 is not supported by this engine (supports 3-7)
```

Version 12+ also changes proto serialization (size prefix), so raising a constant
alone cannot decompile real v13 dumps.

## What this fix does

1. **Route aliases** — `POST /decompile`, `/api/decompile`, `/v1/decompile`,
   `/luau/decompile`, `/lua/decompile` all work (previously only the first three
   path styles without `/api` and `/v1` were registered, so those returned 404).
2. **Honest version gate**
   - WASM path: versions **3–7** only.
   - Versions **8–14**: require `LUAU_BACKEND_URL` pointing at the Unluau HTTP
     adapter (`services/unluau-http`). Without it, the worker returns a clear 422
     with `X-KYNX-Hint: LUAU_BACKEND_URL or recompile-lower`.
3. **Health / languages** report both `luauWasmVersions` and `luauBackendVersions`.

## How to decompile v13 today

### Option A — Unluau backend (recommended for Roblox / current Luau)

```bash
# From services/unluau-http (needs `unluau` binary on PATH)
python server.py
# then in Worker secrets / wrangler.toml:
# LUAU_BACKEND_URL = "http://your-host:8788/decompile"
npx wrangler deploy
```

### Option B — Recompile source to version ≤ 7

If you still have the `.lua` source:

```bash
luau-compile --binary -O1 \
  --fflags=LuauCompileFastpcall=false,LuauCompileEmitVectorDouble=false,LuauBytecodeCostModel=false,LuauEmitCallFeedback=false \
  script.lua > script.luauc
# First byte of script.luauc should be 6 or 7
```

Then `POST` the base64 of `script.luauc` to `/decompile`.

### Option C — Full native v13 in WASM (not done here)

Requires extending `unluac-rs` (`src/parser/dialect/luau/parser.rs`) for:
- v8 integer constants
- v9 atom userdata
- v10–11 class / feedback
- **v12 proto size prefix** (serialization break)
- v13 double-precision vectors
- v14 FASTPCALL

That is upstream work on [x3zvawq/unluac-rs](https://github.com/x3zvawq/unluac-rs).

## Deploy

```bash
cd kynx-upstream-fixed   # this package
npm install              # syncs WASM via postinstall
npm test
npx wrangler deploy
```

Set `LUAU_BACKEND_URL` if you need v8–v14.
