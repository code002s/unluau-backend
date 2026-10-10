// kynx-upstream: Luau/Lua bytecode decompile engine backed by unluac-js/WASM.
// https://github.com/x3zvawq/unluac-rs — MIT licensed.

import { init, decompile, supportedOptionValues } from "./engine.js";
import {
  buildLuauOptions, buildOptions, resolveLuaDialect, sniffBytecode,
  ENGINE_MIN_VERSION, ENGINE_MAX_VERSION, ENGINE_WASM_MAX_VERSION,
  LUA_FAMILY_DIALECTS, LANGUAGE_NOTES, LANGUAGE_CATALOG,
} from "./luau-detect.js";
import { isAuthorized } from "./auth.js";
import { prepareLuauBytecode, LuauBytecodeError } from "./luau-bytecode.js";
import { decompileWithUnluau, luauBackendUrl } from "./luau-backend.js";

let initPromise = null;
function ensureInit() {
  if (!initPromise) initPromise = init();
  return initPromise;
}

function base64ToBytes(b64) {
  const bin = atob(b64);
  const bytes = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
  return bytes;
}

function json(obj, status = 200) {
  return new Response(JSON.stringify(obj), {
    status,
    headers: { "Content-Type": "application/json; charset=utf-8" },
  });
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);

    if (url.pathname !== "/health" && !isAuthorized(request, env)) {
      return new Response("Unauthorized", { status: 401 });
    }

    if (url.pathname === "/health") {
      return json({
        ok: true,
        engine: "kynx-multi-backend",
        lua: true,
        luajit: true,
        luau: true,
        roblox: true,
        luauBackend: Boolean(luauBackendUrl(env)),
        luauBackendName: "Unluau",
        luauWasmVersions: { min: ENGINE_MIN_VERSION, max: ENGINE_WASM_MAX_VERSION },
        luauBackendVersions: { min: ENGINE_MIN_VERSION, max: ENGINE_MAX_VERSION },
      });
    }

    if (url.pathname === "/languages") {
      return json({
        ok: true,
        languages: LANGUAGE_CATALOG,
        dialects: LUA_FAMILY_DIALECTS.concat("luau"),
        luauVersions: { min: ENGINE_MIN_VERSION, max: ENGINE_MAX_VERSION },
        luauWasmVersions: { min: ENGINE_MIN_VERSION, max: ENGINE_WASM_MAX_VERSION },
        notes: LANGUAGE_NOTES,
      });
    }

    if (url.pathname === "/luau/info" || url.pathname === "/lua/info") {
      if (request.method !== "POST") return json({ error: "Use POST" }, 405);
      let body;
      try { body = await request.json(); } catch { return json({ error: "Invalid JSON" }, 400); }
      const script = body?.script;
      if (typeof script !== "string" || script.length === 0) {
        return json({ error: 'Expected {"script":"<base64>"}' }, 400);
      }
      let bytes;
      try { bytes = base64ToBytes(script); } catch { return json({ error: "script is not valid base64" }, 400); }
      try {
        await ensureInit();
        const info = sniffBytecode(bytes);
        let structure = null;
        if (info.dialect === "luau") {
          try { structure = prepareLuauBytecode(bytes).info; }
          catch (e) { structure = { error: e.message }; }
        }
        return json({ ok: true, ...info, isLuau: info.dialect === "luau", bytes: bytes.length, structure });
      } catch (err) {
        return json({ ok: false, error: err?.message || String(err) }, 422);
      }
    }

    // Accept common aliases so clients posting to /api/decompile or /v1/decompile work.
    const DECOMPILE_PATHS = new Set([
      "/decompile",
      "/luau/decompile",
      "/lua/decompile",
      "/api/decompile",
      "/v1/decompile",
    ]);
    if (!DECOMPILE_PATHS.has(url.pathname)) {
      return new Response("Not found", { status: 404 });
    }
    if (request.method !== "POST") {
      return new Response("Use POST", { status: 405 });
    }

    let body;
    try {
      body = await request.json();
    } catch {
      return new Response("Invalid JSON", { status: 400 });
    }

    const script = body?.script;
    if (typeof script !== "string" || script.length === 0) {
      return new Response('Expected {"script":"<base64>"}', { status: 400 });
    }

    let bytes;
    try {
      bytes = base64ToBytes(script);
    } catch {
      return new Response("script is not valid base64", { status: 400 });
    }

    try {
      await ensureInit();

      // /luau/decompile is deliberately Luau-only. /decompile keeps the
      // original auto-detect behavior for Lua 5.x/LuaJIT as well.
      const info = sniffBytecode(bytes);
      const detected = info.dialect;
      const luauRequest = url.pathname === "/luau/decompile";
      const luaRequest = url.pathname === "/lua/decompile";
      if (luauRequest && detected !== "luau") {
        return new Response(`Expected Luau bytecode; ${detected ? "detected " + detected : info.reason}`, { status: 422 });
      }
      if (luaRequest && detected !== "lua" && detected !== "luajit") {
        return new Response(`Expected Lua 5.x / LuaJIT bytecode; ${detected ? "detected " + detected : info.reason}`, { status: 422 });
      }

      if (detected === "luajit" && !info.engineSupported) {
        return new Response(
          `LuaJIT dump version ${info.luajitVersion} is not supported by this engine (supports 2 = LuaJIT 2.1).`,
          { status: 422, headers: { "X-KYNX-Error": "unsupported-version", "X-KYNX-Bytecode-Version": String(info.luajitVersion) } },
        );
      }

      if (detected === "luau") {
        const hasBackend = Boolean(luauBackendUrl(env));
        // WASM engine only understands versions 3-7. Versions 8-14 need Unluau.
        if (info.version > ENGINE_WASM_MAX_VERSION) {
          if (!hasBackend) {
            return new Response(
              `Luau bytecode version ${info.version} is not supported by the bundled WASM engine ` +
              `(supports ${ENGINE_MIN_VERSION}-${ENGINE_WASM_MAX_VERSION}). ` +
              `Set LUAU_BACKEND_URL to an Unluau HTTP service for v8-v14, or recompile the script with ` +
              `luau-compile flags that emit version <= ${ENGINE_WASM_MAX_VERSION}.`,
              {
                status: 422,
                headers: {
                  "X-KYNX-Error": "unsupported-version",
                  "X-KYNX-Bytecode-Version": String(info.version),
                  "X-KYNX-Wasm-Max": String(ENGINE_WASM_MAX_VERSION),
                  "X-KYNX-Hint": "LUAU_BACKEND_URL or recompile-lower",
                },
              },
            );
          }
          // Backend will handle it; skip legacy walker.
          info.opcodeEncoding = "backend-native";
        } else if (!info.engineSupported) {
          return new Response(
            `Luau bytecode version ${info.version} is not supported by this engine (supports ${ENGINE_MIN_VERSION}-${ENGINE_WASM_MAX_VERSION}).`,
            { status: 422, headers: { "X-KYNX-Error": "unsupported-version", "X-KYNX-Bytecode-Version": String(info.version) } },
          );
        } else {
          try {
            // Legacy container parser/opcode normalization is verified against v5-v7 fixtures.
            const prepared = prepareLuauBytecode(bytes);
            bytes = prepared.bytes;
            info.opcodeEncoding = prepared.info.opcodeEncoding;
          } catch (e) {
            if (e instanceof LuauBytecodeError) {
              return new Response(`Invalid Luau bytecode: ${e.message}`, { status: 422, headers: { "X-KYNX-Error": "corrupt-input" } });
            }
            throw e;
          }
        }
      }

      let options;
      let engineDialect;
      if (detected === "luau") {
        engineDialect = "luau";
        options = buildLuauOptions(body?.options);

        // Prefer the dedicated Unluau backend for Roblox/Luau. The bundled WASM
        // engine remains the fallback for legacy Luau when no backend URL is set.
        if (luauBackendUrl(env)) {
          try {
            const source = await decompileWithUnluau(bytes, options, env);
            return new Response(source, {
              status: 200,
              headers: {
                "Content-Type": "text/plain; charset=utf-8",
                "X-KYNX-Dialect": "luau",
                "X-KYNX-Engine-Dialect": "unluau",
                "X-KYNX-Luau-Backend": "Unluau",
                ...(info.opcodeEncoding ? { "X-KYNX-Opcodes": info.opcodeEncoding } : {}),
              },
            });
          } catch (backendErr) {
            return new Response(`Luau/Roblox Unluau backend failed: ${backendErr?.message || backendErr}`, { status: 502 });
          }
        }
      } else if (detected === "lua" || detected === "luajit") {
        engineDialect = resolveLuaDialect(info, body?.dialect);
        options = buildOptions(engineDialect, body?.options);
      } else {
        // Unknown header: let the engine decide.
        engineDialect = "auto";
        options = { dialect: "auto" };
      }

      const source = await decompile(bytes, options);
      return new Response(source, {
        status: 200,
        headers: {
          "Content-Type": "text/plain; charset=utf-8",
          "X-KYNX-Dialect": detected || "unknown",
          "X-KYNX-Engine-Dialect": engineDialect,
          ...(info.opcodeEncoding ? { "X-KYNX-Opcodes": info.opcodeEncoding } : {}),
        },
      });
    } catch (err) {
      const message = err && err.message ? err.message : String(err);
      return new Response(`Decompilation failed: ${message}`, { status: 422 });
    }
  },
};
