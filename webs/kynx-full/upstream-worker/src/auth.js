// If the UPSTREAM_TOKEN secret is set, every request except /health must carry
// "Authorization: Bearer <token>". If it is not set the worker stays open (as before).
export function isAuthorized(request, env) {
  const expected = env && env.UPSTREAM_TOKEN;
  if (!expected) return true;
  const got = (request.headers.get("authorization") || "").replace(/^Bearer\s+/i, "");
  if (got.length !== expected.length) return false;
  let diff = 0; // constant-time compare
  for (let i = 0; i < got.length; i++) diff |= got.charCodeAt(i) ^ expected.charCodeAt(i);
  return diff === 0;
}
