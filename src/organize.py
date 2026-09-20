"""M11: 폴더 정리 — RAW/영상 분리, 짝 안 맞는 파일 찾기, 촬영 날짜별 정리, 빈 폴더 정리.

베스트컷/C컷과 달리 품질 판단이 없는 순수 파일 배치 작업이라 Qt 의존 없이
독립적으로 테스트 가능한 함수로 둔다. 대상은 지정한 폴더의 최상위 파일만이며
(하위 폴더는 건드리지 않음 — 이미 정리된 RAW/영상 하위 폴더를 다시 뒤섞지
않기 위함), 빈 폴더 탐색만 하위까지 본다.

CLAUDE.md 원칙(원본 보호)에 따라 이동만 하고, 삭제는 파일이 하나도 없다고
확인된 "완전히 빈 폴더"에 한해서만 한다.
"""

from __future__ import annotations

import datetime
import json
import shutil
from dataclasses import dataclass
from pathlib import Path

from scanner import RAW_EXTENSIONS, SUPPORTED_EXTENSIONS, extract_metadata


@dataclass(frozen=True)
class MovePlanRow:
    old_path: Path
    new_path: Path


@dataclass(frozen=True)
class FolderSummary:
    total_files: int
    total_size_bytes: int
    photo_count: int
    raw_count: int
    video_count: int
    other_count: int


def _top_level_files(folder: Path) -> list[Path]:
    return sorted(p for p in Path(folder).iterdir() if p.is_file())


def write_operation_log(items: list, folder: Path, action: str) -> Path:
    """정리 작업 내역을 folder/organize_log_<타임스탬프>.jsonl에 기록한다
    (rename_by_time.py의 rename_log_*.jsonl과 같은 형식). items는
    MovePlanRow 목록이거나(이동) Path 목록(폴더 삭제)이다."""
    folder = Path(folder)
    log_path = folder / f"organize_log_{datetime.datetime.now():%Y%m%d_%H%M%S}.jsonl"
    with open(log_path, "w", encoding="utf-8") as f:
        for item in items:
            if isinstance(item, MovePlanRow):
                entry = {"action": action, "old_path": str(item.old_path), "new_path": str(item.new_path)}
            else:
                entry = {"action": action, "path": str(item)}
            f.write(
                json.dumps({"timestamp": datetime.datetime.now().isoformat(), **entry}, ensure_ascii=False)
                + "\n"
            )
    return log_path


def build_undo_plan(rows: list[MovePlanRow]) -> list[MovePlanRow]:
    """이동 계획의 old/new를 뒤바꿔 되돌리기 계획을 만든다."""
    return [MovePlanRow(old_path=row.new_path, new_path=row.old_path) for row in rows]


def summarize_folder(folder: Path, video_extensions: set[str]) -> FolderSummary:
    """폴더 전체(하위 포함)의 파일 수/용량/카테고리별 개수를 센다.

    읽기 전용 정보 표시라 다른 정리 함수와 달리 하위 폴더까지 재귀적으로 봐도
    안전하다."""
    folder = Path(folder)
    raw_exts_lower = {ext.lower() for ext in RAW_EXTENSIONS}
    video_exts_lower = {ext.lower() for ext in video_extensions}

    total_files = 0
    total_size = 0
    photo_count = 0
    raw_count = 0
    video_count = 0
    other_count = 0

    for path in folder.rglob("*"):
        if not path.is_file():
            continue
        total_files += 1
        total_size += path.stat().st_size
        suffix = path.suffix.lower()
        if suffix in SUPPORTED_EXTENSIONS:
            photo_count += 1
        elif suffix in raw_exts_lower:
            raw_count += 1
        elif suffix in video_exts_lower:
            video_count += 1
        else:
            other_count += 1

    return FolderSummary(
        total_files=total_files,
        total_size_bytes=total_size,
        photo_count=photo_count,
        raw_count=raw_count,
        video_count=video_count,
        other_count=other_count,
    )


