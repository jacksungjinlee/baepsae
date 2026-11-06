// 뱁새 서비스워커 v17.5
// ─────────────────────────────────────────────────────────────
// 예전 v10 워커는 data.json 말고 다른 JSON(corp·macro·disc)을 '캐시 우선'으로 줘서,
// 7~8월에 방문한 기기에는 그때 받은 데이터가 계속 남아 있었어요.
// 이제 같은 사이트의 모든 요청은 '네트워크 우선'이고, 캐시는 오프라인일 때만 써요.
// 새 워커가 켜지면 이름이 다른 캐시(baepsae-v10 등)를 모두 지웁니다.
// CV 링크 (2026-11-05): baepsae.html 을 표시(?from=app)도 # 도 없이 열면 app.html 로 가요 (template.html). 캐시 이름을 바꿔서
// 휴대폰이 예전에 캐시한 페이지 대신 새 규칙을 받아요. 오프라인 화면 이동은 그 주소의 캐시 → app.html → baepsae.html 순서.
// baepsae.html 의 내용이 다른 주소(app.html 등)에서 열리면 보내지 않아서 두 페이지 사이를 오가지 않아요 (tests/test_sw.py).
// 회사 로고 (v19.3a): logos/ 의 파일은 이 워커가 건드리지 않고 캐시에 넣지도 않아요 (tests/test_logos_branch.py). 로고는 아직
// 캐시된 적이 없어서 캐시 이름은 그대로예요; 워커 파일이 바뀌었으니 브라우저가 새 워커를 받아요.
// 홈 화면 아이콘 (v19.5a, 2026-11-06): 새 이름의 그림(icon-v19-*.png · apple-touch-icon-v19.png)이라 어떤 캐시에도 없어요. 예전
// icon-*.png 는 그대로 두되 쓰지 않아요. 이 줄로 워커 파일이 바뀌어서 휴대폰이 새 워커를 받아요 (캐시 이름은 그대로: 네트워크 우선이라
// 온라인이면 새 페이지와 새 아이콘을 받아요).
const CACHE = "baepsae-v19-cv";

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
  if (/\/logos\/[^/]*$/.test(url.pathname)) return;   // v19.3a 회사 로고(logos/)는 이 캐시에 넣지 않아요: 오프라인이면 글자 표시
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
        .then((hit) => hit || (req.mode !== "navigate" ? Response.error()
          : caches.match("./app.html", { ignoreSearch: true })
            .then((app) => app || caches.match("./baepsae.html", { ignoreSearch: true })))))
  );
});
