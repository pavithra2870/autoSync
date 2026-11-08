import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// In dev, Vite serves the UI on :5173 and forwards /api to FastAPI on :8000.
// In production, `npm run build` writes dist/ and FastAPI serves it from the same origin.
export default defineConfig({
  plugins: [react()],
  server: { port: 5173, proxy: { '/api': 'http://127.0.0.1:8000' } },
  build: { outDir: 'dist' },
})
