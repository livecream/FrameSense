# FrameSense UX 전면 개선 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 베스트컷/C컷 미리보기를 썸네일 있는 테이블로 바꾸고, 모든 폴더 입력 영역에 드래그앤드롭을 붙이고, 탭·역할별로 마지막 사용 폴더를 기억하며, 앱에 첫 버전 번호(1.0.0)를 도입한다.

**Architecture:** 로직 계층(scanner/scoring/selector/report/badcut/rename_by_time/organize/file_ops)은 전혀 건드리지 않는다. 순수 헬퍼 4개(`version.py`, `thumbnails.py`, `gui_dnd.py`, `gui_settings.py`)를 새로 만들고, 기존 4개 탭 위젯(`gui_bestcut_tab.py`, `gui_badcut_tab.py`, `gui_rename_tab.py`, `gui_organize_tab.py`)과 `gui.py`, `packaging/FrameSense.spec`을 그 헬퍼로 얇게 연결한다.

**Tech Stack:** Python, PySide6(Qt), Pillow(PIL.ImageQt로 QPixmap 변환), pytest, PyInstaller.

**Spec:** `docs/superpowers/specs/2026-09-20-ux-overhaul-design.md`

## Global Constraints

- 로직 계층 파일(scanner.py/scoring.py/selector.py/report.py/badcut.py/rename_by_time.py/organize.py/file_ops.py)은 이 계획의 어떤 태스크에서도 수정하지 않는다.
- 기존 `gui_format.py`의 `format_preview_summary`/`format_badcut_preview` 함수와 그 pytest는 그대로 둔다 (삭제/변경 금지) — 새 헤더 전용 함수를 추가만 한다.
- 새로 만드는 모든 순수 로직 파일(`thumbnails.py`, `gui_dnd.py`, `gui_settings.py`, `gui_format.py` 추가분)은 pytest로 테스트한다. Qt 위젯 자체의 동작(테이블 채우기, 드래그앤드롭 이벤트, QSettings 실제 연결)은 이 저장소의 기존 관례대로 자동화 테스트 대신 수동 스모크 테스트 스크립트로 검증한다.
- 각 태스크는 `pytest`(로직 계층)로 회귀를 확인한 뒤 커밋한다. 전체 스위트는 134개 이상 통과 상태를 유지해야 한다.
- 삭제 예외(빈 폴더/완전 동일 중복 파일) 등 기존 CLAUDE.md 원칙은 이 계획에서 건드리지 않는다.

---

### Task 1: 버전 상수 도입

**Files:**
- Create: `src/version.py`
- Modify: `src/gui.py` (import + `setWindowTitle` 줄)
- Modify: `packaging/FrameSense.spec` (`BUNDLE(...)` 호출)
- Test: `tests/test_version.py`

**Interfaces:**
- Produces: `version.__version__: str` — 이후 모든 태스크와 무관하게 `gui.py`와 패키징 스펙에서만 쓰임.

- [ ] **Step 1: Write the failing test**

`tests/test_version.py`:
```python
from version import __version__


def test_version_is_semver_string():
    parts = __version__.split(".")
    assert len(parts) == 3
    assert all(part.isdigit() for part in parts)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/taek/Claude/FrameSense && ./.venv/bin/python -m pytest tests/test_version.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'version'`

- [ ] **Step 3: Write minimal implementation**

`src/version.py`:
```python
"""FrameSense 앱 버전. gui.py 창 제목과 packaging/FrameSense.spec의
CFBundleShortVersionString이 이 값을 그대로 쓴다 (버전 드리프트 방지)."""

__version__ = "1.0.0"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Users/taek/Claude/FrameSense && ./.venv/bin/python -m pytest tests/test_version.py -v`
Expected: PASS

- [ ] **Step 5: 창 제목에 버전 표시**

`src/gui.py`의 import 블록에 한 줄 추가 (기존 `from gui_photo_selection_tab import PhotoSelectionTab` 바로 아래):
```python
from gui_photo_selection_tab import PhotoSelectionTab
from version import __version__
```

`self.setWindowTitle("FrameSense")`를 찾아 아래로 교체:
```python
        self.setWindowTitle(f"FrameSense v{__version__}")
```

- [ ] **Step 6: 패키징 스펙에 버전 반영**

`packaging/FrameSense.spec` 맨 위(`# -*- mode: python ; coding: utf-8 -*-` 바로 아래)에 추가:
```python
import sys as _sys
from pathlib import Path as _Path

_sys.path.insert(0, str(_Path(__file__).resolve().parent.parent / "src"))
from version import __version__
```

파일 끝의 `app = BUNDLE(...)` 블록을 찾아 아래로 교체:
```python
app = BUNDLE(
    coll,
    name="FrameSense.app",
    bundle_identifier="com.framesense.app",
    info_plist={
        "CFBundleShortVersionString": __version__,
        "CFBundleVersion": __version__,
    },
)
```

- [ ] **Step 7: 전체 회귀 테스트**

Run: `cd /Users/taek/Claude/FrameSense && ./.venv/bin/python -m pytest -q`
Expected: 이전과 같은 개수 + 1(새 테스트) PASS, 실패 없음.

- [ ] **Step 8: 수동 확인 (패키징)**

Run: `cd /Users/taek/Claude/FrameSense && .venv/bin/pyinstaller packaging/FrameSense.spec --distpath dist --workpath build -y`
그 다음: `plutil -p dist/FrameSense.app/Contents/Info.plist | grep CFBundleShortVersionString`
Expected: `"CFBundleShortVersionString" => "1.0.0"` 출력. 앱을 열어(`open dist/FrameSense.app`) 창 제목이 "FrameSense v1.0.0"인지 확인.

- [ ] **Step 9: Commit**

```bash
cd /Users/taek/Claude/FrameSense
git add src/version.py src/gui.py packaging/FrameSense.spec tests/test_version.py
git commit -m "feat: introduce app version 1.0.0"
```

---

### Task 2: 썸네일 생성 순수 함수

**Files:**
- Create: `src/thumbnails.py`
- Test: `tests/test_thumbnails.py`

**Interfaces:**
- Produces: `thumbnails.make_thumbnail(path: Path, size: tuple[int, int] = (64, 64)) -> PIL.Image.Image | None`, `thumbnails.THUMBNAIL_SIZE: tuple[int, int]` — Task 6/8이 이 함수를 백그라운드 QThread 안에서 호출한다.

- [ ] **Step 1: Write the failing tests**

`tests/test_thumbnails.py`:
```python
from PIL import Image

from thumbnails import make_thumbnail


def _make_jpeg(path, size=(200, 100), color=(200, 50, 50)):
    Image.new("RGB", size, color).save(path, "jpeg")
    return path


def test_make_thumbnail_shrinks_within_bounds(tmp_path):
    path = _make_jpeg(tmp_path / "a.jpg", size=(200, 100))

    thumb = make_thumbnail(path, size=(64, 64))

    assert thumb is not None
    assert thumb.width <= 64
    assert thumb.height <= 64


def test_make_thumbnail_preserves_aspect_ratio(tmp_path):
    path = _make_jpeg(tmp_path / "a.jpg", size=(200, 100))  # 2:1 비율

    thumb = make_thumbnail(path, size=(64, 64))

    assert thumb.width == 64
    assert thumb.height == 32


def test_make_thumbnail_returns_none_for_corrupt_file(tmp_path):
    path = tmp_path / "broken.jpg"
    path.write_bytes(b"not an image")

    assert make_thumbnail(path) is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/taek/Claude/FrameSense && ./.venv/bin/python -m pytest tests/test_thumbnails.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'thumbnails'`

