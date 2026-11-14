import type { ReactNode } from 'react'
import Logo from '../components/Logo'

type ScreenFrameProps = {
  // Prénom affiché à droite, avec un lien pour quitter ce compte sur cet appareil.
  name?: string
  onLeave?: () => void
  children: ReactNode
}

// Cadre des écrans de la vraie app : une colonne étroite, pensée pour le téléphone.
function ScreenFrame({ name, onLeave, children }: ScreenFrameProps) {
  return (
    <div className="screen">
      <header className="topbar">
        <a className="brand" href="#/">
          <Logo size={30} />
          <span className="brand-name">needed</span>
        </a>
        {name && (
          <div className="who">
            <span>{name}</span>
            {onLeave && (
              <button type="button" className="link" onClick={onLeave}>
                Leave
              </button>
            )}
          </div>
        )}
      </header>
      {children}
    </div>
  )
}

export default ScreenFrame
