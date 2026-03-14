# VitalNet — Phase 8 Build Instructions
**PWA · Offline Queue · Background Sync**

| | |
|---|---|
| **Prepared for** | Google Antigravity |
| **Phase** | 8 of 10 |
| **Depends on** | Phase 7 complete — all three panels working, auth live |
| **Files changed** | `frontend/` only — no backend changes in this phase |
| **Risk level** | MEDIUM — service worker wraps the entire app, misconfiguration breaks all navigation |
| **Date** | March 2026 |

---

## 1. What Phase 7 Left Us

- Three panels: `ASHAPanel`, `DoctorPanel`, `AdminPanel` — role-gated, all functional
- Tokens stored in IndexedDB via `idb` (set up in Phase 6 for exactly this moment)
- `submitCase()` in `api.js` is the only write operation that needs offline queuing
- `GET /api/cases/mine` — ASHA history endpoint, online-only is acceptable (read-only, not critical path)
- No service worker exists yet — app requires connectivity for everything

---

## 2. What Phase 8 Builds

### 2.1 Scope

**In scope:**
- App shell caching — the app loads from cache with no network
- Offline detection UI — ASHA panel shows a connectivity banner when offline
- Offline submission queue — form submissions while offline are stored in IndexedDB and synced when connectivity returns
- Workbox Background Sync for the submission queue
- PWA manifest — installable on Android/iOS home screen
- `vite-plugin-pwa` integration

**Out of scope (Phase 9):**
- Offline triage classification (that requires the ONNX model — Phase 9)
- Push notifications
- Offline doctor dashboard (doctor panel requires connectivity — read-only data that must be fresh)

### 2.2 What Works Offline After Phase 8

| Feature | Offline? | Notes |
|---|---|---|
| App load | ✅ | Service worker precaches full app shell |
| Login page | ✅ | Cached — but actual login requires connectivity |
| ASHA intake form | ✅ | Form renders fully offline |
| Submit case | ✅ queued | Stored in IndexedDB, syncs on reconnect |
| ASHA submission history | ❌ | Requires network fetch |
| Doctor dashboard | ❌ | Intentionally online-only — fresh data required |
| Admin panel | ❌ | Intentionally online-only |

### 2.3 Offline Submission Flow (End to End)

```
ASHA fills form → submit pressed
  ↓
navigator.onLine check
  ↓ offline
Store in IndexedDB queue:
  { client_id: uuid, payload: formData, token: accessToken, queued_at: timestamp }
  ↓
Show success toast: "Saved offline. Will submit when connected."
  ↓
Connectivity returns → 'online' event fires
  ↓
Queue processor reads IndexedDB, POSTs each entry to /api/submit
  ↓
On success: remove from IndexedDB queue, show sync toast
On failure: leave in queue, retry on next 'online' event
```

The `client_id` UUID is generated at form submission time (Phase 6 schema already has this column). If the same submission is accidentally POSTed twice (retry after partial success), the `client_id` UNIQUE constraint on `case_records` prevents a duplicate insert — Supabase will return a conflict error which the queue processor treats as success and removes from queue.

---

## 3. Architecture — Two Queuing Mechanisms

There are two approaches to offline sync. Both are implemented in this phase and they serve different purposes:

**Mechanism 1 — Manual IndexedDB queue (primary)**

The `submitCase()` function in `api.js` is replaced with an offline-aware version. On submit, if `navigator.onLine` is false, the payload is written to an IndexedDB store called `submission_queue` and the function returns a fake "queued" response so the UI can show success feedback. A queue processor runs on every `online` event and on page load (to catch queued items from previous sessions).

This is the reliable path. It works regardless of service worker state.

**Mechanism 2 — Workbox Background Sync (secondary/belt-and-suspenders)**

`vite-plugin-pwa` with `workbox.runtimeCaching` also registers a Background Sync handler for `POST /api/submit`. This catches the case where a request was attempted (not offline-detected) but failed mid-flight due to connectivity loss. The Workbox queue has a 24-hour `maxRetentionTime`.

The two mechanisms are complementary, not redundant — Mechanism 1 catches pre-flight offline, Mechanism 2 catches in-flight failures.

---

## 4. Step-by-Step Instructions

### STEP 1 — Install Dependencies

```bash
npm install vite-plugin-pwa workbox-window
npm install --save-dev @vite-pwa/assets-generator
```

