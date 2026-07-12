import { useTranslation } from 'react-i18next'
import { LogOut } from 'lucide-react'
import { useAuth } from '../store/authStore'

const ROLE_LABELS = {
  asha_worker: 'ASHA Worker',
  doctor:      'Doctor',
  admin:       'Admin',
  supervisor:  'Supervisor',
}

const ROLE_COLORS = {
  asha_worker: 'bg-leaf text-forest',
  doctor:      'bg-sand text-forest',
  admin:       'bg-surface3 text-text',
  supervisor:  'bg-urgent/10 text-urgent',
}

const LANGUAGES = ['en', 'hi', 'ta']

export default function NavBar({ tabs, activeTab, onTabChange }) {
  const { profile, signOut } = useAuth()
  const { t, i18n } = useTranslation()

  return (
    <nav className="sticky top-0 z-10 bg-surface/80 backdrop-blur-md border-b border-leaf/60 shadow-card">
      <div className="max-w-6xl mx-auto px-4 h-14 flex items-center gap-3 sm:gap-6">

        {/* Wordmark — a pulse line, not decoration: the app's actual subject */}
        <span className="flex items-center gap-2 shrink-0">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" className="text-forest" aria-hidden="true">
            <path d="M2 12h4l2-7 3 14 2.5-9 2 6h6.5" />
          </svg>
          <span className="font-display font-bold text-text text-lg tracking-tight">
            VitalNet
          </span>
        </span>

        {/* Tabs — underline indicator, horizontally scrollable so it never
            pushes "Sign out" off-screen on narrow viewports or panels with
            many tabs. */}
        <div className="flex items-stretch gap-1 flex-1 min-w-0 h-full overflow-x-auto [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
          {tabs.map(tab => (
            <button
              key={tab.id}
              onClick={() => onTabChange(tab.id)}
              className={`px-3 text-sm font-medium whitespace-nowrap transition-colors duration-200 border-b-[2.5px] ${
                activeTab === tab.id
                  ? 'text-text border-forest font-semibold'
                  : 'text-text2 border-transparent hover:text-forest'
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {/* User identity */}
        <div className="flex items-center gap-3 shrink-0">
          <select
            value={i18n.language}
            onChange={(e) => i18n.changeLanguage(e.target.value)}
            aria-label={t('common.language')}
            className="text-xs font-mono bg-surface2 border border-leaf/40 rounded-pill px-2 py-1 text-text2 hidden sm:block"
          >
            {LANGUAGES.map((lng) => (
              <option key={lng} value={lng}>{t(`common.languages.${lng}`)}</option>
            ))}
          </select>
          <span className="text-sm text-text2 hidden sm:block font-body">
            {profile?.full_name || profile?.id?.slice(0, 8)}
          </span>
          <span className={`text-xs font-mono px-2 py-0.5 rounded-pill font-medium ${
            ROLE_COLORS[profile?.role] || ROLE_COLORS.admin
          }`}>
            {ROLE_LABELS[profile?.role] || profile?.role}
          </span>
          <button
            onClick={signOut}
            title="Sign out"
            aria-label="Sign out"
            className="flex items-center justify-center w-8 h-8 min-w-[44px] min-h-[44px] sm:min-w-8 sm:min-h-8 rounded-md border border-leaf/40 text-text3 hover:text-terra hover:border-terra/40 transition-colors cursor-pointer"
          >
            <LogOut size={15} aria-hidden="true" />
          </button>
        </div>

      </div>
    </nav>
  )
}
