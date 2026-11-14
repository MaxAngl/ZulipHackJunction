import { useCallback, useEffect, useRef, useState } from 'react'
import {
  ApiError,
  getThreads,
  type Role,
  type Thread,
  type ThreadMessage,
  type ThreadsResponse,
} from '../api/client'
import { saveNotification } from '../session'

const POLL_MS = 4000
const OFFLINE_MESSAGE = 'The server is not responding.'

function title(message: ThreadMessage): string {
  switch (message.kind) {
    case 'request':
      return `New request from ${message.sender_name}`
    case 'reply':
      return `${message.sender_name} answered you`
    case 'thanks':
      return `${message.sender_name} says thank you`
    default:
      return `New message from ${message.sender_name}`
  }
}

function newestIncoming(threads: Thread[]): ThreadMessage | null {
  let newest: ThreadMessage | null = null
  for (const thread of threads) {
    for (const message of thread.messages) {
      if (
        !message.mine &&
        (!newest || message.created_at > newest.created_at)
      ) {
        newest = message
      }
    }
  }
  return newest
}

// Les fils de la personne connectée : chargés au montage, rafraîchis toutes les 4 secondes,
// remplacés par la réponse de chaque action. Un message reçu entre deux lectures s'annonce
// dans le bandeau de notification.
export function useThreads(token: string, role: Role, onSignedOut: () => void) {
  const [threads, setThreads] = useState<Thread[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const busyRef = useRef(false)
  const lastIncoming = useRef<number | null>(null)

  const accept = useCallback(
    (next: Thread[]) => {
      const newest = newestIncoming(next)
      const known = lastIncoming.current
      if (newest && known !== null && newest.created_at > known) {
        saveNotification({
          id: `msg-${newest.id}`,
          type: newest.kind === 'request' ? 'new_request' : 'new_message',
          title: title(newest),
          body: newest.text || 'Shared a file',
          timestamp: 'Just now',
          read: false,
          linkHash: `#/${role}`,
        })
      }
      if (known === null || (newest && newest.created_at > known)) {
        lastIncoming.current = newest?.created_at ?? 0
      }
      setThreads(next)
    },
    [role],
  )

  const fail = useCallback(
    (err: unknown) => {
      if (err instanceof ApiError && err.status === 401) {
        onSignedOut()
        return
      }
      setError(err instanceof ApiError ? err.message : OFFLINE_MESSAGE)
    },
    [onSignedOut],
  )

  // Une lecture, ignorée si une action est en cours (son résultat fait foi).
  const refresh = useCallback(
    () =>
      getThreads(token)
        .then((next) => {
          if (busyRef.current) return
          accept(next.threads)
          setError(null)
        })
        .catch(fail),
    [token, accept, fail],
  )

  useEffect(() => {
    const tick = () => {
      if (!busyRef.current) void refresh()
    }
    tick()
    const timer = window.setInterval(tick, POLL_MS)
    return () => window.clearInterval(timer)
  }, [refresh])

  // Renvoie vrai si l'action a réussi.
  const run = useCallback(
    async (action: () => Promise<ThreadsResponse>): Promise<boolean> => {
      busyRef.current = true
      setBusy(true)
      setError(null)
      try {
        accept((await action()).threads)
        return true
      } catch (err) {
        fail(err)
        return false
      } finally {
        busyRef.current = false
        setBusy(false)
      }
    },
    [accept, fail],
  )

  return { threads, error, busy, run, refresh }
}
