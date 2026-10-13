/* Customa service worker: leftover-food alerts (web push).
 *
 * The server sends {title, body, slug, url, tag, character, ...} (backend services/alerts.py).
 * The stand character's picture is drawn on the phone when the customer turns alerts on and
 * kept in IndexedDB (customa/art, key = stand slug) as image data URLs:
 *   icon  - the character on a round blush badge (Android, desktop)
 *   image - a wide "LAST PLATES" banner with the character (Android, expanded)
 * iPhone (iOS 16.4+, Customa on the Home Screen) shows the title and body with the app icon.
 */

const DB = 'customa';
const STORE = 'art';

function readArt(slug) {
  return new Promise((resolve) => {
    if (!slug || !self.indexedDB) return resolve(null);
    const open = indexedDB.open(DB, 1);
    open.onupgradeneeded = () => open.result.createObjectStore(STORE);
    open.onerror = () => resolve(null);
    open.onsuccess = () => {
      try {
        const get = open.result.transaction(STORE, 'readonly').objectStore(STORE).get(slug);
        get.onsuccess = () => resolve(get.result || null);
        get.onerror = () => resolve(null);
      } catch (e) {
        resolve(null);
      }
    };
  });
}

// Fast repeat visits on slow networks: the app's built files (hashed names, never change) are
// kept on the phone; pages always try the network first, so a new deploy shows at once, and
// fall back to the kept copy when offline. API calls (another origin) are never touched.
const SHELL = 'customa-shell-v1';
const MAX_ASSETS = 80;

self.addEventListener('install', () => self.skipWaiting());
self.addEventListener('activate', (event) =>
  event.waitUntil(
    caches
      .keys()
      .then((keys) => Promise.all(keys.filter((k) => k.startsWith('customa-shell-') && k !== SHELL).map((k) => caches.delete(k))))
      .then(() => self.clients.claim()),
  ),
);

async function trim(cache) {
  const keys = await cache.keys();
  for (const k of keys.slice(0, Math.max(0, keys.length - MAX_ASSETS))) await cache.delete(k);
}

self.addEventListener('fetch', (event) => {
  const req = event.request;
  if (req.method !== 'GET') return;
  const url = new URL(req.url);
  if (url.origin !== self.location.origin) return;

  if (req.mode === 'navigate') {
    event.respondWith(
      fetch(req)
        .then((res) => {
          if (res.ok) caches.open(SHELL).then((c) => c.put('/index.html', res.clone()));
          return res;
        })
        .catch(() => caches.open(SHELL).then((c) => c.match('/index.html')).then((r) => r || Response.error())),
    );
    return;
  }

  if (url.pathname.startsWith('/assets/') || url.pathname.startsWith('/icons/')) {
    event.respondWith(
      caches.open(SHELL).then(async (cache) => {
        const hit = await cache.match(req);
        if (hit) return hit;
        const res = await fetch(req);
        if (res.ok) {
          await cache.put(req, res.clone());
          trim(cache);
        }
        return res;
      }),
    );
  }
});

self.addEventListener('push', (event) => {
  let data = {};
  try {
    data = event.data ? event.data.json() : {};
  } catch (e) {
    data = { title: 'Customa', body: event.data ? event.data.text() : '' };
  }
  event.waitUntil(
    readArt(data.slug).then((art) =>
      self.registration.showNotification(data.title || 'Customa', {
        body: data.body || '',
        icon: (art && art.icon) || '/icons/icon-192.png',
        image: (art && art.image) || undefined,
        badge: '/icons/badge-96.png',
        tag: data.tag || 'customa',
        renotify: true,
        requireInteraction: false,
        vibrate: [120, 60, 120, 60, 240],
        timestamp: Date.now(),
        data: { url: data.url || '/' },
        actions: [
          { action: 'come', title: "I'm coming 🏃🏾" },
          { action: 'later', title: 'Not today' },
        ],
      }),
    ),
  );
});

self.addEventListener('notificationclick', (event) => {
  event.notification.close();
  if (event.action === 'later') return;
  const url = new URL((event.notification.data && event.notification.data.url) || '/', self.location.origin).href;
  event.waitUntil(
    self.clients.matchAll({ type: 'window', includeUncontrolled: true }).then((wins) => {
      for (const w of wins) {
        if (w.url.startsWith(url) && 'focus' in w) return w.focus();
      }
      return self.clients.openWindow(url);
    }),
  );
});
