# VitalNet — Phase 10 Build Instructions
**Analytics Dashboard · Realtime Updates · System Completion**

| | |
|---|---|
| **Prepared for** | Google Antigravity |
| **Phase** | 10 of 10 |
| **Depends on** | Phase 9 complete — full offline-capable PWA with ONNX triage |
| **Files changed** | `frontend/` (analytics, realtime) · minor `backend/` (analytics endpoint) |
| **Risk level** | LOW — additive only, no changes to existing data flow or auth |
| **Date** | March 2026 |

---

## 1. What the System Looks Like at Phase 9 Completion

By the end of Phase 9, VitalNet is a complete clinical triage platform:

- **ASHA Worker:** installs as PWA, fills intake form offline, gets instant triage badge via ONNX, submissions queue and sync automatically
- **Doctor:** views prioritised case queue (EMERGENCY → URGENT → ROUTINE), reads LLM briefings, marks cases reviewed
- **Admin:** creates and manages users and facilities, views basic system stats
- **Backend:** FastAPI on Railway — classifier + SHAP + Groq LLM + Supabase Postgres
- **Auth:** Supabase JWT, offline-capable token caching in IndexedDB, RLS on all tables

Phase 10 is the final layer — it replaces the placeholder stat cards in the Admin System tab with a real analytics dashboard, adds Supabase Realtime to the doctor dashboard, and makes two small quality-of-life improvements across the app.

---

## 2. What Phase 10 Builds

### 2.1 Admin Analytics Dashboard (replaces AdminStats.jsx stub)

A data-dense, Grafana-inspired analytics panel in the Admin > System tab. No charting library — all visualisations are built with CSS (bar charts as `div` widths, sparklines as SVG paths). This matches the established aesthetic: minimal, data-dense, no decorative animations.

**Section 1 — Case Volume**
- Total cases (all time)
- Cases in the last 7 days (trend bar: today vs 6 days ago)
- Triage breakdown: three horizontal bar segments — EMERGENCY (red-600), URGENT (amber-500), ROUTINE (emerald-600) — proportional widths, absolute counts labelled

**Section 2 — Review Performance**
- Total reviewed vs unreviewed (with percentage)
- Average time from submission to first review (in hours) — computed from `created_at` → `reviewed_at`
- Cases pending review > 2 hours (red badge if any)

**Section 3 — Submission Activity (7-day bar chart)**
- One bar per day for the last 7 days
- Bars broken into EMERGENCY / URGENT / ROUTINE stacked segments
- Built with CSS flexbox columns, no library

**Section 4 — User Activity**
- Active users in last 7 days (users with at least 1 submission)
- Breakdown by role: ASHA workers vs doctors
- Top submitting ASHA workers (name + count, top 5) — **no PHI** — name and count only

### 2.2 Realtime Doctor Dashboard

Replace the polling interval in `Dashboard.jsx` with Supabase Realtime. New cases appear immediately without a page refresh.

The subscription listens for `INSERT` events on `case_records` filtered to the doctor's `facility_id`. When a new case arrives, it is prepended to the case list. A small "New case" pulse indicator appears on the EMERGENCY badge if the incoming case is EMERGENCY.

### 2.3 Quality-of-Life Improvements

**QoL 1 — Doctor: briefing search**
A search input above the case list in the doctor dashboard. Filters visible cards by `chief_complaint` text. Client-side only — no backend call.

**QoL 2 — ASHA: sync status in submission history**
Submission history rows show a "Pending sync" badge (amber) for entries that exist in the offline queue but haven't synced yet. After sync, the badge disappears and the server-confirmed triage badge shows.

---

## 3. Backend: Analytics Endpoint

The existing `GET /api/admin/stats` returns simple counts. Phase 10 adds a richer analytics endpoint.

Add to `backend/admin_routes.py`:

