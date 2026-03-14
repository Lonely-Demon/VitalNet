// frontend/src/hooks/useLocalTriage.js
import { useState, useEffect, useCallback } from 'react'
import { loadModel, warmupModel, runTriage } from '../utils/triageClassifier'

export function useLocalTriage() {
  const [modelReady, setModelReady] = useState(false)
  const [modelError, setModelError] = useState(null)

  useEffect(() => {
    warmupModel()
      .then(() => setModelReady(true))
      .catch((err) => {
        console.warn('[VitalNet] ONNX warmup failed:', err)
        setModelError(err.message)
        // Non-fatal — form still works, local triage just unavailable
      })
  }, [])

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

  return { modelReady, modelError, classify }
}