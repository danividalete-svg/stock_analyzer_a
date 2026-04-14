import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { VitePWA } from 'vite-plugin-pwa'
import { visualizer } from 'rollup-plugin-visualizer'
import path from 'node:path'

export default defineConfig(({ mode }) => ({
  plugins: [
    react({
      babel: {
        // React Compiler: memoización automática de todos los componentes
        plugins: [['babel-plugin-react-compiler', {}]],
      },
    }),
    tailwindcss(),
    VitePWA({
      registerType: 'autoUpdate',
      injectRegister: 'auto',
      // Usar el manifest.json existente en public/
      manifest: false,
      workbox: {
        globPatterns: ['**/*.{js,css,html,ico,png,svg,woff2}'],
        navigateFallback: '/stock_analyzer_a/app/index.html',
        navigateFallbackDenylist: [/^\/api\//, /^\/stock_analyzer_a\/(?!app\/)/],
        runtimeCaching: [
          {
            // CSV/JSON de GitHub Pages — StaleWhileRevalidate: devuelve cache inmediato,
            // actualiza en background. El usuario siempre ve datos, nunca spinner.
            urlPattern: /^https:\/\/tantancansado\.github\.io\/stock_analyzer_a\/.*\.(csv|json)$/,
            handler: 'StaleWhileRevalidate',
            options: {
              cacheName: 'csv-data-v1',
              expiration: { maxEntries: 50, maxAgeSeconds: 60 * 60 * 2 },
              cacheableResponse: { statuses: [0, 200] },
            },
          },
          {
            // Railway API — NetworkFirst con fallback a cache (5s timeout)
            urlPattern: /railway\.app\/api\//,
            handler: 'NetworkFirst',
            options: {
              cacheName: 'api-v1',
              networkTimeoutSeconds: 5,
              expiration: { maxEntries: 30, maxAgeSeconds: 5 * 60 },
              cacheableResponse: { statuses: [0, 200] },
            },
          },
        ],
      },
    }),
    // Activar con: vite build --mode analyze
    mode === 'analyze' && visualizer({
      open: true,
      filename: '../docs/app/stats.html',
      gzipSize: true,
      brotliSize: true,
    }),
  ].filter(Boolean),
  resolve: {
    alias: { '@': path.resolve(__dirname, './src') },
  },
  server: {
    proxy: {
      '/api': {
        target: 'http://localhost:5002',
        changeOrigin: true,
      },
    },
  },
  base: '/stock_analyzer_a/app/',
  build: {
    outDir: '../docs/app',
    emptyOutDir: true,
    rollupOptions: {
      output: {
        manualChunks: {
          // Remotion (~500KB) — solo páginas de video
          'remotion': ['remotion', '@remotion/player'],
          // Recharts — solo PriceChart
          'recharts': ['recharts'],
          // Supabase — solo al autenticar
          'supabase': ['@supabase/supabase-js'],
          // Motion — animaciones, compartido
          'motion': ['motion'],
        },
      },
    },
  },
}))
