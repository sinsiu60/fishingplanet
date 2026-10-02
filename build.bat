@echo off
chcp 65001 > nul
cd /d "%~dp0"
echo ==========================================
echo   낚시 게임 - Windows 실행 파일 빌드
echo ==========================================

if not exist ".venv\Scripts\python.exe" (
    echo 가상환경이 없어서 먼저 설치를 진행합니다...
    call setup.bat
    if errorlevel 1 exit /b 1
)
set PY=".venv\Scripts\python.exe"

echo [1/4] 빌드 도구(PyInstaller) 확인 중...
%PY% -m pip install -q -r requirements.txt -r requirements-build.txt
if errorlevel 1 goto fail

echo [2/4] 물고기 아이콘 생성 중...
%PY% tools\make_icon.py build\icon.ico
if errorlevel 1 goto fail

echo [3/4] 실행 파일 빌드 중... (1~3분)
if exist "dist\FishingGame" rmdir /s /q "dist\FishingGame"
%PY% -m PyInstaller --noconfirm --clean --onedir --windowed ^
    --name FishingGame ^
    --icon "%~dp0build\icon.ico" ^
    --add-data "%~dp0data;data" ^
    --add-data "%~dp0assets;assets" ^
    --exclude-module tkinter ^
    --specpath build ^
    "%~dp0main.py"
if errorlevel 1 goto fail

echo [4/4] 정리 중...
copy /y "dist_readme.txt" "dist\FishingGame\README.txt" > nul

echo.
echo 빌드 완료!  dist\FishingGame\FishingGame.exe
echo dist\FishingGame 폴더를 통째로 압축해서 나눠주면 됩니다.
explorer "dist\FishingGame"
pause
exit /b 0

:fail
echo.
echo 빌드 실패. 위 에러 메시지를 확인하세요.
pause
exit /b 1
