// frontend/src/lib/offlineDB.js
// Shared IndexedDB opener for the single 'vitalnet_offline' database used by
// the unified offline outbox (lib/outbox.js) and the form-draft autosave
// (hooks/useDraftSave.js) — one schema definition so the stores stay in
// lockstep instead of drifting across independent upgrade callbacks.

import { openDB } from 'idb'

const DB_NAME = 'vitalnet_offline'
const DB_VERSION = 3

export async function getOfflineDB() {
  return openDB(DB_NAME, DB_VERSION, {
    async upgrade(db, oldVersion, _newVersion, transaction) {
      // form-drafts (added in v2)
      if (!db.objectStoreNames.contains('form-drafts')) {
        db.createObjectStore('form-drafts')   // manually keyed — key is `draft-{clientId}`
      }

      // outbox (added in v3, Round 6 rebuild plan Phase 5) — a generic
      // event queue replacing the case-submission-only submission_queue.
      // Every queued action becomes { event_id, type, payload, created_at,
      // attempts, status, last_error }; event_id doubles as the server-side
      // idempotency key (apps/api's client_events table, and — for
      // type:'case.submit' specifically — case_records.client_id).
      if (!db.objectStoreNames.contains('outbox')) {
        const outbox = db.createObjectStore('outbox', { keyPath: 'event_id' })
        outbox.createIndex('created_at', 'created_at')
        outbox.createIndex('status', 'status')
      }

      // v2 -> v3: migrate any still-queued submission_queue rows into the
      // outbox as type:'case.submit' events, then retire the old store.
      // Only runs when upgrading FROM a version that actually had
      // submission_queue (oldVersion < 3) — a fresh install goes straight
      // to the outbox-only schema above with nothing to migrate.
      if (oldVersion > 0 && oldVersion < 3 && db.objectStoreNames.contains('submission_queue')) {
        const oldStore = transaction.objectStore('submission_queue')
        const outboxStore = transaction.objectStore('outbox')
        const rows = await oldStore.getAll()
        for (const row of rows) {
          await outboxStore.put({
            event_id: row.client_id,
            type: 'case.submit',
            payload: row.payload,
            created_at: row.queued_at,
            attempts: 0,
            status: 'pending',
            last_error: null,
          })
        }
        db.deleteObjectStore('submission_queue')
      }
    },
  })
}
