# -*- coding: utf-8 -*-
"""CV 링크 (Jack, 2026-11-05): https://jacksungjinlee.github.io/baepsae/baepsae.html 은 Jack 의 이력서에 있어요.

- 2.0 에서 온 표시(?from=app)도 # 도 없이 열면, 예전 뱁새를 그리기 전에 app.html 로 보내요 (location.replace: 기록이 늘지 않아요)
- 표시는 src/links.js 의 OLD_APP 한 곳에서 정하고, 2.0 이 예전 뱁새를 여는 모든 링크(OLD_APP · OLD_LINKS)가 그것을 써요.
  template.html 의 첫 스크립트도 같은 "from=app" 을 읽어요 (아래에서 둘이 같은지 봐요)
- 남는 경우: 표시 · # (예전에 공유한 링크, 2.0 의 바로가기) · 이 탭에서 이미 예전 뱁새를 열었음 · 10초 안에 이미 한 번 보냄(되돌이 막기).
  # 때문에 남으면 주소에 표시를 붙여요 (예전 뱁새가 # 을 지운 뒤 새로고침해도 남아요). ?utm_* · ?trk= 같은 다른 값은 상관없어요
- 저장소: 이 탭의 sessionStorage 표시 두 개만. localStorage 는 읽기만 해요 (GoatCounter 를 건너뛸지)
- GoatCounter: 보낼 때 한 번만, 경로 '/baepsae/baepsae.html→app' 으로 따로 세요. 로컬·시험 주소 · ?dev=1 · 개발 표시가 있으면 안 세요.
  남을 때는 예전 뱁새의 원래 페이지뷰 경로 그대로 (표시를 빼요)
- 서비스워커: 오프라인일 때 두 페이지 사이를 오가지 않아요 (sw.js + 이 스크립트를 함께 돌려 봐요)
- 링크 미리 보기: 크롤러는 JS 를 돌리지 않으니, 빌드한 baepsae.html 에 og-v19 제목·그림 태그가 그대로 있어야 해요
브라우저에서 실제로 여는 검사는 tests/smoke_launch.py 의 'CV 링크' 장면들이에요.
"""
import json
import os
import re
import shutil
import subprocess

import pytest

from buildapp import built

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NODE = shutil.which("node")
LIVE = "https://jacksungjinlee.github.io/baepsae/"


def read(p):
    with open(os.path.join(ROOT, p), encoding="utf-8") as f:
        return f.read()


def scripts(html):
    return re.findall(r"<script>(.*?)</script>", html, flags=re.S)


def redirect_script(html):
    found = [s for s in scripts(html) if 'MARK="from=app"' in s]
    assert len(found) == 1, len(found)
    return found[0]


# ── Node 에서 template.html 의 첫 스크립트를 그대로 돌려요 (location · history · 저장소 · navigator 를 흉내 내요) ──
HARNESS = r"""
const SRC = process.argv[1];
const cases = JSON.parse(process.argv[2]);
function store(init, name, log) {
  if (init === 'throw') return { getItem() { throw new Error('blocked'); }, setItem() { throw new Error('blocked'); } };
  const m = Object.assign({}, init || {});
  return { getItem: (k) => (Object.prototype.hasOwnProperty.call(m, k) ? m[k] : null),
           setItem: (k, v) => { m[k] = String(v); log.push(name + ':' + k); }, dump: () => m };
}
function run(c, session) {
  const url = new URL(c.href);
  const out = { replace: [], replaceState: [], write: [], beacons: [], images: [], writes: [] };
  const location = { pathname: url.pathname, search: url.search, hash: url.hash, hostname: url.hostname, protocol: url.protocol,
                     href: url.href, replace: (u) => out.replace.push(new URL(u, url.href).href) };
  const history = { state: { keep: 1 }, replaceState: (s, t, u) => out.replaceState.push([s, new URL(u, url.href).href]) };
  const ss = session || store(c.session || {}, 'session', out.writes);
  const ls = store(c.local || {}, 'local', out.writes);
  const window = {};
  Object.defineProperty(window, 'sessionStorage', { get() { if (c.session === 'throw') throw new Error('denied'); return ss; } });
  window.top = c.inFrame ? {} : window;
  const document = { documentElement: { style: {} }, referrer: c.referrer || '', visibilityState: c.prerender ? 'prerender' : 'visible',
                     write: (h) => out.write.push(h) };
  const navigator = { webdriver: !!c.webdriver };
  if (c.beacon !== 'none') navigator.sendBeacon = (u) => { out.beacons.push(u); return c.beacon !== 'refuse'; };
  function Image() { const o = {}; Object.defineProperty(o, 'src', { set: (u) => out.images.push(u) }); return o; }
  const D = { now: () => c.now || 1700000000000 };
  new Function('window', 'location', 'history', 'document', 'navigator', 'screen', 'Image', 'Date', 'localStorage', SRC)(
    window, location, history, document, navigator, { width: 390 }, Image, D, ls);
  out.hidden = document.documentElement.style.display === 'none';
  out.session = ss && ss.dump ? ss.dump() : null;
  out.local = ls.dump ? ls.dump() : null;
  if (window.goatcounter && typeof window.goatcounter.path === 'function') {
    out.gcPath = (c.gcPaths || []).map((p) => window.goatcounter.path(p));
  }
  return out;
}
const res = {};
for (const [name, c] of Object.entries(cases)) {
  if (c.sequence) {            // same tab, several visits: one sessionStorage
    const log = [];
    const ss = store({}, 'session', log);
    res[name] = c.sequence.map((v) => run(v, ss));
  } else {
    res[name] = run(c);
  }
}
console.log(JSON.stringify(res));
"""


