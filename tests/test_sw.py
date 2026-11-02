# -*- coding: utf-8 -*-
"""서비스워커(sw.js): app.html(뱁새 2.0 미리 보기)도 baepsae.html 과 똑같이 '네트워크 우선, 캐시는 오프라인일 때만'.
(v17.5 의 sw.js 가 같은 사이트의 모든 요청을 이렇게 다뤄서, v18.3 은 sw.js 를 바꾸지 않고 이 검사로 확인해요.)

Node 안에서 sw.js 를 그대로 돌려요 (self · caches · fetch 를 흉내 내요).
- 온라인: app.html · baepsae.html · data.json 은 언제나 네트워크에서 새로 받아요 (캐시에 옛것이 있어도)
- 오프라인: app.html 을 열면 캐시해 둔 app.html (baepsae.html 이 아니에요). app.html 캐시가 없으면 지금 앱
- 오프라인: baepsae.html 은 예전과 같아요. 다른 사이트 요청은 건드리지 않아요
"""
import json
import os
import shutil
import subprocess

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NODE = shutil.which("node")

HARNESS = r"""
const fs = require('fs');
const src = fs.readFileSync(process.argv[1], 'utf8');
const BASE = 'https://jack.example/baepsae/';
const listeners = {};
let store = [];             // [{ url, body }]
let online = true, netCalls = 0, version = 'v1';
const self = { addEventListener: (t, f) => { listeners[t] = f; }, location: { origin: 'https://jack.example' },
  skipWaiting() {}, clients: { claim: async () => {} } };
const key = (u) => new URL(u, BASE);
const caches = {
  open: async () => ({ put: async (req, res) => { const u = key(req.url).href; store = store.filter((e) => e.url !== u); store.push({ url: u, body: res.body }); } }),
  match: async (req, opts) => {
    const u = key(typeof req === 'string' ? req : req.url);
    const hit = store.find((e) => { const k = new URL(e.url); return k.pathname === u.pathname && ((opts && opts.ignoreSearch) || k.search === u.search); });
    return hit ? { body: hit.body, fromCache: true } : undefined;
  },
  keys: async () => ['baepsae-v17-5'], delete: async () => true,
};
const fetch = async (req) => { netCalls++; if (!online) throw new Error('offline');
  return { ok: true, type: 'basic', body: 'net ' + version + ' ' + new URL(req.url).pathname, clone() { return { body: this.body }; } }; };
const Response = { error: () => ({ body: 'ERROR' }) };
new Function('self', 'caches', 'fetch', 'Response', 'URL', src)(self, caches, fetch, Response, URL);
async function get(path, mode) {
  let p = null;
  listeners.fetch({ request: { method: 'GET', url: new URL(path, BASE).href, mode: mode || 'cors' }, respondWith: (x) => { p = x; } });
  if (!p) return 'PASS-THROUGH';
  const r = await p; await new Promise((ok) => setTimeout(ok, 0));
  return r ? r.body : 'NOTHING';
}
(async () => {
  const out = {};
  out.app1 = await get('app.html', 'navigate');
  out.old1 = await get('baepsae.html', 'navigate');
  out.data1 = await get('data.json');
  version = 'v2';
  out.app2 = await get('app.html', 'navigate');          // 캐시에 v1 이 있어도 네트워크의 v2
  out.data2 = await get('data.json');
  online = false;
  out.appOff = await get('app.html?from=home', 'navigate');
  out.oldOff = await get('baepsae.html', 'navigate');
  out.dataOff = await get('data.json');
  out.missOff = await get('corp.json');
  store = store.filter((e) => !e.url.endsWith('/app.html'));
  out.appNoCache = await get('app.html', 'navigate');
  out.other = await get('https://fonts.example/x.css');
  out.netCalls = netCalls;
  console.log(JSON.stringify(out));
})();
"""


@pytest.mark.skipif(NODE is None, reason="node 가 없어요")
def test_app_html_is_network_first_and_offline_falls_back_to_itself():
    r = subprocess.run([NODE, "-e", HARNESS, os.path.join(ROOT, "sw.js")], capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr
    got = json.loads(r.stdout)
    assert got["app1"] == "net v1 /baepsae/app.html" and got["old1"] == "net v1 /baepsae/baepsae.html"
    assert got["app2"] == "net v2 /baepsae/app.html" and got["data2"] == "net v2 /baepsae/data.json"   # 네트워크 우선
    assert got["appOff"] == "net v2 /baepsae/app.html"            # 오프라인: 캐시해 둔 app.html (지금 앱이 아니에요)
    assert got["oldOff"] == "net v1 /baepsae/baepsae.html"        # 지금 앱은 예전 그대로
    assert got["dataOff"] == "net v2 /baepsae/data.json" and got["missOff"] == "ERROR"
    assert got["appNoCache"] == "net v1 /baepsae/baepsae.html"    # app.html 캐시가 없으면 지금 앱이라도
    assert got["other"] == "PASS-THROUGH"


def test_sw_keeps_one_cache_and_mentions_app_html():
    src = open(os.path.join(ROOT, "sw.js"), encoding="utf-8").read()
    assert 'const CACHE = "baepsae-v17-5";' in src            # 캐시 이름은 그대로 (smoke_app 의 서비스워커 장면)
    assert "styleguide" not in src
    sh = open(os.path.join(ROOT, "build-app.sh"), encoding="utf-8").read()   # app.html 만 등록해요 (미리 보기는 안 해요)
    assert 'navigator.serviceWorker.register("./sw.js")' in sh


# ── Part F (메인 주소 → app.html): 예전 워커와 캐시를 가진 재방문자 ──
RETURNING = HARNESS.split("(async () => {", 1)[0] + r"""
(async () => {
  const out = {};
  // 예전 방문 때 캐시된 것: index.html 은 baepsae.html 로 보내던 판, 지금 앱도 캐시돼 있어요
  store.push({ url: BASE + 'index.html', body: 'OLD index -> baepsae.html' }, { url: BASE, body: 'OLD root -> baepsae.html' },
             { url: BASE + 'baepsae.html', body: 'OLD baepsae.html' });
  version = 'F';
  out.root = await get('', 'navigate');                 // https://…/baepsae/ 를 다시 열면
  out.index = await get('index.html', 'navigate');
  out.app = await get('app.html', 'navigate');
  online = false;
  out.rootOff = await get('', 'navigate');              // 오프라인: 마지막으로 받은 새 index (app.html 로 보내는 판)
  out.appOff = await get('app.html?x=1', 'navigate');
  store = store.filter((e) => !e.url.endsWith('/app.html'));
  out.appNoCache = await get('app.html', 'navigate');   // app.html 을 한 번도 못 받았으면 지금 앱이라도
  console.log(JSON.stringify(out));
})();
"""


@pytest.mark.skipif(NODE is None, reason="node 가 없어요")
def test_returning_visitors_get_the_new_redirect_on_their_next_online_visit():
    """sw.js 는 바꾸지 않아요: 화면 이동은 언제나 네트워크 먼저라서, 예전에 캐시된 index.html 대신 새 index.html(→ app.html)을 받아요."""
    r = subprocess.run([NODE, "-e", RETURNING, os.path.join(ROOT, "sw.js")], capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr
    got = json.loads(r.stdout)
    assert got["root"] == "net F /baepsae/" and got["index"] == "net F /baepsae/index.html", got
    assert got["app"] == "net F /baepsae/app.html"
    assert got["rootOff"] == "net F /baepsae/" and got["appOff"] == "net F /baepsae/app.html"
    assert got["appNoCache"] == "OLD baepsae.html"
