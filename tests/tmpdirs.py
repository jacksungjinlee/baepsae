# -*- coding: utf-8 -*-
"""스모크 시험의 임시 폴더 (Jack 승인, 2026-11-07).

전에는 스모크 시험이 시험 사이트를 tempfile.mkdtemp 로 만들고 지우지 않아서 4,000개 가까이 쌓여 디스크를 채웠어요. 이제는:
  · make(prefix)  시스템 임시 폴더 안에 폴더를 만들고, 그 안에 표시 파일(.baepsae-test-tmp: 시험 이름 · 접두어 · 실행 번호 ·
                  프로세스 번호)을 써서 이번 실행의 목록에 올려요. 접두어는 'baepsae-' 로 시작해야 해요.
  · run(main)     시험의 main() 을 돌리고, 끝에 finish(통과 여부)를 불러요. main() 이 예외로 멈추면 실패로 봐요(폴더를 남겨요).
                  main() 의 반환값(종료 코드)과 예외는 그대로 돌려줘요.
  · finish(passed)
      통과  이번 실행이 만든 폴더만 지워요 (표시 파일의 실행 번호로 확인). 다른 폴더는 보지도 않아요.
      실패  이번 실행의 폴더는 남기고 위치를 찍어요(디버깅용). 그리고 같은 시험의 그 전 실패 폴더를 지워요 — 표시 파일이 이 시험
            것이고, 그 실행이 이미 끝난 것만 (같은 시험이 다른 창에서 아직 돌고 있으면 그대로 둬요). 그래서 남는 건 가장 최근에
            실패한 실행의 폴더뿐이에요. 이번 실행이 남길 폴더가 하나도 없으면 그 전 실패 폴더도 지우지 않아요.
절대 지우지 않는 것: 표시 파일이 없거나 · 읽을 수 없거나 · 다른 시험 것인 폴더, 시스템 임시 폴더 바로 아래가 아닌 것, 바로가기(심볼릭
링크), 이름이 'baepsae-' 로 시작하지 않는 것.
시험 코드가 이미 지우는 폴더('끝나면 지워요')는 그대로 지워지고, 여기서는 없는 폴더로 건너뛰어요.
검사 · 장면 · 결과 줄(stdout) · 종료 코드는 바꾸지 않아요. 이 도우미의 알림은 stderr 로만 나가고, 정리하다 오류가 나도 크게 알릴 뿐
시험 결과는 바꾸지 않아요 (정리는 검사가 아니니까요).
pytest 안에서는 conftest.py 가 tempfile.tempdir 를 실행 폴더로 바꾸고 끝나면 통째로 지워요 (finish 는 부르지 않아요)."""
import json
import os
import shutil
import socket
import sys
import tempfile
import time

MARK = ".baepsae-test-tmp"
PREFIX = "baepsae-"
SHOW = 20                                   # 실패한 실행에서 남긴 폴더 위치를 이만큼 찍고 나머지는 개수만
_HOST = socket.gethostname()
_RUN = f"{_HOST}:{os.getpid()}:{time.time_ns()}"
_MADE = []


def _say(msg):
    print(msg, file=sys.stderr, flush=True)


def _script():
    """돌고 있는 시험 파일 이름 (python3 tests/smoke_v2.py → smoke_v2.py)."""
    main = sys.modules.get("__main__")
    path = getattr(main, "__file__", None) or (sys.argv[0] if sys.argv else "")
    return os.path.basename(path) or "python"


def _root():
    return os.path.realpath(tempfile.gettempdir())


def make(prefix):
    """임시 폴더를 만들고 표시 파일을 쓴 뒤 이번 실행의 목록에 올려요. tempfile.mkdtemp(prefix=…) 대신 써요."""
    if not isinstance(prefix, str) or not prefix.startswith(PREFIX):
        raise ValueError(f"임시 폴더 접두어는 '{PREFIX}' 로 시작해야 해요: {prefix!r}")
    d = tempfile.mkdtemp(prefix=prefix)
    with open(os.path.join(d, MARK), "w", encoding="utf-8") as fh:
        json.dump({"script": _script(), "prefix": prefix, "run": _RUN, "pid": os.getpid(), "host": _HOST,
                   "made": time.strftime("%Y-%m-%dT%H:%M:%S%z")}, fh, ensure_ascii=False)
    _MADE.append(d)
    return d


def _in_root(path):
    """시스템 임시 폴더 바로 아래의 진짜 폴더(바로가기 아님)이고 이름이 'baepsae-' 로 시작하는지."""
    p = os.path.abspath(path)
    name = os.path.basename(p)
    root = _root()
    return (name.startswith(PREFIX) and not os.path.islink(p) and os.path.isdir(p)
            and os.path.realpath(os.path.dirname(p)) == root and os.path.realpath(p) == os.path.join(root, name))


