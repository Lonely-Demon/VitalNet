// Supabase client factories — mirrors backend/app/core/database.py's
// three-client model exactly (see that file's module docstring for the
// full security rationale, ported verbatim below):
//   1. supabaseAnon  — anon key, public reads + auth-token network fallback.
//   2. getSupabaseForUser(token) — per-request client scoped to the
//      caller's JWT so Row Level Security applies. Used for all
//      user-facing data access, including the .rpc() calls to the
//      SECURITY DEFINER functions from phase28_security_definer_fns.sql.
//   3. supabaseAdmin — service_role key, bypasses RLS entirely. Reserved
//      for admin-only routes (Phase 4) — Tranche A (this function) never
//      uses it.
import { createClient, type SupabaseClient } from "@supabase/supabase-js";
import { getConfig } from "./config.ts";

let anonClient: SupabaseClient | null = null;

export function getSupabaseAnon(): SupabaseClient {
  if (!anonClient) {
    const config = getConfig();
    anonClient = createClient(config.supabaseUrl, config.supabaseAnonKey);
  }
  return anonClient;
}

/** A fresh client per call, scoped to the caller's JWT — deliberate, same
 * reasoning as the Python original: a shared client with a mutated
 * per-request auth token would race across concurrently-served requests. */
export function getSupabaseForUser(token: string): SupabaseClient {
  const config = getConfig();
  return createClient(config.supabaseUrl, config.supabaseAnonKey, {
    global: { headers: { Authorization: `Bearer ${token}` } },
    auth: { persistSession: false, autoRefreshToken: false },
  });
}

let adminClient: SupabaseClient | null = null;

/** service_role key — bypasses RLS entirely. Use ONLY inside an
 * admin-role-guarded route (Phase 4's admin_routes/dsr_routes port). */
export function getSupabaseAdmin(): SupabaseClient {
  if (!adminClient) {
    const config = getConfig();
    adminClient = createClient(config.supabaseUrl, config.supabaseServiceRoleKey, {
      auth: { persistSession: false, autoRefreshToken: false },
    });
  }
  return adminClient;
}

export function extractBearerToken(authorization: string | null | undefined): string {
  if (!authorization) {
    throw new HttpError(401, "Missing Authorization header");
  }
  const parts = authorization.trim().split(/\s+/, 2);
  if (parts.length !== 2 || parts[0]?.toLowerCase() !== "bearer") {
    throw new HttpError(401, "Malformed Authorization header");
  }
  const token = parts[1]?.trim() ?? "";
  if (token.split(".").length !== 3) {
    throw new HttpError(401, "Malformed bearer token");
  }
  return token;
}

export class HttpError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}
