import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    port: 3000,
    headers: {
      'Cache-Control': 'no-cache, no-store, must-revalidate',
      'Pragma': 'no-cache',
      'Expires': '0'
    },
    proxy: {
      '/health': {
        target: 'http://localhost:8001',
        changeOrigin: true,
        secure: false,
        timeout: 60000,      // Proxy connection timeout (1 minute)
        proxyTimeout: 60000, // Proxy response timeout (1 minute)
      },
      '/api': {
        target: 'http://localhost:8001',
        changeOrigin: true,
        secure: false,
        timeout: 60000,      // Proxy connection timeout (1 minute)
        proxyTimeout: 60000, // Proxy response timeout (1 minute)
      },
      '/socket.io': {
        target: 'http://localhost:8001',
        changeOrigin: true,
        secure: false,
        ws: true,
        timeout: 60000,      // Proxy connection timeout (1 minute)
        proxyTimeout: 60000, // Proxy response timeout (1 minute)
      },
    },
  },
  build: {
    outDir: 'dist',
    sourcemap: true,
  },
})
