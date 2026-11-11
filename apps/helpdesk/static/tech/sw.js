// Weststar ONE tech app service worker. Keeps ONLY the app's own static files (styles, script, icons) so it opens fast.
// Pages with customer or ticket information always come from the server and are never stored on the phone.
const CACHE = "ws-tech-__VERSION__";
const ASSETS = [__ASSETS__];
const OFFLINE = "/tech/offline/";

self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll(ASSETS.concat([OFFLINE]))).then(() => self.skipWaiting()));
});
self.addEventListener("activate", (e) => {
  e.waitUntil(caches.keys().then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k)))).then(() => self.clients.claim()));
});
self.addEventListener("fetch", (e) => {
  const req = e.request;
  if (req.method !== "GET") return;
  const url = new URL(req.url);
  if (url.origin !== location.origin) return;
  if (ASSETS.includes(url.pathname)) {
    e.respondWith(caches.match(req).then((hit) => hit || fetch(req)));
    return;
  }
  if (req.mode === "navigate") {
    // Network only; if there's no signal show the offline notice instead of an old copy.
    e.respondWith(fetch(req).catch(() => caches.match(OFFLINE)));
  }
});