def marker(path):
    """폴더의 표시 파일 내용. 없거나 · 바로가기거나 · 읽을 수 없거나 · 모양이 틀리거나 · 폴더 이름이 접두어와 맞지 않으면 None."""
    try:
        if os.path.islink(path) or not os.path.isdir(path):
            return None
        m = os.path.join(path, MARK)
        if os.path.islink(m) or not os.path.isfile(m):
            return None
        with open(m, encoding="utf-8") as fh:
            j = json.load(fh)
    except (OSError, ValueError):
        return None
    if not isinstance(j, dict) or not all(isinstance(j.get(k), str) and j[k] for k in ("script", "prefix", "run", "host")):
        return None
    if not isinstance(j.get("pid"), int) or isinstance(j["pid"], bool):
        return None
    if not j["prefix"].startswith(PREFIX) or not os.path.basename(os.path.abspath(path)).startswith(j["prefix"]):
        return None
    return j


def _finished(j):
    """표시 파일을 쓴 실행이 이미 끝났는지. 확실하지 않으면 끝나지 않은 것으로 봐요 (지우지 않게)."""
    pid = j["pid"]
    if os.name != "posix" or j["host"] != _HOST or pid <= 0 or pid == os.getpid():
        return False
    try:
        os.kill(pid, 0)                      # 신호 0: 보내지 않고 그 프로세스가 있는지만 봐요
    except ProcessLookupError:
        return True
    except OSError:
        return False
    return False


def _remove(path):
    try:
        shutil.rmtree(path)
        return True
    except OSError as e:
        _say(f"!! 임시 폴더를 지우지 못했어요: {path} ({e})")
        return False


def _older_failed(script):
    """같은 시험의 그 전 실행이 남긴 폴더 (표시 파일이 이 시험 것이고 · 이번 실행이 아니고 · 그 실행이 끝난 것)."""
    root = _root()
    try:
        names = sorted(os.listdir(root))
    except OSError as e:
        _say(f"!! 임시 폴더 목록을 읽지 못했어요: {root} ({e})")
        return []
    out = []
    for name in names:
        d = os.path.join(root, name)
        if not name.startswith(PREFIX) or not _in_root(d):
            continue
        j = marker(d)
        if j and j["script"] == script and j["run"] != _RUN and _finished(j):
            out.append(d)
    return out


def _finish(passed):
    script = _script()
    made = [d for d in dict.fromkeys(_MADE) if os.path.lexists(d)]    # 시험 코드가 이미 지운 폴더는 건너뛰어요
    del _MADE[:]
    mine = []
    for d in made:
        j = marker(d)
        if j and j["run"] == _RUN and _in_root(d):
            mine.append(d)
        else:
            _say(f"!! 임시 폴더 {d}: 이번 실행의 표시 파일이 없거나 임시 폴더 바로 아래가 아니라 그대로 둬요")
    if passed:
        if mine:
            gone = sum(_remove(d) for d in mine)
            _say(f"· 임시 폴더: 통과한 실행이라 이번 실행이 만든 폴더 {gone} / {len(mine)}개를 지웠어요 ({script})")
        return
    if not mine:
        return
    _say(f"· 임시 폴더: 실패한 실행이라 이번 실행의 폴더 {len(mine)}개를 디버깅용으로 남겨요 ({script} · 실행 {_RUN} · 표시 파일 {MARK}):")
    for d in mine[:SHOW]:
        _say("    " + d)
    if len(mine) > SHOW:
        _say(f"    … 외 {len(mine) - SHOW}개 (표시 파일에 실행 {_RUN})")
    old = _older_failed(script)
    if old:
        gone = sum(_remove(d) for d in old)
        _say(f"· 임시 폴더: 같은 시험({script})의 그 전 실패 실행 폴더 {gone} / {len(old)}개를 지웠어요")


def finish(passed):
    """시험 맨 끝에 불러요 (run 이 대신 불러요). 정리하다 난 오류는 크게 알리되 시험 결과(종료 코드)는 바꾸지 않아요."""
    try:
        _finish(bool(passed))
    except Exception as e:                   # 정리는 검사가 아니에요: 결과를 바꾸지 않고 stderr 에 크게 알려요
        _say(f"!! 임시 폴더 정리 중 오류 (시험 결과는 그대로예요): {e!r}")


def run(main):
    """main() 을 돌리고 그 반환값을 돌려줘요. 0 이면 통과, 그 밖의 값 · 예외 · 중단은 실패로 봐요."""
    code = None
    try:
        code = main()
        return code
    finally:
        finish(code == 0)
