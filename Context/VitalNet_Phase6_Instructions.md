# VitalNet — Phase 6 Build Instructions
**Authentication · Database Migration · Offline Token Strategy**

| | |
|---|---|
| **Prepared for** | Google Antigravity |
| **Phase** | 6 of 10 |
| **Depends on** | Phases 1–5 complete and deployed |
| **Files changed** | `backend/` (auth, db, routes) · `frontend/` (auth, store, routes) · SQL (Supabase dashboard) |
| **Risk level** | HIGH — auth touches every endpoint and every frontend route |
| **Date** | March 2026 |

---

## 1. What Has Been Built (Phases 1–5 Review)

This section exists so Antigravity has full context before making any Phase 6 change. Read it before touching a single file.

### 1.1 The Pipeline (Phases 1–2)

VitalNet is a clinical triage platform for ASHA field health workers and PHC doctors in India. The core intelligence pipeline processes a patient submission end-to-end:

| # | Component | What it does |
|---|---|---|
| 1 | ASHA Intake Form | React form (React 19 + Vite + Tailwind v4). ASHA worker enters vitals, symptoms, chief complaint. |
| 2 | FastAPI backend | Python 3.13, Render deployment. Receives `POST /api/submit`. |
| 3 | HistGBC Classifier | `HistGradientBoostingClassifier` (.pkl). 14-feature vector. Returns ROUTINE / URGENT / EMERGENCY + SHAP risk driver. |
| 4 | Groq LLM | `llama-3.3-70b-versatile` (primary), `llama-3.1-8b-instant` (fallback). Generates structured JSON briefing via `response_format={type:json_object}`. |
| 5 | SQLite database | SQLAlchemy 2.x, Mapped classes. Stores case record. **CURRENTLY BEING REPLACED** by Supabase Postgres in Phase 6. |
| 6 | Doctor Dashboard | Auto-polling React UI. Priority queue EMERGENCY > URGENT > ROUTINE. Expandable briefing cards. Mark Reviewed. |

### 1.2 Classifier (Phase 0 + Iterations)

The classifier has been through multiple iterations. The final `.pkl` in `backend/models/` is the ONLY version that matters:

- Model type: `HistGradientBoostingClassifier` (NOT `GradientBoostingClassifier` — GBC does not support multi-class SHAP TreeExplainer)
- Class weights: EMERGENCY=10.0, URGENT=2.0, ROUTINE=1.0
- SHAP: `TreeExplainer` bundled inside `.pkl`. Returns shape `(1, 14, 3)` — index as `shap_vals[0, :, class_idx]`
- Missing vitals: passed as `-1` sentinel. Do NOT substitute neutral defaults.
- All 6 `.pkl` keys: `classifier`, `explainer`, `feature_names`, `label_map`, `accuracy`, `emergency_fn`

### 1.3 LLM Layer (Phase 2 + Update)

- Primary model: `llama-3.3-70b-versatile` (1K req/day free tier)
- Fallback model: `llama-3.1-8b-instant` (14.4K req/day). Auto-rotates on `RateLimitError`.
- `response_format={type: json_object}` enforced on both models.
- Classifier triage level is hardcoded into LLM output — LLM cannot override it.
- `FIXED_DISCLAIMER` is non-removable, hardcoded.

### 1.4 Frontend (Phases 3–5)

- Stack: React 19, Vite 5, Tailwind CSS v4 (`@tailwindcss/vite`, single `@import` in CSS, no config file)
- Deployed: Vercel. Environment variable: `VITE_API_BASE_URL`
- Phase 5 polish applied: Inter font, pill symptom checkboxes, loading spinner, toast notifications, empty state, shadow elevation (no glassmorphism), WCAG AA contrast on triage badges
- No `react-router-dom`. State-based routing via `useState`. Appropriate for single-page scope.

### 1.5 Current Auth State

> **CRITICAL CONTEXT:** There is currently NO auth on any endpoint. `POST /api/submit`, `GET /api/cases`, `PATCH /api/cases/{id}/review` are all completely open. Any caller who knows the URL can read or write data. Phase 6 closes this. Every file Antigravity touches in Phase 6 exists to fix this.

### 1.6 Environment Variables (Current)

| Variable | Location | Description |
|---|---|---|
| `GROQ_API_KEY` | Render | Groq free tier API key |
| `VITE_API_BASE_URL` | Vercel | `https://<render-app>.onrender.com` |

