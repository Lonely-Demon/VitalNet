import { useAuth } from '../store/authStore'
import LoginPage from '../pages/LoginPage'

export function RouteGuard({ children, requiredRole = null }) {
  const { session, role, isLoading } = useAuth()

  if (isLoading) {
    return (
      <div className="min-h-screen bg-bg flex items-center justify-center">
        <div className="text-center">
          <div className="w-8 h-8 border-3 border-forest border-t-transparent rounded-full animate-spin mx-auto mb-4" />
          <p className="text-sm text-text3">Loading...</p>
        </div>
      </div>
    )
  }

  if (!session) return <LoginPage />

  if (requiredRole && role !== requiredRole && role !== 'admin') {
    return (
      <div className="min-h-screen bg-bg flex items-center justify-center px-4">
        <div className="bg-surface rounded-xl shadow-card border border-leaf/40 p-8 text-center max-w-sm">
          <div className="text-4xl mb-3">🚫</div>
          <h2 className="text-xl font-bold text-text tracking-tight mb-2 font-display">Access Denied</h2>
          <p className="text-sm text-text2">Your account role does not have access to this view.</p>
        </div>
      </div>
    )
  }

  return children
}
