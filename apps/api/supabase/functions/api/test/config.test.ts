import { assertEquals } from "@std/assert";
import { allowedOrigins, type Config } from "../_shared/config.ts";

function baseConfig(overrides: Partial<Config> = {}): Config {
  return {
    supabaseUrl: "https://example.supabase.co",
    supabaseAnonKey: "anon",
    supabaseJwtSecret: "secret",
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

Deno.test("allowedOrigins: development includes localhost vite ports", () => {
  const origins = allowedOrigins(baseConfig());
  assertEquals(origins.includes("http://localhost:5173"), true);
  assertEquals(origins.includes("http://127.0.0.1:4173"), true);
});

Deno.test("allowedOrigins: production excludes localhost", () => {
  const origins = allowedOrigins(baseConfig({ environment: "production" }));
  assertEquals(origins.includes("http://localhost:5173"), false);
});

Deno.test("allowedOrigins: frontendUrl trailing slash is stripped", () => {
  const origins = allowedOrigins(baseConfig({ environment: "production", frontendUrl: "https://app.example.com/" }));
  assertEquals(origins, ["https://app.example.com"]);
});

Deno.test("allowedOrigins: cors_allowed_origins is comma-split, trimmed, and de-duplicated", () => {
  const origins = allowedOrigins(
    baseConfig({
      environment: "production",
      frontendUrl: "https://app.example.com",
      corsAllowedOrigins: " https://staging.example.com/, https://app.example.com ,,",
    }),
  );
  assertEquals(origins, ["https://app.example.com", "https://staging.example.com"]);
});
