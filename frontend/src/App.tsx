import { useCallback, useEffect, useState } from 'react'
import type { Role } from './api/client'
import DemoScreen from './screens/DemoScreen'
import HelperScreen from './screens/HelperScreen'
import JoinForm from './screens/JoinForm'
import Landing from './screens/Landing'
import PatientScreen from './screens/PatientScreen'
import ScreenFrame from './screens/ScreenFrame'
import { clearToken, readToken } from './session'

// Quatre adresses : `#/` l'accueil, `#/helper` et `#/patient` la vraie app, `#/demo` la console.
type Route = 'home' | 'helper' | 'patient' | 'demo'

function readRoute(): Route {
  const path = window.location.hash.replace(/^#\/?/, '')
  return path === 'helper' || path === 'patient' || path === 'demo'
    ? path
    : 'home'
}

function App() {
  const [route, setRoute] = useState<Route>(readRoute)
  const [tokens, setTokens] = useState<Record<Role, string | null>>(() => ({
    helper: readToken('helper'),
    patient: readToken('patient'),
  }))

  useEffect(() => {
    const onChange = () => setRoute(readRoute())
    window.addEventListener('hashchange', onChange)
    return () => window.removeEventListener('hashchange', onChange)
  }, [])

  const leave = useCallback((role: Role) => {
    clearToken(role)
    setTokens((current) => ({ ...current, [role]: null }))
  }, [])
  const leaveHelper = useCallback(() => leave('helper'), [leave])
  const leavePatient = useCallback(() => leave('patient'), [leave])

  if (route === 'demo') return <DemoScreen />
  if (route === 'home') return <Landing />

  const token = tokens[route]
  if (!token) {
    return (
      <ScreenFrame>
        <JoinForm
          key={route}
          role={route}
          onJoined={(joined) =>
            setTokens((current) => ({ ...current, [route]: joined }))
          }
        />
      </ScreenFrame>
    )
  }
  return route === 'helper' ? (
    <HelperScreen token={token} onLeave={leaveHelper} />
  ) : (
    <PatientScreen token={token} onLeave={leavePatient} />
  )
}

export default App
