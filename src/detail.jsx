import React, { useState, useEffect, useRef, useMemo } from "react";

/*
  뱁새 (Baepsae) — 포트폴리오 도구 v11 (AI 없이 동작 · 한국+미국+금은)
  Toss-like friendly fintech for Korean retail investors. Mascot: 뱁이 the long-tailed tit.
  "황새 말고, 내 걸음으로" — invest within your own risk budget, at your own pace.
  - Free-text voyage questionnaire scored by Claude API (robust, with preset fallback)
  - Long-only KRX builder: sliders, 4 risk rails, health score, rich stock cards
  - Insights: risk contribution, goal gap, projection fan, dividends, benchmark+robo
  - Educational only. Data are dated, approximate, editable. Not investment advice.
*/

// ================= Palette: tokens.js (v11 디자인 시스템) =================
import { C, FONT, SERIF, RAD, HAIR } from "./tokens.js";
import { Ic } from "./icons.jsx";
import { renderPortfolioCard, saveCard, shareCard } from "./sharecard.js";

function makeCardData(holdings, stocksById, cashMw, score, lang) {
  const sums = { kr: 0, us: 0, mt: 0 };
  let inv = 0;
  holdings.forEach((h) => {
    const st = stocksById[h.t]; const mw = h.mw || 0; inv += mw;
    if (st && st.cls === "us") sums.us += mw;
    else if (st && st.cls === "metal") sums.mt += mw;
    else if (st && st.cls === "bond") sums.bd = (sums.bd || 0) + mw;
    else sums.kr += mw;
  });
  const cash = Math.max(cashMw || 0, 0);
  const tot = inv + cash || 1;
  const buckets = [
    { ko: lang === "ko" ? "국내 주식" : "KR stocks", pct: sums.kr / tot * 100, color: "#5B7DB1" },
    { ko: lang === "ko" ? "미국 주식" : "US stocks", pct: sums.us / tot * 100, color: "#8A6FB8" },
    { ko: lang === "ko" ? "금·은" : "Gold/Silver", pct: sums.mt / tot * 100, color: "#C9A227" },
    { ko: lang === "ko" ? "채권" : "Bonds", pct: (sums.bd || 0) / tot * 100, color: "#4E8577" },
    { ko: lang === "ko" ? "현금" : "Cash", pct: cash / tot * 100, color: "#8B95A8" },
  ].filter((b) => b.pct >= 0.5);
  const top = [...holdings].sort((a, b) => (b.mw || 0) - (a.mw || 0)).slice(0, 3)
    .map((h) => ({ nk: (stocksById[h.t] && stocksById[h.t].nk) || h.t, pct: (h.mw || 0) / tot * 100 }));
  return { score, buckets, top, dateStr: new Date().toISOString().slice(0, 10) };
}

function ShareCardModal({ card, onClose, lang }) {
  const [shared, setShared] = useState(false);
  if (!card) return null;
  const canShare = typeof navigator !== "undefined" && !!navigator.share;
  return (
    <div onClick={onClose} style={{ position: "fixed", inset: 0, background: "rgba(28,43,69,0.5)", zIndex: 95, display: "flex", alignItems: "center", justifyContent: "center", padding: 16 }}>
      <div onClick={(e) => e.stopPropagation()} style={{ background: "#fff", borderRadius: 14, padding: 16, maxWidth: 380, width: "100%", fontFamily: FONT, maxHeight: "92vh", overflowY: "auto" }}>
        <div style={{ fontSize: 14, fontWeight: 800, color: C.ink }}>{lang === "ko" ? "이렇게 저장돼요" : "Card preview"}</div>
        <img src={card.url} alt="portfolio card" style={{ width: "100%", borderRadius: 10, marginTop: 10, border: "1px solid " + C.line, display: "block" }} />
        <div style={{ display: "grid", gridTemplateColumns: canShare ? "1fr 1fr" : "1fr", gap: 8, marginTop: 12 }}>
          <Btn kind="dark" onClick={() => saveCard(card.cv, card.dateStr)}>{lang === "ko" ? "이미지 저장" : "Save image"}</Btn>
          {canShare && <Btn onClick={async () => { const ok = await shareCard(card.cv, card.dateStr); if (ok) { setShared(true); setTimeout(() => setShared(false), 1500); } }}>{shared ? (lang === "ko" ? "공유됨!" : "Shared!") : (lang === "ko" ? "공유하기" : "Share")}</Btn>}
        </div>
        <Btn kind="ghost" onClick={onClose} style={{ width: "100%", marginTop: 8 }}>{lang === "ko" ? "닫기" : "Close"}</Btn>
      </div>
    </div>
  );
}
const DATA_AS_OF = "2026-01";

// ================= Storage adapter (artifact / browser / memory) =================
const SCHEMA = 10;
const KEY_SLOTS = "baepsae_v10_slots";
const KEY_SLOT = (id) => "baepsae_v10_slot_" + id;
const KEY_ONB = "baepsae_v9_seen";
const store = (() => {
  const ws = typeof window !== "undefined" && window.storage && typeof window.storage.get === "function" ? window.storage : null;
  let ls = null;
  try {
    if (typeof localStorage !== "undefined") { localStorage.setItem("__bt", "1"); localStorage.removeItem("__bt"); ls = localStorage; }
  } catch (e) { ls = null; }
  const mem = {};
  return {
    kind: ws ? "artifact" : ls ? "browser" : "memory",
    async get(k) {
      if (ws) { try { const r = await ws.get(k); if (r && r.value != null) return r.value; } catch (e) {} }
      if (ls) { try { const v = ls.getItem(k); if (v != null) return v; } catch (e) {} }
      return mem[k] != null ? mem[k] : null;
    },
    async set(k, v) {
      mem[k] = v;
      if (ws) { try { await ws.set(k, v); return true; } catch (e) {} }
      if (ls) { try { ls.setItem(k, v); return true; } catch (e) {} }
      return false;
    },
    async del(k) {
      delete mem[k];
      if (ws) { try { await ws.delete(k); } catch (e) {} }
      if (ls) { try { ls.removeItem(k); } catch (e) {} }
    },
  };
})();
const MAX_SLOTS = 20;
async function readSlots() {
  try { const raw = await store.get(KEY_SLOTS); const a = raw ? JSON.parse(raw) : []; return Array.isArray(a) ? a : []; } catch (e) { return []; }
}
async function writeSlots(list) { try { await store.set(KEY_SLOTS, JSON.stringify(list.slice(0, MAX_SLOTS))); } catch (e) {} }

// ================= Live data loader =================
// The daily GitHub Action writes data.json next to this file. Absent (local double-click),
// the tool falls back to the snapshot embedded below.
async function loadLiveData() {
  try {
    const res = await fetch("./data.json", { cache: "no-store" });
    if (!res.ok) throw new Error("no data.json");
    const j = await res.json();
    if (!j || !Array.isArray(j.stocks)) throw new Error("bad shape");
    return { asOf: j.asOf || null, fx: typeof j.fx === "number" ? j.fx : null, settings: (j.settings && typeof j.settings === "object") ? j.settings : null, stocks: j.stocks, popular: Array.isArray(j.popular) ? j.popular : [] };
  } catch (e) { return null; }
}
function mergeStocks(base, live) {
  if (!live) return base;
  // 미국 티커는 표기가 갈려요(BRK.B / BRK-B). 점·하이픈을 무시하고 맞춰봅니다.
  const norm = (x) => String(x || "").toUpperCase().replace(/[.\-]/g, "");
  const byT = Object.fromEntries(base.map((s) => [s.t, s]));
  const byNorm = {};
  base.forEach((s) => { byNorm[norm(s.t)] = s; });
  const out = [];
  live.forEach((L) => {
    const b = byT[L.t] || byNorm[norm(L.t)];
    if (b) {
      out.push({ ...b, price: L.price != null ? L.price : b.price, beta: L.beta != null ? L.beta : b.beta,
        vol: L.vol != null ? L.vol : b.vol, per: L.per != null ? L.per : b.per, pbr: L.pbr != null ? L.pbr : b.pbr,
        dy: L.dy != null ? L.dy : b.dy, al: L.al != null ? L.al : b.al,
        sh: L.sh, mdd: L.mdd, hit: L.hit, mom: L.mom, cap: L.cap, val: L.val,
        pz: L.pz, vz: L.vz, mz: L.mz, qz: L.qz,
        x: { ...(b.x || {}), roe: L.roe != null ? L.roe : (b.x || {}).roe, debt: L.debt != null ? L.debt : (b.x || {}).debt,
             opm: L.opm != null ? L.opm : (b.x || {}).opm, g3: L.g3 != null ? L.g3 : (b.x || {}).g3,
             frn: L.frn != null ? L.frn : (b.x || {}).frn, mcap: L.cap != null ? L.cap : (b.x || {}).mcap,
             lo: L.lo != null ? L.lo : (b.x || {}).lo, hi: L.hi != null ? L.hi : (b.x || {}).hi },
        live: true });
      delete byT[b.t]; delete byNorm[norm(b.t)];
    } else {
      out.push({ t: L.t, nk: L.nk || L.t, ne: L.ne || L.t, s: L.s || "index", cls: L.cls || "kr",
        ccy: L.ccy, fxu: !!L.fxu, price: L.price || 0, beta: L.beta != null ? L.beta : 1,
        vol: L.vol != null ? L.vol : 30, per: L.per || 0, pbr: L.pbr || 0, dy: L.dy || 0, al: L.al || 0,
        cap: L.cap || 0, val: L.val || 0, sh: L.sh, mdd: L.mdd, hit: L.hit, mom: L.mom,
        pz: L.pz, vz: L.vz, mz: L.mz, qz: L.qz, live: true, auto: true,
        x: { dk: L.dk, de: L.de, roe: L.roe, debt: L.debt, opm: L.opm, g3: L.g3, frn: L.frn,
             mcap: L.cap, lo: L.lo, hi: L.hi } });
    }
  });
  Object.values(byT).forEach((b) => out.push(b));
  return out;
}


// ================= Sectors =================
// ================= Sectors (KRX 업종분류 기반) =================
const SECTORS = {
  bond: { ko: "채권", en: "Bonds", color: "#4E8577" },
  semi:       { ko: "반도체", en: "Semiconductors", color: "#2C4C7C" },
  elec:       { ko: "전자·전기장비", en: "Electronics", color: "#2E86DE" },
  battery:    { ko: "2차전지", en: "Battery", color: "#11A9A0" },
  auto:       { ko: "자동차", en: "Autos", color: "#5E6AD2" },
  ship:       { ko: "조선", en: "Shipbuilding", color: "#2C5282" },
  defense:    { ko: "방산·항공우주", en: "Defense/Aero", color: "#1A365D" },
  machine:    { ko: "기계·장비", en: "Machinery", color: "#4A5568" },
  steel:      { ko: "철강·금속", en: "Steel/Metals", color: "#718096" },
  chem:       { ko: "화학", en: "Chemicals", color: "#DD6B20" },
  energy:     { ko: "정유·에너지", en: "Oil & Gas", color: "#9C4221" },
  utility:    { ko: "전기·가스·환경", en: "Utilities", color: "#975A16" },
  bio:        { ko: "제약·바이오", en: "Pharma/Bio", color: "#0E9F6E" },
  health:     { ko: "의료·헬스케어", en: "Healthcare", color: "#38A169" },
  platform:   { ko: "인터넷·소프트웨어", en: "Internet/Software", color: "#0BA5C9" },
  game:       { ko: "게임", en: "Games", color: "#B83280" },
  media:      { ko: "미디어·엔터", en: "Media/Ent", color: "#D53F8C" },
  telecom:    { ko: "통신", en: "Telecom", color: "#2F855A" },
  bank:       { ko: "은행", en: "Banks", color: "#B7791F" },
  insure:     { ko: "보험", en: "Insurance", color: "#8B6914" },
  broker:     { ko: "증권·금융서비스", en: "Brokers/Fin", color: "#A16207" },
  holding:    { ko: "지주회사", en: "Holdings", color: "#52525B" },
  build:      { ko: "건설·건자재", en: "Construction", color: "#78716C" },
  realestate: { ko: "부동산", en: "Real Estate", color: "#A8A29E" },
  retail:     { ko: "유통·소비재", en: "Retail", color: "#EA580C" },
  food:       { ko: "식음료·담배", en: "Food/Bev", color: "#CA8A04" },
  cosmetic:   { ko: "화장품·생활용품", en: "Cosmetics/HH", color: "#DB2777" },
  textile:    { ko: "섬유·의류", en: "Apparel", color: "#9333EA" },
  transport:  { ko: "운송·물류", en: "Transport", color: "#0891B2" },
  edu:        { ko: "교육", en: "Education", color: "#7C3AED" },
  paper:      { ko: "종이·목재·인쇄", en: "Paper/Wood", color: "#92400E" },
  hotel:      { ko: "호텔·레저·외식", en: "Hotels/Leisure", color: "#E11D48" },
  index:      { ko: "지수 ETF", en: "Index ETF", color: "#059669" },
  metal:      { ko: "금·은", en: "Gold/Silver", color: "#E8B54A" },
  etc:        { ko: "기타", en: "Other", color: "#94A3B8" },
};

// ================= Asset classes =================
const CLASSES = {
  kr:    { ko: "한국 주식", en: "KR stocks", color: "#2C4C7C", flag: "KR", bench: "코스피" },
  us:    { ko: "미국 주식", en: "US stocks", color: "#5E6AD2", flag: "US", bench: "S&P 500" },
  metal: { ko: "금·은", en: "Gold/Silver", color: "#E8B54A", flag: "AU", bench: "금 가격" },
  bond:  { ko: "채권", en: "Bonds", color: "#4E8577", flag: "BD", bench: "국고채" },
};

const SEC = (k) => SECTORS[k] || { ko: "기타", en: "Other", color: "#94A3B8" };

// Sector lens: 이 업종을 볼 때 무엇을 먼저 봐야 하는지
const LENS = {
  semi:     { ko: "PER보다 사이클 위치가 중요해요. 이익 바닥일 땐 PER이 높아 '비싸 보이는 착시', 고점일 땐 '싸 보이는 착시'가 생겨요. PBR과 업황을 함께 보세요.", en: "Cycle position beats PER. Trough earnings make PER look expensive; peak earnings make it look cheap. Watch PBR and the cycle." },
  elec:     { ko: "누구에게 파는지가 핵심이에요. 대형 고객 한 곳에 매출이 몰려 있으면, 그 고객의 투자 계획이 곧 이 회사의 실적이 돼요.", en: "Who they sell to is the whole story. If revenue concentrates in one big customer, that customer's capex plan is this company's earnings." },
  battery:  { ko: "성장 투자기라 이익이 눌려 PER이 왜곡돼요. 매출 성장률·수주(고객사)·자본 조달 여력을 먼저 보세요.", en: "Heavy growth capex distorts PER. Look at revenue growth, orders, and funding capacity first." },
  auto:     { ko: "낮은 PER이 기본인 경기순환주예요. '싸다'가 아니라 '사이클 어디쯤인가'를 물어보세요. 배당과 주주환원도 핵심.", en: "Low PER is normal for this cyclical. Ask 'where in the cycle', not 'is it cheap'." },
  ship:     { ko: "수주잔고가 미래 매출이에요. PER보다 수주잔고÷연매출(몇 년치 일감인지)과 선가 추이를 보세요.", en: "Order backlog is future revenue. Backlog ÷ annual sales and newbuild prices beat PER." },
  defense:  { ko: "수주잔고와 정부 예산이 실적을 결정해요. 수출 계약 한 건이 몇 년치 실적을 바꾸는 구조라 뉴스에 크게 반응해요.", en: "Backlog and government budgets drive earnings; a single export deal can reset years of results." },
  machine:  { ko: "전형적인 경기순환주예요. 고객 산업의 설비투자 사이클을 먼저 보고, 그다음에 밸류에이션을 보세요.", en: "A classic cyclical — read the customer industry's capex cycle before the multiple." },
  steel:    { ko: "사이클 저점에선 PBR로, 고점에선 조심스럽게. 중국 수급이 가격을 흔들어요.", en: "Use PBR at cycle lows, be careful at peaks. China supply-demand moves prices." },
  chem:     { ko: "정제마진·스프레드가 이익을 좌우하는 사이클 산업이에요. 현재 이익보다 스프레드 방향을 보세요.", en: "Spreads drive earnings. Watch spread direction, not current profits." },
  energy:   { ko: "유가가 실적의 대부분을 결정해요. 인플레이션 국면에서 주식 포트폴리오의 완충재 역할을 하기도 해요.", en: "Oil prices drive earnings; can cushion an equity portfolio in inflationary stretches." },
  utility:  { ko: "요금은 정부가 정해요. 실적보다 정책·규제 방향이 주가를 움직여요.", en: "Tariffs are set by government. Policy moves the stock more than earnings." },
  bio:      { ko: "이익이 없어 PER이 무의미한 경우가 많아요. 파이프라인(임상 단계)·기술수출 계약이 가치의 대부분이에요. 변동성이 큰 이유죠.", en: "PER is often meaningless. Pipeline stage and licensing deals carry the value — hence the volatility." },
  health:   { ko: "정책·보험 수가가 실적을 좌우해요. 성장은 완만하지만 경기 방어력이 있는 편이에요.", en: "Policy and reimbursement rates drive results; slower growth but defensive." },
  platform: { ko: "성장률과 이익률의 조합을 보세요. 성장이 꺾이면 멀티플이 급격히 낮아지는 구조예요.", en: "Watch the growth × margin combo. When growth stalls, the multiple derates fast." },
  game:     { ko: "히트작 의존 산업이라 이익 변동이 커요. 신작 파이프라인과 기존작의 수명이 핵심.", en: "Hit-driven earnings swing hard. New pipeline and longevity of live titles are key." },
  media:    { ko: "IP의 힘과 제작비 부담이 줄다리기해요. 구독자 증가율과 편당 수익성을 함께 보세요.", en: "IP strength versus production cost. Watch subscriber growth alongside per-title economics." },
  telecom:  { ko: "성장보다 배당이 본질인 준(準)유틸리티예요. 배당수익률과 배당의 지속가능성을 보세요.", en: "A quasi-utility: dividends, not growth. Check yield and sustainability." },
  bank:     { ko: "PBR과 ROE가 핵심이에요. 자본이 곧 원료인 산업이라 '자본 대비 얼마나 버는가'가 가치를 결정해요. 금리와 연체율도 함께 보세요.", en: "PBR and ROE rule. Capital is the raw material, so earnings on book equity set the value." },
  insure:   { ko: "보험은 '받은 보험료를 굴려서 버는' 구조예요. 금리 방향과 손해율(들어온 보험료 대비 나간 보험금)을 보세요.", en: "Insurers earn on the float. Watch rates and the loss ratio." },
  broker:   { ko: "거래대금과 시장 분위기에 실적이 직결돼요. 강세장에 잘 벌고 약세장에 급격히 줄어드는 구조예요.", en: "Earnings track trading volumes and sentiment — strong in bull markets, thin in bear ones." },
  holding:  { ko: "지주사는 보유 지분 가치 대비 할인(NAV 할인)으로 거래돼요. 할인율의 역사적 범위를 보세요.", en: "Holdcos trade at a discount to NAV. Compare today's discount to its historical range." },
  build:    { ko: "수주와 분양 실적이 미래 매출이에요. 미분양과 PF(프로젝트 파이낸싱) 부담을 꼭 확인하세요.", en: "Orders and pre-sales are future revenue. Check unsold inventory and project-finance exposure." },
  realestate: { ko: "금리에 가장 민감한 업종이에요. 임대수익률과 금리 차이(스프레드)가 가치를 결정해요.", en: "The most rate-sensitive sector. The spread between yield and rates sets the value." },
  retail:   { ko: "브랜드력과 이익률의 안정성을 보세요. 경기 방어력이 강점, 폭발적 성장은 약점.", en: "Brand power and margin stability. Defensive, but limited explosive growth." },
  food:     { ko: "경기와 무관한 현금창출력이 강점이에요. 원재료 가격과 판가 인상 여력을 보세요.", en: "Cycle-independent cash flows. Watch input costs and pricing power." },
  cosmetic: { ko: "브랜드와 수출 시장 구성이 핵심이에요. 특정 국가 의존도가 높으면 그 나라 경기가 곧 실적이에요.", en: "Brand and export mix matter. Heavy country concentration makes that country's economy the earnings driver." },
  textile:  { ko: "브랜드 없이 위탁생산만 하면 마진이 얇아요. 브랜드력이 있는지부터 확인하세요.", en: "Contract manufacturing without a brand means thin margins — check for brand power first." },
  transport:{ ko: "운임(운송 가격)이 실적을 좌우하는 사이클 산업이에요. 유가는 비용, 물동량은 매출이에요.", en: "Freight rates drive earnings. Fuel is cost, volume is revenue." },
  edu:      { ko: "학령인구 감소가 구조적 역풍이에요. 온라인 전환과 성인 교육 확장 여부를 보세요.", en: "Shrinking school-age population is a structural headwind; watch online and adult-education pivots." },
  paper:    { ko: "원재료(펄프) 가격과 판가의 시차가 이익을 만들어요. 사이클 산업으로 보세요.", en: "The lag between pulp costs and prices creates the profit. Treat it as cyclical." },
  hotel:    { ko: "고정비가 커서 매출이 조금 늘면 이익이 크게 늘고, 조금 줄면 크게 줄어요(레버리지 효과).", en: "High fixed costs mean profits swing far more than revenue does." },
  index:    { ko: "ETF는 수백 개 종목을 한 바구니에 담은 상품이에요. 여기 적힌 PER·배당은 바구니 안 종목들의 평균이라 개별 기업처럼 읽으면 안 돼요. 대신 보수(수수료)와 어떤 지수를 따라가는지를 먼저 확인하세요.", en: "An ETF is a basket — its PER and yield are averages, not company figures. Check the expense ratio and which index it tracks." },
  metal:    { ko: "금·은은 이익도 배당도 없어서 PER 같은 지표가 아예 없어요. 값을 정하는 건 '남들이 얼마에 사주느냐'뿐이에요. 그래서 기대수익이 아니라, 주식과 따로 움직이는 성질(분산 효과)을 보고 담는 자산이에요.", en: "Metals have no earnings or dividends, so multiples don't apply. You hold them for low correlation, not expected return." },
  etc:      { ko: "업종 분류가 애매한 종목이에요. 사업 개요를 직접 읽어보고, 이 회사가 무엇으로 돈을 버는지 한 문장으로 말할 수 있는지 확인해보세요.", en: "Sector classification is unclear here. Read the business summary and check you can state in one sentence how it makes money." },
};

// ================= Stock snapshot (approximate, editable) =================
// price KRW · beta vs KOSPI · vol annual % · x: {mcap 조원, roe %, opm %, g3 rev growth %/y, debt %, frn foreign %, lo/hi 52w, dk/de desc}
const BASE_STOCKS = [
  { t:"005930", nk:"삼성전자", ne:"Samsung Elec", s:"semi", price:78000, beta:1.15, vol:32, per:14, pbr:1.4, dy:1.8, al:-6,
    x:{ mcap:466, roe:9.2, opm:15, g3:8, debt:27, frn:52, lo:52300, hi:84500, dk:"메모리 세계 1위. 스마트폰·가전·파운드리 종합 IT. 메모리 가격 사이클을 크게 타요.", de:"World #1 memory; phones, appliances, foundry. Rides the memory cycle." } },
  { t:"000660", nk:"SK하이닉스", ne:"SK Hynix", s:"semi", price:420000, beta:1.50, vol:46, per:9, pbr:2.6, dy:0.4, al:25,
    x:{ mcap:300, roe:21, opm:35, g3:22, debt:60, frn:55, lo:210000, hi:460000, dk:"HBM(AI 메모리) 선두. AI 투자 사이클의 최대 수혜주이자, 그만큼 사이클 위험도 커요.", de:"HBM (AI memory) leader. Biggest AI-cycle beneficiary — and cycle risk." } },
  { t:"042700", nk:"한미반도체", ne:"Hanmi Semi", s:"semi", price:90000, beta:1.70, vol:55, per:30, pbr:8.0, dy:0.3, al:35,
    x:{ mcap:9, roe:28, opm:35, g3:45, debt:15, frn:35, lo:48000, hi:130000, dk:"HBM 공정 장비(TC본더) 강자. 성장성은 높지만 고객 집중도가 높아요.", de:"HBM bonder equipment leader. High growth, concentrated customers." } },
  { t:"373220", nk:"LG에너지솔루션", ne:"LG Energy", s:"battery", price:350000, beta:1.30, vol:42, per:60, pbr:3.5, dy:0.0, al:-18,
    x:{ mcap:82, roe:5, opm:4, g3:15, debt:90, frn:10, lo:290000, hi:450000, dk:"글로벌 배터리 2위. 북미 투자 확대 중. EV 수요와 보조금 정책에 민감해요.", de:"Global #2 battery maker. NA expansion; sensitive to EV demand & subsidies." } },
  { t:"006400", nk:"삼성SDI", ne:"Samsung SDI", s:"battery", price:250000, beta:1.35, vol:45, per:25, pbr:1.0, dy:0.4, al:-22,
    x:{ mcap:17, roe:4, opm:3, g3:5, debt:70, frn:40, lo:180000, hi:340000, dk:"프리미엄 배터리·전자재료. 수익성 중심 전략이지만 EV 수요 둔화 영향권.", de:"Premium batteries & materials. Profit-focused; exposed to EV slowdown." } },
  { t:"247540", nk:"에코프로비엠", ne:"EcoPro BM", s:"battery", price:110000, beta:1.80, vol:60, per:45, pbr:6.0, dy:0.0, al:2,
    x:{ mcap:11, roe:8, opm:3, g3:30, debt:120, frn:8, lo:70000, hi:210000, dk:"양극재 대표주. 2023년 테마 급등의 주인공. 변동성이 매우 커요.", de:"Cathode materials flagship; 2023 theme-rally star. Very volatile." } },
  { t:"086520", nk:"에코프로", ne:"EcoPro", s:"battery", price:60000, beta:1.90, vol:65, per:35, pbr:5.0, dy:0.0, al:3,
    x:{ mcap:8, roe:6, opm:4, g3:25, debt:100, frn:6, lo:38000, hi:130000, dk:"에코프로비엠의 지주사. 자회사 가치에 연동되며 변동성은 더 커요.", de:"EcoPro BM's holdco. Tracks subsidiary value with even more volatility." } },
  { t:"005380", nk:"현대차", ne:"Hyundai Motor", s:"auto", price:230000, beta:0.90, vol:28, per:5.5, pbr:0.7, dy:4.5, al:8,
    x:{ mcap:48, roe:12, opm:9, g3:10, debt:110, frn:35, lo:180000, hi:270000, dk:"글로벌 3위권 완성차. 저PER·고배당의 대표 가치주. 미국 판매와 환율이 변수.", de:"Top-3 global automaker. Classic low-PER, high-dividend value; US sales & FX matter." } },
  { t:"000270", nk:"기아", ne:"Kia", s:"auto", price:110000, beta:0.85, vol:27, per:4.5, pbr:0.8, dy:5.5, al:10,
    x:{ mcap:44, roe:15, opm:11, g3:11, debt:70, frn:38, lo:85000, hi:130000, dk:"현대차그룹의 수익성 챔피언. 업계 최상위 이익률과 적극적 주주환원.", de:"The group's profitability champion; top-tier margins, active shareholder returns." } },
  { t:"012330", nk:"현대모비스", ne:"Hyundai Mobis", s:"auto", price:250000, beta:0.80, vol:26, per:7, pbr:0.6, dy:2.0, al:0,
    x:{ mcap:23, roe:8, opm:5, g3:8, debt:40, frn:30, lo:200000, hi:290000, dk:"그룹 핵심 부품사. 전동화 부품 성장 중. 안정적이지만 그룹 의존도가 높아요.", de:"Group's core parts maker; growing e-powertrain. Stable but group-dependent." } },
  { t:"207940", nk:"삼성바이오로직스", ne:"Samsung Bio", s:"bio", price:950000, beta:0.80, vol:30, per:60, pbr:7.0, dy:0.0, al:6,
    x:{ mcap:68, roe:12, opm:30, g3:20, debt:35, frn:12, lo:720000, hi:1080000, dk:"세계 최대 바이오 위탁생산(CDMO). 수주 기반이라 바이오치고 실적이 안정적.", de:"World's largest biologics CDMO. Order-based, unusually stable for bio." } },
  { t:"068270", nk:"셀트리온", ne:"Celltrion", s:"bio", price:180000, beta:1.00, vol:35, per:40, pbr:3.0, dy:0.3, al:-2,
    x:{ mcap:39, roe:8, opm:22, g3:15, debt:30, frn:22, lo:150000, hi:230000, dk:"바이오시밀러 선두. 미국 직판 전환이 성장 열쇠. 합병 후 체급이 커졌어요.", de:"Biosimilar leader; US direct sales are the growth key. Bigger post-merger." } },
  { t:"000100", nk:"유한양행", ne:"Yuhan", s:"bio", price:120000, beta:0.90, vol:38, per:30, pbr:3.5, dy:0.4, al:15,
    x:{ mcap:9.6, roe:7, opm:5, g3:9, debt:25, frn:20, lo:80000, hi:160000, dk:"국내 제약 대표. 폐암 신약 '렉라자'의 글로벌 성과가 가치의 핵심 변수.", de:"Leading Korean pharma; global results of lung-cancer drug Leclaza are key." } },
  { t:"196170", nk:"알테오젠", ne:"Alteogen", s:"bio", price:350000, beta:1.60, vol:60, per:90, pbr:25, dy:0.0, al:45,
    x:{ mcap:19, roe:15, opm:40, g3:60, debt:10, frn:15, lo:180000, hi:460000, dk:"피하주사 변환 플랫폼 기술수출로 급성장. 계약 뉴스에 주가가 크게 반응해요.", de:"SC-conversion platform with big licensing deals. Headline-driven price swings." } },
  { t:"035420", nk:"NAVER", ne:"NAVER", s:"platform", price:220000, beta:1.05, vol:33, per:20, pbr:1.2, dy:0.6, al:-8,
    x:{ mcap:33, roe:7, opm:16, g3:9, debt:40, frn:47, lo:160000, hi:250000, dk:"검색·커머스·웹툰·클라우드. AI 검색 경쟁이 리스크이자 기회.", de:"Search, commerce, webtoon, cloud. AI search competition = risk and option." } },
  { t:"035720", nk:"카카오", ne:"Kakao", s:"platform", price:45000, beta:1.20, vol:40, per:45, pbr:1.5, dy:0.3, al:-15,
    x:{ mcap:20, roe:3, opm:8, g3:7, debt:55, frn:27, lo:33000, hi:62000, dk:"국민 메신저 기반 플랫폼. 계열사 구조조정과 신뢰 회복이 관건.", de:"Messenger-based platform; restructuring and trust recovery in progress." } },
  { t:"259960", nk:"크래프톤", ne:"Krafton", s:"game", price:330000, beta:0.90, vol:35, per:15, pbr:2.2, dy:0.0, al:12,
    x:{ mcap:16, roe:14, opm:30, g3:12, debt:15, frn:32, lo:230000, hi:400000, dk:"배틀그라운드 IP의 힘. 인도 시장과 신작이 다음 성장 동력.", de:"PUBG IP powerhouse; India and new titles drive the next leg." } },
  { t:"105560", nk:"KB금융", ne:"KB Financial", s:"bank", price:90000, beta:0.95, vol:26, per:6, pbr:0.6, dy:4.0, al:15,
    x:{ mcap:36, roe:10, opm:0, g3:6, debt:0, frn:76, lo:65000, hi:105000, dk:"국내 1위 금융지주. 밸류업(주주환원 확대) 정책의 대표 수혜주.", de:"#1 financial group; flagship beneficiary of the 'Value-up' returns push." } },
  { t:"055550", nk:"신한지주", ne:"Shinhan", s:"bank", price:55000, beta:0.90, vol:25, per:5.5, pbr:0.5, dy:4.5, al:8,
    x:{ mcap:28, roe:9, opm:0, g3:5, debt:0, frn:60, lo:42000, hi:62000, dk:"균형 잡힌 포트폴리오의 금융지주. 꾸준한 배당 성향 확대 중.", de:"Well-balanced financial group; steadily raising payout." } },
  { t:"086790", nk:"하나금융지주", ne:"Hana Financial", s:"bank", price:65000, beta:0.90, vol:25, per:5, pbr:0.5, dy:5.0, al:10,
    x:{ mcap:19, roe:9, opm:0, g3:5, debt:0, frn:68, lo:50000, hi:75000, dk:"은행 비중이 높은 지주. 배당수익률이 업계 최상위권이에요.", de:"Bank-heavy group with sector-leading dividend yield." } },
  { t:"323410", nk:"카카오뱅크", ne:"KakaoBank", s:"bank", price:22000, beta:1.25, vol:40, per:25, pbr:1.6, dy:0.7, al:-10,
    x:{ mcap:10.5, roe:6, opm:0, g3:15, debt:0, frn:15, lo:17000, hi:30000, dk:"인터넷은행 1위. 은행이지만 플랫폼 멀티플로 거래돼 변동성이 커요.", de:"#1 internet bank; trades on platform multiples, so it swings." } },
  { t:"032830", nk:"삼성생명", ne:"Samsung Life", s:"insure", price:95000, beta:0.80, vol:24, per:8, pbr:0.4, dy:4.0, al:5,
    x:{ mcap:19, roe:5, opm:0, g3:3, debt:0, frn:18, lo:70000, hi:110000, dk:"생보 1위. 삼성전자 지분 보유가 숨은 자산이자 지배구조 변수.", de:"#1 life insurer; its Samsung Elec stake is hidden value and a governance variable." } },
  { t:"000810", nk:"삼성화재", ne:"Samsung Fire", s:"insure", price:350000, beta:0.70, vol:22, per:9, pbr:0.8, dy:4.5, al:12,
    x:{ mcap:16.5, roe:11, opm:0, g3:5, debt:0, frn:52, lo:270000, hi:400000, dk:"손보 1위. 안정적 이익과 높은 주주환원의 모범생.", de:"#1 P&C insurer; steady profits, strong shareholder returns." } },
  { t:"051910", nk:"LG화학", ne:"LG Chem", s:"chem", price:300000, beta:1.25, vol:40, per:20, pbr:0.9, dy:1.0, al:-20,
    x:{ mcap:21, roe:4, opm:5, g3:3, debt:85, frn:40, lo:230000, hi:420000, dk:"석유화학+배터리(LGES 지분)+신소재. 화학 불황과 배터리 가치가 줄다리기.", de:"Petrochem + LGES stake + materials. Chem downturn vs battery value tug-of-war." } },
  { t:"010950", nk:"S-Oil", ne:"S-Oil", s:"energy", price:65000, beta:1.00, vol:30, per:9, pbr:0.9, dy:4.0, al:-3,
    x:{ mcap:7.3, roe:9, opm:5, g3:2, debt:120, frn:78, lo:52000, hi:80000, dk:"정유 대표주. 정제마진이 곧 실적. 대규모 석유화학 투자(샤힌) 진행 중.", de:"Refining pure-play; margins = earnings. Big Shaheen petchem project underway." } },
  { t:"096770", nk:"SK이노베이션", ne:"SK Innovation", s:"energy", price:110000, beta:1.30, vol:42, per:25, pbr:0.7, dy:0.0, al:-15,
    x:{ mcap:10.5, roe:2, opm:3, g3:4, debt:150, frn:22, lo:85000, hi:150000, dk:"정유+배터리(SK온). 배터리 자회사의 자금 수요가 부담 요인.", de:"Refining + SK On battery; subsidiary funding needs weigh on it." } },
  { t:"005490", nk:"POSCO홀딩스", ne:"POSCO Hldgs", s:"steel", price:280000, beta:1.20, vol:38, per:12, pbr:0.5, dy:2.5, al:-12,
    x:{ mcap:23.7, roe:4, opm:5, g3:2, debt:65, frn:27, lo:220000, hi:420000, dk:"철강 본업 + 리튬·2차전지 소재 신사업. 두 사이클이 겹쳐 움직여요.", de:"Steel core + lithium/battery materials. Two cycles overlap." } },
  { t:"012450", nk:"한화에어로스페이스", ne:"Hanwha Aero", s:"defense", price:700000, beta:1.40, vol:48, per:25, pbr:5.0, dy:0.5, al:40,
    x:{ mcap:32, roe:20, opm:10, g3:35, debt:130, frn:35, lo:280000, hi:820000, dk:"K9 자주포·천무의 방산 대장주. 수주잔고가 수년치 매출을 보장해요.", de:"K-defense flagship (K9, Chunmoo). Backlog covers years of revenue." } },
  { t:"329180", nk:"HD현대중공업", ne:"HD Hyundai HI", s:"ship", price:350000, beta:1.35, vol:45, per:30, pbr:4.0, dy:0.3, al:30,
    x:{ mcap:31, roe:12, opm:7, g3:20, debt:110, frn:20, lo:120000, hi:400000, dk:"조선 슈퍼사이클 수혜. 함정(군함)과 친환경 선박이 성장 축.", de:"Shipbuilding supercycle play; naval vessels and green ships lead." } },
  { t:"042660", nk:"한화오션", ne:"Hanwha Ocean", s:"ship", price:70000, beta:1.50, vol:55, per:35, pbr:4.5, dy:0.0, al:25,
    x:{ mcap:21.5, roe:8, opm:4, g3:18, debt:180, frn:15, lo:26000, hi:85000, dk:"옛 대우조선. 한화 편입 후 방산 조선으로 재평가. 변동성 주의.", de:"Ex-DSME, re-rated under Hanwha for naval focus. Mind the volatility." } },
  { t:"034020", nk:"두산에너빌리티", ne:"Doosan Ener", s:"machine", price:40000, beta:1.60, vol:55, per:45, pbr:3.5, dy:0.0, al:20,
    x:{ mcap:25.6, roe:5, opm:6, g3:12, debt:120, frn:18, lo:15000, hi:48000, dk:"원전·가스터빈·SMR. 원전 르네상스 기대감이 주가의 핵심 동력.", de:"Nuclear, gas turbines, SMR. Nuclear-renaissance hopes drive the stock." } },
  { t:"036570", nk:"엔씨소프트", ne:"NCSOFT", s:"game", price:180000, beta:1.00, vol:40, per:20, pbr:1.0, dy:1.0, al:-18,
    x:{ mcap:3.9, roe:5, opm:10, g3:-8, debt:20, frn:40, lo:150000, hi:250000, dk:"리니지 IP 의존을 벗어나려는 중. 신작 성패에 따라 크게 움직여요.", de:"Trying to move past Lineage reliance; swings on new-title outcomes." } },
  { t:"352820", nk:"하이브", ne:"HYBE", s:"media", price:250000, beta:1.10, vol:42, per:30, pbr:3.0, dy:0.0, al:-5,
    x:{ mcap:10.4, roe:8, opm:12, g3:15, debt:60, frn:20, lo:150000, hi:290000, dk:"BTS·뉴진스 등 멀티레이블. 위버스 플랫폼화가 다음 단계.", de:"Multi-label K-pop (BTS etc.); Weverse platformization is next." } },
  { t:"017670", nk:"SK텔레콤", ne:"SK Telecom", s:"telecom", price:55000, beta:0.45, vol:18, per:9, pbr:0.9, dy:6.5, al:3,
    x:{ mcap:12, roe:9, opm:10, g3:2, debt:90, frn:45, lo:48000, hi:60000, dk:"통신 1위. 배당 매력이 본질. AI 사업 전환을 시도 중.", de:"#1 telecom; dividends are the point. Pivoting toward AI services." } },
  { t:"030200", nk:"KT", ne:"KT", s:"telecom", price:45000, beta:0.50, vol:19, per:8, pbr:0.6, dy:4.5, al:6,
    x:{ mcap:11.7, roe:7, opm:7, g3:2, debt:110, frn:42, lo:33000, hi:50000, dk:"통신+부동산+클라우드 자산주. 지배구조 개선과 주주환원이 테마.", de:"Telecom + real estate + cloud assets; governance and returns are the theme." } },
  { t:"032640", nk:"LG유플러스", ne:"LG Uplus", s:"telecom", price:11000, beta:0.45, vol:18, per:8, pbr:0.6, dy:5.5, al:-2,
    x:{ mcap:4.8, roe:7, opm:7, g3:2, debt:120, frn:35, lo:9500, hi:12500, dk:"통신 3위. 안정적 배당이 강점, 성장 스토리는 약해요.", de:"#3 telecom; steady dividends, thin growth story." } },
  { t:"015760", nk:"한국전력", ne:"KEPCO", s:"utility", price:22000, beta:0.70, vol:30, per:6, pbr:0.4, dy:1.5, al:4,
    x:{ mcap:14.1, roe:6, opm:8, g3:5, debt:500, frn:15, lo:16000, hi:26000, dk:"전기요금이 정치로 정해지는 공기업. 요금 정상화가 실적의 전부예요.", de:"State utility; politically set tariffs. Rate normalization is everything." } },
  { t:"033780", nk:"KT&G", ne:"KT&G", s:"food", price:100000, beta:0.35, vol:17, per:11, pbr:1.2, dy:5.5, al:2,
    x:{ mcap:12.4, roe:11, opm:22, g3:4, debt:20, frn:42, lo:85000, hi:110000, dk:"담배+인삼. 경기와 무관한 현금창출력, 시장이 흔들릴 때 빛나는 방어주.", de:"Tobacco + ginseng cash machine; a defensive that shines in storms." } },
  { t:"090430", nk:"아모레퍼시픽", ne:"Amorepacific", s:"cosmetic", price:120000, beta:0.90, vol:38, per:30, pbr:2.0, dy:0.8, al:-10,
    x:{ mcap:7, roe:6, opm:8, g3:3, debt:15, frn:30, lo:95000, hi:170000, dk:"K뷰티 대표. 중국 의존을 줄이고 서구권 확장 중. 회복 스토리 주식.", de:"K-beauty flagship; shifting from China to Western markets. A recovery story." } },
  { t:"097950", nk:"CJ제일제당", ne:"CJ CheilJedang", s:"food", price:280000, beta:0.60, vol:24, per:9, pbr:0.6, dy:2.0, al:-4,
    x:{ mcap:4.2, roe:7, opm:6, g3:4, debt:130, frn:22, lo:220000, hi:330000, dk:"식품+바이오(아미노산). K푸드 수출 성장이 새 동력.", de:"Food + bio (amino acids); K-food exports are the new engine." } },
  { t:"021240", nk:"코웨이", ne:"Coway", s:"elec", price:70000, beta:0.50, vol:22, per:9, pbr:1.8, dy:2.0, al:8,
    x:{ mcap:5.2, roe:20, opm:18, g3:6, debt:60, frn:60, lo:55000, hi:80000, dk:"정수기 렌탈 구독모델. 경기 방어력과 높은 ROE가 매력.", de:"Water-purifier rental subscriptions; defensive with high ROE." } },
  { t:"139480", nk:"이마트", ne:"E-mart", s:"retail", price:65000, beta:0.70, vol:30, per:10, pbr:0.2, dy:3.0, al:-12,
    x:{ mcap:1.8, roe:1, opm:1, g3:1, debt:110, frn:20, lo:50000, hi:80000, dk:"오프라인 유통 1위. PBR 0.2배의 극단적 저평가 vs 구조적 쇠퇴 논쟁.", de:"#1 offline retail. PBR 0.2 deep value vs structural decline debate." } },
  { t:"028260", nk:"삼성물산", ne:"Samsung C&T", s:"holding", price:140000, beta:0.90, vol:28, per:12, pbr:0.8, dy:1.8, al:5,
    x:{ mcap:26, roe:7, opm:5, g3:5, debt:35, frn:25, lo:110000, hi:170000, dk:"그룹 사실상 지주사. 바이오·전자 지분가치 대비 할인 거래.", de:"De facto group holdco; trades at a discount to its bio/electronics stakes." } },
  // ---- 미국 주식 (beta = S&P 500 대비, 변동성·가격은 원화 투자자 기준) ----
  { t:"AAPL", nk:"애플", ne:"Apple", s:"elec", cls:"us", ccy:"USD", fxu:true, price:232, beta:1.10, vol:26, per:32, pbr:48, dy:0.5, al:2,
    x:{ mcap:4830, roe:150, opm:31, g3:6, lo:164, hi:260, dk:"아이폰 생태계와 서비스 매출. 이익률이 매우 높지만 성장은 완만해요. 중국 매출과 규제가 변수.", de:"iPhone ecosystem plus services. Very high margins, moderate growth; China and regulation are swing factors." } },
  { t:"MSFT", nk:"마이크로소프트", ne:"Microsoft", s:"platform", cls:"us", ccy:"USD", fxu:true, price:430, beta:1.05, vol:24, per:33, pbr:11, dy:0.7, al:5,
    x:{ mcap:4420, roe:35, opm:45, g3:14, lo:355, hi:470, dk:"오피스·윈도우의 현금흐름 위에 애저(클라우드)와 AI를 얹었어요. AI 투자비 회수 속도가 관건.", de:"Office/Windows cash flows plus Azure and AI. The question is how fast AI capex pays back." } },
  { t:"NVDA", nk:"엔비디아", ne:"NVIDIA", s:"semi", cls:"us", ccy:"USD", fxu:true, price:135, beta:1.70, vol:48, per:45, pbr:45, dy:0.0, al:60,
    x:{ mcap:4550, roe:90, opm:62, g3:80, lo:75, hi:153, dk:"AI 가속기 사실상 독점. 최근 3년 수익률이 압도적이었던 만큼, 기대치도 함께 올라가 있어요.", de:"Near-monopoly in AI accelerators. Spectacular 3-year run — but expectations have risen with it." } },
  { t:"AVGO", nk:"브로드컴", ne:"Broadcom", s:"semi", cls:"us", ccy:"USD", fxu:true, price:230, beta:1.25, vol:35, per:35, pbr:16, dy:1.0, al:30,
    x:{ mcap:1490, roe:38, opm:45, g3:30, lo:128, hi:251, dk:"맞춤형 AI칩과 인프라 소프트웨어. 대형 고객 몇 곳에 매출이 집중돼 있어요.", de:"Custom AI silicon plus infrastructure software; revenue concentrated in a few large customers." } },
  { t:"AMD", nk:"AMD", ne:"AMD", s:"semi", cls:"us", ccy:"USD", fxu:true, price:140, beta:1.75, vol:45, per:40, pbr:4, dy:0.0, al:5,
    x:{ mcap:315, roe:8, opm:12, g3:15, lo:94, hi:211, dk:"CPU에선 인텔을 추격해 성공했지만, AI 가속기에선 엔비디아의 대항마 자리를 노리는 중.", de:"Won share from Intel in CPUs; still fighting for the #2 slot in AI accelerators." } },
  { t:"GOOGL", nk:"알파벳", ne:"Alphabet", s:"platform", cls:"us", ccy:"USD", fxu:true, price:196, beta:1.05, vol:28, per:24, pbr:7, dy:0.5, al:8,
    x:{ mcap:3270, roe:32, opm:32, g3:13, lo:130, hi:208, dk:"검색 광고가 현금줄, 클라우드와 유튜브가 성장축. AI 검색 경쟁이 기회이자 최대 리스크.", de:"Search ads fund it; cloud and YouTube grow it. AI search is both the opportunity and the risk." } },
  { t:"AMZN", nk:"아마존", ne:"Amazon", s:"retail", cls:"us", ccy:"USD", fxu:true, price:225, beta:1.15, vol:30, per:38, pbr:8, dy:0.0, al:6,
    x:{ mcap:3300, roe:22, opm:11, g3:12, lo:151, hi:243, dk:"이커머스는 규모, 이익은 AWS(클라우드)에서 나와요. 사실상 두 개의 회사를 함께 사는 셈.", de:"E-commerce for scale, AWS for profit — effectively two companies in one ticker." } },
  { t:"META", nk:"메타", ne:"Meta", s:"platform", cls:"us", ccy:"USD", fxu:true, price:600, beta:1.25, vol:36, per:25, pbr:8, dy:0.4, al:20,
    x:{ mcap:2090, roe:35, opm:42, g3:16, lo:414, hi:740, dk:"인스타·페이스북 광고가 본업. AI와 메타버스에 막대한 투자를 이어가고 있어요.", de:"Instagram/Facebook advertising, with heavy ongoing spend on AI and the metaverse." } },
  { t:"TSLA", nk:"테슬라", ne:"Tesla", s:"auto", cls:"us", ccy:"USD", fxu:true, price:340, beta:1.90, vol:55, per:90, pbr:15, dy:0.0, al:-5,
    x:{ mcap:1510, roe:18, opm:8, g3:10, lo:139, hi:488, dk:"전기차 실적보다 자율주행·로봇에 대한 기대가 주가를 움직여요. 변동성이 매우 큽니다.", de:"Priced on autonomy and robotics hopes more than EV earnings. Extremely volatile." } },
  { t:"JPM", nk:"JP모간", ne:"JPMorgan", s:"bank", cls:"us", ccy:"USD", fxu:true, price:245, beta:1.05, vol:24, per:13, pbr:2.1, dy:2.2, al:10,
    x:{ mcap:950, roe:17, opm:0, g3:9, lo:190, hi:255, dk:"미국 최대 은행. 금리와 경기에 민감하지만, 위기 때 오히려 예금이 몰리는 강자예요.", de:"Largest US bank — rate- and cycle-sensitive, yet deposits flow toward it in crises." } },
  { t:"BRK.B", nk:"버크셔해서웨이", ne:"Berkshire", s:"insure", cls:"us", ccy:"USD", fxu:true, price:465, beta:0.85, vol:18, per:22, pbr:1.6, dy:0.0, al:2,
    x:{ mcap:1380, roe:9, opm:0, g3:8, lo:395, hi:492, dk:"버핏이 만든 복합기업. 보험 자금으로 기업을 사 모으는 구조라 시장보다 덜 흔들려요.", de:"Buffett's conglomerate: insurance float used to buy businesses, so it swings less than the market." } },
  { t:"V", nk:"비자", ne:"Visa", s:"broker", cls:"us", ccy:"USD", fxu:true, price:315, beta:0.95, vol:21, per:28, pbr:14, dy:0.7, al:0,
    x:{ mcap:850, roe:50, opm:67, g3:10, lo:252, hi:329, dk:"카드 결제망 통행료를 걷는 사업. 이익률이 극단적으로 높고 경기 방어력도 있어요.", de:"Collects a toll on card payments — extraordinary margins with defensive characteristics." } },
  { t:"LLY", nk:"일라이릴리", ne:"Eli Lilly", s:"bio", cls:"us", ccy:"USD", fxu:true, price:790, beta:0.60, vol:32, per:55, pbr:45, dy:0.7, al:25,
    x:{ mcap:1030, roe:60, opm:35, g3:30, lo:678, hi:972, dk:"비만·당뇨 치료제(GLP-1)의 최대 수혜주. 성장은 강하지만 밸류에이션 부담도 커요.", de:"Biggest winner of the GLP-1 obesity/diabetes wave — strong growth, demanding valuation." } },
  { t:"UNH", nk:"유나이티드헬스", ne:"UnitedHealth", s:"health", cls:"us", ccy:"USD", fxu:true, price:500, beta:0.65, vol:28, per:18, pbr:4, dy:1.6, al:-12,
    x:{ mcap:640, roe:24, opm:8, g3:11, lo:436, hi:630, dk:"미국 최대 건강보험사. 정책·규제 리스크가 실적보다 주가를 더 흔드는 편이에요.", de:"Largest US health insurer; policy and regulation move the stock more than earnings do." } },
  { t:"JNJ", nk:"존슨앤존슨", ne:"Johnson & Johnson", s:"bio", cls:"us", ccy:"USD", fxu:true, price:155, beta:0.55, vol:18, per:16, pbr:5, dy:3.0, al:-4,
    x:{ mcap:515, roe:30, opm:25, g3:5, lo:140, hi:169, dk:"60년 넘게 배당을 올려온 제약·의료기기 회사. 성장은 느리지만 시장이 흔들릴 때 버팀목이 돼요.", de:"Pharma and devices with 60+ years of dividend growth — slow, but a ballast in rough markets." } },
  { t:"COST", nk:"코스트코", ne:"Costco", s:"retail", cls:"us", ccy:"USD", fxu:true, price:920, beta:0.80, vol:22, per:50, pbr:16, dy:0.5, al:12,
    x:{ mcap:565, roe:31, opm:4, g3:8, lo:730, hi:1078, dk:"이익의 상당 부분이 연회비에서 나오는 구독형 유통. 안정적이지만 PER이 유통업 치고 매우 높아요.", de:"Membership fees drive much of the profit — stable, but priced far above typical retail multiples." } },
  { t:"WMT", nk:"월마트", ne:"Walmart", s:"retail", cls:"us", ccy:"USD", fxu:true, price:92, beta:0.60, vol:20, per:35, pbr:8, dy:1.0, al:15,
    x:{ mcap:1020, roe:22, opm:4, g3:6, lo:66, hi:105, dk:"오프라인 최강자가 온라인·광고로 확장 중. 불황에 오히려 손님이 늘어나는 방어주.", de:"The offline giant expanding into e-commerce and ads; traffic actually rises in downturns." } },
  { t:"KO", nk:"코카콜라", ne:"Coca-Cola", s:"food", cls:"us", ccy:"USD", fxu:true, price:63, beta:0.55, vol:16, per:24, pbr:10, dy:3.0, al:-2,
    x:{ mcap:375, roe:42, opm:30, g3:5, lo:57, hi:74, dk:"경기와 거의 무관한 브랜드 현금흐름. 배당을 60년 넘게 올려온 대표적 방어주예요.", de:"Brand cash flows nearly independent of the cycle, with 60+ years of dividend increases." } },
  { t:"PG", nk:"P&G", ne:"Procter & Gamble", s:"cosmetic", cls:"us", ccy:"USD", fxu:true, price:168, beta:0.50, vol:16, per:25, pbr:8, dy:2.4, al:-3,
    x:{ mcap:545, roe:31, opm:23, g3:3, lo:154, hi:180, dk:"생활필수품 브랜드 묶음. 성장은 물가상승률 수준이지만, 시장이 무너질 때 가장 덜 빠지는 축.", de:"A basket of household staples: inflation-level growth, but among the least-hit when markets break." } },
  { t:"XOM", nk:"엑슨모빌", ne:"Exxon Mobil", s:"energy", cls:"us", ccy:"USD", fxu:true, price:112, beta:0.85, vol:26, per:14, pbr:1.8, dy:3.3, al:5,
    x:{ mcap:670, roe:13, opm:12, g3:2, lo:97, hi:126, dk:"유가가 실적의 대부분을 결정해요. 인플레이션 국면에서 주식 포트폴리오의 완충재 역할을 하기도 해요.", de:"Oil prices drive earnings; can cushion an equity portfolio during inflationary stretches." } },
  { t:"CAT", nk:"캐터필러", ne:"Caterpillar", s:"machine", cls:"us", ccy:"USD", fxu:true, price:390, beta:1.15, vol:28, per:16, pbr:9, dy:1.5, al:12,
    x:{ mcap:255, roe:55, opm:20, g3:9, lo:287, hi:418, dk:"건설·광산 장비의 대표주. 전형적인 경기순환주라 사이클 위치를 먼저 봐야 해요.", de:"Construction and mining equipment — a classic cyclical; read the cycle before the multiple." } },
  { t:"BA", nk:"보잉", ne:"Boeing", s:"defense", cls:"us", ccy:"USD", fxu:true, price:180, beta:1.40, vol:40, per:60, pbr:0, dy:0.0, al:-20,
    x:{ mcap:250, roe:0, opm:-3, g3:2, lo:137, hi:200, dk:"항공기 2강 중 하나지만 품질·생산 문제로 오래 부진했어요. 회복 스토리이자 리스크.", de:"Half of the aircraft duopoly, long troubled by quality and production issues — a recovery story with risk." } },
  { t:"NFLX", nk:"넷플릭스", ne:"Netflix", s:"media", cls:"us", ccy:"USD", fxu:true, price:900, beta:1.30, vol:36, per:40, pbr:15, dy:0.0, al:18,
    x:{ mcap:530, roe:38, opm:27, g3:14, lo:585, hi:1058, dk:"스트리밍 1위. 광고 요금제와 계정 공유 단속으로 수익성이 크게 개선됐어요.", de:"Streaming leader; ad tiers and password-sharing crackdowns sharply improved profitability." } },
  { t:"DIS", nk:"디즈니", ne:"Disney", s:"media", cls:"us", ccy:"USD", fxu:true, price:112, beta:1.10, vol:30, per:22, pbr:2, dy:0.9, al:-8,
    x:{ mcap:280, roe:6, opm:13, g3:5, lo:83, hi:123, dk:"테마파크는 튼튼하지만 스트리밍 전환 비용이 컸어요. IP의 가치와 실적의 괴리가 논쟁거리.", de:"Parks are solid; the streaming transition was costly. IP value versus earnings remains the debate." } },
  { t:"VOO", nk:"S&P500 ETF (VOO)", ne:"Vanguard S&P 500", s:"index", cls:"us", ccy:"USD", fxu:true, price:560, beta:1.00, vol:16, per:26, pbr:5, dy:1.3, al:0 },
  { t:"QQQ", nk:"나스닥100 ETF (QQQ)", ne:"Invesco QQQ", s:"index", cls:"us", ccy:"USD", fxu:true, price:510, beta:1.15, vol:21, per:32, pbr:8, dy:0.6, al:4 },
  { t:"SCHD", nk:"미국 배당 ETF (SCHD)", ne:"Schwab US Dividend", s:"index", cls:"us", ccy:"USD", fxu:true, price:27, beta:0.80, vol:15, per:17, pbr:3, dy:3.5, al:-2 },
  // ---- 국내 상장 ETF ----
  { t:"069500", nk:"KODEX 200", ne:"KODEX 200", s:"index", cls:"kr", price:36000, beta:1.00, vol:18, per:12, pbr:1.0, dy:2.0, al:0 },
  { t:"379800", nk:"KODEX 미국S&P500", ne:"KODEX US S&P500", s:"index", cls:"us", fxu:true, price:19000, beta:1.00, vol:16, per:26, pbr:5, dy:1.2, al:0 },
  // ---- 금·은 (헤지용 보조 자산) ----
  { t:"04020000", nk:"KRX 금현물 (99.99K)", ne:"KRX Gold Spot", s:"metal", cls:"metal", fxu:true, price:135000, beta:1.00, vol:15, per:0, pbr:0, dy:0.0, al:0,
    x:{ dk:"KRX 금시장에서 사는 실물 금. 매매차익이 비과세라 금 ETF보다 세금에서 유리해요. 달러로 값이 매겨져 원화 약세 때 이중으로 오릅니다.", de:"Physical gold on the KRX exchange: capital gains are untaxed, unlike gold ETFs. Priced in dollars, so a weak won lifts it twice." } },
  { t:"132030", nk:"KODEX 골드선물(H)", ne:"KODEX Gold Futures(H)", s:"metal", cls:"metal", price:15000, beta:1.00, vol:15.5, per:0, pbr:0, dy:0.0, al:0,
    x:{ dk:"환헤지형 금 ETF. 환율 변동은 막아주지만, 위기 때 원화 약세가 주는 완충 효과도 함께 사라져요. 매매차익에 배당소득세 15.4%가 붙습니다.", de:"Currency-hedged gold ETF: it removes FX swings, but also the cushion a weak won provides in a crisis. Gains taxed at 15.4%." } },
  { t:"144600", nk:"KODEX 은선물(H)", ne:"KODEX Silver Futures(H)", s:"metal", cls:"metal", price:5000, beta:1.50, vol:30, per:0, pbr:0, dy:0.0, al:0,
    x:{ dk:"은은 금보다 훨씬 크게 출렁여요(연 30%). 태양광·전자 등 산업 수요가 절반이라 경기가 나쁠 땐 주식처럼 같이 빠질 수 있어요 — 금보다 약한 방패입니다.", de:"Silver swings far harder than gold (~30%/yr). Half its demand is industrial, so it can fall with stocks in a downturn — a weaker shield than gold." } },
];

const DEFAULT_SETTINGS = {
  rf: 3.0, mrp: 5.5, mktVol: 18,
  usMrp: 5.0, usVol: 16,
  mtMrp: 0.5, mtVol: 15,
  rhoKrUs: 0.50, rhoKrMt: 0.00, rhoUsMt: 0.05,
  bdMrp: 1.0, bdVol: 7.0, rhoKrBd: 0.05, rhoUsBd: 0.05, rhoMtBd: 0.10,
  fx: 1380, fxFee: 0.5, infl: 2.0,
};

const DEFAULT_PROFILE = {
  ready: false, source: null,
  riskCapacity: 5, riskTolerance: 5, riskNeedPct: 7,
  targetBetaMin: 0.7, targetBetaMax: 1.1, targetVolMaxPct: 24,
  stocksMin: 8, stocksMax: 15, maxPositionPct: 20, maxSectorPct: 35,
  attrs: null, account: "normal", interestedSectors: [], tips: [], checkFreq: "", cashFloorPct: 10,
  title: "", summary: "", flags: [],
};

// Fallback presets (no-AI path)
const PRESETS = {
  calm: { ko:"신중형", en:"Cautious", emoji:"",
    freq: { ko:"분기 1회", en:"Quarterly" },
    tips: { ko:["출렁임이 큰 종목은 비중을 작게 시작해보세요.","현금 15%는 '기회'이자 '안전벨트'예요 — 다 쓰지 않아도 괜찮아요."], en:["Start volatile names at small weights.","Your 15% cash floor is both option and seatbelt — it needn't be spent."] },
    p:{ riskCapacity:5, riskTolerance:3, riskNeedPct:5, targetBetaMin:0.4, targetBetaMax:0.8, targetVolMaxPct:18, stocksMin:10, stocksMax:18, maxPositionPct:15, maxSectorPct:30, cashFloorPct:15,
        attrs:{ capacity:5, tolerance:3, horizon:7, experience:3, knowledge:4, discipline:7, ambition:3, engagement:3 } } },
  balance: { ko:"균형형", en:"Balanced", emoji:"",
    freq: { ko:"월 1회", en:"Monthly" },
    tips: { ko:["관심 섹터가 섹터 상한(35%)을 넘기기 쉬워요 — 계기판을 믿으세요.","실효 종목 수가 8을 넘도록 비중을 고르게 가져가보세요."], en:["Favorite sectors easily breach the 35% cap — trust the gauges.","Keep weights even enough that effective N stays above 8."] },
    p:{ riskCapacity:6, riskTolerance:6, riskNeedPct:7, targetBetaMin:0.7, targetBetaMax:1.1, targetVolMaxPct:24, stocksMin:8, stocksMax:15, maxPositionPct:20, maxSectorPct:35, cashFloorPct:10,
        attrs:{ capacity:6, tolerance:6, horizon:6, experience:5, knowledge:5, discipline:6, ambition:5, engagement:5 } } },
  bold: { ko:"적극형", en:"Aggressive", emoji:"",
    freq: { ko:"월 1회", en:"Monthly" },
    tips: { ko:["β 상한 1.4를 넘기고 싶은 유혹이 올 거예요 — 상한은 브레이크가 아니라 안전벨트예요.","한 종목 몰빵의 유혹이 가장 큰 유형이에요. 종목당 25%를 지켜주세요."], en:["You'll be tempted past the 1.4 β cap — it's a seatbelt, not a brake.","This profile is most tempted by all-in bets. Hold the 25%/stock line."] },
    p:{ riskCapacity:7, riskTolerance:8, riskNeedPct:9, targetBetaMin:0.9, targetBetaMax:1.4, targetVolMaxPct:32, stocksMin:6, stocksMax:12, maxPositionPct:25, maxSectorPct:40, cashFloorPct:5,
        attrs:{ capacity:7, tolerance:8, horizon:6, experience:7, knowledge:6, discipline:4, ambition:8, engagement:8 } } },
};

// ================= Questionnaire =================
const Q_INTRO = {
  ko: "안녕하세요, 뱁이예요 탭하고 밀기만 하면 끝나요. 정답은 없으니 편하게 골라주세요.",
  en: "Hi, I'm Baebi Just tap and slide — no typing. There are no right answers.",
};
const QUESTIONS = [
  { id:"goal", type:"one", ko:"이 돈으로 이루고 싶은 게 뭐예요?", en:"What is this money for?", opts:[
    { v:"house", e:"", ko:"내 집 마련", en:"A home" },
    { v:"retire", e:"", ko:"은퇴 준비", en:"Retirement" },
    { v:"lump", e:"", ko:"목돈 만들기", en:"A lump sum" },
    { v:"wed", e:"", ko:"결혼 자금", en:"Wedding fund" },
    { v:"edu", e:"", ko:"자녀 교육비", en:"Kids' education" },
    { v:"living", e:"", ko:"노후 생활비", en:"Living in later life" },
    { v:"grow", e:"", ko:"그냥 불려보기", en:"Just growing it" },
    { v:"unsure", e:"", ko:"아직 모르겠어요", en:"Not sure yet" },
  ]},
  { id:"horizon", type:"slider", min:1, max:30, step:1, def:10, ko:"이 돈이 실제로 필요해지는 건 언제쯤인가요?", en:"When will you actually need this money?",
    fmt:(v,l)=> v>=30 ? (l==="ko"?"30년 이상 뒤":"30+ years") : (l==="ko"? v+"년 뒤" : "in "+v+" years") },
  { id:"share", type:"slider", min:0, max:100, step:5, def:40, ko:"전체 재산 중 이 투자에 넣을 비중은요?", en:"What share of your total wealth goes here?",
    fmt:(v,l)=> v===0 ? (l==="ko"?"아주 조금":"Almost none") : v>=100 ? (l==="ko"?"전 재산 전부":"Everything I have") : v+"%" },
  { id:"emergency", type:"slider", min:0, max:12, step:1, def:3, ko:"수입이 끊겨도 버틸 수 있는 비상금은 몇 달치인가요?", en:"How many months of emergency fund do you keep?",
    fmt:(v,l)=> v===0 ? (l==="ko"?"거의 없어요":"Almost none") : v>=12 ? (l==="ko"?"1년치 이상":"A year or more") : (l==="ko"? v+"개월치" : v+" months") },
  { id:"target", type:"slider", min:3, max:20, step:1, def:8, ko:"연 몇 %쯤 벌면 '성공'이라고 느끼실까요?", en:"What annual return would feel like success?",
    fmt:(v,l)=> (l==="ko"? "연 "+v+"%" : v+"%/yr") + (v<=4 ? (l==="ko"?" · 예금 수준":" · deposit-like") : v<=8 ? (l==="ko"?" · 코스피 장기 평균 근처":" · near KOSPI long-run") : v<=12 ? (l==="ko"?" · 꽤 공격적":" · fairly aggressive") : (l==="ko"?" · 전설들의 영역":" · legend territory")) },
  { id:"style", type:"chips", ko:"나를 잘 설명하는 말을 모두 골라주세요.", en:"Pick everything that describes you.", opts:[
    { v:"safe", e:"", ko:"안정이 최우선", en:"Safety first" },
    { v:"ret", e:"", ko:"수익이 최우선", en:"Returns first" },
    { v:"long", e:"", ko:"길게 본다", en:"Think long-term" },
    { v:"short", e:"", ko:"짧게 치고 빠진다", en:"Quick in and out" },
    { v:"data", e:"", ko:"숫자로 판단", en:"Judge by numbers" },
    { v:"gut", e:"", ko:"감으로 판단", en:"Judge by feel" },
    { v:"news", e:"", ko:"뉴스에 민감", en:"News-sensitive" },
    { v:"calm", e:"", ko:"웬만하면 무던", en:"Mostly unbothered" },
    { v:"fomo", e:"", ko:"남들 하는 건 해봐야", en:"Must try what's hot" },
    { v:"rule", e:"", ko:"내 원칙대로", en:"Stick to my rules" },
    { v:"div", e:"", ko:"배당 받는 게 좋다", en:"Love dividends" },
    { v:"new", e:"", ko:"새로운 것에 끌린다", en:"Drawn to what's new" },
  ]},
  { id:"crash", type:"chips", ko:"어느 날 아침 계좌가 −30%. 나에게 있을 법한 반응을 모두 골라주세요.", en:"Your account is down 30% overnight. Pick your likely reactions.", opts:[
    { v:"sellall", e:"", ko:"전부 판다", en:"Sell everything" },
    { v:"sellsome", e:"", ko:"일부 판다", en:"Sell some" },
    { v:"hold", e:"", ko:"일단 버틴다", en:"Hold on" },
    { v:"buy", e:"", ko:"오히려 더 산다", en:"Buy more" },
    { v:"nosleep", e:"", ko:"잠이 안 올 듯", en:"Won't sleep" },
    { v:"numb", e:"", ko:"의외로 무덤덤할 듯", en:"Probably unfazed" },
    { v:"nolook", e:"", ko:"아예 계좌를 안 본다", en:"Stop looking entirely" },
    { v:"ask", e:"", ko:"누군가에게 물어본다", en:"Ask someone" },
  ]},
  { id:"exp", type:"chips", ko:"지금까지 해본 것을 모두 골라주세요.", en:"Pick everything you've tried.", opts:[
    { v:"dep", e:"", ko:"예·적금만", en:"Deposits only" },
    { v:"krstock", e:"", ko:"국내 주식", en:"KR stocks" },
    { v:"usstock", e:"", ko:"해외 주식", en:"Foreign stocks" },
    { v:"etfkr", e:"", ko:"국내 ETF", en:"KR ETFs" },
    { v:"etfus", e:"", ko:"해외 ETF", en:"Overseas ETFs" },
    { v:"lev", e:"", ko:"레버리지·인버스", en:"Leveraged/inverse" },
    { v:"coin", e:"", ko:"코인", en:"Crypto" },
    { v:"ipo", e:"", ko:"공모주", en:"IPOs" },
    { v:"fund", e:"", ko:"펀드·연금", en:"Funds/pension" },
    { v:"metal", e:"", ko:"금·은", en:"Gold/silver" },
    { v:"bond", e:"", ko:"채권", en:"Bonds" },
    { v:"newbie", e:"", ko:"거의 처음이에요", en:"Almost brand new" },
  ]},
  { id:"checking", type:"one", ko:"계좌를 얼마나 자주 확인하실 것 같나요?", en:"How often will you check your account?", opts:[
    { v:"many", e:"", ko:"하루에 여러 번", en:"Many times a day" },
    { v:"daily", e:"", ko:"하루 한 번", en:"Once a day" },
    { v:"weekly", e:"", ko:"주 1~2회", en:"Once or twice a week" },
    { v:"monthly", e:"", ko:"월 1회", en:"Monthly" },
    { v:"quarterly", e:"", ko:"분기에 한 번", en:"Quarterly" },
    { v:"rare", e:"", ko:"거의 안 봐요", en:"Almost never" },
  ]},
  { id:"fear", type:"chips", ko:"투자에서 가장 두려운 걸 모두 골라주세요.", en:"Pick what you fear most in investing.", opts:[
    { v:"loss", e:"", ko:"원금을 잃는 것", en:"Losing the principal" },
    { v:"swing", e:"", ko:"계좌가 크게 출렁이는 것", en:"Big account swings" },
    { v:"fomo", e:"", ko:"남들만 버는 것", en:"Others getting rich" },
    { v:"pick", e:"", ko:"잘못된 종목을 고르는 것", en:"Picking the wrong stock" },
    { v:"early", e:"", ko:"너무 일찍 파는 것", en:"Selling too early" },
    { v:"stuck", e:"", ko:"물려서 못 파는 것", en:"Being stuck underwater" },
    { v:"goal", e:"", ko:"목표를 못 이루는 것", en:"Missing the goal" },
    { v:"none", e:"", ko:"딱히 없어요", en:"Nothing much" },
  ]},
  { id:"account", type:"one", ko:"어떤 계좌로 투자하실 건가요? (세금이 꽤 달라져요)", en:"Which account will you invest through? (taxes differ a lot)", opts:[
    { v:"normal", e:"", ko:"일반 계좌", en:"Regular" },
    { v:"isa", e:"", ko:"ISA", en:"ISA" },
    { v:"pension", e:"", ko:"연금저축", en:"Pension savings" },
    { v:"irp", e:"", ko:"IRP", en:"IRP" },
    { v:"unsure", e:"", ko:"아직 모르겠어요", en:"Not sure yet" },
  ]},
  { id:"interest", type:"chips", ko:"끌리는 분야를 골라주세요. 종목 고를 때 로 표시해드릴게요.", en:"Pick sectors that attract you — we'll them later.", opts:[
    { v:"semi", e:"", ko:"반도체·AI", en:"Semis/AI" },
    { v:"battery", e:"", ko:"2차전지", en:"Battery" },
    { v:"bio", e:"", ko:"바이오·헬스케어", en:"Bio/Health" },
    { v:"platform", e:"", ko:"인터넷·플랫폼", en:"Internet/Platform" },
    { v:"game", e:"", ko:"게임·엔터", en:"Games/Ent" },
    { v:"finance", e:"", ko:"금융", en:"Finance" },
    { v:"auto", e:"", ko:"자동차", en:"Autos" },
    { v:"defense", e:"", ko:"방산·조선", en:"Defense/Ship" },
    { v:"consumer", e:"", ko:"소비재·유통", en:"Consumer" },
    { v:"chem", e:"", ko:"화학·정유", en:"Chem/Energy" },
    { v:"telecom", e:"", ko:"통신·배당", en:"Telecom/Div" },
    { v:"index", e:"", ko:"지수 ETF", en:"Index ETFs" },
    { v:"metal", e:"", ko:"금·은", en:"Gold/Silver" },
    { v:"none", e:"", ko:"아직 모르겠어요", en:"Not sure yet" },
  ]},
];

// ================= Metric explainers =================
const EXPLAIN = {
  beta:   { ko:{ name:"베타 (β)", what:"시장이 1% 움직일 때 내 포트폴리오가 몇 % 움직이는지예요.", ana:"시장을 따라 움직이는 '볼륨 다이얼'이에요. β 1.5면 시장의 움직임을 1.5배로 증폭해서 듣고, β 0.5면 절반 볼륨으로 들어요.", act:"높다고 좋은 게 아니에요. '내가 견딜 수 있는 볼륨'이 목표 범위이고, 그 안에 있으면 충분해요. β는 과거로 추정한 값이라 ±0.1~0.2 정도의 오차는 늘 있어요." },
            en:{ name:"Beta (β)", what:"How many % your portfolio moves when the market moves 1%.", ana:"A volume dial on the market. β 1.5 plays market moves amplified 1.5×; β 0.5 at half volume.", act:"Higher isn't better — stay at a volume you can bear. β is a historical estimate with ±0.1–0.2 of error built in." } },
  vol:    { ko:{ name:"변동성 (σ)", what:"1년 동안 수익률이 보통 얼마나 위아래로 출렁이는지예요.", ana:"롤러코스터의 높이차예요. 변동성 30%면 평범한 해에도 ±30%의 오르내림은 '정상 운행'이라는 뜻이에요.", act:"출렁임에 놀라 팔면 손실이 확정돼요. 견딜 수 있는 높이의 롤러코스터만 타세요." },
            en:{ name:"Volatility (σ)", what:"How much returns typically swing up and down in a year.", ana:"The height gap of a rollercoaster. 30% vol means ±30% swings are 'normal operation'.", act:"Selling in a scare locks in the loss. Ride only coasters whose drops you can stomach." } },
  effn:   { ko:{ name:"실효 종목 수", what:"비중까지 고려했을 때 실질적으로 몇 종목에 분산되어 있는지예요.", ana:"계란을 나눠 담은 바구니 수예요. 10종목을 사도 한 종목이 60%면 바구니는 사실상 2~3개뿐이에요.", act:"바구니가 많을수록 하나를 떨어뜨려도 아침식사는 지킬 수 있어요. 권장 범위까지 늘려보세요." },
            en:{ name:"Effective # of stocks", what:"How many stocks you're really diversified across, weight-adjusted.", ana:"Baskets your eggs are split into. Ten stocks with one at 60% is really 2–3 baskets.", act:"More baskets means one drop won't ruin breakfast. Work toward your recommended range." } },
  sector: { ko:{ name:"섹터 쏠림", what:"가장 큰 산업 하나가 포트폴리오에서 차지하는 비중이에요.", ana:"우산 장수와 짚신 장수 이야기예요. 비 오는 날엔 우산이, 맑은 날엔 짚신이 팔리죠. 한 산업에만 몰면 날씨(업황) 하나에 전부가 걸려요.", act:"같은 산업은 함께 오르내려요. '여러 종목'이 아니라 '여러 산업'이 진짜 분산이에요." },
            en:{ name:"Sector concentration", what:"The share of your largest single industry.", ana:"The umbrella seller and the sandal seller: umbrellas sell in rain, sandals in sun. Bet on one and everything rides on the weather (the industry cycle).", act:"Same-industry stocks move together. Real diversification is many industries, not many tickers." } },
  sharpe: { ko:{ name:"위험 대비 효율 (샤프 비율)", what:"감수한 위험(변동성) 한 단위당 무위험 이자보다 얼마나 더 벌었는지예요.", ana:"자동차의 연비예요. 위험이라는 연료 1을 태워서 초과수익이라는 거리를 얼마나 가느냐 — 같은 거리라면 연료를 덜 쓰는 차가 좋은 차죠.", act:"내 포트폴리오와 인덱스의 샤프를 비교해보세요. 인덱스보다 낮다면, 연료(위험)는 더 쓰면서 덜 가는 중이라는 뜻이에요." },
            en:{ name:"Sharpe ratio", what:"Extra return over the risk-free rate per unit of volatility.", ana:"Fuel efficiency: distance (excess return) per liter of fuel (risk). At equal distance, the thriftier car wins.", act:"Compare yours to the index. Lower means burning more fuel to travel less." } },
  r2:     { ko:{ name:"시장 동조율 (R²)", what:"내 포트폴리오 움직임 중 몇 %가 시장 전체의 흐름으로 설명되는지예요.", ana:"에스컬레이터 위에서 걷는 것과 같아요. 동조율 85%면 내 상승의 85%는 에스컬레이터(시장)가 만든 것이고, 내가 걸어 올라간 몫은 15%뿐이에요.", act:"동조율이 높은데 인덱스보다 성과가 낮다면, 비싼 수고로 인덱스를 흉내 내는 셈이에요. 그럴 바엔 인덱스가 낫죠." },
            en:{ name:"Market sync (R²)", what:"The % of your portfolio's movement explained by the overall market.", ana:"Walking on an escalator. At 85% sync, the escalator (market) does 85% of your rise; your own steps add 15%.", act:"High sync but worse than the index means imitating the index expensively. Just buy the index then." } },
  ret:    { ko:{ name:"기대수익률", what:"CAPM으로 계산한, 감수한 위험에 대해 '시장이 쳐주는' 연평균 보상이에요.", ana:"위험을 감수한 대가로 시장이 주는 '월급'이에요. 무위험 이자 + (β × 시장 위험 프리미엄).", act:"이건 약속이 아니라 장기 평균 기대치예요. 어떤 해는 훨씬 좋고 어떤 해는 훨씬 나쁠 거예요." },
            en:{ name:"Expected return", what:"The average annual compensation the market 'pays' for your risk, per CAPM.", ana:"A salary for carrying risk: risk-free rate + (β × market risk premium).", act:"A long-run average, not a promise. Some years will be far better, some far worse." } },
  cagr:   { ko:{ name:"복리 수익률 (CAGR)", what:"출렁임(변동성)의 감가를 반영한, 장기적으로 실제 쌓이는 연 수익률이에요.", ana:"지그재그로 달리는 차는 직선으로 달리는 차보다 늦게 도착해요. 변동성이 클수록 평균수익률보다 실제 복리수익률이 낮아져요 (≈ 평균 − ½σ²).", act:"변동성을 줄이는 것만으로 장기 복리 수익이 좋아질 수 있어요. 분산이 '공짜 점심'인 이유예요." },
            en:{ name:"CAGR", what:"The annual return that actually compounds long-term, after volatility drag.", ana:"A zigzagging car arrives later than one driving straight. More volatility, bigger gap below the average (≈ mean − ½σ²).", act:"Cutting volatility alone can raise long-run compounding. That's why diversification is the free lunch." } },
  per:    { ko:{ name:"PER", what:"주가가 연간 이익의 몇 배인지예요. 낮을수록 '이익 대비 싸다'는 뜻이지만…", ana:"치킨집 인수 가격이에요. 연 순이익 5천만원인 가게를 5억에 사면 PER 10 — 본전까지 10년. 그런데 올해 이익이 유난히 좋았거나 나빴다면? 착시가 생기죠.", act:"섹터마다 정상 범위가 달라요. 종목 카드의 '이 섹터를 볼 땐' 힌트를 꼭 함께 읽으세요." },
            en:{ name:"PER", what:"Price as a multiple of annual earnings. Lower looks cheaper, but…", ana:"Buying a chicken shop: ₩500m for ₩50m/yr profit is PER 10 — ten years to break even. If this year's profit was unusual, the multiple deceives.", act:"Normal ranges differ by sector — always read the sector lens hint on the stock card." } },
  alpha:  { ko:{ name:"알파 (α)", what:"위험(β)에 대한 정당한 보상을 빼고 남는 초과수익이에요. 이게 진짜 '종목 선택 실력'의 몫이죠.", ana:"에스컬레이터(시장)가 올려준 것 말고, 내 두 발로 걸어 올라간 몫이에요. 시장이 올라서 번 건 실력이 아니에요.", act:"이 도구는 '과거 알파'는 보여드리지만 '미래 알파 예측'은 보여드리지 않아요. 과거 알파가 이어질 확률은 동전 던지기에 가깝고(SPIVA), 예측 숫자는 과신만 키우거든요. 확실한 알파를 약속하는 사람은 일단 의심하세요." },
            en:{ name:"Alpha (α)", what:"Return left over after fair compensation for risk (β) — the true stock-picking skill share.", ana:"The steps you climbed yourself, beyond what the escalator (market) gave you. Market gains aren't skill.", act:"We show PAST alpha but never a forecast: past alpha persists at roughly coin-flip odds (SPIVA), and a forecast number only breeds overconfidence. Distrust anyone promising certain alpha." } },
};

// ================= i18n =================
const T = {
  appName: { ko:"뱁새", en:"Baepsae" },
  appSub: { ko:"내 그릇에 맞는 포트폴리오", en:"Risk-first portfolio" },
  tab1: { ko:"① 프로필", en:"① Profile" },
  tab2: { ko:"② 포트폴리오", en:"② Build" },
  tab3: { ko:"③ 내보내기", en:"③ Export" },
  disclaimer: { ko:"교육용 도구입니다. 투자 자문이 아니며 모든 판단과 책임은 본인에게 있습니다. 종목 데이터는 " + DATA_AS_OF + " 기준 추정치로 실시간이 아니며, 직접 수정해 쓰세요.", en:"Educational tool, not investment advice; decisions are your own. Stock data are rough estimates as of " + DATA_AS_OF + " — not live. Edit them yourself." },
  skipPreset: { ko:"질문 건너뛰고 프리셋으로 시작하기", en:"Skip questions, pick a profile" },
  presetTitle: { ko:"프로필 고르기", en:"Pick a profile" },
  presetSub: { ko:"대충 이 정도다 싶은 걸 고르세요. 세부 수치는 나중에 언제든 바꿀 수 있어요.", en:"Start from a preset; fine-tune anytime." },
  profileTitle: { ko:"나의 투자 프로필", en:"My Investor Profile" },
  capacity: { ko:"위험 감수 능력", en:"Risk capacity" },
  tolerance: { ko:"위험 감수 의지", en:"Risk tolerance" },
  need: { ko:"필요 수익률", en:"Required return" },
  capacityHint: { ko:"능력 = 잃어도 되는가 (형편)", en:"Ability (circumstances)" },
  toleranceHint: { ko:"의지 = 견딜 수 있는가 (마음)", en:"Willingness (psychology)" },
  needHint: { ko:"목표 달성에 필요한 수익률", en:"Return the goal requires" },
  targetBeta: { ko:"목표 베타", en:"Target beta" },
  targetVol: { ko:"변동성 상한", en:"Vol ceiling" },
  numStocks: { ko:"권장 종목 수", en:"# of stocks" },
  maxPos: { ko:"종목당 최대", en:"Max/stock" },
  maxSector: { ko:"섹터당 최대", en:"Max/sector" },
  redo: { ko:"질문 다시 답하기", en:"Redo questions" },
  edit: { ko:"수정", en:"Edit" }, save: { ko:"저장", en:"Save" }, cancel: { ko:"취소", en:"Cancel" },
  goBuild: { ko:"포트폴리오 만들러 가기 →", en:"Go build the portfolio →" },
  budget: { ko:"투자 예산", en:"Budget" },
  manwon: { ko:"만원", en:"×₩10k" },
  shelf: { ko:"종목 고르기", en:"Pick Stocks" },
  searchPh: { ko:"종목명·코드 검색", en:"Search name/ticker" },
  all: { ko:"전체", en:"All" },
  add: { ko:"담기", en:"Add" }, added: { ko:"담김", en:"Added" },
  addCustom: { ko:"+ 직접 종목 추가", en:"+ Add custom stock" },
  myShip: { ko:"내 포트폴리오", en:"My Portfolio" },
  emptyCart: { ko:"아직 비어 있어요. 아래에서 종목을 담아보세요.", en:"Empty for now. Add stocks from the list below." },
  cash: { ko:"남는 현금 (무위험)", en:"Cash left (risk-free)" },
  overBudget: { ko:"예산 초과!", en:"Over budget!" },
  weight: { ko:"비중", en:"Weight" },
  dash: { ko:"리스크 계기판", en:"Risk Dashboard" },
  dashSub: { ko:"초록 구간 = 내 프로필의 목표", en:"Green zone = your profile targets" },
  railBeta: { ko:"베타 · 시장 대비 민감도", en:"Beta · market sensitivity" },
  railVol: { ko:"변동성 · 연간 출렁임", en:"Volatility · yearly swings" },
  railEffn: { ko:"실효 종목 수 · 진짜 분산", en:"Effective stocks · true spread" },
  railSector: { ko:"섹터 쏠림 · 최대 산업 비중", en:"Sector · top-industry weight" },
  railRemaining: { ko:"남은 예산이 맞춰야 할 β", en:"β the remaining budget must hit" },
  railImpossible: { ko:"남은 예산만으론 목표 β에 못 미쳐요. β 높은 종목을 늘리거나 목표를 낮춰보세요.", en:"Remaining budget alone can't reach target β. Add higher-β names or lower the target." },
  good: { ko:"좋아요", en:"Good" }, warn: { ko:"주의", en:"Watch" },
  score: { ko:"포트폴리오 건강 점수", en:"Portfolio health" },
  scoreGood: { ko:"탄탄하게 가고 있어요", en:"Looking solid" },
  scoreMid: { ko:"조금만 다듬어 볼까요?", en:"A little trimming?" },
  scoreBad: { ko:"점검이 필요해요", en:"Needs a check-up" },
  metrics: { ko:"핵심 지표", en:"Key Metrics" },
  mBeta: { ko:"포트폴리오 베타", en:"Portfolio beta" },
  mRet: { ko:"기대수익률", en:"Expected return" },
  mVol: { ko:"변동성 (연)", en:"Volatility (yr)" },
  mSharpe: { ko:"위험 대비 효율(샤프)", en:"Sharpe" },
  mCagr: { ko:"복리 수익률(CAGR)", en:"CAGR" },
  mR2: { ko:"시장 동조율 R²", en:"Market sync R²" },
  mAl: { ko:"과거 3y 알파(추정)", en:"Past 3y α (est.)" },
  mEffN: { ko:"실효 종목 수", en:"Effective stocks" },
  mSector: { ko:"최대 섹터", en:"Top sector" },
  mPer: { ko:"가중 PER", en:"Wtd PER" },
  mDy: { ko:"가중 배당", en:"Wtd dividend" },
  betaErr: { ko:"β·σ는 과거 추정치 — ±오차가 늘 있어요. '점'이 아니라 '근처'로 읽으세요.", en:"β and σ are historical estimates with real error — read them as 'around there', not points." },
  stress: { ko:"스트레스 테스트 (원화 기준)", en:"Stress Test (in KRW)" },
  stressBad: { ko:"운 나쁜 해 (20년에 1번)", en:"A bad year (1-in-20)" },
  stressCrisis: { ko:"2008년급 위기 (시장 −40%)", en:"A 2008-scale crisis (−40%)" },
  stressNote: { ko:"이 금액을 보고도 잠이 온다면, 이 구성으로 오래 갈 수 있어요. 그게 수익률보다 중요해요.", en:"If you can sleep seeing these numbers, you can stay the course. That matters more than returns." },
  insights: { ko:"인사이트", en:"Insights" },
  riskContrib: { ko:"돈의 비중 ≠ 위험의 비중", en:"Money weight ≠ risk weight" },
  moneyBase: { ko:"돈 기준", en:"By money" },
  riskBase: { ko:"위험 기준", en:"By risk" },
  goalGap: { ko:"목표와의 거리", en:"Distance to Goal" },
  projection: { ko:"장기 전망", en:"Long-run Outlook" },
  projSub: { ko:"미래는 점이 아니라 부채꼴이에요. 통계적 범위(10~90% 구간)로 보세요.", en:"The future is a fan, not a point. Read it as a 10–90% statistical range." },
  divIncome: { ko:"연간 배당 (예상)", en:"Annual dividends (est.)" },
  bench: { ko:"냉정하게 비교하면", en:"Honest Benchmark" },
  benchIdx: { ko:"KODEX 200 인덱스", en:"KODEX 200 index" },
  benchRobo: { ko:"로보라면 이렇게", en:"What a robo would do" },
  mine: { ko:"내 포트폴리오", en:"Mine" },
  benchNote: { ko:"장기 통계상 대부분의 개인은 인덱스를 이기지 못해요 (Barber-Odean, DALBAR). 이 표에서 밀린다면, 그래도 이 구성을 고른 나만의 이유를 한 문장으로 말할 수 있어야 해요.", en:"Long-run evidence says most individuals fail to beat the index (Barber-Odean, DALBAR). If you trail here, you should still be able to state your reason in one sentence." },
  alerts: { ko:"경고", en:"Alerts" },
  noAlerts: { ko:"모든 계기가 초록불이에요! 오늘도 무리하지 않기 ", en:"All gauges green! Nothing overstretched today " },
  wOverBudget: { ko:"예산을 초과했어요", en:"Over budget" },
  wBetaHigh: { ko:"베타가 목표보다 높아요", en:"Beta above target" },
  wBetaLow: { ko:"베타가 목표보다 낮아요 (더 보수적)", en:"Beta below target (more conservative)" },
  wVol: { ko:"변동성이 상한을 넘어요", en:"Volatility over ceiling" },
  wPos: { ko:"종목 쏠림", en:"Position too large" },
  wSector: { ko:"섹터 쏠림", en:"Sector too concentrated" },
  wCount: { ko:"종목 수가 권장보다 적어요", en:"Fewer stocks than recommended" },
  settings: { ko:"시장 가정", en:"Market Assumptions" },
  rf: { ko:"무위험 이자율 (국고채 10년)", en:"Risk-free (10y KTB)" },
  rfTip: { ko:"한국 관행은 3년물이지만, 장기 투자 기간과 맞추려면 10년물이 이론적으로 더 적합해요.", en:"Korean convention quotes the 3y, but the 10y better matches a long horizon." },
  mrp: { ko:"시장 위험 프리미엄", en:"Market risk premium" },
  mktVol: { ko:"시장(코스피) 변동성", en:"Market (KOSPI) vol" },
  dataBadge: { ko:DATA_AS_OF + " 추정 · 수정 가능", en:"est. " + DATA_AS_OF + " · editable" },
  logTitle: { ko:"요약 · 내보내기", en:"Summary & Export" },
  logHint: { ko:"아래 목록을 확인하고, 증권사 앱에서 직접 주문하세요. 뱁새는 주문을 실행하지 않아요.", en:"Review the list, then place orders yourself in your brokerage app. Baepsae never executes trades." },
  checklist: { ko:"주문 전 마음 점검", en:"Pre-order mind check" },
  chk1: { ko:"친구의 수익 자랑을 듣고 담은 종목이 있나요?", en:"Any stock added because of a friend's bragging?" },
  chk2: { ko:"이 중 한 종목이 −40%가 되어도 계획대로 들고 갈 수 있나요?", en:"If one stock drops −40%, can you hold as planned?" },
  chk3: { ko:"이 구성이 인덱스보다 나은 이유를 한 문장으로 말할 수 있나요?", en:"Can you state in one sentence why this beats the index?" },
  chk4: { ko:"최근 급등했다는 이유만으로 담은 종목은 없나요?", en:"Nothing added just because it surged recently?" },
  chk5: { ko:"①에서 답한 목표와 지금 구성이 서로 맞나요?", en:"Does this match the goal you wrote in ①?" },
  alphaCard: { ko:"마지막 수업: 알파 이야기", en:"Last lesson: about alpha" },
  dlJson: { ko:"JSON 저장 (백업·공유)", en:"Save JSON (backup/share)" },
  dlCsv: { ko:"CSV 저장 (주문표)", en:"Save CSV (order sheet)" },
  copyText: { ko:"텍스트 복사 (주문 메모)", en:"Copy text (order memo)" },
  copied: { ko:"복사됨!", en:"Copied!" },
  reset: { ko:"전체 초기화", en:"Reset all" },
  resetConfirm: { ko:"프로필과 포트폴리오를 모두 지울까요?", en:"Delete profile and portfolio?" },
  name: { ko:"종목명", en:"Name" }, ticker: { ko:"코드", en:"Ticker" }, sector: { ko:"섹터", en:"Sector" },
  price: { ko:"현재가(원)", en:"Price" }, amount: { ko:"금액", en:"Amount" },
  needProfile: { ko:"먼저 ① 프로필을 마치면 목표 범위가 계기판에 표시돼요.", en:"Finish ① Profile first — targets will appear on the dashboard." },
  lensTitle: { ko:"이 섹터를 볼 땐", en:"Sector lens" },
  peers: { ko:"같은 섹터 비교", en:"Sector peers" },
  editData: { ko:"데이터 수정", en:"Edit data" },
  mcap: { ko:"시가총액", en:"Mkt cap" }, roe: { ko:"ROE", en:"ROE" }, opm: { ko:"영업이익률", en:"Op margin" },
  g3: { ko:"매출성장(3y)", en:"Rev growth 3y" }, debt: { ko:"부채비율", en:"Debt ratio" }, frn: { ko:"외국인", en:"Foreign" },
  w52: { ko:"52주 범위", en:"52w range" },
  jo: { ko:"조", en:"T KRW" },
  lvl: { ko:["새싹 투자자","꾸준한 모으기","균형 투자자","리스크 관리자","뱁새 마스터"], en:["Sprout","Steady Saver","Balanced Investor","Risk Manager","Baepsae Master"] },
  gapShort: { ko:(need,ret,gap)=>`목표(연 ${need}%)까지 지금 구성의 기대수익(연 ${ret}%)으로는 연 ${gap}%p가 모자라요. 목표·기간·저축액 중 하나는 조정이 필요해요 — 무리하게 위험을 키우는 건 답이 아니에요.`, en:(need,ret,gap)=>`Your goal (${need}%/yr) is ${gap}%p beyond this mix's expected return (${ret}%/yr). Adjust the goal, horizon, or savings — stretching for more risk is not the answer.` },
  gapOk: { ko:(need,ret)=>`지금 구성의 기대수익(연 ${ret}%)이면 목표(연 ${need}%)에 닿을 수 있어요. 꾸준히 유지하는 게 최고의 전략이에요.`, en:(need,ret)=>`This mix's expected return (${ret}%/yr) can reach your goal (${need}%/yr). Staying the course is the best strategy.` },
  tagline: { ko:"황새 말고, 내 걸음으로", en:"Not the stork's pace — your own" },
  s1: { ko:"① 프로필", en:"① Profile" },
  s2: { ko:"② 구성", en:"② Build" },
  s3: { ko:"③ 진단", en:"③ Diagnose" },
  s4: { ko:"④ 내보내기", en:"④ Export" },
  modeSimple: { ko:"간단히", en:"Simple" },
  modeDetail: { ko:"자세히", en:"Detail" },
  goDiagnose: { ko:"진단 보러 가기 →", en:"See diagnosis →" },
  diagTitle: { ko:"진단 — 내 포트폴리오 해부", en:"Diagnosis — under the hood" },
  diagEmpty: { ko:"② 구성에서 종목을 담으면 진단이 열려요.", en:"Add stocks in ② Build to unlock the diagnosis." },
  secAnatomy: { ko:"위험 해부", en:"Risk Anatomy" },
  secProb: { ko:"확률로 보기", en:"In Probabilities" },
  secSim: { ko:"시뮬레이션", en:"Simulations" },
  secCompare: { ko:"비교와 목표", en:"Benchmarks & Goal" },
  probTitle: { ko:"원금을 지킬 수 있을까?", en:"Will the principal survive?" },
  probLoss: { ko:"손실로 끝날 확률", en:"Chance of ending in loss" },
  probGoal: { ko:"목표 달성 확률", en:"Chance of reaching the goal" },
  probSub: { ko:"기간을 바꿔보세요 — 시간이 확률을 어떻게 바꾸는지가 핵심이에요.", en:"Switch the horizon — how time reshapes the odds is the whole lesson." },
  varTitle: { ko:"최악의 해는 얼마나 아플까?", en:"How much would a worst year hurt?" },
  varBad: { ko:"나쁜 해 (하위 5% 경계, VaR)", en:"Bad year (5% VaR)" },
  varWorse: { ko:"그보다 나쁠 때 평균 (CVaR)", en:"Average beyond it (CVaR)" },
  varNote: { ko:"실제 시장은 정규분포보다 꼬리가 두꺼워요 — 폭락은 계산보다 자주 옵니다. 이 숫자는 '최소 이 정도' 각오로 읽으세요.", en:"Real markets have fatter tails than the normal curve — crashes come more often than computed. Read these as 'at least this much'." },
  divTitle: { ko:"분산의 공짜 점심", en:"Diversification's free lunch" },
  divNone: { ko:"종목이 하나뿐이라 분산 효과가 아직 없어요. 두 번째 바구니부터 공짜 점심이 시작돼요.", en:"Only one stock, so no diversification effect yet. The free lunch starts with basket #2." },
  donutTitle: { ko:"무엇을 들고 있나요", en:"What you actually hold" },
  splitTitle: { ko:"수익으로 돌려받는 위험 vs 그냥 떠안은 위험", en:"Risk that pays you back vs risk you just carry" },
  splitSub: { ko:"파란 부분(시장 위험)만 기대수익으로 돌려받아요. 주황 부분(개별 위험)은 시장이 한 푼도 쳐주지 않는데 내가 그냥 떠안고 있는 위험이에요 — 나눠 담으면 지울 수 있어요.", en:"Only the blue part (market risk) pays you back as expected return. The orange part (specific risk) pays nothing — you are simply carrying it, and splitting your money can erase it." },
  splitComp: { ko:"돌려받는 위험 (시장)", en:"Paid risk (market)" },
  splitIdio: { ko:"떠안은 위험 (개별)", en:"Unpaid risk (specific)" },
  splitFair: { ko:"적정 기대수익", en:"Fair E(r)" },
  quickTitle: { ko:"핵심 숫자만", en:"Quick Facts" },
  qTop3: { ko:"상위 3종목 비중", en:"Top-3 weight" },
  qDiv: { ko:"연 배당 (예상·세전)", en:"Annual dividends (est., pre-tax)" },
  qCash: { ko:"현금 비중", en:"Cash share" },
  whatifTitle: { ko:"만약에 실험실", en:"What-if Lab" },
  wiMkt: { ko:"시장(코스피)이 이만큼 움직이면", en:"If the market moves this much" },
  wiMine: { ko:"내 포트폴리오는 약", en:"My portfolio moves about" },
  wiIdio: { ko:"개별 위험 때문에 실제론 이 근처 어딘가예요", en:"Specific risk puts you somewhere around this" },
  wiSector: { ko:"최대 섹터가 −30% 나쁜 해를 보내면", en:"If your top sector has a −30% year" },
  wiStock: { ko:"가장 큰 종목이 반토막(−50%) 나면", en:"If your biggest holding halves (−50%)" },
  wiOneN: { ko:"같은 종목을 그냥 1/N씩 담았다면", en:"Same stocks, naive 1/N weights" },
  tmTitle: { ko:"타임머신 — 폭락을 미리 살아보기", en:"Time Machine — live a crash in advance" },
  tmPlay: { ko:"▶ 재생", en:"▶ Play" },
  tmPause: { ko:"일시정지", en:"Pause" },
  tmReset: { ko:"↺ 처음부터", en:"↺ Reset" },
  tmHeld: { ko:"끝까지 버텼다면", en:"If you held to the end" },
  tmSold: { ko:"최저점에서 팔았다면", en:"If you sold at the bottom" },
  tmDiff: { ko:"버틴 값어치", en:"What holding was worth" },
  tmNote: { ko:"실제 코스피 월별 흐름에 내 β와 개별 위험을 입힌 시뮬레이션이에요. 과거가 미래를 보장하진 않지만, '견디는 감각'은 미리 연습할 수 있어요.", en:"A simulation: the real KOSPI monthly path wearing your β and specific risk. The past guarantees nothing — but the feel of holding on can be rehearsed." },
  oneN: { ko:"1/N 균등 분할", en:"Naive 1/N split" },
  oneNNote: { ko:"재미있는 사실: 학계 실험에서 단순 1/N이 정교한 최적화 14종을 이긴 적이 있어요 (DeMiguel 외). 복잡함이 늘 이기는 건 아니에요.", en:"Fun fact: in academic tests, naive 1/N beat fourteen sophisticated optimizers (DeMiguel et al.). Complexity doesn't always win." },
  chkTitle: { ko:"간단 체크리스트 (추천 아님)", en:"Quick checklist (not a recommendation)" },
  chkNote: { ko:"'좋은 편'은 같은 섹터 안에서의 상대 비교일 뿐이에요. 매수 추천이 아니라 질문의 시작점으로 쓰세요.", en:"'Good' means relative to sector peers only. A starting point for questions — not a buy signal." },
  chkProfit: { ko:"수익성 (ROE)", en:"Profitability (ROE)" },
  chkSafety: { ko:"재무 안정성 (부채)", en:"Balance-sheet safety (debt)" },
  chkValue: { ko:"밸류에이션 (PER)", en:"Valuation (PER)" },
  chkNoPeers: { ko:"비교군이 부족해요", en:"Not enough peers" },
  betaBand: { ko:"파란 띠 = β 추정 오차 범위(±0.15). '점'이 아니라 '구간'으로 읽으세요.", en:"Blue band = β estimation error (±0.15). Read a range, not a point." },
  attrMap: { ko:"나의 투자 성향 지도", en:"My Investor Map" },
  avg5: { ko:"점선 = 중간(5점)", en:"Dashed line = midpoint (5)" },
  tipsTitle: { ko:"만들 때 이것만은", en:"Watch-outs while building" },
  checkFreqL: { ko:"점검 주기", en:"Review cadence" },
  cashFloorL: { ko:"권장 최소 현금", en:"Cash floor" },
  interestL: { ko:"관심 분야", en:"Interests" },
  chipHint: { ko:"해당하는 걸 모두 골라주세요 (여러 개 OK)", en:"Pick all that apply (multiple OK)" },
  wCashFloor: { ko:"현금이 권장 최소보다 적어요", en:"Cash below suggested floor" },
  rjSep: { ko:"따로따로 들었다면", en:"If held separately" },
  rjErased: { ko:"나눠 담아 사라진 위험", en:"Erased by diversifying" },
  rjNow: { ko:"지금 포트폴리오", en:"Your portfolio now" },
  rjAction: { ko:"그래서, 뭘 하면 좋을까요?", en:"So what should I do?" },
  rjGood: { ko:"지금은 꽤 효율적이에요. 떠안은 위험이 20% 아래면 잘 짜인 포트폴리오예요 — 이 균형을 유지하는 게 할 일의 전부예요.", en:"Quite efficient already — unpaid risk under 20% marks a well-built portfolio. Keeping this balance is the whole job." },
  rjDetails: { ko:"종목별로 뜯어보기", en:"Per-stock breakdown" },
  rjZig: { ko:"반대로 출렁이는 두 종목을 합치면, 출렁임이 서로를 지워요. 위험이 '공짜로' 줄어드는 원리예요 — 경제학에서는 이걸 공짜 점심이라고 불러요.", en:"Two holdings that zig oppositely cancel each other's swings — risk shrinks 'for free'. Economists call this the free lunch." },
  secAlpha: { ko:"알파 — 시장을 이긴다는 것", en:"Alpha — beating the market" },
  alTitle: { ko:"내 포트폴리오의 알파", en:"My portfolio's alpha" },
  alPast: { ko:"과거 3년 알파 (추정)", en:"Past 3y alpha (est.)" },
  alCaveat: { ko:"과거값이에요 — 미래를 보장하지 않아요", en:"A past value — no promise about the future" },
  alSpace: { ko:"알파가 나올 공간 (트래킹 에러)", en:"Room for alpha (tracking error)" },
  alSpaceLow: { ko:"인덱스와 거의 똑같이 움직이고 있어요. 알파가 나올 공간 자체가 작아요 — 이럴 바엔 인덱스 펀드가 더 싸고 편해요.", en:"You move almost exactly with the index — little room for alpha either way. An index fund would be cheaper and easier." },
  alSpaceHigh: { ko:"인덱스와 꽤 다르게 움직여요. 플러스 알파도, 마이너스 알파도 나올 수 있는 구조예요.", en:"You move quite differently from the index — room for alpha, positive or negative." },
  alPersist: { ko:"참고로, 과거 알파가 앞으로도 이어질 확률은 통계적으로 동전 던지기에 가까워요 (SPIVA 지속성 연구).", en:"Note: the odds that past alpha persists are statistically close to a coin flip (SPIVA persistence studies)." },
  alGrow: { ko:"내 알파는 어디서 나올 수 있을까?", en:"Where could my alpha come from?" },
  alTop: { ko:"알파 기여 상위 (과거 기준)", en:"Top alpha contributors (past)" },
  lgTitle: { ko:"전설들과 나란히 세워보면", en:"Lined up with the legends" },
  lgNote: { ko:"버핏의 비결은 천재적인 종목 선택만이 아니었어요 — 흔들림 적은 저베타 우량주 + 보험사를 통한 안전한 레버리지 + 60년을 버틴 시간이었죠 ('Buffett's Alpha', Frazzini 외). 그리고 15년 기준, 액티브 펀드의 약 90%는 인덱스를 못 이겨요 (SPIVA).", en:"Buffett's edge wasn't only genius picks — steady low-beta quality + safe insurance-float leverage + sixty years of holding ('Buffett's Alpha', Frazzini et al.). And over 15 years, ~90% of active funds trail the index (SPIVA)." },
  mktAll: { ko:"전체", en:"All" },
  chipOne: { ko:"하나만 골라주세요", en:"Pick one" },
  tapNeeded: { ko:"탭으로 고르는 질문에 모두 답하면 결과를 볼 수 있어요.", en:"Answer every tap question to see your result." },
  seeResult: { ko:"내 프로필 보기", en:"See my profile" },
  demo: { ko:"예시 포트폴리오로 둘러보기", en:"Try a sample portfolio" },
  lt1: { ko:"위험 효율", en:"Risk efficiency" },
  lt2: { ko:"업종 쏠림", en:"Sector concentration" },
  lt3: { ko:"목표와의 거리", en:"Distance to goal" },
  oneAction: { ko:"먼저 이것부터", en:"Start with this" },
  sxA: { ko:"내 위험은 보상받고 있나요?", en:"Is my risk being paid for?" },
  sxAs: { ko:"돌려받는 위험과 그냥 떠안은 위험, 그리고 할 일", en:"Paid vs unpaid risk, and what to do" },
  sxB: { ko:"나는 무엇을 들고 있나요?", en:"What am I actually holding?" },
  sxBs: { ko:"자산군·업종 구성과 위험의 출처", en:"Asset classes, sectors, and where risk comes from" },
  sxC: { ko:"폭락하면 얼마나 잃나요?", en:"How much would a crash cost?" },
  sxCs: { ko:"최악의 해, 그리고 원금을 지킬 확률", en:"Worst years and the odds of keeping your principal" },
  sxD: { ko:"시장을 이길 수 있을까요?", en:"Can I beat the market?" },
  sxDs: { ko:"알파, 그리고 전설들과의 비교", en:"Alpha, and how the legends compare" },
  sxE: { ko:"직접 실험해볼까요?", en:"Want to experiment?" },
  sxEs: { ko:"만약에 실험실과 폭락 타임머신", en:"What-if lab and the crash time machine" },
  sxF: { ko:"목표까지 갈 수 있을까요?", en:"Will I reach the goal?" },
  sxFs: { ko:"장기 전망과 인덱스 비교", en:"Long-run outlook and index comparison" },
  ciTitle: { ko:"점검 기록", en:"Check-in log" },
  ciSave: { ko:"지금 상태 기록", en:"Record now" },
  ciEmpty: { ko:"아직 기록이 없어요. 지금 상태를 기록해두면, 다음에 왔을 때 무엇이 어떻게 달라졌는지 보여드릴게요.", en:"No records yet. Save today's state and next time we'll show exactly what changed." },
  ciSince: { ko:"지난 기록:", en:"Last record:" },
  ciAmount: { ko:"투자 금액", en:"Invested" },
  ciCount: { ko:"종목 수", en:"Holdings" },
  credit: { ko:"만든 사람 · 이성진, INSEAD MBA 26J", en:"Created by Jack (Sung Jin) Lee, INSEAD MBA 26J" },
  autoTag: { ko:"자동", en:"live" },
  assumeTag: { ko:"가정", en:"assumption" },
  mrpScenTip: { ko:"위험 프리미엄은 관측되는 값이 아니라 '가정'이에요. 최근 수익률로 자동 계산하면, 많이 오른 뒤에 오히려 더 낙관적으로 잡히는 함정이 있어서 직접 고르게 해뒀어요.", en:"The risk premium is an assumption, not an observation. Auto-fitting it to recent returns would turn optimistic right after a run-up — so you choose it." },
  mrpLow: { ko:"보수", en:"Cautious" }, mrpBase: { ko:"기본", en:"Base" }, mrpHigh: { ko:"낙관", en:"Optimistic" },
  setInfl: { ko:"물가", en:"Inflation" },
  inflL: { ko:"예상 물가상승률", en:"Expected inflation" },
  inflTip: { ko:"장기 전망을 '실질 기준'으로 볼 때 빼는 값이에요. 목표는 결국 돈의 액수가 아니라 살 수 있는 물건의 양이니까요.", en:"Subtracted when viewing the outlook in real terms — the goal is purchasing power, not a nominal number." },
  realBtn: { ko:"실질", en:"Real" },
  realNote: { ko:"물가를 뺀 실질 기준이에요", en:"in real (inflation-adjusted) terms" },
  sortBy: { ko:"정렬", en:"Sort" },
  sortPop: { ko:"인기", en:"Popular" }, sortSh: { ko:"샤프", en:"Sharpe" }, sortAl: { ko:"알파", en:"Alpha" },
  sortDy: { ko:"배당", en:"Dividend" }, sortCap: { ko:"시총", en:"Mkt cap" }, sortMdd: { ko:"낙폭 적은", en:"Least drawdown" },
  sortShNote: { ko:"과거 3년 기준이에요. 과거에 효율이 좋았다고 앞으로도 좋다는 뜻은 아니에요 — 오히려 많이 오른 뒤엔 기대수익이 낮아지는 경우가 많아요.", en:"Based on the past 3 years. Past efficiency doesn't predict future efficiency — after a big run, expected returns are often lower." },
  shPast: { ko:"샤프(3y)", en:"Sharpe 3y" },
  shCapm: { ko:"이론 샤프", en:"CAPM Sharpe" },
  mddL2: { ko:"최대낙폭", en:"Max DD" },
  momL: { ko:"12개월", en:"12mo" },
  mddL: { ko:"내 종목들의 3년 최대낙폭 (가중평균)", en:"Holdings' 3y max drawdown (wtd avg)" },
  hitL: { ko:"오른 달의 비율 (가중평균)", en:"Share of up months (wtd avg)" },
  alIR: { ko:"이 알파는 실력일까, 운일까", en:"Skill or luck?" },
  recTitle: { ko:"이렇게 하면 맞춰져요", en:"How to bring it in line" },
  recApply: { ko:"이대로 적용하기", en:"Apply this" },
  recApplied: { ko:"적용했어요", en:"Applied" },
  recUndo: { ko:"되돌리기", en:"Undo" },
  recMoves: { ko:"바뀌는 금액", en:"Amounts that change" },
  recNote: { ko:"수학적으로 목표 범위에 들어오는 조정안이에요. 좋은 투자라는 뜻은 아니고, 종목의 좋고 나쁨은 전혀 판단하지 않았어요.", en:"These are arithmetic adjustments that bring you into range. They are not investment advice and make no judgement about any stock." },
  rjWhere: { ko:"다른 사람들과 비교하면", en:"Where this sits" },
  rjAnchor: { ko:"인덱스만 사면 0%, 한 종목만 들면 60~70%예요. 개인 포트폴리오는 보통 10~25% 사이에 있어요.", en:"Index-only is 0%; a single stock is 60–70%. Most individual portfolios land between 10% and 25%." },
  rjZeroTitle: { ko:"0%가 목표는 아니에요", en:"Zero is not the goal" },
  rjZeroBody: { ko:"0%는 인덱스를 그대로 사는 것과 같아요. 종목을 직접 고르는 순간 이 비율은 반드시 올라가고, 그건 잘못이 아니에요 — 시장을 이겨보려면 내야 하는 입장료예요. 다만 '내가 이 회사를 남보다 잘 안다'는 근거가 있을 때만 값어치가 있어요. 그 근거가 실제로 있었는지는 '알파' 섹션에서 확인해볼 수 있어요.", en:"Zero means simply buying the index. The moment you pick individual companies this rises — and that's not a mistake, it's the admission fee for trying to beat the market. It only pays off if you genuinely know something others don't, which the alpha section puts to the test." },
  sxW: { ko:"내가 잘하고 있는 것", en:"What I'm doing right" },
  sxWs: { ko:"이미 지켜낸 것들과 그 값어치", en:"What you've already got right, and what it's worth" },
  sxR: { ko:"내 수익은 어디서 나오나요?", en:"Where do my returns come from?" },
  sxRs: { ko:"기대수익의 출처와 배당", en:"Sources of expected return, and dividends" },
  wdTitle: { ko:"잘하고 있는 것", en:"Going right" },
  wdTodo: { ko:"아직 남은 것", en:"Still open" },
  raTitle: { ko:"내 수익은 어디서 나오나요", en:"Where returns come from" },
  raSub: { ko:"기대수익은 '가만히 둬도 받는 이자'와 '위험을 감수한 대가'로 나뉘어요.", en:"Expected return splits into the interest you'd get anyway and the reward for taking risk." },
  raByCls: { ko:"자산군별 기여", en:"Contribution by asset class" },
  raTop: { ko:"기대수익 기여 상위", en:"Top contributors" },
  raVerdict: { ko:"배당은 시장이 어떻든 실제로 통장에 들어오는 몫이고, 나머지는 주가가 올라야 생기는 몫이에요. 둘의 비율이 곧 '기다릴 수 있는 힘'을 결정해요.", en:"Dividends actually arrive regardless of the market; the rest requires prices to rise. That ratio determines how long you can wait." },
  ftTitle: { ko:"내 포트폴리오의 성향 (팩터)", en:"My portfolio's tilts (factors)" },
  ftSub: { ko:"같은 '주식'이라도 어떤 성격의 주식을 모았는지가 성과를 크게 갈라요. 시장 평균과 비교한 위치예요.", en:"Which kind of stocks you own drives much of the outcome. This shows your position against the market average." },
  ftNone: { ko:"성향을 계산할 데이터가 아직 부족해요. 시세 데이터가 갱신되면 표시됩니다.", en:"Not enough data yet — this appears once live data is in place." },
  ftNote: { ko:"보유 종목의 특성(시가총액·PBR·12개월 수익률·ROE)을 시장 내 백분위로 환산해 가중평균한 값이에요. 정식 팩터 회귀분석 결과는 아니에요.", en:"A weighted average of holdings' characteristic percentiles (size, PBR, 12-month return, ROE) — not a formal factor regression." },
  srTitle: { ko:"순서의 위험 — 언제 나쁜 해가 오는가", en:"Sequence risk — when the bad years hit" },
  srSub: { ko:"돈을 빼 쓰는 동안에는, 평균 수익률이 같아도 '나쁜 해가 먼저 오는지'에 따라 결과가 크게 달라져요.", en:"While withdrawing, identical average returns produce very different outcomes depending on whether the bad years come first." },
  srRate: { ko:"매년 빼 쓸 비율", en:"Annual withdrawal" },
  srGood: { ko:"좋은 해가 먼저 왔다면", en:"Good years first" },
  srBad: { ko:"나쁜 해가 먼저 왔다면", en:"Bad years first" },
  srNote: { ko:"같은 수익률 묶음의 순서만 바꿔 계산한 시뮬레이션이에요. 은퇴 직후 몇 년이 특히 중요한 이유이고, 그래서 그 시기엔 위험을 줄이는 게 일반적인 조언이에요.", en:"A simulation using the same set of returns in different orders. This is why the first years of retirement matter so much, and why reducing risk then is standard advice." },
  tabPop: { ko:"인기", en:"Popular" },
  tabFav: { ko:"관심", en:"My picks" },
  tabSec: { ko:"업종별", en:"By sector" },
  popNote: { ko:"거래대금·시가총액 기준이에요. 많이 거래된다고 좋은 종목은 아니에요 — 그냥 눈에 많이 띄는 종목일 뿐이에요.", en:"Ranked by turnover and market cap. Heavily traded doesn't mean good — just visible." },
  noHit: { ko:"찾는 종목이 없어요. 코드(예: 005930, AAPL)로도 찾아보세요.", en:"No match. Try the ticker (e.g. 005930, AAPL)." },
  more50: { ko:"상위 50개만 보여드려요. 더 좁혀서 검색해보세요.", en:"Showing the top 50 — narrow your search." },
  slotExit: { ko:"저장하고 나가기", en:"Save and exit" },
  taxTitle: { ko:"세금", en:"Taxes" },
  taxYear: { ko:"예상 세금", en:"Estimated tax" },
  taxNet: { ko:"세후 기대수익", en:"After-tax return" },
  taxDivKr: { ko:"국내 배당소득세", en:"KR dividend tax" },
  taxDivUs: { ko:"해외 배당 원천징수", en:"US dividend withholding" },
  taxGainUs: { ko:"해외주식 양도소득세", en:"Foreign capital gains" },
  taxNote: { ko:"2026-01 기준 추정이며 세무 자문이 아니에요. 국내주식 매매차익은 소액주주라면 비과세, 해외주식은 연 250만원 공제 후 22%예요. 국내 상장 채권 ETF의 매매차익은 배당소득세 15.4% 대상이라 아래 계산과 달라요. 금융소득이 연 2,000만원을 넘으면 종합과세 대상이 될 수 있어요. 실제 세액은 개인 상황에 따라 달라지니 확정 신고 전엔 전문가와 확인하세요.", en:"Estimates as of 2026-01, not tax advice. Domestic stock gains are untaxed for most retail investors; foreign gains are taxed at 22% above a ₩2.5m annual deduction. Financial income above ₩20m/yr may trigger comprehensive taxation. Confirm with a professional." },
  fxTitle: { ko:"환전 안내", en:"Currency exchange" },
  fxNeed: { ko:"필요한 달러", en:"USD needed" },
  fxFee: { ko:"환전 수수료", en:"FX fee" },
  fxCost: { ko:"환전에 드는 원화", en:"KRW required" },
  fxNote: { ko:"증권사마다 환전 우대율이 달라요(보통 0.1~1%). 미리 환전해두거나 통합증거금을 쓰면 수수료를 줄일 수 있어요.", en:"FX spreads vary by broker (typically 0.1–1%). Pre-converting or using an integrated margin account can reduce the cost." },
  setTax: { ko:"세금 (2026-01 기준 · 수정 가능)", en:"Taxes (as of 2026-01, editable)" },
  amTitle: { ko:"자산군 배분", en:"Asset-class mix" },
  fxExp: { ko:"달러 노출", en:"USD exposure" },
  amUsHedge: { ko:"미국 주식은 달러로 사죠. 위기가 오면 원달러 환율이 오르는 편이라, 주가가 빠져도 환차익이 손실을 일부 메워줘요. 한국 투자자에게 미국 주식이 '자연 헤지'가 되는 이유예요.", en:"US stocks are bought in dollars. In a crisis the won usually weakens, so FX gains offset part of the price drop — this is why US equity acts as a natural hedge for a Korean investor." },
  amHedge: { ko:"금·은이 실제로 깎아준 위험", en:"What the metals actually removed" },
  amNoMetal: { ko:"금·은이 없었다면", en:"Without metals" },
  amWithMetal: { ko:"지금 (금·은 포함)", en:"Now (with metals)" },
  amNoEffect: { ko:"비중이 작아 아직 눈에 띄는 효과는 없어요. 보통 5~10%부터 체감되기 시작해요.", en:"The weight is still small, so the effect is minimal — it usually starts to show around 5–10%." },
  setBasic: { ko:"기본", en:"Basics" },
  setKr: { ko:"한국 주식 시장", en:"Korean equity" },
  setUs: { ko:"미국 주식 시장", en:"US equity" },
  setMt: { ko:"금·은", en:"Metals" },
  setRho: { ko:"자산군 사이 상관계수", en:"Cross-class correlations" },
  setFx: { ko:"원달러 환율", en:"KRW/USD rate" },
  setUsVol: { ko:"S&P500 변동성 (원화 기준)", en:"S&P 500 vol (in KRW)" },
  setUsVolTip: { ko:"달러 기준 변동성보다 낮게 잡혀 있어요. 주가가 빠질 때 환율이 오르며 서로 상쇄되기 때문이에요.", en:"Set below the USD-terms figure: when prices fall the won weakens, and the two partly cancel." },
  setMtVol: { ko:"금 가격 변동성", en:"Gold price vol" },
  setMtMrpTip: { ko:"금은 이익도 배당도 없어 위험 프리미엄을 0에 가깝게 봐요. 기대수익이 아니라 분산 효과로 값어치를 하는 자산이에요.", en:"Metals produce no cash flows, so the premium is near zero — they earn their place through diversification, not expected return." },
  rhoKrUs: { ko:"한국 ↔ 미국", en:"KR ↔ US" },
  rhoKrMt: { ko:"한국 ↔ 금", en:"KR ↔ Gold" },
  rhoUsMt: { ko:"미국 ↔ 금", en:"US ↔ Gold" },
  rhoTip: { ko:"1에 가까울수록 함께 움직이고, 0이면 서로 무관하게 움직여요. 낮을수록 분산 효과가 커집니다.", en:"Closer to 1 means they move together; 0 means unrelated. Lower values give more diversification." },
  lgVerdict: { ko:"전설들의 알파도 연 10%p 안팎이에요. '확실한 연 30%'를 말하는 사람은 전설이 아니라 다른 무언가일 가능성이 커요. 개인이 가장 확실하게 챙길 수 있는 알파는, 행동 실수로 새는 연 2~4%p를 지키는 거예요.", en:"Even the legends' alpha sits near 10%p a year. Anyone promising a certain 30% is probably something other than a legend. The surest alpha an individual can claim is keeping the 2–4%p/yr that behavioral mistakes leak away." },
};

// ================= Baebi mascot — long-tailed tit (SVG) =================
// 뱁이 1.0 — 사용자 제작 아트워크 (9종 포즈, mood 이름 → 포즈 번호)
const BAEPI_POSES = { happy: 1, search: 2, worried: 2, data: 3, think: 4, cheer: 5, grow: 6, work: 7, care: 8, sleep: 9 };
function Bird({ mood = "happy", pose = "stand", size = 64 }) {
  const n = BAEPI_POSES[mood] || 1;
  return (
    <img src={"./baepi-" + n + ".png"} alt="뱁이" width={size} height={size}
      style={{ display: "inline-block", objectFit: "contain", verticalAlign: "middle" }}
      onError={(e) => { try { e.currentTarget.onerror = null; e.currentTarget.src = "./icon-192.png"; } catch (err) {} }} />
  );
}

// ================= Helpers =================
const fmtWon = (v) => "₩" + Math.round(v).toLocaleString("ko-KR");
const fmtMw = (v, lang) => {
  const mw = v / 10000;
  if (lang === "ko") {
    if (Math.abs(mw) >= 10000) return (mw / 10000).toFixed(mw % 10000 === 0 ? 0 : 1) + "억원";
    return Math.round(mw).toLocaleString("ko-KR") + "만원";
  }
  return "₩" + Math.round(v).toLocaleString("en-US");
};
const fmtPx = (v, s) => (s && s.ccy === "USD" ? "$" + Math.round(v).toLocaleString("en-US") : "\u20A9" + Math.round(v).toLocaleString("ko-KR"));
const pct = (v, d = 1) => (v == null || isNaN(v) ? "–" : v.toFixed(d) + "%");
const num = (v, d = 2) => (v == null || isNaN(v) ? "–" : v.toFixed(d));

// Block correlation model: several class factors, linked by a correlation matrix.
// σp² = ΣΣ (Wc1·σc1)(Wc2·σc2)·ρ(c1,c2) + Σ wᵢ²·idioᵢ,  where Wc = Σ_{i∈c} wᵢβᵢ
const CLS_LIST = ["kr", "us", "metal", "bond"];
const clsOf = (s) => { const c = s && s.cls; return c === "us" || c === "metal" || c === "bond" ? c : "kr"; };
const clsVol = (c, st) => (c === "us" ? st.usVol : c === "metal" ? st.mtVol : c === "bond" ? (st.bdVol ?? 7) : st.mktVol) / 100;
const clsMrp = (c, st) => (c === "us" ? st.usMrp : c === "metal" ? st.mtMrp : c === "bond" ? (st.bdMrp ?? 1) : st.mrp) / 100;
function rhoOf(a, b, st) {
  if (a === b) return 1;
  const k = [a, b].sort().join("|");
  if (k === "kr|us") return st.rhoKrUs;
  if (k === "kr|metal") return st.rhoKrMt;
  if (k === "metal|us") return st.rhoUsMt;
  if (k === "bond|kr") return st.rhoKrBd ?? 0.05;
  if (k === "bond|us") return st.rhoUsBd ?? 0.05;
  if (k === "bond|metal") return st.rhoMtBd ?? 0.1;
  return 0;
}
const priceKrw = (s, st) => s.price * (s.ccy === "USD" ? st.fx : 1);

function computeMetrics(holdings, budgetWon, settings) {
  const invested = holdings.reduce((a, h) => a + h.won, 0);
  const total = budgetWon > 0 ? Math.max(budgetWon, invested) : invested;
  const cash = Math.max((budgetWon > 0 ? budgetWon : invested) - invested, 0);
  const overBudget = budgetWon > 0 && invested > budgetWon + 1;
  if (total <= 0 || holdings.length === 0) return { empty: true, invested, cash, total: total || 0, overBudget, rows: [] };

  const rf = settings.rf / 100, sigKr = settings.mktVol / 100;
  const Wc = { kr: 0, us: 0, metal: 0 };
  const clsW = { kr: 0, us: 0, metal: 0 };
  let idioVar = 0, per = 0, dy = 0, hhi = 0, divWon = 0, fxW = 0;
  const sectorW = {};
  const rows = holdings.map((h) => {
    const w = h.won / total;
    const c = clsOf(h.stock);
    const sc = clsVol(c, settings);
    const b = h.stock.beta, volTot = h.stock.vol / 100;
    const sysV = Math.pow(b * sc, 2);
    const idio = Math.max(volTot * volTot - sysV, 0);
    Wc[c] += w * b; clsW[c] += w; idioVar += w * w * idio;
    if (h.stock.fxu) fxW += w;
    per += w * (h.stock.per || 0); dy += w * (h.stock.dy || 0);
    divWon += h.won * ((h.stock.dy || 0) / 100);
    hhi += w * w;
    sectorW[h.stock.s] = (sectorW[h.stock.s] || 0) + w;
    return { ...h, w, idio, b, c, sc, sysShare: volTot > 0 ? Math.min(sysV / (volTot * volTot), 1) : 0 };
  });
  let sysVar = 0;
  CLS_LIST.forEach((a) => CLS_LIST.forEach((b) => {
    sysVar += Wc[a] * clsVol(a, settings) * Wc[b] * clsVol(b, settings) * rhoOf(a, b, settings);
  }));
  const varP = Math.max(sysVar + idioVar, 0);
  const volP = Math.sqrt(varP);
  const expRet = rf + CLS_LIST.reduce((a, c) => a + Wc[c] * clsMrp(c, settings), 0);
  const sharpe = volP > 0 ? (expRet - rf) / volP : 0;
  const cagr = expRet - 0.5 * varP;
  const r2 = varP > 0 ? sysVar / varP : 0;
  const beta = CLS_LIST.reduce((a, c) => a + Wc[c] * (clsVol(c, settings) / sigKr) * rhoOf(c, "kr", settings), 0);
  const te = Math.sqrt(Math.max(varP - 2 * beta * sigKr * sigKr + sigKr * sigKr, 0));
  const investedW = invested / total;
  const effN = hhi > 0 ? (investedW * investedW) / hhi : 0;
  let maxSectorKey = null, maxSectorW = 0;
  Object.entries(sectorW).forEach(([k, w]) => {
    const wi = investedW > 0 ? w / investedW : 0;
    if (wi > maxSectorW) { maxSectorW = wi; maxSectorKey = k; }
  });
  const rows2 = rows.map((r) => {
    const cov = r.b * r.sc * CLS_LIST.reduce((a, c) => a + Wc[c] * clsVol(c, settings) * rhoOf(r.c, c, settings), 0) + r.w * r.idio;
    return { ...r, wInv: investedW > 0 ? r.w / investedW : 0, rc: varP > 0 ? (r.w * cov) / varP : 0 };
  });
  const wAvgVol = rows2.reduce((a, r) => a + r.wInv * r.stock.vol, 0);
  const pastAl = rows2.reduce((a, r) => a + r.wInv * (r.stock.al || 0), 0);
  const top3 = [...rows2].sort((a, b) => b.wInv - a.wInv).slice(0, 3).reduce((a, r) => a + r.wInv, 0) * 100;
  const clsWInv = {};
  CLS_LIST.forEach((c) => { clsWInv[c] = investedW > 0 ? (clsW[c] / investedW) * 100 : 0; });
  return {
    empty: false, invested, cash, total, overBudget, wAvgVol, top3, pastAl, te: te * 100,
    beta, volP: volP * 100, expRet: expRet * 100, sharpe, cagr: cagr * 100, r2: r2 * 100,
    effN, per, dy, divWon, sectorW, maxSectorKey, maxSectorW: maxSectorW * 100,
    clsW: clsWInv, fxExp: investedW > 0 ? (fxW / investedW) * 100 : 0,
    investedW: investedW * 100, rows: rows2,
  };
}
function benchMetrics(settings) {
  const rf = settings.rf / 100, mrp = settings.mrp / 100, sigM = settings.mktVol / 100;
  return { beta: 1, expRet: (rf + mrp) * 100, volP: sigM * 100, sharpe: mrp / sigM, cagr: (rf + mrp - 0.5 * sigM * sigM) * 100 };
}
function roboMix(profile, settings) {
  const wIdx = Math.min(profile.targetVolMaxPct / settings.mktVol, 1);
  const rf = settings.rf / 100, mrp = settings.mrp / 100, sigM = settings.mktVol / 100;
  return { wIdx: wIdx * 100, expRet: (rf + wIdx * mrp) * 100, volP: wIdx * sigM * 100, sharpe: mrp / sigM };
}
// ================= Statistics helpers (UDJ) =================
function normCdf(z) {
  const t = 1 / (1 + 0.2316419 * Math.abs(z));
  const d = 0.3989423 * Math.exp(-z * z / 2);
  const p = d * t * (0.3193815 + t * (-0.3565638 + t * (1.781478 + t * (-1.821256 + t * 1.330274))));
  return z > 0 ? 1 - p : p;
}
function mulberry32(a) {
  return function () {
    a |= 0; a = (a + 0x6D2B79F5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}
function gaussFactory(seed) {
  const rng = mulberry32(seed);
  return () => {
    const u = Math.max(rng(), 1e-9), v = rng();
    return Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * v);
  };
}
// Approximate real KOSPI monthly returns for the crash replays
const MKT_PATHS = {
  gfc: { ko: "2008 금융위기 (24개월)", en: "2008 GFC (24mo)",
    m: [-0.14, 0.07, -0.01, 0.06, -0.01, -0.12, -0.04, -0.08, -0.01, -0.23, -0.03, 0.05, 0.03, -0.02, 0.13, 0.13, 0.02, 0.0, 0.12, 0.02, 0.05, -0.05, 0.01, 0.08] },
  covid: { ko: "2020 코로나 (12개월)", en: "2020 COVID (12mo)",
    m: [-0.036, -0.062, -0.117, 0.11, 0.042, 0.039, 0.067, 0.034, 0.001, -0.026, 0.143, 0.109] },
};

function downloadFile(name, content, type) {
  const blob = new Blob([content], { type });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url; a.download = name; a.click();
  URL.revokeObjectURL(url);
}

// ================= Deterministic profile scoring (no AI, fully offline) =================
function scoreProfile(answers, lang) {
  const ko = lang === "ko";
  const arr = (id) => { const v = answers[id]; return Array.isArray(v) ? v : v == null || v === "" ? [] : [v]; };
  const has = (id, k) => arr(id).includes(k);
  const sl = (id, d) => { const v = answers[id]; return typeof v === "number" ? v : d; };
  const cl = (v, lo, hi) => Math.min(hi, Math.max(lo, v));
  const r10 = (v) => Math.round(cl(v, 1, 10));

  const hzY = sl("horizon", 10), shareP = sl("share", 40), emgM = sl("emergency", 3), tgt = sl("target", 8);
  const chk = arr("checking")[0] || "weekly";
  const INSTR = ["krstock", "usstock", "etfkr", "etfus", "lev", "coin", "ipo", "fund", "metal", "bond"];
  const nInstr = INSTR.filter((k) => has("exp", k)).length;
  const newbie = has("exp", "newbie") || (nInstr === 0 && has("exp", "dep"));

  let cap = 5;
  cap += hzY < 2 ? -3 : hzY < 5 ? -1 : hzY < 10 ? 1 : 2;
  cap += emgM < 1 ? -3 : emgM < 3 ? -1.5 : emgM < 6 ? 1 : 2;
  cap += shareP > 70 ? -2 : shareP > 40 ? -1 : shareP > 15 ? 0.5 : 1.5;

  let tol = 5;
  if (has("crash", "sellall")) tol -= 3;
  if (has("crash", "sellsome")) tol -= 1;
  if (has("crash", "hold")) tol += 1.5;
  if (has("crash", "buy")) tol += 2;
  if (has("crash", "nosleep")) tol -= 2;
  if (has("crash", "numb")) tol += 2;
  if (has("crash", "nolook")) tol += 0.5;
  if (has("style", "safe")) tol -= 1.5;
  if (has("style", "ret")) tol += 1.5;
  if (has("style", "calm")) tol += 1;
  if (has("style", "news")) tol -= 1;
  if (has("fear", "loss")) tol -= 1;
  if (has("fear", "swing")) tol -= 1;
  if (has("fear", "none")) tol += 1;

  let dis = 5;
  if (has("crash", "sellall")) dis -= 2;
  if (has("crash", "hold")) dis += 1.5;
  if (has("crash", "buy")) dis += 1;
  if (has("crash", "ask")) dis -= 0.5;
  dis += chk === "many" ? -2.5 : chk === "daily" ? -1.5 : chk === "weekly" ? 0 : chk === "monthly" ? 1 : chk === "quarterly" ? 1.5 : 2;
  if (has("style", "gut")) dis -= 1;
  if (has("style", "data")) dis += 1;
  if (has("style", "long")) dis += 1.5;
  if (has("style", "short")) dis -= 2;
  if (has("style", "fomo")) dis -= 1.5;
  if (has("style", "rule")) dis += 1.5;
  if (has("exp", "lev")) dis -= 1.5;
  if (has("exp", "coin")) dis -= 0.5;
  if (has("fear", "fomo")) dis -= 1;

  let expS = newbie ? 1 : 1.5 + nInstr * 1.1;
  let kn = newbie ? 2 : 3 + nInstr * 0.7;
  if (has("style", "data")) kn += 1;
  if (has("exp", "bond")) kn += 0.5;
  if (has("exp", "etfus")) kn += 0.5;
  if (has("style", "gut")) kn -= 0.5;

  const hz = hzY >= 20 ? 10 : hzY <= 1 ? 1 : 1 + ((hzY - 1) * 9) / 19;
  const amb = 2 + ((tgt - 3) * 8) / 17;
  let eng = 5 + (chk === "many" ? 3 : chk === "daily" ? 2 : chk === "weekly" ? 0.5 : chk === "monthly" ? -0.5 : chk === "quarterly" ? -1.5 : -2.5);
  if (has("style", "news")) eng += 1;
  eng += Math.min(arr("interest").filter((x) => x !== "none").length, 5) * 0.3;

  const attrs = { capacity: r10(cap), tolerance: r10(tol), horizon: r10(hz), experience: r10(expS), knowledge: r10(kn), discipline: r10(dis), ambition: r10(amb), engagement: r10(eng) };
  const bind = Math.min(attrs.capacity, attrs.tolerance);
  const riskNeedPct0 = cl(tgt, 3, 15);
  const canBetaMax = bind <= 3 ? 0.7 : bind <= 5 ? 0.9 : bind <= 7 ? 1.1 : 1.4;
  // Take no more risk than the goal actually requires — surplus risk is uncompensated by definition.
  const needBeta = cl((riskNeedPct0 - DEFAULT_SETTINGS.rf) / DEFAULT_SETTINGS.mrp, 0.2, 1.5);
  const targetBetaMax = Math.round(Math.min(canBetaMax, needBeta + 0.25) * 20) / 20;
  const needCaps = targetBetaMax < canBetaMax - 0.02;
  const targetBetaMin = Math.round(cl(Math.min(bind <= 3 ? 0.3 : bind <= 5 ? 0.5 : bind <= 7 ? 0.7 : 0.9, targetBetaMax - 0.3), 0.2, 1.2) * 20) / 20;
  const targetVolMaxPct = Math.round(cl(Math.min(11 + bind * 2.3, 9 + targetBetaMax * 16), 12, 34));
  const stocksMin = Math.round(cl(16 - bind - (attrs.experience >= 7 ? 1 : 0), 6, 13));
  const maxPositionPct = Math.round(cl(7 + bind * 2, 10, 25));
  const maxSectorPct = Math.round(cl(20 + bind * 2.6, 25, 45));
  const cashFloorPct = Math.round(cl(30 - attrs.capacity * 1.6 - attrs.tolerance * 0.8 - Math.min(hzY, 12), 0, 30));
  const riskNeedPct = riskNeedPct0;
  const interestedSectors = arr("interest").filter((v) => v !== "none" && SECTORS[v]);

  const checkFreq = dis <= 4 ? (ko ? "분기 1회" : "Quarterly") : attrs.horizon >= 8 && dis >= 8 ? (ko ? "반기 1회" : "Twice a year") : (ko ? "월 1회" : "Monthly");
  const base = bind <= 3 ? (ko ? "안전 우선형" : "Safety-first") : bind <= 5 ? (ko ? "계획형" : "Planner") : bind <= 7 ? (ko ? "균형형" : "Balanced") : (ko ? "적극형" : "Assertive");
  const pre = attrs.discipline >= 8 ? (ko ? "원칙 있는 " : "Disciplined ") : attrs.discipline <= 4 ? (ko ? "서두르기 쉬운 " : "Impulse-prone ") : (ko ? "차분한 " : "Steady ");
  const title = pre + base;

  const bindWord = attrs.capacity <= attrs.tolerance ? (ko ? "형편(감수 능력)" : "circumstances (capacity)") : (ko ? "마음(감수 의지)" : "temperament (willingness)");
  const summary = ko
    ? `${hzY >= 30 ? "30년 이상" : hzY + "년"} 뒤를 보고 계시고, 전 재산의 ${shareP}%를 이 투자에 담을 계획이에요. 비상금은 ${emgM >= 12 ? "1년치 이상" : emgM + "개월치"}이고요. 감수 능력 ${attrs.capacity}점, 감수 의지 ${attrs.tolerance}점 중 더 낮은 쪽인 ${bindWord}이 기준이 돼요. 목표는 연 ${tgt}%라서, 베타 ${targetBetaMin.toFixed(1)}~${targetBetaMax.toFixed(1)} 범위에서 ${stocksMin}~${stocksMin + 7}종목쯤으로 나눠 담는 걸 권해요.`
    : `You're looking ${hzY >= 30 ? "30+ " : hzY + " "}years out, putting ${shareP}% of your wealth here, with ${emgM >= 12 ? "a year or more" : emgM + " months"} of emergency fund. Between capacity ${attrs.capacity} and willingness ${attrs.tolerance}, the lower one — ${bindWord} — binds. With a ${tgt}%/yr goal, aim for beta ${targetBetaMin.toFixed(1)}–${targetBetaMax.toFixed(1)} across roughly ${stocksMin}–${stocksMin + 7} holdings.`;

  const flags = [];
  if (Math.abs(attrs.capacity - attrs.tolerance) >= 3) {
    flags.push(attrs.capacity > attrs.tolerance
      ? (ko ? `형편은 더 감수해도 될 만한데(${attrs.capacity}점) 마음이 못 따라가요(${attrs.tolerance}점). 이럴 땐 마음을 기준으로 삼는 게 맞아요 — 못 버티고 파는 순간 손실이 진짜가 되니까요.` : `Your circumstances allow more risk (${attrs.capacity}) than your temperament wants (${attrs.tolerance}). Let temperament bind — a loss only becomes real when you sell.`)
      : (ko ? `마음은 더 감수하고 싶은데(${attrs.tolerance}점) 형편이 아직 못 받쳐줘요(${attrs.capacity}점). 비상금을 먼저 채우거나 기간을 늘리는 게 순서예요.` : `You want more risk (${attrs.tolerance}) than your circumstances support (${attrs.capacity}). Build the emergency fund or extend the horizon first.`));
  }
  if (riskNeedPct > 3 + targetBetaMax * 5.5 + 0.5) {
    flags.push(ko ? `목표 연 ${tgt}%는 지금 감당 가능한 위험(β 최대 ${targetBetaMax.toFixed(1)})으로 기대하기 어려운 수치예요. 목표·기간·저축액 셋 중 하나는 조정이 필요해요 — 위험을 억지로 키우는 건 답이 아니고요.` : `A ${tgt}%/yr goal is hard to expect from the risk you can carry (β up to ${targetBetaMax.toFixed(1)}). Adjust the goal, the horizon, or how much you save — forcing more risk is not the answer.`);
  }
  if (has("exp", "lev") && flags.length < 3) {
    flags.push(ko ? "레버리지·인버스 경험이 있으시네요. 이 상품들은 오래 들고 있을수록 원지수보다 뒤처지는 구조(변동성 끌림)라, 이 도구는 다루지 않아요." : "You've used leveraged/inverse products. They decay against the underlying index the longer you hold (volatility drag), so this tool doesn't cover them.");
  }
  if ((chk === "many" || chk === "daily") && attrs.discipline <= 5 && flags.length < 3) {
    flags.push(ko ? "계좌를 자주 보는 편인데 절제력 점수가 높지 않아요. 자주 보는 사람일수록 더 자주 사고팔고, 그만큼 수익이 깎인다는 연구가 많아요." : "You check often and your discipline score isn't high. Frequent checking leads to frequent trading, which research consistently links to lower returns.");
  }
  if (shareP > 70 && emgM < 3 && flags.length < 3) {
    flags.push(ko ? "전 재산의 대부분을 넣는데 비상금이 얇아요. 급한 돈이 생기면 하필 시장이 나쁠 때 팔아야 할 수 있어요 — 비상금이 먼저예요." : "Most of your wealth goes in while the emergency fund is thin. An unexpected bill could force a sale at the worst moment — fund the cushion first.");
  }

  const tips = [];
  const push = (k) => { if (tips.length < 4) tips.push(k); };
  if (needCaps) push(ko ? `목표가 연 ${tgt}%라면 베타 ${targetBetaMax.toFixed(2)} 정도면 충분해요. 형편상 더 감수할 수 있어도, 필요 없는 위험까지 질 이유는 없어요 — 안 써도 되는 위험은 그냥 떠안은 위험이 되니까요.` : `A ${tgt}%/yr goal only needs about beta ${targetBetaMax.toFixed(2)}. You could bear more, but risk you don't need is risk you don't get paid for.`);
  if (interestedSectors.length > 0) push(ko ? `관심 분야()만 담다 보면 섹터 상한 ${maxSectorPct}%를 넘기기 쉬워요. 계기판이 빨간불이 되면 그때가 멈출 때예요.` : `Loading up on your sectors easily breaches the ${maxSectorPct}% cap. When the gauge turns red, that's the stop sign.`);
  if (newbie) push(ko ? "처음이라면 지수 ETF 한두 개로 뼈대를 세우고, 잘 아는 종목을 조금씩 얹어가는 순서가 편해요." : "If you're new, build the frame with one or two index ETFs, then add individual names you actually know.");
  if (attrs.discipline <= 4) push(ko ? "사고 싶은 종목이 생기면 하루만 묵혀보세요. 하루 뒤에도 같은 이유가 남아 있으면 그때 담아도 늦지 않아요." : "When you want to buy something, sleep on it for a day. If the reason still holds tomorrow, it'll still be there.");
  if (attrs.ambition >= 8) push(ko ? `연 ${tgt}%는 전설들의 영역에 가까워요. 목표를 낮추는 게 지는 게 아니라, 지킬 수 있는 계획을 세우는 거예요.` : `${tgt}%/yr is near legend territory. Lowering the target isn't losing — it's making a plan you can keep.`);
  if (hzY <= 3) push(ko ? "3년 안에 쓸 돈이라면 주식 비중 자체를 줄이는 게 가장 확실한 방법이에요. 짧은 기간에는 운의 영향이 실력보다 커요." : "For money needed within three years, the surest move is holding less equity. Over short spans, luck outweighs skill.");
  if (interestedSectors.includes("metal")) push(ko ? "금·은은 기대수익이 아니라 '주식과 따로 움직이는 성질' 때문에 담는 자산이에요. 비중은 5~15% 정도가 흔해요." : "Hold metals for their low correlation with stocks, not for expected return. A 5–15% sleeve is typical.");
  if (attrs.experience >= 7 && tips.length < 4) push(ko ? "경험이 넓은 편이니, 종목 수를 늘리기보다 서로 성격이 다른 자산군으로 나누는 쪽이 효과가 커요." : "With your breadth, splitting across different asset classes beats simply adding more tickers.");
  if (cashFloorPct >= 15) push(ko ? `현금 ${cashFloorPct}%는 놀고 있는 돈이 아니라, 급할 때 안 팔아도 되게 해주는 장치예요.` : `That ${cashFloorPct}% cash isn't idle — it's what keeps you from having to sell at a bad moment.`);

  return {
    ready: true, source: "rules", attrs,
    account: (arr("account")[0] === "unsure" || !arr("account")[0]) ? "normal" : arr("account")[0],
    riskCapacity: attrs.capacity, riskTolerance: attrs.tolerance, riskNeedPct,
    targetBetaMin, targetBetaMax, targetVolMaxPct,
    stocksMin, stocksMax: stocksMin + 7, maxPositionPct, maxSectorPct, cashFloorPct,
    checkFreq, interestedSectors, title, summary, flags: flags.slice(0, 3), tips,
  };
}

// ================= UI atoms =================
const Card = ({ children, style = {}, onClick }) => (
  <div onClick={onClick} style={{ background: "#FFFFFF", borderRadius: RAD.card, padding: 18, border: HAIR, ...style }}>{children}</div>
);
const Chip = ({ children, color = C.blue, soft = C.blueSoft, style = {} }) => (
  <span style={{ background: soft, color, fontSize: 11, fontWeight: 700, padding: "3px 9px", borderRadius: 999, whiteSpace: "nowrap", ...style }}>{children}</span>
);
const H3 = ({ children, size = 15 }) => <div style={{ fontSize: size, fontWeight: 800, color: C.ink, letterSpacing: "-0.01em" }}>{children}</div>;
const Sub = ({ children, style = {} }) => <div style={{ fontSize: 12, color: C.sub, lineHeight: 1.55, ...style }}>{children}</div>;
const Btn = ({ children, onClick, kind = "primary", style = {}, disabled }) => {
  const base = { border: "none", borderRadius: RAD.btn, padding: "13px 18px", fontSize: 14, fontWeight: 800, cursor: disabled ? "default" : "pointer", opacity: disabled ? 0.55 : 1, fontFamily: FONT };
  const kinds = {
    primary: { background: C.blue, color: "#fff" },
    ghost: { background: "#fff", color: C.sub, border: "1.5px solid " + C.line },
    dark: { background: C.ink, color: "#fff" },
  };
  return <button disabled={disabled} onClick={onClick} style={{ ...base, ...kinds[kind], ...style }}>{children}</button>;
};
// ticker monogram badge (no brand logos — sector-colored, ticker digits)
function Mono({ stock, size = 40 }) {
  const col = SECTORS[stock.s]?.color || C.blue;
  const top = stock.t.slice(0, 3), bot = stock.t.slice(3);
  return (
    <div style={{ width: size, height: size, borderRadius: size * 0.3, background: col + "1A", border: "1.5px solid " + col + "55", display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", flexShrink: 0 }}>
      <span style={{ fontSize: size * 0.24, fontWeight: 800, color: col, lineHeight: 1.1, letterSpacing: "0.02em" }}>{top}</span>
      <span style={{ fontSize: size * 0.24, fontWeight: 800, color: col, lineHeight: 1.1, letterSpacing: "0.02em" }}>{bot}</span>
    </div>
  );
}

// ================= Explainer sheet =================
function ExplainSheet({ id, lang, onClose }) {
  if (!id || !EXPLAIN[id]) return null;
  const e = EXPLAIN[id][lang];
  const done = lang === "ko" ? "이해했어요!" : "Got it!";
  const L = lang === "ko" ? ["한 줄 정의", "비유하자면", "그래서 어떻게?"] : ["In one line", "Think of it as", "So what?"];
  return (
    <div onClick={onClose} style={{ position: "fixed", inset: 0, background: "rgba(11,34,57,0.45)", zIndex: 70, display: "flex", alignItems: "flex-end", justifyContent: "center" }}>
      <div onClick={(ev) => ev.stopPropagation()} style={{ background: "#fff", borderRadius: "26px 26px 0 0", padding: "22px 20px 30px", width: "100%", maxWidth: 560, maxHeight: "85vh", overflowY: "auto", animation: "slideUp .25s ease" }}>
        <div style={{ width: 40, height: 4, background: C.line, borderRadius: 2, margin: "0 auto 16px" }} />
        <H3 size={18}>{e.name}</H3>
        <div style={{ marginTop: 12, display: "flex", flexDirection: "column", gap: 10 }}>
          {[["what", C.bg, C.ink], ["ana", C.blueSoft, C.blue], ["act", C.tealSoft, C.teal]].map(([k, bgc, tc], i) => (
            <div key={k} style={{ background: bgc, borderRadius: 15, padding: 13 }}>
              <Sub style={{ fontWeight: 700, color: tc, marginBottom: 3 }}>{L[i]}</Sub>
              <div style={{ fontSize: 13.5, color: C.ink, lineHeight: 1.65 }}>{e[k]}</div>
            </div>
          ))}
        </div>
        <Btn onClick={onClose} style={{ width: "100%", marginTop: 16 }}>{done}</Btn>
      </div>
    </div>
  );
}

// ================= Badge toast =================
function Toast({ msg, show }) {
  return (
    <div style={{ position: "fixed", top: 16, left: "50%", zIndex: 80, transform: "translateX(-50%) translateY(" + (show ? "0" : "-130px") + ")", transition: "transform .45s cubic-bezier(.34,1.56,.64,1)", background: "#fff", borderRadius: 18, padding: "10px 16px", boxShadow: "0 8px 30px rgba(11,34,57,0.2)", display: "flex", alignItems: "center", gap: 10 }}>
      <Bird mood="cheer" size={40} />
      <div>
        <div style={{ fontSize: 13, fontWeight: 800, color: C.ink }}>{msg && msg.title}</div>
        <div style={{ fontSize: 11, color: C.sub }}>{msg && msg.sub}</div>
      </div>
    </div>
  );
}

// ================= Health hero =================
function HealthHero({ score, okCount, lang, t }) {
  const R = 42, CIRC = 2 * Math.PI * R;
  const msg = score >= 85 ? t("scoreGood") : score >= 55 ? t("scoreMid") : t("scoreBad");
  return (
    <Card style={{ background: "linear-gradient(140deg, #2C4C7C 0%, #1B2B4B 55%, #12203A 100%)", color: "#fff", position: "relative", overflow: "hidden", padding: 20 }}>
      <div style={{ position: "absolute", right: 4, bottom: -10, transform: "rotate(-8deg)", opacity: 0.95, pointerEvents: "none" }}>
        <Bird mood={score >= 85 ? "cheer" : "happy"} size={62} />
      </div>
      <div style={{ display: "flex", alignItems: "center", gap: 16, position: "relative", paddingRight: 54 }}>
        <div style={{ position: "relative", width: 104, height: 104, flexShrink: 0 }}>
          <svg width="104" height="104" viewBox="0 0 104 104">
            <circle cx="52" cy="52" r={R} fill="none" stroke="rgba(255,255,255,0.25)" strokeWidth="9" />
            <circle cx="52" cy="52" r={R} fill="none" stroke="#fff" strokeWidth="9" strokeLinecap="round" strokeDasharray={CIRC} strokeDashoffset={CIRC * (1 - score / 100)} transform="rotate(-90 52 52)" style={{ transition: "stroke-dashoffset .6s ease" }} />
          </svg>
          <div style={{ position: "absolute", inset: 0, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center" }}>
            <div style={{ fontSize: 28, fontWeight: 900, lineHeight: 1 }}>{score}</div>
            <div style={{ fontSize: 10, opacity: 0.85 }}>/ 100</div>
          </div>
        </div>
        <div>
          <div style={{ fontSize: 12, fontWeight: 700, opacity: 0.85 }}>{t("score")}</div>
          <div style={{ fontSize: 19, fontWeight: 900, marginTop: 2, letterSpacing: "-0.02em" }}>{msg}</div>
          <div style={{ fontSize: 12, opacity: 0.9, marginTop: 5, lineHeight: 1.5 }}>
            {lang === "ko" ? <>계기판 4개 중 <b>{okCount}개</b>가 초록불이에요.</> : <><b>{okCount}</b> of 4 gauges are green.</>}
          </div>
        </div>
      </div>
    </Card>
  );
}

// ================= Rail =================
function Rail({ emoji, label, valueLabel, value, min, max, tMin, tMax, ok, onExplain, extraDot, extraLabel, danger, band }) {
  const clamp = (v) => Math.min(Math.max(v, min), max);
  const p = (v) => ((clamp(v) - min) / (max - min)) * 100;
  return (
    <div style={{ padding: "13px 0", borderBottom: "1px solid " + C.line }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 9 }}>
        <button onClick={onExplain} style={{ display: "flex", alignItems: "center", gap: 6, background: "none", border: "none", cursor: "pointer", padding: 0, fontFamily: FONT }}>
          <span style={{ fontSize: 12.5, fontWeight: 700, color: C.ink }}>{label}</span>
          <span style={{ fontSize: 10, color: C.faint, background: C.bg, borderRadius: 999, width: 15, height: 15, display: "inline-flex", alignItems: "center", justifyContent: "center", fontWeight: 800 }}>?</span>
        </button>
        <div style={{ display: "flex", alignItems: "center", gap: 7 }}>
          <span style={{ fontSize: 13.5, fontWeight: 800, color: ok ? C.ink : C.coral }}>{valueLabel}</span>
          <Chip color={ok ? C.teal : C.coral} soft={ok ? C.tealSoft : C.coralSoft}>{ok ? "" : ""}</Chip>
        </div>
      </div>
      <div style={{ position: "relative", height: 20 }}>
        <div style={{ position: "absolute", top: 8, left: 0, right: 0, height: 5, background: C.line, borderRadius: 3 }} />
        <div style={{ position: "absolute", top: 6, left: p(tMin) + "%", width: Math.max(p(tMax) - p(tMin), 1.5) + "%", height: 9, background: C.tealSoft, border: "1.5px solid " + C.teal, borderRadius: 6 }} />
        {band != null && (
          <div style={{ position: "absolute", top: 6, left: p(value - band) + "%", width: Math.max(p(value + band) - p(value - band), 1) + "%", height: 9, background: C.blue + "26", border: "1.5px solid " + C.blue + "55", borderRadius: 6, transition: "left .3s ease" }} />
        )}
        {extraDot != null && (
          <div title={extraLabel} style={{ position: "absolute", top: 3, left: "calc(" + p(extraDot) + "% - 7px)", width: 14, height: 14, borderRadius: "50%", background: "#fff", border: "2.5px dashed " + (danger ? C.coral : C.sand), transition: "left .3s ease" }} />
        )}
        <div style={{ position: "absolute", top: 1, left: "calc(" + p(value) + "% - 9px)", width: 18, height: 18, background: ok ? C.blue : C.coral, borderRadius: "50%", border: "3px solid #fff", boxShadow: "0 1px 4px rgba(11,34,57,0.25)", transition: "left .3s ease" }} />
      </div>
    </div>
  );
}

// ================= Attribute radar & chip question =================
const ATTR_META = [
  ["capacity", "감수 능력", "Capacity"],
  ["tolerance", "감수 의지", "Willingness"],
  ["discipline", "절제력", "Discipline"],
  ["knowledge", "지식", "Knowledge"],
  ["experience", "경험", "Experience"],
  ["engagement", "시장 관심", "Engagement"],
  ["ambition", "목표 눈높이", "Ambition"],
  ["horizon", "투자 기간", "Horizon"],
];
function Radar({ attrs, lang, size = 272 }) {
  const cx = size / 2, cy = size / 2, R = size * 0.32;
  const pt = (i, frac) => {
    const a = (Math.PI * 2 * i) / 8 - Math.PI / 2;
    return [cx + Math.cos(a) * R * frac, cy + Math.sin(a) * R * frac];
  };
  const poly = (frac) => ATTR_META.map((_, i) => pt(i, frac).join(",")).join(" ");
  const valPoly = ATTR_META.map(([k], i) => pt(i, (attrs[k] || 0) / 10).join(",")).join(" ");
  return (
    <svg width={size} height={size} style={{ flexShrink: 0 }}>
      {[0.25, 0.5, 0.75, 1].map((f) => (
        <polygon key={f} points={poly(f)} fill="none" stroke={C.line} strokeWidth={f === 1 ? 1.5 : 1} />
      ))}
      {ATTR_META.map((_, i) => {
        const [x, y] = pt(i, 1);
        return <line key={i} x1={cx} y1={cy} x2={x} y2={y} stroke={C.line} />;
      })}
      <polygon points={poly(0.5)} fill="none" stroke={C.faint} strokeDasharray="3 3" />
      <polygon points={valPoly} fill={C.blue + "30"} stroke={C.blue} strokeWidth="2" strokeLinejoin="round" />
      {ATTR_META.map(([k], i) => {
        const [x, y] = pt(i, (attrs[k] || 0) / 10);
        return <circle key={k} cx={x} cy={y} r="3.2" fill={C.blue} stroke="#fff" strokeWidth="1.5" />;
      })}
      {ATTR_META.map(([k, ko, en], i) => {
        const [x, y] = pt(i, 1.26);
        return (
          <text key={k} x={x} y={y + 3} textAnchor="middle" style={{ fontSize: 10, fontWeight: 700, fill: C.sub, fontFamily: FONT }}>
            {lang === "ko" ? ko : en} <tspan style={{ fill: C.ink, fontWeight: 800 }}>{attrs[k]}</tspan>
          </text>
        );
      })}
    </svg>
  );
}
function ChipQ({ q, val, onChange, lang, single }) {
  const toggle = (v) => onChange(single ? (val.includes(v) ? [] : [v]) : val.includes(v) ? val.filter((x) => x !== v) : [...val, v]);
  return (
    <div style={{ display: "flex", flexWrap: "wrap", gap: 7, marginTop: 9 }}>
      {q.opts.map((o) => {
        const on = val.includes(o.v);
        return (
          <button key={o.v} onClick={() => toggle(o.v)} style={{ fontFamily: FONT, fontSize: 12.5, fontWeight: 700, padding: "9px 13px", borderRadius: 999, cursor: "pointer", border: "1.5px solid " + (on ? C.blue : C.line), background: on ? C.blue : "#fff", color: on ? "#fff" : C.sub, transition: "all .12s" }}>
            {lang === "ko" ? o.ko : o.en}
          </button>
        );
      })}
    </div>
  );
}

// ================= Profile: questionnaire =================
function SliderQ({ q, val, onChange, lang }) {
  const v = typeof val === "number" ? val : q.def;
  return (
    <div style={{ marginTop: 12 }}>
      <div style={{ textAlign: "center", fontSize: 19, fontWeight: 900, color: C.blueDeep, marginBottom: 8 }}>{q.fmt(v, lang)}</div>
      <input type="range" min={q.min} max={q.max} step={q.step} value={v} onChange={(e) => onChange(parseFloat(e.target.value))}
        style={{ width: "100%", accentColor: C.blue, cursor: "pointer" }} />
      <div style={{ display: "flex", justifyContent: "space-between", fontSize: 10.5, color: C.faint, marginTop: 2 }}>
        <span>{q.fmt(q.min, lang)}</span><span>{q.fmt(q.max, lang)}</span>
      </div>
    </div>
  );
}

function ProfileView({ lang, t, profile, setProfile, answers, setAnswers, goBuild }) {
  const [editing, setEditing] = useState(false);
  const [showPresets, setShowPresets] = useState(false);
  const tapQs = QUESTIONS.filter((q) => q.type !== "slider");
  const isDone = (q) => { const v = answers[q.id]; return Array.isArray(v) ? v.length > 0 : v != null && v !== ""; };
  const doneN = QUESTIONS.filter((q) => q.type === "slider" || isDone(q)).length;
  const allDone = tapQs.every(isDone);
  const applyPreset = (key) => {
    const pr = PRESETS[key];
    setProfile({ ...DEFAULT_PROFILE, ...pr.p, ready: true, source: "preset", title: (lang === "ko" ? pr.ko : pr.en), summary: "", flags: [], tips: pr.tips[lang], checkFreq: pr.freq[lang], interestedSectors: (Array.isArray(answers.interest) ? answers.interest : []).filter((v) => v !== "none" && SECTORS[v]) });
    setShowPresets(false);
  };

  if (profile.ready && !editing) {
    return (
      <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
        <ProfileCard profile={profile} lang={lang} t={t} onRedo={() => setProfile({ ...DEFAULT_PROFILE })} onEdit={() => setEditing(true)} />
        <Btn onClick={goBuild} style={{ width: "100%" }}>{t("goBuild")}</Btn>
      </div>
    );
  }
  if (editing) {
    return <ManualProfile lang={lang} t={t} profile={profile} onSave={(p) => { setProfile({ ...p, ready: true }); setEditing(false); }} onCancel={() => setEditing(false)} />;
  }
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
      <Card style={{ display: "flex", gap: 14, alignItems: "flex-start" }}>
        <Bird mood="happy" size={62} />
        <div style={{ flex: 1 }}>
          <H3>{lang === "ko" ? "뱁이의 질문" : "Baebi's Questions"}</H3>
          <Sub style={{ marginTop: 5 }}>{Q_INTRO[lang]}</Sub>
          <div style={{ display: "flex", alignItems: "center", gap: 8, marginTop: 8 }}>
            <div style={{ flex: 1, height: 6, background: C.bg, borderRadius: 3, overflow: "hidden" }}>
              <div style={{ height: 6, width: (doneN / QUESTIONS.length) * 100 + "%", background: C.blue, transition: "width .3s ease" }} />
            </div>
            <span style={{ fontSize: 11, color: C.faint, fontWeight: 700 }}>{doneN}/{QUESTIONS.length}</span>
          </div>
        </div>
      </Card>
      <div className="qgrid">
        {QUESTIONS.map((q, i) => (
          <Card key={q.id} style={{ padding: 16 }}>
            <div style={{ display: "flex", gap: 11 }}>
              <div style={{ flexShrink: 0, width: 26, height: 26, borderRadius: "50%", background: isDone(q) || q.type === "slider" ? C.blue : C.faint, color: "#fff", fontSize: 12, fontWeight: 800, display: "flex", alignItems: "center", justifyContent: "center" }}>{i + 1}</div>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ fontSize: 13.5, fontWeight: 600, color: C.ink, lineHeight: 1.65 }}>{lang === "ko" ? q.ko : q.en}</div>
                {q.type === "slider" ? (
                  <SliderQ q={q} lang={lang} val={answers[q.id]} onChange={(v) => setAnswers({ ...answers, [q.id]: v })} />
                ) : (
                  <>
                    <div style={{ fontSize: 10.5, color: C.faint, marginTop: 3 }}>{q.type === "one" ? t("chipOne") : t("chipHint")}</div>
                    <ChipQ q={q} lang={lang} single={q.type === "one"} val={Array.isArray(answers[q.id]) ? answers[q.id] : answers[q.id] ? [answers[q.id]] : []}
                      onChange={(a) => setAnswers({ ...answers, [q.id]: q.type === "one" ? (a[0] || "") : a })} />
                  </>
                )}
              </div>
            </div>
          </Card>
        ))}
      </div>
      {!allDone && <div style={{ fontSize: 12.5, fontWeight: 700, color: C.faint, textAlign: "center" }}>{t("tapNeeded")}</div>}
      <Btn onClick={() => setProfile(scoreProfile(answers, lang))} disabled={!allDone} style={{ width: "100%" }}>{t("seeResult")}</Btn>
      <Btn kind="ghost" onClick={() => setShowPresets(!showPresets)} style={{ width: "100%" }}>{t("skipPreset")}</Btn>
      {showPresets && (
        <Card>
          <H3 size={14}>{t("presetTitle")}</H3>
          <Sub style={{ marginTop: 3 }}>{t("presetSub")}</Sub>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(3,1fr)", gap: 8, marginTop: 10 }}>
            {Object.entries(PRESETS).map(([k, pr]) => (
              <button key={k} onClick={() => applyPreset(k)} style={{ background: C.bg, border: "1.5px solid " + C.line, borderRadius: 16, padding: "14px 8px", cursor: "pointer", fontFamily: FONT }}>
                <div style={{ display: "flex", justifyContent: "center" }}><Ic name={k === "calm" ? "seed" : k === "bold" ? "flame" : "scale"} size={22} color={C.blue} /></div>
                <div style={{ fontSize: 13, fontWeight: 800, color: C.ink, marginTop: 4 }}>{lang === "ko" ? pr.ko : pr.en}</div>
                <div style={{ fontSize: 10.5, color: C.faint, marginTop: 2 }}>β {pr.p.targetBetaMin}–{pr.p.targetBetaMax} · σ≤{pr.p.targetVolMaxPct}%</div>
              </button>
            ))}
          </div>
        </Card>
      )}
    </div>
  );
}

function GaugeBar({ value, label, hint, color }) {
  return (
    <div style={{ flex: 1, minWidth: 128 }}>
      <Sub>{label}</Sub>
      <div style={{ display: "flex", alignItems: "flex-end", gap: 4, marginTop: 2 }}>
        <span style={{ fontSize: 22, fontWeight: 900, color }}>{value}</span>
        <span style={{ fontSize: 11, color: C.faint, marginBottom: 3 }}>/ 10</span>
      </div>
      <div style={{ height: 6, borderRadius: 3, background: C.bg, marginTop: 4 }}>
        <div style={{ height: 6, borderRadius: 3, width: value * 10 + "%", background: color }} />
      </div>
      <div style={{ fontSize: 10.5, color: C.faint, marginTop: 3, lineHeight: 1.4 }}>{hint}</div>
    </div>
  );
}

function ProfileCard({ profile, lang, t, onRedo, onEdit, compact }) {
  return (
    <Card>
      <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 8 }}>
        <div style={{ display: "flex", gap: 12, alignItems: "center" }}>
          {!compact && <Bird mood="happy" size={50} />}
          <div>
            <H3>{t("profileTitle")}</H3>
            {profile.title && <Chip color={C.blueDeep} soft={C.blueSoft} style={{ marginTop: 4, display: "inline-block" }}>{profile.title}</Chip>}
          </div>
        </div>
        {!compact && (
          <div style={{ display: "flex", gap: 6 }}>
            {onEdit && <Btn kind="ghost" onClick={onEdit} style={{ padding: "6px 11px", fontSize: 12 }}>{t("edit")}</Btn>}
            {onRedo && <Btn kind="ghost" onClick={onRedo} style={{ padding: "6px 11px", fontSize: 12 }}>{t("redo")}</Btn>}
          </div>
        )}
      </div>
      {profile.summary && <div style={{ fontSize: 13.5, color: C.ink, lineHeight: 1.7, marginTop: 12, background: C.bg, borderRadius: 14, padding: 13 }}>{profile.summary}</div>}
      {profile.attrs ? (
        <div style={{ display: "flex", flexWrap: "wrap", gap: 14, marginTop: 12, alignItems: "center" }}>
          <div style={{ flex: "0 0 auto", margin: "0 auto" }}>
            <div style={{ fontSize: 12, fontWeight: 800, color: C.ink, textAlign: "center" }}>{t("attrMap")}</div>
            <Radar attrs={profile.attrs} lang={lang} />
            <div style={{ fontSize: 10, color: C.faint, textAlign: "center" }}>{t("avg5")}</div>
          </div>
          <div style={{ flex: 1, minWidth: 210, display: "flex", flexDirection: "column", gap: 9 }}>
            <div style={{ background: C.bg, borderRadius: 13, padding: 11 }}>
              <Sub>{t("need")}</Sub>
              <div style={{ fontSize: 24, fontWeight: 900, color: C.ink, marginTop: 1 }}>{pct(profile.riskNeedPct, 0)}</div>
              <div style={{ fontSize: 10.5, color: C.faint }}>{t("needHint")}</div>
            </div>
            <div style={{ display: "flex", gap: 8 }}>
              <div style={{ flex: 1, background: C.bg, borderRadius: 13, padding: 11 }}>
                <Sub>{t("checkFreqL")}</Sub>
                <div style={{ fontSize: 15, fontWeight: 900, color: C.ink, marginTop: 2 }}>{profile.checkFreq || "–"}</div>
              </div>
              <div style={{ flex: 1, background: C.bg, borderRadius: 13, padding: 11 }}>
                <Sub>{t("cashFloorL")}</Sub>
                <div style={{ fontSize: 15, fontWeight: 900, color: C.ink, marginTop: 2 }}>{profile.cashFloorPct}%</div>
              </div>
            </div>
            {profile.interestedSectors && profile.interestedSectors.length > 0 && (
              <div style={{ background: C.bg, borderRadius: 13, padding: 11 }}>
                <Sub>{t("interestL")}</Sub>
                <div style={{ display: "flex", flexWrap: "wrap", gap: 5, marginTop: 5 }}>
                  {profile.interestedSectors.map((k) => SECTORS[k] && (
                    <Chip key={k} color={SEC(k).color} soft={SEC(k).color + "1A"}>{lang === "ko" ? SEC(k).ko : SEC(k).en}</Chip>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      ) : (
        <div style={{ display: "flex", flexWrap: "wrap", gap: 14, marginTop: 14 }}>
          <GaugeBar value={profile.riskCapacity} label={t("capacity")} hint={t("capacityHint")} color={C.blueDeep} />
          <GaugeBar value={profile.riskTolerance} label={t("tolerance")} hint={t("toleranceHint")} color={C.violet} />
          <div style={{ flex: 1, minWidth: 128 }}>
            <Sub>{t("need")}</Sub>
            <div style={{ fontSize: 22, fontWeight: 900, color: C.ink, marginTop: 2 }}>{pct(profile.riskNeedPct, 0)}</div>
            <div style={{ fontSize: 10.5, color: C.faint, marginTop: 3 }}>{t("needHint")}</div>
          </div>
        </div>
      )}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(90px, 1fr))", gap: 8, marginTop: 14, paddingTop: 13, borderTop: "1px solid " + C.line, textAlign: "center" }}>
        {[[t("targetBeta"), profile.targetBetaMin.toFixed(1) + "–" + profile.targetBetaMax.toFixed(1)], [t("targetVol"), "≤" + profile.targetVolMaxPct + "%"], [t("numStocks"), profile.stocksMin + "–" + profile.stocksMax], [t("maxPos"), profile.maxPositionPct + "%"], [t("maxSector"), profile.maxSectorPct + "%"]].map(([l, v]) => (
          <div key={l} style={{ background: C.bg, borderRadius: 12, padding: "8px 4px" }}>
            <div style={{ fontSize: 10, color: C.faint }}>{l}</div>
            <div style={{ fontSize: 13, fontWeight: 800, color: C.ink, marginTop: 2 }}>{v}</div>
          </div>
        ))}
      </div>
      {profile.tips && profile.tips.length > 0 && (
        <div style={{ marginTop: 12 }}>
          <div style={{ fontSize: 12.5, fontWeight: 800, color: C.ink, marginBottom: 6 }}>{t("tipsTitle")}</div>
          <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
            {profile.tips.map((tip, i) => (
              <div key={i} style={{ fontSize: 12.5, background: C.blueSoft, color: C.blueDeep, borderRadius: 12, padding: "9px 12px", lineHeight: 1.6, fontWeight: 600 }}>→ {tip}</div>
            ))}
          </div>
        </div>
      )}
      {profile.flags && profile.flags.length > 0 && (
        <div style={{ marginTop: 12, display: "flex", flexDirection: "column", gap: 7 }}>
          {profile.flags.map((f, i) => (
            <div key={i} style={{ fontSize: 12.5, background: C.sandSoft, border: "1px solid #F3DCB2", color: "#7A5410", borderRadius: 12, padding: "9px 12px", lineHeight: 1.6 }}>{f}</div>
          ))}
        </div>
      )}
    </Card>
  );
}

function ManualProfile({ lang, t, profile, onSave, onCancel }) {
  const [p, setP] = useState({ ...profile });
  const F = ({ label, k, step = 1, min = 0, max = 100 }) => (
    <label style={{ display: "block" }}>
      <span style={{ fontSize: 11, color: C.sub }}>{label}</span>
      <input type="number" value={p[k]} step={step} min={min} max={max}
        onChange={(e) => setP({ ...p, [k]: parseFloat(e.target.value) || 0 })}
        style={{ marginTop: 3, width: "100%", boxSizing: "border-box", borderRadius: 10, border: "1.5px solid " + C.line, padding: 8, fontSize: 13, fontFamily: FONT, outline: "none" }} />
    </label>
  );
  return (
    <Card>
      <H3>{t("profileTitle")} · {t("edit")}</H3>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(140px, 1fr))", gap: 10, marginTop: 12 }}>
        {F({ label: t("capacity") + " (1-10)", k: "riskCapacity", min: 1, max: 10 })}
        {F({ label: t("tolerance") + " (1-10)", k: "riskTolerance", min: 1, max: 10 })}
        {F({ label: t("need") + " %", k: "riskNeedPct", min: 3, max: 15, step: 0.5 })}
        {F({ label: t("targetBeta") + " min", k: "targetBetaMin", min: 0.3, max: 1.3, step: 0.05 })}
        {F({ label: t("targetBeta") + " max", k: "targetBetaMax", min: 0.5, max: 1.5, step: 0.05 })}
        {F({ label: t("targetVol") + " %", k: "targetVolMaxPct", min: 12, max: 40 })}
        {F({ label: t("numStocks") + " min", k: "stocksMin", min: 4, max: 20 })}
        {F({ label: t("numStocks") + " max", k: "stocksMax", min: 6, max: 25 })}
        {F({ label: t("maxPos") + " %", k: "maxPositionPct", min: 5, max: 30 })}
        {F({ label: t("maxSector") + " %", k: "maxSectorPct", min: 15, max: 50 })}
      </div>
      <div style={{ display: "flex", gap: 8, marginTop: 14 }}>
        <Btn onClick={() => onSave(p)} style={{ flex: 1 }}>{t("save")}</Btn>
        <Btn kind="ghost" onClick={onCancel}>{t("cancel")}</Btn>
      </div>
    </Card>
  );
}

// ================= Stock shelf (market) =================
// ================= Stock picker (search-first) =================
const isCurated = (s) => !!(s.x && s.x.dk && !s.auto);
const popScore = (s) => (s.val || 0) * 1e6 + (s.cap || 0) * 1e3 + (isCurated(s) ? 1 : 0);
const SORTS = { pop: popScore, sh: (s) => (typeof s.sh === "number" ? s.sh : -99),
  al: (s) => (typeof s.al === "number" ? s.al : -999), dy: (s) => s.dy || 0,
  cap: (s) => s.cap || 0, mdd: (s) => (typeof s.mdd === "number" ? s.mdd : -999) };

function StockShelf({ lang, t, mode, interested, stocks, holdings, onAdd, onAddCustom, expanded, setExpanded, updateStock, settings }) {
  const [query, setQuery] = useState("");
  const [market, setMarket] = useState("all");
  const [tab, setTab] = useState("pop");
  const [sort, setSort] = useState("pop");
  const [sector, setSector] = useState("all");
  const [showCustom, setShowCustom] = useState(false);
  const [note, setNote] = useState(null);
  const inCart = new Set(holdings.map((h) => h.t));
  const q = query.trim().toLowerCase();

  const byMarket = useMemo(() => stocks.filter((s) => market === "all" || clsOf(s) === market), [stocks, market]);
  // 2,900개 종목을 행마다 훑으면 느려져서, 업종별 색인을 한 번만 만들어 둡니다.
  const bySector = useMemo(() => {
    const m = {};
    stocks.forEach((s) => { (m[s.s] || (m[s.s] = [])).push(s); });
    return m;
  }, [stocks]);
  const results = useMemo(() => {
    if (q) {
      const hit = byMarket.filter((s) => {
        const sec = SECTORS[s.s] ? (SEC(s.s).ko + SEC(s.s).en).toLowerCase() : "";
        return s.nk.toLowerCase().includes(q) || (s.ne || "").toLowerCase().includes(q) || s.t.toLowerCase().includes(q) || sec.includes(q);
      });
      return hit.sort((a, b) => {
        const ea = a.t.toLowerCase() === q || a.nk.toLowerCase() === q ? 1 : 0;
        const eb = b.t.toLowerCase() === q || b.nk.toLowerCase() === q ? 1 : 0;
        if (ea !== eb) return eb - ea;
        return SORTS[sort](b) - SORTS[sort](a);
      }).slice(0, 50);
    }
    if (tab === "fav") {
      const set = new Set(interested || []);
      return byMarket.filter((s) => set.has(s.s)).sort((a, b) => SORTS[sort](b) - SORTS[sort](a)).slice(0, 60);
    }
    if (tab === "sec") {
      return byMarket.filter((s) => sector === "all" || s.s === sector).sort((a, b) => SORTS[sort](b) - SORTS[sort](a)).slice(0, 60);
    }
    return [...byMarket].sort((a, b) => SORTS[sort](b) - SORTS[sort](a)).slice(0, 100);
  }, [byMarket, q, tab, sector, interested, sort]);

  const grouped = useMemo(() => {
    const g = { kr: [], us: [], metal: [], bond: [] };
    results.forEach((s) => g[clsOf(s)].push(s));
    return CLS_LIST.filter((c) => g[c].length).map((c) => [c, g[c]]);
  }, [results]);

  const add = (s) => {
    onAdd(s);
    if (!isCurated(s)) { setNote(lang === "ko" ? s.nk : s.ne); setTimeout(() => setNote(null), 7000); }
  };
  const TabB = ({ k, label }) => (
    <button onClick={() => setTab(k)} style={{ flex: 1, fontSize: 12, fontWeight: 800, padding: "8px 4px", borderRadius: 10, border: "none", background: tab === k ? C.ink : "transparent", color: tab === k ? "#fff" : C.sub, cursor: "pointer", fontFamily: FONT }}>{label}</button>
  );
  return (
    <Card style={{ padding: 16 }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 9, gap: 8 }}>
        <H3>{t("shelf")}</H3>
        <Chip color={C.faint} soft={C.bg}>{stocks.length.toLocaleString()}{lang === "ko" ? "종목" : ""}</Chip>
      </div>
      <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder={t("searchPh")}
        style={{ width: "100%", boxSizing: "border-box", borderRadius: 12, border: "1.5px solid " + C.line, padding: "11px 12px", fontSize: 14, fontFamily: FONT, outline: "none", background: "#FBFDFF" }} />
      <div style={{ display: "flex", gap: 5, marginTop: 9 }}>
        {[["all", t("mktAll"), C.ink], ["kr", CLASSES.kr.flag, CLASSES.kr.color], ["us", CLASSES.us.flag, CLASSES.us.color], ["metal", CLASSES.metal.flag, CLASSES.metal.color], ["bond", CLASSES.bond.flag, CLASSES.bond.color]].map(([k, label, col]) => (
          <button key={k} onClick={() => setMarket(k)} style={{ flex: 1, fontSize: 11.5, fontWeight: 800, padding: "7px 4px", borderRadius: 10, border: "1.5px solid " + (market === k ? col : C.line), background: market === k ? col : "#fff", color: market === k ? "#fff" : C.sub, cursor: "pointer", fontFamily: FONT }}>{label}</button>
        ))}
      </div>
      {!q && (
        <>
          <div style={{ display: "flex", gap: 3, background: C.bg, borderRadius: 12, padding: 3, marginTop: 9 }}>
            <TabB k="pop" label={t("tabPop")} />
            {(interested || []).length > 0 && <TabB k="fav" label={t("tabFav")} />}
            <TabB k="sec" label={t("tabSec")} />
          </div>
          {tab === "sec" && (
            <div style={{ display: "flex", flexWrap: "wrap", gap: 5, marginTop: 9 }}>
              <button onClick={() => setSector("all")} style={{ fontSize: 11, fontWeight: 700, padding: "5px 10px", borderRadius: 999, border: "1.5px solid " + (sector === "all" ? C.ink : C.line), background: sector === "all" ? C.ink : "#fff", color: sector === "all" ? "#fff" : C.sub, cursor: "pointer", fontFamily: FONT }}>{t("all")}</button>
              {Object.entries(SECTORS).map(([k, v]) => (
                <button key={k} onClick={() => setSector(k)} style={{ fontSize: 11, fontWeight: 700, padding: "5px 10px", borderRadius: 999, border: "1.5px solid " + (sector === k ? v.color : C.line), background: sector === k ? v.color : "#fff", color: sector === k ? "#fff" : C.sub, cursor: "pointer", fontFamily: FONT }}>
                  {(interested || []).includes(k) ? "" : ""}{lang === "ko" ? v.ko : v.en}
                </button>
              ))}
            </div>
          )}
          {tab === "pop" && <Sub style={{ marginTop: 7, fontSize: 11 }}>{t("popNote")}</Sub>}
        </>
      )}
      <div style={{ display: "flex", alignItems: "center", gap: 6, marginTop: 9, overflowX: "auto" }}>
        <span style={{ fontSize: 10.5, color: C.faint, fontWeight: 700, flexShrink: 0 }}>{t("sortBy")}</span>
        {[["pop", t("sortPop")], ["sh", t("sortSh")], ["al", t("sortAl")], ["dy", t("sortDy")], ["cap", t("sortCap")], ["mdd", t("sortMdd")]].map(([k, label]) => (
          <button key={k} onClick={() => setSort(k)} style={{ flexShrink: 0, fontSize: 10.5, fontWeight: 800, padding: "4px 9px", borderRadius: 999, border: "1.5px solid " + (sort === k ? C.violet : C.line), background: sort === k ? C.violet : "#fff", color: sort === k ? "#fff" : C.sub, cursor: "pointer", fontFamily: FONT }}>{label}</button>
        ))}
      </div>
      {sort === "sh" && <Sub style={{ marginTop: 6, fontSize: 10.5 }}>{t("sortShNote")}</Sub>}
      {note && (
        <div style={{ marginTop: 9, background: C.blueSoft, borderRadius: 12, padding: "10px 12px", display: "flex", gap: 8, animation: "fadeIn .2s ease" }}>
          <span style={{ fontSize: 13, flexShrink: 0 }}></span>
          <span style={{ fontSize: 12, color: C.blueDeep, lineHeight: 1.6, fontWeight: 600 }}>
            {lang === "ko" ? <><b>{note}</b>은(는) 아직 설명을 못 적어둔 종목이에요. 담는 건 자유지만, 이 회사가 무엇으로 돈을 버는지 한 문장으로 말할 수 있는지만 스스로 확인해보세요.</> : <>No write-up exists for <b>{note}</b> yet. Adding it is fine — just check that you could explain in one sentence how this company makes money.</>}
          </span>
        </div>
      )}
      <div style={{ maxHeight: 620, overflowY: "auto", margin: "8px -4px 0", padding: "0 4px" }}>
        {grouped.map(([c, list]) => (
          <div key={c}>
            {grouped.length > 1 && (
              <div style={{ fontSize: 11, fontWeight: 800, color: CLASSES[c].color, padding: "9px 2px 4px", position: "sticky", top: 0, background: "#fff", zIndex: 1 }}>
                {CLASSES[c].flag} {lang === "ko" ? CLASSES[c].ko : CLASSES[c].en} <span style={{ color: C.faint, fontWeight: 600 }}>{list.length}</span>
              </div>
            )}
            {list.map((s) => (
              <StockRow key={s.t} s={s} lang={lang} t={t} mode={mode} settings={settings} loaded={inCart.has(s.t)} onAdd={() => add(s)}
                open={expanded === s.t} onToggle={() => setExpanded(expanded === s.t ? null : s.t)}
                peers={(bySector[s.s] || []).slice(0, 12)} updateStock={updateStock} />
            ))}
          </div>
        ))}
        {results.length === 0 && (
          <div style={{ textAlign: "center", padding: "26px 12px" }}>
            <Sub>{q ? t("noHit") : "–"}</Sub>
          </div>
        )}
      </div>
      {q && results.length >= 50 && <Sub style={{ marginTop: 7, fontSize: 11, textAlign: "center" }}>{t("more50")}</Sub>}
      <button onClick={() => setShowCustom(!showCustom)} style={{ marginTop: 10, background: "none", border: "none", color: C.blue, fontSize: 12.5, fontWeight: 700, cursor: "pointer", padding: 0, fontFamily: FONT }}>{t("addCustom")}</button>
      {showCustom && <CustomStockForm lang={lang} t={t} onAdd={(s) => { onAddCustom(s); setShowCustom(false); }} />}
    </Card>
  );
}

function StockRow({ s, lang, t, mode, settings, loaded, onAdd, open, onToggle, peers, updateStock }) {
  const [editing, setEditing] = useState(false);
  const x = s.x || {};
  return (
    <div style={{ borderBottom: "1px solid " + C.line }}>
      <div style={{ display: "flex", alignItems: "center", gap: 10, padding: "11px 0", cursor: "pointer" }} onClick={onToggle}>
        <Mono stock={s} />
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontSize: 13.5, fontWeight: 700, color: C.ink, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
            {lang === "ko" ? s.nk : s.ne} <span style={{ fontSize: 10, color: C.faint, fontWeight: 400 }}>{s.t}</span>
          </div>
          <div style={{ fontSize: 11, color: C.faint }}>
            {isCurated(s) ? "" : ""}{SECTORS[s.s] ? (lang === "ko" ? SEC(s.s).ko : SEC(s.s).en) : "–"} · β {s.beta.toFixed(2)} · σ {s.vol}%{typeof s.sh === "number" ? " · S " + s.sh.toFixed(2) : ""} · {fmtPx(s.price, s)}
          </div>
        </div>
        <button onClick={(e) => { e.stopPropagation(); onAdd(); }} disabled={loaded}
          style={{ fontSize: 12, fontWeight: 800, padding: "8px 14px", borderRadius: 11, border: "none", cursor: loaded ? "default" : "pointer", background: loaded ? C.bg : C.blue, color: loaded ? C.faint : "#fff", fontFamily: FONT, flexShrink: 0 }}>
          {loaded ? t("added") : t("add")}
        </button>
        <span style={{ color: C.faint, fontSize: 11, transform: open ? "rotate(180deg)" : "none", transition: "transform .2s", flexShrink: 0 }}>▼</span>
      </div>
      {open && (
        <div style={{ paddingBottom: 14, animation: "fadeIn .2s ease" }}>
          {x.dk && <div style={{ fontSize: 12.5, color: C.sub, lineHeight: 1.65, background: C.bg, borderRadius: 13, padding: 11 }}>{lang === "ko" ? x.dk : x.de || x.dk}</div>}
          {mode !== "simple" && <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 6, marginTop: 9 }}>
            {[[t("mcap"), (x.mcap != null ? x.mcap + (lang === "ko" ? "조" : "T") : "–")], [t("roe"), pct(x.roe, 1)], [t("opm"), pct(x.opm, 0)], [t("g3"), (x.g3 > 0 ? "+" : "") + (x.g3 != null ? x.g3 + "%/y" : "–")], [t("debt"), pct(x.debt, 0)], [t("frn"), pct(x.frn, 0)], ["PER / PBR", num(s.per, 0) + " / " + num(s.pbr, 1)], [lang === "ko" ? "배당" : "Div", pct(s.dy, 1)], ["3y α", s.al != null ? (s.al > 0 ? "+" : "") + s.al + "%p" : "–"],
              [t("shPast"), typeof s.sh === "number" ? s.sh.toFixed(2) : "–"],
              [t("shCapm"), settings ? (s.beta * clsMrp(clsOf(s), settings) * 100 / Math.max(s.vol, 1)).toFixed(2) : "–"],
              [t("mddL2"), typeof s.mdd === "number" ? s.mdd.toFixed(0) + "%" : "–"],
              [t("momL"), typeof s.mom === "number" ? (s.mom > 0 ? "+" : "") + s.mom.toFixed(0) + "%" : "–"]].map(([k, v]) => (
              <div key={k} style={{ background: C.bg, borderRadius: 10, padding: "8px 5px", textAlign: "center" }}>
                <div style={{ fontSize: 9.5, color: C.faint }}>{k}</div>
                <div style={{ fontSize: 12, fontWeight: 800, color: C.ink, marginTop: 1 }}>{v}</div>
              </div>
            ))}
          </div>}
          {x.lo != null && (
            <div style={{ marginTop: 9 }}>
              <div style={{ display: "flex", justifyContent: "space-between", fontSize: 10, color: C.faint, marginBottom: 3 }}>
                <span>{t("w52")}: {fmtPx(x.lo, s)}</span><span>{fmtPx(x.hi, s)}</span>
              </div>
              <div style={{ position: "relative", height: 6, background: C.line, borderRadius: 3 }}>
                <div style={{ position: "absolute", top: -2, left: "calc(" + Math.min(Math.max(((s.price - x.lo) / Math.max(x.hi - x.lo, 1)) * 100, 0), 100) + "% - 5px)", width: 10, height: 10, borderRadius: "50%", background: C.blue, border: "2px solid #fff", boxShadow: "0 1px 3px rgba(0,0,0,.2)" }} />
              </div>
            </div>
          )}
          {LENS[s.s] && (
            <div style={{ marginTop: 9, background: C.sandSoft, borderRadius: 12, padding: 11 }}>
              <div style={{ fontSize: 11, fontWeight: 800, color: "#7A5410" }}>{t("lensTitle")} · {lang === "ko" ? SEC(s.s).ko : SEC(s.s).en}</div>
              <div style={{ fontSize: 12, color: "#7A5410", lineHeight: 1.65, marginTop: 3 }}>{LENS[s.s][lang]}</div>
            </div>
          )}
          <MiniCheck s={s} peers={peers} lang={lang} t={t} />
          {mode !== "simple" && peers.length > 1 && (
            <div style={{ marginTop: 9 }}>
              <Sub style={{ fontWeight: 700, color: C.ink, marginBottom: 4 }}>{t("peers")}</Sub>
              <div>
                <div style={{ display: "grid", gridTemplateColumns: "1.6fr 0.8fr 0.8fr 0.9fr 0.9fr", fontSize: 10, color: C.faint, padding: "3px 4px" }}>
                  <span></span><span>β</span><span>σ</span><span>PER</span><span>ROE</span>
                </div>
                {peers.map((p) => (
                  <div key={p.t} style={{ display: "grid", gridTemplateColumns: "1.6fr 0.8fr 0.8fr 0.9fr 0.9fr", fontSize: 11.5, padding: "5px 4px", borderTop: "1px solid " + C.line, color: p.t === s.t ? C.blue : C.sub, fontWeight: p.t === s.t ? 800 : 500 }}>
                    <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{lang === "ko" ? p.nk : p.ne}</span>
                    <span>{p.beta.toFixed(2)}</span><span>{p.vol}%</span><span>{num(p.per, 0)}</span><span>{p.x ? pct(p.x.roe, 0) : "–"}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
          <button onClick={() => setEditing(!editing)} style={{ marginTop: 8, background: "none", border: "none", color: C.faint, fontSize: 11.5, fontWeight: 700, cursor: "pointer", padding: 0, fontFamily: FONT }}>{t("editData")}</button>
          {editing && (
            <div style={{ marginTop: 6, display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 6, background: C.bg, borderRadius: 12, padding: 10 }}>
              {["price", "beta", "vol", "per", "pbr", "dy", "al"].map((k) => (
                <label key={k} style={{ display: "block" }}>
                  <span style={{ fontSize: 9.5, color: C.faint, textTransform: "uppercase" }}>{k}</span>
                  <input type="number" step={k === "beta" ? 0.05 : k === "pbr" || k === "dy" ? 0.1 : 1} value={s[k]}
                    onChange={(e) => updateStock(s.t, k, parseFloat(e.target.value) || 0)}
                    style={{ marginTop: 1, width: "100%", boxSizing: "border-box", borderRadius: 8, border: "1px solid " + C.line, padding: 5, fontSize: 12, fontFamily: FONT }} />
                </label>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function CustomStockForm({ lang, t, onAdd }) {
  const [f, setF] = useState({ t: "", nk: "", s: "semi", price: 10000, beta: 1.0, vol: 35, per: 10, pbr: 1, dy: 0, al: 0 });
  const set = (k, v) => setF({ ...f, [k]: v });
  const I = ({ k, label, type = "number", step }) => (
    <label style={{ display: "block" }}>
      <span style={{ fontSize: 10, color: C.faint }}>{label}</span>
      <input type={type} step={step} value={f[k]}
        onChange={(e) => set(k, type === "number" ? parseFloat(e.target.value) || 0 : e.target.value)}
        style={{ marginTop: 2, width: "100%", boxSizing: "border-box", borderRadius: 8, border: "1px solid " + C.line, padding: 6, fontSize: 12, fontFamily: FONT }} />
    </label>
  );
  return (
    <div style={{ marginTop: 8, background: C.bg, borderRadius: 14, padding: 12, display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 8 }}>
      {I({ k: "nk", label: t("name"), type: "text" })}
      {I({ k: "t", label: t("ticker"), type: "text" })}
      <label style={{ display: "block" }}>
        <span style={{ fontSize: 10, color: C.faint }}>{t("sector")}</span>
        <select value={f.s} onChange={(e) => set("s", e.target.value)} style={{ marginTop: 2, width: "100%", borderRadius: 8, border: "1px solid " + C.line, padding: 6, fontSize: 12, fontFamily: FONT, background: "#fff" }}>
          {Object.entries(SECTORS).map(([k, v]) => <option key={k} value={k}>{lang === "ko" ? v.ko : v.en}</option>)}
        </select>
      </label>
      {I({ k: "price", label: t("price") })}
      {I({ k: "beta", label: "β", step: "0.05" })}
      {I({ k: "vol", label: "σ %" })}
      {I({ k: "per", label: "PER" })}
      {I({ k: "pbr", label: "PBR", step: "0.1" })}
      {I({ k: "dy", label: "DY %", step: "0.1" })}
      {I({ k: "al", label: "3y α %p", step: "1" })}
      <button onClick={() => f.nk && f.t && onAdd({ ...f, ne: f.nk, custom: true, x: {} })}
        style={{ gridColumn: "1 / -1", padding: 9, borderRadius: 10, border: "none", background: C.ink, color: "#fff", fontSize: 12.5, fontWeight: 800, cursor: "pointer", fontFamily: FONT }}>{t("add")}</button>
    </div>
  );
}

// ================= Cargo holds (cart with sliders) =================
function Cart({ lang, t, holdings, setHoldings, budgetMw, setBudgetMw, metrics, profile, stocksById, settings }) {
  const setMw = (tk, mw) => setHoldings(holdings.map((h) => (h.t === tk ? { ...h, mw: Math.max(mw, 0) } : h)));
  const sliderMax = Math.max(budgetMw, 100);
  return (
    <Card style={{ padding: 16 }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <H3>{t("myShip")}</H3>
        <div style={{ fontSize: 13, fontWeight: 800, color: metrics.overBudget ? C.coral : C.sub }}>
          {Math.round(metrics.invested / 10000).toLocaleString()} / {budgetMw.toLocaleString()} {t("manwon")}
        </div>
      </div>
      <label style={{ display: "flex", alignItems: "center", gap: 8, margin: "10px 0 4px" }}>
        <span style={{ fontSize: 11.5, color: C.sub, flexShrink: 0 }}>{t("budget")}</span>
        <input type="number" value={budgetMw} min={0} step={100} onChange={(e) => setBudgetMw(parseFloat(e.target.value) || 0)}
          style={{ flex: 1, borderRadius: 10, border: "1.5px solid " + C.line, padding: 8, fontSize: 13.5, textAlign: "right", fontFamily: FONT, outline: "none" }} />
        <span style={{ fontSize: 11, color: C.faint, flexShrink: 0 }}>{t("manwon")} = {fmtMw(budgetMw * 10000, lang)}</span>
      </label>
      <div style={{ height: 7, background: C.line, borderRadius: 4, margin: "8px 0 4px", overflow: "hidden" }}>
        <div style={{ height: 7, width: Math.min((metrics.invested / Math.max(budgetMw * 10000, 1)) * 100, 100) + "%", background: metrics.overBudget ? C.coral : "linear-gradient(90deg," + C.blue + "," + C.teal + ")", transition: "width .3s ease" }} />
      </div>
      {holdings.length === 0 && (
        <div style={{ textAlign: "center", padding: "22px 10px", display: "flex", flexDirection: "column", alignItems: "center", gap: 8 }}>
          <Bird mood="think" size={54} />
          <Sub>{t("emptyCart")}</Sub>
        </div>
      )}
      {holdings.map((h) => {
        const s = stocksById[h.t];
        if (!s) return null;
        const row = metrics.rows.find((r) => r.t === h.t);
        const wInv = row ? row.wInv * 100 : 0;
        const over = profile.ready && wInv > profile.maxPositionPct + 0.01;
        const pk = priceKrw(s, settings);
        const shares = pk > 0 ? Math.floor((h.mw * 10000) / pk) : 0;
        return (
          <div key={h.t} style={{ padding: "11px 0", borderBottom: "1px solid " + C.line }}>
            <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
              <Mono stock={s} size={36} />
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ fontSize: 13, fontWeight: 700, color: C.ink }}>{lang === "ko" ? s.nk : s.ne}</div>
                <div style={{ fontSize: 10.5, color: over ? C.coral : C.faint, fontWeight: over ? 800 : 400 }}>
                  {t("weight")} {wInv.toFixed(1)}% · β {s.beta.toFixed(2)} · ~{shares.toLocaleString()}{lang === "ko" ? "주" : "sh"}{over ? " · " + t("wPos") + "!" : ""}
                </div>
                {s.ccy === "USD" && (
                  <div style={{ fontSize: 10, color: CLASSES.us.color, fontWeight: 700, marginTop: 1 }}>
                    ${(h.mw * 10000 / settings.fx).toFixed(0)} → {shares}{lang === "ko" ? "주" : "sh"} × ${s.price} = ${(shares * s.price).toFixed(0)} · {lang === "ko" ? "남는 돈" : "left"} ${(h.mw * 10000 / settings.fx - shares * s.price).toFixed(0)}
                  </div>
                )}
              </div>
              <input type="number" value={h.mw} min={0} step={10} onChange={(e) => setMw(h.t, parseFloat(e.target.value) || 0)}
                style={{ width: 74, borderRadius: 9, border: "1.5px solid " + (over ? "#F5B5B4" : C.line), padding: "6px 6px", fontSize: 12.5, textAlign: "right", fontFamily: FONT, outline: "none", color: over ? C.coral : C.ink }} />
              <span style={{ fontSize: 10, color: C.faint, flexShrink: 0 }}>{t("manwon")}</span>
              <button onClick={() => setHoldings(holdings.filter((x) => x.t !== h.t))} style={{ background: "none", border: "none", color: C.faint, cursor: "pointer", fontSize: 13, padding: 2, fontFamily: FONT }}></button>
            </div>
            <input type="range" min={0} max={sliderMax} step={10} value={Math.min(h.mw, sliderMax)} onChange={(e) => setMw(h.t, parseInt(e.target.value))}
              style={{ width: "100%", marginTop: 7, accentColor: over ? C.coral : C.blue, cursor: "pointer" }} />
          </div>
        );
      })}
      {!metrics.empty && (
        <div style={{ display: "flex", justifyContent: "space-between", paddingTop: 11, fontSize: 12.5 }}>
          <span style={{ color: C.sub }}>{t("cash")}</span>
          <span style={{ fontWeight: 800, color: metrics.overBudget ? C.coral : C.ink }}>
            {metrics.overBudget ? t("overBudget") + " −" + fmtMw(metrics.invested - budgetMw * 10000, lang) : fmtMw(metrics.cash, lang)}
          </span>
        </div>
      )}
    </Card>
  );
}

// ================= Dashboard, alerts, metrics, insights =================
function Dashboard({ lang, t, metrics, profile, setExplain }) {
  const p = profile;
  const railsBase = { beta: p.targetBetaMin <= metrics.beta && metrics.beta <= p.targetBetaMax };
  // remaining-budget β requirement
  let req = null, impossible = false;
  if (!metrics.empty && metrics.total > 0) {
    const remW = 1 - metrics.investedW / 100;
    if (remW > 0.001) {
      const mid = (p.targetBetaMin + p.targetBetaMax) / 2;
      req = (mid - metrics.beta) / remW;
      if (req > 2) { impossible = true; }
      req = Math.min(Math.max(req, 0), 2);
    }
  }
  return (
    <Card style={{ padding: 16 }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <H3>{t("dash")}</H3>
        <Sub>{t("dashSub")}</Sub>
      </div>
      <Rail emoji="" label={t("railBeta")} value={metrics.beta} valueLabel={"β " + num(metrics.beta)} min={0} max={2}
        tMin={p.targetBetaMin} tMax={p.targetBetaMax} ok={railsBase.beta} onExplain={() => setExplain("beta")}
        extraDot={req} extraLabel={t("railRemaining")} danger={impossible} band={0.15} />
      <div style={{ fontSize: 10.5, color: C.faint, padding: "5px 0 0" }}>{t("betaBand")}</div>
      {req != null && (
        <div style={{ fontSize: 11, color: impossible ? C.coral : C.sub, padding: "6px 0 0", display: "flex", alignItems: "center", gap: 6 }}>
          <span style={{ width: 11, height: 11, borderRadius: "50%", border: "2px dashed " + (impossible ? C.coral : C.sand), display: "inline-block", flexShrink: 0 }} />
          {impossible ? t("railImpossible") : t("railRemaining") + " ≈ " + num(req)}
        </div>
      )}
      <Rail emoji="" label={t("railVol")} value={metrics.volP} valueLabel={pct(metrics.volP)} min={0} max={50}
        tMin={0} tMax={p.targetVolMaxPct} ok={metrics.volP <= p.targetVolMaxPct + 0.01} onExplain={() => setExplain("vol")} />
      <Rail emoji="" label={t("railEffn")} value={metrics.effN} valueLabel={num(metrics.effN, 1)} min={0} max={20}
        tMin={p.stocksMin} tMax={20} ok={metrics.effN >= p.stocksMin * 0.75} onExplain={() => setExplain("effn")} />
      <Rail emoji="" label={t("railSector")} value={metrics.maxSectorW} valueLabel={pct(metrics.maxSectorW, 0)} min={0} max={100}
        tMin={0} tMax={p.maxSectorPct} ok={metrics.maxSectorW <= p.maxSectorPct + 0.01} onExplain={() => setExplain("sector")} />
    </Card>
  );
}

function railStates(metrics, profile) {
  if (metrics.empty || !profile.ready) return { ok: 0, states: [false, false, false, false] };
  const s = [
    profile.targetBetaMin <= metrics.beta && metrics.beta <= profile.targetBetaMax,
    metrics.volP <= profile.targetVolMaxPct + 0.01,
    metrics.effN >= profile.stocksMin * 0.75,
    metrics.maxSectorW <= profile.maxSectorPct + 0.01,
  ];
  return { ok: s.filter(Boolean).length, states: s };
}

function AlertsBox({ lang, t, metrics, profile, stocksById, settings, stocks, holdings, setHoldings, budgetMw }) {
  if (!profile.ready || metrics.empty) return null;
  const w = [];
  if (metrics.overBudget) w.push({ sev: 2, msg: t("wOverBudget") });
  if (metrics.beta > profile.targetBetaMax + 0.001) w.push({ sev: 2, msg: t("wBetaHigh") + ` (β ${num(metrics.beta)} > ${profile.targetBetaMax.toFixed(1)})` });
  else if (metrics.beta < profile.targetBetaMin - 0.001 && metrics.investedW > 50) w.push({ sev: 1, msg: t("wBetaLow") + ` (β ${num(metrics.beta)})` });
  if (metrics.volP > profile.targetVolMaxPct + 0.01) w.push({ sev: 2, msg: t("wVol") + ` (${pct(metrics.volP)} > ${profile.targetVolMaxPct}%)` });
  metrics.rows.forEach((r) => {
    if (r.wInv * 100 > profile.maxPositionPct + 0.01) {
      const s = stocksById[r.t];
      w.push({ sev: 2, msg: t("wPos") + `: ${lang === "ko" ? s.nk : s.ne} ${(r.wInv * 100).toFixed(1)}% > ${profile.maxPositionPct}%` });
    }
  });
  if (metrics.maxSectorW > profile.maxSectorPct + 0.01 && metrics.maxSectorKey) {
    const sec = SECTORS[metrics.maxSectorKey];
    w.push({ sev: 2, msg: t("wSector") + `: ${lang === "ko" ? sec.ko : sec.en} ${metrics.maxSectorW.toFixed(0)}% > ${profile.maxSectorPct}%` });
  }
  const n = metrics.rows.filter((r) => r.mw > 0).length;
  if (n > 0 && n < profile.stocksMin) w.push({ sev: 1, msg: t("wCount") + ` (${n} < ${profile.stocksMin})` });
  if (profile.cashFloorPct > 0) {
    const cp = (metrics.cash / metrics.total) * 100;
    if (cp < profile.cashFloorPct - 0.01) w.push({ sev: 1, msg: t("wCashFloor") + ` (${cp.toFixed(0)}% < ${profile.cashFloorPct}%)` });
  }
  accountIssues(metrics, profile, lang).forEach((m) => w.push({ sev: 2, msg: m }));
  const red = w.some((x) => x.sev === 2);
  return (
    <Card style={{ padding: 16, border: "1.5px solid " + (w.length === 0 ? "#BEE9E4" : red ? "#F7C6C5" : "#F3DCB2"), background: w.length === 0 ? "#F4FBFA" : red ? "#FFF9F9" : "#FFFCF4" }}>
      <div style={{ display: "flex", gap: 12, alignItems: "flex-start" }}>
        <Bird mood={w.length === 0 ? "cheer" : red ? "worried" : "think"} size={48} />
        <div style={{ flex: 1 }}>
          <H3 size={14}>{t("alerts")}</H3>
          {w.length === 0 ? (
            <Sub style={{ marginTop: 4, color: C.teal, fontWeight: 700 }}>{t("noAlerts")}</Sub>
          ) : (
            <div style={{ marginTop: 5, display: "flex", flexDirection: "column", gap: 5 }}>
              {w.map((x, i) => (
                <div key={i} style={{ fontSize: 12.5, fontWeight: 700, color: x.sev === 2 ? C.coral : "#9A6B00", lineHeight: 1.55 }}>• {x.msg}</div>
              ))}
            </div>
          )}
        </div>
      </div>
      {w.length > 0 && setHoldings && (
        <FixList lang={lang} t={t} metrics={metrics} stocksById={stocksById} holdings={holdings} setHoldings={setHoldings}
          fixes={buildFixes({ metrics, profile, settings, stocks, holdings, budgetMw, lang })} />
      )}
    </Card>
  );
}

function MetricsPanel({ lang, t, metrics, profile, setExplain, mode }) {
  if (metrics.empty) return null;
  const items = [
    ["beta", t("mBeta"), num(metrics.beta), profile.ready && !(profile.targetBetaMin <= metrics.beta && metrics.beta <= profile.targetBetaMax)],
    ["ret", t("mRet"), pct(metrics.expRet), false],
    ["vol", t("mVol"), pct(metrics.volP), profile.ready && metrics.volP > profile.targetVolMaxPct],
    ["sharpe", t("mSharpe"), num(metrics.sharpe), false],
    ["cagr", t("mCagr"), pct(metrics.cagr), false],
    ["r2", t("mR2"), pct(metrics.r2, 0), false],
    ["alpha", t("mAl"), (metrics.pastAl > 0 ? "+" : "") + num(metrics.pastAl, 1) + "%p", false],
    ["effn", t("mEffN"), num(metrics.effN, 1), false],
    ["sector", t("mSector"), pct(metrics.maxSectorW, 0), profile.ready && metrics.maxSectorW > profile.maxSectorPct],
    ["per", t("mPer"), num(metrics.per, 1), false],
  ];
  const shown = mode === "simple" ? items.filter(([id]) => ["beta", "ret", "vol", "effn"].includes(id)) : items;
  return (
    <Card style={{ padding: 16 }}>
      <H3>{t("metrics")}</H3>
      <div style={{ display: "grid", gridTemplateColumns: mode === "simple" ? "repeat(2, 1fr)" : "repeat(3, 1fr)", gap: 6, marginTop: 10 }}>
        {shown.map(([id, label, val, alert]) => (
          <button key={id} onClick={() => EXPLAIN[id] && setExplain(id)} style={{ background: C.bg, border: "none", borderRadius: 13, padding: "10px 6px", textAlign: "center", cursor: EXPLAIN[id] ? "pointer" : "default", fontFamily: FONT }}>
            <div style={{ fontSize: 10, color: C.faint }}>{label}{EXPLAIN[id] ? " ?" : ""}</div>
            <div style={{ fontSize: 15, fontWeight: 900, color: alert ? C.coral : C.ink, marginTop: 2 }}>{val}</div>
          </button>
        ))}
      </div>
      <div style={{ marginTop: 9, background: C.blueSoft, borderRadius: 12, padding: "9px 12px", fontSize: 12, fontWeight: 700, color: C.blueDeep, lineHeight: 1.6 }}>
        {lang === "ko"
          ? <>지금 예산 기준: 보통 해 <b>±{fmtMw(metrics.total * metrics.volP / 100, lang)}</b> 출렁 · 기대 <b>+{fmtMw(metrics.total * metrics.expRet / 100, lang)}/년</b></>
          : <>At this budget: a typical year swings <b>±{fmtMw(metrics.total * metrics.volP / 100, lang)}</b> · expected <b>+{fmtMw(metrics.total * metrics.expRet / 100, lang)}/yr</b></>}
      </div>
      {mode !== "simple" && <Sub style={{ marginTop: 8, fontSize: 11 }}>{t("betaErr")}</Sub>}
    </Card>
  );
}

const RC_COLORS = ["#1B2B4B", "#E8987A", "#2E9E8F", "#566BB8", "#C98F2B", "#8C5B74", "#4E7A5A", "#7A8699", "#3B6FD4", "#A3703F"];
function RiskContribCard({ lang, t, metrics, stocksById }) {
  if (metrics.empty || metrics.rows.length < 2) return null;
  const rows = [...metrics.rows].sort((a, b) => b.rc - a.rc).slice(0, 10);
  const topName = stocksById[rows[0].t] ? (lang === "ko" ? stocksById[rows[0].t].nk : stocksById[rows[0].t].ne) : "";
  return (
    <Card style={{ padding: 16 }}>
      <H3>{t("riskContrib")}</H3>
      <Sub style={{ marginTop: 3 }}>
        {lang === "ko"
          ? <>{topName}에 돈의 <b>{(rows[0].wInv * 100).toFixed(0)}%</b>를 넣었는데, 위험의 <b style={{ color: C.coral }}>{(rows[0].rc * 100).toFixed(0)}%</b>가 거기서 나와요.</>
          : <>{topName} holds <b>{(rows[0].wInv * 100).toFixed(0)}%</b> of your money but <b style={{ color: C.coral }}>{(rows[0].rc * 100).toFixed(0)}%</b> of your risk.</>}
      </Sub>
      {[["wInv", t("moneyBase")], ["rc", t("riskBase")]].map(([k, label]) => (
        <div key={k} style={{ marginTop: 10 }}>
          <Sub style={{ fontWeight: 700, marginBottom: 4 }}>{label}</Sub>
          <div style={{ display: "flex", height: 24, borderRadius: 8, overflow: "hidden" }}>
            {rows.map((r, i) => {
              const v = r[k] * 100;
              const nm = stocksById[r.t] ? (lang === "ko" ? stocksById[r.t].nk : stocksById[r.t].ne) : r.t;
              return (
                <div key={r.t} title={nm + " " + v.toFixed(1) + "%"} style={{ width: v + "%", background: RC_COLORS[i % RC_COLORS.length], display: "flex", alignItems: "center", justifyContent: "center", overflow: "hidden", whiteSpace: "nowrap", fontSize: 9.5, color: "#fff", fontWeight: 800, transition: "width .3s ease" }}>
                  {v >= 14 ? nm : ""}
                </div>
              );
            })}
          </div>
        </div>
      ))}
    </Card>
  );
}

function GoalGapCard({ lang, t, metrics, profile }) {
  if (metrics.empty || !profile.ready) return null;
  const need = profile.riskNeedPct, ret = metrics.expRet;
  const gap = need - ret;
  const okv = gap <= 0.5;
  return (
    <Card style={{ padding: 16, background: okv ? "#F4FBFA" : "#FFFCF4", border: "1.5px solid " + (okv ? "#BEE9E4" : "#F3DCB2") }}>
      <H3>{t("goalGap")}</H3>
      <div style={{ fontSize: 13, color: C.ink, lineHeight: 1.7, marginTop: 6 }}>
        {okv ? T.gapOk[lang](num(need, 1), num(ret, 1)) : T.gapShort[lang](num(need, 1), num(ret, 1), num(gap, 1))}
      </div>
    </Card>
  );
}

function ProjectionCard({ lang, t, metrics, settings }) {
  if (metrics.empty) return null;
  const [yrs, setYrs] = useState(20);
  const [real, setReal] = useState(false);
  const infl = (settings && settings.infl != null ? settings.infl : 2.0) / 100;
  const mid = metrics.cagr / 100 - (real ? infl : 0), sd = metrics.volP / 100;
  const se = sd / Math.sqrt(yrs);
  const rOpt = mid + 1.28 * se, rPes = mid - 1.28 * se;
  const base = metrics.total;
  const W = 320, Hh = 130;
  const grow = (r) => { const a = [[0, base]]; let v = base; for (let y = 1; y <= yrs; y++) { v *= 1 + r; a.push([y, v]); } return a; };
  const opt = grow(rOpt), midA = grow(mid), pes = grow(Math.max(rPes, -0.5));
  const maxV = opt[yrs][1] * 1.05;
  const x = (y) => 34 + (y / yrs) * (W - 70);
  const yv = (v) => Hh - 16 - (v / maxV) * (Hh - 30);
  const path = (arr) => arr.map(([a, b], i) => (i === 0 ? "M" : "L") + x(a) + "," + yv(b)).join(" ");
  const area = path(opt) + " " + [...pes].reverse().map(([a, b]) => "L" + x(a) + "," + yv(b)).join(" ") + " Z";
  return (
    <Card style={{ padding: 16 }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <H3>{t("projection")}</H3>
        <div style={{ display: "flex", gap: 4 }}>
          <button onClick={() => setReal(!real)} style={{ fontSize: 11, fontWeight: 800, padding: "4px 10px", borderRadius: 999, border: "1.5px solid " + (real ? C.teal : C.line), background: real ? C.teal : "#fff", color: real ? "#fff" : C.sub, cursor: "pointer", fontFamily: FONT, marginRight: 4 }}>{t("realBtn")}</button>
          {[10, 20, 30].map((y) => (
            <button key={y} onClick={() => setYrs(y)} style={{ fontSize: 11, fontWeight: 800, padding: "4px 10px", borderRadius: 999, border: "1.5px solid " + (yrs === y ? C.blue : C.line), background: yrs === y ? C.blue : "#fff", color: yrs === y ? "#fff" : C.sub, cursor: "pointer", fontFamily: FONT }}>{y}{lang === "ko" ? "년" : "y"}</button>
          ))}
        </div>
      </div>
      <Sub style={{ marginTop: 4 }}>{t("projSub")}{real ? " · " + t("realNote") : ""}</Sub>
      <svg width="100%" viewBox={"0 0 " + W + " " + Hh} style={{ marginTop: 6 }}>
        <path d={area} fill={C.blueSoft} />
        <path d={path(opt)} fill="none" stroke={C.teal} strokeWidth="2" strokeDasharray="4 3" />
        <path d={path(midA)} fill="none" stroke={C.blueDeep} strokeWidth="2.5" />
        <path d={path(pes)} fill="none" stroke={C.coral} strokeWidth="2" strokeDasharray="4 3" />
      </svg>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 6 }}>
        {[[lang === "ko" ? "운 좋으면 (상위 10%)" : "Lucky (top 10%)", opt[yrs][1], C.teal], [lang === "ko" ? "기대치" : "Expected", midA[yrs][1], C.blueDeep], [lang === "ko" ? "운 나쁘면 (하위 10%)" : "Unlucky (bottom 10%)", pes[yrs][1], C.coral]].map(([l, v, col]) => (
          <div key={l} style={{ background: C.bg, borderRadius: 12, padding: "8px 6px", textAlign: "center" }}>
            <div style={{ fontSize: 9.5, color: C.faint }}>{l}</div>
            <div style={{ fontSize: 13, fontWeight: 900, color: col, marginTop: 2 }}>{fmtMw(v, lang)}</div>
          </div>
        ))}
      </div>
      <Sub style={{ marginTop: 8, fontSize: 11 }}>
        {lang === "ko" ? "연간 배당 예상: " : "Est. annual dividends: "}<b style={{ color: C.ink }}>{fmtMw(metrics.divWon, lang)}</b>{lang === "ko" ? " (재투자 가정 없음 · 세전)" : " (no reinvestment, pre-tax)"}
      </Sub>
    </Card>
  );
}

function BenchCard({ lang, t, metrics, profile, settings }) {
  if (metrics.empty) return null;
  const b = benchMetrics(settings);
  const robo = profile.ready ? roboMix(profile, settings) : null;
  const n = metrics.rows.filter((r) => r.mw > 0).length;
  let eq = null;
  if (n >= 2) {
    const eqH = metrics.rows.filter((r) => r.mw > 0).map((r) => ({ t: r.t, mw: metrics.invested / n / 10000, won: metrics.invested / n, stock: r.stock }));
    eq = computeMetrics(eqH, metrics.total, settings);
  }
  const rows = [
    [t("mine"), "β " + num(metrics.beta) + " · σ " + pct(metrics.volP) + " · E(r) " + pct(metrics.expRet) + " · Sharpe " + num(metrics.sharpe), true],
    [t("benchIdx"), "β 1.00 · σ " + pct(b.volP, 0) + " · E(r) " + pct(b.expRet) + " · Sharpe " + num(b.sharpe), false],
  ];
  if (eq && !eq.empty) rows.push([t("oneN"), "β " + num(eq.beta) + " · σ " + pct(eq.volP) + " · E(r) " + pct(eq.expRet) + " · Sharpe " + num(eq.sharpe), false]);
  if (robo) rows.push([t("benchRobo"), (lang === "ko" ? "인덱스 " : "index ") + robo.wIdx.toFixed(0) + "% + " + (lang === "ko" ? "현금 " : "cash ") + (100 - robo.wIdx).toFixed(0) + "% · σ " + pct(robo.volP) + " · E(r) " + pct(robo.expRet), false]);
  const worse = metrics.sharpe < b.sharpe - 0.001;
  return (
    <Card style={{ padding: 16 }}>
      <H3>{t("bench")}</H3>
      <div style={{ marginTop: 10, display: "flex", flexDirection: "column", gap: 6 }}>
        {rows.map(([nm, d, mine]) => (
          <div key={nm} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 10, background: mine ? C.blueSoft : C.bg, borderRadius: 13, padding: "10px 12px" }}>
            <span style={{ fontSize: 12.5, fontWeight: mine ? 900 : 700, color: mine ? C.blueDeep : C.ink, flexShrink: 0 }}>{nm}</span>
            <span style={{ fontSize: 11, color: C.sub, textAlign: "right" }}>{d}</span>
          </div>
        ))}
      </div>
      {eq && !eq.empty && <Sub style={{ marginTop: 8, fontSize: 11 }}>{t("oneNNote")}</Sub>}
      <Sub style={{ marginTop: 8 }}>{worse ? t("benchNote") : (lang === "ko" ? "지금은 위험 대비 효율(샤프)이 인덱스보다 낫네요. 다만 이 계산은 과거 추정치 기반이라, 겸손함은 늘 챙겨가세요." : "Your Sharpe currently beats the index — but this rests on historical estimates, so pack humility.")}</Sub>
    </Card>
  );
}

// ================= v4.5 diagnostic components =================
function Verdict({ children }) {
  return (
    <div style={{ display: "flex", gap: 8, alignItems: "flex-start", background: C.blueSoft, borderRadius: 12, padding: "9px 12px", marginTop: 8 }}>
      <span style={{ fontSize: 13, flexShrink: 0 }}></span>
      <span style={{ fontSize: 12.5, fontWeight: 700, color: C.blueDeep, lineHeight: 1.6 }}>{children}</span>
    </div>
  );
}
function SectionH({ children }) {
  return <div style={{ padding: "6px 4px 0" }}><H3 size={16}>{children}</H3></div>;
}
function IconArray({ p, color }) {
  const k = Math.round(Math.min(Math.max(p, 0), 1) * 100);
  return (
    <div style={{ display: "grid", gridTemplateColumns: "repeat(20, 1fr)", gap: 2.5, width: "100%", maxWidth: 210 }}>
      {Array.from({ length: 100 }, (_, i) => (
        <div key={i} style={{ width: 6, height: 6, borderRadius: "50%", background: i < k ? color : C.line, transition: "background .3s" }} />
      ))}
    </div>
  );
}

function ProbCard({ lang, t, metrics, profile }) {
  const [yrs, setYrs] = useState(10);
  if (metrics.empty) return null;
  const mu = metrics.cagr / 100, sd = metrics.volP / 100;
  const pLoss = normCdf((0 - mu) * Math.sqrt(yrs) / sd);
  const need = profile.ready ? profile.riskNeedPct / 100 : null;
  const pGoal = need != null ? 1 - normCdf((need - mu) * Math.sqrt(yrs) / sd) : null;
  const kL = Math.round(pLoss * 100), kG = pGoal != null ? Math.round(pGoal * 100) : null;
  return (
    <Card style={{ padding: 16 }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8 }}>
        <H3>{t("probTitle")}</H3>
        <div style={{ display: "flex", gap: 4 }}>
          {[1, 5, 10, 20].map((y) => (
            <button key={y} onClick={() => setYrs(y)} style={{ fontSize: 11, fontWeight: 800, padding: "4px 9px", borderRadius: 999, border: "1.5px solid " + (yrs === y ? C.blue : C.line), background: yrs === y ? C.blue : "#fff", color: yrs === y ? "#fff" : C.sub, cursor: "pointer", fontFamily: FONT }}>{y}{lang === "ko" ? "년" : "y"}</button>
          ))}
        </div>
      </div>
      <Sub style={{ marginTop: 3 }}>{t("probSub")}</Sub>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14, marginTop: 12 }}>
        <div>
          <Sub style={{ fontWeight: 700, color: C.ink }}>{t("probLoss")}</Sub>
          <div style={{ fontSize: 24, fontWeight: 900, color: kL >= 25 ? C.coral : C.ink, margin: "3px 0 7px" }}>{kL}%</div>
          <IconArray p={pLoss} color={C.coral} />
          <div style={{ fontSize: 10.5, color: C.faint, marginTop: 5 }}>{lang === "ko" ? `100번의 ${yrs}년 중 약 ${kL}번은 원금보다 적게 끝나요` : `~${kL} of 100 such ${yrs}-year runs end below principal`}</div>
        </div>
        <div>
          <Sub style={{ fontWeight: 700, color: C.ink }}>{t("probGoal")}{need != null ? ` (연 ${profile.riskNeedPct}%)` : ""}</Sub>
          {pGoal != null ? (
            <>
              <div style={{ fontSize: 24, fontWeight: 900, color: kG >= 50 ? C.teal : C.sand, margin: "3px 0 7px" }}>{kG}%</div>
              <IconArray p={pGoal} color={C.teal} />
              <div style={{ fontSize: 10.5, color: C.faint, marginTop: 5 }}>{lang === "ko" ? `100번 중 약 ${kG}번은 목표를 넘어서 끝나요` : `~${kG} of 100 runs end above the goal`}</div>
            </>
          ) : <Sub style={{ marginTop: 6 }}>{t("needProfile")}</Sub>}
        </div>
      </div>
      <Verdict>
        {lang === "ko"
          ? `시간이 최고의 아군이에요. 1년 → ${Math.round(normCdf(-mu / sd) * 100)}%였던 손실 확률이 ${yrs}년이면 ${kL}%가 돼요.`
          : `Time is your best ally: a ${Math.round(normCdf(-mu / sd) * 100)}% one-year loss chance becomes ${kL}% over ${yrs} years.`}
      </Verdict>
    </Card>
  );
}

function TailRiskCard({ lang, t, metrics }) {
  if (metrics.empty) return null;
  const mu = metrics.expRet / 100, sd = metrics.volP / 100, total = metrics.total;
  const varRet = mu - 1.645 * sd;
  const cvarRet = mu - 2.063 * sd;
  const beta = metrics.beta;
  return (
    <Card style={{ padding: 16 }}>
      <H3>{t("varTitle")}</H3>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8, marginTop: 10 }}>
        {[[t("varBad"), varRet], [t("varWorse"), cvarRet]].map(([l, r]) => (
          <div key={l} style={{ background: C.bg, borderRadius: 14, padding: 12 }}>
            <Sub>{l}</Sub>
            <div style={{ fontSize: 19, fontWeight: 900, color: r < 0 ? C.coral : C.teal, marginTop: 3 }}>{r < 0 ? "−" : "+"}{fmtMw(Math.abs(total * r), lang)}</div>
            <div style={{ fontSize: 10.5, color: C.faint }}>{pct(r * 100)}</div>
          </div>
        ))}
      </div>
      <div style={{ display: "flex", justifyContent: "space-between", background: C.coralSoft, borderRadius: 12, padding: "9px 12px", marginTop: 8 }}>
        <span style={{ fontSize: 12, fontWeight: 700, color: "#8E2A28" }}>{lang === "ko" ? "2008년급 (시장 −40%)" : "2008-scale (market −40%)"}</span>
        <span style={{ fontSize: 12.5, fontWeight: 900, color: C.coral }}>≈ −{fmtMw(total * beta * 0.4, lang)}</span>
      </div>
      {(() => {
        let wm = 0, wh = 0, sm = 0, sh2 = 0;
        metrics.rows.forEach((r) => {
          if (typeof r.stock.mdd === "number") { sm += r.wInv * r.stock.mdd; wm += r.wInv; }
          if (typeof r.stock.hit === "number") { sh2 += r.wInv * r.stock.hit; wh += r.wInv; }
        });
        if (wm < 0.3 && wh < 0.3) return null;
        return (
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8, marginTop: 8 }}>
            {wm >= 0.3 && (
              <div style={{ background: C.bg, borderRadius: 12, padding: 11 }}>
                <div style={{ fontSize: 10.5, color: C.faint }}>{t("mddL")}</div>
                <div style={{ fontSize: 17, fontWeight: 900, color: C.coral, marginTop: 2 }}>{pct(sm / wm, 0)}</div>
              </div>
            )}
            {wh >= 0.3 && (
              <div style={{ background: C.bg, borderRadius: 12, padding: 11 }}>
                <div style={{ fontSize: 10.5, color: C.faint }}>{t("hitL")}</div>
                <div style={{ fontSize: 17, fontWeight: 900, color: C.ink, marginTop: 2 }}>{pct(sh2 / wh, 0)}</div>
              </div>
            )}
          </div>
        );
      })()}
      <Sub style={{ marginTop: 8, fontSize: 11 }}>{t("varNote")}</Sub>
      <Verdict>{lang === "ko" ? "이 금액들을 보고도 잠이 온다면, 이 구성으로 오래 갈 수 있어요. 그게 수익률보다 중요해요." : "If you can sleep seeing these numbers, you can stay the course — which matters more than returns."}</Verdict>
    </Card>
  );
}

function SectorDonut({ lang, t, metrics, stocksById }) {
  if (metrics.empty) return null;
  const entries = Object.entries(metrics.sectorW).map(([k, w]) => ({ k, w: w / (metrics.investedW / 100) })).sort((a, b) => b.w - a.w);
  const CIRCUM = 2 * Math.PI * 44;
  let cum = 0;
  const top = entries[0];
  return (
    <Card style={{ padding: 16 }}>
      <H3>{t("donutTitle")}</H3>
      <div style={{ display: "flex", gap: 16, alignItems: "center", marginTop: 10 }}>
        <svg width="130" height="130" viewBox="0 0 120 120" style={{ flexShrink: 0 }}>
          {entries.map((e) => {
            const dash = e.w * CIRCUM;
            const rot = cum * 360 - 90;
            cum += e.w;
            return <circle key={e.k} cx="60" cy="60" r="44" fill="none" stroke={SEC(e.k).color} strokeWidth="20" strokeDasharray={dash + " " + CIRCUM} transform={"rotate(" + rot + " 60 60)"} />;
          })}
          <text x="60" y="57" textAnchor="middle" style={{ fontSize: 11, fontWeight: 800, fill: C.ink, fontFamily: FONT }}>{entries.length}{lang === "ko" ? "개" : ""}</text>
          <text x="60" y="70" textAnchor="middle" style={{ fontSize: 9, fill: C.faint, fontFamily: FONT }}>{lang === "ko" ? "섹터" : "sectors"}</text>
        </svg>
        <div style={{ flex: 1, display: "flex", flexDirection: "column", gap: 4, minWidth: 0 }}>
          {entries.slice(0, 6).map((e) => (
            <div key={e.k} style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 11.5 }}>
              <span style={{ width: 9, height: 9, borderRadius: 3, background: SEC(e.k).color, flexShrink: 0 }} />
              <span style={{ flex: 1, color: C.ink, fontWeight: 700, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{lang === "ko" ? SEC(e.k).ko : SEC(e.k).en}</span>
              <span style={{ color: C.sub, fontWeight: 800 }}>{(e.w * 100).toFixed(0)}%</span>
              <span style={{ color: C.faint, fontSize: 10.5 }}>{fmtMw(metrics.invested * e.w, lang)}</span>
            </div>
          ))}
          {entries.length > 6 && <Sub style={{ fontSize: 10.5 }}>+{entries.length - 6}</Sub>}
        </div>
      </div>
      {top && (
        <Verdict>
          {lang === "ko"
            ? <>내 돈의 <b>{(top.w * 100).toFixed(0)}%</b>가 <b>{SEC(top.k).ko}</b> 업황 하나에 달려 있어요. {top.w > 0.4 ? "우산 장수 이야기처럼, 날씨(업황) 하나에 온 살림이 출렁일 수 있어요." : "업종이 여러 곳에 적당히 나뉘어 있어요."}</>
            : <><b>{(top.w * 100).toFixed(0)}%</b> of your money hangs on <b>{SEC(top.k).en}</b> conditions alone. {top.w > 0.4 ? "Like the umbrella-seller tale — one turn of weather shakes the whole household." : "Reasonably split across industries."}</>}
        </Verdict>
      )}
    </Card>
  );
}

function QuickFactsCard({ lang, t, metrics, settings, profile }) {
  if (metrics.empty) return null;
  const depEq = metrics.divWon / Math.max(settings.rf / 100, 0.001);
  const cashPct = (metrics.cash / metrics.total) * 100;
  const rows = [
    [t("qTop3"), pct(metrics.top3, 0)],
    [t("qDiv"), fmtMw(metrics.divWon, lang) + (lang === "ko" ? ` (예금 ${fmtMw(depEq, lang)} 이자와 비슷)` : ` (≈ interest on ${fmtMw(depEq, lang)} deposit)`)],
    [t("qCash"), pct(cashPct, 0) + (cashPct > 25 && profile.ready ? (lang === "ko" ? " · 꽤 쉬고 있어요" : " · quite idle") : "")],
  ];
  return (
    <Card style={{ padding: 16 }}>
      <H3>{t("quickTitle")}</H3>
      <div style={{ marginTop: 8, display: "flex", flexDirection: "column", gap: 6 }}>
        {rows.map(([l, v]) => (
          <div key={l} style={{ display: "flex", justifyContent: "space-between", gap: 10, background: C.bg, borderRadius: 12, padding: "9px 12px" }}>
            <span style={{ fontSize: 12, color: C.sub, fontWeight: 700, flexShrink: 0 }}>{l}</span>
            <span style={{ fontSize: 12, color: C.ink, fontWeight: 800, textAlign: "right" }}>{v}</span>
          </div>
        ))}
      </div>
    </Card>
  );
}

function MiniCheck({ s, peers, lang, t }) {
  const others = peers.filter((p) => p.x && p.x.roe != null);
  if (others.length < 3) {
    return <div style={{ marginTop: 9, background: C.bg, borderRadius: 12, padding: 10, fontSize: 11.5, color: C.faint }}>{t("chkTitle")}: {t("chkNoPeers")}</div>;
  }
  const med = (arr) => { const a = [...arr].sort((x, y) => x - y); return a[Math.floor(a.length / 2)]; };
  const roeMed = med(others.map((p) => p.x.roe || 0));
  const debtMed = med(others.map((p) => p.x.debt || 0));
  const perMed = med(others.map((p) => p.per || 0));
  const isFin = s.s === "finance";
  const lvl = (good, mid) => (good ? 0 : mid ? 1 : 2);
  const roeL = lvl((s.x?.roe || 0) >= roeMed, (s.x?.roe || 0) >= roeMed * 0.7);
  const debtL = isFin ? -1 : lvl((s.x?.debt || 0) <= debtMed, (s.x?.debt || 0) <= debtMed * 1.5);
  const perL = lvl(s.per <= perMed, s.per <= perMed * 1.3);
  const W = {
    p: lang === "ko" ? ["좋은 편", "보통", "아쉬운 편"] : ["Good", "OK", "Weak"],
    v: lang === "ko" ? ["낮은 편", "보통", "높은 편"] : ["Low", "Mid", "High"],
  };
  const CL = [[C.teal, C.tealSoft], ["#9A6B00", C.sandSoft], [C.coral, C.coralSoft]];
  const Row = ({ label, i, words }) => (
    <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
      <span style={{ fontSize: 11.5, color: C.sub }}>{label}</span>
      {i === -1 ? <span style={{ fontSize: 11, color: C.faint }}>—</span> :
        <Chip color={CL[i][0]} soft={CL[i][1]}>{words[i]}</Chip>}
    </div>
  );
  return (
    <div style={{ marginTop: 9, background: C.bg, borderRadius: 12, padding: 11 }}>
      <div style={{ fontSize: 11, fontWeight: 800, color: C.ink, marginBottom: 6 }}>{t("chkTitle")}</div>
      <div style={{ display: "flex", flexDirection: "column", gap: 5 }}>
        <Row label={t("chkProfit")} i={roeL} words={W.p} />
        <Row label={t("chkSafety")} i={debtL} words={W.p} />
        <Row label={t("chkValue")} i={perL} words={W.v} />
      </div>
      <div style={{ fontSize: 10, color: C.faint, marginTop: 6, lineHeight: 1.5 }}>{t("chkNote")}</div>
    </div>
  );
}

// ================= 내 위험은 어디서 오나요 (구성 위험 해부) =================
function RiskJourneyCard({ lang, t, metrics, stocksById, settings, profile, mode }) {
  const [showDetail, setShowDetail] = useState(false);
  if (metrics.empty) return null;
  const ko = lang === "ko";
  const sysVol = metrics.volP * Math.sqrt(Math.max(metrics.r2, 0) / 100);
  const idioVolStack = Math.max(metrics.volP - sysVol, 0);
  const sep = Math.max(metrics.wAvgVol, metrics.volP);
  const own = 100 - metrics.r2;                 // 개별 회사 때문에 흔들리는 비율
  const n = metrics.rows.filter((r) => r.mw > 0).length;
  const idioVarTot = metrics.rows.reduce((a, r) => a + r.w * r.w * r.idio, 0);
  let eqOwn = null;
  if (n >= 2) {
    const eqH = metrics.rows.filter((r) => r.mw > 0).map((r) => ({ t: r.t, mw: metrics.invested / n / 10000, won: metrics.invested / n, stock: r.stock }));
    const eq = computeMetrics(eqH, metrics.total, settings);
    if (!eq.empty) eqOwn = 100 - eq.r2;
  }
  let bigC = null;
  metrics.rows.forEach((r) => { const c = r.w * r.w * r.idio; if (!bigC || c > bigC.c) bigC = { c, r }; });

  // 어디쯤인지 알려주는 기준점 — 숫자만 보고 불안해지지 않게
  const band = own <= 25 ? 0 : own <= 40 ? 1 : 2;
  const bandTxt = [
    ko ? "잘 분산된 편이에요" : "Well spread",
    ko ? "보통이에요" : "About average",
    ko ? "한쪽에 많이 쏠려 있어요" : "Quite concentrated",
  ][band];
  const bandCol = [C.teal, "#9A6B00", C.coral][band];

  const levers = [];
  if (band === 0) levers.push({ icon: "", text: t("rjGood") });
  else {
    if (eqOwn != null && eqOwn < own - 1.5) levers.push({
      icon: "", bars: [own, eqOwn],
      text: ko ? `지금 종목 그대로, 비중만 고르게 나눠도 이 비율이 ${own.toFixed(0)}% → ${eqOwn.toFixed(0)}%로 내려가요.`
               : `Same stocks, evened weights: this share drops ${own.toFixed(0)}% → ${eqOwn.toFixed(0)}%.`,
    });
    if (bigC && idioVarTot > 0 && bigC.c / idioVarTot > 0.35) {
      const nm = ko ? bigC.r.stock.nk : bigC.r.stock.ne;
      levers.push({ icon: "", text: ko ? `특히 ${nm} 비중을 줄이는 효과가 가장 커요 — 이 부분의 ${(bigC.c / idioVarTot * 100).toFixed(0)}%가 이 한 종목에서 나와요.` : `Trimming ${nm} helps most — ${(bigC.c / idioVarTot * 100).toFixed(0)}% of this comes from that one name.` });
    }
    if (n < (profile.ready ? profile.stocksMax : 15)) {
      const newVol = Math.sqrt(Math.pow(sysVol / 100, 2) + idioVarTot * n / (n + 3)) * 100;
      const dd = metrics.volP - newVol;
      if (dd > 0.8) levers.push({ icon: "", text: ko ? `성격이 겹치지 않는 종목 3개를 더 나눠 담으면 전체 출렁임이 약 ${dd.toFixed(1)}%p 줄어요 (√n 효과).` : `Three more non-overlapping names cut total swing by ~${dd.toFixed(1)}%p (the √n effect).` });
    }
    const nSec = Object.keys(metrics.sectorW).length;
    if (nSec < 3) levers.push({ icon: "", text: ko ? `업종이 ${nSec}곳뿐이에요. 서로 다른 업종 3곳 이상으로 나누면 뉴스 하나에 전체가 흔들리는 일을 막을 수 있어요.` : `Only ${nSec} industr${nSec === 1 ? "y" : "ies"} — three or more keeps one headline from shaking everything.` });
  }

  const W = 372, H = 178, baseY = 148, scale = 112 / Math.max(sep, 1);
  const bw = 80, x1 = 16, x2 = 146, x3 = 276;
  const y = (v) => baseY - v * scale;
  const ANCH = [[0, ko ? "인덱스" : "index"], [20, ""], [40, ""], [65, ko ? "한 종목" : "one stock"]];

  return (
    <Card style={{ padding: 18 }}>
      <H3>{t("splitTitle")}</H3>
      <Sub style={{ marginTop: 3 }}>{t("splitSub")}</Sub>

      <div style={{ display: "flex", height: 30, borderRadius: 9, overflow: "hidden", marginTop: 12 }}>
        <div style={{ width: metrics.r2 + "%", background: C.blue, display: "flex", alignItems: "center", justifyContent: "center", color: "#fff", fontSize: 11.5, fontWeight: 800, minWidth: 40 }}>{metrics.r2.toFixed(0)}%</div>
        <div style={{ flex: 1, background: "#F0954F", display: "flex", alignItems: "center", justifyContent: "center", color: "#fff", fontSize: 11.5, fontWeight: 800 }}>{own.toFixed(0)}%</div>
      </div>
      <div style={{ display: "flex", justifyContent: "space-between", fontSize: 11, marginTop: 4 }}>
        <span style={{ color: C.blueDeep, fontWeight: 700 }}>{t("splitComp")}</span>
        <span style={{ color: "#C05621", fontWeight: 700 }}>{t("splitIdio")}</span>
      </div>

      {/* 기준점 — 내 숫자가 보통인지 아닌지 바로 알 수 있게 */}
      <div style={{ marginTop: 14, background: C.bg, borderRadius: 14, padding: "12px 13px" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
          <span style={{ fontSize: 12, color: C.sub, fontWeight: 700 }}>{t("rjWhere")}</span>
          <span style={{ fontSize: 13, fontWeight: 900, color: bandCol }}>{own.toFixed(0)}% · {bandTxt}</span>
        </div>
        <div style={{ position: "relative", height: 30, marginTop: 8 }}>
          <div style={{ position: "absolute", top: 9, left: 0, right: 0, height: 6, borderRadius: 3, background: "linear-gradient(90deg," + C.teal + "," + C.sand + "," + C.coral + ")" }} />
          {ANCH.map(([v, lab]) => (
            <div key={v} style={{ position: "absolute", left: Math.min(v / 70 * 100, 100) + "%", top: 4 }}>
              <div style={{ width: 1.5, height: 16, background: "#fff" }} />
              {lab && <div style={{ fontSize: 9, color: C.faint, transform: "translateX(-50%)", whiteSpace: "nowrap", marginTop: 1 }}>{lab}</div>}
            </div>
          ))}
          <div style={{ position: "absolute", top: 2, left: "calc(" + Math.min(own / 70 * 100, 100) + "% - 8px)", width: 16, height: 16, borderRadius: "50%", background: "#fff", border: "3px solid " + bandCol, transition: "left .3s ease" }} />
        </div>
        <div style={{ fontSize: 11.5, color: C.sub, lineHeight: 1.65, marginTop: 6 }}>{t("rjAnchor")}</div>
      </div>

      <div style={{ marginTop: 12, background: C.blueSoft, borderRadius: 14, padding: 13 }}>
        <div style={{ fontSize: 12.5, fontWeight: 800, color: C.blueDeep }}>{t("rjZeroTitle")}</div>
        <div style={{ fontSize: 12.5, color: C.blueDeep, lineHeight: 1.7, marginTop: 4 }}>{t("rjZeroBody")}</div>
      </div>

      <svg width="100%" viewBox={"0 0 " + W + " " + H} style={{ marginTop: 14 }}>
        <line x1="8" x2={W - 8} y1={baseY} y2={baseY} stroke={C.line} strokeWidth="1.5" />
        <rect x={x1} y={y(sep)} width={bw} height={sep * scale} rx="7" fill="#C9D6E2" />
        <text x={x1 + bw / 2} y={y(sep) - 6} textAnchor="middle" style={{ fontSize: 12, fontWeight: 800, fill: C.sub, fontFamily: FONT }}>{sep.toFixed(1)}%</text>
        <line x1={x1 + bw} y1={y(sep)} x2={x2} y2={y(sep)} stroke={C.faint} strokeDasharray="3 3" />
        <rect x={x2} y={y(sep)} width={bw} height={Math.max((sep - metrics.volP) * scale, 2)} rx="6" fill={C.tealSoft} stroke={C.teal} strokeWidth="1.5" strokeDasharray="4 3" />
        <text x={x2 + bw / 2} y={(y(sep) + y(metrics.volP)) / 2 + 4} textAnchor="middle" style={{ fontSize: 12, fontWeight: 900, fill: C.teal, fontFamily: FONT }}>−{Math.max(sep - metrics.volP, 0).toFixed(1)}%p</text>
        <line x1={x2 + bw} y1={y(metrics.volP)} x2={x3} y2={y(metrics.volP)} stroke={C.faint} strokeDasharray="3 3" />
        <rect x={x3} y={y(sysVol)} width={bw} height={sysVol * scale} fill={C.blue} />
        <rect x={x3} y={y(metrics.volP)} width={bw} height={Math.max(idioVolStack * scale, 0)} fill="#F0954F" />
        <text x={x3 + bw / 2} y={y(metrics.volP) - 6} textAnchor="middle" style={{ fontSize: 12, fontWeight: 800, fill: C.ink, fontFamily: FONT }}>{metrics.volP.toFixed(1)}%</text>
        <text x={x1 + bw / 2} y={baseY + 15} textAnchor="middle" style={{ fontSize: 10, fill: C.sub, fontFamily: FONT }}>{t("rjSep")}</text>
        <text x={x2 + bw / 2} y={baseY + 15} textAnchor="middle" style={{ fontSize: 10, fill: C.teal, fontWeight: 700, fontFamily: FONT }}>{t("rjErased")}</text>
        <text x={x3 + bw / 2} y={baseY + 15} textAnchor="middle" style={{ fontSize: 10, fill: C.sub, fontFamily: FONT }}>{t("rjNow")}</text>
      </svg>

      <div style={{ display: "flex", alignItems: "center", gap: 12, background: C.bg, borderRadius: 13, padding: "10px 12px", marginTop: 8 }}>
        <svg width="120" height="40" viewBox="0 0 150 40" style={{ flexShrink: 0 }}>
          <polyline points="0,25 20,12 40,28 60,10 80,26 100,12 120,28 140,14" fill="none" stroke="#C9D6E2" strokeWidth="1.8" />
          <polyline points="0,15 20,28 40,12 60,30 80,14 100,28 120,12 140,26" fill="none" stroke="#C9D6E2" strokeWidth="1.8" />
          <polyline points="0,20 20,20 40,20 60,20 80,20 100,20 120,20 140,20" fill="none" stroke={C.blueDeep} strokeWidth="2.6" />
        </svg>
        <span style={{ fontSize: 11.5, color: C.sub, lineHeight: 1.55 }}>{t("rjZig")}</span>
      </div>

      <div style={{ marginTop: 12, background: band === 0 ? C.tealSoft : "#FFF7EE", border: "1.5px solid " + (band === 0 ? "#BEE9E4" : "#F5D9B8"), borderRadius: 14, padding: 13 }}>
        <div style={{ fontSize: 13, fontWeight: 900, color: band === 0 ? "#0B6E66" : "#8A5A16" }}>{t("rjAction")}</div>
        <div style={{ marginTop: 7, display: "flex", flexDirection: "column", gap: 8 }}>
          {levers.slice(0, 3).map((l, i) => (
            <div key={i}>
              <div style={{ display: "flex", gap: 8, alignItems: "flex-start" }}>
                <span style={{ fontSize: 14, flexShrink: 0 }}>{l.icon}</span>
                <span style={{ fontSize: 12.5, color: C.ink, lineHeight: 1.6, fontWeight: 600 }}>{l.text}</span>
              </div>
              {l.bars && (
                <div style={{ marginLeft: 24, marginTop: 5, display: "flex", flexDirection: "column", gap: 3 }}>
                  {[[ko ? "지금" : "Now", l.bars[0], "#F0954F"], [ko ? "고르게 나누면" : "If evened", l.bars[1], C.teal]].map(([lb, v, col]) => (
                    <div key={lb} style={{ display: "flex", alignItems: "center", gap: 6 }}>
                      <span style={{ fontSize: 10, color: C.sub, width: 68, flexShrink: 0 }}>{lb}</span>
                      <div style={{ flex: 1, height: 9, background: C.line, borderRadius: 5, overflow: "hidden" }}>
                        <div style={{ width: v + "%", height: 9, background: col, transition: "width .4s ease" }} />
                      </div>
                      <span style={{ fontSize: 10.5, fontWeight: 800, color: C.ink, width: 32, textAlign: "right" }}>{v.toFixed(0)}%</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      </div>

      <button onClick={() => setShowDetail(!showDetail)} style={{ marginTop: 10, background: "none", border: "none", color: C.blue, fontSize: 12, fontWeight: 800, cursor: "pointer", padding: 0, fontFamily: FONT }}>
        {showDetail ? "▲ " : "▼ "}{t("rjDetails")}
      </button>
      {showDetail && (
        <div style={{ marginTop: 8, display: "flex", flexDirection: "column", gap: 7, animation: "fadeIn .2s ease" }}>
          {[...metrics.rows].filter((r) => r.mw > 0).sort((a, b) => b.wInv - a.wInv).slice(0, 12).map((r) => (
            <div key={r.t}>
              <div style={{ display: "flex", justifyContent: "space-between", fontSize: 11, marginBottom: 2 }}>
                <span style={{ fontWeight: 700, color: C.ink }}>{ko ? r.stock.nk : r.stock.ne} <span style={{ color: C.faint, fontWeight: 400 }}>{(r.wInv * 100).toFixed(0)}%</span></span>
                {mode !== "simple" && <span style={{ color: C.faint }}>{t("splitFair")} {pct(settings.rf + r.stock.beta * clsMrp(r.c, settings) * 100)}</span>}
              </div>
              <div style={{ display: "flex", height: 12, borderRadius: 6, overflow: "hidden" }}>
                <div style={{ width: r.sysShare * 100 + "%", background: C.blue }} />
                <div style={{ width: (1 - r.sysShare) * 100 + "%", background: "#F0954F" }} />
              </div>
            </div>
          ))}
        </div>
      )}
    </Card>
  );
}

// ================= Alpha corner =================
function AlphaCard({ lang, t, metrics, profile, settings, stocksById, setExplain }) {
  if (metrics.empty) return null;
  const te = metrics.te;
  const teLow = te < 4;
  const contribs = [...metrics.rows].filter((r) => r.mw > 0)
    .map((r) => ({ r, c: r.wInv * (r.stock.al || 0) }))
    .sort((a, b) => Math.abs(b.c) - Math.abs(a.c)).slice(0, 3);
  const at = profile.attrs || {};
  const strat = [
    { on: (at.discipline || 5) <= 5, icon: "",
      ko: `행동의 알파 — 가장 확실한 알파예요. 패닉 매도, 추격 매수, 잦은 매매만 안 해도 연 2~4%p가 지켜져요 (DALBAR·Barber-Odean).${(at.discipline || 5) <= 5 ? " 절제력 점수가 낮은 편이라, 특히 나에게 해당돼요." : ""}`,
      en: `Behavioral alpha — the surest kind. Skipping panic sells, FOMO chases and overtrading keeps 2–4%p/yr (DALBAR, Barber-Odean).${(at.discipline || 5) <= 5 ? " Your discipline score is on the low side, so this one is especially yours." : ""}` },
    { on: (profile.interestedSectors || []).length > 0, icon: "",
      ko: `아는 분야의 우위 — 개별 종목 승부는 남보다 잘 아는 분야()에서만, 나머지는 넓게 나눠 담으세요.`,
      en: `Knowledge edge — pick individual names only where you know more than most (); diversify the rest.` },
    { on: (at.horizon || 5) >= 7, icon: "",
      ko: `시간의 우위 — 펀드매니저는 분기 성과에 쫓기지만 나는 아니에요. 남들이 못 버티는 구간을 버티는 것 자체가 개인의 몇 안 되는 구조적 우위예요.`,
      en: `Time edge — fund managers answer to quarterly numbers; you don't. Holding through what others can't is one of retail's few structural advantages.` },
    { on: true, icon: "",
      ko: `비용의 알파 — 수수료·세금·회전율을 줄이는 건 유일하게 '확실한' 플러스예요.`,
      en: `Cost alpha — cutting fees, taxes and turnover is the only guaranteed positive.` },
  ];
  return (
    <Card style={{ padding: 16 }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <H3>{t("alTitle")}</H3>
        <button onClick={() => setExplain("alpha")} style={{ background: C.bg, border: "none", borderRadius: 999, fontSize: 11, fontWeight: 800, padding: "5px 11px", cursor: "pointer", color: C.sub, fontFamily: FONT }}>{lang === "ko" ? "알파가 뭐예요?" : "What's alpha?"}</button>
      </div>
      <div style={{ display: "flex", alignItems: "center", gap: 12, marginTop: 12, flexWrap: "wrap" }}>
        <div style={{ background: C.bg, borderRadius: 14, padding: "12px 16px" }}>
          <Sub>{t("alPast")}</Sub>
          <div style={{ fontSize: 26, fontWeight: 900, color: metrics.pastAl >= 0 ? C.teal : C.coral, marginTop: 2 }}>
            {metrics.pastAl > 0 ? "+" : ""}{num(metrics.pastAl, 1)}%p<span style={{ fontSize: 12, color: C.faint, fontWeight: 700 }}>/{lang === "ko" ? "년" : "yr"}</span>
          </div>
        </div>
        <Chip color="#8A5A16" soft={C.sandSoft}>{t("alCaveat")}</Chip>
      </div>
      {contribs.length > 0 && (
        <div style={{ marginTop: 10 }}>
          <Sub style={{ fontWeight: 700, color: C.ink }}>{t("alTop")}</Sub>
          <div style={{ display: "flex", flexDirection: "column", gap: 4, marginTop: 5 }}>
            {contribs.map(({ r, c }) => (
              <div key={r.t} style={{ display: "flex", justifyContent: "space-between", fontSize: 11.5, background: C.bg, borderRadius: 10, padding: "7px 10px" }}>
                <span style={{ fontWeight: 700, color: C.ink }}>{lang === "ko" ? r.stock.nk : r.stock.ne} <span style={{ color: C.faint, fontWeight: 400 }}>(α {r.stock.al > 0 ? "+" : ""}{r.stock.al}%p)</span></span>
                <span style={{ fontWeight: 800, color: c >= 0 ? C.teal : C.coral }}>{c > 0 ? "+" : ""}{c.toFixed(1)}%p</span>
              </div>
            ))}
          </div>
        </div>
      )}
      <div style={{ marginTop: 10, background: C.bg, borderRadius: 13, padding: 11 }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
          <Sub style={{ fontWeight: 700, color: C.ink }}>{t("alSpace")}</Sub>
          <span style={{ fontSize: 15, fontWeight: 900, color: C.ink }}>{pct(te)}</span>
        </div>
        <div style={{ fontSize: 11.5, color: C.sub, lineHeight: 1.6, marginTop: 3 }}>{teLow ? t("alSpaceLow") : t("alSpaceHigh")}</div>
      </div>
      {(() => {
        const ir = te > 0.01 ? metrics.pastAl / te : 0;
        const tstat = ir * Math.sqrt(3);   // 3년 표본
        const strong = Math.abs(tstat) >= 2;
        const yrsNeeded = Math.abs(ir) > 0.01 ? Math.min(Math.ceil(Math.pow(2 / ir, 2)), 999) : 999;
        return (
          <div style={{ marginTop: 10, background: C.bg, borderRadius: 13, padding: 12 }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", gap: 8, flexWrap: "wrap" }}>
              <span style={{ fontSize: 12, fontWeight: 800, color: C.ink }}>{t("alIR")}</span>
              <span style={{ fontSize: 13, fontWeight: 900, color: C.ink }}>IR {num(ir)} · t {num(tstat)}</span>
            </div>
            <div style={{ fontSize: 12, color: strong ? C.teal : C.sub, lineHeight: 1.65, marginTop: 4, fontWeight: strong ? 700 : 500 }}>
              {strong
                ? (lang === "ko" ? "통계적으로도 의미 있는 수준이에요. 다만 3년은 여전히 짧은 표본이에요." : "Statistically meaningful — though three years is still a short sample.")
                : (lang === "ko"
                  ? <>t값이 2보다 작아요. 즉 이 알파가 <b>실력인지 운인지 구분할 수 없어요</b>. 지금 추세라면 판별에 약 {yrsNeeded > 60 ? "60년 이상" : yrsNeeded + "년"}의 기록이 필요해요.</>
                  : <>t is below 2, so this alpha is <b>indistinguishable from luck</b>. At this rate you'd need about {yrsNeeded > 60 ? "60+ years" : yrsNeeded + " years"} of record to tell.</>)}
            </div>
          </div>
        );
      })()}
      <Sub style={{ marginTop: 8, fontSize: 11 }}>{t("alPersist")}</Sub>
      <div style={{ marginTop: 12 }}>
        <div style={{ fontSize: 13, fontWeight: 900, color: C.ink }}>{t("alGrow")}</div>
        <div style={{ display: "flex", flexDirection: "column", gap: 6, marginTop: 7 }}>
          {strat.map((s, i) => (
            <div key={i} style={{ display: "flex", gap: 9, alignItems: "flex-start", background: s.on ? C.blueSoft : C.bg, border: s.on ? "1.5px solid #C7DEFA" : "1.5px solid transparent", borderRadius: 12, padding: "9px 11px" }}>
              <span style={{ fontSize: 14, flexShrink: 0 }}>{s.icon}</span>
              <span style={{ fontSize: 12, color: s.on ? C.blueDeep : C.sub, lineHeight: 1.6, fontWeight: s.on ? 700 : 500 }}>{lang === "ko" ? s.ko : s.en}</span>
            </div>
          ))}
        </div>
      </div>
    </Card>
  );
}

function LegendsCard({ lang, t, metrics }) {
  if (metrics.empty) return null;
  const rows = [
    { ko: "나 (과거 3년, 추정)", en: "Me (past 3y, est.)", al: metrics.pastAl, me: true },
    { ko: "워런 버핏 (전성기 40년)", en: "Warren Buffett (prime 40y)", al: 10 },
    { ko: "피터 린치 (마젤란 13년)", en: "Peter Lynch (Magellan 13y)", al: 13 },
    { ko: "액티브 펀드 평균 (15년, 수수료 후)", en: "Avg active fund (15y, after fees)", al: -1 },
    { ko: "개인투자자 평균 (행동 격차 포함)", en: "Avg retail investor (behavior gap incl.)", al: -3 },
  ];
  const MAX = 16;
  return (
    <Card style={{ padding: 16 }}>
      <H3>{t("lgTitle")}</H3>
      <div style={{ marginTop: 12, display: "flex", flexDirection: "column", gap: 8 }}>
        {rows.map((r) => {
          const v = Math.max(Math.min(r.al, MAX), -MAX);
          const w = Math.abs(v) / MAX * 50;
          return (
            <div key={r.ko} style={{ background: r.me ? C.blueSoft : "transparent", borderRadius: 10, padding: r.me ? "7px 8px" : "0 8px" }}>
              <div style={{ display: "flex", justifyContent: "space-between", fontSize: 11.5, marginBottom: 3 }}>
                <span style={{ fontWeight: r.me ? 900 : 700, color: r.me ? C.blueDeep : C.ink }}>{lang === "ko" ? r.ko : r.en}</span>
                <span style={{ fontWeight: 800, color: r.al >= 0 ? C.teal : C.coral }}>{r.al > 0 ? "+" : ""}{typeof r.al === "number" ? r.al.toFixed(1) : r.al}%p</span>
              </div>
              <div style={{ position: "relative", height: 10, background: C.bg, borderRadius: 5 }}>
                <div style={{ position: "absolute", left: "50%", top: -1, bottom: -1, width: 1.5, background: C.faint }} />
                <div style={{ position: "absolute", top: 0, height: 10, borderRadius: 5, background: r.al >= 0 ? C.teal : C.coral, left: r.al >= 0 ? "50%" : (50 - w) + "%", width: w + "%", transition: "width .4s ease" }} />
              </div>
            </div>
          );
        })}
      </div>
      <Sub style={{ marginTop: 10, fontSize: 11 }}>{t("lgNote")}</Sub>
      <Verdict>{t("lgVerdict")}</Verdict>
    </Card>
  );
}

// ================= Asset-class mix & hedge effect =================
function AssetMixCard({ lang, t, metrics, settings }) {
  if (metrics.empty) return null;
  const entries = CLS_LIST.map((c) => ({ c, w: metrics.clsW[c] || 0 })).filter((e) => e.w > 0.01);
  const CIRCUM = 2 * Math.PI * 44;
  let cum = 0;
  const hasMetal = (metrics.clsW.metal || 0) > 0.01;
  const hasUs = (metrics.clsW.us || 0) > 0.01;
  let noMetal = null;
  if (hasMetal) {
    const keep = metrics.rows.filter((r) => r.c !== "metal" && r.mw > 0);
    if (keep.length > 0) {
      const scale = metrics.invested / keep.reduce((a, r) => a + r.won, 0);
      noMetal = computeMetrics(keep.map((r) => ({ t: r.t, mw: r.mw * scale, won: r.won * scale, stock: r.stock })), metrics.total, settings);
    }
  }
  return (
    <Card style={{ padding: 16 }}>
      <H3>{t("amTitle")}</H3>
      <div style={{ display: "flex", gap: 16, alignItems: "center", marginTop: 10, flexWrap: "wrap" }}>
        <svg width="130" height="130" viewBox="0 0 120 120" style={{ flexShrink: 0 }}>
          {entries.map((e) => {
            const dash = (e.w / 100) * CIRCUM;
            const rot = (cum / 100) * 360 - 90;
            cum += e.w;
            return <circle key={e.c} cx="60" cy="60" r="44" fill="none" stroke={CLASSES[e.c].color} strokeWidth="20" strokeDasharray={dash + " " + CIRCUM} transform={"rotate(" + rot + " 60 60)"} />;
          })}
          <text x="60" y="57" textAnchor="middle" style={{ fontSize: 11, fontWeight: 800, fill: C.ink, fontFamily: FONT }}>{entries.length}</text>
          <text x="60" y="70" textAnchor="middle" style={{ fontSize: 9, fill: C.faint, fontFamily: FONT }}>{lang === "ko" ? "자산군" : "classes"}</text>
        </svg>
        <div style={{ flex: 1, minWidth: 180, display: "flex", flexDirection: "column", gap: 5 }}>
          {entries.map((e) => (
            <div key={e.c} style={{ display: "flex", alignItems: "center", gap: 7, fontSize: 12 }}>
              <span style={{ width: 10, height: 10, borderRadius: 3, background: CLASSES[e.c].color, flexShrink: 0 }} />
              <span style={{ flex: 1, color: C.ink, fontWeight: 700 }}>{CLASSES[e.c].flag} {lang === "ko" ? CLASSES[e.c].ko : CLASSES[e.c].en}</span>
              <span style={{ color: C.sub, fontWeight: 800 }}>{e.w.toFixed(0)}%</span>
              <span style={{ color: C.faint, fontSize: 11 }}>{fmtMw(metrics.invested * e.w / 100, lang)}</span>
            </div>
          ))}
          <div style={{ display: "flex", justifyContent: "space-between", background: C.bg, borderRadius: 10, padding: "7px 10px", marginTop: 3 }}>
            <span style={{ fontSize: 11.5, color: C.sub, fontWeight: 700 }}>{t("fxExp")}</span>
            <span style={{ fontSize: 12, color: C.ink, fontWeight: 800 }}>{pct(metrics.fxExp, 0)}</span>
          </div>
        </div>
      </div>
      {hasUs && <Verdict>{t("amUsHedge")}</Verdict>}
      {noMetal && !noMetal.empty && (
        <div style={{ marginTop: 10, background: C.tealSoft, border: "1.5px solid #BEE9E4", borderRadius: 14, padding: 13 }}>
          <div style={{ fontSize: 13, fontWeight: 900, color: "#0B6E66" }}>{t("amHedge")}</div>
          <div style={{ display: "flex", alignItems: "center", gap: 10, marginTop: 8 }}>
            <div style={{ flex: 1, textAlign: "center", background: "#fff", borderRadius: 11, padding: 9 }}>
              <div style={{ fontSize: 10, color: C.faint }}>{t("amNoMetal")}</div>
              <div style={{ fontSize: 16, fontWeight: 900, color: C.sub, marginTop: 2 }}>{pct(noMetal.volP)}</div>
            </div>
            <span style={{ fontSize: 17, color: C.teal, fontWeight: 900 }}>→</span>
            <div style={{ flex: 1, textAlign: "center", background: "#fff", borderRadius: 11, padding: 9 }}>
              <div style={{ fontSize: 10, color: C.teal, fontWeight: 700 }}>{t("amWithMetal")}</div>
              <div style={{ fontSize: 16, fontWeight: 900, color: C.teal, marginTop: 2 }}>{pct(metrics.volP)}</div>
            </div>
          </div>
          <div style={{ fontSize: 12.5, color: C.ink, lineHeight: 1.6, marginTop: 8, fontWeight: 600 }}>
            {noMetal.volP - metrics.volP > 0.05
              ? (lang === "ko"
                ? <>금·은이 연간 출렁임을 <b>{(noMetal.volP - metrics.volP).toFixed(1)}%p</b>(약 <b>{fmtMw(metrics.total * (noMetal.volP - metrics.volP) / 100, lang)}</b>) 줄여줬어요. 금은 자체가 안전해서가 아니라, 주식과 <b>따로 움직이기</b> 때문이에요.</>
                : <>Gold/silver cut yearly swing by <b>{(noMetal.volP - metrics.volP).toFixed(1)}%p</b> (≈ <b>{fmtMw(metrics.total * (noMetal.volP - metrics.volP) / 100, lang)}</b>) — not because metal is calm, but because it moves <b>separately</b> from stocks.</>)
              : t("amNoEffect")}
          </div>
        </div>
      )}
    </Card>
  );
}
// ================= What-if lab & Time machine =================
function WhatIfLab({ lang, t, metrics, profile, settings, stocksById }) {
  const [mv, setMv] = useState(-30);
  if (metrics.empty) return null;
  const beta = metrics.beta, total = metrics.total;
  const port = beta * (mv / 100);
  const idioVol = (metrics.volP / 100) * Math.sqrt(Math.max(1 - metrics.r2 / 100, 0));
  const secWon = metrics.maxSectorKey ? metrics.invested * (metrics.maxSectorW / 100) : 0;
  const rowsSorted = [...metrics.rows].sort((a, b) => b.wInv - a.wInv);
  const big = rowsSorted[0];
  // naive 1/N comparison
  const n = metrics.rows.filter((r) => r.mw > 0).length;
  let eq = null;
  if (n >= 2) {
    const eqH = metrics.rows.filter((r) => r.mw > 0).map((r) => ({ t: r.t, mw: 0, won: metrics.invested / n, stock: r.stock }));
    eq = computeMetrics(eqH.map((h) => ({ ...h, mw: h.won / 10000 })), metrics.total, settings);
  }
  const D = ({ a, b, fmt, invert }) => {
    const d = b - a;
    const better = invert ? d < 0 : d > 0;
    return <span style={{ color: Math.abs(d) < 0.005 ? C.faint : better ? C.teal : C.coral, fontWeight: 800 }}>{d > 0 ? "+" : ""}{fmt(d)}</span>;
  };
  return (
    <Card style={{ padding: 16 }}>
      <H3>{t("whatifTitle")}</H3>
      <div style={{ marginTop: 10, background: C.bg, borderRadius: 14, padding: 12 }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <Sub style={{ fontWeight: 700 }}>{t("wiMkt")}</Sub>
          <span style={{ fontSize: 15, fontWeight: 900, color: mv < 0 ? C.coral : C.teal }}>{mv > 0 ? "+" : ""}{mv}%</span>
        </div>
        <input type="range" min={-50} max={50} step={5} value={mv} onChange={(e) => setMv(parseInt(e.target.value))} style={{ width: "100%", marginTop: 6, accentColor: C.blue, cursor: "pointer" }} />
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginTop: 6 }}>
          <span style={{ fontSize: 12, color: C.sub }}>{t("wiMine")} <b>β {num(beta)}</b> ×</span>
          <span style={{ fontSize: 18, fontWeight: 900, color: port < 0 ? C.coral : C.teal }}>{port < 0 ? "−" : "+"}{fmtMw(Math.abs(total * port), lang)} ({pct(port * 100, 0)})</span>
        </div>
        <div style={{ fontSize: 10.5, color: C.faint, marginTop: 3 }}>{t("wiIdio")}: ±{fmtMw(total * idioVol, lang)}</div>
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: 6, marginTop: 8 }}>
        {metrics.maxSectorKey && (
          <div style={{ display: "flex", justifyContent: "space-between", gap: 10, background: C.bg, borderRadius: 12, padding: "9px 12px" }}>
            <span style={{ fontSize: 12, color: C.sub, fontWeight: 700 }}>{t("wiSector")} <b style={{ color: C.ink }}>({lang === "ko" ? SEC(metrics.maxSectorKey).ko : SEC(metrics.maxSectorKey).en})</b></span>
            <span style={{ fontSize: 12.5, fontWeight: 900, color: C.coral, flexShrink: 0 }}>≈ −{fmtMw(secWon * 0.3, lang)}</span>
          </div>
        )}
        {big && (
          <div style={{ display: "flex", justifyContent: "space-between", gap: 10, background: C.bg, borderRadius: 12, padding: "9px 12px" }}>
            <span style={{ fontSize: 12, color: C.sub, fontWeight: 700 }}>{t("wiStock")} <b style={{ color: C.ink }}>({lang === "ko" ? big.stock.nk : big.stock.ne})</b></span>
            <span style={{ fontSize: 12.5, fontWeight: 900, color: C.coral, flexShrink: 0 }}>−{fmtMw(big.won * 0.5, lang)} ({pct(-big.wInv * 50, 1)})</span>
          </div>
        )}
      </div>
      {eq && !eq.empty && (
        <div style={{ marginTop: 8, background: C.blueSoft, borderRadius: 13, padding: 11 }}>
          <div style={{ fontSize: 12, fontWeight: 800, color: C.blueDeep }}>{t("wiOneN")}</div>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 5, marginTop: 6, textAlign: "center" }}>
            {[["β", metrics.beta, eq.beta, (d) => d.toFixed(2), false],
              ["σ", metrics.volP, eq.volP, (d) => d.toFixed(1) + "%p", true],
              [lang === "ko" ? "실효 종목" : "Eff. N", metrics.effN, eq.effN, (d) => d.toFixed(1), false],
              ["Sharpe", metrics.sharpe, eq.sharpe, (d) => d.toFixed(2), false]].map(([l, a, b, f, inv]) => (
              <div key={l} style={{ background: "#fff", borderRadius: 10, padding: "6px 3px" }}>
                <div style={{ fontSize: 9.5, color: C.faint }}>{l}</div>
                <div style={{ fontSize: 11.5, fontWeight: 800, color: C.ink }}>{typeof b === "number" ? (l === "σ" ? b.toFixed(1) + "%" : b.toFixed(l === "β" || l === "Sharpe" ? 2 : 1)) : b}</div>
                <D a={a} b={b} fmt={f} invert={inv} />
              </div>
            ))}
          </div>
          <div style={{ fontSize: 10.5, color: C.blueDeep, marginTop: 6, lineHeight: 1.5 }}>{t("oneNNote")}</div>
        </div>
      )}
    </Card>
  );
}

function TimeMachine({ lang, t, metrics, settings }) {
  const [path, setPath] = useState("gfc");
  const [idx, setIdx] = useState(0);
  const [playing, setPlaying] = useState(false);
  const sim = useMemo(() => {
    if (metrics.empty) return null;
    const beta = metrics.beta, total = metrics.total;
    const idioM = (metrics.volP / 100) * Math.sqrt(Math.max(1 - metrics.r2 / 100, 0)) / Math.sqrt(12);
    const g = gaussFactory(42);
    const ms = MKT_PATHS[path].m;
    const vals = [total];
    let v = total;
    ms.forEach((m) => { v = Math.max(v * (1 + beta * m + idioM * g()), 1); vals.push(v); });
    let minI = 0;
    vals.forEach((x, i) => { if (x < vals[minI]) minI = i; });
    return { vals, minI, n: ms.length };
  }, [metrics.empty, metrics.beta, metrics.volP, metrics.total, settings.mktVol, path]);
  useEffect(() => { setIdx(0); setPlaying(false); }, [path, metrics.total]);
  useEffect(() => {
    if (!playing || !sim) return;
    if (idx >= sim.n) { setPlaying(false); return; }
    const id = setTimeout(() => setIdx(idx + 1), 240);
    return () => clearTimeout(id);
  }, [playing, idx, sim]);
  if (!sim) return null;
  const { vals, minI, n } = sim;
  const maxV = Math.max(...vals) * 1.04, minV = Math.min(...vals) * 0.94;
  const W = 420, H = 150;
  const x = (i) => 8 + (i / n) * (W - 16);
  const y = (v) => H - 10 - ((v - minV) / (maxV - minV)) * (H - 24);
  const done = idx >= n;
  const cur = vals[idx];
  const peakSoFar = Math.max(...vals.slice(0, idx + 1));
  const dd = (cur / peakSoFar - 1) * 100;
  const line = vals.slice(0, idx + 1).map((v, i) => (i === 0 ? "M" : "L") + x(i) + "," + y(v)).join(" ");
  return (
    <Card style={{ padding: 16 }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8, flexWrap: "wrap" }}>
        <H3>{t("tmTitle")}</H3>
        <div style={{ display: "flex", gap: 4 }}>
          {Object.entries(MKT_PATHS).map(([k, p]) => (
            <button key={k} onClick={() => setPath(k)} style={{ fontSize: 11, fontWeight: 800, padding: "4px 10px", borderRadius: 999, border: "1.5px solid " + (path === k ? C.ink : C.line), background: path === k ? C.ink : "#fff", color: path === k ? "#fff" : C.sub, cursor: "pointer", fontFamily: FONT }}>{lang === "ko" ? p.ko : p.en}</button>
          ))}
        </div>
      </div>
      <div style={{ display: "flex", alignItems: "baseline", justifyContent: "space-between", marginTop: 8 }}>
        <span style={{ fontSize: 12, color: C.sub }}>{idx}/{n}{lang === "ko" ? "개월" : "mo"}</span>
        <span style={{ fontSize: 17, fontWeight: 900, color: cur >= vals[0] ? C.teal : C.coral }}>{fmtMw(cur, lang)} <span style={{ fontSize: 11, fontWeight: 700 }}>({pct((cur / vals[0] - 1) * 100, 0)})</span></span>
      </div>
      {idx > 0 && dd < -1 && <div style={{ fontSize: 11, color: C.coral, fontWeight: 700, textAlign: "right" }}>{lang === "ko" ? "고점 대비" : "From peak"} {pct(dd, 0)}</div>}
      <svg width="100%" viewBox={"0 0 " + W + " " + H} style={{ marginTop: 4 }}>
        <line x1="8" x2={W - 8} y1={y(vals[0])} y2={y(vals[0])} stroke={C.line} strokeDasharray="4 4" />
        <path d={line} fill="none" stroke={C.blueDeep} strokeWidth="2.5" strokeLinejoin="round" />
        {idx >= minI && minI > 0 && <circle cx={x(minI)} cy={y(vals[minI])} r="4" fill={C.coral} />}
        {idx > 0 && <circle cx={x(idx)} cy={y(cur)} r="4.5" fill={C.blue} stroke="#fff" strokeWidth="2" />}
      </svg>
      <div style={{ display: "flex", gap: 8, marginTop: 6 }}>
        <Btn onClick={() => { if (done) { setIdx(0); setPlaying(true); } else setPlaying(!playing); }} style={{ flex: 1, padding: "10px 12px", fontSize: 13 }}>
          {playing ? t("tmPause") : done ? t("tmReset") : t("tmPlay")}
        </Btn>
        {idx > 0 && !playing && !done && <Btn kind="ghost" onClick={() => setIdx(0)} style={{ padding: "10px 12px", fontSize: 13 }}>{t("tmReset")}</Btn>}
      </div>
      {done && (
        <div style={{ marginTop: 10, animation: "fadeIn .4s ease" }}>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
            <div style={{ background: C.coralSoft, borderRadius: 13, padding: 11, textAlign: "center" }}>
              <div style={{ fontSize: 10.5, color: "#8E2A28", fontWeight: 700 }}>{t("tmSold")}</div>
              <div style={{ fontSize: 16, fontWeight: 900, color: C.coral, marginTop: 2 }}>{fmtMw(vals[minI], lang)}</div>
              <div style={{ fontSize: 10.5, color: C.coral }}>{pct((vals[minI] / vals[0] - 1) * 100, 0)}</div>
            </div>
            <div style={{ background: C.tealSoft, borderRadius: 13, padding: 11, textAlign: "center" }}>
              <div style={{ fontSize: 10.5, color: "#0B6E66", fontWeight: 700 }}>{t("tmHeld")}</div>
              <div style={{ fontSize: 16, fontWeight: 900, color: C.teal, marginTop: 2 }}>{fmtMw(vals[n], lang)}</div>
              <div style={{ fontSize: 10.5, color: C.teal }}>{pct((vals[n] / vals[0] - 1) * 100, 0)}</div>
            </div>
          </div>
          <Verdict>{lang === "ko" ? <>{t("tmDiff")}: <b>{fmtMw(vals[n] - vals[minI], lang)}</b>. 폭락의 한가운데서 '지금이라도 팔까'를 이긴 값이에요.</> : <>{t("tmDiff")}: <b>{fmtMw(vals[n] - vals[minI], lang)}</b> — the reward for beating "should I sell now" at the very bottom.</>}</Verdict>
        </div>
      )}
      <Sub style={{ marginTop: 8, fontSize: 10.5 }}>{t("tmNote")}</Sub>
    </Card>
  );
}

// ================= Stage views =================
function BuildView({ lang, t, mode, profile, holdings, setHoldings, budgetMw, setBudgetMw, metrics, stocksById, stocks, addStock, addCustom, updateStock, expanded, setExpanded, setExplain, score, okCount, goDiagnose, settings, onDemo }) {
  const [cardM, setCardM] = useState(null);
  return (
    <div className="grid3">
      <div>
        <StockShelf lang={lang} t={t} mode={mode} settings={settings} interested={profile.interestedSectors} stocks={stocks} holdings={holdings} onAdd={addStock} onAddCustom={addCustom} expanded={expanded} setExpanded={setExpanded} updateStock={updateStock} />
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
        {!profile.ready && (
          <Card style={{ display: "flex", gap: 11, alignItems: "center", background: C.sandSoft, border: "1px solid #F3DCB2" }}>
            <Bird mood="think" size={44} />
            <Sub style={{ color: "#7A5410", fontWeight: 700 }}>{t("needProfile")}</Sub>
          </Card>
        )}
        {metrics.empty && <Btn kind="ghost" onClick={onDemo} style={{ width: "100%" }}>{t("demo")}</Btn>}
        <Cart lang={lang} t={t} holdings={holdings} setHoldings={setHoldings} budgetMw={budgetMw} setBudgetMw={setBudgetMw} metrics={metrics} profile={profile} stocksById={stocksById} settings={settings} />
        <MetricsPanel lang={lang} t={t} mode={mode} metrics={metrics} profile={profile} setExplain={setExplain} />
      </div>
      <div className="stickyR" style={{ display: "flex", flexDirection: "column", gap: 12 }}>
        {profile.ready && !metrics.empty ? (
          <HealthHero score={score} okCount={okCount} lang={lang} t={t} />
        ) : (
          <Card style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 8, padding: 22, textAlign: "center" }}>
            <Bird mood="think" size={56} />
            <Sub>{metrics.empty ? t("emptyCart") : t("needProfile")}</Sub>
          </Card>
        )}
        <div className="stickyScroll">
          {profile.ready && !metrics.empty && <Dashboard lang={lang} t={t} metrics={metrics} profile={profile} setExplain={setExplain} />}
          {profile.ready && !metrics.empty && <AlertsBox lang={lang} t={t} metrics={metrics} profile={profile} stocksById={stocksById} settings={settings} stocks={stocks} holdings={holdings} setHoldings={setHoldings} budgetMw={budgetMw} />}
          {!metrics.empty && <Btn onClick={goDiagnose} style={{ width: "100%" }}>{t("goDiagnose")}</Btn>}
          <ShareCardModal card={cardM} onClose={() => setCardM(null)} lang={lang} />
          {!metrics.empty && profile.ready && (
            <Btn kind="ghost" style={{ width: "100%" }} onClick={() => {
              try {
                let inv = 0;
                holdings.forEach((h) => { inv += h.mw || 0; });
                const data = makeCardData(holdings, stocksById, Math.max((budgetMw || 0) - inv, 0), score, lang);
                const cv = renderPortfolioCard(data);
                setCardM({ cv, url: cv.toDataURL("image/png"), dateStr: data.dateStr });
              } catch (e) {}
            }}>{lang === "ko" ? "포트폴리오 카드 만들기" : "Make portfolio card"}</Btn>
          )}
        </div>
      </div>
    </div>
  );
}

// ================= Tax layer (Korean retail, as of 2026-01 · editable) =================
const ACCOUNTS = {
  normal: { ko:"일반 계좌", en:"Regular account", e:"",
    ko_d:"제한 없이 국내·해외 주식을 모두 담을 수 있어요.", en_d:"No restrictions — domestic and foreign stocks both allowed." },
  isa:    { ko:"ISA", en:"ISA", e:"",
    ko_d:"국내 상장 종목만 담을 수 있어요(해외 직접투자 불가). 순이익 200만원까지 비과세, 초과분은 9.9% 분리과세. 3년 의무가입.", en_d:"KR-listed only (no direct foreign stocks). First ₩2m of net profit tax-free, then 9.9% separate taxation. 3-year lock-in." },
  pension:{ ko:"연금저축", en:"Pension savings", e:"",
    ko_d:"개별 주식은 담을 수 없고 ETF·펀드만 가능해요. 대신 연 600만원까지 세액공제(13.2~16.5%), 세금은 인출 때까지 미뤄져요.", en_d:"ETFs and funds only — no individual stocks. Up to ₩6m/yr tax credit (13.2–16.5%); tax deferred until withdrawal." },
  irp:    { ko:"IRP", en:"IRP", e:"",
    ko_d:"ETF·펀드만 가능하고, 주식형 등 위험자산은 전체의 70%까지만 담을 수 있어요. 연금저축과 합쳐 연 900만원까지 세액공제.", en_d:"ETFs and funds only, with risky assets capped at 70% of the account. Up to ₩9m/yr combined tax credit with pension savings." },
};
const DEFAULT_TAX = { divKr: 15.4, divUs: 15.0, gainUs: 22.0, gainUsFree: 250, isaFree: 200, isaRate: 9.9 };

function taxEstimate(metrics, profile, settings, tax) {
  if (metrics.empty) return null;
  const acc = profile.account || "normal";
  let divKr = 0, divUs = 0, gainUsBase = 0, gainMetalEtf = 0;
  metrics.rows.forEach((r) => {
    const d = r.won * ((r.stock.dy || 0) / 100);
    if (r.c === "us") {
      divUs += d;
      gainUsBase += r.won * Math.max((settings.rf + r.stock.beta * settings.usMrp) / 100 - (r.stock.dy || 0) / 100, 0);
    } else if (r.c === "metal") {
      if (r.stock.t !== "04020000") gainMetalEtf += r.won * (settings.mtMrp / 100);
    } else divKr += d;
  });
  const W = 10000;
  const norm = divKr * (tax.divKr / 100) + divUs * (tax.divUs / 100)
    + Math.max(gainUsBase - tax.gainUsFree * W, 0) * (tax.gainUs / 100)
    + gainMetalEtf * (tax.divKr / 100);
  let mine = norm, note = null;
  if (acc === "isa") {
    const pool = divKr + gainMetalEtf;
    mine = Math.max(pool - tax.isaFree * W, 0) * (tax.isaRate / 100)
      + divUs * (tax.divUs / 100) + Math.max(gainUsBase - tax.gainUsFree * W, 0) * (tax.gainUs / 100);
    note = "isa";
  } else if (acc === "pension" || acc === "irp") {
    mine = divUs * (tax.divUs / 100);
    note = "defer";
  }
  return { acc, norm, mine, saved: norm - mine, divKr, divUs, gainUsBase, gainMetalEtf, note };
}
function accountIssues(metrics, profile, lang) {
  const acc = profile.account || "normal";
  const out = [];
  if (metrics.empty) return out;
  const direct = metrics.rows.filter((r) => r.mw > 0 && r.stock.s !== "index" && r.stock.s !== "metal");
  const foreignDirect = metrics.rows.filter((r) => r.mw > 0 && r.c === "us" && r.stock.ccy === "USD");
  if (acc === "isa" && foreignDirect.length > 0)
    out.push(lang === "ko" ? `ISA에는 해외 주식을 직접 담을 수 없어요. 지금 ${foreignDirect.length}종목이 해당돼요 — 국내 상장 해외 ETF로 바꾸면 ISA에서도 가능해요.` : `ISA can't hold foreign stocks directly — ${foreignDirect.length} of your holdings are. KR-listed overseas ETFs work instead.`);
  if ((acc === "pension" || acc === "irp") && direct.length > 0)
    out.push(lang === "ko" ? `${ACCOUNTS[acc].ko} 계좌에는 개별 주식을 담을 수 없어요. 지금 ${direct.length}종목이 해당돼요 — ETF로 대체해야 해요.` : `${ACCOUNTS[acc].en} accounts can't hold individual stocks; ${direct.length} of yours are. Use ETFs instead.`);
  if (acc === "irp") {
    const risky = 100 - (metrics.cash / metrics.total) * 100;
    if (risky > 70.5) out.push(lang === "ko" ? `IRP는 위험자산을 70%까지만 담을 수 있어요. 지금 약 ${risky.toFixed(0)}%예요 — 현금이나 예금형을 ${(risky - 70).toFixed(0)}%p 더 두셔야 해요.` : `IRP caps risky assets at 70%; you're at about ${risky.toFixed(0)}%. Add ${(risky - 70).toFixed(0)}%p of cash-like holdings.`);
  }
  return out;
}

function TaxCard({ lang, t, metrics, profile, settings, tax }) {
  const e = taxEstimate(metrics, profile, settings, tax);
  if (!e) return null;
  const A = ACCOUNTS[e.acc];
  const issues = accountIssues(metrics, profile, lang);
  const netRet = metrics.expRet - (e.mine / metrics.total) * 100;
  return (
    <Card style={{ padding: 16 }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8, flexWrap: "wrap" }}>
        <H3>{t("taxTitle")}</H3>
        <Chip color={C.blueDeep} soft={C.blueSoft}>{A.e} {lang === "ko" ? A.ko : A.en}</Chip>
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8, marginTop: 11 }}>
        <div style={{ background: C.bg, borderRadius: 13, padding: 12 }}>
          <Sub>{t("taxYear")}</Sub>
          <div style={{ fontSize: 19, fontWeight: 900, color: C.ink, marginTop: 3 }}>{fmtMw(e.mine, lang)}</div>
          <div style={{ fontSize: 10.5, color: C.faint }}>{lang === "ko" ? "연간 · 추정" : "per year, est."}</div>
        </div>
        <div style={{ background: C.tealSoft, borderRadius: 13, padding: 12 }}>
          <Sub style={{ color: "#0B6E66" }}>{t("taxNet")}</Sub>
          <div style={{ fontSize: 19, fontWeight: 900, color: C.teal, marginTop: 3 }}>{pct(netRet)}</div>
          <div style={{ fontSize: 10.5, color: C.teal }}>{lang === "ko" ? "세전 " : "pre-tax "}{pct(metrics.expRet)}</div>
        </div>
      </div>
      <div style={{ marginTop: 9, display: "flex", flexDirection: "column", gap: 5 }}>
        {[[t("taxDivKr"), e.divKr * (tax.divKr / 100), tax.divKr + "%"],
          [t("taxDivUs"), e.divUs * (tax.divUs / 100), tax.divUs + "%"],
          [t("taxGainUs"), Math.max(e.gainUsBase - tax.gainUsFree * 10000, 0) * (tax.gainUs / 100), tax.gainUs + "%"]].map(([l, v, r]) => (
          <div key={l} style={{ display: "flex", justifyContent: "space-between", fontSize: 12, padding: "6px 2px", borderTop: "1px solid " + C.line }}>
            <span style={{ color: C.sub, fontWeight: 700 }}>{l} <span style={{ color: C.faint, fontWeight: 500 }}>{r}</span></span>
            <span style={{ color: C.ink, fontWeight: 800 }}>{fmtMw(v, lang)}</span>
          </div>
        ))}
      </div>
      {e.note === "isa" && <Verdict>{lang === "ko" ? <>일반 계좌였다면 <b>{fmtMw(e.norm, lang)}</b>을 냈을 텐데, ISA라서 <b>{fmtMw(e.saved, lang)}</b>을 아꼈어요. 다만 해외 주식 직접투자는 ISA에서 안 된다는 점만 기억하세요.</> : <>A regular account would owe <b>{fmtMw(e.norm, lang)}</b>; ISA saves you <b>{fmtMw(e.saved, lang)}</b>. Remember it can't hold foreign stocks directly.</>}</Verdict>}
      {e.note === "defer" && <Verdict>{lang === "ko" ? <>연금 계좌라 세금이 인출할 때까지 미뤄져요(연금소득세 3.3~5.5%). 일반 계좌 대비 매년 <b>{fmtMw(e.saved, lang)}</b>씩 굴릴 돈이 더 남는 셈이에요.</> : <>Pension accounts defer tax to withdrawal (3.3–5.5% pension income tax), leaving about <b>{fmtMw(e.saved, lang)}</b> more compounding each year than a regular account.</>}</Verdict>}
      {issues.length > 0 && (
        <div style={{ marginTop: 10, display: "flex", flexDirection: "column", gap: 6 }}>
          {issues.map((x, i) => (
            <div key={i} style={{ fontSize: 12.5, background: C.coralSoft, border: "1px solid #F5C9C8", color: "#8E2A28", borderRadius: 12, padding: "9px 12px", lineHeight: 1.6, fontWeight: 600 }}>{x}</div>
          ))}
        </div>
      )}
      <Sub style={{ marginTop: 9, fontSize: 10.5 }}>{t("taxNote")}</Sub>
    </Card>
  );
}

// ================= Recommendation engine =================
// 목표 범위를 벗어난 항목마다 "수학적으로 맞춰지는" 조정안을 만들어 줍니다.
// 종목의 좋고 나쁨은 전혀 판단하지 않고, 비중 계산만 합니다.
const effBeta = (s, st) => s.beta * (clsVol(clsOf(s), st) / (st.mktVol / 100)) * rhoOf(clsOf(s), "kr", st);

function shiftToward(items, scoreOf, target, up, maxPosPct) {
  const w = items.map((r) => ({ t: r.t, mw: r.mw, s: scoreOf(r.stock) }));
  const total0 = w.reduce((a, x) => a + x.mw, 0);
  if (total0 <= 0) return null;
  const step = Math.max(total0 * 0.01, 1);
  let moved = false;
  for (let i = 0; i < 500; i++) {
    const tot = w.reduce((a, x) => a + x.mw, 0);
    if (tot <= 0) break;
    const cur = w.reduce((a, x) => a + (x.mw / tot) * x.s, 0);
    if ((up && cur >= target) || (!up && cur <= target)) break;
    const asc = [...w].sort((a, b) => a.s - b.s);
    const donor = (up ? asc : [...asc].reverse()).find((x) => x.mw > step + 0.01);
    const recip = (up ? [...asc].reverse() : asc).find((x) => ((x.mw + step) / tot) * 100 <= maxPosPct + 1e-6);
    if (!donor || !recip || donor.t === recip.t) break;
    donor.mw -= step; recip.mw += step; moved = true;
  }
  return moved ? w.map((x) => ({ t: x.t, mw: Math.round(x.mw) })) : null;
}

function buildFixes(ctx) {
  const { metrics, profile, settings, stocks, holdings, budgetMw, lang } = ctx;
  if (metrics.empty || !profile.ready) return [];
  const ko = lang === "ko";
  const byT = Object.fromEntries(stocks.map((s) => [s.t, s]));
  const live = metrics.rows.filter((r) => r.mw > 0);
  if (!live.length) return [];
  const sim = (hs) => {
    const clean = hs.filter((h) => h.mw > 0 && byT[h.t]);
    return computeMetrics(clean.map((h) => ({ ...h, won: h.mw * 10000, stock: byT[h.t] })), budgetMw * 10000, settings);
  };
  const other = holdings.filter((h) => !live.some((r) => r.t === h.t));
  const fin = (arr) => [...arr.filter((x) => x.mw > 0), ...other];
  const out = [];
  const midBeta = (profile.targetBetaMin + profile.targetBetaMax) / 2;

  // ── 베타가 목표 밖일 때: 지금 종목 그대로 비중만 조정
  if (metrics.beta > profile.targetBetaMax + 0.001 || metrics.beta < profile.targetBetaMin - 0.001) {
    const up = metrics.beta < profile.targetBetaMin;
    const w = shiftToward(live, (s) => effBeta(s, settings), midBeta, up, profile.maxPositionPct);
    if (w) {
      const nh = fin(w);
      const m2 = sim(nh);
      if (!m2.empty && Math.abs(m2.beta - midBeta) < Math.abs(metrics.beta - midBeta) - 0.01) {
        const moves = w.map((x) => ({ t: x.t, d: x.mw - (live.find((r) => r.t === x.t) || {}).mw }))
          .filter((x) => Math.abs(x.d) >= 1).sort((a, b) => b.d - a.d);
        out.push({
          id: "rebal-beta", icon: "", apply: nh, preview: m2,
          title: ko ? (up ? "지금 종목 그대로, 비중만 옮겨서 베타 올리기" : "지금 종목 그대로, 비중만 옮겨서 베타 낮추기")
                    : (up ? "Raise beta by shifting weights only" : "Lower beta by shifting weights only"),
          why: ko ? "새로 살 종목 없이, 이미 가진 것들 사이에서만 비중을 옮기는 방법이에요."
                  : "No new stocks — this only moves weight between what you already hold.",
          moves,
        });
      }
    }
  }

  // ── 변동성이 상한을 넘을 때: 현금 비중을 늘려 정확히 맞춤
  if (metrics.volP > profile.targetVolMaxPct + 0.01) {
    const ratio = (profile.targetVolMaxPct - 0.3) / metrics.volP;
    if (ratio > 0.2 && ratio < 0.999) {
      const w = live.map((r) => ({ t: r.t, mw: Math.round(r.mw * ratio) }));
      const nh = fin(w);
      const m2 = sim(nh);
      if (!m2.empty && m2.volP < metrics.volP - 0.2) {
        out.push({
          id: "cash-vol", icon: "", apply: nh, preview: m2,
          title: ko ? `현금을 ${(100 - (m2.investedW || 0)).toFixed(0)}%까지 늘려 출렁임 낮추기` : `Raise cash to ${(100 - (m2.investedW || 0)).toFixed(0)}% to cut swings`,
          why: ko ? "모든 종목을 같은 비율로 줄여 현금을 남기는 방법이에요. 종목 구성은 그대로 두고 위험만 줄여요."
                  : "Scales every holding down by the same ratio, leaving cash. Same mix, less risk.",
          moves: [],
        });
      }
    }
  }

  // ── 업종 쏠림: 초과분을 다른 업종으로 옮김
  if (metrics.maxSectorKey && metrics.maxSectorW > profile.maxSectorPct + 0.01) {
    const key = metrics.maxSectorKey;
    const inSec = live.filter((r) => r.stock.s === key);
    const outSec = live.filter((r) => r.stock.s !== key);
    if (outSec.length) {
      const cap = profile.maxSectorPct / 100;
      const invMw = live.reduce((a, r) => a + r.mw, 0);
      const secMw = inSec.reduce((a, r) => a + r.mw, 0);
      const targetSec = invMw * cap;
      const cut = secMw - targetSec;
      if (cut > 0.5) {
        const outMw = outSec.reduce((a, r) => a + r.mw, 0);
        const w = [
          ...inSec.map((r) => ({ t: r.t, mw: Math.round(r.mw * (targetSec / secMw)) })),
          ...outSec.map((r) => ({ t: r.t, mw: Math.round(r.mw + cut * (r.mw / outMw)) })),
        ];
        const nh = fin(w);
        const m2 = sim(nh);
        if (!m2.empty && m2.maxSectorW < metrics.maxSectorW - 0.5) {
          out.push({
            id: "sector", icon: "", apply: nh, preview: m2,
            title: ko ? `${SEC(key).ko} 비중을 ${profile.maxSectorPct}%까지 줄이기` : `Trim ${SEC(key).en} to ${profile.maxSectorPct}%`,
            why: ko ? "줄인 만큼을 다른 업종 종목들에 비례해서 나눠 담아요. 총 투자금은 그대로예요."
                    : "Redistributes the trimmed amount across your other industries. Same total invested.",
            moves: w.map((x) => ({ t: x.t, d: x.mw - (live.find((r) => r.t === x.t) || {}).mw })).filter((x) => Math.abs(x.d) >= 1).sort((a, b) => a.d - b.d),
          });
        }
      }
    }
  }

  // ── 한 종목 쏠림: 상한까지 자르고 나머지에 분배
  const over = live.filter((r) => r.wInv * 100 > profile.maxPositionPct + 0.01);
  if (over.length) {
    const invMw = live.reduce((a, r) => a + r.mw, 0);
    const capMw = invMw * (profile.maxPositionPct / 100);
    let freed = 0;
    const kept = live.map((r) => {
      if (r.wInv * 100 > profile.maxPositionPct + 0.01) { freed += r.mw - capMw; return { t: r.t, mw: Math.round(capMw) }; }
      return { t: r.t, mw: r.mw };
    });
    const room = kept.filter((x) => !over.some((o) => o.t === x.t));
    const roomMw = room.reduce((a, x) => a + x.mw, 0);
    if (freed > 0.5 && roomMw > 0) {
      const w = kept.map((x) => room.some((r) => r.t === x.t) ? { t: x.t, mw: Math.round(x.mw + freed * (x.mw / roomMw)) } : x);
      const nh = fin(w);
      const m2 = sim(nh);
      if (!m2.empty) {
        out.push({
          id: "pos", icon: "", apply: nh, preview: m2,
          title: ko ? `한 종목 상한(${profile.maxPositionPct}%)에 맞춰 자르기` : `Trim to the ${profile.maxPositionPct}% per-stock cap`,
          why: ko ? "상한을 넘은 종목을 잘라, 남은 종목들에 비례해서 옮겨 담아요." : "Cuts the oversized positions and spreads the amount across the rest.",
          moves: w.map((x) => ({ t: x.t, d: x.mw - (live.find((r) => r.t === x.t) || {}).mw })).filter((x) => Math.abs(x.d) >= 1),
        });
      }
    }
  }

  // ── 현금이 권장 최소보다 적을 때
  const cashPct = (metrics.cash / metrics.total) * 100;
  if (profile.cashFloorPct > 0 && cashPct < profile.cashFloorPct - 0.01) {
    const ratio = (100 - profile.cashFloorPct) / Math.max(metrics.investedW, 1);
    if (ratio > 0.2 && ratio < 0.999) {
      const w = live.map((r) => ({ t: r.t, mw: Math.round(r.mw * ratio) }));
      const nh = fin(w); const m2 = sim(nh);
      if (!m2.empty) out.push({
        id: "cashfloor", icon: "", apply: nh, preview: m2,
        title: ko ? `현금을 권장 최소 ${profile.cashFloorPct}%까지 남기기` : `Restore the ${profile.cashFloorPct}% cash floor`,
        why: ko ? "급할 때 안 팔아도 되게 해주는 여유분이에요. 모든 종목을 같은 비율로 줄여 만듭니다."
                : "The buffer that keeps you from having to sell at a bad moment.",
        moves: [],
      });
    }
  }

  // ── 종목 수가 부족할 때: 지수 ETF 후보 제시(개별 종목 추천이 아님)
  const n = live.length;
  if (n > 0 && n < profile.stocksMin) {
    const cands = stocks.filter((s) => s.s === "index" && !holdings.some((h) => h.t === s.t)).slice(0, 3);
    if (cands.length) out.push({
      id: "addidx", icon: "", apply: null, preview: null, candidates: cands,
      title: ko ? `종목이 ${n}개예요. 권장은 ${profile.stocksMin}개 이상` : `You hold ${n}; ${profile.stocksMin}+ is recommended`,
      why: ko ? "종목 수를 늘리는 가장 단순한 방법은 지수 ETF 한 개를 담는 거예요. 수백 개 종목을 한 번에 나눠 담는 효과가 나요."
              : "The simplest way to add breadth is one index ETF — it spreads across hundreds of names at once.",
      moves: [],
    });
  }
  return out.slice(0, 3);
}

function FixList({ lang, t, fixes, stocksById, holdings, setHoldings, metrics }) {
  const [open, setOpen] = useState(false);
  const [prev, setPrev] = useState(null);
  if (!fixes.length) return null;
  const num1 = (v) => (v > 0 ? "+" : "") + v.toFixed(0);
  const rowName = (tk) => { const s = stocksById[tk]; return s ? (lang === "ko" ? s.nk : s.ne) : tk; };
  return (
    <div style={{ marginTop: 11 }}>
      <button onClick={() => setOpen(!open)} style={{ width: "100%", display: "flex", alignItems: "center", justifyContent: "space-between", background: C.ink, color: "#fff", border: "none", borderRadius: 12, padding: "11px 13px", cursor: "pointer", fontFamily: FONT, fontSize: 13, fontWeight: 800 }}>
        <span>{t("recTitle")} ({fixes.length})</span><span style={{ fontSize: 11 }}>{open ? "▲" : "▼"}</span>
      </button>
      {prev && (
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8, background: C.tealSoft, borderRadius: 11, padding: "8px 11px", marginTop: 7 }}>
          <span style={{ fontSize: 12, color: "#0B6E66", fontWeight: 700 }}>{t("recApplied")}</span>
          <button onClick={() => { setHoldings(prev); setPrev(null); }} style={{ background: "#fff", border: "1.5px solid " + C.teal, color: C.teal, borderRadius: 9, padding: "5px 11px", fontSize: 11.5, fontWeight: 800, cursor: "pointer", fontFamily: FONT }}>{t("recUndo")}</button>
        </div>
      )}
      {open && (
        <div style={{ display: "flex", flexDirection: "column", gap: 9, marginTop: 9, animation: "fadeIn .2s ease" }}>
          {fixes.map((f) => (
            <div key={f.id} style={{ background: "#fff", border: "1.5px solid " + C.line, borderRadius: 14, padding: 13 }}>
              <div style={{ display: "flex", gap: 9, alignItems: "flex-start" }}>
                <span style={{ fontSize: 15, flexShrink: 0 }}>{f.icon}</span>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: 13, fontWeight: 800, color: C.ink, lineHeight: 1.5 }}>{f.title}</div>
                  <div style={{ fontSize: 12, color: C.sub, lineHeight: 1.6, marginTop: 3 }}>{f.why}</div>
                </div>
              </div>
              {f.preview && (
                <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 5, marginTop: 10 }}>
                  {[["β", metrics.beta, f.preview.beta, 2], ["σ", metrics.volP, f.preview.volP, 1],
                    [lang === "ko" ? "최대업종" : "Top sec", metrics.maxSectorW, f.preview.maxSectorW, 0],
                    [lang === "ko" ? "기대수익" : "E(r)", metrics.expRet, f.preview.expRet, 1]].map(([l, a, b, d]) => (
                    <div key={l} style={{ background: C.bg, borderRadius: 10, padding: "7px 4px", textAlign: "center" }}>
                      <div style={{ fontSize: 9.5, color: C.faint }}>{l}</div>
                      <div style={{ fontSize: 11.5, fontWeight: 800, color: C.ink }}>{a.toFixed(d)} → {b.toFixed(d)}</div>
                    </div>
                  ))}
                </div>
              )}
              {f.moves && f.moves.length > 0 && (
                <div style={{ marginTop: 9, background: C.bg, borderRadius: 11, padding: 10 }}>
                  <div style={{ fontSize: 10.5, color: C.faint, fontWeight: 700, marginBottom: 4 }}>{t("recMoves")}</div>
                  {f.moves.slice(0, 6).map((m) => (
                    <div key={m.t} style={{ display: "flex", justifyContent: "space-between", fontSize: 11.5, padding: "2px 0" }}>
                      <span style={{ color: C.ink, fontWeight: 600 }}>{rowName(m.t)}</span>
                      <span style={{ fontWeight: 800, color: m.d > 0 ? C.teal : C.coral }}>{num1(m.d)} {t("manwon")}</span>
                    </div>
                  ))}
                </div>
              )}
              {f.candidates && (
                <div style={{ marginTop: 9, display: "flex", flexDirection: "column", gap: 5 }}>
                  {f.candidates.map((s) => (
                    <div key={s.t} style={{ display: "flex", alignItems: "center", gap: 8, background: C.bg, borderRadius: 11, padding: "8px 10px" }}>
                      <span style={{ flex: 1, fontSize: 12, fontWeight: 700, color: C.ink }}>{lang === "ko" ? s.nk : s.ne} <span style={{ color: C.faint, fontWeight: 400 }}>β {s.beta.toFixed(2)}</span></span>
                      <button onClick={() => { setPrev(holdings); setHoldings([...holdings, { t: s.t, mw: Math.max(10, Math.round(metrics.invested / 10000 / 10)) }]); }}
                        style={{ background: C.blue, color: "#fff", border: "none", borderRadius: 9, padding: "5px 12px", fontSize: 11.5, fontWeight: 800, cursor: "pointer", fontFamily: FONT }}>{t("add")}</button>
                    </div>
                  ))}
                </div>
              )}
              {f.apply && (
                <Btn onClick={() => { setPrev(holdings); setHoldings(f.apply); }} style={{ width: "100%", marginTop: 9, padding: "10px 12px", fontSize: 13 }}>{t("recApply")}</Btn>
              )}
            </div>
          ))}
          <Sub style={{ fontSize: 10.5 }}>{t("recNote")}</Sub>
        </div>
      )}
    </div>
  );
}

// ================= 잘하고 있는 것 =================
function WellDoneCard({ lang, t, metrics, profile, settings }) {
  if (metrics.empty) return null;
  const ko = lang === "ko";
  const wins = [], todo = [];
  const push = (ok, icon, title, worth) => (ok ? wins : todo).push({ icon, title, worth });
  const nSec = Object.keys(metrics.sectorW).length;
  const nCls = CLS_LIST.filter((c) => (metrics.clsW[c] || 0) > 1).length;
  const n = metrics.rows.filter((r) => r.mw > 0).length;
  const saved = Math.max(metrics.wAvgVol - metrics.volP, 0);
  const cashPct = (metrics.cash / metrics.total) * 100;
  const curated = metrics.rows.filter((r) => r.mw > 0 && r.stock.x && r.stock.x.dk).length;

  push(saved > 1, "", ko ? "나눠 담아 위험을 실제로 줄였어요" : "Splitting actually cut your risk",
    ko ? `연간 출렁임 ${saved.toFixed(1)}%p 감소 · 약 ${fmtMw(metrics.total * saved / 100, lang)}` : `${saved.toFixed(1)}%p less annual swing (≈${fmtMw(metrics.total * saved / 100, lang)})`);
  push(nSec >= 3, "", ko ? "업종을 여러 곳에 나눴어요" : "Spread across industries", ko ? `${nSec}개 업종` : `${nSec} industries`);
  push(nCls >= 2, "", ko ? "자산군을 나눠 담았어요" : "More than one asset class",
    ko ? CLS_LIST.filter((c) => (metrics.clsW[c] || 0) > 1).map((c) => CLASSES[c].ko).join(" + ") : `${nCls} classes`);
  push(profile.ready && n >= profile.stocksMin, "", ko ? "종목 수가 권장 범위에 있어요" : "Holding count in range", ko ? `${n}개 (권장 ${profile.stocksMin}개 이상)` : `${n} (${profile.stocksMin}+ recommended)`);
  push(profile.ready && !metrics.rows.some((r) => r.wInv * 100 > profile.maxPositionPct + 0.01), "",
    ko ? "한 종목에 몰지 않았어요" : "No oversized position", ko ? `가장 큰 종목 ${Math.max(...metrics.rows.map((r) => r.wInv * 100)).toFixed(0)}% (상한 ${profile.maxPositionPct}%)` : `Largest ${Math.max(...metrics.rows.map((r) => r.wInv * 100)).toFixed(0)}%`);
  push(profile.ready && profile.targetBetaMin <= metrics.beta && metrics.beta <= profile.targetBetaMax, "",
    ko ? "내 그릇에 맞는 베타를 지켰어요" : "Beta matches your capacity", `β ${num(metrics.beta)} (${profile.targetBetaMin.toFixed(1)}–${profile.targetBetaMax.toFixed(1)})`);
  push(profile.cashFloorPct === 0 || cashPct >= profile.cashFloorPct - 0.01, "",
    ko ? "급할 때 쓸 현금을 남겨뒀어요" : "Kept a cash buffer", ko ? `현금 ${cashPct.toFixed(0)}% · ${fmtMw(metrics.cash, lang)}` : `${cashPct.toFixed(0)}% cash`);
  push(true, "", ko ? "레버리지·인버스를 쓰지 않았어요" : "No leveraged or inverse products",
    ko ? "장기 보유 시 원지수보다 뒤처지는 상품을 피했어요" : "Avoided products that decay against their index over time");
  push(metrics.divWon > 0, "", ko ? "배당이 들어오는 구조예요" : "The portfolio pays you cash", ko ? `연 ${fmtMw(metrics.divWon, lang)} (세전)` : `${fmtMw(metrics.divWon, lang)}/yr pre-tax`);
  push(curated >= Math.max(1, Math.ceil(n * 0.5)), "", ko ? "설명을 읽을 수 있는 종목이 절반 이상이에요" : "Most holdings have write-ups", ko ? `${curated}/${n}종목` : `${curated}/${n}`);

  return (
    <Card style={{ padding: 16, border: "1.5px solid #BEE9E4", background: "#F6FCFB" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
        <Bird mood="cheer" size={44} />
        <div>
          <H3>{t("wdTitle")}</H3>
          <Sub style={{ marginTop: 2 }}>{ko ? `${wins.length}가지를 이미 잘 하고 있어요` : `${wins.length} things already going right`}</Sub>
        </div>
      </div>
      <div style={{ marginTop: 11, display: "flex", flexDirection: "column", gap: 6 }}>
        {wins.map((w, i) => (
          <div key={i} style={{ display: "flex", gap: 9, alignItems: "flex-start", background: "#fff", borderRadius: 12, padding: "9px 11px" }}>
            <span style={{ fontSize: 14, flexShrink: 0 }}>{w.icon}</span>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ fontSize: 12.5, fontWeight: 800, color: C.ink }}>{w.title}</div>
              <div style={{ fontSize: 11.5, color: C.teal, fontWeight: 700, marginTop: 1 }}>{w.worth}</div>
            </div>
          </div>
        ))}
      </div>
      {todo.length > 0 && (
        <div style={{ marginTop: 10, background: "#fff", borderRadius: 12, padding: 11 }}>
          <div style={{ fontSize: 11, fontWeight: 800, color: C.faint, marginBottom: 5 }}>{t("wdTodo")}</div>
          {todo.map((w, i) => <div key={i} style={{ fontSize: 12, color: C.sub, padding: "2px 0" }}>· {w.title}</div>)}
        </div>
      )}
    </Card>
  );
}

// ================= 내 수익은 어디서 나오나요 =================
function ReturnAnatomyCard({ lang, t, metrics, settings }) {
  if (metrics.empty) return null;
  const ko = lang === "ko";
  const total = metrics.total;
  const rfWon = total * (settings.rf / 100);
  const premWon = total * (metrics.expRet - settings.rf) / 100;
  const divWon = metrics.divWon;
  const gainWon = Math.max(total * metrics.expRet / 100 - divWon, 0);
  const byCls = CLS_LIST.map((c) => {
    const rows = metrics.rows.filter((r) => r.c === c && r.mw > 0);
    if (!rows.length) return null;
    const contrib = rows.reduce((a, r) => a + r.w * r.stock.beta * clsMrp(c, settings) * 100, 0);
    return { c, contrib, w: metrics.clsW[c] || 0 };
  }).filter(Boolean);
  const top = [...metrics.rows].filter((r) => r.mw > 0)
    .map((r) => ({ r, c: r.w * (settings.rf + r.stock.beta * clsMrp(r.c, settings) * 100) }))
    .sort((a, b) => b.c - a.c).slice(0, 5);
  const maxC = Math.max(...top.map((x) => x.c), 0.01);
  return (
    <Card style={{ padding: 16 }}>
      <H3>{t("raTitle")}</H3>
      <Sub style={{ marginTop: 3 }}>{t("raSub")}</Sub>
      <div style={{ display: "flex", height: 28, borderRadius: 9, overflow: "hidden", marginTop: 11 }}>
        <div style={{ width: (rfWon / Math.max(rfWon + premWon, 1)) * 100 + "%", background: "#94A3B8", display: "flex", alignItems: "center", justifyContent: "center", color: "#fff", fontSize: 10.5, fontWeight: 800 }}>
          {ko ? "그냥 두면" : "risk-free"}
        </div>
        <div style={{ flex: 1, background: C.blue, display: "flex", alignItems: "center", justifyContent: "center", color: "#fff", fontSize: 10.5, fontWeight: 800 }}>
          {ko ? "위험을 감수한 대가" : "risk premium"}
        </div>
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8, marginTop: 8 }}>
        {[[ko ? "무위험 이자 몫" : "Risk-free part", rfWon, "#64748B"], [ko ? "위험 프리미엄 몫" : "Risk premium part", premWon, C.blue],
          [ko ? "배당으로 들어올 몫" : "Arrives as dividends", divWon, C.teal], [ko ? "주가 상승에 기대는 몫" : "Depends on price gains", gainWon, C.sand]].map(([l, v, col]) => (
          <div key={l} style={{ background: C.bg, borderRadius: 12, padding: 11 }}>
            <div style={{ fontSize: 10.5, color: C.faint }}>{l}</div>
            <div style={{ fontSize: 15, fontWeight: 900, color: col, marginTop: 2 }}>{fmtMw(v, lang)}</div>
          </div>
        ))}
      </div>
      {byCls.length > 1 && (
        <div style={{ marginTop: 10 }}>
          <Sub style={{ fontWeight: 700, color: C.ink, marginBottom: 5 }}>{t("raByCls")}</Sub>
          {byCls.map((b) => (
            <div key={b.c} style={{ display: "flex", alignItems: "center", gap: 7, fontSize: 11.5, padding: "3px 0" }}>
              <span style={{ width: 9, height: 9, borderRadius: 3, background: CLASSES[b.c].color, flexShrink: 0 }} />
              <span style={{ flex: 1, color: C.ink, fontWeight: 700 }}>{ko ? CLASSES[b.c].ko : CLASSES[b.c].en}</span>
              <span style={{ color: C.faint }}>{b.w.toFixed(0)}%{ko ? " 담아서" : " weight"}</span>
              <span style={{ color: C.ink, fontWeight: 800, width: 62, textAlign: "right" }}>+{b.contrib.toFixed(2)}%p</span>
            </div>
          ))}
        </div>
      )}
      <div style={{ marginTop: 10 }}>
        <Sub style={{ fontWeight: 700, color: C.ink, marginBottom: 5 }}>{t("raTop")}</Sub>
        {top.map(({ r, c }) => (
          <div key={r.t} style={{ marginBottom: 5 }}>
            <div style={{ display: "flex", justifyContent: "space-between", fontSize: 11.5, marginBottom: 2 }}>
              <span style={{ fontWeight: 700, color: C.ink }}>{lang === "ko" ? r.stock.nk : r.stock.ne}</span>
              <span style={{ fontWeight: 800, color: C.blueDeep }}>+{c.toFixed(2)}%p</span>
            </div>
            <div style={{ height: 8, background: C.bg, borderRadius: 4, overflow: "hidden" }}>
              <div style={{ width: (c / maxC) * 100 + "%", height: 8, background: C.blue }} />
            </div>
          </div>
        ))}
      </div>
      <Verdict>{t("raVerdict")}</Verdict>
    </Card>
  );
}

// ================= 팩터 성향 =================
const FACTORS = [
  ["pz", "규모", "Size", "작은 회사 쪽", "small-cap", "큰 회사 쪽", "large-cap"],
  ["vz", "가치", "Value", "싼 주식 쪽(가치)", "value", "비싼 주식 쪽(성장)", "growth"],
  ["mz", "모멘텀", "Momentum", "오르던 주식 쪽", "winners", "빠지던 주식 쪽", "losers"],
  ["qz", "퀄리티", "Quality", "돈 잘 버는 쪽", "profitable", "이익이 약한 쪽", "weak profit"],
];
function FactorTiltCard({ lang, t, metrics }) {
  if (metrics.empty) return null;
  const ko = lang === "ko";
  const rows = metrics.rows.filter((r) => r.mw > 0);
  const tilts = FACTORS.map(([k, ko1, en1, hiK, hiE, loK, loE]) => {
    let wsum = 0, acc = 0;
    rows.forEach((r) => { const v = r.stock[k]; if (typeof v === "number") { acc += r.wInv * v; wsum += r.wInv; } });
    if (wsum < 0.3) return null;
    return { k, name: ko ? ko1 : en1, tilt: acc / wsum - 50, hi: ko ? hiK : hiE, lo: ko ? loK : loE };
  }).filter(Boolean);
  if (!tilts.length) {
    return (
      <Card style={{ padding: 16 }}>
        <H3>{t("ftTitle")}</H3>
        <Sub style={{ marginTop: 8 }}>{t("ftNone")}</Sub>
      </Card>
    );
  }
  const strongest = [...tilts].sort((a, b) => Math.abs(b.tilt) - Math.abs(a.tilt))[0];
  return (
    <Card style={{ padding: 16 }}>
      <H3>{t("ftTitle")}</H3>
      <Sub style={{ marginTop: 3 }}>{t("ftSub")}</Sub>
      <div style={{ marginTop: 12, display: "flex", flexDirection: "column", gap: 11 }}>
        {tilts.map((f) => {
          const w = Math.min(Math.abs(f.tilt) / 50, 1) * 50;
          const right = f.tilt > 0;
          return (
            <div key={f.k}>
              <div style={{ display: "flex", justifyContent: "space-between", fontSize: 11, marginBottom: 3 }}>
                <span style={{ color: C.faint }}>{f.lo}</span>
                <span style={{ fontWeight: 800, color: C.ink }}>{f.name}</span>
                <span style={{ color: C.faint }}>{f.hi}</span>
              </div>
              <div style={{ position: "relative", height: 12, background: C.bg, borderRadius: 6 }}>
                <div style={{ position: "absolute", left: "50%", top: -2, bottom: -2, width: 1.5, background: C.faint }} />
                <div style={{ position: "absolute", top: 0, height: 12, borderRadius: 6, background: Math.abs(f.tilt) < 6 ? C.faint : C.violet, left: right ? "50%" : (50 - w) + "%", width: Math.max(w, 1.5) + "%", transition: "width .3s ease" }} />
              </div>
            </div>
          );
        })}
      </div>
      <Verdict>
        {Math.abs(strongest.tilt) < 6
          ? (ko ? "특별히 한쪽으로 기울지 않았어요. 시장 평균에 가까운 구성이에요." : "No strong tilt — close to the market average.")
          : (ko ? <>가장 두드러진 성향은 <b>{strongest.name}</b>이에요 — <b>{strongest.hi}</b>으로 기울어 있어요. 이런 성향은 ETF로도 싸게 담을 수 있어요. 내 수익이 종목 선택 실력인지 이 성향 때문인지 구분해봐야 하는 이유예요.</>
                : <>Your strongest tilt is <b>{strongest.name}</b>, leaning toward <b>{strongest.hi}</b>. Tilts like this are cheaply available as ETFs — which is why it's worth asking whether your returns come from skill or from the tilt.</>)}
      </Verdict>
      <Sub style={{ marginTop: 8, fontSize: 10.5 }}>{t("ftNote")}</Sub>
    </Card>
  );
}

// ================= 순서의 위험 =================
function SequenceRiskCard({ lang, t, metrics, profile }) {
  const [rate, setRate] = useState(4);
  if (metrics.empty) return null;
  const ko = lang === "ko";
  const yrs = Math.min(Math.max(profile.ready ? Math.round(profile.attrs ? profile.attrs.horizon * 2.5 : 15) : 15, 10), 30);
  const mu = metrics.cagr / 100, sd = metrics.volP / 100;
  const g = gaussFactory(2024);
  const rets = Array.from({ length: yrs }, () => mu + sd * g());
  const run = (arr) => {
    let v = metrics.total;
    const w = metrics.total * (rate / 100);
    const path = [v];
    for (const r of arr) { v = Math.max(v * (1 + r) - w, 0); path.push(v); }
    return path;
  };
  const bad = run([...rets].sort((a, b) => a - b));
  const good = run([...rets].sort((a, b) => b - a));
  const mid = run(rets);
  const W = 380, H = 130;
  const all = [...bad, ...good, ...mid];
  const maxV = Math.max(...all) * 1.05, minV = 0;
  const x = (i) => 10 + (i / yrs) * (W - 20);
  const y = (v) => H - 12 - ((v - minV) / Math.max(maxV - minV, 1)) * (H - 24);
  const path = (arr) => arr.map((v, i) => (i === 0 ? "M" : "L") + x(i) + "," + y(v)).join(" ");
  return (
    <Card style={{ padding: 16 }}>
      <H3>{t("srTitle")}</H3>
      <Sub style={{ marginTop: 3 }}>{t("srSub")}</Sub>
      <div style={{ display: "flex", alignItems: "center", gap: 10, marginTop: 10, background: C.bg, borderRadius: 12, padding: "9px 12px" }}>
        <span style={{ fontSize: 11.5, color: C.sub, fontWeight: 700, flexShrink: 0 }}>{t("srRate")}</span>
        <input type="range" min={0} max={8} step={0.5} value={rate} onChange={(e) => setRate(parseFloat(e.target.value))} style={{ flex: 1, accentColor: C.blue }} />
        <span style={{ fontSize: 13, fontWeight: 900, color: C.blueDeep, width: 78, textAlign: "right" }}>{ko ? `연 ${rate}%` : `${rate}%/yr`}</span>
      </div>
      <div style={{ fontSize: 10.5, color: C.faint, marginTop: 4 }}>{ko ? `${yrs}년 · 매년 ${fmtMw(metrics.total * rate / 100, lang)} 인출 가정` : `${yrs} years, withdrawing ${fmtMw(metrics.total * rate / 100, lang)} annually`}</div>
      <svg width="100%" viewBox={"0 0 " + W + " " + H} style={{ marginTop: 8 }}>
        <line x1="10" x2={W - 10} y1={y(metrics.total)} y2={y(metrics.total)} stroke={C.line} strokeDasharray="4 4" />
        <path d={path(good)} fill="none" stroke={C.teal} strokeWidth="2.2" />
        <path d={path(mid)} fill="none" stroke={C.faint} strokeWidth="1.6" strokeDasharray="3 3" />
        <path d={path(bad)} fill="none" stroke={C.coral} strokeWidth="2.2" />
      </svg>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
        <div style={{ background: C.tealSoft, borderRadius: 12, padding: 11, textAlign: "center" }}>
          <div style={{ fontSize: 10.5, color: "#0B6E66", fontWeight: 700 }}>{t("srGood")}</div>
          <div style={{ fontSize: 16, fontWeight: 900, color: C.teal, marginTop: 2 }}>{fmtMw(good[yrs], lang)}</div>
        </div>
        <div style={{ background: C.coralSoft, borderRadius: 12, padding: 11, textAlign: "center" }}>
          <div style={{ fontSize: 10.5, color: "#8E2A28", fontWeight: 700 }}>{t("srBad")}</div>
          <div style={{ fontSize: 16, fontWeight: 900, color: C.coral, marginTop: 2 }}>{fmtMw(bad[yrs], lang)}</div>
        </div>
      </div>
      <Verdict>
        {ko ? <>수익률의 <b>순서만</b> 바꿨을 뿐인데 결과가 <b>{fmtMw(good[yrs] - bad[yrs], lang)}</b> 차이가 나요. 평균 수익률은 두 경우 모두 똑같아요. 돈을 빼 쓰는 동안엔 '언제 나쁜 해가 오는가'가 '평균이 얼마인가'보다 중요해요.</>
             : <>Only the <b>order</b> changed, yet the outcomes differ by <b>{fmtMw(good[yrs] - bad[yrs], lang)}</b> — with identical average returns. While withdrawing, when the bad years arrive matters more than what the average is.</>}
      </Verdict>
      <Sub style={{ marginTop: 8, fontSize: 10.5 }}>{t("srNote")}</Sub>
    </Card>
  );
}

// ================= Diagnosis: hero, sections, check-in =================
function Light({ state, label, value }) {
  const C3 = [[C.teal, C.tealSoft, ""], ["#9A6B00", C.sandSoft, ""], [C.coral, C.coralSoft, ""]][state];
  return (
    <div style={{ flex: 1, minWidth: 132, background: C3[1], borderRadius: 14, padding: "11px 12px" }}>
      <div style={{ fontSize: 11, color: C3[0], fontWeight: 800 }}>{C3[2]} {label}</div>
      <div style={{ fontSize: 13, fontWeight: 800, color: C.ink, marginTop: 3, lineHeight: 1.45 }}>{value}</div>
    </div>
  );
}

function DiagHero({ lang, t, metrics, profile, score }) {
  const unpaid = 100 - metrics.r2;
  const l1 = unpaid <= 20 ? 0 : unpaid <= 35 ? 1 : 2;
  const secCap = profile.ready ? profile.maxSectorPct : 35;
  const l2 = metrics.maxSectorW <= secCap ? 0 : metrics.maxSectorW <= secCap + 10 ? 1 : 2;
  const gap = (profile.ready ? profile.riskNeedPct : 7) - metrics.expRet;
  const l3 = gap <= 0.5 ? 0 : gap <= 2 ? 1 : 2;
  const secName = metrics.maxSectorKey ? (lang === "ko" ? SEC(metrics.maxSectorKey).ko : SEC(metrics.maxSectorKey).en) : "–";
  const worst = Math.max(l1, l2, l3);
  const verdict = worst === 0
    ? (lang === "ko" ? "지금은 꽤 잘 짜여 있어요. 큰 손볼 곳이 안 보여요." : "This is well put together — nothing major to fix.")
    : worst === 1
      ? (lang === "ko" ? "큰 문제는 없지만, 한두 군데 다듬으면 더 단단해져요." : "No big problems — a tweak or two would firm it up.")
      : (lang === "ko" ? "지금 상태로는 손볼 곳이 있어요. 아래 한 가지부터 해보세요." : "There's something to fix here. Start with the one action below.");
  const action = l2 === 2
    ? (lang === "ko" ? `${secName} 비중을 ${secCap}% 아래로 줄여보세요. 지금은 업황 하나에 너무 많이 걸려 있어요.` : `Bring ${secName} below ${secCap}%. Too much rides on one industry right now.`)
    : l1 === 2
      ? (lang === "ko" ? "비중을 더 고르게 나눠보세요. 지금은 보상받지 못하는 위험이 많아요." : "Even out your weights — too much of your risk goes unpaid.")
      : l3 === 2
        ? (lang === "ko" ? "목표(연 " + profile.riskNeedPct + "%)가 지금 구성으로는 버거워요. 목표·기간·저축액 중 하나를 조정해보세요." : `Your ${profile.riskNeedPct}%/yr goal is a stretch for this mix. Adjust the goal, horizon, or savings.`)
        : worst === 1
          ? (lang === "ko" ? "계기판에서 노란불인 항목 하나만 초록으로 돌려놓으면 충분해요." : "Turn the one amber gauge green and you're set.")
          : (lang === "ko" ? "이 구성을 유지하면서, 정한 주기마다 점검만 해주세요." : "Keep this mix and just review on your chosen cadence.");
  return (
    <Card style={{ background: "linear-gradient(135deg, #F3F8FF, #EAF3FF)", border: "1.5px solid #D6E7FA", padding: 18 }}>
      <div style={{ display: "flex", gap: 14, alignItems: "flex-start" }}>
        <Bird mood={worst === 0 ? "cheer" : worst === 2 ? "worried" : "think"} size={60} />
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontSize: 11.5, fontWeight: 800, color: C.blueDeep }}>{t("diagTitle")} · {t("score")} {score}</div>
          <div style={{ fontSize: 17, fontWeight: 900, color: C.ink, marginTop: 3, letterSpacing: "-0.02em", lineHeight: 1.4 }}>{verdict}</div>
        </div>
      </div>
      <div style={{ display: "flex", flexWrap: "wrap", gap: 8, marginTop: 13 }}>
        <Light state={l1} label={t("lt1")} value={lang === "ko" ? `위험의 ${Math.round(metrics.r2)}%만 보상받는 중` : `${Math.round(metrics.r2)}% of risk is paid`} />
        <Light state={l2} label={t("lt2")} value={`${secName} ${metrics.maxSectorW.toFixed(0)}%`} />
        <Light state={l3} label={t("lt3")} value={gap > 0.05 ? (lang === "ko" ? `연 ${gap.toFixed(1)}%p 모자람` : `${gap.toFixed(1)}%p short`) : (lang === "ko" ? "닿을 수 있어요" : "Reachable")} />
      </div>
      <div style={{ marginTop: 11, background: "#fff", borderRadius: 14, padding: "12px 14px" }}>
        <div style={{ fontSize: 11.5, fontWeight: 800, color: C.blueDeep }}>{t("oneAction")}</div>
        <div style={{ fontSize: 13.5, color: C.ink, lineHeight: 1.6, marginTop: 3, fontWeight: 600 }}>{action}</div>
      </div>
    </Card>
  );
}

function Section({ title, sub, open, onToggle, children }) {
  return (
    <div>
      <button onClick={onToggle} style={{ width: "100%", display: "flex", alignItems: "center", justifyContent: "space-between", gap: 10, background: "#fff", border: "none", borderRadius: 16, padding: "14px 16px", cursor: "pointer", fontFamily: FONT, boxShadow: "0 1px 3px rgba(11,34,57,0.06)", textAlign: "left" }}>
        <span>
          <span style={{ fontSize: 15, fontWeight: 800, color: C.ink, display: "block" }}>{title}</span>
          {sub && <span style={{ fontSize: 11.5, color: C.faint }}>{sub}</span>}
        </span>
        <span style={{ fontSize: 11, color: C.faint, flexShrink: 0 }}>{open ? "▲" : "▼"}</span>
      </button>
      {open && <div style={{ marginTop: 12, display: "flex", flexDirection: "column", gap: 14, animation: "fadeIn .2s ease" }}>{children}</div>}
    </div>
  );
}

function CheckinCard({ lang, t, metrics, profile, checkins, onSave }) {
  const snap = {
    d: new Date().toISOString().slice(0, 10), inv: metrics.invested, beta: metrics.beta, vol: metrics.volP,
    exp: metrics.expRet, unpaid: 100 - metrics.r2, sec: metrics.maxSectorW,
    secKey: metrics.maxSectorKey, top3: metrics.top3, n: metrics.rows.filter((r) => r.mw > 0).length,
  };
  const last = checkins && checkins.length ? checkins[checkins.length - 1] : null;
  const rows = last ? [
    [t("ciAmount"), fmtMw(last.inv, lang), fmtMw(snap.inv, lang), snap.inv - last.inv, 0],
    [t("mVol"), pct(last.vol), pct(snap.vol), snap.vol - last.vol, 1],
    [t("mRet"), pct(last.exp), pct(snap.exp), snap.exp - last.exp, 2],
    [t("splitIdio"), pct(last.unpaid, 0), pct(snap.unpaid, 0), snap.unpaid - last.unpaid, 1],
    [t("mSector"), pct(last.sec, 0), pct(snap.sec, 0), snap.sec - last.sec, 1],
    [t("ciCount"), last.n, snap.n, snap.n - last.n, 0],
  ] : [];
  const dVol = last ? snap.vol - last.vol : 0, dExp = last ? snap.exp - last.exp : 0;
  const verdict = !last ? null
    : dVol > 0.5 && dExp <= 0.15
      ? (lang === "ko" ? "위험은 늘었는데 기대수익은 거의 그대로예요. 보상받지 못한 변화였어요." : "Risk went up, expected return barely moved — an uncompensated change.")
      : dVol > 0.5 && dExp > 0.15
        ? (lang === "ko" ? "위험이 늘어난 만큼 기대수익도 함께 올라갔어요. 값을 치르고 산 위험이에요." : "Risk rose and expected return rose with it — risk you actually got paid for.")
        : dVol < -0.5
          ? (lang === "ko" ? "위험을 줄이셨네요. 기대수익도 " + (dExp < -0.15 ? "함께 낮아졌어요" : "거의 그대로예요") + "." : "You cut risk; expected return " + (dExp < -0.15 ? "came down with it" : "held roughly steady") + ".")
          : (lang === "ko" ? "지난번과 큰 차이는 없어요. 유지하는 것도 훌륭한 선택이에요." : "Little changed since last time — holding steady is a fine choice.");
  return (
    <Card style={{ padding: 16 }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 10, flexWrap: "wrap" }}>
        <H3>{t("ciTitle")}</H3>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          {profile.checkFreq && <Chip color={C.blueDeep} soft={C.blueSoft}>{t("checkFreqL")} {profile.checkFreq}</Chip>}
          <Btn onClick={() => onSave(snap)} style={{ padding: "7px 13px", fontSize: 12 }}>{t("ciSave")}</Btn>
        </div>
      </div>
      {!last ? (
        <Sub style={{ marginTop: 8 }}>{t("ciEmpty")}</Sub>
      ) : (
        <>
          <Sub style={{ marginTop: 6 }}>{t("ciSince")} {last.d} · {checkins.length}{lang === "ko" ? "번째 기록" : " records"}</Sub>
          <div style={{ marginTop: 9 }}>
            {rows.map(([label, a, b, d, kind]) => {
              const flat = Math.abs(d) < 0.05;
              const good = kind === 0 ? d > 0 : kind === 1 ? d < 0 : d > 0;
              const col = flat ? C.faint : good ? C.teal : C.coral;
              return (
                <div key={label} style={{ display: "grid", gridTemplateColumns: "1.3fr 1fr 1fr 0.9fr", fontSize: 12, padding: "7px 4px", borderTop: "1px solid " + C.line, alignItems: "center" }}>
                  <span style={{ color: C.sub, fontWeight: 700 }}>{label}</span>
                  <span style={{ color: C.faint, textAlign: "right" }}>{a}</span>
                  <span style={{ color: C.ink, fontWeight: 800, textAlign: "right" }}>{b}</span>
                  <span style={{ color: col, fontWeight: 800, textAlign: "right" }}>{flat ? "–" : (d > 0 ? "+" : "") + (typeof d === "number" && Math.abs(d) >= 1000 ? fmtMw(d, lang) : d.toFixed(Math.abs(d) < 10 ? 1 : 0))}</span>
                </div>
              );
            })}
          </div>
          <Verdict>{verdict}</Verdict>
        </>
      )}
    </Card>
  );
}

function DiagnoseView({ lang, t, mode, metrics, profile, settings, tax, stocksById, setExplain, score, okCount, checkins, onCheckin }) {
  const [open, setOpen] = useState({});
  // 처음에는 모두 닫아 둡니다. 자세히/간단히는 카드 안쪽 밀도만 바꿉니다.
  if (metrics.empty) {
    return (
      <Card style={{ textAlign: "center", padding: 34, display: "flex", flexDirection: "column", alignItems: "center", gap: 10, maxWidth: 560, margin: "0 auto" }}>
        <Bird mood="think" size={66} />
        <Sub>{t("diagEmpty")}</Sub>
      </Card>
    );
  }
  const tg = (k) => setOpen((o) => ({ ...o, [k]: !o[k] }));
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
      <DiagHero lang={lang} t={t} metrics={metrics} profile={profile} score={score} />
      <CheckinCard lang={lang} t={t} metrics={metrics} profile={profile} checkins={checkins} onSave={onCheckin} />
      <Section title={t("sxW")} sub={t("sxWs")} open={!!open.w} onToggle={() => tg("w")}>
        <WellDoneCard lang={lang} t={t} metrics={metrics} profile={profile} settings={settings} />
      </Section>
      <Section title={t("sxA")} sub={t("sxAs")} open={!!open.a} onToggle={() => tg("a")}>
        <RiskJourneyCard lang={lang} t={t} metrics={metrics} stocksById={stocksById} settings={settings} profile={profile} mode={mode} />
      </Section>
      <Section title={t("sxB")} sub={t("sxBs")} open={!!open.b} onToggle={() => tg("b")}>
        <div className="grid2">
          <AssetMixCard lang={lang} t={t} metrics={metrics} settings={settings} />
          <SectorDonut lang={lang} t={t} metrics={metrics} stocksById={stocksById} />
        </div>
        <RiskContribCard lang={lang} t={t} metrics={metrics} stocksById={stocksById} />
      </Section>
      <Section title={t("sxR")} sub={t("sxRs")} open={!!open.r} onToggle={() => tg("r")}>
        <ReturnAnatomyCard lang={lang} t={t} metrics={metrics} settings={settings} />
      </Section>
      <Section title={t("sxC")} sub={t("sxCs")} open={!!open.c} onToggle={() => tg("c")}>
        <div className="grid2">
          <TailRiskCard lang={lang} t={t} metrics={metrics} />
          <ProbCard lang={lang} t={t} metrics={metrics} profile={profile} />
        </div>
      </Section>
      <Section title={t("sxD")} sub={t("sxDs")} open={!!open.d} onToggle={() => tg("d")}>
        <div className="grid2">
          <AlphaCard lang={lang} t={t} metrics={metrics} profile={profile} settings={settings} stocksById={stocksById} setExplain={setExplain} />
          <LegendsCard lang={lang} t={t} metrics={metrics} />
          <FactorTiltCard lang={lang} t={t} metrics={metrics} />
        </div>
      </Section>
      <Section title={t("sxE")} sub={t("sxEs")} open={!!open.e} onToggle={() => tg("e")}>
        <div className="grid2">
          <WhatIfLab lang={lang} t={t} metrics={metrics} profile={profile} settings={settings} stocksById={stocksById} />
          <TimeMachine lang={lang} t={t} metrics={metrics} settings={settings} />
          <SequenceRiskCard lang={lang} t={t} metrics={metrics} profile={profile} />
        </div>
      </Section>
      <Section title={t("sxF")} sub={t("sxFs")} open={!!open.f} onToggle={() => tg("f")}>
        <div className="grid2">
          <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
            <GoalGapCard lang={lang} t={t} metrics={metrics} profile={profile} />
            <ProjectionCard lang={lang} t={t} metrics={metrics} settings={settings} />
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
            <BenchCard lang={lang} t={t} metrics={metrics} profile={profile} settings={settings} />
            <TaxCard lang={lang} t={t} metrics={metrics} profile={profile} settings={settings} tax={tax} />
            <QuickFactsCard lang={lang} t={t} metrics={metrics} settings={settings} profile={profile} />
          </div>
        </div>
      </Section>
    </div>
  );
}

// ================= Export (ship's log) =================
function ExportView({ lang, t, metrics, profile, holdings, stocksById, settings, tax, setExplain, slotName, score }) {
  const [checks, setChecks] = useState([false, false, false, false, false]);
  const [cardM, setCardM] = useState(null);
  const openCard = () => {
    try {
      const data = makeCardData(holdings, stocksById, (metrics.cash || 0) / 1e4, score || 0, lang);
      const cv = renderPortfolioCard(data);
      setCardM({ cv, url: cv.toDataURL("image/png"), dateStr: data.dateStr });
    } catch (e) {}
  };
  const [copied, setCopied] = useState(false);
  if (metrics.empty) {
    return (
      <Card style={{ textAlign: "center", padding: 30, display: "flex", flexDirection: "column", alignItems: "center", gap: 10 }}>
        <Bird mood="think" size={64} />
        <Sub>{lang === "ko" ? "아직 담은 종목이 없어요. ② 포트폴리오 탭에서 먼저 만들어주세요." : "Nothing here yet. Build your portfolio in tab ② first."}</Sub>
      </Card>
    );
  }
  const rows = metrics.rows.filter((r) => r.mw > 0).map((r) => {
    const s = stocksById[r.t];
    const pk = s ? priceKrw(s, settings) : 0;
    return { ...r, s, shares: pk > 0 ? Math.floor(r.won / pk) : 0 };
  });
  const stamp = new Date().toISOString().slice(0, 10);
  const buildJson = () => JSON.stringify({ app: "Baepsae 뱁새 v12", author: T.credit.en, slot: slotName, date: stamp, dataAsOf: DATA_AS_OF, settings, profile, budgetWon: metrics.total, holdings: rows.map((r) => ({ ticker: r.t, name: r.s.nk, sector: r.s.s, priceAssumed: r.s.price, amountWon: r.won, weightPct: +(r.wInv * 100).toFixed(2), approxShares: r.shares, beta: r.s.beta, volPct: r.s.vol })), metrics: { beta: +num(metrics.beta), volPct: +num(metrics.volP), expRetPct: +num(metrics.expRet), sharpe: +num(metrics.sharpe), cagrPct: +num(metrics.cagr), r2Pct: +num(metrics.r2, 0), effN: +num(metrics.effN, 1), cashWon: Math.round(metrics.cash) } }, null, 2);
  const buildCsv = () => {
    const h = "ticker,name,sector,assumed_price_krw,amount_krw,weight_pct,approx_shares,beta,vol_pct";
    const lines = rows.map((r) => [r.t, r.s.nk, r.s.s, r.s.price, Math.round(r.won), (r.wInv * 100).toFixed(2), r.shares, r.s.beta, r.s.vol].join(","));
    return "\uFEFF" + h + "\n" + lines.join("\n") + "\nCASH,현금,-," + "-," + Math.round(metrics.cash) + "," + (metrics.cash / metrics.total * 100).toFixed(2) + ",-,0,0";
  };
  const buildMemo = () => {
    const L = [];
    L.push((lang === "ko" ? "뱁새 주문 메모 " : "Baepsae Order Memo ") + stamp);
    L.push(T.credit[lang]);
    L.push((lang === "ko" ? "예산 " : "Budget ") + fmtMw(metrics.total, lang) + " · β " + num(metrics.beta) + " · σ " + pct(metrics.volP) + " · E(r) " + pct(metrics.expRet));
    L.push("");
    rows.forEach((r) => L.push(`${r.s.nk} (${r.t}) — ${fmtMw(r.won, lang)} (${(r.wInv * 100).toFixed(1)}%) ≈ ${r.shares}${lang === "ko" ? "주" : "sh"} @${fmtPx(r.s.price, r.s)}`));
    L.push((lang === "ko" ? "현금 " : "Cash ") + fmtMw(metrics.cash, lang));
    L.push("");
    L.push(lang === "ko" ? "※ 가격은 " + DATA_AS_OF + " 추정치. 주문 시 실제 시세로 수량을 조정하세요." : "※ Prices are estimates as of " + DATA_AS_OF + ". Adjust share counts at live prices.");
    return L.join("\n");
  };
  const copyMemo = async () => {
    try { await navigator.clipboard.writeText(buildMemo()); setCopied(true); setTimeout(() => setCopied(false), 1600); } catch (e) {}
  };
  const allChecked = checks.every(Boolean);
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
      <Card style={{ padding: 16 }}>
        <H3>{t("logTitle")}</H3>
        <Sub style={{ marginTop: 4 }}>{t("logHint")}</Sub>
        <div style={{ marginTop: 12 }}>
          <div style={{ display: "grid", gridTemplateColumns: "2fr 1.1fr 0.9fr 0.9fr", fontSize: 10, color: C.faint, padding: "0 4px 5px" }}>
            <span>{t("name")}</span><span style={{ textAlign: "right" }}>{t("amount")}</span><span style={{ textAlign: "right" }}>{t("weight")}</span><span style={{ textAlign: "right" }}>{lang === "ko" ? "수량≈" : "≈sh"}</span>
          </div>
          {rows.map((r) => (
            <div key={r.t} style={{ display: "grid", gridTemplateColumns: "2fr 1.1fr 0.9fr 0.9fr", fontSize: 12.5, padding: "8px 4px", borderTop: "1px solid " + C.line, alignItems: "center" }}>
              <span style={{ fontWeight: 700, color: C.ink, display: "flex", alignItems: "center", gap: 7, minWidth: 0 }}>
                <Mono stock={r.s} size={26} /><span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{lang === "ko" ? r.s.nk : r.s.ne}</span>
              </span>
              <span style={{ textAlign: "right", fontWeight: 700 }}>{fmtMw(r.won, lang)}</span>
              <span style={{ textAlign: "right", color: C.sub }}>{(r.wInv * 100).toFixed(1)}%</span>
              <span style={{ textAlign: "right", color: C.sub }}>{r.shares.toLocaleString()}</span>
            </div>
          ))}
          <div style={{ display: "grid", gridTemplateColumns: "2fr 1.1fr 0.9fr 0.9fr", fontSize: 12.5, padding: "8px 4px", borderTop: "1.5px solid " + C.line }}>
            <span style={{ color: C.sub }}>{t("cash")}</span>
            <span style={{ textAlign: "right", fontWeight: 700 }}>{fmtMw(metrics.cash, lang)}</span>
            <span style={{ textAlign: "right", color: C.sub }}>{(metrics.cash / metrics.total * 100).toFixed(1)}%</span><span />
          </div>
        </div>
      </Card>
      {(() => {
        const usd = rows.filter((r) => r.s.ccy === "USD").reduce((a, r) => a + r.shares * r.s.price, 0);
        if (usd <= 0) return null;
        const feeP = settings.fxFee != null ? settings.fxFee : 0.5;
        const krw = usd * settings.fx * (1 + feeP / 100);
        return (
          <Card style={{ padding: 16, border: "1.5px solid #D6D9F5", background: "#F7F8FE" }}>
            <H3>{""} {t("fxTitle")}</H3>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 8, marginTop: 10 }}>
              <div style={{ background: "#fff", borderRadius: 12, padding: 11, textAlign: "center" }}>
                <div style={{ fontSize: 10, color: C.faint }}>{t("fxNeed")}</div>
                <div style={{ fontSize: 16, fontWeight: 900, color: CLASSES.us.color, marginTop: 2 }}>${Math.ceil(usd).toLocaleString()}</div>
              </div>
              <div style={{ background: "#fff", borderRadius: 12, padding: 11, textAlign: "center" }}>
                <div style={{ fontSize: 10, color: C.faint }}>{t("fxFee")}</div>
                <div style={{ fontSize: 16, fontWeight: 900, color: C.ink, marginTop: 2 }}>{feeP}%</div>
              </div>
              <div style={{ background: "#fff", borderRadius: 12, padding: 11, textAlign: "center" }}>
                <div style={{ fontSize: 10, color: C.faint }}>{t("fxCost")}</div>
                <div style={{ fontSize: 16, fontWeight: 900, color: C.ink, marginTop: 2 }}>{fmtMw(krw, lang)}</div>
              </div>
            </div>
            <Sub style={{ marginTop: 8, fontSize: 11 }}>{t("fxNote")} ({lang === "ko" ? "환율" : "rate"} {settings.fx.toLocaleString()}{lang === "ko" ? "원" : ""})</Sub>
          </Card>
        );
      })()}
      <TaxCard lang={lang} t={t} metrics={metrics} profile={profile} settings={settings} tax={tax} />
      <Card style={{ padding: 16, border: "1.5px solid " + (allChecked ? "#BEE9E4" : C.line), background: allChecked ? "#F4FBFA" : "#fff" }}>
        <H3>{t("checklist")}</H3>
        <div style={{ marginTop: 9, display: "flex", flexDirection: "column", gap: 7 }}>
          {["chk1", "chk2", "chk3", "chk4", "chk5"].map((k, i) => (
            <label key={k} style={{ display: "flex", gap: 10, alignItems: "flex-start", background: C.bg, borderRadius: 13, padding: 11, cursor: "pointer" }}>
              <input type="checkbox" checked={checks[i]} onChange={() => setChecks(checks.map((c, j) => (j === i ? !c : c)))} style={{ marginTop: 2, accentColor: C.teal, width: 15, height: 15 }} />
              <span style={{ fontSize: 12.5, color: C.ink, lineHeight: 1.55 }}>{t(k)}</span>
            </label>
          ))}
        </div>
        {allChecked && <Sub style={{ marginTop: 9, color: C.teal, fontWeight: 800 }}>{lang === "ko" ? "마음 점검 완료! 무리하지 않는 투자 되세요 " : "Mind check complete! Invest at your own pace "}</Sub>}
      </Card>
      <Card style={{ padding: 16, background: "linear-gradient(135deg, #1C2B45, #123B70)", color: "#fff" }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
          <div style={{ fontSize: 14.5, fontWeight: 900 }}>{t("alphaCard")}</div>
          <button onClick={() => setExplain("alpha")} style={{ background: "rgba(255,255,255,0.14)", border: "none", color: "#fff", borderRadius: 999, fontSize: 11, fontWeight: 800, padding: "5px 11px", cursor: "pointer", fontFamily: FONT }}>{lang === "ko" ? "자세히" : "More"}</button>
        </div>
        <div style={{ fontSize: 12.5, lineHeight: 1.7, marginTop: 7, opacity: 0.92 }}>
          {lang === "ko"
            ? "여기까지 왔다면 이제 알파(α) 이야기를 들을 차례예요. 알파는 위험(β)에 대한 정당한 보상을 뺀 '진짜 실력의 몫'이에요. 시장이 올라서 번 건 실력이 아니라는 뜻이죠. 그리고 불편한 진실 하나 — 장기적으로 양(+)의 알파를 내는 개인은 극소수예요. 내 포트폴리오가 인덱스를 이기지 못해도 부끄러운 게 아니에요. 중요한 건 내 위험 예산 안에서, 내 이유로 투자하는 거예요."
            : "Having come this far, you've earned the alpha talk. Alpha is the skill residual after fair pay for risk (β) — gains from a rising market aren't skill. One uncomfortable truth: very few individuals sustain positive alpha long-term. Trailing the index is no shame. What matters is investing within your risk budget, for your own reasons."}
        </div>
      </Card>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
        <Btn kind="dark" onClick={() => downloadFile("baepsae-portfolio-" + stamp + ".json", buildJson(), "application/json")}>{t("dlJson")}</Btn>
        <Btn kind="dark" onClick={() => downloadFile("baepsae-orders-" + stamp + ".csv", buildCsv(), "text/csv")}>{t("dlCsv")}</Btn>
      </div>
      <Btn onClick={openCard} style={{ width: "100%" }}>{lang === "ko" ? "포트폴리오 카드 만들기 (이미지 공유)" : "Make portfolio card (share image)"}</Btn>
      <ShareCardModal card={cardM} onClose={() => setCardM(null)} lang={lang} />
      <Btn kind="ghost" onClick={copyMemo} style={{ width: "100%" }}>{copied ? "" + t("copied") : t("copyText")}</Btn>
    </div>
  );
}

// ================= Settings =================
function SettingsPanel({ lang, t, settings, setSettings, tax, setTax, autoKeys, onClose }) {
  const isAuto = (k) => (autoKeys || []).includes(k);
  const F = ({ k, label, tip, step = 0.1, unit = "%" }) => (
    <div style={{ marginBottom: 11 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 10 }}>
        <span style={{ fontSize: 12.5, fontWeight: 700, color: C.ink }}>
          {label} {isAuto(k) ? <Chip color={C.teal} soft={C.tealSoft} style={{ marginLeft: 3 }}>{t("autoTag")}</Chip>
                              : <Chip color={C.faint} soft={C.bg} style={{ marginLeft: 3 }}>{t("assumeTag")}</Chip>}
        </span>
        <div style={{ display: "flex", alignItems: "center", gap: 4, flexShrink: 0 }}>
          <input type="number" step={step} value={settings[k]} onChange={(e) => setSettings({ ...settings, [k]: parseFloat(e.target.value) || 0 })}
            style={{ width: 78, borderRadius: 9, border: "1.5px solid " + C.line, padding: 7, fontSize: 13, textAlign: "right", fontFamily: FONT, outline: "none" }} />
          <span style={{ fontSize: 12, color: C.faint, width: 14 }}>{unit}</span>
        </div>
      </div>
      {tip && <div style={{ fontSize: 10.5, color: C.faint, marginTop: 3, lineHeight: 1.5 }}>{tip}</div>}
    </div>
  );
  const Grp = ({ title, children }) => (
    <div style={{ marginTop: 14 }}>
      <div style={{ fontSize: 11.5, fontWeight: 800, color: C.blueDeep, marginBottom: 7 }}>{title}</div>
      {children}
    </div>
  );
  return (
    <div onClick={onClose} style={{ position: "fixed", inset: 0, background: "rgba(11,34,57,0.45)", zIndex: 70, display: "flex", alignItems: "flex-end", justifyContent: "center" }}>
      <div onClick={(e) => e.stopPropagation()} style={{ background: "#fff", borderRadius: "26px 26px 0 0", padding: "22px 20px 30px", width: "100%", maxWidth: 560, maxHeight: "88vh", overflowY: "auto", animation: "slideUp .25s ease" }}>
        <div style={{ width: 40, height: 4, background: C.line, borderRadius: 2, margin: "0 auto 16px" }} />
        <H3 size={17}>{t("settings")}</H3>
        <Grp title={t("setBasic")}>
          {F({ k: "rf", label: t("rf"), tip: t("rfTip") })}
          {F({ k: "fx", label: t("setFx"), step: 10, unit: "₩" })}
        </Grp>
        <Grp title={t("setKr")}>
          <div style={{ marginBottom: 9 }}>
            <div style={{ fontSize: 11.5, color: C.sub, lineHeight: 1.6, marginBottom: 6 }}>{t("mrpScenTip")}</div>
            <div style={{ display: "flex", gap: 5 }}>
              {[[3.5, t("mrpLow")], [5.5, t("mrpBase")], [7.0, t("mrpHigh")]].map(([v, label]) => (
                <button key={v} onClick={() => setSettings({ ...settings, mrp: v, usMrp: Math.max(v - 0.5, 1) })}
                  style={{ flex: 1, fontSize: 11.5, fontWeight: 800, padding: "8px 4px", borderRadius: 10, cursor: "pointer", fontFamily: FONT,
                    border: "1.5px solid " + (Math.abs(settings.mrp - v) < 0.05 ? C.blue : C.line),
                    background: Math.abs(settings.mrp - v) < 0.05 ? C.blue : "#fff",
                    color: Math.abs(settings.mrp - v) < 0.05 ? "#fff" : C.sub }}>{label}<br /><span style={{ fontSize: 10, opacity: 0.85 }}>{v}%</span></button>
              ))}
            </div>
          </div>
          {F({ k: "mrp", label: t("mrp") })}
          {F({ k: "mktVol", label: t("mktVol"), step: 0.5 })}
        </Grp>
        <Grp title={t("setUs")}>
          {F({ k: "usMrp", label: t("mrp") })}
          {F({ k: "usVol", label: t("setUsVol"), step: 0.5, tip: t("setUsVolTip") })}
        </Grp>
        <Grp title={t("setMt")}>
          {F({ k: "mtMrp", label: t("mrp"), tip: t("setMtMrpTip") })}
          {F({ k: "mtVol", label: t("setMtVol"), step: 0.5 })}
        </Grp>
        <Grp title={lang === "ko" ? "채권" : "Bonds"}>
          {F({ k: "bdMrp", label: t("mrp"), tip: lang === "ko" ? "채권이 현금 대비 기대할 초과수익. 보통 주식보다 훨씬 작아요." : "Expected excess return of bonds over cash — much smaller than equities." })}
          {F({ k: "bdVol", label: lang === "ko" ? "채권 블록 변동성" : "Bond block volatility", step: 0.5 })}
        </Grp>
        <Grp title={t("setInfl")}>
          {F({ k: "infl", label: t("inflL"), tip: t("inflTip"), step: 0.1 })}
        </Grp>
        <Grp title={t("setTax")}>
          {[["divKr", t("taxDivKr")], ["divUs", t("taxDivUs")], ["gainUs", t("taxGainUs")], ["isaRate", "ISA"]].map(([k, label]) => (
            <div key={k} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 10, marginBottom: 9 }}>
              <span style={{ fontSize: 12.5, fontWeight: 700, color: C.ink }}>{label}</span>
              <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
                <input type="number" step={0.1} value={tax[k]} onChange={(e) => setTax({ ...tax, [k]: parseFloat(e.target.value) || 0 })}
                  style={{ width: 78, borderRadius: 9, border: "1.5px solid " + C.line, padding: 7, fontSize: 13, textAlign: "right", fontFamily: FONT, outline: "none" }} />
                <span style={{ fontSize: 12, color: C.faint, width: 14 }}>%</span>
              </div>
            </div>
          ))}
          <div style={{ fontSize: 10.5, color: C.faint, lineHeight: 1.55 }}>{t("taxNote")}</div>
        </Grp>
        <Grp title={t("setRho")}>
          {F({ k: "rhoKrUs", label: t("rhoKrUs"), step: 0.05, unit: "" })}
          {F({ k: "rhoKrBd", label: lang === "ko" ? "한국 ↔ 채권" : "KR ↔ Bonds", step: 0.05, unit: "" })}
          {F({ k: "rhoUsBd", label: lang === "ko" ? "미국 ↔ 채권" : "US ↔ Bonds", step: 0.05, unit: "" })}
          {F({ k: "rhoMtBd", label: lang === "ko" ? "금·은 ↔ 채권" : "Gold ↔ Bonds", step: 0.05, unit: "" })}
          {F({ k: "rhoKrMt", label: t("rhoKrMt"), step: 0.05, unit: "" })}
          {F({ k: "rhoUsMt", label: t("rhoUsMt"), step: 0.05, unit: "" })}
          <div style={{ fontSize: 10.5, color: C.faint, lineHeight: 1.55 }}>{t("rhoTip")}</div>
        </Grp>
        <Btn onClick={onClose} style={{ width: "100%", marginTop: 14 }}>{lang === "ko" ? "닫기" : "Close"}</Btn>
      </div>
    </div>
  );
}

// ================= Onboarding & launch =================
function Onboarding({ lang, onDone }) {
  const items = lang === "ko" ? [
    ["", "이건 이런 도구예요", "내 위험 그릇을 먼저 재고, 그 안에서 포트폴리오를 짜보는 연습 도구예요. 숫자 뒤에 '그래서 뭘 하면 좋을지'까지 같이 알려드려요."],
    ["", "이건 이런 게 아니에요", "종목 추천도, 매수 신호도, 수익 보장도 아니에요. 주문은 증권사 앱에서 직접 하셔야 하고, 결과에 대한 책임은 본인에게 있어요."],
    ["", "기록은 이 기기에만 남아요", "입력한 내용과 포트폴리오는 이 브라우저에만 저장돼요. 서버로 올라가지 않고, 만든 사람도 볼 수 없어요."],
  ] : [
    ["", "What this is", "A practice tool: measure your risk capacity first, then build inside it. Every number comes with what to actually do about it."],
    ["", "What this isn't", "Not stock picks, not buy signals, not a promise of returns. You place orders yourself, and the decisions are yours."],
    ["", "Your data stays here", "Everything is stored in this browser only. Nothing is uploaded, and the author cannot see it."],
  ];
  return (
    <div style={{ position: "fixed", inset: 0, background: "rgba(11,34,57,0.55)", zIndex: 90, display: "flex", alignItems: "center", justifyContent: "center", padding: 16 }}>
      <div style={{ background: "#fff", borderRadius: 24, padding: 24, maxWidth: 460, width: "100%", maxHeight: "88vh", overflowY: "auto", animation: "slideUp .3s ease" }}>
        <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 6 }}>
          <Bird mood="happy" size={72} />
          <div style={{ fontSize: 20, fontWeight: 900, color: C.ink }}>{lang === "ko" ? "안녕하세요, 뱁이예요" : "Hi, I'm Baebi"}</div>
          <Sub style={{ textAlign: "center" }}>{lang === "ko" ? "황새 말고, 내 걸음으로 " : "Not the stork's pace — your own "}</Sub>
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: 10, marginTop: 18 }}>
          {items.map(([e, h, b]) => (
            <div key={h} style={{ display: "flex", gap: 11, background: C.bg, borderRadius: 14, padding: 13 }}>
              <span style={{ fontSize: 18, flexShrink: 0 }}>{e}</span>
              <div>
                <div style={{ fontSize: 13, fontWeight: 800, color: C.ink }}>{h}</div>
                <div style={{ fontSize: 12.5, color: C.sub, lineHeight: 1.6, marginTop: 2 }}>{b}</div>
              </div>
            </div>
          ))}
        </div>
        <Btn onClick={onDone} style={{ width: "100%", marginTop: 16 }}>{lang === "ko" ? "시작하기" : "Get started"}</Btn>
      </div>
    </div>
  );
}

function LaunchScreen({ lang, t, slots, onNew, onOpen, onDelete, onRename, onImport, dataInfo }) {
  const fileRef = useRef(null);
  return (
    <div style={{ maxWidth: 620, margin: "0 auto", display: "flex", flexDirection: "column", gap: 14 }}>
      <Card style={{ display: "flex", gap: 14, alignItems: "center", padding: 20 }}>
        <Bird mood="cheer" size={64} />
        <div>
          <H3 size={19}>{lang === "ko" ? "어떻게 시작할까요?" : "How would you like to start?"}</H3>
          <Sub style={{ marginTop: 4 }}>{lang === "ko" ? "저장한 포트폴리오는 이 기기에만 남아요. 여러 개를 따로 만들어 비교해봐도 좋아요." : "Saves live only on this device. Feel free to keep several and compare."}</Sub>
        </div>
      </Card>
      <Btn onClick={onNew} style={{ width: "100%", padding: "16px 18px", fontSize: 15 }}>＋ {lang === "ko" ? "새로 시작하기" : "Start something new"}</Btn>
      {slots.length > 0 && (
        <Card style={{ padding: 16 }}>
          <H3 size={14}>{lang === "ko" ? "이어서 하기" : "Continue"} <span style={{ color: C.faint, fontWeight: 600, fontSize: 12 }}>({slots.length}/{MAX_SLOTS})</span></H3>
          <div style={{ marginTop: 8, display: "flex", flexDirection: "column", gap: 7 }}>
            {slots.map((s) => (
              <div key={s.id} style={{ display: "flex", alignItems: "center", gap: 10, background: C.bg, borderRadius: 13, padding: "11px 13px" }}>
                <button onClick={() => onOpen(s.id)} style={{ flex: 1, textAlign: "left", background: "none", border: "none", cursor: "pointer", fontFamily: FONT, minWidth: 0 }}>
                  <div style={{ fontSize: 13.5, fontWeight: 800, color: C.ink, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{s.name}</div>
                  <div style={{ fontSize: 11, color: C.faint, marginTop: 2 }}>
                    {s.updated}{s.p ? ` · ${s.p.n}${lang === "ko" ? "종목" : " holdings"} · β ${num(s.p.beta)} · ${fmtMw(s.p.inv, lang)}` : ""}
                  </div>
                </button>
                <button title={lang === "ko" ? "이름 바꾸기" : "Rename"} onClick={() => onRename(s.id, s.name)} style={{ background: "none", border: "none", cursor: "pointer", padding: 5, flexShrink: 0, lineHeight: 0 }}>
                  <Ic name="pen" size={14} color={C.faint} />
                </button>
                <button title={lang === "ko" ? "삭제" : "Delete"} onClick={() => onDelete(s.id, s.name)} style={{ background: "none", border: "none", cursor: "pointer", padding: 5, flexShrink: 0, lineHeight: 0 }}>
                  <Ic name="close" size={14} color={C.faint} />
                </button>
              </div>
            ))}
          </div>
        </Card>
      )}
      <input ref={fileRef} type="file" accept="application/json" style={{ display: "none" }}
        onChange={(e) => { const f = e.target.files && e.target.files[0]; if (f) { const rd = new FileReader(); rd.onload = () => onImport(String(rd.result)); rd.readAsText(f); } e.target.value = ""; }} />
      <Btn kind="ghost" onClick={() => fileRef.current && fileRef.current.click()} style={{ width: "100%" }}>{lang === "ko" ? "저장한 파일에서 불러오기 (JSON)" : "Load from a saved file (JSON)"}</Btn>
      <Card style={{ padding: 14, background: dataInfo.stale ? C.sandSoft : C.bg, border: "1px solid " + (dataInfo.stale ? "#F3DCB2" : C.line) }}>
        <div style={{ fontSize: 12, fontWeight: 800, color: dataInfo.stale ? "#8A5A16" : C.sub }}>
          {dataInfo.live ? (lang === "ko" ? "시세 데이터 기준일: " : "Data as of: ") + dataInfo.asOf : (lang === "ko" ? "내장 데이터 사용 중 (" : "Using built-in snapshot (") + DATA_AS_OF + ")"}
        </div>
        <div style={{ fontSize: 11, color: dataInfo.stale ? "#8A5A16" : C.faint, marginTop: 3, lineHeight: 1.55 }}>
          {dataInfo.stale
            ? (lang === "ko" ? "데이터가 일주일 넘게 갱신되지 않았어요. 숫자는 참고용으로만 보시고, 주문 전엔 증권사 시세를 꼭 확인하세요." : "Data hasn't refreshed in over a week. Treat the numbers as reference only and check live quotes before ordering.")
            : (lang === "ko" ? "모든 수치는 추정치예요. 주문 전엔 증권사 앱에서 실제 시세를 확인하세요." : "All figures are estimates. Check real quotes in your brokerage app before ordering.")}
        </div>
      </Card>
      <Sub style={{ textAlign: "center", fontSize: 10.5, padding: "0 10px" }}>{t("disclaimer")}</Sub>
    </div>
  );
}

const APP_CSS = `
  html { font-variant-numeric: tabular-nums }
  @keyframes slideUp { from { transform: translateY(40px); opacity: 0 } to { transform: none; opacity: 1 } }
  @keyframes fadeIn { from { opacity: 0 } to { opacity: 1 } }
  @keyframes spinA { to { transform: rotate(360deg) } }
  @keyframes bob { 0%,100% { transform: translateY(0) } 50% { transform: translateY(-5px) } }
  .spin { animation: spinA .8s linear infinite }
  * { -webkit-tap-highlight-color: transparent }
  textarea:focus, input:focus { border-color: #1B2B4B !important }
  .wrap { max-width: 1140px; margin: 0 auto; padding: 16px 18px }
  .grid3 { display: grid; grid-template-columns: 330px minmax(0,1fr) 340px; gap: 16px; align-items: start }
  .grid2 { display: grid; grid-template-columns: repeat(2, minmax(0,1fr)); gap: 14px; align-items: start }
  .qgrid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px }
  .stickyR { position: sticky; top: 122px; max-height: calc(100vh - 138px); padding-bottom: 4px }
  .stickyScroll { overflow-y: auto; min-height: 0; display: flex; flex-direction: column; gap: 12px }
  .narrow { max-width: 780px; margin: 0 auto }
  .mobilebar { display: none }
  @media (max-width: 1080px) { .grid3 { grid-template-columns: 1fr } .stickyR { position: static; max-height: none } .stickyScroll { overflow-y: visible } }
  @media (max-width: 880px) { .grid2 { grid-template-columns: 1fr } .qgrid { grid-template-columns: 1fr } }
  @media (max-width: 700px) {
    .wrap { padding: 12px 12px 84px }
    .hdr { gap: 7px }
    .stages { width: 100%; order: 3; padding-bottom: 2px }
    .stages::-webkit-scrollbar { display: none }
    .mobilebar { display: block; position: fixed; left: 0; right: 0; bottom: calc(56px + env(safe-area-inset-bottom)); z-index: 45; background: #fff; box-shadow: 0 -2px 12px rgba(11,34,57,0.12); border-radius: 12px 12px 0 0 }
    input[type=range] { height: 26px }
  }
  @media (prefers-reduced-motion: reduce) { * { animation: none !important; transition: none !important } }
`;

// ================= 오류 화면 (흰 화면 대신 원인을 보여줍니다) =================
function CrashScreen({ err, info }) {
  const [copied, setCopied] = useState(false);
  const detail = [String(err && err.message ? err.message : err), (err && err.stack) || "", (info && info.componentStack) || ""].join("\n").slice(0, 4000);
  const wipe = async () => {
    try {
      const list = await readSlots();
      await Promise.all(list.map((s) => store.del(KEY_SLOT(s.id))));
      await store.set(KEY_SLOTS, "[]");
    } catch (e) {}
    location.reload();
  };
  return (
    <div style={{ minHeight: "100vh", background: C.bg, fontFamily: FONT, padding: 20, boxSizing: "border-box" }}>
      <div style={{ maxWidth: 560, margin: "40px auto", background: "#fff", borderRadius: 22, padding: 22 }}>
        <div style={{ display: "flex", gap: 12, alignItems: "center" }}>
          <Bird mood="worried" size={56} />
          <div>
            <div style={{ fontSize: 17, fontWeight: 900, color: C.ink }}>문제가 생겨서 화면을 못 그렸어요</div>
            <div style={{ fontSize: 12.5, color: C.sub, marginTop: 3, lineHeight: 1.6 }}>아래 내용을 복사해서 알려주시면 바로 고칠 수 있어요. 저장된 포트폴리오는 그대로 남아 있어요.</div>
          </div>
        </div>
        <pre style={{ marginTop: 14, background: C.bg, borderRadius: 12, padding: 12, fontSize: 11, lineHeight: 1.55, color: "#8E2A28", whiteSpace: "pre-wrap", wordBreak: "break-all", maxHeight: 260, overflowY: "auto" }}>{detail}</pre>
        <div style={{ display: "flex", gap: 8, marginTop: 12, flexWrap: "wrap" }}>
          <Btn onClick={() => { try { navigator.clipboard.writeText(detail); setCopied(true); setTimeout(() => setCopied(false), 1600); } catch (e) {} }} style={{ flex: 1 }}>
            {copied ? "복사됐어요" : "오류 내용 복사하기"}
          </Btn>
          <Btn kind="ghost" onClick={() => location.reload()}>새로고침</Btn>
          <Btn kind="ghost" onClick={wipe} style={{ color: C.coral, borderColor: "#F5C9C8" }}>저장기록 지우고 처음부터</Btn>
        </div>
      </div>
    </div>
  );
}
class ErrorBoundary extends React.Component {
  constructor(props) { super(props); this.state = { err: null, info: null }; }
  static getDerivedStateFromError(err) { return { err }; }
  componentDidCatch(err, info) { this.setState({ err, info }); }
  render() { return this.state.err ? <CrashScreen err={this.state.err} info={this.state.info} /> : this.props.children; }
}

// ================= App =================
function AppInner({ seed, lang: langProp }) {
  const [lang, setLang] = useState(langProp || "ko");
  useEffect(() => { if (langProp) setLang(langProp); }, [langProp]);
  const [mode] = useState("detail"); // v11: 간단 모드는 별도 앱(SimpleApp)으로 분리
  const [stage, setStage] = useState(0);
  const [settings, setSettings] = useState({ ...DEFAULT_SETTINGS });
  const [tax, setTax] = useState({ ...DEFAULT_TAX });
  const [profile, setProfile] = useState({ ...DEFAULT_PROFILE });
  const [answers, setAnswers] = useState({});
  const [stocks, setStocks] = useState(BASE_STOCKS.map((s) => ({ ...s })));
  const [holdings, setHoldings] = useState([]);
  const [budgetMw, setBudgetMw] = useState(1000);
  const [explain, setExplain] = useState(null);
  const [showSettings, setShowSettings] = useState(false);
  const [expanded, setExpanded] = useState(null);
  const [checkins, setCheckins] = useState([]);
  const [slots, setSlots] = useState([]);
  const [slotId, setSlotId] = useState(null);
  const [slotName, setSlotName] = useState("");
  const [booted, setBooted] = useState(false);
  const [onb, setOnb] = useState(false);
  const [live, setLive] = useState({ live: false, asOf: null, stale: false });
  const universe = useRef(null);
  const [autoKeys, setAutoKeys] = useState([]);

  // ---- boot: onboarding flag, slots, live data ----
  useEffect(() => {
    (async () => {
      try { const seen = await store.get(KEY_ONB); if (!seen) setOnb(true); } catch (e) {}
      setSlots(await readSlots());
      const L = await loadLiveData();
      if (L) {
        universe.current = mergeStocks(BASE_STOCKS, L.stocks);
        setStocks(universe.current.map((s) => ({ ...s })));
        // 파이프라인이 계산한 시장 가정을 기본값으로 반영합니다(설정에서 언제든 수정 가능)
        const AUTO = ["rf", "mktVol", "usVol", "mtVol", "rhoKrUs", "rhoKrMt", "rhoUsMt", "bdVol", "rhoKrBd", "rhoUsBd", "rhoMtBd"];
        setSettings((s) => {
          const nx = { ...s };
          if (L.fx) nx.fx = L.fx;
          if (L.settings) AUTO.forEach((k) => { if (typeof L.settings[k] === "number") nx[k] = L.settings[k]; });
          return nx;
        });
        setAutoKeys(L.settings ? ["fx", ...AUTO.filter((k) => typeof L.settings[k] === "number")] : ["fx"]);
        const days = L.asOf ? Math.floor((Date.now() - new Date(L.asOf).getTime()) / 86400000) : 999;
        setLive({ live: true, asOf: L.asOf, stale: days > 7 });
      }
      setBooted(true);
    })();
  }, []);

  const baseUniverse = () => (universe.current || BASE_STOCKS);

  // ---- v11: 간단 모드에서 이어온 답변(seed)으로 새 슬롯 시작 ----
  const seededRef = useRef(false);
  useEffect(() => {
    if (!booted || !seed || seededRef.current) return;
    seededRef.current = true;
    const id = "s" + Date.now().toString(36);
    if (seed.quick) {
      // v15: 30초 진단 — 균형 기본 성향으로 바로 담기 화면에
      setProfile({ ...DEFAULT_PROFILE, targetBetaMin: 0.7, targetBetaMax: 1.15, targetVolMaxPct: 24,
        ready: true, source: "preset", title: lang === "ko" ? "빠른 진단 · 균형 기본값" : "Quick check · balanced default",
        summary: lang === "ko" ? "기본 성향으로 계산했어요. 성향 테스트를 하면 기준이 내게 맞춰져요." : "Using a balanced default profile.",
        flags: [], tips: [], checkFreq: "", interestedSectors: [] });
      setAnswers({}); setHoldings(seed.holdings || []); setBudgetMw(1000); setCheckins([]);
      setStocks(baseUniverse().map((s) => ({ ...s }))); setStage(1);
      setSlotId(id); setSlotName(lang === "ko" ? "빠른 진단" : "Quick check");
      return;
    }
    setProfile({ ...DEFAULT_PROFILE }); setAnswers(seed.answers || {}); setHoldings([]);
    setBudgetMw(seed.budgetMw || 1000); setCheckins([]);
    setStocks(baseUniverse().map((s) => ({ ...s }))); setStage(0);
    setSlotId(id); setSlotName(lang === "ko" ? "간단 모드에서 이어옴" : "From simple mode");
  }, [booted]);

  // ---- slot persistence ----
  const saveSlot = async (id, name, extra) => {
    const payload = {
      schema: SCHEMA, lang, mode, settings, tax, profile, answers, budgetMw, holdings, checkins, stage,
      customStocks: stocks.filter((s) => s.custom),
      stockEdits: (() => {
        const base = Object.fromEntries(baseUniverse().map((b) => [b.t, b]));
        const d = {};
        stocks.forEach((s) => {
          const b = base[s.t];
          if (!b) return;
          const diff = {};
          ["price", "beta", "vol", "per", "pbr", "dy", "al"].forEach((k) => { if (s[k] !== b[k]) diff[k] = s[k]; });
          if (Object.keys(diff).length) d[s.t] = diff;
        });
        return d;
      })(),
      ...extra,
    };
    await store.set(KEY_SLOT(id), JSON.stringify(payload));
    const m = await computeMetricsForSave();
    const next = [{ id, name, updated: new Date().toISOString().slice(0, 10), p: m }, ...(await readSlots()).filter((s) => s.id !== id)].slice(0, MAX_SLOTS);
    await writeSlots(next);
    setSlots(next);
  };
  const computeMetricsForSave = async () => {
    const inv = holdings.reduce((a, h) => { const s = stocks.find((x) => x.t === h.t); return a + (s ? h.mw * 10000 : 0); }, 0);
    return { n: holdings.length, inv, beta: metricsRef.current ? metricsRef.current.beta : 0 };
  };
  const metricsRef = useRef(null);

  const openSlot = async (id) => {
    try {
      const raw = await store.get(KEY_SLOT(id));
      if (raw) applyState(JSON.parse(raw));
    } catch (e) {}
    setSlotId(id);
    const s = (await readSlots()).find((x) => x.id === id);
    setSlotName(s ? s.name : "");
  };
  const applyState = (s) => {
    if (s.lang) setLang(s.lang);
    if (s.settings) setSettings({ ...DEFAULT_SETTINGS, ...s.settings });
    if (s.tax) setTax({ ...DEFAULT_TAX, ...s.tax });
    if (s.profile) setProfile({ ...DEFAULT_PROFILE, ...s.profile });
    if (s.answers) setAnswers(s.answers);
    if (s.budgetMw != null) setBudgetMw(s.budgetMw);
    let base = baseUniverse().map((x) => ({ ...x }));
    if (Array.isArray(s.customStocks)) base = [...base, ...s.customStocks.filter((c) => !base.some((p) => p.t === c.t))];
    if (s.stockEdits) base = base.map((p) => (s.stockEdits[p.t] ? { ...p, ...s.stockEdits[p.t] } : p));
    setStocks(base);
    setHoldings(Array.isArray(s.holdings) ? s.holdings : []);
    setCheckins(Array.isArray(s.checkins) ? s.checkins : []);
    setStage(s.stage != null ? s.stage : 0);
  };
  const newSlot = () => {
    const id = "s" + Date.now().toString(36);
    const name = (lang === "ko" ? "포트폴리오 " : "Portfolio ") + (slots.length + 1);
    setProfile({ ...DEFAULT_PROFILE }); setAnswers({}); setHoldings([]); setBudgetMw(1000);
    setCheckins([]); setStocks(baseUniverse().map((s) => ({ ...s }))); setStage(0);
    setSlotId(id); setSlotName(name);
  };
  const deleteSlot = async (id, name) => {
    const q = lang === "ko" ? `"${name || "이 저장본"}"을(를) 지울까요? 되돌릴 수 없어요.` : `Delete "${name || "this save"}"? This can't be undone.`;
    if (!window.confirm(q)) return;
    await store.del(KEY_SLOT(id));
    const next = (await readSlots()).filter((s) => s.id !== id);
    await writeSlots(next); setSlots(next);
  };
  const renameSlot = async (id, cur) => {
    const name = window.prompt(lang === "ko" ? "포트폴리오 이름을 입력하세요" : "Enter a new name", cur || "");
    if (name == null) return;
    const nm = name.trim().slice(0, 40);
    if (!nm) return;
    const next = (await readSlots()).map((s) => (s.id === id ? { ...s, name: nm } : s));
    await writeSlots(next); setSlots(next);
  };
  const importJson = (txt) => {
    try {
      const j = JSON.parse(txt);
      const st = j.state || j;
      const id = "s" + Date.now().toString(36);
      applyState(st);
      setSlotId(id); setSlotName((lang === "ko" ? "불러온 포트폴리오" : "Imported portfolio"));
    } catch (e) { window.alert(lang === "ko" ? "파일을 읽을 수 없어요." : "Couldn't read that file."); }
  };

  const t = (k) => (T[k] ? T[k][lang] : k);
  const stocksById = useMemo(() => Object.fromEntries(stocks.map((s) => [s.t, s])), [stocks]);
  const holdingsFull = useMemo(() => holdings.map((h) => ({ ...h, won: h.mw * 10000, stock: stocksById[h.t] })).filter((h) => h.stock), [holdings, stocksById]);
  const metrics = useMemo(() => computeMetrics(holdingsFull, budgetMw * 10000, settings), [holdingsFull, budgetMw, settings]);
  metricsRef.current = metrics;
  const rs = railStates(metrics, profile);
  const nStocks = metrics.empty ? 0 : metrics.rows.filter((r) => r.mw > 0).length;
  const posOk = metrics.empty ? false : !metrics.rows.some((r) => profile.ready && r.wInv * 100 > profile.maxPositionPct + 0.01);
  const countOk = profile.ready && nStocks >= profile.stocksMin && nStocks <= profile.stocksMax;
  const score = metrics.empty || !profile.ready ? 0 : Math.min(100, rs.ok * 18 + (countOk ? 14 : 0) + (posOk ? 14 : 0));

  // ---- autosave ----
  useEffect(() => {
    if (!booted || !slotId) return;
    const id = setTimeout(() => { saveSlot(slotId, slotName); }, 800);
    return () => clearTimeout(id);
  }, [booted, slotId, slotName, lang, mode, settings, tax, profile, answers, budgetMw, holdings, stocks, checkins, stage]);

  const addCheckin = (snap) => setCheckins((c) => [...c.filter((x) => x.d !== snap.d), snap].slice(-24));
  const loadDemo = () => {
    const want = [["005930", 200], ["000270", 120], ["105560", 120], ["AAPL", 150], ["VOO", 250], ["04020000", 100], ["207940", 60]];
    setHoldings(want.filter(([tk]) => stocks.some((s) => s.t === tk)).map(([tk, mw]) => ({ t: tk, mw })));
    setBudgetMw(1000);
  };
  const addStock = (s) => { if (!holdings.some((h) => h.t === s.t)) setHoldings([...holdings, { t: s.t, mw: Math.max(10, Math.round(budgetMw / 10)) }]); };
  const addCustom = (s) => { setStocks([...stocks, s]); setHoldings([...holdings, { t: s.t, mw: Math.max(10, Math.round(budgetMw / 10)) }]); };
  const updateStock = (tk, k, v) => setStocks(stocks.map((s) => (s.t === tk ? { ...s, [k]: v } : s)));
  const exitSlot = () => { setSlotId(null); setExpanded(null); };

  if (!booted) {
    return <div style={{ minHeight: "100vh", background: C.bg, fontFamily: FONT, display: "flex", alignItems: "center", justifyContent: "center" }}>
      <div style={{ textAlign: "center" }}><div style={{ animation: "bob 1.1s ease-in-out infinite" }}><Bird pose="fly" mood="cheer" size={64} /></div></div>
    </div>;
  }

  const StageBtn = ({ i, done }) => (
    <button onClick={() => setStage(i)} style={{ display: "flex", alignItems: "center", gap: 6, padding: "9px 14px", borderRadius: 999, border: "1.5px solid " + (stage === i ? C.ink : C.line), cursor: "pointer", fontFamily: FONT, fontSize: 13, fontWeight: 800, background: stage === i ? C.ink : "#fff", color: stage === i ? "#fff" : done ? C.teal : C.sub, whiteSpace: "nowrap" }}>
      {t("s" + (i + 1))}{done && stage !== i ? " " : ""}
    </button>
  );

  return (
    <div style={{ minHeight: "100vh", background: C.bg, fontFamily: FONT, color: C.ink, paddingBottom: 60 }}>
      <style>{APP_CSS}</style>
      {onb && <Onboarding lang={lang} onDone={() => { setOnb(false); store.set(KEY_ONB, "1"); }} />}
      <div style={{ background: "#fff", padding: "10px 16px", position: "sticky", top: 48, zIndex: 40, boxShadow: "0 1px 0 " + C.line }}>
        <div className="hdr" style={{ maxWidth: 1140, margin: "0 auto", display: "flex", alignItems: "center", justifyContent: "space-between", gap: 10, flexWrap: "wrap" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 9, minWidth: 0 }}>
            <Bird mood="happy" size={34} />
            <div style={{ minWidth: 0 }}>
              <div style={{ fontSize: 15.5, fontWeight: 700, letterSpacing: "-0.01em", lineHeight: 1.1, fontFamily: SERIF }}>{t("appName")}</div>
              <div style={{ fontSize: 9.5, color: C.faint, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{slotId ? slotName : t("appSub")}</div>
            </div>
          </div>
          {slotId && <div className="stages" style={{ display: "flex", alignItems: "center", gap: 6, overflowX: "auto" }}>
            <StageBtn i={0} done={profile.ready} /><StageBtn i={1} done={!metrics.empty} /><StageBtn i={2} done={false} /><StageBtn i={3} done={false} />
          </div>}
          <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
            <button onClick={() => setLang(lang === "ko" ? "en" : "ko")} style={{ background: C.bg, border: "none", borderRadius: 999, padding: "6px 10px", fontSize: 11.5, fontWeight: 800, color: C.sub, cursor: "pointer", fontFamily: FONT }}>{lang === "ko" ? "EN" : "한국어"}</button>
            {slotId && <button onClick={() => setShowSettings(true)} style={{ background: C.bg, border: "none", borderRadius: 999, width: 30, height: 30, cursor: "pointer", display: "inline-flex", alignItems: "center", justifyContent: "center" }}><Ic name="gear" size={15} color={C.sub} /></button>}
            {slotId && <button onClick={exitSlot} title={t("slotExit")} style={{ background: C.bg, border: "none", borderRadius: 999, width: 30, height: 30, cursor: "pointer", display: "inline-flex", alignItems: "center", justifyContent: "center" }}><Ic name="home" size={15} color={C.sub} /></button>}
          </div>
        </div>
      </div>

      <div className="wrap" style={{ display: "flex", flexDirection: "column", gap: 14 }}>
        {!slotId && <LaunchScreen lang={lang} t={t} slots={slots} onNew={newSlot} onOpen={openSlot} onDelete={deleteSlot} onRename={renameSlot} onImport={importJson} dataInfo={live} />}
        {slotId && live.stale && (
          <Card style={{ background: C.sandSoft, border: "1px solid #F3DCB2", padding: "11px 14px" }}>
            <Sub style={{ color: "#8A5A16", fontWeight: 700 }}>{lang === "ko" ? `시세 데이터가 ${live.asOf} 이후 갱신되지 않았어요. 주문 전엔 증권사 시세를 꼭 확인하세요.` : `Prices haven't refreshed since ${live.asOf}. Check live quotes before ordering.`}</Sub>
          </Card>
        )}
        {slotId && stage === 0 && (
          <div className="narrow" style={{ width: "100%" }}>
            <ProfileView lang={lang} t={t} profile={profile} setProfile={setProfile} answers={answers} setAnswers={setAnswers} goBuild={() => setStage(1)} />
          </div>
        )}
        {slotId && stage === 1 && (
          <BuildView lang={lang} t={t} mode={mode} settings={settings} profile={profile} holdings={holdings} setHoldings={setHoldings} budgetMw={budgetMw} setBudgetMw={setBudgetMw} metrics={metrics} stocksById={stocksById} stocks={stocks} addStock={addStock} addCustom={addCustom} updateStock={updateStock} expanded={expanded} setExpanded={setExpanded} setExplain={setExplain} score={score} okCount={rs.ok} goDiagnose={() => setStage(2)} onDemo={loadDemo} />
        )}
        {slotId && stage === 2 && (
          <DiagnoseView lang={lang} t={t} mode={mode} metrics={metrics} profile={profile} settings={settings} tax={tax} stocksById={stocksById} setExplain={setExplain} score={score} okCount={rs.ok} checkins={checkins} onCheckin={addCheckin} />
        )}
        {slotId && stage === 3 && (
          <div className="narrow" style={{ width: "100%", display: "flex", flexDirection: "column", gap: 14 }}>
            <ExportView lang={lang} t={t} metrics={metrics} profile={profile} holdings={holdings} stocksById={stocksById} settings={settings} tax={tax} setExplain={setExplain} slotName={slotName} score={score} />
            <Btn kind="ghost" onClick={exitSlot} style={{ width: "100%" }}>{t("slotExit")}</Btn>
          </div>
        )}
        <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 3, paddingTop: 6 }}>
          <Bird mood="cheer" size={44} />
          <Sub style={{ fontWeight: 800, color: C.faint }}>{t("tagline")} </Sub>
          <Sub style={{ fontWeight: 700, color: C.sub, marginTop: 2 }}>{t("credit")}</Sub>
        </div>
        <Sub style={{ textAlign: "center", padding: "2px 16px", fontSize: 10.5 }}>{t("disclaimer")}</Sub>
      </div>
      <ExplainSheet id={explain} lang={lang} onClose={() => setExplain(null)} />
      {showSettings && <SettingsPanel lang={lang} t={t} settings={settings} setSettings={setSettings} tax={tax} setTax={setTax} autoKeys={autoKeys} onClose={() => setShowSettings(false)} />}
      {slotId && stage === 1 && profile.ready && !metrics.empty && (
        <div className="mobilebar">
          <div style={{ display: "flex", alignItems: "center", gap: 10, padding: "9px 14px" }}>
            <div style={{ fontSize: 17, fontWeight: 900, color: score >= 85 ? C.teal : score >= 55 ? C.sand : C.coral }}>{score}</div>
            <div style={{ display: "flex", gap: 5, flex: 1 }}>
              {rs.states.map((ok, i) => (
                <div key={i} style={{ flex: 1, height: 6, borderRadius: 3, background: ok ? C.teal : C.coral, opacity: ok ? 1 : 0.65 }} />
              ))}
            </div>
            <button onClick={() => setStage(2)} style={{ background: C.ink, color: "#fff", border: "none", borderRadius: 10, padding: "7px 12px", fontSize: 12, fontWeight: 800, fontFamily: FONT, cursor: "pointer", flexShrink: 0 }}>{t("s3")}</button>
          </div>
        </div>
      )}
    </div>
  );
}

export default function App({ seed, lang }) {
  return (
    <ErrorBoundary>
      <AppInner seed={seed} lang={lang} />
    </ErrorBoundary>
  );
}

export { Bird, DEFAULT_SETTINGS, store, normCdf, SECTORS, SEC, KEY_SLOTS, KEY_SLOT };
