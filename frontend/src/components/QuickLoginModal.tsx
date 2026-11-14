import { useState } from 'react'
import {
  ApiError,
  login,
  type AccountRole,
  type SessionResponse,
} from '../api/client'

export type QuickPerson = {
  id: string
  role: AccountRole
  email: string
  name: string
  roleLabel: string
  city?: string
  avatarUrl: string
  badgeClass: string
  interests?: string[]
  bio: string
}

export const DEMO_PEOPLE: QuickPerson[] = [
  // Aidants (Helpers)
  {
    id: 'clara',
    role: 'helper',
    email: 'clara@needed.demo',
    name: 'Clara Fontaine',
    roleLabel: 'Aidante',
    city: 'Helsinki, Punavuori',
    avatarUrl: '/moomins/Characters-04-2.svg',
    badgeClass: 'badge-helper',
    interests: ['gardening', 'cooking', 'reading'],
    bio: 'Jardinière urbaine et cuisine saine. Ravie d’échanger graines et conseils.',
  },
  {
    id: 'thomas',
    role: 'helper',
    email: 'thomas@needed.demo',
    name: 'Thomas Lindqvist',
    roleLabel: 'Aidant',
    city: 'Espoo, Tapiola',
    avatarUrl: '/moomins/Muumipappa2.jpg',
    badgeClass: 'badge-helper',
    interests: ['photography', 'cycling', 'hiking'],
    bio: 'Photographe argentique et cycliste. Adore les sentiers côtiers et les parcs nationaux.',
  },
  {
    id: 'elena',
    role: 'helper',
    email: 'elena@needed.demo',
    name: 'Elena Sjöberg',
    roleLabel: 'Aidante',
    city: 'Vantaa, Tikkurila',
    avatarUrl: '/moomins/Nuuskamuikkunen.png',
    badgeClass: 'badge-helper',
    interests: ['baking', 'knitting', 'jazz'],
    bio: 'Brioches à la cannelle (korvapuusti) et collectionneuse de vinyles jazz.',
  },

  // Patients (Clinique / Rémission)
  {
    id: 'julien',
    role: 'patient',
    email: 'julien@needed.demo',
    name: 'Julien Mercier',
    roleLabel: 'Patient',
    city: 'Helsinki, Töölö',
    avatarUrl: '/moomins/Muumipeikko2.jpg',
    badgeClass: 'badge-patient',
    interests: ['gardening', 'baking', 'reading'],
    bio: 'Parcours de rétablissement doux. Herbes aromatiques et pain au levain.',
  },
  {
    id: 'sofia',
    role: 'patient',
    email: 'sofia@needed.demo',
    name: 'Sofia Hakala',
    roleLabel: 'Patiente',
    city: 'Helsinki, Kallio',
    avatarUrl: '/moomins/Nuuskamuikkunen.png',
    badgeClass: 'badge-patient',
    interests: ['cooking', 'jazz', 'photography'],
    bio: 'Musique acoustique, balades calmes au bord de l’eau et soupes réconfortantes.',
  },
  {
    id: 'lucas',
    role: 'patient',
    email: 'lucas@needed.demo',
    name: 'Lucas Virtanen',
    roleLabel: 'Patient',
    city: 'Helsinki, Ullanlinna',
    avatarUrl: '/moomins/Characters-04-2.svg',
    badgeClass: 'badge-patient',
    interests: ['cycling', 'hiking', 'knitting'],
    bio: 'Grand air et tricot scandinave pour garder les pensées légères et ancrées.',
  },

  // Clinicien & Admin
  {
    id: 'clinic',
    role: 'clinician',
    email: 'clinic@needed.demo',
    name: 'Dr. Clinic',
    roleLabel: 'Clinicien TMS',
    city: 'Helsinki TMS Centre',
    avatarUrl: '/moomins/Muumipappa2.jpg',
    badgeClass: 'badge-staff',
    bio: 'Suivi médical discret des patients en rémission et notes d’évolution clinique.',
  },
  {
    id: 'admin',
    role: 'admin',
    email: 'admin@needed.demo',
    name: 'Admin Needed',
    roleLabel: 'Administrateur',
    city: 'Support Communauté',
    avatarUrl: '/moomins/Characters-04-2.svg',
    badgeClass: 'badge-staff',
    bio: 'Supervision de la communauté, traitement des signalements et sécurité.',
  },
]

type QuickLoginModalProps = {
  isOpen: boolean
  onClose: () => void
  onSignedIn: (session: SessionResponse) => void
}

