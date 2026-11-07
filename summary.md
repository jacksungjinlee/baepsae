# logo.dev logos (v19.3a)

Run 2026-11-06 20:33 – 2026-11-06 21:33 KST · data.json prices 2026-11-05 (US 2026-11-05) · logo files: WEBP 128 × 128

**Finished: every company was looked up.**

Companies finished: **3,151 of 3,151**

## Coverage

Shares are of the companies finished in that market.

| Market | Companies | Finished | Logo by ticker | Logo by DART homepage | Letter mark |
|---|---:|---:|---:|---:|---:|
| Korea (common shares) | 2,411 | 2,411 | 709 (29.4%) | 755 (31.3%) | 947 (39.3%) |
| US | 740 | 740 | 699 (94.5%) | 0 (0.0%) | 41 (5.5%) |

Korean preferred shares: 59, of which 51 reuse their issuer's logo (no lookup of their own); the rest show the letter mark.

Letter marks by reason: Korea (common shares): blank 1, download_failed 1, faint 1, no_image 304, not_found 143, not_indexed 69, shared 21, small 407; US: download_failed 1, not_found 25, not_indexed 2, odd_answer 1, small 12.

## Korea: ticker against the DART homepage

The logo lookup returns brand_id, not a brand domain, so the homepage lookup checks the ticker's brand.

- same brand by ticker and homepage (ticker logo kept): **650**
- the homepage reached another brand with a logo (homepage logo used instead): **42**
- ticker logo kept, unverified: **59** — homepage: no_image 16, homepage: not_found 10, homepage: not_indexed 3, no usable DART homepage domain 30
- no ticker logo, homepage logo used: **713**

## Automatic quality checks

Counted on the chosen picture (dropped → letter mark), plus companies whose final logo is shared:

- small: **419**
- blank: **90**
- faint: **83**
- one_colour: **0**
- shared: **21**
- file_clash: **0**
- odd_code: **0**
- monogram-looking, kept and flagged (never dropped): **181**
- size-less vectors (no size in the answer; judged on the downloaded picture), kept and flagged: **0**
- odd answers from logo.dev (letter mark, reason odd_answer): **1** (the run stops above 30)
- shared pictures: **43** groups, 104 companies: **21** companies of different or unknown brands switched to letter marks (in 13 groups), **24** kept because their own homepage confirmed them (same-brand); groups of one brand kept

Every dropped picture is in dropped/ (never published); `--keep CODES --dir DIR` restores one after review. Restored after review: 009830, 009835, 052710, 094840, 236200, 016790.

