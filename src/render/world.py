"""배경 그리기: 하늘, 별, 해·달, 구름, 산, 수면, 반사광, 갈대.

나중에 이미지로 교체할 때는 이 모듈의 함수만 바꾸면 된다.
"""
import math
import random

import numpy as np
import pygame

from src.core.mathutil import clamp, lerp, lerp_color, scale_color

MOON_COLOR = (236, 236, 214)
STAR_COLOR = (255, 255, 240)


# ───────────────────────── 해 · 달 ─────────────────────────

def celestial_bodies(hour: float) -> list[dict]:
    """현재 보이는 해/달의 방위각·고도(라디안). 화면에 잘 보이도록 고도는 낮게 잡는다."""
    bodies = []
    if 5.6 <= hour <= 19.4:
        s = (hour - 5.6) / 13.8
        bodies.append({
            "kind": "sun",
            "az": math.radians(lerp(-32, 20, s)),
            "elev": math.radians(-2 + 17 * math.sin(math.pi * s)),
        })
    moon_t = (hour - 19.5) % 24.0
    if moon_t <= 11.0:
        s = moon_t / 11.0
        bodies.append({
            "kind": "moon",
            "az": math.radians(lerp(-35, 40, s)),
            "elev": math.radians(-2 + 15 * math.sin(math.pi * s)),
        })
    return bodies


def body_screen_pos(cam, body) -> tuple[float, float] | None:
    x = cam.angle_to_x(body["az"])
    if x is None:
        return None
    return x, cam.horizon - math.tan(body["elev"]) * cam.f


# ───────────────────────── 하늘 ─────────────────────────

def draw_sky(canvas: pygame.Surface, pal: dict, cam) -> None:
    band = 3
    for y in range(0, cam.horizon, band):
        t = (y / cam.horizon) ** 1.3
        canvas.fill(lerp_color(pal["sky_top"], pal["sky_bottom"], t), (0, y, cam.width, band))


class StarField:
    def __init__(self, cam, count: int = 80, seed: int = 7):
        rnd = random.Random(seed)
        self.span = cam.width * 3
        self.stars = [
            (rnd.uniform(0, self.span), rnd.uniform(0, cam.horizon - 18) ** 1.0,
             rnd.random(), rnd.uniform(0, math.tau))
            for _ in range(count)
        ]

    def draw(self, canvas, pal, cam, t: float) -> None:
        amount = pal["stars"]
        if amount <= 0.01:
            return
        off = cam.parallax(0.15)
        for x, y, b, ph in self.stars:
            if b > amount:
                continue
            sx = int((x - off) % self.span)
            if sx >= cam.width:
                continue
            twinkle = 0.6 + 0.4 * math.sin(t * 2.0 + ph)
            # 수평선 근처 별은 흐리게
            fade = clamp((cam.horizon - 10 - y) / 40, 0, 1)
            k = amount * twinkle * fade
            canvas.set_at((sx, int(y)), lerp_color(pal["sky_top"], STAR_COLOR, k))


def draw_celestial(canvas, pal, cam, hour: float, t: float) -> None:
    for body in celestial_bodies(hour):
        pos = body_screen_pos(cam, body)
        if pos is None:
            continue
        x, y = int(pos[0]), int(pos[1])
        if body["kind"] == "sun":
            color, radius = pal["sun"], 8
        else:
            color, radius = MOON_COLOR, 6
        sky_here = lerp_color(pal["sky_top"], pal["sky_bottom"], clamp(y / cam.horizon, 0, 1) ** 1.3)
        # 픽셀아트식 계단 후광
        for i, (r_add, k) in enumerate(((10, 0.18), (6, 0.32), (3, 0.5))):
            pygame.draw.circle(canvas, lerp_color(sky_here, color, k), (x, y), radius + r_add)
        pygame.draw.circle(canvas, color, (x, y), radius)
        if body["kind"] == "moon":
            crater = scale_color(MOON_COLOR, 0.86)
            pygame.draw.circle(canvas, crater, (x - 2, y - 1), 2)
            pygame.draw.circle(canvas, crater, (x + 2, y + 2), 1)


