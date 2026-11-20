// frontend/src/hooks/useRealtimeCases.js
import { useEffect } from 'react'
import { supabase } from '../lib/supabase'

/**
 * Subscribes to Realtime changes on case_records.
 *
 * @param {object} options
 * @param {function} options.onInsert   - Called with new row on INSERT
 * @param {function} options.onUpdate   - Called with updated row on UPDATE
 * @param {string}   options.facilityId - Filters to this facility (optional)
 * @param {string}   options.userId     - Filters to this user's cases (optional, for ASHA)
 * @param {boolean}  options.global     - Allows unscoped/global subscription when explicitly true
 */
export function useRealtimeCases({ onInsert, onUpdate, facilityId, userId, global = false } = {}) {
  useEffect(() => {
    // Guard against subscribing to realtime cases without resolved scoping filters unless explicitly global
    if (!global && !facilityId && !userId) {
      return
    }

    // Build a unique channel name to avoid collisions across hook instances
    const channelName = `case_records_${facilityId ?? 'all'}_${userId ?? 'all'}_${Date.now()}`

    // F-15: Supabase Realtime supports only a single filter string per channel.
    // Use facility_id as primary filter when available, falling back to submitted_by.
    // Secondary criteria (e.g. user filter within facility) is enforced client-side.
    const primaryFilter = facilityId
      ? 'facility_id=eq.' + facilityId
      : (userId ? 'submitted_by=eq.' + userId : undefined)

    const channel = supabase
      .channel(channelName)
      .on(
        'postgres_changes',
        {
          event: 'INSERT',
          schema: 'public',
          table: 'case_records',
          ...(primaryFilter ? { filter: primaryFilter } : {}),
        },
        (payload) => {
          // Client-side secondary filter when both facilityId and userId are active
          if (facilityId && userId && payload.new?.submitted_by !== userId) {
            return
          }
          onInsert?.(payload.new)
        }
      )
      .on(
        'postgres_changes',
        {
          event: 'UPDATE',
          schema: 'public',
          table: 'case_records',
          ...(primaryFilter ? { filter: primaryFilter } : {}),
        },
        (payload) => {
          // Client-side secondary filter when both facilityId and userId are active
          if (facilityId && userId && payload.new?.submitted_by !== userId) {
            return
          }
          onUpdate?.(payload.new)
        }
      )
      .subscribe()

    return () => {
      supabase.removeChannel(channel)
    }
  }, [facilityId, userId, global]) // re-subscribe if scoping filters or global mode change
}