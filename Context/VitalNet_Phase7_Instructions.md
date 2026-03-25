# VitalNet — Phase 7 Build Instructions
**Panel Separation — ASHA Worker · Doctor · Admin**

| | |
|---|---|
| **Prepared for** | Google Antigravity |
| **Phase** | 7 of 10 |
| **Depends on** | Phase 6 complete — Auth working, Supabase Postgres live |
| **Files changed** | `backend/` (admin routes, admin client) · `frontend/` (panels, nav, layout) |
| **Risk level** | MEDIUM — no changes to classifier, LLM, or auth layer |
| **Date** | March 2026 |

---

## 1. What Phase 6 Left Us (Context for Antigravity)

Phase 6 delivered a working auth foundation. The current state before Phase 7 starts:

- `AuthProvider` + `useAuth()` hook live in `src/store/authStore.js`
- `RouteGuard` in `src/components/RouteGuard.jsx` — shows `LoginPage` if unauthenticated
- `App.jsx` has a minimal `AppInner` that routes `doctor/admin → Dashboard`, `asha_worker → IntakeForm`
- The role comes from `profile.role` fetched from `public.profiles` on login
- `src/lib/api.js` has three authenticated fetch helpers: `submitCase`, `getCases`, `reviewCase`
- Backend has `get_current_user()` + `require_role()` on all three endpoints
- `database.py` has two clients: anon client (public/health) and `get_supabase_for_user(token)` factory (RLS-scoped)

**What Phase 7 adds:** Three distinct, fully-featured panels with proper navigation, layout, and an admin backend that can create/deactivate users and assign roles and facilities.

---

## 2. What Phase 7 Builds

### 2.1 The Three Panels

**ASHA Worker panel** — Two views within a tabbed layout:
- `New Case` tab: the existing `IntakeForm` (unchanged functionally)
- `My Submissions` tab: a list of the worker's own past cases, pulled from `case_records` filtered by `submitted_by = auth.uid()` via RLS. Shows triage badge, chief complaint, timestamp. Read-only.

**Doctor panel** — Two views within a tabbed layout:
- `Pending Review` tab: existing dashboard priority queue — EMERGENCY → URGENT → ROUTINE, unreviewed cases only
- `All Cases` tab: same data but includes reviewed cases, with a visual distinction (muted/checked)

**Admin panel** — Three views within a tabbed layout:
- `Users` tab: paginated table of all users with role, facility, active status. Actions: Create User, Deactivate/Reactivate, Edit role and facility assignment.
- `Facilities` tab: table of all facilities from `public.facilities`. Actions: Add facility, toggle `is_active`.
- `System` tab: read-only stats — total cases, breakdown by triage level, total users by role. No charting library needed — plain stat cards.

### 2.2 Shared Navigation Shell

All three panels share a top navigation bar:
- Left: `VitalNet` wordmark
- Centre: tab pills for the current panel's views (varies per role)
- Right: user's name + role badge + `Sign out` button

This nav lives in a single `src/components/NavBar.jsx` component that reads `profile` from `useAuth()`. The tab state lives in each panel component, not in the nav.

### 2.3 What Does NOT Change in Phase 7

- Classifier, `.pkl`, SHAP, LLM layer — untouched
- `auth.py`, `get_current_user()`, `require_role()` — untouched
- `src/lib/supabase.js`, `src/lib/api.js` (api.js gets additions, not modifications)
- `RouteGuard.jsx` — untouched
- `LoginPage.jsx` — untouched
- The existing `IntakeForm` form logic and `BriefingCard` component — untouched
- All existing backend endpoints — untouched

---

## 3. Architecture Decision — Admin API Client

The Admin API (`create_user`, `list_users`, `update_user_by_id`) requires the `service_role` key. This key must never be in the anon client used for RLS-scoped queries — it bypasses RLS entirely. The solution is a third client in `database.py`:

