"""미리보기 테이블에 쓸 작은 썸네일 이미지를 만든다. Qt에 의존하지 않는
순수 함수라 pytest로 바로 테스트한다. 실패해도 예외를 던지지 않고 None을
반환해 호출자(테이블 렌더링)가 placeholder를 쓸 수 있게 한다."""

from __future__ import annotations

from pathlib import Path

from PIL import Image

THUMBNAIL_SIZE = (64, 64)


def make_thumbnail(path: Path, size: tuple[int, int] = THUMBNAIL_SIZE) -> Image.Image | None:
    """path의 이미지를 size 안에 들어가도록 비율 유지한 채 축소한다.
    파일을 열 수 없으면(손상 등) None을 반환한다."""
    try:
        img = Image.open(path)
        img.load()
    except Exception:
        return None
    img = img.convert("RGB")
    img.thumbnail(size)
    return img
