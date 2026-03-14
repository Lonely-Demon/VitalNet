import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App.jsx'
import './index.css'
import { registerSW } from 'virtual:pwa-register'

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
)

// PWA service worker registration
const updateSW = registerSW({
  onNeedRefresh() {
    console.log('[VitalNet PWA] New version available')
  },
  onOfflineReady() {
    console.log('[VitalNet PWA] App ready for offline use')
  },
})
