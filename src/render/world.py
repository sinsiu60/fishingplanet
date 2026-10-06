"""배경 그리기: 하늘, 별, 해·달, 구름, 산, 수면, 반사광, 갈대.

나중에 이미지로 교체할 때는 이 모듈의 함수만 바꾸면 된다.
"""
import math
import random

import numpy as np
import pygame

from src.render.screen import opaque as _opaque

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

_GRAD: dict = {}  # 그라데이션 캐시: 색·크기가 같으면 줄마다 다시 칠하지 않고 한 번에 붙인다 (폰 렉, v0.8.7)


def _cached(key, w: int, h: int, paint) -> pygame.Surface:
    surf = _GRAD.get(key)
    if surf is None:
        if len(_GRAD) > 24:
            _GRAD.clear()
        surf = _opaque((max(1, w), max(1, h)))
        paint(surf)
        _GRAD[key] = surf
    return surf


def draw_sky(canvas: pygame.Surface, pal: dict, cam) -> None:
    top, bottom = tuple(pal["sky_top"]), tuple(pal["sky_bottom"])

    def paint(s):
        band = 3
        for y in range(0, cam.horizon, band):
            t = (y / cam.horizon) ** 1.3
            s.fill(lerp_color(top, bottom, t), (0, y, cam.width, band))
    canvas.blit(_cached(("sky", top, bottom, cam.horizon, cam.width), cam.width, cam.horizon, paint), (0, 0))


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


def draw_celestial(canvas, pal, cam, hour: float, t: float, visible: bool = True) -> None:
    if not visible:
        return
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


def _peak_far(u: float) -> float:
    # 뾰족한 바위산: 삼각파 + 잔물결
    def tri(x, p):
        k = (x / p) % 1.0
        return 1 - abs(2 * k - 1)
    return 34 + 52 * tri(u + 40, 150) ** 1.5 + 18 * tri(u + 10, 63) + 4 * math.sin(u * 0.4)


def _forest_near(u: float) -> float:
    trees = 5 * abs(math.sin(u * 0.32)) + 3 * abs(math.sin(u * 0.71 + 1)) + 2 * abs(math.sin(u * 1.3))
    return 16 + 6 * math.sin(u * 0.02 + 2) + trees


def _island(u: float) -> float:
    # 왼쪽 멀리 작은 섬 하나
    d = (u + 140) / 70
    return max(0.0, 9 * (1 - d * d)) if abs(d) < 1 else 0.0


def _cliff(u: float) -> float:
    # 폭포: 양옆 높은 절벽, 가운데 틈
    a = abs(u - 240) / 240
    return max(0.0, 20 + 110 * a ** 1.5 + 6 * math.sin(u * 0.15))


TERRAIN = {
    "hills": [(_mountain_far, 0.5, "mountain_far"), (_mountain_near, 0.8, "mountain_near")],
    "peaks": [(_peak_far, 0.5, "mountain_far"), (_forest_near, 0.8, "mountain_near")],
    "coast": [(_island, 0.5, "mountain_far")],
    "open": [],
    "falls": [(_cliff, 0.6, "mountain_near")],
}


_HEIGHTS: dict = {}


