// Served at the root path (see app/routes/pages.py:/sw.js) so its default
// scope covers "/" and "/m", not just "/static/". Caches the static shell
// only - API calls and file bytes are always fetched fresh over the network.
const CACHE = "nahardrop-shell-v1";
const SHELL = [
  "/static/css/styles.css",
  "/static/js/theme.js",
  "/static/js/chunked-uploader.js",
  "/static/js/upload.js",
  "/static/js/download.js",
  "/static/js/pair.js",
  "/static/js/mobile.js",
  "/static/manifest.json",
];

self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(CACHE).then((cache) => cache.addAll(SHELL)));
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
  );
});

self.addEventListener("fetch", (event) => {
  const url = new URL(event.request.url);
  if (url.pathname.startsWith("/api/") || url.pathname.startsWith("/ws/")) return;
  event.respondWith(caches.match(event.request).then((cached) => cached || fetch(event.request)));
});
