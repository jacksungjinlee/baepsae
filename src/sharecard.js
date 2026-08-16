// ================= 뱁새 v13 — 포트폴리오 공유 카드 =================
// 카톡·인스타에서 3초 안에 읽히는 자랑 카드. 점수 + 배분 도넛 + 담은 종목 TOP 3.
import { C } from "./tokens.js";

const SERIF_CV = "'Noto Serif KR', serif";
const FONT_CV = "'Pretendard Variable', Pretendard, 'Apple SD Gothic Neo', sans-serif";

export function renderPortfolioCard({ score, buckets, top, dateStr }) {
  const W = 1080, H = 1350;
  const cv = document.createElement("canvas");
  cv.width = W; cv.height = H;
  const g = cv.getContext("2d");

  // 배경 — 잉크 네이비 그라데이션
  const gr = g.createLinearGradient(0, 0, W, H);
  gr.addColorStop(0, "#2C4C7C"); gr.addColorStop(0.55, "#1B2B4B"); gr.addColorStop(1, "#12203A");
  g.fillStyle = gr; g.fillRect(0, 0, W, H);

  // 뱁 도장 (좌상단)
  g.save();
  g.translate(110, 118); g.rotate(-7 * Math.PI / 180);
  g.strokeStyle = C.apricotDeep; g.globalAlpha = 0.95;
  g.lineWidth = 6; g.beginPath(); g.arc(0, 0, 46, 0, Math.PI * 2); g.stroke();
  g.lineWidth = 2; g.globalAlpha = 0.55; g.beginPath(); g.arc(0, 0, 38, 0, Math.PI * 2); g.stroke();
  g.globalAlpha = 0.95; g.fillStyle = C.apricotDeep;
  g.font = "900 46px " + SERIF_CV; g.textAlign = "center"; g.textBaseline = "middle";
  g.fillText("뱁", 0, 3);
  g.restore();

  // 헤더
  g.fillStyle = "#fff"; g.textAlign = "left"; g.textBaseline = "alphabetic";
  g.font = "800 44px " + FONT_CV;
  g.fillText("내 포트폴리오", 190, 112);
  g.font = "500 24px " + FONT_CV; g.globalAlpha = 0.65;
  g.fillText(dateStr + " · 뱁새에서 만듦", 190, 150);
  g.globalAlpha = 1;

  // 건강 점수 (우측 큰 숫자)
  g.textAlign = "right";
  g.font = "900 190px " + FONT_CV;
  g.fillText(String(score), W - 100, 400);
  g.font = "700 30px " + FONT_CV; g.globalAlpha = 0.7;
  g.fillText("포트폴리오 건강 점수 / 100", W - 100, 448);
  g.globalAlpha = 1;

  // 배분 도넛 (좌측)
  const cx = 300, cy = 350, R = 150, LW = 62;
  let a0 = -Math.PI / 2;
  const totPct = buckets.reduce((s, b) => s + b.pct, 0) || 1;
  buckets.forEach((b) => {
    const a1 = a0 + (b.pct / totPct) * Math.PI * 2;
    g.strokeStyle = b.color; g.lineWidth = LW;
    g.beginPath(); g.arc(cx, cy, R, a0 + 0.015, a1 - 0.015); g.stroke();
    a0 = a1;
  });

  // 범례
  g.textAlign = "left";
  let ly = 560;
  buckets.forEach((b) => {
    g.fillStyle = b.color;
    g.beginPath(); g.arc(120, ly - 9, 11, 0, Math.PI * 2); g.fill();
    g.fillStyle = "#fff"; g.font = "700 28px " + FONT_CV;
    g.fillText(b.ko, 148, ly);
    g.font = "800 28px " + FONT_CV; g.textAlign = "right";
    g.fillText(b.pct.toFixed(0) + "%", 480, ly);
    g.textAlign = "left";
    ly += 52;
  });

  // 구분선
  g.strokeStyle = "rgba(255,255,255,0.22)"; g.lineWidth = 2;
  g.beginPath(); g.moveTo(100, 810); g.lineTo(W - 100, 810); g.stroke();

  // 담은 종목 TOP
  g.fillStyle = "#fff"; g.font = "800 30px " + FONT_CV; g.globalAlpha = 0.75;
  g.fillText("담은 종목 TOP " + top.length, 100, 878);
  g.globalAlpha = 1;
  let ty = 946;
  top.forEach((h, i) => {
    g.fillStyle = C.apricot; g.font = "900 34px " + FONT_CV;
    g.fillText(String(i + 1), 100, ty);
    g.fillStyle = "#fff"; g.font = "700 36px " + FONT_CV;
    const nm = h.nk.length > 14 ? h.nk.slice(0, 13) + "…" : h.nk;
    g.fillText(nm, 156, ty);
    g.font = "800 36px " + FONT_CV; g.textAlign = "right";
    g.fillText(h.pct.toFixed(0) + "%", W - 100, ty);
    g.textAlign = "left";
    ty += 66;
  });

  // 태그라인 + 푸터
  g.fillStyle = C.apricot; g.font = "700 34px " + SERIF_CV;
  g.fillText("황새 말고, 내 걸음으로", 100, H - 150);
  g.fillStyle = "#fff"; g.globalAlpha = 0.55; g.font = "500 22px " + FONT_CV;
  g.fillText("pewpewmfer.github.io/baepsae · 교육용 도구 · 투자 자문 아님", 100, H - 104);
  g.fillText("이성진 · Jack (Sung Jin) Lee, INSEAD MBA 26J", 100, H - 68);
  g.globalAlpha = 1;

  return cv;
}

export function saveCard(cv, dateStr) {
  cv.toBlob((b) => {
    if (!b) return;
    const a = document.createElement("a");
    a.href = URL.createObjectURL(b);
    a.download = `baepsae-portfolio-${dateStr}.png`;
    a.click();
    setTimeout(() => URL.revokeObjectURL(a.href), 4000);
  }, "image/png");
}

export function shareCard(cv, dateStr) {
  return new Promise((res) => {
    cv.toBlob(async (b) => {
      if (!b) return res(false);
      const file = new File([b], `baepsae-portfolio-${dateStr}.png`, { type: "image/png" });
      if (navigator.share && navigator.canShare && navigator.canShare({ files: [file] })) {
        try { await navigator.share({ files: [file], url: "https://pewpewmfer.github.io/baepsae/" }); return res(true); } catch (e) { return res(false); }
      }
      res(false);
    }, "image/png");
  });
}

export function downloadPortfolioCard(opts) {
  saveCard(renderPortfolioCard(opts), opts.dateStr);
}
