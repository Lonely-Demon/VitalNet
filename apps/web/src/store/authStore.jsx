import { createContext, useContext, useEffect, useState } from 'react'
import { supabase } from '../lib/supabase'
import { getOfflineDB } from '../lib/offlineDB'

const AuthContext = createContext(null)

// Shared-device teardown on logout. The PHC tablets are handed between ASHA
// workers, so ending a session must not leave the previous worker's data
// readable by the next one:
//   - form-drafts: in-progress (unsubmitted) intake forms — partial patient
//     PHI. Cleared. A draft is not a committed case, so this is safe to drop.
//   - vn_facility_phone: the previous worker's cached facility contact.
// The offline OUTBOX is deliberately NOT cleared here: it is owner-scoped
// (lib/outbox.js), so another worker can neither drain nor view its rows, and
// wiping it would break the offline-first guarantee that a queued case
// survives until it can sync. vn_device_id is a browser-stable anti-replay
// identifier (not user data) and is intentionally left in place.
async function clearSharedDeviceState() {
  try {
    localStorage.removeItem('vn_facility_phone')
  } catch { /* localStorage unavailable — nothing to clear */ }
  try {
    const db = await getOfflineDB()
    await db.clear('form-drafts')
  } catch (e) {
    console.warn('[VitalNet] Could not clear local drafts on logout', e)
  }
}

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
        .select('*, facilities(phone, capacity_status)')
        .eq('id', userId)
        .single()
      if (data) {
        setProfile(data)
        // Cached to localStorage (not just React state) so the facility
        // contact number survives an offline reload — the offline-emergency
        // SMS alert (IntakeForm.jsx) needs it precisely when there's no
        // network to re-fetch it.
        const phone = data.facilities?.phone
        if (phone) localStorage.setItem('vn_facility_phone', phone)
      }
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
    signOut:   async () => {
      // Tear down device-local PHI before ending the session (see
      // clearSharedDeviceState). Teardown never blocks sign-out: even if the
      // local clear fails, the session must still end.
      await clearSharedDeviceState()
      return supabase.auth.signOut()
    },
  }

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export const useAuth = () => useContext(AuthContext)
