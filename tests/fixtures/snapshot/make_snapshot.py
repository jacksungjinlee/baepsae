#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""예전 뱁새 스모크 테스트(tests/smoke_app.py)가 쓰는 고정 데이터를 만들어요 (Jack, 2026-11-11).

  python3 tests/fixtures/snapshot/make_snapshot.py [발행 파일이 있는 폴더 = 저장소 맨 위] [--source "어느 발행인지"]

하루치 실제 발행 파일 넷(data · corp · disc · macro)을 줄인 사본이에요. 목록만 줄이고 값은 바꾸지 않아요 — 사람의 거래 보고 줄만 빼고요:
- data.json 의 stocks · corp.json 의 companies: 아래 규칙으로 고른 종목만 (순서는 발행 파일 그대로)
- disc.json 의 insider (임원 · 주요주주 거래 보고): tests/smoke_app.py 가 이름을 부르는 종목의 줄만, 종목마다 처음 INSIDER_PER 줄.
  줄의 모양(칸)과 회사 · 날짜만 발행 그대로이고, 사람에 관한 값은 모두 지어낸 거예요 (Jack, 2026-11-12): 이름(nm) · 직위(pos) ·
  접수번호(rc) · 수량(q) · 비율(r) · 금액(amt). 공개된 공시라도 시험 데이터가 실제 사람의 실제 거래를 가리키지 않게요
  (이름만 바꾸면 회사 · 날짜 · 직위 · 수량으로 그 공시를 찾을 수 있어요). 시험은 이 줄들의 내용을 보지 않아요 — 목록이 그려지는지만 봐요.
- disc.json 의 nps (국민연금 보유 변동): 고른 종목의 줄 가운데 처음 NPS_ROWS 줄 (사람 이름이 없는 줄이에요)
- 그 밖의 필드(날짜 · 환율 · popular · count · 업종 통계 · macro.json 전체)는 발행된 그대로
  (popular · count · 업종 통계는 줄이기 전 전체 시장의 값이에요)

고르는 규칙 (KEEP_KR · KEEP_US 를 바꾸면 크기가 바뀌어요):
1. 앱 소스(src/)와 tests/smoke_app.py 에 따옴표로 적힌 종목 (앱에 내장된 종목 · 시험이 이름을 부르는 종목)
2. 주식이 아닌 것 전부 (채권 · 금속) · ETF · 펀드
3. 해외 기업(종목코드 9…) 전부 · 재무제표가 원화가 아닌 회사(stmtCur) 전부
4. 시가총액 상위 한국 KEEP_KR · 미국 KEEP_US

