import { createClient } from '@supabase/supabase-js'
import { openDB } from 'idb'

// IndexedDB store for token persistence (survives memory pressure, PWA-safe)
const DB_NAME    = 'vitalnet_auth'
const STORE_NAME = 'tokens'

async function getTokenDB() {
  return openDB(DB_NAME, 1, {
    upgrade(db) { db.createObjectStore(STORE_NAME) }
  })
}

const idbStorage = {
  async getItem(key) {
    const db = await getTokenDB()
    return db.get(STORE_NAME, key) ?? null
  },
  async setItem(key, value) {
    const db = await getTokenDB()
    await db.put(STORE_NAME, value, key)
  },
  async removeItem(key) {
    const db = await getTokenDB()
    await db.delete(STORE_NAME, key)
  },
}

export const supabase = createClient(
  import.meta.env.VITE_SUPABASE_URL,
  import.meta.env.VITE_SUPABASE_ANON_KEY,
  {
    auth: {
      storage:             idbStorage,   // persist in IndexedDB, not localStorage
      autoRefreshToken:    true,          // silent background refresh
      persistSession:      true,          // survive page reload
      detectSessionInUrl:  false,         // no OAuth redirects
    }
  }
)
