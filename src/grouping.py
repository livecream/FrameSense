"""M2: 장면 그룹핑 (촬영 시각 간격 기준).

PROJECT_SPEC.md 4.2절, 8절: 연속 촬영 시각 간격이 gap_seconds 이내인 사진들을
같은 장면으로 묶는다. 입력은 scan_and_extract가 반환하는, 이미 촬영 시각순으로
정렬된 목록을 전제로 한다.
"""

from __future__ import annotations

from scanner import PhotoMetadata

DEFAULT_SCENE_GAP_SECONDS = 3


def group_by_time_gap(
    photos: list[PhotoMetadata],
    gap_seconds: float = DEFAULT_SCENE_GAP_SECONDS,
) -> list[list[PhotoMetadata]]:
    """촬영 시각순으로 정렬된 사진들을 시간 간격 기준으로 장면 그룹으로 묶는다.

    연속한 두 사진의 촬영 시각 차이가 gap_seconds 이내(포함)면 같은 장면으로 묶고,
    초과하면 새 장면을 시작한다.
    """
    if not photos:
        return []

    groups: list[list[PhotoMetadata]] = [[photos[0]]]
    for previous, current in zip(photos, photos[1:]):
        gap = (current.datetime_original - previous.datetime_original).total_seconds()
        if gap <= gap_seconds:
            groups[-1].append(current)
        else:
            groups.append([current])
    return groups