---

## 2. Why Phase 6 — The Case for Auth + Supabase

### 2.1 The Problems Phase 6 Solves

**Problem 1 — No identity:** Every form submission is anonymous. There is no way to know which ASHA worker submitted a case, which PHC it belongs to, or whether the submitter is authorised. The doctor dashboard shows cases from anyone who can POST to the endpoint.

**Problem 2 — No access control:** An ASHA worker could read another ASHA worker's cases. A random internet user could read the entire case database. There is no separation between the ASHA view and the doctor view. The admin panel cannot be built without roles.

**Problem 3 — No foundation for panels:** Phase 7 (panel separation), Phase 8 (PWA offline), and Phase 9 (ONNX) all depend on knowing who the user is and what role they have. None of those phases can be built correctly without Phase 6 being complete.

### 2.2 Why Supabase (Decision Already Made — Context for Antigravity)

The database choice has already been decided. Antigravity does not need to revisit it:

- Supabase provides Auth + Postgres + Row Level Security as one integrated platform. MongoDB Atlas provides only a database — auth would require a separate vendor.
- Row Level Security (RLS) lets the database itself enforce access rules. ASHA workers cannot read other workers' cases even if the FastAPI code has a bug. The database is the last line of defence.
- Supabase Auth issues JWTs that FastAPI can verify locally — no network call required. This is what makes offline token caching (Phase 8) architecturally possible.
- The current SQLite data is test data generated by Antigravity. There is nothing to migrate. We start clean.

### 2.3 The Offline Auth Strategy (Critical — Read Before Writing Any Auth Code)

ASHA workers operate in rural areas with intermittent connectivity. The auth architecture must support this. The strategy chosen is:

**Offline Auth Contract:**

1. ASHA worker authenticates ONCE with connectivity (at PHC, at home, on any WiFi).
2. Supabase issues a JWT (access token, 1-hour expiry) + refresh token (30-day expiry).
3. Both tokens are stored in IndexedDB (not localStorage — more storage, survives memory pressure).
4. ASHA goes into field. No connectivity. App reads cached tokens from IndexedDB.
5. Form submissions are queued in IndexedDB with the cached access token attached.
6. FastAPI validates the JWT signature LOCALLY — no Supabase call, no connectivity required.
7. When connectivity returns: Background Sync fires, queued submissions POST to backend.
8. Access token refresh happens silently in background. ASHA worker sees nothing.

**Requires connectivity:** First login, access token refresh (every hour, silent background), submission sync.

**Works offline:** Loading the app (PWA cache), filling the intake form, ONNX triage classification (Phase 9), viewing previously synced cases.

### 2.4 Database Schema (New — Supabase Postgres)

Phase 6 creates the following tables in Supabase. These replace the SQLite schema entirely. The SQL is provided in the step-by-step instructions below and must be run in the Supabase SQL Editor BEFORE any backend code changes.

| Table | Purpose |
|---|---|
| `profiles` | Extends `auth.users`. Stores role, ASHA ID, facility linkage, phone. Created via trigger on every new user signup. |
| `facilities` | PHC / CHC / hospital registry. Seeded manually. |
| `case_records` | Core clinical table. All patient data, vitals, classifier output, LLM briefing, review status, offline sync metadata, soft delete. |

---

## 3. Step-by-Step Instructions

> **Before you begin:** Complete all steps in order. Steps 1–3 are in the Supabase dashboard (SQL + settings). Steps 4–6 are backend Python changes. Steps 7–9 are frontend React changes. Step 10 is environment variables and deployment. Do not start Step 4 until Steps 1–3 are verified complete.

---

### STEP 1 — Create Supabase Schema (SQL Editor)

Open your Supabase project dashboard. Navigate to SQL Editor. Create a new query. Paste and run the following SQL EXACTLY as written. Do not modify column names, types, or constraints — the backend code references these exact names.

#### 1a — Enable PostGIS extension

```sql
create extension if not exists postgis schema extensions;
```

#### 1b — Create facilities table

```sql
create table public.facilities (
    id          uuid primary key default gen_random_uuid(),
    name        text not null,
    type        text not null default 'PHC',
    address     text,
    district    text,
    state       text default 'Tamil Nadu',
    pincode     text,
    phone       text,
    is_active   boolean default true,
    created_at  timestamptz default now()
);

alter table public.facilities enable row level security;

create policy "facilities_public_read" on public.facilities
    for select using (true);
```

