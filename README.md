# 사진셀렉정리툴 (FrameSense)

사진 폴더를 스캔해 같은 장면(연속 촬영)끼리 자동으로 묶고, 선명도/노출/얼굴(눈뜸)
기준으로 장면별 베스트 컷을 골라 지정한 폴더로 복사(또는 이동)해주는 도구.

## 다운로드 (macOS)

터미널 없이 바로 쓰려면 [Releases](https://github.com/livecream/FrameSense/releases/latest)에서
`FrameSense-macOS.zip`을 받아 압축을 풀고 `FrameSense.app`을 실행하세요.

> 서명되지 않은 앱이라 **첫 실행은 반드시 우클릭 → 열기**로 해야 합니다
> (macOS가 처음 한 번은 더블클릭 실행을 막습니다). 이후에는 평소처럼 더블클릭하면 됩니다.

## 개발자용 (소스에서 실행)

```bash
git clone https://github.com/livecream/FrameSense.git
cd FrameSense
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

# GUI 실행
.venv/bin/python src/gui.py

# CLI로 직접 실행 (예: 미리보기)
.venv/bin/python src/cli.py report --input ~/Photos/2026-09 --recursive --output report.csv

# .app으로 재빌드
.venv/bin/pyinstaller packaging/FrameSense.spec --distpath dist --workpath build
```

자세한 개발 가이드는 [CLAUDE.md](CLAUDE.md), 스펙은 [PROJECT_SPEC.md](PROJECT_SPEC.md) 참고.