```python
from datetime import datetime, timezone, timedelta

@router.get('/analytics')
async def get_analytics(
    authorization: str = Header(None),
    user: dict = Depends(require_role('admin')),
):
    raw_token = authorization.split(' ', 1)[1]
    db = get_supabase_for_user(raw_token)

    now = datetime.now(timezone.utc)
    seven_days_ago = (now - timedelta(days=7)).isoformat()

    # All-time case counts by triage level
    all_cases = (
        db.table('case_records')
        .select('id, triage_level, created_at, reviewed_at, submitted_by')
        .is_('deleted_at', 'null')
        .execute()
    )

    # Last 7 days
    recent_cases = [
        c for c in all_cases.data
        if c['created_at'] >= seven_days_ago
    ]

    # Triage breakdown
    triage_counts = {'EMERGENCY': 0, 'URGENT': 0, 'ROUTINE': 0}
    for c in all_cases.data:
        triage_counts[c['triage_level']] = triage_counts.get(c['triage_level'], 0) + 1

    # Review stats
    reviewed   = [c for c in all_cases.data if c['reviewed_at']]
    unreviewed = [c for c in all_cases.data if not c['reviewed_at']]

    # Average review time (hours)
    review_times = []
    for c in reviewed:
        created  = datetime.fromisoformat(c['created_at'].replace('Z', '+00:00'))
        rev_time = datetime.fromisoformat(c['reviewed_at'].replace('Z', '+00:00'))
        review_times.append((rev_time - created).total_seconds() / 3600)

    avg_review_hours = (sum(review_times) / len(review_times)) if review_times else 0

    # Cases pending review > 2 hours
    two_hours_ago = (now - timedelta(hours=2)).isoformat()
    overdue = [
        c for c in unreviewed
        if c['created_at'] < two_hours_ago
    ]

    # 7-day daily breakdown
    daily = {}
    for i in range(7):
        day = (now - timedelta(days=i)).strftime('%Y-%m-%d')
        daily[day] = {'EMERGENCY': 0, 'URGENT': 0, 'ROUTINE': 0, 'total': 0}

    for c in recent_cases:
        day = c['created_at'][:10]
        if day in daily:
            daily[day][c['triage_level']] += 1
            daily[day]['total'] += 1

    # Active submitters in last 7 days
    submitter_counts = {}
    for c in recent_cases:
        sid = c['submitted_by']
        if sid:
            submitter_counts[sid] = submitter_counts.get(sid, 0) + 1

    # Enrich top 5 submitters with names from profiles
    top_submitter_ids = sorted(submitter_counts, key=submitter_counts.get, reverse=True)[:5]
    top_submitters = []
    if top_submitter_ids:
        profiles = (
            db.table('profiles')
            .select('id, full_name, role')
            .in_('id', top_submitter_ids)
            .execute()
        )
        name_map = {p['id']: p['full_name'] for p in profiles.data}
        for sid in top_submitter_ids:
            top_submitters.append({
                'name':  name_map.get(sid, 'Unknown'),
                'count': submitter_counts[sid],
            })

    return {
        'total_cases':        len(all_cases.data),
        'recent_cases_7d':    len(recent_cases),
        'triage_counts':      triage_counts,
        'reviewed_count':     len(reviewed),
        'unreviewed_count':   len(unreviewed),
        'avg_review_hours':   round(avg_review_hours, 1),
        'overdue_count':      len(overdue),
        'daily_breakdown':    daily,
        'active_submitters':  len(submitter_counts),
        'top_submitters':     top_submitters,
    }
```

Add API helper in `src/lib/api.js`:

```javascript
export async function adminGetAnalytics() {
  const headers = await authHeaders()
  const res = await fetch(`${BASE}/api/admin/analytics`, { headers })
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}
```

---

## 4. Frontend: Analytics Dashboard

Replace `src/components/admin/AdminStats.jsx` entirely.

### 4.1 Component Structure

```
AdminStats
├── StatCard (total cases, 7d trend)
├── TriageBreakdownBar (proportional CSS bar)
├── ReviewPerformanceCard (reviewed %, avg time, overdue badge)
├── SevenDayChart (CSS stacked bar columns)
└── TopSubmittersCard (ranked list)
```

### 4.2 TriageBreakdownBar

A single horizontal bar divided into three proportional segments. Pure CSS:

```jsx
function TriageBreakdownBar({ counts }) {
  const total = counts.EMERGENCY + counts.URGENT + counts.ROUTINE
  if (total === 0) return <div className="text-slate-400 text-sm">No cases yet</div>

  const pct = level => `${((counts[level] / total) * 100).toFixed(1)}%`

  return (
    <div>
      <div className="flex rounded-full overflow-hidden h-3 bg-slate-100">
        {counts.EMERGENCY > 0 && (
          <div
            style={{ width: pct('EMERGENCY') }}
            className="bg-red-500 transition-all"
            title={`EMERGENCY: ${counts.EMERGENCY}`}
          />
        )}
        {counts.URGENT > 0 && (
          <div
            style={{ width: pct('URGENT') }}
            className="bg-amber-400 transition-all"
            title={`URGENT: ${counts.URGENT}`}
          />
        )}
        {counts.ROUTINE > 0 && (
          <div
            style={{ width: pct('ROUTINE') }}
            className="bg-emerald-400 transition-all"
            title={`ROUTINE: ${counts.ROUTINE}`}
          />
        )}
      </div>
      <div className="flex gap-4 mt-2">
        {['EMERGENCY', 'URGENT', 'ROUTINE'].map(level => (
          <span key={level} className="text-xs text-slate-500">
            <span className={`font-semibold ${
              level === 'EMERGENCY' ? 'text-red-600' :
              level === 'URGENT'    ? 'text-amber-600' :
                                      'text-emerald-600'
            }`}>{counts[level]}</span> {level.toLowerCase()}
          </span>
        ))}
      </div>
    </div>
  )
}
```

