import { useCallback, useEffect, useState } from 'react'
import type { Role } from './api/client'
import InAppNotificationBanner from './components/InAppNotificationBanner'
import AdminScreen from './screens/AdminScreen'
import ClinicianScreen from './screens/ClinicianScreen'
import DemoScreen from './screens/DemoScreen'
import HelperScreen from './screens/HelperScreen'
import JoinForm from './screens/JoinForm'
import Landing from './screens/Landing'
import PatientScreen from './screens/PatientScreen'
import ScreenFrame from './screens/ScreenFrame'
import SettingsScreen from './screens/SettingsScreen'
import {
  clearToken,
  readActiveRole,
  readToken,
  saveActiveRole,
} from './session'

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

  // Si l'utilisateur a déjà une session active, il ne peut pas aller sur la page d'accueil (#/) :
  // redirection automatique vers son écran actif (#/helper ou #/patient).
  // Pour revenir sur l'accueil, il doit explicitement se déconnecter.
  useEffect(() => {
    if (route === 'home') {
      const active = readActiveRole()
      if (active && tokens[active]) {
        window.location.hash = `#/${active}`
      } else if (tokens.helper) {
        window.location.hash = '#/helper'
      } else if (tokens.patient) {
        window.location.hash = '#/patient'
      }
    }
  }, [route, tokens])

  const leave = useCallback((role: Role) => {
    clearToken(role)
    saveActiveRole(null)
    setTokens((current) => ({ ...current, [role]: null }))
    window.location.hash = '#/'
  }, [])
  const leaveHelper = useCallback(() => leave('helper'), [leave])
  const leavePatient = useCallback(() => leave('patient'), [leave])

  const handleAccountSelected = useCallback((role: Role, token: string) => {
    setTokens((current) => ({ ...current, [role]: token }))
    window.location.hash = `#/${role}`
  }, [])

  let content: React.ReactNode

  if (route === 'demo') {
    content = <DemoScreen />
  } else if (route === 'home') {
    content = <Landing onAccountSelected={handleAccountSelected} />
  } else if (route === 'clinician') {
    content = <ClinicianScreen />
  } else if (route === 'settings') {
    content = <SettingsScreen />
  } else if (route === 'admin') {
    content = <AdminScreen />
  } else {
    const token = tokens[route]
    if (!token) {
      content = (
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
    } else {
      content =
        route === 'helper' ? (
          <HelperScreen token={token} onLeave={leaveHelper} />
        ) : (
          <PatientScreen token={token} onLeave={leavePatient} />
        )
    }
  }

  return (
    <>
      <InAppNotificationBanner />
      {content}
    </>
  )
}

export default App
