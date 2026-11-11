// apps/web/src/lib/offlineDB.js
// Shared IndexedDB opener for the single 'vitalnet_offline' database used by
// the unified offline outbox (lib/outbox.js) and the form-draft autosave
// (hooks/useDraftSave.js) — one schema definition so the stores stay in
// lockstep instead of drifting across independent upgrade callbacks.

import { openDB } from 'idb'

const DB_NAME = 'vitalnet_offline'
const DB_VERSION = 5

export const LEGACY_RECOVERY_STATUS = 'recovery_required'
export const LEGACY_RECOVERY_REASON = 'legacy_owner_missing'
export const CORRUPT_KEY_REASON = 'key_unavailable_after_session_loss'

/**
 * Register persistent storage to protect IndexedDB from eviction under disk pressure.
 */
export async function ensurePersistentStorage() {
  if (typeof navigator !== 'undefined' && navigator.storage && navigator.storage.persist) {
    try {
      const persisted = await navigator.storage.persist()
      return persisted
    } catch (err) {
      console.warn('[VitalNet] Storage persistence registration failed', err)
    }
  }
  return false
}

/**
 * Query disk quota and usage health to alert on storage pressure (>= 80%).
 */
export async function getStorageHealth() {
  if (typeof navigator !== 'undefined' && navigator.storage && navigator.storage.estimate) {
    try {
      const estimate = await navigator.storage.estimate()
      const usageBytes = estimate.usage || 0
      const quotaBytes = estimate.quota || 0
      const usageRatio = quotaBytes > 0 ? usageBytes / quotaBytes : 0
      return {
        usageBytes,
        quotaBytes,
        usageRatio,
        highPressure: usageRatio >= 0.80,
      }
    } catch (err) {
      console.warn('[VitalNet] Storage estimate query failed', err)
    }
  }
  return { usageBytes: 0, quotaBytes: 0, usageRatio: 0, highPressure: false }
}

export async function getOfflineDB() {
  // Fire persistent storage registration in background
  if (typeof navigator !== 'undefined' && navigator.storage?.persist) {
    ensurePersistentStorage().catch(() => {})
  }

  return openDB(DB_NAME, DB_VERSION, {
    async upgrade(db, oldVersion, _newVersion, transaction) {
      // BUG-15: ISOLATE ALL SCHEMA CREATIONS SYNCHRONOUSLY FIRST.
      // In W3C IndexedDB, all createObjectStore calls must execute
      // synchronously before any async operations to prevent TransactionInactiveError.
      // form-drafts (added in v2)
      if (!db.objectStoreNames.contains('form-drafts')) {
        db.createObjectStore('form-drafts')   // manually keyed — key is `draft-{ownerId}`
      }

      // outbox (added in v3, Round 6 rebuild plan Phase 5) — a generic
      // event queue replacing the case-submission-only submission_queue.
      if (!db.objectStoreNames.contains('outbox')) {
        const outbox = db.createObjectStore('outbox', { keyPath: 'event_id' })
        outbox.createIndex('created_at', 'created_at')
        outbox.createIndex('status', 'status')
      }

      // device_keystore (added in v5, ADR §47) — stores persistent non-extractable
      // Web CryptoKey objects structured-cloned directly in IndexedDB.
      if (!db.objectStoreNames.contains('device_keystore')) {
        db.createObjectStore('device_keystore', { keyPath: 'key_id' })
      }

      // patient_history_cache (added in v5, ADR §49) — stores 14-day trailing
      // patient visits for offline longitudinal deterioration calculation.
      if (!db.objectStoreNames.contains('patient_history_cache')) {
        db.createObjectStore('patient_history_cache', { keyPath: 'patient_key' })
      }

      // v2 -> v3: migrate any still-queued submission_queue rows into the
      // outbox as explicit recovery records.
      if (oldVersion > 0 && oldVersion < 3 && db.objectStoreNames.contains('submission_queue')) {
        const oldStore = transaction.objectStore('submission_queue')
        const outboxStore = transaction.objectStore('outbox')
        const rows = await oldStore.getAll()
        await Promise.all(rows.map((row) =>
          outboxStore.put({
            event_id: row.client_id,
            owner_id: null,
            type: 'case.submit',
            payload: row.payload,
            created_at: row.queued_at,
            attempts: 0,
            status: LEGACY_RECOVERY_STATUS,
            recovery_reason: LEGACY_RECOVERY_REASON,
            last_error: 'Legacy offline submission requires explicit device recovery.',
          })
        ))
        try {
          db.deleteObjectStore('submission_queue')
        } catch (err) {
          console.warn('[VitalNet] Cleanup of legacy submission_queue deferred', err)
        }
      }
      await transaction.done
    },
  })
}
