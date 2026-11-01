# -*- coding: utf-8 -*-
"""app.html · app-preview.html 를 임시 폴더에 빌드해요 (bash build-app.sh DIR).

app.html 은 v17.5.1 필드가 실제 데이터에 들어올 때까지 커밋하지 않아요 (v18.3 머지 조건). 그래서 app.html 이 필요한 검사는
저장소의 파일이 아니라 지금 소스로 새로 빌드한 것을 봐요. 한 번 빌드하면 같은 실행 안에서는 다시 쓰여요."""
import os
import subprocess
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_DIR = {}


def built_dir():
    if "d" not in _DIR:
        d = tempfile.mkdtemp(prefix="baepsae-app-build-")
        r = subprocess.run(["bash", "build-app.sh", d], cwd=ROOT, capture_output=True, text=True, encoding="utf-8")
        assert r.returncode == 0, r.stdout + r.stderr
        _DIR["d"] = d
    return _DIR["d"]


def built(name):
    with open(os.path.join(built_dir(), name), encoding="utf-8") as f:
        return f.read()
