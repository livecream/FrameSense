# 사진셀렉정리툴 (PixThrough)

사진 폴더를 스캔해 같은 장면(연속 촬영)끼리 자동으로 묶고, 선명도/노출/얼굴(눈뜸)
기준으로 장면별 베스트 컷을 골라 지정한 폴더로 복사(또는 이동)해주는 도구.

## 다운로드 (macOS)

터미널 없이 바로 쓰려면 [Releases](https://github.com/livecream/PixThrough/releases/latest)에서
`PixThrough-macOS.zip`을 받아 압축을 풀고 `PixThrough.app`을 실행하세요.

> 서명되지 않은 앱이라 **첫 실행은 반드시 우클릭 → 열기**로 해야 합니다
> (macOS가 처음 한 번은 더블클릭 실행을 막습니다). 이후에는 평소처럼 더블클릭하면 됩니다.

## 다운로드 (Windows)

[Releases](https://github.com/livecream/PixThrough/releases/latest)에서
`PixThrough-Windows.zip`을 받아 압축을 풀고, `PixThrough` 폴더 안의
`PixThrough.exe`를 실행하세요. 설치나 Python은 필요 없습니다.

> 압축을 **반드시 먼저 푼 뒤** 실행하세요(zip 안에서 바로 실행하면 동작하지 않습니다).
> `PixThrough.exe`는 같은 폴더의 `_internal` 폴더가 있어야 실행되므로 폴더째로 두세요.
> 서명되지 않은 앱이라 처음 실행할 때 "Windows의 PC 보호" 창이 뜨면
> **추가 정보 → 실행**을 누르면 됩니다.

## 개발자용 (소스에서 실행)

```bash
git clone https://github.com/livecream/PixThrough.git
cd PixThrough
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

# GUI 실행
.venv/bin/python src/gui.py

# CLI로 직접 실행 (예: 미리보기)
.venv/bin/python src/cli.py report --input ~/Photos/2026-09 --recursive --output report.csv

# .app으로 재빌드
.venv/bin/pyinstaller packaging/PixThrough.spec --distpath dist --workpath build
```

## macOS 릴리스 자동 빌드

GitHub에서 릴리스를 발행하면 `.github/workflows/release-macos.yml`이 macOS(Apple Silicon)
러너에서 `.app`을 빌드해 `PixThrough-macOS.zip`을 같은 릴리스에 첨부하고, 릴리스 노트의
`- **macOS**: 추후 추가 예정` 줄을 다운로드 안내로 바꾼다. 이미 발행된 릴리스에 붙이려면
Actions 탭 → "Release macOS build" → Run workflow에서 태그(예: `v1.1.0`)를 입력한다.

## Windows에서 빌드하기

PyInstaller는 크로스 컴파일을 지원하지 않는다 — macOS에서 빌드하면 macOS용
바이너리만 나오므로, Windows용 실행 파일은 **반드시 Windows PC(또는 VM)에서**
빌드해야 한다. `packaging/PixThrough.windows.spec`이 Windows 전용 스펙이다
(macOS 전용인 `.app` 번들 단계만 빠지고 나머지는 동일).

Windows PowerShell(또는 cmd)에서:

```powershell
git clone https://github.com/livecream/PixThrough.git
cd PixThrough
py -3 -m venv .venv
.venv\Scripts\pip install -r requirements.txt

# GUI 실행
.venv\Scripts\python src\gui.py

# .exe로 빌드 (dist\PixThrough\PixThrough.exe 생성)
.venv\Scripts\pyinstaller packaging\PixThrough.windows.spec --distpath dist --workpath build
```

빌드 결과물은 `dist\PixThrough\` 폴더 전체(실행 파일 + 의존 DLL/데이터)이며,
이 폴더를 통째로 압축해서 배포한다 — `PixThrough.exe`만 따로 옮기면 실행되지
않는다. macOS와 마찬가지로 서명되지 않은 실행 파일이라 처음 실행할 때
Windows Defender SmartScreen이 "알 수 없는 게시자" 경고를 띄울 수 있는데,
"추가 정보" → "실행"으로 넘어가면 된다(코드 서명 인증서가 없으면 항상 뜨는
정상적인 경고).

자세한 개발 가이드는 [CLAUDE.md](CLAUDE.md), 스펙은 [PROJECT_SPEC.md](PROJECT_SPEC.md) 참고.
