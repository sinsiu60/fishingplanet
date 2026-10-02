"""플랫폼 감지: PC / 안드로이드. `--mobile-preview` 인자면 PC에서도 모바일 UI (Phase M4)."""
import os
import sys


def _is_android() -> bool:
    # python-for-android 가 넣어 주는 환경변수
    return "ANDROID_ARGUMENT" in os.environ or "ANDROID_PRIVATE" in os.environ


IS_ANDROID = _is_android()
PREVIEW = "--mobile-preview" in sys.argv
PLATFORM = "android" if IS_ANDROID else "pc"
IS_MOBILE = IS_ANDROID or PREVIEW
