"""모닥불 야영지 배경 (쉬기 타임랩스 전용, DESIGN.md 48-5): 물가가 아니라 바닥이 있는 풀밭.

하늘 · 별 · 해/달 · 구름 · 번개는 낚시 화면과 같은 것(같은 시각 · 날씨 팔레트)을 쓰고, 수평선 아래는 물 대신
먼 언덕 → 숲 줄 → 풀밭(가까울수록 어둡게) + 텐트 · 통나무 의자 · 돌로 두른 불자리 · 기대 놓은 낚싯대.
밝기는 팔레트 하늘색에서 (밤이면 어둡고 모닥불 빛이 더 큼). 겨울 · 얼음 바다 = 눈밭, 엘드라시온 = 푸른 풀.
비 · 안개 · 계절 파티클은 낚시 화면 것을 그대로 위에 그림.
"""
import math
import random

import pygame

from src.core.mathutil import clamp, lerp_color, scale_color
from src.render import world

GRASS = (92, 138, 76)
GRASS_ELDRA = (84, 132, 116)
SNOW = (222, 230, 240)
DIRT = (122, 96, 70)
TENT = (206, 128, 72)
TENT_DARK = (150, 84, 50)
LOG = (0x6B, 0x4A, 0x2E)
STONE = (128, 128, 136)

def _tufts(n: int = 36) -> list[tuple[float, float]]:
    rnd = random.Random(11)
    return [(rnd.random(), rnd.random() ** 0.7) for _ in range(n)]


TUFTS = _tufts()


def light_of(pal: dict) -> float:
    """하늘 아래쪽 밝기 → 0.28(한밤) ~ 1.0(한낮)."""
    r, g, b = pal["sky_bottom"]
    return clamp((0.299 * r + 0.587 * g + 0.114 * b) / 190.0, 0.28, 1.0)


def fire_pos(w: int, h: int) -> tuple[int, int]:
    """모닥불 바닥 자리 (화면 가운데 조금 아래)."""
    return w // 2 + 10, h - 52


