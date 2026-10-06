"""엘드라시온 대륙 배경: 지형(습지·수정 동굴·부유섬·화산·빙해·세계수)과 전경, 오로라.

world.draw_mountains / FOREGROUND 가 이 모듈의 함수를 부른다. 색은 모두 팔레트에서 섞어 시간대·날씨를 따른다.
"""
import math
import random

import numpy as np
import pygame

from src.core.mathutil import clamp, lerp_color, scale_color

_rnd = random.Random(7)
CRYSTALS = [(_rnd.uniform(0, 480), _rnd.uniform(10, 34), _rnd.uniform(-0.4, 0.4)) for _ in range(26)]
STALACTITES = [(_rnd.uniform(0, 480), _rnd.uniform(14, 60), _rnd.uniform(5, 12)) for _ in range(30)]
MOTES = [(_rnd.uniform(0, 480), _rnd.uniform(0, 140), _rnd.uniform(0, math.tau)) for _ in range(40)]


def _ridge(canvas, cam, color, fn, factor: float) -> None:
    hz = cam.horizon
    off = cam.parallax(factor)
    pts = [(0, hz + 1)]
    for x in range(0, cam.width + 4, 3):
        pts.append((x, hz - fn(x + off)))
    pts.append((cam.width, hz + 1))
    pygame.draw.polygon(canvas, color, pts)


# ───────────────────────── 하늘 연출 ─────────────────────────

_AURORA = {}


def draw_aurora(canvas, pal, cam, t: float) -> None:
    """오로라: 밤에 진하게, 낮에도 아주 옅게.
    띠 3개 × 2px 간격 세로줄(굵기 2)을 numpy 로 한꺼번에 층에 쓴다 (DESIGN.md 44 — 예전엔 프레임마다 draw.line 900번 · 새 층).
    줄 하나 = 열 x, x+1 · 행 int(y) ~ int(y + h) (pygame.draw.line 굵기 2 와 같은 칸), 뒤 띠가 앞 띠를 덮음 (그대로)."""
    night = pal.get("stars", 0.0)
    k = 0.25 + 0.75 * night
    W, H = cam.width, cam.horizon
    layer = _AURORA.get((W, H))
    if layer is None:
        layer = _AURORA[(W, H)] = pygame.Surface((W, H), pygame.SRCALPHA)
    off = cam.parallax(0.2)
    u = np.arange(0, W, 2) + off
    col_of = np.arange(W) // 2          # 열 c 를 칠하는 줄 = c // 2 번째 (x = 0, 2, 4 … 의 x 와 x+1)
    rows = np.arange(H, dtype=np.intp)[None, :]
    rs, gs, bs, ash = layer.get_shifts()
    out = np.zeros((W, H), dtype=np.uint32)
    for band, (col, y0, amp) in enumerate((((90, 255, 180), 34, 10), ((150, 120, 255), 54, 8), ((80, 220, 255), 22, 6))):
        y = y0 + amp * np.sin(u * 0.02 + t * 0.4 + band) + 5 * np.sin(u * 0.055 - t * 0.7)
        h = 18 + 10 * np.sin(u * 0.03 + band * 2 + t * 0.3)
        a = np.maximum(0, (70 * k * (0.6 + 0.4 * np.sin(u * 0.08 + t + band))).astype(np.int64))
        px = ((a.astype(np.uint32) << ash) | np.uint32((col[0] << rs) | (col[1] << gs) | (col[2] << bs)))[col_of]
        ys, ye = y.astype(np.intp)[col_of], (y + h).astype(np.intp)[col_of]
        m = (rows >= ys[:, None]) & (rows <= ye[:, None])
        out = np.where(m, px[:, None], out)
    pygame.surfarray.blit_array(layer, out)
    canvas.blit(layer, (0, 0))


# ───────────────────────── 지형 ─────────────────────────

