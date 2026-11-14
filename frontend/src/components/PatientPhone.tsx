import type { LoopState, PatientAction } from '../api/client'
import PhoneFrame from './PhoneFrame'

type PatientPhoneProps = {
  state: LoopState
  busy: boolean
  onRespond: (action: PatientAction) => void
}

// Ce que voit le patient : une demande venue d'une personne, rien d'autre.
// On ne lui pose aucune question sur son état.
function PatientPhone({ state, busy, onRespond }: PatientPhoneProps) {
  const { round, patient } = state
  const helper = state.helpers.find((person) => person.id === round.helper_id)
  const delivered =
    round.stage === 'sent' && round.message?.status === 'delivered'
      ? round.message
      : null
  const lastEntry = state.history.at(-1)

  return (
    <PhoneFrame role="Patient" person={patient}>
      {delivered && helper && (
        <>
          <p className="phone-lead">{helper.name} is asking you:</p>
          <p className="bubble bubble-in">{delivered.text}</p>
          <div className="row">
            <button
              type="button"
              className="button button-primary"
              disabled={busy}
              onClick={() => onRespond('helped')}
            >
              Help {helper.name}
            </button>
            <button
              type="button"
              className="button button-ghost"
              disabled={busy}
              onClick={() => onRespond('ignored')}
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
