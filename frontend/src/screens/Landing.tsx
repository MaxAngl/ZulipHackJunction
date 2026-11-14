import { useState } from 'react'
import type { SessionResponse } from '../api/client'
import Logo from '../components/Logo'
import QuickLoginModal from '../components/QuickLoginModal'
import ScreenFrame from './ScreenFrame'

type LandingProps = {
  onSignedIn?: (session: SessionResponse) => void
}

// Page d'entrée de la vraie app : parcours aidant, patient, connexion et accès démo rapide.
function Landing({ onSignedIn }: LandingProps) {
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
              className="button-quick-demo"
              onClick={() => setShowQuickLogin(true)}
            >
              Try a demo account
            </button>
          )}
        </div>
        <p className="lead">
          Needed is a community of people helping each other through the small
          tasks and simple gestures of everyday life.
        </p>

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