Insert a seed facility for development testing:

```sql
insert into public.facilities (name, type, address, district)
values ('PHC Tambaram', 'PHC', 'Tambaram, Chennai', 'Chengalpattu');
```

#### 1c — Create profiles table with trigger

```sql
create table public.profiles (
    id          uuid primary key references auth.users(id) on delete cascade,
    full_name   text not null default '',
    role        text not null default 'asha_worker'
                check (role in ('asha_worker', 'doctor', 'admin')),
    facility_id uuid references public.facilities(id),
    asha_id     text unique,
    phone       text,
    is_active   boolean default true,
    created_at  timestamptz default now(),
    updated_at  timestamptz default now()
);

alter table public.profiles enable row level security;

-- Trigger: auto-create profile on every new signup
create or replace function public.handle_new_user()
returns trigger language plpgsql security definer set search_path = ''
as $$
begin
  insert into public.profiles (id, full_name, role)
  values (
    new.id,
    coalesce(new.raw_user_meta_data ->> 'full_name', ''),
    coalesce(new.raw_user_meta_data ->> 'role', 'asha_worker')
  );
  return new;
end;
$$;

create trigger on_auth_user_created
  after insert on auth.users
  for each row execute procedure public.handle_new_user();
```

#### 1d — Create case_records table

```sql
create table public.case_records (
    -- Identity
    id                   uuid primary key default gen_random_uuid(),
    client_id            uuid unique not null,
    -- Links
    submitted_by         uuid references public.profiles(id),
    facility_id          uuid references public.facilities(id),
    -- Patient demographics
    patient_age          integer,
    patient_sex          text check (patient_sex in ('male','female','other')),
    patient_location     text,
    -- Vitals (null = not measured)
    bp_systolic          integer,
    bp_diastolic         integer,
    spo2                 integer,
    heart_rate           integer,
    temperature          numeric(4,1),
    -- Complaint
    chief_complaint      text not null,
    complaint_duration   text,
    symptoms             text[],
    observations         text,
    known_conditions     text,
    current_medications  text,
    -- Classifier output
    triage_level         text not null
                         check (triage_level in ('ROUTINE','URGENT','EMERGENCY')),
    triage_confidence    numeric(5,4),
    risk_driver          text,
    -- LLM briefing
    briefing             jsonb,
    llm_model_used       text,
    -- Doctor review
    reviewed_by          uuid references public.profiles(id),
    reviewed_at          timestamptz,
    doctor_notes         text,
    -- Offline sync metadata
    created_offline      boolean default false,
    client_submitted_at  timestamptz,
    synced_at            timestamptz,
    -- Soft delete (NEVER hard delete from application layer)
    deleted_at           timestamptz,
    deleted_by           uuid references public.profiles(id),
    -- Server timestamps
    created_at           timestamptz default now(),
    updated_at           timestamptz default now()
);

-- Indexes
create index case_records_submitted_by_idx on public.case_records(submitted_by);
create index case_records_facility_idx     on public.case_records(facility_id);
create index case_records_triage_idx       on public.case_records(triage_level);
create index case_records_created_at_idx   on public.case_records(created_at desc);
create index case_records_active_idx       on public.case_records(deleted_at)
    where deleted_at is null;
```

#### 1e — Row Level Security policies

```sql
alter table public.case_records enable row level security;

-- ASHA workers see only their own cases (and only non-deleted)
create policy "asha_select_own" on public.case_records for select
using (
  deleted_at is null and (
    submitted_by = auth.uid()
    or (auth.jwt()->'user_metadata'->>'role') in ('doctor','admin')
  )
);

-- Only authenticated users can insert, and only as themselves
create policy "authenticated_insert" on public.case_records for insert
with check (submitted_by = auth.uid());

-- Only doctors and admins can update review fields
create policy "doctor_update" on public.case_records for update
using ((auth.jwt()->'user_metadata'->>'role') in ('doctor','admin'));

-- Profiles: users can read their own profile, admins read all
create policy "profile_select" on public.profiles for select
using (
  id = auth.uid()
  or (auth.jwt()->'user_metadata'->>'role') = 'admin'
);
```

#### 1f — Auth hook: embed role in JWT

This function puts the user's role into the JWT so FastAPI can read it without a database call. Run this SQL, then enable the hook in the Supabase dashboard under **Authentication > Hooks > Custom Access Token**.

