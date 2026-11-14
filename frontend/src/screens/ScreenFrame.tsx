import type { ReactNode } from 'react'
import Logo from '../components/Logo'

type ScreenFrameProps = {
  // Prénom ou nom complet affiché à droite, avec avatar éventuel et lien pour quitter ce compte.
  name?: string
  avatarUrl?: string
  onLeave?: () => void
  hideLogo?: boolean
  noHeader?: boolean
  showSettings?: boolean
  bottomNav?: ReactNode
  children: ReactNode
}

// Cadre des écrans de la vraie app : une colonne étroite, pensée pour le téléphone.
function ScreenFrame({
  hideLogo = false,
  noHeader = false,
  showSettings = true,
  bottomNav,
  children,
}: ScreenFrameProps) {
  return (
    <div className={`screen ${bottomNav ? 'has-bottom-nav' : ''}`}>
      {!noHeader && (
        <header className="topbar">
          <a className="brand" href="#/">
            {!hideLogo && <Logo size={42} />}
            <span className="brand-name">Needed</span>
          </a>
          <div className="topbar-right">
            {showSettings && (
              <a
                href="#/settings"
                className="topbar-settings-btn"
                title="Settings"
                aria-label="Settings"
              >
                <svg
                  width="22"
                  height="22"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                >
                  <circle cx="12" cy="12" r="3" />
                  <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z" />
                </svg>
              </a>
            )}
          </div>
        </header>
      )}
      <div className="screen-body">{children}</div>
      {bottomNav}
    </div>
  )
}

export default ScreenFrame
