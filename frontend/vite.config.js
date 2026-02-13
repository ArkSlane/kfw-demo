import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'
import path from 'path'

// https://vite.dev/config/
export default defineConfig({
  plugins: [
    react({
      fastRefresh: true,
    }),
  ],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    middlewareMode: false,
    allowedHosts: ['frontend', 'localhost', '127.0.0.1'],
    proxy: {
      '/svc/8001': { target: 'http://requirements:8000', changeOrigin: true, rewrite: p => p.replace(/^\/svc\/8001/, '') },
      '/svc/8002': { target: 'http://testcases:8000', changeOrigin: true, rewrite: p => p.replace(/^\/svc\/8002/, '') },
      '/svc/8003': { target: 'http://generator:8000', changeOrigin: true, rewrite: p => p.replace(/^\/svc\/8003/, '') },
      '/svc/8004': { target: 'http://releases:8000', changeOrigin: true, rewrite: p => p.replace(/^\/svc\/8004/, '') },
      '/svc/8005': { target: 'http://executions:8000', changeOrigin: true, rewrite: p => p.replace(/^\/svc\/8005/, '') },
      '/svc/8006': { target: 'http://automations:8000', changeOrigin: true, rewrite: p => p.replace(/^\/svc\/8006/, '') },
      '/svc/8007': { target: 'http://git:8000', changeOrigin: true, rewrite: p => p.replace(/^\/svc\/8007/, '') },
      '/svc/8008': { target: 'http://toabrkia:8000', changeOrigin: true, rewrite: p => p.replace(/^\/svc\/8008/, '') },
      '/svc/8009': { target: 'http://testcase-migration:8000', changeOrigin: true, rewrite: p => p.replace(/^\/svc\/8009/, '') },
    },
    hmr: {
      host: 'localhost',
      port: 5173,
      protocol: 'ws',
    },
    watch: {
      usePolling: true,
    },
    open: false,
    port: 5173,
    strictPort: false,
  },
  build: {
    sourcemap: false,
    minify: 'esbuild',
  },
});