```sql
create or replace function public.custom_access_token_hook(event jsonb)
returns jsonb language plpgsql stable as $$
declare
  claims jsonb;
  user_role text;
  user_facility_id text;
begin
  select role::text, facility_id::text
  into user_role, user_facility_id
  from public.profiles where id = (event->>'user_id')::uuid;

  claims := event->'claims';
  claims := jsonb_set(claims, '{user_metadata,role}',
            to_jsonb(coalesce(user_role, 'asha_worker')));
  claims := jsonb_set(claims, '{user_metadata,facility_id}',
            to_jsonb(coalesce(user_facility_id, '')));
  return jsonb_set(event, '{claims}', claims);
end;
$$;

grant usage on schema public to supabase_auth_admin;
grant execute on function public.custom_access_token_hook to supabase_auth_admin;
revoke execute on function public.custom_access_token_hook from authenticated, anon, public;
```

> **After running this SQL:** Go to Supabase Dashboard > Authentication > Hooks. Enable "Custom Access Token Hook". Select the function `public.custom_access_token_hook`. Save. This is what causes the JWT to carry the role claim that FastAPI reads.

---

### STEP 2 — Create Test Users in Supabase Dashboard

Go to Supabase Dashboard > Authentication > Users > Add User. Create three test users:

| Role | Email | Password | Metadata |
|---|---|---|---|
| ASHA worker | `asha@test.vitalnet` | `TestASHA2026!` | `{role: asha_worker}` |
| Doctor | `doctor@test.vitalnet` | `TestDoctor2026!` | `{role: doctor}` |
| Admin | `admin@test.vitalnet` | `TestAdmin2026!` | `{role: admin}` |

After creating each user, verify the trigger ran correctly:

```sql
select p.full_name, p.role, p.created_at
from public.profiles p
join auth.users u on u.id = p.id
order by p.created_at desc limit 5;
```

This should return 3 rows with the correct roles. If the profiles table is empty, the trigger did not fire — check Step 1c.

---

### STEP 3 — Supabase Dashboard Configuration

#### JWT Expiry Settings

Navigate to **Authentication > Configuration > Sessions**. Set:

- JWT Expiry: `3600` (1 hour). FastAPI validates this.
- Refresh Token Rotation: Enabled
- Refresh Token Reuse Interval: 10 seconds

#### Get Your Credentials

Navigate to **Settings > API**. Copy and store:

| Credential | Notes |
|---|---|
| Project URL | `https://<ref>.supabase.co` → goes into `SUPABASE_URL` env var |
| Anon/public key | Starts with `eyJ...` → goes into `SUPABASE_ANON_KEY` (frontend and backend) |
| JWT Secret | **Settings > API > JWT Settings > JWT Secret** → goes into `SUPABASE_JWT_SECRET` (backend ONLY, never frontend) |

> **Security rule:** `SUPABASE_JWT_SECRET` goes in backend environment variables ONLY. It must never appear in frontend code or be committed to git. The frontend uses only the anon key.

---

### STEP 4 — Backend: Dependencies and Configuration

#### 4a — Update requirements.txt

Add the following to `backend/requirements.txt`:

```
python-jose[cryptography]==3.3.0   # JWT local validation
supabase==2.10.0                   # Supabase Python client (for admin ops)
psycopg2-binary==2.9.9             # Postgres driver
```

#### 4b — Update .env.local (local development only)

Add to `backend/.env.local` (this file must be in `.gitignore`):

```
SUPABASE_URL=https://<ref>.supabase.co
SUPABASE_ANON_KEY=eyJ...
SUPABASE_JWT_SECRET=<your-jwt-secret>
```

Also create `backend/.env.example` with placeholder values (this file IS committed to git):

```
SUPABASE_URL=https://your-ref.supabase.co
SUPABASE_ANON_KEY=your_anon_key_here
SUPABASE_JWT_SECRET=your_jwt_secret_here
GROQ_API_KEY=your_groq_api_key_here
```

#### 4c — Update backend/config.py

Create or update `backend/config.py`:

```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    supabase_url: str
    supabase_anon_key: str
    supabase_jwt_secret: str
    groq_api_key: str

    class Config:
        env_file = '.env.local'
        env_file_encoding = 'utf-8'

settings = Settings()
```

---

### STEP 5 — Backend: Auth Dependency (auth.py)

