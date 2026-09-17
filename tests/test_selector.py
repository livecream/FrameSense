import datetime

import numpy as np
import pytest
from PIL import Image, ImageFilter

from scanner import PhotoMetadata
from selector import _normalize, select_best


def _make_checkerboard(path, size=64, block=4):
    arr = (np.indices((size, size)).sum(axis=0) // block % 2 * 255).astype("uint8")
    Image.fromarray(arr).convert("RGB").save(path, "png")
    return path


def _make_blurred_checkerboard(path, size=64, block=4):
    arr = (np.indices((size, size)).sum(axis=0) // block % 2 * 255).astype("uint8")
    img = Image.fromarray(arr).convert("RGB").filter(ImageFilter.GaussianBlur(radius=5))
    img.save(path, "png")
    return path


def _make_flat(path, size=64, color=128):
    Image.new("RGB", (size, size), (color, color, color)).save(path, "png")
    return path


def _meta(path, seconds_offset=0):
    base = datetime.datetime(2026, 6, 1, 14, 0, 0)
    return PhotoMetadata(
        path=path,
        datetime_original=base + datetime.timedelta(seconds=seconds_offset),
        exif_source="exif",
    )


def test_normalize_scales_values_to_zero_one_range():
    assert _normalize([10.0, 20.0, 30.0]) == [0.0, 0.5, 1.0]


def test_normalize_returns_all_ones_when_all_values_equal():
    assert _normalize([5.0, 5.0, 5.0]) == [1.0, 1.0, 1.0]


def test_select_best_picks_the_sharper_photo(tmp_path):
    sharp_path = _make_checkerboard(tmp_path / "sharp.png")
    blurred_path = _make_blurred_checkerboard(tmp_path / "blurred.png")
    scene = [_meta(blurred_path, 0), _meta(sharp_path, 1)]

    selection = select_best(scene)

    assert selection.best.path == sharp_path


def test_select_best_breaks_ties_by_earliest_photo(tmp_path):
    p1 = _make_flat(tmp_path / "a.png")
    p2 = _make_flat(tmp_path / "b.png")
    scene = [_meta(p1, 0), _meta(p2, 1)]

    selection = select_best(scene)

    assert selection.best.path == p1


def test_select_best_raises_on_empty_scene():
    with pytest.raises(ValueError):
        select_best([])