Quality checks (a failing logo gets the letter mark): **small** — a raster source whose shorter side is under 64 px (logo.dev's width and height); **blank** — under 1% of the 128 px picture is visible (alpha 32 or more); **faint** — near-invisible on white, which is how the app shows logos: laid on white, under 1.5% of the pixels are more than 40 levels (of 255) away from white in any channel, so a white or very light logo on transparency is dropped; **one_colour** — the picture laid on white and laid on black is, both times, at least 98.5% one colour (colours rounded to 32 levels a channel), such as a flat coloured square; **monogram-looking** (a flag, never a drop: on real data it caught only real logos) — an opaque square (75% or more of the picture fully opaque) of two flat colours (background 55% or more, a far colour 4–40%, at most 6% of other colours besides the blend between them) whose far colour forms one or two blobs centred within 12% of the middle, 25–75% of the height and 10–75% of the width. The logo is kept and drawn on the review sheet. **shared** — the same picture for companies whose logo.dev brand_id differs or is missing (a generic picture, or a group logo under different brands): the same 64-bit difference hash and 16 x 16 colour thumbnails at most 6 levels apart on average; only checked pairs form a group. In such a group every company gets the letter mark except one whose own homepage confirmed its ticker logo (same-brand); a group whose companies all have one real brand_id is kept. Every shared group is on the review sheet; --keep restores a checked one. **file_clash** — two codes would share one file name; **odd_code** — a code that is not a plain stock code (both never expected).

## Credits and requests

- Credits counted: **5,282** of the 14,000 cap ($52.82) — 2 for each of 2,637 answers marked Credits-Charged: 1, 0 billable answers without the header, and 4 requests that got no answer. 6,601 answers were free (Credits-Charged: 0).
- Balance logo.dev reported (Credits-Remaining), first → last answer: 14830 → 9562.
- Ceiling before the run (every lookup billed): 10,942 credits for 5,471 lookups (3,151 by ticker, 2,320 by DART homepage).
- API lookups sent: **9,242** (retries after 202: 3,767 · after 429: 0 · after an error: 4) · downloads: 2,650 (not billed, not CDN requests) · failed downloads of a chosen logo: 2.
- Pace: at most 200 lookups a minute, 4 open at once, downloads at most 300 a minute · run time 59.9 min.

## Review sheet

sheet.html and sheet-01.png, sheet-02.png, sheet-03.png, sheet-04.png, sheet-05.png, sheet-06.png, sheet-07.png, sheet-08.png, sheet-09.png, sheet-10.png, sheet-11.png, sheet-12.png, sheet-13.png, sheet-14.png, sheet-15.png, sheet-16.png, sheet-17.png, sheet-18.png, sheet-19.png, sheet-20.png, sheet-21.png, sheet-22.png, sheet-23.png, sheet-24.png, sheet-25.png, sheet-26.png, sheet-27.png, sheet-28.png, sheet-29.png, sheet-30.png, sheet-31.png, sheet-32.png, sheet-33.png, sheet-34.png, sheet-35.png, every tile in each category, no caps (chosen logo or letter mark, with any dropped picture beside it):

- Korea: the 300 largest by market cap: **300**
- US: the 300 largest by market cap: **300**
- Korea outside the top 300: homepage logo used instead of a different ticker brand: **27**
- Korea outside the top 300: ticker logo kept, unverified by the DART homepage: **47**
- Korea outside the top 300: no ticker logo, homepage logo used: **695**
- Monogram-looking (kept): every company, any rank: **181**
- Size-less vector (kept): every company, any rank: **0**
- Odd answers from logo.dev (letter mark): every company, any rank: **1**
- Shared picture, group 1: 6 companies, 2 switched to letter marks (different brands), 4 kept (same-brand): **6**
- Shared picture, group 2: 5 companies, kept (one brand): **5**
- Shared picture, group 3: 5 companies, kept (one brand): **5**
- Shared picture, group 4: 4 companies, kept (one brand): **4**
- Shared picture, group 5: 4 companies, kept (one brand): **4**
- Shared picture, group 6: 3 companies, kept (one brand): **3**
- Shared picture, group 7: 3 companies, kept (one brand): **3**
- Shared picture, group 8: 3 companies, 2 switched to letter marks (different brands), 1 kept (same-brand): **3**
- Shared picture, group 9: 3 companies, kept (one brand): **3**
- Shared picture, group 10: 2 companies, kept (one brand): **2**
- Shared picture, group 11: 2 companies, 2 switched to letter marks (different brands): **2**
- Shared picture, group 12: 2 companies, kept (one brand): **2**
- Shared picture, group 13: 2 companies, kept (one brand): **2**
- Shared picture, group 14: 2 companies, kept (one brand): **2**
- Shared picture, group 15: 2 companies, 1 switched to letter marks (different brands), 1 kept (same-brand): **2**
- Shared picture, group 16: 2 companies, kept (one brand): **2**
- Shared picture, group 17: 2 companies, kept (one brand): **2**
- Shared picture, group 18: 2 companies, 2 switched to letter marks (different brands): **2**
- Shared picture, group 19: 2 companies, kept (one brand): **2**
- Shared picture, group 20: 2 companies, kept (one brand): **2**
- Shared picture, group 21: 2 companies, 1 switched to letter marks (different brands), 1 kept (same-brand): **2**
- Shared picture, group 22: 2 companies, kept (one brand): **2**
- Shared picture, group 23: 2 companies, kept (one brand): **2**
- Shared picture, group 24: 2 companies, kept (one brand): **2**
- Shared picture, group 25: 2 companies, kept (one brand): **2**
- Shared picture, group 26: 2 companies, 1 switched to letter marks (different brands), 1 kept (same-brand): **2**
- Shared picture, group 27: 2 companies, kept (one brand): **2**
- Shared picture, group 28: 2 companies, kept (one brand): **2**
- Shared picture, group 29: 2 companies, 1 switched to letter marks (different brands), 1 kept (same-brand): **2**
- Shared picture, group 30: 2 companies, 2 switched to letter marks (different brands): **2**
- Shared picture, group 31: 2 companies, kept (one brand): **2**
- Shared picture, group 32: 2 companies, 2 switched to letter marks (different brands): **2**
- Shared picture, group 33: 2 companies, 2 switched to letter marks (different brands): **2**
- Shared picture, group 34: 2 companies, kept (one brand): **2**
- Shared picture, group 35: 2 companies, kept (one brand): **2**
- Shared picture, group 36: 2 companies, 2 switched to letter marks (different brands): **2**
- Shared picture, group 37: 2 companies, kept (one brand): **2**
- Shared picture, group 38: 2 companies, kept (one brand): **2**
- Shared picture, group 39: 2 companies, 1 switched to letter marks (different brands), 1 kept (same-brand): **2**
- Shared picture, group 40: 2 companies, kept (one brand): **2**
- Shared picture, group 41: 2 companies, kept (one brand): **2**
- Shared picture, group 42: 2 companies, kept (one brand): **2**
- Shared picture, group 43: 2 companies, kept (one brand): **2**

## Switched to the letter mark after review

- 000040 KR모터스 — 다른 회사·호스팅 업체의 그림 (sheet review 2026-11-06)
- 000430 대원강업 — 다른 회사·호스팅 업체의 그림 (sheet review 2026-11-06)
- 003460 유화증권 — 다른 회사·호스팅 업체의 그림 (sheet review 2026-11-06)
- 003465 유화증권우 — 다른 회사·호스팅 업체의 그림 (sheet review 2026-11-06) (preferred share of an issuer above)
- 003830 대한화섬 — 다른 회사·호스팅 업체의 그림 (sheet review 2026-11-06)
- 009150 삼성전기 — 다른 회사·호스팅 업체의 그림 (sheet review 2026-11-06)
- 009155 삼성전기우 — 다른 회사·호스팅 업체의 그림 (sheet review 2026-11-06) (preferred share of an issuer above)
- 009470 삼화전기 — 다른 회사·호스팅 업체의 그림 (sheet review 2026-11-06)
- 011000 진원생명과학 — 다른 회사·호스팅 업체의 그림 (sheet review 2026-11-06)
- 011230 삼화전자 — 다른 회사·호스팅 업체의 그림 (sheet review 2026-11-06)
- 011500 한농화성 — 다른 회사·호스팅 업체의 그림 (sheet review 2026-11-06)
- 014910 성문전자 — 다른 회사·호스팅 업체의 그림 (sheet review 2026-11-06)
- 014970 삼륭물산 — 다른 회사·호스팅 업체의 그림 (sheet review 2026-11-06)
- 018290 브이티 — 다른 회사·호스팅 업체의 그림 (sheet review 2026-11-06)
- 027410 BGF — 다른 회사·호스팅 업체의 그림 (sheet review 2026-11-06)
- 034590 인천도시가스 — 다른 회사·호스팅 업체의 그림 (sheet review 2026-11-06)
- 036000 예림당 — 다른 회사·호스팅 업체의 그림 (sheet review 2026-11-06)
- 039560 다산네트웍스 — 다른 회사·호스팅 업체의 그림 (sheet review 2026-11-06)
- 042000 카페24 — 다른 회사·호스팅 업체의 그림 (sheet review 2026-11-06)
- 045660 에이텍 — 다른 회사·호스팅 업체의 그림 (sheet review 2026-11-06)
- 067990 도이치모터스 — 다른 회사·호스팅 업체의 그림 (sheet review 2026-11-06)
- 069260 TKG휴켐스 — 다른 회사·호스팅 업체의 그림 (sheet review 2026-11-06)
- 089150 케이씨티 — 다른 회사·호스팅 업체의 그림 (sheet review 2026-11-06)
- 089850 유비벨록스 — 다른 회사·호스팅 업체의 그림 (sheet review 2026-11-06)
- 090460 비에이치 — 다른 회사·호스팅 업체의 그림 (sheet review 2026-11-06)
- 108380 대양전기공업 — 다른 회사·호스팅 업체의 그림 (sheet review 2026-11-06)
- 123010 MSDI — 다른 회사·호스팅 업체의 그림 (sheet review 2026-11-06)
- 123040 엠에스오토텍 — 다른 회사·호스팅 업체의 그림 (sheet review 2026-11-06)
- 143240 사람인 — 다른 회사·호스팅 업체의 그림 (sheet review 2026-11-06)
- 168360 펨트론 — 다른 회사·호스팅 업체의 그림 (sheet review 2026-11-06)
- 191410 육일씨엔에쓰 — 다른 회사·호스팅 업체의 그림 (sheet review 2026-11-06)
- 192410 오늘이엔엠 — 다른 회사·호스팅 업체의 그림 (sheet review 2026-11-06)
- 246960 SCL사이언스 — 다른 회사·호스팅 업체의 그림 (sheet review 2026-11-06)
- 317240 TS트릴리온 — 다른 회사·호스팅 업체의 그림 (sheet review 2026-11-06)
- 435570 에르코스 — 다른 회사·호스팅 업체의 그림 (sheet review 2026-11-06)
- 452160 제이엔비 — 다른 회사·호스팅 업체의 그림 (sheet review 2026-11-06)
- ARGX argenx SE — 다른 회사·호스팅 업체의 그림 (sheet review 2026-11-06)
- MEDP Medpace Holdings, Inc. — 다른 회사·호스팅 업체의 그림 (sheet review 2026-11-06)
- 000240 한국앤컴퍼니 — 사진·배너·화면 캡처 (sheet review 2026-11-06)
- 0013V0 삼진식품 — 사진·배너·화면 캡처 (sheet review 2026-11-06)
- 002030 아세아 — 사진·배너·화면 캡처 (sheet review 2026-11-06)
- 003570 SNT다이내믹스 — 사진·배너·화면 캡처 (sheet review 2026-11-06)
- 007280 한국특강 — 사진·배너·화면 캡처 (sheet review 2026-11-06)
- 008250 이건산업 — 사진·배너·화면 캡처 (sheet review 2026-11-06)
- 011780 금호석유화학 — 사진·배너·화면 캡처 (sheet review 2026-11-06)
- 011785 금호석유화학우 — 사진·배너·화면 캡처 (sheet review 2026-11-06) (preferred share of an issuer above)
- 013360 일성건설 — 사진·배너·화면 캡처 (sheet review 2026-11-06)
- 021040 대호특수강 — 사진·배너·화면 캡처 (sheet review 2026-11-06)
- 035250 강원랜드 — 사진·배너·화면 캡처 (sheet review 2026-11-06)
- 038010 제일테크노스 — 사진·배너·화면 캡처 (sheet review 2026-11-06)
- 038540 상상인 — 사진·배너·화면 캡처 (sheet review 2026-11-06)
- 041460 한국전자인증 — 사진·배너·화면 캡처 (sheet review 2026-11-06)
- 052260 현대바이오랜드 — 사진·배너·화면 캡처 (sheet review 2026-11-06)
- 054210 이랜텍 — 사진·배너·화면 캡처 (sheet review 2026-11-06)
- 060540 에스에이티 — 사진·배너·화면 캡처 (sheet review 2026-11-06)
- 064960 SNT모티브 — 사진·배너·화면 캡처 (sheet review 2026-11-06)
- 085910 네오티스 — 사진·배너·화면 캡처 (sheet review 2026-11-06)
- 092230 KPX홀딩스 — 사진·배너·화면 캡처 (sheet review 2026-11-06)
- 115570 스타플렉스 — 사진·배너·화면 캡처 (sheet review 2026-11-06)
- 145270 케이탑리츠 — 사진·배너·화면 캡처 (sheet review 2026-11-06)
- 171120 라이온켐텍 — 사진·배너·화면 캡처 (sheet review 2026-11-06)
- 187270 신화콘텍 — 사진·배너·화면 캡처 (sheet review 2026-11-06)
- 189300 인텔리안테크 — 사진·배너·화면 캡처 (sheet review 2026-11-06)
- 194700 노바렉스 — 사진·배너·화면 캡처 (sheet review 2026-11-06)
- 247660 나노씨엠에스 — 사진·배너·화면 캡처 (sheet review 2026-11-06)
- 261520 이지스 — 사진·배너·화면 캡처 (sheet review 2026-11-06)
- 288330 파라택시스코리아 — 사진·배너·화면 캡처 (sheet review 2026-11-06)
- 365550 ESR켄달스퀘어리츠 — 사진·배너·화면 캡처 (sheet review 2026-11-06)
- 368600 아이씨에이치 — 사진·배너·화면 캡처 (sheet review 2026-11-06)
- 424980 마이크로투나노 — 사진·배너·화면 캡처 (sheet review 2026-11-06)
- 462520 조선내화 — 사진·배너·화면 캡처 (sheet review 2026-11-06)
- HONA Honeywell Aerospace Inc. — 사진·배너·화면 캡처 (sheet review 2026-11-06)
- 002990 금호건설 — 제품 브랜드·슬로건·예전 이름 (sheet review 2026-11-06)
- 005800 신영와코루 — 제품 브랜드·슬로건·예전 이름 (sheet review 2026-11-06)
- 007720 소노스퀘어 — 제품 브랜드·슬로건·예전 이름 (sheet review 2026-11-06)
- 013580 계룡건설 — 제품 브랜드·슬로건·예전 이름 (sheet review 2026-11-06)
- 015590 DKME — 제품 브랜드·슬로건·예전 이름 (sheet review 2026-11-06)
- 030960 양지사 — 제품 브랜드·슬로건·예전 이름 (sheet review 2026-11-06)
- 064520 테크엘 — 제품 브랜드·슬로건·예전 이름 (sheet review 2026-11-06)
- 068290 삼성출판사 — 제품 브랜드·슬로건·예전 이름 (sheet review 2026-11-06)
- 073640 테라사이언스 — 제품 브랜드·슬로건·예전 이름 (sheet review 2026-11-06)
- 078020 LS증권 — 제품 브랜드·슬로건·예전 이름 (sheet review 2026-11-06)
- 091810 트리니티항공 — 제품 브랜드·슬로건·예전 이름 (sheet review 2026-11-06)
- 101730 위메이드맥스 — 제품 브랜드·슬로건·예전 이름 (sheet review 2026-11-06)
- 108320 LX세미콘 — 제품 브랜드·슬로건·예전 이름 (sheet review 2026-11-06)
- 114450 그린생명과학 — 제품 브랜드·슬로건·예전 이름 (sheet review 2026-11-06)
- 187420 HLB제넥스 — 제품 브랜드·슬로건·예전 이름 (sheet review 2026-11-06)
- 196300 HLB펩 — 제품 브랜드·슬로건·예전 이름 (sheet review 2026-11-06)
- 200470 에이팩트 — 제품 브랜드·슬로건·예전 이름 (sheet review 2026-11-06)
- 234690 녹십자웰빙 — 제품 브랜드·슬로건·예전 이름 (sheet review 2026-11-06)
- 290560 파라택시스이더리움 — 제품 브랜드·슬로건·예전 이름 (sheet review 2026-11-06)
- 290660 다이나믹솔루션 — 제품 브랜드·슬로건·예전 이름 (sheet review 2026-11-06)
- 317530 에피소드컴퍼니 — 제품 브랜드·슬로건·예전 이름 (sheet review 2026-11-06)
- 317860 노드메이슨 — 제품 브랜드·슬로건·예전 이름 (sheet review 2026-11-06)
- 352700 씨앤투스 — 제품 브랜드·슬로건·예전 이름 (sheet review 2026-11-06)
- 462980 아이지넷 — 제품 브랜드·슬로건·예전 이름 (sheet review 2026-11-06)
- APA APA Corporation — 제품 브랜드·슬로건·예전 이름 (sheet review 2026-11-06)
- BEN Franklin Templeton, Inc. — 제품 브랜드·슬로건·예전 이름 (sheet review 2026-11-06)
- DOC Healthpeak Properties, Inc. — 제품 브랜드·슬로건·예전 이름 (sheet review 2026-11-06)
- 001560 제일연마 — 의심스럽거나 알아보기 어려운 그림 (sheet review 2026-11-06)
- 004410 서울식품 — 의심스럽거나 알아보기 어려운 그림 (sheet review 2026-11-06)
- 007530 와이엠 — 의심스럽거나 알아보기 어려운 그림 (sheet review 2026-11-06)
- 020120 키다리스튜디오 — 의심스럽거나 알아보기 어려운 그림 (sheet review 2026-11-06)
- 030000 제일기획 — 의심스럽거나 알아보기 어려운 그림 (sheet review 2026-11-06)
- 030610 교보증권 — 의심스럽거나 알아보기 어려운 그림 (sheet review 2026-11-06)
- 033340 좋은사람들 — 의심스럽거나 알아보기 어려운 그림 (sheet review 2026-11-06)
- 039340 한국경제TV — 의심스럽거나 알아보기 어려운 그림 (sheet review 2026-11-06)
- 039830 오로라 — 의심스럽거나 알아보기 어려운 그림 (sheet review 2026-11-06)
- 067280 멀티캠퍼스 — 의심스럽거나 알아보기 어려운 그림 (sheet review 2026-11-06)
- 073570 리튬포어스 — 의심스럽거나 알아보기 어려운 그림 (sheet review 2026-11-06)
- 078590 휴림에이텍 — 의심스럽거나 알아보기 어려운 그림 (sheet review 2026-11-06)
- 096350 대창솔루션 — 의심스럽거나 알아보기 어려운 그림 (sheet review 2026-11-06)
- 099430 바이오플러스 — 의심스럽거나 알아보기 어려운 그림 (sheet review 2026-11-06)
- 142280 녹십자엠에스 — 의심스럽거나 알아보기 어려운 그림 (sheet review 2026-11-06)
- 175140 아고스 — 의심스럽거나 알아보기 어려운 그림 (sheet review 2026-11-06)
- 180060 탑선 — 의심스럽거나 알아보기 어려운 그림 (sheet review 2026-11-06)
- 277070 린드먼아시아 — 의심스럽거나 알아보기 어려운 그림 (sheet review 2026-11-06)
- 308430 셀비온 — 의심스럽거나 알아보기 어려운 그림 (sheet review 2026-11-06)
- 317330 덕산테코피아 — 의심스럽거나 알아보기 어려운 그림 (sheet review 2026-11-06)
- 397810 애드포러스 — 의심스럽거나 알아보기 어려운 그림 (sheet review 2026-11-06)
- 475560 더본코리아 — 의심스럽거나 알아보기 어려운 그림 (sheet review 2026-11-06)
- 481070 에이유브랜즈 — 의심스럽거나 알아보기 어려운 그림 (sheet review 2026-11-06)
- APTV Aptiv PLC — 의심스럽거나 알아보기 어려운 그림 (sheet review 2026-11-06)
- CLX Clorox Company (The) — 의심스럽거나 알아보기 어려운 그림 (sheet review 2026-11-06)
- CZR Caesars Entertainment, Inc. — 의심스럽거나 알아보기 어려운 그림 (sheet review 2026-11-06)
- IBRX ImmunityBio, Inc. — 의심스럽거나 알아보기 어려운 그림 (sheet review 2026-11-06)
- TPR Tapestry, Inc. — 의심스럽거나 알아보기 어려운 그림 (sheet review 2026-11-06)

## Added after review (from a --only run)

- 000270 기아 — Jack 2026-11-07: 기아 ticker logo (KIA wordmark), looked at by eye; replaces the 32 px homepage picture

## Sources

- data.json: https://jacksungjinlee.github.io/baepsae/data.json (2,335,944 bytes)
- KRX listing: https://raw.githubusercontent.com/FinanceData/fdr_krx_data_cache/refs/heads/master/data/listing/krx/2026-11-05.csv (397,696 bytes)
- DART homepages: /home/runner/work/baepsae/baepsae/tools/logos/kr_homepages.csv (2,470 companies)

Files: logos/ (pictures + index.json, for tools/push_logos_branch.sh), review.csv (one row per company), run.json, run.log. Signed image addresses are never kept (they expire after about 24 hours).
