# VitalNet Test Credentials

> [!WARNING]
> **SECURITY**: Never commit real or plaintext passwords to this repository —
> not even for throwaway test accounts, since anyone with repo access (now or
> in the git history, forever) can read them. Set actual passwords via the
> Supabase Admin Panel (Authentication > Users) or a secure secret manager
> (1Password, Supabase Vault), and reference them here only by account pattern.

Use these account patterns to test role-based routing and permissions in a
**dedicated test** Supabase project only — never in a project that also holds
real patient data.

## ASHA Worker
- **Email**: `asha@test.vitalnet`
- **Password**: `[SET_VIA_SUPABASE_ADMIN]`
- **Role**: `asha_worker`
- **View**: Intake Form

## Doctor
- **Email**: `doctor@test.vitalnet`
- **Password**: `[SET_VIA_SUPABASE_ADMIN]`
- **Role**: `doctor`
- **View**: Dashboard

## Supervisor
- **Email**: `supervisor@test.vitalnet`
- **Password**: `[SET_VIA_SUPABASE_ADMIN]`
- **Role**: `supervisor`
- **View**: Team Metrics / Outbreak Signals / Protocol Assistant (facility-scoped, aggregate-only — `docs/DECISIONS.md` §25)

## Administrator
- **Email**: `admin@test.vitalnet`
- **Password**: `[SET_VIA_SUPABASE_ADMIN]`
- **Role**: `admin`
- **View**: Dashboard (Global access)

> [!IMPORTANT]
> Passwords must meet the backend's policy (`CreateUserRequest` in
> `backend/app/api/routes/admin_routes.py`): 12–128 characters. Set them
> directly in the Supabase Admin Panel, never in plaintext documentation or
> commit history.

> [!NOTE]
> `asha_worker`, `doctor`, and `supervisor` should all be assigned the
> **same** `facility_id` for local testing — Team Metrics and Outbreak
> Signals have nothing to show a supervisor/doctor at a facility with no
> ASHA-worker submissions. `admin` is global and needs no `facility_id`.
