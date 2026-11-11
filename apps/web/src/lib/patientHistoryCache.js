// apps/web/src/lib/patientHistoryCache.js
// ADR §49: Offline 14-day Longitudinal Patient Deterioration Cache
// Caches patient visits in IndexedDB v5 store 'patient_history_cache' and calculates
// 7-day severe deterioration offline without requiring active network connectivity.
// Encrypted with AES-256-GCM using getOwnerOutboxKey for DPDP Act compliance (BUG-47).

import { getOfflineDB } from './offlineDB'
import { getOwnerOutboxKey } from './outbox'
import { normalizePatientKey, buildIndicPhoneticSkeleton } from '@vitalnet/clinical-core'

const STORE_NAME = 'patient_history_cache'
export const RETENTION_MS = 14 * 24 * 60 * 60 * 1000 // 14-day sliding retention
export const DETERIORATION_WINDOW_MS = 7 * 24 * 60 * 60 * 1000 // 7-day severe window
export const MAX_CACHED_VISITS_PER_PATIENT = 15

function buildHistoryAad(ownerId, patientKey) {
  return new TextEncoder().encode(`vn:history:${ownerId || 'anon'}:${patientKey}`)
}

async function encryptHistoryPayload(payload, ownerId, patientKey) {
  const key = await getOwnerOutboxKey(ownerId)
  const iv = crypto.getRandomValues(new Uint8Array(12))
  const aad = buildHistoryAad(ownerId, patientKey)
  const encoded = new TextEncoder().encode(JSON.stringify(payload))
  const ct = await crypto.subtle.encrypt(
    { name: 'AES-GCM', iv, additionalData: aad },
    key,
    encoded
  )
  return {
    _encrypted: true,
    _v: 1,
    iv: Array.from(iv),
    ct: Array.from(new Uint8Array(ct)),
  }
}

async function decryptHistoryPayload(record, ownerId, patientKey) {
  if (!record || !record._encrypted) return record
  try {
    const key = await getOwnerOutboxKey(ownerId)
    const iv = new Uint8Array(record.iv)
    const ct = new Uint8Array(record.ct)
    const aad = buildHistoryAad(ownerId, patientKey)
    const decrypted = await crypto.subtle.decrypt(
      { name: 'AES-GCM', iv, additionalData: aad },
      key,
      ct
    )
    const data = JSON.parse(new TextDecoder().decode(decrypted))
    return { ...record, ...data, _encrypted: false }
  } catch (err) {
    console.warn('[VitalNet] Patient history decryption failed', err)
    return null
  }
}

export async function cachePatientVisit(visitData, ownerId = null) {
  const results = await cachePatientVisits([visitData], ownerId)
  return results && results.length > 0 ? results[0] : null
}

/**
 * BUG-25: Batch patient history IndexedDB transactions during offline sync.
 * REG-07: Decrypt and encrypt payloads outside the IndexedDB transaction to
 * prevent TransactionInactiveError caused by async Web Crypto operations.
 */
export async function cachePatientVisits(visitsList, ownerId = null) {
  if (!Array.isArray(visitsList) || visitsList.length === 0) return []

  const visitsByPatient = new Map()
  for (const v of visitsList) {
    const rawKey = v.patient_key || v.patientKey
    const patientKey = normalizePatientKey(rawKey)
    if (!patientKey) continue
    if (!visitsByPatient.has(patientKey)) visitsByPatient.set(patientKey, [])
    visitsByPatient.get(patientKey).push(v)
  }
  if (visitsByPatient.size === 0) return []

  const db = await getOfflineDB()

  // Stage 1 & 2: Pre-read, Decrypt, Merge, and Pre-Encrypt outside IDB transaction
  const recordsToStore = []
  const updatedRecords = []

  for (const [patientKey, incomingVisits] of visitsByPatient.entries()) {
    const existingRaw = await db.get(STORE_NAME, patientKey)
    const existing = (await decryptHistoryPayload(existingRaw, ownerId, patientKey)) || {
      patient_key: patientKey,
      owner_id: ownerId,
      patient_name: null,
      phonetic_skeleton: null,
      patient_sex: null,
      patient_age: null,
      visits: [],
      updated_at: new Date().toISOString(),
    }

    let patientName = existing.patient_name
    let patientSex = existing.patient_sex
    let patientAge = existing.patient_age

    const newVisits = incomingVisits.map((visitData) => {
      if (visitData.patient_name || visitData.patientName) {
        patientName = (visitData.patient_name || visitData.patientName).trim() || patientName
      }
      if (visitData.patient_sex || visitData.patientSex) {
        patientSex = visitData.patient_sex || visitData.patientSex
      }
      if (visitData.patient_age != null) {
        patientAge = Number(visitData.patient_age)
      }
      return {
        case_id: visitData.id || visitData.case_id || null,
        client_id: visitData.client_id || null,
        created_at: visitData.created_at || visitData.client_submitted_at || new Date().toISOString(),
        chief_complaint: visitData.chief_complaint || visitData.chiefComplaint || 'Consultation',
        triage_level: visitData.triage_level || visitData.triageLevel || 'ROUTINE',
        vitals: {
          bp_systolic: visitData.bp_systolic != null ? Number(visitData.bp_systolic) : null,
          bp_diastolic: visitData.bp_diastolic != null ? Number(visitData.bp_diastolic) : null,
          spo2: visitData.spo2 != null ? Number(visitData.spo2) : null,
          heart_rate: visitData.heart_rate != null ? Number(visitData.heart_rate) : null,
          temperature: visitData.temperature != null ? Number(visitData.temperature) : null,
        },
      }
    })

    const phoneticSkeleton = patientName ? buildIndicPhoneticSkeleton(patientName) : existing.phonetic_skeleton
    const now = Date.now()
    const existingVisits = (existing.visits || []).filter((v) => {
      const visitTs = Date.parse(v.created_at)
      if (Number.isFinite(visitTs) && now - visitTs > RETENTION_MS) return false
      for (const nv of newVisits) {
        if (nv.case_id && v.case_id && v.case_id === nv.case_id) return false
        if (nv.client_id && v.client_id && v.client_id === nv.client_id) return false
      }
      return true
    })

    const mergedVisits = [...newVisits, ...existingVisits]
      .sort((a, b) => Date.parse(b.created_at) - Date.parse(a.created_at))
      .slice(0, MAX_CACHED_VISITS_PER_PATIENT)

    // BUG-47: Encrypt sensitive payload
    const sensitivePayload = {
      patient_name: patientName,
      patient_sex: patientSex,
      patient_age: patientAge,
      visits: mergedVisits,
    }
    const encryptedEnvelope = await encryptHistoryPayload(sensitivePayload, ownerId, patientKey)

    const recordToStore = {
      patient_key: patientKey,
      owner_id: ownerId || existing.owner_id || null,
      phonetic_skeleton: phoneticSkeleton,
      updated_at: new Date().toISOString(),
      ...encryptedEnvelope,
    }

    recordsToStore.push(recordToStore)
    updatedRecords.push({ ...recordToStore, ...sensitivePayload })
  }

  // Stage 3: Synchronous Put inside single IDB transaction (REG-07)
  const tx = db.transaction(STORE_NAME, 'readwrite')
  for (const record of recordsToStore) {
    tx.store.put(record)
  }
  await tx.done

  return updatedRecords
}

