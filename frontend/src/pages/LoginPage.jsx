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
    <div className="min-h-screen bg-bg flex items-center justify-center px-4">
      <div className="w-full max-w-sm animate-fade-up">
        {/* Brand */}
        <div className="text-center mb-8">
          <h1 className="font-display italic text-4xl text-forest tracking-tight animate-shimmer">VitalNet</h1>
          <p className="text-sm text-text2 mt-2 font-body">Clinical Triage Platform</p>
        </div>

        {/* Login Card */}
        <form
          onSubmit={handleSubmit}
          className="bg-surface rounded-xl shadow-card border border-leaf/40 p-8 hover:shadow-card-hover transition-shadow duration-300"
        >
          <h2 className="text-lg font-bold text-text tracking-tight mb-6 text-center font-body">Sign In</h2>

          {error && (
            <div className="bg-emergency/10 border border-emergency/30 text-emergency px-4 py-3 rounded-md mb-5 text-sm">
              {error}
            </div>
          )}

          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-text2 mb-2 ml-1 font-mono text-xs uppercase tracking-wider">Email</label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@example.com"
                required
                className="w-full border border-surface3 rounded-md px-4 py-3 text-sm text-text bg-surface2 shadow-sm transition-all duration-200 outline-none focus:ring-2 focus:ring-leaf focus:border-sage hover:border-sage"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-text2 mb-2 ml-1 font-mono text-xs uppercase tracking-wider">Password</label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                required
                className="w-full border border-surface3 rounded-md px-4 py-3 text-sm text-text bg-surface2 shadow-sm transition-all duration-200 outline-none focus:ring-2 focus:ring-leaf focus:border-sage hover:border-sage"
              />
            </div>
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full bg-forest text-white py-3 rounded-pill font-bold text-sm mt-6 shadow-btn hover:shadow-card-hover disabled:opacity-75 disabled:cursor-wait transition-all duration-200 active:scale-[0.98] cursor-pointer"
          >
            {loading ? <span className="animate-pulse">Signing in...</span> : 'Sign In'}
          </button>
        </form>

        <p className="text-xs text-text3 text-center mt-6 font-mono">
          For authorised healthcare workers only
        </p>
      </div>
    </div>
  )
}
