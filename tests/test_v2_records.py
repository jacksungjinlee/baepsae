# -*- coding: utf-8 -*-
"""뱁새 2.0 v19.6a 기록 (src/v2/records.js · csv.js · store.js 의 splits) — Node 에서 가짜 localStorage 로 돌려봐요.

docs/tasks/v19.6-records-alerts-dark.md A.1 · A.2 · A.5 · Part I.1:
- 새 미국 기록의 환율은 그 날짜의 것: 오늘은 data.json fx, 지난 날은 macro.json fxHist 의 그날(또는 그 전) 종가. fxHist 가 없거나
  그날까지 오지 않으면 저장하지 않아요 (다른 날 환율로는 절대 안 해요). 2016 년 전은 환율 없이
- 팔았어요: 가진 수량보다 많이 못 팔고, 처음 산 날보다 앞선 날짜도 안 돼요. 금액으로 넣은 종목은 판 금액으로 한 번에 다
- 기록 지우기: 뒤의 판매가 가진 수량보다 많아지면 거절
- 다 판 뒤 빼기 → 판 기록 · 배당 기록은 history 로 (내 수익에 남아요) · 남겨 두기 → 0주 종목 (산 적 없는 종목이 아니에요)
- 기록 내려받기 CSV: BOM · CRLF · RFC 4180 따옴표 · 종목 코드 ="005930" · 사용자 글은 수식으로 읽히지 않게 ' · 환율 없으면 원화 금액 빈칸
- 저장 기록: 분할(splits)도 2판 부분이에요. 검사 · 합치기 · 내보내기 → 불러오기가 그대로 돌아요. 예전 앱 창(v19.3d)은 분할을 모르니
  분할 뒤 판매가 있는 포트폴리오를 따로 둘 뿐(판 주식을 가진 것으로 세지 않아요), 새 앱이 다시 열면 되돌려 합쳐요 (아무것도 잃지 않아요)
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
_B = {}


def _old_sources(tmp):
    """main 의 v19.3d store.js · held.js (분할을 모르는 예전 앱, 7b5c895) — tests/fixtures/old_client_7b5c895 에 둔 그 파일들이에요
    (CI 는 git 기록을 얕게 받아서 git show 로는 읽을 수 없어요). 임시 폴더로 옮겨 그대로 써요."""
    d = os.path.join(tmp, "old")
    os.makedirs(d, exist_ok=True)
    for f in ("store.js", "held.js", "dcf.js"):
        shutil.copy(os.path.join(ROOT, "tests", "fixtures", "old_client_7b5c895", f), os.path.join(d, f))
    return os.path.join(d, "store.js")


def run(body):
    if "p" not in _B:
        tmp = tempfile.mkdtemp(prefix="baepsae-rec-")
        entry = os.path.join(tmp, "entry.js")
        old = _old_sources(tmp)
        with open(entry, "w", encoding="utf-8") as f:
            for name, mod in (("S", "store.js"), ("H", "held.js"), ("L", "lots.js"), ("Rc", "records.js"), ("Csv", "csv.js"), ("Rt", "routes.js")):
                f.write(f"export * as {name} from {json.dumps(os.path.join(ROOT, 'src', 'v2', mod))};\n")
            f.write(f"export * as Old from {json.dumps(old)};\n")
        exe = os.path.join(ROOT, "node_modules", ".bin", "esbuild")
        r = subprocess.run([exe, entry, "--bundle", "--format=esm", "--platform=node", f"--outfile={tmp}/rec.mjs", "--log-level=warning",
                            "--loader:.js=jsx", "--charset=utf8"], cwd=ROOT, capture_output=True, text=True)
        assert r.returncode == 0, r.stderr
        _B["p"] = tmp
    code = ("import { S, H, L, Rc, Csv, Old, Rt } from './rec.mjs';\n" + FAKE + "let out;\n" + body + "\nprocess.stdout.write(JSON.stringify(out));")
    r = subprocess.run([NODE, "--input-type=module", "-e", code], cwd=_B["p"], capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


@pytest.fixture(scope="module", autouse=True)
def _cleanup():
    yield
    if "p" in _B:
        shutil.rmtree(_B["p"], ignore_errors=True)


FAKE = """
const mem = new Map(); const warns = [];
globalThis.localStorage = { getItem: (k) => (mem.has(k) ? mem.get(k) : null), setItem: (k, v) => mem.set(k, String(v)), removeItem: (k) => mem.delete(k),
  get length() { return mem.size; }, key: (i) => [...mem.keys()][i] ?? null };
console.warn = (m) => warns.push(String(m)); console.info = () => {};
const K = 'baepsae2.v1', T = '2026-11-06';
const HIST = { asOf: '2026-11-05', rows: [['2016-01-04', 1172.5], ['2026-10-30', 1338.0], ['2026-11-03', 1375.2], ['2026-11-05', 1390.4]] };
const env = (o = {}) => ({ today: T, fx: 1401.1, fxDate: '2026-11-05', fxHist: HIST, stale: false, ...o });
const band = (t) => [{ id: 'band', kind: 'band', check: 'checked', target: t, bands: [0.75 * t, 1.25 * t, 1.4 * t] }];
const deckOf = (extra = {}) => ({ id: 'd1', name: '배당 생활비 포트폴리오', createdAt: '2026-10-01', planFx: 1300,
  holdings: [{ t: '005930', nk: '삼성전자', target: 0.5, rules: band(0.5) }, { t: 'AAPL', nk: 'Apple Inc.', target: 0.5, rules: band(0.5) }],
  purchases: [{ id: 'p1aaaaaa', t: '005930', qty: 10, price: 200000, date: '2026-10-02', ccy: 'KRW' }, { id: 'p2aaaaaa', t: 'AAPL', qty: 3, price: 300, date: '2026-10-02', ccy: 'USD', fx: 1300 }],
  ...extra });
