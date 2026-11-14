import { useState } from 'react'
import type { LoopState, PatientAction, TypingSignals } from '../api/client'
import { useTypingSignals } from '../typing'
import PhoneFrame from './PhoneFrame'

type PatientPhoneProps = {
  state: LoopState
  busy: boolean
  onRespond: (action: PatientAction, typing?: TypingSignals) => void
}

// Ce que voit le patient : une demande venue d'une personne, rien d'autre.
// On ne lui pose aucune question sur son état. S'il écrit sa réponse, l'app relève sa frappe
// (corrections, temps avant la première touche) : ces signaux entrent dans θ.
function PatientPhone({ state, busy, onRespond }: PatientPhoneProps) {
  const { round, patient } = state
  const helper = state.helpers.find((person) => person.id === round.helper_id)
  const delivered =
    round.stage === 'sent' && round.message?.status === 'delivered'
      ? round.message
      : null
  const lastEntry = state.history.at(-1)
  const [draft, setDraft] = useState('')
  const typing = useTypingSignals(delivered?.id ?? null)

  function answer(action: PatientAction) {
    onRespond(action, action === 'helped' ? typing.collect() : undefined)
    setDraft('')
  }

  return (
    <PhoneFrame role="Patient" person={patient}>
      {delivered && helper && (
        <>
          <p className="phone-lead">{helper.name} is asking you:</p>
          <p className="bubble bubble-in">{delivered.text}</p>
          <label className="field">
            <span className="field-label">Your answer (optional)</span>
            <textarea
              rows={3}
              value={draft}
              disabled={busy}
              placeholder={`Write to ${helper.name}…`}
              onChange={(event) => setDraft(event.target.value)}
              onInput={typing.onInput}
            />
          </label>
          <div className="row">
            <button
              type="button"
              className="button button-primary"
              disabled={busy}
              onClick={() => answer('helped')}
            >
              Help {helper.name}
            </button>
            <button
              type="button"
              className="button button-ghost"
              disabled={busy}
              onClick={() => answer('ignored')}
            >
              Not now
            </button>
          </div>
        </>
      )}

      {!delivered && round.stage === 'answered' && lastEntry && (
        <>
          <p className="bubble bubble-in">{lastEntry.text}</p>
          <p className="quiet">
            {lastEntry.action === 'helped'
              ? `You helped ${lastEntry.helper_name}. Thank you.`
              : 'Set aside. No problem.'}
          </p>
        </>
      )}

      {!delivered && round.stage !== 'answered' && (
        <p className="quiet">Nothing for now.</p>
      )}
    </PhoneFrame>
  )
}

export default PatientPhone
