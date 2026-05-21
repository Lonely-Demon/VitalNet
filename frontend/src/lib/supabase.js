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

async function getCryptoKey() {
  let keyHex = localStorage.getItem('vn_session_key')
  if (!keyHex) {
    const array = new Uint8Array(32)
    window.crypto.getRandomValues(array)
    keyHex = Array.from(array, b => b.toString(16).padStart(2, '0')).join('')
    localStorage.setItem('vn_session_key', keyHex)
  }
  const keyData = new Uint8Array(keyHex.match(/.{1,2}/g).map(byte => parseInt(byte, 16)))
  return window.crypto.subtle.importKey(
    'raw',
    keyData,
    { name: 'AES-GCM' },
    false,
    ['encrypt', 'decrypt']
  )
}

async function encryptToken(plaintext) {
  try {
    const key = await getCryptoKey()
    const iv = window.crypto.getRandomValues(new Uint8Array(12))
    const encoder = new TextEncoder()
    const encoded = encoder.encode(plaintext)
    const encrypted = await window.crypto.subtle.encrypt(
      { name: 'AES-GCM', iv },
      key,
      encoded
    )
    const ivHex = Array.from(iv, b => b.toString(16).padStart(2, '0')).join('')
    const dataHex = Array.from(new Uint8Array(encrypted), b => b.toString(16).padStart(2, '0')).join('')
    return JSON.stringify({
      encrypted: true,
      iv: ivHex,
      data: dataHex
    })
  } catch (e) {
    console.error('Encryption failed, falling back to plaintext:', e)
    return plaintext
  }
}

async function decryptToken(storedValue) {
  if (!storedValue) return null
  try {
    if (typeof storedValue !== 'string' || !storedValue.startsWith('{"encrypted":true')) {
      return storedValue
    }
    const parsed = JSON.parse(storedValue)
    if (!parsed.encrypted || !parsed.iv || !parsed.data) {
      return storedValue
    }
    const key = await getCryptoKey()
    const iv = new Uint8Array(parsed.iv.match(/.{1,2}/g).map(byte => parseInt(byte, 16)))
    const encryptedData = new Uint8Array(parsed.data.match(/.{1,2}/g).map(byte => parseInt(byte, 16)))
    const decrypted = await window.crypto.subtle.decrypt(
      { name: 'AES-GCM', iv },
      key,
      encryptedData
    )
    const decoder = new TextDecoder()
    return decoder.decode(decrypted)
  } catch (e) {
    console.error('Decryption failed, returning legacy plaintext or raw stored value:', e)
    return storedValue
  }
}

const idbStorage = {
  async getItem(key) {
    const db = await getTokenDB()
    const rawVal = await db.get(STORE_NAME, key) ?? null
    if (key === 'sb-auth-token' && rawVal) {
      return decryptToken(rawVal)
    }
    return rawVal
  },
  async setItem(key, value) {
    const db = await getTokenDB()
    let valToStore = value
    if (key === 'sb-auth-token' && value) {
      valToStore = await encryptToken(value)
    }
    await db.put(STORE_NAME, valToStore, key)
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