Create `backend/auth.py`. This is the single most important file in Phase 6. Every protected endpoint depends on it.

The verification uses `python-jose` to decode the JWT using the JWT secret. This is FULLY LOCAL — zero network calls. FastAPI validates the signature, expiry, issuer, and audience purely from the token and the secret.

```python
from jose import jwt, JWTError
from fastapi import Header, HTTPException, status, Depends
from config import settings

ALGORITHM  = 'HS256'
AUDIENCE   = 'authenticated'


async def get_current_user(authorization: str = Header(None)) -> dict:
    """
    Extracts and locally validates the Supabase JWT from the
    Authorization: Bearer <token> header.
    Returns the decoded payload (user_id, role, facility_id, expiry).
    Raises HTTP 401 on any failure.
    No network call to Supabase is made. Offline-compatible.
    """
    if not authorization or not authorization.startswith('Bearer '):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail='Missing or malformed Authorization header',
            headers={'WWW-Authenticate': 'Bearer'},
        )

    token = authorization.split(' ', 1)[1]

    try:
        payload = jwt.decode(
            token,
            settings.supabase_jwt_secret,
            algorithms=[ALGORITHM],
            audience=AUDIENCE,
        )
        return payload

    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f'Invalid or expired token: {str(e)}',
            headers={'WWW-Authenticate': 'Bearer'},
        )


def require_role(*roles: str):
    """
    Returns a dependency that enforces the caller has one of the given roles.
    Usage: Depends(require_role('doctor', 'admin'))
    """
    async def role_guard(user: dict = Depends(get_current_user)) -> dict:
        user_role = (
            user.get('user_metadata', {}).get('role', '')
        )
        if user_role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f'Role {user_role!r} is not permitted for this endpoint.',
            )
        return user
    return role_guard
```

> How to read user identity from the token in any endpoint: `user['sub']` is the Supabase user UUID. `user['user_metadata']['role']` is the role. `user['user_metadata']['facility_id']` is their PHC UUID. These come from the JWT claims — no database call needed.

---

### STEP 6 — Backend: Replace SQLite with Supabase Postgres

The current backend uses SQLAlchemy + SQLite. Replace the entire database layer with direct Supabase client calls. The Supabase Python client wraps the PostgREST API and handles connection pooling automatically.

#### 6a — Replace database.py

Delete the existing SQLAlchemy `database.py`. Replace with:

```python
from supabase import create_client, Client
from config import settings

supabase: Client = create_client(
    settings.supabase_url,
    settings.supabase_anon_key,
)
```

#### 6b — Update main.py

Remove the SQLite table creation from the lifespan handler. The database already exists — Supabase manages it. Keep the classifier loading. Update CORS:

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        'http://localhost:5173',
        os.getenv('FRONTEND_URL', ''),   # Vercel production URL
    ],
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)
```

#### 6c — Update POST /api/submit

```python
from fastapi import Depends
from auth import get_current_user, require_role
from database import supabase
import uuid as uuid_lib

@app.post('/api/submit')
async def submit_case(
    form: CaseForm,
    user: dict = Depends(require_role('asha_worker', 'admin')),
):
    triage = predict_triage(form.dict())
    briefing = generate_briefing(form.dict(), triage)

    record = {
        'client_id':           str(form.client_id or uuid_lib.uuid4()),
        'submitted_by':        user['sub'],
        'facility_id':         user['user_metadata'].get('facility_id') or None,
        'patient_age':         form.patient_age,
        'patient_sex':         form.patient_sex,
        'patient_location':    form.location,
        'bp_systolic':         form.bp_systolic,
        'bp_diastolic':        form.bp_diastolic,
        'spo2':                form.spo2,
        'heart_rate':          form.heart_rate,
        'temperature':         form.temperature,
        'chief_complaint':     form.chief_complaint,
        'complaint_duration':  form.complaint_duration,
        'symptoms':            form.symptoms or [],
        'observations':        form.observations,
        'known_conditions':    form.known_conditions,
        'current_medications': form.current_medications,
        'triage_level':        triage['triage_level'],
        'triage_confidence':   triage['confidence_score'],
        'risk_driver':         triage['risk_driver'],
        'briefing':            briefing,
        'llm_model_used':      briefing.get('_model_used', 'unknown'),
        'created_offline':     False,
        'client_submitted_at': form.client_submitted_at,
    }

    result = supabase.table('case_records').insert(record).execute()
    return result.data[0]
