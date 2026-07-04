import { lazy, Suspense, useEffect } from 'react'
import { AuthProvider, useAuth } from './store/authStore'
import { RouteGuard } from './components/RouteGuard'
import ToastProvider from './components/ToastProvider'
import { UpdatePrompt } from './components/UpdatePrompt'
import ErrorBoundary from './components/ErrorBoundary'
import { purgeExpiredDrafts } from './hooks/useDraftSave'

// Lazy-loaded per role — a given user only ever renders ONE of these three
// panels (their own role), so bundling all three into the main chunk makes
// every user download and parse code paths (e.g. AdminUsers, AnalyticsDashboard)
// they will never use. This matters on the low-end Android tablets ASHA
// workers use in the field: smaller main bundle = faster first interactive
// paint, especially over rural 2G/3G connections.
const ASHAPanel   = lazy(() => import('./panels/ASHAPanel'))
const DoctorPanel = lazy(() => import('./panels/DoctorPanel'))
const AdminPanel  = lazy(() => import('./panels/AdminPanel'))

function PanelLoadingFallback() {
  return (
    <div className="min-h-screen bg-bg flex items-center justify-center">
      <div className="w-8 h-8 border-3 border-forest border-t-transparent rounded-full animate-spin" />
    </div>
  )
}

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

  return (
    <Suspense fallback={<PanelLoadingFallback />}>
      {profile?.role === 'admin'       && <AdminPanel />}
      {profile?.role === 'doctor'      && <DoctorPanel />}
      {profile?.role === 'asha_worker' && <ASHAPanel />}
    </Suspense>
  )
}

export default function App() {
  useEffect(() => {
    purgeExpiredDrafts().catch((err) => console.error('Failed to purge expired drafts:', err))
  }, [])

  return (
    <ErrorBoundary>
      <AuthProvider>
        <ToastProvider>
          <UpdatePrompt />
          <RouteGuard>
            <AppInner />
          </RouteGuard>
        </ToastProvider>
      </AuthProvider>
    </ErrorBoundary>
  )
}
