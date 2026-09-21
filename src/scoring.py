"""M3: 품질 스코어링 — 선명도 + 노출 + 얼굴/눈감음.

PROJECT_SPEC.md 4.3절: 선명도 → 노출 → 얼굴/눈감음 순으로 단계적으로 점수를 추가한다.
total을 여러 지표의 가중합으로 확정하는 것은 CLAUDE.md가 금지하는 "임의의 점수
가중치 확정"에 해당하므로, 사용자와 가중치를 정하기 전까지는 total = sharpness로
유지한다 (exposure/face는 참고용으로 별도 필드에 노출; face는 얼굴이 없으면 None).
"""

from __future__ import annotations

import sys
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import cv2
import mediapipe as mp
import numpy as np
from mediapipe.tasks.python import vision as mp_vision
from PIL import Image

from scanner import PhotoMetadata

# 얼굴 랜드마크 모델 (눈감음 판단용 블렌드셰이프 포함). 저장소에는 커밋하지 않고
# 최초 사용 시 다운로드해 캐시한다 (.gitignore 참고).
def _default_model_dir() -> Path:
    """모델 저장 위치. PyInstaller로 얼린 실행 파일에서는 __file__ 기준 상대경로가
    번들 내부 임시/읽기전용 경로를 가리켜 의미가 달라지므로, 그 경우 사용자 홈 아래
    쓰기 가능한 경로를 대신 쓴다."""
    if getattr(sys, "frozen", False):
        return Path.home() / "Library" / "Application Support" / "PixThrough" / "models"
    return Path(__file__).resolve().parent.parent / "models"


_MODEL_DIR = _default_model_dir()
_MODEL_PATH = _MODEL_DIR / "face_landmarker.task"
_MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/face_landmarker/"
    "face_landmarker/float16/1/face_landmarker.task"
)

_landmarker: mp_vision.FaceLandmarker | None = None


@dataclass(frozen=True)
class PhotoScore:
    path: Path
    sharpness: float
    exposure: float
    face: float | None
    total: float
    error: str | None = None


def _decode(path: Path) -> tuple[np.ndarray, np.ndarray]:
    """이미지를 한 번만 디스크에서 읽어 (grayscale, rgb) 배열 쌍으로 반환한다.

    선명도/노출/얼굴 세 지표를 각자 따로 파일을 열면 실사진(수 MB, 수천만 화소) 기준
    사진당 처리 시간이 3배로 늘어나는 게 실측으로 확인돼(장당 ~0.33s), score_photo가
    이 함수로 한 번만 디코딩해 공유한다.
    """
    with Image.open(path) as img:
        rgb_img = img.convert("RGB")
        gray = np.array(rgb_img.convert("L"))
        rgb = np.array(rgb_img)
    return gray, rgb


def _sharpness_from_gray(gray: np.ndarray) -> float:
    return float(cv2.Laplacian(gray, cv2.CV_64F).var())


def _exposure_from_gray(gray: np.ndarray) -> float:
    clipped = np.count_nonzero(gray == 0) + np.count_nonzero(gray == 255)
    return 1.0 - clipped / gray.size


def sharpness_score(path: Path) -> float:
    """라플라시안 분산 기반 선명도 점수. 높을수록 선명(블러 적음)."""
    gray, _ = _decode(path)
    return _sharpness_from_gray(gray)


def exposure_score(path: Path) -> float:
    """히스토그램 클리핑 기반 노출 적정성 점수.

    순수 검정(0)·순수 흰색(255)으로 잘린 픽셀 비율이 높을수록 노출 손실이 큰 것으로
    보고 점수를 낮춘다. 1.0(클리핑 없음) ~ 0.0(전부 클리핑) 범위.
    """
    gray, _ = _decode(path)
    return _exposure_from_gray(gray)


def _ensure_model() -> Path:
    if not _MODEL_PATH.exists():
        _MODEL_DIR.mkdir(parents=True, exist_ok=True)
        urllib.request.urlretrieve(_MODEL_URL, _MODEL_PATH)
    return _MODEL_PATH


