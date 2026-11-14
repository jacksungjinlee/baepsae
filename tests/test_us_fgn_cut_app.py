# -*- coding: utf-8 -*-
"""2.0: 미국 상장 외국 회사의 숫자가 회사 전체 재무제표와 맞지 않아 비운 칸 (Jack, 2026-11-14) — src/v2/fcur.js fgnCutOf · fgnBlank ·
fgnRowsBlank · src/v2/fixnote.jsx FgnCutNote · src/v2/company.jsx tileViews (규칙 fgn) · src/copy/v2.js co.fgnCut. (Node 로 직접 돌려봐요)

- data.json fgnCut = {per | pbr | dy: "mismatch" | "currency"} (fetch_data.py us_foreign_check). 앱은 그 칸 중 실제로 빈 칸만 봐요 (숫자 옆에
  줄이 서지 않게) · 통화 회사(fcur)는 자기 줄이 있어 보지 않아요.
- 요약: PBR 이 비면 가치 칸, 배당수익률이 비면 배당 칸이 '–' 와 'PBR –' · '배당수익률 –' (규칙 fgn, 그림 · 날짜 없음) — 실적 · 출렁임 다음.
  PER 만 빈 회사는 칸이 그대로 (요약 칸은 PBR · 배당만 보여요).
- 줄: "자료의 숫자가 회사 전체 재무제표와 맞지 않아서 비워 두었어요." 그대로 (승인 표).
"""
import os

from test_us_fcur_app import ROOT, run, us, pytestmark  # noqa: F401  (같은 묶음 · node 가 없으면 건너뛰어요)

LINE = "자료의 숫자가 회사 전체 재무제표와 맞지 않아서 비워 두었어요."


def test_fgn_cut_of_reads_only_blank_fields_of_us_non_currency_stocks():
    got = run("""
      const bp = { t: 'BP', cls: 'us', dy: 4.55, fgnCut: { per: 'mismatch', pbr: 'mismatch' } };
      out = {
        bp: FC.fgnCutOf(bp), bpBlank: [FC.fgnBlank(bp, 'per'), FC.fgnBlank(bp, 'pbr'), FC.fgnBlank(bp, 'dy')],
        left: FC.fgnCutOf({ ...bp, pbr: 7.62 }),                                 // 숫자가 남은 칸은 빼요
        cur: FC.fgnCutOf({ ...bp, fgnCut: { dy: 'currency' }, dy: null }),
        fcur: FC.fgnCutOf({ ...bp, fcur: 'GBP' }), kr: FC.fgnCutOf({ ...bp, cls: 'kr' }),
        odd: [FC.fgnCutOf({ ...bp, fgnCut: ['per'] }), FC.fgnCutOf({ ...bp, fgnCut: { per: 1, roe: 'mismatch' } }), FC.fgnCutOf({ t: 'X', cls: 'us' }),
              FC.fgnCutOf(null)],
        rows: [FC.fgnRowsBlank(bp, [{ id: 'value', blank: true }]), FC.fgnRowsBlank(bp, [{ id: 'div', blank: true }]),
               FC.fgnRowsBlank({ ...bp, fgnCut: { dy: 'mismatch' }, dy: null }, [{ id: 'div', blank: true }]),
               FC.fgnRowsBlank(bp, [{ id: 'value', blank: false }])],
      };""")
    assert got["bp"] == ["per", "pbr"] and got["bpBlank"] == [True, True, False]
    assert got["left"] == ["per"] and got["cur"] == ["dy"] and got["fcur"] == [] and got["kr"] == []
    assert got["odd"] == [[], [], [], []]
    assert got["rows"] == [True, False, True, False]


def test_the_note_names_its_fields_and_stays_out_otherwise():
    got = run("""
      const s = { t: 'HSBC', cls: 'us', per: 11.7, fgnCut: { pbr: 'mismatch', dy: 'mismatch' } };
      const html = (props) => renderToStaticMarkup(h(FN.FgnCutNote, props));
      out = { all: html({ s }), div: html({ s, fields: ['dy'] }), per: html({ s, fields: ['per'] }), shel: html({ s: { t: 'SHEL', cls: 'us', pbr: 1.43 } }) };""")
    assert LINE in got["all"] and 'data-ui-v2="fgn-cut"' in got["all"] and 'data-fields="pbr,dy"' in got["all"]
    assert 'data-fields="dy"' in got["div"] and got["per"] == "" and got["shel"] == ""


def test_tiles_hold_the_blanked_pbr_and_yield_with_rule_fgn():
    got = run("""
      const load = { status: 'ok', data: { stocks: STOCKS, usPxDate: '2026-11-13', pxDate: '2026-11-14', fx: 1333.8 }, coByT: new Map(), byT: new Map(STOCKS.map((x) => [x.t, x])) };
      const view = (t) => { const s = STOCKS.find((x) => x.t === t); return CO.orderTiles(CO.tileViews(load, s)).map((x) => [x.topic, x.rule, x.phrase, x.number, x.basis, x.art]); };
      out = { bp: view('BP'), hsbc: view('HSBC'), shel: view('SHEL'), peronly: view('PO') };""",
        STOCKS=[us("BP", dy=4.55, fgnCut={"per": "mismatch", "pbr": "mismatch"}),
                us("HSBC", per=11.7, fgnCut={"pbr": "mismatch", "dy": "mismatch"}),
                us("SHEL", per=8.6, pbr=1.43, dy=3.15), us("PO", pbr=2.0, dy=1.0, fgnCut={"per": "mismatch"})]
        + [us(f"U{i}", pbr=1.0 + i, dy=1.0) for i in range(6)])
    bp, hsbc = got["bp"], got["hsbc"]
    assert [x[:4] for x in bp][-1] == ["value", "fgn", "–", "PBR –"] and bp[-1][4] is None and bp[-1][5] is None
    assert [x[0] for x in bp][:3] == ["earn", "div", "risk"] and bp[1][1] != "fgn"                  # 배당은 평소대로 (남은 숫자)
    assert [x[:4] for x in hsbc[-2:]] == [["value", "fgn", "–", "PBR –"], ["div", "fgn", "–", "배당수익률 –"]], hsbc
    assert all(x[1] != "fgn" for x in got["shel"]) and all(x[1] != "fgn" for x in got["peronly"])    # PER 만 빈 회사: 칸은 그대로


def test_copy_line_word_for_word_and_approved():
    got = run("out = C2.co.fgnCut;")
    assert got == LINE
    appr = open(os.path.join(ROOT, "docs", "tasks", "v18.3-approved-in-chat.md"), encoding="utf-8").read()
    assert f"| `co.fgnCut` | {LINE} | Jack, 2026-11-14" in appr
