// 뱁새 서비스워커 v17.5
// ─────────────────────────────────────────────────────────────
// 예전 v10 워커는 data.json 말고 다른 JSON(corp·macro·disc)을 '캐시 우선'으로 줘서,
// 7~8월에 방문한 기기에는 그때 받은 데이터가 계속 남아 있었어요.
// 이제 같은 사이트의 모든 요청은 '네트워크 우선'이고, 캐시는 오프라인일 때만 써요.
// 새 워커가 켜지면 이름이 다른 캐시(baepsae-v10 등)를 모두 지웁니다.
const CACHE = "baepsae-v17-5";

self.addEventListener("install", () => {
  self.skipWaiting();
});

self.addEventListener("activate", (e) => {
  e.waitUntil(
    caches.keys()
      .then((ks) => Promise.all(ks.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("message", (e) => { if (e.data === "skipWaiting") self.skipWaiting(); });

self.addEventListener("fetch", (e) => {
  const req = e.request;
  if (req.method !== "GET") return;
  const url = new URL(req.url);
  if (url.origin !== self.location.origin) return;   // 글꼴·통계 등 다른 사이트 요청은 브라우저에 맡겨요
  e.respondWith(
    fetch(req)
      .then((res) => {
        if (res && res.ok && res.type === "basic") {
          const copy = res.clone();
          caches.open(CACHE).then((c) => c.put(req, copy)).catch(() => {});
        }
        return res;
      })
      .catch(() => caches.match(req, { ignoreSearch: req.mode === "navigate" })
        .then((hit) => hit || (req.mode === "navigate" ? caches.match("./baepsae.html", { ignoreSearch: true }) : Response.error())))
  );
});
