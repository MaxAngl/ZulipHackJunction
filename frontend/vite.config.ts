import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    // Le front appelle toujours des URLs relatives /api/... ; en dev, Vite les relaie au backend.
    proxy: {
      '/api': 'http://localhost:8000',
    },
  },
})
