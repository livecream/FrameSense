import datetime
from pathlib import Path

from file_ops import FileOpResult
from gui_format import (
    format_apply_summary,
    format_badcut_preview,
    format_preview_summary,
    format_rename_apply_summary,
    format_rename_preview,
)
from rename_by_time import RenamePlanRow, RenameResult
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


def _rename_row(old_name, new_name, raw_old_name=None, raw_new_name=None):
    old_path = Path("/in") / old_name
    return RenamePlanRow(
        seq=1,
        old_path=old_path,
        new_path=Path("/in") / new_name,
        raw_old_path=Path("/in") / raw_old_name if raw_old_name else None,
        raw_new_path=Path("/in") / raw_new_name if raw_new_name else None,
        datetime_original=datetime.datetime(2026, 1, 1, 10, 0, 0),
    )


def test_format_rename_preview_lists_old_and_new_names():
    rows = [_rename_row("DSC_001.jpg", "00001.jpg")]

    summary = format_rename_preview(rows)

    assert "1개 파일 리네임 예정" in summary
    assert "DSC_001.jpg → 00001.jpg" in summary


def test_format_rename_preview_shows_raw_pairing():
    rows = [_rename_row("DSC_001.jpg", "00001.jpg", "DSC_001.cr3", "00001.cr3")]

    summary = format_rename_preview(rows)

    assert "DSC_001.cr3 → 00001.cr3" in summary


def test_format_rename_apply_summary_reports_count():
    results = [
        RenameResult(
            old_path=Path("/in/a.jpg"),
            new_path=Path("/in/00001.jpg"),
            raw_old_path=None,
            raw_new_path=None,
        )
    ]

    assert "1개 파일" in format_rename_apply_summary(results)


def test_format_badcut_preview_counts_and_lists_flagged_only():
    rows = [
        _row("a.jpg", 0, True, "C컷: 블러(선명도 낮음)"),
        _row("b.jpg", 0, False, "정상 컷(임계값 이상)"),
    ]

    summary = format_badcut_preview(rows)

    assert "2장 중 1장 C컷 판정" in summary
    assert "a.jpg" in summary
    assert "b.jpg" not in summary
