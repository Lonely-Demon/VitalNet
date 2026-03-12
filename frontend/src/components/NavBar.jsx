import { useAuth } from '../store/authStore'

const ROLE_LABELS = {
  asha_worker: 'ASHA Worker',
  doctor:      'Doctor',
  admin:       'Admin',
}

const ROLE_COLORS = {
  asha_worker: 'bg-emerald-100 text-emerald-800',
  doctor:      'bg-blue-100 text-blue-800',
  admin:       'bg-slate-100 text-slate-700',
}

export default function NavBar({ tabs, activeTab, onTabChange }) {
  const { profile, signOut } = useAuth()

  return (
    <nav className="sticky top-0 z-10 bg-white border-b border-slate-200 shadow-sm">
      <div className="max-w-6xl mx-auto px-4 h-14 flex items-center gap-6">

        {/* Wordmark */}
        <span className="font-semibold text-slate-800 text-sm tracking-tight shrink-0">
          VitalNet
        </span>

        {/* Tab pills */}
        <div className="flex items-center gap-1 flex-1">
          {tabs.map(tab => (
            <button
              key={tab.id}
              onClick={() => onTabChange(tab.id)}
              className={`px-3 py-1.5 rounded-md text-sm font-medium transition-colors ${
                activeTab === tab.id
                  ? 'bg-slate-100 text-slate-900'
                  : 'text-slate-500 hover:text-slate-700 hover:bg-slate-50'
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {/* User identity */}
        <div className="flex items-center gap-3 shrink-0">
          <span className="text-sm text-slate-600 hidden sm:block">
            {profile?.full_name || profile?.id?.slice(0, 8)}
          </span>
          <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${
            ROLE_COLORS[profile?.role] || ROLE_COLORS.admin
          }`}>
            {ROLE_LABELS[profile?.role] || profile?.role}
          </span>
          <button
            onClick={signOut}
            className="text-sm text-slate-400 hover:text-slate-600 transition-colors"
          >
            Sign out
          </button>
        </div>

      </div>
    </nav>
  )
}
