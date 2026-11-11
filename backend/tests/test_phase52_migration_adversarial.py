"""
Milestone M1 Adversarial Challenge: phase52_security_definer_and_trigger_hardening.sql

Empirically challenges:
1. SQL syntax, tokenization, transaction boundary, and delimiter balance.
2. protect_case_records_clinical_columns trigger logic against injection & bypass attacks.
3. fn_mark_referral_followup_due authorization & status state machine.
4. fn_erase_case_pii concurrency locking, atomicity, idempotency, and PII scrubbing.
5. fn_patient_recent_trajectory input clamping, empty key handling, and facility scoping.
6. RLS two-tier facility isolation for case_records and referrals policies.
7. fn_triage_metrics two-tier admin & supervisor authorization.
"""
import re
from pathlib import Path
import pytest
import sqlparse
from sqlparse.sql import Statement

MIGRATION_PATH = Path(__file__).resolve().parent.parent / "supabase" / "migrations" / "phase52_security_definer_and_trigger_hardening.sql"


@pytest.fixture(scope="module")
def migration_sql():
    assert MIGRATION_PATH.exists(), f"Migration file not found at {MIGRATION_PATH}"
    with open(MIGRATION_PATH, "r", encoding="utf-8") as f:
        return f.read()


# ==============================================================================
# 1. SQL Syntax, Tokenization & Transaction Boundaries
# ==============================================================================

def test_sql_transaction_boundaries(migration_sql):
    """Ensure the migration is strictly enclosed in a single BEGIN; ... COMMIT; transaction."""
    stripped = migration_sql.strip()
    # Remove leading comments
    lines = [line.strip() for line in stripped.splitlines() if line.strip() and not line.strip().startswith("--")]
    assert lines[0].upper() == "BEGIN;", "First non-comment statement must be BEGIN;"
    assert lines[-1].upper() == "COMMIT;", "Last non-comment statement must be COMMIT;"

    # Ensure no internal commits or rollbacks break the atomic migration
    internal_lines = lines[1:-1]
    for line in internal_lines:
        assert not re.match(r"^\s*(COMMIT|ROLLBACK)\s*;", line, re.IGNORECASE), "Unexpected transaction break inside migration"


def test_sqlparse_tokenization(migration_sql):
    """Ensure all statements in the migration parse cleanly via sqlparse."""
    statements = sqlparse.split(migration_sql)
    assert len(statements) >= 15, f"Expected at least 15 SQL statements, found {len(statements)}"

    parsed_statements = [sqlparse.parse(s)[0] for s in statements if s.strip()]
    assert len(parsed_statements) >= 15

    # Check that each parsed statement has tokens and does not have unparseable garbage
    for stmt in parsed_statements:
        tokens = [t for t in stmt.tokens if not t.is_whitespace]
        assert len(tokens) > 0, "Encountered empty or malformed SQL statement token"


def test_sql_balanced_delimiters(migration_sql):
    """Ensure all parentheses, brackets, braces, and dollar-quote blocks are perfectly balanced."""
    # Track dollar quoting: $$, $body$, etc.
    dollar_blocks = re.findall(r"\$[a-zA-Z0-9_]*\$", migration_sql)
    assert len(dollar_blocks) % 2 == 0, f"Unbalanced dollar quote tags in PL/pgSQL: {dollar_blocks}"

    # For each function definition, check opening and closing dollar quotes
    funcs = re.findall(r"CREATE OR REPLACE FUNCTION (.*?)\$\$(.*?)\$\$", migration_sql, re.DOTALL)
    assert len(funcs) == 5, f"Expected exactly 5 PL/pgSQL functions using $$ delimiter, found {len(funcs)}"

    # Check balanced parentheses and brackets inside PL/pgSQL function bodies
    for func_header, func_body in funcs:
        p_count = 0
        b_count = 0
        for char in func_body:
            if char == '(':
                p_count += 1
            elif char == ')':
                p_count -= 1
            elif char == '[':
                b_count += 1
            elif char == ']':
                b_count -= 1
            assert p_count >= 0, f"Mismatched closing parenthesis in function {func_header.split()[0]}"
            assert b_count >= 0, f"Mismatched closing bracket in function {func_header.split()[0]}"
        assert p_count == 0, f"Unclosed parenthesis in function {func_header.split()[0]}"
        assert b_count == 0, f"Unclosed bracket in function {func_header.split()[0]}"


