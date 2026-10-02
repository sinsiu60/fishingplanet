#!/usr/bin/env bash
# 안드로이드 APK 빌드 (MOBILE.md Phase M6). WSL2 Ubuntu에서 프로젝트 폴더로 가서 실행:
#   ./build_android.sh          디버그 APK  → dist/android/
#   ./build_android.sh deps     처음 한 번: 필요한 우분투 패키지 설치 (sudo 비밀번호 필요)
# 첫 빌드는 Android SDK·NDK 다운로드 때문에 30분~1시간. 두 번째부터는 몇 분.
set -euo pipefail
cd "$(dirname "$0")"

if [[ "${1:-}" == "deps" ]]; then
    sudo apt-get update
    # buildozer / python-for-android 공식 문서의 우분투 의존성
    sudo apt-get install -y git zip unzip openjdk-17-jdk python3-pip python3-venv autoconf libtool pkg-config \
        zlib1g-dev libncurses-dev cmake libffi-dev libssl-dev automake lld libltdl-dev gettext build-essential
    echo "패키지 설치 끝. 이제 ./build_android.sh 로 빌드하세요."
    exit 0
fi

# 프로젝트가 윈도우 드라이브(/mnt/c/...)에 있으면 매우 느리고 권한 문제가 난다 → 경고만
if [[ "$PWD" == /mnt/* ]]; then
    echo "주의: 윈도우 드라이브($PWD)에서 빌드하면 느리고 실패하기 쉬워요."
    echo "      WSL 홈으로 복사해서 빌드하길 권장: cp -r . ~/fishingplanet && cd ~/fishingplanet"
fi

VENV="$HOME/.fishing-buildozer"
if [[ ! -x "$VENV/bin/buildozer" ]]; then
    echo "[1/4] buildozer 설치 (가상환경 $VENV)"
    python3 -m venv "$VENV"
    "$VENV/bin/pip" install -q --upgrade pip
    "$VENV/bin/pip" install -q "buildozer==1.6.0" "cython<3.1" setuptools pygame-ce==2.5.8 numpy
fi
export PATH="$VENV/bin:$PATH"

echo "[2/4] 아이콘·스플래시 그리기"
python tools/make_android_assets.py

echo "[3/4] APK 빌드 (buildozer android debug)"
yes | buildozer android debug

echo "[4/4] 결과 복사"
mkdir -p dist/android
cp -v bin/*.apk dist/android/
echo
echo "완료! dist/android/ 의 APK를 폰에 설치하세요:"
echo "  adb install -r dist/android/$(ls -t bin/*.apk | head -1 | xargs basename)"
echo "  크래시 로그: adb logcat -s python:D SDL:D AndroidRuntime:E"
