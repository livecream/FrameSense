"""M11: 폴더 정리 탭. RAW/영상 분리, 짝 안 맞는 파일 찾기, 촬영 날짜별 정리,
빈 폴더 정리를 폴더 하나 선택 후 버튼 한 번으로 수행한다.

무거운 스코어링(mediapipe)이 없는 단순 파일 이동/조회라 QThread 없이 동기로
처리한다.
ponytail: 폴더 안 파일이 매우 많으면(수만 개) 버튼 클릭 시 UI가 잠깐 멈출 수
있음 — 체감되면 다른 탭처럼 QThread로 옮길 것.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from gui_format import format_folder_summary
from organize import (
    apply_move_plan,
    build_capture_date_plan,
    build_move_by_extension_plan,
    build_undo_plan,
    find_empty_folders,
    find_raw_jpg_mismatches,
    remove_empty_folders,
    summarize_folder,
)
from rename_by_time import VIDEO_EXTENSIONS
from scanner import RAW_EXTENSIONS


class OrganizeTab(QWidget):
    def __init__(self) -> None:
        super().__init__()

        self._folder: Path | None = None
        # 직전 정리 작업 하나만 기억해 "실행 취소"로 되돌린다. 앱을 껐다 켜면
        # 사라짐(세션 한정) — organize_log_*.jsonl에는 남아있어 수동 확인 가능.
        self._last_operation: dict | None = None

        self._folder_label = QLabel("대상 폴더: (선택 안 됨)")
        folder_button = QPushButton("폴더 선택...")
        folder_button.clicked.connect(self._choose_folder)

        summary_button = QPushButton("폴더 정보 보기")
        summary_button.clicked.connect(self._show_folder_summary)

        raw_button = QPushButton("RAW 폴더로 이동")
        raw_button.clicked.connect(self._move_raw)

        video_button = QPushButton("영상 폴더로 이동")
        video_button.clicked.connect(self._move_video)

        mismatch_button = QPushButton("RAW-JPG 짝 안 맞는 파일 찾기")
        mismatch_button.clicked.connect(self._find_mismatches)

        date_button = QPushButton("촬영 날짜별로 정리")
        date_button.clicked.connect(self._organize_by_date)

        empty_button = QPushButton("빈 폴더 정리")
        empty_button.clicked.connect(self._remove_empty_folders)

        self._undo_button = QPushButton("방금 작업 실행 취소")
        self._undo_button.setEnabled(False)
        self._undo_button.clicked.connect(self._undo_last_operation)

        self._result_text = QPlainTextEdit()
        self._result_text.setReadOnly(True)

        button_row = QHBoxLayout()
        for button in (
            summary_button,
            raw_button,
            video_button,
            mismatch_button,
            date_button,
            empty_button,
            self._undo_button,
        ):
            button_row.addWidget(button)

        layout = QVBoxLayout()
        layout.addWidget(self._folder_label)
        layout.addWidget(folder_button)
        layout.addLayout(button_row)
        layout.addWidget(self._result_text)
        self.setLayout(layout)

    @property
    def is_busy(self) -> bool:
        return False

    def _choose_folder(self) -> None:
        directory = QFileDialog.getExistingDirectory(self, "정리할 폴더 선택")
        if directory:
            self._folder = Path(directory)
            self._folder_label.setText(f"대상 폴더: {directory}")
            self._result_text.setPlainText("")
            self._last_operation = None
            self._undo_button.setEnabled(False)

    def _require_folder(self) -> Path | None:
        if self._folder is None or not self._folder.is_dir():
            QMessageBox.warning(self, "폴더 없음", "먼저 정리할 폴더를 선택하세요.")
            return None
        return self._folder

    def _confirm(self, title: str, message: str) -> bool:
        return (
            QMessageBox.question(self, title, message) == QMessageBox.StandardButton.Yes
        )

    def _remember_move(self, rows: list) -> None:
        self._last_operation = {"kind": "move", "rows": rows}
        self._undo_button.setEnabled(True)

    def _move_raw(self) -> None:
        folder = self._require_folder()
        if folder is None:
            return
        rows = build_move_by_extension_plan(folder, RAW_EXTENSIONS, "RAW")
        if not rows:
            self._result_text.setPlainText("이동할 RAW 파일이 없습니다.")
            return
        dest = folder / "RAW"
        if not self._confirm("RAW 이동 확인", f"{len(rows)}개 RAW 파일을 {dest}(으)로 이동합니다.\n계속하시겠습니까?"):
            return
        apply_move_plan(rows, log_folder=folder, action="move_raw")
        self._remember_move(rows)
        self._result_text.setPlainText(f"RAW {len(rows)}개 이동 완료 → {dest}")

    def _move_video(self) -> None:
        folder = self._require_folder()
        if folder is None:
            return
        rows = build_move_by_extension_plan(folder, VIDEO_EXTENSIONS, "영상")
        if not rows:
            self._result_text.setPlainText("이동할 영상 파일이 없습니다.")
            return
        dest = folder / "영상"
        if not self._confirm("영상 이동 확인", f"{len(rows)}개 영상 파일을 {dest}(으)로 이동합니다.\n계속하시겠습니까?"):
            return
        apply_move_plan(rows, log_folder=folder, action="move_video")
        self._remember_move(rows)
        self._result_text.setPlainText(f"영상 {len(rows)}개 이동 완료 → {dest}")

    def _find_mismatches(self) -> None:
        folder = self._require_folder()
        if folder is None:
            return
        messages = find_raw_jpg_mismatches(folder)
        if not messages:
            self._result_text.setPlainText("짝이 안 맞는 파일이 없습니다.")
            return
        self._result_text.setPlainText(f"짝 안 맞는 파일 {len(messages)}개:\n\n" + "\n".join(messages))

    def _organize_by_date(self) -> None:
        folder = self._require_folder()
        if folder is None:
            return
        rows = build_capture_date_plan(folder, video_extensions=VIDEO_EXTENSIONS)
        if not rows:
            self._result_text.setPlainText("정리할 파일이 없습니다.")
            return
        dest_folders = sorted({r.new_path.parent.name for r in rows})
        if not self._confirm(
            "날짜별 정리 확인",
            f"{len(rows)}개 파일을 다음 날짜별 폴더로 이동합니다:\n"
            + ", ".join(dest_folders)
            + "\n계속하시겠습니까?",
        ):
            return
        apply_move_plan(rows, log_folder=folder, action="organize_by_date")
        self._remember_move(rows)
        self._result_text.setPlainText(f"{len(rows)}개 파일을 날짜별 폴더로 이동 완료")

    def _remove_empty_folders(self) -> None:
        folder = self._require_folder()
        if folder is None:
            return
        empty = find_empty_folders(folder)
        if not empty:
            self._result_text.setPlainText("빈 폴더가 없습니다.")
            return
        listing = "\n".join(str(p) for p in empty)
        if not self._confirm(
            "빈 폴더 삭제 확인", f"다음 {len(empty)}개 빈 폴더를 삭제합니다:\n{listing}\n계속하시겠습니까?"
        ):
            return
        remove_empty_folders(empty, log_folder=folder)
        self._last_operation = {"kind": "empty_folders", "folders": empty}
        self._undo_button.setEnabled(True)
        self._result_text.setPlainText(f"빈 폴더 {len(empty)}개 삭제 완료")

    def _undo_last_operation(self) -> None:
        if self._last_operation is None:
            return
        kind = self._last_operation["kind"]
        if kind == "move":
            rows = self._last_operation["rows"]
            apply_move_plan(build_undo_plan(rows))
            self._result_text.setPlainText(f"{len(rows)}개 파일 되돌리기 완료")
        elif kind == "empty_folders":
            folders = self._last_operation["folders"]
            for folder in folders:
                folder.mkdir(parents=True, exist_ok=True)
            self._result_text.setPlainText(f"빈 폴더 {len(folders)}개 다시 생성(복구) 완료")
        self._last_operation = None
        self._undo_button.setEnabled(False)

    def _show_folder_summary(self) -> None:
        folder = self._require_folder()
        if folder is None:
            return
        summary = summarize_folder(folder, video_extensions=VIDEO_EXTENSIONS)
        self._result_text.setPlainText(format_folder_summary(summary))
