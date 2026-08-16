// ================= 뱁새 v13 — 공시·수급 =================
// 내부자 거래 피드(90일, 필터)와 국민연금 대량보유 변동.
// 원칙: 신호가 아니라 사실. 맥락이 다양하다는 것을 화면에 명시합니다.
import React, { useState, useEffect, useMemo } from "react";
import { C, FONT, RAD, HAIR } from "./tokens.js";
import { Ic } from "./icons.jsx";
import { Bird, store, SECTORS, SEC, KEY_SLOTS, KEY_SLOT } from "./detail.jsx";

const CREDIT = "이성진, INSEAD MBA 26J · Jack (Sung Jin) Lee, INSEAD MBA 26J";
const fmtD = (d) => d && d.length === 8 ? `${d.slice(4, 6)}.${d.slice(6, 8)}` : d || "—";
const fmtQ = (q) => (q >= 0 ? "+" : "−") + Math.abs(q).toLocaleString() + "주";

const Card = ({ children, style = {} }) => (
  <div style={{ background: "#fff", border: HAIR, borderRadius: RAD.card, padding: 18, ...style }}>{children}</div>
);
const H = ({ num, main, sub }) => (
  <div>
    <div style={{ display: "flex", alignItems: "baseline", gap: 8 }}>
      {num && <span style={{ fontSize: 11, fontWeight: 800, color: C.apricotDeep, letterSpacing: "0.1em" }}>{num}</span>}
      <span style={{ fontSize: 15.5, fontWeight: 800, color: C.ink, letterSpacing: "-0.01em" }}>{main}</span>
    </div>
    {sub && <div style={{ fontSize: 10.5, color: C.faint, marginTop: 3 }}>{sub}</div>}
  </div>
);
const Sub = ({ children, style = {} }) => <div style={{ fontSize: 12, color: C.sub, lineHeight: 1.6, ...style }}>{children}</div>;
const ChipBtn = ({ on, onClick, children }) => (
  <button onClick={onClick} style={{ border: on ? "1.5px solid " + C.ink : "1.5px solid " + C.line, background: on ? C.ink : "#fff", color: on ? "#fff" : C.sub, borderRadius: 999, padding: "5px 11px", fontSize: 11.5, fontWeight: 800, cursor: "pointer", fontFamily: FONT }}>{children}</button>
);

function MissingData({ onRetry }) {
  return (
    <div style={{ maxWidth: 560, margin: "0 auto", padding: "44px 16px", textAlign: "center", fontFamily: FONT, color: C.ink }}>
      <Bird mood="search" size={80} />
      <div style={{ fontSize: 19, fontWeight: 800, marginTop: 14 }}>공시 데이터가 아직 없어요</div>
      <Card style={{ marginTop: 16, textAlign: "left" }}>
        <Sub>GitHub 저장소 → <b style={{ color: C.ink }}>Actions</b> → <b style={{ color: C.ink }}>시세 데이터 갱신</b> → <b style={{ color: C.ink }}>Run workflow</b> 실행 후 새로고침하면 disc.json이 만들어져요. 첫 실행은 90일치 공시를 채우느라 평소보다 오래 걸려요.</Sub>
      </Card>
      <button onClick={onRetry} style={{ marginTop: 14, background: C.blue, color: "#fff", border: "none", borderRadius: RAD.btn, padding: "12px 22px", fontSize: 13.5, fontWeight: 800, cursor: "pointer", fontFamily: FONT }}>다시 확인</button>
    </div>
  );
}

