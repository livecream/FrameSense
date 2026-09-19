"""M9: 여러 바디의 사진(+영상)을 촬영 시각순으로 정렬해 파일명을 00001부터 순서대로 바꾼다.

CLAUDE.md 원칙(원본 보호)에 따라 파일을 다른 곳으로 옮기지는 않고, 각 파일을
원래 있던 폴더에서 제자리로 리네임한다(파일 내용은 그대로, 이름만 바뀜). 여러
입력 폴더(바디별 폴더)를 한 번에 받아 촬영 시각 기준으로 전체를 한 줄로 합쳐
정렬하고, 같은 베이스 파일명의 RAW가 있으면 짝지어 같은 번호를 부여한다.

영상 파일(VIDEO_EXTENSIONS)은 이 리네임 기능에서만 함께 다룬다 — 화질 점수
(선명도/노출/얼굴)를 매기는 베스트컷/C컷 판정은 사진 전용이라 영상에는 의미가
없기 때문. 영상은 EXIF가 없어 파일 수정 시각(mtime)을 촬영 시각으로 쓴다(사진에서
EXIF가 없을 때 mtime으로 폴백하는 것과 동일한 방식). RAW 짝짓기 대상도 아니다.

리네임은 실수로 파일을 덮어써 잃어버리면 되돌릴 수 없으므로, 실행 전 전수
충돌 검사를 하고 실제 적용은 임시 이름을 거치는 2단계로 수행해 이번 배치 안에서
새 이름이 서로 겹치는 경우에도 데이터 손실 없이 처리한다.
"""

from __future__ import annotations

import datetime
import json
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from file_ops import find_matching_raw
from scanner import extract_metadata, scan_folder

DEFAULT_DIGITS = 5
VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi", ".mts", ".m4v"}


@dataclass(frozen=True)
class RenamePlanRow:
    seq: int
    old_path: Path
    new_path: Path
    raw_old_path: Path | None
    raw_new_path: Path | None
    datetime_original: datetime.datetime


@dataclass(frozen=True)
class RenameResult:
    old_path: Path
    new_path: Path
    raw_old_path: Path | None
    raw_new_path: Path | None


def _scan_video_files(input_dir: Path, recursive: bool) -> list[Path]:
    pattern_iter = input_dir.rglob("*") if recursive else input_dir.glob("*")
    return sorted(
        p for p in pattern_iter if p.is_file() and p.suffix.lower() in VIDEO_EXTENSIONS
    )


def build_rename_plan(
    input_dirs: list[Path],
    recursive: bool = False,
    digits: int = DEFAULT_DIGITS,
) -> list[RenamePlanRow]:
    """여러 입력 폴더의 사진+영상을 촬영 시각순으로 합쳐 정렬하고 순번 리네임 계획을 만든다.

    동일 촬영 시각(초 단위까지만 있는 EXIF 특성상 서로 다른 바디가 같은 초에 찍을 수
    있음)이 겹치면 원본 경로 문자열 순서로 동점을 처리해 실행할 때마다 결과가
    같도록 한다.
    """
    items: list[tuple[Path, datetime.datetime]] = []
    for input_dir in input_dirs:
        input_dir = Path(input_dir)
        for path in scan_folder(input_dir, recursive=recursive):
            items.append((path, extract_metadata(path).datetime_original))
        for path in _scan_video_files(input_dir, recursive=recursive):
            items.append((path, datetime.datetime.fromtimestamp(path.stat().st_mtime)))
    items.sort(key=lambda item: (item[1], str(item[0])))

    rows: list[RenamePlanRow] = []
    for seq, (path, dt) in enumerate(items, start=1):
        stem = f"{seq:0{digits}d}"
        new_path = path.with_name(f"{stem}{path.suffix}")
        is_video = path.suffix.lower() in VIDEO_EXTENSIONS
        raw_old = None if is_video else find_matching_raw(path)
        raw_new = raw_old.with_name(f"{stem}{raw_old.suffix}") if raw_old else None
        rows.append(
            RenamePlanRow(
                seq=seq,
                old_path=path,
                new_path=new_path,
                raw_old_path=raw_old,
                raw_new_path=raw_new,
                datetime_original=dt,
            )
        )
    return rows


def _row_to_report_dict(row: RenamePlanRow) -> dict:
    return {
        "seq": row.seq,
        "old_path": str(row.old_path),
        "new_path": str(row.new_path),
        "raw_old_path": str(row.raw_old_path) if row.raw_old_path else None,
        "raw_new_path": str(row.raw_new_path) if row.raw_new_path else None,
        "datetime_original": row.datetime_original.isoformat(),
    }