- [ ] **Step 3: Write minimal implementation**

`src/thumbnails.py`:
```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/taek/Claude/FrameSense && ./.venv/bin/python -m pytest tests/test_thumbnails.py -v`
Expected: 3 PASS

- [ ] **Step 5: Commit**

```bash
cd /Users/taek/Claude/FrameSense
git add src/thumbnails.py tests/test_thumbnails.py
git commit -m "feat: add pure thumbnail generation helper"
```

---

### Task 3: 드래그앤드롭 헬퍼 함수

**Files:**
- Create: `src/gui_dnd.py`
- Test: `tests/test_gui_dnd.py`

**Interfaces:**
- Produces: `gui_dnd.extract_dropped_folders(mime_data: QMimeData) -> list[Path]` — Task 7/9/10/11이 각 탭의 `dropEvent`에서 호출한다.

- [ ] **Step 1: Write the failing tests**

`tests/test_gui_dnd.py`:
```python
from PySide6.QtCore import QMimeData, QUrl

from gui_dnd import extract_dropped_folders


def test_extract_dropped_folders_filters_to_existing_dirs(tmp_path):
    folder = tmp_path / "sub"
    folder.mkdir()
    file_path = tmp_path / "a.txt"
    file_path.write_text("hi")

    mime = QMimeData()
    mime.setUrls([QUrl.fromLocalFile(str(folder)), QUrl.fromLocalFile(str(file_path))])

    result = extract_dropped_folders(mime)

    assert result == [folder]


def test_extract_dropped_folders_returns_empty_when_no_urls():
    mime = QMimeData()

    assert extract_dropped_folders(mime) == []


def test_extract_dropped_folders_ignores_nonexistent_paths(tmp_path):
    missing = tmp_path / "does_not_exist"
    mime = QMimeData()
    mime.setUrls([QUrl.fromLocalFile(str(missing))])

    assert extract_dropped_folders(mime) == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/taek/Claude/FrameSense && ./.venv/bin/python -m pytest tests/test_gui_dnd.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'gui_dnd'`

- [ ] **Step 3: Write minimal implementation**

`src/gui_dnd.py`:
```python
"""드래그앤드롭으로 떨어뜨린 항목 중 실제 존재하는 폴더 경로만 걸러내는
공용 헬퍼. 여러 탭의 dragEnterEvent/dropEvent에서 재사용한다."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QMimeData


def extract_dropped_folders(mime_data: QMimeData) -> list[Path]:
    """mime_data에 담긴 로컬 파일 URL 중 실제 폴더인 것만 반환한다."""
    if not mime_data.hasUrls():
        return []
    paths = [Path(url.toLocalFile()) for url in mime_data.urls() if url.isLocalFile()]
    return [p for p in paths if p.is_dir()]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/taek/Claude/FrameSense && ./.venv/bin/python -m pytest tests/test_gui_dnd.py -v`
Expected: 3 PASS

- [ ] **Step 5: Commit**

```bash
cd /Users/taek/Claude/FrameSense
git add src/gui_dnd.py tests/test_gui_dnd.py
git commit -m "feat: add drag-and-drop folder extraction helper"
```

---

### Task 4: QSettings 폴더 기억 헬퍼

**Files:**
- Create: `src/gui_settings.py`
- Test: `tests/test_gui_settings.py`

**Interfaces:**
- Produces: `gui_settings.make_settings() -> QSettings`, `gui_settings.load_folder_list(settings, key) -> list[Path]`, `gui_settings.save_folder_list(settings, key, folders: list[Path]) -> None`, `gui_settings.load_folder(settings, key) -> Path | None`, `gui_settings.save_folder(settings, key, folder: Path | None) -> None` — Task 7/9/10/11이 각 탭에서 호출한다.

- [ ] **Step 1: Write the failing tests**

`tests/test_gui_settings.py`:
```python
from PySide6.QtCore import QSettings

from gui_settings import load_folder, load_folder_list, save_folder, save_folder_list


def _settings(tmp_path) -> QSettings:
    return QSettings(str(tmp_path / "test_settings.ini"), QSettings.Format.IniFormat)


def test_save_and_load_folder_list_round_trip(tmp_path):
    settings = _settings(tmp_path)
    folder_a = tmp_path / "a"
    folder_b = tmp_path / "b"
    folder_a.mkdir()
    folder_b.mkdir()

    save_folder_list(settings, "test/dirs", [folder_a, folder_b])
    settings.sync()

    assert load_folder_list(settings, "test/dirs") == [folder_a, folder_b]


def test_save_and_load_single_item_folder_list_round_trip(tmp_path):
    # QSettings는 1개짜리 리스트를 문자열로 돌려주는 경우가 있어 별도로 검증한다.
    settings = _settings(tmp_path)
    folder = tmp_path / "a"
    folder.mkdir()

    save_folder_list(settings, "test/dirs", [folder])
    settings.sync()

    assert load_folder_list(settings, "test/dirs") == [folder]


def test_load_folder_list_filters_out_missing_paths(tmp_path):
    settings = _settings(tmp_path)
    existing = tmp_path / "exists"
    existing.mkdir()
    missing = tmp_path / "missing"

    save_folder_list(settings, "test/dirs", [existing, missing])
    settings.sync()

    assert load_folder_list(settings, "test/dirs") == [existing]


def test_load_folder_list_returns_empty_when_key_unset(tmp_path):
    settings = _settings(tmp_path)

    assert load_folder_list(settings, "test/unset") == []


def test_save_and_load_folder_round_trip(tmp_path):
    settings = _settings(tmp_path)
    folder = tmp_path / "a"
    folder.mkdir()

    save_folder(settings, "test/dir", folder)
    settings.sync()

    assert load_folder(settings, "test/dir") == folder


def test_load_folder_returns_none_when_missing_on_disk(tmp_path):
    settings = _settings(tmp_path)
    missing = tmp_path / "missing"

    save_folder(settings, "test/dir", missing)
    settings.sync()

    assert load_folder(settings, "test/dir") is None


def test_load_folder_returns_none_when_unset(tmp_path):
    settings = _settings(tmp_path)

    assert load_folder(settings, "test/unset") is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/taek/Claude/FrameSense && ./.venv/bin/python -m pytest tests/test_gui_settings.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'gui_settings'`

- [ ] **Step 3: Write minimal implementation**