def decide(cases, html=None):
    src = redirect_script(html or read("template.html"))
    r = subprocess.run([NODE, "-e", HARNESS, src, json.dumps(cases)], capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


def gc_params(u):
    from urllib.parse import parse_qs, urlsplit
    s = urlsplit(u)
    return f"{s.scheme}://{s.netloc}{s.path}", {k: v[0] for k, v in parse_qs(s.query).items()}


@pytest.mark.skipif(NODE is None, reason="node 가 없어요")
def test_plain_visits_go_to_2_0_and_marked_or_hashed_visits_stay():
    L = LIVE + "baepsae.html"
    got = decide({
        "plain": {"href": L},
        "extensionless": {"href": LIVE + "baepsae"},
        "utm": {"href": L + "?utm_source=x&utm_medium=cv"},
        "trk": {"href": L + "?trk=public_profile"},
        "otherFrom": {"href": L + "?from=linkedin"},
        "emptyHash": {"href": L + "#"},
        "marker": {"href": L + "?from=app"},
        "markerWithOthers": {"href": L + "?dev=1&from=app&x=2"},
        "hash": {"href": L + "#corp=005930"},
        "hashUnknown": {"href": L + "#foo"},
        "hashWithUtm": {"href": L + "?utm_source=x#macro"},
        "tabFlag": {"href": L, "session": {"baepsae_old_tab": "1"}},
        "otherPage": {"href": LIVE + "app.html"},
        "root": {"href": LIVE},
        "index": {"href": LIVE + "index.html"},
    })
    for name in ("plain", "extensionless", "utm", "trk", "otherFrom", "emptyHash"):
        r = got[name]
        assert r["replace"] == [LIVE + "app.html"], (name, r["replace"])               # location.replace: 기록이 늘지 않아요
        assert r["hidden"] and r["write"] == ['<plaintext style="display:none">'], name   # 아무것도 그리지 않고 파싱을 멈춰요
        assert r["replaceState"] == [] and "baepsae_old_tab" not in r["session"], name
    for name in ("marker", "markerWithOthers"):
        r = got[name]
        assert r["replace"] == [] and r["replaceState"] == [] and not r["hidden"] and r["write"] == [], name
        assert r["session"] == {"baepsae_old_tab": "1"}, name                          # 이 탭은 예전 뱁새에 들어왔어요
    # # 때문에 남으면 주소에 표시를 붙여요 (# 과 다른 값은 그대로, history.state 도 그대로)
    assert got["hash"]["replaceState"] == [[{"keep": 1}, L + "?from=app#corp=005930"]] and got["hash"]["replace"] == []
    assert got["hashUnknown"]["replaceState"] == [[{"keep": 1}, L + "?from=app#foo"]]
    assert got["hashWithUtm"]["replaceState"] == [[{"keep": 1}, L + "?utm_source=x&from=app#macro"]]
    assert got["tabFlag"]["replace"] == [] and got["tabFlag"]["replaceState"] == [[{"keep": 1}, L + "?from=app"]]
    for name in ("otherPage", "root", "index"):                    # 서비스워커가 다른 주소에 예전 뱁새를 줘도 보내지 않아요
        r = got[name]
        assert r["replace"] == r["replaceState"] == r["write"] == r["writes"] == [] and not r["hidden"], name


@pytest.mark.skipif(NODE is None, reason="node 가 없어요")
def test_redirect_guard_and_storage():
    L = LIVE + "baepsae.html"
    t = 1700000000000
    got = decide({
        # 같은 탭: 보낸 지 10초 안에 다시 오면 남아요 (되돌이 막기), 그 뒤로는 이 탭이 예전 뱁새에 들어온 것으로 봐요
        "loop": {"sequence": [{"href": L, "now": t}, {"href": L, "now": t + 3000}, {"href": L, "now": t + 60000}]},
        # 10초가 지나면 다시 보내요
        "later": {"sequence": [{"href": L, "now": t}, {"href": L, "now": t + 10001}]},
        # 저장소가 막힌 브라우저(사생활 보호 등): 오류 없이 그대로 보내거나 남아요
        "blocked": {"href": L, "session": "throw", "local": "throw"},
        "blockedHash": {"href": L + "#macro", "session": "throw", "local": "throw"},
        "saved": {"href": L, "local": {"baepsae_v10_slots": "[{\"id\":\"s1\"}]", "baepsae_v10_slot_s1": "{}", "baepsae_lang": "en"}},
    })
    first, again, third = got["loop"]
    assert first["replace"] == [LIVE + "app.html"] and again["replace"] == [] and third["replace"] == []
    assert again["replaceState"][0][1] == L + "?from=app" and again["session"]["baepsae_old_tab"] == "1"
    assert [len(x["replace"]) for x in got["later"]] == [1, 1]
    assert got["blocked"]["replace"] == [LIVE + "app.html"] and got["blocked"]["writes"] == []
    assert got["blockedHash"]["replace"] == [] and got["blockedHash"]["replaceState"][0][1] == L + "?from=app#macro"
    s = got["saved"]                                              # 저장한 포트폴리오: 아무것도 옮기거나 지우지 않아요
    assert s["local"] == {"baepsae_v10_slots": "[{\"id\":\"s1\"}]", "baepsae_v10_slot_s1": "{}", "baepsae_lang": "en"}
    assert s["writes"] == ["session:baepsae_cv_sent"] and s["session"] == {"baepsae_cv_sent": str(t)}   # 이 탭의 표시 하나만


@pytest.mark.skipif(NODE is None, reason="node 가 없어요")
def test_goatcounter_counts_the_cv_path_once_and_never_on_local_or_dev():
    L = LIVE + "baepsae.html"
    got = decide({
        "live": {"href": L, "referrer": "https://www.linkedin.com/", "webdriver": False},
        "liveUtm": {"href": L + "?utm_source=cv", "webdriver": True},
        "noBeacon": {"href": L, "beacon": "none"},
        "refused": {"href": L, "beacon": "refuse"},
        "local127": {"href": "http://127.0.0.1:8000/baepsae.html"},
        "localhost": {"href": "http://localhost:8000/baepsae/baepsae.html"},
        "lan": {"href": "http://192.168.0.7/baepsae.html"},
        "file": {"href": "file:///home/jack/baepsae/baepsae.html"},
        "devFlag": {"href": L, "local": {"baepsae_dev": "1"}},
        "devParam": {"href": L + "?dev=1"},
        "devOff": {"href": L + "?dev=0", "local": {"baepsae_dev": "1"}},
        "skipgc": {"href": L, "local": {"skipgc": "t"}},
        "frame": {"href": L, "inFrame": True},
        "prerender": {"href": L, "prerender": True},
        "stay": {"href": L + "?from=app", "gcPaths": ["/baepsae/baepsae.html?from=app", "/baepsae/baepsae.html?dev=1&from=app",
                                                       "/baepsae/baepsae.html?from=app&x=1", "/baepsae/baepsae.html", "evt-lang-en"]},
        "stayHash": {"href": L + "#macro", "gcPaths": ["/baepsae/baepsae.html?from=app"]},
    })
    live = got["live"]
    assert len(live["beacons"]) == 1 and live["images"] == [], live            # 한 번만 (sendBeacon: 페이지를 떠나도 가요)
    base, q = gc_params(live["beacons"][0])
    snippet = re.search(r'var code="([a-z0-9-]+)";', read("template.html")).group(1)
    assert base == f"https://{snippet}.goatcounter.com/count", base           # 지금 페이지들의 GoatCounter 와 같은 사이트
    assert q["p"] == "/baepsae/baepsae.html→app" and q["r"] == "https://www.linkedin.com/" and q["s"] == "390", q
    assert q["t"] == "CV link → 2.0" and "b" not in q and "q" not in q and re.fullmatch(r"[0-9a-z]{1,5}", q["rnd"]), q
    _, q2 = gc_params(got["liveUtm"]["beacons"][0])
    assert q2["q"] == "?utm_source=cv" and q2["b"] == "153" and "r" not in q2, q2   # count.js 처럼: 캠페인 값 · 자동 브라우저 표시
    assert got["noBeacon"]["images"] and got["refused"]["images"] and len(got["refused"]["beacons"]) == 1   # sendBeacon 이 없으면 그림으로
    for name in ("local127", "localhost", "lan", "file", "devFlag", "devParam", "devOff", "skipgc", "frame", "prerender"):
        r = got[name]
        assert r["beacons"] == [] and r["images"] == [], name                  # 로컬·시험 주소 · 개발 표시: 세지 않아요
        assert len(r["replace"]) == 1, name                                     # 보내기는 그대로
    assert got["local127"]["replace"] == ["http://127.0.0.1:8000/app.html"]
    assert got["devParam"]["replace"] == [LIVE + "app.html?dev=1"] and got["devOff"]["replace"] == [LIVE + "app.html?dev=0"]
    for name in ("stay", "stayHash"):                                           # 남을 때: 세지 않고, 예전 뱁새의 원래 경로로 세요
        assert got[name]["beacons"] == [] and got[name]["images"] == [], name
    assert got["stay"]["gcPath"] == ["/baepsae/baepsae.html", "/baepsae/baepsae.html?dev=1", "/baepsae/baepsae.html?x=1",
                                     "/baepsae/baepsae.html", "evt-lang-en"]
    assert got["stayHash"]["gcPath"] == ["/baepsae/baepsae.html"]
    assert "gcPath" not in got["live"]


# ── 서비스워커 + 이 스크립트: 오프라인일 때 두 페이지 사이를 오가지 않아요 ──
LOOP = r"""
const fs = require('fs');
const [swPath, src, plan] = [process.argv[1], process.argv[2], JSON.parse(process.argv[3])];
const BASE = 'https://jacksungjinlee.github.io/baepsae/';
const listeners = {};
let store = [];
const self = { addEventListener: (t, f) => { listeners[t] = f; }, location: { origin: 'https://jacksungjinlee.github.io' },
  skipWaiting() {}, clients: { claim: async () => {} } };
const caches = {
  open: async () => ({ put: async () => {} }),
  match: async (req, opts) => {
    const u = new URL(typeof req === 'string' ? req : req.url, BASE);
    const hit = store.find((e) => { const k = new URL(e.url); return k.pathname === u.pathname && ((opts && opts.ignoreSearch) || k.search === u.search); });
    return hit ? { body: hit.body } : undefined;
  },
  keys: async () => [], delete: async () => true,
};
const fetch = async () => { throw new Error('offline'); };
const Response = { error: () => ({ body: 'ERROR' }) };
new Function('self', 'caches', 'fetch', 'Response', 'URL', fs.readFileSync(swPath, 'utf8'))(self, caches, fetch, Response, URL);
async function serve(href) {
  let p = null;
  listeners.fetch({ request: { method: 'GET', url: href, mode: 'navigate' }, respondWith: (x) => { p = x; } });
  const r = await p;
  return r ? r.body : 'NOTHING';
}
function decide(href, ss, now) {      // the old app's first script, run on whatever page the worker served at this address
  const url = new URL(href);
  let to = null;
  const window = { sessionStorage: ss };
  window.top = window;
  new Function('window', 'location', 'history', 'document', 'navigator', 'screen', 'Image', 'Date', 'localStorage', src)(
    window, { pathname: url.pathname, search: url.search, hash: url.hash, hostname: url.hostname, protocol: url.protocol,
              replace: (u) => { to = new URL(u, href).href; } },
    { state: null, replaceState() {} }, { documentElement: { style: {} }, referrer: '', write() {}, visibilityState: 'visible' },
    { webdriver: true, sendBeacon: () => true }, { width: 390 }, function () { return {}; }, { now: () => now },
    { getItem: () => '1' });                                  // dev browser: no GoatCounter in this test
  return to;
}
(async () => {
  const out = {};
  for (const [name, c] of Object.entries(plan)) {
    store = c.cached.map((p) => ({ url: BASE + p, body: p.startsWith('app') ? 'APP' : p.startsWith('baepsae') ? 'OLD' : 'INDEX' }));
    const m = {};
    const ss = { getItem: (k) => (k in m ? m[k] : null), setItem: (k, v) => { m[k] = String(v); } };
    const hops = [];
    let href = BASE + c.open, now = 1700000000000;
    for (let i = 0; i < 8; i++) {
      const body = await serve(href);
      hops.push([href.slice(BASE.length), body]);
      if (body !== 'OLD') break;                 // app.html (2.0), index.html → app.html, or nothing: this page never sends back
      const to = decide(href, ss, now);
      if (!to) break;
      href = to; now += 300;
    }
    out[name] = hops;
  }
  console.log(JSON.stringify(out));
})();
"""


@pytest.mark.skipif(NODE is None, reason="node 가 없어요")
def test_offline_service_worker_and_redirect_never_loop():
    states = {"both": ["app.html", "baepsae.html"], "oldOnly": ["baepsae.html"], "appOnly": ["app.html"], "none": [],
              "allPages": ["app.html", "baepsae.html?from=app", "index.html"]}
    opens = ["baepsae.html", "baepsae.html?utm_source=x", "baepsae.html?from=app", "baepsae.html#macro", "app.html", "", "index.html",
             "anything.html"]
    plan = {f"{s}|{o}": {"cached": c, "open": o} for s, c in states.items() for o in opens}
    src = redirect_script(read("template.html"))
    r = subprocess.run([NODE, "-e", LOOP, os.path.join(ROOT, "sw.js"), src, json.dumps(plan)], capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr
    got = json.loads(r.stdout)
    for k, hops in got.items():
        assert len(hops) <= 2, (k, hops)                                    # 많아야 한 번 보내요: 오가지 않아요
    # 둘 다 캐시에 있으면: 예전 뱁새(캐시) → app.html(캐시)
    assert got["both|baepsae.html"] == [["baepsae.html", "OLD"], ["app.html", "APP"]]
    assert got["both|baepsae.html?utm_source=x"] == [["baepsae.html?utm_source=x", "OLD"], ["app.html", "APP"]]
    assert got["both|baepsae.html?from=app"] == [["baepsae.html?from=app", "OLD"]]
    assert got["both|baepsae.html#macro"] == [["baepsae.html#macro", "OLD"]]
    # app.html 이 캐시에 없으면: app.html 주소에 예전 뱁새가 열리고, 거기서 멈춰요
    assert got["oldOnly|baepsae.html"] == [["baepsae.html", "OLD"], ["app.html", "OLD"]]
    assert got["oldOnly|app.html"] == [["app.html", "OLD"]] and got["oldOnly|"] == [["", "OLD"]]
    # 캐시에 없는 화면은 2.0 먼저 (sw.js)
    assert got["appOnly|baepsae.html"] == [["baepsae.html", "APP"]] and got["both|anything.html"] == [["anything.html", "APP"]]
    assert got["none|baepsae.html"] == [["baepsae.html", "NOTHING"]]
    assert got["allPages|"] == [["", "APP"]] and got["allPages|baepsae.html"] == [["baepsae.html", "OLD"], ["app.html", "APP"]]


# ── 소스 · 빌드 결과 ──
def test_marker_is_defined_once_and_every_2_0_link_carries_it():
    links = read("src/links.js")
    m = re.findall(r'export const OLD_APP = "\./baepsae\.html\?([^"#]+)";', links)
    assert m == ["from=app"], m
    assert redirect_script(read("template.html")).count('MARK="from=app"') == 1      # template.html 이 읽는 표시와 같아요
    routes = read("src/v2/routes.js")
    assert 'import { OLD_APP } from "../links.js";' in routes and "export { OLD_APP };" in routes
    assert not re.search(r'["\']\./baepsae\.html', routes), "routes.js 는 src/links.js 의 OLD_APP 만 써요"
    for name in ("app.html",):                                                      # 2.0 의 모든 예전 뱁새 링크에 표시가 있어요
        html = built(name)
        uses = re.findall(r"baepsae\.html[^\"'`]{0,12}", html)
        assert uses and all(u.startswith("baepsae.html?from=app") for u in uses), sorted(set(uses))
    for f in os.listdir(os.path.join(ROOT, "src", "v2")):                            # 다른 곳에서 예전 주소를 직접 만들지 않아요
        if f.endswith((".js", ".jsx")):
            code = re.sub(r"//[^\n]*", "", read(os.path.join("src", "v2", f)))
            assert "baepsae.html" not in code, f


def test_redirect_runs_first_in_the_built_page():
    tpl, old = read("template.html"), read("baepsae.html")
    s = redirect_script(old)
    assert s == redirect_script(tpl)
    head = old.split("</head>", 1)[0]
    at = head.index(s)
    end = at + len(s)
    sheets = [m.start() for m in re.finditer(r"<link[^>]*stylesheet", head)]
    assert head.count("s.dataset.goatcounter") == 1 and head.count(s) == 1
    assert sheets and end < min(sheets) and end < head.index("s.dataset.goatcounter"), "보내기 스크립트는 글꼴 · GoatCounter 보다 먼저예요"
    assert old.index("<body>") > at and old.index('<div id="root">') > at
    assert head[:at].count("<script") == 1                                            # head 의 첫 스크립트 (이것 자신)
    code = re.sub(r"(?m)^\s*//.*$|\s//\s.*$", "", s)                                  # 주석 빼고 코드만
    assert code.count("L.replace(") == 1 and code.count('L.replace("./app.html"') == 1   # 보내는 곳은 한 군데 (location.replace)
    assert "assign(" not in code and "href=" not in code and "pushState" not in code
    assert "localStorage.setItem" not in code and "removeItem" not in code             # 저장소는 읽기만 (sessionStorage 표시 두 개 빼고)
    assert set(re.findall(r'put\("([a-z_]+)"', code)) == {"baepsae_old_tab", "baepsae_cv_sent"}
    # build-app.sh 가 app.html 로 가져가는 것은 GoatCounter 조각뿐이에요: 보내기 스크립트는 app.html 에 없어요
    assert 'MARK="from=app"' not in built("app.html") and 'MARK="from=app"' not in built("app-preview.html")


def test_link_preview_stays_in_the_built_page():
    """크롤러(카카오톡 · 슬랙 · 링크드인)는 JS 를 돌리지 않아요: baepsae.html 링크도 새 미리 보기(제목 · og-v19 그림)를 보여요."""
    old = read("baepsae.html")
    head = old.split("</head>", 1)[0]
    title = "뱁새 — 내 기준으로 만드는 포트폴리오"
    img = "https://jacksungjinlee.github.io/baepsae/og-v19.png"
    want = [f"<title>{title}</title>", f'<meta property="og:title" content="{title}">', f'<meta name="twitter:title" content="{title}">',
            f'<meta property="og:image" content="{img}">', f'<meta name="twitter:image" content="{img}">',
            '<meta property="og:image:width" content="1200">', '<meta property="og:image:height" content="630">',
            '<meta name="twitter:card" content="summary_large_image">', '<meta property="og:type" content="website">']
    at = head.index(redirect_script(old))
    for w in want:
        assert head.count(w) == 1 and head.index(w) < at, w                          # 보내기 스크립트보다 앞, <head> 안에 한 번
    assert "/og.png" not in old and os.path.exists(os.path.join(ROOT, "og-v19.png"))
