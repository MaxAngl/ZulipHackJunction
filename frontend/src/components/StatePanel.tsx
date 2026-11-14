import type { LoopState } from '../api/client'
import './ModelPanels.css'

type StatePanelProps = {
  components: NonNullable<LoopState['state']>
  distance: number
  signals: NonNullable<LoopState['signals']>
}

const MODALITIES: { key: string; title: string }[] = [
  { key: 'watch', title: 'Watch' },
  { key: 'app', title: 'Replies in the app' },
  { key: 'touch', title: 'Typing' },
]

function pretty(name: string): string {
  return name.replaceAll('_', ' ')
}

// L'état du patient tel que l'autoencodeur le lit : six composantes, chacune comparée à la
// moyenne des personnes saines. En dessous, les signaux bruts dont il part.
function StatePanel({ components, distance, signals }: StatePanelProps) {
  if (components.length === 0) return null
  const missing = signals.filter((signal) => signal.value == null).length

  return (
    <section
      className="model-panel"
      aria-label="Patient state read by the autoencoder"
    >
      <h3>State L(θ), read by the autoencoder</h3>
      <p className="model-note">
        Six components from {signals.length} raw signals. The line marks the
        healthy average. Distance to healthy: {distance.toFixed(1)}.
      </p>
      <ul className="model-rows">
        {components.map((component) => (
          <li className="model-row" key={component.key}>
            <span className="model-label">{component.label}</span>
            <span className="model-track">
              <span
                className="model-fill"
                style={{ width: `${component.value * 100}%` }}
              />
              <span
                className="model-reference"
                style={{ left: `${component.reference * 100}%` }}
                title={`Healthy average ${component.reference.toFixed(2)}`}
              />
            </span>
            <span className="model-value">{component.value.toFixed(2)}</span>
          </li>
        ))}
      </ul>

      <details className="signals">
        <summary>
          Raw signals θ at the last reading ({signals.length - missing} of{' '}
          {signals.length} present)
        </summary>
        <div className="signals-groups">
          {MODALITIES.map((modality) => (
            <div className="signals-group" key={modality.key}>
              <h4>{modality.title}</h4>
              <dl>
                {signals
                  .filter((signal) => signal.modality === modality.key)
                  .map((signal) => (
                    <div style={{ display: 'contents' }} key={signal.name}>
                      <dt title={`${pretty(signal.name)} (${signal.unit})`}>
                        {pretty(signal.name)}
                      </dt>
                      <dd
                        className={
                          signal.value == null ? 'signal-missing' : undefined
                        }
                      >
                        {signal.value == null ? 'missing' : signal.value}
                      </dd>
                    </div>
                  ))}
              </dl>
            </div>
          ))}
        </div>
      </details>
    </section>
  )
}

export default StatePanel
