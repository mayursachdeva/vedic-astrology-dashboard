import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    // Proxy keeps the browser on one origin, so the API needs no CORS in normal use.
    proxy: { '/api': 'http://127.0.0.1:8000' },
  },
})
