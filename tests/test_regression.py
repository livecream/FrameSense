"""M7: test_photos/의 실사진 결과가 기준선(baseline.json) 대비 나빠지지 않았는지 확인.

기준선이 없으면(아직 실사진을 안 넣었거나 기준선을 안 만들었으면) 스킵한다 —
test_photos/는 개인 사진용이라 CI/다른 개발자 환경엔 없을 수 있다.
"""

import json

from update_regression_baseline import BASELINE_PATH, TEST_PHOTOS_DIR, compute_selection

import pytest


@pytest.mark.skipif(
    not BASELINE_PATH.exists(),
    reason=(
        "회귀 테스트 기준선이 없습니다. test_photos/에 실사진을 넣고 "
        "python tests/update_regression_baseline.py 로 기준선을 먼저 만드세요."
    ),
)
def test_selection_matches_baseline():
    baseline = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
    current = compute_selection(TEST_PHOTOS_DIR)

    assert current == baseline, (
        "베스트 컷 선정 결과가 기준선과 달라졌습니다. 의도한 변경이면 "
        "python tests/update_regression_baseline.py 로 기준선을 갱신하세요."
    )
