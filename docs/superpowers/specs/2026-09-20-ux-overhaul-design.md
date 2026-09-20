# FrameSense UX 전면 개선 설계 (v1.0.0)

## 배경

M1~M11로 스캔/그룹핑/스코어링/베스트컷/C컷/시간순 정렬/폴더 정리 기능이 모두
갖춰졌고, 실제 사진 워크플로에 쓰이고 있다. 이번 작업은 새 기능이 아니라
**기존 기능을 더 쓰기 편하게 만드는 UX/디자인 개선**이다:

1. 베스트컷/C컷 미리보기를 텍스트 목록 → 썸네일이 있는 테이블로 전환
2. 모든 폴더 입력/선택 영역에 드래그앤드롭 지원
3. 탭·역할별로 마지막 사용 폴더를 기억해 자동으로 채움
4. 앱에 처음으로 버전 번호(1.0.0)를 도입

브레인스토밍 과정에서 사용자가 확정한 범위:
- 테이블 전환은 **베스트컷/C컷 미리보기만** (리네임 미리보기, 정리 탭 리포트는
  텍스트 그대로 유지)
- 썸네일은 **테이블 각 행의 한 컬럼**
- 드래그앤드롭은 **모든 폴더 입력/선택 영역**
- 폴더 기억은 **탭·역할별로 따로**

## 아키텍처 개요

새로 생기는 파일:
- `src/gui_dnd.py` — 드래그앤드롭 공용 헬퍼 함수 하나 (`extract_dropped_folders`)
- `src/version.py` — `__version__` 상수 하나

수정되는 파일:
- `src/gui_bestcut_tab.py`, `src/gui_badcut_tab.py` — `QPlainTextEdit` 결과창을
  `QTableWidget`으로 교체, 썸네일 캐시 추가, 드래그앤드롭 오버라이드, QSettings
  연동
- `src/gui_rename_tab.py`, `src/gui_organize_tab.py` — 드래그앤드롭 오버라이드,
  QSettings 연동 (텍스트 결과창은 그대로)
- `src/gui.py` — 창 제목에 버전 표시
- `packaging/FrameSense.spec` — `CFBundleShortVersionString` 추가

건드리지 않는 것: `scanner.py`/`scoring.py`/`selector.py`/`report.py`/
`badcut.py`/`rename_by_time.py`/`organize.py`/`file_ops.py` 등 로직 계층
전부. `gui_format.py`의 기존 텍스트 포맷 함수도 유지(상단 집계 라벨에 계속
씀). 순수 UI 계층 변경이라 회귀 테스트(`pytest`) 결과는 동일해야 한다.

## 1. 테이블 + 썸네일

### 컬럼 구성

- 베스트컷 (`BestCutTab`): 썸네일 / 파일명 / 장면(`ReportRow.scene_id`) / 선택여부 / 사유
- C컷 (`BadCutTab`): 썸네일 / 파일명 / 판정 / 선명도 / 눈뜸 / 사유

기존 상단 집계(예: "22장 중 5개 장면, N장 선택", 선명도/눈뜸 점수 분포)는
`QLabel`로 유지하고, `format_preview_summary`/`format_badcut_preview`가 만드는
텍스트에서 **집계 부분만** 뽑아 쓴다. 개별 파일 나열(장면별 리스트, C컷 목록)은
테이블이 대체하므로 그 부분은 더 이상 텍스트로 만들지 않는다 — 대신 테이블을
`ReportRow` 리스트에서 직접 채운다.

### 썸네일 생성과 캐싱

`PreviewWorker`/`ScoreWorker`(이미 스캔·스코어링을 도는 백그라운드 QThread)
안에서, 사진 하나를 처리한 직후 Pillow로 축소한다:

```python
img = Image.open(path)
img.thumbnail((64, 64))
```

`QPixmap`은 GUI 스레드 밖에서 만들면 안전하지 않으므로, 캐시에는 **PIL
Image**를 그대로 저장한다 (`self._thumbnail_cache: dict[Path, tuple[float,int,Image.Image]]`,
기존 `scan_cache`/`score_cache`와 같은 `(mtime, size, 값)` 키 패턴 — 앱 세션
동안만 유지, 파일이 바뀌면 다시 생성).

테이블에 행을 채우는 시점(메인 스레드)에 캐시된 PIL 이미지를 `QPixmap`으로
변환한다:

```python
from PIL.ImageQt import ImageQt
from PySide6.QtGui import QPixmap

qim = ImageQt(pil_img.convert("RGBA"))
pixmap = QPixmap.fromImage(qim)
```

같은 파일을 다시 미리보기해도(폴더 추가 후 재실행 등) 이미 캐시된 썸네일은
재생성하지 않는다 — 앞서 만든 스캔/스코어링 캐시와 동일한 이점.