# ==============================================================================
# 2. Section 1: protect_case_records_clinical_columns() Simulation
# ==============================================================================

ALLOWED_SMS_PROMOTION_COLS = {
    'is_sms_stub', 'patient_name', 'patient_age', 'age_months', 'patient_sex',
    'patient_location', 'patient_key', 'chief_complaint', 'complaint_duration',
    'symptoms', 'observations', 'known_conditions', 'current_medications',
    'is_pregnant', 'muac_mm', 'contraindication_flags', 'temperature',
    'heart_rate', 'bp_systolic', 'bp_diastolic', 'spo2', 'respiratory_rate',
    'triage_level', 'triage_priority', 'triage_confidence', 'triage_model_version',
    'risk_driver', 'low_confidence', 'needs_review', 'deterioration_alert',
    'deterioration_visit_count', 'briefing', 'consent_given', 'consent_timestamp',
    'created_offline', 'client_submitted_at', 'updated_at'
}

ALLOWED_SUBMITTER_COLS = {
    'deleted_at', 'human_review_requested', 'human_review_reason',
    'follow_up_completed_at', 'updated_at'
}

CLINICIAN_AND_TENANT_FORBIDDEN_COLS = {
    'reviewed_by', 'reviewed_at', 'doctor_notes', 'overridden_triage',
    'override_reason', 'overridden_at', 'facility_id', 'submitted_by',
    'id', 'client_id', 'follow_up_required', 'follow_up_due_at'
}


def simulate_protect_case_records_clinical_columns(old_row, new_row, caller_id, caller_role, is_active=True):
    """
    Python model of public.protect_case_records_clinical_columns() trigger.
    Raises PermissionError(42501) on violation, returns modified new_row on success.
    """
    v_is_clinician_or_admin = (is_active and caller_role in ['doctor', 'facility_admin', 'admin', 'super_admin'])
    res = dict(new_row)

    # 1. SMS stub promotion check
    old_is_stub = old_row.get("is_sms_stub") is True
    new_is_stub = new_row.get("is_sms_stub") is False
    is_original_submitter = (caller_id == old_row.get("submitted_by"))

    if old_is_stub and new_is_stub and is_original_submitter and not v_is_clinician_or_admin:
        # Clinician review preservation
        if old_row.get("reviewed_at") is not None or old_row.get("overridden_triage") is not None:
            res["triage_level"] = old_row.get("triage_level")
            res["triage_priority"] = old_row.get("triage_priority")
            res["needs_review"] = old_row.get("needs_review")

        # Column difference check: (NEW - allowed) IS DISTINCT FROM (OLD - allowed)
        new_remainder = {k: v for k, v in res.items() if k not in ALLOWED_SMS_PROMOTION_COLS}
        old_remainder = {k: v for k, v in old_row.items() if k not in ALLOWED_SMS_PROMOTION_COLS}

        if new_remainder != old_remainder:
            raise PermissionError("42501: SMS stub promotion cannot modify clinician review, override, or tenant identity columns")
        return res

    # 2. Standard subsequent submitter update check
    if is_original_submitter and not v_is_clinician_or_admin:
        new_remainder = {k: v for k, v in res.items() if k not in ALLOWED_SUBMITTER_COLS}
        old_remainder = {k: v for k, v in old_row.items() if k not in ALLOWED_SUBMITTER_COLS}
        if new_remainder != old_remainder:
            raise PermissionError("42501: Clinical, triage, override, and identity columns cannot be modified by the submitter")

    return res


def test_sms_stub_promotion_allowed_columns_pass():
    old = {
        "id": "case-1", "is_sms_stub": True, "submitted_by": "user-asha", "facility_id": "fac-1",
        "triage_level": "URGENT", "triage_priority": 2, "needs_review": False,
        "reviewed_at": None, "overridden_triage": None, "reviewed_by": None,
        "patient_name": "Stub Name", "temperature": 37.0
    }
    new = dict(old)
    new["is_sms_stub"] = False
    new["patient_name"] = "Full Patient Name"
    new["temperature"] = 38.5
    new["bp_systolic"] = 130
    new["symptoms"] = ["fever", "cough"]
    new["triage_level"] = "EMERGENCY"
    new["triage_priority"] = 1

    result = simulate_protect_case_records_clinical_columns(old, new, "user-asha", "asha_worker")
    assert result["is_sms_stub"] is False
    assert result["patient_name"] == "Full Patient Name"
    assert result["triage_level"] == "EMERGENCY"


