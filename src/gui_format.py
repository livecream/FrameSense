"""M8/M9/M10: GUI용 순수 텍스트 포맷팅 헬퍼. Qt에 의존하지 않아 pytest로 바로 테스트한다."""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from file_ops import FileOpResult
from rename_by_time import RenamePlanRow, RenameResult
from report import ReportRow


def format_preview_summary(rows: list[ReportRow]) -> str:
    """dry-run 미리보기 결과를 사람이 읽을 요약 텍스트로 만든다."""
    by_scene: dict[int, list[ReportRow]] = defaultdict(list)
    for row in rows:
        by_scene[row.scene_id].append(row)

    total = len(rows)
    selected = sum(1 for r in rows if r.selected)
    lines = [f"{len(by_scene)}개 장면, {total}장 중 {selected}장 선택\n"]

    for scene_id in sorted(by_scene):
        scene_rows = by_scene[scene_id]
        selected_row = next((r for r in scene_rows if r.selected), None)
        excluded_names = [Path(r.path).name for r in scene_rows if not r.selected]

        if selected_row is None:
            lines.append(f"[장면 {scene_id}] 선택된 컷 없음")
            continue

        line = f"[장면 {scene_id}] 선택: {Path(selected_row.path).name}"
        if excluded_names:
            line += f"  (제외: {', '.join(excluded_names)})"
        lines.append(line)

    return "\n".join(lines)


def format_apply_summary(results: list[FileOpResult], output_dir: Path) -> str:
    """apply_selection 결과를 사람이 읽을 요약 텍스트로 만든다."""
    action = results[0].action if results else "copy"
    verb = "이동" if action == "move" else "복사"
    return f"{verb} 완료: {len(results)}장 → {output_dir}"


def format_rename_preview(rows: list[RenamePlanRow]) -> str:
    """M9 시간순 리네임 dry-run 미리보기 결과를 사람이 읽을 요약 텍스트로 만든다."""
    lines = [f"{len(rows)}개 파일 리네임 예정 (제자리 rename, 원본 폴더는 그대로)\n"]
    for row in rows:
        line = f"{row.old_path.name} → {row.new_path.name}  ({row.old_path.parent})"
        if row.raw_old_path is not None:
            line += f"  [+RAW: {row.raw_old_path.name} → {row.raw_new_path.name}]"
        lines.append(line)
    return "\n".join(lines)


def format_rename_apply_summary(results: list[RenameResult]) -> str:
    """M9 리네임 적용 결과를 사람이 읽을 요약 텍스트로 만든다."""
    return f"리네임 완료: {len(results)}개 파일"


def format_badcut_preview(rows: list[ReportRow]) -> str:
    """M10 C컷 판정 dry-run 미리보기 결과를 사람이 읽을 요약 텍스트로 만든다.

    임계값을 얼마로 잡아야 할지는 사진마다(카메라/해상도) 달라 코드에 기본값을
    두지 않으므로, 실제 선명도/눈뜸 점수 분포를 보여줘 사용자가 직접 판단할 수
    있게 한다."""
    scored_rows = [r for r in rows if not r.reason.startswith("판정 불가")]
    bad_rows = [r for r in rows if r.selected]
    lines = [f"{len(rows)}장 중 {len(bad_rows)}장 C컷 판정\n"]

    sharpness_values = [r.sharpness for r in scored_rows]
    if sharpness_values:
        lines.append(
            f"선명도 분포: 최소 {min(sharpness_values):.1f} / "
            f"평균 {sum(sharpness_values) / len(sharpness_values):.1f} / "
            f"최대 {max(sharpness_values):.1f}"
        )

    face_values = [r.face for r in scored_rows if r.face is not None]
    if face_values:
        lines.append(
            f"눈뜸 점수 분포(얼굴 검출된 {len(face_values)}장): "
            f"최소 {min(face_values):.2f} / "
            f"평균 {sum(face_values) / len(face_values):.2f} / "
            f"최대 {max(face_values):.2f}"
        )
    lines.append("")

    for r in bad_rows:
        detail = f"선명도 {r.sharpness:.1f}"
        if r.face is not None:
            detail += f", 눈뜸 {r.face:.2f}"
        lines.append(f"{Path(r.path).name}  ({r.reason} — {detail})")
    return "\n".join(lines)