### 실패 처리

이미지를 열 수 없는 파일(손상 등)은 이미 `PhotoMetadata.error`/
`PhotoScore.error`로 표시되므로, 그 행은 썸네일 대신 placeholder 아이콘(또는
빈 셀)을 넣고 사유 컬럼에 에러 메시지를 그대로 보여준다. 썸네일 생성 자체가
실패해도(파일은 열리지만 축소 실패 등) 전체 미리보기가 죽지 않도록
try/except로 감싸고 해당 행만 placeholder 처리한다.

## 2. 드래그앤드롭

`src/gui_dnd.py`:

```python
def extract_dropped_folders(mime_data: QMimeData) -> list[Path]:
    """드롭된 항목 중 실제 존재하는 폴더 경로만 걸러 반환한다."""
    if not mime_data.hasUrls():
        return []
    paths = [Path(url.toLocalFile()) for url in mime_data.urls() if url.isLocalFile()]
    return [p for p in paths if p.is_dir()]
```

각 탭 위젯(또는 그 안의 QListWidget/QLabel)에 `setAcceptDrops(True)`를 걸고
`dragEnterEvent`/`dropEvent`를 얇게 오버라이드해 이 함수를 호출한 뒤, 결과를
**기존 "폴더 추가" 버튼과 동일한 메서드**(`_add_input_dir`, `_choose_folder`
등)에 그대로 넘긴다 — 새 폴더 추가 로직을 중복 구현하지 않는다.

적용 대상: 베스트컷/C컷/시간순 정렬의 입력 폴더 리스트, 정리 탭의 대상 폴더,
병합 출력 폴더. (파일 하나만 드롭하는 경우는 무시 — 폴더만 받는다.)

## 3. 마지막 사용 폴더 기억

`QSettings("FrameSense", "FrameSense")` 하나를 앱 전역에서 공유하고, 탭·역할별
키로 저장한다:

| 키 | 값 |
|---|---|
| `bestcut/input_dirs` | 문자열 리스트 |
| `bestcut/output_dir` | 문자열 |
| `badcut/input_dirs` | 문자열 리스트 |
| `badcut/output_dir` | 문자열 |
| `rename/input_dirs` | 문자열 리스트 |
| `rename/merge_output_dir` | 문자열 |
| `organize/folder` | 문자열 |

각 탭 `__init__`에서 저장된 값을 읽어 폴더 리스트/라벨을 미리 채우고, 폴더가
바뀔 때마다(추가/삭제/선택) 즉시 다시 저장한다. 저장된 경로가 더 이상
존재하지 않으면(외장하드 분리 등) `Path.is_dir()`로 걸러 조용히 무시하고
빈 상태로 시작한다 — 에러를 띄우지 않는다.

## 4. 버전 표시

`src/version.py`:

```python
__version__ = "1.0.0"
```

`gui.py`의 `MainWindow.setWindowTitle`을 `f"FrameSense v{__version__}"`로
바꾸고, `packaging/FrameSense.spec`의 `BUNDLE(...)` 호출에
`info_plist={"CFBundleShortVersionString": __version__, ...}`를 추가한다
(기존 info_plist 항목이 있으면 병합).

## 테스트 전략

- `gui_dnd.py`의 `extract_dropped_folders`는 Qt에 의존하는 `QMimeData`를
  받지만 순수 로직(경로 필터링)이라 pytest에서 `QMimeData`+`QUrl`을 직접
  만들어 단위 테스트 가능.
- 썸네일 생성 함수(예: `make_thumbnail(path) -> Image.Image`, PIL까지만
  다루고 QPixmap 변환 이전 단계)도 Qt 의존 없이 pytest로 테스트 가능 —
  `scoring.py`처럼 순수 함수로 분리한다.
- QSettings 연동과 테이블/드래그앤드롭 이벤트 자체는 기존 GUI 코드처럼
  자동화 테스트 대신 수동 스모크 테스트(이번 세션에서 계속 해온 방식:
  스크립트로 위젯을 직접 생성해 상태 확인)로 검증한다.
- 기존 124+ 개 pytest는 전부 그대로 통과해야 한다 (로직 계층 무변경).

## 리스크 / 알려진 제약

- 썸네일은 파일을 다시 디코드하므로(스코어링에서 이미 한 번 연 파일을 또
  엶) 사진 수가 매우 많으면(수백~수천 장) 미리보기가 느려질 수 있다.
  ponytail: 지금은 단순 재디코드, 체감되면 스코어링 단계의 디코드 결과를
  재사용하도록 최적화.
- QSettings로 자동 채워진 폴더가 이미 존재하지 않는 외부 드라이브를
  가리킬 수 있음 — 위에서 설명한 대로 조용히 무시하고 사용자가 다시
  선택하게 한다.
