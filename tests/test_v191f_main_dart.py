# -*- coding: utf-8 -*-
"""fetch_data.main() 의 DART 단계를 실제로 돌려 봐요 (네트워크 없음 · 행동 시험 — 코드 글자를 찾는 시험이 아니에요).

리뷰 2026-11-08: b6852d0 에서 'v2 파일을 v3 저장 뒤에 지우기' 블록이 들어가며 DART · 업종 코드 단계와 '키 없음' 로그를 그 블록 안으로
끌고 들어갔어요 (키가 있어도 DART 를 안 돌리고 '키 없음'이라고 남김 · dart=off 에 v2 파일이 있으면 client=None 으로 DART 를 부름).
여기서는 main() 을 처음부터 돌리되, 앞 단계(시세 · 표)는 가짜로 바꾸고, DART 단계 바로 뒤(blank_foreign_dart)에서 멈춰요."""
import datetime as dt
import gzip
import json
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import fetch_data as F  # noqa: E402


class Stop(Exception):
    """DART 단계 바로 다음 단계에 닿았어요 (시험은 여기서 끝)."""


@pytest.fixture
def drive(tmp_path, monkeypatch, capsys):
    """main() 을 DART 단계까지 돌려요 → (enrich 호출들, ksic 호출들, 로그, tmp_path)."""
    monkeypatch.chdir(tmp_path)                       # DartClient 의 캐시 경로(.dart-cache/…)가 이 폴더 안이 되게
    for k in ("GITHUB_REF", "GITHUB_EVENT_NAME", "BAEPSAE_SELFTEST", "SAMPLE_KR", "BAEPSAE_AUTO_RUN", "DRY_RUN"):
        monkeypatch.delenv(k, raising=False)
    kr = [{"t": "000100", "nk": "가", "cls": "kr", "price": 1000.0, "cap": 1.0, "shr": 1000}]
    kmeta = {"pxDate": "2026-11-06", "ksDate": "2026-11-06", "_prefShares": {}, "_prefCaps": {}}
    monkeypatch.setattr(F, "read_prev_data", lambda *a, **k: None)
    monkeypatch.setattr(F, "load_industry_tables", lambda *a, **k: {"groups": {}, "kmap": {}, "usmap": {}, "over": {}, "refine": {}})
    monkeypatch.setattr(F, "load_us_kr_duplicates", lambda *a, **k: {})
    monkeypatch.setattr(F, "load_krx_special_sessions", lambda *a, **k: {})
    monkeypatch.setattr(F, "load_market_holidays", lambda *a, **k: {"KR": {}, "US": {}, "start": None, "end": dt.date(2027, 12, 31)})
    monkeypatch.setattr(F, "fetch_rf", lambda *a, **k: (0.03, "시험"))
    monkeypatch.setattr(F, "fetch_korea", lambda *a, **k: (kr, None, {}, kmeta))
    calls = {"enrich": [], "ksic": []}

    def enrich(kr_, client, pref):
        calls["enrich"].append(client)
        return kr_, {"000100": {"rev": [1.0, None, None]}}

    def ksic(kr_, client):
        calls["ksic"].append(client)
        return {}

    def stop(kr_):
        raise Stop()
    monkeypatch.setattr(F, "enrich_with_dart", enrich)
    monkeypatch.setattr(F, "fetch_ksic", ksic)
    monkeypatch.setattr(F, "blank_foreign_dart", stop)

    def run(key, mode, v2=False):
        monkeypatch.setattr(F, "DART_KEY", key)
        monkeypatch.setenv("DART_MODE", mode)
        if v2:
            os.makedirs(tmp_path / ".dart-cache", exist_ok=True)
            with gzip.open(tmp_path / ".dart-cache" / "dart-v2.json.gz", "wt", encoding="utf-8") as f:
                json.dump({"v": 2, "meta": {}, "entries": {"C1|company": {"st": "000", "at": "2026-11-01", "d": {"induty": "264"}}}}, f)
        with pytest.raises(Stop):
            F.main()
        return calls, capsys.readouterr().out
    return run


def v2_file(tmp_path):
    return tmp_path / ".dart-cache" / "dart-v2.json.gz"


def test_with_a_key_dart_and_industry_codes_run_with_a_real_client(drive, tmp_path):
    calls, out = drive("k", "cache", v2=True)
    assert len(calls["enrich"]) == 1 and isinstance(calls["enrich"][0], F.DartClient)
    assert len(calls["ksic"]) == 1 and calls["ksic"][0] is calls["enrich"][0]
    assert "DART_API_KEY 없음" not in out
    client = calls["enrich"][0]
    assert client.carried == 1 and client.remove_after_save == [os.path.join(".dart-cache", "dart-v2.json.gz")]
    assert v2_file(tmp_path).exists()                                       # v3 를 처음 저장할 때까지 남아요


def test_with_a_key_and_no_old_file_dart_still_runs(drive, tmp_path):
    calls, out = drive("k", "full")
    assert len(calls["enrich"]) == 1 and len(calls["ksic"]) == 1 and "DART_API_KEY 없음" not in out


def test_dart_off_with_an_old_v2_file_calls_nothing_and_removes_the_file(drive, tmp_path):
    calls, out = drive("k", "off", v2=True)
    assert calls == {"enrich": [], "ksic": []}
    assert not v2_file(tmp_path).exists() and "이번 실행은 DART 를 쓰지 않아요" in out
    assert "시험 실행: DART 를 끄고 진행해요" in out and "DART_API_KEY 없음" not in out


def test_no_key_logs_it_and_calls_nothing(drive, tmp_path):
    calls, out = drive("", "cache", v2=True)
    assert calls == {"enrich": [], "ksic": []}
    assert "DART_API_KEY 없음 → 재무지표·공시를 못 받아요" in out and not v2_file(tmp_path).exists()
