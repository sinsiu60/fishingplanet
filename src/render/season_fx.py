"""계절 연출 (DESIGN.md 35-4): 팔레트 덧입힘 · 파티클(꽃잎·반딧불·낙엽·눈송이) · 겨울 살얼음 · 마을 장식.

시간대가 기본이고 계절은 은은하게 (하늘·물·산 8~14%). 엘드라시온은 개화기(수정 꽃)·성하기(청록 마력)·수확기(금빛)·극야기(별빛).
환상 전용 표현(오로라·멈춘 물방울·보라)은 쓰지 않는다. 파이팅 중에는 파티클을 화면 위쪽에만 30% (신호 슬롯을 가리지 않게).
"""
import math
import random

import pygame

from src.core import fxq
from src.core.mathutil import lerp_color

# (팔레트 키들, 목표 색, 비율)
TINT = {
    ("sharmion", "spring"): [(("sky_bottom", "cloud"), (255, 214, 226), 0.12), (("mountain_near", "mountain_far"), (150, 190, 120), 0.10)],
    ("sharmion", "summer"): [(("sky_top",), (70, 150, 235), 0.10), (("mountain_near", "mountain_far", "reed"), (50, 130, 60), 0.14)],
    ("sharmion", "autumn"): [(("sky_bottom",), (250, 200, 150), 0.12), (("mountain_near", "mountain_far", "reed"), (200, 110, 50), 0.16)],
    ("sharmion", "winter"): [(("sky_top", "sky_bottom", "water_top"), (215, 228, 245), 0.10), (("mountain_near", "mountain_far"), (235, 240, 248), 0.22)],
    ("eldrasion", "spring"): [(("sky_bottom", "cloud"), (220, 240, 250), 0.10), (("mountain_near",), (170, 220, 230), 0.10)],
    ("eldrasion", "summer"): [(("sky_top", "water_top"), (40, 140, 160), 0.10), (("wave_light",), (140, 240, 240), 0.12)],
    ("eldrasion", "autumn"): [(("sky_bottom", "reed", "mountain_near"), (230, 200, 110), 0.13)],
    ("eldrasion", "winter"): [(("sky_top", "sky_bottom"), (20, 26, 60), 0.12), (("mountain_far",), (210, 220, 240), 0.15)],
}
PARTICLE = {
    ("sharmion", "spring"): ("petal", [(255, 190, 210), (250, 215, 225)]),
    ("sharmion", "summer"): ("firefly", [(200, 255, 120)]),
    ("sharmion", "autumn"): ("leaf", [(220, 110, 40), (200, 70, 40), (230, 170, 60)]),
    ("sharmion", "winter"): ("snow", [(250, 252, 255)]),
    ("eldrasion", "spring"): ("petal", [(200, 240, 255), (230, 245, 255)]),
    ("eldrasion", "summer"): ("firefly", [(110, 240, 230)]),
    ("eldrasion", "autumn"): ("leaf", [(240, 200, 90), (220, 180, 70)]),
    ("eldrasion", "winter"): ("snow", [(240, 245, 255), (255, 250, 210)]),
}


def season_palette(pal: dict, season: str, cont: str = "sharmion") -> dict:
    rules = TINT.get((cont, season))
    if not rules:
        return pal
    out = dict(pal)
    for keys, col, k in rules:
        for key in keys:
            if isinstance(out.get(key), tuple):
                out[key] = lerp_color(out[key], col, k)
    if (cont, season) == ("eldrasion", "winter") and "stars" in out:
        out["stars"] = max(out["stars"], 0.35)   # 극야기: 별이 가장 밝다
    return out