```python
# database.py — three clients, three purposes
from supabase import create_client
from supabase.lib.client_options import ClientOptions
from config import settings

# 1. Anon client — public reads (health check, facilities list for frontend)
supabase_anon = create_client(settings.supabase_url, settings.supabase_anon_key)

# 2. Per-request factory — RLS-scoped, used for all case_records operations
def get_supabase_for_user(raw_token: str):
    client = create_client(settings.supabase_url, settings.supabase_anon_key)
    client.postgrest.auth(raw_token)
    return client

# 3. Admin client — service_role, used ONLY for auth.admin.* operations
supabase_admin = create_client(
    settings.supabase_url,
    settings.supabase_service_role_key,
    options=ClientOptions(auto_refresh_token=False, persist_session=False),
)
```

`supabase_admin` is used **exclusively** for admin auth operations in the new admin routes. It is never used to query `case_records` or `profiles` — those always go through the per-request RLS client.

Add `SUPABASE_SERVICE_ROLE_KEY` to `config.py` and both `.env.local` and `.env.example`.

> **Security:** `SUPABASE_SERVICE_ROLE_KEY` is backend-only. Never in frontend, never in a `VITE_` variable. It grants full database access with no RLS.

---

## 4. Step-by-Step Instructions

> Complete steps in order. Steps 1–2 are backend. Steps 3–7 are frontend. Step 8 is env vars and deployment. Step 9 is verification.

---

### STEP 1 — Backend: Config + Admin Client

#### 1a — Add SUPABASE_SERVICE_ROLE_KEY to config.py

```python
class Settings(BaseSettings):
    supabase_url: str
    supabase_anon_key: str
    supabase_jwt_secret: str
    supabase_service_role_key: str      # NEW
    groq_api_key: str

    class Config:
        env_file = '.env.local'
        env_file_encoding = 'utf-8'
```

#### 1b — Update database.py

Replace the existing two-client setup with the three-client setup shown in Section 3 above. The existing `supabase` variable (anon client) should be renamed `supabase_anon` for clarity — update the one reference in `main.py`'s health endpoint accordingly.

#### 1c — Update .env.example

```
SUPABASE_URL=https://your-ref.supabase.co
SUPABASE_ANON_KEY=your_anon_key_here
SUPABASE_JWT_SECRET=your_jwt_secret_here
SUPABASE_SERVICE_ROLE_KEY=your_service_role_key_here
GROQ_API_KEY=your_groq_api_key_here
```

---

### STEP 2 — Backend: Admin Routes

Create `backend/admin_routes.py`. This file contains all admin API endpoints. They are mounted in `main.py` under the `/api/admin` prefix and all require `require_role('admin')`.

#### 2a — admin_routes.py

