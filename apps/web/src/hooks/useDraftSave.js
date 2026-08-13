// frontend/src/hooks/useDraftSave.js
// Auto-save hook for IntakeForm — persists form state to IndexedDB on every change,
// keyed by client_id (UUID generated at form mount). This prevents data loss when
// Android evicts the background browser tab (common on 2GB RAM devices within 30s).
//
// Keyed by client_id (not user_id) so multiple concurrent drafts are safe.
// Drafts older than 24h are ignored to prevent stale data from silently restoring.
// Shares the vitalnet_offline DB (v2) with the submission queue — same IndexedDB connection.

import { getOfflineDB } from '../lib/offlineDB'

const STORE = 'form-drafts'

const DRAFT_TTL_MS = 24 * 60 * 60 * 1000   // 24 hours

/**
 * Hook exposing per-draft save/load/clear tied to a specific owner id (the
 * authenticated worker's profile id). All three operations no-op when
 * ownerId is falsy: on a shared device the profile may not have resolved yet,
 * and a fixed 'anonymous' key would let two different workers read/write the
 * SAME draft bucket — leaking one worker's in-progress patient data to the
 * next. No stable owner ⇒ no draft persistence, rather than a shared bucket.
 * @param {string|null} ownerId — the authenticated worker's profile id
 */
export function useDraftSave(ownerId) {
  const key = ownerId ? `draft-${ownerId}` : null

  /**
   * Load a saved draft. Returns null if no owner, no draft, or draft is >24h old.
   */
  async function loadDraft() {
    if (!key) return null
    const db = await getOfflineDB()
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
    if (!key) return
    const db = await getOfflineDB()
    await db.put(STORE, { formData, savedAt: Date.now() }, key)
  }

  /**
   * Clear the draft. Call only after successful queue push or submission —
   * NOT after a failed attempt, so the draft survives transient errors.
   */
  async function clearDraft() {
    if (!key) return
    const db = await getOfflineDB()
    await db.delete(STORE, key)
  }

  return { loadDraft, saveDraft, clearDraft }
}

/**
 * Purge all drafts older than 24h. Call at app startup to prevent IndexedDB bloat.
 */
export async function purgeExpiredDrafts() {
  const db = await getOfflineDB()
  const keys = await db.getAllKeys(STORE)
  const now = Date.now()
  for (const k of keys) {
    const draft = await db.get(STORE, k)
    if (!draft || now - draft.savedAt >= DRAFT_TTL_MS) {
      await db.delete(STORE, k)
    }
  }
}
