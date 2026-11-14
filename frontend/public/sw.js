// Service worker de l'app installée (PWA). Repris de la PR #41 (Rami), simplifié.
//
// Le réseau d'abord, toujours : l'app change souvent pendant le hackathon, et une ancienne
// version servie depuis le cache serait pire qu'une page hors ligne. Le cache ne sert que quand
// le réseau manque. L'API n'est jamais mise en cache : les demandes et les réponses sont vivantes.
const CACHE = 'needed-v1'

self.addEventListener('install', () => self.skipWaiting())

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) =>
        Promise.all(
          keys.filter((key) => key !== CACHE).map((key) => caches.delete(key)),
        ),
      )
      .then(() => self.clients.claim()),
  )
})

self.addEventListener('fetch', (event) => {
  const { request } = event
  const url = new URL(request.url)
  if (
    request.method !== 'GET' ||
    url.origin !== self.location.origin ||
    url.pathname.startsWith('/api/')
  ) {
    return
  }
  event.respondWith(
    fetch(request)
      .then((response) => {
        if (response.ok) {
          const copy = response.clone()
          caches.open(CACHE).then((cache) => cache.put(request, copy))
        }
        return response
      })
      .catch(async () => {
        const cached = await caches.match(request)
        if (cached) return cached
        if (request.mode === 'navigate') return caches.match('/')
        return Response.error()
      }),
  )
})
