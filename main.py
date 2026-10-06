"""미니 피싱 (Mini Fishing) — 1인칭 낚시 게임 진입점."""
# 웹 버전(pygbag)이 브라우저에 미리 깔아 둘 패키지
# /// script
# dependencies = [
#  "numpy",
# ]
# ///
import os
import sys
import traceback

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")


def _write_crash_log() -> str | None:
    """콘솔 없는 exe에선 에러가 안 보이므로 내 문서/FishingPlanet/crash.log 에 남긴다."""
    try:
        from src.core.paths import save_dir
        path = save_dir() / "crash.log"
        with open(path, "a", encoding="utf-8") as f:
            f.write(traceback.format_exc() + "\n")
        return str(path)
    except Exception:
        return None


def _boot_tail() -> list[str]:
    try:
        from src.core.paths import save_dir
        return (save_dir() / "boot.log").read_text(encoding="utf-8").splitlines()[-8:]
    except Exception:
        return []


def main() -> None:
    from src.core import bootlog
    bootlog.start()
    from src.platform.detect import IS_ANDROID
    if IS_ANDROID:
        # 가로 고정: SDL 이 창을 만들 때 쓰는 방향 힌트 + 안드로이드에 직접 요청 (창 크기를 가로로 잡게 pygame 보다 먼저)
        os.environ.setdefault("SDL_IOS_ORIENTATIONS", "LandscapeLeft LandscapeRight")
        from src.platform import android
        android.lock_landscape()
    audio = True
    if IS_ANDROID and (bootlog.previous or bootlog.fault):
        # 지난번 실행이 통째로 죽었다 → 어디서 멈췄는지 보여 주고, 이번엔 소리 없이(안전 모드) 시작
        audio = False
        os.environ["SDL_AUDIODRIVER"] = "dummy"
        os.environ["FP_SAFE"] = "1"   # 화면 확대도 예전 방식 (GPU 확대가 원인일 수도 있으니)
        bootlog.mark("안전 모드: 소리 끔 · 화면 예전 방식")
        lines = list(bootlog.previous or [])
        if bootlog.fault:
            lines += ["", "충돌 위치 (faulthandler):"] + bootlog.fault
        # pygame 을 불러오기 전에 안드로이드 대화상자로 먼저 (pygame 자체가 죽는 원인이어도 보이게)
        if not bootlog.android_dialog("지난번 실행이 도중에 꺼졌어요", lines):
            bootlog.show_lines("지난번 실행이 도중에 꺼졌어요 — 이번엔 소리 없이 시작합니다", lines)
    bootlog.mark("pygame 불러오기")
    import pygame  # noqa: F401  (여기서 죽으면 기록이 이 줄에서 멈춘다)
    bootlog.mark(f"pygame {pygame.version.ver} 불러옴")
    from src.core.game import Game
    bootlog.mark("게임 코드 불러옴")

    # 자동 테스트: python main.py --frames 120
    max_frames = None
    if "--frames" in sys.argv:
        max_frames = int(sys.argv[sys.argv.index("--frames") + 1])
    game = Game(max_frames=max_frames, audio=audio)
    if "--require-baked" in sys.argv and game.sfx.enabled and game.sfx.missing_baked:
        # 빌드 확인 (CI): 미리 구운 소리가 빠진 채 묶였으면 실패 (32장 S8)
        print("구운 소리 없음:", game.sfx.missing_baked)
        sys.exit(2)
    game.run()


async def main_web() -> None:
    """웹(브라우저, pygbag): 세이브를 브라우저 저장소에서 되살리고, 메인 루프를 비동기로 돌린다 (DESIGN.md 41)."""
    from src.core.paths import save_dir
    from src.platform import web
    print("세이브 되살림:", web.restore(save_dir()), "개")
    from src.core import bootlog
    bootlog.start()
    import pygame  # noqa: F401
    from src.core.game import Game
    game = Game()
    await game.run_async()


if sys.platform == "emscripten":
    import asyncio
    asyncio.run(main_web())
elif __name__ == "__main__":
    try:
        main()
    except Exception:
        log = _write_crash_log()
        if sys.stderr:
            traceback.print_exc()
        from src.platform.detect import IS_ANDROID
        if IS_ANDROID:
            # 폰: 그냥 꺼지지 않고 에러를 화면에 보여 준다 (캡처해서 보내 주면 원인을 바로 앎)
            from src.core import bootlog
            tb = traceback.format_exc().strip().splitlines()
            bootlog.mark("에러: " + (tb[-1] if tb else "?"))
            bootlog.show_lines("에러로 멈췄어요", tb[-12:] + ["", "시작 기록:"] + _boot_tail())
        if sys.platform == "win32" and getattr(sys, "frozen", False):
            import ctypes
            ctypes.windll.user32.MessageBoxW(
                None, f"게임이 에러로 종료되었습니다.\n로그: {log}", "미니 피싱", 0x10)
        sys.exit(1)
