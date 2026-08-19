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


const GLOSSARY = [["PER", "주가를 주당순이익으로 나눈 값. 이익 1원에 시장이 몇 원을 쳐주는지예요. 업종끼리 비교해야 뜻이 있어요."], ["PBR", "주가를 주당순자산으로 나눈 값. 1배면 장부상 자산 가치만큼 거래된다는 뜻이에요."], ["PSR", "시가총액을 매출로 나눈 값. 아직 이익이 없는 성장 기업을 비교할 때 써요."], ["EV/EBITDA", "빚까지 포함한 기업의 몸값(EV)을 감가상각 전 영업이익으로 나눈 값. 빚이 다른 회사끼리 비교할 때 공정해요."], ["P/OCF", "주가를 주당 영업현금흐름으로 나눈 값. 회계 이익보다 속이기 어려운 잣대예요."], ["EPS", "주당순이익. 회사가 1주당 벌어들인 이익이에요."], ["ROE", "자본 대비 순이익. 주주 돈 100원으로 1년에 몇 원을 벌었는지예요."], ["배당수익률", "1주당 배당금을 주가로 나눈 값. 예금 이자처럼 읽히지만, 배당은 약속이 아니에요."], ["TTM", "최근 4개 분기 합산. 연간 보고서보다 최신 상태를 보여줘요. 뱁새 투자지표의 기본이에요."], ["베타", "시장이 1% 움직일 때 이 주식이 평균 몇 % 움직였는지. 1보다 크면 시장보다 크게 출렁여요."], ["변동성", "수익률이 얼마나 넓게 출렁이는지의 통계값(연간 표준편차). 클수록 오르내림이 커요."], ["샤프지수", "감수한 변동성 1단위당 얼마의 초과수익을 얻었는지. 과거 성적의 효율이에요."], ["최대낙폭(MDD)", "고점에서 저점까지 가장 크게 빠졌던 폭. 버틸 수 있는 크기인지가 질문이에요."], ["상관관계", "두 자산이 같이 움직이는 정도(−1~+1). 낮을수록 섞었을 때 분산 효과가 커요."], ["팩터", "주식을 성향으로 나눠 보는 틀. 가치·퀄리티·모멘텀·규모·저변동. 자세한 건 조건 검색의 ? 를 보세요."], ["멀티플", "PER·PBR처럼 이익이나 자산에 곱해지는 배수. '시장의 눈높이'라고도 불러요."], ["DCF", "미래 현금흐름을 현재 가치로 할인해 더하는 가치평가법. 가정에 따라 값이 크게 변해요."], ["리버스 DCF", "지금 주가가 성립하려면 어떤 성장이 필요한지 거꾸로 푸는 방법. 뱁새가 쓰는 방식이에요."], ["듀레이션", "금리가 1%p 움직일 때 채권값이 대략 몇 % 움직이는지. 만기가 길수록 커요."], ["수익률 곡선", "만기별 국채 금리를 이은 선. 기울기가 경기 전망을 담을 때가 많아요."], ["장단기 금리차", "장기금리 − 단기금리. 마이너스로 뒤집히는 역전은 역사적으로 둔화에 앞선 일이 많았어요."], ["신용 스프레드", "회사채와 국고채의 금리 차이. 시장이 매기는 부도 걱정의 가격이에요."], ["환헤지", "환율 변동을 계약으로 막는 것. 공짜가 아니라 두 나라 금리 차이만큼 비용이 들어요."], ["유동비율", "유동자산 ÷ 유동부채. 1년 안에 갚을 돈을 감당할 수 있는지예요."], ["이자보상배율", "영업이익 ÷ 이자비용. 1 아래면 번 돈으로 이자도 못 갚는다는 뜻이에요."], ["자본잠식", "자본총계가 자본금보다 작아진 상태. 누적 손실이 밑천을 갉아먹은 거예요."], ["수주잔고", "받아놓고 아직 못 만든 일감. 조선·방산처럼 만드는 데 오래 걸리는 업의 미래 매출이에요."], ["NIM", "은행의 순이자마진. 대출금리와 조달금리의 차이로, 은행 수익성의 몸이에요."], ["시가총액", "주가 × 상장주식수. 시장이 매기는 회사 전체의 값이에요."], ["알파", "시장 대비 초과수익. 뱁새에선 과거 기록으로만 보여드리고, 미래를 약속하지 않아요."], ["공매도", "주식을 빌려서 판 뒤 나중에 사서 갚는 것. 주가 하락에 거는 방법이라 뉴스에 자주 나와요."], ["유상증자", "회사가 새 주식을 팔아 돈을 모으는 것. 주식 수가 늘어 내 지분 가치가 희석돼요."], ["무상증자", "이익잉여금을 자본금으로 옮기며 주식을 공짜로 나눠주는 것. 회사 가치는 그대로예요."], ["감자", "자본금을 줄이는 것. 보통 누적 손실을 지우려는 신호라 주의 깊게 봐야 해요."], ["액면분할", "한 주를 여러 주로 쪼개는 것. 값이 싸 보일 뿐 가치는 같아요."], ["자사주 매입·소각", "회사가 자기 주식을 사서 없애는 것. 주식 수가 줄어 주당 가치가 올라가는 주주환원이에요."], ["배당기준일·배당락", "배당 받을 권리가 정해지는 날과, 그 권리가 떨어져 주가가 조정되는 날이에요."], ["배당성향", "순이익 중 배당으로 주는 비율. 너무 높으면 이익이 줄 때 배당도 위태로워요."], ["컨센서스", "증권사 전망치의 평균. 실적이 이보다 좋으면 서프라이즈, 나쁘면 쇼크라고 불러요."], ["잠정실적", "확정 전 미리 발표하는 분기 숫자. 시장은 보통 이때 먼저 반응해요."], ["가이던스", "회사가 스스로 내놓는 실적 전망. 약속이 아니라 목표예요."], ["공모주(IPO)", "처음 상장하며 파는 주식. 청약 경쟁률과 보호예수 물량을 같이 봐야 해요."], ["보호예수(락업)", "대주주 등이 일정 기간 팔지 못하게 묶인 물량. 풀리는 날 매물 부담이 생길 수 있어요."], ["오버행", "언제든 시장에 나올 수 있는 잠재 매물. 전환사채·보호예수 해제 물량이 대표적이에요."], ["전환사채(CB)", "나중에 주식으로 바꿀 수 있는 채권. 전환되면 주식 수가 늘어 희석이 생겨요."], ["블록딜", "큰 물량을 장 밖에서 한 번에 넘기는 거래. 보통 시가보다 할인돼 다음 날 주가를 눌러요."], ["물적분할·인적분할", "사업을 떼어내는 두 방식. 물적분할 뒤 자회사 상장은 모회사 주주에게 불리할 수 있어 논쟁이 많아요."], ["지주회사 할인", "지주회사가 자회사 가치 합보다 싸게 거래되는 현상. 한국 시장에서 특히 커요."], ["관리종목·상장폐지", "거래소가 문제 있는 회사에 붙이는 경고와 퇴출. 재무 신호가 먼저 알려줄 때가 많아요."], ["감사의견", "회계법인이 재무제표에 주는 판정. '적정'이 아니면 큰 경고예요."], ["코스피·코스닥", "한국의 두 시장. 코스피는 대형·전통, 코스닥은 중소·기술 성향이에요."], ["ETF", "지수나 자산 묶음을 통째로 사는 상장 펀드. 뱁새의 금·채권 블록이 모두 ETF예요."], ["레버리지·인버스 ETF", "지수의 2배로, 또는 반대로 움직이게 설계된 ETF. 오래 들고 있으면 복리 손실이 쌓여 장기 투자엔 맞지 않아요."], ["괴리율·NAV", "ETF 시장가와 실제 자산가치(NAV)의 차이. 괴리가 크면 비싸게 사는 거예요."], ["분배금", "ETF가 주는 배당. 주식 배당과 달리 15.4% 세금이 원천징수돼요."], ["ISA·연금저축·IRP", "세금을 아껴주는 계좌들. 뱁새 세금 층이 계좌별 차이를 계산해줘요."], ["신용융자·반대매매", "증권사 돈을 빌려 사는 것과, 담보가 부족해지면 강제로 팔리는 것. 하락장을 더 가파르게 만들어요."], ["미수거래", "결제일까지 돈을 안 내고 사는 초단기 외상. 이틀 뒤 갚지 못하면 반대매매돼요."], ["시간외거래·동시호가", "정규장 밖의 거래와, 장 시작·마감 때 주문을 모아 한 번에 체결하는 방식이에요."], ["상한가·하한가", "하루 ±30%로 묶인 가격 제한. 붙으면 거래 자체가 어려워져요."], ["VI(변동성완화장치)", "주가가 급변하면 2분간 단일가로 바꾸는 브레이크. 과열 신호로 읽혀요."], ["거래량·거래대금", "얼마나 활발히 거래됐는지. 가격 움직임에 거래량이 없으면 신뢰가 낮아요."], ["호가", "사고팔려는 주문 가격의 사다리. 호가가 얇으면 조금만 사도 가격이 밀려요."], ["평단가", "내가 산 평균 가격. 뱁새는 평단가보다 '지금 비중이 맞는가'를 먼저 물어요."], ["물타기", "떨어질 때 더 사서 평단가를 낮추는 것. 계획된 분할매수와 달리, 근거 없이 하면 손실만 커져요."], ["분할매수(적립식)", "시점을 나눠 사는 것. 타이밍 실수를 평균으로 지우는 방법이에요."], ["리밸런싱", "자산 비중이 목표에서 벗어나면 되돌리는 것. 오른 걸 팔고 빠진 걸 사게 되는 규칙이에요."], ["손절·익절", "손실이나 이익을 확정하고 파는 것. 기준 없이 감으로 하면 규칙이 아니라 감정이에요."], ["어닝 시즌", "분기 실적이 몰려 발표되는 기간. 컨센서스와의 차이가 주가를 흔들어요."], ["서킷브레이커", "시장 전체가 급락하면 거래를 멈추는 장치. 발동 자체가 역사적 사건이에요."]];
function GlossaryList() {
  const [q, setQ] = useState("");
  const rows = GLOSSARY.filter(([k, v]) => !q || k.toLowerCase().includes(q.toLowerCase()) || v.includes(q));
  return (
    <div style={{ marginTop: 10 }}>
      <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="찾는 말이 있나요?"
        style={{ width: "100%", boxSizing: "border-box", border: "1.5px solid " + C.line, borderRadius: 10, padding: "10px 12px", fontSize: 13, fontFamily: FONT, color: C.ink, background: "#fff" }} />
      <div style={{ marginTop: 8, maxHeight: 340, overflowY: "auto" }}>
        {rows.map(([k, v]) => (
          <div key={k} style={{ padding: "9px 2px", borderBottom: "1px solid " + C.line }}>
            <span style={{ fontSize: 12.5, fontWeight: 800, color: C.ink }}>{k}</span>
            <span style={{ fontSize: 12, color: C.sub, lineHeight: 1.65, marginLeft: 8 }}>{v}</span>
          </div>
        ))}
        {rows.length === 0 && <div style={{ fontSize: 12, color: C.faint, padding: "14px 2px" }}>아직 없는 말이에요. 피드백으로 알려주시면 더해둘게요.</div>}
      </div>
    </div>
  );
}

