"""CLI 진입점. 현재는 M1(스캔 + EXIF 추출) 확인용 `scan` 서브커맨드만 제공한다."""

from __future__ import annotations

import argparse
from pathlib import Path

from scanner import scan_and_extract


def cmd_scan(args: argparse.Namespace) -> None:
    results = scan_and_extract(Path(args.input), recursive=args.recursive)
    print(f"총 {len(results)}개 파일 발견 (입력: {args.input}, 하위폴더 포함: {args.recursive})\n")
    for m in results:
        marker = "  [EXIF 없음, mtime 사용]" if m.exif_source == "mtime" else ""
        err = f"  [오류: {m.error}]" if m.error else ""
        print(f"{m.datetime_original}  {m.path.name}  ({m.width}x{m.height}){marker}{err}")


def main() -> None:
    parser = argparse.ArgumentParser(description="사진 베스트컷 선별 도구")
    sub = parser.add_subparsers(dest="command", required=True)

    p_scan = sub.add_parser("scan", help="폴더 스캔 + EXIF 메타데이터 추출 (M1)")
    p_scan.add_argument("--input", required=True, help="스캔할 사진 폴더 경로")
    p_scan.add_argument("--recursive", action="store_true", help="하위 폴더까지 재귀 탐색")
    p_scan.set_defaults(func=cmd_scan)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
