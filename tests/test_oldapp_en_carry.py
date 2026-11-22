# -*- coding: utf-8 -*-
"""예전 뱁새 영어 화면의 마지막 확인 종가 목록 줄 (Jack, 2026-11-22, verbatim: "1. Yes, with "these show" when several stocks are listed:
* "AAPL, MSFT, NVDA, AMZN, GOOGL and 2 more: we couldn't confirm today's close, so these show the Nov 20 close."
* "US stocks: we couldn't confirm today's close, so these show the Nov 20 close."").

Node 로 실제 코드(src/detail.jsx ownCloseLines · src/fixnote.jsx · src/data.js)를 돌려서 봐요 (더한 시험만):
- 시장 전체 목록 (종목 고르기, compact): 한국어 줄과 같은 규칙 — 같은 날짜의 코드가 5개를 넘으면 앞 5개 (화면 순서) + "and {n} more" · 그날 미국
  종목의 절반 넘게 마지막 확인 종가면 (data.js US_CARRY_WIDE) 미국 쪽은 "US stocks: …" 한 줄 (국내 종목은 자기 줄 그대로)
- 줄이 종목 둘 이상을 말하면 "these show", 하나면 "this shows" · 콜론 뒤는 소문자 "we" — 내 보유 목록(배너 · 주문 메모 · CSV)도
- 내 보유 목록은 상한 위에서도 모든 코드 · 묶음은 예전 그대로 (같은 날짜의 국내 · 미국 마지막 확인 종가는 한 줄)
- 한 종목 카드의 문장 (영어 첫 화면 성적표, 앞에 코드 없음) · 한국어 줄 · 거래 정지 모양의 미국 pxd 문장은 그대로
브라우저 화면은 tests/smoke_app.py 장면 '확인종가' · '미국확인종가' 가 봐요.
"""
import json
import os
import shutil
import subprocess
import tempfile

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NODE = shutil.which("node")
pytestmark = pytest.mark.skipif(NODE is None, reason="node 가 없어요")
MODS = {"DT": "src/detail.jsx", "D": "src/data.js", "FX": "src/fixnote.jsx"}
D19, D20 = "2026-11-19", "2026-11-20"

JACK_QUOTE = ('"1. Yes, with "these show" when several stocks are listed: * "AAPL, MSFT, NVDA, AMZN, GOOGL and 2 more: we couldn\'t confirm '
              'today\'s close, so these show the Nov 20 close." * "US stocks: we couldn\'t confirm today\'s close, so these show the Nov 20 close.""')
EN_ONE = "{names}: we couldn't confirm today's close, so this shows the {date} close."
EN_MANY = "{names}: we couldn't confirm today's close, so these show the {date} close."
EN_MORE = "{names} and {n} more: we couldn't confirm today's close, so these show the {date} close."
EN_US_ALL = "US stocks: we couldn't confirm today's close, so these show the {date} close."
EN_CARD = "We couldn't confirm today's close, so this shows the {date} close."          # Jack, 2026-11-20 (c) — 그대로
KO_LIST = "{names}: 오늘 종가를 확인하지 못해서 {date} 종가를 보여 드려요."
KO_MORE = "{names} 외 {n}종목: 오늘 종가를 확인하지 못해서 {date} 종가를 보여 드려요."
KO_US_ALL = "미국 종목은 오늘 종가를 확인하지 못해서 {date} 종가를 보여 드려요."
_B = {}


def fill(tpl, **v):
    for k, x in v.items():
        tpl = tpl.replace("{" + k + "}", str(x))
    return tpl


def bundle_dir():
    if "p" not in _B:
        tmp = tempfile.mkdtemp(prefix="baepsae-encarry-")
        with open(os.path.join(tmp, "entry.js"), "w", encoding="utf-8") as f:
            for k, v in MODS.items():
                f.write(f"export * as {k} from {json.dumps(os.path.join(ROOT, v))};\n")
        exe = os.path.join(ROOT, "node_modules", ".bin", "esbuild")
        r = subprocess.run([exe, os.path.join(tmp, "entry.js"), "--bundle", "--format=esm", "--platform=node", "--jsx=automatic",
                            "--loader:.js=jsx", "--charset=utf8", "--external:react", "--external:react-dom", f"--outfile={tmp}/b.mjs",
                            "--log-level=error"], cwd=ROOT, capture_output=True, text=True)
        assert r.returncode == 0, r.stderr
        os.symlink(os.path.join(ROOT, "node_modules"), os.path.join(tmp, "node_modules"))
        _B["p"] = tmp
    return _B["p"]


@pytest.fixture(scope="module", autouse=True)
def _cleanup():
    yield
    if "p" in _B:
        shutil.rmtree(_B["p"], ignore_errors=True)