```python
from fastapi import APIRouter, Depends, HTTPException, Header
from pydantic import BaseModel, EmailStr
from typing import Optional
from auth import require_role, get_current_user
from database import supabase_admin, get_supabase_for_user

router = APIRouter(prefix='/api/admin', tags=['admin'])


# ── User management ──────────────────────────────────────────────────────────

class CreateUserRequest(BaseModel):
    email: EmailStr
    password: str
    full_name: str
    role: str                           # 'asha_worker' | 'doctor' | 'admin'
    facility_id: Optional[str] = None
    asha_id: Optional[str] = None


class UpdateUserRequest(BaseModel):
    role: Optional[str] = None
    facility_id: Optional[str] = None
    asha_id: Optional[str] = None
    is_active: Optional[bool] = None


@router.get('/users')
async def list_users(
    authorization: str = Header(None),
    user: dict = Depends(require_role('admin')),
):
    """
    Returns all users joined with their profiles.
    Uses admin client for auth.admin.list_users(), then enriches
    with profiles data for role/facility info.
    """
    raw_token = authorization.split(' ', 1)[1]
    db = get_supabase_for_user(raw_token)

    # Fetch all profiles (admin can read all via RLS policy)
    profiles_result = db.table('profiles').select(
        'id, full_name, role, facility_id, asha_id, is_active, created_at, '
        'facilities(name, district)'
    ).execute()

    profiles_by_id = {p['id']: p for p in profiles_result.data}

    # Fetch auth users for email + last_sign_in
    auth_users = supabase_admin.auth.admin.list_users()

    result = []
    for au in auth_users:
        profile = profiles_by_id.get(au.id, {})
        result.append({
            'id':             au.id,
            'email':          au.email,
            'full_name':      profile.get('full_name', ''),
            'role':           profile.get('role', 'asha_worker'),
            'facility_id':    profile.get('facility_id'),
            'facility_name':  (profile.get('facilities') or {}).get('name'),
            'asha_id':        profile.get('asha_id'),
            'is_active':      profile.get('is_active', True),
            'created_at':     str(au.created_at),
            'last_sign_in':   str(au.last_sign_in_at) if au.last_sign_in_at else None,
        })

    return result


@router.post('/users')
async def create_user(
    body: CreateUserRequest,
    authorization: str = Header(None),
    user: dict = Depends(require_role('admin')),
):
    """
    Creates a new auth user and their profile row.
    email_confirm=True so new users can log in immediately without
    going through email verification flow.
    """
    # Create auth user — trigger will auto-create profiles row
    response = supabase_admin.auth.admin.create_user({
        'email':         body.email,
        'password':      body.password,
        'email_confirm': True,
        'user_metadata': {
            'full_name':    body.full_name,
            'role':         body.role,
            'facility_id':  body.facility_id or '',
        },
    })

    new_user_id = response.user.id

    # Update profile with facility_id and asha_id
    # (trigger creates the row, we patch the extra fields)
    raw_token = authorization.split(' ', 1)[1]
    db = get_supabase_for_user(raw_token)
    db.table('profiles').update({
        'facility_id': body.facility_id,
        'asha_id':     body.asha_id,
    }).eq('id', new_user_id).execute()

    return {'id': new_user_id, 'email': body.email}


@router.patch('/users/{user_id}')
async def update_user(
    user_id: str,
    body: UpdateUserRequest,
    authorization: str = Header(None),
    user: dict = Depends(require_role('admin')),
):
    """
    Updates profile fields (role, facility, asha_id, is_active).
    Also updates user_metadata in auth so the JWT hook re-embeds
    the new role on next login.
    """
    raw_token = authorization.split(' ', 1)[1]
    db = get_supabase_for_user(raw_token)

    profile_update = {}
    meta_update = {}

    if body.role is not None:
        profile_update['role'] = body.role
        meta_update['role'] = body.role
    if body.facility_id is not None:
        profile_update['facility_id'] = body.facility_id
        meta_update['facility_id'] = body.facility_id
    if body.asha_id is not None:
        profile_update['asha_id'] = body.asha_id
    if body.is_active is not None:
        profile_update['is_active'] = body.is_active

    if profile_update:
        db.table('profiles').update(profile_update).eq('id', user_id).execute()

    if meta_update:
        supabase_admin.auth.admin.update_user_by_id(
            user_id, {'user_metadata': meta_update}
        )

    return {'status': 'updated'}


@router.delete('/users/{user_id}')
async def deactivate_user(
    user_id: str,
    authorization: str = Header(None),
    user: dict = Depends(require_role('admin')),
):
    """
    Soft-deactivates: sets profiles.is_active = false.
    Does NOT delete the auth user or their case records.
    The user can no longer log in because RouteGuard will
    detect is_active=false and redirect to an AccessDenied page.
    Hard deletion is intentionally not exposed via API.
    """
    raw_token = authorization.split(' ', 1)[1]
    db = get_supabase_for_user(raw_token)
    db.table('profiles').update({'is_active': False}).eq('id', user_id).execute()
    return {'status': 'deactivated'}


@router.post('/users/{user_id}/reactivate')
async def reactivate_user(
    user_id: str,
    authorization: str = Header(None),
    user: dict = Depends(require_role('admin')),
):
    raw_token = authorization.split(' ', 1)[1]
    db = get_supabase_for_user(raw_token)
    db.table('profiles').update({'is_active': True}).eq('id', user_id).execute()
    return {'status': 'reactivated'}


# ── Facilities management ────────────────────────────────────────────────────

class CreateFacilityRequest(BaseModel):
    name: str
    type: str = 'PHC'
    address: Optional[str] = None
    district: Optional[str] = None
    state: str = 'Tamil Nadu'
    pincode: Optional[str] = None
    phone: Optional[str] = None


@router.get('/facilities')
async def list_facilities(
    authorization: str = Header(None),
    user: dict = Depends(require_role('admin')),
):
    raw_token = authorization.split(' ', 1)[1]
    db = get_supabase_for_user(raw_token)
    result = db.table('facilities').select('*').order('name').execute()
    return result.data


@router.post('/facilities')
async def create_facility(
    body: CreateFacilityRequest,
    authorization: str = Header(None),
    user: dict = Depends(require_role('admin')),
):
    raw_token = authorization.split(' ', 1)[1]
    db = get_supabase_for_user(raw_token)
    result = db.table('facilities').insert(body.dict()).execute()
    return result.data[0]


@router.patch('/facilities/{facility_id}/toggle')
async def toggle_facility(
    facility_id: str,
    authorization: str = Header(None),
    user: dict = Depends(require_role('admin')),
):
    raw_token = authorization.split(' ', 1)[1]
    db = get_supabase_for_user(raw_token)
    current = db.table('facilities').select('is_active').eq('id', facility_id).single().execute()
    new_state = not current.data['is_active']
    db.table('facilities').update({'is_active': new_state}).eq('id', facility_id).execute()
    return {'is_active': new_state}


# ── System stats ─────────────────────────────────────────────────────────────

@router.get('/stats')
async def get_stats(
    authorization: str = Header(None),
    user: dict = Depends(require_role('admin')),
):
    raw_token = authorization.split(' ', 1)[1]
    db = get_supabase_for_user(raw_token)

    cases = db.table('case_records').select('triage_level').is_('deleted_at', 'null').execute()
    profiles = db.table('profiles').select('role, is_active').execute()

    triage_counts = {'EMERGENCY': 0, 'URGENT': 0, 'ROUTINE': 0}
    for c in cases.data:
        triage_counts[c['triage_level']] = triage_counts.get(c['triage_level'], 0) + 1

    role_counts = {}
    active_count = 0
    for p in profiles.data:
        role_counts[p['role']] = role_counts.get(p['role'], 0) + 1
        if p['is_active']:
            active_count += 1

    return {
        'total_cases':    len(cases.data),
        'triage_counts':  triage_counts,
        'total_users':    len(profiles.data),
        'active_users':   active_count,
        'role_counts':    role_counts,
    }
```

