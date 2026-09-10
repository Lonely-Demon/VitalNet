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
// Shared-device teardown on logout. The PHC tablets are handed between ASHA
// workers, so ending a session must not leave the previous worker's data
// readable by the next one:
//   - form-drafts: in-progress (unsubmitted) intake forms belonging to the signing-out user (VN-2026-08-C4-04).
//   - vn_facility_phone / vn_outbox_key: cleared from sessionStorage (VN-2026-08-C4-02, C4-03).
// vn_device_id is a browser-stable anti-replay identifier and is intentionally left in place.
async function clearSharedDeviceState(userId) {
  try {
    sessionStorage.removeItem('vn_facility_phone')
    sessionStorage.removeItem('vn_outbox_key')
  } catch { /* sessionStorage unavailable */ }
  try {
    const db = await getOfflineDB()
    const tx = db.transaction('form-drafts', 'readwrite')
    const store = tx.objectStore('form-drafts')
    const allKeys = await store.getAllKeys()
    for (const key of allKeys) {
      const draft = await store.get(key)
      if (!draft || !draft.owner_id || draft.owner_id === userId) {
        await store.delete(key)
      }
    }
    await tx.done
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
        // Cached to sessionStorage so the facility contact number survives
        // offline page refresh during the session without persisting across logins (VN-2026-08-C4-02).
        const phone = data.facilities?.phone
        if (phone) sessionStorage.setItem('vn_facility_phone', phone)
      }
    } catch {
      // Offline or network error — keep existing profile (don't blank the page)
      console.warn('[VitalNet] Profile fetch failed (offline?), keeping cached state')
    }
  }

  const value = {
    session,
    profile,
    // Database profile is the single source of truth for user role (VN-2026-08-C4-01).
    role:      profile?.role ?? null,
    isLoading: session === undefined,
    signIn:    (email, password) =>
                 supabase.auth.signInWithPassword({ email, password }),
    signOut:   async () => {
      // Tear down device-local PHI for the signing-out user before ending session.
      await clearSharedDeviceState(session?.user?.id)
      return supabase.auth.signOut()
    },
  }

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export const useAuth = () => useContext(AuthContext)
