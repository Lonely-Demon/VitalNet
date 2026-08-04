// One-tap call to India's national ambulance/emergency helpline (108) —
// the "ship now" tier of the ambulance-alert idea: a tel: intent needs no
// account, no partnership, and no registry to maintain, unlike a nearest-
// ambulance dispatch integration (there is no public dispatch API for
// India's 108/GVK EMRI service to call into — docs/DECISIONS.md). Shown
// whenever local or server triage is EMERGENCY, online or offline — a
// phone call works over cellular voice even when data connectivity (and
// therefore the rest of the app) doesn't.
import { useTranslation } from 'react-i18next'

export function AmbulanceCallButton() {
  const { t } = useTranslation()

  return (
    <div className="mb-6 p-4 rounded-lg bg-emergency/5 border border-emergency/20 text-left">
      <p className="text-sm font-semibold text-emergency mb-1">{t('intakeForm.result.ambulanceCallTitle')}</p>
      <p className="text-xs text-text2 mb-3">{t('intakeForm.result.ambulanceCallDescription')}</p>
      <a
        href="tel:108"
        className="inline-block bg-emergency text-white px-5 py-2.5 rounded-pill font-medium text-sm shadow-btn hover:shadow-card-hover transition-all active:scale-[0.98]"
      >
        {t('intakeForm.result.ambulanceCallButton')}
      </a>
    </div>
  )
}
