"""M10: 흔들림/눈감음 임계값 미달 사진(C컷)을 판정해 이동하는 탭.

스코어링(사진마다 ~100ms대, 장 수가 많으면 분 단위)과 임계값 재분류(즉시 끝남)를
분리해뒀다 — 미리보기 버튼으로 한 번 스코어링해두면, 그 뒤로 임계값(민감도)
스핀박스를 바꿀 때마다 사진을 다시 읽지 않고 즉시 재분류해 결과가 갱신된다.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from badcut import BadCutThresholds, classify_badcut, score_for_badcut
from file_ops import FileOpResult, apply_selection
from gui_format import format_apply_summary, format_badcut_preview
from report import ReportRow
from scanner import PhotoMetadata, scan_and_extract
from scoring import PhotoScore


class ScoreWorker(QThread):
    progress = Signal(int, int)
    finished_ok = Signal(list, list)  # list[PhotoMetadata], list[PhotoScore]
    failed = Signal(str)

    def __init__(self, input_dir: Path, recursive: bool) -> None:
        super().__init__()
        self._input_dir = input_dir
        self._recursive = recursive

    def run(self) -> None:
        try:
            photos = scan_and_extract(self._input_dir, recursive=self._recursive)
            scores = score_for_badcut(photos, on_progress=self.progress.emit)
            self.finished_ok.emit(photos, scores)
        except Exception as e:  # noqa: BLE001 - surfaced to the user, not swallowed
            self.failed.emit(str(e))


class ApplyWorker(QThread):
    progress = Signal(int, int)
    finished_ok = Signal(list)  # list[FileOpResult]
    failed = Signal(str)

    def __init__(self, rows: list[ReportRow], output_dir: Path) -> None:
        super().__init__()
        self._rows = rows
        self._output_dir = output_dir

    def run(self) -> None:
        try:
            results = apply_selection(
                self._rows, self._output_dir, move=True, on_progress=self.progress.emit
            )
            self.finished_ok.emit(results)
        except Exception as e:  # noqa: BLE001 - surfaced to the user, not swallowed
            self.failed.emit(str(e))


class BadCutTab(QWidget):
    def __init__(self) -> None:
        super().__init__()

        self._input_dir: Path | None = None
        self._output_dir: Path | None = None
        self._photos: list[PhotoMetadata] | None = None
        self._scores: list[PhotoScore] | None = None
        self._rows: list[ReportRow] | None = None
        self._score_worker: ScoreWorker | None = None
        self._apply_worker: ApplyWorker | None = None
        self._busy = False

        self._input_label = QLabel("입력 폴더: (선택 안 됨)")
        input_button = QPushButton("입력 폴더 선택...")
        input_button.clicked.connect(self._choose_input_dir)

        self._output_label = QLabel("출력 폴더: (선택 안 됨)")
        output_button = QPushButton("출력 폴더 선택...")
        output_button.clicked.connect(self._choose_output_dir)

        self._recursive_checkbox = QCheckBox("하위 폴더까지 포함")

        self._min_sharpness_spin = QDoubleSpinBox()
        self._min_sharpness_spin.setRange(0.0, 1_000_000.0)
        self._min_sharpness_spin.setDecimals(1)
        self._min_sharpness_spin.setSingleStep(10.0)
        self._min_sharpness_spin.setToolTip(
            "선명도 점수(라플라시안 분산)가 이 값 미만이면 블러로 판정. "
            "한 번 미리보기(스코어링)한 뒤에는 이 값을 바꿀 때마다 다시 스캔하지 "
            "않고 즉시 재판정합니다 — 민감도를 마음껏 올렸다 내렸다 해보세요."
        )
        self._min_sharpness_spin.valueChanged.connect(self._on_threshold_changed)

        self._min_eyes_open_spin = QDoubleSpinBox()
        self._min_eyes_open_spin.setRange(0.0, 1.0)
        self._min_eyes_open_spin.setDecimals(2)
        self._min_eyes_open_spin.setSingleStep(0.05)
        self._min_eyes_open_spin.setToolTip(
            "눈 뜬 정도(0~1) 점수가 이 값 미만이면 눈감음으로 판정. 얼굴이 없는 사진엔 적용 안 됨. "
            "선명도 임계값과 마찬가지로 재스코어링 없이 즉시 재판정됩니다."
        )
        self._min_eyes_open_spin.valueChanged.connect(self._on_threshold_changed)

        threshold_form = QFormLayout()
        threshold_form.addRow("선명도 임계값 (미만이면 블러):", self._min_sharpness_spin)
        threshold_form.addRow("눈뜸 임계값 (미만이면 눈감음, 0~1):", self._min_eyes_open_spin)

        self._preview_button = QPushButton("미리보기")
        self._preview_button.clicked.connect(self._run_preview)

        self._apply_button = QPushButton("적용 (이동)")
        self._apply_button.setEnabled(False)
        self._apply_button.clicked.connect(self._run_apply)

        self._progress_bar = QProgressBar()
        self._summary_text = QPlainTextEdit()
        self._summary_text.setReadOnly(True)

        button_row = QHBoxLayout()
        button_row.addWidget(self._preview_button)
        button_row.addWidget(self._apply_button)

        layout = QVBoxLayout()
        layout.addWidget(self._input_label)
        layout.addWidget(input_button)
        layout.addWidget(self._output_label)
        layout.addWidget(output_button)
        layout.addWidget(self._recursive_checkbox)
        layout.addLayout(threshold_form)
        layout.addLayout(button_row)
        layout.addWidget(self._progress_bar)
        layout.addWidget(self._summary_text)
        self.setLayout(layout)

    @property
    def is_busy(self) -> bool:
        return self._busy

    def _choose_input_dir(self) -> None:
        directory = QFileDialog.getExistingDirectory(self, "입력 폴더 선택")
        if directory:
            self._input_dir = Path(directory)
            self._input_label.setText(f"입력 폴더: {directory}")
            self._invalidate_preview()

    def _choose_output_dir(self) -> None:
        directory = QFileDialog.getExistingDirectory(self, "C컷을 옮길 출력 폴더 선택")
        if directory:
            self._output_dir = Path(directory)
            self._output_label.setText(f"출력 폴더: {directory}")
            self._invalidate_preview()

    def _invalidate_preview(self) -> None:
        self._photos = None
        self._scores = None
        self._rows = None
        self._apply_button.setEnabled(False)

    def _run_preview(self) -> None:
        if self._busy:
            QMessageBox.warning(
                self, "작업 진행 중", "다른 작업이 진행 중입니다. 완료될 때까지 기다려주세요."
            )
            return

        if self._input_dir is None or not self._input_dir.is_dir():
            QMessageBox.warning(self, "입력 폴더 없음", "먼저 입력 폴더를 선택하세요.")
            return

        self._busy = True
        self._preview_button.setEnabled(False)
        self._progress_bar.setValue(0)
        self._summary_text.setPlainText("스캔/스코어링 중... (한 번만 하면 이후 임계값 조정은 즉시 반영됩니다)")

        self._score_worker = ScoreWorker(self._input_dir, self._recursive_checkbox.isChecked())
        self._score_worker.progress.connect(self._on_progress)
        self._score_worker.finished_ok.connect(self._on_scored)
        self._score_worker.failed.connect(self._on_error)
        self._score_worker.start()

    def _on_scored(self, photos: list[PhotoMetadata], scores: list[PhotoScore]) -> None:
        self._busy = False
        self._photos = photos
        self._scores = scores
        self._preview_button.setEnabled(True)
        self._reclassify()

    def _on_threshold_changed(self) -> None:
        # 아직 스코어링 전이면(입력 폴더를 막 바꿨거나 미리보기 전) 할 일이 없다 —
        # 미리보기를 눌러야 점수가 생기고, 그 뒤부터 이 핸들러가 즉시 재판정한다.
        if self._scores is not None:
            self._reclassify()

    def _reclassify(self) -> None:
        thresholds = BadCutThresholds(
            min_sharpness=self._min_sharpness_spin.value(),
            min_eyes_open=self._min_eyes_open_spin.value(),
        )
        rows = classify_badcut(self._photos, self._scores, thresholds)
        self._rows = rows
        bad_count = sum(1 for r in rows if r.selected)
        self._apply_button.setEnabled(bad_count > 0 and self._output_dir is not None)
        self._summary_text.setPlainText(format_badcut_preview(rows))

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

        bad_count = sum(1 for r in self._rows if r.selected)
        confirm = QMessageBox.question(
            self,
            "적용 확인",
            f"C컷으로 판정된 {bad_count}장(RAW 포함)을 {self._output_dir}(으)로 "
            "이동합니다 (복사 아님, 원본 위치엔 남지 않음).\n계속하시겠습니까?",
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return

        self._busy = True
        self._apply_button.setEnabled(False)
        self._progress_bar.setValue(0)

        self._apply_worker = ApplyWorker(self._rows, self._output_dir)
        self._apply_worker.progress.connect(self._on_progress)
        self._apply_worker.finished_ok.connect(self._on_apply_done)
        self._apply_worker.failed.connect(self._on_error)
        self._apply_worker.start()

    def _on_apply_done(self, results: list[FileOpResult]) -> None:
        self._busy = False
        self._apply_button.setEnabled(False)
        # 이동된 파일은 더 이상 입력 폴더에 없으므로 캐시된 점수가 낡았다 —
        # 다시 정리하려면 미리보기를 새로 눌러야 한다.
        self._invalidate_preview()
        self._summary_text.setPlainText(format_apply_summary(results, self._output_dir))

    def _on_progress(self, done: int, total: int) -> None:
        self._progress_bar.setMaximum(total)
        self._progress_bar.setValue(done)

    def _on_error(self, message: str) -> None:
        self._busy = False
        self._preview_button.setEnabled(True)
        bad_count = sum(1 for r in (self._rows or []) if r.selected)
        self._apply_button.setEnabled(bad_count > 0 and self._output_dir is not None)
        QMessageBox.critical(self, "오류", message)