def run(body, **data):
    """한 번마다 새 node (data.js 의 미국 상한 표시 US_WIDE 는 그 실행 안에서만)."""
    tmp = bundle_dir()
    decl = "".join(f"const {k} = {json.dumps(v, ensure_ascii=False)};\n" for k, v in data.items())
    code = ("import * as B from './b.mjs'; import { renderToStaticMarkup } from 'react-dom/server'; import { createElement as h } from 'react';\n"
            "const { DT, D, FX } = B;\n"
            "const WARN = []; console.warn = (m) => WARN.push(String(m)); console.info = () => {};\n"
            + decl + "let out;\n" + body + "\nconsole.log(JSON.stringify(out));")
    fd, path = tempfile.mkstemp(suffix=".mjs", dir=tmp)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(code)
    r = subprocess.run([NODE, path], cwd=tmp, capture_output=True, text=True, timeout=180)
    assert r.returncode == 0, r.stderr[-3000:]
    return json.loads(r.stdout.strip().splitlines()[-1])


def us(t, **kw):
    s = {"t": t, "nk": t + " Inc.", "ne": t + " Inc.", "cls": "us", "ccy": "USD", "price": 100.0, "d1": 0.5}
    s.update(kw)
    return {k: v for k, v in s.items() if v is not None}


def kr(t, nk, **kw):
    s = {"t": t, "nk": nk, "ne": nk, "cls": "kr", "price": 5000.0, "d1": 0.5}
    s.update(kw)
    return {k: v for k, v in s.items() if v is not None}


def usc(t, day=D20):
    """야후 종가가 없어 마지막 확인 종가로 실은 미국 종목 (data.json pxc · pxd · d1 없음)."""
    return us(t, d1=None, pxd=day, pxc=True)


def krc(t, nk, day=D20):
    """두 출처로 확인하지 못해 마지막 확인 종가로 실은 국내 종목 (pxd · d1 없음)."""
    return kr(t, nk, d1=None, pxd=day)


LINES = "const lines = (lang, rows, compact) => DT.ownCloseLines(lang, rows, compact);\n"


# ── 글자: Jack 이 승인한 영어 그대로 · 승인 기록 ──
def test_the_english_list_lines_are_jacks_words():
    got = run("out = { one: FX.FIX_KR_OWN_CLOSE_LIST_EN_ONE, many: FX.FIX_KR_OWN_CLOSE_LIST_EN, more: FX.FIX_KR_OWN_CLOSE_LIST_MORE_EN,"
              " all: FX.FIX_US_OWN_CLOSE_ALL_EN, card: FX.FIX_KR_OWN_CLOSE_EN, max: FX.FIX_OWN_LIST_MAX };")
    assert got == {"one": EN_ONE, "many": EN_MANY, "more": EN_MORE, "all": EN_US_ALL, "card": EN_CARD, "max": 5}, got
    appr = open(os.path.join(ROOT, "docs", "tasks", "v18.3-approved-in-chat.md"), encoding="utf-8").read()
    assert JACK_QUOTE in appr, "Jack 의 승인 (2026-11-22) 이 그대로 기록되지 않았어요"
    for x in (EN_ONE, EN_MANY, EN_MORE, EN_US_ALL):
        assert x in appr, x