파일 이름은 snap_*.json — 사이트가 읽는 data.json · corp.json · disc.json · macro.json 과 헷갈리지 않게요. 이 폴더는 배포되지
않고(tests/ 는 사이트에 올라가지 않아요), 앱은 이 이름의 파일을 읽지 않아요 (tests/test_snapshot.py 가 확인해요).
이 사본은 발행 관문(validate_data.py)을 통과시키려는 것이 아니에요 — 줄인 목록이라 개수 기준에 맞지 않고, 맞출 이유도 없어요.
"""
import argparse
import datetime as dt
import glob
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
KEEP_KR, KEEP_US = 120, 50
INSIDER_PER, NPS_ROWS = 2, 5
SYL = "가나다라마바사아자차카타파하"


def made_up_name(i):
    """지어낸 이름 (i = 0, 1, 2 …): 가나다 · 나다라 … 처럼 글자표에서 뽑은 세 글자. 196개까지 서로 달라요."""
    a, b = i % len(SYL), i // len(SYL)
    return SYL[a] + SYL[(a + 1 + b) % len(SYL)] + SYL[(a + 2 + 2 * b) % len(SYL)]


def trim_insider(rows, named):
    """tests/smoke_app.py 가 이름을 부르는 종목(named)의 줄만, 종목마다 처음 INSIDER_PER 줄. 회사(t · nk · s · cap)와 날짜(d)만 그대로 두고
    사람에 관한 값은 모두 지어내요: 이름 · 직위 · 접수번호 · 수량 · 비율 · 금액 (사고 판 줄이 번갈아 나오게)."""
    out, per = [], {}
    for x in rows:
        t = x.get("t")
        if t not in named or per.get(t, 0) >= INSIDER_PER:
            continue
        per[t] = per.get(t, 0) + 1
        i = len(out)
        q = (i + 1) * 100 * (1 if i % 2 == 0 else -1)
        out.append({**x, "nm": made_up_name(i), "pos": "임원", "rc": f"TEST-{i + 1:04d}", "q": q, "r": 0.0, "amt": round(0.1 * (i + 1), 1)})
    return out


NAMES = {"data.json": "snap_data.json", "corp.json": "snap_corp.json", "disc.json": "snap_disc.json", "macro.json": "snap_macro.json"}
SMOKE = os.path.join(ROOT, "tests", "smoke_app.py")


def norm(t):
    """점 · 하이픈만 무시해요 (BRK.B = BRK-B). 대소문자는 그대로: 소스의 "ko" 같은 글자가 티커 KO 로 읽히지 않게요."""
    return re.sub(r"[.\-]", "", str(t or ""))


def quoted_tickers(tickers, paths=None):
    """src/ 와 tests/smoke_app.py 에 (paths 를 주면 그 파일들에) "005930" · 'AAPL' 처럼 따옴표로 적힌 종목."""
    text = ""
    for p in paths or sorted(glob.glob(os.path.join(ROOT, "src", "**", "*.js*"), recursive=True)) + [SMOKE]:
        with open(p, encoding="utf-8") as f:
            text += f.read() + "\n"
    quoted = set(re.findall(r"""["']([A-Za-z0-9.\-]{1,9})["']""", text))
    # 미국 티커는 표기가 갈려요 (소스 BRK.B · 데이터 BRK-B): 앱처럼 점 · 하이픈을 무시하고 맞춰요
    quoted_norm = {norm(q) for q in quoted}
    return {t for t in tickers if t in quoted or norm(t) in quoted_norm}


def pick(data, corp):
    stocks = data["stocks"]
    by_t = {s["t"]: s for s in stocks}
    co = {c["t"]: c for c in corp["companies"]}
    keep = quoted_tickers(set(by_t))
    keep |= {s["t"] for s in stocks if s.get("cls") not in ("kr", "us") or s.get("etf") or s.get("fund")}
    keep |= {t for t in by_t if by_t[t].get("cls") == "kr" and len(t) == 6 and t.startswith("9")}
    keep |= {t for t, c in co.items() if c.get("stmtCur")}
    cap = lambda s: s.get("cap") if isinstance(s.get("cap"), (int, float)) else -1.0
    for cls, n in (("kr", KEEP_KR), ("us", KEEP_US)):
        top = sorted((s for s in stocks if s.get("cls") == cls and not s.get("etf") and not s.get("fund")), key=lambda s: (-cap(s), s["t"]))
        keep |= {s["t"] for s in top[:n]}
    return keep, quoted_tickers(set(by_t), [SMOKE])


def write(name, obj):
    path = os.path.join(HERE, NAMES[name])
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, allow_nan=False, separators=(",", ":"))
        f.write("\n")
    return os.path.getsize(path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src", nargs="?", default=ROOT)
    ap.add_argument("--source", default="", help="어느 발행인지 (예: main 3ff1ce2 · 데이터 갱신 2026-11-11)")
    args = ap.parse_args()
    files = {}
    for name in NAMES:
        with open(os.path.join(args.src, name), encoding="utf-8") as f:
            files[name] = json.load(f)
    data, corp, disc = files["data.json"], files["corp.json"], files["disc.json"]
    keep, named = pick(data, corp)
    full = {"stocks": len(data["stocks"]), "companies": len(corp["companies"]), "insider": len(disc["insider"]), "nps": len(disc["nps"])}
    data["stocks"] = [s for s in data["stocks"] if s["t"] in keep]
    corp["companies"] = [c for c in corp["companies"] if c["t"] in keep]
    real = disc["insider"]
    disc["insider"] = trim_insider(disc["insider"], named)
    disc["nps"] = [x for x in disc["nps"] if x.get("t") in keep][:NPS_ROWS]
    assert not ({x["nm"] for x in disc["insider"]} & {x.get("nm") for x in real}) and not ({x["rc"] for x in disc["insider"]} & {x.get("rc") for x in real}), \
        "지어낸 이름 · 접수번호가 실제 것과 겹쳐요"
    # CI 의 예전 뱁새 검사는 '예시 가격 · 금 환산' 안내가 없는 데이터를 요구해요 (tests/smoke_app.py banner_due): 내장 종목이 모두 있고
    # 가격 · 베타 · 변동성이 차 있어야 하고, 금 환산 표시가 없어야 해요. 그렇지 않은 날의 발행으로는 고정 데이터를 만들지 않아요.
    base = re.findall(r'\bt:\s*"([^"]+)"', (lambda t: t[t.index("const BASE_STOCKS = ["):t.index("\n];", t.index("const BASE_STOCKS = ["))])(
        open(os.path.join(ROOT, "src", "detail.jsx"), encoding="utf-8").read()))
    have = {norm(x["t"]): x for x in data["stocks"]}
    bad = [t for t in base if norm(t) not in have or any(have[norm(t)].get(k) is None for k in ("price", "beta", "vol")) or have[norm(t)].get("est")]
    assert len(base) >= 60 and not bad, f"이 발행으로는 고정 데이터를 만들 수 없어요: 내장 종목이 없거나 값이 비었거나 금 환산이에요 {bad} (다른 날의 발행을 쓰세요)"
    sizes = {NAMES[n]: write(n, files[n]) for n in NAMES}
    pub = dt.datetime.fromisoformat(data["publishedAt"])
    meta = {
        "what": "tests/smoke_app.py 의 고정 데이터: 하루치 실제 발행 파일을 줄인 사본 (목록만 줄임 · 값은 그대로, 단 임원 거래 줄은 회사와 날짜만 그대로이고 나머지는 지어낸 것). make_snapshot.py 로 만들어요.",
        "madeUp": "snap_disc.json insider 의 nm · pos · rc · q · r · amt (이름 · 직위 · 접수번호 · 수량 · 비율 · 금액)",
        "source": args.source,
        "publishedAt": data["publishedAt"], "pxDate": data["pxDate"],
        # 시험의 시계가 시작하는 순간: 발행한 날 07:00 (한국 시간). 날짜가 흘러도 시험 결과가 바뀌지 않게요. 07:00 이라 한국 날짜와
        # UTC 날짜가 달라요 (UTC 로는 전날 22시): '오늘'을 UTC 날짜로 잘못 읽는 코드가 드러나요. 한 번 도는 동안 어느 쪽 날짜도 넘지 않아요.
        "now": pub.replace(hour=7, minute=0, second=0, microsecond=0).isoformat(timespec="seconds"),
        "rule": {"keepKr": KEEP_KR, "keepUs": KEEP_US, "insiderPerStock": INSIDER_PER, "npsRows": NPS_ROWS},
        "kept": {"stocks": len(data["stocks"]), "companies": len(corp["companies"]), "insider": len(disc["insider"]), "nps": len(disc["nps"])},
        "published": full,
        "bytes": sizes,
    }
    with open(os.path.join(HERE, "snap_meta.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=1)
        f.write("\n")
    print(json.dumps(meta, ensure_ascii=False, indent=1))
    print(f"· 합계 {sum(sizes.values()):,} 바이트")


if __name__ == "__main__":
    main()
