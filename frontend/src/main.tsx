import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import './theme.css'
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

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
