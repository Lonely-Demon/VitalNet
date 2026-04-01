import { createContext, useContext, useEffect, useState } from 'react'
import { clearPersistedAuthStorage, supabase } from '../lib/supabase'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [session,  setSession]  = useState(undefined) // undefined = loading
  const [profile,  setProfile]  = useState(null)
  const [profileFetchFailed, setProfileFetchFailed] = useState(false)

  useEffect(() => {
    // Load existing session from IndexedDB on mount
    supabase.auth.getSession().then(({ data: { session } }) => {
      setSession(session)
      setProfileFetchFailed(false)
      if (session) fetchProfile(session.user.id)
    })

    // Listen for auth state changes (login, logout, token refresh)
    const { data: { subscription } } = supabase.auth.onAuthStateChange(
      (_event, session) => {
        setSession(session)
        setProfileFetchFailed(false)
        if (session) fetchProfile(session.user.id)
        else {
          setProfile(null)
          clearPersistedAuthStorage().catch(() => {})
        }
      }
    )
    return () => subscription.unsubscribe()
  }, [])

  async function fetchProfile(userId) {
    try {
      const { data } = await supabase
        .from('profiles')
        .select('*')
        .eq('id', userId)
        .single()
      if (data) {
        setProfile(data)
        setProfileFetchFailed(false)
      }
    } catch {
      setProfileFetchFailed(true)
    }
  }

  async function signOut() {
    await supabase.auth.signOut()
    await clearPersistedAuthStorage()
    setProfile(null)
    setProfileFetchFailed(false)
  }

  const value = {
    session,
    profile,
    role:      session?.user?.app_metadata?.role ?? profile?.role ?? null,
    isLoading: session === undefined || (Boolean(session) && !profile && !profileFetchFailed),
    hasProfileError: profileFetchFailed,
    signIn:    (email, password) =>
                 supabase.auth.signInWithPassword({ email, password }),
    signOut,
  }

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export const useAuth = () => useContext(AuthContext)
