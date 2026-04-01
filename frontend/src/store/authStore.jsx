/**
 * VitalNet Authentication Store
 * 
 * Security Fixes Applied:
 * - ROOT-COMPLY-004: Session inactivity timeout (15 minutes)
 * - R3-DATA-LIFECYCLE-R3-003: Clear device PHI on logout
 */
import { createContext, useContext, useEffect, useState, useRef, useCallback } from 'react'
import { supabase } from '../lib/supabase'
import { clearAllQueues, setQueueUserId } from '../lib/offlineQueue'

const AuthContext = createContext(null)

// Session inactivity timeout in milliseconds (15 minutes for HIPAA compliance)
const INACTIVITY_TIMEOUT_MS = 15 * 60 * 1000

export function AuthProvider({ children }) {
  const [session,  setSession]  = useState(undefined) // undefined = loading
  const [profile,  setProfile]  = useState(null)
  const inactivityTimer = useRef(null)
  const lastActivity = useRef(Date.now())

  // Reset inactivity timer on user activity
  const resetInactivityTimer = useCallback(() => {
    lastActivity.current = Date.now()
    
    if (inactivityTimer.current) {
      clearTimeout(inactivityTimer.current)
    }
    
    // Only set timer if user is logged in
    if (session) {
      inactivityTimer.current = setTimeout(async () => {
        console.warn('[VitalNet] Session expired due to inactivity (ROOT-COMPLY-004)')
        await handleSignOut()
      }, INACTIVITY_TIMEOUT_MS)
    }
  }, [session])

  // Handle sign out with PHI cleanup
  const handleSignOut = useCallback(async () => {
    try {
      // R3-DATA-LIFECYCLE-R3-003: Clear device-side PHI before logout
      await clearAllQueues()
      console.log('[VitalNet] Device PHI cleared on logout')
    } catch (e) {
      console.error('[VitalNet] Failed to clear PHI queues:', e)
    }
    
    if (inactivityTimer.current) {
      clearTimeout(inactivityTimer.current)
    }
    
    await supabase.auth.signOut()
  }, [])

  useEffect(() => {
    // Load existing session from IndexedDB on mount
    supabase.auth.getSession().then(({ data: { session } }) => {
      setSession(session)
      if (session) {
        fetchProfile(session.user.id)
        setQueueUserId(session.user.id)  // Set encryption context
        resetInactivityTimer()
      }
    })

    // Listen for auth state changes (login, logout, token refresh)
    const { data: { subscription } } = supabase.auth.onAuthStateChange(
      (_event, session) => {
        setSession(session)
        if (session) {
          fetchProfile(session.user.id)
          setQueueUserId(session.user.id)
          resetInactivityTimer()
        } else {
          setProfile(null)
          setQueueUserId(null)
          if (inactivityTimer.current) {
            clearTimeout(inactivityTimer.current)
          }
        }
      }
    )

    // ROOT-COMPLY-004: Track user activity for inactivity timeout
    const activityEvents = ['mousedown', 'keydown', 'touchstart', 'scroll']
    const handleActivity = () => {
      if (session) {
        resetInactivityTimer()
      }
    }
    
    activityEvents.forEach(event => {
      window.addEventListener(event, handleActivity, { passive: true })
    })

    return () => {
      subscription.unsubscribe()
      activityEvents.forEach(event => {
        window.removeEventListener(event, handleActivity)
      })
      if (inactivityTimer.current) {
        clearTimeout(inactivityTimer.current)
      }
    }
  }, [resetInactivityTimer])

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
    signOut:   handleSignOut,  // Use enhanced sign out with PHI cleanup
    // Expose last activity for UI indicators if needed
    getLastActivity: () => lastActivity.current,
  }

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export const useAuth = () => useContext(AuthContext)
