"""M8: 베스트컷(A컷) 선별 탭. gui.py에서 분리해 QTabWidget의 탭 하나로 얹는다."""

from __future__ import annotations

import subprocess
from pathlib import Path

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)

from file_ops import FileOpResult, apply_selection
from grouping import group_by_time_gap
from gui_format import format_apply_summary, format_preview_summary
from report import ReportRow, build_report
from scanner import scan_and_extract_many


class PreviewWorker(QThread):
    progress = Signal(int, int)
    finished_ok = Signal(list)  # list[ReportRow]
    failed = Signal(str)

    def __init__(self, input_dirs: list[Path], recursive: bool = True) -> None:
        super().__init__()
        self._input_dirs = input_dirs
        self._recursive = recursive

    def run(self) -> None:
        try:
            photos = scan_and_extract_many(self._input_dirs, recursive=self._recursive)
            groups = group_by_time_gap(photos)
            rows = build_report(groups, on_progress=self.progress.emit)
            self.finished_ok.emit(rows)
        except Exception as e:  # noqa: BLE001 - surfaced to the user, not swallowed
            self.failed.emit(str(e))


class ApplyWorker(QThread):
    progress = Signal(int, int)
    finished_ok = Signal(list)  # list[FileOpResult]
    failed = Signal(str)

    def __init__(self, rows: list[ReportRow], output_dir: Path, move: bool) -> None:
        super().__init__()
        self._rows = rows
        self._output_dir = output_dir
        self._move = move

    def run(self) -> None:
        try:
            results = apply_selection(
                self._rows,
                self._output_dir,
                move=self._move,
                on_progress=self.progress.emit,
            )
            self.finished_ok.emit(results)
        except Exception as e:  # noqa: BLE001 - surfaced to the user, not swallowed
            self.failed.emit(str(e))