class SeasonParticles:
    def __init__(self, rnd=None):
        self.rnd = rnd or random.Random()
        self.ps: list[list] = []   # [x, y, vx, vy, phase, size, color_i]
        self.key = None

    def update(self, dt: float, season: str, cont: str, w: int, h: int, period: str, weather: str,
               mobile: bool = False, fighting: bool = False, enabled: bool = True, wind: float = 0.0,
               protect=None, fireflies: bool = True) -> None:
        """wind = 바람(-1~1, 화면 날씨 Wind.x) — 꽃잎 · 낙엽 · 눈송이가 바람 쪽으로 흘러감 (DT2).
        protect = 신호 보호 영역 (파이팅 중 그 안의 파티클은 그리지 않음, DESIGN.md 45장 📐)."""
        kind, cols = PARTICLE.get((cont, season), (None, []))
        if not enabled or kind is None or (kind == "firefly" and (period not in ("evening", "night") or not fireflies)):
            self.ps.clear()
            return
        self.key = (kind, cont)
        cap = (30 if mobile else 60) * (0.5 if weather in ("rain", "storm") else 1.0) * fxq.particles()
        rate = {"petal": 9, "leaf": 7, "snow": 16, "firefly": 4}[kind] * (0.5 if mobile else 1.0)
        r = self.rnd
        if len(self.ps) < cap and r.random() < rate * dt:
            if kind == "firefly":
                self.ps.append([r.uniform(0, w), r.uniform(h * 0.35, h * 0.85), r.uniform(-8, 8), r.uniform(-5, 5),
                                r.uniform(0, 6.28), 1, r.randrange(len(cols))])
            else:
                self.ps.append([r.uniform(-20, w + 20), -6, r.uniform(-14, 6) if kind != "snow" else r.uniform(-6, 6),
                                r.uniform(14, 30) if kind != "snow" else r.uniform(10, 22), r.uniform(0, 6.28),
                                r.choice((1, 2, 2, 3)), r.randrange(len(cols))])
        for p in self.ps:
            p[4] += dt * (2.2 if kind != "firefly" else 1.6)
            if kind == "firefly":
                p[2] += math.sin(p[4] * 1.3) * 10 * dt
                p[3] += math.cos(p[4]) * 8 * dt
                p[2] *= 0.98
                p[3] *= 0.98
            else:
                p[0] += math.sin(p[4]) * (14 if kind != "snow" else 6) * dt
            p[0] += p[2] * dt
            if kind != "firefly":
                p[0] += wind * 24 * dt   # 바람 쪽으로
            p[1] += p[3] * dt
        self.ps = [p for p in self.ps if -30 < p[0] < w + 30 and p[1] < h + 10]
        self.cols = cols
        self.kind = kind
        self.fighting = fighting
        self.protect = protect

    def draw(self, canvas) -> None:
        if not self.ps:
            return
        w, h = canvas.get_size()
        fight = getattr(self, "fighting", False)
        for i, p in enumerate(self.ps):
            if fight and (i % 3 or p[1] > h * 0.35):
                continue   # 파이팅 중: 위쪽에 1/3만 (신호 슬롯·물고기 주변 비움)
            if fight and self.protect is not None and self.protect.hit_pt(p[0], p[1], 4):
                continue   # 신호 보호 영역 (가운데 40%×50% · 슬롯 주변)
            x, y, s = int(p[0]), int(p[1]), p[5]
            col = self.cols[p[6] % len(self.cols)]
            k = self.kind
            if k == "petal":
                tilt = math.sin(p[4]) * 2
                pygame.draw.ellipse(canvas, col, (x, y, s + 2, max(1, s + int(tilt))))
            elif k == "leaf":
                a = p[4]
                pts = [(x + math.cos(a) * (s + 2), y + math.sin(a) * (s + 1)), (x - math.cos(a) * (s + 2), y - math.sin(a) * (s + 1)),
                       (x + math.sin(a) * s, y - math.cos(a) * s)]
                pygame.draw.polygon(canvas, col, pts)
            elif k == "snow":
                canvas.fill(col, (x, y, s, s))
            elif k == "firefly":
                glow = 0.5 + 0.5 * math.sin(p[4] * 3)
                if glow > 0.2:
                    g = pygame.Surface((10, 10))
                    pygame.draw.circle(g, tuple(int(v * 0.4 * glow) for v in col), (5, 5), 4)
                    canvas.blit(g, (x - 5, y - 5), special_flags=pygame.BLEND_RGB_ADD)
                    canvas.fill(tuple(int(v * glow) for v in col), (x, y, 1, 1))


