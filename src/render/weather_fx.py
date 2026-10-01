"""날씨·환경 연출: 낚시터/날씨 색감, 빗줄기, 번개, 환경 파티클(잠자리·갈매기·새 떼·반딧불)."""
import math
import random

import pygame

from src.core.mathutil import clamp, lerp, lerp_color, scale_color

KEEP = ("text", "bobber", "bobber_base")


def themed_palette(pal: dict, theme: dict, weather: str, flash: float = 0.0, legend: float = 0.0) -> dict:
    """시간대 팔레트에 낚시터 물색·어두움, 날씨 색감, 번개 섬광을 입힌다."""
    out = dict(pal)
    k = theme.get("tint_k", 0.0)
    if k > 0:
        tint = tuple(theme["water_tint"])
        for key in ("water_top", "water_bottom", "wave_dark"):
            out[key] = lerp_color(out[key], tint, k)
        out["wave_light"] = lerp_color(out["wave_light"], lerp_color(tint, (255, 255, 255), 0.6), k * 0.6)
    sk = theme.get("sky_k", 0.0)
    if sk > 0:
        # 엘드라시온: 낚시터 고유 하늘색 (화산 = 붉은 하늘, 동굴 = 거의 검정 등)
        tint = tuple(theme["sky_tint"])
        for key in ("sky_top", "sky_bottom", "cloud", "mountain_far", "mountain_near"):
            if key in out:
                out[key] = lerp_color(out[key], tint, sk)
    dark = theme.get("dark", 0.0)
    if dark > 0:
        for key, v in out.items():
            if isinstance(v, tuple) and key not in KEEP:
                out[key] = lerp_color(v, (4, 6, 18), dark)
        out["stars"] = max(out["stars"], 0.6)
    if weather in ("rain", "storm"):
        amt, gray = (0.3, (110, 116, 128)) if weather == "rain" else (0.5, (38, 42, 58))
        for key, v in out.items():
            if isinstance(v, tuple) and key not in KEEP:
                out[key] = lerp_color(v, gray, amt)
        out["stars"] = 0.0
        out["reflect"] = out["reflect"] * 0.25
        out["cloud"] = lerp_color(out["sky_top"], (80, 84, 96) if weather == "rain" else (30, 32, 44), 0.6)
    if weather == "fog":
        haze = lerp_color(out["sky_bottom"], (196, 204, 214), 0.6)
        for key, v in out.items():
            if isinstance(v, tuple) and key not in KEEP:
                out[key] = lerp_color(v, haze, 0.38)
        out["stars"] = out["stars"] * 0.3
        out["reflect"] = out["reflect"] * 0.3
    if legend > 0:
        # 전설 등장: 하늘·물이 보랏빛 황혼처럼 물든다
        for key, v in out.items():
            if isinstance(v, tuple) and key not in KEEP:
                out[key] = lerp_color(v, (70, 36, 96), 0.22 * legend)
        out["wave_light"] = lerp_color(out["wave_light"], (255, 214, 120), 0.3 * legend)
    if flash > 0:
        for key, v in out.items():
            if isinstance(v, tuple) and key not in KEEP:
                out[key] = lerp_color(v, (235, 240, 255), flash * 0.7)
    return out


class Rain:
    """화면 공간 빗줄기 + 수면 빗방울 파문(월드)."""

    def __init__(self, w: int, h: int):
        self.w, self.h = w, h
        self.drops: list[list[float]] = []
        self.ripple_t = 0.0

    def update(self, dt: float, weather: str, ripples, cam) -> None:
        heavy = weather == "storm"
        rate = 0 if weather in ("clear", "fog") else (10 if heavy else 4)
        wind = 0.35 if heavy else 0.12
        for _ in range(rate):
            sp = random.uniform(300, 430)
            self.drops.append([random.uniform(-40, self.w + 10), random.uniform(-20, 0), sp, wind,
                               random.uniform(5, 10) * (1.3 if heavy else 1.0),
                               random.uniform(cam.horizon + 4, self.h + 10)])
        for d in self.drops:
            d[1] += d[2] * dt
            d[0] += d[2] * d[3] * dt
        self.drops = [d for d in self.drops if d[1] < d[5]]
        # 수면 빗방울
        if rate:
            self.ripple_t += dt
            per = 0.03 if heavy else 0.08
            while self.ripple_t > per:
                self.ripple_t -= per
                ang = random.uniform(-0.65, 0.65) + cam.yaw
                dist = random.uniform(3.2, 26)
                ripples.spawn(math.sin(ang) * dist, math.cos(ang) * dist, size=0.15, life=0.5)

    def draw(self, canvas, pal) -> None:
        col = lerp_color(pal["sky_bottom"], (230, 236, 250), 0.45)
        for x, y, sp, wind, ln, _ in self.drops:
            pygame.draw.line(canvas, col, (x, y), (x - wind * ln, y - ln), 1)


