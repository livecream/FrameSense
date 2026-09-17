"""M5: dry-run 리포트.

PROJECT_SPEC.md 4.5절: 실제 파일 작업(M6) 전에 어떤 사진이 왜 선택/제외됐는지
CSV 또는 JSON으로 먼저 보여준다. 이 모듈은 리포트 생성까지만 하고 파일 복사/이동은
하지 않는다.
"""

from __future__ import annotations

import csv
import json
from dataclasses import asdict, dataclass
from pathlib import Path

from scanner import PhotoMetadata
from selector import SceneSelection, select_best


@dataclass(frozen=True)
class ReportRow:
    path: Path
    scene_id: int
    sharpness: float
    exposure: float
    face: float | None
    total: float
    selected: bool
    reason: str


def _reason_for(index: int, selection: SceneSelection) -> str:
    if index == selection.best_index:
        return "선택됨: 장면 내 최고 종합점수"

    score = selection.scores[index]
    if score.error:
        return f"제외: {score.error}"
    if selection.combined_scores[index] == selection.combined_scores[selection.best_index]:
        return "제외: 동점이며 더 늦게 촬영됨"
    return "제외: 종합 점수가 더 낮음"


def build_report(groups: list[list[PhotoMetadata]]) -> list[ReportRow]:
    """장면 그룹 목록으로부터 사진별 선택/제외 리포트 행을 만든다."""
    rows: list[ReportRow] = []
    for scene_id, group in enumerate(groups, start=1):
        selection = select_best(group)
        for i, meta in enumerate(group):
            score = selection.scores[i]
            rows.append(
                ReportRow(
                    path=meta.path,
                    scene_id=scene_id,
                    sharpness=score.sharpness,
                    exposure=score.exposure,
                    face=score.face,
                    total=selection.combined_scores[i],
                    selected=i == selection.best_index,
                    reason=_reason_for(i, selection),
                )
            )
    return rows


def _row_to_dict(row: ReportRow) -> dict:
    d = asdict(row)
    d["path"] = str(row.path)
    return d


def write_report(rows: list[ReportRow], output_path: Path) -> None:
    """확장자(.csv 또는 .json)에 따라 리포트를 파일로 쓴다."""
    output_path = Path(output_path)
    suffix = output_path.suffix.lower()

    if suffix == ".csv":
        with open(output_path, "w", newline="", encoding="utf-8") as f:
            fieldnames = list(_row_to_dict(rows[0]).keys()) if rows else []
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for row in rows:
                writer.writerow(_row_to_dict(row))
    elif suffix == ".json":
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump([_row_to_dict(r) for r in rows], f, ensure_ascii=False, indent=2)
    else:
        raise ValueError(f"지원하지 않는 리포트 형식입니다: {suffix} (.csv 또는 .json만 지원)")
