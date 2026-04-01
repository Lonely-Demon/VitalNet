import { Component } from 'react'
import { getQueueCount } from '../lib/offlineQueue'

/**
 * ErrorBoundary.jsx — React Error Boundary for VitalNet
 *
 * Catches uncaught React component errors and displays a graceful error UI
 * instead of crashing to a white screen. Critical for clinical reliability.
 *
 * Features:
 * - User-friendly error messaging appropriate for clinical users
 * - Offline queue status preservation (pending submissions are not lost)
 * - Recovery actions: reload app or return to home
 * - Error logging for developer/operator observability
 * - Auth state preservation (session survives error boundary)
 */

export class ErrorBoundary extends Component {
  constructor(props) {
    super(props)
    this.state = {
      hasError: false,
      error: null,
      errorInfo: null,
      queueCount: 0,
    }
  }

  static getDerivedStateFromError(error) {
    // Update state so the next render shows the fallback UI
    return { hasError: true }
  }

  async componentDidCatch(error, errorInfo) {
    // Get offline queue count for display
    let queueCount = 0
    try {
      queueCount = await getQueueCount()
    } catch {
      // IndexedDB might be unavailable - that's OK
    }

    this.setState({
      error,
      errorInfo,
      queueCount,
    })

    // Log error for observability
    this.logError(error, errorInfo, queueCount)
  }

  logError(error, errorInfo, queueCount) {
    const timestamp = new Date().toISOString()
    const errorMessage = error?.message || 'Unknown error'
    const componentStack = errorInfo?.componentStack || errorInfo?.stack || 'No stack trace'

    // Console logging for development
    console.error('=== VitalNet Error Boundary Caught Error ===')
    console.error(`Timestamp: ${timestamp}`)
    console.error(`Error: ${errorMessage}`)
    console.error(`Queue Count: ${queueCount}`)
    console.error(`Component Stack:\n${componentStack}`)

    // Optional: Send to error reporting service in production
    // This could be Sentry, LogRocket, or a custom endpoint
    if (import.meta.env.PROD) {
      try {
        // Example: Send to error reporting service
        // fetch('/api/errors', {
        //   method: 'POST',
        //   headers: { 'Content-Type': 'application/json' },
        //   body: JSON.stringify({
        //     message: errorMessage,
        //     stack: componentStack,
        //     queueCount,
        //     timestamp,
        //     userAgent: navigator.userAgent,
        //   }),
        // }).catch(() => {})
      } catch {
        // Silently fail - don't let error reporting break the app
      }
    }
  }

  handleReload = () => {
    // Preserve auth by not clearing storage
    window.location.reload()
  }

  handleReturnHome = () => {
    // Navigate to home without full reload if possible
    // This preserves the React component tree and auth state
    this.setState({ hasError: false, error: null, errorInfo: null })
    window.dispatchEvent(new CustomEvent('navigate-to-home'))
  }

  render() {
    if (this.state.hasError) {
      return (
        <ErrorFallback
          error={this.state.error}
          queueCount={this.state.queueCount}
          onReload={this.handleReload}
          onReturnHome={this.handleReturnHome}
        />
      )
    }

    return this.props.children
  }
}

/**
 * ErrorFallback — User-friendly error UI displayed when an error is caught
 */
function ErrorFallback({ error, queueCount, onReload, onReturnHome }) {
  const errorMessage = error?.message || 'An unexpected error occurred'
  const isNetworkError = errorMessage.includes('fetch') || errorMessage.includes('network')
  const isAuthError = errorMessage.includes('auth') || errorMessage.includes('session')

  return (
    <div className="min-h-screen bg-bg flex items-center justify-center p-4">
      <div className="max-w-md w-full bg-card rounded-xl shadow-card-hover p-6 animate-fade-up">
        {/* Error Icon */}
        <div className="flex justify-center mb-4">
          <div className="w-16 h-16 bg-emergency/20 rounded-full flex items-center justify-center">
            <svg
              className="w-8 h-8 text-emergency"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
              />
            </svg>
          </div>
        </div>

        {/* Error Title */}
        <h1 className="text-xl font-semibold text-text text-center mb-2">
          Something went wrong
        </h1>

        {/* Error Message */}
        <p className="text-text2 text-center mb-4 text-sm">
          {isNetworkError
            ? 'Unable to connect to the server. Please check your internet connection.'
            : isAuthError
            ? 'Your session may have expired. Try reloading the app.'
            : 'A technical error occurred. Your data is safe.'}
        </p>

        {/* Technical Error Details (collapsible) */}
        <details className="mb-4">
          <summary className="text-xs text-text3 cursor-pointer hover:text-text2 transition-colors">
            Technical details
          </summary>
          <pre className="mt-2 p-2 bg-bg rounded text-xs text-text3 overflow-x-auto max-h-32 text-left">
            {errorMessage}
          </pre>
        </details>

        {/* Offline Queue Status */}
        {queueCount > 0 && (
          <div className="mb-4 p-3 bg-forest/10 border border-forest/20 rounded-lg">
            <div className="flex items-center gap-2">
              <svg className="w-5 h-5 text-forest" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
              </svg>
              <span className="text-sm text-forest font-medium">
                {queueCount} submission{queueCount > 1 ? 's' : ''} saved offline
              </span>
            </div>
            <p className="text-xs text-text2 mt-1">
              Your pending submissions are safe and will sync when you reconnect.
            </p>
          </div>
        )}

        {/* Action Buttons */}
        <div className="flex flex-col gap-2">
          <button
            onClick={onReload}
            className="w-full py-3 px-4 bg-primary text-white rounded-lg font-medium
                       hover:bg-primary/90 transition-colors focus:outline-none focus:ring-2
                       focus:ring-primary/50"
          >
            Reload App
          </button>
          <button
            onClick={onReturnHome}
            className="w-full py-3 px-4 bg-bg border border-border text-text rounded-lg font-medium
                       hover:bg-bg/80 transition-colors focus:outline-none focus:ring-2
                       focus:ring-border"
          >
            Try Again
          </button>
        </div>

        {/* Help Text */}
        <p className="text-xs text-text3 text-center mt-4">
          If this problem persists, please contact your administrator.
        </p>
      </div>
    </div>
  )
}

export default ErrorBoundary