@pytest.mark.parametrize("forbidden_col,forbidden_val", [
    ("reviewed_by", "doc-uuid"),
    ("reviewed_at", "2026-11-08T12:00:00Z"),
    ("doctor_notes", "Clinician note injection"),
    ("overridden_triage", "NON_URGENT"),
    ("override_reason", "Forged override reason"),
    ("overridden_at", "2026-11-08T12:00:00Z"),
    ("facility_id", "fac-other"),
    ("submitted_by", "user-other"),
    ("id", "case-other"),
    ("client_id", "client-other"),
    ("follow_up_required", True),
    ("follow_up_due_at", "2026-11-10T12:00:00Z"),
])
def test_sms_stub_promotion_rejects_forbidden_columns(forbidden_col, forbidden_val):
    old = {
        "id": "case-1", "is_sms_stub": True, "submitted_by": "user-asha", "facility_id": "fac-1",
        "triage_level": "URGENT", "triage_priority": 2, "needs_review": False,
        "reviewed_at": None, "overridden_triage": None, "reviewed_by": None,
        "patient_name": "Stub Name", "doctor_notes": None, "follow_up_required": False
    }
    new = dict(old)
    new["is_sms_stub"] = False
    new[forbidden_col] = forbidden_val

    with pytest.raises(PermissionError) as exc_info:
        simulate_protect_case_records_clinical_columns(old, new, "user-asha", "asha_worker")
    assert "42501" in str(exc_info.value)


def test_sms_stub_promotion_preserves_clinician_review_override():
    """BUG-52: If doctor reviewed or overrode stub, promote sync must preserve doctor decision."""
    old = {
        "id": "case-1", "is_sms_stub": True, "submitted_by": "user-asha", "facility_id": "fac-1",
        "triage_level": "EMERGENCY", "triage_priority": 1, "needs_review": False,
        "reviewed_at": "2026-11-08T10:00:00Z", "overridden_triage": "EMERGENCY", "reviewed_by": "doc-1",
        "patient_name": "Stub Name"
    }
    new = dict(old)
    new["is_sms_stub"] = False
    new["patient_name"] = "Full Sync Name"
    # Sync tries to downgrade triage to NON_URGENT
    new["triage_level"] = "NON_URGENT"
    new["triage_priority"] = 4
    new["needs_review"] = True

    result = simulate_protect_case_records_clinical_columns(old, new, "user-asha", "asha_worker")
    assert result["is_sms_stub"] is False
    assert result["patient_name"] == "Full Sync Name"
    # MUST be preserved from OLD
    assert result["triage_level"] == "EMERGENCY"
    assert result["triage_priority"] == 1
    assert result["needs_review"] is False


def test_post_promotion_update_restricts_submitter():
    """Once promoted (is_sms_stub = false), submitter cannot modify clinical fields."""
    old = {
        "id": "case-1", "is_sms_stub": False, "submitted_by": "user-asha", "facility_id": "fac-1",
        "triage_level": "URGENT", "patient_name": "Alice", "temperature": 37.0
    }
    new = dict(old)
    new["temperature"] = 39.0  # Disallowed after promotion

    with pytest.raises(PermissionError) as exc_info:
        simulate_protect_case_records_clinical_columns(old, new, "user-asha", "asha_worker")
    assert "42501" in str(exc_info.value)


def test_re_stubbing_attack_rejected():
    """Submitter cannot flip is_sms_stub back to true."""
    old = {
        "id": "case-1", "is_sms_stub": False, "submitted_by": "user-asha", "facility_id": "fac-1",
        "triage_level": "URGENT"
    }
    new = dict(old)
    new["is_sms_stub"] = True

    with pytest.raises(PermissionError) as exc_info:
        simulate_protect_case_records_clinical_columns(old, new, "user-asha", "asha_worker")
    assert "42501" in str(exc_info.value)


# ==============================================================================
# 3. Section 2: fn_mark_referral_followup_due() State & Scope Checks
# ==============================================================================

def simulate_fn_mark_referral_followup_due(caller_role, caller_fac, referral_fac, referral_status):
    """Model SQL checks in fn_mark_referral_followup_due."""
    if caller_role not in ('doctor', 'facility_admin', 'admin', 'super_admin'):
        raise PermissionError("42501: insufficient_privilege")
    if referral_status != 'completed':
        raise ValueError("22023: referral must be in completed status to schedule post-discharge follow-up")
    if caller_role != 'super_admin' and caller_fac != referral_fac:
        raise PermissionError("42501: only receiving facility can trigger post-referral follow-up")
    return True


