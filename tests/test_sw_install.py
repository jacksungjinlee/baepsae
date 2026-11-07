# -*- coding: utf-8 -*-
"""The new worker takes over quickly even when the pictures are slow (2026-11-08). sw.js's first job is to delete old
caches (baepsae-v10 kept a frozen corp.json for weeks); v19.3b made install wait for 19 pictures, so on a slow phone
(and on a busy CI machine: smoke_app's 서비스워커 check failed twice on 2026-11-07) the old cache stayed longer.
Install now waits for the picture pre-cache at most INSTALL_WAIT_MS."""
import os
import re
import shutil
import subprocess
import time

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NODE = shutil.which("node")

HARNESS = r"""
const src = require('fs').readFileSync(process.argv[1], 'utf8');
const listeners = {};
const self = { addEventListener: (t, f) => { listeners[t] = f; }, location: { origin: 'https://jack.example' }, skipWaiting() {},
  clients: { claim: async () => {} } };
const never = new Promise(() => {});
const caches = { open: async () => ({ addAll: () => never, put: async () => {} }), keys: async () => [],
  delete: async () => true, match: async () => undefined };
new Function('self', 'caches', 'fetch', 'Response', 'URL', 'console', src)(self, caches, async () => { throw new Error('x'); }, {}, URL, console);
let wait = null;
const t0 = Date.now();
listeners.install({ waitUntil: (p) => { wait = p; } });
wait.then(() => { console.log(String(Date.now() - t0)); process.exit(0); });
"""


def bound_ms():
    m = re.search(r"const INSTALL_WAIT_MS = (\d+);", open(os.path.join(ROOT, "sw.js"), encoding="utf-8").read())
    assert m, "sw.js has no INSTALL_WAIT_MS"
    return int(m.group(1))


def test_the_install_wait_is_short():
    assert 0 < bound_ms() <= 5000


@pytest.mark.skipif(NODE is None, reason="node 가 없어요")
def test_install_finishes_even_when_the_pictures_never_arrive():
    t = time.time()
    r = subprocess.run([NODE, "-e", HARNESS, os.path.join(ROOT, "sw.js")], capture_output=True, text=True, timeout=30)
    assert r.returncode == 0, r.stderr
    assert r.stdout.strip(), "install never finished while the pictures were still loading"
    waited = int(r.stdout.strip())
    assert bound_ms() - 50 <= waited <= bound_ms() + 1500, waited
    assert time.time() - t < 20
