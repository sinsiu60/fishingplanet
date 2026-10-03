"""시작 과정 기록 (폰에서 '켜자마자 꺼짐' 원인 찾기, v0.8.2).

단계마다 세이브 폴더/boot.log 에 한 줄씩 쓰고 바로 디스크에 내린다(fsync).
- 파이썬 에러로 죽으면: main.py 가 화면에 에러를 띄운다 (show_error).
- 메모리 부족 등으로 앱이 통째로 죽으면 파이썬이 아무것도 못 남기므로, 다음 실행 때 지난 기록이 'OK'로 안 끝났으면
  그 마지막 단계들을 화면에 보여 주고(화면 누르면 계속) 그대로 진행한다.
"""
import os
import time

_path = None
_t0 = time.perf_counter()
previous: list[str] | None = None   # 지난번 시작이 끝까지 못 간 경우 그 기록


def start() -> None:
    global _path, previous
    try:
        from src.core.paths import save_dir
        _path = save_dir() / "boot.log"
        if _path.exists():
            old = _path.read_text(encoding="utf-8", errors="replace").splitlines()
            if old and old[-1].strip() != "OK":
                previous = old[-14:]
        _path.write_text("", encoding="utf-8")
    except Exception:
        _path = None
    from src.version import VERSION
    import sys
    mark(f"v{VERSION} python {sys.version.split()[0]}")


def mark(msg: str) -> None:
    line = f"{time.perf_counter() - _t0:6.2f}s {msg}"
    if _path is None:
        return
    try:
        with open(_path, "a", encoding="utf-8") as f:
            f.write(line + "\n")
            f.flush()
            os.fsync(f.fileno())
    except Exception:
        pass


def done() -> None:
    if _path is not None:
        try:
            with open(_path, "a", encoding="utf-8") as f:
                f.write("OK\n")
        except Exception:
            pass


def show_lines(title: str, lines: list[str], wait: bool = True) -> None:
    """화면에 글을 띄운다 (게임 화면이 아직 없어도). 누르면(또는 20초 뒤) 돌아온다."""
    import pygame
    try:
        if not pygame.display.get_init():
            pygame.display.init()
        surf = pygame.display.get_surface()
        if surf is None:
            surf = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
        pygame.font.init()
        w, h = surf.get_size()
        size = max(14, h // 34)
        try:
            from src.core.paths import data_path
            font = pygame.font.Font(str(data_path("fonts", "NotoSansKR-Subset.ttf")), size)
        except Exception:
            font = pygame.font.Font(None, size)
        surf.fill((14, 18, 32))
        y = size
        for i, ln in enumerate([title, ""] + lines + ["", "화면을 누르면 계속 / 이 화면을 캡처해서 보내 주세요"]):
            col = (255, 214, 90) if i == 0 else (225, 230, 240)
            if not ln:
                y += size // 2
            while ln:
                cut = len(ln)
                while cut > 1 and font.size(ln[:cut])[0] > w - 2 * size:
                    cut -= 1
                surf.blit(font.render(ln[:cut], True, col), (size, y))
                ln = ln[cut:]
                y += int(size * 1.25)
        pygame.display.flip()
        if not wait:
            return
        end = time.time() + 20
        while time.time() < end:
            for e in pygame.event.get():
                if e.type in (pygame.MOUSEBUTTONDOWN, pygame.FINGERDOWN, pygame.KEYDOWN, pygame.QUIT):
                    return
            time.sleep(0.05)
    except Exception:
        pass