def test_jacks_two_example_lines_come_out_word_for_word():
    """Jack 이 승인한 두 줄 그대로: 일곱 미국 종목 (시가총액 순 화면) → 앞 5개 + "and 2 more" · 절반 넘게 → "US stocks: …"."""
    seven = [usc(t) for t in ("AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "TSLA")]
    got = run(LINES + """
out = { cut: lines('en', SEVEN, true) };
out.wideOn = D.setOwnCarryWide({ stocks: [...SEVEN, ...SEVEN.slice(0, 6).map((s) => ({ ...s, t: s.t + 'X', pxc: undefined, pxd: undefined }))] });
out.wide = lines('en', SEVEN, true);""", SEVEN=seven)
    assert got["cut"] == ["AAPL, MSFT, NVDA, AMZN, GOOGL and 2 more: we couldn't confirm today's close, so these show the Nov 20 close."], got
    assert got["wideOn"] is True
    assert got["wide"] == ["US stocks: we couldn't confirm today's close, so these show the Nov 20 close."], got


# ── 1 · 2–5 · 6+ 종목 ──
@pytest.mark.parametrize("compact", [False, True])
def test_one_code_says_this_shows(compact):
    got = run(LINES + "out = [lines('en', [K], C), lines('en', [U], C), lines('en', [K, P], C), lines('en', [P, U, P], C)];",
              K=krc("094800", "맵스리얼티"), U=usc("AAPL"), P=kr("005930", "삼성전자"), C=compact)
    one = lambda t: [fill(EN_ONE, names=t, date="Nov 20")]
    assert got == [one("094800"), one("AAPL"), one("094800"), one("AAPL")], got     # pxd 없는 종목은 세지 않아요


@pytest.mark.parametrize("compact", [False, True])
def test_two_to_five_codes_say_these_show(compact):
    five = [krc("094800", "맵스리얼티"), usc("AAPL"), krc("011810", "STX"), usc("MSFT"), krc("100220", "비상교육")]
    got = run(LINES + "out = [2, 3, 4, 5].map((n) => lines('en', FIVE.slice(0, n), C));", FIVE=five, C=compact)
    codes = ["094800", "AAPL", "011810", "MSFT", "100220"]
    assert got == [[fill(EN_MANY, names=", ".join(codes[:n]), date="Nov 20")] for n in (2, 3, 4, 5)], got


def test_six_or_more_codes_on_a_market_wide_list_stop_at_five_in_screen_order():
    rows = [krc(f"{i}00000", f"가{i}") if i % 2 else usc(f"T{i}") for i in range(9)]
    got = run(LINES + "out = { six: lines('en', R.slice(0, 6), true), nine: lines('en', R, true), ko: lines('ko', R, true) };", R=rows)
    codes = [r["t"] for r in rows]
    assert got["six"] == [fill(EN_MORE, names=", ".join(codes[:5]), n=1, date="Nov 20")], got
    assert got["nine"] == [fill(EN_MORE, names=", ".join(codes[:5]), n=4, date="Nov 20")], got
    names = [r["nk"] if r["cls"] == "kr" else r["t"] for r in rows]                 # 한국어 줄은 그대로 (이름 · 외 n종목)
    assert got["ko"] == [fill(KO_MORE, names=", ".join(names[:5]), n=4, date="11월 20일")], got


def test_six_or_more_on_the_users_own_lists_name_every_code():
    """포트폴리오 배너 · 주문 메모 · CSV (compact 없음): 모든 코드 + "these show"."""
    rows = [usc(f"T{i}") for i in range(7)] + [krc("094800", "맵스리얼티")]
    got = run(LINES + "out = { en: lines('en', R), ko: lines('ko', R) };", R=rows)
    codes = [r["t"] for r in rows]
    assert got["en"] == [fill(EN_MANY, names=", ".join(codes), date="Nov 20")], got
    assert got["ko"] == [fill(KO_LIST, names=", ".join(codes[:7] + ["맵스리얼티"]), date="11월 20일")], got


# ── 미국 상한 (US_CARRY_WIDE: 미국 종목의 절반 넘게 마지막 확인 종가) ──
def test_us_cap_turns_the_us_side_into_one_line_and_korean_carries_keep_theirs():
    us_carried = [usc(f"T{i}") for i in range(4)]
    us_plain = [us(f"N{i}") for i in range(3)]
    k1, k2 = krc("094800", "맵스리얼티"), krc("011810", "STX")
    halted = us("HALT", d1=None, pxd=D20)                                           # pxc 없는 미국 pxd (거래 정지 모양): 예전 문장
    got = run(LINES + """
out = { half: D.setOwnCarryWide({ stocks: [...UC.slice(0, 3), ...UP] }) };
out.halfLines = lines('en', [K1, ...UC.slice(0, 3)], true);
out.on = D.setOwnCarryWide({ stocks: [...UC, ...UP] });
out.wide = lines('en', [HALT, K1, ...UC, K2], true);
out.wideOneKr = lines('en', [K1, ...UC], true);
out.wideNoKr = lines('en', UC.slice(0, 1), true);
out.own = lines('en', [HALT, K1, ...UC, K2]);
out.ko = lines('ko', [HALT, K1, ...UC, K2], true);""", UC=us_carried, UP=us_plain, K1=k1, K2=k2, HALT=halted)
    assert got["half"] is False and got["on"] is True                                  # 정확히 절반은 아니에요 · 절반 넘게
    assert got["halfLines"] == [fill(EN_MANY, names="094800, T0, T1, T2", date="Nov 20")], got
    us_all = fill(EN_US_ALL, date="Nov 20")
    assert got["wide"] == ["HALT: priced at the Nov 20 close.", fill(EN_MANY, names="094800, 011810", date="Nov 20"), us_all], got
    assert got["wideOneKr"] == [fill(EN_ONE, names="094800", date="Nov 20"), us_all], got          # 국내 하나: "this shows"
    assert got["wideNoKr"] == [us_all], got
    # 내 보유 목록은 상한 위에서도 예전 그대로 묶고 모든 코드
    assert got["own"] == ["HALT: priced at the Nov 20 close.", fill(EN_MANY, names="094800, T0, T1, T2, T3, 011810", date="Nov 20")], got
    assert got["ko"] == ["HALT 가격은 11월 20일 종가예요.", fill(KO_LIST, names="맵스리얼티, STX", date="11월 20일"), fill(KO_US_ALL, date="11월 20일")], got


# ── 국내 + 미국 · 날짜마다 ──
def test_korean_and_us_carries_of_one_date_share_one_line_and_each_date_counts_its_own_codes():
    rows = [usc("AAPL"), krc("094800", "맵스리얼티"), usc("MSFT", day=D19), us("HALT", d1=None, pxd=D19), kr("005930", "삼성전자")]
    got = run(LINES + "out = { m: lines('en', R, true), own: lines('en', R) };", R=rows)
    want = [fill(EN_MANY, names="AAPL, 094800", date="Nov 20"), "HALT: priced at the Nov 19 close.", fill(EN_ONE, names="MSFT", date="Nov 19")]
    assert got["m"] == want and got["own"] == want, got                               # 새 날짜 먼저 · 같은 날짜는 예전 문장 다음


def test_built_in_stocks_without_cls_read_as_korean():
    got = run(LINES + "out = lines('en', [{ t: '094800', nk: '맵스리얼티', price: 5000, pxd: '2026-11-20' }, { t: '011810', nk: 'STX', price: 1, pxd: '2026-11-20' }]);")
    assert got == [fill(EN_MANY, names="094800, 011810", date="Nov 20")], got


def test_list_line_helper_counts_a_joined_string_and_cuts_only_an_array():
    got = run("""out = [FX.krOwnCloseListLine('AAPL', '2026-11-18', 'en'), FX.krOwnCloseListLine('094800, 011810', '2026-11-16', 'en'),
  FX.krOwnCloseListLine('A, B, C, D, E, F', '2026-11-18', 'en'), FX.krOwnCloseListLine(['A', 'B', 'C', 'D', 'E', 'F'], '2026-11-18', 'en'),
  FX.krOwnCloseListLine(['A', 'B', 'C', 'D', 'E'], '2026-11-18', 'en'), FX.krOwnCloseListLine(['A$&B'], '2026-11-18', 'en'),
  FX.krOwnCloseListLine(['A'], 'bad', 'en'), FX.usOwnCloseAllLine('2026-11-18', 'en'), FX.usOwnCloseAllLine('2026-11-18'),
  FX.usOwnCloseAllLine('bad', 'en')];""")
    assert got == [fill(EN_ONE, names="AAPL", date="Nov 18"), fill(EN_MANY, names="094800, 011810", date="Nov 16"),
                   fill(EN_MANY, names="A, B, C, D, E, F", date="Nov 18"), fill(EN_MORE, names="A, B, C, D, E", n=1, date="Nov 18"),
                   fill(EN_MANY, names="A, B, C, D, E", date="Nov 18"), fill(EN_ONE, names="A$&B", date="Nov 18"),
                   None, fill(EN_US_ALL, date="Nov 18"), fill(KO_US_ALL, date="11월 18일"), None], got


# ── 그대로인 것: 한 종목 카드 · 한국어 줄 ──
def test_single_stock_card_sentence_is_unchanged():
    got = run("""out = { t: [FX.krOwnCloseText(A, null, 'en'), FX.krOwnCloseText(U, '2026-11-20', 'en'), FX.krOwnCloseText(A, null)],
  html: renderToStaticMarkup(h(FX.KrOwnCloseLine, { c: A, lang: 'en' })) };""", A=krc("094800", "맵스리얼티"), U=usc("AAPL", day=D19))
    assert got["t"] == [fill(EN_CARD, date="Nov 20"), fill(EN_CARD, date="Nov 19"), "오늘 종가를 확인하지 못해서 11월 20일 종가를 보여 드려요."], got
    assert ">" + fill(EN_CARD, date="Nov 20").replace("'", "&#x27;") + "<" in got["html"], got["html"]
    shell = open(os.path.join(ROOT, "src", "shell.jsx"), encoding="utf-8").read()
    assert "<KrOwnCloseLine c={c} marketDate={asOf && asOf.date} lang={lang}" in shell       # 영어 첫 화면 성적표가 이 문장을 써요


def test_korean_list_lines_are_unchanged():
    seven = [usc(f"T{i}") for i in range(7)]
    got = run(LINES + "out = { cut: lines('ko', S, true), own: lines('ko', S), two: lines('ko', [K, S[0]], true) };", S=seven,
              K=krc("094800", "맵스리얼티"))
    assert got["cut"] == [fill(KO_MORE, names="T0, T1, T2, T3, T4", n=2, date="11월 20일")], got
    assert got["own"] == [fill(KO_LIST, names="T0, T1, T2, T3, T4, T5, T6", date="11월 20일")], got
    assert got["two"] == [fill(KO_LIST, names="맵스리얼티, T0", date="11월 20일")], got
