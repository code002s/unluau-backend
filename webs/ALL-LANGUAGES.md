# KYNX — all 10 languages in one project

The UI/API catalog contains:

- Lua 5.1
- Lua 5.2
- Lua 5.3
- Lua 5.4
- LuaJIT 2.0
- LuaJIT 2.1
- Luau / Roblox
- MoonScript
- Teal
- eLua

The official Luau repository is referenced and can be fetched into
`vendor/luau/source` with:

```bash
cd webs/kynx-full/upstream-worker
npm run fetch:luau:upstream
```

This intentionally does not claim that the official Luau compiler/VM is a decompiler.
Real Luau v13/v14 decompilation requires a decompiler engine that supports those bytecode
versions.
