import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// In dev, proxy /api to the FastAPI backend so the frontend can use relative
// URLs (same as in production behind nginx). Override the target with
// VITE_API_TARGET if the backend runs elsewhere.
// Use 127.0.0.1 (not "localhost"): on Windows "localhost" can resolve to IPv6
// ::1 while uvicorn binds IPv4, which makes the proxy 500.
const API_TARGET = process.env.VITE_API_TARGET || 'http://127.0.0.1:8000'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': { target: API_TARGET, changeOrigin: true },
    },
  },
})
