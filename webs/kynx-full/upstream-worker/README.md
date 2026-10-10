# KYNX Upstream Worker


## Luau v13/v14 engine refresh

`npm install` runs `tools/sync-unluac-wasm.mjs`, copying the WASM glue and binary from the
installed `unluac-js` package into `src/` before Cloudflare bundling. The dependency is set
to `^1.4.4` so a fresh install does not keep the old 1.4.3 WASM binary.

The legacy local container walker/opcode normalizer is only used for Luau v3-v7, where this
repository has regression fixtures. Luau v8-v14 are passed to the updated WASM parser because
those versions add constant tags, opcode changes, and (v12+) proto serialization changes.

Before production rollout, install dependencies and run `npm test`; additionally test with a
real bytecode-v13 fixture from the target source. Roblox-client opcode-encoded v13 fixtures
must be verified separately; the legacy opcode normalizer is not claimed to support them.
