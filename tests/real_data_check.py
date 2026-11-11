# -*- coding: utf-8 -*-
"""발행 전 확인: 오늘 받은 진짜 데이터로 보는 검사 (브라우저 없이). 매일 실행(update-data.yml)의 '발행 전 화면 검사' 단계가 돌려요.

  python tests/real_data_check.py --data DIR      # DIR 의 data.json · corp.json · disc.json · macro.json

Jack 2026-11-11: 스모크 테스트와 pytest 가 고정된 시험 데이터로 옮겨 가도, 진짜 데이터로만 볼 수 있는 검사는 발행을 막는 자리에서
계속 돌아야 해요. 하나라도 실패하면 exit 1 → 그 실행은 발행하지 않아요 (어제 데이터가 그대로 남아요).

1. 2.0 이 쓰는 항목이 다 있어요 (tests/test_launch.py real_data_missing — 메인 주소가 2.0 을 여는 조건과 같은 판단).
2. 예전 뱁새(src/data.js krGrowthBasis)와 2.0(src/v2/engine.js growthBasis)의 매출 성장 기준이 오늘의 모든 한국 종목에서 같아요
   (tests/test_app_data.py 의 '오늘 데이터' 비교와 같은 계산 · 같은 기준). node 가 없으면 건너뛰지 않고 실패예요.
"""
import argparse
import json
import os
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tests"))
from test_launch import real_data_missing  # noqa: E402

NEEDS = ("data.json", "corp.json", "disc.json", "macro.json")     # 발행하는 네 파일 모두 (NaN · Infinity 가 있으면 브라우저가 파일을 통째로 못 읽어요)
GROWTH_MIN = 1000          # 비교한 한국 종목이 이보다 적으면 비교 자체가 비어 있는 거예요 (test_app_data.py 와 같은 숫자)

# test_app_data.py test_korean_growth_basis_matches_2_0_on_todays_data 의 compare 와 같은 코드 (경로만 인자로 받아요)
GROWTH_JS = (
    "import * as D from './src/data.js'; import * as E from './src/v2/engine.js'; import fs from 'fs';"
    "const d = JSON.parse(fs.readFileSync(process.argv[1], 'utf8')); const c = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));"
    "const co = new Map(c.companies.map((x) => [x.t, x])); const out = { n: 0, diff: [], y2: 0, y1: 0, none: 0 };"
    "for (const s of d.stocks) { if (s.cls !== 'kr' || s.g3 == null) continue; const k = co.get(s.t); out.n++;"
    " const a = D.krGrowthBasis(s.g3, k ? k.rev : null), b = E.growthBasis(s, k || null); if (a !== b) out.diff.push(s.t);"
    " out[a || 'none']++; }"
    "console.log(JSON.stringify(out));")


def _no_constant(name):
    raise ValueError(f"JSON 에 {name} 이 있어요")


def load(dir_):
    """(파일 이름 → 내용). 없거나 읽히지 않거나 NaN · Infinity 가 있으면 ValueError."""
    out = {}
    for f in NEEDS:
        p = os.path.join(dir_, f)
        if not os.path.isfile(p):
            raise ValueError(f"{f} 가 없어요 ({p})")
        with open(p, encoding="utf-8") as fh:
            try:
                out[f] = json.loads(fh.read(), parse_constant=_no_constant)
            except ValueError as e:
                raise ValueError(f"{f} 를 읽지 못했어요: {str(e)[:120]}")
    return out


def check_fields(files):
    """(통과, 설명): 2.0 이 쓰는 v17.5 형식 · v17.5.1 항목."""
    missing = real_data_missing(files["data.json"], files["corp.json"], files["macro.json"])
    n = len(files["data.json"].get("stocks") or [])
    if missing:
        return False, "빠진 항목: " + ", ".join(missing)
    return True, f"빠진 항목 없음 (종목 {n:,}개)"


def growth_compare(dir_, node=None, run=subprocess.run):
    """node 로 두 앱의 매출 성장 기준을 오늘의 모든 한국 종목에서 비교해요 → {n, diff, y2, y1, none}."""
    node = node or shutil.which("node")
    if not node:
        raise RuntimeError("node 가 없어요 (건너뛰지 않아요)")
    r = run([node, "--input-type=module", "-e", GROWTH_JS, os.path.join(dir_, "data.json"), os.path.join(dir_, "corp.json")],
            cwd=ROOT, capture_output=True, text=True, timeout=120)
    if r.returncode != 0:
        err = (r.stderr or "").strip().splitlines()
        raise RuntimeError("node 실행 실패" + (": " + err[-1][:200] if err else ""))
    return json.loads(r.stdout)


def check_growth(got):
    """(통과, 설명): 한국 종목 GROWTH_MIN 개 넘게 비교 · 다른 종목 0개 · 2년 기준이 1년 기준보다 많음 (test_app_data.py 와 같은 기준)."""
    n, diff, y2, y1 = got.get("n"), got.get("diff"), got.get("y2"), got.get("y1")
    if not (isinstance(n, int) and isinstance(diff, list) and isinstance(y2, int) and isinstance(y1, int)):
        return False, f"비교 결과를 읽지 못했어요: {str(got)[:120]}"
    text = f"한국 종목 {n:,}개 비교 · 다른 종목 {len(diff):,}개 · 2년 기준 {y2:,} · 1년 기준 {y1:,} · 기준 없음 {got.get('none', 0):,}"
    if diff:
        text += " · 다른 종목: " + ", ".join(str(t) for t in diff[:10]) + (" …" if len(diff) > 10 else "")
    return (n > GROWTH_MIN and not diff and y2 > y1 >= 0), text


def run_all(dir_, node=None):
    """[(이름, 통과, 설명)]. 어떤 검사도 건너뛰지 않아요: 못 돌리면 그 검사는 실패예요."""
    rows = []
    try:
        files = load(dir_)
    except ValueError as e:
        return [("데이터 파일 읽기 (data · corp · disc · macro)", False, str(e))]
    rows.append(("데이터 파일 읽기 (data · corp · disc · macro)", True, "네 파일 모두 읽힘 · NaN 없음"))
    try:
        rows.append(("2.0 이 쓰는 항목", *check_fields(files)))
    except Exception as e:                                   # 모양이 달라 검사 자체가 죽어도 '실패'로 남겨요
        rows.append(("2.0 이 쓰는 항목", False, f"검사하지 못했어요: {str(e)[:160]}"))
    try:
        rows.append(("매출 성장 기준: 예전 뱁새 = 2.0", *check_growth(growth_compare(dir_, node))))
    except Exception as e:
        rows.append(("매출 성장 기준: 예전 뱁새 = 2.0", False, f"검사하지 못했어요: {str(e)[:160]}"))
    return rows


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True, help="data.json · corp.json · disc.json · macro.json 이 있는 폴더")
    args = ap.parse_args(argv)
    dir_ = os.path.abspath(args.data)
    rows = run_all(dir_)
    print(f"발행 전 확인 (진짜 데이터 · 브라우저 없이) · 데이터: {dir_}")
    for name, ok, msg in rows:
        print(f"  {'PASS' if ok else 'FAIL'}  {name}: {msg}")
    bad = [r for r in rows if not r[1]]
    print(f"\n{len(rows) - len(bad)} / {len(rows)} 통과")
    if bad and os.environ.get("GITHUB_ACTIONS") == "true":
        for name, _, msg in bad:
            print(f"::error title=발행 전 확인 실패::{name}: {msg}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
