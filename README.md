# 🎣 낚시 게임

어렵지만 공정한 1인칭 낚시 게임. 설계는 [DESIGN.md](DESIGN.md) 참고.

## 실행 (Windows)

1. Python 3.12 설치 (설치 첫 화면에서 **"Add python.exe to PATH" 체크**)
2. `run.bat` 더블클릭
   - 처음 실행하면 `setup.bat`이 자동으로 가상환경(`.venv`)을 만들고 라이브러리를 설치합니다.

## 실행 (직접)

```
python -m venv .venv
.venv\Scripts\activate        (macOS/Linux: source .venv/bin/activate)
pip install -r requirements.txt
python main.py
```

## 모바일 화면 미리보기 (PC에서)

`run_mobile_preview.bat` 더블클릭 (또는 `python main.py --mobile-preview --preset phone20`)
- 마우스 = 손가락. **F7** 화면 프리셋 바꾸기 (폰 18:9·20:9·21:9, 태블릿 16:10·4:3), **F8** 노치·둥근 모서리 표시
- 두 번째 손가락 대신 키보드: 스페이스 = 숙이기, ↑/↓ = 드랙, F 누르고 있기 = 릴 감기, R = 회수
- 진동은 화면 아래에 `[진동] 종류`로 표시. 세이브는 PC와 같은 것을 씁니다.

## 음악 넣기 (선택)

`data/music/`에 정해진 이름의 ogg/mp3 파일을 넣으면 낚시터·파이팅·전설별로 자동 재생됩니다.
AI 작곡용 프롬프트와 파일 이름은 [MUSIC_PROMPTS.md](MUSIC_PROMPTS.md) 참고.

## exe 빌드 (배포용)

1. `build.bat` 더블클릭 (처음이면 가상환경·PyInstaller를 자동 설치, 1~3분)
2. 완료되면 `dist\FishingGame\` 폴더가 열립니다 → `FishingGame.exe` 실행
3. **`dist\FishingGame` 폴더를 통째로 압축**해서 나눠주면 끝 (exe만 따로 떼면 실행 안 됨)

세이브·설정·에러 로그(`crash.log`)는 `내 문서\FishingPlanet`에 저장됩니다.

### Python 없는 PC에서 확인하는 법

- **가장 확실**: Windows 샌드박스(Windows Pro: "Windows 기능 켜기/끄기" → Windows Sandbox) 실행 →
  압축파일을 복사해 넣고 풀어서 `FishingGame.exe` 실행. 샌드박스엔 Python이 없으니 그대로 검증됩니다.
- 또는 Python 안 깔린 다른 PC / 가상머신(VirtualBox 등)에서 같은 방법으로 실행.
- 내 PC에서 간이 확인: 압축을 **다른 폴더(예: 바탕화면)**에 풀고 실행 → 프로젝트 폴더 없이도 도는지(데이터 경로) 확인.
- "Windows의 PC 보호" 창이 뜨면 **[추가 정보] → [실행]** (코드 서명이 없는 개인 제작 exe라 뜨는 정상 경고).
- 백신이 막으면 예외 등록하거나 VirusTotal로 확인. (onedir 방식이라 onefile보다 오탐이 적습니다)
- 실행이 안 되면 `내 문서\FishingPlanet\crash.log` 내용을 확인하세요.
