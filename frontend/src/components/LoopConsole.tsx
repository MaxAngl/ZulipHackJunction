import type { LoopState } from '../api/client'
import AxesPanel from './AxesPanel'
import StatePanel from './StatePanel'
import ZoneAxis from './ZoneAxis'

type LoopConsoleProps = {
  state: LoopState
  // Valeur affichée du curseur : le niveau caché du patient virtuel, celui du serveur ou
  // celui en cours de réglage.
  theta: number
  busy: boolean
  onTheta: (value: number) => void
  onRun: () => void
}

function runLabel(stage: LoopState['round']['stage'], busy: boolean): string {
  if (busy) return 'Working…'
  if (stage === 'proposed') return 'Generate more for this zone'
  if (stage === 'sent') return 'Waiting for the patient'
  if (stage === 'answered') return 'Run the next round'
  return 'Run the loop'
}

// La console montre ce que ni l'aidant ni le patient ne voient : l'état, la zone,
// les demandes mesurées et ce que le modèle a appris.
function LoopConsole({ state, theta, busy, onTheta, onRun }: LoopConsoleProps) {
  const { zone, round, generator, model } = state
  const inZone = round.candidates.filter((candidate) => candidate.in_zone)
  const proposed = round.candidates.filter((candidate) => candidate.slot)
  const lastEntry = state.history.at(-1)

  return (
    <section className="console" aria-label="Loop console">
      <div className="sensor">
        <label htmlFor="theta">
          <span className="sensor-title">Virtual patient, hidden level</span>
          <span className="sensor-value">{theta.toFixed(2)}</span>
        </label>
        <input
          id="theta"
          type="range"
          min="0"
          max="1"
          step="0.01"
          value={theta}
          onChange={(event) => onTheta(Number(event.target.value))}
        />
        <div className="sensor-ends">
          <span>very low</span>
          <span>
            The networks never see this. They read it back from the signals.
          </span>
          <span>very well</span>
        </div>
      </div>

      <dl className="metrics">
        <div>
          <dt>State read</dt>
          <dd>{state.theta.toFixed(2)}</dd>
        </div>
        <div>
          <dt>Zone centre</dt>
          <dd>{zone.center.toFixed(2)}</dd>
        </div>
        <div>
          <dt>Zone width</dt>
          <dd>± {zone.half_width.toFixed(2)}</dd>
        </div>
        <div>
          <dt>Personal shift</dt>
          <dd>
            {model.offset > 0 ? '+' : ''}
            {model.offset.toFixed(2)}
          </dd>
        </div>
      </dl>

      <StatePanel
        components={state.state ?? []}
        distance={state.distance ?? 0}
        signals={state.signals ?? []}
      />

      <ZoneAxis
        zone={zone}
        formats={state.formats}
        candidates={round.candidates}
        message={round.message ?? null}
      />

      <ul className="legend">
        <li>
          <span className="swatch swatch-in" /> in the zone
        </li>
        <li>
          <span className="swatch swatch-out" /> filtered out
        </li>
        <li>
          <span className="swatch swatch-proposed" /> proposed to the helper
        </li>
        <li>
          <span className="swatch swatch-sent" /> sent
        </li>
      </ul>

      <p className="facts">
        {round.candidates.length} generated · {inZone.length} in the zone ·{' '}
        {proposed.length} proposed
      </p>

      <AxesPanel
        zone={zone}
        candidates={round.candidates}
        message={round.message ?? null}
        vector={model.vector ?? []}
      />

      {round.message && (
        <p
          className={
            round.message.status === 'held' ? 'xray xray-held' : 'xray'
          }
        >
          <strong>
            {round.message.status === 'held' ? 'Held back' : 'Delivered'}
          </strong>{' '}
          · position {round.message.lam.toFixed(2)} ·{' '}
          {round.message.format_label}, effort {round.message.effort.toFixed(2)}{' '}
          · {round.message.source.replace('_', ' ')}
          {round.message.hold_reason && (
            <>
              <br />
              {round.message.hold_reason} It will be delivered when it fits.
            </>
          )}
        </p>
      )}

      {round.stage === 'answered' && lastEntry && (
        <p className="xray">
          <strong>Learned</strong> · state {lastEntry.theta_before.toFixed(2)} →{' '}
          {lastEntry.theta_after.toFixed(2)} a day later · reward{' '}
          {lastEntry.reward.toFixed(0)} / 100 · zone centre{' '}
          {lastEntry.center_before.toFixed(2)} →{' '}
          {lastEntry.center_after.toFixed(2)}
          {lastEntry.fit != null && (
            <>
              <br />
              Hidden truth of the virtual patient: this request suited them at{' '}
              {(lastEntry.fit * 100).toFixed(0)} %
              {lastEntry.overload ? ', and it was too heavy' : ''}.
            </>
          )}
        </p>
      )}

      <button
        type="button"
        className="button button-primary button-wide"
        disabled={busy || round.stage === 'sent'}
        onClick={onRun}
      >
        {runLabel(round.stage, busy)}
      </button>

      <p className="provenance">
        <span
          className={
            generator.provider === 'offline'
              ? 'status status-offline'
              : 'status status-live'
          }
        />
        {generator.provider === 'claude'
          ? `Requests written by Claude (${generator.model}), measured locally`
          : generator.provider === 'gemini'
            ? `Requests written and measured with Gemini (${generator.model})`
            : 'Requests from the built-in bank (no Claude or Gemini key)'}
        {generator.note && ` · ${generator.note}`}
        <br />
        State, zone and personal vector: three networks trained on simulated
        patients
        {model.parameters
          ? ` (${Math.round(model.parameters / 1000)}k parameters)`
          : ''}
        . {model.observations} answer
        {model.observations === 1 ? '' : 's'} from this patient so far.
      </p>
    </section>
  )
}

export default LoopConsole
