// ================= 뱁새 v14 — 정보 =================
// 뱁새 소개, 데이터 출처, 피드백, 약관·개인정보처리방침 골격.
import React, { useState } from "react";
import { C, FONT, SERIF, RAD, HAIR } from "./tokens.js";
import { Seal } from "./icons.jsx";
import { Bird } from "./detail.jsx";

// 탤리(tally.so)에서 폼을 만든 뒤 이 주소를 교체하세요. 비어 있으면 이메일 안내가 대신 나와요.
const TALLY_URL = "https://tally.so/embed/GxEGKL?alignLeft=1&hideTitle=0&transparentBackground=1";
// 지원 이메일. 비워두면 "준비 중"으로 표시돼요.
const SUPPORT_EMAIL = "SUPPORT_EMAIL_HERE";

const CREDIT = "이성진, INSEAD MBA 26J · Jack (Sung Jin) Lee, INSEAD MBA 26J";

const Card = ({ children, style = {} }) => (
  <div style={{ background: "#fff", border: HAIR, borderRadius: RAD.card, padding: 18, ...style }}>{children}</div>
);
const H = ({ main, sub }) => (
  <div>
    <span style={{ fontSize: 15.5, fontWeight: 800, color: C.ink }}>{main}</span>
    {sub && <div style={{ fontSize: 10.5, color: C.faint, marginTop: 3 }}>{sub}</div>}
  </div>
);
const Sub = ({ children, style = {} }) => <div style={{ fontSize: 12.5, color: C.sub, lineHeight: 1.75, ...style }}>{children}</div>;

function Fold({ title, children }) {
  const [open, setOpen] = useState(false);
  return (
    <div style={{ borderBottom: "1px solid " + C.line }}>
      <button onClick={() => setOpen(!open)} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", width: "100%", background: "none", border: "none", padding: "13px 2px", cursor: "pointer", fontFamily: FONT }}>
        <span style={{ fontSize: 13, fontWeight: 800, color: C.ink }}>{title}</span>
        <span style={{ fontSize: 13, color: C.faint }}>{open ? "−" : "+"}</span>
      </button>
      {open && <div style={{ padding: "0 2px 14px" }}>{children}</div>}
    </div>
  );
}

