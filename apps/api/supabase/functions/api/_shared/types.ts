// Shared types — lets c.get("user")/c.set("user", ...) type-check across
// every route/middleware module without each one redeclaring the same
// Hono Variables map, and avoids a circular import between auth.ts and
// this file (AuthedUser lives here; auth.ts imports and re-exports it).
import type { JWTPayload } from "jose";

export interface AuthedUser extends JWTPayload {
  resolvedRole: string;
  resolvedFacilityId: string | null;
  /** The raw bearer token — routes need it to build their own
   * getSupabaseForUser() client for RLS-scoped queries/.rpc() calls. */
  token: string;
}

export interface AppEnv {
  Variables: {
    user: AuthedUser;
    correlationId: string;
  };
}
