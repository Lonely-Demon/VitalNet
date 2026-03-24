import { openDB } from 'idb'

const DB_NAME    = 'vitalnet_offline'
const STORE_NAME = 'submission_queue'

async function getQueueDB() {
  return openDB(DB_NAME, 1, {
    upgrade(db) {
      if (!db.objectStoreNames.contains(STORE_NAME)) {
        const store = db.createObjectStore(STORE_NAME, { keyPath: 'client_id' })
        store.createIndex('queued_at', 'queued_at')
      }
    }
  })
}

function notifyQueueChange() {
  window.dispatchEvent(new CustomEvent('offline-queue-changed'))
}

const MAX_QUEUE_SIZE = 50

/** Queue a submission for later sync. No token stored — fresh token fetched at sync time. */
export async function enqueue(clientId, payload) {
  const db = await getQueueDB()

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
  const db = await getQueueDB()
  await db.delete(STORE_NAME, clientId)
  notifyQueueChange()
}

export async function getAllQueued() {
  const db = await getQueueDB()
  return db.getAllFromIndex(STORE_NAME, 'queued_at')
}

export async function getQueueCount() {
  const db = await getQueueDB()
  return db.count(STORE_NAME)
}
