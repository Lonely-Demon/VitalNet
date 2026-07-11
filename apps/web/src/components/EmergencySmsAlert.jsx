// Offline-emergency facility alert — a genuine gap versus VitalNet's
// original design intent (never previously built): when an ASHA worker is
// offline and the locally-computed triage is EMERGENCY, the case sits in
// the sync queue until connectivity returns, which could be hours in a
// low-signal area. This gives the ASHA worker a one-tap way to alert the
// facility over SMS in the meantime — a plain-text workflow ping, not a
// clinical handoff. It deliberately carries no patient name, vitals, or
// diagnosis: SMS is unencrypted and often visible in a shared device's
// default messaging app, so no PHI is put in the message body.
import { useTranslation } from 'react-i18next'

export function EmergencySmsAlert() {
  const { t } = useTranslation()
  const facilityPhone = (typeof window !== 'undefined' && localStorage.getItem('vn_facility_phone')) || ''
  const body = encodeURIComponent(t('intakeForm.result.emergencySmsBody'))
  const smsHref = `sms:${facilityPhone}?body=${body}`

  return (
    <div className="mb-6 p-4 rounded-lg bg-emergency/5 border border-emergency/20 text-left">
      <p className="text-sm font-semibold text-emergency mb-1">{t('intakeForm.result.emergencySmsTitle')}</p>
      <p className="text-xs text-text2 mb-3">{t('intakeForm.result.emergencySmsDescription')}</p>
      {!facilityPhone && (
        <p className="text-xs text-text2 italic mb-2">{t('intakeForm.result.emergencySmsNoNumber')}</p>
      )}
      <a
        href={smsHref}
        className="inline-block bg-emergency text-white px-5 py-2.5 rounded-pill font-medium text-sm shadow-btn hover:shadow-card-hover transition-all active:scale-[0.98]"
      >
        {t('intakeForm.result.emergencySmsButton')}
      </a>
    </div>
  )
}
