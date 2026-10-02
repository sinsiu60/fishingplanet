@echo off
chcp 65001 > nul
cd /d "%~dp0"
rem 모바일 화면·터치 조작을 PC에서 미리 보기. 프리셋: phone18 phone20 phone21 tab1610 tab43
rem 예) run_mobile_preview.bat tab43
if not exist ".venv\Scripts\activate.bat" (
    echo 가상환경이 없어서 처음 한 번 설치를 진행합니다...
    call setup.bat
    if errorlevel 1 exit /b 1
)
call ".venv\Scripts\activate.bat"
set PRESET=%1
if "%PRESET%"=="" set PRESET=phone20
echo 모바일 미리보기: 마우스 = 손가락, F7 = 화면 프리셋 바꾸기, F8 = 노치 표시
echo   스페이스 = 숙이기, 위/아래 화살표 = 드랙, F 누르고 있기 = 릴 감기, R = 회수
python main.py --mobile-preview --preset %PRESET%
if errorlevel 1 (
    echo.
    echo 게임이 에러로 종료되었습니다. 위 메시지를 복사해서 알려주세요.
    pause
)
