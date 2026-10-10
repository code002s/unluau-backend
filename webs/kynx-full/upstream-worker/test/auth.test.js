import { test } from "node:test";
import assert from "node:assert/strict";
import { isAuthorized } from "../src/auth.js";
const req = (h) => new Request("https://x.test/decompile", { headers: h });
test("open when no token configured", () => assert.equal(isAuthorized(req({}), {}), true));
test("requires the bearer token when configured", () => {
  const env = { UPSTREAM_TOKEN: "s3cret" };
  assert.equal(isAuthorized(req({}), env), false);
  assert.equal(isAuthorized(req({ authorization: "Bearer nope" }), env), false);
  assert.equal(isAuthorized(req({ authorization: "Bearer s3cret" }), env), true);
});