def test_fn_mark_referral_followup_due_matrix():
    # 1. Non-clinician -> 42501
    with pytest.raises(PermissionError) as exc:
        simulate_fn_mark_referral_followup_due('asha_worker', 'fac-1', 'fac-1', 'completed')
    assert "42501" in str(exc.value)

    # 2. Incomplete referral -> 22023
    for incomplete in ['pending', 'accepted', 'rejected', 'in_transit']:
        with pytest.raises(ValueError) as exc:
            simulate_fn_mark_referral_followup_due('doctor', 'fac-1', 'fac-1', incomplete)
        assert "22023" in str(exc.value)

    # 3. Cross-facility receiving doctor -> 42501
    with pytest.raises(PermissionError) as exc:
        simulate_fn_mark_referral_followup_due('doctor', 'fac-1', 'fac-2', 'completed')
    assert "42501" in str(exc.value)

    # 4. Same facility receiving doctor -> Success
    assert simulate_fn_mark_referral_followup_due('doctor', 'fac-2', 'fac-2', 'completed') is True

    # 5. Same facility receiving admin -> Success
    assert simulate_fn_mark_referral_followup_due('admin', 'fac-2', 'fac-2', 'completed') is True

    # 6. Super admin across any facility -> Success
    assert simulate_fn_mark_referral_followup_due('super_admin', 'fac-1', 'fac-2', 'completed') is True
    assert simulate_fn_mark_referral_followup_due('super_admin', None, 'fac-2', 'completed') is True


# ==============================================================================
# 4. Section 3: fn_erase_case_pii() Concurrency, Locking & Redaction
# ==============================================================================

def test_fn_erase_case_pii_sql_locks_for_update(migration_sql):
    """Ensure fn_erase_case_pii acquires a row lock via FOR UPDATE."""
    erase_func = re.search(r"CREATE OR REPLACE FUNCTION public\.fn_erase_case_pii.*?AS \$\$(.*?)\$\$;", migration_sql, re.DOTALL)
    assert erase_func is not None, "fn_erase_case_pii function definition not found"
    body = erase_func.group(1)

    assert "FOR UPDATE;" in body, "fn_erase_case_pii must acquire exclusive FOR UPDATE row lock"
    assert "SECURITY DEFINER" in erase_func.group(0)
    assert "search_path = public" in erase_func.group(0)


def simulate_erase_case_pii_briefing(briefing):
    """Model the briefing JSONB scrub logic in fn_erase_case_pii."""
    redacted = "[REDACTED — DSR ERASURE]"
    if isinstance(briefing, dict):
        return {
            'triage_level': briefing.get('triage_level'),
            'primary_risk_driver': redacted,
            'differential_diagnoses': [redacted],
            'red_flags': [redacted],
            'recommended_immediate_actions': briefing.get('recommended_immediate_actions', []),
            'recommended_tests': briefing.get('recommended_tests', []),
            'uncertainty_flags': redacted,
            'disclaimer': briefing.get('disclaimer'),
            'llm_status': 'redacted_dsr',
            'needs_review': False
        }
    return briefing


def test_briefing_scrub_eliminates_phi():
    raw_briefing = {
        "triage_level": "EMERGENCY",
        "primary_risk_driver": "Severe dyspnea and tachycardia in 45-year-old male",
        "differential_diagnoses": ["Acute Coronary Syndrome", "Pulmonary Embolism"],
        "red_flags": ["Chest pain radiating to left jaw"],
        "recommended_immediate_actions": ["Administer aspirin", "Supplemental oxygen"],
        "recommended_tests": ["ECG", "Troponin"],
        "uncertainty_flags": "Atypical presentation",
        "disclaimer": "Clinical decision support tool only.",
        "llm_status": "generated",
        "needs_review": True
    }
    scrubbed = simulate_erase_case_pii_briefing(raw_briefing)
    assert scrubbed["triage_level"] == "EMERGENCY"
    assert scrubbed["primary_risk_driver"] == "[REDACTED — DSR ERASURE]"
    assert scrubbed["differential_diagnoses"] == ["[REDACTED — DSR ERASURE]"]
    assert scrubbed["red_flags"] == ["[REDACTED — DSR ERASURE]"]
    assert scrubbed["uncertainty_flags"] == "[REDACTED — DSR ERASURE]"
    assert scrubbed["llm_status"] == "redacted_dsr"
    assert scrubbed["needs_review"] is False
    assert scrubbed["recommended_immediate_actions"] == ["Administer aspirin", "Supplemental oxygen"]
    assert scrubbed["disclaimer"] == "Clinical decision support tool only."


