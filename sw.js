// 뱁새 서비스워커
// ─────────────────────────────────────────────────────────────
// v9 에서는 앱 파일까지 '캐시 우선'으로 서비스해서, 새 버전을 올려도
// 기존 방문자에게는 옛 화면이 계속 보이는 문제가 있었습니다.
// 이제 화면과 데이터는 '네트워크 우선'으로 받아오고, 캐시는 오프라인일 때만 씁니다.
const CACHE = "baepsae-v10";
const SHELL = ["./", "./baepsae.html", "./manifest.webmanifest", "./icon-192.png", "./icon-512.png"];

self.addEventListener("install", (e) => {
  e.waitUntil(
    caches.open(CACHE)
      .then((c) => Promise.allSettled(SHELL.map((u) => c.add(u))))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (e) => {
  e.waitUntil(
    caches.keys()
      .then((ks) => Promise.all(ks.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

// 새 워커가 준비되면 열려 있는 탭을 한 번 새로 그리게 합니다
self.addEventListener("message", (e) => { if (e.data === "skipWaiting") self.skipWaiting(); });

function netFirst(req) {
  return fetch(req)
    .then((res) => {
      if (res && res.ok) {
        const copy = res.clone();
        caches.open(CACHE).then((c) => c.put(req, copy)).catch(() => {});
      }
      return res;
    })
    .catch(() => caches.match(req).then((hit) => hit || caches.match("./baepsae.html")));
}

self.addEventListener("fetch", (e) => {
  const req = e.request;
  if (req.method !== "GET") return;
  const url = new URL(req.url);
  const isDoc = req.mode === "navigate" || req.destination === "document" ||
                url.pathname.endsWith(".html") || url.pathname.endsWith("/");
  const isData = url.pathname.endsWith("data.json");

  // 화면과 시세 데이터는 항상 최신을 먼저 시도합니다
  if (isDoc || isData) { e.respondWith(netFirst(req)); return; }

  // 아이콘·매니페스트 같은 정적 파일만 캐시 우선
  e.respondWith(
    caches.match(req).then((hit) => hit || fetch(req).then((res) => {
      if (res && res.ok && url.origin === location.origin) {
        const copy = res.clone();
        caches.open(CACHE).then((c) => c.put(req, copy)).catch(() => {});
      }
      return res;
    }).catch(() => caches.match("./baepsae.html")))
  );
});
