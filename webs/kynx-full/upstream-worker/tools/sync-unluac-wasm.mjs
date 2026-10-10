import { copyFileSync, existsSync, mkdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = dirname(fileURLToPath(import.meta.url));
const packageDir = join(root, "..", "node_modules", "unluac-js");
const sourceGlue = join(packageDir, "unluac_wasm.js");
const sourceWasm = join(packageDir, "unluac_wasm_bg.wasm");
const targetDir = join(root, "..", "src");
const targetGlue = join(targetDir, "unluac_wasm.js");
const targetWasm = join(targetDir, "unluac_wasm_bg.wasm");

if (!existsSync(sourceGlue) || !existsSync(sourceWasm)) {
  throw new Error("unluac-js WASM assets are missing. Run npm install before deploying.");
}
mkdirSync(targetDir, { recursive: true });
copyFileSync(sourceGlue, targetGlue);
copyFileSync(sourceWasm, targetWasm);
console.log("Synced unluac-js WASM assets into src/ for the Cloudflare Worker bundle.");
