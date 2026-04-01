import { lazy, Suspense } from 'react'
import { AuthProvider, useAuth } from './store/authStore'
import { RouteGuard } from './components/RouteGuard'
import ToastProvider from './components/ToastProvider'
import { UpdatePrompt } from './components/UpdatePrompt'

// Lazy load panel components
const ASHAPanel = lazy(() => import('./panels/ASHAPanel'))
const DoctorPanel = lazy(() => import('./panels/DoctorPanel'))
const AdminPanel = lazy(() => import('./panels/AdminPanel'))

function AppInner() {
  const { profile, signOut } = useAuth()

  // Deactivated users see an access denied screen, not the app
  if (profile && profile.is_active === false) {
    return (
      <div className="min-h-screen bg-bg flex items-center justify-center">
        <div className="text-center animate-fade-up">
          <p className="text-text font-medium">Account deactivated</p>
          <p className="text-text3 text-sm mt-1">Contact your administrator.</p>
          <button
            onClick={signOut}
            className="mt-4 text-sm text-text2 hover:text-terra transition-colors"
          >
            Sign out
          </button>
        </div>
      </div>
    )
  }

  if (profile?.role === 'admin') {
    return (
      <Suspense fallback={<div className="min-h-screen bg-bg flex items-center justify-center text-text2">Loading...</div>}>
        <AdminPanel />
      </Suspense>
    )
  }
  if (profile?.role === 'doctor') {
    return (
      <Suspense fallback={<div className="min-h-screen bg-bg flex items-center justify-center text-text2">Loading...</div>}>
        <DoctorPanel />
      </Suspense>
    )
  }
  if (profile?.role === 'asha_worker') {
    return (
      <Suspense fallback={<div className="min-h-screen bg-bg flex items-center justify-center text-text2">Loading...</div>}>
        <ASHAPanel />
      </Suspense>
    )
  }
  return null
}

export default function App() {
  return (
    <AuthProvider>
      <ToastProvider>
        <UpdatePrompt />
        <RouteGuard>
          <AppInner />
        </RouteGuard>
      </ToastProvider>
    </AuthProvider>
  )
}
