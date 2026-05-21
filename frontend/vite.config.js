import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { VitePWA } from 'vite-plugin-pwa'
import path from 'path'

export default defineConfig({
  // Handle ONNX files as static assets
  assetsInclude: ['**/*.onnx'],

  // Exclude onnxruntime-web from pre-bundling (uses dynamic WASM loading)
  optimizeDeps: {
    exclude: ['onnxruntime-web'],
  },

  build: {
    chunkSizeWarningLimit: 2000,
    rollupOptions: {
      output: {
        // ROOT-PERF-001: deterministic chunking strategy for stable cache reuse.
        manualChunks(id) {
          const moduleId = id.replace(/\\/g, '/')
          if (!moduleId.includes('node_modules')) return undefined

          if (
            moduleId.includes('/react/') ||
            moduleId.includes('/react-dom/') ||
            moduleId.includes('/react-router')
          ) {
            return 'vendor-react'
          }

          if (moduleId.includes('/@supabase/')) {
            return 'vendor-supabase'
          }

          if (moduleId.includes('/onnxruntime-web/')) {
            return 'vendor-onnx'
          }

          if (moduleId.includes('/recharts/') || moduleId.includes('/d3-')) {
            return 'vendor-charts'
          }

          if (moduleId.includes('/date-fns/')) {
            return 'vendor-date'
          }

          return 'vendor-misc'
        },
      },
    },
  },

  resolve: {
    alias: { '@': path.resolve(__dirname, './src') },
  },

  plugins: [
    react(),
    tailwindcss(),
    VitePWA({
      registerType: 'prompt',

      // Precache app shell only; heavy ML assets are runtime-cached below.
      workbox: {
        globPatterns: [
          '**/*.{js,css,html,ico,png,svg,woff2}',
        ],

        runtimeCaching: [
          {
            // R3-PERF-ASSET-R3-001: runtime caching policy for large ML assets.
            urlPattern: ({ url }) =>
              url.pathname.endsWith('.wasm') ||
              url.pathname.endsWith('.onnx') ||
              url.pathname.includes('/models/'),
            handler: 'CacheFirst',
            options: {
              cacheName: 'ml-assets-cache',
              expiration: {
                maxEntries: 12,
                maxAgeSeconds: 7 * 24 * 60 * 60,
              },
              cacheableResponse: {
                statuses: [0, 200],
              },
            },
          },

          // Background Sync for POST /api/submit (in-flight failure recovery)
          {
            urlPattern: ({ url }) => url.pathname === '/api/submit',
            handler: 'NetworkOnly',
            method: 'POST',
            options: {
              backgroundSync: {
                name: 'vitalnet_submission_queue',
                options: {
                  maxRetentionTime: 24 * 60, // 24 hours in minutes
                },
              },
            },
          },
        ],
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
      '/api': 'http://localhost:8000',
    },
  },
})
