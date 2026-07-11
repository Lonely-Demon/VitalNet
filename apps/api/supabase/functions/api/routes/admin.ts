// Ported from app/api/routes/admin_routes.py — user, facility, stats and
// audit-log management. admin-only throughout; uses getSupabaseAdmin()
// (service-role) for every query, matching the Python original.
import { Hono } from "hono";
import { z } from "zod";
import { requireRole } from "../_shared/auth.ts";
import { rateLimit } from "../_shared/rateLimit.ts";
import { getSupabaseAdmin, HttpError } from "../_shared/database.ts";
import { AuditEventType, getClientIp, logPhiAccess } from "../_shared/audit.ts";
import type { AppEnv } from "../_shared/types.ts";

export const admin = new Hono<AppEnv>();

// Uppercase + lowercase + digit + symbol, 12-128 chars.
const PASSWORD_POLICY_RE = /^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[^A-Za-z\d]).{12,128}$/;

function validatePassword(password: string): void {
  if (!PASSWORD_POLICY_RE.test(password || "")) {
    throw new HttpError(
      400,
      "Password must be 12-128 characters and include an uppercase letter, " +
        "a lowercase letter, a number, and a symbol",
    );
  }
}

/**
 * Neutralise CSV/spreadsheet formula injection: if this admin data is ever
 * exported and opened in Excel/Sheets, a value starting with =, +, -, @ or a
 * control character can execute as a formula. Prefixing with a quote forces
 * it to be read as literal text.
 */
function maskCsvValue(value: string | null | undefined): string | null {
  if (value === null || value === undefined) return null;
  const text = String(value);
  if (text && ["=", "+", "-", "@", "\t", "\r", "\n"].includes(text[0]!)) {
    return "'" + text;
  }
  return text;
}

const ROLE_ENUM = z.enum(["asha_worker", "doctor", "admin", "supervisor"]);

const createUserSchema = z.object({
  email: z.string().email(),
  password: z.string().min(12).max(128),
  full_name: z.string().min(1).max(100),
  role: ROLE_ENUM,
  facility_id: z.string().nullish(),
  asha_id: z.string().max(50).nullish(),
});
type CreateUserInput = z.infer<typeof createUserSchema>;

const bulkCreateUsersSchema = z.object({
  users: z.array(createUserSchema).min(1).max(100),
});

const updateUserSchema = z.object({
  role: ROLE_ENUM.nullish(),
  facility_id: z.string().nullish(),
  asha_id: z.string().max(50).nullish(),
  is_active: z.boolean().nullish(),
});

const createFacilitySchema = z.object({
  name: z.string().min(1).max(200),
  type: z.string().max(50).default("PHC"),
  address: z.string().max(300).nullish(),
  district: z.string().max(100).nullish(),
  state: z.string().max(100).default("Tamil Nadu"),
  pincode: z.string().max(10).nullish(),
  phone: z.string().max(20).nullish(),
});

async function readJsonBody(c: { req: { json: () => Promise<unknown> } }): Promise<unknown> {
  try {
    return await c.req.json();
  } catch {
    throw new HttpError(400, "Invalid JSON body");
  }
}

function parseBody<T extends z.ZodTypeAny>(schema: T, raw: unknown): z.infer<T> {
  const parsed = schema.safeParse(raw);
  if (!parsed.success) {
    throw new HttpError(400, parsed.error.issues.map((i) => i.message).join("; "));
  }
  return parsed.data;
}

// ── User management ────────────────────────────────────────────────────────

interface ProfileRow {
  id: string;
  full_name: string | null;
  role: string | null;
  facility_id: string | null;
  asha_id: string | null;
  is_active: boolean | null;
  created_at: string;
  facilities: { name: string | null; district: string | null } | null;
}

