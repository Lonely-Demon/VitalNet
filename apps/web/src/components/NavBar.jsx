import { useState, useRef, useEffect } from 'react'
import { useTranslation } from 'react-i18next'
import { LogOut, Menu, X } from 'lucide-react'
import { useAuth } from '../store/authStore'
import { localeReviewManifest } from '../i18n'

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
  supervisor:  'bg-urgent/10 text-urgent-ink',
}

const LANGUAGES = ['en', 'hi', 'ta']

export default function NavBar({ tabs = [], activeTab, onTabChange }) {
  const { profile, signOut } = useAuth()
  const { t, i18n } = useTranslation()
  const [menuOpen, setMenuOpen] = useState(false)
  const menuButtonRef = useRef(null)

  const activeTabObj = tabs.find(t => t.id === activeTab) || tabs[0]
  const localeMeta = localeReviewManifest.locales[i18n.language] || localeReviewManifest.locales.en
  const localeReviewLabel = localeMeta.pilotApproved ? 'Reviewed' : localeMeta.status === 'source' ? 'Source' : 'Draft — review needed'

  useEffect(() => {
    function handleKeyDown(e) {
      if (e.key === 'Escape' && menuOpen) {
        setMenuOpen(false)
        menuButtonRef.current?.focus()
      }
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [menuOpen])

  return (
    <nav className="sticky top-0 z-20 bg-surface/90 backdrop-blur-md border-b border-leaf/60 shadow-card">
      <div className="max-w-6xl mx-auto px-4 h-14 flex items-center justify-between gap-3">

        {/* Brand Wordmark */}
        <span className="flex items-center gap-2 shrink-0">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" className="text-forest" aria-hidden="true">
            <path d="M2 12h4l2-7 3 14 2.5-9 2 6h6.5" />
          </svg>
          <span className="font-display font-bold text-text text-lg tracking-tight">
            VitalNet
          </span>
        </span>

        {/* Desktop Navigation Tabs (sm+) */}
        <div className="hidden sm:flex items-stretch gap-1 flex-1 min-w-0 h-full overflow-x-auto [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
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

        {/* Desktop User Identity & Controls (sm+) */}
        <div className="hidden sm:flex items-center gap-3 shrink-0">
          <select
            value={i18n.language}
            onChange={(e) => i18n.changeLanguage(e.target.value)}
            aria-label={t('common.language')}
            className="text-xs font-mono bg-surface2 border border-leaf/40 rounded-pill px-2 py-1 text-text2"
          >
            {LANGUAGES.map((lng) => (
              <option key={lng} value={lng}>{t(`common.languages.${lng}`)}</option>
            ))}
          </select>
          <span
            className="text-[10px] font-mono text-text3 border border-leaf/40 rounded-pill px-2 py-1"
            title={localeMeta.reviewStatus}
            aria-label={`Language review status: ${localeReviewLabel}`}
          >
            {localeReviewLabel}
          </span>
          <span className="text-sm text-text2 font-body">
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

        {/* Mobile View: Active tab indicator & Compact menu trigger button */}
        <div className="flex sm:hidden items-center gap-2 shrink-0">
          {activeTabObj && (
            <span className="text-xs font-medium text-forest bg-leaf/40 px-2.5 py-1 rounded-pill font-body truncate max-w-[130px]">
              {activeTabObj.label}
            </span>
          )}
          <button
            ref={menuButtonRef}
            onClick={() => setMenuOpen(v => !v)}
            aria-expanded={menuOpen}
            aria-controls="vitalnet-mobile-navigation"
            aria-label="Toggle navigation menu"
            className="flex items-center justify-center w-11 h-11 min-w-[44px] min-h-[44px] rounded-md border border-leaf/60 text-text hover:text-forest bg-surface2 transition-colors cursor-pointer"
          >
            {menuOpen ? <X size={20} aria-hidden="true" /> : <Menu size={20} aria-hidden="true" />}
          </button>
        </div>
      </div>

      {/* Mobile Compact Dropdown Menu Overlay */}
      {menuOpen && (
        <div id="vitalnet-mobile-navigation" className="sm:hidden border-t border-leaf/40 bg-surface px-4 py-4 space-y-4 shadow-lg animate-fade-down">
          {/* Identity & Role Badge */}
          <div className="flex items-center justify-between pb-3 border-b border-leaf/20">
            <div>
              <p className="text-sm font-semibold text-text font-body">
                {profile?.full_name || profile?.id?.slice(0, 8)}
              </p>
              <p className="text-xs text-text3 font-mono">{profile?.email}</p>
            </div>
            <span className={`text-xs font-mono px-2 py-0.5 rounded-pill font-medium ${
              ROLE_COLORS[profile?.role] || ROLE_COLORS.admin
            }`}>
              {ROLE_LABELS[profile?.role] || profile?.role}
            </span>
          </div>

          {/* Role Navigation Tabs */}
          <div className="space-y-1">
            <p className="text-[11px] font-mono font-semibold uppercase text-text3 tracking-wider mb-1">
              Navigation
            </p>
            {tabs.map(tab => (
              <button
                key={tab.id}
                onClick={() => {
                  onTabChange(tab.id)
                  setMenuOpen(false)
                }}
                className={`w-full text-left px-3 py-2.5 rounded-md text-sm font-medium transition-colors ${
                  activeTab === tab.id
                    ? 'bg-forest/10 text-forest font-semibold border-l-4 border-forest'
                    : 'text-text2 hover:bg-surface2 hover:text-text'
                }`}
              >
                {tab.label}
              </button>
            ))}
          </div>

          {/* Language & Actions */}
          <div className="pt-3 border-t border-leaf/20 flex items-center justify-between gap-3">
            <div className="flex items-center gap-2">
              <span className="text-xs text-text3 font-mono">Language:</span>
              <select
                value={i18n.language}
                onChange={(e) => i18n.changeLanguage(e.target.value)}
                aria-label={t('common.language')}
                className="text-xs font-mono bg-surface2 border border-leaf/40 rounded-pill px-2.5 py-1 text-text"
              >
                {LANGUAGES.map((lng) => (
                  <option key={lng} value={lng}>{t(`common.languages.${lng}`)}</option>
                ))}
              </select>
              <span className="text-[10px] font-mono text-text3" title={localeMeta.reviewStatus}>
                {localeReviewLabel}
              </span>
            </div>

            <button
              onClick={() => {
                setMenuOpen(false)
                signOut()
              }}
              className="flex items-center gap-2 text-xs font-medium text-terra bg-terra/10 border border-terra/30 px-3 py-2 rounded-md hover:bg-terra/20 transition-colors min-h-[44px]"
            >
              <LogOut size={14} aria-hidden="true" />
              Sign out
            </button>
          </div>
        </div>
      )}
    </nav>
  )
}