function QuickLoginModal({
  isOpen,
  onClose,
  onSignedIn,
}: QuickLoginModalProps) {
  const [filter, setFilter] = useState<'all' | 'helper' | 'patient' | 'staff'>(
    'all',
  )
  const [busyId, setBusyId] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  if (!isOpen) return null

  const filtered = DEMO_PEOPLE.filter((p) => {
    if (filter === 'all') return true
    if (filter === 'helper') return p.role === 'helper'
    if (filter === 'patient') return p.role === 'patient'
    return p.role === 'clinician' || p.role === 'admin'
  })

  async function handleSelect(person: QuickPerson) {
    setBusyId(person.id)
    setError(null)
    try {
      const session = await login(person.email, 'needed')
      onSignedIn(session)
      onClose()
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.message
          : 'Impossible de joindre le serveur. Vérifiez que le backend tourne sur le port 8000.',
      )
    } finally {
      setBusyId(null)
    }
  }

  return (
    <div
      className="modal-backdrop"
      role="dialog"
      aria-modal="true"
      aria-labelledby="quick-login-title"
      onClick={onClose}
    >
      <div
        className="modal-card modal-card-large stack"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="modal-header">
          <span className="eyebrow">Hackathon Demo · Junction 2026</span>
          <button
            type="button"
            className="modal-close"
            aria-label="Fermer"
            onClick={onClose}
          >
            ✕
          </button>
        </div>

        <div className="quick-login-headline">
          <h2 id="quick-login-title" style={{ margin: 0 }}>
            ⚡ Connexion rapide
          </h2>
          <p className="quiet" style={{ margin: '4px 0 0 0' }}>
            Choisissez une personne pour essayer l’application en 1 clic :
          </p>
        </div>

        {error && (
          <p className="error" role="alert">
            {error}
          </p>
        )}

        <div className="quick-login-tabs">
          <button
            type="button"
            className={`quick-tab ${filter === 'all' ? 'active' : ''}`}
            onClick={() => setFilter('all')}
          >
            Tous ({DEMO_PEOPLE.length})
          </button>
          <button
            type="button"
            className={`quick-tab ${filter === 'helper' ? 'active' : ''}`}
            onClick={() => setFilter('helper')}
          >
            🌿 Aidants (3)
          </button>
          <button
            type="button"
            className={`quick-tab ${filter === 'patient' ? 'active' : ''}`}
            onClick={() => setFilter('patient')}
          >
            🌸 Patients (3)
          </button>
          <button
            type="button"
            className={`quick-tab ${filter === 'staff' ? 'active' : ''}`}
            onClick={() => setFilter('staff')}
          >
            🩺 Équipe (2)
          </button>
        </div>

        <div className="quick-people-list">
          {filtered.map((person) => {
            const isBusy = busyId === person.id
            return (
              <div
                key={person.id}
                className={`quick-person-card ${isBusy ? 'busy' : ''}`}
                onClick={() => !isBusy && void handleSelect(person)}
                role="button"
                tabIndex={0}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault()
                    if (!isBusy) void handleSelect(person)
                  }
                }}
              >
                <img
                  src={person.avatarUrl}
                  alt=""
                  className="quick-person-avatar"
                />
                <div className="quick-person-content">
                  <div className="quick-person-header">
                    <strong>{person.name}</strong>
                    <span className={`quick-badge ${person.badgeClass}`}>
                      {person.roleLabel}
                    </span>
                  </div>
                  {person.city && (
                    <span className="quick-person-city">{person.city}</span>
                  )}
                  {person.interests && person.interests.length > 0 && (
                    <div className="quick-person-tags">
                      {person.interests.map((tag) => (
                        <span key={tag} className="quick-tag">
                          {tag}
                        </span>
                      ))}
                    </div>
                  )}
                  <p className="quick-person-bio">{person.bio}</p>
                </div>
                <div className="quick-person-action">
                  <button
                    type="button"
                    className="button button-primary button-small"
                    disabled={isBusy}
                    onClick={(e) => {
                      e.stopPropagation()
                      void handleSelect(person)
                    }}
                  >
                    {isBusy ? 'Connexion…' : 'Choisir →'}
                  </button>
                </div>
              </div>
            )
          })}
        </div>

        <div className="quick-login-footer">
          <p className="quiet font-small text-center" style={{ margin: 0 }}>
            💡 Mot de passe universel de démo pour tous les comptes :{' '}
            <code>needed</code>
          </p>
        </div>
      </div>
    </div>
  )
}

export default QuickLoginModal
