"""화면에 맺히는 날씨 효과 · 바람 (DETAILS.md A-1 · A-2, DESIGN.md 45장 DT2). 수치는 data/details/weather_screen.json.

화면에 맺히는 효과 (렌즈 위, 카메라 연출 뒤에 그림):
  빗방울(맺힘 → 흘러내림 → 1px 자국) · 폭풍 굵은 빗줄기(바람 15~30도) · 안개 김 서림 + 안개 덩어리 · 눈송이 녹음 · 모서리 성에 ·
  해 빛 번짐 · 날리는 꽃잎/낙엽/눈송이 · 입김
수면 위 (월드, 카메라 연출 전에 그림): 구름 그림자 · 윤슬

공통 규칙 (45장 📐): 파이팅 중에는 신호 보호 영역(가운데 40%×50% + 신호 슬롯 2칸 주변 8px)에 닿는 효과는 생기지 않거나 즉시 투명,
나머지는 투명도 60%. 화질 상한 [높음, 중간, 낮음]. 화면 효과 줄이기면 맺히는 효과 개수 절반.
모든 그림은 내부 해상도에서 도트로 (정수배 확대는 PixelScreen). 무거운 모양(빗방울 · 김 서림 · 안개 덩어리 · 성에 · 빛 번짐)은 한 번만 만들어 둔다.
"""
import math
import random

import pygame

from src.core import fxq
from src.core.config import load_json
from src.core.mathutil import clamp, lerp


def cfg() -> dict:
    return load_json("details/weather_screen.json")


def q_index() -> int:
    """화질 단계 → 표의 [높음, 중간, 낮음] 칸 번호."""
    return {2: 0, 1: 1, 0: 2}[fxq.level()]


def q_val(lst):
    return lst[q_index()]


# ───────────────────────── 바람 ─────────────────────────

class Wind:
    """세기 = 날씨 (맑음 0.3 · 비 0.6 · 폭풍 1.0 · 안개 0.1), 방향 = 날씨가 바뀔 때 좌/우 무작위, 2~4초 돌풍 출렁임 ±25%.
    x = 방향 × 세기 × 돌풍 (-1.25~1.25) — 줄 휨 · 빗줄기 각도 · 날림 · 갈대가 이 값 하나를 쓴다."""

    def __init__(self, rnd=None):
        self.rnd = rnd or random.Random()
        self.dir = self.rnd.choice((-1, 1))
        self.weather = None
        self.strength = 0.3
        self.target = 0.3
        self.gust_t = 0.0
        self.gust_len = 3.0
        self.gust = 0.0

    def update(self, dt: float, weather: str) -> None:
        c = cfg()["wind"]
        if weather != self.weather:
            if self.weather is not None:
                self.dir = self.rnd.choice((-1, 1))
            self.weather = weather
            self.target = c["strength"].get(weather, 0.3)
        self.strength += (self.target - self.strength) * min(1.0, dt / 2.0)   # 날씨가 바뀌면 2초에 걸쳐
        self.gust_t += dt
        if self.gust_t >= self.gust_len:
            self.gust_t = 0.0
            self.gust_len = self.rnd.uniform(*c["gust_sec"])
        self.gust = math.sin(math.pi * self.gust_t / self.gust_len) * c["gust_amp"]

    @property
    def x(self) -> float:
        return self.dir * self.strength * (1.0 + self.gust)

    def reed_mult(self, weather: str) -> float:
        """갈대 흔들림 세기 (기존 날씨별 값 그대로 — 바람 방향만 맞춤)."""
        return {"clear": 1.0, "rain": 1.4, "storm": 2.2, "fog": 0.6}.get(weather, 1.0)


# ───────────────────────── 신호 보호 영역 ─────────────────────────

