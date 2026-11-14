import { useEffect, useRef, useState } from 'react'
import Logo from '../components/Logo'
import {
  type AdminContactMessage,
  type ThemePreference,
  readThemePreference,
  readUserProfile,
  saveAdminContactMessage,
  saveThemePreference,
} from '../session'

type CategoryOption = {
  value: 'bug' | 'question' | 'suggestion' | 'other'
  icon: string
  label: string
  description: string
}

const CATEGORIES: CategoryOption[] = [
  {
    value: 'bug',
    icon: '🐞',
    label: 'Report a bug',
    description: 'Notice an error, crash, or unexpected behavior',
  },
  {
    value: 'question',
    icon: '❓',
    label: 'Ask a question',
    description: 'Need clarification on how peer exchanges work',
  },
  {
    value: 'suggestion',
    icon: '💡',
    label: 'Feature suggestion',
    description: 'Share ideas to improve your daily recovery experience',
  },
  {
    value: 'other',
    icon: '📝',
    label: 'General feedback',
    description: 'Any other remark or thought for the administration',
  },
]

function SettingsScreen() {
  const [theme, setTheme] = useState<ThemePreference>(readThemePreference)

  const helperProfile = readUserProfile('helper')
  const patientProfile = readUserProfile('patient')
  const activeProfile = helperProfile || patientProfile

  const [category, setCategory] = useState<
    'bug' | 'question' | 'suggestion' | 'other'
  >('bug')
  const [isDropdownOpen, setIsDropdownOpen] = useState(false)
  const dropdownRef = useRef<HTMLDivElement>(null)

  const [message, setMessage] = useState('')
  const [sentSuccess, setSentSuccess] = useState(false)

  useEffect(() => {
    document.title = 'Needed · Settings'
    return () => {
      document.title = 'Needed'
    }
  }, [])

  // Close dropdown on outside click
  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (
        dropdownRef.current &&
        !dropdownRef.current.contains(e.target as Node)
      ) {
        setIsDropdownOpen(false)
      }
    }
    if (isDropdownOpen) {
      document.addEventListener('mousedown', handleClickOutside)
    }
    return () => {
      document.removeEventListener('mousedown', handleClickOutside)
    }
  }, [isDropdownOpen])

  function handleThemeChange(newTheme: ThemePreference) {
    setTheme(newTheme)
    saveThemePreference(newTheme)
  }

  function handleSendMessage(e: React.FormEvent) {
    e.preventDefault()
    if (!message.trim()) return

    const newMessage: AdminContactMessage = {
      id: `admin-msg-${Date.now()}`,
      senderName: activeProfile
        ? `${activeProfile.firstName} ${activeProfile.lastName}`.trim()
        : 'Community Member',
      senderRole: helperProfile
        ? 'helper'
        : patientProfile
          ? 'patient'
          : 'visitor',
      category,
      message: message.trim(),
      timestamp: new Date().toLocaleTimeString('en-US', {
        hour: '2-digit',
        minute: '2-digit',
        hour12: false,
      }),
      resolved: false,
    }

    saveAdminContactMessage(newMessage)
    setMessage('')
    setIsDropdownOpen(false)
    setSentSuccess(true)
    setTimeout(() => {
      setSentSuccess(false)
    }, 4000)
  }

  const selectedCategory =
    CATEGORIES.find((c) => c.value === category) || CATEGORIES[0]

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
          aria-label="Back"
          title="Back"
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
          <h1>Settings</h1>
        </section>

        {/* 1. Theme Mode: Light / Dark / Auto */}
        <section className="settings-card stack">
          <h2>Appearance</h2>
          <div
            className="theme-segmented-control"
            role="radiogroup"
            aria-label="Color Theme"
          >
            {/* Sliding glider */}
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
              <span>Light</span>
            </button>
            <button
              type="button"
              role="radio"
              aria-checked={theme === 'dark'}
              className={`theme-segmented-btn ${theme === 'dark' ? 'active' : ''}`}
              onClick={() => handleThemeChange('dark')}
            >
              <span>Dark</span>
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

        {/* 2. Form to contact administrator */}
        <section className="settings-card stack">
          <div className="settings-section-header text-center">
            <h2>Contact Administrator</h2>
            <p className="quiet font-small settings-section-desc">
              Encountered a bug or have a suggestion? Send a direct note to the
              administrative team.
            </p>
          </div>

          <form
            onSubmit={handleSendMessage}
            className="stack"
            style={{ gap: '16px' }}
          >
            {/* Beautiful custom dropdown */}
            <div className="settings-field-group">
              <label
                id="category-dropdown-label"
                className="field-label block font-small"
                style={{ marginBottom: '6px', fontWeight: 600 }}
              >
                Topic & Category
              </label>

              <div className="custom-select-wrap" ref={dropdownRef}>
                <button
                  type="button"
                  id="category-dropdown-trigger"
                  aria-haspopup="listbox"
                  aria-expanded={isDropdownOpen}
                  aria-labelledby="category-dropdown-label category-dropdown-trigger"
                  className={`custom-select-trigger ${isDropdownOpen ? 'open' : ''}`}
                  onClick={() => setIsDropdownOpen((prev) => !prev)}
                >
                  <div className="custom-select-selected-content">
                    <span className="custom-select-icon">
                      {selectedCategory.icon}
                    </span>
                    <div className="custom-select-labels">
                      <strong className="custom-select-title">
                        {selectedCategory.label}
                      </strong>
                      <span className="custom-select-subtitle quiet font-small">
                        {selectedCategory.description}
                      </span>
                    </div>
                  </div>

                  <span
                    className={`custom-select-chevron ${isDropdownOpen ? 'open' : ''}`}
                    aria-hidden="true"
                  >
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
                      <polyline points="6 9 12 15 18 9" />
                    </svg>
                  </span>
                </button>

                {isDropdownOpen && (
                  <div
                    className="custom-select-menu"
                    role="listbox"
                    aria-labelledby="category-dropdown-label"
                  >
                    {CATEGORIES.map((cat) => {
                      const isSelected = cat.value === category
                      return (
                        <div
                          key={cat.value}
                          role="option"
                          aria-selected={isSelected}
                          tabIndex={0}
                          className={`custom-select-option ${isSelected ? 'selected' : ''}`}
                          onClick={() => {
                            setCategory(cat.value)
                            setIsDropdownOpen(false)
                          }}
                          onKeyDown={(e) => {
                            if (e.key === 'Enter' || e.key === ' ') {
                              e.preventDefault()
                              setCategory(cat.value)
                              setIsDropdownOpen(false)
                            }
                          }}
                        >
                          <div className="custom-select-option-info">
                            <span className="custom-select-icon">
                              {cat.icon}
                            </span>
                            <div>
                              <strong className="custom-select-opt-label">
                                {cat.label}
                              </strong>
                              <span className="quiet font-small block">
                                {cat.description}
                              </span>
                            </div>
                          </div>
                          {isSelected && (
                            <span
                              className="custom-select-check"
                              aria-hidden="true"
                            >
                              ✓
                            </span>
                          )}
                        </div>
                      )
                    })}
                  </div>
                )}
              </div>
            </div>

            {/* Message input */}
            <div className="settings-field-group">
              <label
                htmlFor="admin-msg-text"
                className="field-label block font-small"
                style={{ marginBottom: '6px', fontWeight: 600 }}
              >
                Message
              </label>
              <textarea
                id="admin-msg-text"
                rows={4}
                value={message}
                placeholder="Describe the issue or share your thoughts in detail..."
                className="settings-textarea"
                onChange={(e) => setMessage(e.target.value)}
                required
              />
            </div>

            {/* Centered button */}
            <div
              className="settings-submit-wrap"
              style={{
                display: 'flex',
                justifyContent: 'center',
                marginTop: '4px',
              }}
            >
              <button
                type="submit"
                className="button button-primary button-wide settings-submit-btn"
                disabled={!message.trim()}
              >
                Send to Administrator
              </button>
            </div>

            {sentSuccess && (
              <div
                className="settings-success-badge"
                role="status"
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: '8px',
                  padding: '12px 14px',
                  borderRadius: '12px',
                  textAlign: 'center',
                  fontWeight: 600,
                  fontSize: '0.9rem',
                }}
              >
                <span>✓</span>
                <span>Your message has been sent to the administrator.</span>
              </div>
            )}
          </form>
        </section>

        {/* 3. Application version & details */}
        <section className="settings-card stack">
          <h2>Application Information</h2>
          <div
            className="version-info-box"
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              padding: '12px 14px',
              background: 'var(--bg)',
              border: '1px solid var(--line)',
              borderRadius: '12px',
            }}
          >
            <div>
              <strong style={{ fontSize: '0.95rem' }}>Needed</strong>
              <p className="quiet font-small" style={{ margin: 0 }}>
                rTMS Recovery Peer Network · Junction 2026
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
