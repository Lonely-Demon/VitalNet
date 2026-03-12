import { AuthProvider, useAuth } from './store/authStore'
import { RouteGuard } from './components/RouteGuard'
import ASHAPanel   from './panels/ASHAPanel'
import DoctorPanel from './panels/DoctorPanel'
import AdminPanel  from './panels/AdminPanel'

function AppInner() {
  const { profile, signOut } = useAuth()

  // Deactivated users see an access denied screen, not the app
  if (profile && profile.is_active === false) {
    return (
      <div className="min-h-screen bg-slate-50 flex items-center justify-center">
        <div className="text-center">
          <p className="text-slate-700 font-medium">Account deactivated</p>
          <p className="text-slate-400 text-sm mt-1">Contact your administrator.</p>
          <button
            onClick={signOut}
            className="mt-4 text-sm text-slate-500 hover:text-slate-700"
          >
            Sign out
          </button>
        </div>
      </div>
    )
  }

  if (profile?.role === 'admin')       return <AdminPanel />
  if (profile?.role === 'doctor')      return <DoctorPanel />
  if (profile?.role === 'asha_worker') return <ASHAPanel />
  return null
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
