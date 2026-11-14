import { useState } from 'react'
import type { Role } from '../api/client'
import Logo from '../components/Logo'
import {
  loginToAccount,
  loginWithToken,
  readSavedAccounts,
  removeSavedAccount,
  setSimulationAccount,
  SIMULATION_ACCOUNTS,
  type SavedAccount,
} from '../session'
import ScreenFrame from './ScreenFrame'

type LandingProps = {
  onAccountSelected?: (role: Role, token: string) => void
}

// Page d'entrée de la vraie app : deux chemins, fenêtre d'information et modal de connexion/comptes enregistrés.
function Landing({ onAccountSelected }: LandingProps) {
  const [showInfo, setShowInfo] = useState(false)
  const [showSignIn, setShowSignIn] = useState(false)
  const [savedAccounts, setSavedAccounts] = useState<SavedAccount[]>(() =>
    readSavedAccounts(),
  )
  const [demoRoleFilter, setDemoRoleFilter] = useState<
    'all' | 'helper' | 'patient'
  >('all')
  const [manualRole, setManualRole] = useState<Role>('helper')
  const [manualToken, setManualToken] = useState('')
  const [manualName, setManualName] = useState('')
  const [showManualLogin, setShowManualLogin] = useState(false)

  const refreshAccounts = () => {
    setSavedAccounts(readSavedAccounts())
  }

  const handleOpenSignIn = () => {
    refreshAccounts()
    setShowSignIn(true)
  }

  const handleSelectAccount = (account: SavedAccount) => {
    loginToAccount(account)
    onAccountSelected?.(account.role, account.token)
    window.location.hash = `#/${account.role}`
    setShowSignIn(false)
  }

  const handleRemoveAccount = (id: string, e: React.MouseEvent) => {
    e.stopPropagation()
    removeSavedAccount(id)
    refreshAccounts()
  }

  const handleSelectDemo = (accountId: string, role: Role, token: string) => {
    setSimulationAccount(accountId)
    onAccountSelected?.(role, token)
    window.location.hash = `#/${role}`
    setShowSignIn(false)
  }

  const handleManualLogin = (e: React.FormEvent) => {
    e.preventDefault()
    if (!manualToken.trim()) return
    loginWithToken(
      manualRole,
      manualToken.trim(),
      manualName.trim() || undefined,
    )
    onAccountSelected?.(manualRole, manualToken.trim())
    window.location.hash = `#/${manualRole}`
    setShowSignIn(false)
  }

  return (
    <ScreenFrame noHeader>
      <main className="stack hero">
        <div className="brand-hero">
          <Logo size={88} />
          <span className="brand-hero-name">Needed</span>
        </div>
        <h1>Helping others by answering their needs.</h1>
        <div className="stack">
          <a className="button button-primary button-wide" href="#/helper">
            Join the community
          </a>
          <a className="button button-wide" href="#/patient">
            My clinic invited me
          </a>
          <button
            type="button"
            className="button button-ghost button-wide landing-signin-btn"
            onClick={handleOpenSignIn}
          >
            🔑 Se connecter / Sign in
          </button>
        </div>
        <p className="lead">
          Needed is a community of people helping each other through the small
          tasks and simple gestures of everyday life.
        </p>

        <div className="info-action">
          <button
            type="button"
            className="button-info"
            onClick={() => setShowInfo(true)}
          >
            <span className="info-icon" aria-hidden="true">
              i
            </span>
            How it works for clinic patients
          </button>
        </div>

        <div className="landing-admin-action">
          <a
            href="#/admin"
            className="button-admin-pill"
            title="Access Administrator Portal"
          >
            <span className="admin-pill-icon">🛡️</span>
            <span>Admin Portal</span>
          </a>
        </div>

        {/* Modal Se connecter / Sign in */}
        {showSignIn && (
          <div
            className="modal-backdrop"
            role="dialog"
            aria-modal="true"
            aria-labelledby="signin-modal-title"
            onClick={() => setShowSignIn(false)}
          >
            <div
              className="modal-card modal-card-large stack"
              onClick={(event) => event.stopPropagation()}
            >
              <div className="modal-header">
                <span className="eyebrow">Connexion & Profils</span>
                <button
                  type="button"
                  className="modal-close"
                  aria-label="Close"
                  onClick={() => setShowSignIn(false)}
                >
                  ✕
                </button>
              </div>

              <h2 id="signin-modal-title" className="signin-modal-title">
                Se connecter à un compte
              </h2>

              <div className="modal-body stack signin-modal-body">
                {/* Section 1 : Comptes enregistrés sur cet appareil */}
                <div className="signin-section">
                  <div className="signin-section-header">
                    <span className="signin-section-title">
                      📱 Comptes enregistrés sur cet appareil
                    </span>
                    <span className="signin-count-badge">
                      {savedAccounts.length}
                    </span>
                  </div>

                  {savedAccounts.length === 0 ? (
                    <div className="signin-empty-card">
                      <p className="quiet font-small">
                        Aucun compte n'a encore été enregistré sur cet appareil.
                        Inscrivez-vous via « Join the community » ou
                        sélectionnez un profil de test ci-dessous.
                      </p>
                    </div>
                  ) : (
                    <div className="saved-accounts-list">
                      {savedAccounts.map((acc) => (
                        <div
                          key={acc.id}
                          className="saved-account-card"
                          onClick={() => handleSelectAccount(acc)}
                          role="button"
                          tabIndex={0}
                        >
                          <img
                            src={
                              acc.avatarUrl ||
                              (acc.role === 'patient'
                                ? '/moomins/Muumipeikko2.jpg'
                                : '/moomins/Characters-04-2.svg')
                            }
                            alt=""
                            className="saved-account-avatar"
                          />
                          <div className="saved-account-info">
                            <div className="saved-account-name-row">
                              <strong>{acc.name}</strong>
                              <span
                                className={`role-pill role-pill-${acc.role}`}
                              >
                                {acc.role === 'helper' ? 'Aidant' : 'Patient'}
                              </span>
                            </div>
                            {acc.city && (
                              <span className="saved-account-meta quiet font-small">
                                {acc.city}
                              </span>
                            )}
                          </div>
                          <div className="saved-account-actions">
                            <button
                              type="button"
                              className="button button-small button-primary"
                              onClick={(e) => {
                                e.stopPropagation()
                                handleSelectAccount(acc)
                              }}
                            >
                              Ouvrir
                            </button>
                            <button
                              type="button"
                              className="saved-account-delete-btn"
                              title="Supprimer de cet appareil"
                              aria-label="Supprimer du stockage de cet appareil"
                              onClick={(e) => handleRemoveAccount(acc.id, e)}
                            >
                              ✕
                            </button>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>

                {/* Section 2 : Profils de test & démonstration */}
                <div className="signin-section">
                  <div className="signin-section-header">
                    <span className="signin-section-title">
                      🧪 Profils de test & simulation
                    </span>
                  </div>
                  <p
                    className="quiet font-small"
                    style={{ margin: '0 0 10px 0' }}
                  >
                    Accédez directement en 1 clic aux profils préconfigurés de
                    la communauté.
                  </p>

                  <div className="demo-filter-tabs">
                    <button
                      type="button"
                      className={`demo-filter-pill ${demoRoleFilter === 'all' ? 'active' : ''}`}
                      onClick={() => setDemoRoleFilter('all')}
                    >
                      Tous ({SIMULATION_ACCOUNTS.length})
                    </button>
                    <button
                      type="button"
                      className={`demo-filter-pill ${demoRoleFilter === 'helper' ? 'active' : ''}`}
                      onClick={() => setDemoRoleFilter('helper')}
                    >
                      Aidants (3)
                    </button>
                    <button
                      type="button"
                      className={`demo-filter-pill ${demoRoleFilter === 'patient' ? 'active' : ''}`}
                      onClick={() => setDemoRoleFilter('patient')}
                    >
                      Patients (3)
                    </button>
                  </div>

                  <div className="demo-accounts-grid">
                    {SIMULATION_ACCOUNTS.filter(
                      (acc) =>
                        demoRoleFilter === 'all' || acc.role === demoRoleFilter,
                    ).map((acc) => (
                      <div
                        key={acc.id}
                        className="demo-account-item"
                        onClick={() =>
                          handleSelectDemo(acc.id, acc.role, acc.token)
                        }
                        role="button"
                        tabIndex={0}
                      >
                        <img
                          src={
                            acc.avatarUrl ||
                            (acc.role === 'patient'
                              ? '/moomins/Muumipeikko2.jpg'
                              : '/moomins/Characters-04-2.svg')
                          }
                          alt=""
                          className="demo-account-avatar"
                        />
                        <div className="demo-account-details">
                          <div className="demo-account-top">
                            <strong>
                              {acc.firstName} {acc.lastName}
                            </strong>
                            <span className={`role-pill role-pill-${acc.role}`}>
                              {acc.role === 'helper' ? 'Aidant' : 'Patient'}
                            </span>
                          </div>
                          <span className="demo-account-city quiet font-small">
                            {acc.city}
                          </span>
                          <div className="demo-account-tags">
                            {acc.interests.slice(0, 2).map((item) => (
                              <span key={item} className="demo-tag">
                                {item}
                              </span>
                            ))}
                          </div>
                        </div>
                        <button
                          type="button"
                          className="button button-small button-ghost demo-login-btn"
                          onClick={(e) => {
                            e.stopPropagation()
                            handleSelectDemo(acc.id, acc.role, acc.token)
                          }}
                        >
                          Tester
                        </button>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Section 3 : Connexion manuelle par jeton */}
                <div className="signin-section">
                  <button
                    type="button"
                    className="button-toggle-manual"
                    onClick={() => setShowManualLogin((prev) => !prev)}
                  >
                    <span>⚙️ Connexion manuelle par jeton (avancé)</span>
                    <span className="toggle-chevron">
                      {showManualLogin ? '▲' : '▼'}
                    </span>
                  </button>

                  {showManualLogin && (
                    <form
                      onSubmit={handleManualLogin}
                      className="manual-login-form stack-compact"
                    >
                      <label className="field-group">
                        <span className="field-label">Rôle</span>
                        <select
                          value={manualRole}
                          onChange={(e) =>
                            setManualRole(e.target.value as Role)
                          }
                          className="select-field"
                        >
                          <option value="helper">Aidant (Helper)</option>
                          <option value="patient">Patient clinique</option>
                        </select>
                      </label>
                      <label className="field-group">
                        <span className="field-label">
                          Jeton d'accès (Token)
                        </span>
                        <input
                          type="text"
                          value={manualToken}
                          onChange={(e) => setManualToken(e.target.value)}
                          placeholder="ex: token-helper-clara-1234"
                          className="input-field"
                          required
                        />
                      </label>
                      <label className="field-group">
                        <span className="field-label">
                          Nom d'affichage (optionnel)
                        </span>
                        <input
                          type="text"
                          value={manualName}
                          onChange={(e) => setManualName(e.target.value)}
                          placeholder="ex: Julien"
                          className="input-field"
                        />
                      </label>
                      <button
                        type="submit"
                        className="button button-primary button-wide"
                        style={{ marginTop: '8px' }}
                      >
                        Valider et se connecter
                      </button>
                    </form>
                  )}
                </div>
              </div>

              <button
                type="button"
                className="button button-ghost button-wide"
                onClick={() => setShowSignIn(false)}
              >
                Fermer
              </button>
            </div>
          </div>
        )}

        {/* Modal Information Clinique */}
        {showInfo && (
          <div
            className="modal-backdrop"
            role="dialog"
            aria-modal="true"
            aria-labelledby="info-modal-title"
            onClick={() => setShowInfo(false)}
          >
            <div
              className="modal-card stack"
              onClick={(event) => event.stopPropagation()}
            >
              <div className="modal-header">
                <span className="eyebrow">Clinic Patient Information</span>
                <button
                  type="button"
                  className="modal-close"
                  aria-label="Close"
                  onClick={() => setShowInfo(false)}
                >
                  ✕
                </button>
              </div>

              <h2 id="info-modal-title">
                Recovery through reciprocal community
              </h2>

              <div className="modal-body stack">
                <p>
                  <strong>Invited after treatment:</strong> If your depression
                  clinic or TMS centre invited you, you are in the crucial
                  remission maintenance phase.
                </p>
                <p>
                  <strong>No intrusive questions:</strong> We will never ask you
                  daily mood scores or clinical surveys that trigger anxiety.
                </p>
                <p>
                  <strong>You are the one who helps:</strong> When someone in
                  the community has a small, low-effort question (baking, books,
                  gardening), our AI ensures it matches your current comfort
                  zone.
                </p>
                <p>
                  <strong>Clinician continuity:</strong> Your clinician remains
                  discreetly connected in the background to ensure steady,
                  empowering progress without therapeutic pressure.
                </p>
              </div>

              <button
                type="button"
                className="button button-primary button-wide"
                onClick={() => setShowInfo(false)}
              >
                Got it
              </button>
            </div>
          </div>
        )}
      </main>
    </ScreenFrame>
  )
}

export default Landing
