# 안드로이드 빌드 설정 (MOBILE.md Phase M6). WSL Ubuntu: ./build_android.sh / GitHub: .github/workflows/build.yml
# 기준: buildozer 1.6.0 + python-for-android 2026.5.9 (권장 NDK 28c, minapi 24). Google Play 기준 target API 35.

[app]
title = 낚시 게임
package.name = fishingplanet
package.domain = com.sinsiu
source.dir = .
# 게임 코드(.py) + 데이터(JSON) + 글꼴(.ttf) + 그림·소리
source.include_exts = py,json,ttf,txt,png,ogg,wav,mp3
source.exclude_dirs = tools, build, dist, bin, .venv, .github, .buildozer, android, __pycache__
source.exclude_patterns = *.bat,*.md,requirements*.txt,dist_readme.txt
version = 1.0.0

# pygame-ce는 p4a 레시피가 없어서 p4a의 pygame(2.1.0) 레시피를 쓴다 — 코드는 pygame 2.1.x로 호환 확인 (DESIGN.md 26장)
# numpy = 효과음 합성, pyjnius·android = 진동·화면 켜짐·공유 (src/platform/android.py)
requirements = python3,pygame,numpy,pyjnius,android

presplash.filename = %(source.dir)s/android/presplash.png
icon.filename = %(source.dir)s/android/icon.png
android.presplash_color = #0C1020

# 가로 화면 고정 (양쪽 가로 회전은 허용)
orientation = landscape, landscape-reverse
fullscreen = 1

android.permissions = android.permission.VIBRATE, android.permission.WAKE_LOCK
# 낚시 중 화면 꺼짐 방지 (src/platform/android.keep_screen_on 도 함께)
android.wakelock = True
android.api = 35
android.minapi = 24
android.ndk = 28c
android.accept_sdk_license = True
android.archs = arm64-v8a, armeabi-v7a
android.allow_backup = True
p4a.bootstrap = sdl2

[buildozer]
log_level = 2
warn_on_root = 1