#### 2b — Mount admin router in main.py

Add at the bottom of the imports section and after the existing app setup:

```python
from admin_routes import router as admin_router
app.include_router(admin_router)
```

#### 2c — Add RLS policy for admin to read all profiles

Run this in the Supabase SQL Editor:

```sql
-- Admins can update any profile (for role/facility assignment)
create policy "admin_update_profiles" on public.profiles
    for update
    using ((auth.jwt()->'user_metadata'->>'role') = 'admin');

-- Admins can insert facilities
create policy "admin_insert_facilities" on public.facilities
    for insert
    with check ((auth.jwt()->'user_metadata'->>'role') = 'admin');

-- Admins can update facilities
create policy "admin_update_facilities" on public.facilities
    for update
    using ((auth.jwt()->'user_metadata'->>'role') = 'admin');
```

---

### STEP 3 — Frontend: Add Admin API helpers to api.js

Add the following to `src/lib/api.js`. Do not modify any existing functions.

```javascript
// ── Admin: Users ─────────────────────────────────────────────────────────────

export async function adminListUsers() {
  const headers = await authHeaders()
  const res = await fetch(`${BASE}/api/admin/users`, { headers })
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

export async function adminCreateUser(data) {
  const headers = await authHeaders()
  const res = await fetch(`${BASE}/api/admin/users`, {
    method: 'POST', headers, body: JSON.stringify(data),
  })
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

export async function adminUpdateUser(userId, data) {
  const headers = await authHeaders()
  const res = await fetch(`${BASE}/api/admin/users/${userId}`, {
    method: 'PATCH', headers, body: JSON.stringify(data),
  })
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

export async function adminDeactivateUser(userId) {
  const headers = await authHeaders()
  const res = await fetch(`${BASE}/api/admin/users/${userId}`, {
    method: 'DELETE', headers,
  })
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

export async function adminReactivateUser(userId) {
  const headers = await authHeaders()
  const res = await fetch(`${BASE}/api/admin/users/${userId}/reactivate`, {
    method: 'POST', headers,
  })
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

// ── Admin: Facilities ─────────────────────────────────────────────────────────

export async function adminListFacilities() {
  const headers = await authHeaders()
  const res = await fetch(`${BASE}/api/admin/facilities`, { headers })
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

export async function adminCreateFacility(data) {
  const headers = await authHeaders()
  const res = await fetch(`${BASE}/api/admin/facilities`, {
    method: 'POST', headers, body: JSON.stringify(data),
  })
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

export async function adminToggleFacility(facilityId) {
  const headers = await authHeaders()
  const res = await fetch(`${BASE}/api/admin/facilities/${facilityId}/toggle`, {
    method: 'PATCH', headers,
  })
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

// ── Admin: Stats ──────────────────────────────────────────────────────────────

export async function adminGetStats() {
  const headers = await authHeaders()
  const res = await fetch(`${BASE}/api/admin/stats`, { headers })
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

// ── ASHA: Submission history ──────────────────────────────────────────────────

export async function getMySubmissions() {
  const headers = await authHeaders()
  const res = await fetch(`${BASE}/api/cases/mine`, { headers })
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}
```

