"""안드로이드 아이콘·스플래시를 코드로 그린다 (build_android.sh / CI에서 호출, MOBILE.md M6).

android/icon.png      512×512 (PC .ico와 같은 물고기 그림, 정수 배율로 키움)
android/presplash.png 1280×720 (로딩 중 화면: 어두운 물빛 + 아이콘 + 제목)
사용: python tools/make_android_assets.py [출력 폴더]
"""
import os
import sys

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import pygame  # noqa: E402

from src.render.icon import icon_surface  # noqa: E402


def main(out: str) -> None:
    pygame.init()
    os.makedirs(out, exist_ok=True)
    pygame.image.save(icon_surface(512), os.path.join(out, "icon.png"))
    w, h = 1280, 720
    splash = pygame.Surface((w, h))
    for y in range(h):  # 위는 밤하늘, 아래로 갈수록 깊은 물
        k = y / h
        splash.fill((int(12 + 10 * k), int(16 + 30 * k), int(30 + 50 * k)), (0, y, w, 1))
    icon = icon_surface(256)
    splash.blit(icon, icon.get_rect(center=(w // 2, h // 2 - 40)))
    try:
        from src.core.config import game_config
        from src.core.fonts import get_font
        title = get_font(16).render(game_config()["title"], False, (255, 228, 150))
        title = pygame.transform.scale(title, (title.get_width() * 4, title.get_height() * 4))
        splash.blit(title, title.get_rect(center=(w // 2, h // 2 + 150)))
    except Exception as e:  # 글꼴이 없어도 아이콘만으로 충분
        print("제목 글자 생략:", e)
    pygame.image.save(splash, os.path.join(out, "presplash.png"))
    print("저장:", os.path.join(out, "icon.png"), os.path.join(out, "presplash.png"))


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "android"))
