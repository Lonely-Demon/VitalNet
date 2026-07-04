import { createContext, useContext, useEffect, useState } from 'react'
import { supabase } from '../lib/supabase'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [session,  setSession]  = useState(undefined) // undefined = loading
  const [profile,  setProfile]  = useState(null)

  useEffect(() => {
    // Load existing session from IndexedDB on mount
    supabase.auth.getSession().then(({ data: { session } }) => {
      setSession(session)
      if (session) fetchProfile(session.user.id)
    })

    // Listen for auth state changes (login, logout, token refresh)
    const { data: { subscription } } = supabase.auth.onAuthStateChange(
      (_event, session) => {
        setSession(session)
        if (session) fetchProfile(session.user.id)
        else setProfile(null)
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
      if (data) setProfile(data)
    } catch {
      // Offline or network error — keep existing profile (don't blank the page)
      console.warn('[VitalNet] Profile fetch failed (offline?), keeping cached state')
    }
  }

  const value = {
    session,
    profile,
    role:      session?.user?.app_metadata?.role ?? profile?.role ?? null,
    isLoading: session === undefined,
    signIn:    (email, password) =>
                 supabase.auth.signInWithPassword({ email, password }),
    signOut:   () => supabase.auth.signOut(),
  }

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export const useAuth = () => useContext(AuthContext)
