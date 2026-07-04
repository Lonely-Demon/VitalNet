// frontend/src/hooks/useRealtimeReferrals.js
import { useEffect, useRef } from 'react'
import { supabase } from '../lib/supabase'

/**
 * Subscribes to Realtime changes on referrals. A facility can be on either
 * side of a referral (referring or receiving), so — unlike useRealtimeCases,
 * which filters on a single column — this binds two separate postgres_changes
 * filters (one per side) on the same channel when a facilityId is given.
 * admin (no facilityId) gets an unfiltered subscription.
 *
 * @param {object} options
 * @param {function} options.onInsert   - Called with new row on INSERT
 * @param {function} options.onUpdate   - Called with updated row on UPDATE
 * @param {string}   options.facilityId - Filters to referrals touching this facility (optional; omit for admin/global)
 */
export function useRealtimeReferrals({ onInsert, onUpdate, facilityId } = {}) {
  const channelRef = useRef(null)

  useEffect(() => {
    const channelName = `referrals_${facilityId ?? 'all'}_${Date.now()}`
    let channel = supabase.channel(channelName)

    const bind = (filter) => {
      channel = channel
        .on(
          'postgres_changes',
          { event: 'INSERT', schema: 'public', table: 'referrals', ...(filter ? { filter } : {}) },
          (payload) => onInsert?.(payload.new)
        )
        .on(
          'postgres_changes',
          { event: 'UPDATE', schema: 'public', table: 'referrals', ...(filter ? { filter } : {}) },
          (payload) => onUpdate?.(payload.new)
        )
    }

    if (facilityId) {
      bind(`referring_facility_id=eq.${facilityId}`)
      bind(`receiving_facility_id=eq.${facilityId}`)
    } else {
      bind(null)
    }

    channel.subscribe()
    channelRef.current = channel

    return () => {
      supabase.removeChannel(channel)
    }
  }, [facilityId])
}
