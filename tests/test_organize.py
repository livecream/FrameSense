import datetime
import os

import piexif
import pytest
from PIL import Image

from organize import (
    build_capture_date_plan,
    build_move_by_extension_plan,
    find_empty_folders,
    find_raw_jpg_mismatches,
    remove_empty_folders,
)
from organize import apply_move_plan


def _make_jpeg(path, dt=None, color=(200, 50, 50)):
    img = Image.new("RGB", (32, 24), color)
    if dt is not None:
        exif_dict = {
            "0th": {},
            "Exif": {
                piexif.ExifIFD.DateTimeOriginal: dt.strftime("%Y:%m:%d %H:%M:%S").encode(),
            },
            "1st": {},
            "thumbnail": None,
        }
        img.save(path, "jpeg", exif=piexif.dump(exif_dict))
    else:
        img.save(path, "jpeg")
    return path


def _make_video(path, dt):
    path.write_bytes(b"fake video bytes")
    ts = dt.timestamp()
    os.utime(path, (ts, ts))
    return path


def test_build_move_by_extension_plan_targets_top_level_only(tmp_path):
    raw = tmp_path / "a.cr3"
    raw.write_bytes(b"fake raw")
    _make_jpeg(tmp_path / "a.jpg")
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "b.cr3").write_bytes(b"fake raw nested")

    rows = build_move_by_extension_plan(tmp_path, {".cr3"}, "RAW")

    assert [r.old_path.name for r in rows] == ["a.cr3"]
    assert rows[0].new_path == tmp_path / "RAW" / "a.cr3"


def test_apply_move_plan_moves_files_and_creates_dest_dir(tmp_path):
    raw = tmp_path / "a.cr3"
    raw.write_bytes(b"fake raw")
    rows = build_move_by_extension_plan(tmp_path, {".cr3"}, "RAW")

    apply_move_plan(rows)

    assert not raw.exists()
    assert (tmp_path / "RAW" / "a.cr3").exists()


def test_find_raw_jpg_mismatches_reports_both_directions(tmp_path):
    _make_jpeg(tmp_path / "matched.jpg")
    (tmp_path / "matched.cr3").write_bytes(b"fake raw")
    _make_jpeg(tmp_path / "orphan_photo.jpg")
    (tmp_path / "orphan_raw.cr3").write_bytes(b"fake raw")

    messages = find_raw_jpg_mismatches(tmp_path)

    assert any("orphan_photo.jpg" in m for m in messages)
    assert any("orphan_raw.cr3" in m for m in messages)
    assert not any("matched" in m for m in messages)


def test_find_raw_jpg_mismatches_empty_when_all_paired(tmp_path):
    _make_jpeg(tmp_path / "a.jpg")
    (tmp_path / "a.cr3").write_bytes(b"fake raw")

    assert find_raw_jpg_mismatches(tmp_path) == []


def test_build_capture_date_plan_groups_photos_and_videos_by_date(tmp_path):
    _make_jpeg(tmp_path / "a.jpg", datetime.datetime(2024, 1, 1, 10, 0, 0))
    _make_jpeg(tmp_path / "b.jpg", datetime.datetime(2024, 1, 2, 9, 0, 0))
    _make_video(tmp_path / "c.mp4", datetime.datetime(2024, 1, 1, 11, 0, 0))

    rows = build_capture_date_plan(tmp_path, video_extensions={".mp4"})
    by_name = {r.old_path.name: r.new_path for r in rows}

    assert by_name["a.jpg"] == tmp_path / "2024-01-01" / "a.jpg"
    assert by_name["b.jpg"] == tmp_path / "2024-01-02" / "b.jpg"
    assert by_name["c.mp4"] == tmp_path / "2024-01-01" / "c.mp4"


def test_build_capture_date_plan_ignores_unsupported_files(tmp_path):
    (tmp_path / "notes.txt").write_text("hello")

    assert build_capture_date_plan(tmp_path, video_extensions={".mp4"}) == []


def test_find_empty_folders_finds_nested_empty_dirs_deepest_first(tmp_path):
    (tmp_path / "keep").mkdir()
    _make_jpeg(tmp_path / "keep" / "a.jpg")

    empty_parent = tmp_path / "empty_parent"
    empty_child = empty_parent / "empty_child"
    empty_child.mkdir(parents=True)

    result = find_empty_folders(tmp_path)

    assert empty_child in result
    assert empty_parent in result
    assert tmp_path / "keep" not in result
    # 자식이 부모보다 먼저 나와야 순서대로 삭제해도 안전함
    assert result.index(empty_child) < result.index(empty_parent)


def test_find_empty_folders_ignores_folder_with_file_in_subtree(tmp_path):
    nested = tmp_path / "a" / "b"
    nested.mkdir(parents=True)
    _make_jpeg(nested / "photo.jpg")

    result = find_empty_folders(tmp_path)

    assert tmp_path / "a" not in result
    assert nested not in result


def test_remove_empty_folders_deletes_in_given_order(tmp_path):
    empty_parent = tmp_path / "empty_parent"
    empty_child = empty_parent / "empty_child"
    empty_child.mkdir(parents=True)

    remove_empty_folders([empty_child, empty_parent])

    assert not empty_parent.exists()


def test_remove_empty_folders_raises_if_folder_not_actually_empty(tmp_path):
    folder = tmp_path / "not_empty"
    folder.mkdir()
    (folder / "file.txt").write_text("oops")

    with pytest.raises(OSError):
        remove_empty_folders([folder])