def _marsh(canvas, pal, cam, t):
    _ridge(canvas, cam, pal["mountain_far"], lambda u: 10 + 5 * math.sin(u * 0.02) + 3 * math.sin(u * 0.07 + 1), 0.4)
    reed = lerp_color(pal["mountain_near"], (200, 210, 225), 0.35)
    _ridge(canvas, cam, reed, lambda u: 5 + 2.5 * abs(math.sin(u * 0.6)) + 2 * abs(math.sin(u * 1.3 + 1)), 0.8)
    # 수면 위 옅은 안개 띠
    mist = pygame.Surface((cam.width, 14), pygame.SRCALPHA)
    mist.fill((*lerp_color(pal["sky_bottom"], (230, 235, 245), 0.5), 60))
    canvas.blit(mist, (0, cam.horizon - 6))


def _cave(canvas, pal, cam, t):
    hz = cam.horizon
    rock = scale_color(pal["mountain_near"], 0.6)
    rock2 = scale_color(pal["mountain_near"], 0.45)
    # 천장이 하늘을 덮는다
    canvas.fill(rock2, (0, 0, cam.width, hz))
    off = cam.parallax(0.6)
    for x0, ln, w in STALACTITES:
        x = (x0 - off) % (cam.width + 40) - 20
        pygame.draw.polygon(canvas, rock, [(x - w, 0), (x + w, 0), (x, ln)])
    # 안쪽 벽 (수평선 근처) + 빛나는 수정
    _ridge(canvas, cam, rock, lambda u: 24 + 8 * math.sin(u * 0.04) + 6 * abs(math.sin(u * 0.2)), 0.6)
    glow = (140, 180, 255)
    for x0, h, lean in CRYSTALS:
        x = (x0 - cam.parallax(0.7)) % (cam.width + 40) - 20
        tw = 0.6 + 0.4 * math.sin(t * 1.5 + x0)
        col = lerp_color((90, 120, 200), (200, 230, 255), tw)
        base = hz - 2
        pygame.draw.polygon(canvas, col, [(x - 3, base), (x + 3, base), (x + 1 + lean * h, base - h)])
        pygame.draw.line(canvas, lerp_color(col, (255, 255, 255), 0.5), (x, base), (x + lean * h * 0.8, base - h * 0.8))
    halo = pygame.Surface((cam.width, 30), pygame.SRCALPHA)
    halo.fill((*glow, 18))
    canvas.blit(halo, (0, hz - 30))


def _sky_isles(canvas, pal, cam, t):
    hz = cam.horizon
    off = cam.parallax(0.3)
    isle = lerp_color(pal["mountain_far"], (120, 150, 120), 0.3)
    under = scale_color(isle, 0.6)
    fall = lerp_color(pal["sky_bottom"], (240, 250, 255), 0.7)
    for i, (x0, y, w) in enumerate(((60, 50, 70), (230, 30, 110), (390, 62, 60), (520, 40, 80))):
        x = (x0 - off) % 600 - 60
        bob = math.sin(t * 0.5 + i) * 2
        pygame.draw.ellipse(canvas, isle, (x - w / 2, y + bob, w, 12))
        pygame.draw.polygon(canvas, under, [(x - w / 2 + 4, y + 6 + bob), (x + w / 2 - 4, y + 6 + bob),
                                            (x + w * 0.1, y + 6 + w * 0.45 + bob)])
        # 섬에서 떨어지는 가는 폭포
        fx = x + w * 0.2
        for k in range(0, int(hz - y - 10), 4):
            canvas.fill(fall, (int(fx + math.sin(k * 0.3 + t * 4)), int(y + 10 + k + bob), 2, 3))
    # 수평선 = 구름 바다
    cloud = lerp_color(pal["sky_bottom"], (250, 252, 255), 0.6)
    for x in range(0, cam.width, 6):
        h = 6 + 4 * math.sin((x + off * 2) * 0.05 + t * 0.3)
        pygame.draw.ellipse(canvas, cloud, (x - 6, hz - h, 18, h * 2))