const S5930 = { t: '005930', nk: '삼성전자', cls: 'kr', price: 225000 };
const SAAPL = { t: 'AAPL', nk: 'Apple Inc.', cls: 'us', ccy: 'USD', price: 344.63 };
"""


def test_the_rate_of_a_records_date_never_another_days():
    got = run("""out = {
      today: Rc.rateFor(T, env()), onDay: Rc.rateFor('2026-11-03', env()), weekend: Rc.rateFor('2026-11-01', env()), last: Rc.rateFor('2026-11-05', env()),
      gapFresh: Rc.rateFor('2026-11-06', env({ today: '2026-11-07' })), gapStale: Rc.rateFor('2026-11-06', env({ today: '2026-11-07', stale: true })),
      gapOtherDate: Rc.rateFor('2026-11-06', env({ today: '2026-11-07', fxDate: '2026-11-06' })),
      noHist: Rc.rateFor('2026-11-03', env({ fxHist: null })), badHist: Rc.rateFor('2026-11-03', env({ fxHist: { asOf: '2026-11-05', rows: [['2026-11-05', 0]] } })),
      asOfOff: Rc.rateFor('2026-11-03', env({ fxHist: { ...HIST, asOf: '2026-11-04' } })),
      pre2016: Rc.rateFor('2015-12-31', env()), first2016: Rc.rateFor('2016-01-01', env()), beforeFirst: Rc.rateFor('2016-01-02', env()),
      noToday: Rc.rateFor(T, env({ fx: null })), staleToday: Rc.rateFor(T, env({ stale: true })), bad: Rc.rateFor('2026-02-30', env()) };""")
    assert got["today"] == {"ok": True, "fx": 1401.1}                                        # 오늘: data.json fx
    assert got["onDay"] == {"ok": True, "fx": 1375.2} and got["weekend"] == {"ok": True, "fx": 1338.0} and got["last"] == {"ok": True, "fx": 1390.4}
    assert got["gapFresh"] == {"ok": False, "why": "past"}                                   # 리뷰 2차: fxHist 마지막 날 뒤의 지난 날짜는 거절 (오늘만 data.json fx)
    assert got["gapStale"] == {"ok": False, "why": "past"} and got["gapOtherDate"] == {"ok": False, "why": "past"}
    assert got["noHist"] == {"ok": False, "why": "past"} and got["badHist"]["ok"] is False and got["asOfOff"]["ok"] is False
    assert got["pre2016"] == {"ok": True, "fx": None, "before": True}                           # 2016 전: 환율 없이 (noFx 표시)
    assert got["first2016"] == {"ok": False, "why": "past"} and got["beforeFirst"] == {"ok": False, "why": "past"}   # 2016 부터 fxHist 가 닿지 않으면 거절
    assert got["noToday"] == {"ok": False, "why": "today"} and got["bad"] == {"ok": False, "why": "date"}
    assert got["staleToday"] == {"ok": False, "why": "today"}                                  # 멈춘 데이터의 fx 는 다른 날의 환율


def test_sale_checks_too_many_too_early_whole_shares_and_past_us_dates():
    got = run("""const d = deckOf({ sales: [{ id: 's1aaaaaa', t: '005930', qty: 4, price: 210000, date: '2026-10-20', ccy: 'KRW' }] });
      const c = (t, i, s, e = env()) => { const r = Rc.checkSale(d, t, i, s, e); return r.ok ? { ok: true, rec: { ...r.rec, id: undefined } } : { ok: false, why: r.why, field: r.field }; };
      out = { ok: c('005930', { qty: '6', price: '', date: T }, S5930), many: c('005930', { qty: '7', date: T }, S5930),
        early: c('005930', { qty: '1', date: '2026-10-01' }, S5930), frac: c('005930', { qty: '1.5', date: T }, S5930), past: c('005930', { qty: '7', date: '2026-10-19' }, S5930),
        between: c('005930', { qty: '7', date: '2026-10-21' }, S5930),
        usToday: c('AAPL', { qty: '0.5', price: '350.25', date: T }, SAAPL), usPast: c('AAPL', { qty: '1', date: '2026-11-03' }, SAAPL),
        usNoHist: c('AAPL', { qty: '1', date: '2026-11-03' }, SAAPL, env({ fxHist: null })), usDecimals: c('AAPL', { qty: '0.00001', date: T }, SAAPL),
        future: c('005930', { qty: '1', date: '2026-11-07' }, S5930), word: c('005930', { qty: 'abc', date: T }, S5930) };""")
    assert got["ok"] == {"ok": True, "rec": {"t": "005930", "qty": 6, "price": 225000, "date": "2026-11-06", "ccy": "KRW"}}   # 가격 빈칸 → 마지막 종가
    assert got["many"] == {"ok": False, "why": "tooMany", "field": "qty"} and got["early"] == {"ok": False, "why": "tooEarly", "field": "date"}
    assert got["frac"] == {"ok": False, "why": "input", "field": "qty"} and got["usDecimals"] == {"ok": False, "why": "input", "field": "qty"}
    assert got["past"] == {"ok": False, "why": "tooMany", "field": "qty"}                      # 10/19 에 7주를 팔면 10/20 의 4주가 0 아래
    assert got["between"] == {"ok": False, "why": "tooMany", "field": "qty"}
    assert got["usToday"] == {"ok": True, "rec": {"t": "AAPL", "qty": 0.5, "price": 350.25, "date": "2026-11-06", "ccy": "USD", "fx": 1401.1}}
    assert got["usPast"]["ok"] and got["usPast"]["rec"]["fx"] == 1375.2 and got["usPast"]["rec"]["price"] == 344.63
    assert got["usNoHist"] == {"ok": False, "why": "rate", "field": "date"}                  # 지난 날짜의 미국 기록: 환율이 없으면 저장 안 함
    assert got["future"] == {"ok": False, "why": "input", "field": "date"} and got["word"] == {"ok": False, "why": "input", "field": "qty"}


def test_a_holding_put_in_by_amount_is_sold_all_at_once_by_its_amount():
    got = run("""const d = { id: 'i', name: 'i', createdAt: '2026-10-01', kind: 'imported', settings: { points: {} }, holdings: [{ t: '005930', nk: '삼성전자', cls: 'kr' }],
        purchases: [], imported: [{ t: '005930', nk: '삼성전자', ccy: 'KRW', amountWon: 1000000, close: 300000, date: '2026-10-01' }] };
      const r = Rc.checkSale(d, '005930', { amountWon: '1200000', date: T }, S5930, env());
      const next = r.ok ? Rc.withRecord({ v: 2, decks: [d] }, 'i', 'sales', r.rec, T) : null;
      out = { r: r.ok ? { qty: r.rec.qty, money: Math.round(r.rec.qty * r.rec.price) } : r, bad: Rc.checkSale(d, '005930', { amountWon: '', date: T }, S5930, env()),
        st: Rc.stockState(d, '005930').byAmount, valid: next && S.validStore(next, T), out: next && Rc.soldOutNow(next.decks[0], '005930') };""")
    assert got["r"] == {"qty": 3.3333, "money": 1200000} and got["st"] is True                # 가진 3.3333주(금액 ÷ 그날 종가) 모두, 판 금액 그대로
    assert got["bad"]["why"] == "input" and got["bad"]["field"] == "amount" and got["valid"] is True and got["out"] is True


def test_records_go_in_with_the_split_they_need_and_a_dividend_after_removal_goes_into_history():
    got = run("""const d = deckOf({ purchases: [{ id: 'p1aaaaaa', t: 'AAPL', qty: 10, price: 400, date: '2026-08-01', ccy: 'USD', fx: 1300 }],
        holdings: [{ t: 'AAPL', nk: 'Apple Inc.', target: 1, rules: band(1) }] });
      const view = L.withDataSplits({ v: 2, decks: [d] }, [{ t: 'AAPL', date: '2026-09-01', r: 4 }], T);
      const sale = Rc.checkSale(view.decks[0], 'AAPL', { qty: '40', price: '120', date: '2026-10-01' }, SAAPL, env({ fxHist: { asOf: '2026-11-05', rows: [['2026-09-30', 1350], ['2026-11-05', 1390]] } }));
      const next = Rc.withRecord(view, 'd1', 'sales', sale.rec, T);
      const text = JSON.stringify(next);
      const back = S.parseImport(S.exportText(next), T);
      const gone = S.withoutHolding(next, 'd1', 'AAPL', T, 9);
      const div = Rc.checkDiv(gone.decks[0], 'AAPL', { amount: '2.5', date: T }, SAAPL, env());
      const later = Rc.withRecord(gone, 'd1', 'divs', div.rec, T);
      out = { sale: sale.ok, splits: next.decks[0].splits, valid: S.validStore(JSON.parse(text), T), back: back && back.decks[0].splits, v: back && back.v,
        hist: later.decks[0].history.map((e) => [e.t, e.sales.length, e.divs.length]), lateValid: S.validStore(JSON.parse(JSON.stringify(later)), T),
        noRec: Rc.withRecord(gone, 'd1', 'sales', sale.rec, T) };""")
    assert got["sale"] is True and got["splits"] == [{"t": "AAPL", "date": "2026-09-01", "r": 4}]
    assert got["valid"] is True and got["back"] == got["splits"] and got["v"] == 2            # 내보내기 → 불러오기 그대로
    assert got["hist"] == [["AAPL", 1, 1]] and got["lateValid"] is True                       # 뺀 뒤에 받은 배당은 그 종목의 history 로
    assert got["noRec"] is None                                                              # 빠진 종목에 판 기록은 안 들어가요


def test_deleting_a_record_that_would_leave_a_later_sale_too_big_is_refused():
    got = run("""const d = deckOf({ purchases: [...deckOf().purchases, { id: 'p3aaaaaa', t: '005930', qty: 5, price: 210000, date: '2026-10-05', ccy: 'KRW' }],
        sales: [{ id: 's1aaaaaa', t: '005930', qty: 12, price: 230000, date: '2026-10-20', ccy: 'KRW' }],
        divs: [{ id: 'v1aaaaaa', t: '005930', amount: 3610, ccy: 'KRW', date: '2026-10-25' }] });
      const data = { v: 2, decks: [d] };
      const items = Rc.recordsOf(d, '005930');
      const it = (k) => items.find((x) => x.kind === k);
      const delBuy = Rc.withoutRecord(data, 'd1', items.find((x) => x.kind === 'buy' && x.rec.qty === 5), T);
      const delSale = Rc.withoutRecord(data, 'd1', it('sell'), T);
      const delDiv = Rc.withoutRecord(data, 'd1', it('div'), T);
      out = { order: items.map((x) => [x.kind, x.date]), delBuy, delSale: delSale.ok && delSale.data.decks[0].sales.length, delDiv: delDiv.ok && delDiv.data.decks[0].divs.length,
        stale: Rc.withoutRecord(data, 'd1', { ...it('div'), rec: { ...it('div').rec } }, T) };""")
    assert got["order"] == [["div", "2026-10-25"], ["sell", "2026-10-20"], ["buy", "2026-10-05"], ["buy", "2026-10-02"]]
    assert got["delBuy"] == {"ok": False, "why": "below"}                                    # 5주를 지우면 12주 판매가 10주보다 많아요
    assert got["delSale"] == 0 and got["delDiv"] == 0
    assert got["stale"] == {"ok": False, "why": "gone"}                                       # 이미 바뀐 기록은 지우지 않아요


def test_full_sale_then_remove_or_keep():
    got = run("""const d = deckOf();
      const r = Rc.checkSale(d, 'AAPL', { qty: '3', date: T }, SAAPL, env());
      const next = Rc.withRecord({ v: 2, decks: [d] }, 'd1', 'sales', r.rec, T);
      const kept = next.decks[0];
      const removed = S.withoutHolding(next, 'd1', 'AAPL', T, 5).decks[0];
      out = { soldOut: Rc.soldOutNow(kept, 'AAPL'), units: H.heldUnits(kept).get('AAPL'), inHoldings: kept.holdings.some((h) => h.t === 'AAPL'),
        removed: { holdings: removed.holdings.map((h) => h.t), sales: removed.sales.length, hist: removed.history.map((e) => [e.t, e.purchases.length, e.sales.length]) },
        notSold: Rc.soldOutNow(d, 'AAPL') };""")
    assert got["soldOut"] is True and got["units"] == 0 and got["inHoldings"] is True and got["notSold"] is False
    assert got["removed"] == {"holdings": ["005930"], "sales": 0, "hist": [["AAPL", 1, 1]]}   # 판 기록은 history 로 (내 수익에 남아요)


def test_csv_quotes_escapes_keeps_codes_and_leaves_won_blank_without_a_rate():
    got = run("""const d = deckOf({ name: '=SUM(A1), "내" 계좌', planFx: undefined,
        holdings: [{ t: '005930', nk: '+삼성전자\\n우', target: 0.5 }, { t: 'AAPL', nk: 'Apple Inc.', target: 0.5 }],
        purchases: [{ t: '005930', qty: 10, price: 200000, date: '2026-10-02', ccy: 'KRW' }, { t: 'AAPL', qty: 3, price: 300.5, date: '2026-10-02', ccy: 'USD' }],
        sales: [{ t: 'AAPL', qty: 0.5, price: 310, date: '2026-10-03', ccy: 'USD', fx: 1350.5 }], divs: [{ t: 'AAPL', amount: 1.2, date: '2026-10-04', ccy: 'USD' }],
        history: [{ t: '000660', nk: '@SK하이닉스', out: '2026-10-10', purchases: [{ t: '000660', qty: 1, price: 1000000, date: '2026-10-01', ccy: 'KRW' }],
          sales: [{ t: '000660', qty: 1, price: 1100000, date: '2026-10-09', ccy: 'KRW' }], divs: [] }] });
      delete d.planFx;
      const imp = { id: 'i', name: '-가진', kind: 'imported', holdings: [{ t: '035420', nk: 'NAVER' }], imported: [{ t: '035420', nk: 'NAVER', ccy: 'KRW', qty: 2, avg: 180000 },
        { nk: '비상장', ccy: 'KRW', amountWon: 500000, date: '2026-10-01', unscored: true }], purchases: [] };
      const text = Csv.recordsCsv({ decks: [d, imp] }, ['포트폴리오', '기록', '날짜', '종목 코드', '종목명', '수량', '가격', '통화', '환율', '원화 금액'],
        { buy: '샀어요', sell: '팔았어요', div: '배당 받았어요', imp: '가진 종목' });
      out = { text, name: Csv.csvName('baepsae-records', T), plain: [Csv.plain(1234567.5, 4), Csv.plain(0.1 + 0.2, 4), Csv.plain(2e21, 0), Csv.plain(NaN)] };""")
    t = got["text"]
    assert t.startswith("\ufeff") and t.endswith("\r\n")
    assert "\n" not in t.replace("\r\n", "").replace('"\'+삼성전자\n우"', "")                # 줄바꿈은 따옴표 안 이름의 것뿐, 줄 끝은 CRLF
    lines = t[1:].split("\r\n")
    assert lines[0] == "포트폴리오,기록,날짜,종목 코드,종목명,수량,가격,통화,환율,원화 금액"
    pf = "\"'=SUM(A1), \"\"내\"\" 계좌\""                                                      # ' 를 앞에 · 쉼표 · 따옴표 → 따옴표로 감싸고 두 번
    assert lines[1:7] == [                                                                     # 오래된 기록부터 (뺀 종목의 기록도)
        pf + ",샀어요,2026-10-01,\"=\"\"000660\"\"\",'@SK하이닉스,1,1000000,KRW,,1000000",
        pf + ',샀어요,2026-10-02,"=""005930""","\'+삼성전자\n우",10,200000,KRW,,2000000',
        pf + ',샀어요,2026-10-02,"=""AAPL""",Apple Inc.,3,300.5,USD,,',                      # 환율 없는 미국 매수: 원화 금액 빈칸
        pf + ',팔았어요,2026-10-03,"=""AAPL""",Apple Inc.,0.5,310,USD,1350.5,209328',
        pf + ',배당 받았어요,2026-10-04,"=""AAPL""",Apple Inc.,,1.2,USD,,',                  # 배당: 수량 빈칸, 금액은 가격 칸
        pf + ",팔았어요,2026-10-09,\"=\"\"000660\"\"\",'@SK하이닉스,1,1100000,KRW,,1100000"]
    assert lines[7] == "'-가진,가진 종목,,\"=\"\"035420\"\"\",NAVER,2,180000,KRW,,360000"    # 날짜 없는 가져온 줄이 먼저
    assert lines[8] == "'-가진,가진 종목,2026-10-01,,비상장,,,KRW,,500000" and lines[9] == "" and len(lines) == 10
    assert got["name"] == "baepsae-records-2026-11-06.csv"
    assert got["plain"] == ["1234567.5", "0.3", "2000000000000000000000", ""]


