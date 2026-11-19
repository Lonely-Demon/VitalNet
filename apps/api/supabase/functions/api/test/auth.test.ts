// Tests the novel, hand-rolled piece of Phase 3: hybrid local JWT
// verification (HS256 against SUPABASE_JWT_SECRET). The JWKS/ES256 path
// is jose's own well-tested code path (createRemoteJWKSet + jwtVerify)
// and requires a live network fetch to exercise for real, so it isn't
// re-tested here — this suite's job is proving OUR verifyToken()
// orchestration (which path wins, how failures are classified) is
// correct for the path that doesn't need network: HS256.
import { assertEquals, assertRejects } from "@std/assert";
import { SignJWT } from "jose";
import {
  verifyToken,
  PROFILE_CACHE_MAX_ENTRIES,
  _resetProfileCacheForTest,
  _getProfileCacheSizeForTest,
  _setProfileCacheForTest,
  _hasProfileCacheKeyForTest,
} from "../_shared/auth.ts";
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
    groqApiKey: "",
    geminiApiKey: "",
    sarvamApiKey: "",
    vapidPublicKey: "",
    vapidPrivateKey: "",
    vapidSubject: "mailto:admin@example.com",
    dataRetentionDays: 0,
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

Deno.test("profileCache: enforces 10,000-entry upper bound and LRU eviction (A1-a)", () => {
  _resetProfileCacheForTest();
  assertEquals(_getProfileCacheSizeForTest(), 0);

  // Populate exactly PROFILE_CACHE_MAX_ENTRIES items
  for (let i = 0; i < PROFILE_CACHE_MAX_ENTRIES; i++) {
    _setProfileCacheForTest(`user-${i}`, {
      checkedAt: Date.now() / 1000,
      isActive: true,
      role: "doctor",
      facilityId: null,
    });
  }
  assertEquals(_getProfileCacheSizeForTest(), PROFILE_CACHE_MAX_ENTRIES);
  assertEquals(_hasProfileCacheKeyForTest("user-0"), true);
  assertEquals(_hasProfileCacheKeyForTest(`user-${PROFILE_CACHE_MAX_ENTRIES - 1}`), true);

  // Refresh user-0 by re-inserting (simulating cache hit refresh)
  _setProfileCacheForTest("user-0", {
    checkedAt: Date.now() / 1000,
    isActive: true,
    role: "doctor",
    facilityId: null,
  });

  // Adding one more entry triggers eviction of the OLDEST un-refreshed entry (user-1)
  _setProfileCacheForTest("user-overflow-1", {
    checkedAt: Date.now() / 1000,
    isActive: true,
    role: "doctor",
    facilityId: null,
  });

  // Bound strictly preserved
  assertEquals(_getProfileCacheSizeForTest(), PROFILE_CACHE_MAX_ENTRIES);
  // user-0 was refreshed, so it survived!
  assertEquals(_hasProfileCacheKeyForTest("user-0"), true);
  // user-1 was oldest un-refreshed, so it was evicted!
  assertEquals(_hasProfileCacheKeyForTest("user-1"), false);
  // new entry exists
  assertEquals(_hasProfileCacheKeyForTest("user-overflow-1"), true);
});

// Note: jwtLocalVerification=false and the JWKS/ES256 path both require a
// real network fetch against a live Supabase project's JWKS endpoint —
// not exercised here to keep this suite fast and network-independent (see
// this file's header). Covered by the local-only smoke test performed
// against the running function during Phase 3 development instead.
