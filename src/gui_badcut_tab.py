"""M10: 흔들림/눈감음 임계값 미달 사진(C컷)을 판정해 이동하는 탭.

스코어링(사진마다 ~100ms대, 장 수가 많으면 분 단위)과 임계값 재분류(즉시 끝남)를
분리해뒀다 — 미리보기 버튼으로 한 번 스코어링해두면, 그 뒤로 임계값(민감도)
스핀박스를 바꿀 때마다 사진을 다시 읽지 않고 즉시 재분류해 결과가 갱신된다.
"""

from __future__ import annotations

from pathlib import Path

from PIL.ImageQt import ImageQt
from PySide6.QtCore import QSize, Qt, QThread, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from badcut import BadCutThresholds, classify_badcut, score_for_badcut
from file_ops import FileOpResult, apply_selection
from gui_format import format_apply_summary, format_badcut_header
from report import ReportRow
from scanner import PhotoMetadata, scan_and_extract_many
from scoring import PhotoScore
from thumbnails import make_thumbnail
from gui_dnd import extract_dropped_folders
from gui_settings import load_folder, load_folder_list, make_settings, save_folder, save_folder_list


def _percent(done: int, total: int) -> int:
    return int(done / total * 100) if total else 0


class ScoreWorker(QThread):
    progress = Signal(int, int)
    status = Signal(str)
    finished_ok = Signal(list, list)  # list[PhotoMetadata], list[PhotoScore]
    failed = Signal(str)

    def __init__(
        self,
        input_dirs: list[Path],
        recursive: bool,
        scan_cache: dict | None = None,
        score_cache: dict | None = None,
        thumbnail_cache: dict | None = None,
    ) -> None:
        super().__init__()
        self._input_dirs = input_dirs
        self._recursive = recursive
        self._scan_cache = scan_cache
        self._score_cache = score_cache
        self._thumbnail_cache = thumbnail_cache

    def run(self) -> None:
        try:
            def on_scan_progress(done: int, total: int, path: Path) -> None:
                self.progress.emit(done, total)
                self.status.emit(f"스캔 중: {path.name} ({done}/{total}, {_percent(done, total)}%)")

            photos = scan_and_extract_many(
                self._input_dirs,
                recursive=self._recursive,
                on_progress=on_scan_progress,
                cache=self._scan_cache,
            )

            def on_score_progress(done: int, total: int) -> None:
                self.progress.emit(done, total)
                self.status.emit(f"스코어링 중... ({done}/{total}, {_percent(done, total)}%)")

            scores = score_for_badcut(photos, on_progress=on_score_progress, cache=self._score_cache)
            self._generate_thumbnails(photos)
            self.finished_ok.emit(photos, scores)
        except Exception as e:  # noqa: BLE001 - surfaced to the user, not swallowed
            self.failed.emit(str(e))

    def _generate_thumbnails(self, photos: list[PhotoMetadata]) -> None:
        if self._thumbnail_cache is None:
            return
        for meta in photos:
            stat = meta.path.stat()
            key = (stat.st_mtime, stat.st_size)
            cached = self._thumbnail_cache.get(meta.path)
            if cached is not None and cached[:2] == key:
                continue
            self._thumbnail_cache[meta.path] = (*key, make_thumbnail(meta.path))


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

        self._input_dirs: list[Path] = []
        self._output_dir: Path | None = None
        self._photos: list[PhotoMetadata] | None = None
        self._scores: list[PhotoScore] | None = None
        self._rows: list[ReportRow] | None = None
        self._score_worker: ScoreWorker | None = None
        self._apply_worker: ApplyWorker | None = None
        self._busy = False
        # 같은 세션(앱 종료 전까지) 동안 이미 스캔/스코어링한 파일은 다시 처리하지
        # 않도록 재사용하는 인메모리 캐시. (mtime, size)가 바뀐 파일만 다시 계산됨.
        self._scan_cache: dict = {}
        self._score_cache: dict = {}
        self._thumbnail_cache: dict = {}
        self.setAcceptDrops(True)
        self._settings = make_settings()

        self._folder_list = QListWidget()
        add_input_button = QPushButton("입력 폴더 추가...")
        add_input_button.clicked.connect(self._add_input_dir)
        remove_input_button = QPushButton("선택 삭제")
        remove_input_button.clicked.connect(self._remove_selected_input_dir)

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
        self._status_label = QLabel("")
        self._summary_text = QPlainTextEdit()
        self._summary_text.setReadOnly(True)

        self._table = QTableWidget(0, 6)
        self._table.setHorizontalHeaderLabels(["썸네일", "파일명", "판정", "선명도", "눈뜸", "사유"])
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.setIconSize(QSize(64, 64))

        input_button_row = QHBoxLayout()
        input_button_row.addWidget(add_input_button)
        input_button_row.addWidget(remove_input_button)

        button_row = QHBoxLayout()
        button_row.addWidget(self._preview_button)
        button_row.addWidget(self._apply_button)

        layout = QVBoxLayout()
        layout.addWidget(QLabel("입력 폴더 (여러 개 추가 가능):"))
        layout.addWidget(self._folder_list)
        layout.addLayout(input_button_row)
        layout.addWidget(self._output_label)
        layout.addWidget(output_button)
        layout.addWidget(self._recursive_checkbox)
        layout.addLayout(threshold_form)
        layout.addLayout(button_row)
        layout.addWidget(self._progress_bar)
        layout.addWidget(self._status_label)
        layout.addWidget(self._summary_text)
        layout.addWidget(self._table)

        for folder in load_folder_list(self._settings, "badcut/input_dirs"):
            self._input_dirs.append(folder)
            self._folder_list.addItem(str(folder))
        restored_output = load_folder(self._settings, "badcut/output_dir")
        if restored_output is not None:
            self._output_dir = restored_output
            self._output_label.setText(f"출력 폴더: {restored_output}")

        self.setLayout(layout)

    @property
    def is_busy(self) -> bool:
        return self._busy

    def dragEnterEvent(self, event) -> None:  # noqa: N802 - Qt override signature
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event) -> None:  # noqa: N802 - Qt override signature
        folders = extract_dropped_folders(event.mimeData())
        if folders:
            self._add_folders(folders)
        event.acceptProposedAction()

    def _add_input_dir(self) -> None:
        directory = QFileDialog.getExistingDirectory(self, "입력 폴더 추가")
        if directory:
            self._add_folders([Path(directory)])

    def _add_folders(self, folders: list[Path]) -> None:
        for folder in folders:
            if folder not in self._input_dirs:
                self._input_dirs.append(folder)
                self._folder_list.addItem(str(folder))
        self._invalidate_preview()
        save_folder_list(self._settings, "badcut/input_dirs", self._input_dirs)

    def _remove_selected_input_dir(self) -> None:
        for item in self._folder_list.selectedItems():
            index = self._folder_list.row(item)
            self._folder_list.takeItem(index)
            del self._input_dirs[index]
        self._invalidate_preview()
        save_folder_list(self._settings, "badcut/input_dirs", self._input_dirs)

    def _choose_output_dir(self) -> None:
        directory = QFileDialog.getExistingDirectory(self, "C컷을 옮길 출력 폴더 선택")
        if directory:
            self._output_dir = Path(directory)
            self._output_label.setText(f"출력 폴더: {directory}")
            # 미리보기 결과(스캔/스코어링)는 출력 폴더와 무관하므로 다시 계산할
            # 필요 없음 — 적용 버튼 활성화 여부만 갱신한다.
            bad_count = sum(1 for r in (self._rows or []) if r.selected)
            self._apply_button.setEnabled(bad_count > 0)
            save_folder(self._settings, "badcut/output_dir", self._output_dir)

    def _invalidate_preview(self) -> None:
        self._photos = None
        self._scores = None
        self._rows = None
        self._apply_button.setEnabled(False)
        self._table.setRowCount(0)

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
        self._status_label.setText("스캔/스코어링 중...")
        self._summary_text.setPlainText("스캔/스코어링 중... (한 번만 하면 이후 임계값 조정은 즉시 반영됩니다)")

        self._score_worker = ScoreWorker(
            list(self._input_dirs),
            self._recursive_checkbox.isChecked(),
            scan_cache=self._scan_cache,
            score_cache=self._score_cache,
            thumbnail_cache=self._thumbnail_cache,
        )
        self._score_worker.progress.connect(self._on_progress)
        self._score_worker.status.connect(self._status_label.setText)
        self._score_worker.finished_ok.connect(self._on_scored)
        self._score_worker.failed.connect(self._on_error)
        self._score_worker.start()

    def _on_scored(self, photos: list[PhotoMetadata], scores: list[PhotoScore]) -> None:
        self._busy = False
        self._status_label.setText("완료")
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
        self._summary_text.setPlainText(format_badcut_header(rows))
        self._populate_table(rows)

    def _populate_table(self, rows: list[ReportRow]) -> None:
        self._table.setRowCount(len(rows))
        for i, row in enumerate(rows):
            thumb_item = QTableWidgetItem()
            pixmap = self._thumbnail_pixmap(row.path)
            if pixmap is not None:
                thumb_item.setData(Qt.ItemDataRole.DecorationRole, pixmap)
            self._table.setItem(i, 0, thumb_item)
            self._table.setItem(i, 1, QTableWidgetItem(row.path.name))
            self._table.setItem(i, 2, QTableWidgetItem("C컷" if row.selected else "정상"))
            self._table.setItem(i, 3, QTableWidgetItem(f"{row.sharpness:.1f}"))
            self._table.setItem(i, 4, QTableWidgetItem("" if row.face is None else f"{row.face:.2f}"))
            self._table.setItem(i, 5, QTableWidgetItem(row.reason))
        self._table.resizeRowsToContents()

    def _thumbnail_pixmap(self, path: Path) -> QPixmap | None:
        cached = self._thumbnail_cache.get(path)
        if cached is None or cached[2] is None:
            return None
        qim = ImageQt(cached[2].convert("RGBA"))
        return QPixmap.fromImage(qim)

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
