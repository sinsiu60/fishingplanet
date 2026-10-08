"""기다려지는 것 (CU12) 마을 그림: 계절 축제 장식 4종 · 떠돌이 상인 수레. 화면 효과만 (확률 · 판매 영향 없음)."""
import math

import pygame

from src.core.mathutil import lerp_color


def draw_festival(canvas, kind: str, places: list, ox: float, w: int, t: float, night: float, ground: int, horizon: int) -> None:
    """축제 장식: 봄 = 처마 사이 분홍 등불 줄 · 여름 = 밤하늘 불꽃 · 가을 = 단풍 깃발 줄 · 겨울 = 얼음 등불."""
    if kind == "fireworks":
        if night < 0.3:
            return
        for i in range(3):   # 3초 주기로 하나씩 터짐
            ph = (t * 0.45 + i / 3) % 1.0
            cx = (i * 157 + int(t * 0.45 + i / 3) * 97) % w
            cy = 30 + (i * 37) % 50
            if ph < 0.25:   # 올라가는 꼬리
                y = horizon - (horizon - cy) * (ph / 0.25)
                canvas.fill((255, 240, 200), (cx, int(y), 1, 3))
                continue
            k = (ph - 0.25) / 0.75
            col = ((255, 120, 120), (255, 214, 90), (140, 220, 255))[i]
            r = 4 + 26 * (1 - (1 - k) ** 2)
            for j in range(14):
                a = j / 14 * math.tau
                x, y = cx + math.cos(a) * r, cy + math.sin(a) * r + k * k * 8
                canvas.fill(lerp_color((20, 20, 30), col, 1 - k * 0.8), (int(x), int(y), 2, 2))
        return
    houses = [p for p in places if p["kind"] not in ("dock",)]
    for a, b in zip(houses, houses[1:]):   # 이웃한 건물 처마 사이 줄
        x0, x1 = a["x"] + a["w"] / 2 - ox, b["x"] - b["w"] / 2 - ox
        if x1 < -20 or x0 > w + 20:
            continue
        y0 = ground - 52
        n = max(2, int((x1 - x0) / 14))
        pts = [(x0 + (x1 - x0) * i / n, y0 + math.sin(math.pi * i / n) * 10) for i in range(n + 1)]
        pygame.draw.lines(canvas, (70, 60, 50), False, [(int(x), int(y)) for x, y in pts], 1)
        for i, (x, y) in enumerate(pts[1:-1], 1):
            sway = math.sin(t * 2 + i) * 1.5
            if kind == "lantern":   # 분홍 등불 (밤엔 빛남)
                col = lerp_color((230, 140, 170), (255, 200, 220), night)
                if night > 0.3:
                    pygame.draw.circle(canvas, lerp_color((40, 30, 40), (255, 190, 210), night * 0.4), (int(x + sway), int(y + 6)), 6)
                pygame.draw.ellipse(canvas, col, (int(x + sway) - 3, int(y) + 2, 6, 8))
                canvas.fill((120, 60, 70), (int(x + sway) - 1, int(y) + 1, 2, 1))
            elif kind == "maple":   # 단풍 깃발 (삼각)
                col = ((230, 100, 40), (240, 170, 50), (200, 60, 40))[i % 3]
                pygame.draw.polygon(canvas, col, [(int(x) - 3, int(y)), (int(x) + 3, int(y)), (int(x + sway), int(y) + 8)])
            elif kind == "ice":     # 얼음 등불 (작은 육각 + 푸른 빛)
                col = lerp_color((180, 220, 245), (230, 250, 255), night)
                if night > 0.3:
                    pygame.draw.circle(canvas, lerp_color((30, 40, 60), (170, 220, 255), night * 0.35), (int(x), int(y + 6)), 6)
                pygame.draw.polygon(canvas, col, [(int(x) - 3, int(y) + 3), (int(x), int(y) + 1), (int(x) + 3, int(y) + 3),
                                                  (int(x) + 3, int(y) + 8), (int(x), int(y) + 10), (int(x) - 3, int(y) + 8)])


def draw_merchant(canvas, sx: float, feet: int, t: float, night: float, hover: bool) -> pygame.Rect:
    """떠돌이 상인: 등롱 단 수레 + 망토 두른 상인."""
    x, y = int(sx), feet
    canvas.fill((110, 70, 40), (x - 26, y - 16, 34, 12))         # 수레 짐칸
    canvas.fill((150, 100, 60), (x - 26, y - 18, 34, 3))
    pygame.draw.circle(canvas, (60, 40, 30), (x - 18, y - 3), 4)  # 바퀴
    pygame.draw.circle(canvas, (60, 40, 30), (x + 1, y - 3), 4)
    canvas.fill((120, 80, 140), (x - 24, y - 26, 10, 9))           # 짐 보따리
    canvas.fill((200, 160, 80), (x - 12, y - 24, 9, 7))
    pygame.draw.line(canvas, (80, 60, 40), (x - 26, y - 18), (x - 26, y - 34), 1)
    glow = 0.6 + 0.4 * math.sin(t * 3)
    if night > 0.3:
        pygame.draw.circle(canvas, lerp_color((30, 25, 30), (255, 170, 90), night * 0.35 * glow), (x - 26, y - 33), 7)
    pygame.draw.ellipse(canvas, (220, 70, 60), (x - 29, y - 37, 6, 8))   # 등롱
    bob = int(math.sin(t * 2) * 1)
    canvas.fill((70, 60, 90), (x + 12, y - 22 + bob, 10, 20))            # 망토
    pygame.draw.circle(canvas, (215, 185, 160), (x + 17, y - 25 + bob), 4)
    pygame.draw.polygon(canvas, (60, 50, 80), [(x + 11, y - 26 + bob), (x + 23, y - 26 + bob), (x + 17, y - 34 + bob)])   # 고깔
    r = pygame.Rect(x - 32, y - 40, 58, 42)
    if hover:
        pygame.draw.rect(canvas, (255, 230, 150), r, 1)
    return r
