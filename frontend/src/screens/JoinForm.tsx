import { useState } from 'react'
import { ApiError, join, type Role } from '../api/client'
import { saveToken } from '../session'

const STARTERS: Record<Role, string[]> = {
  patient: ['gardening', 'jazz', 'baking', 'reading', 'chess', 'knitting'],
  helper: [
    'cooking',
    'cycling',
    'photography',
    'hiking',
    'woodworking',
    'board games',
  ],
}

const COPY: Record<Role, { title: string; ask: string }> = {
  patient: {
    title: 'Welcome.',
    ask: 'What do you like, or know a thing or two about?',
  },
  helper: {
    title: 'Join the community.',
    ask: 'What are you into these days?',
  },
}

type JoinFormProps = {
  role: Role
  onJoined: (token: string) => void
}

// Inscription : un prénom et des centres d'intérêt. Rien d'autre n'est demandé.
function JoinForm({ role, onJoined }: JoinFormProps) {
  const [name, setName] = useState('')
  const [interests, setInterests] = useState<string[]>([])
  const [custom, setCustom] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  function toggle(interest: string) {
    setInterests((current) =>
      current.includes(interest)
        ? current.filter((item) => item !== interest)
        : [...current, interest],
    )
  }

  function addCustom() {
    const value = custom.trim().toLowerCase()
    if (value && !interests.includes(value)) {
      setInterests((current) => [...current, value])
    }
    setCustom('')
  }

  async function submit() {
    setBusy(true)
    setError(null)
    try {
      const session = await join(role, name.trim(), interests)
      saveToken(role, session.token)
      onJoined(session.token)
    } catch (err) {
      setError(
        err instanceof ApiError ? err.message : 'The server is not responding.',
      )
    } finally {
      setBusy(false)
    }
  }

  const options = [
    ...STARTERS[role],
    ...interests.filter((item) => !STARTERS[role].includes(item)),
  ]
  const ready = name.trim() !== '' && interests.length > 0

  return (
    <form
      className="stack"
      onSubmit={(event) => {
        event.preventDefault()
        if (ready && !busy) void submit()
      }}
    >
      <h1>{COPY[role].title}</h1>
      <label className="field">
        <span>Your first name</span>
        <input
          type="text"
          value={name}
          maxLength={40}
          autoComplete="given-name"
          onChange={(event) => setName(event.target.value)}
        />
      </label>

      <div className="field">
        <span>{COPY[role].ask}</span>
        <div className="chips">
          {options.map((interest) => (
            <button
              key={interest}
              type="button"
              className={
                interests.includes(interest) ? 'chip chip-on' : 'chip chip-off'
              }
              aria-pressed={interests.includes(interest)}
              onClick={() => toggle(interest)}
            >
              {interest}
            </button>
          ))}
        </div>
        <div className="row">
          <input
            type="text"
            value={custom}
            maxLength={40}
            placeholder="Add your own"
            aria-label="Add your own interest"
            onChange={(event) => setCustom(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === 'Enter') {
                event.preventDefault()
                addCustom()
              }
            }}
          />
          <button
            type="button"
            className="button"
            disabled={custom.trim() === ''}
            onClick={addCustom}
          >
            Add
          </button>
        </div>
      </div>

      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
      <button
        type="submit"
        className="button button-primary button-wide"
        disabled={!ready || busy}
      >
        {busy ? 'Joining…' : 'Continue'}
      </button>
    </form>
  )
}

export default JoinForm
