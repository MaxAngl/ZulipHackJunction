import { useEffect, useRef, useState } from 'react'
import './Mascot.css'

// La mascotte de Needed (issue #64) : un petit singe bleu, dessin original. Il se promène par
// petits bonds en bas de l'écran, fait parfois un grand saut, grimpe se suspendre par la queue
// à la barre du haut et s'y balance, puis se laisse tomber. Il s'assoit, cligne des yeux, fait
// coucou ; touché, il saute et dit un mot. Seul son corps reçoit les clics. Immobile si le
// système demande moins d'animations.
//
// Les trajectoires sont calculées image par image (requestAnimationFrame) et écrites
// directement dans le style : React ne redessine que quand la posture change.

type Pose = 'sit' | 'hop' | 'air' | 'hang' | 'land' | 'wave'

const SIZE = 64
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

const linear = (t: number) => t
const easeInOut = (t: number) =>
  t < 0.5 ? 2 * t * t : 1 - (-2 * t + 2) ** 2 / 2
const easeOut = (t: number) => 1 - (1 - t) ** 2 // un saut ralentit en montant
const easeIn = (t: number) => t * t // une chute accélère

function prefersLessMotion(): boolean {
  return (
    window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ?? false
  )
}

function between(low: number, high: number): number {
  return low + Math.random() * (high - low)
}

function Mascot() {
  const trackRef = useRef<HTMLDivElement>(null)
  const bodyRef = useRef<HTMLDivElement>(null)
  const buttonRef = useRef<HTMLButtonElement>(null)
  const [pose, setPose] = useState<Pose>('sit')
  const [jumping, setJumping] = useState(false)
  const [bubble, setBubble] = useState<string | null>(null)

  // La vie du singe : une suite d'actions au hasard, chacune une ou plusieurs trajectoires.
  useEffect(() => {
    const track = trackRef.current
    const body = bodyRef.current
    const button = buttonRef.current
    if (!track || !body || !button) return
    let alive = true
    let frame = 0
    const timers: number[] = []
    const pos = { x: 24, y: 0 }

    const place = () => {
      body.style.transform = `translate(${pos.x}px, ${pos.y}px)`
    }
    const face = (target: number) => {
      if (Math.abs(target - pos.x) > 2) {
        button.style.setProperty('--facing', target > pos.x ? '1' : '-1')
      }
    }
    const ground = () =>
      track.clientHeight -
      SIZE -
      (document.querySelector('.bottom-nav') ? 84 : 12)
    const ceiling = () => {
      const bar = document.querySelector('.topbar')
      return bar ? bar.getBoundingClientRect().bottom - 8 : null
    }
    const spot = () =>
      Math.round(between(0, Math.max(0, track.clientWidth - SIZE)))
    const wait = (ms: number) =>
      new Promise<void>((resolve) => {
        timers.push(window.setTimeout(resolve, ms))
      })
    // Une trajectoire : ligne droite déformée par une parabole de hauteur `arc`.
    const fly = (
      toX: number,
      toY: number,
      ms: number,
      arc: number,
      ease: (t: number) => number,
    ) =>
      new Promise<void>((resolve) => {
        const fromX = pos.x
        const fromY = pos.y
        const start = performance.now()
        const step = (now: number) => {
          if (!alive) return resolve()
          const t = Math.min(1, (now - start) / ms)
          const e = ease(t)
          pos.x = fromX + (toX - fromX) * e
          pos.y = fromY + (toY - fromY) * e - arc * 4 * t * (1 - t)
          place()
          if (t < 1) frame = requestAnimationFrame(step)
          else resolve()
        }
        frame = requestAnimationFrame(step)
      })

    const land = async () => {
      setPose('land')
      await wait(260)
      setPose('sit')
    }
    // Petits bonds jusqu'à un point du sol.
    const hopTo = async (target: number) => {
      face(target)
      setPose('hop')
      while (alive && Math.abs(target - pos.x) > 3) {
        const stride =
          Math.sign(target - pos.x) *
          Math.min(between(34, 52), Math.abs(target - pos.x))
        await fly(
          pos.x + stride,
          ground(),
          between(300, 380),
          between(12, 22),
          linear,
        )
      }
      await land()
    }
    // Un grand saut, haut et loin.
    const leapTo = async (target: number) => {
      face(target)
      setPose('hop')
      await wait(160)
      setPose('air')
      await fly(
        target,
        ground(),
        between(700, 900),
        between(80, 130),
        easeInOut,
      )
      await land()
    }
    // Grimper se suspendre par la queue à la barre du haut, s'y balancer, peut-être s'y
    // déplacer, puis se laisser tomber.
    const hang = async () => {
      const bar = ceiling()
      if (bar === null) return leapTo(spot())
      const x = spot()
      face(x)
      setPose('hop')
      await wait(160)
      setPose('air')
      await fly(x, bar, between(650, 800), 30, easeOut)
      setPose('hang')
      await wait(between(2200, 4200))
      if (Math.random() < 0.5) {
        const along = spot()
        face(along)
        await fly(along, bar, Math.abs(along - pos.x) * 9 + 400, 0, easeInOut)
        await wait(between(1200, 2400))
      }
      setPose('air')
      await fly(
        pos.x + between(-30, 30),
        ground(),
        between(600, 750),
        0,
        easeIn,
      )
      await land()
    }

    const live = async () => {
      await wait(1200)
      while (alive) {
        if (Math.abs(pos.y - ground()) > 2) {
          // L'écran a changé sous lui (barre du bas apparue ou disparue) : il retombe.
          setPose('air')
          await fly(pos.x, ground(), 450, 0, easeIn)
          await land()
        }
        const roll = Math.random()
        if (roll < 0.42) await hopTo(spot())
        else if (roll < 0.62) await leapTo(spot())
        else if (roll < 0.8) await hang()
        else {
          setPose(Math.random() < 0.45 ? 'wave' : 'sit')
          await wait(between(1800, 3500))
          setPose('sit')
        }
        await wait(between(700, 2200))
      }
    }

    pos.y = ground()
    place()
    body.classList.add('mascot-ready')
    if (!prefersLessMotion()) void live()
    return () => {
      alive = false
      cancelAnimationFrame(frame)
      timers.forEach((timer) => window.clearTimeout(timer))
    }
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
      <div className="mascot" ref={bodyRef}>
        {bubble && (
          <span className="mascot-bubble" role="status">
            {bubble}
          </span>
        )}
        <button
          ref={buttonRef}
          type="button"
          className={`mascot-body mascot-${pose} ${jumping ? 'mascot-jump' : ''}`}
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
