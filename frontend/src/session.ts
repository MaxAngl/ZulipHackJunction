import type { Role } from './api/client'

// Un jeton par rôle : le même navigateur peut tenir un compte aidant et un compte patient,
// ce qui permet d'essayer les deux côtés sur une seule machine.
function key(role: Role): string {
  return `needed.token.${role}`
}

export function readToken(role: Role): string | null {
  try {
    return window.localStorage.getItem(key(role))
  } catch {
    return null
  }
}

export function saveToken(role: Role, token: string): void {
  try {
    window.localStorage.setItem(key(role), token)
  } catch {
    // Stockage indisponible (navigation privée) : le compte ne survivra pas au rechargement.
  }
}

export function clearToken(role: Role): void {
  try {
    window.localStorage.removeItem(key(role))
  } catch {
    // Rien à effacer.
  }
}