```

#### 6d — Update GET /api/cases

```python
@app.get('/api/cases')
async def get_cases(
    user: dict = Depends(require_role('doctor', 'admin')),
):
    result = (
        supabase.table('case_records')
        .select('*')
        .is_('deleted_at', 'null')
        .order('created_at', desc=True)
        .execute()
    )
    cases = result.data
    order = {'EMERGENCY': 0, 'URGENT': 1, 'ROUTINE': 2}
    cases.sort(key=lambda c: order.get(c.get('triage_level', 'ROUTINE'), 2))
    return cases
```

#### 6e — Update PATCH /api/cases/{id}/review

```python
@app.patch('/api/cases/{case_id}/review')
async def review_case(
    case_id: str,
    user: dict = Depends(require_role('doctor', 'admin')),
):
    from datetime import datetime, timezone
    supabase.table('case_records').update({
        'reviewed_by': user['sub'],
        'reviewed_at': datetime.now(timezone.utc).isoformat(),
    }).eq('id', case_id).execute()
    return {'status': 'reviewed'}
```

#### 6f — Update GET /api/health

```python
@app.get('/api/health')
async def health():
    try:
        supabase.table('facilities').select('id').limit(1).execute()
        db_status = 'connected'
    except Exception as e:
        db_status = f'error: {str(e)}'
    return {
        'status': 'ok',
        'database': db_status,
        'classifier': 'loaded',
    }
```

#### 6g — Update CaseForm schema

Add `client_id` and `client_submitted_at` to the Pydantic `CaseForm` in `schemas.py`:

```python
from typing import Optional
import uuid
from datetime import datetime

class CaseForm(BaseModel):
    client_id:           Optional[uuid.UUID] = None
    client_submitted_at: Optional[datetime]  = None
    # ... all existing fields remain unchanged
```

---

### STEP 7 — Frontend: Supabase Client and Auth Store

#### 7a — Install dependencies

```bash
npm install @supabase/supabase-js idb
```

`idb` is the IndexedDB wrapper for token storage. Smaller and cleaner than the raw IndexedDB API.

#### 7b — Add environment variables

Add to `frontend/.env.local`:

```
VITE_SUPABASE_URL=https://<ref>.supabase.co
VITE_SUPABASE_ANON_KEY=eyJ...
# VITE_API_BASE_URL already exists
```

Create `frontend/.env.example` (committed to git):

```
VITE_SUPABASE_URL=https://your-ref.supabase.co
VITE_SUPABASE_ANON_KEY=your_anon_key_here
VITE_API_BASE_URL=https://your-backend.onrender.com
```

#### 7c — Create src/lib/supabase.js

```javascript
import { createClient } from '@supabase/supabase-js'
import { openDB } from 'idb'

// IndexedDB store for token persistence (survives memory pressure, PWA-safe)
const DB_NAME    = 'vitalnet_auth'
const STORE_NAME = 'tokens'

async function getTokenDB() {
  return openDB(DB_NAME, 1, {
    upgrade(db) { db.createObjectStore(STORE_NAME); }
  })
}

const idbStorage = {
  async getItem(key) {
    const db = await getTokenDB()
    return db.get(STORE_NAME, key) ?? null
  },
  async setItem(key, value) {
    const db = await getTokenDB()
    await db.put(STORE_NAME, value, key)
  },
  async removeItem(key) {
    const db = await getTokenDB()
    await db.delete(STORE_NAME, key)
  },
}

