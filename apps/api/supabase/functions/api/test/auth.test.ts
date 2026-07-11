// Tests the novel, hand-rolled piece of Phase 3: hybrid local JWT
// verification (HS256 against SUPABASE_JWT_SECRET). The JWKS/ES256 path
// is jose's own well-tested code path (createRemoteJWKSet + jwtVerify)
// and requires a live network fetch to exercise for real, so it isn't
// re-tested here — this suite's job is proving OUR verifyToken()
// orchestration (which path wins, how failures are classified) is
// correct for the path that doesn't need network: HS256.
import { assertEquals, assertRejects } from "@std/assert";
import { SignJWT } from "jose";
import { verifyToken } from "../_shared/auth.ts";
import { _setConfigForTest, type Config } from "../_shared/config.ts";
import { HttpError } from "../_shared/database.ts";

const SECRET = "test-secret-at-least-32-bytes-long-xxxx";

function testConfig(overrides: Partial<Config> = {}): Config {
  return {
    supabaseUrl: "https://example.supabase.co",
    supabaseAnonKey: "anon",
    supabaseJwtSecret: SECRET,
    supabaseServiceRoleKey: "service",
    environment: "development",
    corsAllowedOrigins: "",
    frontendUrl: "",
    jwtLocalVerification: true,
    revocationRecheckSeconds: 300,
    csrfToken: "vitalnet-spa",
    ...overrides,
  };
}

async function signToken(opts: {
  secret?: string;
  audience?: string;
  expiresInSeconds?: number;
  sub?: string;
} = {}): Promise<string> {
  const key = new TextEncoder().encode(opts.secret ?? SECRET);
  const now = Math.floor(Date.now() / 1000);
  return await new SignJWT({ sub: opts.sub ?? "user-123" })
    .setProtectedHeader({ alg: "HS256" })
    .setIssuedAt(now)
    .setExpirationTime(now + (opts.expiresInSeconds ?? 3600))
    .setAudience(opts.audience ?? "authenticated")
    .sign(key);
}

Deno.test("verifyToken: valid HS256 token verifies locally and returns the payload", async () => {
  _setConfigForTest(testConfig());
  const token = await signToken({ sub: "abc-123" });
  const payload = await verifyToken(token);
  assertEquals(payload.sub, "abc-123");
});

Deno.test("verifyToken: wrong secret is rejected", async () => {
  _setConfigForTest(testConfig());
  const token = await signToken({ secret: "a-completely-different-32-byte-secret!!" });
  await assertRejects(() => verifyToken(token), HttpError);
});

Deno.test("verifyToken: expired token is rejected", async () => {
  _setConfigForTest(testConfig());
  const token = await signToken({ expiresInSeconds: -10 });
  await assertRejects(() => verifyToken(token), HttpError);
});

Deno.test("verifyToken: wrong audience is rejected", async () => {
  _setConfigForTest(testConfig());
  const token = await signToken({ audience: "some-other-audience" });
  await assertRejects(() => verifyToken(token), HttpError);
});

Deno.test("verifyToken: malformed token is rejected without throwing an unhandled error", async () => {
  _setConfigForTest(testConfig());
  await assertRejects(() => verifyToken("not.a.jwt"), HttpError);
});

// Note: jwtLocalVerification=false and the JWKS/ES256 path both require a
// real network fetch against a live Supabase project's JWKS endpoint —
// not exercised here to keep this suite fast and network-independent (see
// this file's header). Covered by the local-only smoke test performed
// against the running function during Phase 3 development instead.
