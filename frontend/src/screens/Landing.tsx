import { useState } from 'react'
import type { SessionResponse } from '../api/client'
import Logo from '../components/Logo'
import QuickLoginModal from '../components/QuickLoginModal'
import ScreenFrame from './ScreenFrame'

type LandingProps = {
  onSignedIn?: (session: SessionResponse) => void
}

// Page d'entrée de la vraie app : deux chemins, et une fenêtre d'information pour les patients de clinique.
function Landing({ onSignedIn }: LandingProps) {
  const [showInfo, setShowInfo] = useState(false)
  const [showQuickLogin, setShowQuickLogin] = useState(false)

  return (
    <ScreenFrame noHeader>
      <main className="stack hero">
        <div className="brand-hero">
          <Logo size={88} />
          <span className="brand-hero-name">Needed</span>
        </div>
        <h1>Helping others by answering their needs.</h1>
        <div className="stack">
          <a className="button button-primary button-wide" href="#/join/helper">
            Join the community
          </a>
          <a className="button button-wide" href="#/join/patient">
            My clinic invited me
          </a>
          <a className="button button-ghost button-wide" href="#/login">
            I already have an account
          </a>
          {onSignedIn && (
            <button
              type="button"
              className="button button-ghost button-wide button-quick-demo"
              onClick={() => setShowQuickLogin(true)}
            >
              ⚡ Connexion rapide (Démo)
            </button>
          )}
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

        {onSignedIn && (
          <QuickLoginModal
            isOpen={showQuickLogin}
            onClose={() => setShowQuickLogin(false)}
            onSignedIn={onSignedIn}
          />
        )}
      </main>
    </ScreenFrame>
  )
}

export default Landing