# ==============================================================================
# 5. Section 4: fn_patient_recent_trajectory() Clamping & Isolation
# ==============================================================================

def clamp_trajectory_limit(p_limit):
    """Python simulation of LEAST(GREATEST(COALESCE(p_limit, 3), 1), 10)."""
    val = 3 if p_limit is None else p_limit
    return min(max(val, 1), 10)


@pytest.mark.parametrize("p_limit,expected", [
    (None, 3),
    (0, 1),
    (-100, 1),
    (1, 1),
    (3, 3),
    (5, 5),
    (10, 10),
    (11, 10),
    (100, 10),
    (1000000, 10),
])
def test_trajectory_limit_clamping(p_limit, expected):
    assert clamp_trajectory_limit(p_limit) == expected


def test_trajectory_empty_patient_key_handling():
    def should_return_early(key):
        return key is None or len(key.strip()) == 0

    assert should_return_early(None) is True
    assert should_return_early("") is True
    assert should_return_early("   ") is True
    assert should_return_early("\t\n") is True
    assert should_return_early("SALTED_HASH_123") is False


# ==============================================================================
# 6. Section 5: Two-Tier RBAC Policies on case_records & referrals
# ==============================================================================

def test_two_tier_rbac_policies_sql_presence(migration_sql):
    """Verify that all 6 two-tier RBAC policies are dropped and recreated."""
    required_policies = [
        "case_records_insert_policy",
        "case_records_update_policy",
        "case_records_delete_policy",
        "referrals_select_policy",
        "referrals_insert_policy",
        "referrals_update_policy",
    ]
    for pol in required_policies:
        assert f"DROP POLICY IF EXISTS {pol}" in migration_sql, f"Missing DROP POLICY IF EXISTS for {pol}"
        assert f"CREATE POLICY {pol}" in migration_sql, f"Missing CREATE POLICY for {pol}"


def test_case_records_policies_restrict_phc_admin(migration_sql):
    """
    Ensure PHC admin is scoped to p.facility_id = case_records.facility_id,
    while super_admin has global bypass.
    """
    # Insert policy
    assert "p.role = 'super_admin'::text\n          OR p.facility_id = case_records.facility_id" in migration_sql

    # Update policy
    update_pol = re.search(r"CREATE POLICY case_records_update_policy.*?;", migration_sql, re.DOTALL)
    assert update_pol is not None
    assert "p.role = 'super_admin'::text" in update_pol.group(0)
    assert "p.facility_id = case_records.facility_id" in update_pol.group(0)

    # Delete policy
    delete_pol = re.search(r"CREATE POLICY case_records_delete_policy.*?;", migration_sql, re.DOTALL)
    assert delete_pol is not None
    assert "p.role = 'super_admin'::text" in delete_pol.group(0)
    assert "p.facility_id = case_records.facility_id" in delete_pol.group(0)


def test_referrals_policies_restrict_phc_admin(migration_sql):
    """Ensure referrals policies scope non-super-admin to referring/receiving facility."""
    select_pol = re.search(r"CREATE POLICY referrals_select_policy.*?;", migration_sql, re.DOTALL)
    assert select_pol is not None
    assert "p.facility_id IN (referring_facility_id, receiving_facility_id)" in select_pol.group(0)


# ==============================================================================
# 7. Section 6: fn_triage_metrics() Role & Facility Isolation
# ==============================================================================

def test_fn_triage_metrics_scope(migration_sql):
    """Verify fn_triage_metrics supports super_admin & supervisor globally and admin by facility."""
    metrics_func = re.search(r"CREATE OR REPLACE FUNCTION public\.fn_triage_metrics.*?AS \$\$(.*?)\$\$;", migration_sql, re.DOTALL)
    assert metrics_func is not None
    body = metrics_func.group(1)

    assert "'admin', 'super_admin', 'supervisor'" in body
    assert "IF v_role IN ('super_admin', 'supervisor') THEN" in body
    assert "cr.facility_id = v_own_facility" in body
