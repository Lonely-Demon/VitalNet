// frontend/src/hooks/useRealtimeCases.js
import { useEffect, useRef } from 'react'
import { supabase } from '../lib/supabase'

/**
 * Subscribes to Realtime changes on case_records.
 *
 * @param {object} options
 * @param {function} options.onInsert   - Called with new row on INSERT
 * @param {function} options.onUpdate   - Called with updated row on UPDATE
 * @param {string}   options.facilityId - Filters to this facility (optional)
 * @param {string}   options.userId     - Filters to this user's cases (optional, for ASHA)
 */
export function useRealtimeCases({ onInsert, onUpdate, facilityId, userId } = {}) {
  const channelRef = useRef(null)

  useEffect(() => {
    // Build a unique channel name to avoid collisions across hook instances
    const channelName = `case_records_${facilityId ?? 'all'}_${userId ?? 'all'}_${Date.now()}`

    const channel = supabase
      .channel(channelName)
      .on(
        'postgres_changes',
        {
          event: 'INSERT',
          schema: 'public',
          table: 'case_records',
          // Supabase Realtime filter syntax: "column=eq.value"
          ...(facilityId ? { filter: `facility_id=eq.${facilityId}` } : {}),
          ...(userId ? { filter: `submitted_by=eq.${userId}` } : {}),
        },
        (payload) => {
          onInsert?.(payload.new)
        }
      )
      .on(
        'postgres_changes',
        {
          event: 'UPDATE',
          schema: 'public',
          table: 'case_records',
          ...(facilityId ? { filter: `facility_id=eq.${facilityId}` } : {}),
          ...(userId ? { filter: `submitted_by=eq.${userId}` } : {}),
        },
        (payload) => {
          onUpdate?.(payload.new)
        }
      )
      .subscribe()

    channelRef.current = channel

    return () => {
      supabase.removeChannel(channel)
    }
  }, [facilityId, userId]) // re-subscribe if facility or user changes
}