export const supabase = createClient(
  import.meta.env.VITE_SUPABASE_URL,
  import.meta.env.VITE_SUPABASE_ANON_KEY,
  {
    auth: {
      storage:             idbStorage,   // persist in IndexedDB, not localStorage
      autoRefreshToken:    true,          // silent background refresh
      persistSession:      true,          // survive page reload
      detectSessionInUrl:  false,         // no OAuth redirects
    }
  }
)
```

#### 7d — Create src/store/authStore.js

```javascript
import { createContext, useContext, useEffect, useState } from 'react'
import { supabase } from '../lib/supabase'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [session,  setSession]  = useState(undefined) // undefined = loading
  const [profile,  setProfile]  = useState(null)

  useEffect(() => {
    // Load existing session from IndexedDB on mount
    supabase.auth.getSession().then(({ data: { session } }) => {
      setSession(session)
      if (session) fetchProfile(session.user.id)
    })

    // Listen for auth state changes (login, logout, token refresh)
    const { data: { subscription } } = supabase.auth.onAuthStateChange(
      (_event, session) => {
        setSession(session)
        if (session) fetchProfile(session.user.id)
        else setProfile(null)
      }
    )
    return () => subscription.unsubscribe()
  }, [])

  async function fetchProfile(userId) {
    const { data } = await supabase
      .from('profiles')
      .select('*')
      .eq('id', userId)
      .single()
    setProfile(data)
  }

  const value = {
    session,
    profile,
    role:      profile?.role ?? null,
    isLoading: session === undefined,
    signIn:    (email, password) =>
                 supabase.auth.signInWithPassword({ email, password }),
    signOut:   () => supabase.auth.signOut(),
  }

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export const useAuth = () => useContext(AuthContext)
```

---

### STEP 8 — Frontend: Login Page and Route Guards

#### 8a — Create src/pages/LoginPage.jsx

A minimal login form. Email + password. No OAuth. Submit calls `supabase.auth.signInWithPassword`.

On success, the `onAuthStateChange` listener in `authStore` fires automatically — no manual navigation needed. Add a loading state on the button and display `error.message` on failure.

Visual spec: centered card, `max-w-sm`, Inter font, same shadow elevation system as Phase 5. EMERGENCY/URGENT/ROUTINE color palette is NOT used here — this is a neutral UI.

#### 8b — Create src/components/RouteGuard.jsx

```javascript
import { useAuth } from '../store/authStore'

export function RouteGuard({ children, requiredRole = null }) {
  const { session, role, isLoading } = useAuth()

  if (isLoading) return <FullscreenSpinner />
  if (!session)  return <LoginPage />
  if (requiredRole && role !== requiredRole && role !== 'admin')
    return <AccessDenied />

  return children
}
```

#### 8c — Update App.jsx routing

Wrap the entire app in `AuthProvider`. Apply `RouteGuard` per panel. Do not add `react-router-dom`.

```javascript
import { AuthProvider, useAuth } from './store/authStore'
import { RouteGuard } from './components/RouteGuard'

function AppInner() {
  const { role } = useAuth()

  // Role-based view selection
  if (role === 'doctor' || role === 'admin') return <DoctorDashboard />
  if (role === 'asha_worker')                return <IntakeForm />
  return null  // RouteGuard handles unauthenticated state
}

export default function App() {
  return (
    <AuthProvider>
      <RouteGuard>
        <AppInner />
      </RouteGuard>
    </AuthProvider>
  )
}
```

#### 8d — Create src/lib/api.js

Replace all existing `fetch()` calls in `IntakeForm.jsx` and `Dashboard.jsx` with these helpers:

```javascript
import { supabase } from './supabase'

const BASE = import.meta.env.VITE_API_BASE_URL

async function authHeaders() {
  const { data: { session } } = await supabase.auth.getSession()
  if (!session) throw new Error('Not authenticated')
  return {
    'Content-Type':  'application/json',
    'Authorization': `Bearer ${session.access_token}`,
  }
}