`src/gui_settings.py`:
```python
"""탭·역할별로 마지막 사용 폴더를 QSettings에 저장/복원하는 공용 헬퍼.
존재하지 않는 경로(외장 드라이브 분리 등)는 조용히 걸러낸다.

QSettings는 1개짜리 문자열 리스트를 저장했다가 읽으면 리스트가 아니라
문자열 하나로 돌아오는 경우가 있어(백엔드에 따라 다름), load_folder_list가
그 경우를 문자열 1개짜리 리스트로 취급해 방어한다."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSettings

ORG_NAME = "FrameSense"
APP_NAME = "FrameSense"


def make_settings() -> QSettings:
    return QSettings(ORG_NAME, APP_NAME)


def load_folder_list(settings: QSettings, key: str) -> list[Path]:
    raw = settings.value(key, [])
    if not raw:
        return []
    if isinstance(raw, str):
        raw = [raw]
    return [p for p in (Path(s) for s in raw) if p.is_dir()]


def save_folder_list(settings: QSettings, key: str, folders: list[Path]) -> None:
    settings.setValue(key, [str(p) for p in folders])


def load_folder(settings: QSettings, key: str) -> Path | None:
    raw = settings.value(key, "")
    if not raw:
        return None
    path = Path(raw)
    return path if path.is_dir() else None


def save_folder(settings: QSettings, key: str, folder: Path | None) -> None:
    settings.setValue(key, str(folder) if folder is not None else "")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/taek/Claude/FrameSense && ./.venv/bin/python -m pytest tests/test_gui_settings.py -v`
Expected: 7 PASS

- [ ] **Step 5: Commit**

```bash
cd /Users/taek/Claude/FrameSense
git add src/gui_settings.py tests/test_gui_settings.py
git commit -m "feat: add per-tab QSettings folder memory helper"
```

---

### Task 5: gui_format.py에 헤더 전용 포맷 함수 추가

기존 `format_preview_summary`/`format_badcut_preview`는 그대로 두고(테이블이 대체할 개별 파일 나열까지 포함된 함수라 기존 pytest가 계속 이걸 검증함), 테이블 위에 놓을 **집계 한 줄만** 만드는 함수 두 개를 추가한다.

**Files:**
- Modify: `src/gui_format.py`
- Test: `tests/test_gui_format.py`

**Interfaces:**
- Consumes: `report.ReportRow` (기존 필드: `path, scene_id, sharpness, exposure, face, total, selected, reason`)
- Produces: `gui_format.format_preview_header(rows: list[ReportRow]) -> str`, `gui_format.format_badcut_header(rows: list[ReportRow]) -> str` — Task 6/8이 테이블 위 라벨에 쓴다.

- [ ] **Step 1: Write the failing tests**

`tests/test_gui_format.py` 맨 끝에 추가:
```python
def test_format_preview_header_counts_scenes_and_selection():
    rows = [
        _row("a.jpg", 1, True, "선택됨"),
        _row("b.jpg", 1, False, "제외"),
        _row("c.jpg", 2, True, "선택됨"),
    ]

    header = format_preview_header(rows)

    assert "2개 장면" in header
    assert "3장 중 2장 선택" in header


def test_format_badcut_header_counts_and_no_scores_when_all_error():
    rows = [
        _row("a.jpg", 0, False, "판정 불가: 손상"),
    ]

    header = format_badcut_header(rows)

    assert "1장 중 0장 C컷 판정" in header
```

같은 파일 상단 import에 두 함수 추가:
```python
from gui_format import (
    format_apply_summary,
    format_badcut_header,
    format_badcut_preview,
    format_duplicate_report,
    format_folder_summary,
    format_preview_header,
    format_preview_summary,
    format_rename_apply_summary,
    format_rename_preview,
)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/taek/Claude/FrameSense && ./.venv/bin/python -m pytest tests/test_gui_format.py -v`
Expected: FAIL with `ImportError: cannot import name 'format_badcut_header'`

- [ ] **Step 3: Write minimal implementation**

`src/gui_format.py`에서 `format_preview_summary` 함수 바로 아래(그 함수는 그대로 두고)에 추가:
```python
def format_preview_header(rows: list[ReportRow]) -> str:
    """장면 수/선택 수 집계 한 줄. 개별 파일 나열은 GUI가 테이블로 그린다."""
    scene_ids = {row.scene_id for row in rows}
    total = len(rows)
    selected = sum(1 for r in rows if r.selected)
    return f"{len(scene_ids)}개 장면, {total}장 중 {selected}장 선택"
```

`format_badcut_preview` 함수 바로 위에 추가:
```python
def format_badcut_header(rows: list[ReportRow]) -> str:
    """C컷 판정 개수/점수 분포 집계. 개별 파일 나열은 GUI가 테이블로 그린다."""
    scored_rows = [r for r in rows if not r.reason.startswith("판정 불가")]
    bad_rows = [r for r in rows if r.selected]
    lines = [f"{len(rows)}장 중 {len(bad_rows)}장 C컷 판정"]

    sharpness_values = [r.sharpness for r in scored_rows]
    if sharpness_values:
        lines.append(
            f"선명도 분포: 최소 {min(sharpness_values):.1f} / "
            f"평균 {sum(sharpness_values) / len(sharpness_values):.1f} / "
            f"최대 {max(sharpness_values):.1f}"
        )

    face_values = [r.face for r in scored_rows if r.face is not None]
    if face_values:
        lines.append(
            f"눈뜸 점수 분포(얼굴 검출된 {len(face_values)}장): "
            f"최소 {min(face_values):.2f} / "
            f"평균 {sum(face_values) / len(face_values):.2f} / "
            f"최대 {max(face_values):.2f}"
        )
    return "\n".join(lines)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/taek/Claude/FrameSense && ./.venv/bin/python -m pytest tests/test_gui_format.py -v`
Expected: 모든 테스트(기존 + 새 2개) PASS

- [ ] **Step 5: 전체 회귀 테스트**

Run: `cd /Users/taek/Claude/FrameSense && ./.venv/bin/python -m pytest -q`
Expected: 전부 PASS, 실패 없음.

- [ ] **Step 6: Commit**

```bash
cd /Users/taek/Claude/FrameSense
git add src/gui_format.py tests/test_gui_format.py
git commit -m "feat: add header-only summary formatters for preview tables"
```

---

### Task 6: 베스트컷 탭 — 테이블 + 썸네일

**Files:**
- Modify: `src/gui_bestcut_tab.py`

**Interfaces:**
- Consumes: `thumbnails.make_thumbnail`, `gui_format.format_preview_header`, `report.ReportRow`
- Produces: `BestCutTab._thumbnail_cache: dict[Path, tuple[float, int, Image.Image | None]]` (다른 태스크는 참조하지 않음, 내부 상태)

- [ ] **Step 1: import 추가 및 PreviewWorker에 썸네일 캐시 파라미터 추가**

`src/gui_bestcut_tab.py` 상단 import 블록을 아래로 교체:
```python
from __future__ import annotations

import subprocess
from pathlib import Path

from PIL.ImageQt import ImageQt
from PySide6.QtCore import QSize, Qt, QThread, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QRadioButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from file_ops import FileOpResult, apply_selection
from grouping import group_by_time_gap
from gui_format import format_apply_summary, format_preview_header
from report import ReportRow, build_report
from scanner import scan_and_extract_many
from thumbnails import make_thumbnail
```