class Protect:
    """파이팅 중 화면 효과가 가리면 안 되는 사각형들 (45-B). 화면 크기 · 슬롯 크기 · 왼손잡이가 바뀔 때만 다시 계산."""

    def __init__(self):
        self.key = None
        self.rects: list[pygame.Rect] = []

    def update(self, w: int, h: int, touch: bool, left: bool) -> list:
        from src.ui import signal_slots
        k = signal_slots.OPTS.get("scale", 1.0)
        key = (w, h, touch, left, k)
        if key != self.key:
            self.key = key
            c = cfg()["common"]
            cw, ch = c["protect_center"]
            rects = [pygame.Rect(round(w * (1 - cw) / 2), round(h * (1 - ch) / 2), round(w * cw), round(h * ch))]
            half = int(signal_slots.cfg()["slots"]["size"] * k) // 2 + c["protect_slot_pad"]
            for x, y in signal_slots.slot_positions(w, h, touch, left):
                rects.append(pygame.Rect(x - half, y - half, half * 2, half * 2))
            self.rects = rects
        return self.rects

    def hit(self, r) -> bool:
        return any(p.colliderect(r) for p in self.rects)

    def hit_pt(self, x: float, y: float, pad: int = 0) -> bool:
        return self.hit(pygame.Rect(int(x) - pad, int(y) - pad, 2 * pad + 1, 2 * pad + 1))

    def draw_debug(self, canvas, t: float) -> None:
        col = (255, 80, 200) if int(t * 4) % 2 else (255, 200, 80)
        for r in self.rects:
            pygame.draw.rect(canvas, col, r, 1)


# ───────────────────────── 미리 만든 모양 ─────────────────────────

_DROP: dict = {}
_SPRITES: dict = {}


GOLD_DROP = {"rim": [255, 220, 120, 220], "body": [255, 236, 190, 96], "center": [255, 255, 255, 220]}


def drop_sprite(size: int, style: str | None = None) -> pygame.Surface:
    """빗방울: 가운데 밝은 점 1px(흰 80%) + 테두리 어두운 1px(검정 25%) + 몸통 반투명 하늘색(#BFE6FF 35%). 아래가 조금 무거운 물방울꼴.
    style 'gold' = 전설 챔질 금빛(#FFDC78) 테두리 물보라 (DT5)."""
    s = _DROP.get((size, style))
    if s is None:
        c = GOLD_DROP if style == "gold" else cfg()["rain_drops"]
        w, h = size, size + 1
        s = pygame.Surface((w, h), pygame.SRCALPHA)
        cx, cy = (w - 1) / 2, h * 0.58
        rx, ry = w / 2, h / 2
        inside = set()
        for y in range(h):
            for x in range(w):
                dy = (y + 0.5 - cy) / (ry * (0.85 if y + 0.5 < cy else 1.0))
                if ((x + 0.5 - w / 2) / rx) ** 2 + dy ** 2 <= 1.0:
                    inside.add((x, y))
        for x, y in inside:
            edge = any((x + dx, y + dy) not in inside for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)))
            s.set_at((x, y), tuple(c["rim"]) if edge else tuple(c["body"]))
        hx, hy = int(cx), max(1, int(cy) - 1)
        if (hx, hy) in inside:
            s.set_at((hx, hy), tuple(c["center"]))
        _DROP[(size, style)] = s
    return s


def _cached(key, make):
    s = _SPRITES.get(key)
    if s is None:
        s = _SPRITES[key] = make()
    return s


def _glare_sprite(radius: int) -> pygame.Surface:
    """빛 번짐: 더하기 합성용 원형 그라데이션 (계단 4단, 도트 느낌)."""
    def make():
        d = radius * 2 + 1
        s = pygame.Surface((d, d))
        for i, (rk, v) in enumerate(((1.0, 18), (0.72, 30), (0.46, 44), (0.24, 60))):
            pygame.draw.circle(s, (v, int(v * 0.92), int(v * 0.7)), (radius, radius), max(1, int(radius * rk)))
        return s
    return _cached(("glare", radius), make)


