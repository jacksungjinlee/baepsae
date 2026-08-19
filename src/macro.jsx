// ================= 뱁새 v14 — 금리·원자재 =================
// 국고채 수익률 곡선, 장단기 금리차, 금·은·유가, 듀레이션 체험, 브라질 국채 사례.
// 원칙: 예측이 아니라 이해. 금리와 자산의 관계를 스스로 만져보게 합니다.
import React, { useState, useEffect, useMemo } from "react";
import { C, FONT, RAD, HAIR } from "./tokens.js";
import { Bird } from "./detail.jsx";
import { Verdict } from "./corp.jsx";

const CREDIT = "이성진, INSEAD MBA 26J · Jack (Sung Jin) Lee, INSEAD MBA 26J";
const clamp = (v, a, b) => Math.min(Math.max(v, a), b);

export const MyBox = ({ children }) => (
  <div style={{ border: "1.6px solid " + C.ink, borderRadius: 10, padding: "11px 13px", marginTop: 12 }}>
    <div style={{ fontSize: 12, fontWeight: 800, color: C.ink }}>그래서 나는?</div>
    <div style={{ fontSize: 11.5, color: C.sub, lineHeight: 1.65, marginTop: 5 }}>{children}</div>
  </div>
);

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

// ---------------- 선 차트 (월별 시계열) ----------------
function LineChart({ series, height = 220, unit = "", zero }) {
  // series: [{m:[...], v:[...], ko, color}]
  const W = 640, Hh = height, m = { l: 44, r: 10, t: 12, b: 26 };
  const all = series.flatMap((s) => s.v);
  if (!all.length) return null;
  let lo = Math.min(...all), hi = Math.max(...all);
  if (zero) { lo = Math.min(lo, 0); hi = Math.max(hi, 0); }
  const pad = (hi - lo) * 0.08 || 1;
  lo -= pad; hi += pad;
  const n = Math.max(...series.map((s) => s.v.length));
  const sx = (i, len) => m.l + (len <= 1 ? 0 : (i / (len - 1)) * (W - m.l - m.r));
  const sy = (v) => Hh - m.b - ((v - lo) / (hi - lo)) * (Hh - m.t - m.b);
  const labels = series[0].m;
  const step = Math.max(1, Math.floor(labels.length / 6));
  return (
    <svg viewBox={`0 0 ${W} ${Hh}`} style={{ width: "100%", height: "auto", display: "block" }}>
      <rect x={m.l} y={m.t} width={W - m.l - m.r} height={Hh - m.t - m.b} fill={C.bg} rx="6" />
      {[lo + pad, (lo + hi) / 2, hi - pad].map((v, i) => (
        <g key={i}>
          <line x1={m.l} y1={sy(v)} x2={W - m.r} y2={sy(v)} stroke={C.line} strokeWidth="1" strokeDasharray="2 3" />
          <text x={m.l - 6} y={sy(v) + 3} textAnchor="end" fontSize="9.5" fill={C.faint} fontFamily={FONT}>{v.toFixed(1)}{unit}</text>
        </g>
      ))}
      {zero && lo < 0 && hi > 0 && <line x1={m.l} y1={sy(0)} x2={W - m.r} y2={sy(0)} stroke={C.faint} strokeWidth="1.4" />}
      {labels.map((lb, i) => i % step === 0 ? <text key={i} x={sx(i, labels.length)} y={Hh - 8} textAnchor="middle" fontSize="9" fill={C.faint} fontFamily={FONT}>{lb}</text> : null)}
      {series.map((s) => (
        <g key={s.ko}>
          <path d={s.v.map((v, i) => `${i === 0 ? "M" : "L"}${sx(i, s.v.length)},${sy(v)}`).join(" ")}
            fill="none" stroke={s.color} strokeWidth="2.2" strokeLinejoin="round" />
          <circle cx={sx(s.v.length - 1, s.v.length)} cy={sy(s.v[s.v.length - 1])} r="3.5" fill={s.color} />
        </g>
      ))}
      <g>
        {series.map((s, i) => (
          <g key={s.ko} transform={`translate(${m.l + 8 + i * 130}, ${m.t + 12})`}>
            <line x1="0" y1="0" x2="16" y2="0" stroke={s.color} strokeWidth="2.5" />
            <text x="21" y="3.5" fontSize="10" fontWeight="700" fill={C.ink} fontFamily={FONT}>{s.ko}</text>
          </g>
        ))}
      </g>
    </svg>
  );
}