`PreviewWorker.__init__`을 찾아 아래로 교체:
```python
    def __init__(
        self,
        input_dirs: list[Path],
        recursive: bool = True,
        scan_cache: dict | None = None,
        score_cache: dict | None = None,
        thumbnail_cache: dict | None = None,
    ) -> None:
        super().__init__()
        self._input_dirs = input_dirs
        self._recursive = recursive
        self._scan_cache = scan_cache
        self._score_cache = score_cache
        self._thumbnail_cache = thumbnail_cache
```

`PreviewWorker.run`의 마지막 줄(`self.finished_ok.emit(rows)`) 바로 위에 한 줄 추가:
```python
            rows = build_report(groups, on_progress=on_group_progress, cache=self._score_cache)
            self._generate_thumbnails(rows)
            self.finished_ok.emit(rows)
```

같은 클래스에 `run` 메서드 바로 아래로 새 메서드 추가:
```python

    def _generate_thumbnails(self, rows: list[ReportRow]) -> None:
        if self._thumbnail_cache is None:
            return
        for row in rows:
            stat = row.path.stat()
            key = (stat.st_mtime, stat.st_size)
            cached = self._thumbnail_cache.get(row.path)
            if cached is not None and cached[:2] == key:
                continue
            self._thumbnail_cache[row.path] = (*key, make_thumbnail(row.path))
```

- [ ] **Step 2: BestCutTab에 썸네일 캐시와 테이블 위젯 추가**

`self._score_cache: dict = {}` 바로 아래에 한 줄 추가:
```python
        self._score_cache: dict = {}
        self._thumbnail_cache: dict = {}
```

`self._summary_text = QPlainTextEdit()` ~ `self._summary_text.setReadOnly(True)` 바로 아래에 테이블 생성 코드 추가:
```python
        self._summary_text = QPlainTextEdit()
        self._summary_text.setReadOnly(True)

        self._table = QTableWidget(0, 5)
        self._table.setHorizontalHeaderLabels(["썸네일", "파일명", "장면", "선택여부", "사유"])
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.setIconSize(QSize(64, 64))
```

`layout.addWidget(self._summary_text)` 바로 아래에 한 줄 추가:
```python
        layout.addWidget(self._summary_text)
        layout.addWidget(self._table)
```

- [ ] **Step 3: PreviewWorker 생성 시 썸네일 캐시 전달**

`_run_preview`의 `self._preview_worker = PreviewWorker(...)` 호출을 찾아 아래로 교체:
```python
        self._preview_worker = PreviewWorker(
            list(self._input_dirs),
            scan_cache=self._scan_cache,
            score_cache=self._score_cache,
            thumbnail_cache=self._thumbnail_cache,
        )
```

- [ ] **Step 4: 미리보기 완료 시 헤더+테이블 갱신**

`_on_preview_done`을 찾아 아래로 교체:
```python
    def _on_preview_done(self, rows: list[ReportRow]) -> None:
        self._busy = False
        self._status_label.setText("완료")
        self._rows = rows
        self._preview_button.setEnabled(True)
        self._apply_button.setEnabled(bool(rows) and self._output_dir is not None)
        self._summary_text.setPlainText(format_preview_header(rows))
        self._populate_table(rows)

    def _populate_table(self, rows: list[ReportRow]) -> None:
        self._table.setRowCount(len(rows))
        for i, row in enumerate(rows):
            thumb_item = QTableWidgetItem()
            pixmap = self._thumbnail_pixmap(row.path)
            if pixmap is not None:
                thumb_item.setData(Qt.ItemDataRole.DecorationRole, pixmap)
            self._table.setItem(i, 0, thumb_item)
            self._table.setItem(i, 1, QTableWidgetItem(row.path.name))
            self._table.setItem(i, 2, QTableWidgetItem(str(row.scene_id)))
            self._table.setItem(i, 3, QTableWidgetItem("선택" if row.selected else "제외"))
            self._table.setItem(i, 4, QTableWidgetItem(row.reason))
        self._table.resizeRowsToContents()

    def _thumbnail_pixmap(self, path: Path) -> QPixmap | None:
        cached = self._thumbnail_cache.get(path)
        if cached is None or cached[2] is None:
            return None
        qim = ImageQt(cached[2].convert("RGBA"))
        return QPixmap.fromImage(qim)
```

- [ ] **Step 5: 입력 폴더가 바뀌면 테이블도 비우기**

`_invalidate_preview`를 찾아 아래로 교체:
```python
    def _invalidate_preview(self) -> None:
        self._rows = None
        self._apply_button.setEnabled(False)
        self._open_output_button.setEnabled(False)
        self._table.setRowCount(0)
```

- [ ] **Step 6: 컴파일 확인**

Run: `cd /Users/taek/Claude/FrameSense && python3 -m py_compile src/gui_bestcut_tab.py`
Expected: 에러 없이 종료.

- [ ] **Step 7: 수동 스모크 테스트**

Run:
```bash
cd /Users/taek/Claude/FrameSense && ./.venv/bin/python -c "
import sys, tempfile, datetime
sys.path.insert(0, 'src')
from pathlib import Path
import piexif
from PIL import Image
from PySide6.QtWidgets import QApplication
app = QApplication([])
from gui_bestcut_tab import BestCutTab, PreviewWorker

def make_jpeg(path, dt):
    img = Image.new('RGB', (32, 24), (200, 50, 50))
    exif_dict = {'0th': {}, 'Exif': {piexif.ExifIFD.DateTimeOriginal: dt.strftime('%Y:%m:%d %H:%M:%S').encode()}, '1st': {}, 'thumbnail': None}
    img.save(path, 'jpeg', exif=piexif.dump(exif_dict))

with tempfile.TemporaryDirectory() as d:
    d = Path(d)
    make_jpeg(d / 'a.jpg', datetime.datetime(2024,1,1,10,0,0))
    tab = BestCutTab()
    w = PreviewWorker([d], scan_cache=tab._scan_cache, score_cache=tab._score_cache, thumbnail_cache=tab._thumbnail_cache)
    w.finished_ok.connect(lambda rows: tab._on_preview_done(rows))
    w.run()
    print('table row count:', tab._table.rowCount())
    print('table col 1 (filename):', tab._table.item(0, 1).text())
    print('thumbnail cached:', tab._thumbnail_cache[d / 'a.jpg'][2] is not None)
    assert tab._table.rowCount() == 1
    assert tab._table.item(0, 1).text() == 'a.jpg'
print('OK')
"
```
Expected: `OK` 출력, assert 실패 없음.

- [ ] **Step 8: 전체 회귀 테스트**

Run: `cd /Users/taek/Claude/FrameSense && ./.venv/bin/python -m pytest -q`
Expected: 전부 PASS.

- [ ] **Step 9: Commit**

```bash
cd /Users/taek/Claude/FrameSense
git add src/gui_bestcut_tab.py
git commit -m "feat: replace bestcut preview text with thumbnail table"
```

