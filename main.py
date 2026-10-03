"""1인칭 낚시 게임 진입점."""
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
    audio = True
    if IS_ANDROID and (bootlog.previous or bootlog.fault):
        # 지난번 실행이 통째로 죽었다 → 어디서 멈췄는지 보여 주고, 이번엔 소리 없이(안전 모드) 시작
        audio = False
        os.environ["SDL_AUDIODRIVER"] = "dummy"
        bootlog.mark("안전 모드: 소리 끔")
        lines = list(bootlog.previous or [])
        if bootlog.fault:
            lines += ["", "충돌 위치 (faulthandler):"] + bootlog.fault
        bootlog.show_lines("지난번 실행이 도중에 꺼졌어요 — 이번엔 소리 없이 시작합니다", lines)
    from src.core.game import Game

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


if __name__ == "__main__":
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
                None, f"게임이 에러로 종료되었습니다.\n로그: {log}", "낚시 게임", 0x10)
        sys.exit(1)