def _edge_fog(w: int, h: int, px: int, alpha: float) -> pygame.Surface:
    """김 서림: 가장자리 px 픽셀, 흰색 alpha → 0 계단 그라데이션 (한 번만)."""
    def make():
        s = pygame.Surface((w, h), pygame.SRCALPHA)
        for i in range(px):
            a = int(255 * alpha * (1 - i / px) ** 1.5)
            if a <= 0:
                continue
            pygame.draw.rect(s, (255, 255, 255, a), (i, i, w - 2 * i, h - 2 * i), 1)
        return s
    return _cached(("edge", w, h, px, alpha), make)


def _fog_blob(w: int, h: int, seed: int) -> pygame.Surface:
    def make():
        r = random.Random(seed)
        s = pygame.Surface((w, h), pygame.SRCALPHA)
        for _ in range(9):
            ew, eh = r.uniform(0.35, 0.7) * w, r.uniform(0.35, 0.7) * h
            x, y = r.uniform(0, w - ew), r.uniform(0, h - eh)
            pygame.draw.ellipse(s, (226, 232, 238, 16), (x, y, ew, eh))
        return s
    return _cached(("blob", w, h, seed), make)


def _frost_field(n: int = 24):
    """성에 문턱 값: 모서리에서 멀수록 · 결이 거칠수록 늦게 자람 (거리 + 결정 줄기 노이즈)."""
    def make():
        r = random.Random(7)
        rays = [(r.uniform(0.05, 1.5), r.uniform(0.6, 1.0)) for _ in range(7)]
        field = {}
        for y in range(n):
            for x in range(n):
                d = math.hypot(x, y)
                ang = math.atan2(y, x)
                ray = max(k * max(0.0, 1 - abs(ang - a) * 6) for a, k in rays)
                field[(x, y)] = d * (1.0 - 0.45 * ray) + r.uniform(0, 2.2)
        return field
    return _cached(("frost_field", n), make)


def _frost_sprite(size: int) -> pygame.Surface:
    """모서리 하나(왼쪽 위 기준) 성에 — size(px) 까지 자란 모양. 정수 크기마다 한 번만."""
    def make():
        n = 24
        s = pygame.Surface((n, n), pygame.SRCALPHA)
        field = _frost_field(n)
        for (x, y), v in field.items():
            if v < size:
                k = 1 - v / max(1, size)
                a = int(80 + 140 * k)
                bright = (v * 7.3) % 1.0 < 0.3   # 결정 줄기 반짝이는 점 (무늬 줄이 생기지 않게 문턱 값으로)
                col = (255, 255, 255, min(255, a + 30)) if bright else (226, 240, 252, a)
                s.set_at((x, y), col)
        return s
    return _cached(("frost", size), make)


# ───────────────────────── 화면 날씨 ─────────────────────────

