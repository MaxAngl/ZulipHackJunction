import { useCallback, useEffect, useRef } from 'react'
import type { TypingSignals } from './api/client'

// Relève la frappe pendant que le patient écrit sa réponse : des durées et des comptes, jamais
// les caractères tapés. Ce sont les signaux de frappe de θ (docs/modele.md, section 11).
//
// Usage : brancher `onInput` sur la zone de texte, appeler `collect()` à l'envoi et joindre
// le résultat à la réponse. `shownKey` change quand une nouvelle demande s'affiche : le
// chronomètre repart.
//
// On écoute les saisies, pas les touches : un clavier de téléphone n'annonce pas ses touches,
// alors que chaque insertion et chaque effacement passe par un événement de saisie.
export function useTypingSignals(shownKey: string | null) {
  const shownAt = useRef(0)
  const firstKeyAt = useRef<number | null>(null)
  const characters = useRef(0)
  const corrections = useRef(0)

  useEffect(() => {
    shownAt.current = performance.now()
    firstKeyAt.current = null
    characters.current = 0
    corrections.current = 0
  }, [shownKey])

  const onInput = useCallback((event: { nativeEvent: Event }) => {
    const native = event.nativeEvent as InputEvent
    if (firstKeyAt.current === null) firstKeyAt.current = performance.now()
    if ((native.inputType ?? '').startsWith('delete')) {
      corrections.current += 1
      characters.current += 1
    } else {
      // Un texte collé d'un bloc compte pour une seule saisie.
      characters.current += Math.max(1, native.data?.length ?? 1)
    }
  }, [])

  // Rien à dire si le patient n'a rien tapé : le signal reste absent, comme une montre non portée.
  const collect = useCallback((): TypingSignals | undefined => {
    if (characters.current === 0 || firstKeyAt.current === null)
      return undefined
    const delay = (firstKeyAt.current - shownAt.current) / 1000
    return {
      characters: characters.current,
      corrections: corrections.current,
      first_key_delay_seconds: Math.max(0, Math.round(delay * 10) / 10),
    }
  }, [])

  return { onInput, collect }
}