export async function submitCase(formData) {
  const headers = await authHeaders()
  const res = await fetch(`${BASE}/api/submit`, {
    method:  'POST',
    headers,
    body:    JSON.stringify(formData),
  })
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

export async function getCases() {
  const headers = await authHeaders()
  const res = await fetch(`${BASE}/api/cases`, { headers })
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

export async function reviewCase(caseId) {
  const headers = await authHeaders()
  const res = await fetch(`${BASE}/api/cases/${caseId}/review`, {
    method: 'PATCH', headers,
  })
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}
```

---

### STEP 9 — Deployment: Environment Variables

#### Render (backend)

Go to Render dashboard > your backend service > Environment. Add:

| Variable | Value |
|---|---|
| `SUPABASE_URL` | `https://<ref>.supabase.co` |
| `SUPABASE_ANON_KEY` | `eyJ...` (anon/public key) |
| `SUPABASE_JWT_SECRET` | Your JWT secret (never commit this) |
| `GROQ_API_KEY` | Already set — verify it's still there |
| `FRONTEND_URL` | `https://your-app.vercel.app` |

#### Vercel (frontend)

Go to Vercel dashboard > your project > Settings > Environment Variables. Add:

| Variable | Value |
|---|---|
| `VITE_SUPABASE_URL` | `https://<ref>.supabase.co` |
| `VITE_SUPABASE_ANON_KEY` | `eyJ...` (anon/public key) |
| `VITE_API_BASE_URL` | Already set — verify it's still there |

---

### STEP 10 — Verification Checklist

Run all 10 checks in order. All must pass before Phase 6 is considered complete.

| # | Check | Expected Result |
|---|---|---|
| 1 | `GET /api/health` | Returns `{status:ok, database:connected, classifier:loaded}` |
| 2 | `POST /api/submit` (no token) | Returns HTTP 401 Unauthorized |
| 3 | `GET /api/cases` (no token) | Returns HTTP 401 Unauthorized |
| 4 | Login as `asha@test.vitalnet` in browser | LoginPage disappears, IntakeForm renders |
| 5 | Login as `doctor@test.vitalnet` in browser | LoginPage disappears, DoctorDashboard renders |
| 6 | Submit a case as ASHA worker | Returns case record with `submitted_by` = ASHA user UUID |
| 7 | `GET /api/cases` as doctor | Returns the submitted case with correct `triage_level` |
| 8 | `GET /api/cases` as ASHA worker (Postman/curl) | Returns HTTP 403 Forbidden |
| 9 | Mark Reviewed as doctor | `reviewed_by` and `reviewed_at` populated in Supabase |
| 10 | Check profiles table in Supabase dashboard | 3 rows, correct roles for all 3 test users |

---

## 4. What NOT to Do

These rules are non-negotiable. Violating any of them will introduce security vulnerabilities or break downstream phases.

- **Do NOT commit `SUPABASE_JWT_SECRET` to git** under any circumstances. It must only exist in environment variable configuration.
- **Do NOT put `SUPABASE_JWT_SECRET` in frontend code** or any `VITE_` prefixed variable. Vite embeds `VITE_` variables in the browser bundle. `SUPABASE_JWT_SECRET` is backend-only.
- **Do NOT use HS256 with the anon key** for JWT verification. The anon key is for Supabase client calls. `SUPABASE_JWT_SECRET` is for JWT signature verification. These are different values.
- **Do NOT add `react-router-dom`.** State-based routing is the established pattern for this project.
- **Do NOT modify the classifier, `.pkl` file, SHAP logic, or LLM layer.** Phase 6 is auth and database only.
- **Do NOT hard delete records.** All deletes set `deleted_at` timestamp only.
- **Do NOT store tokens in `localStorage`.** IndexedDB only — this is the PWA-safe approach designed for Phase 8.
- **Do NOT change the Groq model list, `FIXED_DISCLAIMER`, or clinical output logic.**

---

## 5. Quick Reference

### New Files Created in Phase 6

| File | Purpose |
|---|---|
| `backend/auth.py` | JWT dependency — `get_current_user()` and `require_role()` |
| `backend/config.py` | Pydantic settings with `SUPABASE_*` env vars |
| `backend/.env.example` | Template for required env vars (committed to git) |
| `frontend/src/lib/supabase.js` | Supabase client with IndexedDB token storage |
| `frontend/src/lib/api.js` | Authenticated fetch helpers for all 3 endpoints |
| `frontend/src/store/authStore.js` | `AuthProvider` + `useAuth` hook |
| `frontend/src/pages/LoginPage.jsx` | Login form UI |
| `frontend/src/components/RouteGuard.jsx` | Auth + role route guard |
| `frontend/.env.example` | Template for required `VITE_` env vars (committed to git) |

### Files Modified in Phase 6

| File | Change |
|---|---|
| `backend/database.py` | Replaced SQLAlchemy/SQLite with `supabase-py` client |
| `backend/main.py` | Removed DB lifespan init. Added `Depends(auth)` to all 3 endpoints. Updated CORS. |
| `backend/schemas.py` | Added `client_id` and `client_submitted_at` to `CaseForm` |
| `backend/requirements.txt` | Added `python-jose`, `supabase`, `psycopg2-binary` |
| `frontend/src/App.jsx` | Wrapped in `AuthProvider` + `RouteGuard`. Role-based view routing. |
| `frontend/src/IntakeForm.jsx` | Replace `fetch()` with `api.js` `submitCase()` |
| `frontend/src/Dashboard.jsx` | Replace `fetch()` with `api.js` `getCases()` and `reviewCase()` |
| `frontend/package.json` | Added `@supabase/supabase-js` and `idb` |
