import { createContext, useContext, useState, useCallback } from 'react'

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
    // - error/warning: stay until acknowledged (no auto-dismiss)
    // - info/success: 5 seconds (slightly longer for readability)
    // - custom duration: use provided value
    const toastDuration = duration ?? (type === 'error' || type === 'warning' ? null : 5000)

    if (toastDuration !== null) {
      setTimeout(() => {
        setToasts(prev => prev.filter(t => t.id !== id))
      }, toastDuration)
    }
  }, [])

  const dismissToast = useCallback((id) => {
    setToasts(prev => prev.filter(t => t.id !== id))
  }, [])

  return (
    <ToastContext.Provider value={{ showToast, dismissToast }}>
      {children}
      {/* Fixed bottom-right toast container */}
      <div className="fixed bottom-4 right-4 z-50 flex flex-col gap-2 max-w-sm">
        {toasts.map(t => (
          <div
            key={t.id}
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
