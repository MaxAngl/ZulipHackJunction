import { useCallback, useEffect, useRef, useState } from 'react'
import {
  ApiError,
  getLoop,
  propose,
  reset,
  respond,
  send,
  setTheta,
  skip,
  type LoopState,
} from '../api/client'
import HelperPhone from '../components/HelperPhone'
import HistoryPanel from '../components/HistoryPanel'
import Logo from '../components/Logo'
import LoopConsole from '../components/LoopConsole'
import LoopSteps from '../components/LoopSteps'
import PatientPhone from '../components/PatientPhone'

// `?view=helper` ou `?view=patient` affiche un seul téléphone, pour une démo sur deux appareils.
type View = 'all' | 'helper' | 'patient' | 'console'

const POLL_MS = 2500
const OFFLINE_MESSAGE = 'The server is not responding.'

function readView(): View {
  const value = new URLSearchParams(window.location.search).get('view')
  return value === 'helper' || value === 'patient' || value === 'console'
    ? value
    : 'all'
}

// La console de démo : un patient simulé, et tout ce que la boucle fait, visible sur un écran.
function DemoScreen() {
  const [state, setState] = useState<LoopState | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [draftTheta, setDraftTheta] = useState<number | null>(null)
  const busyRef = useRef(false)
  const latestTheta = useRef<number | null>(null)
  const sendingTheta = useRef(false)
  const view = readView()

  const run = useCallback(async (action: () => Promise<LoopState>) => {
    busyRef.current = true
    setBusy(true)
    setError(null)
    try {
      setState(await action())
    } catch (err) {
      setError(err instanceof ApiError ? err.message : OFFLINE_MESSAGE)
    } finally {
      busyRef.current = false
      setBusy(false)
    }
  }, [])

  // Rafraîchit l'état régulièrement : plusieurs appareils restent ainsi synchronisés.
  useEffect(() => {
    let cancelled = false
    const idle = () => !busyRef.current && latestTheta.current === null
    const refresh = () => {
      if (!idle()) return
      getLoop()
        .then((next) => {
          if (!cancelled && idle()) setState(next)
        })
        .catch(() => {
          if (!cancelled) setError(OFFLINE_MESSAGE)
        })
    }
    refresh()
    const timer = window.setInterval(refresh, POLL_MS)
    return () => {
      cancelled = true
      window.clearInterval(timer)
    }
  }, [])

  // Le curseur envoie la dernière valeur dès que la requête précédente est revenue :
  // la zone suit le doigt sans inonder le serveur.
  const pushTheta = useCallback(async () => {
    if (sendingTheta.current) return
    sendingTheta.current = true
    try {
      while (latestTheta.current !== null) {
        const value = latestTheta.current
        const next = await setTheta(value)
        setState(next)
        if (latestTheta.current === value) {
          latestTheta.current = null
          setDraftTheta(null)
        }
      }
    } catch (err) {
      latestTheta.current = null
      setDraftTheta(null)
      setError(err instanceof ApiError ? err.message : OFFLINE_MESSAGE)
    } finally {
      sendingTheta.current = false
    }
  }, [])

  function slideTheta(value: number) {
    latestTheta.current = value
    setDraftTheta(value)
    void pushTheta()
  }

  if (!state) {
    return <main className="loading">{error ?? 'Loading…'}</main>
  }

  const showAll = view === 'all'
  return (
    <div className={`app view-${view}`}>
      <header className="topbar">
        <a className="brand" href="#/">
          <Logo />
          <div className="brand-text">
            <span className="brand-name">needed</span>
            {(showAll || view === 'console') && (
              <span className="brand-tagline">
                A community where recovering patients are the ones who help.
              </span>
            )}
          </div>
        </a>
        {(showAll || view === 'console') && (
          <button
            type="button"
            className="button button-ghost"
            disabled={busy}
            onClick={() => void run(reset)}
          >
            Reset demo
          </button>
        )}
      </header>

      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}

      {showAll && (
        <LoopSteps
          current={state.round.step}
          complete={state.round.stage === 'answered'}
        />
      )}

      <main className="board">
        {(showAll || view === 'helper') && (
          <HelperPhone
            state={state}
            busy={busy}
            onSend={(body) => void run(() => send(body))}
            onSkip={() => void run(skip)}
          />
        )}
        {(showAll || view === 'console') && (
          <LoopConsole
            state={state}
            theta={draftTheta ?? state.theta}
            busy={busy}
            onTheta={slideTheta}
            onRun={() => void run(propose)}
          />
        )}
        {(showAll || view === 'patient') && (
          <PatientPhone
            state={state}
            busy={busy}
            onRespond={(action) => void run(() => respond(action))}
          />
        )}
      </main>

      {(showAll || view === 'console') && (
        <>
          <HistoryPanel history={state.history} />
          <footer className="disclaimer">
            Demo with simulated data: the patient state comes from a simulated
            sensor and the zone model is a hand-written stand-in. Not a medical
            device.
          </footer>
        </>
      )}
    </div>
  )
}

export default DemoScreen