// ---------------- 수익률 곡선 ----------------
function CurveChart({ curve }) {
  const W = 640, Hh = 240, m = { l: 44, r: 14, t: 14, b: 30 };
  const all = [...curve.now, ...curve.ago];
  const lo = Math.min(...all) - 0.2, hi = Math.max(...all) + 0.2;
  const sx = (i) => m.l + (i / (curve.tenors.length - 1)) * (W - m.l - m.r);
  const sy = (v) => Hh - m.b - ((v - lo) / (hi - lo)) * (Hh - m.t - m.b);
  const path = (vals) => vals.map((v, i) => `${i === 0 ? "M" : "L"}${sx(i)},${sy(v)}`).join(" ");
  return (
    <svg viewBox={`0 0 ${W} ${Hh}`} style={{ width: "100%", height: "auto", display: "block" }}>
      <rect x={m.l} y={m.t} width={W - m.l - m.r} height={Hh - m.t - m.b} fill={C.bg} rx="6" />
      {curve.tenors.map((t, i) => (
        <text key={t} x={sx(i)} y={Hh - 10} textAnchor="middle" fontSize="10" fill={C.sub} fontFamily={FONT} fontWeight="700">{t}년</text>
      ))}
      {[lo + 0.2, (lo + hi) / 2, hi - 0.2].map((v, i) => (
        <text key={i} x={m.l - 6} y={sy(v) + 3} textAnchor="end" fontSize="9.5" fill={C.faint} fontFamily={FONT}>{v.toFixed(1)}%</text>
      ))}
      <path d={path(curve.ago)} fill="none" stroke="#B9C2D4" strokeWidth="2.2" strokeDasharray="5 4" />
      <path d={path(curve.now)} fill="none" stroke={C.ink} strokeWidth="2.6" />
      {curve.now.map((v, i) => (
        <g key={i}>
          <circle cx={sx(i)} cy={sy(v)} r="4" fill={C.ink} />
          <text x={sx(i)} y={sy(v) - 9} textAnchor="middle" fontSize="9.5" fontWeight="800" fill={C.ink} fontFamily={FONT}>{v.toFixed(2)}</text>
        </g>
      ))}
      <g transform={`translate(${m.l + 8}, ${m.t + 12})`}>
        <line x1="0" y1="0" x2="16" y2="0" stroke={C.ink} strokeWidth="2.6" /><text x="21" y="3.5" fontSize="10" fontWeight="700" fill={C.ink} fontFamily={FONT}>지금</text>
        <line x1="64" y1="0" x2="80" y2="0" stroke="#B9C2D4" strokeWidth="2.2" strokeDasharray="5 4" /><text x="85" y="3.5" fontSize="10" fontWeight="700" fill={C.sub} fontFamily={FONT}>1년 전</text>
      </g>
    </svg>
  );
}

