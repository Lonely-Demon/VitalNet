// tests/helpers/mockBackend.js
//
// Shared Supabase-auth + legacy-API mocking for Playwright tests that need a
// logged-in page but must not depend on live credentials (CI's PR-triggered
// jobs deliberately receive no secrets — see docs/TESTING_STRATEGY.md and
// .github/workflows/ci.yml's build-frontend-pr comment). Route-interception
// technique and gotchas (route.fallback() vs route.continue(), registration
// order, UUID-shaped JWT sub) are documented in docs/TESTING_STRATEGY.md.

const CORS_HEADERS = {
  'access-control-allow-origin': '*',
  'access-control-allow-methods': 'GET,POST,PATCH,PUT,DELETE,OPTIONS',
  'access-control-allow-headers': '*',
}

function fulfillJson(route, { status = 200, body, extraHeaders = {} }) {
  const req = route.request()
  if (req.method() === 'OPTIONS') return route.fulfill({ status: 204, headers: CORS_HEADERS })
  return route.fulfill({
    status,
    headers: { ...CORS_HEADERS, 'content-type': 'application/json', ...extraHeaders },
    body: JSON.stringify(body),
  })
}

function fakeJwt(sub) {
  const header = Buffer.from(JSON.stringify({ alg: 'HS256', typ: 'JWT' })).toString('base64url')
  const now = Math.floor(Date.now() / 1000)
  const payload = Buffer.from(JSON.stringify({
    sub, aud: 'authenticated', role: 'authenticated', iat: now, exp: now + 3600, email: `${sub}@test.vitalnet`,
  })).toString('base64url')
  return `${header}.${payload}.fakesig`
}

export const UUIDS = {
  asha_worker: '11111111-1111-4111-8111-111111111111',
  doctor: '22222222-2222-4222-8222-222222222222',
  supervisor: '33333333-3333-4333-8333-333333333333',
  admin: '44444444-4444-4444-8444-444444444444',
}

const FULL_NAMES = {
  asha_worker: 'Priya Sharma',
  doctor: 'Dr. Anil Kumar',
  supervisor: 'Meena Devi',
  admin: 'Admin User',
}

// One emergency + one urgent + one reviewed-routine case — enough to exercise
// BriefingCard's expanded (EMERGENCY auto-expands), flagged, and reviewed
// visual states in a single dashboard scan.
const SAMPLE_CASES = [
  {
    id: 'case-1', created_at: new Date().toISOString(), reviewed_at: null,
    triage_level: 'EMERGENCY', triage_model_version: '3.1.0',
    patient_name: 'Test Patient A', patient_age: 58, patient_sex: 'male', patient_location: 'Rampur Village',
    chief_complaint: 'Chest pain / tightness',
    needs_review: true, low_confidence: false, human_review_requested: false, deterioration_alert: false,
    contraindication_flags: ['Aspirin contraindicated: active GI bleed reported'],
    briefing: {
      primary_risk_driver: 'Crushing central chest pain with diaphoresis, age 58 — high pre-test probability of ACS.',
      differential_diagnoses: ['Acute coronary syndrome', 'Unstable angina', 'Aortic dissection'],
      red_flags: ['Chest pain radiating to left arm', 'Diaphoresis', 'Age > 50'],
      recommended_immediate_actions: ['Administer O2 if SpO2 < 94%', 'Arrange urgent ECG', 'Prepare for referral to higher facility'],
      recommended_tests: ['ECG', 'Troponin'],
      uncertainty_flags: null,
      disclaimer: 'Decision support only — clinical judgment overrides.',
    },
  },
  {
    id: 'case-2', created_at: new Date().toISOString(), reviewed_at: null,
    triage_level: 'URGENT', triage_model_version: '3.1.0',
    patient_name: 'Test Patient B', patient_age: 34, patient_sex: 'female', patient_location: 'Rampur Village',
    chief_complaint: 'High fever with chills',
    needs_review: false, low_confidence: true, human_review_requested: false, deterioration_alert: false,
    contraindication_flags: [],
    briefing: {
      primary_risk_driver: 'Sustained high fever, possible early sepsis picture.',
      differential_diagnoses: ['Malaria', 'Typhoid', 'Dengue'],
      red_flags: [],
      recommended_immediate_actions: ['Antipyretics', 'Oral rehydration', 'Refer if fever persists > 48h'],
      recommended_tests: ['Rapid malaria test', 'CBC'],
      uncertainty_flags: 'Low model confidence — vitals partially missing.',
      disclaimer: 'Decision support only — clinical judgment overrides.',
    },
  },
  {
    id: 'case-3', created_at: new Date().toISOString(), reviewed_at: new Date().toISOString(),
    triage_level: 'ROUTINE', triage_model_version: '3.1.0',
    patient_name: 'Test Patient C', patient_age: 8, patient_sex: 'male', patient_location: 'Rampur Village',
    chief_complaint: 'Mild cough',
    needs_review: false, low_confidence: false, human_review_requested: false, deterioration_alert: false,
    contraindication_flags: [],
    briefing: {
      primary_risk_driver: 'Isolated mild cough, no red flags, well-appearing child.',
      differential_diagnoses: ['Viral URI'],
      red_flags: [],
      recommended_immediate_actions: ['Supportive care', 'Return if breathing difficulty develops'],
      recommended_tests: [],
      uncertainty_flags: null,
      disclaimer: 'Decision support only — clinical judgment overrides.',
    },
  },
]

