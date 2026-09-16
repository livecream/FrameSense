import datetime

import piexif
import pytest
from PIL import Image

from scanner import extract_metadata, scan_and_extract, scan_folder


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


def test_scan_folder_filters_supported_extensions(tmp_path):
    _make_jpeg(tmp_path / "a.jpg")
    (tmp_path / "notes.txt").write_text("hello")
    (tmp_path / "raw.cr2").write_bytes(b"fake raw")

    found = scan_folder(tmp_path)

    assert [p.name for p in found] == ["a.jpg"]


def test_scan_folder_recursive(tmp_path):
    sub = tmp_path / "sub"
    sub.mkdir()
    _make_jpeg(tmp_path / "top.jpg")
    _make_jpeg(sub / "nested.jpg")

    assert len(scan_folder(tmp_path, recursive=False)) == 1
    assert len(scan_folder(tmp_path, recursive=True)) == 2


def test_scan_folder_missing_input_raises(tmp_path):
    with pytest.raises(NotADirectoryError):
        scan_folder(tmp_path / "does_not_exist")


def test_extract_metadata_reads_exif_datetime(tmp_path):
    dt = datetime.datetime(2026, 6, 1, 14, 0, 0)
    path = _make_jpeg(tmp_path / "shot.jpg", dt=dt)

    meta = extract_metadata(path)

    assert meta.datetime_original == dt
    assert meta.exif_source == "exif"
    assert meta.width == 32 and meta.height == 24
    assert meta.error is None


def test_extract_metadata_falls_back_to_mtime_without_exif(tmp_path):
    path = _make_jpeg(tmp_path / "no_exif.jpg", dt=None)

    meta = extract_metadata(path)

    assert meta.exif_source == "mtime"
    assert meta.error is None


def test_extract_metadata_reports_error_for_broken_file(tmp_path):
    path = tmp_path / "broken.jpg"
    path.write_bytes(b"not a real image")

    meta = extract_metadata(path)

    assert meta.exif_source == "mtime"
    assert meta.error is not None


def test_scan_and_extract_sorts_by_datetime(tmp_path):
    later = datetime.datetime(2026, 6, 1, 14, 0, 30)
    earlier = datetime.datetime(2026, 6, 1, 14, 0, 0)
    _make_jpeg(tmp_path / "later.jpg", dt=later)
    _make_jpeg(tmp_path / "earlier.jpg", dt=earlier)

    results = scan_and_extract(tmp_path)

    assert [m.path.name for m in results] == ["earlier.jpg", "later.jpg"]
