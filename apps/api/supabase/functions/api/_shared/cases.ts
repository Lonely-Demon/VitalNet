// Shared helpers ported from app/api/routes/cases.py's module-level
// functions — used by routes/cases.ts, routes/security.ts and (indirectly,
// via the same authorization shape) routes/dsr.ts.
import type { SupabaseClient } from "@supabase/supabase-js";
// @deno-types="../../../../../../packages/clinical-core/dist/index.d.ts"
import type { FiredRule } from "@vitalnet/clinical-core";
import { HttpError } from "./database.ts";
import type { AuthedUser } from "./types.ts";

/**
 * Defense-in-depth on top of Zod's control-char stripping (schema.ts):
 * strips embedded HTML/markup tags before the text reaches the DB, the LLM
 * prompt, or a doctor's browser.
 */
export function sanitizeMedicalText(value: string | null | undefined, maxLength = 500): string | null {
  if (value === null || value === undefined) return null;
  const withoutTags = value.replace(/<[^>]+>/g, "");
  const collapsed = withoutTags.replace(/\s+/g, " ").trim();
  return collapsed ? collapsed.slice(0, maxLength) : null;
}

// Deliberately a plain hyphenated-UUID format check rather than a fully
// permissive UUID parse (Python's UUID() constructor also accepts
// no-hyphen/braced forms) — every id this API ever receives back
// originates from Postgres's own canonical hyphenated representation, so a
// stricter check here costs nothing in practice.
const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export function parseUuid(value: string, field = "id"): string {
  if (!UUID_RE.test(value)) {
    throw new HttpError(400, `Invalid ${field}`);
  }
  return value.toLowerCase();
}

const HAS_TZ_RE = /(?:[zZ]|[+-]\d{2}:?\d{2})$/;

/** Parses an ISO timestamp, assuming UTC when no offset/zone is present
 * (matches Python's `datetime.fromisoformat` + `.replace(tzinfo=utc)`
 * fallback — JS's own `Date` parser would otherwise interpret a
 * bare-of-timezone string in the *server process's local* time zone). */
export function normalizedIsoTs(value: string, field: string): string {
  const trimmed = value.trim();
  const withTz = HAS_TZ_RE.test(trimmed) ? trimmed : `${trimmed}Z`;
  const date = new Date(withTz);
  if (Number.isNaN(date.getTime())) {
    throw new HttpError(400, `Invalid ${field}`);
  }
  return date.toISOString();
}

export interface CaseRowAuth {
  facility_id: string | null;
  submitted_by: string | null;
}

/**
 * Fine-grained, row-level authorization for a single case, on top of the
 * endpoint's requireRole() gate: 'admin' is global; 'doctor' is scoped to
 * their own facility_id; 'asha_worker' is scoped to cases they submitted.
 */
export function authorizeCaseRowAccess(user: AuthedUser, row: CaseRowAuth): void {
  const role = user.resolvedRole;
  const userId = typeof user.sub === "string" ? user.sub : undefined;
  const facilityId = user.resolvedFacilityId;

  if (role === "admin") return;
  if (role === "doctor" && facilityId && facilityId === row.facility_id) return;
  if (role === "asha_worker" && row.submitted_by === userId) return;
  throw new HttpError(403, "Not authorized for this case");
}

export interface AuthorizedCaseRow extends CaseRowAuth {
  id: string;
  deleted_at: string | null;
}

/**
 * Fetch a non-deleted case row by id (404 if missing/deleted), then apply
 * authorizeCaseRowAccess (403 if not authorized). Shared by every endpoint
 * that acts on a single existing case (review, triage-override, outcome,
 * soft-delete).
 */
export async function fetchAuthorizedCase(
  db: SupabaseClient,
  caseUuid: string,
  user: AuthedUser,
): Promise<AuthorizedCaseRow> {
  const { data, error } = await db
    .from("case_records")
    .select("id, facility_id, submitted_by, deleted_at")
    .eq("id", caseUuid)
    .maybeSingle();
  if (error) throw error;
  if (!data || data.deleted_at !== null) {
    throw new HttpError(404, "Case not found");
  }
  authorizeCaseRowAccess(user, data as AuthorizedCaseRow);
  return data as AuthorizedCaseRow;
}

/**
 * Renders the rules engine's fired-rule audit trail as the human-readable
 * risk_driver string — replaces classifier.py's SHAP-prose generation
 * (_generate_shap_explanation) now that the rules engine, not the model, is
 * authoritative. Strictly more auditable: every clause here is a citable
 * rule id, not a black-box feature attribution.
 */
export function formatRiskDriver(tier: string, firedRules: readonly FiredRule[]): string {
  if (firedRules.length === 0) {
    return `No escalation rule fired — routine presentation. Classified as ${tier}.`;
  }
  const parts = firedRules.map((r) => `${r.detail} (${r.citation})`);
  return `${parts.join("; ")}. Classified as ${tier}.`;
}

export interface NeedsReviewInput {
  llmNeedsReview: boolean;
  humanReviewRequested: boolean;
  hasContraindicationFlags: boolean;
  deteriorationAlert: boolean;
  /** result.modelAgreed from clinical-core's triage() — undefined when no
   * advisory model ran (no tree bundle supplied). */
  modelAgreed: boolean | undefined;
}

/**
 * Whether a newly-submitted case needs a human (doctor) review. Folds in
 * the advisory model's disagreement with the rules-authoritative tier
 * (modelAgreed === false) — this is the safety signal the advisory-ML
 * design (triage.ts's TriageResult.modelAgreed doc comment; Round 6
 * rebuild plan Phase 4: "disagreement folds into needs_review") exists to
 * guarantee: an EMERGENCY(model)->lower(rules) de-escalation must not sink
 * out of the priority queue unflagged just because the rules engine (which
 * is deterministic, so never "low confidence") was certain of its own
 * lower tier.
 */
export function computeNeedsReview(input: NeedsReviewInput): boolean {
  return Boolean(
    input.llmNeedsReview ||
      input.humanReviewRequested ||
      input.hasContraindicationFlags ||
      input.deteriorationAlert ||
      input.modelAgreed === false,
  );
}
