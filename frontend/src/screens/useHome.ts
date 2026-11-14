import { useCallback, useEffect, useRef, useState } from 'react'
import { ApiError } from '../api/client'

const POLL_MS = 4000
const OFFLINE_MESSAGE = 'The server is not responding.'

// État d'un écran de la vraie app : chargé au montage, rafraîchi régulièrement (une demande ou
// une réponse peut arriver à tout moment), et remplacé par le résultat de chaque action.
export function useHome<T>(
  token: string,
  fetcher: (token: string) => Promise<T>,
  onSignedOut: () => void,
) {
  const [home, setHome] = useState<T | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const busyRef = useRef(false)

  const fail = useCallback(
    (err: unknown) => {
      if (err instanceof ApiError && err.status === 401) {
        onSignedOut() // jeton inconnu du serveur : on repasse par l'inscription
        return
      }
      setError(err instanceof ApiError ? err.message : OFFLINE_MESSAGE)
    },
    [onSignedOut],
  )

  useEffect(() => {
    let cancelled = false
    const refresh = () => {
      if (busyRef.current) return
      fetcher(token)
        .then((next) => {
          if (!cancelled && !busyRef.current) setHome(next)
        })
        .catch((err: unknown) => {
          if (!cancelled) fail(err)
        })
    }
    refresh()
    const timer = window.setInterval(refresh, POLL_MS)
    return () => {
      cancelled = true
      window.clearInterval(timer)
    }
  }, [token, fetcher, fail])

  const run = useCallback(
    async (action: () => Promise<T>) => {
      busyRef.current = true
      setBusy(true)
      setError(null)
      try {
        setHome(await action())
      } catch (err) {
        fail(err)
      } finally {
        busyRef.current = false
        setBusy(false)
      }
    },
    [fail],
  )

  return { home, error, busy, run }
}