def draw_ice_edges(canvas, pal: dict, horizon: float, t: float) -> None:
    """겨울 샤르미온: 수면 가장자리 살얼음 (화면 아래 양쪽 물가)."""
    w, h = canvas.get_size()
    ice = lerp_color((215, 230, 242), pal.get("water_top", (120, 150, 180)), 0.25)
    rnd = random.Random(3)
    surf = pygame.Surface((w, h), pygame.SRCALPHA)
    for side in (-1, 1):
        x0 = 0 if side < 0 else w
        pts = [(x0, h)]
        for i in range(9):
            u = i / 8
            x = x0 - side * (w * 0.28) * (1 - u) * (0.8 + 0.4 * rnd.random())
            y = h - (h - horizon) * 0.5 * u * (0.7 + 0.3 * rnd.random())
            pts.append((x, y))
        pts.append((x0, horizon + (h - horizon) * 0.45))
        pygame.draw.polygon(surf, (*ice, 150), pts)
        for j in range(5):   # 금
            a = pts[1 + j]
            b = (a[0] + side * rnd.uniform(10, 30), a[1] + rnd.uniform(4, 14))
            pygame.draw.line(surf, (*lerp_color(ice, (150, 180, 205), 0.6), 180), a, b, 1)
        shine = int(40 + 30 * math.sin(t * 0.8 + side))
        pygame.draw.lines(surf, (255, 255, 255, shine), False, pts[1:-1], 1)
    canvas.blit(surf, (0, 0))


def draw_village_decor(canvas, places: list, ox: float, season: str, night: float, t: float, ground: int) -> None:
    """마을 계절 장식: 봄 꽃 화분 · 여름 풍경 · 가을 곡식 다발 · 겨울 등불 + 지붕 눈."""
    for p in places:
        if p["kind"] in ("dock",):
            continue
        sx = p["x"] - ox
        x0, x1 = int(sx - p["w"] / 2), int(sx + p["w"] / 2)
        if season == "spring":
            for px in (x0 - 6, x1 + 2):
                canvas.fill((150, 90, 60), (px, ground - 8, 8, 8))
                for j, c in enumerate(((255, 160, 190), (255, 220, 120), (255, 190, 210))):
                    pygame.draw.circle(canvas, c, (px + 1 + j * 3, ground - 10 - (j % 2) * 2), 2)
        elif season == "summer":
            if p["kind"] in ("house", "hut", "arch"):
                cx = x1 - 6
                sway = math.sin(t * 2.4 + sx) * 2
                pygame.draw.line(canvas, (120, 110, 100), (cx, ground - 60), (cx + sway, ground - 50), 1)
                pygame.draw.polygon(canvas, (200, 220, 230), [(cx + sway - 3, ground - 50), (cx + sway + 3, ground - 50), (cx + sway, ground - 44)])
        elif season == "autumn":
            for px in (x0 - 8, x1 + 4):
                pygame.draw.polygon(canvas, (220, 180, 80), [(px, ground), (px + 3, ground - 16), (px + 6, ground)])
                canvas.fill((170, 120, 50), (px, ground - 7, 7, 2))
        elif season == "winter":
            if p["kind"] in ("house", "hut", "arch"):
                canvas.fill((245, 248, 252), (x0 - 6, ground - (62 if p["kind"] == "house" else 44 if p["kind"] == "hut" else 76) - 2, p["w"] + 12, 3))
            lx = sx
            col = (230, 70, 50)
            pygame.draw.ellipse(canvas, col, (lx - 4, ground - 70, 8, 10))
            if night > 0.2:
                g = pygame.Surface((20, 20))
                pygame.draw.circle(g, tuple(int(v * 0.4 * night) for v in (255, 150, 90)), (10, 10), 9)
                canvas.blit(g, (lx - 10, ground - 75), special_flags=pygame.BLEND_RGB_ADD)
