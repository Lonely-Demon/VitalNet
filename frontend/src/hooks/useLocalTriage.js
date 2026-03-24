// frontend/src/hooks/useLocalTriage.js
import { useState, useEffect, useCallback } from 'react'
import { warmupModel, runTriage } from '../utils/triageClassifier'

export function useLocalTriage() {
  const [modelReady, setModelReady] = useState(false)
  const [modelError, setModelError] = useState(null)

  // Shared warmup function — can be triggered internally or externally via event
  const triggerWarmup = useCallback(() => {
    if (modelReady) return  // Already loaded — skip
    warmupModel()
      .then(() => setModelReady(true))
      .catch((err) => {
        console.warn('[VitalNet] ONNX warmup failed:', err)
        setModelError(err.message)
        // Non-fatal — form still works, local triage just unavailable
      })
  }, [modelReady])

  useEffect(() => {
    // Load immediately if already offline at mount time
    if (!navigator.onLine) triggerWarmup()

    // Preemptively load when the browser detects loss of network
    window.addEventListener('offline', triggerWarmup)
    // Also warm up if server becomes unreachable while browser is online
    // (dispatched by api.js on TypeError or navigator.onLine === false)
    window.addEventListener('vitalnet-server-unreachable', triggerWarmup)

    return () => {
      window.removeEventListener('offline', triggerWarmup)
      window.removeEventListener('vitalnet-server-unreachable', triggerWarmup)
    }
  }, [triggerWarmup])

  const classify = useCallback(
    async (formData) => {
      if (!modelReady) return null
      try {
        return await runTriage(formData)
      } catch (err) {
        console.warn('[VitalNet] Local triage failed:', err)
        return null
      }
    },
    [modelReady]
  )

  // triggerWarmup is exported so callers can imperatively trigger it
  return { modelReady, modelError, classify, triggerWarmup }
}