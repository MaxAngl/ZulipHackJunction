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
        onSignedOut() // session inconnue du serveur : on repasse par la connexion
        return
      }
      setError(err instanceof ApiError ? err.message : OFFLINE_MESSAGE)
    },
    [onSignedOut],
  )

  // Une lecture, ignorée si une action est en cours (son résultat fait foi).
  const load = useCallback(
    () =>
      fetcher(token)
        .then((next) => {
          if (!busyRef.current) setHome(next)
        })
        .catch(fail),
    [token, fetcher, fail],
  )

  useEffect(() => {
    const tick = () => {
      if (!busyRef.current) void load()
    }
    tick()
    const timer = window.setInterval(tick, POLL_MS)
    return () => window.clearInterval(timer)
  }, [load])

  // Renvoie le nouvel état, ou null si l'action a échoué (le message est dans `error`).
  const run = useCallback(
    async (action: () => Promise<T>): Promise<T | null> => {
      busyRef.current = true
      setBusy(true)
      setError(null)
      try {
        const next = await action()
        setHome(next)
        return next
      } catch (err) {
        fail(err)
        return null
      } finally {
        busyRef.current = false
        setBusy(false)
      }
    },
    [fail],
  )

  return { home, error, busy, run, refresh: load }
}
