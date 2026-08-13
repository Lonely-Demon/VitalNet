// Hybrid JWT verification — ported from backend/app/core/auth.py, but
// fixes the "dead fast path" finding (DECISIONS.md §29): the Python
// version's fast path is local HS256 decode, which ALWAYS fails (falling
// through to a network get_user() call, on every single request) for a
// project using Supabase's newer asymmetric (ES256/RS256) signing keys.
// Here, BOTH verification paths are local: HS256 against
// SUPABASE_JWT_SECRET, or JWKS against Supabase's public keyset (fetched
// once per isolate and cached in-process by jose's createRemoteJWKSet —
// no per-request network round-trip either way). Whichever one matches
// the project's actual signing algorithm succeeds; there is no network
// fallback left to be "dead."
//
// Authorization fields: role and facility_id are NEVER trusted from the
// JWT's user_metadata (client-settable at signup, can go stale after an
// admin changes it) — every request resolves fresh values from the
// profiles table, cached per-isolate for revocationRecheckSeconds, same
// contract as the Python _resolve_profile.
import { createRemoteJWKSet, type JWTPayload, jwtVerify } from "jose";
import type { Context, Next } from "hono";
import { getConfig } from "./config.ts";
import { extractBearerToken, getSupabaseForUser, HttpError } from "./database.ts";
import type { AppEnv, AuthedUser } from "./types.ts";

export type { AuthedUser } from "./types.ts";

const AUDIENCE = "authenticated";

let remoteJwks: ReturnType<typeof createRemoteJWKSet> | null = null;

function getRemoteJwks() {
  if (!remoteJwks) {
    const config = getConfig();
    remoteJwks = createRemoteJWKSet(new URL(`${config.supabaseUrl}/auth/v1/.well-known/jwks.json`));
  }
  return remoteJwks;
}

/** Test-only: reset the cached JWKS fetcher between tests. */
export function _resetJwksForTest(): void {
  remoteJwks = null;
}

async function verifyLocalHS256(token: string): Promise<JWTPayload | null> {
  const config = getConfig();
  if (!config.supabaseJwtSecret) return null;
  try {
    const secret = new TextEncoder().encode(config.supabaseJwtSecret);
    const { payload } = await jwtVerify(token, secret, { algorithms: ["HS256"], audience: AUDIENCE });
    return payload;
  } catch {
    return null;
  }
}

async function verifyRemoteJwks(token: string): Promise<JWTPayload | null> {
  try {
    const { payload } = await jwtVerify(token, getRemoteJwks(), { audience: AUDIENCE });
    return payload;
  } catch {
    return null;
  }
}

export async function verifyToken(token: string): Promise<JWTPayload> {
  const config = getConfig();
  if (config.jwtLocalVerification) {
    const hs256 = await verifyLocalHS256(token);
    if (hs256) return hs256;
  }
  const jwks = await verifyRemoteJwks(token);
  if (jwks) return jwks;
  throw new HttpError(401, "Invalid or expired token");
}

interface ProfileCacheEntry {
  checkedAt: number; // seconds
  isActive: boolean;
  role: string;
  facilityId: string | null;
}

// Per-isolate cache — an edge isolate roughly corresponds to one FastAPI
// worker process for this purpose; each maintains its own cache and
// re-checks within the TTL, same bound as the Python original.
const profileCache = new Map<string, ProfileCacheEntry>();

/** Test-only: clear the cache between tests. */
export function _resetProfileCacheForTest(): void {
  profileCache.clear();
}

export async function resolveProfile(
  userId: string,
  token: string,
): Promise<{ isActive: boolean; role: string; facilityId: string | null }> {
  const config = getConfig();
  const now = Date.now() / 1000;
  const cached = profileCache.get(userId);
  if (cached && now - cached.checkedAt < config.revocationRecheckSeconds) {
    return cached;
  }

  try {
    const db = getSupabaseForUser(token);
    const { data, error } = await db
      .from("profiles")
      .select("role, facility_id, is_active")
      .eq("id", userId)
      .maybeSingle();
    if (error) throw error;

    if (!data) {
      // Confirmed: no profile row for this authenticated user. Fail closed.
      const entry: ProfileCacheEntry = { checkedAt: now, isActive: false, role: "", facilityId: null };
      profileCache.set(userId, entry);
      return entry;
    }

    const entry: ProfileCacheEntry = {
      checkedAt: now,
      isActive: data.is_active ?? true,
      role: data.role ?? "",
      facilityId: data.facility_id ?? null,
    };
    profileCache.set(userId, entry);
    return entry;
  } catch {
    // Transient failure — do not cache; fall back to last known state so
    // an outage doesn't lock out every authenticated user.
    if (cached) return cached;
    return { isActive: true, role: "", facilityId: null };
  }
}

export async function getCurrentUser(authorization: string | null | undefined): Promise<AuthedUser> {
  const token = extractBearerToken(authorization);
  const payload = await verifyToken(token);

  const userId = typeof payload.sub === "string" ? payload.sub : undefined;
  let role = "";
  let facilityId: string | null = null;
  if (userId) {
    const { isActive, role: r, facilityId: f } = await resolveProfile(userId, token);
    if (!isActive) {
      throw new HttpError(403, "Account is deactivated or not provisioned. Contact your administrator.");
    }
    role = r;
    facilityId = f;
  }

  return { ...payload, resolvedRole: role, resolvedFacilityId: facilityId, token };
}

/**
 * Best-effort extraction of a VERIFIED user id for rate-limiting keys —
 * ported from verify_sub_for_rate_limit (app/core/auth.py). Returns the
 * sub only if the token verifies (locally, either signing algorithm);
 * returns null otherwise so the caller falls back to IP-based limiting.
 * Prevents an attacker forging a token with a victim's sub to consume the
 * victim's rate-limit budget.
 */
export async function verifiedSubForRateLimit(token: string): Promise<string | null> {
  try {
    const payload = await verifyToken(token);
    return typeof payload.sub === "string" ? payload.sub : null;
  } catch {
    return null;
  }
}

/** Hono middleware factory — enforces the caller has one of the given
 * roles, setting c.set("user", ...) for downstream handlers. Usage:
 * app.get("/api/x", requireRole("doctor", "admin"), handler) */
export function requireRole(...roles: string[]) {
  return async (c: Context<AppEnv>, next: Next) => {
    const user = await getCurrentUser(c.req.header("authorization"));
    if (!roles.includes(user.resolvedRole)) {
      throw new HttpError(403, `Role '${user.resolvedRole}' is not permitted for this endpoint.`);
    }
    c.set("user", user);
    await next();
  };
}
