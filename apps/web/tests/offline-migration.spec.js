import { test, expect } from '@playwright/test'
import { mockAuthAndData } from './helpers/mockBackend.js'

const DB_NAME = 'vitalnet_offline'

async function seedLegacyDatabase(page) {
  await page.evaluate(() => new Promise((resolve, reject) => {
    const request = indexedDB.deleteDatabase('vitalnet_offline')
    request.onsuccess = () => resolve()
    request.onerror = () => reject(request.error)
    request.onblocked = () => reject(new Error('legacy database deletion was blocked'))
  }))

  await page.evaluate(() => new Promise((resolve, reject) => {
    const request = indexedDB.open('vitalnet_offline', 2)
    request.onupgradeneeded = () => {
      const db = request.result
      db.createObjectStore('form-drafts')
      const queue = db.createObjectStore('submission_queue', { keyPath: 'client_id' })
      queue.put({
        client_id: 'legacy-event-1',
        payload: { patient_name: 'Synthetic Legacy Patient', chief_complaint: 'Synthetic complaint' },
        queued_at: '2026-08-22T00:00:00.000Z',
      })
    }
    request.onsuccess = () => {
      request.result.close()
      resolve()
    }
    request.onerror = () => reject(request.error)
  }))
}

async function readOutbox(page) {
  return page.evaluate((dbName) => new Promise((resolve, reject) => {
    const request = indexedDB.open(dbName)
    request.onsuccess = () => {
      const db = request.result
      const read = db.transaction('outbox', 'readonly').objectStore('outbox').getAll()
      read.onsuccess = () => {
        db.close()
        resolve(read.result)
      }
      read.onerror = () => reject(read.error)
    }
    request.onerror = () => reject(request.error)
  }), DB_NAME)
}

test.describe('legacy offline queue recovery', () => {
  test.beforeEach(async ({ page }) => {
    await mockAuthAndData(page, { role: 'asha_worker' })
    // Seed from a separate same-origin fixture page so the application page
    // has not opened IndexedDB v4 before the legacy v2 database is created.
    const fixturePage = await page.context().newPage()
    await fixturePage.goto('http://localhost:5173/favicon.ico', { waitUntil: 'commit' }).catch(() => {})
    await seedLegacyDatabase(fixturePage)
    await fixturePage.close()
    await page.goto('http://localhost:5173/')
    await page.waitForLoadState('networkidle')

    const emailInput = page.locator('input[type="email"]')
    try {
      await emailInput.waitFor({ state: 'visible', timeout: 3000 })
      await emailInput.fill('asha@test.vitalnet')
      await page.fill('input[type="password"]', 'whatever-mocked')
      await page.click('button[type="submit"]')
    } catch {
      // The synthetic session may already be active.
    }

    await expect(page.getByRole('button', { name: 'New Case', exact: true })).toBeVisible({ timeout: 10000 })
  })

  test('migrates ownerless legacy rows into explicit recovery state', async ({ page }) => {
    const rows = await readOutbox(page)
    expect(rows).toHaveLength(1)
    expect(rows[0]).toMatchObject({
      event_id: 'legacy-event-1',
      owner_id: null,
      status: 'recovery_required',
      recovery_reason: 'legacy_owner_missing',
    })
    expect(rows[0].payload.patient_name).toBe('Synthetic Legacy Patient')
    await expect(page.getByText(/legacy offline submission.*require device cleanup/i)).toBeVisible()
    await expect(page.getByText('Synthetic Legacy Patient')).toHaveCount(0)
  })

  test('purges only recovery rows after explicit confirmation', async ({ page }) => {
    await page.evaluate((dbName) => new Promise((resolve, reject) => {
      const request = indexedDB.open(dbName)
      request.onsuccess = () => {
        const db = request.result
        const tx = db.transaction('outbox', 'readwrite')
        tx.objectStore('outbox').put({
          event_id: 'owned-pending',
          owner_id: 'synthetic-owner',
          type: 'case.submit',
          payload: { patient_name: 'Synthetic Pending Patient' },
          created_at: '2026-08-22T00:01:00.000Z',
          attempts: 0,
          status: 'pending',
          last_error: null,
        })
        tx.objectStore('outbox').put({
          event_id: 'owned-dead',
          owner_id: 'synthetic-owner',
          type: 'case.submit',
          payload: { patient_name: 'Synthetic Dead Patient' },
          created_at: '2026-08-22T00:02:00.000Z',
          attempts: 1,
          status: 'dead',
          last_error: 'Synthetic failure',
        })
        tx.oncomplete = () => {
          db.close()
          resolve()
        }
        tx.onerror = () => reject(tx.error)
      }
      request.onerror = () => reject(request.error)
    }), DB_NAME)

    page.once('dialog', (dialog) => dialog.accept())
    await page.getByRole('button', { name: 'Clear legacy data' }).click()
    await page.waitForTimeout(250)

    const rows = await readOutbox(page)
    expect(rows.map((row) => row.event_id).sort()).toEqual(['owned-dead', 'owned-pending'])

    await page.reload()
    await page.waitForLoadState('networkidle')
    await expect(page.getByText(/legacy offline submission.*require device cleanup/i)).toHaveCount(0)
  })
})
