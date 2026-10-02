"""뜰채 성공 → 획득 컷 사이의 연출 (약 2.1초).

1) 뜰채 스윙 (0~0.5초): 뜰채가 아래에서 올라와 물고기를 퍼 담는다. 닿는 순간 섬광·물보라·히트스톱.
2) 끌어올리기 (0.5~1.25초): 시선이 하늘로 올라가고(화면이 아래로 흐름), 그물 속 물고기가 퍼덕이며 물이 떨어진다.
3) 튀어 오름 (1.25~2.1초): 물고기가 그물에서 빙글 돌며 튀어 오르고, 희귀도 색 빛살 → 정점 반짝 → 하얀 섬광.
그 다음 획득 컷에서 물고기가 위에서 떨어져 두 손에 안긴다 (fish_draw.draw_catch_cut).
"""
import math
import random

import pygame

from src.core.mathutil import clamp, lerp, lerp_color, scale_color, smoothstep
from src.render.chest import draw_chest, draw_glow
from src.render.fish_draw import catch_length, draw_fish_side, fish_colors
from src.ui.fight_fx import big_text

T_HIT = 0.22      # 뜰채가 물고기에 닿음
T_SCOOP = 0.5     # 퍼 담기 끝
T_LIFT = 1.25     # 끌어올리기 끝 → 튀어 오름 시작
HIT_STOP = 0.07   # 닿는 순간 잠깐 멈춤

RARITY_GLOW = {"common": (255, 245, 210), "uncommon": (150, 255, 170), "rare": (140, 200, 255),
               "legend": (255, 210, 90)}
TIER = {"common": 0, "uncommon": 1, "rare": 2, "legend": 3}
# 희귀도가 높을수록: 오르는 시간·정점 머무는 시간·회전 수가 늘어난다
RISE_SEC = (0.45, 0.48, 0.55, 0.7)
APEX_HOLD = (0.22, 0.27, 0.45, 0.95)
SPINS = (1.0, 1.0, 1.5, 2.0)
BANNER = {2: "희귀!", 3: "전설!"}
# 크기 등급 (cm): 작은 건 가볍게 휙, 큰 건 무겁게 버티며 끌어올림
#            (닿음, 퍼 담기 끝, 끌어올리기 끝, 히트스톱, 물보라 수, 뜰채 반지름, 끌어올리는 중 '영차' 횟수)
SIZE_CLASS = (
    (30, "small", (0.16, 0.38, 1.0, 0.04, 10, 38, 0)),
    (100, "mid", (T_HIT, T_SCOOP, T_LIFT, HIT_STOP, 26, 0, 0)),
    (200, "big", (0.26, 0.7, 1.65, 0.1, 44, 70, 1)),
    (99999, "huge", (0.3, 0.85, 2.0, 0.13, 64, 76, 2)),
)


def size_class(size_cm: float) -> tuple[str, tuple]:
    for lim, name, v in SIZE_CLASS:
        if size_cm < lim:
            return name, v
    return SIZE_CLASS[-1][1], SIZE_CLASS[-1][2]


def draw_star(canvas, x: float, y: float, r: float, color) -> None:
    """4방향 반짝 별."""
    x, y, r = int(x), int(y), max(1, int(r))
    pygame.draw.line(canvas, color, (x - r, y), (x + r, y), 1)
    pygame.draw.line(canvas, color, (x, y - r), (x, y + r), 1)
    if r >= 3:
        canvas.fill((255, 255, 255), (x - 1, y - 1, 2, 2))


def _ease_out(k: float) -> float:
    k = clamp(k, 0, 1)
    return 1 - (1 - k) ** 3