admin.get("/api/admin/users", rateLimit(60, 60), requireRole("admin"), async (c) => {
  const user = c.get("user");
  const limit = Math.max(1, Math.min(Number.parseInt(c.req.query("limit") ?? "100", 10) || 100, 200));
  const page = Math.max(1, Number.parseInt(c.req.query("page") ?? "1", 10) || 1);
  const start = (page - 1) * limit;
  const end = start + limit - 1;

  const svc = getSupabaseAdmin();
  const { data: profileRows, error: profilesError } = await svc
    .from("profiles")
    .select("id, full_name, role, facility_id, asha_id, is_active, created_at, facilities(name, district)")
    .range(start, end);
  if (profilesError) throw profilesError;

  const profilesById = new Map<string, ProfileRow>();
  for (const p of (profileRows ?? []) as unknown as ProfileRow[]) profilesById.set(p.id, p);

  const { data: authPage, error: authError } = await svc.auth.admin.listUsers({ page, perPage: limit });
  if (authError) throw authError;
  const authUsers = (authPage?.users ?? []).filter((au) => profilesById.has(au.id));

  const result = authUsers.map((au) => {
    const profile = profilesById.get(au.id);
    return {
      id: au.id,
      email: maskCsvValue(au.email),
      full_name: profile?.full_name ?? "",
      role: profile?.role ?? "asha_worker",
      facility_id: profile?.facility_id ?? null,
      facility_name: profile?.facilities?.name ?? null,
      asha_id: maskCsvValue(profile?.asha_id),
      is_active: profile?.is_active ?? true,
      created_at: au.created_at,
      last_sign_in: au.last_sign_in_at ?? null,
    };
  });

  await logPhiAccess({
    eventType: AuditEventType.PHI_READ,
    userId: user.sub ?? "unknown",
    userRole: user.resolvedRole,
    resourceType: "profiles",
    resourceId: `page:${page}`,
    ipAddress: getClientIp(c),
    details: { count: result.length },
  });

  return c.json({ data: result, page, limit });
});

/**
 * Core create-user logic shared by create_user (single) and
 * bulk_create_users. Raises HttpError exactly as the single-user endpoint
 * always has — bulk creation catches it per-row so one bad row can't fail
 * the batch.
 */
async function provisionUser(body: CreateUserInput): Promise<{ id: string; email: string }> {
  validatePassword(body.password);

  if (["asha_worker", "doctor", "supervisor"].includes(body.role) && !body.facility_id) {
    throw new HttpError(400, "facility_id is required for this role");
  }

  const svc = getSupabaseAdmin();
  const { data: created, error: createError } = await svc.auth.admin.createUser({
    email: body.email,
    password: body.password,
    email_confirm: true,
    user_metadata: {
      full_name: body.full_name,
      role: body.role,
      facility_id: body.facility_id || "",
    },
  });
  if (createError || !created?.user) {
    throw new HttpError(400, createError?.message ?? "Failed to create user");
  }
  const newUserId = created.user.id;

  try {
    const { data: profileData, error: profileError } = await svc
      .from("profiles")
      .update({ facility_id: body.facility_id ?? null, asha_id: body.asha_id ?? null })
      .eq("id", newUserId)
      .select();
    if (profileError) throw profileError;
    if (!profileData || profileData.length === 0) {
      throw new Error("Profile update returned no data");
    }
  } catch (e) {
    console.error(`Failed to provision profile for new user ${newUserId}:`, e);
    try {
      await svc.auth.admin.deleteUser(newUserId);
    } catch (rollbackErr) {
      console.error(`Failed to roll back orphaned auth user ${newUserId}:`, rollbackErr);
    }
    throw new HttpError(500, "Failed to initialize user profile. The created account was rolled back.");
  }

  return { id: newUserId, email: body.email };
}

admin.post("/api/admin/users", rateLimit(10, 60), requireRole("admin"), async (c) => {
  const user = c.get("user");
  const body = parseBody(createUserSchema, await readJsonBody(c));

  const result = await provisionUser(body);

  await logPhiAccess({
    eventType: AuditEventType.PHI_CREATE,
    userId: user.sub ?? "unknown",
    userRole: user.resolvedRole,
    resourceType: "profiles",
    resourceId: result.id,
    facilityId: body.facility_id ?? null,
    ipAddress: getClientIp(c),
    details: { created_role: body.role },
  });

  return c.json(result);
});

admin.post("/api/admin/users/bulk", rateLimit(3, 60), requireRole("admin"), async (c) => {
  const user = c.get("user");
  const body = parseBody(bulkCreateUsersSchema, await readJsonBody(c));

  const results: Array<Record<string, unknown>> = [];
  for (let i = 0; i < body.users.length; i++) {
    const row = body.users[i]!;
    let created: { id: string; email: string };
    try {
      created = await provisionUser(row);
    } catch (e) {
      const detail = e instanceof HttpError ? e.message : "Unexpected error creating this user";
      if (!(e instanceof HttpError)) console.error(`Bulk user creation failed for row ${i} (${row.email}):`, e);
      results.push({ row: i, email: row.email, status: "error", detail });
      continue;
    }

    await logPhiAccess({
      eventType: AuditEventType.PHI_CREATE,
      userId: user.sub ?? "unknown",
      userRole: user.resolvedRole,
      resourceType: "profiles",
      resourceId: created.id,
      facilityId: row.facility_id ?? null,
      ipAddress: getClientIp(c),
      details: { created_role: row.role, bulk: true },
    });
    results.push({ row: i, email: row.email, status: "created", id: created.id });
  }

  const succeeded = results.filter((r) => r.status === "created").length;
  return c.json({ results, succeeded, failed: results.length - succeeded });
});

