# Official Luau source integration

KYNX integrates with the official Luau implementation from Roblox:

https://github.com/luau-lang/luau

This directory is intentionally a fetch/build integration point rather than a copied snapshot. The official repository is large and is updated frequently. Run:

```bash
node tools/fetch-luau.mjs
```

That downloads the selected upstream ref into `vendor/luau/upstream`.

The official Luau implementation provides the compiler, VM, bytecode definitions, CLI and analyzer. It is **not a decompiler**. KYNX's decompiler remains a separate component.
