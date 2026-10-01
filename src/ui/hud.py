"""HUD: 시계, 조작 안내, 파워 게이지, 둘러보기 화살표, 커서."""
import pygame

from src.core.fonts import get_font
from src.core.mathutil import lerp_color, scale_color

SHADOW = (10, 12, 24)


def text(canvas, s: str, pos, color, size: int = 11, anchor: str = "topleft") -> pygame.Rect:
    font = get_font(size)
    img = font.render(s, False, color)
    shadow = font.render(s, False, SHADOW)
    rect = img.get_rect(**{anchor: pos})
    canvas.blit(shadow, rect.move(1, 1))
    canvas.blit(img, rect)
    return rect


def draw_clock(canvas, pal, label: str, fast: bool, mult: int) -> None:
    r = text(canvas, label, (6, 4), pal["text"])
    if fast:
        text(canvas, f"▶▶ ×{mult}", (r.right + 6, 4), (255, 220, 120))


def draw_hint(canvas, pal, s: str) -> None:
    text(canvas, s, (6, canvas.get_height() - 6), pal["text"], anchor="bottomleft")


def draw_power_gauge(canvas, pal, power: float, distance: float) -> None:
    x, y, w, h = 452, 132, 8, 72
    canvas.fill(SHADOW, (x - 1, y - 1, w + 2, h + 2))
    canvas.fill((40, 44, 60), (x, y, w, h))
    fill = int(h * power)
    low, high = (120, 200, 255), (255, 230, 90)
    for i in range(fill):
        canvas.fill(lerp_color(low, high, i / h), (x, y + h - 1 - i, w, 1))
    # 최대 파워 눈금
    canvas.fill((255, 255, 255), (x - 2, y, w + 4, 1))
    text(canvas, f"{distance:.0f}m", (x + w // 2, y - 3), pal["text"], anchor="midbottom")


def draw_look_arrows(canvas, pal, left: bool, right: bool, t: float) -> None:
    h = canvas.get_height()
    cy = h // 2 - 20
    blink = int(t * 4) % 2 == 0
    color = pal["text"] if blink else scale_color(pal["text"], 0.7)
    if left:
        pygame.draw.polygon(canvas, color, [(4, cy), (11, cy - 6), (11, cy + 6)])
    if right:
        w = canvas.get_width()
        pygame.draw.polygon(canvas, color, [(w - 5, cy), (w - 12, cy - 6), (w - 12, cy + 6)])


def draw_cursor(canvas, pos) -> None:
    x, y = pos
    for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
        canvas.fill(SHADOW, (x - 3 + dx, y + dy, 7, 1))
        canvas.fill(SHADOW, (x + dx, y - 3 + dy, 1, 7))
    canvas.fill((255, 255, 255), (x - 3, y, 7, 1))
    canvas.fill((255, 255, 255), (x, y - 3, 1, 7))