def test_store_splits_part_is_checked_merged_and_set_aside_per_portfolio():
    got = run("""const good = deckOf({ splits: [{ t: 'AAPL', date: '2026-09-01', r: 4 }] });
      const bad = { ...deckOf(), id: 'd2', splits: [{ t: 'AAPL', date: '2026-09-01', r: 1 }] };
      const twice = { ...deckOf(), id: 'd3', splits: [{ t: 'AAPL', date: '2026-09-01', r: 4 }, { t: 'AAPL', date: '2026-09-01', r: 2 }] };
      const future = { ...deckOf(), id: 'd4', splits: [{ t: 'AAPL', date: '2026-12-01', r: 4 }] };
      const chk = S.checkStore({ v: 2, decks: [good, bad, twice, future] }, T);
      const v1 = S.checkStore({ v: 1, decks: [good] }, T);
      const v1sales = S.checkStore({ v: 1, decks: [{ ...good, sales: [] }] }, T);
      const a = deckOf({ splits: [{ t: 'AAPL', date: '2026-09-01', r: 4 }] }), b = deckOf({ splits: [{ t: '005930', date: '2026-08-01', r: 2 }] });
      const m = S.mergeTabs({ v: 2, decks: [b] }, { v: 2, decks: [a] }, T);
      out = { kept: chk.data.decks.map((d) => d.id), problems: chk.problems.length, v1: v1.problems, v1sales: v1sales.problems[0], merged: m && m.decks[0].splits,
        ver: S.versionFor({ decks: [good] }), parts: S.V2_DECK_PARTS.includes('splits') };""")
    assert got["kept"] == ["d1"] and got["problems"] == 3                                    # 나쁜 분할이 있는 포트폴리오만 따로
    # a v1 store holding only splits (the v19.3d app re-tags v1 and keeps the key) reads; any other v2 part still does not
    assert got["v1"] == [] and "version-2 part in a version-1 store" in got["v1sales"] and got["ver"] == 2 and got["parts"] is True
    assert got["merged"] == [{"t": "AAPL", "date": "2026-09-01", "r": 4}, {"t": "005930", "date": "2026-08-01", "r": 2}]


