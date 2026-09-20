from PySide6.QtCore import QSettings

from gui_settings import load_folder, load_folder_list, save_folder, save_folder_list


def _settings(tmp_path) -> QSettings:
    return QSettings(str(tmp_path / "test_settings.ini"), QSettings.Format.IniFormat)


def test_save_and_load_folder_list_round_trip(tmp_path):
    settings = _settings(tmp_path)
    folder_a = tmp_path / "a"
    folder_b = tmp_path / "b"
    folder_a.mkdir()
    folder_b.mkdir()

    save_folder_list(settings, "test/dirs", [folder_a, folder_b])
    settings.sync()

    assert load_folder_list(settings, "test/dirs") == [folder_a, folder_b]


def test_save_and_load_single_item_folder_list_round_trip(tmp_path):
    # QSettings는 1개짜리 리스트를 문자열로 돌려주는 경우가 있어 별도로 검증한다.
    settings = _settings(tmp_path)
    folder = tmp_path / "a"
    folder.mkdir()

    save_folder_list(settings, "test/dirs", [folder])
    settings.sync()

    assert load_folder_list(settings, "test/dirs") == [folder]


def test_load_folder_list_filters_out_missing_paths(tmp_path):
    settings = _settings(tmp_path)
    existing = tmp_path / "exists"
    existing.mkdir()
    missing = tmp_path / "missing"

    save_folder_list(settings, "test/dirs", [existing, missing])
    settings.sync()

    assert load_folder_list(settings, "test/dirs") == [existing]


def test_load_folder_list_returns_empty_when_key_unset(tmp_path):
    settings = _settings(tmp_path)

    assert load_folder_list(settings, "test/unset") == []


def test_save_and_load_folder_round_trip(tmp_path):
    settings = _settings(tmp_path)
    folder = tmp_path / "a"
    folder.mkdir()

    save_folder(settings, "test/dir", folder)
    settings.sync()

    assert load_folder(settings, "test/dir") == folder


def test_load_folder_returns_none_when_missing_on_disk(tmp_path):
    settings = _settings(tmp_path)
    missing = tmp_path / "missing"

    save_folder(settings, "test/dir", missing)
    settings.sync()

    assert load_folder(settings, "test/dir") is None


def test_load_folder_returns_none_when_unset(tmp_path):
    settings = _settings(tmp_path)

    assert load_folder(settings, "test/unset") is None
