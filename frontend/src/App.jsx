import { AuthProvider, useAuth } from './store/authStore'
import { RouteGuard } from './components/RouteGuard'
import IntakeForm from './pages/IntakeForm'
import Dashboard from './pages/Dashboard'

function AppInner() {
  const { role, signOut, profile } = useAuth()

  // Role-based view selection
  const content = (() => {
    if (role === 'doctor' || role === 'admin') return <Dashboard />
    if (role === 'asha_worker') return <IntakeForm />
    return null // RouteGuard handles unauthenticated state
  })()

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Navigation */}
      <nav className="bg-blue-700 text-white px-4 py-3 flex items-center justify-between">
        <div className="flex gap-3 items-center">
          <span className="font-bold text-lg tracking-tight">VitalNet</span>
          {role && (
            <span className="text-xs text-blue-200 bg-blue-800/40 px-2.5 py-1 rounded-full capitalize">
              {profile?.full_name || role.replace('_', ' ')}
            </span>
          )}
        </div>
        <button
          onClick={signOut}
          className="text-sm text-slate-300 hover:text-white transition-colors cursor-pointer"
        >
          Sign out
        </button>
      </nav>

      {content}
    </div>
  )
}

export default function App() {
  return (
    <AuthProvider>
      <RouteGuard>
        <AppInner />
      </RouteGuard>
    </AuthProvider>
  )
}