class ScreenWeather:
    def __init__(self, w: int, h: int, rnd=None):
        self.w, self.h = w, h
        self.rnd = rnd or random.Random()
        self.drops: list[list] = []      # [x, y, size, stay, vy, age, trail[(x, y, t)]]
        self.streaks: list[list] = []    # [x, y, vx, vy, len]
        self.flakes: list[list] = []     # [x, y, age, size]
        self.flyers: list[list] = []     # [x, y, vx, phase, kind, col]
        self.clouds: list[list] = []     # [x, y, w, h, vx]
        self.glints: list[list] = []     # [x, y, life, age]
        self.puffs: list[list] = []      # [x, y, age]
        self.frost = 0.0                 # 지금 성에 크기 (px)
        self.frost_base = 0.0            # 낚시터 상시 성에 (극광 빙해 8px, DT3)
        self.fog_k = 0.0
        self.fog_off = 0.0
        self.acc = {"drop": 0.0, "streak": 0.0, "flake": 0.0, "flyer": 0.0}
        self.cloud_t = self.rnd.uniform(20, 60)
        self.breath_t = self.rnd.uniform(*cfg()["breath"]["every_sec"])
        self.protect = Protect()
        self.fighting = False
        self.reduce = False
        self.show_protect = False
        self.glare_pos = None
        self.glare_k = 0.0
        self.sun_x = None
        self.ctx: dict = {}

    # ── 갱신 ──
    def update(self, dt: float, ctx: dict) -> None:
        """ctx: weather · season · cont · period · spot · sea · fighting · reduce · wind(Wind) · touch · left · horizon ·
        sun(화면 좌표 | None) · enabled(동굴 · 아주 어두운 곳이면 False)."""
        self.ctx = ctx
        C = cfg()
        w, h = self.w, self.h
        r = self.rnd
        weather, season = ctx["weather"], ctx["season"]
        self.fighting = ctx["fighting"]
        self.reduce = ctx["reduce"]
        self.protect.update(w, h, ctx["touch"], ctx["left"])
        cnt = C["common"]["reduce_fx_count_mult"] if self.reduce else 1.0
        wind = ctx["wind"]
        open_sky = ctx["enabled"]

        def spawn(key, rate, cap, make):
            if cap <= 0:
                self.acc[key] = 0.0
                return
            self.acc[key] += rate * dt
            while self.acc[key] >= 1.0:
                self.acc[key] -= 1.0
                make(cap)

        # 빗방울 (비 · 폭풍)
        rd = C["rain_drops"]
        rate = rd["rate"].get(weather, 0.0) if open_sky else 0.0
        cap = int(q_val(rd["cap"]) * cnt)

        def mk_drop(cap):
            if len(self.drops) >= cap:
                return
            sz = r.randint(*rd["size"])
            x, y = r.uniform(4, w - 4 - sz), r.uniform(4, h * 0.85)
            if self.fighting and self.protect.hit(pygame.Rect(int(x), int(y), sz, sz + 1)):
                return   # 보호 영역에는 생기지 않음
            self.drops.append([x, y, sz, r.uniform(*rd["stay_sec"]), r.uniform(*rd["slide_px_s"]), 0.0, []])
        spawn("drop", rate * cnt, cap, mk_drop)
        keep = []
        for d in self.drops:
            d[5] += dt
            if d[5] > d[3]:
                tx, ty = int(d[0] + d[2] // 2), int(d[1])
                if not d[6] or (d[6][-1][0], d[6][-1][1]) != (tx, ty):
                    d[6].append((tx, ty, d[5]))   # 자국은 픽셀이 바뀔 때만 (같은 칸을 여러 번 칠하지 않게)
                d[1] += d[4] * dt * min(1.0, (d[5] - d[3]) / 0.3)   # 머물다 천천히 흘러내림
            d[6] = [p for p in d[6] if d[5] - p[2] < rd["trail_sec"]]
            if d[1] < h + 2:
                keep.append(d)
        self.drops = keep

        # 폭풍 굵은 빗줄기 (바람 세기 15~30도)
        st = C["storm_streaks"]
        cap = q_val(st["cap"]) if weather == "storm" and open_sky else 0
        a0, a1 = st["angle_deg"]
        ang = math.radians(lerp(a0, a1, clamp(abs(wind.x), 0, 1)))
        sgn = 1 if wind.x >= 0 else -1

        def mk_streak(cap):
            if len(self.streaks) >= cap:
                return
            sp = r.uniform(*st["speed_px_s"])
            self.streaks.append([r.uniform(-60, w + 60), r.uniform(-30, -5), sgn * math.sin(ang) * sp, math.cos(ang) * sp,
                                 r.uniform(*st["length"])])
        spawn("streak", cap * 2.5, cap, mk_streak)
        for s in self.streaks:
            s[0] += s[2] * dt
            s[1] += s[3] * dt
        self.streaks = [s for s in self.streaks if s[1] - s[4] < h and -80 < s[0] < w + 80]

        # 안개 김 서림 · 덩어리
        fc = C["fog_screen"]
        tgt = 1.0 if weather == "fog" and q_val(fc["layers"]) > 0 else 0.0
        self.fog_k += (tgt - self.fog_k) * min(1.0, dt / 2.0)
        self.fog_off += fc["drift_px_s"] * dt * (1 if wind.x >= 0 else -1)

        # 눈 (= 겨울 + 맑음 · 안개, 45-D 확정 1)
        snowing = season == "winter" and weather in ("clear", "fog") and open_sky
        sc = C["snow_screen"]
        cap = int(q_val(sc["cap"]) * cnt) if snowing else 0

        def mk_flake(cap):
            if len(self.flakes) >= cap:
                return
            sz = r.choice((2, 2, 3))
            x, y = r.uniform(4, w - 6), r.uniform(4, h * 0.9)
            if self.fighting and self.protect.hit(pygame.Rect(int(x) - 1, int(y) - 1, sz + 2, sz + 2)):
                return
            self.flakes.append([x, y, 0.0, sz])
        spawn("flake", sc["rate"] * cnt, cap, mk_flake)
        for f in self.flakes:
            f[2] += dt
        self.flakes = [f for f in self.flakes if f[2] < sc["melt_sec"]]

        # 성에: 눈 오는 동안 60초에 걸쳐 18px, 그치면 10초에 걸쳐 사라짐 (낚시터 상시 성에가 있으면 그 아래로는 안 줄어듦)
        fr = C["frost"]
        if q_val(fr["enabled"]):
            if snowing:
                self.frost = min(fr["max_px"], self.frost + fr["max_px"] / fr["grow_sec"] * dt)
            else:
                self.frost = max(self.frost_base, self.frost - fr["max_px"] / fr["fade_sec"] * dt)
            self.frost = max(self.frost, self.frost_base)
        else:
            self.frost = 0.0

        # 날리는 것: 봄 꽃잎 · 가을 낙엽 · 겨울 눈송이 (여름 없음)
        fl = C["flyers"]
        from src.render.season_fx import PARTICLE
        kind, cols = PARTICLE.get((ctx["cont"], season), (None, []))
        if kind == "firefly" or not open_sky:
            kind = None
        cap = q_val(fl["cap"]) if kind else 0

        def mk_flyer(cap):
            if len(self.flyers) >= cap:
                return
            sp = lerp(fl["speed_px_s"][0], fl["speed_px_s"][1], clamp(abs(wind.x), 0, 1)) * r.uniform(0.8, 1.2)
            d = 1 if wind.x >= 0 else -1
            self.flyers.append([-8 if d > 0 else w + 8, r.uniform(10, h * 0.8), d * sp, r.uniform(0, 6.28), kind,
                                cols[r.randrange(len(cols))]])
        spawn("flyer", fl["rate"], cap, mk_flyer)
        for p in self.flyers:
            p[3] += dt * 3.0
            p[0] += p[2] * dt
            p[1] += math.sin(p[3]) * 14 * dt + 6 * dt
        self.flyers = [p for p in self.flyers if -12 < p[0] < w + 12 and p[1] < h + 8]

        # 입김: 겨울 또는 극광 빙해, 4~6초마다 (파이팅 중 없음)
        br = C["breath"]
        cold = season == "winter" or ctx["spot"] in br["spots"]
        if cold and not self.fighting and q_val(br["enabled"]):
            self.breath_t -= dt
            if self.breath_t <= 0:
                self.breath_t = r.uniform(*br["every_sec"])
                self.puffs.append([w * 0.5 + r.uniform(-6, 6), h - 6, 0.0])
        for p in self.puffs:
            p[2] += dt
        self.puffs = [p for p in self.puffs if p[2] < br["life_sec"] and not self.fighting]

        # 해 빛 번짐 (맑음 · 아침 · 저녁 · 해가 화면 안)
        sg = C["sun_glare"]
        k = q_val(sg["strength"]) if weather == "clear" and ctx["period"] in sg["periods"] and open_sky else 0.0
        self.glare_pos = ctx.get("sun")
        if self.glare_pos is None or not (-sg["radius"] < self.glare_pos[0] < w + sg["radius"]) \
                or not (-sg["radius"] < self.glare_pos[1] < h):
            k = 0.0
        self.glare_k += (k - self.glare_k) * min(1.0, dt / 1.5)

        # 구름 그림자 (맑음, 2~3분에 1개)
        cs = C["cloud_shadow"]
        if weather == "clear" and q_val(cs["enabled"]) and open_sky and not ctx.get("cave"):
            self.cloud_t -= dt
            if self.cloud_t <= 0:
                self.cloud_t = r.uniform(*cs["every_sec"])
                cw, ch = r.uniform(*cs["size"][0]), r.uniform(*cs["size"][1])
                d = 1 if wind.x >= 0 else -1
                hz = ctx["horizon"]
                self.clouds.append([-cw if d > 0 else w, r.uniform(hz + 8, hz + (h - hz) * 0.55), cw, ch,
                                    d * r.uniform(*cs["speed_px_s"])])
        for c in self.clouds:
            c[0] += c[4] * dt
        self.clouds = [c for c in self.clouds if -c[2] - 4 < c[0] < w + 4] if weather == "clear" else []

        # 윤슬 (맑은 낮, 해가 비치는 쪽 수면)
        gl = C["glitter"]
        self.sun_x = ctx.get("sun_x")
        n = min(q_val(gl["cap"]), gl["count"][1])
        on = weather == "clear" and ctx["period"] == "day" and self.sun_x is not None and open_sky and not ctx.get("cave")
        if not on:
            self.glints.clear()
        else:
            # 20~40개 사이에서 천천히 오르내림, 화질 상한 40 / 20 / 10
            want = min(n, int(lerp(gl["count"][0], gl["count"][1], 0.5 + 0.5 * math.sin(ctx.get("t", 0.0) * 0.3))))
            hz = ctx["horizon"]
            for g in self.glints:
                g[3] += dt
            self.glints = [g for g in self.glints if g[3] < g[2]]
            while len(self.glints) < want:
                dy = r.uniform(2, gl["depth_px"])
                spread = gl["spread_px"] * (0.3 + dy / gl["depth_px"])
                self.glints.append([self.sun_x + r.uniform(-spread, spread), hz + dy, r.uniform(*gl["blink_sec"]), 0.0])

    def add_drops(self, n: int, region=None, style: str | None = None, protect: bool = False, size=None) -> int:
        """행동 · 낚시터 연출이 화면에 물방울을 맺히게 함 (DT3: 뜰채 · 수면 몸부림 · 방파제 물보라). region = (x0, y0, x1, y1).
        빗방울과 같은 모양 · 흐름 · 자국, 화면 효과 줄이기면 절반, 파이팅 중 보호 영역엔 안 생김. 화면 전체 상한 = 높음 빗방울 상한."""
        rd = cfg()["rain_drops"]
        if self.reduce:
            n = max(1, n // 2)
        x0, y0, x1, y1 = region or (4, 4, self.w - 4, self.h * 0.85)
        made = 0
        for _ in range(n):
            if len(self.drops) >= rd["cap"][0]:
                break
            sz = self.rnd.randint(*(size or rd["size"]))
            x, y = self.rnd.uniform(x0, max(x0, x1 - sz)), self.rnd.uniform(y0, max(y0, y1 - sz))
            if (self.fighting or protect) and self.protect.hit(pygame.Rect(int(x) - 1, int(y) - 7, sz + 2, sz + 9)):
                continue
            self.drops.append([x, y, sz, self.rnd.uniform(*rd["stay_sec"]), self.rnd.uniform(*rd["slide_px_s"]), 0.0, [], style])
            made += 1
        return made

    # ── 그리기 ──
    def _alpha(self) -> float:
        return cfg()["common"]["fight_alpha"] if self.fighting else 1.0

    def draw_water(self, canvas) -> None:
        """수면 위: 구름 그림자 · 윤슬 (카메라 연출 전, 물고기 그림자보다 먼저)."""
        if self.clouds:
            a = int(255 * cfg()["cloud_shadow"]["alpha"] * self._alpha())
            for x, y, cw, ch, _ in self.clouds:
                s = _cached(("cloud", int(cw), int(ch)), lambda: self._ellipse(int(cw), int(ch)))
                s.set_alpha(a)
                canvas.blit(s, (int(x), int(y - ch / 2)))
        for x, y, life, age in self.glints:
            k = math.sin(math.pi * age / life)
            if k < 0.35:
                continue
            col = (255, 255, 236) if k > 0.75 else (230, 236, 220)
            canvas.fill(col, (int(x), int(y), 1, 1))

    @staticmethod
    def _ellipse(w: int, h: int) -> pygame.Surface:
        s = pygame.Surface((w, h), pygame.SRCALPHA)
        pygame.draw.ellipse(s, (0, 0, 0, 255), (0, 0, w, h))
        return s

    def draw_screen(self, canvas) -> None:
        """화면에 맺히는 효과 (카메라 연출 뒤, HUD · 신호 슬롯보다 먼저)."""
        w, h = self.w, self.h
        fa = self._alpha()
        fight = self.fighting
        P = self.protect
        C = cfg()
        # 빛 번짐 (더하기)
        if self.glare_k > 0.02 and self.glare_pos is not None:
            rad = C["sun_glare"]["radius"]
            x, y = int(self.glare_pos[0]), int(self.glare_pos[1])
            if not (fight and P.hit(pygame.Rect(x - rad, y - rad, rad * 2, rad * 2))):
                g = _glare_sprite(rad)
                k = self.glare_k * fa
                if k < 0.99:
                    g = g.copy()
                    g.fill((int(255 * k),) * 3, special_flags=pygame.BLEND_RGB_MULT)
                canvas.blit(g, (x - rad, y - rad), special_flags=pygame.BLEND_RGB_ADD)
        # 안개 덩어리 + 김 서림
        if self.fog_k > 0.02:
            fc = C["fog_screen"]
            layers = q_val(fc["layers"])
            for i in range(layers):
                bw, bh = int(w * 0.75), int(h * 0.42)
                blob = _fog_blob(bw, bh, 31 + i)
                blob.set_alpha(int(255 * self.fog_k * fa))
                span = w + bw
                x = (self.fog_off * (1 + 0.6 * i) + i * span * 0.5) % span - bw
                y = int(h * (0.18 + 0.34 * i))
                if fight and P.hit(pygame.Rect(int(x), y, bw, bh)):
                    continue
                canvas.blit(blob, (int(x), y))
            edge = _edge_fog(w, h, fc["edge_px"], fc["edge_alpha"])
            edge.set_alpha(int(255 * self.fog_k * fa))
            canvas.blit(edge, (0, 0))
        # 성에 (네 모서리)
        if self.frost >= 1.0:
            size = int(self.frost)
            spr = _frost_sprite(size)
            n = spr.get_width()
            for fx, fy in ((False, False), (True, False), (False, True), (True, True)):
                s = _cached(("frost", size, fx, fy), lambda: pygame.transform.flip(spr, fx, fy)) if (fx or fy) else spr
                s.set_alpha(int(255 * fa))
                pos = (w - n if fx else 0, h - n if fy else 0)
                if fight and P.hit(pygame.Rect(pos[0], pos[1], n, n)):
                    continue
                canvas.blit(s, pos)
        # 폭풍 굵은 빗줄기
        if self.streaks:
            col = (206, 216, 236)
            for x, y, vx, vy, ln in self.streaks:
                sp = math.hypot(vx, vy)
                x0, y0 = x - vx / sp * ln, y - vy / sp * ln
                if fight and P.hit(pygame.Rect(int(min(x, x0)), int(min(y, y0)), int(abs(x - x0)) + 2, int(abs(y - y0)) + 2)):
                    continue
                pygame.draw.line(canvas, col, (x0, y0), (x, y), 2 if fa >= 1.0 else 1)
        # 빗방울 (+ 흘러내린 자국)
        for d in self.drops:
            x, y, sz = d[0], d[1], d[2]
            if fight and P.hit(pygame.Rect(int(x), int(y) - 6, sz, sz + 7)):
                continue   # 보호 영역에 닿으면 즉시 투명
            trail = C["rain_drops"]["trail_sec"]
            for tx, ty, tt in d[6]:
                if fight and P.hit_pt(tx, ty):
                    continue   # 흘러내린 자국이 보호 영역까지 이어져 있으면 그 점만 안 그림 (DT12)
                k = (1 - (d[5] - tt) / trail) * fa   # 1px 밝은 자국 0.5초 (도트라 반투명 대신 밝기 2단)
                if k > 0.55:
                    canvas.fill((226, 242, 255), (int(tx), int(ty), 1, 1))
                elif k > 0.2:
                    canvas.fill((176, 204, 228), (int(tx), int(ty), 1, 1))
            spr = drop_sprite(sz, d[7] if len(d) > 7 else None)
            if fa < 1.0:
                spr = spr.copy()
                spr.set_alpha(int(255 * fa))
            pop = min(1.0, d[5] / 0.08)   # 톡 맺힘
            if pop < 1.0:
                small = max(1, int(sz * pop))
                canvas.blit(pygame.transform.scale(spr, (small, small + 1)), (int(x + (sz - small) / 2), int(y)))
            else:
                canvas.blit(spr, (int(x), int(y)))
        # 눈송이 녹음
        if self.flakes:
            melt = C["snow_screen"]["melt_sec"]
            for x, y, age, sz in self.flakes:
                k = 1 - age / melt
                s = max(1, int(round(sz * (0.5 + 0.5 * k))))
                a = int(255 * k * fa)
                if fight and P.hit(pygame.Rect(int(x), int(y), s, s)):
                    continue
                col = (250, 252, 255) if k > 0.5 else (214, 232, 248)
                if a > 150:
                    canvas.fill(col, (int(x), int(y), s, s))
                elif a > 50:
                    canvas.fill(col, (int(x) + s // 2, int(y) + s // 2, 1, 1))
        # 날리는 것
        for x, y, vx, ph, kind, col in self.flyers:
            if fight and P.hit_pt(x, y, 3):
                continue
            ix, iy = int(x), int(y)
            if kind == "petal":
                canvas.fill(col, (ix, iy, 3, 1 + int(abs(math.sin(ph)) * 1.5)))
            elif kind == "leaf":
                a = ph
                pts = [(x + math.cos(a) * 3, y + math.sin(a) * 2), (x - math.cos(a) * 3, y - math.sin(a) * 2),
                       (x + math.sin(a) * 2, y - math.cos(a) * 2)]
                pygame.draw.polygon(canvas, col, pts)
            else:
                canvas.fill(col, (ix, iy, 2, 2))
        # 입김
        if self.puffs:
            life = C["breath"]["life_sec"]
            for x, y, age in self.puffs:
                k = age / life
                rad = 2 + int(7 * k)
                a = int(90 * math.sin(math.pi * min(1.0, k * 1.2)) if k < 0.83 else 90 * (1 - k) * 3)
                if a <= 4:
                    continue
                s = _cached(("puff", rad), lambda: self._puff(rad))
                s.set_alpha(a)
                canvas.blit(s, (int(x - rad), int(y - 8 - k * 26 - rad)))
        if self.show_protect:
            P.draw_debug(canvas, self.ctx.get("t", 0.0))

    @staticmethod
    def _puff(rad: int) -> pygame.Surface:
        s = pygame.Surface((rad * 2 + 4, rad * 2 + 2), pygame.SRCALPHA)
        for dx, dy, rr in ((0, 0, 1.0), (-0.55, 0.25, 0.7), (0.6, 0.3, 0.65)):
            pygame.draw.circle(s, (240, 246, 252, 255), (int(rad + 2 + dx * rad), int(rad + 1 + dy * rad)), max(1, int(rad * rr)))
        return s
