import { execFileSync } from "node:child_process";
import { existsSync, mkdirSync, rmSync, copyFileSync } from "node:fs";
import { join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const root = resolve(fileURLToPath(new URL("..", import.meta.url)));
const vendor = join(root, ".vendor", "unluac-rs");
const wasmTarget = join(vendor, "target", "wasm32-unknown-unknown", "release", "unluac_wasm.wasm");
const out = join(root, "src");

function run(cmd, args, cwd = root) {
  console.log(`> ${cmd} ${args.join(" ")}`);
  execFileSync(cmd, args, { cwd, stdio: "inherit" });
}

if (!existsSync(join(vendor, ".git"))) {
  mkdirSync(join(root, ".vendor"), { recursive: true });
  run("git", ["clone", "--depth", "1", "https://github.com/x3zvawq/unluac-rs.git", vendor]);
} else {
  run("git", ["fetch", "--depth", "1", "origin", "main"], vendor);
  run("git", ["reset", "--hard", "origin/main"], vendor);
}

run("rustup", ["target", "add", "wasm32-unknown-unknown"]);
run("cargo", ["build", "-p", "unluac-wasm", "--release", "--target", "wasm32-unknown-unknown"], vendor);

if (!existsSync(wasmTarget)) throw new Error(`WASM build did not produce ${wasmTarget}`);
run("wasm-bindgen", [wasmTarget, "--target", "web", "--out-dir", join(root, ".generated-unluac")]);

mkdirSync(out, { recursive: true });
copyFileSync(join(root, ".generated-unluac", "unluac_wasm.js"), join(out, "unluac_wasm.js"));
copyFileSync(join(root, ".generated-unluac", "unluac_wasm_bg.wasm"), join(out, "unluac_wasm_bg.wasm"));
rmSync(join(root, ".generated-unluac"), { recursive: true, force: true });

console.log("Built and installed the current unluac-rs WASM backend.");
console.log("This backend tracks current Luau bytecode definitions; verify v13/v14 before deployment.");
