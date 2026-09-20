"""드래그앤드롭으로 떨어뜨린 항목 중 실제 존재하는 폴더 경로만 걸러내는
공용 헬퍼. 여러 탭의 dragEnterEvent/dropEvent에서 재사용한다."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QMimeData


def extract_dropped_folders(mime_data: QMimeData) -> list[Path]:
    """mime_data에 담긴 로컬 파일 URL 중 실제 폴더인 것만 반환한다."""
    if not mime_data.hasUrls():
        return []
    paths = [Path(url.toLocalFile()) for url in mime_data.urls() if url.isLocalFile()]
    return [p for p in paths if p.is_dir()]