### 4.3 SevenDayChart

Seven columns, one per day, each a stacked bar built with CSS flex:

```jsx
function SevenDayChart({ daily }) {
  const days = Object.entries(daily)
    .sort(([a], [b]) => a.localeCompare(b))  // ascending date order

  const maxTotal = Math.max(...days.map(([, d]) => d.total), 1)

  return (
    <div className="flex items-end gap-1 h-24">
      {days.map(([date, counts]) => (
        <div key={date} className="flex-1 flex flex-col items-center gap-0.5">
          <div
            className="w-full flex flex-col-reverse rounded-sm overflow-hidden"
            style={{ height: `${(counts.total / maxTotal) * 80}px` }}
          >
            {counts.ROUTINE > 0 && (
              <div
                className="bg-emerald-400"
                style={{ flex: counts.ROUTINE }}
              />
            )}
            {counts.URGENT > 0 && (
              <div
                className="bg-amber-400"
                style={{ flex: counts.URGENT }}
              />
            )}
            {counts.EMERGENCY > 0 && (
              <div
                className="bg-red-500"
                style={{ flex: counts.EMERGENCY }}
              />
            )}
          </div>
          <span className="text-xs text-slate-400">
            {new Date(date).toLocaleDateString('en-IN', { weekday: 'short' })}
          </span>
        </div>
      ))}
    </div>
  )
}
```

---

## 5. Frontend: Realtime Doctor Dashboard

### 5.1 Enable Realtime on case_records

Run in Supabase SQL Editor:

```sql
-- Enable realtime for case_records table
alter publication supabase_realtime add table public.case_records;
```

### 5.2 Update Dashboard.jsx

Replace the polling `setInterval` with a Supabase Realtime subscription:

```javascript
import { supabase } from '../lib/supabase'

useEffect(() => {
  // Initial load
  fetchCases()

  // Realtime subscription — INSERT events only
  // Filter to current user's facility_id if available
  const channel = supabase
    .channel('case_records_live')
    .on(
      'postgres_changes',
      {
        event:  'INSERT',
        schema: 'public',
        table:  'case_records',
      },
      (payload) => {
        const newCase = payload.new
        // Prepend to case list, maintaining priority sort
        setCases(prev => {
          const updated = [newCase, ...prev]
          const order = { EMERGENCY: 0, URGENT: 1, ROUTINE: 2 }
          return updated.sort(
            (a, b) => order[a.triage_level] - order[b.triage_level]
          )
        })

        // Flash indicator for EMERGENCY cases
        if (newCase.triage_level === 'EMERGENCY') {
          setNewEmergency(true)
          setTimeout(() => setNewEmergency(false), 5000)
        }
      }
    )
    .subscribe()

  return () => supabase.removeChannel(channel)
}, [])
```

Add a `newEmergency` state flag to `Dashboard.jsx`. When true, show a pulsing red dot next to the EMERGENCY section header:

```jsx
{newEmergency && (
  <span className="inline-block w-2 h-2 rounded-full bg-red-500 animate-pulse ml-2" />
)}
```

Remove the existing `setInterval` polling entirely.

### 5.3 Also Subscribe to UPDATE Events

When a doctor marks a case reviewed, all other connected doctors should see the change:

```javascript
.on(
  'postgres_changes',
  { event: 'UPDATE', schema: 'public', table: 'case_records' },
  (payload) => {
    const updated = payload.new
    setCases(prev =>
      prev.map(c => c.id === updated.id ? { ...c, ...updated } : c)
    )
  }
)
```

---

## 6. QoL 1 — Case Search in Doctor Dashboard

Add above the case list in `Dashboard.jsx`:

```jsx
const [search, setSearch] = useState('')

const visibleCases = cases
  .filter(c => filter === 'pending' ? !c.reviewed_at : true)
  .filter(c =>
    !search ||
    c.chief_complaint?.toLowerCase().includes(search.toLowerCase())
  )
```

UI: a single `<input>` with `placeholder="Search complaints…"`, `text-sm`, `border border-slate-200`, `rounded-md`, `px-3 py-1.5`, full width.

