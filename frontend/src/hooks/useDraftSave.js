// frontend/src/hooks/useDraftSave.js
// Auto-save hook for IntakeForm — persists form state to IndexedDB on every change,
// keyed by client_id (UUID generated at form mount). This prevents data loss when
// Android evicts the background browser tab (common on 2GB RAM devices within 30s).
//
// Keyed by client_id (not user_id) so multiple concurrent drafts are safe.
// Drafts older than 24h are ignored to prevent stale data from silently restoring.
// Shares the vitalnet_offline DB (v2) with the submission queue — same IndexedDB connection.

import { openDB } from 'idb'

const DB_NAME  = 'vitalnet_offline'
const STORE    = 'form-drafts'
const DB_VER   = 2   // bump: adds form-drafts store alongside submission_queue

const DRAFT_TTL_MS = 24 * 60 * 60 * 1000   // 24 hours

async function getDraftDB() {
  return openDB(DB_NAME, DB_VER, {
    upgrade(db, oldVersion) {
      // Create submission_queue if upgrading from nothing (fresh install)
      if (!db.objectStoreNames.contains('submission_queue')) {
        const store = db.createObjectStore('submission_queue', { keyPath: 'client_id' })
        store.createIndex('queued_at', 'queued_at')
      }
      // Create form-drafts store (new in v2)
      if (!db.objectStoreNames.contains(STORE)) {
        db.createObjectStore(STORE)   // manually keyed — key is `draft-{clientId}`
      }
    },
  })
}

/**
 * Hook exposing per-draft save/load/clear tied to a specific clientId.
 * @param {string} clientId — UUID generated at form mount time
 */
export function useDraftSave(clientId) {
  const key = `draft-${clientId}`

  /**
   * Load a saved draft. Returns null if no draft exists or draft is >24h old.
   */
  async function loadDraft() {
    const db = await getDraftDB()
    const draft = await db.get(STORE, key)
    if (draft && Date.now() - draft.savedAt < DRAFT_TTL_MS) {
      return draft.formData
    }
    return null
  }

  /**
   * Save the current form state. Call on every field change (debounced by caller).
   * @param {object} formData — current form values
   */
  async function saveDraft(formData) {
    const db = await getDraftDB()
    await db.put(STORE, { formData, savedAt: Date.now() }, key)
  }

  /**
   * Clear the draft. Call only after successful queue push or submission —
   * NOT after a failed attempt, so the draft survives transient errors.
   */
  async function clearDraft() {
    const db = await getDraftDB()
    await db.delete(STORE, key)
  }

  return { loadDraft, saveDraft, clearDraft }
}

/**
 * List all pending drafts for the "Pending Drafts" UI.
 * Filters out drafts older than 24h.
 * @returns {Promise<Array<{id: string, formData: object, savedAt: number}>>}
 */
export async function getAllPendingDrafts() {
  const db = await getDraftDB()
  const keys = await db.getAllKeys(STORE)
  const drafts = await Promise.all(keys.map(k => db.get(STORE, k)))
  const now = Date.now()
  
  // Combine keys and drafts before filtering so indices stay locked
  const combined = drafts.map((d, i) => ({ key: keys[i], draft: d }))
  
  return combined
    .filter(({ draft }) => draft && now - draft.savedAt < DRAFT_TTL_MS)
    .map(({ key, draft }) => ({
      id: String(key).replace('draft-', ''),
      formData: draft.formData,
      savedAt: draft.savedAt,
    }))
}

/**
 * Purge all drafts older than 24h. Call at app startup to prevent IndexedDB bloat.
 */
export async function purgeExpiredDrafts() {
  const db = await getDraftDB()
  const keys = await db.getAllKeys(STORE)
  const now = Date.now()
  for (const k of keys) {
    const draft = await db.get(STORE, k)
    if (!draft || now - draft.savedAt >= DRAFT_TTL_MS) {
      await db.delete(STORE, k)
    }
  }
}
