# -*- coding: utf-8 -*-
"""2026-11-11 (Jack): CI 가 smoke_app 을 여러 기계로 나눠 돌려요 (tests/smoke_app.py --part N/M).
몫을 모두 합치면 모든 장면이 정확히 한 번씩 — 빠지거나 두 번 도는 장면이 없어요. 새 장면은 목록에 넣기만 하면 어느 한 몫에 들어가요."""
import os
import sys

import pytest
import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tests"))
import smoke_app  # noqa: E402


def scenes():
    return smoke_app.scene_list(None, None, False)            # 함수는 부르지 않아요 — 목록만


def ci_parts():
    with open(os.path.join(ROOT, ".github", "workflows", "ci.yml"), encoding="utf-8") as f:
        matrix = yaml.safe_load(f)["jobs"]["smoke_app"]["strategy"]["matrix"]
    assert set(matrix) == {"part"}, matrix                    # include · exclude 없이 몫 목록 그대로
    return matrix["part"]


@pytest.mark.parametrize("m", [1, 2, 3, 4, 5, 6])
def test_parts_together_cover_every_scene_exactly_once(m):
    all_ = scenes()
    seen = [id(s) for n in range(1, m + 1) for s in smoke_app.part_of(all_, f"{n}/{m}")]
    assert sorted(seen) == sorted(id(s) for s in all_)        # 모두 · 한 번씩 (같은 이름의 장면도 따로 세요)
    assert len(seen) == len(set(seen)) == len(all_)


def test_the_parts_ci_runs_cover_every_scene_exactly_once():
    parts = ci_parts()
    m = len(parts)
    assert parts == [f"{n}/{m}" for n in range(1, m + 1)]
    all_ = scenes()
    seen = [id(s) for p in parts for s in smoke_app.part_of(all_, p)]
    assert sorted(seen) == sorted(id(s) for s in all_) and len(seen) == len(all_)
    assert all(smoke_app.part_of(all_, p) for p in parts)    # 빈 몫 없음 (그 기계가 아무것도 안 하고 '통과'하지 않게)


def test_no_part_means_every_scene_in_order():
    all_ = scenes()
    assert smoke_app.part_of(all_, None) == all_
    assert len(all_) >= 30 and all(callable(fn) for _, fn in all_)


def test_a_new_scene_lands_in_exactly_one_part():
    all_ = scenes() + [("새 장면", lambda: None)]
    for m in (2, 3):
        hits = [n for n in range(1, m + 1) if any(s[0] == "새 장면" for s in smoke_app.part_of(all_, f"{n}/{m}"))]
        assert len(hits) == 1, (m, hits)


@pytest.mark.parametrize("bad", ["0/2", "3/2", "2", "1/0", "a/b", "", "1/2/3", " 1/2", "-1/2"])
def test_a_wrong_part_is_refused(bad):
    with pytest.raises(ValueError):
        smoke_app.parse_part(bad)
