# 🎣 미니 피싱 (Mini Fishing)

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

## 세이브 옮기기 (PC ↔ 모바일)

설정 → **세이브 옮기기** → 슬롯 고르고 **내보내기**: 코드가 클립보드에 복사되고 파일로도 저장됩니다
(`내 문서/FishingPlanet/export/`). 다른 기기에서 그 코드를 복사한 뒤(또는 그 폴더에 `import.txt`로 넣고) **가져오기**.
덮어쓰기 전 지금 세이브는 `backups/` 폴더에 자동 백업됩니다.

## 음악 넣기 (선택)

`data/music/`에 정해진 이름의 ogg/mp3 파일을 넣으면 낚시터·파이팅·전설별로 자동 재생됩니다.
AI 작곡용 프롬프트와 파일 이름은 [MUSIC_PROMPTS.md](MUSIC_PROMPTS.md) 참고.

## exe 빌드 (배포용)

1. `build.bat` 더블클릭 (처음이면 가상환경·PyInstaller를 자동 설치, 1~3분)
2. 완료되면 `dist\MiniFishing\` 폴더가 열립니다 → `MiniFishing.exe` 실행
3. **`dist\MiniFishing` 폴더를 통째로 압축**해서 나눠주면 끝 (exe만 따로 떼면 실행 안 됨)

세이브·설정·에러 로그(`crash.log`)는 `내 문서\FishingPlanet`에 저장됩니다.

### Python 없는 PC에서 확인하는 법

- **가장 확실**: Windows 샌드박스(Windows Pro: "Windows 기능 켜기/끄기" → Windows Sandbox) 실행 →
  압축파일을 복사해 넣고 풀어서 `MiniFishing.exe` 실행. 샌드박스엔 Python이 없으니 그대로 검증됩니다.
- 또는 Python 안 깔린 다른 PC / 가상머신(VirtualBox 등)에서 같은 방법으로 실행.
- 내 PC에서 간이 확인: 압축을 **다른 폴더(예: 바탕화면)**에 풀고 실행 → 프로젝트 폴더 없이도 도는지(데이터 경로) 확인.
- "Windows의 PC 보호" 창이 뜨면 **[추가 정보] → [실행]** (코드 서명이 없는 개인 제작 exe라 뜨는 정상 경고).
- 백신이 막으면 예외 등록하거나 VirusTotal로 확인. (onedir 방식이라 onefile보다 오탐이 적습니다)
- 실행이 안 되면 `내 문서\FishingPlanet\crash.log` 내용을 확인하세요.

## 안드로이드 APK 빌드

**방법 1 — GitHub에서 받기 (설치 없음)**: 저장소 Actions → `build` 실행 → 맨 아래 Artifacts의 `MiniFishing-android`
(디버그 APK)와 `MiniFishing-windows`(exe 폴더). 브랜치에 push하면 자동으로 돌고, Actions 화면의 "Run workflow"로도 실행.

**방법 2 — WSL2 우분투에서 직접**: 프로젝트를 WSL 홈(예: `~/fishingplanet`)에 두고
```
./build_android.sh deps   # 처음 한 번: 자바·빌드 도구 설치 (sudo 암호)
./build_android.sh        # 디버그 APK → dist/android/
```
첫 빌드는 SDK·NDK 내려받기로 30분~1시간 걸립니다.

**폰에 설치**: 폰 설정에서 개발자 옵션 → USB 디버깅 켜고 연결 →
`adb install -r dist/android/<파일>.apk` (또는 APK 파일을 폰에 복사해 열기 — '출처를 알 수 없는 앱' 허용).
튕기면 `adb logcat -s python:D SDL:D AndroidRuntime:E` 로 에러를 볼 수 있습니다.

