// frontend/src/lib/offlineDB.js
// Shared IndexedDB opener for the single 'vitalnet_offline' database used by
// both the offline submission queue (offlineQueue.js) and the form-draft
// autosave (hooks/useDraftSave.js) — one schema definition so the two stay
// in lockstep instead of drifting across two independent upgrade callbacks.

import { openDB } from 'idb'

const DB_NAME = 'vitalnet_offline'
const DB_VERSION = 2

export async function getOfflineDB() {
  return openDB(DB_NAME, DB_VERSION, {
    upgrade(db) {
      // submission_queue (fresh install or upgrading from nothing)
      if (!db.objectStoreNames.contains('submission_queue')) {
        const store = db.createObjectStore('submission_queue', { keyPath: 'client_id' })
        store.createIndex('queued_at', 'queued_at')
      }
      // form-drafts (added in v2)
      if (!db.objectStoreNames.contains('form-drafts')) {
        db.createObjectStore('form-drafts')   // manually keyed — key is `draft-{clientId}`
      }
    },
  })
}
