import type { AccountRole } from './api/client'

// Ce que le navigateur garde pour lui : les jetons de session, le thème, les notifications du
// bandeau et les fils déjà lus. Tout le reste (comptes, profils, fils, notes) vient du backend.

// Un jeton par rôle : le même navigateur peut tenir un compte aidant et un compte patient,
// ce qui permet d'essayer les deux côtés sur une seule machine.
function key(role: AccountRole): string {
  return `needed.token.${role}`
}

export function readToken(role: AccountRole): string | null {
  try {
    return window.localStorage.getItem(key(role))
  } catch {
    return null // stockage indisponible (navigation privée)
  }
}

export function saveToken(role: AccountRole, token: string): void {
  try {
    window.localStorage.setItem(key(role), token)
  } catch {
    // Stockage indisponible : le compte ne survivra pas au rechargement.
  }
}

export function clearToken(role: AccountRole): void {
  try {
    window.localStorage.removeItem(key(role))
  } catch {
    // Rien à effacer.
  }
}

// Le compte de la communauté connecté dans ce navigateur, s'il y en a un (pour les réglages).
export function readMemberToken(): string | null {
  return readToken('patient') ?? readToken('helper')
}

// --- Thème -----------------------------------------------------------------------------

export type ThemePreference = 'auto' | 'light' | 'dark'

export function saveThemePreference(pref: ThemePreference): void {
  try {
    window.localStorage.setItem('needed.theme', pref)
  } catch {
    // ignore
  }
  applyTheme(pref)
}

export function readThemePreference(): ThemePreference {
  try {
    const raw = window.localStorage.getItem('needed.theme')
    if (raw === 'light' || raw === 'dark' || raw === 'auto') return raw
  } catch {
    // ignore
  }
  return 'auto'
}

export function applyTheme(pref: ThemePreference): void {
  const isDark =
    pref === 'dark' ||
    (pref === 'auto' &&
      window.matchMedia &&
      window.matchMedia('(prefers-color-scheme: dark)').matches)

  if (isDark) {
    document.documentElement.setAttribute('data-theme', 'dark')
  } else {
    document.documentElement.removeAttribute('data-theme')
  }
}

// --- Fils déjà lus -----------------------------------------------------------------------

// Pour chaque fil, l'heure du dernier message vu (secondes, comme le backend).
type SeenMarks = Record<string, number>

function seenKey(userId: string): string {
  return `needed.seen.${userId}`
}

export function readSeen(userId: string): SeenMarks {
  try {
    const raw = window.localStorage.getItem(seenKey(userId))
    if (raw) return JSON.parse(raw) as SeenMarks
  } catch {
    // ignore
  }
  return {}
}

export function markSeen(userId: string, threadId: string, at: number): void {
  try {
    const marks = readSeen(userId)
    if ((marks[threadId] ?? 0) >= at) return
    marks[threadId] = at
    window.localStorage.setItem(seenKey(userId), JSON.stringify(marks))
  } catch {
    // ignore
  }
}

// --- Badges déjà vus ---------------------------------------------------------------------

// Les badges débloqués que le profil a déjà montrés : un nouveau badge n'est fêté qu'une fois.
function badgesKey(userId: string): string {
  return `needed.badges.${userId}`
}

export function readUnlockedBadges(userId: string): string[] {
  try {
    const raw = window.localStorage.getItem(badgesKey(userId))
    if (raw) return JSON.parse(raw) as string[]
  } catch {
    // ignore
  }
  return []
}

export function saveUnlockedBadges(userId: string, keys: string[]): void {
  try {
    window.localStorage.setItem(badgesKey(userId), JSON.stringify(keys))
  } catch {
    // ignore
  }
}

// --- Bandeau de notification -------------------------------------------------------------

export type NotificationType =
  'new_request' | 'new_message' | 'pending_24h' | 'declined_limit'

export type AppNotification = {
  id: string
  type: NotificationType
  title: string
  body: string
  timestamp: string
  read?: boolean
  linkHash?: string
}

export function readNotifications(): AppNotification[] {
  try {
    const raw = window.localStorage.getItem('needed.notifications')
    if (raw) return JSON.parse(raw) as AppNotification[]
  } catch {
    // ignore
  }
  return []
}

// Le bandeau affiche la notification tout de suite (l'événement). On la garde comme déjà lue :
// au rechargement, le bandeau ne rejoue que les notifications non lues, et celle-ci a été vue.
export function saveNotification(notif: AppNotification): void {
  try {
    const list = readNotifications()
    const seen = { ...notif, read: true }
    const updated = [seen, ...list.filter((n) => n.id !== notif.id)].slice(
      0,
      20,
    )
    window.localStorage.setItem('needed.notifications', JSON.stringify(updated))
  } catch {
    // ignore
  }
  window.dispatchEvent(
    new CustomEvent('needed:notification', { detail: notif }),
  )
}

export function dismissNotification(id: string): void {
  try {
    const list = readNotifications()
    const updated = list.filter((n) => n.id !== id)
    window.localStorage.setItem('needed.notifications', JSON.stringify(updated))
  } catch {
    // ignore
  }
  window.dispatchEvent(
    new CustomEvent('needed:notification:dismiss', { detail: id }),
  )
}