def draw(canvas, f, t: float) -> None:
    pal = f.scene_palette()
    cam = f.cam
    w, h = canvas.get_size()
    hz = cam.horizon
    weather = f.weather
    # ── 하늘 (낚시 화면과 같은 것) ──
    world.draw_sky(canvas, pal, cam)
    f.stars.draw(canvas, pal, cam, t)
    world.draw_celestial(canvas, pal, cam, f.clock.hour, t, visible=weather == "clear")
    if f.theme.get("aurora"):
        from src.render.eldra_world import draw_aurora
        draw_aurora(canvas, pal, cam, t)
    f.clouds.draw(canvas, pal, cam)
    f.lightning.draw(canvas)
    light = light_of(pal)
    dark = 1.0 - light
    cont = f.spot.get("continent", "sharmion")
    snowy = f.season == "winter" or f.spot_id == "ice_sea"
    base = SNOW if snowy else (GRASS_ELDRA if cont == "eldrasion" else GRASS)
    # ── 먼 언덕 · 숲 줄 ──
    far = pal["mountain_far"]
    pts = [(0, h)] + [(x, hz - 16 - 10 * math.sin(x * 0.013 + 1.3) - 6 * math.sin(x * 0.041)) for x in range(0, w + 8, 8)] + [(w, h)]
    pygame.draw.polygon(canvas, far, pts)
    near = lerp_color(pal["mountain_near"], scale_color((52, 82, 58), light), 0.5)
    pygame.draw.rect(canvas, near, (0, hz - 4, w, h - hz + 4))
    for i in range(0, w + 10, 7):   # 침엽수 줄 (높이 들쭉날쭉)
        th = 8 + (i * 37 % 11)
        x = i + (i * 13 % 5)
        pygame.draw.polygon(canvas, near, [(x - 4, hz), (x, hz - th), (x + 4, hz)])
    # ── 풀밭 (멀수록 하늘색이 섞여 밝고, 가까울수록 어둡게) ──
    gy = hz + 6
    for y in range(gy, h, 3):
        u = (y - gy) / max(1, h - gy)
        col = scale_color(base, light * (1.0 - 0.28 * u))
        col = lerp_color(col, pal["sky_bottom"], 0.22 * (1 - u))
        canvas.fill(col, (0, y, w, 3))
    cx, by = fire_pos(w, h)
    # 불자리 흙 (타원)
    dirt = scale_color(DIRT if not snowy else (150, 140, 130), light * 0.95)
    pygame.draw.ellipse(canvas, dirt, (cx - 70, by - 12, 140, 28))
    # 풀 포기
    tuft = scale_color(lerp_color(base, (40, 70, 40), 0.45 if not snowy else 0.15), light)
    for fx, fy in TUFTS:
        x = int(fx * w)
        y = int(gy + 6 + fy * (h - gy - 8))
        if abs(x - cx) < 74 and abs(y - by) < 16:
            continue
        s = 1 + int(fy * 3)
        pygame.draw.line(canvas, tuft, (x, y), (x - s, y - 2 - s), 1)
        pygame.draw.line(canvas, tuft, (x, y), (x + s, y - 2 - s), 1)
        pygame.draw.line(canvas, tuft, (x, y), (x, y - 3 - s), 1)
    # ── 텐트 (왼쪽 뒤) ──
    tx, ty = cx - 118, by - 6
    tent = scale_color(TENT, light)
    tent_d = scale_color(TENT_DARK, light)
    pygame.draw.polygon(canvas, scale_color((30, 24, 20), light), [(tx - 40, ty + 2), (tx + 44, ty + 2), (tx + 40, ty + 6), (tx - 36, ty + 6)])
    pygame.draw.polygon(canvas, tent_d, [(tx + 4, ty - 44), (tx + 46, ty), (tx + 4, ty)])      # 옆면
    pygame.draw.polygon(canvas, tent, [(tx - 40, ty), (tx + 4, ty - 44), (tx + 4, ty)])        # 앞면
    pygame.draw.polygon(canvas, scale_color((40, 30, 26), light), [(tx - 18, ty), (tx - 4, ty - 22), (tx + 4, ty - 18), (tx + 4, ty)])  # 입구
    pygame.draw.line(canvas, scale_color((90, 70, 50), light), (tx + 4, ty - 44), (tx + 4, ty - 49), 1)   # 기둥 끝
    pygame.draw.line(canvas, scale_color((200, 200, 190), light), (tx - 40, ty), (tx - 52, ty + 4), 1)    # 줄
    # ── 기대 놓은 낚싯대 (텐트 오른쪽) ──
    rod = scale_color(pal["rod"], max(0.5, light))
    pygame.draw.line(canvas, rod, (tx + 52, ty + 2), (tx + 30, ty - 58), 2)
    pygame.draw.line(canvas, scale_color((220, 220, 230), light), (tx + 30, ty - 58), (tx + 34, ty - 30), 1)
    canvas.fill(scale_color(pal["reel"], max(0.5, light)), (tx + 46, ty - 14, 4, 4))
    # ── 통나무 의자 (오른쪽) ──
    lx, ly = cx + 46, by + 2
    log = scale_color(LOG, max(0.45, light))
    pygame.draw.rect(canvas, log, (lx, ly - 7, 34, 8), border_radius=3)
    pygame.draw.ellipse(canvas, scale_color((176, 134, 88), max(0.45, light)), (lx + 30, ly - 7, 6, 8))
    pygame.draw.line(canvas, scale_color((70, 48, 30), max(0.45, light)), (lx + 3, ly - 4), (lx + 26, ly - 4), 1)
    # ── 모닥불 빛 (바닥, 어두울수록 크게) ──
    r = int(46 + 40 * dark)
    a = (0.03 + 0.30 * dark * dark) * (0.85 + 0.15 * math.sin(t * math.tau / 0.5))
    glow = pygame.Surface((r * 2, r), pygame.SRCALPHA)
    for k in range(5):   # 바깥에서 안으로 계단식으로 밝게 (가장자리가 딱 끊기지 않게)
        q = 1.0 - k / 5
        c = a * (k + 1) / 5 * 0.45
        rect = pygame.Rect(0, 0, int(r * 2 * q), int(r * q))
        rect.center = (r, r // 2)
        pygame.draw.ellipse(glow, (int(232 * c), int(116 * c), int(59 * c)), rect)
        canvas.blit(glow, (cx - r, by - r // 2), special_flags=pygame.BLEND_RGB_ADD)
        glow.fill((0, 0, 0, 0))
    # 돌 두르기
    stone = scale_color(STONE, max(0.45, light))
    for k in range(9):
        ang = math.pi * (0.05 + 0.9 * k / 8)
        sx, sy = cx + math.cos(ang) * 15, by + 2 + math.sin(ang) * 4
        pygame.draw.ellipse(canvas, stone, (sx - 3, sy - 2, 6, 4))
    # ── 날씨 (낚시 화면 것 그대로) ──
    f.rain.draw(canvas, pal)
    f.fog.draw(canvas, pal, hz, t)
    f.season_fx.draw(canvas)