def test_an_earlier_app_tab_never_counts_sold_shares_and_never_loses_the_records():
    """v19.6 A.1: the v19.3d app (live before this PR, the 'older client' now) does not know splits. A store whose sale of
    the new share count relies on a stored split reads there with that portfolio set aside (no wrong held quantity, nothing
    shown as held), its first write moves the stored text to a backup key, and this app puts it back and merges (합쳤어요)."""
    got = run("""const d = deckOf({ purchases: [{ id: 'p1aaaaaa', t: 'AAPL', qty: 10, price: 400, date: '2026-08-01', ccy: 'USD', fx: 1300 }],
        holdings: [{ t: 'AAPL', nk: 'Apple Inc.', target: 1, rules: band(1) }],
        sales: [{ id: 's1aaaaaa', t: 'AAPL', qty: 40, price: 120, date: '2026-10-01', ccy: 'USD', fx: 1350 }], splits: [{ t: 'AAPL', date: '2026-09-01', r: 4 }] });
      const other = { ...deckOf(), id: 'd2', name: '두 번째' };
      S.writeStore({ v: 2, decks: [d, other] }, K, T);
      const oldRead = Old.readStore(K, T);
      const oldDecks = oldRead.data.decks.map((x) => x.id);
      // the earlier tab saves a change of its own (a note) over what it could read
      const wrote = Old.writeStore({ ...oldRead.data, notes: { '005930': { text: '메모', at: T } } }, K, T);
      const aside = [...mem.keys()].filter((k) => k.includes('.unreadable.')).length;
      const back = S.readStore(K, T);
      out = { oldDecks, oldLocked: oldRead.locked, wrote, aside, decks: back.data.decks.map((x) => x.id).sort(), restored: back.restored,
        sales: back.data.decks.find((x) => x.id === 'd1').sales.length, splits: back.data.decks.find((x) => x.id === 'd1').splits,
        note: !!(back.data.notes && back.data.notes['005930']), held: H.heldUnits(back.data.decks.find((x) => x.id === 'd1')).get('AAPL') };""")
    assert got["oldDecks"] == ["d2"] and got["oldLocked"] is True                             # 예전 앱: 그 포트폴리오만 따로 (판 주식을 가진 것으로 세지 않아요)
    assert got["wrote"] is True and got["aside"] >= 1                                          # 쓰기 전에 읽지 못한 기록을 따로 보관
    assert got["decks"] == ["d1", "d2"] and got["restored"] is True                          # 새 앱이 되돌려 합치고 한 번 알려요
    assert got["sales"] == 1 and got["splits"] == [{"t": "AAPL", "date": "2026-09-01", "r": 4}] and got["note"] is True and got["held"] == 0


