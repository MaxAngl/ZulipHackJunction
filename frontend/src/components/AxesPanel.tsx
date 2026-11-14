import type { CandidateState, MessageState, ZoneState } from '../api/client'
import './ModelPanels.css'

type AxesPanelProps = {
  zone: ZoneState
  candidates: CandidateState[]
  message: MessageState | null
  vector: number[]
}

const SLOT_NUMBER = { best: 1, bridge: 2, explore: 3 } as const

function percent(value: number): string {
  return `${Math.min(1, Math.max(0, value)) * 100}%`
}

// La zone complète, telle que le réseau B la sort : un intervalle sur cinq axes, un plafond
// sur le sixième. Les trois demandes proposées à l'aidant sont posées sur chaque axe.
function AxesPanel({ zone, candidates, message, vector }: AxesPanelProps) {
  const axes = zone.axes ?? []
  if (axes.length === 0) return null
  const proposed = candidates.filter((candidate) => candidate.slot != null)
  const largest = Math.max(0.05, ...vector.map((value) => Math.abs(value)))

  return (
    <section className="model-panel" aria-label="Zone on the six axes">
      <h3>Zone on six axes, from network B</h3>
      <p className="model-note">
        The band is what suits this patient now. On a cost axis its upper edge
        is never exceeded. Numbers are the three suggestions.
      </p>
      <ul className="model-rows">
        {axes.map((axis, index) => (
          <li className="model-row" key={axis.key}>
            <span className="model-label">{axis.label}</span>
            <span className="model-track">
              <span
                className={
                  axis.kind === 'ceiling'
                    ? 'model-band model-band-ceiling'
                    : 'model-band'
                }
                style={{
                  left: percent(axis.low),
                  width: percent(axis.high - axis.low),
                }}
              />
              {proposed.map((candidate) =>
                candidate.axes?.[index] == null || !candidate.slot ? null : (
                  <span
                    className="model-mark"
                    key={candidate.id}
                    style={{ left: percent(candidate.axes[index]) }}
                    title={candidate.text}
                  >
                    {SLOT_NUMBER[candidate.slot]}
                  </span>
                ),
              )}
              {message?.axes?.[index] != null && (
                <span
                  className="model-mark model-mark-sent"
                  style={{ left: percent(message.axes[index]) }}
                  title={`Sent: ${message.text}`}
                />
              )}
            </span>
            <span className="model-value">
              {axis.kind === 'ceiling'
                ? `≤ ${axis.high.toFixed(2)}`
                : `${axis.low.toFixed(2)}–${axis.high.toFixed(2)}`}
            </span>
          </li>
        ))}
        {vector.length > 0 && (
          <li className="model-row">
            <span className="model-label">Personal vector</span>
            <span
              className="vector"
              title={vector.map((value) => value.toFixed(2)).join('  ')}
            >
              {vector.map((value, index) => {
                const size = (Math.abs(value) / largest) * 50
                return (
                  <span className="vector-cell" key={index}>
                    <span
                      className="vector-bar"
                      style={
                        value >= 0
                          ? { bottom: '50%', height: `${size}%` }
                          : { top: '50%', height: `${size}%` }
                      }
                    />
                  </span>
                )
              })}
            </span>
            <span className="model-value">
              {vector.every((value) => value === 0) ? 'general' : 'learned'}
            </span>
          </li>
        )}
      </ul>
    </section>
  )
}

export default AxesPanel
