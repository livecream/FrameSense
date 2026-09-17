import numpy as np
import pytest
from PIL import Image, ImageFilter

from scanner import PhotoMetadata
from scoring import (
    _eyes_open_from_scores,
    exposure_score,
    face_score,
    score_photo,
    score_photos,
    sharpness_score,
)


def _make_checkerboard(path, size=64, block=4):
    arr = (np.indices((size, size)).sum(axis=0) // block % 2 * 255).astype("uint8")
    Image.fromarray(arr).convert("RGB").save(path, "png")
    return path


def _make_flat(path, size=64, color=128):
    Image.new("RGB", (size, size), (color, color, color)).save(path, "png")
    return path


def _make_blurred_checkerboard(path, size=64, block=4):
    arr = (np.indices((size, size)).sum(axis=0) // block % 2 * 255).astype("uint8")
    img = Image.fromarray(arr).convert("RGB").filter(ImageFilter.GaussianBlur(radius=5))
    img.save(path, "png")
    return path


def test_exposure_score_is_perfect_for_mid_gray_image(tmp_path):
    path = _make_flat(tmp_path / "mid.png", color=128)

    assert exposure_score(path) == 1.0


def test_exposure_score_is_zero_for_pure_black_image(tmp_path):
    path = _make_flat(tmp_path / "black.png", color=0)

    assert exposure_score(path) == 0.0


def test_exposure_score_is_zero_for_pure_white_image(tmp_path):
    path = _make_flat(tmp_path / "white.png", color=255)

    assert exposure_score(path) == 0.0


def test_exposure_score_reflects_partial_clipping(tmp_path):
    size = 64
    arr = np.zeros((size, size), dtype="uint8")
    arr[: size // 2] = 0  # 절반 완전 검정(클리핑)
    arr[size // 2 :] = 128  # 절반 중간 밝기(클리핑 아님)
    path = tmp_path / "half_clipped.png"
    Image.fromarray(arr).convert("RGB").save(path, "png")

    assert exposure_score(path) == pytest.approx(0.5)


def test_eyes_open_from_scores_fully_open_when_no_blink():
    assert _eyes_open_from_scores(blink_left=0.0, blink_right=0.0) == 1.0


def test_eyes_open_from_scores_fully_closed_when_either_eye_blinks():
    assert _eyes_open_from_scores(blink_left=1.0, blink_right=0.0) == 0.0
    assert _eyes_open_from_scores(blink_left=0.0, blink_right=1.0) == 0.0


def test_eyes_open_from_scores_takes_worst_eye():
    assert _eyes_open_from_scores(blink_left=0.3, blink_right=0.7) == pytest.approx(0.3)


def test_face_score_is_none_when_no_face_detected(tmp_path):
    path = _make_flat(tmp_path / "no_face.png")

    assert face_score(path) is None


def test_sharpness_score_is_zero_for_flat_image(tmp_path):
    path = _make_flat(tmp_path / "flat.png")

    assert sharpness_score(path) == 0.0


def test_sharpness_score_higher_for_sharp_than_blurred(tmp_path):
    sharp = _make_checkerboard(tmp_path / "sharp.png")
    blurred = _make_blurred_checkerboard(tmp_path / "blurred.png")

    assert sharpness_score(sharp) > sharpness_score(blurred)


def test_score_photo_uses_sharpness_as_total(tmp_path):
    path = _make_checkerboard(tmp_path / "sharp.png")
    meta = PhotoMetadata(path=path, datetime_original=None, exif_source="exif")

    result = score_photo(meta)

    assert result.path == path
    assert result.sharpness > 0
    assert result.total == result.sharpness
    assert result.error is None


def test_score_photo_propagates_existing_metadata_error(tmp_path):
    path = tmp_path / "broken.png"
    path.write_bytes(b"not a real image")
    meta = PhotoMetadata(
        path=path,
        datetime_original=None,
        exif_source="mtime",
        error="이미지를 열 수 없음",
    )

    result = score_photo(meta)

    assert result.total == 0.0
    assert result.error == "이미지를 열 수 없음"


def test_score_photo_reports_error_when_scoring_itself_fails(tmp_path):
    path = tmp_path / "broken.png"
    path.write_bytes(b"not a real image")
    meta = PhotoMetadata(path=path, datetime_original=None, exif_source="mtime")

    result = score_photo(meta)

    assert result.total == 0.0
    assert result.error is not None


def test_score_photos_scores_each_photo(tmp_path):
    p1 = _make_checkerboard(tmp_path / "a.png")
    p2 = _make_flat(tmp_path / "b.png")
    metas = [
        PhotoMetadata(path=p1, datetime_original=None, exif_source="exif"),
        PhotoMetadata(path=p2, datetime_original=None, exif_source="exif"),
    ]

    results = score_photos(metas)

    assert [r.path for r in results] == [p1, p2]
