// frontend/src/utils/imageCompression.js
// Client-side image compression for patient photo attachments
// (FEATURES_ROADMAP §3.2) — SCAFFOLDING per explicit user decision. This
// utility is vendor-independent and ready to use once a storage backend
// (Supabase Storage vs external) and a retention/consent policy for patient
// photographs are decided. There is deliberately no upload wiring yet —
// see backend/supabase/migrations/phase20_case_attachments.sql.
//
// Resizes to maxDimension and re-encodes as JPEG at the given quality
// BEFORE the image ever touches IndexedDB — a full-resolution photo in the
// offline queue would blow past reasonable storage budgets on a low-end
// device fast, directly counter to the offline-first low-bandwidth design
// center of this app.

export async function compressImage(file, { maxDimension = 1024, quality = 0.6 } = {}) {
  const bitmap = await createImageBitmap(file)
  try {
    const scale = Math.min(1, maxDimension / Math.max(bitmap.width, bitmap.height))
    const width = Math.round(bitmap.width * scale)
    const height = Math.round(bitmap.height * scale)

    const canvas = document.createElement('canvas')
    canvas.width = width
    canvas.height = height
    const ctx = canvas.getContext('2d')
    ctx.drawImage(bitmap, 0, 0, width, height)

    return await new Promise((resolve, reject) => {
      canvas.toBlob(
        (blob) => (blob ? resolve(blob) : reject(new Error('Image compression failed'))),
        'image/jpeg',
        quality
      )
    })
  } finally {
    bitmap.close?.()
  }
}