def draw_mountains(canvas, pal, cam, terrain: str = "hills", t: float = 0.0) -> None:
    from src.render import eldra_world
    if eldra_world.draw_terrain(canvas, pal, cam, terrain, t):
        return  # 엘드라시온 지형
    hz = cam.horizon
    layers = TERRAIN.get(terrain, TERRAIN["hills"])
    if terrain == "falls":
        _draw_waterfall(canvas, pal, cam, t)
    for fn, factor, key in layers:
        color = pal[key]
        off = cam.parallax(factor)
        memo = _HEIGHTS.setdefault(fn, {})
        if len(memo) > 20000:
            memo.clear()
        base = int(round(off))
        pts = [(0, hz + 1)]
        for x in range(0, cam.width + 4, 3):
            u = x + base
            h = memo.get(u)
            if h is None:
                h = memo[u] = fn(u)  # 지형 높이는 위치마다 늘 같다 → 한 번만 계산 (폰 렉, v0.8.7)
            pts.append((x, hz - h))
        pts.append((cam.width, hz + 1))
        pygame.draw.polygon(canvas, color, pts)
    if terrain == "peaks":
        # 봉우리 눈
        off = cam.parallax(0.5)
        snow = lerp_color(pal["mountain_far"], (245, 245, 250), 0.55)
        for x in range(0, cam.width, 2):
            h = _peak_far(x + off)
            if h > 72:
                canvas.fill(snow, (x, int(hz - h), 2, int((h - 72) * 0.5) + 1))
    if terrain == "coast":
        _draw_lighthouse(canvas, pal, cam, t)


def _draw_lighthouse(canvas, pal, cam, t: float) -> None:
    x = cam.angle_to_x(math.radians(24))
    if x is None:
        return
    hz = cam.horizon
    rock = lerp_color(pal["mountain_far"], (60, 60, 70), 0.3)
    pygame.draw.ellipse(canvas, rock, (x - 18, hz - 6, 36, 12))
    body = lerp_color(pal["mountain_far"], (240, 240, 235), 0.6)
    red = lerp_color(pal["mountain_far"], (200, 60, 50), 0.6)
    canvas.fill(body, (int(x) - 3, hz - 34, 7, 30))
    for i in range(3):
        canvas.fill(red, (int(x) - 3, hz - 30 + i * 9, 7, 3))
    canvas.fill(red, (int(x) - 4, hz - 38, 9, 4))
    night = pal["stars"]
    lamp = lerp_color((255, 240, 180), (255, 255, 220), night)
    canvas.fill(lamp, (int(x) - 1, hz - 37, 3, 2))
    if night > 0.2:
        # 회전하는 등대 불빛
        a = t * 1.6
        reach = 110 * abs(math.cos(a))
        side = 1 if math.sin(a) > 0 else -1
        beam = pygame.Surface((int(reach) + 2, 20), pygame.SRCALPHA)
        for i in range(int(reach)):
            k = i / max(1, reach)
            half = 1 + k * 7
            alpha = int(110 * night * (1 - k) ** 0.8)
            pygame.draw.line(beam, (255, 245, 200, alpha), (i, 10 - half), (i, 10 + half))
        if side < 0:
            beam = pygame.transform.flip(beam, True, False)
            canvas.blit(beam, (x - reach, hz - 46))
        else:
            canvas.blit(beam, (x, hz - 46))


