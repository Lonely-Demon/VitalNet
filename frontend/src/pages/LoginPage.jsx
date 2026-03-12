import { useState } from 'react'
import { useAuth } from '../store/authStore'

export default function LoginPage() {
  const { signIn } = useAuth()
  const [email, setEmail]       = useState('')
  const [password, setPassword] = useState('')
  const [loading, setLoading]   = useState(false)
  const [error, setError]       = useState(null)

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError(null)
    setLoading(true)

    const { error: authError } = await signIn(email, password)

    if (authError) {
      setError(authError.message)
      setLoading(false)
    }
    // On success, onAuthStateChange in authStore fires automatically — no manual nav
  }

  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center px-4">
      <div className="w-full max-w-sm">
        {/* Brand */}
        <div className="text-center mb-8">
          <h1 className="text-3xl font-bold text-slate-900 tracking-tight">VitalNet</h1>
          <p className="text-sm text-slate-500 mt-2">Clinical Triage Platform</p>
        </div>

        {/* Login Card */}
        <form
          onSubmit={handleSubmit}
          className="bg-white rounded-xl shadow-sm border border-gray-200 p-8 ring-4 ring-slate-50"
        >
          <h2 className="text-lg font-bold text-slate-800 tracking-tight mb-6 text-center">Sign In</h2>

          {error && (
            <div className="bg-red-50 border border-red-300 text-red-700 px-4 py-3 rounded-lg mb-5 text-sm">
              {error}
            </div>
          )}

          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-2 ml-1">Email</label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@example.com"
                required
                className="w-full border border-gray-200 rounded-lg px-4 py-3 text-sm text-slate-800 shadow-sm transition-all duration-200 outline-none focus:ring-2 focus:ring-blue-100 focus:border-blue-500 hover:border-blue-400 bg-white"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-slate-700 mb-2 ml-1">Password</label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                required
                className="w-full border border-gray-200 rounded-lg px-4 py-3 text-sm text-slate-800 shadow-sm transition-all duration-200 outline-none focus:ring-2 focus:ring-blue-100 focus:border-blue-500 hover:border-blue-400 bg-white"
              />
            </div>
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full bg-blue-700 text-white py-3 rounded-xl font-bold text-sm mt-6 shadow-sm hover:shadow-md disabled:opacity-75 disabled:cursor-wait transition-all duration-200 active:bg-blue-800 focus:ring-4 focus:ring-blue-100 cursor-pointer"
          >
            {loading ? <span className="animate-pulse">Signing in...</span> : 'Sign In'}
          </button>
        </form>

        <p className="text-xs text-slate-400 text-center mt-6">
          For authorised healthcare workers only
        </p>
      </div>
    </div>
  )
}
