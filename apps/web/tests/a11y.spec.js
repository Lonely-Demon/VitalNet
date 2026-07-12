// tests/a11y.spec.js
//
// Automated WCAG 2 A/AA accessibility scan (axe-core) of the app's main
// screens across every role. Runs against a mocked backend (tests/helpers/
// mockBackend.js) so it needs no live Supabase project or secrets — safe to
// run on untrusted PR code, same posture as build-frontend-pr in
// .github/workflows/ci.yml. Complements, not replaces, the manual contrast/
// keyboard/screen-reader review in docs/ACCESSIBILITY.md — axe catches
// structural and programmatic issues (missing labels, contrast, ARIA
// misuse); it cannot verify things like "does this make sense read aloud."
import { test, expect } from '@playwright/test'
import AxeBuilder from '@axe-core/playwright'
import { loginAs } from './helpers/mockBackend.js'

async function expectNoViolations(page) {
  const results = await new AxeBuilder({ page })
    .withTags(['wcag2a', 'wcag2aa'])
    .analyze()
  const summary = results.violations.map((v) => (
    `${v.id} (${v.impact}): ${v.help} — ${v.nodes.length} node(s)\n` +
    v.nodes.slice(0, 3).map((n) => `  ${n.target.join(' ')}`).join('\n')
  )).join('\n\n')
  expect(results.violations, summary).toEqual([])
}

test.describe('Accessibility — WCAG 2 A/AA (axe-core)', () => {
  test('login page', async ({ page }) => {
    await page.goto('/')
    await page.locator('input[type="email"]').waitFor({ state: 'visible', timeout: 5000 })
    // The page wrapper has a 0.5s animate-fade-up entrance transition;
    // Playwright's "visible" only means non-zero size, not opacity:1, so
    // scanning immediately catches axe mid-fade and reports a false-positive
    // contrast violation on the blended (partially transparent) text.
    await page.waitForTimeout(600)
    await expectNoViolations(page)
  })

  test('ASHA — new case intake form', async ({ page }) => {
    await page.goto('/')
    await loginAs(page, 'asha_worker')
    await page.locator('text=New Case').waitFor({ state: 'visible', timeout: 5000 })
    // The symptom checklist staggers each option's entrance animation by
    // idx*40ms (12 options => last one settles ~440ms + 500ms duration
    // after mount) — wait long enough to clear it, same false-positive
    // class as the login page's fade-in (see comment there).
    await page.waitForTimeout(1100)
    await expectNoViolations(page)
  })

  test('ASHA — my submissions', async ({ page }) => {
    await page.goto('/')
    await loginAs(page, 'asha_worker')
    await page.click('text=My Submissions')
    await page.waitForTimeout(400)
    await expectNoViolations(page)
  })

  test('doctor — pending review queue', async ({ page }) => {
    await page.goto('/')
    await loginAs(page, 'doctor')
    await page.waitForTimeout(400)
    await expectNoViolations(page)
  })

  test('supervisor — team metrics', async ({ page }) => {
    await page.goto('/')
    await loginAs(page, 'supervisor')
    await page.waitForTimeout(400)
    await expectNoViolations(page)
  })

  test('admin — analytics', async ({ page }) => {
    await page.goto('/')
    await loginAs(page, 'admin')
    await page.waitForTimeout(400)
    await expectNoViolations(page)
  })

  test('admin — users table', async ({ page }) => {
    await page.goto('/')
    await loginAs(page, 'admin')
    await page.click('text=Users')
    await page.waitForTimeout(400)
    await expectNoViolations(page)
  })
})