def test_the_returns_address_names_one_portfolio():
    got = run("""out = Object.fromEntries(['#portfolio/returns/d1', '#portfolio/returns/d_1-x', '#portfolio/returns/', '#portfolio/returns/a b',
      '#portfolio/returns', '#home/returns/d1'].map((h) => [h, Rt.parseHash(h)]));""")
    assert got["#portfolio/returns/d1"] == {"tab": "portfolio", "sub": "returns/d1", "about": False, "known": True, "returns": "d1"}
    assert got["#portfolio/returns/d_1-x"]["returns"] == "d_1-x"
    for h in ("#portfolio/returns/", "#portfolio/returns/a b", "#portfolio/returns", "#home/returns/d1"):
        assert got[h] == {"tab": "home", "sub": None, "about": False, "known": False}, h            # 모르는 주소 → #home


# ── v19.6a 리뷰 1차 (2026-11-13) ──
def test_new_records_before_2016_carry_no_rate_and_the_csv_leaves_won_blank():
    got = run("""const d = deckOf();
      const p = Rc.checkPurchase(d, 'AAPL', { qty: '1', price: '100', date: '2015-12-31' }, SAAPL, env());
      const s = Rc.checkSale(d, 'AAPL', { qty: '1', price: '100', date: '2015-12-31' }, SAAPL, env());
      const v = Rc.checkDiv(d, 'AAPL', { amount: '1.5', date: '2015-12-31' }, SAAPL, env());
      const next = Rc.withRecord({ v: 2, decks: [d] }, 'd1', 'purchases', p.rec, T);
      const csv = Csv.recordsCsv(next, ['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h', 'i', 'j'], { buy: 'B', sell: 'S', div: 'D', imp: 'I' });
      out = { p: { ...p.rec, id: undefined }, s: s.why, v: { ...v.rec, id: undefined }, valid: S.validStore(next, T), line: csv.split('\\r\\n').find((x) => x.includes('2015-12-31')) };""")
    assert got["p"] == {"t": "AAPL", "date": "2015-12-31", "qty": 1, "price": 100, "ccy": "USD", "noFx": True}
    assert got["v"] == {"t": "AAPL", "amount": 1.5, "ccy": "USD", "date": "2015-12-31", "noFx": True}
    assert got["s"] == "tooEarly" and got["valid"] is True
    assert got["line"] == '배당 생활비 포트폴리오,B,2015-12-31,"=""AAPL""",Apple Inc.,1,100,USD,,'   # 환율 · 원화 금액 빈칸 (planFx 1,300 이 아니에요)