def _get_landmarker() -> mp_vision.FaceLandmarker:
    global _landmarker
    if _landmarker is None:
        base_options = mp.tasks.BaseOptions(model_asset_path=str(_ensure_model()))
        options = mp_vision.FaceLandmarkerOptions(
            base_options=base_options, output_face_blendshapes=True, num_faces=5
        )
        _landmarker = mp_vision.FaceLandmarker.create_from_options(options)
    return _landmarker


def _eyes_open_from_scores(blink_left: float, blink_right: float) -> float:
    """블렌드셰이프의 eyeBlinkLeft/Right 점수(높을수록 감김)를 눈 뜬 정도로 뒤집는다.

    한쪽 눈만 감아도(윙크 등) 눈감음으로 간주하도록 더 심하게 감긴 쪽을 기준으로 삼는다.
    """
    return 1.0 - max(blink_left, blink_right)


def _face_from_rgb(rgb: np.ndarray) -> float | None:
    image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
    result = _get_landmarker().detect(image)
    if not result.face_blendshapes:
        return None

    per_face_scores = []
    for face in result.face_blendshapes:
        scores = {c.category_name: c.score for c in face}
        per_face_scores.append(
            _eyes_open_from_scores(
                scores.get("eyeBlinkLeft", 0.0), scores.get("eyeBlinkRight", 0.0)
            )
        )
    return sum(per_face_scores) / len(per_face_scores)


def face_score(path: Path) -> float | None:
    """얼굴이 있으면 눈 뜬 정도(0~1, 높을수록 좋음)를, 없으면 None(해당 없음)을 반환한다.

    PROJECT_SPEC.md 4.3절: 인물 사진에서만 의미 있는 기준이라 풍경 사진 등 얼굴이
    없는 경우는 페널티 없이 "적용 대상 아님"으로 취급한다.
    """
    _, rgb = _decode(path)
    return _face_from_rgb(rgb)


def score_photo(meta: PhotoMetadata) -> PhotoScore:
    """단일 사진의 품질 점수를 계산한다.

    스캔 단계에서 이미 오류가 기록된 파일(예: 손상된 이미지)은 다시 열어보지 않고
    그 오류를 그대로 전달한다.
    """
    if meta.error is not None:
        return PhotoScore(
            path=meta.path,
            sharpness=0.0,
            exposure=0.0,
            face=None,
            total=0.0,
            error=meta.error,
        )

    try:
        gray, rgb = _decode(meta.path)
        sharpness = _sharpness_from_gray(gray)
        exposure = _exposure_from_gray(gray)
        face = _face_from_rgb(rgb)
    except Exception as e:
        return PhotoScore(
            path=meta.path,
            sharpness=0.0,
            exposure=0.0,
            face=None,
            total=0.0,
            error=f"스코어링 실패: {e}",
        )

    return PhotoScore(
        path=meta.path,
        sharpness=sharpness,
        exposure=exposure,
        face=face,
        total=sharpness,
    )


def _stat_key(path: Path) -> tuple[float, int]:
    stat = path.stat()
    return stat.st_mtime, stat.st_size


def _score_photo_cached(
    meta: PhotoMetadata, cache: dict[Path, tuple[float, int, PhotoScore]] | None
) -> PhotoScore:
    """cache가 주어지면 파일의 (수정 시각, 크기)가 이전과 같을 때 다시 채점하지
    않고 캐시된 점수를 재사용한다. 얼굴 검출(mediapipe)이 사진 1장당 ~100ms대라
    같은 세션에서 반복 스코어링할 때 특히 효과가 크다."""
    if cache is None:
        return score_photo(meta)
    key = _stat_key(meta.path)
    cached = cache.get(meta.path)
    if cached is not None and cached[:2] == key:
        return cached[2]
    score = score_photo(meta)
    cache[meta.path] = (*key, score)
    return score


def score_photos(
    photos: list[PhotoMetadata],
    on_progress: Callable[[int, int], None] | None = None,
    cache: dict[Path, tuple[float, int, PhotoScore]] | None = None,
) -> list[PhotoScore]:
    """사진 목록 각각의 품질 점수를 계산한다.

    on_progress가 주어지면 사진 1장 처리할 때마다 (완료한 수, 전체 수)를 알려준다.
    """
    total = len(photos)
    results: list[PhotoScore] = []
    for i, m in enumerate(photos, start=1):
        results.append(_score_photo_cached(m, cache))
        if on_progress is not None:
            on_progress(i, total)
    return results
