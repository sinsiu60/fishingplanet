"""이동 컷신 그림 (DESIGN.md 35-3): 1인칭 원근 — 지평선에서 물체가 다가와 양옆으로 지나가고, 바닥 줄무늬가 흘러온다.

장면 설정은 data/travel_cutscenes.json (바닥·옆·먼 배경·물체 목록·이동 방식). 색은 지금 시간대 팔레트(pal)·계절을 따른다.
환상 전용 표현(오로라·멈춘 물방울)은 쓰지 않는다 — 극광 빙해도 얼음·눈 요소만.
"""
import math
import random

import pygame

from src.core.mathutil import clamp, lerp_color

H = 118          # 지평선
F = 62           # 원근 배율 (z=1 에서 바닥이 지평선 아래 F px)
Z_FAR, Z_NEAR = 1.7, 0.16

TREE = {"spring": ((110, 160, 90), (245, 180, 200)), "summer": ((60, 130, 60), None),
        "autumn": ((200, 110, 50), (230, 170, 60)), "winter": ((150, 160, 170), (240, 245, 250))}


def _shade(c, pal, k):
    return lerp_color(c, pal.get("sky_top", (0, 0, 0)), k)


class TravelView:
    def __init__(self, cfg: dict, w: int, h: int, season: str = "spring", reduce: bool = False, seed: int = 1):
        self.cfg = cfg
        self.w, self.h = w, h
        self.season = season
        self.reduce = reduce
        self.rnd = random.Random(seed)
        self.objs: list[list] = []      # [lat, z, kind, seed]
        self.dist = 0.0
        self.t = 0.0
        self.spawn_z = 0.0
        dense = cfg.get("dense", 1.0)
        self.gap = 0.22 / dense
        z = Z_NEAR
        while z < Z_FAR:                # 처음부터 길에 물체가 있게
            self._spawn(z)
            z += self.gap
        self.spawn_z = Z_FAR

    def _spawn(self, z: float) -> None:
        r = self.rnd
        kind = r.choice(self.cfg["objects"])
        water = self.cfg["ground"] in ("sea", "deep", "red_sea", "marsh")
        if kind in ("wave", "bubble", "buoy", "steam", "gull_wave", "ice_crack", "glow", "cloud"):
            lat = r.uniform(-2.6, 2.6)
        elif kind in ("root", "arch"):
            lat = 0.0
        else:
            side = r.choice((-1, 1))
            lat = side * r.uniform(0.75 if not water else 0.9, 2.6)
        self.objs.append([lat, z, kind, r.random()])

    # ── 시간 ──
    def update(self, dt: float, speed: float = 1.0) -> None:
        self.t += dt
        v = 0.42 * self.cfg.get("speed", 1.0) * speed
        dz = v * dt
        self.dist += dz
        for o in self.objs:
            o[1] -= dz
        self.objs = [o for o in self.objs if o[1] > Z_NEAR * 0.7]
        self.spawn_z -= dz
        while self.spawn_z < Z_FAR:
            self.spawn_z += self.gap * self.rnd.uniform(0.6, 1.4)
            self._spawn(self.spawn_z)

    # ── 투영 ──
    def bob(self) -> tuple[float, float]:
        if self.reduce:
            return 0.0, 0.0
        m = self.cfg.get("move", "walk")
        if m in ("walk", "bridge"):
            ph = self.dist * 14
            return math.sin(ph) * 1.2, -abs(math.cos(ph)) * 2.2
        if m in ("boat", "ship"):
            return math.sin(self.t * 0.9) * 2.0, math.sin(self.t * 1.3) * 2.5
        return 0.0, 0.0

    def proj(self, lat: float, z: float, height: float = 0.0) -> tuple[float, float, float]:
        s = F / max(0.05, z)
        bx, by = self._b
        return self.w / 2 + lat * s + bx, H + (1.0 - height) * s + by, s / F

    # ── 그리기 ──
    def draw(self, canvas, pal: dict, night: float, weather: str) -> None:
        self._b = self.bob()
        w, h = self.w, self.h
        c = self.cfg
        dark = c.get("darken", 0.0) * clamp(self.t / 3.0, 0, 1)
        if c.get("cave"):
            dark = max(dark, 0.4 * clamp(self.t / 2.0, 0, 1))
        top, bot = pal["sky_top"], pal["sky_bottom"]
        hz = int(H + self._b[1])
        for y in range(0, hz + 1, 3):
            canvas.fill(lerp_color(top, bot, y / max(1, hz)), (0, y, w, 3))
        self._far(canvas, pal, hz, night)
        self._ground(canvas, pal, hz, night)
        for o in sorted(self.objs, key=lambda o: -o[1]):
            self._obj(canvas, pal, o, night)
        self._vehicle(canvas, pal, night)
        if c.get("fog"):
            k = c["fog"] * (0.6 + 0.4 * math.sin(self.t * 0.5))
            fog = pygame.Surface((w, h), pygame.SRCALPHA)
            for y in range(0, h, 4):
                a = int(255 * k * (0.35 + 0.65 * (1 - abs(y - hz) / h)))
                fog.fill((210, 214, 220, min(220, a)), (0, y, w, 4))
            canvas.blit(fog, (0, 0))
        if weather in ("rain", "storm"):
            for i in range(70 if weather == "rain" else 120):
                x = (i * 53 + self.t * 200) % (w + 40) - 20
                y = (i * 97 + self.t * 420) % h
                pygame.draw.line(canvas, (170, 180, 200), (x, y), (x - 3, y + 9), 1)
        if dark > 0.01:
            sh = pygame.Surface((w, h), pygame.SRCALPHA)
            sh.fill((4, 6, 18, int(255 * dark)))
            canvas.blit(sh, (0, 0))
        if c.get("cave"):   # 동굴: 가장자리 바위 + 안쪽 수정 빛이 번짐
            k = clamp(self.t / 2.5, 0, 1)
            edge = pygame.Surface((w, h), pygame.SRCALPHA)
            for i in range(10):
                pygame.draw.rect(edge, (14, 12, 20, int(26 * k)), (i * 6, i * 4, w - i * 12, h - i * 8), 8)
            canvas.blit(edge, (0, 0))
            glow = pygame.Surface((w, h))
            r = int(30 + 80 * k)
            for i in range(8):
                pygame.draw.circle(glow, tuple(int(v * 0.06 * k) for v in (90, 220, 230)), (w // 2, hz), int(r * (1 - i / 9)))
            canvas.blit(glow, (0, 0), special_flags=pygame.BLEND_RGB_ADD)

    def _far(self, canvas, pal, hz, night) -> None:
        w = self.w
        kind = self.cfg["far"]
        mf = pal.get("mountain_far", (90, 100, 120))
        ox = self._b[0] * 0.3
        if kind in ("hills", "peaks", "volcano", "ice", "islands", "tree"):
            pts = [(0, hz)]
            for x in range(0, w + 20, 16):
                u = x * 0.012
                if kind == "peaks":
                    hgt = 30 + 22 * abs(math.sin(u * 1.7)) + 10 * math.sin(u * 4.1)
                elif kind == "ice":
                    hgt = 12 + 6 * abs(math.sin(u * 2.3))
                else:
                    hgt = 16 + 10 * math.sin(u * 1.2) + 6 * math.sin(u * 3.3 + 1)
                pts.append((x + ox, hz - hgt))
            pts.append((w, hz))
            col = (220, 230, 240) if kind == "ice" else mf
            pygame.draw.polygon(canvas, col, pts)
            if kind == "volcano":
                cx = w * 0.62
                pygame.draw.polygon(canvas, lerp_color(mf, (60, 30, 30), 0.5), [(cx - 60, hz), (cx - 10, hz - 52), (cx + 10, hz - 52), (cx + 60, hz)])
                for i in range(5):
                    yy = hz - 56 - i * 9 - (self.t * 8) % 9
                    pygame.draw.circle(canvas, lerp_color((90, 80, 80), pal["sky_top"], i / 6), (int(cx + math.sin(self.t + i) * 4), int(yy)), 6 + i * 2)
            if kind == "tree":   # 세계수: 하늘을 덮는 거대한 나무
                cx = w / 2 + ox
                pygame.draw.rect(canvas, (70, 56, 44), (cx - 26, hz - 110, 52, 110))
                pygame.draw.circle(canvas, (60, 110, 70), (int(cx), int(hz - 120)), 90)
                pygame.draw.circle(canvas, (80, 140, 90), (int(cx - 50), int(hz - 140)), 50)
                pygame.draw.circle(canvas, (80, 140, 90), (int(cx + 56), int(hz - 130)), 46)
            if kind == "islands":
                for i, (fx, fy, fr) in enumerate(((0.2, 60, 26), (0.7, 40, 34), (0.9, 80, 18))):
                    x = fx * w + ox + math.sin(self.t * 0.6 + i) * 3
                    pygame.draw.ellipse(canvas, (110, 150, 100), (x - fr, fy - fr * 0.3, fr * 2, fr * 0.6))
                    pygame.draw.polygon(canvas, (120, 100, 90), [(x - fr, fy), (x + fr, fy), (x, fy + fr * 0.9)])
        elif kind == "land_away":   # 육지가 멀어짐
            k = clamp(1 - self.t / 3.0, 0.15, 1)
            pygame.draw.rect(canvas, mf, (w * 0.1, hz - 10 * k, w * 0.5 * k, 10 * k))
        elif kind == "cave":
            pass

    def _ground(self, canvas, pal, hz, night) -> None:
        w, h = self.w, self.h
        g = self.cfg["ground"]
        side = self.cfg["side"]
        wt, wb = pal["water_top"], pal["water_bottom"]
        cols = {
            "grass": ({"spring": (110, 150, 80), "summer": (70, 130, 60), "autumn": (150, 120, 60), "winter": (225, 230, 236)}[self.season], None),
            "sea": (wt, wb), "deep": (lerp_color(wb, (8, 14, 40), 0.4), (6, 10, 30)), "marsh": (lerp_color(wt, (90, 110, 90), 0.4), None),
            "stone": ((100, 104, 120), None), "clouds": ((235, 238, 245), None), "red_sea": (lerp_color(wt, (170, 60, 40), 0.6), (90, 20, 20)),
            "ice": ((210, 228, 240), None), "moss": ((50, 80, 56), None),
        }
        base, base2 = cols.get(side, ((90, 110, 80), None))
        for y in range(hz, h, 2):
            k = (y - hz) / max(1, h - hz)
            c = lerp_color(base, base2, k) if base2 else lerp_color(lerp_color(base, pal["sky_bottom"], 0.35), base, k)
            canvas.fill(_shade(c, pal, 0.2 * night), (0, y, w, 2))
        # 흘러오는 줄무늬 (바닥이 다가오는 느낌)
        phase = (self.dist * 5) % 1.0
        stripe = {"sea": lerp_color(wt, (240, 245, 250), 0.35), "deep": (30, 50, 90), "red_sea": (230, 120, 80),
                  "marsh": (190, 200, 205), "clouds": (255, 255, 255), "ice": (180, 205, 225), "moss": (90, 140, 90)}.get(side)
        for i in range(14):
            z = Z_NEAR + (i + 1 - phase) * 0.12
            _, y, s = self.proj(0, z)
            if y > h or y < hz:
                continue
            if stripe:
                for j in range(-5, 6):
                    sx, _, _ = self.proj(j * 0.5 + (i % 2) * 0.25, z)
                    canvas.fill(stripe, (int(sx), int(y), max(2, int(10 * s)), 1))
        # 길 (가운데)
        path = {"dirt": (150, 120, 85), "planks": (130, 96, 64), "stone": (130, 134, 150), "bridge": (140, 104, 70),
                "ice": (235, 242, 248), "moss": (90, 76, 58)}.get(g)
        if path:
            half = 0.62 if g != "bridge" else 0.45
            l1, y1, _ = self.proj(-half, Z_FAR)
            r1, _, _ = self.proj(half, Z_FAR)
            l2, y2, _ = self.proj(-half, Z_NEAR)
            r2, _, _ = self.proj(half, Z_NEAR)
            pygame.draw.polygon(canvas, _shade(path, pal, 0.25 * night), [(l1, y1), (r1, y1), (r2, y2), (l2, y2)])
            line = lerp_color(path, (0, 0, 0), 0.25)
            for i in range(16):   # 판자·돌 이음매가 다가옴
                z = Z_NEAR + (i + 1 - (self.dist * 7) % 1.0) * 0.1
                lx, y, _ = self.proj(-half, z)
                rx, _, _ = self.proj(half, z)
                if hz < y < h:
                    canvas.fill(line, (int(lx), int(y), int(rx - lx), 1))
            if g == "ice":   # 발자국
                for i in range(8):
                    z = Z_NEAR + (i + 1 - (self.dist * 3) % 1.0) * 0.2
                    x, y, s = self.proj(-0.12 if i % 2 else 0.12, z)
                    if hz < y < h:
                        pygame.draw.ellipse(canvas, (190, 210, 228), (x - 3 * s * 3, y - s * 2, 6 * s * 3, 4 * s * 2))

    def _obj(self, canvas, pal, o, night) -> None:
        lat, z, kind, seed = o
        x, y, s = self.proj(lat, z)
        if y < H - 40 or s < 0.02:
            return
        sp = self.season
        k_dist = clamp((z - 0.6) / 1.1, 0, 0.75)   # 멀수록 하늘색으로 흐림
        sh = lambda c: _shade(lerp_color(c, pal["sky_bottom"], k_dist), pal, 0.25 * night)  # noqa: E731
        ix, iy = int(x), int(y)
        if kind in ("tree", "pine"):
            leaf, bloom = TREE[sp]
            tw, th = max(1, int(5 * s)), int(34 * s)
            canvas.fill(sh((90, 66, 46)), (ix - tw // 2, iy - th, tw, th))
            if kind == "tree":
                pygame.draw.circle(canvas, sh(leaf), (ix, iy - th), max(2, int(16 * s)))
                if bloom and seed > 0.4:
                    pygame.draw.circle(canvas, sh(bloom), (ix + int(5 * s), iy - th - int(4 * s)), max(1, int(7 * s)))
            else:
                pygame.draw.polygon(canvas, sh(lerp_color(leaf, (30, 70, 40), 0.4) if sp != "winter" else (220, 230, 236)),
                                    [(ix - 14 * s, iy - th * 0.5), (ix, iy - th * 1.6), (ix + 14 * s, iy - th * 0.5)])
        elif kind == "bush":
            pygame.draw.ellipse(canvas, sh(TREE[sp][0]), (ix - 10 * s, iy - 9 * s, 20 * s, 10 * s))
        elif kind in ("fence", "post", "rope_post"):
            pw, ph = max(1, int(3 * s)), int(16 * s)
            canvas.fill(sh((110, 80, 54)), (ix - pw // 2, iy - ph, pw, ph))
            if kind == "rope_post":
                ox, oy, _ = self.proj(lat, z + 0.25)
                pygame.draw.line(canvas, sh((200, 180, 140)), (ix, iy - ph), (ox, oy - ph * 0.6), 1)
        elif kind == "lamp" or kind == "crystal_lamp":
            ph = int(26 * s)
            canvas.fill(sh((70, 60, 50)), (ix, iy - ph, max(1, int(2 * s)), ph))
            col = (255, 200, 120) if kind == "lamp" else (90, 220, 230)
            k = max(0.35, night)
            pygame.draw.circle(canvas, lerp_color((90, 90, 90), col, k), (ix, iy - ph), max(1, int(3 * s)))
            if k > 0.4:
                g = pygame.Surface((int(30 * s) + 2, int(30 * s) + 2))
                pygame.draw.circle(g, tuple(int(v * 0.35 * k) for v in col), (int(15 * s) + 1, int(15 * s) + 1), max(1, int(14 * s)))
                canvas.blit(g, (ix - int(15 * s), iy - ph - int(15 * s)), special_flags=pygame.BLEND_RGB_ADD)
        elif kind == "rock":
            r = 9 * s * (0.7 + seed * 0.6)
            pygame.draw.polygon(canvas, sh((110, 110, 116)), [(ix - r, iy), (ix - r * 0.6, iy - r * 0.9), (ix + r * 0.4, iy - r), (ix + r, iy)])
        elif kind == "tetrapod":
            r = 7 * s
            for a in (0, 2.1, 4.2):
                pygame.draw.line(canvas, sh((160, 160, 165)), (ix, iy - r), (ix + math.cos(a) * r, iy - r + math.sin(a) * r * 0.6 + r * 0.5), max(1, int(3 * s)))
        elif kind == "buoy":
            b = math.sin(self.t * 2 + seed * 6) * 2 * s
            pygame.draw.circle(canvas, sh((230, 70, 60)), (ix, int(iy - 4 * s + b)), max(1, int(4 * s)))
            canvas.fill(sh((240, 240, 240)), (ix - int(4 * s), int(iy - 4 * s + b), int(8 * s), max(1, int(2 * s))))
        elif kind == "wave":
            ln = 18 * s
            pygame.draw.line(canvas, lerp_color(pal["water_top"], (245, 248, 252), 0.6), (ix - ln, iy), (ix + ln, iy - 1), max(1, int(2 * s)))
        elif kind == "gull_wave":
            gy = iy - 60 * s
            pygame.draw.lines(canvas, (240, 240, 245), False, [(ix - 6 * s, gy + 2 * s), (ix, gy), (ix + 6 * s, gy + 2 * s)], 1)
        elif kind == "bubble":
            pygame.draw.circle(canvas, (120, 160, 210), (ix, int(iy - (self.t * 20 + seed * 50) % 30 * s)), max(1, int(2 * s)), 1)
        elif kind == "reed":
            for j in range(4):
                hgt = (28 + 10 * ((seed * 7 + j) % 1)) * s
                sway = math.sin(self.t * 2 + seed * 5 + j) * 3 * s
                bx = ix + (j - 1.5) * 3 * s
                pygame.draw.line(canvas, sh((200, 205, 210)), (bx, iy), (bx + sway, iy - hgt), max(1, int(s)))
        elif kind == "crystal":
            r = 10 * s
            pts = [(ix, iy - r * 2.2), (ix + r * 0.6, iy - r * 0.6), (ix, iy), (ix - r * 0.6, iy - r * 0.6)]
            pygame.draw.polygon(canvas, (140, 230, 240), pts)
            g = pygame.Surface((int(r * 4) + 2, int(r * 4) + 2))
            pygame.draw.circle(g, (30, 90, 100), (int(r * 2) + 1, int(r * 2) + 1), max(1, int(r * 2)))
            canvas.blit(g, (ix - int(r * 2), iy - int(r * 3)), special_flags=pygame.BLEND_RGB_ADD)
        elif kind == "cloud":
            yy = iy + 20 * s
            pygame.draw.ellipse(canvas, (240, 242, 248), (ix - 24 * s, yy - 6 * s, 48 * s, 12 * s))
        elif kind == "steam":
            for j in range(3):
                yy = iy - (j * 14 + (self.t * 18 + seed * 40) % 14) * s
                pygame.draw.circle(canvas, lerp_color((230, 220, 220), pal["sky_bottom"], 0.3 + j * 0.2), (ix + int(math.sin(self.t + j) * 3 * s), int(yy)), max(1, int((6 + j * 3) * s)))
        elif kind == "ice_block":
            r = 10 * s
            pygame.draw.polygon(canvas, (225, 240, 250), [(ix - r, iy), (ix - r * 0.7, iy - r), (ix + r * 0.8, iy - r * 0.8), (ix + r, iy)])
            pygame.draw.line(canvas, (170, 200, 225), (ix - r * 0.7, iy - r), (ix + r * 0.1, iy), 1)
        elif kind == "ice_crack":
            pygame.draw.line(canvas, (150, 185, 215), (ix - 10 * s, iy), (ix + 8 * s, iy + 2 * s), 1)
        elif kind == "glow":
            yy = iy - 10 * s + math.sin(self.t * 2 + seed * 6) * 3 * s
            g = pygame.Surface((int(12 * s) + 2, int(12 * s) + 2))
            pygame.draw.circle(g, (90, 200, 120), (int(6 * s) + 1, int(6 * s) + 1), max(1, int(5 * s)))
            canvas.blit(g, (ix - int(6 * s), int(yy - 6 * s)), special_flags=pygame.BLEND_RGB_ADD)
        elif kind == "root":   # 길 위로 걸친 거대한 뿌리 아치
            lx, ly, _ = self.proj(-1.4, z)
            rx, _, _ = self.proj(1.4, z)
            top = ly - 70 * s
            pygame.draw.arc(canvas, sh((90, 70, 52)), (lx, top, rx - lx, (ly - top) * 2), 0, math.pi, max(2, int(9 * s)))
        elif kind == "arch":
            lx, ly, _ = self.proj(-1.0, z)
            rx, _, _ = self.proj(1.0, z)
            top = ly - 60 * s
            pygame.draw.rect(canvas, sh((120, 124, 150)), (lx - 5 * s, top, 10 * s, ly - top))
            pygame.draw.rect(canvas, sh((120, 124, 150)), (rx - 5 * s, top, 10 * s, ly - top))
            pygame.draw.arc(canvas, sh((120, 124, 150)), (lx, top - 10 * s, rx - lx, 40 * s), 0, math.pi, max(2, int(6 * s)))
        elif kind == "house":
            bw, bh = 30 * s, 22 * s
            canvas.fill(sh((150, 110, 76)), (ix - bw / 2, iy - bh, bw, bh))
            pygame.draw.polygon(canvas, sh((120, 52, 40)), [(ix - bw * 0.6, iy - bh), (ix, iy - bh * 1.7), (ix + bw * 0.6, iy - bh)])
            canvas.fill(lerp_color((60, 70, 90), (255, 210, 120), night), (ix - 4 * s, iy - bh * 0.7, 8 * s, 6 * s))

    def _vehicle(self, canvas, pal, night) -> None:
        w, h = self.w, self.h
        m = self.cfg.get("move")
        bx, by = self._b
        if m == "boat":   # 뱃머리 + 가끔 노
            cx = w / 2 + bx * 2
            pts = [(cx - 70, h), (cx, h - 46 + by), (cx + 70, h)]
            pygame.draw.polygon(canvas, _shade((120, 84, 56), pal, 0.3 * night), pts)
            pygame.draw.lines(canvas, _shade((160, 120, 80), pal, 0.3 * night), False, pts, 2)
            ph = (self.t * 1.1) % 1.0
            if ph < 0.6:   # 노 젓기 (오른쪽 아래)
                a = math.pi * ph / 0.6
                ox, oy = w * 0.78, h - 20
                pygame.draw.line(canvas, (130, 96, 60), (ox, oy), (ox + math.cos(a) * 40, oy - 30 + math.sin(a) * 20), 3)
        elif m == "ship":   # 범선 뱃머리 난간 + 돛대 그림자
            pygame.draw.polygon(canvas, (110, 76, 50), [(w * 0.2, h), (w * 0.5, h - 60 + by), (w * 0.8, h)])
            pygame.draw.line(canvas, (90, 64, 44), (w * 0.5, h - 60 + by), (w * 0.5 + 60, h - 110 + by), 3)   # 뱃머리 기움 돛대
            for i in range(6):
                x = w * 0.2 + i * w * 0.06
                pygame.draw.line(canvas, (140, 104, 70), (x, h - (i * 10) + by * 0.5), (x, h - 14 - (i * 10) + by * 0.5), 2)
        elif m == "bridge":   # 구름다리 밧줄 난간 (양쪽에서 지평선으로)
            for side in (-1, 1):
                x1, y1, _ = self.proj(side * 0.5, Z_FAR, 0.5)
                x2, y2, _ = self.proj(side * 0.5, Z_NEAR, 0.5)
                pygame.draw.line(canvas, (200, 180, 140), (x1, y1), (x2, y2), 2)
