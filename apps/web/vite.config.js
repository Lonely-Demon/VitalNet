import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { VitePWA } from 'vite-plugin-pwa'
import path from 'path'

export default defineConfig({
  resolve: {
    alias: { '@': path.resolve(__dirname, './src') },
  },

  plugins: [
    react(),
    tailwindcss(),
    VitePWA({
      registerType: 'prompt',

      // Precache the app shell + the offline triage model. The model is now a
      // compact tree JSON (~1 MB, gzips far smaller) evaluated in pure JS —
      // there is no onnxruntime-web WASM to precache anymore, which is the
      // headline weak-hardware/low-bandwidth win of the Option-6 offline engine.
      workbox: {
        // Raise the per-file precache cap so triage_trees.json is precached
        // (default is 2 MiB; the JSON is ~1 MB but keep headroom).
        maximumFileSizeToCacheInBytes: 4 * 1024 * 1024,
        globPatterns: [
          '**/*.{js,css,html,ico,png,svg,woff2}',
          'models/triage_trees.json',
          'models/features_config.json',
        ],
        // Web Push handler (FEATURES_ROADMAP §1.4) — a small standalone
        // script rather than switching to injectManifest mode.
        importScripts: ['sw-push.js'],

        // Background Sync for POST /api/submit (in-flight failure recovery)
        runtimeCaching: [{
          urlPattern: ({ url }) => url.pathname === '/api/submit',
          handler: 'NetworkOnly',
          method: 'POST',
          options: {
            backgroundSync: {
              name: 'vitalnet_submission_queue',
              options: {
                maxRetentionTime: 24 * 60,  // 24 hours in minutes
              },
            },
          },
        }],
      },

      manifest: {
        name: 'VitalNet',
        short_name: 'VitalNet',
        description: 'Clinical triage platform for ASHA workers and PHC doctors',
        theme_color: '#1F4D34',
        background_color: '#F7F4EE',
        display: 'standalone',
        orientation: 'portrait',
        start_url: '/',
        scope: '/',
        icons: [
          {
            src: 'pwa-64x64.png',
            sizes: '64x64',
            type: 'image/png',
          },
          {
            src: 'pwa-192x192.png',
            sizes: '192x192',
            type: 'image/png',
          },
          {
            src: 'pwa-512x512.png',
            sizes: '512x512',
            type: 'image/png',
          },
          {
            src: 'maskable-icon-512x512.png',
            sizes: '512x512',
            type: 'image/png',
            purpose: 'maskable',
          },
        ],
      },
    }),
  ],
  server: {
    proxy: {
      '/api': 'http://localhost:8000'
    }
  }
})
