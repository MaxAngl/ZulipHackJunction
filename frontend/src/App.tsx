import { useCallback, useEffect, useState } from 'react'
import { type AccountRole, logout, type SessionResponse } from './api/client'
import InAppNotificationBanner from './components/InAppNotificationBanner'
import Mascot from './components/Mascot'
import AdminScreen from './screens/AdminScreen'
import ClinicianScreen from './screens/ClinicianScreen'
import DemoScreen from './screens/DemoScreen'
import HelperScreen from './screens/HelperScreen'
import JoinForm from './screens/JoinForm'
import Landing from './screens/Landing'
import LoginForm from './screens/LoginForm'
import PatientScreen from './screens/PatientScreen'
import ScreenFrame from './screens/ScreenFrame'
import SettingsScreen from './screens/SettingsScreen'
import { clearToken, readToken, saveToken } from './session'

// Adresses : `#/` l'accueil, `#/login` la connexion, `#/join/helper` et `#/join/patient`
// l'inscription (toujours le formulaire, même si une session est ouverte), `#/helper` et
// `#/patient` la vraie app (inscription si personne n'est connecté), `#/demo` la console, `#/clinician` le portail
// médical, `#/admin` celui de l'équipe, `#/settings` les réglages.
type Route =
  | 'home'
  | 'login'
  | 'join-helper'
  | 'join-patient'
  | 'helper'
  | 'patient'
  | 'demo'
  | 'clinician'
  | 'settings'
  | 'admin'

const ROUTES: Route[] = [
  'login',
  'join-helper',
  'join-patient',
  'helper',
  'patient',
  'demo',
  'clinician',
  'settings',
  'admin',
]
const ROLES: AccountRole[] = ['helper', 'patient', 'clinician', 'admin']

function readRoute(): Route {
  const hash = window.location.hash.replace(/^#\/?/, '')
  const pathname = window.location.pathname
    .replace(/^\//, '')
    .replace(/\/$/, '')
  const target = (hash || pathname).replace('/', '-') as Route
  return ROUTES.includes(target) ? target : 'home'
}

function readTokens(): Record<AccountRole, string | null> {
  return Object.fromEntries(
    ROLES.map((role) => [role, readToken(role)]),
  ) as Record<AccountRole, string | null>
}

function App() {
  const [route, setRoute] = useState<Route>(readRoute)
  const [tokens, setTokens] = useState(readTokens)

  useEffect(() => {
    const onChange = () => setRoute(readRoute())
    window.addEventListener('hashchange', onChange)
    return () => window.removeEventListener('hashchange', onChange)
  }, [])

  // Une session ouverte : le jeton est gardé pour son rôle, et l'on va sur l'écran de ce rôle.
  // Une autre session du même rôle dans ce navigateur est fermée : on ne reste pas connecté
  // sous le compte de quelqu'un d'autre.
  const signIn = useCallback((session: SessionResponse) => {
    const role = session.user.role
    const previous = readToken(role)
    if (previous && previous !== session.token) {
      logout(previous).catch(() => undefined) // déjà fermée : rien à faire
    }
    saveToken(role, session.token)
    setTokens((current) => ({ ...current, [role]: session.token }))
    window.location.hash = `#/${role}`
  }, [])

  const leave = useCallback((role: AccountRole) => {
    const token = readToken(role)
    if (token) logout(token).catch(() => undefined) // déjà fermée : rien à faire
    clearToken(role)
    setTokens((current) => ({ ...current, [role]: null }))
    window.location.hash = '#/'
  }, [])
  const leaveHelper = useCallback(() => leave('helper'), [leave])
  const leavePatient = useCallback(() => leave('patient'), [leave])
  const leaveClinician = useCallback(() => leave('clinician'), [leave])
  const leaveAdmin = useCallback(() => leave('admin'), [leave])

  function staffLogin(title: string, intro: string) {
    return (
      <ScreenFrame showSettings={false}>
        <LoginForm title={title} intro={intro} onSignedIn={signIn} />
      </ScreenFrame>
    )
  }

  let content: React.ReactNode

  if (route === 'demo') {
    content = <DemoScreen />
  } else if (route === 'home') {
    content = <Landing onSignedIn={signIn} />
  } else if (route === 'login') {
    content = (
      <ScreenFrame showSettings={false}>
        <LoginForm signupHref="#/" onSignedIn={signIn} />
      </ScreenFrame>
    )
  } else if (route === 'join-helper' || route === 'join-patient') {
    const role = route === 'join-helper' ? 'helper' : 'patient'
    content = (
      <ScreenFrame showSettings={false}>
        <JoinForm key={role} role={role} onJoined={signIn} />
      </ScreenFrame>
    )
  } else if (route === 'settings') {
    content = <SettingsScreen />
  } else if (route === 'clinician') {
    content = tokens.clinician ? (
      <ClinicianScreen token={tokens.clinician} onLeave={leaveClinician} />
    ) : (
      staffLogin(
        'Clinician portal.',
        'Sign in with the account your clinic received.',
      )
    )
  } else if (route === 'admin') {
    content = tokens.admin ? (
      <AdminScreen token={tokens.admin} onLeave={leaveAdmin} />
    ) : (
      staffLogin('Team portal.', 'Sign in with the team account.')
    )
  } else {
    const token = tokens[route]
    if (!token) {
      content = (
        <ScreenFrame showSettings={false}>
          <JoinForm key={route} role={route} onJoined={signIn} />
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
      {/* La mascotte se promène dans la communauté (aidant, patient), pas sur les pages de connexion, portails ou console. */}
      {(route === 'helper' || route === 'patient') && <Mascot />}
    </>
  )
}

export default App
