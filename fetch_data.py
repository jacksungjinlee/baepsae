#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
뱁새(Baepsae) 데이터 수집 스크립트
──────────────────────────────────────────────────────────────
매일 한 번 GitHub Actions가 이 파일을 실행해서 data.json 을 만듭니다.
data.json 은 baepsae.html 과 같은 폴더에 놓이며, 도구가 자동으로 읽어갑니다.

계산하는 값
  price  현재가 (KRW 종목은 원, 미국 종목은 달러)
  beta   자기 시장 지수 대비 베타 (한국=코스피, 미국=S&P500)
  vol    연 변동성 % — 원화 투자자 기준(미국 종목은 환율 반영)
  al     최근 3년 알파 %p (자기 벤치마크 대비, CAPM 기준)
  per pbr dy  밸류에이션·배당
  cap val     시가총액·거래대금 (인기 순위용)

실패해도 죽지 않습니다. 개별 종목이 실패하면 건너뛰고, 전체의 절반 이상을
못 받아온 경우에만 오류로 종료합니다(그래야 기존 data.json 이 안 망가집니다).
"""

import json
import math
import sys
import datetime as dt
from concurrent.futures import ThreadPoolExecutor, as_completed

import numpy as np
import pandas as pd

# ────────────────────────────────────────────────────────────
# 설정
# ────────────────────────────────────────────────────────────
YEARS = 3                 # 베타·변동성·알파 계산에 쓸 기간
MIN_DAYS = 250            # 이보다 데이터가 적으면 통계값 생략
RF = 0.03                 # 무위험 이자율(연) — 알파 계산용
OUT = "data.json"

# 미국 종목 범위. 필요하면 EXTRA_US 에 티커를 더 넣으세요.
EXTRA_US = [
    "SPY", "VOO", "QQQ", "SCHD", "VTI", "VT", "IVV", "DIA", "IWM",
    "SOXX", "SMH", "XLK", "XLF", "XLE", "XLV", "XLY", "XLP", "XLI",
    "TLT", "IEF", "SHY", "GLD", "IAU", "SLV", "JEPI", "JEPQ", "VYM",
    "ARKK", "TQQQ", "BRK-B", "TSM", "ASML", "BABA", "NVO", "SHOP",
]

KR_INDEX = "KS11"          # 코스피
US_INDEX = "^GSPC"         # S&P 500
FX_TICKER = "USDKRW=X"


def log(*a):
    print(*a, flush=True)


def ann_vol(returns):
    if len(returns) < MIN_DAYS:
        return None
    v = float(np.nanstd(returns, ddof=1)) * math.sqrt(252) * 100
    return round(v, 1) if np.isfinite(v) and 0 < v < 300 else None


def beta_alpha(stock_ret, bench_ret):
    """일별 초과수익 회귀 → (beta, 연 alpha %p)"""
    df = pd.concat([stock_ret, bench_ret], axis=1).dropna()
    if len(df) < MIN_DAYS:
        return None, None
    x = df.iloc[:, 1].values
    y = df.iloc[:, 0].values
    vx = np.var(x, ddof=1)
    if vx <= 0:
        return None, None
    b = float(np.cov(y, x, ddof=1)[0, 1] / vx)
    if not np.isfinite(b) or abs(b) > 5:
        return None, None
    rf_d = RF / 252
    a_daily = float(np.mean(y - rf_d) - b * np.mean(x - rf_d))
    a = a_daily * 252 * 100
    if not np.isfinite(a) or abs(a) > 200:
        a = None
    return round(b, 2), (round(a, 1) if a is not None else None)


# ────────────────────────────────────────────────────────────
# 한국
# ────────────────────────────────────────────────────────────
def fetch_korea(start, end):
    import FinanceDataReader as fdr

    log("· KRX 종목 목록 받는 중…")
    listing = fdr.StockListing("KRX")
    listing = listing[listing["Code"].str.len() == 6].copy()
    for c in ("Name", "Market", "Marcap", "Amount", "Close"):
        if c not in listing.columns:
            listing[c] = np.nan
    log(f"  → {len(listing):,}개 종목")

    kospi = fdr.DataReader(KR_INDEX, start, end)["Close"]
    bench = kospi.pct_change().dropna()
    bench.name = "bench"

    fundamentals = {}
    try:
        from pykrx import stock as pk
        day = pk.get_nearest_business_day_in_a_week()
        fu = pk.get_market_fundamental(day, market="ALL")
        fundamentals = fu.to_dict("index")
        log(f"· 밸류에이션 지표 {len(fundamentals):,}건")
    except Exception as e:
        log(f"  (밸류에이션 지표 생략: {e})")

    out = []

    def one(row):
        code = row["Code"]
        try:
            px = fdr.DataReader(code, start, end)["Close"].dropna()
            if len(px) < 60:
                return None
            ret = px.pct_change().dropna()
            ret.name = "r"
            b, a = beta_alpha(ret, bench)
            f = fundamentals.get(code, {})
            rec = {
                "t": code,
                "nk": str(row["Name"]),
                "ne": str(row["Name"]),
                "cls": "kr",
                "price": float(px.iloc[-1]),
                "vol": ann_vol(ret.values),
                "beta": b,
                "al": a,
                "per": round(float(f.get("PER", 0) or 0), 1) or None,
                "pbr": round(float(f.get("PBR", 0) or 0), 2) or None,
                "dy": round(float(f.get("DIV", 0) or 0), 2),
                "cap": float(row["Marcap"] or 0) / 1e12,
                "val": float(row["Amount"] or 0) / 1e8,
            }
            return {k: v for k, v in rec.items() if v is not None}
        except Exception:
            return None

    with ThreadPoolExecutor(max_workers=8) as ex:
        futs = [ex.submit(one, r) for _, r in listing.iterrows()]
        for i, f in enumerate(as_completed(futs)):
            r = f.result()
            if r:
                out.append(r)
            if (i + 1) % 400 == 0:
                log(f"  … {i + 1:,} 처리")

    log(f"· 한국 완료: {len(out):,}개")
    return out, bench


# ────────────────────────────────────────────────────────────
# 미국
# ────────────────────────────────────────────────────────────
def us_tickers():
    import FinanceDataReader as fdr
    tk = set(EXTRA_US)
    for name in ("S&P500", "NASDAQ"):
        try:
            df = fdr.StockListing(name)
            col = "Symbol" if "Symbol" in df.columns else df.columns[0]
            syms = [str(s) for s in df[col].dropna().tolist()]
            if name == "NASDAQ":
                syms = syms[:400]        # 유동성 낮은 종목까지 다 받으면 너무 느립니다
            tk.update(syms)
        except Exception as e:
            log(f"  ({name} 목록 실패: {e})")
    clean = {s.replace(".", "-").strip().upper() for s in tk if s and len(s) <= 6 and s.isascii()}
    return sorted(clean)


def fetch_us(start, end):
    import yfinance as yf

    syms = us_tickers()
    log(f"· 미국 {len(syms):,}개 종목 시세 받는 중…")

    fx = yf.download(FX_TICKER, start=start, end=end, progress=False, auto_adjust=True)["Close"]
    if isinstance(fx, pd.DataFrame):
        fx = fx.iloc[:, 0]
    fx = fx.dropna()
    fx_last = float(fx.iloc[-1])

    spx = yf.download(US_INDEX, start=start, end=end, progress=False, auto_adjust=True)["Close"]
    if isinstance(spx, pd.DataFrame):
        spx = spx.iloc[:, 0]
    bench = spx.pct_change().dropna()
    bench.name = "bench"

    # S&P500 자체의 원화 기준 변동성 (도구의 usVol 기본값으로 씁니다)
    spx_krw = (spx * fx.reindex(spx.index).ffill()).dropna()
    us_vol_krw = ann_vol(spx_krw.pct_change().dropna().values)

    data = yf.download(syms, start=start, end=end, progress=False,
                       auto_adjust=True, group_by="ticker", threads=True)

    out = []
    for s in syms:
        try:
            px = (data[s]["Close"] if isinstance(data.columns, pd.MultiIndex) else data["Close"]).dropna()
            if len(px) < 60:
                continue
            ret = px.pct_change().dropna()
            ret.name = "r"
            b, a = beta_alpha(ret, bench)
            krw = (px * fx.reindex(px.index).ffill()).dropna()
            rec = {
                "t": s,
                "nk": s,
                "ne": s,
                "cls": "us",
                "ccy": "USD",
                "fxu": True,
                "price": round(float(px.iloc[-1]), 2),
                "vol": ann_vol(krw.pct_change().dropna().values),
                "beta": b,
                "al": a,
            }
            out.append({k: v for k, v in rec.items() if v is not None})
        except Exception:
            continue

    # 이름·PER·배당은 별도 조회(실패해도 무시)
    def enrich(rec):
        try:
            info = yf.Ticker(rec["t"]).get_info()
            nm = info.get("shortName") or info.get("longName")
            if nm:
                rec["nk"] = rec["ne"] = str(nm)
            pe = info.get("trailingPE")
            if pe and 0 < pe < 500:
                rec["per"] = round(float(pe), 1)
            pb = info.get("priceToBook")
            if pb and 0 < pb < 100:
                rec["pbr"] = round(float(pb), 2)
            dyv = info.get("dividendYield")
            if dyv is not None:
                rec["dy"] = round(float(dyv) * (100 if dyv < 1 else 1), 2)
            mc = info.get("marketCap")
            if mc:
                rec["cap"] = round(float(mc) / 1e12, 2)
            vol = info.get("averageVolume")
            if vol and rec.get("price"):
                rec["val"] = round(float(vol) * rec["price"] / 1e8, 1)
        except Exception:
            pass
        return rec

    with ThreadPoolExecutor(max_workers=10) as ex:
        out = list(ex.map(enrich, out))

    log(f"· 미국 완료: {len(out):,}개")
    return out, bench, fx, fx_last, us_vol_krw


# ────────────────────────────────────────────────────────────
def main():
    end = dt.date.today()
    start = end - dt.timedelta(days=int(365.25 * YEARS) + 40)
    log(f"뱁새 데이터 수집 · {start} ~ {end}")

    kr, kr_bench = fetch_korea(start, end)
    us, us_bench, fx, fx_last, us_vol_krw = fetch_us(start, end)

    if len(kr) < 500 or len(us) < 100:
        log("!! 받아온 종목이 너무 적습니다. 기존 data.json 을 지키기 위해 중단합니다.")
        sys.exit(1)

    # 자산군 간 상관계수를 실제 데이터로 계산 (원화 투자자 관점)
    settings = {}
    try:
        import yfinance as yf
        gold = yf.download("GC=F", start=start, end=end, progress=False, auto_adjust=True)["Close"]
        if isinstance(gold, pd.DataFrame):
            gold = gold.iloc[:, 0]
        idx = kr_bench.index
        fxr = fx.pct_change()
        us_krw = (us_bench + fxr.reindex(us_bench.index).fillna(0))
        gold_krw = (gold.pct_change() + fxr.reindex(gold.index).fillna(0)).dropna()
        j = pd.concat([kr_bench.rename("kr"),
                       us_krw.rename("us"),
                       gold_krw.rename("mt")], axis=1).dropna()
        if len(j) > MIN_DAYS:
            c = j.corr()
            settings = {
                "mktVol": ann_vol(j["kr"].values),
                "usVol": us_vol_krw or ann_vol(j["us"].values),
                "mtVol": ann_vol(j["mt"].values),
                "rhoKrUs": round(float(c.loc["kr", "us"]), 2),
                "rhoKrMt": round(float(c.loc["kr", "mt"]), 2),
                "rhoUsMt": round(float(c.loc["us", "mt"]), 2),
            }
            log(f"· 상관계수 계산 완료: {settings}")
    except Exception as e:
        log(f"  (상관계수 생략: {e})")

    stocks = kr + us
    popular = [s["t"] for s in sorted(stocks, key=lambda x: -(x.get("val") or 0))[:120]]

    payload = {
        "asOf": end.isoformat(),
        "fx": round(fx_last, 1),
        "settings": settings,
        "popular": popular,
        "count": {"kr": len(kr), "us": len(us)},
        "stocks": stocks,
    }
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, separators=(",", ":"))
    mb = len(json.dumps(payload, ensure_ascii=False)) / 1e6
    log(f"✓ {OUT} 저장 완료 — {len(stocks):,}종목, {mb:.1f}MB, 환율 {fx_last:,.1f}")


if __name__ == "__main__":
    main()
