import { test, expect } from '@playwright/test'

test.describe('Connectivity & Health Probe (isServerReachable)', () => {
  test('probes the configured backend health endpoint and returns true on HTTP 200', async ({ page }) => {
    let probedUrl = null

    // Intercept health probe to verify URL and return 200 OK
    await page.route('**/api/health', async (route) => {
      probedUrl = route.request().url()
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ status: 'ok' }),
      })
    })

    await page.goto('/')

    const isReachable = await page.evaluate(async () => {
      const { isServerReachable } = await import('/src/lib/connectivity.js')
      return await isServerReachable()
    })

    expect(isReachable).toBe(true)
    expect(probedUrl).not.toBeNull()
    expect(probedUrl).toContain('/api/health')
  })

  test('returns false when backend health probe returns non-OK status (500)', async ({ page }) => {
    await page.route('**/api/health', async (route) => {
      await route.fulfill({
        status: 500,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'Internal Server Error' }),
      })
    })

    await page.goto('/')

    const isReachable = await page.evaluate(async () => {
      const { isServerReachable } = await import('/src/lib/connectivity.js')
      return await isServerReachable()
    })

    expect(isReachable).toBe(false)
  })

  test('returns false when network fetch fails or aborts', async ({ page }) => {
    await page.route('**/api/health', async (route) => {
      await route.abort('failed')
    })

    await page.goto('/')

    const isReachable = await page.evaluate(async () => {
      const { isServerReachable } = await import('/src/lib/connectivity.js')
      return await isServerReachable()
    })

    expect(isReachable).toBe(false)
  })
})
