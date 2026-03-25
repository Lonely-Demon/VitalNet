/**
 * auth.js — Stateless Supabase auth helpers.
 * No state stored here; all auth helpers are pure functions.
 */
import { supabase } from '@/lib/supabase'

/**
 * Returns standard auth headers for API requests.
 * Throws if the user is not authenticated.
 */
export async function authHeaders() {
  const { data: { session } } = await supabase.auth.getSession()
  if (!session) throw new Error('Not authenticated')
  return {
    'Content-Type': 'application/json',
    'Authorization': `Bearer ${session.access_token}`,
  }
}