---

### STEP 4 — Backend: ASHA Submission History Endpoint

Add this endpoint to `main.py`. It returns only the calling user's own cases — RLS enforces this at the DB level as well, but the query explicitly filters by `submitted_by` for clarity:

```python
@app.get('/api/cases/mine')
async def get_my_cases(
    authorization: str = Header(None),
    user: dict = Depends(require_role('asha_worker', 'admin')),
):
    raw_token = authorization.split(' ', 1)[1]
    db = get_supabase_for_user(raw_token)
    result = (
        db.table('case_records')
        .select('id, chief_complaint, triage_level, created_at, reviewed_at, patient_age, patient_sex')
        .eq('submitted_by', user['sub'])
        .is_('deleted_at', 'null')
        .order('created_at', desc=True)
        .execute()
    )
    return result.data
```

Note: this endpoint selects a limited set of columns intentionally — the full `briefing` JSONB is not returned here. The ASHA worker sees enough to confirm submission, not the doctor-facing clinical analysis.

---

### STEP 5 — Frontend: NavBar Component

Create `src/components/NavBar.jsx`:

```jsx
import { useAuth } from '../store/authStore'

const ROLE_LABELS = {
  asha_worker: 'ASHA Worker',
  doctor:      'Doctor',
  admin:       'Admin',
}

const ROLE_COLORS = {
  asha_worker: 'bg-emerald-100 text-emerald-800',
  doctor:      'bg-blue-100 text-blue-800',
  admin:       'bg-slate-100 text-slate-700',
}

export default function NavBar({ tabs, activeTab, onTabChange }) {
  const { profile, signOut } = useAuth()

  return (
    <nav className="sticky top-0 z-10 bg-white border-b border-slate-200 shadow-sm">
      <div className="max-w-6xl mx-auto px-4 h-14 flex items-center gap-6">

        {/* Wordmark */}
        <span className="font-semibold text-slate-800 text-sm tracking-tight shrink-0">
          VitalNet
        </span>

        {/* Tab pills */}
        <div className="flex items-center gap-1 flex-1">
          {tabs.map(tab => (
            <button
              key={tab.id}
              onClick={() => onTabChange(tab.id)}
              className={`px-3 py-1.5 rounded-md text-sm font-medium transition-colors ${
                activeTab === tab.id
                  ? 'bg-slate-100 text-slate-900'
                  : 'text-slate-500 hover:text-slate-700 hover:bg-slate-50'
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {/* User identity */}
        <div className="flex items-center gap-3 shrink-0">
          <span className="text-sm text-slate-600 hidden sm:block">
            {profile?.full_name || profile?.id?.slice(0, 8)}
          </span>
          <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${
            ROLE_COLORS[profile?.role] || ROLE_COLORS.admin
          }`}>
            {ROLE_LABELS[profile?.role] || profile?.role}
          </span>
          <button
            onClick={signOut}
            className="text-sm text-slate-400 hover:text-slate-600 transition-colors"
          >
            Sign out
          </button>
        </div>

      </div>
    </nav>
  )
}
```

---

### STEP 6 — Frontend: Panel Components

#### 6a — Create src/panels/ASHAPanel.jsx

```jsx
import { useState, useEffect } from 'react'
import NavBar from '../components/NavBar'
import IntakeForm from '../IntakeForm'
import { getMySubmissions } from '../lib/api'

const TABS = [
  { id: 'new',     label: 'New Case' },
  { id: 'history', label: 'My Submissions' },
]

const TRIAGE_STYLES = {
  EMERGENCY: 'bg-red-100 text-red-700 border-red-200',
  URGENT:    'bg-amber-100 text-amber-700 border-amber-200',
  ROUTINE:   'bg-emerald-100 text-emerald-700 border-emerald-200',
}

export default function ASHAPanel() {
  const [activeTab,    setActiveTab]    = useState('new')
  const [submissions,  setSubmissions]  = useState([])
  const [loading,      setLoading]      = useState(false)
  const [error,        setError]        = useState(null)

  useEffect(() => {
    if (activeTab === 'history') fetchSubmissions()
  }, [activeTab])

  async function fetchSubmissions() {
    setLoading(true)
    setError(null)
    try {
      const data = await getMySubmissions()
      setSubmissions(data)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-slate-50">
      <NavBar tabs={TABS} activeTab={activeTab} onTabChange={setActiveTab} />

      <main className="max-w-2xl mx-auto px-4 py-6">
        {activeTab === 'new' && <IntakeForm />}

        {activeTab === 'history' && (
          <div>
            <h2 className="text-base font-semibold text-slate-800 mb-4">My Submissions</h2>

            {loading && (
              <div className="text-center py-12 text-slate-400 text-sm">Loading...</div>
            )}

            {error && (
              <div className="bg-red-50 border border-red-200 rounded-lg px-4 py-3 text-red-700 text-sm">
                {error}
              </div>
            )}

            {!loading && !error && submissions.length === 0 && (
              <div className="text-center py-12 text-slate-400 text-sm">
                No submissions yet.
              </div>
            )}

            {!loading && submissions.map(s => (
              <div
                key={s.id}
                className="bg-white rounded-lg border border-slate-200 shadow-sm px-4 py-3 mb-3"
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-slate-800 truncate">
                      {s.chief_complaint}
                    </p>
                    <p className="text-xs text-slate-400 mt-0.5">
                      {s.patient_age ? `${s.patient_age}y` : '—'}
                      {s.patient_sex ? ` · ${s.patient_sex}` : ''}
                      {' · '}
                      {new Date(s.created_at).toLocaleDateString('en-IN', {
                        day: 'numeric', month: 'short', year: 'numeric'
                      })}
                    </p>
                  </div>
                  <div className="flex flex-col items-end gap-1 shrink-0">
                    <span className={`text-xs px-2 py-0.5 rounded border font-medium ${TRIAGE_STYLES[s.triage_level]}`}>
                      {s.triage_level}
                    </span>
                    {s.reviewed_at && (
                      <span className="text-xs text-emerald-600">✓ Reviewed</span>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </main>
    </div>
  )
}
```

#### 6b — Create src/panels/DoctorPanel.jsx

```jsx
import { useState, useEffect } from 'react'
import NavBar from '../components/NavBar'
import Dashboard from '../Dashboard'          // existing component, untouched

const TABS = [
  { id: 'pending', label: 'Pending Review' },
  { id: 'all',     label: 'All Cases' },
]

export default function DoctorPanel() {
  const [activeTab, setActiveTab] = useState('pending')

  return (
    <div className="min-h-screen bg-slate-50">
      <NavBar tabs={TABS} activeTab={activeTab} onTabChange={setActiveTab} />
      {/*
        Pass activeTab to Dashboard so it can filter:
        - 'pending': reviewed_at IS NULL
        - 'all': no filter
      */}
      <Dashboard filter={activeTab} />
    </div>
  )
}
```

Update `Dashboard.jsx` to accept and use the `filter` prop:

```jsx
// In Dashboard.jsx — update the getCases() result filtering
const visibleCases = filter === 'pending'
  ? cases.filter(c => !c.reviewed_at)
  : cases
```

#### 6c — Create src/panels/AdminPanel.jsx

```jsx
import { useState } from 'react'
import NavBar from '../components/NavBar'
import AdminUsers from '../components/admin/AdminUsers'
import AdminFacilities from '../components/admin/AdminFacilities'
import AdminStats from '../components/admin/AdminStats'

const TABS = [
  { id: 'users',      label: 'Users' },
  { id: 'facilities', label: 'Facilities' },
  { id: 'system',     label: 'System' },
]

export default function AdminPanel() {
  const [activeTab, setActiveTab] = useState('users')

  return (
    <div className="min-h-screen bg-slate-50">
      <NavBar tabs={TABS} activeTab={activeTab} onTabChange={setActiveTab} />
      <main className="max-w-5xl mx-auto px-4 py-6">
        {activeTab === 'users'      && <AdminUsers />}
        {activeTab === 'facilities' && <AdminFacilities />}
        {activeTab === 'system'     && <AdminStats />}
      </main>
    </div>
  )
}
```

---

### STEP 7 — Frontend: Admin Sub-Components

#### 7a — Create src/components/admin/AdminUsers.jsx

This is the most complex component. It manages the full user list with inline edit and create form.

**State:** `users` list, `loading`, `error`, `showCreateForm` (boolean), `editingId` (UUID or null).

**On mount:** call `adminListUsers()`, store in `users`.

**Table columns:** Full Name · Email · Role · Facility · ASHA ID · Status · Actions.

**Actions per row:**
- `Edit` button: opens an inline row edit with dropdowns for Role (select: `asha_worker` / `doctor` / `admin`) and Facility (select from facilities list, fetched once on mount via `adminListFacilities()`). Saves via `adminUpdateUser(id, {...})`.
- `Deactivate` / `Reactivate` button: calls the respective API function. Refreshes the list after.

**Create User form** (shown when `showCreateForm=true`): fields for Full Name, Email, Password, Role (select), Facility (select), ASHA ID (optional). Submit calls `adminCreateUser(data)` then refreshes the list and hides the form.

**Visual spec:**
- Active users: normal row
- Inactive users: muted row with `opacity-50`, status badge reads `Inactive` in slate-400
- Role badges: same style as NavBar role badges (emerald for ASHA, blue for doctor, slate for admin)
- Error states: inline red text below the relevant field, not a toast

#### 7b — Create src/components/admin/AdminFacilities.jsx

**State:** `facilities` list, `loading`, `showCreateForm`.

**On mount:** call `adminListFacilities()`.

**Table columns:** Name · Type · District · Phone · Status · Actions.

**Actions:** `Toggle Active/Inactive` button calls `adminToggleFacility(id)` and refreshes. `Add Facility` button shows a create form with fields: Name, Type (select: PHC / CHC / District Hospital), Address, District, State, Pincode, Phone.

#### 7c — Create src/components/admin/AdminStats.jsx

**On mount:** call `adminGetStats()`.

**Layout:** Three stat cards in a row, then a second row with role breakdown.

**Card 1 — Cases:** total count, then three sub-values: EMERGENCY (red-600), URGENT (amber-500), ROUTINE (emerald-600). Same semantic colors as the triage system.

**Card 2 — Users:** total count, active count, then role sub-values.

**Card 3 — System:** a simple placeholder for now — "Analytics dashboard coming in Phase 10."

No charting library. Plain numbers in styled cards with the existing shadow-sm elevation system.

---

### STEP 8 — Update App.jsx

Replace the existing `AppInner` role routing with the three panel components. Also add an `is_active` guard:

```jsx
import ASHAPanel   from './panels/ASHAPanel'
import DoctorPanel from './panels/DoctorPanel'
import AdminPanel  from './panels/AdminPanel'

function AppInner() {
  const { profile, signOut } = useAuth()

  // Deactivated users see an access denied screen, not the app
  if (profile && profile.is_active === false) {
    return (
      <div className="min-h-screen bg-slate-50 flex items-center justify-center">
        <div className="text-center">
          <p className="text-slate-700 font-medium">Account deactivated</p>
          <p className="text-slate-400 text-sm mt-1">Contact your administrator.</p>
          <button
            onClick={signOut}
            className="mt-4 text-sm text-slate-500 hover:text-slate-700"
          >
            Sign out
          </button>
        </div>
      </div>
    )
  }

  if (profile?.role === 'admin')        return <AdminPanel />
  if (profile?.role === 'doctor')       return <DoctorPanel />
  if (profile?.role === 'asha_worker')  return <ASHAPanel />
  return null
}
```

---

### STEP 9 — Environment Variables and Deployment

#### Railway (backend)

Add one new variable:

| Variable | Value |
|---|---|
| `SUPABASE_SERVICE_ROLE_KEY` | Your service role key (Settings > API > Service Role in Supabase dashboard) |

All other variables from Phase 6 remain. No Vercel changes needed.

---

### STEP 10 — Verification Checklist

| # | Check | Expected Result |
|---|---|---|
| 1 | `GET /api/admin/users` (no token) | HTTP 401 |
| 2 | `GET /api/admin/users` (ASHA worker token) | HTTP 403 |
| 3 | `GET /api/admin/users` (admin token) | Returns user list with profile data merged |
| 4 | `POST /api/admin/users` — create new ASHA worker | User appears in Supabase Auth + profiles table |
| 5 | `GET /api/cases/mine` as ASHA worker | Returns only that worker's submissions |
| 6 | Login as ASHA worker in browser | Sees NavBar with "New Case" + "My Submissions" tabs |
| 7 | Login as doctor in browser | Sees NavBar with "Pending Review" + "All Cases" tabs |
| 8 | Login as admin in browser | Sees NavBar with "Users" + "Facilities" + "System" tabs |
| 9 | Doctor: "All Cases" tab | Shows reviewed cases alongside unreviewed |
| 10 | Doctor: "Pending Review" tab | Shows only unreviewed cases |
| 11 | Admin: create a new user | User appears in Users table with correct role badge |
| 12 | Admin: deactivate a user then login as that user | Sees "Account deactivated" screen |
| 13 | Admin: System tab | Correct case counts and user counts |
| 14 | `npm run build` (frontend) | Clean build, no errors |
| 15 | `python -c "from main import app"` (backend) | No import errors |

---

## 5. What NOT to Do

- **Do NOT modify `auth.py`, `get_current_user()`, or `require_role()`** — they are not touched in Phase 7.
- **Do NOT use `supabase_admin` client for case_records queries.** It's for `auth.admin.*` operations only. All data queries go through the per-request RLS client.
- **Do NOT expose a hard-delete user endpoint.** Deactivation only — case records must remain attached to their submitter for clinical audit trail.
- **Do NOT add `react-router-dom`.** Tab state is local `useState` in each panel component.
- **Do NOT put `SUPABASE_SERVICE_ROLE_KEY` in any frontend variable** or commit it to git.
- **Do NOT change the IntakeForm submission logic, classifier, or LLM layer.**
- **Do NOT return the full `briefing` JSONB in `/api/cases/mine`** — that is doctor-facing content. ASHA panel shows triage badge and complaint only.

---

## 6. New Files and Modified Files

### New Files

| File | Purpose |
|---|---|
| `backend/admin_routes.py` | All `/api/admin/*` endpoints — users, facilities, stats |
| `frontend/src/panels/ASHAPanel.jsx` | ASHA worker panel with New Case + My Submissions tabs |
| `frontend/src/panels/DoctorPanel.jsx` | Doctor panel with Pending Review + All Cases tabs |
| `frontend/src/panels/AdminPanel.jsx` | Admin panel shell with tab routing to sub-components |
| `frontend/src/components/NavBar.jsx` | Shared top nav with tabs, user identity, sign out |
| `frontend/src/components/admin/AdminUsers.jsx` | User management table + create form |
| `frontend/src/components/admin/AdminFacilities.jsx` | Facilities table + create form |
| `frontend/src/components/admin/AdminStats.jsx` | System stats cards |

### Modified Files

| File | Change |
|---|---|
| `backend/database.py` | Add `supabase_admin` (service_role client). Rename `supabase` → `supabase_anon`. |
| `backend/config.py` | Add `supabase_service_role_key` field |
| `backend/.env.example` | Add `SUPABASE_SERVICE_ROLE_KEY` placeholder |
| `backend/main.py` | Mount `admin_router`. Add `GET /api/cases/mine`. Update health check to use `supabase_anon`. |
| `frontend/src/lib/api.js` | Add 9 new admin + ASHA history helper functions |
| `frontend/src/App.jsx` | Replace `AppInner` with panel routing + `is_active` guard |
| `frontend/src/Dashboard.jsx` | Accept `filter` prop, apply pending/all filter to rendered list |
