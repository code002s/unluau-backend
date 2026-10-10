import { fileURLToPath } from "node:url";
import { mkdir, rm, cp } from "node:fs/promises";
import { existsSync } from "node:fs";
import { execFile } from "node:child_process";
import { promisify } from "node:util";
import { dirname, resolve } from "node:path";

const exec = promisify(execFile);
const root = resolve(dirname(fileURLToPath(import.meta.url)), "../vendor/luau");
const target = resolve(root, "upstream");
const ref = process.env.LUAU_REF || "master";

await mkdir(root, { recursive: true });
if (existsSync(resolve(target, ".git"))) {
  await exec("git", ["-C", target, "fetch", "origin", ref, "--depth", "1"]);
  await exec("git", ["-C", target, "checkout", "FETCH_HEAD"]);
} else {
  await rm(target, { recursive: true, force: true });
  await exec("git", ["clone", "--depth", "1", "--branch", ref, "https://github.com/luau-lang/luau.git", target]);
}
console.log(`Luau ${ref} fetched to ${target}`);
