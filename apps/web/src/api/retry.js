/**
 * retry.js — Centralized retry logic with exponential backoff for API calls.
 * Used for idempotent (GET) requests only — rural/low-connectivity links see
 * frequent transient 5xx/timeout/network errors that a short backoff resolves
 * without the user needing to manually refresh.
 */

const MAX_RETRIES = 3
const INITIAL_BACKOFF_MS = 500
const MAX_BACKOFF_MS = 4000

function isRetryable(response) {
  if (!response) return true // network error — always retryable
  return (response.status >= 500 && response.status < 600) || response.status === 429 || response.status === 408
}

function getBackoffDelay(attempt) {
  const exponentialDelay = INITIAL_BACKOFF_MS * Math.pow(2, attempt)
  const cappedDelay = Math.min(exponentialDelay, MAX_BACKOFF_MS)
  const jitter = cappedDelay * 0.25 * (Math.random() * 2 - 1) // ±25%, avoids thundering herd
  return Math.floor(cappedDelay + jitter)
}

/**
 * Fetch with retry + exponential backoff. Only retries GET-safe (idempotent)
 * requests — do not use for non-idempotent mutations without a server-side
 * idempotency key.
 */
export async function fetchWithRetry(url, options, { maxRetries = MAX_RETRIES } = {}) {
  let lastError

  for (let attempt = 0; attempt <= maxRetries; attempt++) {
    try {
      const res = await fetch(url, options)
      if (attempt < maxRetries && isRetryable(res)) {
        console.warn(`[VitalNet] Retrying ${url} (attempt ${attempt + 1}/${maxRetries}, status ${res.status})`)
        await new Promise((resolve) => setTimeout(resolve, getBackoffDelay(attempt)))
        continue
      }
      return res
    } catch (error) {
      lastError = error
      if (attempt < maxRetries) {
        console.warn(`[VitalNet] Retrying ${url} (attempt ${attempt + 1}/${maxRetries}): ${error.message}`)
        await new Promise((resolve) => setTimeout(resolve, getBackoffDelay(attempt)))
      }
    }
  }

  throw lastError
}

export async function getWithRetry(url, headers, config = {}) {
  return fetchWithRetry(url, { method: 'GET', headers }, config)
}