/**
 * Mocks Supabase auth + profile + a realistic legacy-API surface for `role`.
 * Fixture shapes are verified against actual consumers (TeamMetrics.jsx,
 * OutbreakSignals.jsx, AnalyticsDashboard.jsx, Dashboard.jsx, ASHAPanel.jsx,
 * AdminUsers/Facilities/Stats/AuditLog.jsx) — not guessed — so pages render
 * real content instead of falling into empty/error states.
 */
export async function mockAuthAndData(page, { role, facility_id = 'fac-1' }) {
  const userId = UUIDS[role]
  const now = Math.floor(Date.now() / 1000)
  const fakeUser = {
    id: userId, aud: 'authenticated', role: 'authenticated',
    email: `${role}@test.vitalnet`, email_confirmed_at: new Date().toISOString(),
    app_metadata: { provider: 'email', providers: ['email'] },
    user_metadata: {}, identities: [], created_at: new Date().toISOString(),
  }
  const profile = {
    id: userId, role, facility_id, is_active: true,
    full_name: FULL_NAMES[role],
    facilities: { phone: '+919876543210' },
  }

  await page.route('**/auth/v1/token**', (route) => fulfillJson(route, { body: {
    access_token: fakeJwt(userId), token_type: 'bearer', expires_in: 3600, expires_at: now + 3600,
    refresh_token: 'fake-refresh-token', user: fakeUser,
  }}))
  await page.route('**/auth/v1/user**', (route) => fulfillJson(route, { body: fakeUser }))
  await page.route('**/rest/v1/profiles**', (route) => fulfillJson(route, {
    body: profile, extraHeaders: { 'content-type': 'application/vnd.pgrst.object+json' },
  }))
  await page.route('**/rest/v1/**', (route) => {
    if (route.request().url().includes('/profiles')) return route.fallback()
    fulfillJson(route, { body: [], extraHeaders: { 'content-range': '0-0/0' } })
  })
  await page.route('**/realtime/v1/**', (route) => route.abort())
  await page.route('**/api/health**', (route) => fulfillJson(route, { body: { status: 'ok' } }))

  await page.route('http://localhost:8000/api/**', (route) => {
    const url = route.request().url()

    if (url.includes('/api/cases/mine')) {
      return fulfillJson(route, { body: { cases: SAMPLE_CASES, hasMore: false, nextCursor: null, nextId: null } })
    }
    if (url.includes('/api/cases')) {
      return fulfillJson(route, { body: {
        cases: SAMPLE_CASES, hasMore: false, nextCursor: null, nextTriagePriority: null, nextId: null,
      }})
    }
    if (url.includes('/api/supervisor/team-metrics')) {
      return fulfillJson(route, { body: {
        workers: [
          {
            user_id: 'w1', full_name: 'Priya Sharma', submission_count: 12,
            needs_review_count: 2, needs_review_rate: 0.17,
            contraindication_flag_count: 1, contraindication_flag_rate: 0.08,
            deterioration_alert_count: 0, deterioration_alert_rate: 0,
            tier_distribution: { EMERGENCY: 1, URGENT: 4, ROUTINE: 7 },
          },
          {
            user_id: 'w2', full_name: 'Ravi Kumar', submission_count: 9,
            needs_review_count: 0, needs_review_rate: 0,
            contraindication_flag_count: 0, contraindication_flag_rate: 0,
            deterioration_alert_count: 1, deterioration_alert_rate: 0.11,
            tier_distribution: { EMERGENCY: 0, URGENT: 2, ROUTINE: 7 },
          },
        ],
      }})
    }
    if (url.includes('/api/outbreak/signals')) {
      return fulfillJson(route, { body: {
        date: '2026-07-12',
        signals: [
          { facility_id: 'fac-1', symptom: 'fever_respiratory', today_count: 6, baseline_mean: 1.8, baseline_stddev: 0.9, threshold: 4 },
        ],
      }})
    }
    if (url.includes('/api/analytics/summary')) {
      return fulfillJson(route, { body: {
        triage_distribution: { EMERGENCY: 9, URGENT: 34, ROUTINE: 99 },
        daily_volume: {
          '2026-07-06': 14, '2026-07-07': 18, '2026-07-08': 21,
          '2026-07-09': 16, '2026-07-10': 23, '2026-07-11': 19, '2026-07-12': 11,
        },
        total_cases: 142, reviewed_count: 128, unreviewed_count: 14,
        top_asha_workers: [
          { name: 'Priya Sharma', count: 32 },
          { name: 'Ravi Kumar', count: 27 },
        ],
      }})
    }
    if (url.includes('/api/analytics/response-times')) {
      return fulfillJson(route, { body: { tiers: {
        EMERGENCY: { median_minutes: 6, p90_minutes: 14, overdue_count: 1, overdue_threshold_minutes: 15 },
        URGENT: { median_minutes: 22, p90_minutes: 48, overdue_count: 0, overdue_threshold_minutes: 60 },
        ROUTINE: { median_minutes: 90, p90_minutes: 210, overdue_count: 0, overdue_threshold_minutes: 1440 },
      }}})
    }
    if (url.includes('/api/analytics/ml-agreement')) {
      return fulfillJson(route, { body: {
        overall_agreement_rate: 0.87, overall_count: 96,
        by_tier: {
          EMERGENCY: { agreement_rate: 0.92, count: 9 },
          URGENT: { agreement_rate: 0.81, count: 30 },
          ROUTINE: { agreement_rate: 0.88, count: 57 },
        },
      }})
    }
    if (url.includes('/api/admin/users')) {
      return fulfillJson(route, { body: { data: [
        { id: 'u1', email: 'asha@test.vitalnet', role: 'asha_worker', is_active: true, full_name: 'Priya Sharma', facility_id: 'fac-1', facility_name: 'Rampur PHC', asha_id: 'ASHA-042' },
        { id: 'u2', email: 'doctor@test.vitalnet', role: 'doctor', is_active: true, full_name: 'Dr. Anil Kumar', facility_id: 'fac-1', facility_name: 'Rampur PHC', asha_id: null },
      ]}})
    }
    if (url.includes('/api/admin/facilities')) {
      return fulfillJson(route, { body: [
        { id: 'fac-1', name: 'Rampur PHC', type: 'PHC', district: 'Rampur', phone: '+911234567890', capacity_status: 'available', is_active: true },
      ]})
    }
    if (url.includes('/api/admin/stats')) {
      return fulfillJson(route, { body: {
        total_cases: 142, triage_counts: { EMERGENCY: 9, URGENT: 34, ROUTINE: 99 },
        total_users: 18, active_users: 16,
        role_counts: { asha_worker: 12, doctor: 3, admin: 2, supervisor: 1 },
      }})
    }
    if (url.includes('/api/admin/audit-log')) {
      return fulfillJson(route, { body: {
        entries: [
          { id: 'a1', created_at: new Date().toISOString(), event_type: 'PHI_CREATE', user_role: 'asha_worker', resource_type: 'case', resource_id: 'c-101', facility_id: 'fac-1', ip_address: '10.0.0.1' },
        ],
        hasMore: false, nextCursor: null,
      }})
    }
    if (url.includes('/api/protocol/questions')) {
      return fulfillJson(route, { body: { questions: [] } })
    }
    return fulfillJson(route, { body: {} })
  })

  return { userId, profile }
}

export async function loginAs(page, role, email = `${role}@test.vitalnet`) {
  await mockAuthAndData(page, { role })
  await page.reload({ waitUntil: 'networkidle' })
  const emailInput = page.locator('input[type="email"]')
  await emailInput.waitFor({ state: 'visible', timeout: 5000 })
  await emailInput.fill(email)
  await page.fill('input[type="password"]', 'whatever-mocked')
  await page.click('button[type="submit"]')
  await page.locator('nav').first().waitFor({ state: 'visible', timeout: 5000 })
  await page.waitForTimeout(300)
}
