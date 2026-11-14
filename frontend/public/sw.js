// Service Worker minimal pour supporter l'installation PWA et le cache offline de base
const CACHE_NAME = 'needed-pwa-v1'
const ASSETS_TO_CACHE = [
  '/',
  '/index.html',
  '/manifest.webmanifest',
  '/favicon.svg',
  '/icons/icon-192.png',
  '/icons/icon-512.png',
]

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      return cache.addAll(ASSETS_TO_CACHE).catch((err) => {
        console.warn('Pre-cache error:', err)
      })
    }),
  )
  self.skipWaiting()
})

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) => {
      return Promise.all(
        keys.map((key) => {
          if (key !== CACHE_NAME) {
            return caches.delete(key)
          }
        }),
      )
    }),
  )
  self.clients.claim()
})

self.addEventListener('fetch', (event) => {
  // Les requêtes API ne doivent pas être cachées avec cette stratégie
  if (event.request.url.includes('/api/')) {
    return
  }

  // Stratégie Network-first avec fallback cache pour les assets et navigation
  event.respondWith(
    fetch(event.request)
      .then((response) => {
        // Mettre à jour le cache si c'est une requête GET valide
        if (event.request.method === 'GET' && response.status === 200) {
          const responseClone = response.clone()
          caches.open(CACHE_NAME).then((cache) => {
            cache.put(event.request, responseClone)
          })
        }
        return response
      })
      .catch(async () => {
        const cached = await caches.match(event.request)
        if (cached) return cached
        if (event.request.mode === 'navigate') {
          return caches.match('/index.html')
        }
      }),
  )
})
