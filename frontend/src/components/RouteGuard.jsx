import { useAuth } from '../store/authStore'
import LoginPage from '../pages/LoginPage'

export function RouteGuard({ children, requiredRole = null }) {
  const { session, role, isLoading } = useAuth()

  if (isLoading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <div className="w-8 h-8 border-3 border-blue-600 border-t-transparent rounded-full animate-spin mx-auto mb-4" />
          <p className="text-sm text-slate-500">Loading...</p>
        </div>
      </div>
    )
  }

  if (!session) return <LoginPage />

  if (requiredRole && role !== requiredRole && role !== 'admin') {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center px-4">
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-8 text-center max-w-sm ring-4 ring-slate-50">
          <div className="text-4xl mb-3">🚫</div>
          <h2 className="text-xl font-bold text-slate-900 tracking-tight mb-2">Access Denied</h2>
          <p className="text-sm text-slate-600">Your account role does not have access to this view.</p>
        </div>
      </div>
    )
  }

  return children
}
