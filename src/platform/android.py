"""안드로이드 API (pyjnius). PC·미리보기에선 import 하지 않거나, 해도 모든 함수가 조용히 아무것도 안 한다.

python-for-android 의 SDL2 앱은 org.kivy.android.PythonActivity 위에서 돈다.
여기 함수들은 기기 없이는 확인할 수 없어서(M6 APK에서 확인) 실패해도 게임이 멈추지 않게 전부 try 로 감쌌다.
"""
_cache: dict = {}


def _activity():
    if "act" not in _cache:
        from jnius import autoclass
        _cache["act"] = autoclass("org.kivy.android.PythonActivity").mActivity
    return _cache["act"]


def vibrate(pattern_ms: list[int], amplitude: float) -> None:
    """pattern_ms = [켬, 끔, 켬, ...] (ms), amplitude 0~1."""
    try:
        from jnius import autoclass
        if "vib" not in _cache:
            ctx = autoclass("android.content.Context")
            _cache["vib"] = _activity().getSystemService(ctx.VIBRATOR_SERVICE)
            _cache["sdk"] = autoclass("android.os.Build$VERSION").SDK_INT
            _cache["ve"] = autoclass("android.os.VibrationEffect")
        vib, ve = _cache["vib"], _cache["ve"]
        amp = max(1, min(255, int(255 * amplitude)))
        if _cache["sdk"] >= 26:
            if len(pattern_ms) == 1:
                vib.vibrate(ve.createOneShot(int(pattern_ms[0]), amp))
            else:
                timings = [0] + [int(x) for x in pattern_ms]
                amps = [0] + [amp if i % 2 == 0 else 0 for i in range(len(pattern_ms))]
                vib.vibrate(ve.createWaveform(timings, amps, -1))
        else:
            vib.vibrate(int(sum(pattern_ms[::2])))
    except Exception:
        pass


def cutout_insets() -> tuple[int, int] | None:
    """화면 좌우 카메라 구멍(디스플레이 컷아웃) 안전 여백 (기기 픽셀). 알 수 없으면 None."""
    try:
        insets = _activity().getWindow().getDecorView().getRootWindowInsets()
        if insets is None:
            return None
        cut = insets.getDisplayCutout()  # API 28+
        if cut is None:
            return (0, 0)
        return (int(cut.getSafeInsetLeft()), int(cut.getSafeInsetRight()))
    except Exception:
        return None


def lock_landscape() -> None:
    """가로 고정 + 양쪽 가로(뒤집기) 허용 = SCREEN_ORIENTATION_SENSOR_LANDSCAPE. 자동 회전이 꺼져 있어도 가로."""
    try:
        from android.runnable import run_on_ui_thread
        info = __import__("jnius").autoclass("android.content.pm.ActivityInfo")

        @run_on_ui_thread
        def _set():
            _activity().setRequestedOrientation(info.SCREEN_ORIENTATION_SENSOR_LANDSCAPE)

        _set()
    except Exception:
        pass


def keep_screen_on() -> None:
    """게임 중 화면 꺼짐 방지 (SDL도 기본으로 막지만 확실히)."""
    try:
        from android.runnable import run_on_ui_thread
        from jnius import autoclass
        params = autoclass("android.view.WindowManager$LayoutParams")

        @run_on_ui_thread
        def _set():
            _activity().getWindow().addFlags(params.FLAG_KEEP_SCREEN_ON)
        _set()
    except Exception:
        pass


def share_text(text: str, title: str) -> bool:
    """안드로이드 공유 창 (카톡·메일 등으로 세이브 코드 보내기)."""
    try:
        from jnius import autoclass, cast
        intent_cls = autoclass("android.content.Intent")
        jstr = autoclass("java.lang.String")
        intent = intent_cls()
        intent.setAction(intent_cls.ACTION_SEND)
        intent.setType("text/plain")
        intent.putExtra(intent_cls.EXTRA_TEXT, cast("java.lang.CharSequence", jstr(text)))
        chooser = intent_cls.createChooser(intent, cast("java.lang.CharSequence", jstr(title)))
        _activity().startActivity(chooser)
        return True
    except Exception:
        return False


def shared_dir():
    """다른 앱·PC(USB)에서 볼 수 있는 앱 전용 외부 폴더 (Android/data/<패키지>/files). 없으면 None."""
    try:
        from pathlib import Path
        d = _activity().getExternalFilesDir(None)
        return Path(d.getAbsolutePath()) if d is not None else None
    except Exception:
        return None