def _volcano(canvas, pal, cam, t):
    hz = cam.horizon
    off = cam.parallax(0.45)
    cone = scale_color(pal["mountain_far"], 0.7)
    x = 300 - off
    pygame.draw.polygon(canvas, cone, [(x - 150, hz), (x - 26, hz - 92), (x + 26, hz - 92), (x + 150, hz)])
    # 분화구 빛 + 용암 줄기
    lava = (255, 120, 40)
    pygame.draw.ellipse(canvas, lerp_color(cone, lava, 0.8), (x - 26, hz - 96, 52, 8))
    for i, dx in enumerate((-10, 6)):
        pts = [(x + dx + math.sin(k * 0.4 + i) * 3, hz - 90 + k) for k in range(0, 60, 6)]
        pygame.draw.lines(canvas, lerp_color(cone, lava, 0.6), False, pts, 2)
    # 연기 기둥
    smoke = lerp_color(pal["sky_bottom"], (70, 60, 60), 0.6)
    for i in range(7):
        k = ((t * 0.12 + i / 7) % 1.0)
        r = 10 + k * 30
        pygame.draw.circle(canvas, lerp_color(smoke, pal["sky_top"], k), (int(x + math.sin(k * 3 + i) * 12 + k * 30),
                                                                          int(hz - 100 - k * 90)), int(r))
    _ridge(canvas, cam, scale_color(pal["mountain_near"], 0.55),
           lambda u: 6 + 4 * abs(math.sin(u * 0.09)) + 3 * math.sin(u * 0.031), 0.8)