class Clouds:
    def __init__(self, cam, count: int = 6, seed: int = 3):
        rnd = random.Random(seed)
        self.span = cam.width * 2
        self.clouds = []
        for _ in range(count):
            w = rnd.randint(24, 56)
            self.clouds.append({
                "x": rnd.uniform(0, self.span),
                "y": rnd.uniform(14, cam.horizon - 40),
                "w": w,
                "speed": rnd.uniform(1.5, 4.0),
                "puffs": [(rnd.uniform(-0.45, 0.45) * w, rnd.uniform(-4, 1), rnd.uniform(0.3, 0.55) * w)
                          for _ in range(4)],
            })

    def update(self, dt: float) -> None:
        for c in self.clouds:
            c["x"] = (c["x"] + c["speed"] * dt) % self.span

    def draw(self, canvas, pal, cam) -> None:
        off = cam.parallax(0.3)
        base = pal["cloud"]
        shade = lerp_color(base, pal["sky_bottom"], 0.45)
        for c in self.clouds:
            cx = (c["x"] - off) % self.span - c["w"]
            if cx < -c["w"] or cx > cam.width + c["w"]:
                continue
            y = c["y"]
            h = c["w"] * 0.22
            pygame.draw.ellipse(canvas, shade, (cx - c["w"] / 2, y, c["w"], h + 2))
            for px, py, pw in c["puffs"]:
                pygame.draw.ellipse(canvas, base, (cx + px - pw / 2, y + py - pw * 0.25, pw, pw * 0.5))
            pygame.draw.ellipse(canvas, base, (cx - c["w"] / 2 + 2, y, c["w"] - 4, h))


# ───────────────────────── 산 ─────────────────────────

def _mountain_far(u: float) -> float:
    return 22 + 13 * math.sin(u * 0.021 + 1.0) + 8 * math.sin(u * 0.053 + 2.0) + 3 * math.sin(u * 0.13 + 0.5)


def _mountain_near(u: float) -> float:
    hill = 9 + 7 * math.sin(u * 0.017 + 4.0) + 4 * math.sin(u * 0.041 + 1.3)
    trees = 2.5 * abs(math.sin(u * 0.45)) + 1.5 * abs(math.sin(u * 0.83 + 1))
    return max(3.0, hill) + trees


def draw_mountains(canvas, pal, cam) -> None:
    hz = cam.horizon
    for fn, factor, color in (
        (_mountain_far, 0.5, pal["mountain_far"]),
        (_mountain_near, 0.8, pal["mountain_near"]),
    ):
        off = cam.parallax(factor)
        pts = [(0, hz + 1)]
        for x in range(0, cam.width + 4, 3):
            pts.append((x, hz - fn(x + off)))
        pts.append((cam.width, hz + 1))
        pygame.draw.polygon(canvas, color, pts)


# ───────────────────────── 수면 ─────────────────────────

