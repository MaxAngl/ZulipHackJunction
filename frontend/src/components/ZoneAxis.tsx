import type {
  CandidateState,
  FormatState,
  MessageState,
  ZoneState,
} from '../api/client'

// Le plan des demandes : en abscisse la position λ entre les deux centres d'intérêt,
// en ordonnée l'effort. La zone est le rectangle des demandes acceptables maintenant.
const WIDTH = 680
const HEIGHT = 340
const LEFT = 104
const RIGHT = 22
const TOP = 40
const BOTTOM = 56
// Marge intérieure : les demandes en position 0 ou 1 ne sont pas coupées par le bord.
const PAD = 16
const PLOT_LEFT = LEFT
const PLOT_RIGHT = WIDTH - RIGHT

const SLOT_NUMBER = { best: 1, bridge: 2, explore: 3 } as const

function x(lam: number): number {
  return LEFT + PAD + lam * (WIDTH - LEFT - RIGHT - 2 * PAD)
}

function y(effort: number): number {
  return HEIGHT - BOTTOM - effort * (HEIGHT - TOP - BOTTOM)
}

// Petit décalage vertical stable par demande, pour que les points superposés restent lisibles.
function jitter(id: string): number {
  let hash = 0
  for (const char of id) {
    hash = (hash * 31 + char.charCodeAt(0)) % 997
  }
  return (hash / 997 - 0.5) * 0.06
}

// Les trois propositions sont écartées verticalement pour rester lisibles quand elles
// tombent au même endroit.
function height(candidate: CandidateState): number {
  const spread = candidate.slot ? (SLOT_NUMBER[candidate.slot] - 2) * 0.045 : 0
  return candidate.effort + jitter(candidate.id) + spread
}

function describe(candidate: CandidateState): string {
  const aim =
    candidate.intended == null
      ? ''
      : ` (generator aimed at ${candidate.intended.toFixed(2)})`
  const where = candidate.off_topic
    ? 'off topic'
    : `position ${candidate.lam.toFixed(2)}${aim}`
  return `${candidate.text}\n${where} · ${candidate.format_label}, effort ${candidate.effort.toFixed(2)}`
}

type ZoneAxisProps = {
  zone: ZoneState
  formats: FormatState[]
  candidates: CandidateState[]
  message: MessageState | null
}

function ZoneAxis({ zone, formats, candidates, message }: ZoneAxisProps) {
  const showShared = Math.abs(zone.common_center - zone.center) > 0.005
  const plain = candidates.filter((candidate) => candidate.slot == null)
  const proposed = candidates.filter((candidate) => candidate.slot != null)

  return (
    <svg
      className="axis"
      viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
      role="img"
      aria-label="Requests placed by position and effort, with the acceptable zone"
    >
      <rect
        className="axis-plot"
        x={PLOT_LEFT}
        y={y(1.06)}
        width={PLOT_RIGHT - PLOT_LEFT}
        height={y(0) - y(1.06)}
      />

      {formats.map((format) => (
        <g key={format.key}>
          <line
            className="axis-grid"
            x1={PLOT_LEFT}
            x2={PLOT_RIGHT}
            y1={y(format.effort)}
            y2={y(format.effort)}
          />
          <text
            className="axis-format"
            x={LEFT - 12}
            y={y(format.effort) + 4}
            textAnchor="end"
          >
            {format.label}
          </text>
        </g>
      ))}

      <rect
        className="axis-zone"
        x={x(zone.low)}
        y={y(zone.effort_max)}
        width={x(zone.high) - x(zone.low)}
        height={y(0) - y(zone.effort_max)}
        rx="6"
      />
      <line
        className="axis-center"
        x1={x(zone.center)}
        x2={x(zone.center)}
        y1={y(zone.effort_max)}
        y2={y(0)}
      />
      <text
        className="axis-zone-label"
        x={(x(zone.low) + x(zone.high)) / 2}
        y={y(zone.effort_max) - 8}
        textAnchor="middle"
      >
        zone
      </text>

      {showShared && (
        <g>
          <line
            className="axis-shared"
            x1={x(zone.common_center)}
            x2={x(zone.common_center)}
            y1={y(1.06)}
            y2={y(0)}
          />
          <text
            className="axis-shared-label"
            x={x(zone.common_center)}
            y={y(1.06) - 8}
            textAnchor="middle"
          >
            shared model
          </text>
        </g>
      )}

      <line
        className="axis-base"
        x1={PLOT_LEFT}
        x2={PLOT_RIGHT}
        y1={y(0)}
        y2={y(0)}
      />
      {[0, 0.25, 0.5, 0.75, 1].map((tick) => (
        <text
          key={tick}
          className="axis-tick"
          x={x(tick)}
          y={y(0) + 18}
          textAnchor="middle"
        >
          {tick}
        </text>
      ))}
      <text
        className="axis-end"
        x={PLOT_LEFT}
        y={HEIGHT - 10}
        textAnchor="start"
      >
        ← helper's interests
      </text>
      <text
        className="axis-end"
        x={PLOT_RIGHT}
        y={HEIGHT - 10}
        textAnchor="end"
      >
        patient's interests →
      </text>
      <text
        className="axis-title"
        x={LEFT - 12}
        y={y(1.06) - 8}
        textAnchor="end"
      >
        effort
      </text>

      {plain.map((candidate) => (
        <circle
          key={candidate.id}
          className={candidate.in_zone ? 'dot dot-in' : 'dot dot-out'}
          cx={x(candidate.lam)}
          cy={y(height(candidate))}
          r="5"
        >
          <title>{describe(candidate)}</title>
        </circle>
      ))}

      {proposed.map((candidate) => (
        <g key={candidate.id}>
          <circle
            className="dot dot-proposed"
            cx={x(candidate.lam)}
            cy={y(height(candidate))}
            r="10"
          >
            <title>{describe(candidate)}</title>
          </circle>
          <text
            className="dot-number"
            x={x(candidate.lam)}
            y={y(height(candidate)) + 4}
            textAnchor="middle"
          >
            {candidate.slot ? SLOT_NUMBER[candidate.slot] : ''}
          </text>
        </g>
      ))}

      {message && (
        <rect
          className={
            message.status === 'held'
              ? 'marker marker-held'
              : 'marker marker-sent'
          }
          x={x(message.lam) - 9}
          y={y(message.effort) - 9}
          width="18"
          height="18"
          rx="3"
          transform={`rotate(45 ${x(message.lam)} ${y(message.effort)})`}
        >
          <title>{`Sent: ${message.text}`}</title>
        </rect>
      )}
    </svg>
  )
}

export default ZoneAxis
