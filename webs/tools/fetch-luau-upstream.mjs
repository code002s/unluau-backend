import { execFileSync } from "node:child_process";
import { mkdirSync, existsSync } from "node:fs";
import { join } from "node:path";

const dir = join(process.cwd(), "vendor", "luau", "source");
if (!existsSync(dir)) mkdirSync(dir, { recursive: true });
execFileSync("git", ["clone", "--depth", "1", "https://github.com/luau-lang/luau.git", dir], { stdio: "inherit" });
console.log(`Luau upstream cloned to ${dir}`);