def _draw_waterfall(canvas, pal, cam, t: float) -> None:
    hz = cam.horizon
    x = cam.cx - cam.parallax(0.6)
    top = hz - 120
    fall = lerp_color(pal["wave_light"], (255, 255, 255), 0.3)
    canvas.fill(lerp_color(pal["water_top"], fall, 0.5), (int(x) - 16, top, 32, hz - top))
    for i in range(10):
        yy = top + ((t * 120 + i * 37) % (hz - top))
        canvas.fill(fall, (int(x) - 14 + (i * 7) % 28, int(yy), 2, 8))
    mist = lerp_color(pal["sky_bottom"], (255, 255, 255), 0.4)
    pygame.draw.ellipse(canvas, mist, (x - 40, hz - 10, 80, 14))


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

    def draw(self, canvas, pal, t: float, hour: float, amp_mult: float = 1.0, show_reflection: bool = True) -> None:
        cam = self.cam
        hz = cam.horizon
        # 1) 바탕 그라데이션 (12단계로 끊어서 픽셀 느낌) — 색이 바뀔 때만 다시 그린 것을 붙인다
        top, bottom = tuple(pal["water_top"]), tuple(pal["water_bottom"])
        edge = lerp_color(pal["sky_bottom"], top, 0.35)

        def paint(s):
            for i, y in enumerate(range(hz + 1, cam.height)):
                q = round(self.row_t[i] * 12) / 12
                s.fill(lerp_color(top, bottom, q), (0, y - hz, cam.width, 1))
            s.fill(edge, (0, 0, cam.width, 1))
        canvas.blit(_cached(("water", top, bottom, edge, hz, cam.width, cam.height), cam.width, cam.height - hz, paint),
                    (0, hz))

        # 2) 해·달 반사광 띠 (아래로 갈수록 넓어짐)
        for body in celestial_bodies(hour) if show_reflection else []:
            if body["elev"] < math.radians(-1.5):
                continue
            x = cam.angle_to_x(body["az"])
            if x is None:
                continue
            strength = pal["reflect"] * (1.0 if body["kind"] == "sun" else 0.75)
            self._draw_reflection(canvas, pal, x, t, strength)

        # 3) 물결 줄
        self._draw_waves(canvas, pal, t, amp_mult, top, bottom)

    # 물결 · 반사광은 numpy 로 한꺼번에 계산해 캔버스 픽셀에 바로 쓴다 (DESIGN.md 44):
    # 예전엔 줄 26개 × 마루·골 구간마다 · 반사광 줄마다 파이썬에서 fill 을 불러 (프레임당 300번 남짓) 폰에서 가장 무거운 그림이었다.
    # 계산식 · 그리는 순서(마루 → 골, 먼 줄 → 가까운 줄, 겹치면 나중 것)는 그대로.
    @staticmethod
    def _mapped(canvas, cols: np.ndarray) -> np.ndarray:
        """(n, 3) 색 → 캔버스 픽셀 값 (불투명 32비트)."""
        rs, gs, bs, _ = canvas.get_shifts()
        cols = cols.astype(np.uint32)
        out = (cols[:, 0] << rs) | (cols[:, 1] << gs) | (cols[:, 2] << bs)
        am = canvas.get_masks()[3]
        return out | np.uint32(am) if am else out

    @staticmethod
    def _put(canvas, xs: np.ndarray, ys: np.ndarray, vals: np.ndarray) -> None:
        """픽셀 쓰기 — 같은 자리에 여러 번이면 나중 것 (fill 을 차례로 부른 것과 같게)."""
        if not len(xs):
            return
        h = canvas.get_height()
        lin = xs.astype(np.int64) * h + ys
        _, last = np.unique(lin[::-1], return_index=True)
        last = len(lin) - 1 - last
        px = pygame.surfarray.pixels2d(canvas)
        px[xs[last], ys[last]] = vals[last]
        del px

    def _draw_waves(self, canvas, pal, t: float, amp_mult: float, top, bottom) -> None:
        cam = self.cam
        hz, H, W = cam.horizon, cam.height, cam.width
        light, dark = pal["wave_light"], pal["wave_dark"]
        rows = []   # 줄마다 (번호, 거리, y0, 배율, 진폭, 마루 색)
        for i, z in enumerate(self.depths):
            y0 = cam.row_for_distance(z)
            if y0 >= H:
                continue
            near = clamp(1.0 - z / 50.0, 0.25, 1.0)
            crest = lerp_color(lerp_color(top, bottom, (y0 - hz) / (H - hz)), light, near)
            rows.append((i, z, y0, cam.f / z, min(2.0, 5.0 / z) * amp_mult, crest))
        if not rows:
            return
        n = len(rows)
        idx = np.array([r[0] for r in rows], dtype=np.float64)
        zz = np.array([r[1] for r in rows])
        ss = np.array([r[3] for r in rows])
        # 월드 좌우 좌표로 패턴을 만들어 둘러볼 때 수면이 같이 움직이게
        U = (self.xs[None, :] - cam.cx) / ss[:, None] + cam.yaw * zz[:, None]
        phase = t * (0.9 + 0.05 * idx) + idx * 1.7
        wave = np.sin(U * 1.3 + phase[:, None]) * np.sin(U * 0.37 - phase[:, None] * 0.6 + idx[:, None])
        # 줄마다 [마루, 골] 두 칸 (골은 가까운 줄 z < 18 만)
        M = np.zeros((2 * n, W + 2), dtype=bool)
        M[0::2, 1:-1] = wave > 0.45
        M[1::2, 1:-1] = (wave < -0.55) & (zz < 18)[:, None]
        ybase = np.empty(2 * n)
        ybase[0::2] = [r[2] for r in rows]
        ybase[1::2] = [r[2] + max(1, r[3] * 0.05) for r in rows]
        amps = np.repeat([r[4] for r in rows], 2)
        cols = np.empty((2 * n, 3), dtype=np.int64)
        cols[0::2] = [r[5] for r in rows]
        cols[1::2] = tuple(dark)
        flat = M.ravel()
        d = np.diff(flat.view(np.int8))
        starts = np.flatnonzero(d == 1) + 1                 # 구간 시작 (평평하게 편 자리)
        if not len(starts):
            return
        srow = starts // (W + 2)
        sx = starts % (W + 2) - 1
        ys_run = (ybase[srow] + np.sin(U[srow // 2, sx] * 0.8 + t * 1.5) * amps[srow]).astype(np.int64)
        pix = np.flatnonzero(flat)
        run = np.searchsorted(starts, pix, side="right") - 1
        xs = pix % (W + 2) - 1
        ys = ys_run[run]
        keep = (ys < H) & (ys >= 0)
        vals = self._mapped(canvas, cols)[srow[run]]
        self._put(canvas, xs[keep], ys[keep], vals[keep])

    def _draw_reflection(self, canvas, pal, bx: float, t: float, strength: float) -> None:
        cam = self.cam
        hz = cam.horizon
        span = cam.height - hz
        W = cam.width
        r = np.arange(1, span)
        r = r[(r + int(t * 6)) % 3 != 0]
        half = 1 + r * 0.22
        jitter = np.sin(r * 0.71 + t * 2.1) * half * 0.35
        length = half * (0.6 + 0.4 * np.sin(r * 1.37 + t * 3.3))
        ok = length >= 0.8
        r, jitter, length = r[ok], jitter[ok], length[ok]
        if not len(r):
            return
        wt, wb = np.array(pal["water_top"], dtype=np.float64), np.array(pal["water_bottom"], dtype=np.float64)
        q = np.clip((r / span) ** 0.55, 0.0, 1.0)[:, None]
        water = (wt + (wb - wt) * q).astype(np.int64).astype(np.float64)   # lerp_color 와 같은 정수 자르기
        k = np.clip(strength * (1.0 - 0.55 * r / span), 0.0, 1.0)[:, None]
        refl = np.array(pal["reflection"], dtype=np.float64)
        cols = (water + (refl - water) * k).astype(np.int64)
        x0 = (bx + jitter - length).astype(np.int64)
        wdt = np.maximum(1, (length * 2).astype(np.int64))
        # 줄마다 [x0, x0 + 폭) — 화면 밖은 잘림 (fill 과 같게)
        a = np.clip(x0, 0, W)
        b = np.clip(x0 + wdt, 0, W)
        cnt = b - a
        live = cnt > 0
        if not live.any():
            return
        a, cnt, rows, vals = a[live], cnt[live], hz + r[live], self._mapped(canvas, cols[live])
        rep = np.repeat(np.arange(len(a)), cnt)
        offs = np.arange(cnt.sum()) - np.repeat(np.cumsum(cnt) - cnt, cnt)
        self._put(canvas, a[rep] + offs, rows[rep], vals[rep])


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

    def draw(self, canvas, pal, t: float, wind: float = 1.0) -> None:
        base_y = self.cam.height + 2
        color = pal["reed"]
        head = scale_color(color, 0.7)
        for s in self.stems:
            sway = math.sin(t * 1.3 * wind + s["phase"]) * 3 * wind + (wind - 1) * 4
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


# ───────────────────────── 환경 위협 구역 (수초·바위·물살) ─────────────────────────

class HazardDecor:
    """구역 안에 장식(수초 줄기·연잎 / 바위 / 물살)을 흩뿌려 월드 좌표로 그린다."""

    def __init__(self, hazards: list, seed: int = 21):
        rnd = random.Random(seed)
        self.items = []
        for hz in hazards:
            count = 26 if hz["type"] == "weeds" else 12 if hz["type"] == "rocks" else 20
            for _ in range(count):
                ang = rnd.uniform(*hz["angle"])
                dist = rnd.uniform(*hz["dist"])
                self.items.append({"type": hz["type"], "hz": hz, "x": math.sin(ang) * dist, "z": math.cos(ang) * dist,
                                   "size": rnd.uniform(0.6, 1.4), "ph": rnd.uniform(0, math.tau)})
        self.items.sort(key=lambda it: -it["z"])

    def draw(self, canvas, pal, cam, t: float, active_hz=None) -> None:
        warn = active_hz is not None and int(t * 6) % 2 == 0
        for it in self.items:
            p = cam.project(it["x"], it["z"])
            if p is None:
                continue
            sx, sy, s = p
            if sx < -20 or sx > cam.width + 20:
                continue
            k = it["size"]
            hot = warn and it["hz"] is active_hz
            if it["type"] == "weeds":
                col = pal["reed"] if not hot else (200, 80, 60)
                pad = lerp_color(pal["reed"], pal["water_top"], 0.25) if not hot else (220, 110, 80)
                w = clamp(0.5 * s * k, 2, 26)
                pygame.draw.ellipse(canvas, pad, (sx - w / 2, sy - max(1, w * 0.12), w, max(2, w * 0.25)))
                h = clamp(0.7 * s * k, 3, 24)
                sway = math.sin(t * 1.4 + it["ph"]) * h * 0.15
                pygame.draw.line(canvas, col, (sx, sy), (sx + sway, sy - h), 1)
                pygame.draw.line(canvas, col, (sx + w * 0.2, sy), (sx + w * 0.2 + sway * 0.7, sy - h * 0.7), 1)
            elif it["type"] == "rocks":
                col = pal["mountain_near"] if not hot else (200, 80, 60)
                w = clamp(0.55 * s * k, 3, 30)
                h = clamp(0.25 * s * k, 2, 12)
                pygame.draw.ellipse(canvas, col, (sx - w / 2, sy - h, w, h * 1.6))
                pygame.draw.line(canvas, lerp_color(col, (255, 255, 255), 0.25), (sx - w * 0.3, sy - h * 0.8),
                                 (sx + w * 0.1, sy - h * 0.95), 1)
                pygame.draw.line(canvas, pal["wave_light"], (sx - w / 2 - 1, sy + h * 0.55), (sx + w / 2 + 1, sy + h * 0.55), 1)
            else:  # current
                col = pal["wave_light"] if not hot else (255, 150, 120)
                w = max(3, 1.5 * s * k)
                off = (t * 30 + it["ph"] * 10) % (w * 2) - w
                pygame.draw.line(canvas, col, (sx - w / 2 + off * 0.3, sy), (sx + w / 2 + off * 0.3, sy), 1)


# ───────────────────────── 낚시터별 전경 ─────────────────────────

def draw_boulders(canvas, pal, t: float) -> None:
    """계곡: 왼쪽 아래 큰 바위들."""
    base = lerp_color(pal["mountain_near"], (95, 95, 100), 0.35)
    shade = scale_color(base, 0.7)
    moss = lerp_color(base, (80, 130, 70), 0.4)
    rocks = [[(-10, 270), (-6, 222), (22, 206), (58, 214), (78, 240), (84, 270)],
             [(70, 270), (78, 248), (104, 238), (128, 246), (136, 270)],
             [(-10, 210), (4, 196), (24, 200), (20, 214)]]
    for pts in rocks:
        pygame.draw.polygon(canvas, base, pts)
        pygame.draw.polygon(canvas, shade, [pts[0]] + [(x + 4, y + 10) for x, y in pts[1:-1]] + [pts[-1]])
        pygame.draw.lines(canvas, moss, False, pts[1:-1], 2)


def _tetrapod(canvas, cx: float, cy: float, r: float, rot: float, col, shade) -> None:
    for i in range(3):
        a = rot + i * math.tau / 3
        ex, ey = cx + math.cos(a) * r, cy + math.sin(a) * r * 0.8
        pygame.draw.line(canvas, shade, (cx + 2, cy + 2), (ex + 2, ey + 2), int(r * 0.55))
        pygame.draw.line(canvas, col, (cx, cy), (ex, ey), int(r * 0.5))
        pygame.draw.circle(canvas, col, (int(ex), int(ey)), int(r * 0.26))
    pygame.draw.circle(canvas, col, (int(cx), int(cy - r * 0.3)), int(r * 0.35))


def draw_tetrapods(canvas, pal, t: float) -> None:
    """방파제: 왼쪽 아래 테트라포드."""
    col = lerp_color(pal["mountain_far"], (175, 175, 168), 0.55)
    shade = scale_color(col, 0.62)
    for cx, cy, r, rot in ((30, 262, 30, 0.4), (88, 270, 24, 1.3), (-6, 226, 22, 2.2)):
        _tetrapod(canvas, cx, cy, r, rot, col, shade)


def draw_boat(canvas, pal, t: float) -> None:
    """배 위: 화면 아래 뱃전(난간)."""
    wood = lerp_color(pal["rod"], (120, 82, 52), 0.5)
    dark = scale_color(wood, 0.65)
    light = lerp_color(wood, (230, 200, 160), 0.3)
    top = [(0, 246), (480, 238)]
    pygame.draw.polygon(canvas, wood, [top[0], top[1], (480, 270), (0, 270)])
    pygame.draw.line(canvas, light, top[0], top[1], 3)
    for i in range(1, 4):
        y0, y1 = 246 + i * 7, 238 + i * 7
        pygame.draw.line(canvas, dark, (0, y0), (480, y1), 1)
    # 난간 기둥 + 로프
    for px in (60, 210, 360):
        py = 246 - px * 8 / 480
        canvas.fill(dark, (px - 2, int(py) - 16, 5, 18))
        canvas.fill(light, (px - 2, int(py) - 16, 5, 2))
    rope = lerp_color(wood, (200, 180, 130), 0.6)
    pts = [(x, 246 - x * 8 / 480 - 14 + math.sin(x * 0.04) * 2) for x in range(60, 361, 30)]
    pygame.draw.lines(canvas, rope, False, pts, 1)


def draw_ship_lamp(canvas, pal, cam) -> None:
    """심해: 배 조명이 비추는 수면."""
    glow = pygame.Surface((cam.width, cam.height), pygame.SRCALPHA)
    for i, (z, w, a) in enumerate(((9.5, 3.4, 28), (8.5, 2.4, 34), (7.8, 1.4, 44))):
        y = cam.row_for_distance(z)
        rx = w * cam.f / z
        ry = rx * cam.cam_h / z * 1.8
        pygame.draw.ellipse(glow, (190, 230, 210, a), (cam.cx - rx, y - ry, rx * 2, ry * 2))
    canvas.blit(glow, (0, 0))


FOREGROUND = {"boulders": draw_boulders, "tetrapods": draw_tetrapods, "boat": draw_boat}


def _register_eldra() -> None:
    from src.render.eldra_world import FOREGROUNDS
    FOREGROUND.update(FOREGROUNDS)


_register_eldra()
