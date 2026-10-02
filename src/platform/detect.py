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

# 미리보기 창 프리셋 (실제 기기 화면비). --preset 이름 으로 고른다 (Phase M4에서 실행 중 전환 키 추가).
PREVIEW_PRESETS = {
    "phone20": (1200, 540),   # 20:9 (대부분의 요즘 폰)
    "phone21": (1260, 540),   # 21:9
    "phone18": (1080, 540),   # 18:9
    "tab43": (960, 720),      # 4:3 (아이패드형)
    "tab1610": (1152, 720),   # 16:10 (안드로이드 태블릿)
}


def preview_preset() -> str:
    if "--preset" in sys.argv:
        name = sys.argv[sys.argv.index("--preset") + 1]
        if name in PREVIEW_PRESETS:
            return name
    return "phone20"


def mobile_window():
    """PixelScreen에 넘길 창: PC = None, 안드로이드 = 전체 화면 (0, 0), 미리보기 = 프리셋 크기."""
    if IS_ANDROID:
        return (0, 0)
    if PREVIEW:
        return PREVIEW_PRESETS[preview_preset()]
    return None