def write_rename_report(rows: list[RenamePlanRow], output_path: Path) -> None:
    """리네임 계획을 JSON으로 저장한다 (실제 적용 전 사람이 먼저 확인하는 dry-run용)."""
    output_path = Path(output_path)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump([_row_to_report_dict(r) for r in rows], f, ensure_ascii=False, indent=2)


def _check_collisions(pairs: list[tuple[Path, Path]]) -> None:
    """이번 배치 밖의 파일과 새 이름이 겹치면 아무것도 건드리기 전에 중단한다.

    배치 안에서 새 이름끼리 겹치는 것(예: 원본 이름 중 하나가 다른 파일의 목표
    이름과 우연히 같은 경우)은 2단계 리네임으로 안전하게 처리되므로, 여기서는
    배치에 속하지 않은 외부 파일과의 충돌만 막는다.
    """
    sources = {old for old, _new in pairs}
    for _old, new in pairs:
        if new.exists() and new not in sources:
            raise ValueError(
                f"리네임 대상 이름이 이미 존재하는 파일과 겹칩니다: {new} "
                "(파일이 뒤섞일 수 있어 중단합니다)"
            )


def apply_rename_plan(
    rows: list[RenamePlanRow],
    log_dir: Path,
    on_progress: Callable[[int, int], None] | None = None,
) -> list[RenameResult]:
    """리네임 계획을 실제로 적용한다 (제자리 rename, 배치 전체를 2단계로 안전하게 수행).

    행 단위로 임시 이름을 거치면, 예를 들어 A의 목표 이름이 아직 처리 전인 B의
    원래 이름과 같은 "이름 스왑" 상황에서 A를 처리하는 순간 B를 덮어써버린다.
    그래서 1단계에서 이번 배치의 모든 파일을 임시 이름으로 옮겨 최종 이름 자리를
    전부 비운 뒤에, 2단계에서 각 파일을 최종 이름으로 옮긴다. 처리 내역은
    log_dir/rename_log_<타임스탬프>.jsonl에 기록한다.
    """
    log_dir = Path(log_dir)
    row_pairs_list = [
        [(row.old_path, row.new_path)]
        + ([(row.raw_old_path, row.raw_new_path)] if row.raw_old_path is not None else [])
        for row in rows
    ]
    flat_pairs = [pair for row_pairs in row_pairs_list for pair in row_pairs]
    _check_collisions(flat_pairs)

    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / f"rename_log_{datetime.datetime.now():%Y%m%d_%H%M%S}.jsonl"

    # 1단계: 전부 임시 이름으로 옮긴다. 도중 실패하면 지금까지 옮긴 것만 원상
    # 복구하고 중단한다 (최종 이름은 아직 아무것도 건드리지 않은 상태).
    temp_for: dict[tuple[Path, Path], Path] = {}
    renamed_so_far: list[tuple[Path, Path]] = []  # (temp, original)
    try:
        for old, new in flat_pairs:
            temp = old.with_name(f".__framesense_tmp_{uuid.uuid4().hex}{old.suffix}")
            old.rename(temp)
            temp_for[(old, new)] = temp
            renamed_so_far.append((temp, old))
    except OSError as e:
        for temp, original in reversed(renamed_so_far):
            if temp.exists():
                temp.rename(original)
        raise RuntimeError(f"리네임 1단계에서 실패해 모두 원상 복구했습니다: {e}") from e

    # 2단계: 임시 이름 -> 최종 이름. 이 시점엔 배치 안 이름 겹침이 전부 해소된
    # 상태라 실패할 여지가 거의 없어(디스크 오류 등 예외적 상황 제외) 자동
    # 롤백은 하지 않는다.
    # ponytail: 2단계 실패 시 자동 롤백 없음 — rename_log로 수동 복구,
    # 필요해지면 phase1처럼 되돌리는 로직 추가.
    total = len(rows)
    results: list[RenameResult] = []
    with open(log_path, "w", encoding="utf-8") as log_file:
        for index, (row, row_pairs) in enumerate(zip(rows, row_pairs_list), start=1):
            for old, new in row_pairs:
                temp_for[(old, new)].rename(new)

            results.append(
                RenameResult(
                    old_path=row.old_path,
                    new_path=row.new_path,
                    raw_old_path=row.raw_old_path,
                    raw_new_path=row.raw_new_path,
                )
            )
            log_file.write(
                json.dumps(
                    {
                        "timestamp": datetime.datetime.now().isoformat(),
                        **_row_to_report_dict(row),
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )
            if on_progress is not None:
                on_progress(index, total)

    return results
