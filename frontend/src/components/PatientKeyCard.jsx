// PatientKeyCard.jsx — Displays a newly-generated patient continuity key
// as both a QR code and human-readable text, so the ASHA worker can hand
// it to the patient (printed, or shown for a photo) for their next visit.
import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import QRCode from 'qrcode'

export function PatientKeyCard({ patientKey }) {
  const { t } = useTranslation()
  const [qrDataUrl, setQrDataUrl] = useState(null)

  useEffect(() => {
    let cancelled = false
    if (!patientKey) return
    QRCode.toDataURL(patientKey, { width: 200, margin: 1 })
      .then(url => { if (!cancelled) setQrDataUrl(url) })
      .catch(() => { if (!cancelled) setQrDataUrl(null) })
    return () => { cancelled = true }
  }, [patientKey])

  if (!patientKey) return null

  return (
    <div className="mb-6 p-4 rounded-lg bg-leaf/10 border border-leaf/30 text-center">
      <p className="text-sm font-semibold text-forest mb-1">{t('intakeForm.result.patientKeyTitle')}</p>
      <p className="text-xs text-text2 mb-3">{t('intakeForm.result.patientKeyDescription')}</p>
      {qrDataUrl && (
        <img
          src={qrDataUrl}
          alt={t('intakeForm.result.patientKeyTitle')}
          width={160}
          height={160}
          className="mx-auto mb-3 rounded-md border border-surface3 bg-white p-2"
        />
      )}
      <p className="text-2xl font-mono font-bold tracking-widest text-text">{patientKey}</p>
    </div>
  )
}
