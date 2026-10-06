# 안드로이드 빌드 설정 (MOBILE.md Phase M6). WSL Ubuntu: ./build_android.sh / GitHub: .github/workflows/build.yml
# 기준: buildozer 1.6.0 + python-for-android 2026.5.9 (권장 NDK 28c, minapi 24). Google Play 기준 target API 35.

[app]
title = 미니 피싱
package.name = fishingplanet
package.domain = com.sinsiu
source.dir = .
# 게임 코드(.py) + 데이터(JSON) + 글꼴(.ttf) + 그림·소리
source.include_exts = py,json,ttf,txt,png,ogg,wav,mp3
source.exclude_dirs = tools, build, dist, bin, .venv, .github, .buildozer, android, __pycache__
source.exclude_patterns = *.bat,*.md,requirements*.txt,dist_readme.txt
version = 1.3.5

# pygame-ce는 p4a 레시피가 없어서 pygame을 쓴다 — 로컬 레시피(android/recipes/pygame)로 2.6.1, 코드는 pygame 2.1.3·2.6.1 호환 확인 (DESIGN.md 26장)
# numpy = 효과음 합성, pyjnius·android = 진동·화면 켜짐·공유 (src/platform/android.py)
requirements = python3,pygame,numpy,pyjnius,android

presplash.filename = %(source.dir)s/android/presplash.png
icon.filename = %(source.dir)s/android/icon.png
android.presplash_color = #0C1020

# 가로 화면 고정. 두 방향을 같이 적으면 p4a 가 매니페스트에 방향을 안 넣어(-1) 세로로 떴다 (v0.8.5) →
# 매니페스트는 landscape 하나로 처음부터 가로, 뒤집힌 가로는 실행 중 '센서 가로'로 허용 (main.py / src/platform/android.py)
orientation = landscape
fullscreen = 1

android.permissions = android.permission.VIBRATE, android.permission.WAKE_LOCK
# 낚시 중 화면 꺼짐 방지 (src/platform/android.keep_screen_on 도 함께)
android.wakelock = True
android.api = 35
android.minapi = 24
android.ndk = 28c
android.accept_sdk_license = True
# 한 빌드엔 아키텍처 하나만: p4a가 두 번째 아키텍처에서 pip venv를 재사용하다 깨짐.
# GitHub 빌드는 이 줄을 arm64-v8a / armeabi-v7a(32비트 — 안드로이드 8 무렵 폰)로 바꿔 APK 두 개를 따로 만든다 (minapi 24 = 안드로이드 7.0부터)
android.archs = arm64-v8a
android.allow_backup = True
p4a.bootstrap = sdl2
# pygame 2.6.1 로컬 레시피 (기본 2.1.0은 Python 3.14에서 빌드 실패)
p4a.local_recipes = ./android/recipes

[buildozer]
log_level = 2
warn_on_root = 1
