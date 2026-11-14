// Poignée de main au trait, en deux couleurs : une main pour l'aidant, une pour le patient.
// Tracé repris de l'icône « handshake » de Lucide (licence ISC, © Lucide Contributors).
type LogoProps = {
  size?: number
}

function Logo({ size = 34 }: LogoProps) {
  return (
    <svg
      className="logo"
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      strokeWidth="1.5"
      strokeLinecap="round"
      strokeLinejoin="round"
      role="img"
      aria-label="Needed"
    >
      <g className="logo-hand-ink">
        <path d="M3 3 2 14l6.5 6.5a1 1 0 1 0 3-3" />
        <path d="M3 4h8" />
        <path d="m11 17 2 2a1 1 0 1 0 3-3" />
        <path d="m14 14 2.5 2.5a1 1 0 1 0 3-3" />
      </g>
      <g className="logo-hand-cyan">
        <path d="m19.5 13.5-3.88-3.88a3 3 0 0 0-4.24 0l-.88.88a1 1 0 1 1-3-3l2.81-2.81a5.79 5.79 0 0 1 7.06-.87l.47.28a2 2 0 0 0 1.42.25L21 4" />
        <path d="m21 3 1 11h-2" />
      </g>
    </svg>
  )
}

export default Logo
