import { useState } from 'react'
import { ApiError, login, type SessionResponse } from '../api/client'
import QuickLoginModal from '../components/QuickLoginModal'

type LoginFormProps = {
  title?: string
  intro?: string
  // Lien vers l'inscription, pour l'aidant et le patient ; absent pour le clinicien et l'admin.
  signupHref?: string
  onSignedIn: (session: SessionResponse) => void
}

// Connexion par e-mail et mot de passe, commune à tous les comptes.
function LoginForm({
  title = 'Welcome back.',
  intro = 'Sign in with the email and password you chose.',
  signupHref,
  onSignedIn,
}: LoginFormProps) {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [showQuickLogin, setShowQuickLogin] = useState(false)

  async function submit() {
    setBusy(true)
    setError(null)
    try {
      onSignedIn(await login(email.trim(), password))
    } catch (err) {
      setError(
        err instanceof ApiError ? err.message : 'The server is not responding.',
      )
    } finally {
      setBusy(false)
    }
  }

  const ready = email.trim() !== '' && password !== ''

  return (
    <form
      className="stack"
      onSubmit={(event) => {
        event.preventDefault()
        if (ready && !busy) void submit()
      }}
    >
      <h1>{title}</h1>
      <p className="quiet">{intro}</p>
      <label className="field">
        <span>Email</span>
        <input
          type="email"
          value={email}
          required
          autoComplete="email"
          placeholder="you@example.com"
          onChange={(event) => setEmail(event.target.value)}
        />
      </label>
      <label className="field">
        <span>Password</span>
        <input
          type="password"
          value={password}
          required
          autoComplete="current-password"
          onChange={(event) => setPassword(event.target.value)}
        />
      </label>
      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
      <button
        type="submit"
        className="button button-primary button-wide"
        disabled={!ready || busy}
      >
        {busy ? 'Signing in…' : 'Sign in'}
      </button>

      <button
        type="button"
        className="button-quick-demo"
        onClick={() => setShowQuickLogin(true)}
      >
        Try a demo account
      </button>

      {signupHref && (
        <p className="quiet text-center">
          New here? <a href={signupHref}>Create an account</a>
        </p>
      )}

      <QuickLoginModal
        isOpen={showQuickLogin}
        onClose={() => setShowQuickLogin(false)}
        onSignedIn={onSignedIn}
      />
    </form>
  )
}

export default LoginForm
