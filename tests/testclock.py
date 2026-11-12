# -*- coding: utf-8 -*-
"""시험의 시계 (2026-11-11, Jack): 스모크 테스트가 그날그날 · 시각마다 다른 결과를 내지 않게, 정해진 순간에서 시작해 평소처럼 흘러요.

- 파이썬 쪽 '지금'(TestClock.now)과 모든 브라우저 창의 Date 가 같은 만큼 옮겨져요. 그래서 '방금 발행한 파일'의 시각과 창의 시각이 맞아요.
- 창에서는 Date 만 옮겨요 (DATE_SHIM, 페이지보다 먼저 도는 스크립트). 타이머 · performance 는 진짜 그대로예요:
  Playwright 의 clock.install 은 타이머와 performance 도 바꿔서, 앱이 평소와 다른 타이머로 돌고 받은 파일을 performance 기록으로
  확인하는 검사가 아무것도 보지 못해요. (시계를 손으로 옮기는 장면만 Playwright 의 페이지 시계를 직접 써요.)
- 시작하지 않은 시계(start_at 을 부르지 않음)는 진짜 시계예요: 실제 데이터로 돌 때(--data)와 다른 테스트가 도우미만 빌려 쓸 때.
- 옮겨지지 않는 것 (지금 앱은 쓰지 않아요): 날짜 없이 부르는 Intl.DateTimeFormat().format() · 워커(서비스워커 포함) ·
  document.lastModified · File.lastModified · 어떤 날짜의 .constructor 로 만든 새 날짜 · class X extends Date.
- 여기서는 Playwright 의 시계 설치를 쓰지 않아요 (tests/test_snapshot.py 가 확인해요).
"""
import datetime as dt
import time

KST = dt.timezone(dt.timedelta(hours=9))

DATE_SHIM = """(() => {
  const RealDate = Date, shift = %d;
  function TestDate(...a) {
    if (!new.target) return new RealDate(RealDate.now() + shift).toString();
    return a.length ? new RealDate(...a) : new RealDate(RealDate.now() + shift);
  }
  Object.setPrototypeOf(TestDate, RealDate);
  TestDate.prototype = RealDate.prototype;
  TestDate.now = () => RealDate.now() + shift;
  window.Date = TestDate;
})();"""

DRIFT_OK = (-2, 600)          # 창의 시계 − 그 창이 시작해야 하는 시각 (초): 진짜 시계로 돈 창은 몇 시간 · 며칠씩 어긋나요


class TestClock:
    __test__ = False          # pytest 가 테스트 클래스로 모으지 않게

    def __init__(self):
        self.start, self.shift = None, 0.0

    @property
    def started(self):
        return self.start is not None

    def start_at(self, when):
        """지금 이 순간을 when (시간대가 있는 datetime) 으로 삼아요. 그 뒤로는 평소처럼 흘러요."""
        self.start, self.shift = when, when.timestamp() - time.time()

    def now(self):
        return dt.datetime.fromtimestamp(time.time() + self.shift, KST)

    def install(self, ctx):
        """그 창(BrowserContext)의 모든 페이지의 Date 를 시험의 시계로. 시작하지 않은 시계면 아무것도 하지 않아요."""
        if self.started:
            ctx.add_init_script(DATE_SHIM % round(self.shift * 1000))

    def drift(self, page, base=None):
        """그 페이지의 시계 − (base 가 있으면 그 시각, 없으면 시험의 지금) 초."""
        return page.evaluate("Date.now()") / 1000 - (base or self.now()).timestamp()


def drift_ok(d):
    return DRIFT_OK[0] <= d < DRIFT_OK[1]