---

### Task 7: 베스트컷 탭 — 드래그앤드롭 + 폴더 기억

**Files:**
- Modify: `src/gui_bestcut_tab.py`

**Interfaces:**
- Consumes: `gui_dnd.extract_dropped_folders`, `gui_settings.make_settings/load_folder_list/save_folder_list/load_folder/save_folder`

- [ ] **Step 1: import 추가**

import 블록의 `from thumbnails import make_thumbnail` 바로 아래에 추가:
```python
from thumbnails import make_thumbnail
from gui_dnd import extract_dropped_folders
from gui_settings import load_folder, load_folder_list, make_settings, save_folder, save_folder_list
```

- [ ] **Step 2: 폴더 추가 로직을 공용 메서드로 추출**

`_add_input_dir`을 찾아 아래로 교체:
```python
    def _add_input_dir(self) -> None:
        directory = QFileDialog.getExistingDirectory(self, "입력 폴더 추가")
        if directory:
            self._add_folders([Path(directory)])

    def _add_folders(self, folders: list[Path]) -> None:
        for folder in folders:
            if folder not in self._input_dirs:
                self._input_dirs.append(folder)
                self._folder_list.addItem(str(folder))
        self._invalidate_preview()
        save_folder_list(self._settings, "bestcut/input_dirs", self._input_dirs)
```

`_remove_selected_input_dir` 끝에 저장 호출 추가:
```python
    def _remove_selected_input_dir(self) -> None:
        for item in self._folder_list.selectedItems():
            index = self._folder_list.row(item)
            self._folder_list.takeItem(index)
            del self._input_dirs[index]
        self._invalidate_preview()
        save_folder_list(self._settings, "bestcut/input_dirs", self._input_dirs)
```

`_choose_output_dir` 끝에 저장 호출 추가:
```python
    def _choose_output_dir(self) -> None:
        directory = QFileDialog.getExistingDirectory(self, "출력 폴더 선택")
        if directory:
            self._output_dir = Path(directory)
            self._output_label.setText(f"출력 폴더: {directory}")
            self._apply_button.setEnabled(bool(self._rows))
            self._open_output_button.setEnabled(False)
            save_folder(self._settings, "bestcut/output_dir", self._output_dir)
```

- [ ] **Step 3: 드래그앤드롭 이벤트 오버라이드 추가**

`is_busy` 프로퍼티 바로 아래에 추가:
```python
    @property
    def is_busy(self) -> bool:
        return self._busy

    def dragEnterEvent(self, event) -> None:  # noqa: N802 - Qt override signature
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event) -> None:  # noqa: N802 - Qt override signature
        folders = extract_dropped_folders(event.mimeData())
        if folders:
            self._add_folders(folders)
        event.acceptProposedAction()
```

- [ ] **Step 4: __init__에 setAcceptDrops + 설정 로드 추가**

`self._thumbnail_cache: dict = {}` 바로 아래에 추가:
```python
        self._thumbnail_cache: dict = {}
        self.setAcceptDrops(True)
        self._settings = make_settings()
```

`self.setLayout(layout)` 바로 위(마지막 줄)에 추가:
```python
        for folder in load_folder_list(self._settings, "bestcut/input_dirs"):
            self._input_dirs.append(folder)
            self._folder_list.addItem(str(folder))
        restored_output = load_folder(self._settings, "bestcut/output_dir")
        if restored_output is not None:
            self._output_dir = restored_output
            self._output_label.setText(f"출력 폴더: {restored_output}")

        self.setLayout(layout)
```

- [ ] **Step 5: 컴파일 확인**

Run: `cd /Users/taek/Claude/FrameSense && python3 -m py_compile src/gui_bestcut_tab.py`
Expected: 에러 없이 종료.

- [ ] **Step 6: 수동 스모크 테스트**

Run:
```bash
cd /Users/taek/Claude/FrameSense && ./.venv/bin/python -c "
import sys, tempfile
sys.path.insert(0, 'src')
from pathlib import Path
from PySide6.QtCore import QMimeData, QUrl, QSettings
from PySide6.QtWidgets import QApplication
app = QApplication([])
import gui_settings

with tempfile.TemporaryDirectory() as settings_dir, tempfile.TemporaryDirectory() as photo_dir:
    ini = str(Path(settings_dir) / 'test.ini')
    gui_settings.make_settings = lambda: QSettings(ini, QSettings.Format.IniFormat)
    from gui_bestcut_tab import BestCutTab

    tab = BestCutTab()
    folder = Path(photo_dir)
    mime = QMimeData()
    mime.setUrls([QUrl.fromLocalFile(str(folder))])
    tab.dropEvent(type('E', (), {'mimeData': lambda self: mime, 'acceptProposedAction': lambda self: None})())
    print('input_dirs after drop:', tab._input_dirs)
    assert tab._input_dirs == [folder]

    tab2 = BestCutTab()
    print('input_dirs restored in new instance:', tab2._input_dirs)
    assert tab2._input_dirs == [folder]
print('OK')
"
```
Expected: `OK` 출력, assert 실패 없음. (드롭 → 저장 → 새 인스턴스에서 자동 복원까지 확인)

- [ ] **Step 7: 전체 회귀 테스트**

Run: `cd /Users/taek/Claude/FrameSense && ./.venv/bin/python -m pytest -q`
Expected: 전부 PASS.

- [ ] **Step 8: Commit**

```bash
cd /Users/taek/Claude/FrameSense
git add src/gui_bestcut_tab.py
git commit -m "feat: add drag-and-drop and folder memory to bestcut tab"
```

---

### Task 8: C컷 탭 — 테이블 + 썸네일

**Files:**
- Modify: `src/gui_badcut_tab.py`

**Interfaces:**
- Consumes: `thumbnails.make_thumbnail`, `gui_format.format_badcut_header`, `report.ReportRow`
- Produces: `BadCutTab._thumbnail_cache: dict[Path, tuple[float, int, Image.Image | None]]`

C컷은 스코어링(ScoreWorker, 백그라운드)과 임계값 재분류(`_reclassify`, 메인 스레드)가 분리돼 있다 — 썸네일은 스코어링 직후 한 번만 만들면 되므로 ScoreWorker 쪽에 붙인다. `_reclassify`는 임계값이 바뀔 때마다 실행되므로 테이블도 그때마다 다시 채운다(썸네일은 캐시에서 재사용, 재생성 없음).

- [ ] **Step 1: import 추가 및 ScoreWorker에 썸네일 캐시 파라미터 추가**

`src/gui_badcut_tab.py` 상단 import 블록을 아래로 교체:
```python
from __future__ import annotations

from pathlib import Path

from PIL.ImageQt import ImageQt
from PySide6.QtCore import QSize, Qt, QThread, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from badcut import BadCutThresholds, classify_badcut, score_for_badcut
from file_ops import FileOpResult, apply_selection
from gui_format import format_apply_summary, format_badcut_header
from report import ReportRow
from scanner import PhotoMetadata, scan_and_extract_many
from scoring import PhotoScore
from thumbnails import make_thumbnail
```

