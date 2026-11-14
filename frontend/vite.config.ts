import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// Par défaut, le backend écoute sur le port 8000. Pour lancer une seconde copie de l'app à
// côté (autre branche, autre port), donner son adresse dans NEEDED_API_URL.
const api = process.env.NEEDED_API_URL ?? 'http://localhost:8000'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    // Le front appelle toujours des URLs relatives /api/... ; en dev, Vite les relaie au backend.
    proxy: {
      '/api': api,
    },
  },
})
