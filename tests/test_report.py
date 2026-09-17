import csv
import datetime
import json

from PIL import Image

from report import build_report, write_report
from scanner import PhotoMetadata


def _make_flat(path, size=32, color=128):
    Image.new("RGB", (size, size), (color, color, color)).save(path, "png")
    return path


def _meta(path, seconds_offset=0):
    base = datetime.datetime(2026, 6, 1, 14, 0, 0)
    return PhotoMetadata(
        path=path,
        datetime_original=base + datetime.timedelta(seconds=seconds_offset),
        exif_source="exif",
    )


def _two_photo_scene(tmp_path):
    p1 = _make_flat(tmp_path / "a.png")
    p2 = _make_flat(tmp_path / "b.png")
    return [[_meta(p1, 0), _meta(p2, 1)]]


def test_build_report_marks_exactly_one_selected_per_scene(tmp_path):
    groups = _two_photo_scene(tmp_path)

    rows = build_report(groups)

    assert len(rows) == 2
    assert sum(1 for r in rows if r.selected) == 1


def test_build_report_selected_row_has_selection_reason(tmp_path):
    groups = _two_photo_scene(tmp_path)

    rows = build_report(groups)
    selected = next(r for r in rows if r.selected)

    assert "선택" in selected.reason


def test_build_report_excluded_row_has_exclusion_reason(tmp_path):
    groups = _two_photo_scene(tmp_path)

    rows = build_report(groups)
    excluded = next(r for r in rows if not r.selected)

    assert "제외" in excluded.reason


def test_build_report_assigns_scene_id_per_group(tmp_path):
    p1 = _make_flat(tmp_path / "scene1.png")
    p2 = _make_flat(tmp_path / "scene2.png")
    groups = [[_meta(p1, 0)], [_meta(p2, 100)]]

    rows = build_report(groups)

    assert [r.scene_id for r in rows] == [1, 2]


def test_write_report_csv_contains_expected_columns(tmp_path):
    groups = _two_photo_scene(tmp_path)
    rows = build_report(groups)
    out = tmp_path / "report.csv"

    write_report(rows, out)

    with open(out, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        records = list(reader)

    assert len(records) == 2
    assert set(records[0].keys()) >= {
        "path", "scene_id", "sharpness", "exposure", "face", "total", "selected", "reason",
    }


def test_write_report_json_round_trips(tmp_path):
    groups = _two_photo_scene(tmp_path)
    rows = build_report(groups)
    out = tmp_path / "report.json"

    write_report(rows, out)

    with open(out, encoding="utf-8") as f:
        records = json.load(f)

    assert len(records) == 2
    assert records[0]["scene_id"] == 1


def test_write_report_rejects_unsupported_extension(tmp_path):
    groups = _two_photo_scene(tmp_path)
    rows = build_report(groups)

    try:
        write_report(rows, tmp_path / "report.txt")
        assert False, "expected ValueError"
    except ValueError:
        pass
