import { useState } from 'react'
import { declineRequest, replyToRequest, type PatientHome } from '../api/client'

type PatientRequestsProps = {
  token: string
  home: PatientHome
  busy: boolean
  run: (action: () => Promise<PatientHome>) => Promise<void>
}

// Les vraies demandes reçues par le patient (`home.inbox`) : il répond ou les met de côté.
// En dessous, celles auxquelles il a déjà répondu, avec le merci de l'aidant.
function PatientRequests({ token, home, busy, run }: PatientRequestsProps) {
  const [drafts, setDrafts] = useState<Record<string, string>>({})

  if (home.inbox.length === 0 && home.past.length === 0) {
    return null
  }

  return (
    <section className="stack">
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
              onClick={() => void run(() => declineRequest(token, request.id))}
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
    </section>
  )
}

export default PatientRequests
