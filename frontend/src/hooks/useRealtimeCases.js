// frontend/src/hooks/useRealtimeCases.js
import { useEffect, useRef, useCallback } from 'react'
import { supabase } from '../lib/supabase'

/**
 * R3-REL-CB-R3-003 fix: Centralized subscription registry to prevent
 * multiple websocket connections for the same filter combination.
 * This implements a bulkhead pattern to limit concurrent realtime channels.
 */

// Registry to track active subscriptions and their callbacks
// Key: channel name, Value: { channel, callbacks: Set, refCount }
const subscriptionRegistry = new Map()

// Maximum number of concurrent realtime channels allowed
// R3-REL-CB-R3-003: Cap to prevent exhaustion of realtime capacity
const MAX_CONCURRENT_CHANNELS = 5

// Track total channel count for the bulkhead limit
let totalChannelCount = 0

/**
 * Get or create a shared channel for the given filter combination.
 * If a channel already exists for these filters, add the callbacks to it
 * and increment the reference count.
 */
function getOrCreateChannel(facilityId, userId, onInsert, onUpdate) {
  // Build a deterministic channel name (no Date.now() - that's the bug!)
  const channelName = `case_records_${facilityId ?? 'all'}_${userId ?? 'all'}`

  // Check if we already have a channel for this filter combination
  if (subscriptionRegistry.has(channelName)) {
    const entry = subscriptionRegistry.get(channelName)
    entry.callbacks.onInsert.add(onInsert)
    entry.callbacks.onUpdate.add(onUpdate)
    entry.refCount++
    return entry.channel
  }

  // Check bulkhead limit - if at capacity, return null to indicate fallback needed
  if (totalChannelCount >= MAX_CONCURRENT_CHANNELS) {
    console.warn(
      `[VitalNet] Realtime bulkhead limit reached (${MAX_CONCURRENT_CHANNELS} channels). ` +
      `Consider falling back to polling for ${channelName}`
    )
    return null
  }

  // Create new channel
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
        // Broadcast to all registered callbacks
        const entry = subscriptionRegistry.get(channelName)
        if (entry) {
          entry.callbacks.onInsert.forEach(cb => cb?.(payload.new))
        }
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
        // Broadcast to all registered callbacks
        const entry = subscriptionRegistry.get(channelName)
        if (entry) {
          entry.callbacks.onUpdate.forEach(cb => cb?.(payload.new))
        }
      }
    )
    .subscribe()

  // Register the channel
  subscriptionRegistry.set(channelName, {
    channel,
    callbacks: {
      onInsert: new Set([onInsert]),
      onUpdate: new Set([onUpdate]),
    },
    refCount: 1,
  })

  totalChannelCount++
  return channel
}

/**
 * Remove callbacks from a channel and clean up if no more references.
 */
function removeFromRegistry(channelName, onInsert, onUpdate) {
  const entry = subscriptionRegistry.get(channelName)
  if (!entry) return

  entry.callbacks.onInsert.delete(onInsert)
  entry.callbacks.onUpdate.delete(onUpdate)
  entry.refCount--

  // If no more references, clean up the channel
  if (entry.refCount <= 0) {
    supabase.removeChannel(entry.channel)
    subscriptionRegistry.delete(channelName)
    totalChannelCount--
  }
}

/**
 * Subscribes to Realtime changes on case_records.
 * R3-REL-CB-R3-003 fix: Uses shared subscription registry to prevent
 * multiple websocket connections for the same filter combination.
 *
 * @param {object} options
 * @param {function} options.onInsert - Called with new row on INSERT
 * @param {function} options.onUpdate - Called with updated row on UPDATE
 * @param {string} options.facilityId - Filters to this facility (optional)
 * @param {string} options.userId - Filters to this user's cases (optional, for ASHA)
 */
export function useRealtimeCases({ onInsert, onUpdate, facilityId, userId } = {}) {
  const channelRef = useRef(null)
  const channelName = `case_records_${facilityId ?? 'all'}_${userId ?? 'all'}`

  // Wrap callbacks in refs to avoid re-registration on every render
  const onInsertRef = useRef(onInsert)
  const onUpdateRef = useRef(onUpdate)

  useEffect(() => {
    onInsertRef.current = onInsert
    onUpdateRef.current = onUpdate
  }, [onInsert, onUpdate])

  useEffect(() => {
    // Try to get or create a shared channel
    const channel = getOrCreateChannel(
      facilityId,
      userId,
      onInsertRef.current,
      onUpdateRef.current
    )

    // If bulkhead limit reached, channel will be null
    // Consumer can handle this by falling back to polling
    channelRef.current = channel

    return () => {
      removeFromRegistry(channelName, onInsertRef.current, onUpdateRef.current)
    }
  }, [facilityId, userId]) // Re-register if facility or user changes

  // Return channel ref for external control (e.g., testing, debugging)
  return channelRef
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