admin.patch("/api/admin/users/:user_id", rateLimit(30, 60), requireRole("admin"), async (c) => {
  const user = c.get("user");
  const userId = c.req.param("user_id")!;
  const body = parseBody(updateUserSchema, await readJsonBody(c));

  const svc = getSupabaseAdmin();
  const { data: targetProfile, error: fetchError } = await svc
    .from("profiles")
    .select("id, role, facility_id, asha_id, is_active")
    .eq("id", userId)
    .maybeSingle();
  if (fetchError) throw fetchError;
  if (!targetProfile) throw new HttpError(404, "User not found");

  const profileUpdate: Record<string, unknown> = {};
  const metaUpdate: Record<string, unknown> = {};

  if (body.role !== null && body.role !== undefined) {
    profileUpdate.role = body.role;
    metaUpdate.role = body.role;
  }
  if (body.facility_id !== null && body.facility_id !== undefined) {
    profileUpdate.facility_id = body.facility_id;
    metaUpdate.facility_id = body.facility_id;
  }
  if (body.asha_id !== null && body.asha_id !== undefined) {
    profileUpdate.asha_id = body.asha_id;
  }
  if (body.is_active !== null && body.is_active !== undefined) {
    profileUpdate.is_active = body.is_active;
  }

  if (Object.keys(profileUpdate).length > 0) {
    const { error } = await svc.from("profiles").update(profileUpdate).eq("id", userId);
    if (error) throw error;
  }

  if (Object.keys(metaUpdate).length > 0) {
    const { error: metaError } = await svc.auth.admin.updateUserById(userId, { user_metadata: metaUpdate });
    if (metaError) {
      console.error(`Auth metadata update failed for user_id=${userId}:`, metaError);
      if (Object.keys(profileUpdate).length > 0) {
        const rollbackValues: Record<string, unknown> = {};
        for (const key of Object.keys(profileUpdate)) {
          rollbackValues[key] = (targetProfile as Record<string, unknown>)[key];
        }
        await svc.from("profiles").update(rollbackValues).eq("id", userId);
      }
      throw new HttpError(500, "Failed to update user metadata. Profile update was rolled back.");
    }
  }

  await logPhiAccess({
    eventType: AuditEventType.PHI_UPDATE,
    userId: user.sub ?? "unknown",
    userRole: user.resolvedRole,
    resourceType: "profiles",
    resourceId: userId,
    facilityId: (profileUpdate.facility_id as string | undefined) ?? targetProfile.facility_id ?? null,
    ipAddress: getClientIp(c),
    details: { fields_updated: Object.keys(profileUpdate).sort() },
  });

  return c.json({ status: "updated" });
});

admin.delete("/api/admin/users/:user_id", rateLimit(30, 60), requireRole("admin"), async (c) => {
  const user = c.get("user");
  const userId = c.req.param("user_id")!;

  const { data: updated, error } = await getSupabaseAdmin()
    .from("profiles")
    .update({ is_active: false })
    .eq("id", userId)
    .select();
  if (error) throw error;
  if (!updated || updated.length === 0) throw new HttpError(404, "User not found");

  await logPhiAccess({
    eventType: AuditEventType.PHI_UPDATE,
    userId: user.sub ?? "unknown",
    userRole: user.resolvedRole,
    resourceType: "profiles",
    resourceId: userId,
    ipAddress: getClientIp(c),
    details: { is_active: false },
  });
  return c.json({ status: "deactivated" });
});

admin.post("/api/admin/users/:user_id/reactivate", rateLimit(30, 60), requireRole("admin"), async (c) => {
  const user = c.get("user");
  const userId = c.req.param("user_id")!;

  const { data: updated, error } = await getSupabaseAdmin()
    .from("profiles")
    .update({ is_active: true })
    .eq("id", userId)
    .select();
  if (error) throw error;
  if (!updated || updated.length === 0) throw new HttpError(404, "User not found");

  await logPhiAccess({
    eventType: AuditEventType.PHI_UPDATE,
    userId: user.sub ?? "unknown",
    userRole: user.resolvedRole,
    resourceType: "profiles",
    resourceId: userId,
    ipAddress: getClientIp(c),
    details: { is_active: true },
  });
  return c.json({ status: "reactivated" });
});

// ── Facilities management ──────────────────────────────────────────────────

admin.get("/api/admin/facilities", rateLimit(60, 60), requireRole("admin"), async (c) => {
  const { data, error } = await getSupabaseAdmin().from("facilities").select("*").order("name");
  if (error) throw error;
  return c.json(data ?? []);
});