// ---------------- 듀레이션 체험 ----------------
function DurationPlay({ baseY }) {
  const [mat, setMat] = useState(10);
  const [dy, setDy] = useState(1.0);
  const y = (baseY || 3.0) / 100;
  // 액면가 채권(쿠폰=수익률)의 맥컬레이 듀레이션 → 수정 듀레이션
  const dMac = (1 + y) / y * (1 - Math.pow(1 + y, -mat));
  const dMod = dMac / (1 + y);
  const chg = -dMod * dy;
  return (
    <div>
      <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
        {[1, 3, 5, 10, 20, 30].map((mv) => (
          <button className="bchip" key={mv} onClick={() => setMat(mv)}
            style={{ border: mat === mv ? "1.5px solid " + C.ink : "1.5px solid " + C.line, background: mat === mv ? C.ink : "#fff", color: mat === mv ? "#fff" : C.sub, borderRadius: 999, padding: "5px 12px", fontSize: 11.5, fontWeight: 800, cursor: "pointer", fontFamily: FONT }}>{mv}년물</button>
        ))}
      </div>
      <div style={{ marginTop: 14 }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
          <span style={{ fontSize: 12, fontWeight: 700, color: C.ink }}>금리가 이만큼 움직이면</span>
          <span style={{ fontSize: 15, fontWeight: 800, color: dy >= 0 ? C.up : C.down }}>{dy >= 0 ? "+" : ""}{dy.toFixed(1)}%p</span>
        </div>
        <input type="range" min="-3" max="3" step="0.1" value={dy} onChange={(e) => setDy(+e.target.value)} style={{ width: "100%", accentColor: C.ink }} />
      </div>
      <div style={{ background: C.bg, border: HAIR, borderRadius: 8, padding: 16, marginTop: 10, textAlign: "center" }}>
        <div style={{ fontSize: 11.5, color: C.sub }}>{mat}년물 채권 가격은 대략</div>
        <div style={{ fontSize: 30, fontWeight: 800, color: chg >= 0 ? C.up : C.down, fontVariantNumeric: "tabular-nums" }}>{chg >= 0 ? "+" : ""}{chg.toFixed(1)}%</div>
        <div style={{ fontSize: 10.5, color: C.faint, marginTop: 4 }}>수정 듀레이션 약 {dMod.toFixed(1)}년 × 금리 변화 (1차 근사 · 현 수익률 {(y * 100).toFixed(1)}% 가정)</div>
      </div>
      <Sub style={{ marginTop: 10, fontSize: 11.5 }}>
        같은 "채권"이라도 만기가 길수록 금리에 몇 배로 출렁여요. 30년물은 안전자산이 아니라 <b style={{ color: C.ink }}>금리 방향에 거는 큰 베팅</b>에 가까워요 — 채권 ETF를 고를 때 가장 먼저 볼 것이 듀레이션인 이유예요.
      </Sub>
    </div>
  );
}

// ---------------- 브라질 국채 사례 ----------------
// ---------------- 루트 ----------------
function DeepBody({ data }) {
  const g10 = data.g10 || {};
  const g10Series = [
    g10.kr ? { ...g10.kr, ko: "한국", color: C.ink } : null,
    g10.us ? { ...g10.us, ko: "미국", color: "#8A6FB8" } : null,
    g10.jp ? { ...g10.jp, ko: "일본", color: "#C9A227" } : null,
    g10.de ? { ...g10.de, ko: "독일", color: C.teal } : null,
  ].filter(Boolean);
  const cr = data.credit;
  const tn = data.tenor;
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
      <div style={{ fontSize: 11.5, color: C.sub, background: "#fff", border: HAIR, borderRadius: 10, padding: "10px 14px", lineHeight: 1.6 }}>
        채권·환율을 조금 더 깊게 보는 자리예요. 처음이라면 기본 탭부터 보셔도 충분해요.
      </div>
      <Card>
        <H num="01" main="주요국 10년물" sub="한국·미국·일본·독일 · 월별 · 최근 3년" />
        {g10Series.length >= 2 ? (
          <>
            {(() => {
              const last = (x) => x.v[x.v.length - 1];
              const kr = g10Series.find((x) => x.ko === "한국"), us = g10Series.find((x) => x.ko === "미국");
              if (!kr || !us) return null;
              const k = last(kr), u = last(us);
              return <Verdict>{`지금 한국 10년물(${k.toFixed(1)}%)은 미국(${u.toFixed(1)}%)보다 ${k < u ? "낮아요" : "높아요"}. 돈은 금리 높은 쪽으로 가려 하고, 그 압력을 환율이 받아요.`}</Verdict>;
            })()}
            <div style={{ marginTop: 10 }}><LineChart series={g10Series} height={230} unit="%" /></div>
            <Sub style={{ marginTop: 8, fontSize: 11 }}>국채 금리는 그 나라 돈의 값이에요. 나라 사이의 차이와 방향이, 환율과 글로벌 자금 흐름의 배경이에요.</Sub>
          </>
        ) : <Sub style={{ padding: "22px 0", textAlign: "center" }}>데이터 갱신 후 표시돼요.</Sub>}
      </Card>
      <Card>
        <H num="02" main="만기별 한·미 금리와 환헤지 비용" sub="1 · 3 · 5 · 10년 · 지금 값" />
        {tn && tn.length ? (
          <>
            <div style={{ overflowX: "auto", marginTop: 10 }}>
              <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12, textAlign: "right" }}>
                <thead><tr>
                  <th style={{ textAlign: "left", padding: "7px 6px", borderBottom: "2px solid " + C.ink, fontSize: 10.5, color: C.faint }}>만기</th>
                  <th style={{ padding: "7px 6px", borderBottom: "2px solid " + C.ink, fontSize: 10.5, color: C.faint }}>한국</th>
                  <th style={{ padding: "7px 6px", borderBottom: "2px solid " + C.ink, fontSize: 10.5, color: C.faint }}>미국</th>
                  <th style={{ padding: "7px 6px", borderBottom: "2px solid " + C.ink, fontSize: 10.5, color: C.faint }}>차이(미−한)</th>
                </tr></thead>
                <tbody>
                  {tn.map(([yr, k, u]) => (
                    <tr key={yr} style={{ borderBottom: "1px solid " + C.line }}>
                      <td style={{ textAlign: "left", padding: "8px 6px", fontWeight: 800, color: C.ink }}>{yr}년</td>
                      <td style={{ padding: "8px 6px", fontVariantNumeric: "tabular-nums" }}>{k == null ? "–" : k.toFixed(2) + "%"}</td>
                      <td style={{ padding: "8px 6px", fontVariantNumeric: "tabular-nums" }}>{u == null ? "–" : u.toFixed(2) + "%"}</td>
                      <td style={{ padding: "8px 6px", fontVariantNumeric: "tabular-nums", fontWeight: 800, color: (k != null && u != null && u - k > 0) ? C.coral : C.teal }}>{k != null && u != null ? (u - k >= 0 ? "+" : "") + (u - k).toFixed(2) + "%p" : "–"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <MyBox>
              달러 자산을 환헤지하면 이 금리 차이만큼 비용을 내요. 1년짜리 헤지 비용은 두 나라 1년 금리의 차이 — 위 표의 1년 행이 바로 그 값이에요. 차이가 클수록 헤지는 비싸지고, 환노출을 택하면 이 비용 대신 환율 변동을 안는 거예요.
            </MyBox>
          </>
        ) : <Sub style={{ padding: "22px 0", textAlign: "center" }}>ECOS 연동 후 표시돼요.</Sub>}
      </Card>
      <Card>
        <H num="03" main="신용 스프레드" sub="회사채(AA−) − 국고채 3년 · 시장의 긴장 게이지" />
        {cr ? (
          <>
            <Verdict>{`지금 스프레드는 ${cr.now.toFixed(2)}%p — 최근 3년에서 ${cr.pct >= 80 ? "높은" : cr.pct >= 40 ? "보통" : "낮은"} 수준이에요(백분위 ${cr.pct}). 회사채와 국고채의 금리 차이는 시장이 매기는 부도 걱정의 가격이에요.`}</Verdict>
            <div style={{ marginTop: 12, padding: "18px 8px 6px" }}>
              <div style={{ position: "relative", height: 26, background: C.bg, border: HAIR, borderRadius: 999 }}>
                <div style={{ position: "absolute", top: -16, left: 0, fontSize: 9.5, color: C.faint }}>{cr.lo.toFixed(1)}%p</div>
                <div style={{ position: "absolute", top: -16, right: 0, fontSize: 9.5, color: C.faint }}>{cr.hi.toFixed(1)}%p</div>
                <div style={{ position: "absolute", top: 3, bottom: 3, left: `calc(${Math.min(97, Math.max(1, cr.pct))}% - 10px)`, width: 20, borderRadius: 999, background: C.ink }} />
              </div>
              <div style={{ fontSize: 10, color: C.faint, marginTop: 6, textAlign: "center" }}>최근 3년 범위 안에서 지금 위치</div>
            </div>
            <div style={{ marginTop: 8 }}><LineChart series={[{ m: cr.m, v: cr.v, ko: "스프레드", color: C.ink }]} height={170} unit="%p" /></div>
            <MyBox>
              스프레드가 갑자기 벌어지면, 빚 많은 회사의 주가가 먼저 아파요. 내 종목의 재무 신호에 차입 관련 깃발이 있다면 이 게이지를 가끔 봐두세요. 신호이지 타이머는 아니에요.
            </MyBox>
          </>
        ) : <Sub style={{ padding: "22px 0", textAlign: "center" }}>ECOS 연동 후 표시돼요.</Sub>}
      </Card>
      <div style={{ fontSize: 10.5, color: C.faint, textAlign: "center", lineHeight: 1.7, padding: "6px 0 20px" }}>
        {CREDIT}
      </div>
    </div>
  );
}

export function MacroBody({ data }) {
  const baseY = data.curve && data.curve.tenors.includes(10) ? data.curve.now[data.curve.tenors.indexOf(10)] : null;
  const sprSeries = [
    data.sprKr ? { ...data.sprKr, ko: "한국 10년−3년", color: C.ink } : null,
    data.sprUs ? { ...data.sprUs, ko: "미국 10년−2년", color: "#8A6FB8" } : null,
  ].filter(Boolean);
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
      <div className="cgrid2" style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
        <Card>
          <H num="01" main="국고채 수익률 곡선" sub={data.curve ? `한국은행 ECOS · 기준 ${data.curve.date}` : "한국은행 ECOS 연동"} />
          {data.curve ? (
            <>
              {(() => {
                const d = data.curve.now.map((v, i) => v - data.curve.ago[i]);
                const avg = d.reduce((a, b) => a + b, 0) / d.length;
                const shortD = d[0], longD = d[d.length - 1];
                let v;
                if (Math.abs(avg) < 0.1) v = '금리는 1년 전과 비슷한 수준이에요.';
                else if (avg < 0) v = '1년 전보다 금리가 전반적으로 내렸어요.' + (shortD < longD - 0.15 ? ' 특히 단기가 많이 내렸어요. 시장은 금리 인하를 기대하는 거예요.' : '');
                else v = '1년 전보다 금리가 전반적으로 올랐어요.';
                return <Verdict>{v}</Verdict>;
              })()}
              <div style={{ marginTop: 10 }}><CurveChart curve={data.curve} /></div>
              <Sub style={{ marginTop: 8, fontSize: 11 }}>
                만기별 금리를 이은 선이에요. 곡선 전체가 오르내리면 통화정책·물가 기대의 변화, 짧은 쪽과 긴 쪽의 기울기가 바뀌면 경기 전망의 변화를 뜻할 때가 많아요. 1년 전(점선)과 비교해 어디가 움직였는지 보세요.
              </Sub>
            </>
          ) : (
            <Sub style={{ padding: "26px 0", textAlign: "center" }}>
              ECOS 키가 아직 연결되지 않았어요.<br />ecos.bok.or.kr에서 무료 키 발급 → GitHub 저장소 → Settings → Secrets → <b style={{ color: C.ink }}>ECOS_API_KEY</b> 등록 → 데이터 갱신 실행.
            </Sub>
          )}
        </Card>
        <Card>
          <H num="02" main="장단기 금리차" sub="장기금리 − 단기금리 · 월별 · 최근 3년" />
          {sprSeries.length ? (
            <>
              {(() => {
                const last = (x) => x && x.v && x.v.length ? x.v[x.v.length - 1] : null;
                const kr = last(data.sprKr), us = last(data.sprUs);
                if (kr == null && us == null) return null;
                const seg = [];
                if (kr != null) seg.push('한국 ' + (kr >= 0 ? '+' : '') + kr.toFixed(2) + '%p ' + (kr < 0 ? '역전' : '정상'));
                if (us != null) seg.push('미국 ' + (us >= 0 ? '+' : '') + us.toFixed(2) + '%p ' + (us < 0 ? '역전' : '정상'));
                return <Verdict>{'지금 금리차: ' + seg.join(' · ') + (((kr != null && kr < 0) || (us != null && us < 0)) ? '. 역전은 경고등이지, 타이머는 아니에요.' : '. 정상 범위예요.')}</Verdict>;
              })()}
              <div style={{ marginTop: 10 }}><LineChart series={sprSeries} unit="%p" zero /></div>
              <Sub style={{ marginTop: 8, fontSize: 11 }}>
                보통은 오래 빌려줄수록 금리가 높아 양(+)이에요. 0 아래로 뒤집히는 역전은 역사적으로 경기 둔화에 앞서는 일이 많았지만 — <b style={{ color: C.ink }}>신호이지 타이머가 아니에요</b>. 역전 후 실제 둔화까지 시차도, 예외도 있었어요.
              </Sub>
            </>
          ) : <Sub style={{ padding: "26px 0", textAlign: "center" }}>데이터 갱신 후 표시돼요.</Sub>}
        </Card>
      </div>

      <Card>
        <H num="03" main="금·은·유가" sub="월별 · 최근 3년 · 금·은은 원화 환산, 유가는 달러(WTI)" />
        <div className="cgrid3m" style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 14, marginTop: 10 }}>
          {[
            data.gold ? { d: data.gold, ko: "금 (원/온스)", color: "#C9A227" } : null,
            data.silver ? { d: data.silver, ko: "은 (원/온스)", color: "#8B95A8" } : null,
            data.wti ? { d: data.wti, ko: "WTI (달러/배럴)", color: "#5A4F45" } : null,
          ].filter(Boolean).map((s) => (
            <div key={s.ko}>
              <LineChart series={[{ ...s.d, ko: s.ko, color: s.color }]} height={180} />
            </div>
          ))}
        </div>
        <Sub style={{ marginTop: 8, fontSize: 10.5, color: C.faint }}>원자재는 이자를 낳지 않아요 — 포트폴리오에서의 역할은 수익이 아니라 분산이에요. 과거 흐름은 미래를 보장하지 않아요.</Sub>
      </Card>

      <div className="cgrid2" style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
        <Card>
          <H num="04" main="금리가 1%p 움직이면, 내 채권은?" sub="듀레이션 체험 · 1차 근사" />
          <div style={{ marginTop: 12 }}><DurationPlay baseY={baseY} /></div>
          <MyBox>포트폴리오의 채권 ETF를 고를 때 첫 질문이 듀레이션이에요. 30년물은 안전자산이 아니라 금리 방향에 크게 베팅하는 상품이에요.</MyBox>
        </Card>
      </div>

      <div style={{ fontSize: 10.5, color: C.faint, textAlign: "center", lineHeight: 1.7, padding: "6px 0 20px" }}>
        뱁새는 수익률을 약속하지 않아요. 금리와 자산의 관계를 스스로 이해하도록 돕는 교육용 도구이며,<br />투자 자문이 아니고 모든 판단과 책임은 본인에게 있습니다.<br />{CREDIT}
      </div>
    </div>
  );
}

