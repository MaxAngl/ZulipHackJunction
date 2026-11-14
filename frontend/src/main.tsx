import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx'
import { applyTheme, readThemePreference } from './session'

// Initialiser le thème (auto / clair / nuit) dès le chargement
applyTheme(readThemePreference())

// Écouter les changements système si mode auto
if (window.matchMedia) {
  window
    .matchMedia('(prefers-color-scheme: dark)')
    .addEventListener('change', () => {
      if (readThemePreference() === 'auto') {
        applyTheme('auto')
      }
    })
}

// Enregistrer le Service Worker pour le support PWA (installation mobile)
if (
  'serviceWorker' in navigator &&
  window.location.protocol.startsWith('http')
) {
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('/sw.js').catch((err) => {
      console.log('SW registration error:', err)
    })
  })
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
