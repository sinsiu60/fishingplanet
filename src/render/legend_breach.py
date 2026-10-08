"""전설 등장 '도약' (LEGEND_BREACH.md LB1, CORE_UPDATE CU10). 수치는 data/legend_breach.json.

이름 카드가 떠 있는 동안 전설이 찌 자리에서 수면을 뚫고 하늘 높이 솟구쳤다(포물선 · 정점 슬로모션) 머리부터 떨어져
착수 순간 금빛 고리 · 흔들림 · 노란 번쩍 → 카드가 체력 바로 → 파이팅. 동안 파이팅은 정지 (fishing_scene 이 update 를 건너뜀).

좌표는 모두 '확대 전' 화면 좌표 (world 를 그린 캔버스). compose() 가 마지막에 그 캔버스를 물고기 쪽으로 확대 · 흔들기 ·
번쩍을 입히고, 이름 카드 · HUD 는 그 뒤에 그려서 확대되지 않음.
"""
import math
import random

import pygame

from src.core.config import load_json
from src.render.fish_draw import draw_fish_side, fish_colors, fish_shape
from src.core.mathutil import clamp, lerp, lerp_color


def cfg() -> dict:
    return load_json("legend_breach.json")


class LegendBreach:
    def __init__(self, fish: dict, bob: tuple[float, float], size: tuple[int, int], reduce: bool,
                 skippable: bool, stage_color: tuple | None = None, impact_at: float | None = None):
        c = cfg()
        self.c = c
        self.fish = fish
        self.g = dict(c["gestures"].get(fish["id"], {}))
        self.W, self.H = size
        self.bx, self.by = bob
        self.reduce = reduce
        self.skippable = skippable
        self.stage = tuple(stage_color) if stage_color else (255, 255, 255)
        self.rnd = random.Random(hash(fish["id"]) & 0xFFFF)
        self.t = 0.0
        self.done = False
        slow = self.g.get("slow", c["slow_until"] - c["apex_at"])
        self.leap_at = c["leap_at"]
        self.apex_at = c["apex_at"]
        self.slow_end = self.apex_at + slow
        fall = c["impact_at"] - c["slow_until"]
        self.impact_at = self.slow_end + fall
        if impact_at is not None:   # 보스 곡 마디 첫 박에 착수 맞춤 (낙하 속도만 조절)
            self.impact_at = clamp(impact_at, self.slow_end + 0.3, self.slow_end + 0.8)
        self.end_at = self.impact_at + (c["end_at"] - c["impact_at"])
        rise = (self.by - self.H * c["apex_y"]) * self.g.get("height", 1.0)
        self.apex_y = max(6.0, self.by - rise)
        self.drift = (self.W / 2 - self.bx) * 0.25
        self.length = self.W * self.g.get("len_frac", c["len_frac"]) / c["zoom_max"]
        self.colors = fish_colors(fish)
        self.shape = fish_shape(fish)
        self.drops: list[list] = []   # [x, y, vx, vy, 남은 초, 금색?]
        self.puffs: list[list] = []   # 김 · 얼음 조각 [x, y, vx, vy, 남은 초, 종류]
        self.fired: set = set()
        self._head = (self.bx, self.by)

    # ───────────────────────── 시계 ─────────────────────────
    @property
    def blocking(self) -> bool:
        return not self.done

    def can_skip(self) -> bool:
        return self.skippable and self.c["skip_after"] <= self.t < self.impact_at - 0.05

    def skip(self) -> None:
        """두 번째부터: 탭 = 착수 순간으로 (번쩍 · 흔들림 · 카드 올라감은 보여 줌)."""
        self.t = self.impact_at - 0.02
        self.drops.clear()
        self.puffs.clear()

    def update(self, dt: float) -> list[tuple]:
        """이벤트 [("sfx", 이름, 음량) | ("reel",) | ("duck", dB, 초) | ("impact",) | ("done",)]."""
        self.t += dt
        ev = []

        def at(key, when):
            if key not in self.fired and self.t >= when:
                self.fired.add(key)
                return True
            return False
        if at("leap", self.leap_at):
            ev += [("sfx", "sfx_jump_out", 1.0), ("sfx", "sfx_splash", 0.8), ("reel",)]
            self._burst(self.bx, self.by, self.c["drops_up"], up=True)
        if at("apex", self.apex_at):
            ev.append(("duck", -8.0, 0.2))
        if at("fall", self.slow_end):
            ev.append(("sfx", "sfx_whip", 0.5))
        if at("impact", self.impact_at):
            ix, iy = self._land_xy()
            self._burst(ix, iy, self.c["drops_impact"], up=True, gold=True)
            ev += [("sfx", "sfx_impact", 1.0), ("sfx", "sfx_splash", 1.0), ("impact",)]
        if at("end", self.end_at):
            self.done = True
            ev.append(("done",))
        self._tick_parts(dt)
        return ev

    # ───────────────────────── 궤적 ─────────────────────────
    def _land_xy(self) -> tuple[float, float]:
        return self.bx, self.by   # 찌 자리로 돌아와 착수 (파이팅이 그 자리에서 시작)

    def flying(self) -> bool:
        return self.leap_at <= self.t < self.impact_at

    def pos(self, t: float | None = None) -> tuple[float, float]:
        """물고기 몸 가운데 (확대 전 화면 좌표)."""
        t = self.t if t is None else t
        if t < self.leap_at:
            return self.bx, self.by
        if t >= self.impact_at:
            return self._land_xy()
        total = self.impact_at - self.leap_at
        x = self.bx + self.drift * math.sin(math.pi * (t - self.leap_at) / total)   # 화면 가운데 쪽으로 나갔다 돌아옴
        if t < self.apex_at:
            u = (t - self.leap_at) / (self.apex_at - self.leap_at)
            y = self.by - (self.by - self.apex_y) * (1 - (1 - u) ** 2)
        elif t < self.slow_end:   # 정점 슬로모션: 거의 멈춘 듯 (연출 시간 × slow_k)
            u = (t - self.apex_at) / (self.slow_end - self.apex_at)
            y = self.apex_y - 3 * math.sin(math.pi * u) * self.c["slow_k"]
        else:
            u = (t - self.slow_end) / (self.impact_at - self.slow_end)
            y = self.apex_y + (self.by - self.apex_y) * u * u
        return x, y

    def head_dir(self) -> float:
        """머리 방향 (화면 각도): 날아가는 방향 + 전설별 몸짓."""
        t = self.t
        st = self.g.get("style")
        if t < self.apex_at:
            a = -math.pi / 2 + (0.0 if st == "bill" else 0.35 * math.copysign(1, self.drift or 1) * ((t - self.leap_at) / (self.apex_at - self.leap_at)))
        elif t < self.slow_end:
            u = (t - self.apex_at) / (self.slow_end - self.apex_at)
            horiz = 0.0 if self.drift >= 0 else math.pi
            a = lerp(-math.pi / 2 + 0.35 * math.copysign(1, self.drift or 1), horiz, min(1.0, u * 1.6)) \
                if st != "bill" else horiz
        else:
            u = (t - self.slow_end) / (self.impact_at - self.slow_end)
            horiz = 0.0 if self.drift >= 0 else math.pi
            a = lerp(horiz, math.pi / 2, min(1.0, u * 1.5))   # 머리부터 떨어짐
        if st == "flip" and self.leap_at <= t < self.slow_end:
            a += math.tau * 1.5 * (t - self.leap_at) / (self.slow_end - self.leap_at)   # 몸을 뒤집으며 한 바퀴 반
        elif st == "head_shake" and t < self.apex_at:
            a += math.sin(t * 34) * 0.18
        elif st not in ("bill", "heavy") and t < self.slow_end:
            a += math.sin((t - self.leap_at) * 6) * 0.26   # 활처럼 휘었다 펴며 회전 30°
        return a

    # ───────────────────────── 입자 ─────────────────────────
    def _burst(self, x: float, y: float, n: int, up: bool, gold: bool = False) -> None:
        if self.reduce:
            n = n // 2
        for _ in range(n):
            ang = -math.pi / 2 + self.rnd.uniform(-0.9, 0.9)
            sp = self.rnd.uniform(60, 190) * (1.15 if gold else 1.0)
            self.drops.append([x + self.rnd.uniform(-self.length * 0.25, self.length * 0.25), y,
                               math.cos(ang) * sp, math.sin(ang) * sp, self.rnd.uniform(0.5, 1.0), gold])

    def _tick_parts(self, dt: float) -> None:
        for d in self.drops:
            d[0] += d[2] * dt
            d[1] += d[3] * dt
            d[3] += 420 * dt
            d[4] -= dt
        self.drops = [d for d in self.drops if d[4] > 0 and d[1] < self.by + 6]
        st = self.g.get("style")
        if self.flying():
            x, y = self.pos()
            if self.rnd.random() < 0.6:   # 몸에서 떨어지는 물방울이 뒤따름
                self.drops.append([x + self.rnd.uniform(-1, 1) * self.length * 0.3, y, self.rnd.uniform(-10, 10), 10, 0.5, False])
            if st == "steam" and self.rnd.random() < 0.5:
                self.puffs.append([x + self.rnd.uniform(-1, 1) * self.length * 0.3, y, self.rnd.uniform(-8, 8), -22, 0.9, "steam"])
            if st == "ice" and self.rnd.random() < 0.45:
                self.puffs.append([x + self.rnd.uniform(-1, 1) * self.length * 0.3, y, self.rnd.uniform(-20, 20), 20, 0.8, "ice"])
        for p in self.puffs:
            p[0] += p[2] * dt
            p[1] += p[3] * dt
            if p[5] == "ice":
                p[3] += 300 * dt
            p[4] -= dt
        self.puffs = [p for p in self.puffs if p[4] > 0]

    # ───────────────────────── 카메라 ─────────────────────────
    def zoom(self) -> float:
        if self.reduce:
            return 1.0
        c, t = self.c, self.t
        z1, z2 = c["zoom_max"], c["zoom_fall"]
        if t < self.leap_at:
            return 1.0
        if t < self.apex_at:
            u = (t - self.leap_at) / (self.apex_at - self.leap_at)
            return lerp(1.0, z1, 1 - (1 - u) ** 2)
        if t < self.slow_end:
            return z1
        if t < self.impact_at:
            return lerp(z1, z2, (t - self.slow_end) / (self.impact_at - self.slow_end))
        u = clamp((t - self.impact_at) / (self.end_at - self.impact_at), 0, 1)
        return lerp(z2, 1.0, 1 - (1 - u) ** 2)

    def shake(self) -> tuple[float, float]:
        if self.reduce or self.t < self.impact_at:
            return 0.0, 0.0
        k = (self.t - self.impact_at) / self.c["shake_sec"]
        if k >= 1:
            return 0.0, 0.0
        amp = self.g.get("shake_px", self.c["shake_px"]) * (1 - k)
        return math.sin(k * 31) * amp * 0.5, math.cos(k * 37) * amp   # 아래 방향 먼저 (cos 0 = +)

    def flash_alpha(self) -> float:
        if self.reduce or self.t < self.impact_at:
            return 0.0
        c = self.c
        hold = c["flash_frames"] / 60.0
        dt = self.t - self.impact_at
        if dt <= hold:
            return c["flash_alpha"]
        return max(0.0, c["flash_alpha"] * (1 - (dt - hold) / c["flash_fade"]))

    def rod_bend(self) -> float:
        """낚싯대: 줄이 하늘로 팽팽 → 최대 휨."""
        if self.leap_at <= self.t < self.impact_at:
            return 34.0
        if self.t < self.leap_at:
            return 34.0 * self.t / self.leap_at
        return 34.0 * max(0.0, 1 - (self.t - self.impact_at) / 0.45)

    # ───────────────────────── 그리기 ─────────────────────────
    def draw_world(self, canvas, line_from: tuple[float, float] | None) -> None:
        """확대 전 캔버스에: 수면 솟음 · 물기둥 · 줄 · 물고기 · 물방울 · 착수 고리."""
        c, t = self.c, self.t
        white = lerp_color((255, 255, 255), self.stage, 0.2)
        if t < self.leap_at:   # 찌 자리 수면이 불룩 — 동그란 물결 2겹이 빠르게
            for i in range(2):
                k = clamp(t / self.leap_at - i * 0.35, 0, 1)
                if k <= 0:
                    continue
                rw = 6 + k * self.length * 0.6
                pygame.draw.ellipse(canvas, lerp_color(white, (90, 120, 150), k * 0.6),
                                    (self.bx - rw, self.by - rw * 0.22, rw * 2, rw * 0.44), 1)
            hump = 4 * math.sin(math.pi * clamp(t / self.leap_at, 0, 1))
            pygame.draw.ellipse(canvas, white, (self.bx - 10, self.by - hump - 2, 20, hump * 2 + 3), 1)
        if self.leap_at <= t < self.leap_at + 0.45:   # 물기둥 (폭 = 물고기 길이 반, 반투명 물줄기)
            u = (t - self.leap_at) / 0.45
            hgt = self.length * 1.1 * math.sin(math.pi * min(1.0, u * 1.4))
            w = int(self.length * 0.5 * (1 - u * 0.5))
            if hgt > 2 and w > 2:
                layer = pygame.Surface((w + 2, int(hgt) + 6), pygame.SRCALPHA)
                for j in range(-3, 4):
                    hj = hgt * (1 - abs(j) / 4.5)
                    xj = w // 2 + int(j * w / 8)
                    pygame.draw.line(layer, (*white, int(190 * (1 - u * 0.6))), (xj, int(hgt) + 4), (xj, int(hgt + 4 - hj)), 2)
                canvas.blit(layer, (int(self.bx - w / 2), int(self.by - hgt - 2)))
        # 줄: 찌 자리에서 전설 입으로 곧게 (하늘로 팽팽)
        if self.flying() and line_from is not None:
            hx, hy = self._mouth()
            pygame.draw.line(canvas, (235, 235, 225), (int(self.bx), int(self.by)), (int(hx), int(hy)), 1)
            pygame.draw.line(canvas, (200, 200, 190), (int(line_from[0]), int(line_from[1])), (int(self.bx), int(self.by)), 1)
        for p in self.puffs:
            k = p[4]
            if p[5] == "steam":
                r = int(3 + (1 - k) * 5)
                pygame.draw.circle(canvas, lerp_color((210, 210, 215), (255, 255, 255), k), (int(p[0]), int(p[1])), r, 1)
            else:
                canvas.fill((200, 235, 255), (int(p[0]), int(p[1]), 2, 2))
        if self.flying():
            self._draw_fish(canvas)
        for d in self.drops:
            col = (255, 220, 120) if d[5] else ((255, 236, 170) if self.apex_at <= t < self.slow_end else white)
            canvas.fill(col, (int(d[0]), int(d[1]), 2 if d[4] > 0.4 else 1, 2 if d[4] > 0.4 else 1))
        if t >= self.impact_at:   # 착수: 금빛 고리 (안쪽부터 ring_gap 간격, ring_sec 동안 화면 폭 ring_w 까지)
            ix, iy = self._land_xy()
            n = self.g.get("rings", c["rings"])
            for i in range(n):
                k = (t - self.impact_at - i * c["ring_gap"]) / c["ring_sec"]
                if not 0 < k < 1:
                    continue
                rw = self.W * c["ring_w"] / 2 * (1 - (1 - k) ** 2)
                col = lerp_color((255, 214, 90), (120, 140, 160), k * 0.8)
                pygame.draw.ellipse(canvas, col, (ix - rw, iy - rw * 0.18, rw * 2, rw * 0.36), 2 if k < 0.5 else 1)
            k = (t - self.impact_at) / 0.45
            if k < 1:   # 금빛 물기둥: 반투명 물줄기 여러 가닥 (가운데가 가장 높음)
                hgt = self.length * 0.9 * math.sin(math.pi * k)
                if hgt > 2:
                    w = int(self.length * 0.36)
                    layer = pygame.Surface((w + 2, int(hgt) + 6), pygame.SRCALPHA)
                    for j in range(-3, 4):
                        hj = hgt * (1 - abs(j) / 4.5) * (0.85 + 0.15 * math.sin(j * 2.1 + t * 20))
                        xj = w // 2 + int(j * w / 8)
                        col = (*lerp_color((255, 228, 140), (255, 255, 255), 0.4 + 0.1 * abs(j)), int(200 * (1 - k * 0.7)))
                        pygame.draw.line(layer, col, (xj, int(hgt) + 4), (xj, int(hgt + 4 - hj)), 2)
                    canvas.blit(layer, (int(ix - w / 2), int(iy - hgt - 2)))

    def _mouth(self) -> tuple[float, float]:
        x, y = self.pos()
        a = self.head_dir()
        return x + math.cos(a) * self.length * 0.48, y + math.sin(a) * self.length * 0.48

    def _draw_fish(self, canvas) -> None:
        x, y = self.pos()
        a = self.head_dir()
        dx, dy = math.cos(a), math.sin(a)
        if dx >= 0:
            facing, ang = 1, math.atan2(dy, dx)
        else:
            facing, ang = -1, math.atan2(-dy, -dx)
        wag = 0.0
        if self.g.get("style") == "tail_s":
            wag = math.sin(self.t * 14) * 0.9   # 꼬리를 크게 치며 · 정점에서 S자
        # 햇빛 받는 쪽 금빛 테두리 1px (정점에서 가장 밝게)
        glow = 1.0 if self.apex_at <= self.t < self.slow_end else 0.55
        edge = lerp_color((120, 100, 60), tuple(self.c["gold_edge"]), glow)
        draw_fish_side(canvas, x - 1, y - 1, self.length, ang, self.colors, facing, silhouette=edge,
                       tail_wag=wag, shape=self.shape)
        draw_fish_side(canvas, x, y, self.length, ang, self.colors, facing, tail_wag=wag, shape=self.shape)

    def compose(self, canvas) -> None:
        """확대 (물고기를 따라감) · 흔들림 · 노란 번쩍 — 이름 카드 · HUD 를 그리기 전에."""
        z = self.zoom()
        sx, sy = self.shake()
        W, H = self.W, self.H
        if z > 1.001 or abs(sx) + abs(sy) > 0.01:
            fx, fy = self.pos() if self.t < self.impact_at else self._land_xy()
            cw, ch = W / z, H / z
            x0 = clamp(fx - cw / 2 - sx / z, 0, W - cw)
            y0 = clamp(fy - ch * 0.55 - sy / z, 0, H - ch)
            src = canvas.subsurface(pygame.Rect(int(x0), int(y0), max(1, int(cw)), max(1, int(ch)))).copy()
            canvas.blit(pygame.transform.scale(src, (W, H)), (0, 0))
        a = self.flash_alpha()
        if a > 0.005:
            ov = pygame.Surface((W, H))
            ov.fill(tuple(self.c["flash"]))
            ov.set_alpha(int(255 * a))
            canvas.blit(ov, (0, 0))
