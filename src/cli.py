"""CLI 진입점. `scan`(M1) + `group`(M2) + `score`(M3) 서브커맨드를 제공한다."""

from __future__ import annotations

import argparse
from pathlib import Path

from grouping import DEFAULT_SCENE_GAP_SECONDS, group_by_time_gap
from scanner import scan_and_extract
from scoring import score_photos


def cmd_scan(args: argparse.Namespace) -> None:
    results = scan_and_extract(Path(args.input), recursive=args.recursive)
    print(f"총 {len(results)}개 파일 발견 (입력: {args.input}, 하위폴더 포함: {args.recursive})\n")
    for m in results:
        marker = "  [EXIF 없음, mtime 사용]" if m.exif_source == "mtime" else ""
        err = f"  [오류: {m.error}]" if m.error else ""
        print(f"{m.datetime_original}  {m.path.name}  ({m.width}x{m.height}){marker}{err}")


def cmd_group(args: argparse.Namespace) -> None:
    results = scan_and_extract(Path(args.input), recursive=args.recursive)
    groups = group_by_time_gap(results, gap_seconds=args.scene_gap_seconds)
    print(
        f"총 {len(results)}개 파일 → {len(groups)}개 장면 그룹 "
        f"(간격: {args.scene_gap_seconds}초)\n"
    )
    for i, group in enumerate(groups, start=1):
        names = ", ".join(m.path.name for m in group)
        print(f"[장면 {i}] {len(group)}장: {names}")


def cmd_score(args: argparse.Namespace) -> None:
    results = scan_and_extract(Path(args.input), recursive=args.recursive)
    scores = score_photos(results)
    print(f"총 {len(scores)}개 파일 스코어링 (입력: {args.input})\n")
    for s in scores:
        err = f"  [오류: {s.error}]" if s.error else ""
        print(f"{s.total:10.2f}  {s.path.name}{err}")


def main() -> None:
    parser = argparse.ArgumentParser(description="사진 베스트컷 선별 도구")
    sub = parser.add_subparsers(dest="command", required=True)

    p_scan = sub.add_parser("scan", help="폴더 스캔 + EXIF 메타데이터 추출 (M1)")
    p_scan.add_argument("--input", required=True, help="스캔할 사진 폴더 경로")
    p_scan.add_argument("--recursive", action="store_true", help="하위 폴더까지 재귀 탐색")
    p_scan.set_defaults(func=cmd_scan)

    p_group = sub.add_parser("group", help="촬영 시각 간격 기준 장면 그룹핑 (M2)")
    p_group.add_argument("--input", required=True, help="스캔할 사진 폴더 경로")
    p_group.add_argument("--recursive", action="store_true", help="하위 폴더까지 재귀 탐색")
    p_group.add_argument(
        "--scene-gap-seconds",
        type=float,
        default=DEFAULT_SCENE_GAP_SECONDS,
        help=f"같은 장면으로 묶을 최대 시간 간격(초), 기본값 {DEFAULT_SCENE_GAP_SECONDS}",
    )
    p_group.set_defaults(func=cmd_group)

    p_score = sub.add_parser("score", help="선명도 기준 품질 스코어링 (M3)")
    p_score.add_argument("--input", required=True, help="스캔할 사진 폴더 경로")
    p_score.add_argument("--recursive", action="store_true", help="하위 폴더까지 재귀 탐색")
    p_score.set_defaults(func=cmd_score)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