export default function MacroApp({ lang }) {
  const [state, setState] = useState({ st: "loading" });
  const [tries, setTries] = useState(0);
  const [sub, setSub] = useState("basic");
  useEffect(() => { (async () => {
    setState({ st: "loading" });
    try {
      const r = await fetch("./macro.json", { cache: "no-store" });
      if (!r.ok) throw new Error("HTTP " + r.status);
      const d = await r.json();
      setState({ st: "ready", data: d });
    } catch (e) { setState({ st: "missing" }); }
  })(); }, [tries]);

  if (state.st === "loading") return (
    <div style={{ minHeight: "50vh", display: "flex", alignItems: "center", justifyContent: "center", fontFamily: FONT }}>
      <div style={{ textAlign: "center" }}><Bird mood="data" size={64} /><div style={{ fontSize: 12.5, color: C.sub, marginTop: 8 }}>금리 데이터를 불러오는 중…</div></div>
    </div>
  );
  if (state.st === "missing") return (
    <div style={{ maxWidth: 560, margin: "0 auto", padding: "44px 16px", textAlign: "center", fontFamily: FONT, color: C.ink }}>
      <Bird mood="search" size={80} />
      <div style={{ fontSize: 19, fontWeight: 800, marginTop: 14 }}>금리·원자재 데이터가 아직 없어요</div>
      <Card style={{ marginTop: 16, textAlign: "left" }}>
        <Sub>GitHub 저장소 → <b style={{ color: C.ink }}>Actions</b> → <b style={{ color: C.ink }}>시세 데이터 갱신</b> → <b style={{ color: C.ink }}>Run workflow</b> 실행 후 새로고침하면 macro.json이 만들어져요.</Sub>
      </Card>
      <button onClick={() => setTries(tries + 1)} style={{ marginTop: 14, background: C.blue, color: "#fff", border: "none", borderRadius: RAD.btn, padding: "12px 22px", fontSize: 13.5, fontWeight: 800, cursor: "pointer", fontFamily: FONT }}>다시 확인</button>
    </div>
  );

  return (
    <div className="cwrap" style={{ maxWidth: 1140, margin: "0 auto", padding: "14px 16px 40px", fontFamily: FONT, color: C.ink }}>
      <style>{`@media (max-width: 880px) { .cgrid2 { grid-template-columns: 1fr !important } .cgrid3m { grid-template-columns: 1fr !important } }
        .cwrap svg, .cwrap svg text { user-select: none; -webkit-user-select: none; }
        @media (max-width: 880px) { .bchip { padding: 8px 14px !important; font-size: 12.5px !important } input[type="range"] { height: 30px } }`}</style>
      {lang === "en" && (
        <div style={{ background: "#fff", border: HAIR, borderRadius: 10, padding: "10px 14px", marginBottom: 10, fontSize: 12, color: C.sub, lineHeight: 1.6 }}>
          This section is <b style={{ color: C.ink }}>Korean-only for now</b> — it reads Korean corporate filings and market data. The <b style={{ color: C.ink }}>Portfolio</b> tab is fully bilingual.
        </div>
      )}
      <div style={{ display: "flex", alignItems: "center", marginBottom: 10, gap: 6 }}>
        {[["basic", "기본"], ["deep", "심화 — 채권·환율 연구실"]].map(([k, ko]) => (
          <button key={k} className="bchip" onClick={() => setSub(k)}
            style={{ border: "1.5px solid " + (sub === k ? C.ink : C.line), background: sub === k ? C.ink : "#fff", color: sub === k ? "#fff" : C.sub, borderRadius: 999, padding: "6px 13px", fontSize: 11.5, fontWeight: 800, cursor: "pointer", fontFamily: FONT }}>{ko}</button>
        ))}
        <span style={{ fontSize: 10.5, color: C.faint, marginLeft: "auto" }}>기준 {state.data.asOf} · 매일 자동 갱신</span>
      </div>
      {sub === "basic" ? <MacroBody data={state.data} /> : <DeepBody data={state.data} />}
    </div>
  );
}
