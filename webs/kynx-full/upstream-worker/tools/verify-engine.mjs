import { readFileSync } from "node:fs";
import { join } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const root = new URL("..", import.meta.url);
const gluePath = new URL("src/unluac_wasm.js", root);
const wasmPath = new URL("src/unluac_wasm_bg.wasm", root);
const glue = await import(pathToFileURL(fileURLToPath(gluePath)).href);
const wasm = readFileSync(fileURLToPath(wasmPath));
await glue.default({ module_or_path: wasm });

const values = glue.supportedOptionValues();
const dialects = values?.dialects ?? [];
if (!dialects.includes("luau")) throw new Error("Installed WASM does not expose the Luau dialect");

// This is a container-level capability gate. Full semantic v13/v14 verification
// must use real v13/v14 bytecode fixtures; the build is not allowed to claim support
// merely because a version constant was changed in KYNX.
console.log("Luau dialect is present in the installed WASM backend.");
console.log("Real v13/v14 fixture verification is required before production deploy.");