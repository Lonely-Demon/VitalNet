import { useAuth } from '../store/authStore'

const ROLE_LABELS = {
  asha_worker: 'ASHA Worker',
  doctor:      'Doctor',
  admin:       'Admin',
}

const ROLE_COLORS = {
  asha_worker: 'bg-leaf text-forest',
  doctor:      'bg-sand text-forest',
  admin:       'bg-surface3 text-text',
}

export default function NavBar({ tabs, activeTab, onTabChange }) {
  const { profile, signOut } = useAuth()

  return (
    <nav className="sticky top-0 z-10 bg-surface/80 backdrop-blur-md border-b border-leaf/60 shadow-card">
      <div className="max-w-6xl mx-auto px-4 h-14 flex items-center gap-6">

        {/* Wordmark */}
        <span className="font-display italic text-forest text-lg tracking-tight shrink-0">
          VitalNet
        </span>

        {/* Tab pills */}
        <div className="flex items-center gap-1 flex-1">
          {tabs.map(tab => (
            <button
              key={tab.id}
              onClick={() => onTabChange(tab.id)}
              className={`px-3 py-1.5 rounded-pill text-sm font-medium transition-all duration-200 ${
                activeTab === tab.id
                  ? 'bg-forest text-white shadow-btn'
                  : 'text-text2 hover:text-forest hover:bg-leaf/40'
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {/* User identity */}
        <div className="flex items-center gap-3 shrink-0">
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
            className="text-sm text-text3 hover:text-terra transition-colors"
          >
            Sign out
          </button>
        </div>

      </div>
    </nav>
  )
}
