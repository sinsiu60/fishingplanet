"""업적 달성 알림 (트로피 + 이름, 화면 위 가운데, 3초). 파이팅·포획 연출 중엔 대기열에 두고 끝난 뒤에.

상태는 game.achv_toast 하나 (낚시터·마을이 같이 씀). update(game, dt, allow) → draw(game, canvas).
"""
import pygame

from src.ui import side_menu
from src.ui.hud import SHADOW, text

SHOW = 3.2


def update(game, dt: float, allow: bool) -> None:
    from src.save import achievements
    if game.save is None:
        return
    achievements.tick(game.save, dt)
    cur = getattr(game, "achv_toast", None)
    if cur is not None:
        cur["t"] += dt
        if cur["t"] > SHOW:
            game.achv_toast = None
        return
    if allow:
        a = achievements.pop_toast(game.save)
        if a is not None:
            game.achv_toast = {"a": a, "t": 0.0}
            game.sfx.play("sfx_record", 0.6)


def draw(game, canvas) -> None:
    cur = getattr(game, "achv_toast", None)
    if not cur:
        return
    t = cur["t"]
    k = min(1.0, t / 0.25, (SHOW - t) / 0.3)
    if k <= 0:
        return
    w = canvas.get_width()
    from src.core.fonts import get_font
    name = cur["a"]["name"]
    tw = max(get_font(11).size(name)[0], 60) + 44
    r = pygame.Rect(w // 2 - tw // 2, int(-28 + 52 * k), tw, 28)
    canvas.fill(SHADOW, r.move(1, 1))
    canvas.fill((26, 22, 14), r)
    pygame.draw.rect(canvas, (255, 204, 70), r, 1)
    side_menu.trophy(canvas, r.x + 14, r.centery, (255, 255, 255), t)
    text(canvas, "업적 달성", (r.x + 28, r.y + 8), (255, 214, 110), 11, "midleft")
    text(canvas, name, (r.x + 28, r.y + 20), (240, 236, 220), 11, "midleft")
