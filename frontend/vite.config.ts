import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// The FastAPI backend (backend/main.py, `uvicorn main:app --port 8000`) serves products,
// images, accounts and the chat. Requests to /api and /media are forwarded to it, so the
// browser sees one origin and the HttpOnly session cookie just works.
const backendUrl = process.env.BACKEND_URL ?? 'http://127.0.0.1:8000'

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': backendUrl,
      '/media': backendUrl,
    },
  },
})
