const CACHE = "wurstbrot-1.0.0-stable";
const ASSETS = ["./", "index.html", "styles.css", "app.js", "solver.mjs", "manifest.webmanifest", "icon.svg", "../../data/samples/WT_Database_2.57.1.67.json"];
self.addEventListener("install", event => event.waitUntil(caches.open(CACHE).then(cache => cache.addAll(ASSETS))));
self.addEventListener("activate", event => event.waitUntil(caches.keys().then(keys => Promise.all(keys.filter(key => key !== CACHE).map(key => caches.delete(key))))));
self.addEventListener("fetch", event => event.respondWith(caches.match(event.request).then(hit => hit || fetch(event.request))));