/**
 * Retrieve patient history from offline cache and calculate 7-day longitudinal deterioration.
 * Returns { found: boolean, patient_key, cases, offlineDeteriorationAlert, deteriorationVisitCount }
 */
export async function getOfflinePatientHistory(patientKeyInput, ownerId = null, now = Date.now()) {
  const patientKey = normalizePatientKey(patientKeyInput)
  if (!patientKey) {
    return { found: false, cases: [], offlineDeteriorationAlert: false, deteriorationVisitCount: 0 }
  }

  const db = await getOfflineDB()
  const rawRecord = await db.get(STORE_NAME, patientKey)
  if (!rawRecord) {
    return { found: false, patient_key: patientKey, cases: [], offlineDeteriorationAlert: false, deteriorationVisitCount: 0 }
  }

  // BUG-47: Scope queries by ownerId
  if (ownerId && rawRecord.owner_id && rawRecord.owner_id !== ownerId) {
    return { found: false, patient_key: patientKey, cases: [], offlineDeteriorationAlert: false, deteriorationVisitCount: 0 }
  }

  const record = await decryptHistoryPayload(rawRecord, ownerId, patientKey)
  if (!record || !Array.isArray(record.visits) || record.visits.length === 0) {
    return { found: false, patient_key: patientKey, cases: [], offlineDeteriorationAlert: false, deteriorationVisitCount: 0 }
  }

  // Filter valid visits within 14 days
  const validVisits = record.visits.filter((v) => {
    const ts = Date.parse(v.created_at)
    return Number.isFinite(ts) && now - ts <= RETENTION_MS
  })

  // Evaluate 7-day longitudinal deterioration
  const urgentVisitsIn7Days = validVisits.filter((v) => {
    const ts = Date.parse(v.created_at)
    const inWindow = Number.isFinite(ts) && now - ts <= DETERIORATION_WINDOW_MS
    const isSevere = v.triage_level === 'URGENT' || v.triage_level === 'EMERGENCY'
    return inWindow && isSevere
  })

  const deteriorationVisitCount = urgentVisitsIn7Days.length
  const offlineDeteriorationAlert = deteriorationVisitCount >= 1

  return {
    found: true,
    patient_key: patientKey,
    patient_name: record.patient_name,
    patient_sex: record.patient_sex,
    patient_age: record.patient_age,
    cases: validVisits,
    offlineDeteriorationAlert,
    deteriorationVisitCount,
  }
}

/**
 * Offline lost-card recovery: search cached patients by Indic/Devanagari phonetic skeleton.
 */
export async function findPatientsByPhonetic(nameQuery, ownerId = null) {
  if (!nameQuery || typeof nameQuery !== 'string') return []
  const querySkeleton = buildIndicPhoneticSkeleton(nameQuery)
  if (!querySkeleton) return []

  const db = await getOfflineDB()
  const all = await db.getAll(STORE_NAME)
  const matched = all.filter(
    (p) => (!ownerId || !p.owner_id || p.owner_id === ownerId) && p.phonetic_skeleton === querySkeleton
  )
  const results = []
  for (const r of matched) {
    const decrypted = await decryptHistoryPayload(r, ownerId, r.patient_key)
    if (decrypted) results.push(decrypted)
  }
  return results
}

/**
 * Purge expired patient history entries older than 14 days.
 */
export async function purgeExpiredPatientHistory(now = Date.now()) {
  const db = await getOfflineDB()
  const tx = db.transaction(STORE_NAME, 'readwrite')
  const all = await tx.store.getAll()
  let purgedCount = 0

  for (const record of all) {
    const updatedTs = Date.parse(record.updated_at)
    if (Number.isFinite(updatedTs) && now - updatedTs > RETENTION_MS) {
      await tx.store.delete(record.patient_key)
      purgedCount++
    }
  }

  await tx.done
  return purgedCount
}
