import { useState } from 'react'
import { declineRequest, getPatientHome, replyToRequest } from '../api/client'
import ScreenFrame from './ScreenFrame'
import { useHome } from './useHome'

type PatientScreenProps = {
  token: string
  onLeave: () => void
}

// L'écran du patient, dans la vraie app : une demande venue d'une personne, sa réponse, puis
// ce que cette personne en a fait. On ne lui pose aucune question sur son état.
function PatientScreen({ token, onLeave }: PatientScreenProps) {
  const { home, error, busy, run } = useHome(token, getPatientHome, onLeave)
  const [drafts, setDrafts] = useState<Record<string, string>>({})

  if (!home) {
    return (
      <ScreenFrame>
        <p className="quiet">{error ?? 'Loading…'}</p>
      </ScreenFrame>
    )
  }

  return (
    <ScreenFrame name={home.user.name} onLeave={onLeave}>
      <main className="stack">
        {error && (
          <p className="error" role="alert">
            {error}
          </p>
        )}

        {home.inbox.length === 0 && (
          <section className="stack">
            <h1>Nothing for now.</h1>
            <p className="quiet">
              When someone needs a hand, you will see it here.
            </p>
          </section>
        )}

        {home.inbox.map((request) => (
          <section key={request.id} className="stack">
            <p className="eyebrow">{request.with_name} is asking you</p>
            <p className="bubble bubble-in bubble-big">{request.text}</p>
            <textarea
              value={drafts[request.id] ?? ''}
              rows={4}
              placeholder="Write your answer"
              aria-label={`Your answer to ${request.with_name}`}
              onChange={(event) =>
                setDrafts((current) => ({
                  ...current,
                  [request.id]: event.target.value,
                }))
              }
            />
            <div className="row">
              <button
                type="button"
                className="button button-primary"
                disabled={busy || (drafts[request.id] ?? '').trim() === ''}
                onClick={() =>
                  void run(() =>
                    replyToRequest(token, request.id, drafts[request.id] ?? ''),
                  )
                }
              >
                Send answer
              </button>
              <button
                type="button"
                className="button button-ghost"
                disabled={busy}
                onClick={() =>
                  void run(() => declineRequest(token, request.id))
                }
              >
                Not now
              </button>
            </div>
          </section>
        ))}

        {home.past.length > 0 && (
          <section className="stack">
            <h2>You helped</h2>
            <ul className="thread">
              {home.past.map((request) => (
                <li key={request.id} className="thread-item">
                  <p className="eyebrow">{request.with_name} asked</p>
                  <p className="bubble bubble-plain">{request.text}</p>
                  <p className="bubble bubble-out">{request.reply}</p>
                  {request.thanks && (
                    <p className="note">
                      <strong>{request.with_name}:</strong> {request.thanks}
                    </p>
                  )}
                </li>
              ))}
            </ul>
          </section>
        )}
      </main>
    </ScreenFrame>
  )
}

export default PatientScreen
