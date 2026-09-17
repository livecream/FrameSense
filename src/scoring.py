"""M3: 품질 스코어링 — 1단계(선명도).

PROJECT_SPEC.md 4.3절: 선명도 → 노출 → 얼굴/눈감음 순으로 단계적으로 점수를 추가한다.
현재는 선명도(라플라시안 분산)만 구현하고, total은 선명도와 동일하다.
노출/얼굴 점수가 추가되면 total은 가중합으로 바뀐다.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

from scanner import PhotoMetadata


@dataclass(frozen=True)
class PhotoScore:
    path: Path
    sharpness: float
    total: float
    error: str | None = None


def sharpness_score(path: Path) -> float:
    """라플라시안 분산 기반 선명도 점수. 높을수록 선명(블러 적음)."""
    with Image.open(path) as img:
        gray = np.array(img.convert("L"))
    return float(cv2.Laplacian(gray, cv2.CV_64F).var())


def score_photo(meta: PhotoMetadata) -> PhotoScore:
    """단일 사진의 품질 점수를 계산한다.

    스캔 단계에서 이미 오류가 기록된 파일(예: 손상된 이미지)은 다시 열어보지 않고
    그 오류를 그대로 전달한다.
    """
    if meta.error is not None:
        return PhotoScore(path=meta.path, sharpness=0.0, total=0.0, error=meta.error)

    try:
        sharpness = sharpness_score(meta.path)
    except Exception as e:
        return PhotoScore(
            path=meta.path, sharpness=0.0, total=0.0, error=f"스코어링 실패: {e}"
        )

    return PhotoScore(path=meta.path, sharpness=sharpness, total=sharpness)


def score_photos(photos: list[PhotoMetadata]) -> list[PhotoScore]:
    """사진 목록 각각의 품질 점수를 계산한다."""
    return [score_photo(m) for m in photos]
