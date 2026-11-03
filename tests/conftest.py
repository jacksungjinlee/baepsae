# -*- coding: utf-8 -*-
"""pytest 공통 설정: 시험이 만드는 임시 폴더(tempfile.mkdtemp · mkstemp)를 한 실행 폴더 안에 모았다가 끝나면 지워요.

디스크를 아끼려는 정리일 뿐, 어떤 검사도 바꾸지 않아요. 묶음 파일(app.js · *.mjs · 빌드한 app.html …)이 실행마다 쌓이지 않게요.
pytest 의 tmp_path 는 pytest 가 따로 관리해요."""
import shutil
import tempfile

import pytest


@pytest.fixture(scope="session", autouse=True)
def _one_temp_dir_per_run():
    run = tempfile.mkdtemp(prefix="baepsae-tests-")
    before = tempfile.tempdir
    tempfile.tempdir = run
    try:
        yield
    finally:
        tempfile.tempdir = before
        shutil.rmtree(run, ignore_errors=True)


@pytest.fixture(autouse=True)
def _not_a_scheduled_run(monkeypatch):
    """시험은 정해진 시각 실행이 아니에요: GitHub 의 정해진 시각 실행 안에서 pytest 를 돌려도 fetch_data 의 '빈 DART 캐시 멈춤'
    (v17.5.3, GITHUB_EVENT_NAME=schedule)이 빈 캐시로 만드는 시험들을 멈추지 않게 지워요. 그 멈춤 자체는 test_schedule.py 가
    값을 직접 넣어서 시험해요. 어떤 검사도 느슨해지지 않아요."""
    monkeypatch.delenv("GITHUB_EVENT_NAME", raising=False)
