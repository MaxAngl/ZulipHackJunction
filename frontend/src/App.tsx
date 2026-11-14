import { useCallback, useEffect, useState } from 'react'
import type { Role } from './api/client'
import AdminScreen from './screens/AdminScreen'
import ClinicianScreen from './screens/ClinicianScreen'
import DemoScreen from './screens/DemoScreen'
import HelperScreen from './screens/HelperScreen'
import JoinForm from './screens/JoinForm'
import Landing from './screens/Landing'
import PatientScreen from './screens/PatientScreen'
import ScreenFrame from './screens/ScreenFrame'
import SettingsScreen from './screens/SettingsScreen'
import { clearToken, readToken } from './session'

// Adresses : `#/` l'accueil, `#/helper` et `#/patient` la vraie app, `#/demo` la console, `#/clinician` espace médical, `#/settings` paramètres, `#/admin` espace administrateur.
type Route =
  'home' | 'helper' | 'patient' | 'demo' | 'clinician' | 'settings' | 'admin'

function readRoute(): Route {
  const hash = window.location.hash.replace(/^#\/?/, '')
  const pathname = window.location.pathname
    .replace(/^\//, '')
    .replace(/\/$/, '')
  const target = hash || pathname
  return target === 'helper' ||
    target === 'patient' ||
    target === 'demo' ||
    target === 'clinician' ||
    target === 'settings' ||
    target === 'admin'
    ? target
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
  if (route === 'clinician') return <ClinicianScreen />
  if (route === 'settings') return <SettingsScreen />
  if (route === 'admin') return <AdminScreen />

  const token = tokens[route]
  if (!token) {
    return (
      <ScreenFrame showSettings={false}>
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