class Fog:
    """안개: 수면 위를 천천히 흐르는 반투명 띠 여러 겹 (화면 공간)."""

    def __init__(self, w: int, h: int):
        self.w, self.h = w, h
        self.k = 0.0  # 안개 농도 (날씨가 바뀌면 서서히)

    def update(self, dt: float, weather: str) -> None:
        target = 1.0 if weather == "fog" else 0.0
        self.k += (target - self.k) * min(1.0, dt / 2.0)

    def draw(self, canvas, pal, horizon: int, t: float) -> None:
        if self.k < 0.02:
            return
        col = lerp_color(pal["sky_bottom"], (214, 220, 228), 0.55)
        layer = pygame.Surface((self.w, self.h), pygame.SRCALPHA)
        for i in range(5):
            y = horizon - 10 + i * 22
            hgt = 26 + i * 8
            a = int((70 + i * 18) * self.k)
            off = (t * (6 + i * 3)) % 120
            for x in range(-120, self.w + 120, 60):
                wob = math.sin((x + off) * 0.05 + i) * 6
                pygame.draw.ellipse(layer, (*col, a // 2), (x + off - 40, y + wob, 140, hgt))
        veil = int(60 * self.k)
        layer.fill((*col, veil), special_flags=pygame.BLEND_RGBA_MAX)
        canvas.blit(layer, (0, 0))


class Lightning:
    """폭풍: 5~12초마다 번개 (섬광 + 번개 줄기), 잠시 뒤 천둥."""

    def __init__(self):
        self.timer = random.uniform(4, 9)
        self.flash = 0.0
        self.bolt: list[tuple] = []
        self.bolt_t = 0.0
        self.thunder_in = -1.0
        self.events: list[str] = []

    def update(self, dt: float, weather: str, horizon: int, width: int) -> None:
        self.flash = max(0.0, self.flash - dt * 4)
        self.bolt_t = max(0.0, self.bolt_t - dt)
        if self.thunder_in > 0:
            self.thunder_in -= dt
            if self.thunder_in <= 0:
                self.events.append("thunder")
        if weather != "storm":
            return
        self.timer -= dt
        if self.timer <= 0:
            self.timer = random.uniform(5, 12)
            self._strike(horizon, width)

    def strike(self, horizon: int, width: int) -> None:
        """강제로 번개 (전설 '번개'의 점프 박자)."""
        self.timer = 0.0
        self._strike(horizon, width)

    def _strike(self, horizon: int, width: int) -> None:
        self.flash = 1.0
        self.bolt_t = 0.18
        x = random.uniform(40, width - 40)
        pts = [(x, 0)]
        y = 0
        while y < horizon - 4:
            y += random.uniform(8, 18)
            x += random.uniform(-12, 12)
            pts.append((x, min(y, horizon - 2)))
        self.bolt = pts
        self.thunder_in = random.uniform(0.2, 0.5)
        self.events.append("strike")

    def draw(self, canvas) -> None:
        if self.bolt_t > 0 and len(self.bolt) > 1:
            pygame.draw.lines(canvas, (200, 210, 255), False, self.bolt, 3)
            pygame.draw.lines(canvas, (255, 255, 255), False, self.bolt, 1)


# ───────────────────────── 환경 파티클 ─────────────────────────

class Ambient:
    """시간대·날씨·낚시터에 맞는 작은 생물들."""

    def __init__(self, w: int, h: int, horizon: int):
        self.w, self.h, self.hz = w, h, horizon
        self.flies = [self._new_fly() for _ in range(3)]
        self.fireflies = [[random.uniform(0, w), random.uniform(horizon + 30, h - 20), random.uniform(0, 6.3),
                           random.uniform(0, 6.3)] for _ in range(14)]
        self.flock: list | None = None
        self.flock_t = random.uniform(3, 10)
        self.gulls = [[random.uniform(0, w), random.uniform(20, horizon - 30), random.choice((-1, 1)),
                       random.uniform(12, 22), random.uniform(0, 6)] for _ in range(3)]

    def _new_fly(self):
        return [random.uniform(0, self.w), random.uniform(self.hz + 30, self.h - 40), 0.0, 0.0,
                random.uniform(0, 6.3)]

    def update(self, dt: float, period: str, weather: str, sea: bool) -> None:
        # 잠자리: 목표 지점으로 휙휙 이동
        for f in self.flies:
            if random.random() < dt * 0.8:
                f[2] = random.uniform(-60, 60)
                f[3] = random.uniform(-25, 25)
            f[0] = (f[0] + f[2] * dt) % self.w
            f[1] = clamp(f[1] + f[3] * dt, self.hz + 20, self.h - 30)
            f[2] *= 0.97
            f[3] *= 0.97
        for ff in self.fireflies:
            ff[2] += dt * 0.7
            ff[0] = (ff[0] + math.cos(ff[2]) * 6 * dt) % self.w
            ff[1] += math.sin(ff[2] * 1.3) * 4 * dt
        for g in self.gulls:
            g[0] += g[2] * g[3] * dt
            g[4] += dt
            if g[0] < -20 or g[0] > self.w + 20:
                g[2] = -g[2]
        # 새 떼 (저녁)
        if self.flock is None and period == "evening" and weather != "storm":
            self.flock_t -= dt
            if self.flock_t <= 0:
                d = random.choice((-1, 1))
                self.flock = [-30 if d > 0 else self.w + 30, random.uniform(25, self.hz - 50), d, 0.0]
                self.flock_t = random.uniform(14, 26)
        if self.flock is not None:
            self.flock[0] += self.flock[2] * 34 * dt
            self.flock[3] += dt
            if self.flock[0] < -80 or self.flock[0] > self.w + 80:
                self.flock = None

    def draw(self, canvas, pal, period: str, weather: str, sea: bool, t: float) -> None:
        dry = weather == "clear"
        if period in ("morning", "day") and dry and not sea:
            body = scale_color(lerp_color(pal["rod"], (40, 70, 160), 0.6), 1.0)
            wing = lerp_color(pal["sky_bottom"], (255, 255, 255), 0.6)
            for x, y, _, _, ph in self.flies:
                canvas.fill(body, (int(x) - 2, int(y), 5, 1))
                if int(t * 30 + ph * 10) % 2:
                    canvas.fill(wing, (int(x) - 1, int(y) - 1, 1, 1))
                    canvas.fill(wing, (int(x) + 1, int(y) - 1, 1, 1))
        if sea and period in ("morning", "day", "evening") and weather != "storm":
            col = lerp_color(pal["sky_top"], (250, 250, 250), 0.8)
            for x, y, d, _, ph in self.gulls:
                flap = 2 if math.sin(t * 6 + ph) > 0 else 0
                pygame.draw.lines(canvas, col, False, [(x - 4, y - flap), (x, y), (x + 4, y - flap)], 1)
        if self.flock is not None:
            x0, y0, d, age = self.flock
            col = lerp_color(pal["mountain_near"], (10, 8, 16), 0.5)
            for i in range(7):
                row = (i + 1) // 2
                side = -1 if i % 2 else 1
                x = x0 - d * row * 9
                y = y0 + side * row * 5
                flap = 2 if math.sin(t * 8 + i) > 0 else 0
                pygame.draw.lines(canvas, col, False, [(x - 3, y - flap), (x, y), (x + 3, y - flap)], 1)
        if period == "night" and dry and not sea:
            for x, y, ph, ph2 in self.fireflies:
                glow = 0.5 + 0.5 * math.sin(t * 2.2 + ph2 * 3)
                if glow < 0.25:
                    continue
                c = lerp_color(pal["water_bottom"], (220, 255, 120), glow)
                canvas.fill(c, (int(x), int(y), 2, 2))
                if glow > 0.8:
                    canvas.fill(lerp_color(pal["water_bottom"], (180, 230, 90), 0.4),
                                (int(x) - 1, int(y) - 1, 4, 4))
                    canvas.fill(c, (int(x), int(y), 2, 2))
