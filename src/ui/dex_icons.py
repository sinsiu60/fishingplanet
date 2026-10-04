"""도감 상세 칸 7x7 픽셀 아이콘 (DEX_UI.md): 시계 · 날씨(맑음/비/폭풍/안개) · 자 · 계절(봄 꽃/여름 해/가을 잎/겨울 눈송이) · 자물쇠 · 체크.

모두 (x, cy) = 왼쪽 끝 · 세로 가운데. 그림 칸 7x7.
"""
import pygame

WHITE = (232, 236, 245)
SUB = (110, 118, 145)
PINK = (255, 200, 220)   # 계절 아이콘에만


def _px(canvas, col, x, y, pts) -> None:
    for dx, dy in pts:
        canvas.fill(col, (x + dx, y + dy, 1, 1))


def clock(canvas, x: int, cy: int, col=WHITE) -> None:
    y = cy - 3
    pygame.draw.circle(canvas, col, (x + 3, y + 3), 3, 1)
    _px(canvas, col, x, y, [(3, 2), (3, 3), (4, 3)])


def ruler(canvas, x: int, cy: int, col=WHITE) -> None:
    y = cy - 1
    pygame.draw.rect(canvas, col, (x, y, 7, 3), 1)
    _px(canvas, col, x, y - 1, [(2, 0), (4, 0)])


def weather(canvas, x: int, cy: int, kinds: list[str]) -> None:
    """조건에 맞게: 폭풍 = 번개, 비 = 구름+빗방울, 안개 = 흐린 선, 맑음만 = 해."""
    y = cy - 3
    if "storm" in kinds:
        _cloud(canvas, x, y, (150, 156, 180))
        _px(canvas, (255, 220, 90), x, y, [(3, 4), (2, 5), (3, 5), (2, 6)])
    elif "rain" in kinds:
        _cloud(canvas, x, y, (190, 196, 214))
        _px(canvas, (120, 180, 255), x, y, [(1, 5), (3, 6), (5, 5)])
    elif "fog" in kinds:
        for i, (a, b) in enumerate(((1, 6), (0, 5), (1, 6))):
            canvas.fill((170, 176, 196), (x + a, y + 1 + i * 2, b - a + 1, 1))
    else:
        sun(canvas, x, cy, (255, 214, 110))


def _cloud(canvas, x, y, col) -> None:
    canvas.fill(col, (x + 1, y + 2, 5, 2))
    canvas.fill(col, (x + 2, y + 1, 3, 1))
    canvas.fill(col, (x, y + 3, 7, 1))


def sun(canvas, x: int, cy: int, col) -> None:
    y = cy - 3
    canvas.fill(col, (x + 2, y + 2, 3, 3))
    _px(canvas, col, x, y, [(3, 0), (3, 6), (0, 3), (6, 3), (1, 1), (5, 1), (1, 5), (5, 5)])


def season(canvas, x: int, cy: int, s: str | None) -> None:
    """계절 아이콘 (분홍 계열): 봄 꽃 · 여름 해 · 가을 잎 · 겨울 눈송이. 계절 무관 = 작은 점 네 개."""
    y = cy - 3
    if s == "spring":
        _px(canvas, PINK, x, y, [(3, 1), (1, 3), (5, 3), (3, 5), (2, 2), (4, 2), (2, 4), (4, 4)])
        canvas.fill((255, 240, 150), (x + 3, y + 3, 1, 1))
    elif s == "summer":
        sun(canvas, x, cy, (255, 190, 170))
    elif s == "autumn":
        pts = [(4, 0), (3, 1), (4, 1), (5, 1), (2, 2), (3, 2), (4, 2), (5, 2), (1, 3), (2, 3), (3, 3), (4, 3),
               (2, 4), (3, 4), (1, 5), (0, 6)]
        _px(canvas, (255, 170, 150), x, y, pts)
    elif s == "winter":
        col = (220, 225, 255)
        canvas.fill(col, (x + 3, y, 1, 7))
        canvas.fill(col, (x, y + 3, 7, 1))
        _px(canvas, col, x, y, [(1, 1), (5, 1), (1, 5), (5, 5)])
    else:
        _px(canvas, PINK, x, y, [(1, 1), (5, 1), (1, 5), (5, 5)])


def lock(canvas, x: int, cy: int, col=SUB) -> None:
    pygame.draw.rect(canvas, col, (x + 1, cy - 4, 4, 4), 1)
    canvas.fill(col, (x, cy - 1, 6, 5))


def check(canvas, x: int, cy: int, col=(170, 255, 200)) -> None:
    pygame.draw.lines(canvas, col, False, [(x, cy), (x + 2, cy + 2), (x + 6, cy - 3)], 1)
