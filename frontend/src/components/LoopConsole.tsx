import type { LoopState } from '../api/client'
import ZoneAxis from './ZoneAxis'

type LoopConsoleProps = {
  state: LoopState
  // Valeur affichée du curseur : celle du serveur, ou celle en cours de réglage.
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
          <span className="sensor-title">Patient state θ</span>
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
          <span>Simulated sensor. Nothing is asked of the patient.</span>
          <span>very well</span>
        </div>
      </div>

      <dl className="metrics">
        <div>
          <dt>Zone centre</dt>
          <dd>{zone.center.toFixed(2)}</dd>
        </div>
        <div>
          <dt>Zone width</dt>
          <dd>± {zone.half_width.toFixed(2)}</dd>
        </div>
        <div>
          <dt>Effort ceiling</dt>
          <dd>{zone.effort_max.toFixed(2)}</dd>
        </div>
        <div>
          <dt>Personal shift</dt>
          <dd>
            {model.offset > 0 ? '+' : ''}
            {model.offset.toFixed(2)}
          </dd>
        </div>
      </dl>

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
          {lastEntry.theta_after.toFixed(2)} · reward{' '}
          {lastEntry.reward > 0 ? '+' : ''}
          {lastEntry.reward.toFixed(2)} · zone centre{' '}
          {lastEntry.center_before.toFixed(2)} →{' '}
          {lastEntry.center_after.toFixed(2)}
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
            generator.provider === 'gemini'
              ? 'status status-live'
              : 'status status-offline'
          }
        />
        {generator.provider === 'gemini'
          ? `Requests written and measured with Gemini (${generator.model})`
          : 'Requests from the built-in bank (no Gemini key)'}
        {generator.note && ` · ${generator.note}`}
        <br />
        Zone model: simulated stand-in, {model.observations} answer
        {model.observations === 1 ? '' : 's'} so far.
      </p>
    </section>
  )
}

export default LoopConsole