`ScoreWorker.__init__`을 찾아 아래로 교체:
```python
    def __init__(
        self,
        input_dirs: list[Path],
        recursive: bool,
        scan_cache: dict | None = None,
        score_cache: dict | None = None,
        thumbnail_cache: dict | None = None,
    ) -> None:
        super().__init__()
        self._input_dirs = input_dirs
        self._recursive = recursive
        self._scan_cache = scan_cache
        self._score_cache = score_cache
        self._thumbnail_cache = thumbnail_cache
```

`ScoreWorker.run`의 마지막 줄(`self.finished_ok.emit(photos, scores)`) 바로 위에 한 줄 추가:
```python
            scores = score_for_badcut(photos, on_progress=on_score_progress, cache=self._score_cache)
            self._generate_thumbnails(photos)
            self.finished_ok.emit(photos, scores)
```

같은 클래스에 `run` 메서드 바로 아래로 새 메서드 추가:
```python

    def _generate_thumbnails(self, photos: list[PhotoMetadata]) -> None:
        if self._thumbnail_cache is None:
            return
        for meta in photos:
            stat = meta.path.stat()
            key = (stat.st_mtime, stat.st_size)
            cached = self._thumbnail_cache.get(meta.path)
            if cached is not None and cached[:2] == key:
                continue
            self._thumbnail_cache[meta.path] = (*key, make_thumbnail(meta.path))
```

- [ ] **Step 2: BadCutTab에 썸네일 캐시와 테이블 위젯 추가**

`self._score_cache: dict = {}` 바로 아래에 한 줄 추가:
```python
        self._score_cache: dict = {}
        self._thumbnail_cache: dict = {}
```

`self._summary_text = QPlainTextEdit()` ~ `self._summary_text.setReadOnly(True)` 바로 아래에 테이블 생성 코드 추가:
```python
        self._summary_text = QPlainTextEdit()
        self._summary_text.setReadOnly(True)

        self._table = QTableWidget(0, 6)
        self._table.setHorizontalHeaderLabels(["썸네일", "파일명", "판정", "선명도", "눈뜸", "사유"])
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.setIconSize(QSize(64, 64))
```

`layout.addWidget(self._summary_text)` 바로 아래에 한 줄 추가:
```python
        layout.addWidget(self._summary_text)
        layout.addWidget(self._table)
```

- [ ] **Step 3: ScoreWorker 생성 시 썸네일 캐시 전달**

`_run_preview`의 `self._score_worker = ScoreWorker(...)` 호출을 찾아 아래로 교체:
```python
        self._score_worker = ScoreWorker(
            list(self._input_dirs),
            self._recursive_checkbox.isChecked(),
            scan_cache=self._scan_cache,
            score_cache=self._score_cache,
            thumbnail_cache=self._thumbnail_cache,
        )
```

- [ ] **Step 4: 재분류 시 헤더+테이블 갱신**

`_reclassify`를 찾아 아래로 교체:
```python
    def _reclassify(self) -> None:
        thresholds = BadCutThresholds(
            min_sharpness=self._min_sharpness_spin.value(),
            min_eyes_open=self._min_eyes_open_spin.value(),
        )
        rows = classify_badcut(self._photos, self._scores, thresholds)
        self._rows = rows
        bad_count = sum(1 for r in rows if r.selected)
        self._apply_button.setEnabled(bad_count > 0 and self._output_dir is not None)
        self._summary_text.setPlainText(format_badcut_header(rows))
        self._populate_table(rows)

    def _populate_table(self, rows: list[ReportRow]) -> None:
        self._table.setRowCount(len(rows))
        for i, row in enumerate(rows):
            thumb_item = QTableWidgetItem()
            pixmap = self._thumbnail_pixmap(row.path)
            if pixmap is not None:
                thumb_item.setData(Qt.ItemDataRole.DecorationRole, pixmap)
            self._table.setItem(i, 0, thumb_item)
            self._table.setItem(i, 1, QTableWidgetItem(row.path.name))
            self._table.setItem(i, 2, QTableWidgetItem("C컷" if row.selected else "정상"))
            self._table.setItem(i, 3, QTableWidgetItem(f"{row.sharpness:.1f}"))
            self._table.setItem(i, 4, QTableWidgetItem("" if row.face is None else f"{row.face:.2f}"))
            self._table.setItem(i, 5, QTableWidgetItem(row.reason))
        self._table.resizeRowsToContents()

    def _thumbnail_pixmap(self, path: Path) -> QPixmap | None:
        cached = self._thumbnail_cache.get(path)
        if cached is None or cached[2] is None:
            return None
        qim = ImageQt(cached[2].convert("RGBA"))
        return QPixmap.fromImage(qim)
```

- [ ] **Step 5: 입력 폴더가 바뀌면 테이블도 비우기**

`_invalidate_preview`를 찾아 아래로 교체:
```python
    def _invalidate_preview(self) -> None:
        self._photos = None
        self._scores = None
        self._rows = None
        self._apply_button.setEnabled(False)
        self._table.setRowCount(0)
```

- [ ] **Step 6: 컴파일 확인**

Run: `cd /Users/taek/Claude/FrameSense && python3 -m py_compile src/gui_badcut_tab.py`
Expected: 에러 없이 종료.

- [ ] **Step 7: 수동 스모크 테스트**

Run:
```bash
cd /Users/taek/Claude/FrameSense && ./.venv/bin/python -c "
import sys, tempfile, datetime
sys.path.insert(0, 'src')
from pathlib import Path
import piexif
from PIL import Image
from PySide6.QtWidgets import QApplication
app = QApplication([])
from gui_badcut_tab import BadCutTab, ScoreWorker

def make_jpeg(path, dt):
    img = Image.new('RGB', (32, 24), (200, 50, 50))
    exif_dict = {'0th': {}, 'Exif': {piexif.ExifIFD.DateTimeOriginal: dt.strftime('%Y:%m:%d %H:%M:%S').encode()}, '1st': {}, 'thumbnail': None}
    img.save(path, 'jpeg', exif=piexif.dump(exif_dict))

with tempfile.TemporaryDirectory() as d:
    d = Path(d)
    make_jpeg(d / 'a.jpg', datetime.datetime(2024,1,1,10,0,0))
    tab = BadCutTab()
    w = ScoreWorker([d], False, scan_cache=tab._scan_cache, score_cache=tab._score_cache, thumbnail_cache=tab._thumbnail_cache)
    w.finished_ok.connect(lambda photos, scores: tab._on_scored(photos, scores))
    w.run()
    print('table row count:', tab._table.rowCount())
    assert tab._table.rowCount() == 1
    assert tab._table.item(0, 1).text() == 'a.jpg'
    assert tab._thumbnail_cache[d / 'a.jpg'][2] is not None
print('OK')
"
```
Expected: `OK` 출력, assert 실패 없음.

- [ ] **Step 8: 전체 회귀 테스트**

Run: `cd /Users/taek/Claude/FrameSense && ./.venv/bin/python -m pytest -q`
Expected: 전부 PASS.

