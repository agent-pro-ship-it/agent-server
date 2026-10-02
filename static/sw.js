const CACHE_NAME = apple-agent-v1;
const ASSETS = [/, /index.html, /app.js, /style.css, /manifest.json];

self.addEventListener(install, (e) => {
  e.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(ASSETS))
  );
  self.skipWaiting();
});

self.addEventListener(activate, (e) => {
  e.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(
        keys.map((k) => {
          if (k !== CACHE_NAME) return caches.delete(k);
        })
      )
    )
  );
  self.clients.claim();
});

self.addEventListener(fetch, (e) => {
  if (e.request.method !== GET) return;
  e.respondWith(
    fetch(e.request).catch(() => caches.match(e.request))
  );
});
