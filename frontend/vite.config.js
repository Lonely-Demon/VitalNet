import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { VitePWA } from 'vite-plugin-pwa'

export default defineConfig({
  // Handle ONNX files as static assets
  assetsInclude: ['**/*.onnx'],

  // Exclude onnxruntime-web from pre-bundling (uses dynamic WASM loading)
  optimizeDeps: {
    exclude: ['onnxruntime-web'],
  },

  plugins: [
    react(),
    tailwindcss(),
    VitePWA({
      registerType: 'prompt',

      // Precache the entire app shell
      workbox: {
        globPatterns: [
          '**/*.{js,css,html,ico,png,svg,woff2}',
          'models/triage_classifier.onnx',
          'models/features_config.json',
        ],

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
