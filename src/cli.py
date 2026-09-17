"""CLI 진입점. `scan`(M1) + `group`(M2) + `score`(M3) + `select`(M4) + `report`(M5) + `apply`(M6)."""

from __future__ import annotations

import argparse
from pathlib import Path

from file_ops import apply_selection
from grouping import DEFAULT_SCENE_GAP_SECONDS, group_by_time_gap
from report import build_report, write_report
from scanner import scan_and_extract
from scoring import score_photos
from selector import select_best


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
        face_str = f"{s.face:.2f}" if s.face is not None else "해당없음"
        print(
            f"total={s.total:10.2f}  sharpness={s.sharpness:10.2f}  "
            f"exposure={s.exposure:.2f}  face={face_str}  {s.path.name}{err}"
        )


def cmd_select(args: argparse.Namespace) -> None:
    results = scan_and_extract(Path(args.input), recursive=args.recursive)
    groups = group_by_time_gap(results, gap_seconds=args.scene_gap_seconds)
    print(f"총 {len(groups)}개 장면 그룹에서 베스트 컷 선정\n")
    for i, group in enumerate(groups, start=1):
        selection = select_best(group)
        others = ", ".join(m.path.name for m in group if m.path != selection.best.path)
        print(f"[장면 {i}] 선택: {selection.best.path.name}" + (f"  (제외: {others})" if others else ""))


def cmd_report(args: argparse.Namespace) -> None:
    results = scan_and_extract(Path(args.input), recursive=args.recursive)
    groups = group_by_time_gap(results, gap_seconds=args.scene_gap_seconds)
    rows = build_report(groups)
    write_report(rows, Path(args.output))
    selected = sum(1 for r in rows if r.selected)
    print(
        f"{len(groups)}개 장면, {len(rows)}개 파일 중 {selected}장 선택 "
        f"→ 리포트 저장: {args.output} (dry-run, 실제 파일 작업 없음)"
    )


def cmd_apply(args: argparse.Namespace) -> None:
    results = scan_and_extract(Path(args.input), recursive=args.recursive)
    groups = group_by_time_gap(results, gap_seconds=args.scene_gap_seconds)
    rows = build_report(groups)
    write_report(rows, Path(args.report))

    if not args.apply:
        selected = sum(1 for r in rows if r.selected)
        print(
            f"[dry-run] {len(groups)}개 장면, {selected}장 선택 예정 → 리포트: {args.report}\n"
            f"실제로 파일을 {'이동' if args.move else '복사'}하려면 --apply를 추가하세요."
        )
        return

    op_results = apply_selection(rows, Path(args.output), move=args.move)
    print(
        f"{'이동' if args.move else '복사'} 완료: {len(op_results)}장 "
        f"→ {args.output} (리포트: {args.report})"
    )


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

    p_select = sub.add_parser("select", help="장면별 베스트 컷 선정 (M4)")
    p_select.add_argument("--input", required=True, help="스캔할 사진 폴더 경로")
    p_select.add_argument("--recursive", action="store_true", help="하위 폴더까지 재귀 탐색")
    p_select.add_argument(
        "--scene-gap-seconds",
        type=float,
        default=DEFAULT_SCENE_GAP_SECONDS,
        help=f"같은 장면으로 묶을 최대 시간 간격(초), 기본값 {DEFAULT_SCENE_GAP_SECONDS}",
    )
    p_select.set_defaults(func=cmd_select)

    p_report = sub.add_parser("report", help="선택/제외 사유가 담긴 dry-run 리포트 생성 (M5)")
    p_report.add_argument("--input", required=True, help="스캔할 사진 폴더 경로")
    p_report.add_argument("--recursive", action="store_true", help="하위 폴더까지 재귀 탐색")
    p_report.add_argument(
        "--scene-gap-seconds",
        type=float,
        default=DEFAULT_SCENE_GAP_SECONDS,
        help=f"같은 장면으로 묶을 최대 시간 간격(초), 기본값 {DEFAULT_SCENE_GAP_SECONDS}",
    )
    p_report.add_argument(
        "--output", required=True, help="리포트 저장 경로 (.csv 또는 .json)"
    )
    p_report.set_defaults(func=cmd_report)

    p_apply = sub.add_parser(
        "apply", help="베스트 컷을 실제로 복사/이동 (M6). --apply 없이는 dry-run만 수행"
    )
    p_apply.add_argument("--input", required=True, help="스캔할 사진 폴더 경로")
    p_apply.add_argument("--recursive", action="store_true", help="하위 폴더까지 재귀 탐색")
    p_apply.add_argument(
        "--scene-gap-seconds",
        type=float,
        default=DEFAULT_SCENE_GAP_SECONDS,
        help=f"같은 장면으로 묶을 최대 시간 간격(초), 기본값 {DEFAULT_SCENE_GAP_SECONDS}",
    )
    p_apply.add_argument("--output", required=True, help="베스트 컷을 저장할 폴더")
    p_apply.add_argument(
        "--report", required=True, help="리포트 저장 경로 (.csv 또는 .json)"
    )
    p_apply.add_argument(
        "--move", action="store_true", help="복사 대신 이동 (기본은 복사)"
    )
    p_apply.add_argument(
        "--apply",
        action="store_true",
        help="실제로 파일 작업을 수행. 없으면 dry-run(리포트만 생성)으로 끝남",
    )
    p_apply.set_defaults(func=cmd_apply)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
