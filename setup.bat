@echo off
chcp 65001 > nul
cd /d "%~dp0"
echo [1/2] 가상환경(.venv) 만드는 중...
python -m venv .venv
if errorlevel 1 (
    echo Python을 찾을 수 없습니다. Python 3.12 설치 시 "Add python.exe to PATH"를 체크했는지 확인하세요.
    pause
    exit /b 1
)
echo [2/2] 라이브러리 설치 중...
".venv\Scripts\python.exe" -m pip install --upgrade pip
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 (
    echo 설치 실패. 위 에러 메시지를 확인하세요.
    pause
    exit /b 1
)
echo 설치 완료!
