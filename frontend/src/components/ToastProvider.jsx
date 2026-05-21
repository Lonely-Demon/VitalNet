import { createContext, useContext, useState, useCallback, useMemo } from 'react'

const ToastContext = createContext(null)

export function useToast() {
  const ctx = useContext(ToastContext)
  if (!ctx) throw new Error('useToast must be used within <ToastProvider>')
  return ctx
}

const TYPE_STYLES = {
  success: 'bg-routine text-white',
  warning: 'bg-urgent text-white',
  error:   'bg-emergency text-white',
  info:    'bg-forest text-white',
}

export default function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([])

  const showToast = useCallback((message, type = 'info', duration = null) => {
    const id = Date.now() + Math.random()
    setToasts(prev => [...prev, { id, message, type }])

    // Determine toast duration based on type:
    // - error: stay until acknowledged (no auto-dismiss)
    // - warning: 10 seconds 
    // - info/success: 5 seconds
    // - custom duration: use provided value
    let defaultDuration = 5000;
    if (type === 'error') defaultDuration = null;
    else if (type === 'warning') defaultDuration = 10000;
    
    const toastDuration = duration !== null ? duration : defaultDuration;

    if (toastDuration !== null) {
      setTimeout(() => {
        setToasts(current => current.filter(t => t.id !== id))
      }, toastDuration)
    }
  }, [])

  const dismissToast = useCallback((id) => {
    setToasts(prev => prev.filter(t => t.id !== id))
  }, [])

  // R3-PERF-RENDER-R3-001: keep provider value reference stable so toast list
  // updates don't invalidate all useToast consumers.
  const contextValue = useMemo(() => ({
    showToast,
    dismissToast,
  }), [showToast, dismissToast])

  return (
    <ToastContext.Provider value={contextValue}>
      {children}
      {/* Fixed bottom-right toast container */}
      <div className="fixed bottom-4 right-4 z-50 flex flex-col gap-2 max-w-sm" aria-live="polite" aria-atomic="true">
        {toasts.map(t => (
          <div
            key={t.id}
            role={t.type === 'error' || t.type === 'warning' ? 'alert' : 'status'}
            className={`px-4 py-3 rounded-lg shadow-card-hover text-sm font-medium animate-fade-up flex items-center justify-between gap-2 ${TYPE_STYLES[t.type] || TYPE_STYLES.info}`}
          >
            <span>{t.message}</span>
            {/* Show dismiss button for error/warning toasts that don't auto-dismiss */}
            {(t.type === 'error' || t.type === 'warning') && (
              <button
                onClick={() => dismissToast(t.id)}
                className="ml-2 text-white/80 hover:text-white text-lg leading-none"
                aria-label="Dismiss"
              >
                ×
              </button>
            )}
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  )
}
