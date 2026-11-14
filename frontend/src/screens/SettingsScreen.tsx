import { useEffect, useState } from 'react'
import Logo from '../components/Logo'
import {
  type AdminContactMessage,
  type ThemePreference,
  readThemePreference,
  readUserProfile,
  saveAdminContactMessage,
  saveThemePreference,
} from '../session'

function SettingsScreen() {
  const [theme, setTheme] = useState<ThemePreference>(readThemePreference)

  // Utilisateur connecté pour pré-remplir le nom
  const helperProfile = readUserProfile('helper')
  const patientProfile = readUserProfile('patient')
  const activeProfile = helperProfile || patientProfile

  const [senderName, setSenderName] = useState(
    activeProfile
      ? `${activeProfile.firstName} ${activeProfile.lastName}`.trim()
      : '',
  )
  const [category, setCategory] = useState<
    'bug' | 'question' | 'suggestion' | 'other'
  >('bug')
  const [message, setMessage] = useState('')
  const [sentSuccess, setSentSuccess] = useState(false)

  useEffect(() => {
    document.title = 'Needed · Paramètres'
    return () => {
      document.title = 'Needed'
    }
  }, [])

  function handleThemeChange(newTheme: ThemePreference) {
    setTheme(newTheme)
    saveThemePreference(newTheme)
  }

  function handleSendMessage(e: React.FormEvent) {
    e.preventDefault()
    if (!message.trim()) return

    const newMessage: AdminContactMessage = {
      id: `admin-msg-${Date.now()}`,
      senderName: senderName.trim() || 'Utilisateur anonyme',
      senderRole: helperProfile
        ? 'helper'
        : patientProfile
          ? 'patient'
          : 'visitor',
      category,
      message: message.trim(),
      timestamp: new Date().toLocaleTimeString('fr-FR', {
        hour: '2-digit',
        minute: '2-digit',
      }),
      resolved: false,
    }

    saveAdminContactMessage(newMessage)
    setMessage('')
    setSentSuccess(true)
    setTimeout(() => {
      setSentSuccess(false)
    }, 4000)
  }

  return (
    <div className="screen settings-screen">
      <header className="topbar">
        <a className="brand" href="#/">
          <Logo size={36} />
          <span className="brand-name">Needed</span>
        </a>
        <button
          type="button"
          onClick={() => window.history.back()}
          className="settings-back-btn"
          aria-label="Retour"
          title="Retour"
        >
          <span className="icon-close" aria-hidden="true">
            <svg
              width="18"
              height="18"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2.5"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <line x1="18" y1="6" x2="6" y2="18" />
              <line x1="6" y1="6" x2="18" y2="18" />
            </svg>
          </span>
          <span className="icon-arrow" aria-hidden="true">
            <svg
              width="20"
              height="20"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2.5"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <line x1="19" y1="12" x2="5" y2="12" />
              <polyline points="12 19 5 12 12 5" />
            </svg>
          </span>
        </button>
      </header>

      <main className="stack settings-main">
        <section className="settings-hero">
          <p className="eyebrow">Préférences &amp; Assistance</p>
          <h1>Paramètres</h1>
        </section>

        {/* 1. Mode Jour / Nuit / Auto */}
        <section className="settings-card stack">
          <h2>Apparence</h2>
          <div
            className="theme-segmented-control"
            role="radiogroup"
            aria-label="Thème visuel"
          >
            {/* Curseur glissant animé */}
            <div
              className={`theme-sliding-glider theme-glider-${theme}`}
              aria-hidden="true"
            />
            <button
              type="button"
              role="radio"
              aria-checked={theme === 'light'}
              className={`theme-segmented-btn ${theme === 'light' ? 'active' : ''}`}
              onClick={() => handleThemeChange('light')}
            >
              <span>Jour</span>
            </button>
            <button
              type="button"
              role="radio"
              aria-checked={theme === 'dark'}
              className={`theme-segmented-btn ${theme === 'dark' ? 'active' : ''}`}
              onClick={() => handleThemeChange('dark')}
            >
              <span>Nuit</span>
            </button>
            <button
              type="button"
              role="radio"
              aria-checked={theme === 'auto'}
              className={`theme-segmented-btn ${theme === 'auto' ? 'active' : ''}`}
              onClick={() => handleThemeChange('auto')}
            >
              <span>Auto</span>
            </button>
          </div>
        </section>

        {/* 2. Formulaire pour envoyer un message à l'administrateur */}
        <section className="settings-card stack">
          <h2>Message à l'administrateur</h2>
          <p className="quiet font-small">
            Un bug, une anomalie ou une suggestion ? Transmettez directement
            votre message à l'équipe d'administration.
          </p>

          <form
            onSubmit={handleSendMessage}
            className="stack"
            style={{ gap: '12px' }}
          >
            <div>
              <label
                htmlFor="admin-msg-category"
                className="field-label block font-small"
                style={{ marginBottom: '6px' }}
              >
                Motif
              </label>
              <select
                id="admin-msg-category"
                value={category}
                onChange={(e) =>
                  setCategory(
                    e.target.value as
                      'bug' | 'question' | 'suggestion' | 'other',
                  )
                }
                className="select-field"
                style={{ width: '100%' }}
              >
                <option value="bug">🐛 Signaler un bug</option>
                <option value="question">❓ Poser une question</option>
                <option value="suggestion">💡 Suggestion d'amélioration</option>
                <option value="other">💬 Autre remarque</option>
              </select>
            </div>

            <div>
              <label
                htmlFor="admin-msg-sender"
                className="field-label block font-small"
                style={{ marginBottom: '6px' }}
              >
                Votre nom
              </label>
              <input
                id="admin-msg-sender"
                type="text"
                value={senderName}
                placeholder="Votre nom ou pseudonyme"
                className="input-field"
                style={{ width: '100%' }}
                onChange={(e) => setSenderName(e.target.value)}
              />
            </div>

            <div>
              <label
                htmlFor="admin-msg-text"
                className="field-label block font-small"
                style={{ marginBottom: '6px' }}
              >
                Message
              </label>
              <textarea
                id="admin-msg-text"
                rows={4}
                value={message}
                placeholder="Décrivez précisément le bug rencontré ou votre message..."
                className="chat-input-field"
                style={{
                  width: '100%',
                  resize: 'vertical',
                  minHeight: '90px',
                  boxSizing: 'border-box',
                }}
                onChange={(e) => setMessage(e.target.value)}
                required
              />
            </div>

            <button
              type="submit"
              className="button button-wide"
              disabled={!message.trim()}
            >
              Envoyer à l'administrateur
            </button>

            {sentSuccess && (
              <div
                className="feedback-badge"
                role="status"
                style={{
                  background: '#e8f5e9',
                  color: '#0b6938',
                  padding: '10px 14px',
                  borderRadius: '10px',
                  textAlign: 'center',
                  fontWeight: 600,
                }}
              >
                ✓ Votre message a bien été transmis à l'administrateur !
              </div>
            )}
          </form>
        </section>

        {/* 3. Numéro de version de l'app */}
        <section className="settings-card stack">
          <h2>Version de l'application</h2>
          <div
            className="version-info-box"
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              padding: '12px 14px',
              background: 'var(--bg)',
              border: '1px solid var(--line)',
              borderRadius: '10px',
            }}
          >
            <div>
              <strong style={{ fontSize: '0.95rem' }}>Needed</strong>
              <p className="quiet font-small" style={{ margin: 0 }}>
                Réseau d'entraide post-rTMS · Junction 2026
              </p>
            </div>
            <span
              style={{
                fontWeight: 700,
                padding: '4px 10px',
                background: 'rgba(0, 216, 255, 0.15)',
                color: 'var(--cyan-deep)',
                borderRadius: '999px',
                fontSize: '0.85rem',
              }}
            >
              v1.2.0
            </span>
          </div>
        </section>
      </main>
    </div>
  )
}

export default SettingsScreen