### STEP 2 — Generate PWA Icons

Create `public/vitalnet-icon.svg` — a simple SVG with a pulse/heartbeat symbol on a dark blue background (#1E3A5F). Then run:

```bash
npx pwa-assets-generator --preset minimal public/vitalnet-icon.svg
```

This generates `pwa-192x192.png` and `pwa-512x512.png` in `public/`. Commit these files.

### STEP 3 — Update vite.config.js

```javascript
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { VitePWA } from 'vite-plugin-pwa'

export default defineConfig({
  plugins: [
    react(),
    VitePWA({
      registerType: 'autoUpdate',

      // Precache the entire app shell
      workbox: {
        globPatterns: ['**/*.{js,css,html,ico,png,svg,woff2}'],

        // Background Sync for POST /api/submit (in-flight failure recovery)
        runtimeCaching: [{
          urlPattern: ({ url }) => url.pathname === '/api/submit',
          handler: 'NetworkOnly',
          method: 'POST',
          options: {
            backgroundSync: {
              name: 'vitalnet_submission_queue',
              options: {
                maxRetentionTime: 24 * 60,  // 24 hours in minutes
              },
            },
          },
        }],
      },

      manifest: {
        name: 'VitalNet',
        short_name: 'VitalNet',
        description: 'Clinical triage platform for ASHA workers and PHC doctors',
        theme_color: '#1E3A5F',
        background_color: '#F8FAFC',
        display: 'standalone',
        orientation: 'portrait',
        start_url: '/',
        scope: '/',
        icons: [
          {
            src: 'pwa-192x192.png',
            sizes: '192x192',
            type: 'image/png',
          },
          {
            src: 'pwa-512x512.png',
            sizes: '512x512',
            type: 'image/png',
          },
          {
            src: 'pwa-512x512.png',
            sizes: '512x512',
            type: 'image/png',
            purpose: 'any maskable',
          },
        ],
      },
    }),
  ],
})
```

### STEP 4 — Create the Offline Queue Module

Create `src/lib/offlineQueue.js`:

```javascript
import { openDB } from 'idb'

const DB_NAME    = 'vitalnet_offline'
const STORE_NAME = 'submission_queue'

async function getQueueDB() {
  return openDB(DB_NAME, 1, {
    upgrade(db) {
      if (!db.objectStoreNames.contains(STORE_NAME)) {
        const store = db.createObjectStore(STORE_NAME, { keyPath: 'client_id' })
        store.createIndex('queued_at', 'queued_at')
      }
    }
  })
}

export async function enqueue(clientId, payload, accessToken) {
  const db = await getQueueDB()
  await db.put(STORE_NAME, {
    client_id:   clientId,
    payload,
    access_token: accessToken,
    queued_at:   new Date().toISOString(),
  })
}

export async function dequeue(clientId) {
  const db = await getQueueDB()
  await db.delete(STORE_NAME, clientId)
}

export async function getAllQueued() {
  const db = await getQueueDB()
  return db.getAllFromIndex(STORE_NAME, 'queued_at')
}

export async function getQueueCount() {
  const db = await getQueueDB()
  return db.count(STORE_NAME)
}
```

### STEP 5 — Update src/lib/api.js

Replace `submitCase()` with an offline-aware version. All other functions remain unchanged.

```javascript
import { supabase } from './supabase'
import { enqueue, dequeue, getAllQueued } from './offlineQueue'
import { v4 as uuidv4 } from 'uuid'   // add: npm install uuid

const BASE = import.meta.env.VITE_API_BASE_URL

async function authHeaders() {
  const { data: { session } } = await supabase.auth.getSession()
  if (!session) throw new Error('Not authenticated')
  return {
    'Content-Type':  'application/json',
    'Authorization': `Bearer ${session.access_token}`,
  }
}

// Returns the raw access token string (needed for offline queue storage)
async function getAccessToken() {
  const { data: { session } } = await supabase.auth.getSession()
  if (!session) throw new Error('Not authenticated')
  return session.access_token
}

export async function submitCase(formData) {
  // Generate client_id here — same UUID whether online or queued
  const clientId = uuidv4()
  const payload  = { ...formData, client_id: clientId, client_submitted_at: new Date().toISOString() }

  if (!navigator.onLine) {
    // Offline path: store in IndexedDB queue
    const token = await getAccessToken()
    await enqueue(clientId, payload, token)
    return { queued: true, client_id: clientId }
  }

  // Online path: normal POST
  const headers = await authHeaders()
  const res = await fetch(`${BASE}/api/submit`, {
    method: 'POST', headers, body: JSON.stringify(payload),
  })
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

/**
 * processQueue — called on every 'online' event and on app load.
 * Fires all queued submissions in order (oldest first).
 * Returns { synced: number, failed: number }
 */
export async function processQueue() {
  const queued = await getAllQueued()
  if (queued.length === 0) return { synced: 0, failed: 0 }

  let synced = 0
  let failed = 0

  for (const item of queued) {
    try {
      const res = await fetch(`${BASE}/api/submit`, {
        method: 'POST',
        headers: {
          'Content-Type':  'application/json',
          'Authorization': `Bearer ${item.access_token}`,
        },
        body: JSON.stringify(item.payload),
      })

      if (res.ok) {
        await dequeue(item.client_id)
        synced++
      } else if (res.status === 409) {
        // Conflict = already inserted (duplicate submission from retry)
        // Treat as success and remove from queue
        await dequeue(item.client_id)
        synced++
      } else {
        failed++
      }
    } catch {
      // Network error — leave in queue
      failed++
    }
  }

  return { synced, failed }
}

// All other existing functions (getCases, reviewCase, adminListUsers, etc.)
// remain unchanged below this line.
```

Install uuid: `npm install uuid`

### STEP 6 — Connectivity Banner Component

Create `src/components/OfflineBanner.jsx`:

```jsx
import { useState, useEffect } from 'react'
import { getQueueCount } from '../lib/offlineQueue'

export default function OfflineBanner() {
  const [online,      setOnline]      = useState(navigator.onLine)
  const [queueCount,  setQueueCount]  = useState(0)

  useEffect(() => {
    async function updateCount() {
      const count = await getQueueCount()
      setQueueCount(count)
    }

    function handleOnline()  { setOnline(true);  updateCount() }
    function handleOffline() { setOnline(false); updateCount() }

    window.addEventListener('online',  handleOnline)
    window.addEventListener('offline', handleOffline)
    updateCount()

    return () => {
      window.removeEventListener('online',  handleOnline)
      window.removeEventListener('offline', handleOffline)
    }
  }, [])

  if (online && queueCount === 0) return null

  if (!online) {
    return (
      <div className="bg-amber-50 border-b border-amber-200 px-4 py-2 text-center text-sm text-amber-800">
        You are offline. Submissions will be saved and synced when connected.
        {queueCount > 0 && (
          <span className="ml-2 font-medium">{queueCount} pending</span>
        )}
      </div>
    )
  }

  // Online but has queued items (syncing in progress)
  if (online && queueCount > 0) {
    return (
      <div className="bg-blue-50 border-b border-blue-200 px-4 py-2 text-center text-sm text-blue-800">
        Syncing {queueCount} offline submission{queueCount > 1 ? 's' : ''}…
      </div>
    )
  }

  return null
}
```

### STEP 7 — Wire Up Queue Processing and Banner

#### 7a — Add to ASHAPanel.jsx

The `OfflineBanner` sits between the `NavBar` and the main content. Queue processing fires on mount and on every `online` event:

```jsx
import { useEffect } from 'react'
import OfflineBanner from '../components/OfflineBanner'
import { processQueue } from '../lib/api'

// Inside ASHAPanel, add to useEffect:
useEffect(() => {
  // Process any queued submissions from previous offline sessions
  processQueue()

  function handleOnline() {
    processQueue().then(({ synced }) => {
      if (synced > 0) {
        // Trigger a toast: "X submission(s) synced"
        // Use the existing toast system from Phase 5
      }
    })
  }

  window.addEventListener('online', handleOnline)
  return () => window.removeEventListener('online', handleOnline)
}, [])
```

Add `<OfflineBanner />` in the JSX between `<NavBar />` and `<main>`:

```jsx
return (
  <div className="min-h-screen bg-slate-50">
    <NavBar tabs={TABS} activeTab={activeTab} onTabChange={setActiveTab} />
    <OfflineBanner />
    <main className="max-w-2xl mx-auto px-4 py-6">
      ...
    </main>
  </div>
)
```

#### 7b — Update IntakeForm submit feedback

The `submitCase()` now returns `{ queued: true, client_id }` when offline. Update `IntakeForm.jsx` to handle this:

```javascript
const result = await submitCase(formData)

if (result.queued) {
  showToast('Saved offline — will sync when connected', 'warning')
} else {
  showToast('Case submitted successfully', 'success')
}
```

### STEP 8 — Register Service Worker Update Prompt

In `src/main.jsx`, register the PWA update handler using `workbox-window`:

```jsx
import { registerSW } from 'virtual:pwa-register'

const updateSW = registerSW({
  onNeedRefresh() {
    // Show a non-intrusive "Update available" banner or toast
    // Call updateSW() to apply it
    console.log('New version available')
  },
  onOfflineReady() {
    console.log('App ready for offline use')
  },
})
```

### STEP 9 — Update .gitignore

Ensure the generated PWA files are handled correctly:

```
# PWA — commit the icons, ignore the generated SW files during dev
# (they are regenerated on build)
dist/sw.js
dist/workbox-*.js
```

The `public/pwa-192x192.png` and `public/pwa-512x512.png` icons should be committed to git.

---

## 5. Verification Checklist

| # | Check | Expected Result |
|---|---|---|
| 1 | `npm run build` | Clean build. `dist/sw.js` and `dist/manifest.webmanifest` present. |
| 2 | Open app in Chrome DevTools > Application > Service Workers | SW registered and active |
| 3 | DevTools > Application > Manifest | All fields populated, icons showing |
| 4 | DevTools > Network tab > set "Offline" | App loads from cache (no network errors) |
| 5 | Fill intake form while offline, submit | Toast says "Saved offline". DevTools > Application > IndexedDB > `vitalnet_offline` > `submission_queue` shows 1 entry |
| 6 | Re-enable network | Toast says "X submission(s) synced". IndexedDB queue is empty. Case appears in doctor dashboard. |
| 7 | Submit same `client_id` twice (simulate retry) | Only one row in `case_records` (UNIQUE constraint prevents duplicate) |
| 8 | Open app on Android Chrome | Install prompt appears ("Add to Home Screen") |
| 9 | Offline banner shows when network disabled | Amber banner visible in ASHA panel |
| 10 | Doctor panel offline | Panel shows stale cached UI but fetch fails gracefully (error state, not white screen) |

---

## 6. What NOT to Do

- **Do NOT cache API responses** in the service worker. Data must always be fresh for clinical accuracy. Only the app shell (JS, CSS, HTML, icons) is precached.
- **Do NOT store the full briefing JSONB in the offline queue.** The queue entry is the raw `IntakeForm` payload only. The briefing is generated server-side after sync.
- **Do NOT run `processQueue()` in the Doctor or Admin panels.** Queue processing is ASHA-only.
- **Do NOT attempt offline triage classification in this phase.** That is Phase 9 (ONNX). In Phase 8, offline submissions get a `triage_level: null` placeholder that gets filled server-side after sync.

Wait — correction: the backend `POST /api/submit` runs the classifier before inserting. So the triage level is always set server-side after sync. The ASHA worker sees "Saved offline" feedback in Phase 8 and sees the triage result in their submission history after sync. Phase 9 adds instant offline triage feedback at form submission time.

---

## 7. Files Summary

### New Files

| File | Purpose |
|---|---|
| `frontend/src/lib/offlineQueue.js` | IndexedDB queue CRUD for offline submissions |
| `frontend/src/components/OfflineBanner.jsx` | Connectivity status banner with queue count |
| `frontend/public/vitalnet-icon.svg` | Source icon for PWA asset generation |
| `frontend/public/pwa-192x192.png` | Generated PWA icon (commit to git) |
| `frontend/public/pwa-512x512.png` | Generated PWA icon (commit to git) |

### Modified Files

| File | Change |
|---|---|
| `frontend/vite.config.js` | Add `VitePWA` plugin with workbox config and manifest |
| `frontend/src/lib/api.js` | Replace `submitCase()` with offline-aware version. Add `processQueue()`. Add `uuid` import. |
| `frontend/src/panels/ASHAPanel.jsx` | Add `OfflineBanner`, `processQueue()` on mount + `online` event |
| `frontend/src/IntakeForm.jsx` | Handle `result.queued` in submit response |
| `frontend/src/main.jsx` | Register service worker with `registerSW` |
| `frontend/package.json` | Add `vite-plugin-pwa`, `workbox-window`, `uuid` |
