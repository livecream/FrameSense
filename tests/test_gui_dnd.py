from PySide6.QtCore import QMimeData, QUrl

from gui_dnd import extract_dropped_folders


def test_extract_dropped_folders_filters_to_existing_dirs(tmp_path):
    folder = tmp_path / "sub"
    folder.mkdir()
    file_path = tmp_path / "a.txt"
    file_path.write_text("hi")

    mime = QMimeData()
    mime.setUrls([QUrl.fromLocalFile(str(folder)), QUrl.fromLocalFile(str(file_path))])

    result = extract_dropped_folders(mime)

    assert result == [folder]


def test_extract_dropped_folders_returns_empty_when_no_urls():
    mime = QMimeData()

    assert extract_dropped_folders(mime) == []


def test_extract_dropped_folders_ignores_nonexistent_paths(tmp_path):
    missing = tmp_path / "does_not_exist"
    mime = QMimeData()
    mime.setUrls([QUrl.fromLocalFile(str(missing))])

    assert extract_dropped_folders(mime) == []