def _ice(canvas, pal, cam, t):
    ice = lerp_color(pal["mountain_far"], (220, 235, 250), 0.55)
    ice_dark = lerp_color(ice, (110, 150, 190), 0.45)
    _ridge(canvas, cam, ice_dark, lambda u: 18 + 10 * abs(math.sin(u * 0.013 + 1)) + 4 * math.sin(u * 0.07), 0.4)
    # 평평한 빙붕 (윗면이 반듯)
    _ridge(canvas, cam, ice, lambda u: 8 + (6 if (u // 70) % 2 else 3), 0.7)


def _world_tree(canvas, pal, cam, t):
    hz = cam.horizon
    off = cam.parallax(0.35)
    bark = lerp_color(scale_color(pal["mountain_far"], 0.7), (96, 72, 50), 0.55)
    leaf = lerp_color(pal["mountain_far"], (90, 170, 120), 0.45)
    x = 240 - off
    # 하늘을 덮는 거대한 수관
    for i in range(9):
        a = i / 9 * math.pi
        pygame.draw.circle(canvas, leaf, (int(x + math.cos(a) * 170), int(18 - math.sin(a) * 10)), 46)
    # 줄기 + 뿌리
    pygame.draw.polygon(canvas, bark, [(x - 40, hz), (x - 22, 20), (x + 22, 20), (x + 40, hz)])
    groove = scale_color(bark, 0.75)
    for gx in (-12, 2, 14):
        pygame.draw.line(canvas, groove, (x + gx, 30), (x + gx * 1.6, hz - 4), 1)
    for s in (-1, 1):
        pts = [(x + s * 30, hz - 20), (x + s * 80, hz - 26), (x + s * 140, hz - 6), (x + s * 160, hz)]
        pygame.draw.lines(canvas, bark, False, pts, 10)
    # 빛나는 홀씨
    for x0, y0, ph in MOTES:
        tw = 0.5 + 0.5 * math.sin(t * 2 + ph)
        yy = (y0 - t * 6) % 140
        canvas.fill(lerp_color((180, 255, 200), (255, 255, 220), tw), (int((x0 - off * 0.5) % 480), int(yy), 1, 1))


TERRAINS = {"marsh": _marsh, "cave": _cave, "sky_isles": _sky_isles, "volcano": _volcano, "ice": _ice,
            "world_tree": _world_tree}


def draw_terrain(canvas, pal, cam, terrain: str, t: float) -> bool:
    fn = TERRAINS.get(terrain)
    if fn is None:
        return False
    fn(canvas, pal, cam, t)
    return True


# ───────────────────────── 전경 ─────────────────────────

def draw_crystals(canvas, pal, t: float) -> None:
    rock = scale_color(pal["mountain_near"], 0.5)
    pygame.draw.polygon(canvas, rock, [(-10, 270), (-10, 220), (40, 214), (90, 236), (110, 270)])
    for i, (x, h, lean) in enumerate(((14, 46, -0.2), (36, 64, 0.1), (60, 38, 0.3), (82, 26, 0.5), (452, 40, -0.4),
                                      (470, 58, -0.15))):
        tw = 0.6 + 0.4 * math.sin(t * 1.3 + i)
        col = lerp_color((110, 140, 230), (210, 235, 255), tw)
        base = 262 if x < 240 else 270
        pygame.draw.polygon(canvas, col, [(x - 7, base), (x + 7, base), (x + 2 + lean * h, base - h), (x - 3 + lean * h, base - h + 6)])
        pygame.draw.line(canvas, (240, 250, 255), (x - 1, base - 4), (x + lean * h, base - h + 4), 1)


def draw_cloud_edge(canvas, pal, t: float) -> None:
    grass = lerp_color(pal["mountain_near"], (110, 170, 100), 0.4)
    soil = scale_color(grass, 0.6)
    pygame.draw.polygon(canvas, soil, [(-10, 270), (-10, 228), (70, 232), (120, 250), (130, 270)])
    pygame.draw.polygon(canvas, grass, [(-10, 232), (70, 236), (118, 252), (110, 246), (60, 228), (-10, 224)])
    for i in range(6):
        fx = 10 + i * 17
        canvas.fill((255, 230, 240) if i % 2 else (255, 255, 200), (fx, 226 + i * 3, 2, 2))
    puff = lerp_color(pal["sky_bottom"], (255, 255, 255), 0.7)
    for i, x in enumerate((380, 430, 470)):
        y = 258 + math.sin(t * 0.6 + i) * 2
        pygame.draw.ellipse(canvas, puff, (x - 30, y - 10, 70, 26))


def draw_obsidian(canvas, pal, t: float) -> None:
    rock = (34, 28, 34)
    rocks = [[(-10, 270), (-8, 220), (30, 206), (70, 222), (90, 270)], [(400, 270), (420, 236), (470, 226), (490, 270)]]
    for pts in rocks:
        pygame.draw.polygon(canvas, rock, pts)
    glow = 0.6 + 0.4 * math.sin(t * 2.2)
    lava = lerp_color((180, 50, 20), (255, 150, 60), glow)
    pygame.draw.lines(canvas, lava, False, [(4, 262), (18, 240), (34, 232), (46, 246)], 2)
    pygame.draw.lines(canvas, lava, False, [(430, 268), (440, 246), (458, 238)], 2)


def draw_ice_hole(canvas, pal, t: float) -> None:
    """빙해: 화면 아래쪽은 얼음판, 가운데 위쪽이 뚫린 얼음 구멍."""
    ice = lerp_color(pal["sky_bottom"], (225, 238, 250), 0.6)
    shade = lerp_color(ice, (120, 160, 200), 0.4)
    pygame.draw.polygon(canvas, ice, [(0, 270), (0, 236), (70, 246), (130, 262), (140, 270)])
    pygame.draw.polygon(canvas, ice, [(480, 270), (480, 232), (410, 244), (350, 262), (340, 270)])
    pygame.draw.lines(canvas, shade, False, [(0, 236), (70, 246), (130, 262)], 2)
    pygame.draw.lines(canvas, shade, False, [(480, 232), (410, 244), (350, 262)], 2)


def draw_roots(canvas, pal, t: float) -> None:
    bark = lerp_color(pal["mountain_near"], (80, 60, 40), 0.5)
    hi = lerp_color(bark, (200, 180, 140), 0.3)
    for pts in ([(-10, 230), (40, 222), (90, 240), (120, 270)], [(490, 222), (430, 230), (390, 252), (380, 270)]):
        pygame.draw.lines(canvas, bark, False, pts, 14)
        pygame.draw.lines(canvas, hi, False, [(x, y - 5) for x, y in pts], 2)
    for i in range(5):
        tw = 0.5 + 0.5 * math.sin(t * 2 + i)
        canvas.fill(lerp_color((150, 255, 190), (255, 255, 220), tw), (30 + i * 18, int(226 + math.sin(t + i) * 3), 2, 2))


FOREGROUNDS = {"crystals": draw_crystals, "cloud_edge": draw_cloud_edge, "obsidian": draw_obsidian,
               "ice_hole": draw_ice_hole, "roots": draw_roots}
