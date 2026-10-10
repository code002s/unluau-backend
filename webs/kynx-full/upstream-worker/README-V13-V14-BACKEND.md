# KYNX Luau v13/v14 backend fix

The old KYNX build changed the accepted version range to 3-14 while keeping an older WASM parser. That caused:

`unsupported luau bytecode version value 13`

This package does **not** fake support by changing a constant. The supported backend is rebuilt from the current `x3zvawq/unluac-rs` source and its WASM bindings.

## Windows

From `kynx-full\upstream-worker`:

```powershell
npm install
npm run build:engine
npm test
npx wrangler deploy
```

Requirements for `npm run build:engine`:
- Git
- Rust/rustup
- a Rust `wasm32-unknown-unknown` target
- `wasm-bindgen` CLI

Install the last tool if needed:

```powershell
cargo install wasm-bindgen-cli --version 0.2.115
```

The build script pulls the current unluac-rs source, builds `packages/unluac-wasm`, runs wasm-bindgen, and replaces the Worker-local WASM assets.

## Important

The official Luau project currently defines bytecode versions 3 through 14. v13 adds double-precision vector constants and v14 adds FASTPCALL. KYNX must test real v13/v14 chunks before advertising them as supported.

A version-range constant alone is never considered a fix.

## Roblox / Luau backend

For Roblox/Dex and current Luau bytecode, configure `LUAU_BACKEND_URL` to the dedicated Unluau HTTP adapter in `services/unluau-http`. The Worker routes detected Luau chunks to Unluau when this variable is present. Lua 5.x and LuaJIT continue using the bundled engine.
