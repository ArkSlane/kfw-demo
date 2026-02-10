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