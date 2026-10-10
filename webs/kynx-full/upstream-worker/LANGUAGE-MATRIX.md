# KYNX — all 10 language targets

KYNX exposes these ten targets in one catalog:

1. Lua 5.1
2. Lua 5.2
3. Lua 5.3
4. Lua 5.4
5. LuaJIT 2.0
6. LuaJIT 2.1
7. Luau / Roblox
8. MoonScript
9. Teal
10. eLua

## Important engine distinction

The selector/catalog can list all ten targets, but a selector entry does not magically add a
decompiler implementation. Lua/LuaJIT bytecode is handled by the configured bytecode engine.
MoonScript and Teal are source languages that normally compile to Lua, so they should be
handled as source-to-Lua rather than pretending they have an independent Lua bytecode format.
eLua is an embedded Lua distribution and follows the compatible Lua family.

## Official Luau source

The official Luau implementation is maintained at:

https://github.com/luau-lang/luau

It contains the compiler, VM, bytecode definitions, analyzer and CLI. It is **not itself a
decompiler**. KYNX therefore keeps the official Luau source as an upstream build dependency
rather than falsely treating the official repository as a decompiler.

For current Luau bytecode v13/v14 decompilation, KYNX still needs a decompiler engine whose
parser and instruction set actually support those versions.