export function DiscBody({ data, heldMap, onOpenCompany }) {
  const [dir, setDir] = useState("all");
  const [heldOnly, setHeldOnly] = useState(false);
  const [bigOnly, setBigOnly] = useState(false);
  const [q, setQ] = useState("");
  const [limit, setLimit] = useState(40);

  const [secF, setSecF] = useState("all");
  const secKeys = useMemo(() => {
    const cnt = {};
    (data.insider || []).forEach((x) => { const k = x.s || "etc"; cnt[k] = (cnt[k] || 0) + 1; });
    return Object.entries(cnt).sort((a, b) => b[1] - a[1]).map(([k]) => k);
  }, [data]);
  const rows = useMemo(() => {
    let r = data.insider || [];
    if (secF !== "all") r = r.filter((x) => (x.s || "etc") === secF);
    if (dir === "buy") r = r.filter((x) => x.q > 0);
    if (dir === "sell") r = r.filter((x) => x.q < 0);
    if (heldOnly) r = r.filter((x) => heldMap[x.t]);
    if (bigOnly) r = r.filter((x) => (x.cap || 0) >= 1);
    if (q.trim()) { const s = q.trim().toLowerCase(); r = r.filter((x) => x.nk.toLowerCase().includes(s) || x.t.includes(s)); }
    return r;
  }, [data, dir, heldOnly, bigOnly, q, secF]);

  // 업종별 매수·매도 건수 (필터와 무관한 90일 전체 집계)
  const [openSec, setOpenSec] = useState(null);
  const secAgg = useMemo(() => {
    const m = {};
    (data.insider || []).forEach((x) => {
      const k = x.s || "etc";
      m[k] = m[k] || { buy: 0, sell: 0 };
      x.q > 0 ? m[k].buy++ : m[k].sell++;
    });
    return Object.entries(m).map(([k, v]) => ({ k, ko: SEC(k).ko, ...v, tot: v.buy + v.sell }))
      .sort((a, b) => b.tot - a.tot).slice(0, 14);
  }, [data]);
  const aggMax = Math.max(...secAgg.map((r) => Math.max(r.buy, r.sell)), 1);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
      <Card>
        <H num="01" main="내부자 거래" sub={`임원·주요주주 소유상황 보고 · 최근 90일 · ${(data.insider || []).length.toLocaleString()}건`} />
        <Sub style={{ marginTop: 7, fontSize: 11.5 }}>
          내부자 매매는 <b style={{ color: C.ink }}>신호가 아니라 사실</b>이에요. 스톡옵션 행사, 상속, 담보 제공, 세금 납부 등 맥락이 다양해서, 매수가 곧 호재도 매도가 곧 악재도 아니에요.
        </Sub>
        <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginTop: 12, alignItems: "center" }}>
          {[["all", "전체"], ["buy", "매수만"], ["sell", "매도만"]].map(([v, ko]) => (
            <ChipBtn key={v} on={dir === v} onClick={() => setDir(v)}>{ko}</ChipBtn>
          ))}
          <ChipBtn on={bigOnly} onClick={() => setBigOnly(!bigOnly)}>1조 이상</ChipBtn>
          <select value={secF} onChange={(e) => setSecF(e.target.value)}
            style={{ border: "1.5px solid " + (secF !== "all" ? C.ink : C.line), borderRadius: 999, padding: "5px 10px", fontSize: 11.5, fontWeight: 700, color: secF !== "all" ? C.ink : C.sub, fontFamily: FONT, background: "#fff" }}>
            <option value="all">전체 업종</option>
            {secKeys.map((k) => <option key={k} value={k}>{SEC(k).ko}</option>)}
          </select>
          <ChipBtn on={heldOnly} onClick={() => setHeldOnly(!heldOnly)}>보유만</ChipBtn>
          <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="회사 검색"
            style={{ border: "1.5px solid " + C.line, borderRadius: 999, padding: "6px 12px", fontSize: 11.5, fontFamily: FONT, color: C.ink, outline: "none", width: 120 }} />
        </div>

        <div style={{ marginTop: 8 }}>
          {rows.slice(0, limit).map((x) => (
            <div key={x.rc} style={{ display: "flex", alignItems: "center", gap: 10, padding: "10px 2px", borderBottom: "1px solid " + C.line }}>
              <span style={{ width: 40, fontSize: 10.5, color: C.faint, flexShrink: 0, fontVariantNumeric: "tabular-nums" }}>{fmtD(x.d)}</span>
              <span style={{ width: 8, height: 8, borderRadius: 999, background: SEC(x.s).color, flexShrink: 0 }} />
              <span style={{ flex: 1, minWidth: 0 }}>
                <button onClick={() => onOpenCompany && onOpenCompany(x.t)} style={{ background: "none", border: "none", padding: 0, cursor: "pointer", fontFamily: FONT, fontSize: 13, fontWeight: 800, color: C.ink, textAlign: "left" }}>{x.nk}</button>
                {heldMap[x.t] && <span style={{ marginLeft: 6, fontSize: 9, fontWeight: 800, color: C.apricotDeep, background: C.apricotSoft, borderRadius: 999, padding: "2px 6px" }}>보유</span>}
                <span style={{ display: "block", fontSize: 10.5, color: C.faint }}>{x.nm}{x.pos ? ` · ${x.pos}` : ""}</span>
              </span>
              <span style={{ textAlign: "right", flexShrink: 0 }}>
                <span style={{ display: "block", fontSize: 12.5, fontWeight: 800, color: x.q > 0 ? C.up : C.down, fontVariantNumeric: "tabular-nums" }}>{fmtQ(x.q)}</span>
                <span style={{ display: "block", fontSize: 10, color: C.sub }}>추정 {x.amt != null ? x.amt.toLocaleString() + "억" : "—"}{x.r != null ? ` · 보유 ${x.r}%` : ""}</span>
              </span>
            </div>
          ))}
          {rows.length === 0 && <Sub style={{ padding: "16px 2px" }}>조건에 맞는 보고가 없어요.</Sub>}
          {rows.length > limit && (
            <button onClick={() => setLimit(limit + 40)} style={{ display: "block", width: "100%", background: "none", border: "none", color: C.blue, fontSize: 12.5, fontWeight: 800, padding: "12px", cursor: "pointer", fontFamily: FONT }}>더 보기 ({(rows.length - limit).toLocaleString()}건 남음)</button>
          )}
        </div>
        <Sub style={{ fontSize: 10, color: C.faint, marginTop: 8 }}>금액은 현재 주가 기준 추정치예요 (보고 당시 단가와 다를 수 있어요) · 증감이 0인 단순 보고는 제외</Sub>
      </Card>

      <div className="cgrid2" style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
        <Card>
          <H num="02" main="업종별 보고 건수" sub="최근 90일 · 매수·매도 보고 수" />
          <Sub style={{ marginTop: 5, fontSize: 10.5 }}>업종을 누르면 그 업종에서 활발했던 회사가 펼쳐져요.</Sub>
          <div style={{ display: "flex", flexDirection: "column", gap: 6, marginTop: 10 }}>
            {secAgg.map((r) => (
              <div key={r.k}>
              <button onClick={() => setOpenSec(openSec === r.k ? null : r.k)}
                style={{ display: "flex", alignItems: "center", gap: 8, width: "100%", background: openSec === r.k ? C.bg : "none", border: "none", borderRadius: 7, padding: "3px 4px", cursor: "pointer", fontFamily: FONT }}>
                <span style={{ width: 88, fontSize: 11, fontWeight: 700, color: C.ink, flexShrink: 0, textAlign: "right" }}>{r.ko}</span>
                <svg viewBox="0 0 200 14" style={{ flex: 1, height: 14 }}>
                  <line x1="100" y1="0" x2="100" y2="14" stroke={C.line} strokeWidth="1" />
                  <rect x={100 - (r.sell / aggMax) * 94} y="2.5" width={Math.max((r.sell / aggMax) * 94, r.sell ? 1.5 : 0)} height="9" rx="2.5" fill={C.down} opacity="0.8" />
                  <rect x="100" y="2.5" width={Math.max((r.buy / aggMax) * 94, r.buy ? 1.5 : 0)} height="9" rx="2.5" fill={C.up} opacity="0.8" />
                </svg>
                <span style={{ flexShrink: 0, whiteSpace: "nowrap", fontSize: 10, color: C.faint, fontVariantNumeric: "tabular-nums", textAlign: "right", minWidth: 86 }}>
                  <b style={{ color: C.down }}>{r.sell}</b> 매도 · <b style={{ color: C.up }}>{r.buy}</b> 매수
                </span>
              </button>
              {openSec === r.k && (
                <div style={{ margin: "4px 0 6px 20px", borderLeft: "2px solid " + C.line, paddingLeft: 12 }}>
                  {(() => {
                    const by = {};
                    (data.insider || []).filter((x) => (x.s || "etc") === r.k).forEach((x) => {
                      const b = by[x.t] = by[x.t] || { t: x.t, nk: x.nk, buy: 0, sell: 0, amtB: 0, amtS: 0 };
                      if (x.q > 0) { b.buy++; b.amtB += x.amt || 0; } else { b.sell++; b.amtS += x.amt || 0; }
                    });
                    return Object.values(by).sort((a, b) => (b.buy + b.sell) - (a.buy + a.sell)).slice(0, 10).map((co) => (
                      <div key={co.t} style={{ display: "flex", alignItems: "center", gap: 8, padding: "5px 0", borderBottom: "1px solid " + C.line }}>
                        <button onClick={() => onOpenCompany && onOpenCompany(co.t)} style={{ flex: 1, background: "none", border: "none", padding: 0, cursor: "pointer", fontFamily: FONT, fontSize: 11.5, fontWeight: 800, color: C.ink, textAlign: "left" }}>{co.nk}</button>
                        <span style={{ whiteSpace: "nowrap", fontSize: 10, color: C.faint, fontVariantNumeric: "tabular-nums" }}>
                          {co.buy > 0 && <span style={{ color: C.up }}>매수 {co.buy}건 {co.amtB >= 1 ? Math.round(co.amtB).toLocaleString() + "억" : ""}</span>}
                          {co.buy > 0 && co.sell > 0 && " · "}
                          {co.sell > 0 && <span style={{ color: C.down }}>매도 {co.sell}건 {co.amtS >= 1 ? Math.round(co.amtS).toLocaleString() + "억" : ""}</span>}
                        </span>
                      </div>
                    ));
                  })()}
                </div>
              )}
              </div>
            ))}
          </div>
          <Sub style={{ fontSize: 10, color: C.faint, marginTop: 8 }}>건수 기준이라 금액 규모와는 달라요 · 집계는 필터와 무관한 90일 전체</Sub>
        </Card>

        <Card>
          <H num="03" main="국민연금 보유 변동" sub={`5% 대량보유 보고 기준 · 최근 90일 · ${(data.nps || []).length}건`} />
          <div style={{ marginTop: 8 }}>
            {(data.nps || []).slice(0, 14).map((x, i) => (
              <div key={i} style={{ display: "flex", alignItems: "center", gap: 10, padding: "9px 2px", borderBottom: "1px solid " + C.line }}>
                <span style={{ width: 40, fontSize: 10.5, color: C.faint, flexShrink: 0, fontVariantNumeric: "tabular-nums" }}>{fmtD(x.d)}</span>
                <button onClick={() => onOpenCompany && onOpenCompany(x.t)} style={{ flex: 1, background: "none", border: "none", padding: 0, cursor: "pointer", fontFamily: FONT, fontSize: 12.5, fontWeight: 800, color: C.ink, textAlign: "left" }}>
                  {x.nk}{heldMap[x.t] && <span style={{ marginLeft: 6, fontSize: 9, fontWeight: 800, color: C.apricotDeep, background: C.apricotSoft, borderRadius: 999, padding: "2px 6px" }}>보유</span>}
                </button>
                <span style={{ textAlign: "right", flexShrink: 0, fontSize: 12, fontWeight: 800, color: C.ink, fontVariantNumeric: "tabular-nums" }}>
                  {x.rt != null ? x.rt + "%" : "—"}
                  {x.chg != null && x.chg !== 0 && <span style={{ marginLeft: 5, fontSize: 10.5, color: x.chg > 0 ? C.up : C.down }}>{x.chg > 0 ? "+" : ""}{x.chg}%p</span>}
                </span>
              </div>
            ))}
            {(data.nps || []).length === 0 && <Sub style={{ padding: "14px 2px" }}>최근 90일 내 국민연금 보고가 없어요.</Sub>}
          </div>
          <Sub style={{ fontSize: 10, color: C.faint, marginTop: 8 }}>5% 이상 보유·1%p 이상 변동 같은 공시 요건을 넘을 때만 보고돼요 — 실시간 보유 지도가 아니에요.</Sub>
        </Card>
      </div>

      <div style={{ fontSize: 10.5, color: C.faint, textAlign: "center", lineHeight: 1.7, padding: "6px 0 20px" }}>
        뱁새는 수익률을 약속하지 않아요. 지금 가격에 어떤 가정이 담겨 있는지 읽도록 돕는 교육용 도구이며,<br />투자 자문이 아니고 모든 판단과 책임은 본인에게 있습니다.<br />{CREDIT}
      </div>
    </div>
  );
}

