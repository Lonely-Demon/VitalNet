/**
 * retry.js — Centralized retry logic with exponential backoff for API calls.
 */

const MAX_RETRIES = 3
const INITIAL_BACKOFF_MS = 500
const MAX_BACKOFF_MS = 4000

/**
 * Determines if an error is retryable (network error or 5xx server error).
 * @param {Error|null} error - The error that occurred
 * @param {Response|null} response - The response object (if available)
 * @returns {boolean}
 */
function isRetryable(error, response) {
  // Network errors (no response) are always retryable
  if (!response) {
    return true
  }

  // 5xx server errors are retryable
  if (response.status >= 500 && response.status < 600) {
    return true
  }

  // 429 Too Many Requests is retryable
  if (response.status === 429) {
    return true
  }

  // 408 Request Timeout is retryable
  if (response.status === 408) {
    return true
  }

  // All other errors (including 4xx) are not retryable
  return false
}

/**
 * Calculates exponential backoff delay with jitter.
 * @param {number} attempt - The current attempt number (0-indexed)
 * @returns {number} Delay in milliseconds
 */
function getBackoffDelay(attempt) {
  const exponentialDelay = INITIAL_BACKOFF_MS * Math.pow(2, attempt)
  const cappedDelay = Math.min(exponentialDelay, MAX_BACKOFF_MS)
  // Add jitter (±25%) to prevent thundering herd
  const jitter = cappedDelay * 0.25 * (Math.random() * 2 - 1)
  return Math.floor(cappedDelay + jitter)
}

/**
 * Logs retry attempts for observability.
 * @param {string} url - The request URL
 * @param {number} attempt - The current attempt number
 * @param {Error|null} error - The error that occurred
 * @param {number|null} status - HTTP status code if available
 */
function logRetryAttempt(url, attempt, error, status) {
  const timestamp = new Date().toISOString()
  console.warn(
    `[RETRY] ${timestamp} | Attempt ${attempt + 1}/${MAX_RETRIES} | URL: ${url} | Status: ${status ?? 'NETWORK_ERROR'} | Error: ${error?.message ?? 'Unknown'}`
  )
}

/**
 * Performs a fetch with retry logic and exponential backoff.
 * @param {string} url - Request URL
 * @param {object} options - Fetch options
 * @param {object} config - Retry configuration
 * @param {number} [config.maxRetries=MAX_RETRIES] - Maximum number of retry attempts
 * @param {number} [config.timeoutMs] - Optional timeout in milliseconds
 * @param {boolean} [config.retryOnServerError=true] - Whether to retry on 5xx errors
 * @returns {Promise<Response>}
 */
export async function fetchWithRetry(url, options, config = {}) {
  const {
    maxRetries = MAX_RETRIES,
    timeoutMs,
    retryOnServerError = true,
  } = config

  let lastError
  let lastResponse = null

  for (let attempt = 0; attempt <= maxRetries; attempt++) {
    try {
      let fetchOptions = { ...options }

      // Apply timeout if specified
      if (timeoutMs) {
        const controller = new AbortController()
        const timeoutId = setTimeout(
          () => controller.abort(new DOMException('Request timeout', 'TimeoutError')),
          timeoutMs
        )
        fetchOptions = { ...fetchOptions, signal: controller.signal }

        const res = await fetch(url, fetchOptions)
        clearTimeout(timeoutId)

        // Check if we should retry based on response status
        if (attempt < maxRetries && retryOnServerError && isRetryable(null, res)) {
          logRetryAttempt(url, attempt, null, res.status)
          const delay = getBackoffDelay(attempt)
          await new Promise((resolve) => setTimeout(resolve, delay))
          lastResponse = res
          continue
        }

        return res
      }

      const res = await fetch(url, fetchOptions)

      // Check if we should retry based on response status
      if (attempt < maxRetries && retryOnServerError && isRetryable(null, res)) {
        logRetryAttempt(url, attempt, null, res.status)
        const delay = getBackoffDelay(attempt)
        await new Promise((resolve) => setTimeout(resolve, delay))
        lastResponse = res
        continue
      }

      return res
    } catch (error) {
      lastError = error

      // Don't retry on abort (timeout or cancellation)
      if (error.name === 'AbortError') {
        console.error(`[RETRY] Aborted after ${attempt + 1} attempt(s) | URL: ${url}`)
        throw error
      }

      // Log the attempt
      if (attempt < maxRetries) {
        logRetryAttempt(url, attempt, error, null)
        const delay = getBackoffDelay(attempt)
        await new Promise((resolve) => setTimeout(resolve, delay))
      }
    }
  }

  // All retries exhausted
  console.error(
    `[RETRY] Failed after ${maxRetries + 1} attempt(s) | URL: ${url} | Last error: ${lastError?.message}`
  )
  throw lastError
}

/**
 * Performs a GET request with retry logic.
 * @param {string} url - Request URL
 * @param {object} headers - Request headers
 * @param {object} config - Retry configuration
 * @returns {Promise<Response>}
 */
export async function getWithRetry(url, headers, config = {}) {
  return fetchWithRetry(
    url,
    { method: 'GET', headers },
    { ...config, retryOnServerError: true }
  )
}

/**
 * Performs a POST request with retry logic.
 * @param {string} url - Request URL
 * @param {object} headers - Request headers
 * @param {object} body - Request body
 * @param {object} config - Retry configuration
 * @returns {Promise<Response>}
 */
export async function postWithRetry(url, headers, body, config = {}) {
  return fetchWithRetry(
    url,
    {
      method: 'POST',
      headers,
      body: JSON.stringify(body),
    },
    { ...config, retryOnServerError: true }
  )
}

/**
 * Performs a PATCH request with retry logic.
 * @param {string} url - Request URL
 * @param {object} headers - Request headers
 * @param {object} body - Request body
 * @param {object} config - Retry configuration
 * @returns {Promise<Response>}
 */
export async function patchWithRetry(url, headers, body, config = {}) {
  return fetchWithRetry(
    url,
    {
      method: 'PATCH',
      headers,
      body: JSON.stringify(body),
    },
    { ...config, retryOnServerError: true }
  )
}

/**
 * Performs a DELETE request with retry logic.
 * @param {string} url - Request URL
 * @param {object} headers - Request headers
 * @param {object} config - Retry configuration
 * @returns {Promise<Response>}
 */
export async function deleteWithRetry(url, headers, config = {}) {
  return fetchWithRetry(
    url,
    { method: 'DELETE', headers },
    { ...config, retryOnServerError: true }
  )
}

export { MAX_RETRIES, INITIAL_BACKOFF_MS, MAX_BACKOFF_MS }