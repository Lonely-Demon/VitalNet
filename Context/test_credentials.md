# VitalNet Test Credentials

> [!WARNING]
> **SECURITY**: Never commit real passwords. Use environment-specific credential management (e.g., 1Password, Supabase vault, or secure `.env.local` files excluded from version control).

Use these account patterns to test role-based routing and permissions. **Actual passwords must be set via Supabase Admin Panel** and never hardcoded in documentation.

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

## Administrator
- **Email**: `admin@test.vitalnet`
- **Password**: `[SET_VIA_SUPABASE_ADMIN]`
- **Role**: `admin`
- **View**: Dashboard (Global access)

> [!IMPORTANT]
> Passwords must meet security policy: 12-128 characters, containing uppercase, lowercase, number, and symbol. Set them directly in the Supabase Admin Panel > Authentication > Users, never in plaintext documentation.
