"""사진 파일 정리 탭 컨테이너: 시간순 정렬(M9)과 폴더 정리(M11)를 하위 탭으로 묶는다."""

from __future__ import annotations

from PySide6.QtWidgets import QTabWidget

from gui_organize_tab import OrganizeTab
from gui_rename_tab import RenameTab


class FileOrganizeTab(QTabWidget):
    def __init__(self) -> None:
        super().__init__()

        self._rename_tab = RenameTab()
        self._organize_tab = OrganizeTab()

        self.addTab(self._rename_tab, "시간순 정렬")
        self.addTab(self._organize_tab, "폴더 정리")

    @property
    def is_busy(self) -> bool:
        return self._rename_tab.is_busy or self._organize_tab.is_busy
