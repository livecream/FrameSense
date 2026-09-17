import datetime

from grouping import group_by_time_gap
from scanner import PhotoMetadata


def _meta(seconds_offset: int) -> PhotoMetadata:
    base = datetime.datetime(2026, 6, 1, 14, 0, 0)
    dt = base + datetime.timedelta(seconds=seconds_offset)
    return PhotoMetadata(
        path=f"/fake/{seconds_offset}.jpg",
        datetime_original=dt,
        exif_source="exif",
    )


def test_empty_input_returns_no_groups():
    assert group_by_time_gap([]) == []


def test_single_photo_is_its_own_group():
    photos = [_meta(0)]

    groups = group_by_time_gap(photos)

    assert groups == [[photos[0]]]


def test_photos_within_gap_join_same_scene():
    photos = [_meta(0), _meta(2)]

    groups = group_by_time_gap(photos, gap_seconds=3)

    assert groups == [[photos[0], photos[1]]]


def test_photo_exactly_at_gap_boundary_joins_same_scene():
    photos = [_meta(0), _meta(3)]

    groups = group_by_time_gap(photos, gap_seconds=3)

    assert groups == [[photos[0], photos[1]]]


def test_photo_beyond_gap_starts_new_scene():
    photos = [_meta(0), _meta(4)]

    groups = group_by_time_gap(photos, gap_seconds=3)

    assert groups == [[photos[0]], [photos[1]]]


def test_multiple_scenes_are_split_correctly():
    photos = [_meta(0), _meta(2), _meta(10), _meta(11)]

    groups = group_by_time_gap(photos, gap_seconds=3)

    assert groups == [[photos[0], photos[1]], [photos[2], photos[3]]]


def test_default_gap_is_three_seconds():
    photos = [_meta(0), _meta(3), _meta(7)]

    groups = group_by_time_gap(photos)

    assert groups == [[photos[0], photos[1]], [photos[2]]]
