// Luau/Roblox backend bridge.
// Cloudflare Workers cannot execute .NET binaries, so Luau decompilation can be
// delegated to an Unluau HTTP service. Lua/LuaJIT remain in the bundled WASM engine.

export function luauBackendUrl(env) {
  const raw = env?.LUAU_BACKEND_URL;
  if (typeof raw !== "string" || !raw.trim()) return null;
  try { return new URL(raw); } catch { throw new Error("LUAU_BACKEND_URL is not a valid URL"); }
}

export async function decompileWithUnluau(bytes, options = {}, env) {
  const target = luauBackendUrl(env);
  if (!target) return null;

  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 30_000);
  try {
    const response = await fetch(target.href, {
      method: "POST",
      headers: {
        "Content-Type": "application/octet-stream",
        "Accept": "text/plain, application/json",
      },
      body: bytes,
      signal: controller.signal,
    });
    const body = await response.text();
    if (!response.ok) throw new Error(body || `Unluau backend returned HTTP ${response.status}`);
    return body;
  } finally {
    clearTimeout(timer);
  }
}
