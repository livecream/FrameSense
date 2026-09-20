"""사진 선별 탭 컨테이너: 베스트컷 선별(M8)과 C컷 정리(M10)를 하위 탭으로 묶는다."""

from __future__ import annotations

from PySide6.QtWidgets import QTabWidget

from gui_badcut_tab import BadCutTab
from gui_bestcut_tab import BestCutTab


class PhotoSelectionTab(QTabWidget):
    def __init__(self) -> None:
        super().__init__()

        self._best_cut_tab = BestCutTab()
        self._bad_cut_tab = BadCutTab()

        self.addTab(self._best_cut_tab, "베스트컷 선별")
        self.addTab(self._bad_cut_tab, "C컷 정리")

    @property
    def is_busy(self) -> bool:
        return self._best_cut_tab.is_busy or self._bad_cut_tab.is_busy
