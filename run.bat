@echo off
chcp 65001 > nul
cd /d "%~dp0"
if not exist ".venv\Scripts\activate.bat" (
    echo 가상환경이 없어서 처음 한 번 설치를 진행합니다...
    call setup.bat
    if errorlevel 1 exit /b 1
)
call ".venv\Scripts\activate.bat"
python main.py
if errorlevel 1 (
    echo.
    echo 게임이 에러로 종료되었습니다. 위 메시지를 복사해서 알려주세요.
    pause
)