def build_move_by_extension_plan(
    folder: Path, extensions: set[str], subfolder_name: str
) -> list[MovePlanRow]:
    """folder 최상위에서 확장자가 일치하는 파일을 folder/subfolder_name/으로 옮기는 계획을 만든다."""
    exts_lower = {ext.lower() for ext in extensions}
    dest_dir = Path(folder) / subfolder_name
    return [
        MovePlanRow(old_path=path, new_path=dest_dir / path.name)
        for path in _top_level_files(folder)
        if path.suffix.lower() in exts_lower
    ]


def apply_move_plan(
    rows: list[MovePlanRow], log_folder: Path | None = None, action: str = "move"
) -> None:
    """계획된 이동을 실제로 수행한다. 대상 폴더는 필요하면 만든다.

    log_folder가 주어지면 이동 후 write_operation_log로 기록을 남긴다."""
    for row in rows:
        row.new_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(row.old_path), str(row.new_path))
    if log_folder is not None and rows:
        write_operation_log(rows, log_folder, action)


def find_raw_jpg_mismatches(folder: Path) -> list[str]:
    """최상위 폴더에서 사진-RAW 베이스 파일명이 서로 짝이 안 맞는 경우를 사람이
    읽을 문자열 목록으로 반환한다 (이동/삭제 없음, 확인용 리포트)."""
    files = _top_level_files(folder)
    raw_exts_lower = {ext.lower() for ext in RAW_EXTENSIONS}
    photo_by_stem = {p.stem: p for p in files if p.suffix.lower() in SUPPORTED_EXTENSIONS}
    raw_by_stem = {p.stem: p for p in files if p.suffix.lower() in raw_exts_lower}

    messages = [
        f"RAW 없음: {photo.name}"
        for stem, photo in sorted(photo_by_stem.items())
        if stem not in raw_by_stem
    ]
    messages += [
        f"짝 사진 없음: {raw.name}"
        for stem, raw in sorted(raw_by_stem.items())
        if stem not in photo_by_stem
    ]
    return messages


def build_capture_date_plan(folder: Path, video_extensions: set[str]) -> list[MovePlanRow]:
    """최상위 파일(사진+영상)을 촬영 날짜(YYYY-MM-DD) 하위 폴더로 옮기는 계획을 만든다.

    사진은 EXIF 촬영 시각, 영상은 파일 수정 시각을 쓴다 (rename_by_time.py와
    동일한 방식 — 영상엔 촬영 시각 EXIF가 없음)."""
    folder = Path(folder)
    video_exts_lower = {ext.lower() for ext in video_extensions}
    rows = []
    for path in _top_level_files(folder):
        suffix = path.suffix.lower()
        if suffix in video_exts_lower:
            dt = datetime.datetime.fromtimestamp(path.stat().st_mtime)
        elif suffix in SUPPORTED_EXTENSIONS:
            dt = extract_metadata(path).datetime_original
        else:
            continue
        date_dir = folder / dt.strftime("%Y-%m-%d")
        rows.append(MovePlanRow(old_path=path, new_path=date_dir / path.name))
    return rows


def find_empty_folders(root: Path) -> list[Path]:
    """root 아래(자기 자신 제외) 파일이 하나도 없는 폴더를 깊은 순서로 전부 찾는다.

    깊은 폴더부터 정렬해 반환하므로, 반환 순서 그대로 삭제하면 부모보다 자식이
    먼저 지워져 부모도 빈 폴더가 된 뒤 안전하게 지워진다."""
    root = Path(root)
    subdirs = [p for p in root.rglob("*") if p.is_dir()]
    subdirs.sort(key=lambda p: len(p.parts), reverse=True)
    return [d for d in subdirs if not any(f.is_file() for f in d.rglob("*"))]


def remove_empty_folders(folders: list[Path], log_folder: Path | None = None) -> None:
    """빈 폴더 목록을 실제로 삭제한다.

    log_folder가 주어지면 삭제 후 write_operation_log로 기록을 남긴다."""
    for folder in folders:
        folder.rmdir()
    if log_folder is not None and folders:
        write_operation_log(folders, log_folder, "remove_empty_folders")
