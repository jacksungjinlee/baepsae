Fable r1 #186 (3494ee2): 2 BLOCKERS, 4 should-fix.
B1 splitsKr free text (fail/out/err) → gate word row (validate_data.py:4113 nan·None·null·undefined) FAIL: DART JSON no status → "상태 None"; exception "KeyError: None"/"float NaN"; out cached as permanent no → fails every publish. Fix: fixed reason codes in data.json, details log only; whole-gate test.
B2 list receipt wrong ratio (= Opus B1): 800/900 count as gone; kr_split_snap 2% accepts 100% of ratios; 057680 2026-04-30 5:1 auction base → 3/16 → ×0.1875 published. Fix: 014 only + price & shares same whole n/1/n within 1%, or Samsung in SPLIT_OVERRIDES and drop path.
S1 차등감자 (= Opus S3): cr_mth per-share ratio; refuse 차등/최대주주/소각.
S2 exact share path first (= Opus S1): 46 seed lines; HMM 7:1 → 3/22 left out.
S3 new events behind backfill and LOST (KRX list window 19 days, waiting not saved, Daum once): new small-cap first asked run 23; 타임X AI 2:1 2026-11-20 live example. Fix: list/Daum candidates before seed; carry unasked in splitsKr.
S4 app: merges + non-whole (코미코 5:2) leave fractions rounded/unsellable no line; records with today's count + old date doubled (only 기록 sheet says).
Nits: Daum no overall deadline (~31 min); comment ±5% vs 10%; 48 vs 49; ETFs/no DART code only in out (RUNBOOK limits); I001 >2 pages fails forever; dry run won't exercise DART path; no tests pin B1/B2/S1-S3.
Sound: dates/ratios vs Naver/Daum (삼성, 시큐브 5:1, 알파칩스, 아시아나, 코미코 5:2, 티비씨 5:1, 타임X AI 2:1); doc path blocks spin-offs/KONEX moves/무상증자/rights; no double rows; gate rows unchanged; budget; KST; no NaN; late rule; US identical; 231 tests.