class LandingCinematic:
    def __init__(self, fish: dict, size_cm: float, start_x: float, chest: str | None = None, golden: bool = False):
        self.fish = fish
        self.chest = chest  # 보물상자 등급 (물고기가 물고 나온다)
        self.chest_color = None
        if chest:
            from src.save.treasure import grade_info
            self.chest_color = tuple(grade_info(chest)["color"])
        self.colors = fish_colors(fish)
        self.shape = fish.get("shape")
        # 크기에 비례 (획득 컷과 같은 눈금), 튀어 오를 때 화면을 넘지 않게 340px까지
        self.size_cm = size_cm
        self.cls, (self.t_hit, self.t_scoop, self.t_lift, self.hit_stop, self.n_splash, net_r, self.heaves) = \
            size_class(size_cm)
        self.length = min(340.0, catch_length(size_cm))
        self.net_r = net_r or clamp(self.length * 0.58, 46, 90)
        self.t = 0.0
        self.x0 = start_x
        self.y0 = 200.0
        self.drips: list[list[float]] = []
        self.splash: list[list[float]] = []
        self.sparks: list[list[float]] = []
        self.fired: set[str] = set()
        self.hold = 0.0
        self.glow = RARITY_GLOW.get(fish["rarity"], (255, 255, 255))
        self.golden = golden  # 황금 뜰채: 금빛 포획 연출
        if golden:
            self.glow = (255, 214, 90)
        self.tier = TIER.get(fish["rarity"], 0)
        self.t_apex = self.t_lift + RISE_SEC[self.tier] * (1.25 if self.cls in ("big", "huge") else 1.0)
        self.t_flash = self.t_apex + APEX_HOLD[self.tier]
        self.total = self.t_flash + 0.18
        self.trail: list[list[float]] = []
        self.rain = [[random.uniform(0, 480), random.uniform(-270, 0), random.uniform(40, 110), random.uniform(0, 6)]
                     for _ in range(70)] if self.tier >= 3 else []
        self.rings: list[float] = []

    @property
    def done(self) -> bool:
        return self.t >= self.total

    def skip(self) -> None:
        if self.t > 0.3:
            self.t = self.total

    # ───────────────────────── 틱 ─────────────────────────
    def update(self, dt: float) -> list[str]:
        """진행. 이번 틱에 일어난 연출 이벤트(소리용)를 돌려준다."""
        events = []
        if self.hold > 0:
            self.hold -= dt
        else:
            self.t += dt
        keys = [("hit", self.t_hit), ("lift", self.t_scoop), ("launch", self.t_lift), ("apex", self.t_apex),
                ("done", self.total)]
        # 큰 물고기: 끌어올리는 중간에 '영차' (잠깐 처졌다가 다시 들어 올림)
        for i in range(self.heaves):
            keys.append((f"heave{i}", self._heave_at(i)))
        for key, at in keys:
            if self.t >= at and key not in self.fired:
                self.fired.add(key)
                events.append(key)
                if key == "hit":
                    self.hold = self.hit_stop
                    fx, fy = self.fish_pos()
                    for _ in range(self.n_splash):
                        a = random.uniform(math.pi * 1.05, math.pi * 1.95)
                        sp = random.uniform(60, 170)
                        self.splash.append([fx + random.uniform(-30, 30), fy, math.cos(a) * sp, math.sin(a) * sp,
                                            random.uniform(0.4, 0.8)])
                elif key == "apex":
                    fx, fy = self.fish_pos()
                    n = (28, 36, 56, 90)[self.tier]
                    for i in range(n):
                        a = i / n * math.tau
                        sp = random.uniform(60, 140) * (1 + 0.25 * self.tier)
                        self.sparks.append([fx, fy, math.cos(a) * sp, math.sin(a) * sp, random.uniform(0.3, 0.6 + 0.2 * self.tier)])
                    # 희귀 이상: 충격파
                    for i in range(max(0, self.tier - 1) * 2):
                        self.rings.append(-i * 0.1)
        # 물방울: 끌어올리는 동안 그물에서 뚝뚝
        if self.t_hit < self.t < self.t_lift + 0.2:
            nx, ny, r = self.net_pos()
            for _ in range({"small": 1, "mid": 2, "big": 4, "huge": 6}[self.cls]):  # 클수록 물이 쏟아짐
                self.drips.append([nx + random.uniform(-r * 0.5, r * 0.5), ny + r * 0.75, random.uniform(-8, 8),
                                   random.uniform(10, 40), 1.0])
        for d in self.drips:
            d[0] += d[2] * dt
            d[1] += d[3] * dt
            d[3] += 420 * dt
            d[4] -= dt
        self.drips = [d for d in self.drips if d[4] > 0 and d[1] < 280]
        for p in self.splash + self.sparks:
            p[0] += p[2] * dt
            p[1] += p[3] * dt
            p[3] += (380 if p in self.splash else 0) * dt
            p[2] *= 0.96
            p[4] -= dt
        self.splash = [p for p in self.splash if p[4] > 0]
        self.sparks = [p for p in self.sparks if p[4] > 0]
        # 고급 이상: 튀어 오를 때 반짝이 꼬리
        if self.tier >= 1 and self.t_lift < self.t < self.t_flash:
            fx, fy = self.fish_pos()
            for _ in range(self.tier):
                self.trail.append([fx + random.uniform(-14, 14), fy + random.uniform(-8, 8), random.uniform(0.3, 0.6)])
        for p in self.trail:
            p[1] += 12 * dt
            p[2] -= dt
        self.trail = [p for p in self.trail if p[2] > 0]
        self.rings = [r + dt for r in self.rings if r < 0.6]
        # 전설: 화면 전체 금가루
        if self.t > self.t_scoop:
            for d in self.rain:
                d[1] += d[2] * dt
                if d[1] > 275:
                    d[1] = random.uniform(-40, -5)
                    d[0] = random.uniform(0, 480)
        return events

    # ───────────────────────── 위치 계산 ─────────────────────────
    def _heave_at(self, i: int) -> float:
        span = self.t_lift - self.t_scoop
        return self.t_scoop + span * (0.35 + 0.35 * i) if self.heaves == 2 else self.t_scoop + span * 0.45

    def _sag(self) -> float:
        """큰 물고기를 들어 올리는 중 무게로 처짐 (영차 직전 가장 깊고, 영차 순간 확 올라감)."""
        if not self.heaves or not (self.t_scoop < self.t < self.t_lift):
            return 0.0
        out = 0.0
        for i in range(self.heaves):
            d = self.t - self._heave_at(i)
            if -0.35 < d < 0:
                out = max(out, (1 + d / 0.35) * (14 if self.cls == "huge" else 9))
            elif 0 <= d < 0.18:
                out = max(out, -6 * (1 - d / 0.18))
        return out

    def strain(self) -> float:
        """뜰채 손잡이 휨 정도 0~1 (무거운 물고기를 들 때)."""
        if self.cls not in ("big", "huge") or not (self.t_hit < self.t < self.t_lift):
            return 0.0
        base = 0.55 if self.cls == "big" else 0.85
        return base * (0.7 + 0.3 * math.sin(self.t * 9)) + self._sag() * 0.02

    def tilt_offset(self) -> float:
        """시선을 들어 올리는 양 (화면이 아래로 흐르는 픽셀)."""
        if self.t < self.t_scoop:
            return 0.0
        return smoothstep((self.t - self.t_scoop) / (self.t_lift - self.t_scoop + 0.3)) * 150

    def net_pos(self):
        """뜰채 고리 중심과 반지름."""
        r = self.net_r
        t = self.t
        if t < self.t_hit:
            k = _ease_out(t / self.t_hit)
            return lerp(430, self.x0, k), lerp(300, self.y0 + 6, k), r
        if t < self.t_scoop:
            k = (t - self.t_hit) / (self.t_scoop - self.t_hit)
            dip = math.sin(k * math.pi) * 8
            return self.x0, lerp(self.y0 + 6, self.y0 - 20, smoothstep(k)) + dip, r
        if t < self.t_lift:
            k = smoothstep((t - self.t_scoop) / (self.t_lift - self.t_scoop))
            wob = math.sin(t * 13) * 2.5 * self.strain()  # 무거우면 부들부들
            return lerp(self.x0, 240, k) + wob, lerp(self.y0 - 20, 128, k) + self._sag(), r
        # 튀어 오르면 뜰채는 아래로 빠짐
        k = (t - self.t_lift) / (self.total - self.t_lift)
        return 240, 128 + 260 * k * k, r

    def fish_pos(self):
        t = self.t
        if t < self.t_hit:
            return self.x0, self.y0
        if t < self.t_lift:
            nx, ny, r = self.net_pos()
            if self.cls == "small":
                return nx + math.sin(t * 17) * r * 0.25, ny + r * 0.32 - abs(math.sin(t * 11)) * r * 0.45  # 그물 안에서 팔딱
            return nx, ny + r * 0.32
        k = clamp((t - self.t_lift) / (self.t_apex - self.t_lift), 0, 1)
        start_y = 128 + self.length * 0.58 * 0.32
        y = lerp(start_y, 78, _ease_out(k))
        if t > self.t_apex:
            y += math.sin((t - self.t_apex) * 6) * 2
        return 240, y

    # ───────────────────────── 그리기 ─────────────────────────
    def draw(self, canvas: pygame.Surface, pal: dict) -> None:
        w, h = canvas.get_size()
        t = self.t
        # 1) 시선 들어올리기: 아래로 흐르고 위는 하늘로 채움
        off = int(self.tilt_offset())
        if off > 0:
            canvas.scroll(0, off)
            top = scale_color(pal["sky_top"], 0.9)
            for y in range(0, off, 3):
                canvas.fill(lerp_color(top, pal["sky_top"], y / max(1, off)), (0, y, w, 3))
        water_line = int(self.y0 + self.length * 0.1) + off
        if t < self.t_scoop + 0.1:
            # 물고기가 잠긴 수면 (뜰채 단계와 같은 화면)
            water = lerp_color(pal["water_top"], pal["water_bottom"], 0.85)
            canvas.fill(water, (0, water_line, w, h - water_line))
            for i in range(6):
                yy = water_line + 3 + i * 6
                canvas.fill(pal["wave_light"], (int((t * 30 + i * 50) % 80) + i * 60, yy, 22, 1))

        tier = self.tier
        # 1-1) 전설: 끌어올리는 동안 하늘이 어두워지고 물에서 금빛 기둥이 솟음
        if tier >= 3 and t > self.t_scoop:
            dk = clamp((t - self.t_scoop) / 0.5, 0, 1) * (1 - clamp((t - self.t_flash) / 0.2, 0, 1))
            dim = pygame.Surface((w, h))
            dim.fill((10, 6, 20))
            dim.set_alpha(int(150 * dk))
            canvas.blit(dim, (0, 0))
            nx0 = self.net_pos()[0]
            pk = clamp((t - self.t_scoop) / 0.6, 0, 1)
            pw = int(lerp(4, 70, pk) + math.sin(t * 20) * 3)
            pillar = pygame.Surface((pw * 2, h), pygame.SRCALPHA)
            for i in range(pw):
                a = int(150 * (1 - i / pw) * dk)
                pygame.draw.line(pillar, (255, 220, 120, a), (pw - i, 0), (pw - i, h))
                pygame.draw.line(pillar, (255, 220, 120, a), (pw + i, 0), (pw + i, h))
            canvas.blit(pillar, (nx0 - pw, 0))

        # 2) 튀어 오를 때 뒤로 퍼지는 빛살 (희귀 이상은 반대로 도는 빛살 한 겹 더)
        if t > self.t_lift:
            k = clamp((t - self.t_lift) / 0.35, 0, 1)
            fx, fy = self.fish_pos()
            sky = pal["sky_top"] if tier < 3 else (30, 20, 40)
            layers = [(14, 0.8, 0.55, 0.3)]
            if tier >= 2:
                layers.append((10, -1.3, 0.75, 0.45))
            for n, speed, strong, weak in layers:
                for i in range(n):
                    a = t * speed + i * math.tau / n
                    ln = (320 + 60 * tier) * k
                    col = lerp_color(sky, self.glow, strong if i % 2 else weak)
                    pygame.draw.polygon(canvas, col, [(fx, fy), (fx + math.cos(a) * ln, fy + math.sin(a) * ln),
                                                      (fx + math.cos(a + 0.13) * ln, fy + math.sin(a + 0.13) * ln)])
            pygame.draw.circle(canvas, lerp_color(sky, self.glow, 0.7), (int(fx), int(fy)), int((30 + 8 * tier) * k + 6))
            # 희귀 이상: 주변에 별 반짝임
            if tier >= 2:
                for i in range(6 + tier * 4):
                    a = i * 2.39 + t * 0.6
                    rr = 50 + (i * 17) % 60
                    tw = 0.5 + 0.5 * math.sin(t * 9 + i * 1.7)
                    draw_star(canvas, fx + math.cos(a) * rr, fy + math.sin(a) * rr * 0.7, 1 + tw * (2 + tier),
                              lerp_color(self.glow, (255, 255, 255), tw))

        # 3) 물고기 + 뜰채
        nx, ny, r = self.net_pos()
        fx, fy = self.fish_pos()
        in_net = self.t_hit <= t < self.t_lift
        flap = math.sin(t * 34)
        if t < self.t_hit:
            # 아직 물속에서 몸부림
            draw_fish_side(canvas, fx, fy, self.length, flap * 0.08, self.colors, -1, tail_wag=flap, shape=self.shape)
            water = lerp_color(pal["water_top"], pal["water_bottom"], 0.85)
            canvas.fill(water, (0, water_line, w, h - water_line))
            self._draw_net(canvas, pal, nx, ny, r, in_net=False, fish=None)
        elif in_net:
            self._draw_net(canvas, pal, nx, ny, r, in_net=True, fish=(fx, fy, flap))
        else:
            # 그물에서 튀어 올라 빙글
            k = clamp((t - self.t_lift) / (self.t_apex - self.t_lift), 0, 1)
            spin = _ease_out(k) * math.tau * SPINS[tier]
            grow = 0.0 if self.cls in ("big", "huge") else 0.2 + 0.05 * tier
            scale = lerp(1.0, 1.0 + grow, _ease_out(k))
            self._draw_net(canvas, pal, nx, ny, r, in_net=False, fish=None)
            draw_fish_side(canvas, fx, fy, self.length * scale, spin, self.colors, -1,
                           tail_wag=math.sin(t * 20) * (1 - k * 0.7), shape=self.shape)
            if self.chest_color:
                # 입에 문 보물상자: 머리(왼쪽 끝) 쪽에 매달려 함께 돈다. 등급 색으로 빛남
                L = self.length * scale
                mx = fx - math.cos(spin) * L * 0.5
                my = fy - math.sin(spin) * L * 0.5
                draw_glow(canvas, mx, my + 7, 26 + 4 * math.sin(t * 8), self.chest_color, 1.4)
                draw_chest(canvas, mx, my + 14, 1.4, self.chest_color, 0.0, 0.0, t)

        # 4) 입자
        drip_col = lerp_color(pal["wave_light"], (255, 255, 255), 0.4)
        for x, y, _, _, _ in self.drips:
            canvas.fill(drip_col, (int(x), int(y), 1, 2))
        for x, y, _, _, life in self.splash:
            s = 2 if life > 0.3 else 1
            canvas.fill(drip_col, (int(x), int(y), s, s))
        for x, y, _, _, life in self.sparks:
            canvas.fill((255, 255, 255) if life > 0.25 else self.glow, (int(x), int(y), 2, 2))
        for x, y, life in self.trail:
            if life > 0.35:
                draw_star(canvas, x, y, 2, (255, 255, 255))
            else:
                canvas.fill(self.glow, (int(x), int(y), 2, 2))
        for x, y, _, ph in self.rain:
            tw = 0.5 + 0.5 * math.sin(t * 8 + ph)
            canvas.fill(lerp_color((200, 150, 40), (255, 240, 170), tw), (int(x), int(y), 2, 2 if tw > 0.5 else 1))
        if self.rings:
            fx, fy = self.fish_pos()
            for age in self.rings:
                if age < 0:
                    continue
                kk = age / 0.6
                pygame.draw.circle(canvas, lerp_color(self.glow, (255, 255, 255), 1 - kk), (int(fx), int(fy)),
                                   int(10 + kk * 160), max(1, int(3 * (1 - kk))))
        # 희귀 이상: 정점에서 배너
        if tier >= 2 and t > self.t_apex:
            bk = t - self.t_apex
            pop = 1.0 + 0.8 * math.exp(-bk * 12) * math.cos(bk * 25)
            big_text(canvas, BANNER[tier], (w // 2, 214), self.glow, (2.2 if tier == 2 else 3.4) * max(0.5, pop),
                     outline=True)

        # 5) 섬광: 닿는 순간 짧게, 마지막엔 하얗게 덮음
        flash = 0.0
        if self.t_hit <= t < self.t_hit + 0.12:
            flash = 0.55 * (1 - (t - self.t_hit) / 0.12)
        if t > self.t_flash - 0.22:
            flash = max(flash, clamp((t - (self.t_flash - 0.22)) / 0.22, 0, 1))
        if flash > 0.01:
            fl = pygame.Surface((w, h))
            fl.fill((255, 245, 200) if tier >= 3 or self.golden else (255, 255, 250))
            fl.set_alpha(int(255 * flash))
            canvas.blit(fl, (0, 0))

    def _draw_net(self, canvas, pal, x, y, r, in_net: bool, fish) -> None:
        frame = pal.get("net_frame") or (190, 196, 205)   # 장착 뜰채 티어 외형
        frame_dark = scale_color(frame, 0.6)
        mesh = pal.get("net_mesh") or (225, 228, 235)
        handle = pal.get("net_handle") or frame
        hw, hh = r, r * 0.28
        # 손잡이 + 두 손
        handle_end = (x + max(r, 46) * 1.9, y + max(r, 46) * 1.9)
        st = self.strain()
        if st > 0.01:
            # 무거우면 손잡이가 휜다 (가운데가 아래로)
            mid = ((x + hw + handle_end[0]) / 2 - 6 * st, (y + handle_end[1]) / 2 + 16 * st)
            pts = [(x + hw, y)] + [((1 - u) ** 2 * (x + hw) + 2 * (1 - u) * u * mid[0] + u * u * handle_end[0],
                                    (1 - u) ** 2 * y + 2 * (1 - u) * u * mid[1] + u * u * handle_end[1])
                                   for u in (0.25, 0.5, 0.75, 1.0)]
            pygame.draw.lines(canvas, scale_color(handle, 0.6), False, pts, 4)
            pygame.draw.lines(canvas, handle, False, [(px, py - 1) for px, py in pts], 2)
        else:
            pygame.draw.line(canvas, scale_color(handle, 0.6), (x + hw, y), handle_end, 4)
            pygame.draw.line(canvas, handle, (x + hw, y - 1), handle_end, 2)
        skin, shadow = pal["hand"], pal["hand_shadow"]
        if skin[0] < 90:
            skin, shadow = (225, 175, 140), (180, 125, 100)
        for k in (0.45, 0.8):
            hx = lerp(x + hw, handle_end[0], k)
            hy = lerp(y, handle_end[1], k)
            pygame.draw.ellipse(canvas, shadow, (hx - 9, hy - 5, 18, 13))
            pygame.draw.ellipse(canvas, skin, (hx - 9, hy - 7, 18, 11))
        # 그물 주머니 (뒤쪽 테두리 → 물고기 → 앞쪽 그물코)
        depth = r * 0.95
        bag = [(x - hw, y), (x - hw * 0.7, y + depth * 0.7), (x, y + depth), (x + hw * 0.7, y + depth * 0.7), (x + hw, y)]
        bag_col = lerp_color(pal["water_bottom"], mesh, 0.25)
        pygame.draw.polygon(canvas, bag_col, bag)
        pygame.draw.ellipse(canvas, frame_dark, (x - hw, y - hh, hw * 2, hh * 2), 2)
        if fish is not None:
            fx, fy, flap = fish
            draw_fish_side(canvas, fx, fy, self.length * 0.9, flap * 0.12, self.colors, -1, tail_wag=flap,
                           shape=self.shape)
        # 그물코
        for i in range(1, 8):
            u = i / 8
            top = (x - hw + u * hw * 2, y + hh * 0.2)
            pygame.draw.line(canvas, mesh, top, (x + (u - 0.5) * hw * 0.5, y + depth * 0.95), 1)
        for j in range(1, 4):
            v = j / 4
            yy = y + depth * v * 0.8
            half = hw * (1 - v * 0.55)
            pygame.draw.line(canvas, mesh, (x - half, yy), (x + half, yy), 1)
        # 앞쪽 테두리 (+ 고티어: 장식 테·빛)
        if pal.get("net_glow"):
            pygame.draw.arc(canvas, lerp_color(frame, pal["net_glow"], 0.5), (x - hw - 2, y - hh - 2, hw * 2 + 4, hh * 2 + 4),
                            math.pi, math.tau, 2)
        pygame.draw.arc(canvas, frame, (x - hw, y - hh, hw * 2, hh * 2), math.pi, math.tau, 3)
        if pal.get("net_trim"):
            pygame.draw.arc(canvas, pal["net_trim"], (x - hw, y - hh + 1, hw * 2, hh * 2), math.pi, math.tau, 1)
