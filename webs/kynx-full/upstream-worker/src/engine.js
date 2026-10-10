// Loads the unluac WASM directly. The unluac-js wrapper imports its glue with a
// dynamic import(variable), which Cloudflare's bundler cannot see, giving
// 'No such module "unluac_wasm.js"' at runtime. Importing the glue statically fixes that.
import wasmModule from "./unluac_wasm_bg.wasm";
import * as glue from "./unluac_wasm.js";

let initPromise = null;
export function init() {
  if (!initPromise) initPromise = glue.default({ module_or_path: wasmModule });
  return initPromise;
}

export async function decompile(bytes, options = {}) {
  await init();
  return glue.decompile(bytes, options);
}

export async function supportedOptionValues() {
  await init();
  return glue.supportedOptionValues();
}