def test_a_dividend_of_a_stock_taken_out_uses_its_own_records_currency():
    """Round-1 review (Opus S6): the form's label and the saved record's currency come from one source, the stock's own
    records (history included), never today's data alone: typing 50,000 in a 원 form never saves $50,000."""
    got = run("""const us = { ...deckOf(), holdings: [{ t: '005930', nk: '삼성전자', target: 1, rules: band(1) }], purchases: [deckOf().purchases[0]],
        history: [{ t: 'AAPL', nk: 'Apple Inc.', out: '2026-10-20', purchases: [deckOf().purchases[1]], sales: [{ t: 'AAPL', qty: 3, price: 310, date: '2026-10-19', ccy: 'USD', fx: 1350 }], divs: [] }] };
      const krData = { t: 'AAPL', cls: 'kr', price: 1 };                                 // a data row that would say 원
      out = { ccy: [Rc.recordCcy(us, 'AAPL', krData), Rc.recordCcy(us, 'AAPL', null), Rc.recordCcy(us, '005930', SAAPL), Rc.recordCcy({ decks: [] }, 'XX', null)],
        div: Rc.checkDiv(us, 'AAPL', { amount: '50000', date: T }, krData, env()), cents: Rc.checkDiv(us, 'AAPL', { amount: '1.25', date: T }, krData, env()).rec.ccy };""")
    assert got["ccy"] == ["USD", "USD", "KRW", None]
    assert got["div"]["ok"] and got["div"]["rec"]["ccy"] == "USD" and got["div"]["rec"]["fx"] == 1401.1 and got["cents"] == "USD"