---

## 7. QoL 2 — Sync Status in ASHA Submission History

In `ASHAPanel.jsx`, the submission history already shows `case_records` rows from the server. Entries in the offline queue are not yet in the server DB. Phase 10 merges both:

```javascript
import { getAllQueued } from '../lib/offlineQueue'

async function fetchSubmissions() {
  const [serverData, queued] = await Promise.all([
    getMySubmissions(),
    getAllQueued(),
  ])

  // Build a set of queued client_ids for quick lookup
  const queuedIds = new Set(queued.map(q => q.client_id))

  // Merge: server rows + pending queue rows
  const queuedRows = queued.map(q => ({
    id:              q.client_id,
    chief_complaint: q.payload.chief_complaint,
    triage_level:    q.local_triage?.triage_level || null,
    created_at:      q.queued_at,
    pending_sync:    true,
  }))

  // Server rows that are still in the queue (syncing) are replaced by queue version
  const serverRows = serverData.filter(s => !queuedIds.has(s.client_id))

  const merged = [...queuedRows, ...serverRows]
  merged.sort((a, b) => new Date(b.created_at) - new Date(a.created_at))
  setSubmissions(merged)
}
```

In the submission history card, add the pending badge:

```jsx
{s.pending_sync && (
  <span className="text-xs px-2 py-0.5 rounded border border-amber-300 bg-amber-50 text-amber-700">
    Pending sync
  </span>
)}
```

---

## 8. Verification Checklist

| # | Check | Expected Result |
|---|---|---|
| 1 | Admin > System tab | Full analytics dashboard renders with real data |
| 2 | Triage breakdown bar | Proportional segments visible, totals correct |
| 3 | 7-day chart | 7 columns, stacked colour segments, day labels |
| 4 | Review performance card | Correct reviewed %, avg hours, overdue count |
| 5 | Submit a new case — doctor dashboard open in another tab | New case appears in doctor dashboard within 1–2 seconds (realtime) |
| 6 | Mark case reviewed — two doctor sessions open | Both sessions update reviewed state |
| 7 | Doctor search: type partial complaint text | Cards filter in real time |
| 8 | ASHA offline submission — check history tab | "Pending sync" badge on queued entry |
| 9 | Reconnect after ASHA offline submission | "Pending sync" badge disappears, server-confirmed entry shows |
| 10 | `npm run build` | Clean build, no errors |
| 11 | `python -c "from main import app; from admin_routes import router"` | No import errors |

---

## 9. What NOT to Do

- **Do NOT add a charting library** (Chart.js, Recharts, etc.). CSS bars are sufficient and maintain the zero-bloat philosophy.
- **Do NOT poll the database** in `Dashboard.jsx` anymore. The `setInterval` is fully replaced by Realtime.
- **Do NOT expose PHI in the analytics dashboard.** Top submitters shows name + count only — no patient data, no case details.
- **Do NOT run the analytics query in the frontend.** All aggregation happens in the backend endpoint — the frontend only renders the pre-computed values.
- **Do NOT modify the classifier, ONNX model, LLM layer, or auth layer** in Phase 10.

---

## 10. Files Summary

### New Files

| File | Purpose |
|---|---|
| *(none — all changes are modifications)* | |

### Modified Files

| File | Change |
|---|---|
| `backend/admin_routes.py` | Add `GET /api/admin/analytics` endpoint |
| `frontend/src/lib/api.js` | Add `adminGetAnalytics()` |
| `frontend/src/components/admin/AdminStats.jsx` | Full replacement — stub → real analytics dashboard |
| `frontend/src/Dashboard.jsx` | Replace polling with Supabase Realtime. Add search input. Handle UPDATE events. |
| `frontend/src/panels/ASHAPanel.jsx` | Merge offline queue with server history. Show pending sync badge. |

---

## 11. System Completion — What VitalNet Is at Phase 10

At the end of Phase 10, VitalNet is a production-capable rural health triage platform:

| Capability | Status |
|---|---|
| ASHA form intake | ✅ |
| ML triage classification (server) | ✅ |
| SHAP explainability + risk driver | ✅ |
| Groq LLM clinical briefing | ✅ |
| Doctor priority queue + review | ✅ |
| Admin user + facility management | ✅ |
| Role-based access (JWT + RLS) | ✅ |
| Offline-capable PWA | ✅ |
| Offline submission queue + Background Sync | ✅ |
| Instant offline triage (ONNX) | ✅ |
| Realtime doctor dashboard | ✅ |
| Analytics dashboard | ✅ |
| Soft deletes + audit trail | ✅ |
