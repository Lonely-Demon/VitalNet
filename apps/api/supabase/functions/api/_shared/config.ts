// Deno.env-backed settings, mirroring backend/app/core/config.py's field
// names exactly (same env var names across both runtimes during the
// transition, so a project's existing secrets work unchanged) — but this
// is the edge function's own copy, not a shared import: Deno and the
// FastAPI backend are different deployables that happen to read the same
// environment.

export interface Config {
  supabaseUrl: string;
  supabaseAnonKey: string;
  supabaseJwtSecret: string;
  supabaseServiceRoleKey: string;
  environment: "development" | "staging" | "production";
  corsAllowedOrigins: string;
  frontendUrl: string;
  jwtLocalVerification: boolean;
  revocationRecheckSeconds: number;
  csrfToken: string;
  // ── Phase 4 (Tranche B) additions ──────────────────────────────────────
  groqApiKey: string;
  geminiApiKey: string;
  sarvamApiKey: string;
  vapidPublicKey: string;
  vapidPrivateKey: string;
  vapidSubject: string;
  dataRetentionDays: number;
}

function env(name: string): string {
  return Deno.env.get(name) ?? "";
}

function envBool(name: string, fallback: boolean): boolean {
  const raw = Deno.env.get(name);
  if (raw === undefined || raw === "") return fallback;
  return raw.toLowerCase() === "true" || raw === "1";
}

function envInt(name: string, fallback: number): number {
  const raw = Deno.env.get(name);
  if (raw === undefined || raw === "") return fallback;
  const n = Number.parseInt(raw, 10);
  return Number.isFinite(n) ? n : fallback;
}

let cached: Config | null = null;

/** Reads Deno.env once per isolate and caches — env vars don't change
 * mid-invocation, and re-reading on every request is pointless work. */
export function getConfig(): Config {
  if (cached) return cached;
  const environment = env("ENVIRONMENT") || "development";
  cached = {
    supabaseUrl: env("SUPABASE_URL"),
    supabaseAnonKey: env("SUPABASE_ANON_KEY"),
    supabaseJwtSecret: env("SUPABASE_JWT_SECRET"),
    supabaseServiceRoleKey: env("SUPABASE_SERVICE_ROLE_KEY"),
    environment: environment === "staging" || environment === "production" ? environment : "development",
    corsAllowedOrigins: env("CORS_ALLOWED_ORIGINS"),
    frontendUrl: env("FRONTEND_URL"),
    jwtLocalVerification: envBool("JWT_LOCAL_VERIFICATION", true),
    revocationRecheckSeconds: envInt("REVOCATION_RECHECK_SECONDS", 300),
    csrfToken: env("CSRF_TOKEN") || "vitalnet-spa",
    groqApiKey: env("GROQ_API_KEY"),
    geminiApiKey: env("GEMINI_API_KEY"),
    sarvamApiKey: env("SARVAM_API_KEY"),
    vapidPublicKey: env("VAPID_PUBLIC_KEY"),
    vapidPrivateKey: env("VAPID_PRIVATE_KEY"),
    vapidSubject: env("VAPID_SUBJECT") || "mailto:admin@example.com",
    dataRetentionDays: envInt("DATA_RETENTION_DAYS", 0),
  };
  return cached;
}

/** Test-only: force-inject a config so tests don't depend on real env vars. */
export function _setConfigForTest(next: Config): void {
  cached = next;
}

export function allowedOrigins(config: Config): string[] {
  const origins: string[] = [];
  if (config.environment === "development") {
    origins.push(
      "http://localhost:5173",
      "http://127.0.0.1:5173",
      "http://localhost:4173",
      "http://127.0.0.1:4173",
    );
  }
  if (config.frontendUrl) {
    origins.push(config.frontendUrl.replace(/\/+$/, ""));
  }
  if (config.corsAllowedOrigins) {
    for (const origin of config.corsAllowedOrigins.split(",")) {
      const trimmed = origin.trim().replace(/\/+$/, "");
      if (trimmed) origins.push(trimmed);
    }
  }
  return [...new Set(origins)];
}
