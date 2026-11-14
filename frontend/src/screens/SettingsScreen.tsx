import { useEffect, useState } from 'react'
import Logo from '../components/Logo'
import {
  clearToken,
  readClinicianEmail,
  readThemePreference,
  readToken,
  readUserProfile,
  saveThemePreference,
  type ThemePreference,
} from '../session'

function SettingsScreen() {
  const patientProfile = readUserProfile('patient')
  const helperProfile = readUserProfile('helper')
  const hasPatient = readToken('patient') !== null
  const hasHelper = readToken('helper') !== null
  const clinicianEmail = readClinicianEmail() ?? 'dr.virtanen@helsinki-tms.fi'

  const [theme, setTheme] = useState<ThemePreference>(readThemePreference)
  const [telemetryEnabled, setTelemetryEnabled] = useState(true)
  const [notificationsEnabled, setNotificationsEnabled] = useState(true)
  const [smartGuardrail, setSmartGuardrail] = useState(true)

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

  function handleLeaveAll() {
    if (
      confirm(
        'Voulez-vous vous déconnecter de tous vos comptes sur cet appareil ?',
      )
    ) {
      clearToken('helper')
      clearToken('patient')
      window.location.hash = '#/'
      window.location.reload()
    }
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
          <p className="eyebrow">Préférences de l'application</p>
          <h1>Paramètres</h1>
          <p className="quiet">
            Gérez vos comptes, votre confort visuel et votre confidentialité
            médicale.
          </p>
        </section>

        {/* Section Apparence & Thème */}
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

        {/* Section Comptes actifs */}
        <section className="settings-card stack">
          <h2>Profils & Comptes actifs</h2>
          {hasHelper && (
            <div className="settings-account-row">
              <div className="settings-avatar-wrap">
                {helperProfile?.avatarUrl ? (
                  <img
                    src={helperProfile.avatarUrl}
                    alt="Helper"
                    className="topbar-avatar"
                  />
                ) : (
                  <div className="avatar-preview-placeholder">A</div>
                )}
              </div>
              <div className="settings-account-info">
                <strong>
                  {helperProfile
                    ? `${helperProfile.firstName} ${helperProfile.lastName}`
                    : 'Aidant actif'}
                </strong>
                <span className="quiet font-small">
                  Rôle : Aidant (Helper) · {helperProfile?.city || 'Helsinki'}
                </span>
              </div>
              <a href="#/helper" className="button button-ghost button-small">
                Ouvrir
              </a>
            </div>
          )}

          {hasPatient && (
            <div className="settings-account-row">
              <div className="settings-avatar-wrap">
                <img
                  src={patientProfile?.avatarUrl ?? '/moomins/Muumipeikko2.jpg'}
                  alt="Patient"
                  className="topbar-avatar"
                />
              </div>
              <div className="settings-account-info">
                <strong>
                  {patientProfile
                    ? `${patientProfile.firstName} ${patientProfile.lastName}`
                    : 'Patient suivi'}
                </strong>
                <span className="quiet font-small">
                  Rôle : Patient · Suivi :{' '}
                  {patientProfile?.clinicianEmail || clinicianEmail}
                </span>
              </div>
              <a href="#/patient" className="button button-ghost button-small">
                Ouvrir
              </a>
            </div>
          )}

          {!hasHelper && !hasPatient && (
            <p className="quiet font-small">
              Aucun profil connecté sur cet appareil.
            </p>
          )}
        </section>

        {/* Confidentialité & Télémétrie clinique */}
        <section className="settings-card stack">
          <h2>Confidentialité & Suivi post-TMS</h2>
          <label className="toggle-row">
            <div>
              <strong>Télémétrie passive discrète</strong>
              <p className="quiet font-small">
                Transmet les signaux de réciprocité positive (θ) à votre
                clinicien sans questionnaires invasifs.
              </p>
            </div>
            <input
              type="checkbox"
              checked={telemetryEnabled}
              onChange={(e) => setTelemetryEnabled(e.target.checked)}
            />
          </label>

          <label className="toggle-row">
            <div>
              <strong>Garde-fou d'effort (Safety Zone)</strong>
              <p className="quiet font-small">
                Filtre automatiquement les demandes exigeantes si votre réserve
                d'énergie baisse.
              </p>
            </div>
            <input
              type="checkbox"
              checked={smartGuardrail}
              onChange={(e) => setSmartGuardrail(e.target.checked)}
            />
          </label>
        </section>

        {/* Notifications */}
        <section className="settings-card stack">
          <h2>Notifications & Entraide</h2>
          <label className="toggle-row">
            <div>
              <strong>Demandes de la communauté</strong>
              <p className="quiet font-small">
                Recevoir une notification lorsqu'un voisin a besoin d'un coup de
                main.
              </p>
            </div>
            <input
              type="checkbox"
              checked={notificationsEnabled}
              onChange={(e) => setNotificationsEnabled(e.target.checked)}
            />
          </label>
        </section>

        {/* Espace Clinicien direct */}
        <section className="settings-card stack">
          <h2>Espace Médical (Réservé soignants)</h2>
          <p className="quiet font-small">
            Accès sécurisé pour les médecins et thérapeutes chargés du suivi de
            rémission post-TMS.
          </p>
          <a href="#/clinician" className="button button-ghost button-wide">
            Accéder au Portail Clinicien
          </a>
        </section>

        {/* Espace Administrateur direct */}
        <section className="settings-card stack">
          <h2>Administration & Supervision</h2>
          <p className="quiet font-small">
            Gestion globale des utilisateurs, supervision des liaisons d'aide et
            suivi des questions en cours ou résolues.
          </p>
          <a href="#/admin" className="button button-ghost button-wide">
            🛡️ Accéder à l'Espace Administrateur
          </a>
        </section>

        {/* Actions de compte */}
        <div className="settings-footer-actions stack">
          {(hasHelper || hasPatient) && (
            <button
              type="button"
              className="button button-wide"
              onClick={handleLeaveAll}
            >
              Déconnexion complète de cet appareil
            </button>
          )}
          <p className="quiet font-small text-center">
            Needed v1.2 · Junction 2026 rTMS Recovery Network
          </p>
        </div>
      </main>
    </div>
  )
}

export default SettingsScreen
