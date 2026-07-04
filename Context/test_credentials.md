# VitalNet Test Credentials

> [!CAUTION]
> **These are throwaway TEST credentials, committed to the repository in plaintext.**
> They must **never** exist in a production Supabase project. Anyone with repo
> access can read these passwords. Before any production deployment: (1) ensure
> the production project has none of these accounts, (2) use a separate Supabase
> project for testing, and (3) rotate immediately if these ever were used
> against a project that also holds real patient data.

Use these accounts to test role-based routing and permissions in a **dedicated
test** Supabase project only.

## ASHA Worker
- **Email**: `asha@test.vitalnet`
- **Password**: `TestASHA2026!`
- **Role**: `asha_worker`
- **View**: Intake Form

## Doctor
- **Email**: `doctor@test.vitalnet`
- **Password**: `TestDoctor2026!`
- **Role**: `doctor`
- **View**: Dashboard

## Administrator
- **Email**: `admin@test.vitalnet`
- **Password**: `TestAdmin2026!`
- **Role**: `admin`
- **View**: Dashboard (Global access)

> [!IMPORTANT]
> These accounts are for testing only. Ensure that a similar pattern is used if re-creating users in the Supabase dashboard.