def test_a_us_holding_put_in_by_amount_sells_at_the_sale_dates_rate():
    got = run("""const d = { id: 'i', name: 'i', createdAt: '2026-10-01', kind: 'imported', settings: { points: {} }, holdings: [{ t: 'AAPL', nk: 'Apple Inc.', cls: 'us' }],
        purchases: [], imported: [{ t: 'AAPL', nk: 'Apple Inc.', ccy: 'USD', amountWon: 1300000, close: 325, fx: 1300, date: '2026-10-01' }] };
      const r = Rc.checkSale(d, 'AAPL', { amountWon: '1500000', date: '2026-11-03' }, SAAPL, env());
      const noRate = Rc.checkSale(d, 'AAPL', { amountWon: '1500000', date: '2026-11-03' }, SAAPL, env({ fxHist: null }));
      out = { fx: r.rec.fx, qty: r.rec.qty, won: Math.round(r.rec.qty * r.rec.price * r.rec.fx * 1000) / 1000, noRate: [noRate.why, noRate.field, noRate.rate] };""")
    assert got["fx"] == 1375.2 and got["qty"] == 3.0769 and got["won"] == 1500000             # 판 날(11/3) 환율, 판 금액 그대로 (130만원 ÷ ($325 × 1,300))
    assert got["noRate"] == ["rate", "date", "past"]


def test_delete_refusal_inside_a_history_entry():
    got = run("""const d = { ...deckOf(), holdings: [{ t: '005930', nk: '삼성전자', target: 1, rules: band(1) }], purchases: [deckOf().purchases[0]],
        history: [{ t: 'AAPL', nk: 'Apple Inc.', out: '2026-10-20', purchases: [{ t: 'AAPL', qty: 3, price: 300, date: '2026-10-02', ccy: 'USD', fx: 1300 }],
          sales: [{ t: 'AAPL', qty: 3, price: 310, date: '2026-10-19', ccy: 'USD', fx: 1350 }], divs: [{ t: 'AAPL', amount: 1, date: '2026-10-25', ccy: 'USD', fx: 1360 }] }] };
      const data = { v: 2, decks: [d] };
      const items = Rc.recordsOf(d, 'AAPL');
      out = { buy: Rc.withoutRecord(data, 'd1', items.find((x) => x.kind === 'buy'), T), div: Rc.withoutRecord(data, 'd1', items.find((x) => x.kind === 'div'), T).ok };""")
    assert got["buy"] == {"ok": False, "why": "below"} and got["div"] is True


def test_csv_quotes_a_leading_tab_or_cr_and_marks_them_as_text():
    got = run("""const d = { ...deckOf({ name: '\\t탭' }), holdings: [{ t: '005930', nk: '\\r삼성', target: 1 }], purchases: [deckOf().purchases[0]] };
      out = Csv.recordsCsv({ decks: [d] }, ['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h', 'i', 'j'], { buy: 'B', sell: 'S', div: 'D', imp: 'I' }).split('\\r\\n')[1];""")
    assert got == "'\t탭,B,2026-10-02,\"=\"\"005930\"\"\",\"'\r삼성\",10,200000,KRW,,2000000"   # 탭: ' 만 · CR: ' + 따옴표


def test_splits_go_into_the_store_when_a_saved_record_is_dated_before_them():
    got = run("""const sp = [{ t: 'AAPL', date: '2026-09-01', r: 4 }];
      const base = deckOf({ purchases: [{ id: 'p1aaaaaa', t: 'AAPL', qty: 10, price: 400, date: '2026-08-01', ccy: 'USD', fx: 1300 }], holdings: [{ t: 'AAPL', nk: 'Apple Inc.', target: 1, rules: band(1) }] });
      const view = L.withDataSplits({ v: 2, decks: [base] }, sp, T);
      const after = Rc.withRecord(view, 'd1', 'purchases', { id: 'p2aaaaaa', t: 'AAPL', qty: 1, price: 100, date: '2026-10-01', ccy: 'USD', fx: 1350 }, T);
      const beforeOnly = Rc.withRecord(view, 'd1', 'purchases', { id: 'p3aaaaaa', t: 'AAPL', qty: 1, price: 400, date: '2026-08-15', ccy: 'USD', fx: 1320 }, T);
      const allAfter = L.withDataSplits({ v: 2, decks: [deckOf({ purchases: [{ id: 'p1aaaaaa', t: 'AAPL', qty: 10, price: 100, date: '2026-10-01', ccy: 'USD', fx: 1300 }],
        holdings: [{ t: 'AAPL', nk: 'Apple Inc.', target: 1, rules: band(1) }] })] }, sp, T);
      const after2 = Rc.withRecord(allAfter, 'd1', 'divs', { id: 'v1aaaaaa', t: 'AAPL', amount: 1, date: '2026-10-02', ccy: 'USD', fx: 1350 }, T);
      out = { after: after.decks[0].splits || null, beforeOnly: beforeOnly.decks[0].splits || null, allAfter: after2.decks[0].splits || null,
        missing: L.storedNotInData({ decks: [{ id: 'd1', splits: sp }] }, []), there: L.storedNotInData({ decks: [{ id: 'd1', splits: sp }] }, sp) };""")
    assert got["after"] == [{"t": "AAPL", "date": "2026-09-01", "r": 4}]
    assert got["beforeOnly"] == got["after"]                                                   # 리뷰 2차: 분할 전 기록이 있으면 저장 (산 뒤 그대로 둔 사람도)
    assert got["allAfter"] is None                                                             # 모든 기록이 분할 뒤면 저장할 것이 없어요
    assert got["missing"] == [{"id": "d1", "t": "AAPL", "date": "2026-09-01", "r": 4}] and got["there"] == []


