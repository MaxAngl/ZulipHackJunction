import { useState } from 'react'
import {
  getHelperHome,
  sayThanks,
  sendToPatient,
  skipSuggestions,
  suggest,
} from '../api/client'
import ScreenFrame from './ScreenFrame'
import { useHome } from './useHome'

type HelperScreenProps = {
  token: string
  onLeave: () => void
}

// L'écran de l'aidant, dans la vraie app. Il choisit une demande, la modifie ou écrit la
// sienne, puis lit la réponse et dit merci. Il ne voit jamais l'état de l'autre personne.
function HelperScreen({ token, onLeave }: HelperScreenProps) {
  const { home, error, busy, run } = useHome(token, getHelperHome, onLeave)
  const [editingId, setEditingId] = useState<string | null>(null)
  const [editText, setEditText] = useState('')
  const [ownText, setOwnText] = useState('')
  const [thanks, setThanks] = useState<Record<string, string>>({})

  if (!home) {
    return (
      <ScreenFrame>
        <p className="quiet">{error ?? 'Loading…'}</p>
      </ScreenFrame>
    )
  }

  const hasProposals = home.patient_name != null

  return (
    <ScreenFrame name={home.user.name} onLeave={onLeave}>
      <main className="stack">
        {error && (
          <p className="error" role="alert">
            {error}
          </p>
        )}

        {hasProposals ? (
          <section className="stack">
            <p className="eyebrow">For you today</p>
            <h1>{home.patient_name} could help you.</h1>
            <p className="quiet">Pick one, change it, or write your own.</p>
            {home.proposals.length === 0 && (
              <p className="quiet">
                No suggestion fits right now. You can still write your own.
              </p>
            )}
            <ul className="proposals">
              {home.proposals.map((proposal) => (
                <li key={proposal.id} className="proposal">
                  {editingId === proposal.id ? (
                    <>
                      <textarea
                        value={editText}
                        rows={4}
                        aria-label="Edit the request"
                        onChange={(event) => setEditText(event.target.value)}
                      />
                      <div className="row">
                        <button
                          type="button"
                          className="button button-primary"
                          disabled={busy || editText.trim() === ''}
                          onClick={() => {
                            setEditingId(null)
                            void run(() =>
                              sendToPatient(token, {
                                proposal_id: proposal.id,
                                text: editText,
                              }),
                            )
                          }}
                        >
                          Send
                        </button>
                        <button
                          type="button"
                          className="button"
                          onClick={() => setEditingId(null)}
                        >
                          Cancel
                        </button>
                      </div>
                    </>
                  ) : (
                    <>
                      <p className="proposal-text">{proposal.text}</p>
                      <div className="row">
                        <button
                          type="button"
                          className="button button-primary"
                          disabled={busy}
                          onClick={() =>
                            void run(() =>
                              sendToPatient(token, {
                                proposal_id: proposal.id,
                              }),
                            )
                          }
                        >
                          Send
                        </button>
                        <button
                          type="button"
                          className="button"
                          disabled={busy}
                          onClick={() => {
                            setEditingId(proposal.id)
                            setEditText(proposal.text)
                          }}
                        >
                          Edit
                        </button>
                      </div>
                    </>
                  )}
                </li>
              ))}
            </ul>
            <label className="field">
              <span>Have a real need? Write your own request.</span>
              <textarea
                value={ownText}
                rows={3}
                placeholder={`Ask ${home.patient_name} for a small favour…`}
                onChange={(event) => setOwnText(event.target.value)}
              />
            </label>
            <div className="row">
              <button
                type="button"
                className="button button-primary"
                disabled={busy || ownText.trim() === ''}
                onClick={() => {
                  const text = ownText
                  setOwnText('')
                  void run(() => sendToPatient(token, { text }))
                }}
              >
                Send mine
              </button>
              <button
                type="button"
                className="button button-ghost"
                disabled={busy}
                onClick={() => void run(() => skipSuggestions(token))}
              >
                Not now
              </button>
            </div>
          </section>
        ) : (
          <section className="stack">
            <h1>Need a hand with something?</h1>
            <p className="quiet">
              We will suggest a few things you could ask someone who would enjoy
              helping.
            </p>
            <button
              type="button"
              className="button button-primary button-wide"
              disabled={busy}
              onClick={() => void run(() => suggest(token))}
            >
              {busy ? 'Looking…' : 'Who could help me?'}
            </button>
          </section>
        )}

        {home.requests.length > 0 && (
          <section className="stack">
            <h2>Your requests</h2>
            <ul className="thread">
              {home.requests.map((request) => (
                <li key={request.id} className="thread-item">
                  <p className="bubble bubble-out">{request.text}</p>
                  {request.status === 'answered' ? (
                    <>
                      <p className="eyebrow">{request.with_name} answered</p>
                      <p className="bubble bubble-plain">{request.reply}</p>
                      {request.thanks ? (
                        <p className="note">You said: {request.thanks}</p>
                      ) : (
                        <>
                          <textarea
                            value={thanks[request.id] ?? ''}
                            rows={2}
                            placeholder={`Tell ${request.with_name} what you did with it`}
                            aria-label={`Thank ${request.with_name}`}
                            onChange={(event) =>
                              setThanks((current) => ({
                                ...current,
                                [request.id]: event.target.value,
                              }))
                            }
                          />
                          <div className="row">
                            <button
                              type="button"
                              className="button"
                              disabled={
                                busy || (thanks[request.id] ?? '').trim() === ''
                              }
                              onClick={() =>
                                void run(() =>
                                  sayThanks(
                                    token,
                                    request.id,
                                    thanks[request.id] ?? '',
                                  ),
                                )
                              }
                            >
                              Say thanks
                            </button>
                          </div>
                        </>
                      )}
                    </>
                  ) : (
                    <p className="quiet">
                      On its way to {request.with_name}. It will arrive at the
                      right moment.
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

export default HelperScreen