class Water:
    """원근 수면. 물결 줄은 수평선 근처 촘촘, 아래로 갈수록 넓게."""

    def __init__(self, cam, lines: int = 26, z_near: float = 3.0, z_far: float = 90.0):
        self.cam = cam
        ratio = (z_far / z_near) ** (1 / (lines - 1))
        self.depths = [z_near * ratio ** i for i in range(lines)]
        self.xs = np.arange(cam.width, dtype=np.float64)
        rows = np.arange(cam.horizon + 1, cam.height)
        self.row_t = ((rows - cam.horizon) / (cam.height - cam.horizon)) ** 0.55

    def draw(self, canvas, pal, t: float, hour: float) -> None:
        cam = self.cam
        hz = cam.horizon
        # 1) 바탕 그라데이션 (12단계로 끊어서 픽셀 느낌)
        top, bottom = pal["water_top"], pal["water_bottom"]
        for i, y in enumerate(range(hz + 1, cam.height)):
            q = round(self.row_t[i] * 12) / 12
            canvas.fill(lerp_color(top, bottom, q), (0, y, cam.width, 1))
        canvas.fill(lerp_color(pal["sky_bottom"], top, 0.35), (0, hz, cam.width, 1))

        # 2) 해·달 반사광 띠 (아래로 갈수록 넓어짐)
        for body in celestial_bodies(hour):
            if body["elev"] < math.radians(-1.5):
                continue
            x = cam.angle_to_x(body["az"])
            if x is None:
                continue
            strength = pal["reflect"] * (1.0 if body["kind"] == "sun" else 0.75)
            self._draw_reflection(canvas, pal, x, t, strength)

        # 3) 물결 줄
        light, dark = pal["wave_light"], pal["wave_dark"]
        for i, z in enumerate(self.depths):
            y0 = cam.row_for_distance(z)
            if y0 >= cam.height:
                continue
            s = cam.f / z
            # 월드 좌우 좌표로 패턴을 만들어 둘러볼 때 수면이 같이 움직이게
            u = (self.xs - cam.cx) / s + cam.yaw * z
            phase = t * (0.9 + 0.05 * i) + i * 1.7
            wave = np.sin(u * 1.3 + phase) * np.sin(u * 0.37 - phase * 0.6 + i)
            amp = min(2.0, 5.0 / z)
            near = clamp(1.0 - z / 50.0, 0.25, 1.0)
            crest_color = lerp_color(lerp_color(top, bottom, (y0 - hz) / (cam.height - hz)), light, near)
            self._draw_runs(canvas, wave > 0.45, y0, amp, u, t, crest_color)
            if z < 18:
                self._draw_runs(canvas, wave < -0.55, y0 + max(1, s * 0.05), amp, u, t, dark)

    def _draw_runs(self, canvas, mask, y0, amp, u, t, color) -> None:
        if not mask.any():
            return
        d = np.diff(np.concatenate(([0], mask.view(np.int8), [0])))
        starts = np.flatnonzero(d == 1)
        ends = np.flatnonzero(d == -1)
        for a, b in zip(starts, ends):
            y = int(y0 + math.sin(u[a] * 0.8 + t * 1.5) * amp)
            if y < self.cam.height:
                canvas.fill(color, (int(a), y, int(b - a), 1))

    def _draw_reflection(self, canvas, pal, bx: float, t: float, strength: float) -> None:
        cam = self.cam
        hz = cam.horizon
        span = cam.height - hz
        for r in range(1, span, 1):
            if (r + int(t * 6)) % 3 == 0:
                continue
            y = hz + r
            half = 1 + r * 0.22
            jitter = math.sin(r * 0.71 + t * 2.1) * half * 0.35
            length = half * (0.6 + 0.4 * math.sin(r * 1.37 + t * 3.3))
            if length < 0.8:
                continue
            water = lerp_color(pal["water_top"], pal["water_bottom"], (r / span) ** 0.55)
            k = strength * (1.0 - 0.55 * r / span)
            color = lerp_color(water, pal["reflection"], k)
            canvas.fill(color, (int(bx + jitter - length), y, max(1, int(length * 2)), 1))


# ───────────────────────── 앞쪽 갈대 ─────────────────────────

class Reeds:
    def __init__(self, cam, seed: int = 11):
        rnd = random.Random(seed)
        self.cam = cam
        self.stems = []
        for _ in range(9):
            self.stems.append({
                "x": rnd.uniform(-6, 70),
                "h": rnd.uniform(36, 70),
                "lean": rnd.uniform(-6, 10),
                "phase": rnd.uniform(0, math.tau),
                "head": rnd.random() < 0.55,
            })

    def draw(self, canvas, pal, t: float) -> None:
        base_y = self.cam.height + 2
        color = pal["reed"]
        head = scale_color(color, 0.7)
        for s in self.stems:
            sway = math.sin(t * 1.3 + s["phase"]) * 3
            tip = (s["x"] + s["lean"] + sway, base_y - s["h"])
            mid = (s["x"] + (s["lean"] + sway) * 0.35, base_y - s["h"] * 0.5)
            pygame.draw.lines(canvas, color, False, [(s["x"], base_y), mid, tip], 2)
            if s["head"]:
                pygame.draw.rect(canvas, head, (tip[0] - 1, tip[1] + 2, 3, 8))
        # 잎사귀
        for i, s in enumerate(self.stems[:5]):
            sway = math.sin(t * 1.1 + s["phase"]) * 2
            x0 = s["x"]
            pygame.draw.lines(canvas, color, False, [
                (x0, base_y), (x0 + 10 + sway, base_y - 18), (x0 + 22 + sway, base_y - 22)], 1)