- [ ] **Step 9: Commit**

```bash
cd /Users/taek/Claude/FrameSense
git add src/gui_badcut_tab.py
git commit -m "feat: replace badcut preview text with thumbnail table"
```

---

### Task 9: C컷 탭 — 드래그앤드롭 + 폴더 기억

**Files:**
- Modify: `src/gui_badcut_tab.py`

패턴은 Task 7(베스트컷)과 동일하되 키가 `badcut/*`이고, output_dir 활성화 로직이 `bad_count` 기준이라는 점만 다르다.

- [ ] **Step 1: import 추가**

import 블록의 `from thumbnails import make_thumbnail` 바로 아래에 추가:
```python
from thumbnails import make_thumbnail
from gui_dnd import extract_dropped_folders
from gui_settings import load_folder, load_folder_list, make_settings, save_folder, save_folder_list
```

- [ ] **Step 2: 폴더 추가 로직을 공용 메서드로 추출**

`_add_input_dir`을 찾아 아래로 교체:
```python
    def _add_input_dir(self) -> None:
        directory = QFileDialog.getExistingDirectory(self, "입력 폴더 추가")
        if directory:
            self._add_folders([Path(directory)])

    def _add_folders(self, folders: list[Path]) -> None:
        for folder in folders:
            if folder not in self._input_dirs:
                self._input_dirs.append(folder)
                self._folder_list.addItem(str(folder))
        self._invalidate_preview()
        save_folder_list(self._settings, "badcut/input_dirs", self._input_dirs)
```

`_remove_selected_input_dir` 끝에 저장 호출 추가:
```python
    def _remove_selected_input_dir(self) -> None:
        for item in self._folder_list.selectedItems():
            index = self._folder_list.row(item)
            self._folder_list.takeItem(index)
            del self._input_dirs[index]
        self._invalidate_preview()
        save_folder_list(self._settings, "badcut/input_dirs", self._input_dirs)
```

`_choose_output_dir` 끝에 저장 호출 추가:
```python
    def _choose_output_dir(self) -> None:
        directory = QFileDialog.getExistingDirectory(self, "C컷을 옮길 출력 폴더 선택")
        if directory:
            self._output_dir = Path(directory)
            self._output_label.setText(f"출력 폴더: {directory}")
            bad_count = sum(1 for r in (self._rows or []) if r.selected)
            self._apply_button.setEnabled(bad_count > 0)
            save_folder(self._settings, "badcut/output_dir", self._output_dir)
```

- [ ] **Step 3: 드래그앤드롭 이벤트 오버라이드 추가**

`is_busy` 프로퍼티 바로 아래에 추가:
```python
    @property
    def is_busy(self) -> bool:
        return self._busy

    def dragEnterEvent(self, event) -> None:  # noqa: N802 - Qt override signature
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event) -> None:  # noqa: N802 - Qt override signature
        folders = extract_dropped_folders(event.mimeData())
        if folders:
            self._add_folders(folders)
        event.acceptProposedAction()
```

- [ ] **Step 4: __init__에 setAcceptDrops + 설정 로드 추가**

`self._thumbnail_cache: dict = {}` 바로 아래에 추가:
```python
        self._thumbnail_cache: dict = {}
        self.setAcceptDrops(True)
        self._settings = make_settings()
```

`self.setLayout(layout)` 바로 위(마지막 줄)에 추가:
```python
        for folder in load_folder_list(self._settings, "badcut/input_dirs"):
            self._input_dirs.append(folder)
            self._folder_list.addItem(str(folder))
        restored_output = load_folder(self._settings, "badcut/output_dir")
        if restored_output is not None:
            self._output_dir = restored_output
            self._output_label.setText(f"출력 폴더: {restored_output}")

        self.setLayout(layout)
```

- [ ] **Step 5: 컴파일 확인**

Run: `cd /Users/taek/Claude/FrameSense && python3 -m py_compile src/gui_badcut_tab.py`
Expected: 에러 없이 종료.

- [ ] **Step 6: 전체 회귀 테스트**

Run: `cd /Users/taek/Claude/FrameSense && ./.venv/bin/python -m pytest -q`
Expected: 전부 PASS.

- [ ] **Step 7: Commit**

```bash
cd /Users/taek/Claude/FrameSense
git add src/gui_badcut_tab.py
git commit -m "feat: add drag-and-drop and folder memory to badcut tab"
```

---

### Task 10: 시간순 정렬 탭 — 드래그앤드롭 + 폴더 기억

**Files:**
- Modify: `src/gui_rename_tab.py`

키: `rename/input_dirs`(리스트), `rename/merge_output_dir`(단일). 병합 출력 폴더는 `_choose_merge_output_dir`와 `_create_merge_output_dir` 두 군데에서 바뀌므로 두 곳 다 저장한다.

- [ ] **Step 1: import 추가**

import 블록의 `from rename_by_time import (...)` 뒤에 추가:
```python
from gui_dnd import extract_dropped_folders
from gui_settings import load_folder, load_folder_list, make_settings, save_folder, save_folder_list
```

- [ ] **Step 2: 폴더 추가 로직을 공용 메서드로 추출**

`_add_folder`를 찾아 아래로 교체:
```python
    def _add_folder(self) -> None:
        directory = QFileDialog.getExistingDirectory(self, "입력 폴더 추가")
        if directory:
            self._add_folders([Path(directory)])

    def _add_folders(self, folders: list[Path]) -> None:
        for folder in folders:
            if folder not in self._input_dirs:
                self._input_dirs.append(folder)
                self._folder_list.addItem(str(folder))
        self._invalidate_preview()
        save_folder_list(self._settings, "rename/input_dirs", self._input_dirs)
```

`_remove_selected_folder` 끝에 저장 호출 추가:
```python
    def _remove_selected_folder(self) -> None:
        for item in self._folder_list.selectedItems():
            index = self._folder_list.row(item)
            self._folder_list.takeItem(index)
            del self._input_dirs[index]
        self._invalidate_preview()
        save_folder_list(self._settings, "rename/input_dirs", self._input_dirs)
```

`_choose_merge_output_dir` 끝에 저장 호출 추가:
```python
    def _choose_merge_output_dir(self) -> None:
        directory = QFileDialog.getExistingDirectory(self, "병합 출력 폴더 선택")
        if directory:
            self._merge_output_dir = Path(directory)
            self._merge_output_label.setText(f"병합 출력 폴더: {directory}")
            self._open_merge_output_button.setEnabled(True)
            self._invalidate_preview()
            save_folder(self._settings, "rename/merge_output_dir", self._merge_output_dir)
```

`_create_merge_output_dir`의 마지막 줄(`self._invalidate_preview()`) 바로 아래에 한 줄 추가:
```python
        self._merge_output_dir = new_dir
        self._merge_output_label.setText(f"병합 출력 폴더: {new_dir}")
        self._open_merge_output_button.setEnabled(True)
        self._invalidate_preview()
        save_folder(self._settings, "rename/merge_output_dir", self._merge_output_dir)
```

