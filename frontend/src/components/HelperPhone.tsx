import { useState } from 'react'
import type { LoopState, SendRequest } from '../api/client'
import PhoneFrame from './PhoneFrame'

const SLOT_ORDER = { best: 1, bridge: 2, explore: 3 } as const

type HelperPhoneProps = {
  state: LoopState
  busy: boolean
  onSend: (body: SendRequest) => void
  onSkip: () => void
}

// Ce que voit l'aidant : trois demandes à choisir, modifier ou remplacer par la sienne.
// Il ne voit jamais l'état du patient, la zone, ni la difficulté d'une demande.
function HelperPhone({ state, busy, onSend, onSkip }: HelperPhoneProps) {
  const [editingId, setEditingId] = useState<string | null>(null)
  const [editText, setEditText] = useState('')
  const [ownText, setOwnText] = useState('')

  const { round, patient } = state
  const helper =
    state.helpers.find((person) => person.id === round.helper_id) ??
    state.helpers[0]
  const proposals = round.candidates
    .filter((candidate) => candidate.slot != null)
    .sort((a, b) => SLOT_ORDER[a.slot ?? 'best'] - SLOT_ORDER[b.slot ?? 'best'])
  const lastEntry = state.history.at(-1)

  function sendOwn() {
    onSend({ text: ownText })
    setOwnText('')
  }

  function sendEdited(proposalId: string) {
    onSend({ proposal_id: proposalId, text: editText })
    setEditingId(null)
  }

  return (
    <PhoneFrame role="Helper" person={helper}>
      {round.stage === 'idle' && (
        <p className="quiet">
          Nothing to ask right now. You will hear from us when {patient.name}{' '}
          could help you.
        </p>
      )}

      {round.stage === 'proposed' && (
        <>
          <p className="phone-lead">
            {patient.name} could help you with one of these. Pick one, change
            it, or write your own.
          </p>
          {proposals.length === 0 && (
            <p className="quiet">No suggestion fits right now.</p>
          )}
          <ul className="proposals">
            {proposals.map((proposal) => (
              <li key={proposal.id} className="proposal">
                {editingId === proposal.id ? (
                  <>
                    <textarea
                      value={editText}
                      onChange={(event) => setEditText(event.target.value)}
                      rows={4}
                      aria-label="Edit the request"
                    />
                    <div className="row">
                      <button
                        type="button"
                        className="button button-primary"
                        disabled={busy || editText.trim() === ''}
                        onClick={() => sendEdited(proposal.id)}
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
                    <p className="proposal-meta">
                      {proposal.pair.patient_interest} ×{' '}
                      {proposal.pair.helper_interest}
                    </p>
                    <div className="row">
                      <button
                        type="button"
                        className="button button-primary"
                        disabled={busy}
                        onClick={() => onSend({ proposal_id: proposal.id })}
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
          <label className="own">
            <span>Have a real need? Write your own request.</span>
            <textarea
              value={ownText}
              onChange={(event) => setOwnText(event.target.value)}
              rows={3}
              placeholder={`Ask ${patient.name} for a small favour…`}
            />
          </label>
          <div className="row">
            <button
              type="button"
              className="button button-primary"
              disabled={busy || ownText.trim() === ''}
              onClick={sendOwn}
            >
              Send mine
            </button>
            <button
              type="button"
              className="button button-ghost"
              disabled={busy}
              onClick={onSkip}
            >
              Not now
            </button>
          </div>
        </>
      )}

      {(round.stage === 'sent' || round.stage === 'held') && round.message && (
        <>
          <p className="bubble bubble-out">{round.message.text}</p>
          <p className="quiet">
            Sent. It will reach {patient.name} at the right moment.
          </p>
        </>
      )}

      {round.stage === 'answered' && lastEntry && (
        <>
          <p className="bubble bubble-out">{lastEntry.text}</p>
          <p className="quiet">
            {lastEntry.action === 'helped'
              ? `${patient.name} answered your request.`
              : 'No answer yet.'}
          </p>
        </>
      )}
    </PhoneFrame>
  )
}

export default HelperPhone
