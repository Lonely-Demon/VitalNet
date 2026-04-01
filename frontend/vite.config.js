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
    rollupOptions: {
      output: {
        manualChunks(id) {
          // React ecosystem
          if (id.includes('node_modules/react') || 
              id.includes('node_modules/react-dom') || 
              id.includes('node_modules/react-router')) {
            return 'vendor-react'
          }
          // Supabase client
          if (id.includes('node_modules/@supabase')) {
            return 'vendor-supabase'
          }
          // ONNX runtime as separate chunk (lazy loaded)
          if (id.includes('node_modules/onnxruntime-web')) {
            return 'vendor-onnx'
          }
          // Chart libraries
          if (id.includes('node_modules/recharts') || 
              id.includes('node_modules/d3')) {
            return 'vendor-charts'
          }
          // Date utilities
          if (id.includes('node_modules/date-fns')) {
            return 'vendor-date'
          }
        }
      }
    }
  },

  resolve: {
    alias: { '@': path.resolve(__dirname, './src') },
  },

  plugins: [
    react(),
    tailwindcss(),
    VitePWA({
      registerType: 'prompt',

      // Precache the entire app shell
      workbox: {
        // Precache the app shell - exclude large WASM/ONNX files
        globPatterns: [
          '**/*.{js,css,html,ico,png,svg,woff2}',
        ],
        // Exclude ONNX/WASM from precache (too large), use runtimeCaching instead
        globIgnores: ['**/*.onnx', '**/*.wasm', '**/ort.*.js'],

        // Runtime caching strategies
        runtimeCaching: [
          // WASM/ONNX assets - CacheFirst with 7-day expiration
          {
            urlPattern: /\.(wasm|onnx)$/,
            handler: 'CacheFirst',
            options: {
              cacheName: 'vitalnet-ml-assets',
              expiration: {
                maxAgeSeconds: 7 * 24 * 60 * 60, // 7 days
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
                  maxRetentionTime: 24 * 60,  // 24 hours in minutes
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
      '/api': 'http://localhost:8000'
    }
  }
})