class BestCutTab(QWidget):
    def __init__(self) -> None:
        super().__init__()

        self._input_dirs: list[Path] = []
        self._output_dir: Path | None = None
        self._rows: list[ReportRow] | None = None
        self._preview_worker: PreviewWorker | None = None
        self._apply_worker: ApplyWorker | None = None
        self._busy = False

        self._folder_list = QListWidget()
        add_input_button = QPushButton("입력 폴더 추가...")
        add_input_button.clicked.connect(self._add_input_dir)
        remove_input_button = QPushButton("선택 삭제")
        remove_input_button.clicked.connect(self._remove_selected_input_dir)

        self._output_label = QLabel("출력 폴더: (선택 안 됨)")
        output_button = QPushButton("출력 폴더 선택...")
        output_button.clicked.connect(self._choose_output_dir)

        self._copy_radio = QRadioButton("복사 (기본)")
        self._copy_radio.setChecked(True)
        self._move_radio = QRadioButton("이동")

        self._preview_button = QPushButton("미리보기")
        self._preview_button.clicked.connect(self._run_preview)

        self._apply_button = QPushButton("적용")
        self._apply_button.setEnabled(False)
        self._apply_button.clicked.connect(self._run_apply)

        self._open_output_button = QPushButton("출력 폴더 열기")
        self._open_output_button.setEnabled(False)
        self._open_output_button.clicked.connect(self._open_output_folder)

        self._progress_bar = QProgressBar()
        self._summary_text = QPlainTextEdit()
        self._summary_text.setReadOnly(True)

        radio_row = QHBoxLayout()
        radio_row.addWidget(self._copy_radio)
        radio_row.addWidget(self._move_radio)

        input_button_row = QHBoxLayout()
        input_button_row.addWidget(add_input_button)
        input_button_row.addWidget(remove_input_button)

        button_row = QHBoxLayout()
        button_row.addWidget(self._preview_button)
        button_row.addWidget(self._apply_button)
        button_row.addWidget(self._open_output_button)

        layout = QVBoxLayout()
        layout.addWidget(QLabel("입력 폴더 (여러 개 추가 가능):"))
        layout.addWidget(self._folder_list)
        layout.addLayout(input_button_row)
        layout.addWidget(self._output_label)
        layout.addWidget(output_button)
        layout.addLayout(radio_row)
        layout.addLayout(button_row)
        layout.addWidget(self._progress_bar)
        layout.addWidget(self._summary_text)
        self.setLayout(layout)

    @property
    def is_busy(self) -> bool:
        return self._busy

    def _add_input_dir(self) -> None:
        directory = QFileDialog.getExistingDirectory(self, "입력 폴더 추가")
        if directory and Path(directory) not in self._input_dirs:
            self._input_dirs.append(Path(directory))
            self._folder_list.addItem(directory)
            self._invalidate_preview()

    def _remove_selected_input_dir(self) -> None:
        for item in self._folder_list.selectedItems():
            index = self._folder_list.row(item)
            self._folder_list.takeItem(index)
            del self._input_dirs[index]
        self._invalidate_preview()

    def _choose_output_dir(self) -> None:
        directory = QFileDialog.getExistingDirectory(self, "출력 폴더 선택")
        if directory:
            self._output_dir = Path(directory)
            self._output_label.setText(f"출력 폴더: {directory}")
            self._invalidate_preview()

    def _invalidate_preview(self) -> None:
        self._rows = None
        self._apply_button.setEnabled(False)
        self._open_output_button.setEnabled(False)

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
        self._progress_bar.setValue(0)
        self._summary_text.setPlainText("스캔/스코어링 중...")

        self._preview_worker = PreviewWorker(list(self._input_dirs))
        self._preview_worker.progress.connect(self._on_progress)
        self._preview_worker.finished_ok.connect(self._on_preview_done)
        self._preview_worker.failed.connect(self._on_error)
        self._preview_worker.start()

    def _on_preview_done(self, rows: list[ReportRow]) -> None:
        self._busy = False
        self._rows = rows
        self._preview_button.setEnabled(True)
        self._apply_button.setEnabled(bool(rows) and self._output_dir is not None)
        self._summary_text.setPlainText(format_preview_summary(rows))

    def _run_apply(self) -> None:
        if self._busy:
            QMessageBox.warning(
                self, "작업 진행 중", "다른 작업이 진행 중입니다. 완료될 때까지 기다려주세요."
            )
            return

        if not self._rows:
            QMessageBox.warning(self, "미리보기 필요", "먼저 미리보기를 실행하세요.")
            return

        if self._output_dir is None:
            QMessageBox.warning(self, "출력 폴더 없음", "출력 폴더를 먼저 선택하세요.")
            return

        move = self._move_radio.isChecked()
        verb = "이동" if move else "복사"
        confirm = QMessageBox.question(
            self,
            "적용 확인",
            f"선택된 사진을 {self._output_dir}(으)로 {verb}하시겠습니까?",
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return

        self._busy = True
        self._apply_button.setEnabled(False)
        self._progress_bar.setValue(0)

        self._apply_worker = ApplyWorker(self._rows, self._output_dir, move)
        self._apply_worker.progress.connect(self._on_progress)
        self._apply_worker.finished_ok.connect(self._on_apply_done)
        self._apply_worker.failed.connect(self._on_error)
        self._apply_worker.start()

    def _on_apply_done(self, results: list[FileOpResult]) -> None:
        self._busy = False
        self._apply_button.setEnabled(True)
        self._open_output_button.setEnabled(True)
        self._summary_text.setPlainText(
            format_apply_summary(results, self._output_dir)
        )

    def _open_output_folder(self) -> None:
        if self._output_dir is not None:
            result = subprocess.run(["open", str(self._output_dir)])
            if result.returncode != 0:
                QMessageBox.warning(
                    self,
                    "폴더 열기 실패",
                    f"출력 폴더를 열지 못했습니다: {self._output_dir}",
                )

    def _on_progress(self, done: int, total: int) -> None:
        self._progress_bar.setMaximum(total)
        self._progress_bar.setValue(done)

    def _on_error(self, message: str) -> None:
        self._busy = False
        self._preview_button.setEnabled(True)
        self._apply_button.setEnabled(bool(self._rows) and self._output_dir is not None)
        QMessageBox.critical(self, "오류", message)
