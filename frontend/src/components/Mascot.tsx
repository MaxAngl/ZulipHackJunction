import { type CSSProperties, useEffect, useRef, useState } from 'react'
import './Mascot.css'

// La mascotte de Needed (issue #64) : un petit singe bleu, dessin original, qui se promène en
// bas de l'écran, s'assoit, cligne des yeux, fait coucou. Touché, il saute et dit un mot.
// Il ne bloque rien : seul son corps reçoit les clics. Immobile si le système demande moins
// d'animations.

type Mood = 'walk' | 'sit' | 'wave'

const SIZE = 64
const SPEED = 36 // pixels par seconde
const PHRASES = [
  'Hi there!',
  "You're doing great!",
  'Got a banana?',
  'Someone might need you today!',
  'Take your time.',
  'Wheee!',
  'Nice to see you!',
  'One small favour at a time.',
]

function prefersLessMotion(): boolean {
  return (
    window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ?? false
  )
}

function Mascot() {
  const trackRef = useRef<HTMLDivElement>(null)
  const xRef = useRef(24)
  const [x, setX] = useState(24)
  const [facing, setFacing] = useState<1 | -1>(1)
  const [mood, setMood] = useState<Mood>('sit')
  const [walkSeconds, setWalkSeconds] = useState(0)
  const [jumping, setJumping] = useState(false)
  const [bubble, setBubble] = useState<string | null>(null)

  // La promenade : marcher vers un point au hasard, s'asseoir un moment, parfois faire coucou.
  useEffect(() => {
    if (prefersLessMotion()) return
    let timer = 0
    const next = () => {
      const width = trackRef.current?.clientWidth ?? 320
      const target = Math.round(Math.random() * Math.max(0, width - SIZE))
      const distance = Math.abs(target - xRef.current)
      if (Math.random() < 0.65 && distance > 40) {
        const seconds = distance / SPEED
        setFacing(target > xRef.current ? 1 : -1)
        setWalkSeconds(seconds)
        setMood('walk')
        setX(target)
        xRef.current = target
        timer = window.setTimeout(() => {
          setMood('sit')
          timer = window.setTimeout(next, 1500 + Math.random() * 2500)
        }, seconds * 1000)
      } else {
        setMood(Math.random() < 0.35 ? 'wave' : 'sit')
        timer = window.setTimeout(next, 2200 + Math.random() * 2800)
      }
    }
    timer = window.setTimeout(next, 1200)
    return () => window.clearTimeout(timer)
  }, [])

  // Touché : un saut et un petit mot, qui s'efface tout seul.
  useEffect(() => {
    if (!bubble) return
    const timer = window.setTimeout(() => setBubble(null), 2200)
    return () => window.clearTimeout(timer)
  }, [bubble])

  function poke() {
    setJumping(true)
    setBubble(PHRASES[Math.floor(Math.random() * PHRASES.length)])
    window.setTimeout(() => setJumping(false), 700)
  }

  return (
    <div className="mascot-track" ref={trackRef}>
      <div
        className="mascot"
        style={{
          transform: `translateX(${x}px)`,
          transitionDuration: `${walkSeconds}s`,
        }}
      >
        {bubble && (
          <span className="mascot-bubble" role="status">
            {bubble}
          </span>
        )}
        <button
          type="button"
          className={`mascot-body mascot-${mood} ${jumping ? 'mascot-jump' : ''}`}
          style={{ '--facing': facing } as CSSProperties}
          aria-label="Needed's little monkey. Say hi"
          onClick={poke}
        >
          <svg
            viewBox="0 0 80 80"
            width={SIZE}
            height={SIZE}
            aria-hidden="true"
          >
            <path
              className="mascot-tail"
              d="M27 60 C13 62 9 47 17 43 C23 40 26 49 20 50"
            />
            <g className="mascot-leg mascot-leg-left">
              <rect x="30" y="61" width="8" height="12" rx="4" />
              <ellipse
                className="mascot-cream"
                cx="33"
                cy="74"
                rx="6"
                ry="3.4"
              />
            </g>
            <g className="mascot-leg mascot-leg-right">
              <rect x="42" y="61" width="8" height="12" rx="4" />
              <ellipse
                className="mascot-cream"
                cx="47"
                cy="74"
                rx="6"
                ry="3.4"
              />
            </g>
            <ellipse className="mascot-fur" cx="40" cy="56" rx="15" ry="13" />
            <ellipse className="mascot-belly" cx="40" cy="58" rx="9" ry="8" />
            <g className="mascot-arm mascot-arm-left">
              <rect x="21" y="48" width="7" height="15" rx="3.5" />
              <circle className="mascot-cream" cx="24.5" cy="63" r="3.6" />
            </g>
            <g className="mascot-arm mascot-arm-right">
              <rect x="52" y="48" width="7" height="15" rx="3.5" />
              <circle className="mascot-cream" cx="55.5" cy="63" r="3.6" />
            </g>
            <g className="mascot-head">
              <circle className="mascot-fur" cx="20" cy="30" r="7" />
              <circle className="mascot-ear-in" cx="20" cy="30" r="3.8" />
              <circle className="mascot-fur" cx="60" cy="30" r="7" />
              <circle className="mascot-ear-in" cx="60" cy="30" r="3.8" />
              <circle className="mascot-fur" cx="40" cy="30" r="17" />
              <path
                className="mascot-tuft"
                d="M37 14 C38 9 44 9 43 13 C46 11 47 15 44 16"
              />
              <path
                className="mascot-face"
                d="M40 47 C30 47 25 41 26 34 C27 28 33 27 36 30 C38 28 42 28 44 30 C47 27 53 28 54 34 C55 41 50 47 40 47Z"
              />
              <g className="mascot-eyes">
                <ellipse cx="34.5" cy="34" rx="2.6" ry="3.2" />
                <ellipse cx="45.5" cy="34" rx="2.6" ry="3.2" />
                <circle className="mascot-glint" cx="35.4" cy="32.9" r="0.95" />
                <circle className="mascot-glint" cx="46.4" cy="32.9" r="0.95" />
              </g>
              <ellipse
                className="mascot-blush"
                cx="30"
                cy="40"
                rx="2.8"
                ry="1.6"
              />
              <ellipse
                className="mascot-blush"
                cx="50"
                cy="40"
                rx="2.8"
                ry="1.6"
              />
              <path className="mascot-mouth" d="M37 41.5 Q40 44.5 43 41.5" />
            </g>
          </svg>
        </button>
      </div>
    </div>
  )
}

export default Mascot