def test_an_earlier_app_tab_that_retags_v1_keeps_the_splits_part_readable():
    """Round-1 review (Fable S1): the v19.3d app tags a store v1 when its only v2 part is one it does not know (splits) and
    keeps the key. This app reads it (not locked), with nothing lost, and its next write tags it v2 again."""
    got = run("""const d = deckOf({ purchases: [{ id: 'p1aaaaaa', t: 'AAPL', qty: 10, price: 400, date: '2026-08-01', ccy: 'USD', fx: 1300 },
          { id: 'p2aaaaaa', t: 'AAPL', qty: 4, price: 100, date: '2026-10-01', ccy: 'USD', fx: 1350 }],
        holdings: [{ t: 'AAPL', nk: 'Apple Inc.', target: 1, rules: band(1) }], splits: [{ t: 'AAPL', date: '2026-09-01', r: 4 }] });
      S.writeStore({ v: 2, decks: [d] }, K, T);
      const oldRead = Old.readStore(K, T);
      const wrote = Old.writeStore({ ...oldRead.data, notes: { '005930': { text: '메모', at: T } } }, K, T);
      const raw = JSON.parse(mem.get(K));
      const back = S.readStore(K, T);
      const again = S.writeStore(back.data, K, T);
      out = { oldDecks: oldRead.data.decks.map((x) => x.id), oldLocked: oldRead.locked, wrote, rawV: raw.v, rawSplits: raw.decks[0].splits, locked: back.locked,
        decks: back.data.decks.map((x) => x.id), splits: back.data.decks[0].splits, note: !!(back.data.notes || {})['005930'], held: H.heldUnits(back.data.decks[0]).get('AAPL'),
        again, v: JSON.parse(mem.get(K)).v };""")
    assert got["oldDecks"] == ["d1"] and got["oldLocked"] is False and got["wrote"] is True
    assert got["rawV"] == 1 and got["rawSplits"] == [{"t": "AAPL", "date": "2026-09-01", "r": 4}]   # 예전 앱: v1 로 적고 splits 는 그대로 둬요
    assert got["locked"] is False and got["decks"] == ["d1"] and got["splits"] == got["rawSplits"] and got["note"] is True
    assert got["held"] == 440000 and got["again"] is True and got["v"] == 2                     # 10주 × 4 + 4주 · 다음 저장은 다시 v2


# ── v19.6a 리뷰 2차 (2026-11-13) ──
def test_forms_refuse_a_year_before_2000_and_an_absurd_quantity():
    got = run("""const d = deckOf();
      out = { buy: Rc.checkPurchase(d, '005930', { qty: '1', date: '1999-12-31' }, S5930, env()), sell: Rc.checkSale(d, '005930', { qty: '1', date: '1926-11-06' }, S5930, env()),
        div: Rc.checkDiv(d, '005930', { amount: '100', date: '1999-01-01' }, S5930, env()), qty: Rc.checkPurchase(d, '005930', { qty: '1000000001', date: T }, S5930, env()),
        ok2000: Rc.checkPurchase(d, '005930', { qty: '1', price: '1000', date: '2000-01-01' }, S5930, env()).ok };""")
    for k in ("buy", "sell", "div"):
        assert got[k]["why"] == "input" and got[k]["field"] == "date", (k, got[k])
    assert got["qty"]["why"] == "input" and got["qty"]["field"] == "qty" and got["ok2000"] is True


def test_a_pre_2016_us_sale_of_a_holding_put_in_by_amount_is_refused():
    """M34: a by-amount sale turns 판 금액 into a dollar price at the sale date's rate; before 2016 there is none."""
    got = run("""const d = { id: 'i', name: 'i', createdAt: '2015-01-02', kind: 'imported', settings: { points: {} }, holdings: [{ t: 'AAPL', nk: 'Apple Inc.', cls: 'us' }],
        purchases: [], imported: [{ t: 'AAPL', nk: 'Apple Inc.', ccy: 'USD', amountWon: 1300000, close: 325, fx: 1300, date: '2015-01-02' }] };
      const r = Rc.checkSale(d, 'AAPL', { amountWon: '1500000', date: '2015-06-01' }, SAAPL, env());
      out = [r.ok, r.why, r.field];""")
    assert got == [False, "rate", "date"]
