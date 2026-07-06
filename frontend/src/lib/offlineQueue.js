import { getOfflineDB } from './offlineDB'

const STORE_NAME = 'submission_queue'

function notifyQueueChange() {
  window.dispatchEvent(new CustomEvent('offline-queue-changed'))
}

const MAX_QUEUE_SIZE = 50

/** Queue a submission for later sync. No token stored — fresh token fetched at sync time. */
export async function enqueue(clientId, payload) {
  const db = await getOfflineDB()

  // Guard: refuse to queue if at capacity
  const count = await db.count(STORE_NAME)
  if (count >= MAX_QUEUE_SIZE) {
    console.warn(`[VitalNet] Offline queue is full (${MAX_QUEUE_SIZE} items). Cannot queue more.`)
    throw new Error(`Offline queue is full (${MAX_QUEUE_SIZE} items). Please sync before submitting more cases.`)
  }

  await db.put(STORE_NAME, {
    client_id:  clientId,
    payload,
    queued_at:  new Date().toISOString(),
  })
  notifyQueueChange()
}

export async function dequeue(clientId) {
  const db = await getOfflineDB()
  await db.delete(STORE_NAME, clientId)
  notifyQueueChange()
}

export async function getAllQueued() {
  const db = await getOfflineDB()
  return db.getAllFromIndex(STORE_NAME, 'queued_at')
}

export async function getQueueCount() {
  const db = await getOfflineDB()
  return db.count(STORE_NAME)
}
