// apps/web/src/lib/patientHistoryCache.js
// ADR §49: Offline 14-day Longitudinal Patient Deterioration Cache
// Caches patient visits in IndexedDB v5 store 'patient_history_cache' and calculates
// 7-day severe deterioration offline without requiring active network connectivity.

import { getOfflineDB } from './offlineDB'
import { normalizePatientKey, buildIndicPhoneticSkeleton } from '@vitalnet/clinical-core'

const STORE_NAME = 'patient_history_cache'
export const RETENTION_MS = 14 * 24 * 60 * 60 * 1000 // 14-day sliding retention
export const DETERIORATION_WINDOW_MS = 7 * 24 * 60 * 60 * 1000 // 7-day severe window
export const MAX_CACHED_VISITS_PER_PATIENT = 15

/**
 * Cache or update a patient visit into the local IndexedDB cache.
 * Normalizes patient key, maintains up to 15 visits within the 14-day window,
 * and maintains Indic/Devanagari phonetic skeleton for offline card recovery.
 */
export async function cachePatientVisit(visitData, ownerId = null) {
  const rawKey = visitData.patient_key || visitData.patientKey
  const patientKey = normalizePatientKey(rawKey)
  if (!patientKey) return null

  const db = await getOfflineDB()
  const tx = db.transaction(STORE_NAME, 'readwrite')
  const existing = (await tx.store.get(patientKey)) || {
    patient_key: patientKey,
    owner_id: ownerId,
    patient_name: null,
    phonetic_skeleton: null,
    patient_sex: null,
    patient_age: null,
    visits: [],
    updated_at: new Date().toISOString(),
  }

  const patientName = (visitData.patient_name || visitData.patientName || existing.patient_name || '').trim() || null
  const patientSex = visitData.patient_sex || visitData.patientSex || existing.patient_sex || null
  const patientAge = visitData.patient_age != null ? Number(visitData.patient_age) : existing.patient_age

  const phoneticSkeleton = patientName ? buildIndicPhoneticSkeleton(patientName) : existing.phonetic_skeleton

  // Build visit summary
  const newVisit = {
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

  // Merge visits without duplicates
  const now = Date.now()
  const existingVisits = (existing.visits || []).filter((v) => {
    // Drop expired visits (> 14 days)
    const visitTs = Date.parse(v.created_at)
    if (Number.isFinite(visitTs) && now - visitTs > RETENTION_MS) return false

    // Deduplicate
    if (newVisit.case_id && v.case_id && v.case_id === newVisit.case_id) return false
    if (newVisit.client_id && v.client_id && v.client_id === newVisit.client_id) return false
    return true
  })

  const mergedVisits = [newVisit, ...existingVisits]
    .sort((a, b) => Date.parse(b.created_at) - Date.parse(a.created_at))
    .slice(0, MAX_CACHED_VISITS_PER_PATIENT)

  const updatedRecord = {
    patient_key: patientKey,
    owner_id: ownerId || existing.owner_id || null,
    patient_name: patientName,
    phonetic_skeleton: phoneticSkeleton,
    patient_sex: patientSex,
    patient_age: patientAge,
    visits: mergedVisits,
    updated_at: new Date().toISOString(),
  }

  await tx.store.put(updatedRecord)
  await tx.done

  return updatedRecord
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
  const record = await db.get(STORE_NAME, patientKey)
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
export async function findPatientsByPhonetic(nameQuery) {
  if (!nameQuery || typeof nameQuery !== 'string') return []
  const querySkeleton = buildIndicPhoneticSkeleton(nameQuery)
  if (!querySkeleton) return []

  const db = await getOfflineDB()
  const all = await db.getAll(STORE_NAME)
  return all.filter((p) => p.phonetic_skeleton && p.phonetic_skeleton === querySkeleton)
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
