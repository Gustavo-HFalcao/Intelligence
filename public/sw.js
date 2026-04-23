// Bomtempo Dashboard — Service Worker (Level 1 PWA: installability + asset cache)
const CACHE_NAME = 'bomtempo-v2';

// Assets to pre-cache on install — always served instantly from cache
const PRECACHE = [
  '/',
  '/manifest.json',
  '/banner.png',
  '/icon.png',
];

// Install: pre-cache shell + brand assets
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(PRECACHE))
  );
  self.skipWaiting();
});

// Activate: clean up old caches
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(
        keys.filter((k) => k !== CACHE_NAME).map((k) => caches.delete(k))
      )
    )
  );
  self.clients.claim();
});

// Determine if a request is for a static asset (images, fonts, icons)
function isStaticAsset(url) {
  return /\.(png|jpg|jpeg|webp|svg|ico|woff2?|ttf|otf)(\?.*)?$/.test(url.pathname);
}

// Fetch strategy:
//  - Static assets (images, fonts): cache-first → instant, no flicker
//  - Everything else: network-first → real-time data
self.addEventListener('fetch', (event) => {
  if (event.request.method !== 'GET') return;
  if (!event.request.url.startsWith(self.location.origin)) return;
  if (event.request.headers.get('upgrade') === 'websocket') return;

  const url = new URL(event.request.url);

  if (isStaticAsset(url)) {
    // Cache-first: serve from cache immediately, update in background
    event.respondWith(
      caches.open(CACHE_NAME).then(async (cache) => {
        const cached = await cache.match(event.request);
        if (cached) return cached;
        const response = await fetch(event.request);
        if (response.ok) cache.put(event.request, response.clone());
        return response;
      })
    );
  } else {
    // Network-first: app needs real-time state via WebSocket
    event.respondWith(
      fetch(event.request).catch(() => caches.match(event.request))
    );
  }
});
