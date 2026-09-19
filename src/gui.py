"""M8/M9/M10: FrameSense 데스크톱 GUI. 탭마다 독립된 기능을 얇게 얹는 컨테이너.

베스트컷 선별(M8) / 시간순 리네임(M9) / C컷 이동(M10) 세 기능은 서로 다른
워크플로라 한 화면에 섞지 않고 QTabWidget 탭으로 분리한다. 각 탭의 실제 로직은
gui_bestcut_tab.py / gui_rename_tab.py / gui_badcut_tab.py에 있다.
"""

from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication, QMainWindow, QMessageBox, QTabWidget

from gui_badcut_tab import BadCutTab
from gui_bestcut_tab import BestCutTab
from gui_rename_tab import RenameTab


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("FrameSense")
        self.resize(640, 560)

        self._best_cut_tab = BestCutTab()
        self._rename_tab = RenameTab()
        self._bad_cut_tab = BadCutTab()

        tabs = QTabWidget()
        tabs.addTab(self._best_cut_tab, "베스트컷 선별")
        tabs.addTab(self._rename_tab, "시간순 리네임")
        tabs.addTab(self._bad_cut_tab, "C컷 정리")
        self.setCentralWidget(tabs)

    def closeEvent(self, event) -> None:  # noqa: N802 - Qt override signature
        busy_tabs = [
            tab
            for tab in (self._best_cut_tab, self._rename_tab, self._bad_cut_tab)
            if tab.is_busy
        ]
        if busy_tabs:
            QMessageBox.warning(
                self,
                "작업 진행 중",
                "다른 작업이 진행 중입니다. 완료된 후 다시 닫아주세요.",
            )
            event.ignore()
            return
        event.accept()


def main() -> None:
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
