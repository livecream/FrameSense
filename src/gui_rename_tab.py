"""M9: 여러 바디 사진을 촬영 시각순으로 정렬해 00001부터 제자리 리네임하는 탭."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from gui_format import format_rename_apply_summary, format_rename_preview
from rename_by_time import RenamePlanRow, RenameResult, apply_rename_plan, build_rename_plan


class PlanWorker(QThread):
    finished_ok = Signal(list)  # list[RenamePlanRow]
    failed = Signal(str)

    def __init__(self, input_dirs: list[Path], recursive: bool) -> None:
        super().__init__()
        self._input_dirs = input_dirs
        self._recursive = recursive

    def run(self) -> None:
        try:
            rows = build_rename_plan(self._input_dirs, recursive=self._recursive)
            self.finished_ok.emit(rows)
        except Exception as e:  # noqa: BLE001 - surfaced to the user, not swallowed
            self.failed.emit(str(e))


class ApplyWorker(QThread):
    progress = Signal(int, int)
    finished_ok = Signal(list)  # list[RenameResult]
    failed = Signal(str)

    def __init__(self, rows: list[RenamePlanRow], log_dir: Path) -> None:
        super().__init__()
        self._rows = rows
        self._log_dir = log_dir

    def run(self) -> None:
        try:
            results = apply_rename_plan(
                self._rows, log_dir=self._log_dir, on_progress=self.progress.emit
            )
            self.finished_ok.emit(results)
        except Exception as e:  # noqa: BLE001 - surfaced to the user, not swallowed
            self.failed.emit(str(e))


class RenameTab(QWidget):
    def __init__(self) -> None:
        super().__init__()

        self._input_dirs: list[Path] = []
        self._rows: list[RenamePlanRow] | None = None
        self._plan_worker: PlanWorker | None = None
        self._apply_worker: ApplyWorker | None = None
        self._busy = False

        self._folder_list = QListWidget()
        add_button = QPushButton("폴더 추가...")
        add_button.clicked.connect(self._add_folder)
        remove_button = QPushButton("선택 삭제")
        remove_button.clicked.connect(self._remove_selected_folder)

        self._recursive_checkbox = QCheckBox("하위 폴더까지 포함")

        self._preview_button = QPushButton("미리보기")
        self._preview_button.clicked.connect(self._run_preview)

        self._apply_button = QPushButton("적용 (제자리 리네임)")
        self._apply_button.setEnabled(False)
        self._apply_button.clicked.connect(self._run_apply)

        self._progress_bar = QProgressBar()
        self._summary_text = QPlainTextEdit()
        self._summary_text.setReadOnly(True)

        folder_button_row = QHBoxLayout()
        folder_button_row.addWidget(add_button)
        folder_button_row.addWidget(remove_button)

        button_row = QHBoxLayout()
        button_row.addWidget(self._preview_button)
        button_row.addWidget(self._apply_button)

        layout = QVBoxLayout()
        layout.addWidget(QLabel("입력 폴더 (바디별로 여러 개 추가 가능, 사진+영상 함께 정렬):"))
        layout.addWidget(self._folder_list)
        layout.addLayout(folder_button_row)
        layout.addWidget(self._recursive_checkbox)
        layout.addLayout(button_row)
        layout.addWidget(self._progress_bar)
        layout.addWidget(self._summary_text)
        self.setLayout(layout)

    @property
    def is_busy(self) -> bool:
        return self._busy

    def _add_folder(self) -> None:
        directory = QFileDialog.getExistingDirectory(self, "입력 폴더 추가")
        if directory and Path(directory) not in self._input_dirs:
            self._input_dirs.append(Path(directory))
            self._folder_list.addItem(directory)
            self._invalidate_preview()

    def _remove_selected_folder(self) -> None:
        for item in self._folder_list.selectedItems():
            index = self._folder_list.row(item)
            self._folder_list.takeItem(index)
            del self._input_dirs[index]
        self._invalidate_preview()

    def _invalidate_preview(self) -> None:
        self._rows = None
        self._apply_button.setEnabled(False)

    def _run_preview(self) -> None:
        if self._busy:
            QMessageBox.warning(
                self, "작업 진행 중", "다른 작업이 진행 중입니다. 완료될 때까지 기다려주세요."
            )
            return

        if not self._input_dirs:
            QMessageBox.warning(self, "입력 폴더 없음", "먼저 입력 폴더를 하나 이상 추가하세요.")
            return

        self._busy = True
        self._preview_button.setEnabled(False)
        self._summary_text.setPlainText("스캔 중...")

        self._plan_worker = PlanWorker(list(self._input_dirs), self._recursive_checkbox.isChecked())
        self._plan_worker.finished_ok.connect(self._on_preview_done)
        self._plan_worker.failed.connect(self._on_error)
        self._plan_worker.start()

    def _on_preview_done(self, rows: list[RenamePlanRow]) -> None:
        self._busy = False
        self._rows = rows
        self._preview_button.setEnabled(True)
        self._apply_button.setEnabled(bool(rows))
        self._summary_text.setPlainText(format_rename_preview(rows))

    def _run_apply(self) -> None:
        if self._busy:
            QMessageBox.warning(
                self, "작업 진행 중", "다른 작업이 진행 중입니다. 완료될 때까지 기다려주세요."
            )
            return

        if not self._rows:
            QMessageBox.warning(self, "미리보기 필요", "먼저 미리보기를 실행하세요.")
            return

        confirm = QMessageBox.question(
            self,
            "적용 확인",
            f"{len(self._rows)}개 파일의 이름을 원본 폴더에서 직접 바꿉니다 "
            "(파일 내용은 그대로, 원래 이름은 되돌릴 수 없음).\n계속하시겠습니까?",
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return

        self._busy = True
        self._apply_button.setEnabled(False)
        self._progress_bar.setValue(0)

        log_dir = self._input_dirs[0]
        self._apply_worker = ApplyWorker(self._rows, log_dir)
        self._apply_worker.progress.connect(self._on_progress)
        self._apply_worker.finished_ok.connect(self._on_apply_done)
        self._apply_worker.failed.connect(self._on_error)
        self._apply_worker.start()

    def _on_apply_done(self, results: list[RenameResult]) -> None:
        self._busy = False
        self._apply_button.setEnabled(True)
        self._summary_text.setPlainText(format_rename_apply_summary(results))
        # 적용 후엔 파일명이 이미 바뀌었으므로 이전 계획으로 다시 적용하면 안 됨.
        self._rows = None
        self._apply_button.setEnabled(False)

    def _on_progress(self, done: int, total: int) -> None:
        self._progress_bar.setMaximum(total)
        self._progress_bar.setValue(done)

    def _on_error(self, message: str) -> None:
        self._busy = False
        self._preview_button.setEnabled(True)
        self._apply_button.setEnabled(bool(self._rows))
        QMessageBox.critical(self, "오류", message)
