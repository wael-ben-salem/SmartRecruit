import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// In development (npm run dev) the API runs on :8000; in production FastAPI serves dist/ itself.
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': 'http://localhost:8000',
      '/runs': 'http://localhost:8000',
    },
  },
})
