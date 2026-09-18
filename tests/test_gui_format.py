import datetime
from pathlib import Path

from file_ops import FileOpResult
from gui_format import format_apply_summary, format_preview_summary
from report import ReportRow


def _row(path, scene_id, selected, reason):
    return ReportRow(
        path=Path(path),
        scene_id=scene_id,
        sharpness=1.0,
        exposure=1.0,
        face=None,
        total=1.0,
        selected=selected,
        reason=reason,
    )


def test_format_preview_summary_counts_scenes_and_selections():
    rows = [
        _row("a.jpg", 1, True, "선택됨: 장면 내 최고 종합점수"),
        _row("b.jpg", 1, False, "제외: 종합 점수가 더 낮음"),
        _row("c.jpg", 2, True, "선택됨: 장면 내 최고 종합점수"),
    ]

    summary = format_preview_summary(rows)

    assert "2개 장면" in summary
    assert "3장 중 2장 선택" in summary


def test_format_preview_summary_lists_selected_file_per_scene():
    rows = [
        _row("a.jpg", 1, True, "선택됨: 장면 내 최고 종합점수"),
        _row("b.jpg", 1, False, "제외: 종합 점수가 더 낮음"),
    ]

    summary = format_preview_summary(rows)

    assert "[장면 1] 선택: a.jpg" in summary
    assert "제외: b.jpg" in summary


def test_format_preview_summary_handles_empty_rows():
    assert "0개 장면" in format_preview_summary([])


def test_format_apply_summary_reports_count_and_output_dir():
    results = [
        FileOpResult(
            source=Path("a.jpg"),
            destination=Path("/out/a.jpg"),
            raw_source=None,
            raw_destination=None,
            action="copy",
        )
    ]

    summary = format_apply_summary(results, Path("/out"))

    assert "1장" in summary
    assert "/out" in summary


def test_format_apply_summary_reports_move_label_for_move_action():
    results = [
        FileOpResult(
            source=Path("a.jpg"),
            destination=Path("/out/a.jpg"),
            raw_source=None,
            raw_destination=None,
            action="move",
        )
    ]

    summary = format_apply_summary(results, Path("/out"))

    assert "이동" in summary
    assert "복사" not in summary
