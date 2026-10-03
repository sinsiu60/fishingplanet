"""보물상자 그림 (픽셀 느낌). 상자 화면과 포획 컷(물고기가 물고 나옴)이 같이 쓴다."""
import math

import pygame

from src.render.screen import opaque as _opaque

from src.core.mathutil import clamp, lerp_color, scale_color


def draw_glow(canvas, x: float, y: float, radius: float, color, strength: float = 1.0) -> None:
    """부드러운 원형 빛 (가산 혼합)."""
    r = max(2, int(radius))
    layer = _opaque((r * 2, r * 2))
    layer.fill((0, 0, 0))
    for i in range(r, 0, -2):
        k = 0.45 * strength * (1 - i / r) ** 1.6  # 가운데로 갈수록 밝게 (가산 혼합이라 색 자체를 어둡게 해서 세기 조절)
        pygame.draw.circle(layer, tuple(min(255, int(c * k)) for c in color), (r, r), i)
    canvas.blit(layer, (int(x) - r, int(y) - r), special_flags=pygame.BLEND_RGB_ADD)


def draw_chest(canvas, x: float, y: float, scale: float, color, lid: float = 0.0, shake: float = 0.0,
               t: float = 0.0) -> None:
    """(x, y) = 상자 바닥 가운데. lid 0 = 닫힘, 1 = 활짝. shake = 흔들림 세기 (픽셀)."""
    s = scale
    if shake > 0:
        x += math.sin(t * 60) * shake
        y += math.cos(t * 47) * shake * 0.4
    w, h = 22 * s, 13 * s
    wood = scale_color(color, 0.75)
    dark = scale_color(color, 0.45)
    band = lerp_color(color, (255, 236, 170), 0.55)
    body = pygame.Rect(int(x - w / 2), int(y - h), int(w), int(h))
    canvas.fill(dark, body.inflate(2, 2))
    canvas.fill(wood, body)
    canvas.fill(scale_color(wood, 0.85), (body.x, body.y + body.h // 2, body.w, max(1, int(s))))
    for bx in (body.x + int(3 * s), body.right - int(5 * s)):
        canvas.fill(band, (bx, body.y, max(2, int(2 * s)), body.h))
    # 뚜껑: 경첩(뒤쪽 위)을 축으로 열린다 → 화면에선 위로 납작해지며 뒤로 넘어감
    lid_h = 7 * s
    k = clamp(lid, 0, 1)
    top = body.y - lid_h * (1 - k) - 2 * s * k
    lid_rect = pygame.Rect(body.x - 1, int(top), body.w + 2, max(2, int(lid_h * (1 - 0.8 * k))))
    if k > 0.05:
        # 열린 틈으로 빛
        inner = pygame.Rect(body.x + 2, body.y - int(2 * s * k), body.w - 4, int(3 * s * k) + 2)
        canvas.fill(lerp_color(color, (255, 255, 230), 0.7), inner)
    canvas.fill(dark, lid_rect.inflate(2, 2))
    canvas.fill(color, lid_rect)
    canvas.fill(lerp_color(color, (255, 255, 255), 0.35), (lid_rect.x + 1, lid_rect.y + 1, lid_rect.w - 2, max(1, int(s))))
    for bx in (body.x + int(3 * s), body.right - int(5 * s)):
        canvas.fill(band, (bx, lid_rect.y, max(2, int(2 * s)), lid_rect.h))
    if k < 0.3:
        # 걸쇠
        cx = int(x)
        canvas.fill(band, (cx - int(2 * s), body.y - int(1 * s), int(4 * s) or 2, int(4 * s) or 3))
        canvas.fill(dark, (cx - 1, body.y + int(1 * s), 2, 2))


def draw_item_icon(canvas, x: float, y: float, kind: str, color, known: bool = True) -> None:
    """상자 아이템 아이콘 (16px 정도). known=False면 실루엣."""
    c = color if known else (58, 62, 78)
    d = scale_color(c, 0.55)
    x, y = int(x), int(y)
    if kind == "consumable":       # 주머니
        pygame.draw.circle(canvas, d, (x, y + 2), 7)
        pygame.draw.circle(canvas, c, (x, y + 2), 6)
        canvas.fill(d, (x - 3, y - 6, 6, 3))
    elif kind == "charm":          # 목걸이 부적
        pygame.draw.arc(canvas, d, (x - 7, y - 9, 14, 12), 0, math.pi, 1)
        pygame.draw.polygon(canvas, c, [(x, y - 2), (x + 6, y + 4), (x, y + 9), (x - 6, y + 4)])
        pygame.draw.polygon(canvas, d, [(x, y - 2), (x + 6, y + 4), (x, y + 9), (x - 6, y + 4)], 1)
    elif kind == "cosmetic":       # 찌
        canvas.fill(c, (x - 3, y - 4, 6, 8))
        canvas.fill((240, 240, 240) if known else d, (x - 3, y + 1, 6, 2))
        canvas.fill(d, (x, y - 9, 1, 5))
    elif kind == "rod":            # 낚싯대
        pygame.draw.line(canvas, c, (x - 8, y + 8), (x + 8, y - 8), 2)
        pygame.draw.circle(canvas, d, (x - 4, y + 4), 3)
    elif kind == "reel":           # 릴
        pygame.draw.circle(canvas, c, (x, y), 7)
        pygame.draw.circle(canvas, d, (x, y), 3)
        pygame.draw.line(canvas, d, (x, y), (x + 9, y - 5), 2)
    else:                          # 뜰채
        pygame.draw.ellipse(canvas, c, (x - 7, y - 9, 14, 11), 2)
        pygame.draw.line(canvas, d, (x + 4, y + 1), (x + 9, y + 9), 2)
