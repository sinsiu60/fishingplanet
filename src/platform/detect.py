"""플랫폼 감지: PC / 안드로이드 / 웹(브라우저, pygbag). `--mobile-preview` 인자면 PC에서도 모바일 UI (Phase M4).

웹: 아이폰·아이패드·안드로이드 브라우저(터치 화면)면 모바일 UI, PC 브라우저면 PC 조작 (DESIGN.md 41).
"""
import os
import sys


def _is_android() -> bool:
    # python-for-android 가 넣어 주는 환경변수
    return "ANDROID_ARGUMENT" in os.environ or "ANDROID_PRIVATE" in os.environ


def _web_touch() -> bool:
    """브라우저가 터치 기기인지 (아이폰·아이패드·안드로이드). 아이패드 사파리는 맥으로 자신을 알려서 터치 점 수로 본다."""
    try:
        import platform as _pf   # pygbag 은 이 모듈에 브라우저 window 를 붙여 준다
        nav = _pf.window.navigator
        ua = str(nav.userAgent)
        if any(k in ua for k in ("iPhone", "iPad", "iPod", "Android", "Mobile")):
            return True
        return int(nav.maxTouchPoints or 0) > 1
    except Exception:
        return False


IS_ANDROID = _is_android()
IS_WEB = sys.platform == "emscripten"
WEB_TOUCH = IS_WEB and _web_touch()
PREVIEW = "--mobile-preview" in sys.argv
PLATFORM = "android" if IS_ANDROID else "web" if IS_WEB else "pc"
IS_MOBILE = IS_ANDROID or PREVIEW or WEB_TOUCH

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


_current = None


def current_preset() -> str:
    return _current or preview_preset()


def set_preset(name: str) -> None:
    """미리보기 실행 중 프리셋 바꾸기 (F7)."""
    global _current
    _current = name


def mobile_window():
    """PixelScreen에 넘길 창: PC = None, 안드로이드 = 전체 화면 (0, 0), 미리보기 = 프리셋 크기, 웹 = 브라우저 화면비."""
    if IS_ANDROID:
        return (0, 0)
    if IS_WEB:
        from src.platform import web
        return web.window_size()
    if PREVIEW:
        return PREVIEW_PRESETS[current_preset()]
    return None