export default function InfoApp() {
  const hasTally = TALLY_URL.startsWith("http");
  const hasMail = SUPPORT_EMAIL.includes("@");
  return (
    <div style={{ maxWidth: 760, margin: "0 auto", padding: "20px 16px 40px", fontFamily: FONT, color: C.ink }}>
      <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>

        <Card style={{ textAlign: "center", padding: "28px 18px" }}>
          <div style={{ display: "flex", justifyContent: "center", alignItems: "center", gap: 14 }}><Bird mood="care" size={84} /><Seal size={44} /></div>
          <div style={{ fontSize: 21, fontWeight: 900, marginTop: 12 }}>뱁새</div>
          <div style={{ fontFamily: SERIF, fontSize: 13.5, color: C.apricotDeep, marginTop: 5 }}>황새 말고, 내 걸음으로</div>
          <Sub style={{ marginTop: 14, textAlign: "left" }}>
            뱁새는 한국 개인 투자자를 위한 <b style={{ color: C.ink }}>교육용 투자 연구 도구</b>예요.
            내 위험 그릇에 맞는 포트폴리오를 설계하고, 기업의 숫자를 업종의 분포 속에서 읽고, 공시와 금리의 맥락을 이해하도록 돕습니다.
            <br /><br />
            뱁새가 하지 않는 것도 분명해요 — <b style={{ color: C.ink }}>종목 추천, 적정주가 제시, 수익률 약속</b>은 하지 않아요.
            시장의 단기 흐름은 실적보다 테마와 수급이 이끄는 날이 많고, 뱁새의 숫자들은 "오를 종목"이 아니라
            "지금 가격에 담긴 가정"을 읽기 위한 것이에요. 모든 판단과 책임은 사용자 본인에게 있습니다.
          </Sub>
        </Card>

        <Card>
          <H main="데이터 출처와 갱신" sub="모든 데이터는 공개 출처에서 매일 자동 수집돼요" />
          <div style={{ marginTop: 10 }}>
            {[
              ["금융감독원 DART", "재무제표 3개년 · 배당 · 내부자 거래 · 국민연금 대량보유 (전자공시 OPEN API)"],
              ["FinanceDataReader", "국내외 주가 · 상장 정보 · 환율 · 채권 ETF 시세"],
              ["한국은행 ECOS", "국고채 만기별 금리 (수익률 곡선 · 장단기 금리차)"],
              ["FRED (미국 연준)", "미국 국채 금리 · WTI 유가"],
            ].map(([k, v]) => (
              <div key={k} style={{ display: "flex", gap: 12, padding: "8px 0", borderBottom: "1px solid " + C.line }}>
                <span style={{ width: 150, flexShrink: 0, fontSize: 12, fontWeight: 800, color: C.ink }}>{k}</span>
                <span style={{ fontSize: 11.5, color: C.sub, lineHeight: 1.6 }}>{v}</span>
              </div>
            ))}
          </div>
          <Sub style={{ marginTop: 10, fontSize: 10.5, color: C.faint }}>
            매일 새벽 자동 갱신돼요. PER·PBR 등 투자지표는 직전 사업보고서 기준 자체 계산이라 실시간 집계값과 소폭 다를 수 있어요.
            데이터의 정확성·완전성은 보장되지 않으며, 주문 전에는 반드시 증권사 시세를 확인하세요.
          </Sub>
        </Card>

        <Card>
          <H main="피드백" sub="쓰다가 이상한 것, 바라는 것, 뭐든 좋아요" />
          <div style={{ marginTop: 12 }}>
            {hasTally ? (
              <iframe src={TALLY_URL} title="피드백" style={{ width: "100%", height: 420, border: "none", borderRadius: 8, background: C.bg }} />
            ) : (
              <Sub>
                피드백 폼을 준비하고 있어요.
                {hasMail ? <> 그동안은 <a href={"mailto:" + SUPPORT_EMAIL} style={{ color: C.blue, fontWeight: 800 }}>{SUPPORT_EMAIL}</a> 로 보내주세요.</> : " 곧 이 자리에 열릴 거예요."}
              </Sub>
            )}
          </div>
        </Card>

        <Card>
          <H main="문의 및 약관" />
          <div style={{ marginTop: 6 }}>
            <Fold title="기술 문의 · 오류 제보">
              <Sub>{hasMail ? <>이메일: <a href={"mailto:" + SUPPORT_EMAIL} style={{ color: C.blue, fontWeight: 800 }}>{SUPPORT_EMAIL}</a></> : "문의 이메일을 준비 중이에요."}</Sub>
            </Fold>
            <Fold title="이용약관 (초안)">
              <Sub>
                제1조 (목적) 이 약관은 뱁새(이하 "서비스")의 이용 조건을 정합니다.<br />
                제2조 (서비스의 성격) 서비스는 교육·정보 제공 목적의 도구이며, 자본시장법상 투자자문업·투자일임업에 해당하는 서비스를 제공하지 않습니다. 서비스가 제공하는 모든 수치·분석·시각화는 투자 판단의 참고 자료일 뿐이며, 투자 권유가 아닙니다.<br />
                제3조 (책임의 한계) 데이터의 정확성·적시성은 보장되지 않으며, 서비스 이용에 따른 투자 결과의 책임은 이용자 본인에게 있습니다.<br />
                <span style={{ color: C.faint }}>— 정식 서비스 전 법률 검토를 거쳐 확정됩니다.</span>
              </Sub>
            </Fold>
            <Fold title="개인정보처리방침 (초안)">
              <Sub>
                뱁새는 회원가입 없이 이용할 수 있으며, 서버에 개인정보를 수집·저장하지 않습니다.
                포트폴리오 등 모든 데이터는 이용자의 브라우저(로컬 저장소)에만 저장됩니다.
                방문 통계는 쿠키를 사용하지 않는 익명 집계 방식(GoatCounter)을 사용합니다.
                피드백 폼 제출 시 입력한 내용은 폼 서비스 제공자(Tally)에 저장됩니다.<br />
                <span style={{ color: C.faint }}>— 정식 서비스 전 법률 검토를 거쳐 확정됩니다.</span>
              </Sub>
            </Fold>
            <Fold title="사업자 정보">
              <Sub style={{ color: C.faint }}>상호·대표자·사업자등록번호·통신판매업 신고번호는 정식 서비스 개시 시 이 자리에 게시됩니다.</Sub>
            </Fold>
          </div>
        </Card>

        <div style={{ fontSize: 10.5, color: C.faint, textAlign: "center", lineHeight: 1.7, padding: "6px 0 20px" }}>
          만든 사람 — {CREDIT}
        </div>
      </div>
    </div>
  );
}
