import { Component } from 'react'
import { getPendingCount } from '../lib/outbox'

/**
 * ErrorBoundary.jsx — React Error Boundary for VitalNet
 *
 * Catches uncaught React component errors and displays a graceful error UI
 * instead of crashing to a white screen. Critical for clinical reliability:
 * shows offline-queue status so a worker mid-submission knows their pending
 * cases are safe, and offers reload/retry recovery actions.
 */
export class ErrorBoundary extends Component {
  constructor(props) {
    super(props)
    this.state = { hasError: false, error: null, queueCount: 0 }
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error }
  }

  async componentDidCatch(error, errorInfo) {
    let queueCount = 0
    try {
      queueCount = await getPendingCount()
    } catch {
      // IndexedDB might be unavailable — that's OK, just show 0
    }
    this.setState({ queueCount })
    console.error('[VitalNet] ErrorBoundary caught:', error, errorInfo?.componentStack)
  }

  handleReload = () => {
    window.location.reload()
  }

  handleReturnHome = () => {
    this.setState({ hasError: false, error: null })
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

function ErrorFallback({ error, queueCount, onReload, onReturnHome }) {
  const errorMessage = error?.message || 'An unexpected error occurred'
  const isNetworkError = /fetch|network/i.test(errorMessage)
  const isAuthError = /auth|session/i.test(errorMessage)

  return (
    <div className="min-h-screen bg-bg flex items-center justify-center p-4">
      <div className="max-w-md w-full bg-card rounded-xl shadow-card-hover p-6 animate-fade-up">
        <div className="flex justify-center mb-4">
          <div className="w-16 h-16 bg-emergency/20 rounded-full flex items-center justify-center">
            <svg className="w-8 h-8 text-emergency" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
              />
            </svg>
          </div>
        </div>

        <h1 className="text-xl font-semibold text-text text-center mb-2">Something went wrong</h1>

        <p className="text-text2 text-center mb-4 text-sm">
          {isNetworkError
            ? 'Unable to connect to the server. Please check your internet connection.'
            : isAuthError
            ? 'Your session may have expired. Try reloading the app.'
            : 'A technical error occurred. Your data is safe.'}
        </p>

        <details className="mb-4">
          <summary className="text-xs text-text3 cursor-pointer hover:text-text2 transition-colors">
            Technical details
          </summary>
          <pre className="mt-2 p-2 bg-bg rounded text-xs text-text3 overflow-x-auto max-h-32 text-left">
            {errorMessage}
          </pre>
        </details>

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

        <p className="text-xs text-text3 text-center mt-4">
          If this problem persists, please contact your administrator.
        </p>
      </div>
    </div>
  )
}

export default ErrorBoundary