export default function DiscApp({ onOpenCompany }) {
  const [state, setState] = useState({ st: "loading" });
  const [heldMap, setHeldMap] = useState({});
  const [tries, setTries] = useState(0);

  useEffect(() => { (async () => {
    setState({ st: "loading" });
    try {
      const r = await fetch("./disc.json", { cache: "no-store" });
      if (!r.ok) throw new Error("HTTP " + r.status);
      const d = await r.json();
      if (!d || !Array.isArray(d.insider)) throw new Error("bad");
      setState({ st: "ready", data: d });
    } catch (e) { setState({ st: "missing" }); }
  })(); }, [tries]);

  useEffect(() => { (async () => {
    try {
      const raw = await store.get(KEY_SLOTS); const slots = raw ? JSON.parse(raw) : [];
      const map = {};
      for (const meta of (Array.isArray(slots) ? slots : []).slice(0, 20)) {
        try {
          const praw = await store.get(KEY_SLOT(meta.id)); if (!praw) continue;
          const hs = JSON.parse(praw).holdings || [];
          hs.forEach((h) => { if (h.t) map[h.t] = true; });
        } catch (e) {}
      }
      setHeldMap(map);
    } catch (e) {}
  })(); }, []);

  if (state.st === "loading") return (
    <div style={{ minHeight: "50vh", display: "flex", alignItems: "center", justifyContent: "center", fontFamily: FONT }}>
      <div style={{ textAlign: "center" }}><Bird mood="search" size={64} /><div style={{ fontSize: 12.5, color: C.sub, marginTop: 8 }}>공시 데이터를 불러오는 중…</div></div>
    </div>
  );
  if (state.st === "missing") return <MissingData onRetry={() => setTries(tries + 1)} />;

  return (
    <div className="cwrap" style={{ maxWidth: 1140, margin: "0 auto", padding: "14px 16px 40px", fontFamily: FONT, color: C.ink }}>
      <style>{`@media (max-width: 880px) { .cgrid2 { grid-template-columns: 1fr !important } }`}</style>
      <div style={{ display: "flex", justifyContent: "flex-end", marginBottom: 10 }}>
        <span style={{ fontSize: 10.5, color: C.faint }}>기준 {state.data.asOf} · 매일 자동 갱신</span>
      </div>
      <DiscBody data={state.data} heldMap={heldMap} onOpenCompany={onOpenCompany} />
    </div>
  );
}