export default function InfoApp({ lang }) {
  const en = lang === "en";
  const hasTally = TALLY_URL.startsWith("http");
  const hasMail = SUPPORT_EMAIL.includes("@");
  return (
    <div style={{ maxWidth: 760, margin: "0 auto", padding: "20px 16px 40px", fontFamily: FONT, color: C.ink }}>
      <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>

        <Card style={{ textAlign: "center", padding: "28px 18px" }}>
          <div style={{ display: "flex", justifyContent: "center", alignItems: "center", gap: 14 }}><Bird mood="care" size={84} /><Seal size={44} /></div>
          <div style={{ fontSize: 21, fontWeight: 900, marginTop: 12 }}>뱁새</div>
          <div style={{ fontFamily: SERIF, fontSize: 13.5, color: C.apricotDeep, marginTop: 5 }}>황새 말고, 내 걸음으로</div>
          {en && (
            <Sub style={{ marginTop: 14, textAlign: "left" }}>
              <b style={{ color: C.ink }}>Baepsae</b> ("crow-tit", from a Korean proverb about keeping your own pace) is an <b style={{ color: C.ink }}>educational research studio for Korean retail investors</b> — risk-fit portfolio construction with a block-correlation engine, company analysis grounded in industry distributions, insider-filing and pension-fund tracking, and rates·bond education. It deliberately does <b style={{ color: C.ink }}>not</b> recommend stocks, publish target prices, or promise returns: every number is framed as "the assumption embedded in today's price," not a forecast. Built solo — data pipeline (DART·KRX·ECOS·FRED), analytics engine and design — by Jack (Sung Jin) Lee, INSEAD MBA 26J. The interface below is in Korean; the Portfolio tab is fully bilingual.
            </Sub>
          )}
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
          <H main="용어 사전" sub="뱁새에 나오는 말들, 한 줄씩" />
          <GlossaryList />
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