admin.post("/api/admin/facilities", rateLimit(10, 60), requireRole("admin"), async (c) => {
  const user = c.get("user");
  const body = parseBody(createFacilitySchema, await readJsonBody(c));

  const { data, error } = await getSupabaseAdmin().from("facilities").insert(body).select();
  if (error) throw error;
  if (!data || data.length === 0) throw new HttpError(500, "Failed to create facility");

  await logPhiAccess({
    eventType: AuditEventType.PHI_CREATE,
    userId: user.sub ?? "unknown",
    userRole: user.resolvedRole,
    resourceType: "facilities",
    resourceId: (data[0] as { id?: string }).id ?? null,
    ipAddress: getClientIp(c),
    details: { name: body.name },
  });
  return c.json(data[0]);
});

admin.patch("/api/admin/facilities/:facility_id/toggle", rateLimit(30, 60), requireRole("admin"), async (c) => {
  const user = c.get("user");
  const facilityId = c.req.param("facility_id")!;
  const svc = getSupabaseAdmin();

  const { data: current, error: fetchError } = await svc
    .from("facilities")
    .select("is_active")
    .eq("id", facilityId)
    .maybeSingle();
  if (fetchError) throw fetchError;
  if (!current) throw new HttpError(404, "Facility not found");

  const currentState = Boolean((current as { is_active: boolean }).is_active);
  const newState = !currentState;

  // Optimistic concurrency: only flip if the state hasn't changed since we
  // read it, so two concurrent toggles can't race into an inconsistent result.
  const { data: updated, error } = await svc
    .from("facilities")
    .update({ is_active: newState })
    .eq("id", facilityId)
    .eq("is_active", currentState)
    .select();
  if (error) throw error;
  if (!updated || updated.length === 0) {
    throw new HttpError(409, "Facility was modified concurrently. Please retry.");
  }

  await logPhiAccess({
    eventType: AuditEventType.PHI_UPDATE,
    userId: user.sub ?? "unknown",
    userRole: user.resolvedRole,
    resourceType: "facilities",
    resourceId: facilityId,
    ipAddress: getClientIp(c),
    details: { is_active: newState },
  });
  return c.json({ is_active: newState });
});

// ── System stats ────────────────────────────────────────────────────────────

admin.get("/api/admin/stats", rateLimit(60, 60), requireRole("admin"), async (c) => {
  const svc = getSupabaseAdmin();
  const [casesResult, profilesResult] = await Promise.all([
    svc.from("case_records").select("triage_level").is("deleted_at", null),
    svc.from("profiles").select("role, is_active"),
  ]);
  if (casesResult.error) throw casesResult.error;
  if (profilesResult.error) throw profilesResult.error;

  const triageCounts: Record<string, number> = { EMERGENCY: 0, URGENT: 0, ROUTINE: 0 };
  for (const row of (casesResult.data ?? []) as Array<{ triage_level: string | null }>) {
    const level = row.triage_level ?? "ROUTINE";
    triageCounts[level] = (triageCounts[level] ?? 0) + 1;
  }

  const roleCounts: Record<string, number> = {};
  let activeCount = 0;
  for (const row of (profilesResult.data ?? []) as Array<{ role: string; is_active: boolean }>) {
    roleCounts[row.role] = (roleCounts[row.role] ?? 0) + 1;
    if (row.is_active) activeCount++;
  }

  return c.json({
    total_cases: (casesResult.data ?? []).length,
    triage_counts: triageCounts,
    total_users: (profilesResult.data ?? []).length,
    active_users: activeCount,
    role_counts: roleCounts,
  });
});

// ── Audit Log ────────────────────────────────────────────────────────────────

admin.get("/api/admin/audit-log", rateLimit(60, 60), requireRole("admin"), async (c) => {
  const limit = Math.max(1, Math.min(Number.parseInt(c.req.query("limit") ?? "50", 10) || 50, 200));
  const before = c.req.query("before");

  let query = getSupabaseAdmin()
    .from("phi_audit_log")
    .select(
      "id, event_type, user_id, user_role, resource_type, resource_id, facility_id, ip_address, details, created_at",
    )
    .order("created_at", { ascending: false })
    .limit(limit + 1);
  if (before) query = query.lt("created_at", before);

  const { data, error } = await query;
  if (error) throw error;

  const rows = (data ?? []) as Array<{ created_at: string; [key: string]: unknown }>;
  const hasMore = rows.length > limit;
  const page = rows.slice(0, limit);
  const last = page[page.length - 1];

  return c.json({
    entries: page,
    hasMore,
    nextCursor: hasMore && last ? last.created_at : null,
  });
});
