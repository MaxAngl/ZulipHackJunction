import { useEffect, useMemo, useState } from 'react'
import { createPortal } from 'react-dom'
import {
  ApiError,
  getDemoAccounts,
  login,
  type AccountRole,
  type DemoAccount,
  type SessionResponse,
} from '../api/client'

// Mot de passe commun des comptes de démo (`backend/seed.py`).
const DEMO_PASSWORD = 'needed'

type Group = 'all' | 'helper' | 'patient' | 'team'

const GROUPS: { key: Group; label: string }[] = [
  { key: 'all', label: 'All' },
  { key: 'helper', label: 'Helpers' },
  { key: 'patient', label: 'Patients' },
  { key: 'team', label: 'Team' },
]

const ROLE_LABELS: Record<AccountRole, string> = {
  helper: 'Helper',
  patient: 'Patient',
  clinician: 'Clinician',
  admin: 'Admin',
}

function inGroup(account: DemoAccount, group: Group): boolean {
  if (group === 'all') return true
  if (group === 'team') {
    return account.role === 'clinician' || account.role === 'admin'
  }
  return account.role === group
}

function fullName(account: DemoAccount): string {
  return `${account.first_name} ${account.last_name}`.trim()
}

function initials(account: DemoAccount): string {
  return `${account.first_name.charAt(0)}${account.last_name.charAt(0)}`.toUpperCase()
}

// Recherche sur ce qu'on voit d'une personne : nom, rôle, quartier, intérêts, e-mail.
function matches(account: DemoAccount, query: string): boolean {
  const haystack = [
    fullName(account),
    ROLE_LABELS[account.role],
    account.city,
    account.email,
    ...account.interests,
  ]
    .join(' ')
    .toLowerCase()
  return query
    .toLowerCase()
    .split(/\s+/)
    .filter(Boolean)
    .every((word) => haystack.includes(word))
}

type QuickLoginModalProps = {
  isOpen: boolean
  onClose: () => void
  onSignedIn: (session: SessionResponse) => void
}

// Connexion rapide de la démo : tous les comptes `@needed.demo` de la base, un clic pour entrer.
// La feuille est rendue sur <body> : posée dans l'accueil, elle passait sous son contenu.
function QuickLoginModal({
  isOpen,
  onClose,
  onSignedIn,
}: QuickLoginModalProps) {
  const [accounts, setAccounts] = useState<DemoAccount[] | null>(null)
  const [group, setGroup] = useState<Group>('all')
  const [query, setQuery] = useState('')
  const [busyEmail, setBusyEmail] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  // La liste est relue à chaque ouverture : un compte ajouté à la base y apparaît.
  useEffect(() => {
    if (!isOpen) return
    let live = true
    getDemoAccounts()
      .then((list) => {
        if (live) setAccounts(list)
      })
      .catch((err: unknown) => {
        if (!live) return
        setAccounts([])
        setError(
          err instanceof ApiError ? err.message : "Can't reach the server.",
        )
      })
    return () => {
      live = false
    }
  }, [isOpen])

  useEffect(() => {
    if (!isOpen) return
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [isOpen, onClose])

  // Les nombres des onglets suivent la recherche : ce qu'on trouverait dans chacun.
  const found = useMemo(
    () => (accounts ?? []).filter((a) => matches(a, query)),
    [accounts, query],
  )

  const counts = useMemo(
    () =>
      Object.fromEntries(
        GROUPS.map(({ key }) => [
          key,
          found.filter((a) => inGroup(a, key)).length,
        ]),
      ) as Record<Group, number>,
    [found],
  )

  const shown = useMemo(
    () => found.filter((a) => inGroup(a, group)),
    [found, group],
  )

  if (!isOpen) return null

  async function choose(account: DemoAccount) {
    setBusyEmail(account.email)
    setError(null)
    try {
      onSignedIn(await login(account.email, DEMO_PASSWORD))
      onClose()
    } catch (err) {
      setError(
        err instanceof ApiError ? err.message : "Can't reach the server.",
      )
    } finally {
      setBusyEmail(null)
    }
  }

  return createPortal(
    <div
      className="modal-backdrop quick-login-backdrop"
      role="dialog"
      aria-modal="true"
      aria-labelledby="quick-login-title"
      onClick={onClose}
    >
      <div
        className="modal-card quick-login-sheet"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="quick-login-head">
          <div>
            <span className="eyebrow">Demo</span>
            <h2 id="quick-login-title">Sign in as anyone</h2>
          </div>
          <button
            type="button"
            className="modal-close"
            aria-label="Close"
            onClick={onClose}
          >
            ✕
          </button>
        </div>

        <input
          type="text"
          className="quick-login-search"
          placeholder="Search a name, an interest, a district"
          aria-label="Search the demo accounts"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          autoFocus
        />

        <div className="quick-login-groups" role="group" aria-label="Role">
          {GROUPS.map(({ key, label }) => (
            <button
              key={key}
              type="button"
              className={`quick-login-group ${group === key ? 'active' : ''}`}
              aria-pressed={group === key}
              onClick={() => setGroup(key)}
            >
              {label}
              <span className="quick-login-count">{counts[key]}</span>
            </button>
          ))}
        </div>

        {error && (
          <p className="error" role="alert">
            {error}
          </p>
        )}

        <ul className="quick-login-list">
          {accounts === null && <li className="quiet">Loading accounts…</li>}
          {accounts !== null && shown.length === 0 && !error && (
            <li className="quiet">No one matches “{query}”.</li>
          )}
          {shown.map((account) => {
            const busy = busyEmail === account.email
            return (
              <li key={account.email}>
                <button
                  type="button"
                  className="quick-login-row"
                  disabled={busyEmail !== null}
                  onClick={() => void choose(account)}
                >
                  <span
                    className={`quick-login-initials quick-login-${account.role}`}
                    aria-hidden="true"
                  >
                    {initials(account)}
                  </span>
                  <span className="quick-login-who">
                    <strong>{fullName(account)}</strong>
                    <span className="quick-login-meta">
                      {ROLE_LABELS[account.role]}
                      {account.city && ` · ${account.city}`}
                    </span>
                    {account.interests.length > 0 && (
                      <span className="quick-login-meta">
                        {account.interests.join(' · ')}
                      </span>
                    )}
                  </span>
                  <span className="quick-login-go" aria-hidden="true">
                    {busy ? '…' : '→'}
                  </span>
                </button>
              </li>
            )
          })}
        </ul>
      </div>
    </div>,
    document.body,
  )
}

export default QuickLoginModal