- [ ] **Step 3: 드래그앤드롭 이벤트 오버라이드 추가**

`is_busy` 프로퍼티 바로 아래에 추가:
```python
    @property
    def is_busy(self) -> bool:
        return self._busy

    def dragEnterEvent(self, event) -> None:  # noqa: N802 - Qt override signature
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event) -> None:  # noqa: N802 - Qt override signature
        folders = extract_dropped_folders(event.mimeData())
        if folders:
            self._add_folders(folders)
        event.acceptProposedAction()
```

- [ ] **Step 4: __init__에 setAcceptDrops + 설정 로드 추가**

`self._scan_cache: dict = {}` 바로 아래에 추가:
```python
        self._scan_cache: dict = {}
        self.setAcceptDrops(True)
        self._settings = make_settings()
```

`self.setLayout(layout)` 바로 위(마지막 줄)에 추가:
```python
        for folder in load_folder_list(self._settings, "rename/input_dirs"):
            self._input_dirs.append(folder)
            self._folder_list.addItem(str(folder))
        restored_merge_output = load_folder(self._settings, "rename/merge_output_dir")
        if restored_merge_output is not None:
            self._merge_output_dir = restored_merge_output
            self._merge_output_label.setText(f"병합 출력 폴더: {restored_merge_output}")
            self._open_merge_output_button.setEnabled(self._merge_checkbox.isChecked())

        self.setLayout(layout)
```

- [ ] **Step 5: 컴파일 확인**

Run: `cd /Users/taek/Claude/FrameSense && python3 -m py_compile src/gui_rename_tab.py`
Expected: 에러 없이 종료.

- [ ] **Step 6: 전체 회귀 테스트**

Run: `cd /Users/taek/Claude/FrameSense && ./.venv/bin/python -m pytest -q`
Expected: 전부 PASS.

- [ ] **Step 7: Commit**

```bash
cd /Users/taek/Claude/FrameSense
git add src/gui_rename_tab.py
git commit -m "feat: add drag-and-drop and folder memory to rename tab"
```

---

### Task 11: 정리 탭 — 드래그앤드롭 + 폴더 기억

**Files:**
- Modify: `src/gui_organize_tab.py`

`OrganizeTab`은 폴더 리스트가 아니라 단일 폴더 라벨이라 `_set_folder` 헬퍼로 통일한다. 키: `organize/folder`(단일).

- [ ] **Step 1: import 추가**

import 블록의 `from scanner import RAW_EXTENSIONS` 바로 아래에 추가:
```python
from scanner import RAW_EXTENSIONS
from gui_dnd import extract_dropped_folders
from gui_settings import load_folder, make_settings, save_folder
```

- [ ] **Step 2: 폴더 선택 로직을 공용 메서드로 추출**

`_choose_folder`를 찾아 아래로 교체:
```python
    def _choose_folder(self) -> None:
        directory = QFileDialog.getExistingDirectory(self, "정리할 폴더 선택")
        if directory:
            self._set_folder(Path(directory))

    def _set_folder(self, folder: Path) -> None:
        self._folder = folder
        self._folder_label.setText(f"대상 폴더: {folder}")
        self._result_text.setPlainText("")
        self._last_operation = None
        self._undo_button.setEnabled(False)
        self._duplicate_groups = []
        self._delete_duplicate_button.setEnabled(False)
        save_folder(self._settings, "organize/folder", folder)
```

- [ ] **Step 3: 드래그앤드롭 이벤트 오버라이드 추가**

`is_busy` 프로퍼티 바로 아래에 추가:
```python
    @property
    def is_busy(self) -> bool:
        return False

    def dragEnterEvent(self, event) -> None:  # noqa: N802 - Qt override signature
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event) -> None:  # noqa: N802 - Qt override signature
        folders = extract_dropped_folders(event.mimeData())
        if folders:
            self._set_folder(folders[0])
        event.acceptProposedAction()
```

- [ ] **Step 4: __init__에 setAcceptDrops + 설정 로드 추가**

`self._duplicate_groups: list = []` 바로 아래에 추가:
```python
        self._duplicate_groups: list = []
        self.setAcceptDrops(True)
        self._settings = make_settings()
```

`self.setLayout(layout)` 바로 위(마지막 줄)에 추가:
```python
        restored_folder = load_folder(self._settings, "organize/folder")
        if restored_folder is not None:
            self._folder = restored_folder
            self._folder_label.setText(f"대상 폴더: {restored_folder}")

        self.setLayout(layout)
```

- [ ] **Step 5: 컴파일 확인**

Run: `cd /Users/taek/Claude/FrameSense && python3 -m py_compile src/gui_organize_tab.py`
Expected: 에러 없이 종료.

- [ ] **Step 6: 전체 회귀 테스트**

Run: `cd /Users/taek/Claude/FrameSense && ./.venv/bin/python -m pytest -q`
Expected: 전부 PASS.

- [ ] **Step 7: Commit**

```bash
cd /Users/taek/Claude/FrameSense
git add src/gui_organize_tab.py
git commit -m "feat: add drag-and-drop and folder memory to organize tab"
```

---

### Task 12: 최종 패키징 및 CLAUDE.md 갱신

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: CLAUDE.md에 UX 개선 항목 기록**

`CLAUDE.md`의 M11 항목 바로 아래(다음 마일스톤 자리)에 추가:
```markdown
- [x] M12: UX 전면 개선 — 베스트컷/C컷 미리보기를 텍스트 목록에서 썸네일 있는 테이블로 전환, 모든 폴더 입력/선택 영역에 드래그앤드롭 지원, 탭·역할별 QSettings로 마지막 사용 폴더 자동 복원(존재하지 않는 경로는 조용히 무시), 첫 버전 번호 1.0.0 도입 — `src/thumbnails.py`, `src/gui_dnd.py`, `src/gui_settings.py`, `src/version.py`. 설계: `docs/superpowers/specs/2026-09-20-ux-overhaul-design.md`
```

- [ ] **Step 2: 최종 재빌드**

Run: `cd /Users/taek/Claude/FrameSense && .venv/bin/pyinstaller packaging/FrameSense.spec --distpath dist --workpath build -y`
Expected: 빌드 성공.

- [ ] **Step 3: 앱 실행 확인**

Run: `open /Users/taek/Claude/FrameSense/dist/FrameSense.app`
확인 항목: 창 제목에 "v1.0.0" 표시, 베스트컷/C컷 탭에서 미리보기 실행 시 테이블+썸네일 표시, 폴더 영역에 Finder 폴더 드래그시 추가됨, 앱을 완전히 껐다 켜도 마지막 입력 폴더가 자동으로 채워짐.

- [ ] **Step 4: 전체 회귀 테스트 최종 확인**

Run: `cd /Users/taek/Claude/FrameSense && ./.venv/bin/python -m pytest -q`
Expected: 전부 PASS.

- [ ] **Step 5: Commit**

```bash
cd /Users/taek/Claude/FrameSense
git add CLAUDE.md
git commit -m "docs: record M12 UX overhaul milestone"
git push
```
