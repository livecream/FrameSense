# M8: GUI 설계 (PyQt/PySide6)

**날짜:** 2026-09-17
**상태:** 승인됨 (사용자 확인 완료)

## 배경

M1~M7로 CLI 파이프라인(스캔 → 그룹핑 → 스코어링 → 베스트 컷 선정 → dry-run 리포트 →
실제 파일 복사/이동)이 완성되고 22장 실사진 기준 회귀 테스트까지 갖춰졌다.
PROJECT_SPEC.md 6절은 "1차는 CLI로 로직을 충분히 검증한 뒤, 이후 macOS 대상 GUI(M8)를
진행"하도록 정해뒀고, 프레임워크는 PyQt 또는 Streamlit 중 택1로 명시돼 있었다.

## 범위 (1차 버전)

- 포함: 입력/출력 폴더 선택, 복사/이동 선택, dry-run 미리보기(요약 텍스트), 진행률 표시,
  실제 적용(apply), 완료 후 출력 폴더 열기.
- 제외 (다음 버전으로 미룸): 장면별 사진 이미지 미리보기, 선택/제외 수동 변경.
  이 두 기능은 UI만 추가하면 되고 백엔드 변경이 필요 없다 — `ReportRow`/`SceneSelection`에
  이미 장면별 사진·점수·선택 여부가 다 들어있기 때문.

## 결정 사항

| 항목 | 결정 |
|---|---|
| GUI 프레임워크 | PySide6 (Qt 공식 파이썬 바인딩, LGPL — 라이선스 이슈 없음) |
| 패키징 | PyInstaller로 `FrameSense.app` 더블클릭 실행 번들까지 이번에 구축 |
| 로직 재사용 | GUI는 `scan_and_extract`/`group_by_time_gap`/`build_report`/`apply_selection`를
그대로 호출하는 얇은 표시 계층. 파이프라인 로직 중복 없음 |

## 아키텍처

```
src/gui.py
├── MainWindow (QMainWindow)
│   ├── 입력 폴더 선택 (QFileDialog)
│   ├── 출력 폴더 선택 (QFileDialog)
│   ├── 복사/이동 라디오 버튼 (기본: 복사)
│   ├── "미리보기" 버튼
│   ├── "적용" 버튼 (미리보기 성공 전에는 비활성)
│   ├── QProgressBar
│   └── 결과 요약 텍스트 영역 (QPlainTextEdit, 읽기 전용)
├── PreviewWorker (QThread)
│   └── scan_and_extract → group_by_time_gap → build_report 실행,
│       진행률/완료/에러 시그널 emit
└── ApplyWorker (QThread)
    └── apply_selection 실행, 진행률/완료/에러 시그널 emit
```

두 워커 모두 `src/`의 기존 함수를 그대로 호출한다. GUI 전용 로직은 상태 관리와
텍스트 포맷팅뿐이다.

## API 변경 (진행률 콜백)

현재 `score_photos(photos)`와 `apply_selection(rows, output_dir, move=False)`는 진행 상황을
보고할 방법이 없다. 아래처럼 **선택적** 콜백 파라미터를 추가한다 (기본값 `None`이라
CLI/기존 테스트는 변경 없음):

```python
def score_photos(
    photos: list[PhotoMetadata],
    on_progress: Callable[[int, int], None] | None = None,
) -> list[PhotoScore]:
    ...
    for i, m in enumerate(photos, start=1):
        result = score_photo(m)
        if on_progress:
            on_progress(i, len(photos))
        ...

def apply_selection(
    rows: list[ReportRow],
    output_dir: Path,
    move: bool = False,
    on_progress: Callable[[int, int], None] | None = None,
) -> list[FileOpResult]:
    ...
```

`build_report`는 내부적으로 `select_best` → `score_photos`를 호출하므로, `build_report`에도
같은 시그니처의 `on_progress`를 추가해 그대로 전달한다.

## 모델 저장 경로 수정 (패키징 대응)

`scoring.py`의 `_MODEL_DIR = Path(__file__).resolve().parent.parent / "models"`는
PyInstaller로 얼린 실행 파일에서는 `__file__`이 번들 내부 임시/읽기전용 경로를
가리켜 의미가 달라진다. 아래처럼 실행 환경을 구분해 사용자 홈 아래 쓰기 가능한
경로를 쓰도록 고친다:

```python
import sys

def _default_model_dir() -> Path:
    if getattr(sys, "frozen", False):  # PyInstaller로 패키징된 실행 파일
        return Path.home() / "Library" / "Application Support" / "FrameSense" / "models"
    return Path(__file__).resolve().parent.parent / "models"

_MODEL_DIR = _default_model_dir()
```

`python src/cli.py`로 직접 실행할 때(개발 중, 기존 테스트)는 기존과 동일하게 동작한다.

## 데이터 흐름 (UX)

1. 사용자가 입력/출력 폴더를 고르고 "미리보기" 클릭
2. `PreviewWorker` 실행 → 진행률 바 갱신 → 완료 시 결과 요약
   (`"{N}개 장면, {M}장 중 {K}장 선택"` + 장면별 한 줄 목록) 표시, `rows`를
   `MainWindow` 상태에 보관, "적용" 버튼 활성화
3. "적용" 클릭 → `QMessageBox.question`으로 확인 → `ApplyWorker` 실행 → 진행률 바 갱신
   → 완료 시 "{K}장 복사 완료 → {output_dir}" + "출력 폴더 열기" 버튼
   (`subprocess.run(["open", str(output_dir)])`)
4. 입력/출력 폴더를 바꾸면 "적용" 버튼은 다시 비활성화된다 (미리보기 재실행 강제 —
   stale 상태로 다른 폴더에 적용하는 사고 방지)

## 에러 처리

- 워커 스레드의 예외는 잡아서 에러 시그널로 emit → `QMessageBox.critical`로 표시.
  조용히 넘어가지 않는다 (`apply_selection`이 실패 시 이미 예외를 던지는 원칙과 일치).
- 입력 폴더가 비어있거나 존재하지 않으면 "미리보기" 전에 즉시 안내 메시지.

## 테스트 전략

- Qt UI 자체는 자동 테스트를 만들지 않는다 (개인용 도구 규모에 과함, ROI 낮음).
- `score_photos`/`apply_selection`/`build_report`에 추가하는 `on_progress` 콜백 동작은
  Qt 없이 순수 pytest로 테스트한다 (호출 횟수, 인자 값 검증).
- 결과 요약 텍스트를 만드는 포맷팅 함수(`_format_summary(rows)` 등)는 Qt와 분리된
  순수 함수로 만들어 pytest로 테스트한다.
- 나머지는 `test_photos/` 실사진으로 앱을 직접 띄워 수동 스모크 테스트한다.

## 패키징

- `packaging/FrameSense.spec` (PyInstaller 스펙 파일) 추가
- 빌드 명령: `pyinstaller packaging/FrameSense.spec` → `dist/FrameSense.app`
- mediapipe/opencv 등 무거운 의존성의 PyInstaller 번들링 이슈(숨은 임포트, 바이너리
  누락)는 빌드해보면서 스펙 파일의 `hiddenimports`/`datas`로 대응한다 — 정확히 어떤
  이슈가 나올지는 실제로 빌드해봐야 알 수 있어 계획 단계에서 전부 예측하지 않는다.

## 다음 버전으로 미루는 것

- 장면별 사진 이미지 미리보기, 클릭으로 선택 변경 (백엔드 변경 불필요, UI만 추가)
- 고급 옵션(scene-gap-seconds 등) 노출 — 1차는 스펙 기본값(3초) 고정
