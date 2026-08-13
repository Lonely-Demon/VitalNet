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
    await page.waitForTimeout(600)
    await expectNoViolations(page)
  })

  test('ASHA — new case intake form', async ({ page }) => {
    await page.goto('/')
    await loginAs(page, 'asha_worker')
    await page.getByRole('button', { name: 'New Case' }).waitFor({ state: 'visible', timeout: 5000 })
    await page.waitForTimeout(1100)
    await expectNoViolations(page)
  })

  test('ASHA — my submissions', async ({ page }) => {
    await page.goto('/')
    await loginAs(page, 'asha_worker')
    await page.getByRole('button', { name: 'My Submissions' }).click()
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

  test('supervisor — management surface', async ({ page }) => {
    await page.goto('/')
    await loginAs(page, 'supervisor')
    await page.getByRole('button', { name: 'Management' }).click()
    await page.waitForTimeout(400)
    await expectNoViolations(page)
  })

  test('admin — local staff management', async ({ page }) => {
    await page.goto('/')
    await loginAs(page, 'admin')
    await page.getByRole('button', { name: 'Staff Management' }).click()
    await page.waitForTimeout(400)
    await expectNoViolations(page)
  })
})

test.describe('Mobile Navigation & Responsiveness', () => {
  const widths = [320, 375, 390, 640, 768]

  for (const width of widths) {
    test(`compact navbar at ${width}px width`, async ({ page }) => {
      await page.setViewportSize({ width, height: 667 })
      await page.goto('/')
      await loginAs(page, 'supervisor')

      // Document must not overflow horizontally
      const overflow = await page.evaluate(() => {
        return document.documentElement.scrollWidth > document.documentElement.clientWidth
      })
      expect(overflow).toBe(false)

      if (width < 640) {
        // Toggle menu button must be visible
        const toggleBtn = page.locator('button[aria-label="Toggle navigation menu"]')
        await expect(toggleBtn).toBeVisible()

        // Open menu
        await toggleBtn.click()
        await expect(toggleBtn).toHaveAttribute('aria-expanded', 'true')

        // Verify menu contents
        const mobileMenu = page.locator('#vitalnet-mobile-navigation')
        await expect(mobileMenu.getByRole('button', { name: 'Management' })).toBeVisible()
        await expect(mobileMenu.getByRole('button', { name: 'Sign out' })).toBeVisible()

        // Close via Escape key
        await page.keyboard.press('Escape')
        await expect(toggleBtn).toHaveAttribute('aria-expanded', 'false')
      }
    })
  }
})
