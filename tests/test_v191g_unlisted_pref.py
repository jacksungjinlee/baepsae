"""v19.1g: 상장되지 않은 우선주가 배당을 받은 회사의 배당 분할 확인 (Jack, 2026-11-07).

배당 표에 배당을 받은 우선주·종류주가 상장 우선주보다 많으면(상환전환우선주 · 종류주식) 현금배당금총액을 보통주 1주 기준으로 나눌 수
없어 위 끝을 셀 수 없었어요 (2026-11-07: 30곳). 그런 회사만 DART '주식의 총수 현황'을 받아 그해 말 보통주 유통 주식 수로 위 끝을
세요. 배당 표와 맞을 때만 (같은 주식 기준인지). 시험 숫자는 2026-11-07 에 받은 실제 2025 사업보고서 값이에요.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import fetch_data as F  # noqa: E402


def srow(se, iss, dist, tes="-"):
    return {"se": se, "istc_totqy": iss, "tesstk_co": tes, "distb_stock_co": dist}


MOBIS = [srow("보통주", "93,697,543", "89,176,783", "4,520,760"), srow("우선주", "3,974", "3,974"),
         srow("합계", "93,701,517", "89,180,757"), srow("비고", "-", "-")]
SOLUM = [srow("보통주", "47,816,236", "47,816,236"), srow("전환우선주", "-", "-"), srow("상환전환우선주", "7,000,000", "7,000,000"),
         srow("합계", "54,816,236", "54,816,236"), srow("비고", "-", "-")]
KIWOOM = [srow("의결권 있는\n 주식", "26,793,591", "25,893,134", "900,457"), srow("의결권 없는\n 주식", "501,388", "501,388"),
          srow("합계", "27,294,979", "26,394,522"), srow("비고", "-", "-")]
HANWHA = [srow("보통주\n(의결권 있는 주식)", "74,958,735", "69,375,482", "5,583,253"), srow("우선주\n(의결권 없는 주식)", "19,603,474", "19,603,474"),
          srow("합계", "94,562,209", "88,978,956"), srow("비고", "* 당사 정관 …", "-")]
ALTEOGEN = [srow("보통주식", "53,505,788", "53,482,080", "23,708"), srow("종류주식", "434,848", "434,848"), srow("합계", "53,940,636", "53,916,928")]


def test_the_share_report_under_each_label_layout():
    assert F.parse_dart_shares(MOBIS) == {"cmo": 89176783.0, "cmi": 93697543.0, "pfo": 3974.0}
    assert F.parse_dart_shares(SOLUM) == {"cmo": 47816236.0, "cmi": 47816236.0, "pfo": 7000000.0}     # '-' 줄은 0
    assert F.parse_dart_shares(KIWOOM)["cmo"] == 25893134.0 and F.parse_dart_shares(KIWOOM)["pfo"] == 501388.0
    assert F.parse_dart_shares(HANWHA)["cmo"] == 69375482.0 and F.parse_dart_shares(HANWHA)["pfo"] == 19603474.0
    assert F.parse_dart_shares(ALTEOGEN) == {"cmo": 53482080.0, "cmi": 53505788.0, "pfo": 434848.0}
    assert F.parse_dart_shares([srow("합계", "1", "1")]) is None                         # 보통주 줄이 없으면 판단하지 않아요
    assert F.parse_dart_shares([srow("보통주", "1", "1"), srow("보통주식", "2", "2")]) is None   # 둘이어도
    assert F.parse_dart_shares([srow("보통주", "-", "-")]) is None


def bas(cash, dps, pdps, par=5000.0):
    return {"cash3": [cash, None, None], "par3": [par] * 3, "eps3": [None] * 3, "ni3": [None] * 3, "pdps": [[p, None, None] for p in pdps]}


def test_mobis_is_checked_with_the_share_report():
    """현대모비스: 우선주 배당 6,550원이 상장되지 않은 우선주 몫까지 총액에 들어 있어요 (예전: 위 끝 없음 → 알 수 없음)."""
    b = bas(89192923 * 6500.0, 6500.0, [6550.0])
    cs3 = [93701517 * 5000 / 1e8] * 3
    old = F.div_basis([6500.0, 5000.0, 4500.0], b, cs3, 89_820_000, (), None)
    assert old["hi"] is None and old["divSt"] == "nd"
    new = F.div_basis([6500.0, 5000.0, 4500.0], b, cs3, 89_820_000, (), None, stk=F.parse_dart_shares(MOBIS))
    assert new["f0"] == 1.0 and new["dps3a"][0] == 6500.0 and abs(new["hi"] - 89_820_000 / 89176783 * 1.001) < 1e-9


def test_solum_with_redeemable_convertible_preferreds():
    b = bas(89866667 * 75.0, 75.0, [451.0], par=500.0)
    cs3 = [54816236 * 500 / 1e8] * 3
    r = F.div_basis([75.0, 70.0, 0.0], b, cs3, 47_820_000, (), None, stk=F.parse_dart_shares(SOLUM))
    assert r["f0"] == 1.0 and r["dps3a"][0] == 75.0


def test_the_share_report_is_not_used_when_it_disagrees_with_the_dividend_table():
    """주당 배당금이 다른 주식 기준(예: 보고서 뒤 분할로 주당 배당이 새 기준)이면 배당 표로 센 보통주 수가 유통 주식 수와 크게 달라요 → 판단하지 않아요."""
    stk = F.parse_dart_shares(MOBIS)
    b = bas(89192923 * 6500.0, 3250.0, [3275.0])                                    # 같은 총액, 주당 배당은 절반 (주식 수 두 배)
    cs3 = [93701517 * 5000 / 1e8] * 3
    r = F.div_basis([3250.0, 5000.0, 4500.0], b, cs3, 89_820_000, (), None, stk=stk)
    assert r["hi"] is None and r["f0"] is None
    # 우선주 줄이 '-' 로만 적혀 있는데 배당을 받은 종류가 있으면: 우선주 몫을 뺄 수 없어 배당 표의 보통주 수가 너무 커요 → 판단하지 않아요
    no_pref = [srow("보통주", "47,816,236", "47,816,236"), srow("상환전환우선주", "-", "-")]
    r = F.div_basis([75.0, 70.0, 0.0], bas(89866667 * 75.0, 75.0, [451.0], par=500.0), [274.08] * 3, 47_820_000, (), None,
                    stk=F.parse_dart_shares(no_pref))
    assert r["hi"] is None and r["f0"] is None


def test_stk_upper_bounds():
    stk = {"cmo": 100.0, "pfo": 10.0}
    assert F.stk_upper(100.0, stk, 100 * 50 + 10 * 60, 50.0, [60.0]) == 100.0 / 100.0 * 1.001
    assert F.stk_upper(100.0, stk, 120 * 50 + 10 * 60, 50.0, [60.0]) is None      # 배당 표의 보통주 120 > 유통 100 × 1.02
    assert F.stk_upper(100.0, stk, 80 * 50 + 10 * 60, 50.0, [60.0]) is None       # 80 < 100 × 0.85
    assert F.stk_upper(100.0, stk, 100 * 50 + 10 * 60, 50.0, []) is None          # 우선주 배당이 없으면 쓰지 않아요
    assert F.stk_upper(100.0, {"cmo": 100.0, "pfo": None}, 5600.0, 50.0, [60.0]) is None
    assert F.stk_upper(None, stk, 5600.0, 50.0, [60.0]) is None


def test_the_listed_preferred_path_is_unchanged():
    """상장 우선주로 셀 수 있는 회사(삼성전자처럼)는 주식의 총수 현황이 있어도 예전 위 끝을 그대로 써요."""
    b = bas(100e6 * 1000 + 20e6 * 1050, 1000.0, [1050.0])
    cs3 = [120e6 * 5000 / 1e8] * 3
    a = F.div_basis([1000.0, 1000.0, 1000.0], b, cs3, 100e6, (20e6,), None)
    s = F.div_basis([1000.0, 1000.0, 1000.0], b, cs3, 100e6, (20e6,), None, stk={"cmo": 1.0, "pfo": 1.0})
    assert a == s and a["f0"] == 1.0


def test_only_companies_with_more_paid_classes_than_listed_preferreds_ask_for_the_report():
    assert F.unlisted_paid({"pdps": [[6550.0, 0, 0]]}, 0) and not F.unlisted_paid({"pdps": [[1050.0, 0, 0]]}, 1)
    assert not F.unlisted_paid({"pdps": [[0.0, 100.0, 0]]}, 0)                     # 올해 우선주 배당이 없으면
    assert F.unlisted_paid({"pdps": [[100.0, 0, 0], [100.0, 0, 0]]}, 1) and not F.unlisted_paid({}, 0)


class FakeClient:
    def __init__(self):
        import threading
        self.calls, self.lock, self.today = [], threading.Lock(), F.dt.date(2026, 11, 8)
        self.fatal = None

    def report(self, endpoint, corp, year, reprt, tag, parse, extra=None, redo=None):
        self.calls.append((endpoint, corp, tag))
        if endpoint == "stockTotqySttus.json":
            return parse(MOBIS)
        return None


def test_the_pipeline_fetches_the_report_only_when_needed_and_never_writes_it_out(monkeypatch):
    c = FakeClient()
    divs = {"C1": {"dps": 6500.0, "dps3": [6500.0, 5000.0, 4500.0], "bas": bas(89192923 * 6500.0, 6500.0, [6550.0])},
            "C2": {"dps": 1000.0, "dps3": [1000.0, 1000.0, 1000.0], "bas": bas(120e6 * 1000, 1000.0, [1050.0])}}
    monkeypatch.setattr(F, "dart_corp_map", lambda client: {"012330": "C1", "005930": "C2"})
    monkeypatch.setattr(F, "dart_financials", lambda client, corp, yr: {"debt": 50.0} if yr == 2025 else {})
    monkeypatch.setattr(F, "dart_dividend", lambda client, corp, yr: divs[corp])
    monkeypatch.setattr(F, "dart_quarter", lambda *a, **k: None)
    c.started_empty, c.mode, c.entries = False, "cache", {}
    c.save = lambda: None
    c.summary = lambda: "ok"
    c.raise_if_fatal = lambda: None
    c.path = "/nonexistent"
    stocks = [{"t": "012330", "cls": "kr", "cap": 20.0, "shr": 89_820_000, "price": 350000.0},
              {"t": "005930", "cls": "kr", "cap": 500.0, "shr": 5.9e9, "price": 60000.0}]
    F.enrich_with_dart(stocks, c, {"00593": [8.2e8]})                                # 삼성전자는 상장 우선주가 있어요
    assert [x for x in c.calls if x[0] == "stockTotqySttus.json"] == [("stockTotqySttus.json", "C1", "STK")]
    assert stocks[0]["_stk"]["cmo"] == 89176783.0 and "_stk" not in stocks[1]
    F.apply_div_basis(stocks, {}, {"00593": [8.2e8]})
    for s in stocks:
        assert not [k for k in s if k.startswith("_")], s
