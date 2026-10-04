"""전설 포획 연출 (DESIGN.md 34장, LEGEND_CATCH_SHOW.md): 전설은 '정복', 환상은 '꿈같은 발견'.

LandingCinematic 대신 전설만. 환상 연출(phantom_show)과 같은 방식 — 실제 시간(+ 오디오 지연 보정) 시계가
data/legend_catch_timeline.json 의 마커(= 전설의 노래 음악 마커)에 맞춰 단계를 실행하고, 빛은 더하기 층에 모아 글로우.
환상 전용 표현(정적·멈춘 물방울·오로라·한 글자씩 이름·보라 인장)은 쓰지 않는다.

층 (11): 짧은 슬로모션 · 물보라 폭발(금빛 반사) · 카메라 묵직한 흔들림 1회 · 금빛 비늘 하이라이트(한 방향) ·
       금빛 햇살 빛줄기(굵고 곧게) · 금빛 충격파 고리 1개 · 금가루 · 고유 이펙트(12종) · 글로우(환상보다 은은) · 카드 쾅 · 금 인장
버전: full(그 종 첫 포획 5초) / short(재포획 2.5초) / final(대륙 최종 보스 첫 포획 → 닫으면 엔딩).
"""
import math
import random
import time

import pygame

from src.core.config import load_json
from src.core.fonts import get_font
from src.core.mathutil import clamp, lerp, lerp_color, smoothstep
from src.render.fish_draw import draw_fish_side, fish_colors, fish_shape
from src.render.phantom_show import _add_circle, _env

GOLD = (255, 205, 90)
GOLD_LIGHT = (255, 236, 170)
GOLD_DEEP = (190, 130, 40)
WHITE = (255, 255, 255)


def tl() -> dict:
    return load_json("legend_catch_timeline.json")


def pick_variant(fish: dict, news: dict, save=None) -> str:
    """최종 보스이고 엔딩을 아직 안 봤으면 final, 그 종 첫 포획이면 full, 아니면 short."""
    c = tl()
    if fish["id"] in c["final_fish"] and save is not None:
        seen = save.data.get("ending_seen") if fish["id"] == "dragon_carp" else save.data["flags"].get("final_ending_seen")
        if not seen:
            return "final"
    return "full" if (news or {}).get("new") else "short"


class LegendShow:
    kind = "legend"

    def __init__(self, fish: dict, result: dict, news: dict, variant: str, w: int, h: int, *,
                 mobile: bool = False, reduce: bool = False, delay: float = 0.0, rnd: random.Random | None = None,
                 low: bool = False, intro=None):
        """intro: 뜰채로 끌어올린 LandingCinematic (게임에서) — 그물에서 튀어 오르는 순간이 이 연출의 0초('쾅'),
        뜰채는 그 자리에서 아래로 빠진다. 없으면(테스트 룸) 수면에서 바로 솟는다."""
        self.fish, self.result, self.news = fish, result, news or {}
        self.variant = variant
        self.intro = intro
        c = tl()
        self.v = c["variants"][variant]
        self.m = self.v["markers"]
        self.fx = c["fx"]
        self.uq = dict(c["unique"].get(fish["id"], {"kind": "gold_rain", "color": [255, 214, 110], "n": 40}))
        self.w, self.h = w, h
        self.mobile, self.reduce = mobile, reduce
        self.cap = c["caps"]["mobile" if mobile else "pc"] // (2 if reduce else 1)
        self.low = False
        self.draw_ms = 0.0
        if low:
            self._lower()
        self.delay = delay
        self.clock = 0.0
        self.t = -delay
        self.rnd = rnd or random.Random()
        self.colors = fish_colors(fish)
        self.shape = fish_shape(fish)
        self.length = clamp(w * 0.30, 110, 160)   # 환상(120~170)보다 한 단계 작게
        self.fired: set = set()
        self.events: list[str] = []
        # 입자: [x, y, vx, vy, life, max_life, kind, size]
        self.splash: list[list] = []
        self.dust: list[list] = []
        self.uniq: list[list] = []
        self.icons_landed = 0
        self.skipped = False
        self.sx = 0.0
        self.water_y = int(h * 0.62)
        self.y_start = int(h * 0.52) if intro is not None else self.water_y + 8   # 그물 자리 / 수면
        self.shake = 0.0
        self.final = variant == "final"
        self._fish_pose = None
        self._bolt = None

    def _lower(self) -> None:
        if not self.low:
            self.low = True
            self.cap //= 2

    # ── 시간 ──
    @property
    def speed(self) -> float:
        """짧은 슬로모션 (0.5배속 0.6초 → 0.3초에 걸쳐 풀림). 화면 효과 줄이기: 0.25초만."""
        a, b, s = self.v["slow"]
        if self.reduce:
            b = min(b, 0.25)
        if self.t < b:
            return s
        return lerp(s, 1.0, smoothstep((self.t - b) / 0.3))

    def can_skip(self) -> bool:
        return self.t >= self.v["skip_after"] and self.t < self.m["wait"]

    def waiting(self) -> bool:
        return self.t >= self.m["wait"]

    def skip(self) -> None:
        self.t = self.m["wait"]
        self.skipped = True
        self.events.append("skip")
        self.splash.clear()

    def update(self, dt: float) -> list[str]:
        self.clock += dt
        self.t += dt
        sp = self.speed
        self.sx += dt * sp
        m = self.m
        for name in ("hit", "rise", "scales", "climax", "card", "record", "rewards", "afterglow", "wait"):
            if name in m and self.t >= m[name] and name not in self.fired:
                self.fired.add(name)
                if not self.skipped or name == "wait":
                    self.events.append(name)
                    self._on(name)
        n_icons = len(self.reward_icons())
        if self.t >= m["rewards"]:
            k = min(n_icons, int((self.t - m["rewards"]) / 0.22) + 1)
            while self.icons_landed < k:
                self.events.append(f"icon:{self.icons_landed}")
                self.icons_landed += 1
        self.shake = max(0.0, self.shake - dt / self.fx["shake_sec"])
        self._update_particles(dt, sp)
        out, self.events = self.events, []
        return out

    def _budget(self) -> int:
        return self.cap - len(self.splash) - len(self.dust) - len(self.uniq)

    def _on(self, name: str) -> None:
        r = self.rnd
        half = 2 if self.reduce else 1
        if name == "hit":
            # 쾅: 물보라 폭발 (힘차게 위로 터지고 떨어짐) + 묵직한 흔들림 1회
            cx = self.w / 2
            n = min(self._budget(), self.fx["splash"] // half)
            net = self.intro is not None
            for _ in range(max(0, n)):
                a = r.uniform(-math.pi * 0.92, -math.pi * 0.08)
                spd = r.uniform(90, 300)
                # 그물에서: 물이 사방으로 쏟아짐 / 수면에서: 위로 폭발
                y0 = self.y_start + (r.uniform(0, 18) if net else 0)
                self.splash.append([cx + r.uniform(-60, 60), y0, math.cos(a) * spd * 0.9, math.sin(a) * spd,
                                    r.uniform(0.9, 1.6), 1.6, "drop", r.uniform(1, 3)])
            if not self.reduce:
                self.shake = 1.0
            self._spawn_unique("hit")
        elif name == "rise":
            self._spawn_unique("rise")
        elif name == "climax":
            fx, fy = self.fish_pos()
            n = min(self._budget(), self.fx["dust_burst"] // half)
            for _ in range(max(0, n)):
                a = r.uniform(-math.pi, 0) if r.random() < 0.75 else r.uniform(0, math.pi)
                spd = r.uniform(60, 260)
                self.dust.append([fx, fy, math.cos(a) * spd, math.sin(a) * spd * 0.8, r.uniform(1.4, 3.0), 3.0, "gold",
                                  r.uniform(1, 2.6)])
            self._spawn_unique("climax")

    # ── 입자 ──
    def _update_particles(self, dt: float, sp: float) -> None:
        r = self.rnd
        for p in self.splash:
            p[0] += p[2] * dt * sp
            p[1] += p[3] * dt * sp
            p[3] += 520 * dt * sp
            p[4] -= dt * sp
        self.splash = [p for p in self.splash if p[4] > 0 and p[1] < max(self.water_y + 12, self.y_start + 60)]
        for p in self.dust:   # 금가루: 터졌다가 천천히 내려옴
            p[0] += p[2] * dt * sp
            p[1] += p[3] * dt * sp
            p[2] *= 1 - 1.6 * dt
            p[3] = p[3] * (1 - 1.6 * dt) + 22 * dt
            p[4] -= dt
        self.dust = [p for p in self.dust if p[4] > 0]
        m = self.m
        if self.t > m["climax"] and self._budget() > 0:
            rate = self.fx["dust_rate"] * (0.5 if self.reduce else 1.0) * (0.6 if self.t > m["afterglow"] else 1.0)
            if r.random() < rate * dt:
                self.dust.append([r.uniform(0, self.w), r.uniform(-10, self.h * 0.3), r.uniform(-5, 5),
                                  r.uniform(8, 20), r.uniform(2.5, 4.0), 4.0, "fall", r.uniform(1, 2)])
        self._update_unique(dt, sp)

    # ── 위치 ──
    def fish_pos(self) -> tuple[float, float]:
        m = self.m
        u = clamp((self.t - m["hit"]) / max(0.3, m["scales"] - m["hit"] + 0.2), 0, 1)
        k = 1 - (1 - u) ** 3 + 0.06 * math.sin(math.pi * u)  # 힘차게 올라 살짝 넘쳤다 자리 잡음
        y = lerp(self.y_start, self.h * 0.40, k)
        if self.t > m["card"] - 0.3:
            y = lerp(y, self.h * 0.30, smoothstep((self.t - (m["card"] - 0.3)) / 0.5))
        bob = math.sin(self.clock * 1.4) * 2 * u
        return self.w / 2, y + bob

    def fish_scale(self) -> float:
        k = smoothstep(clamp((self.t - (self.m["card"] - 0.3)) / 0.5, 0, 1))
        return lerp(1.0, 0.72, k)

    # ── 그리기 ──
    def draw(self, canvas: pygame.Surface, pal: dict) -> None:
        t0 = time.perf_counter()
        self._draw(canvas, pal)
        ms = (time.perf_counter() - t0) * 1000
        self.draw_ms = ms if self.draw_ms == 0 else self.draw_ms * 0.9 + ms * 0.1
        if self.mobile and self.draw_ms > 22 and self.t > 0.5:
            self._lower()

    def _draw_net(self, stage, pal) -> None:
        """뜰채: 물고기가 튀어 오른 자리에서 아래로 빠짐 (LandingCinematic 의 뜰채 그림 그대로)."""
        if self.intro is None or not pal:
            return
        u = self.t / 0.8
        if u >= 1:
            return
        y = self.y_start + 14 + 420 * max(0.0, u) ** 2
        try:
            self.intro._draw_net(stage, pal, self.w / 2, y, self.intro.net_r, False, None)
        except (KeyError, AttributeError):
            pass

    def _draw(self, canvas: pygame.Surface, pal: dict | None = None) -> None:
        w, h = canvas.get_size()
        m, t = self.m, self.t
        stage = canvas.copy()
        if getattr(self, "_lum_t", -9.0) + 0.5 <= self.clock:   # 배경 밝기 (0.5초마다): 밝은 낮엔 빛줄기를 덜 더함 (하얗게 바래지 않게)
            r_, g_, b_ = pygame.transform.average_color(pygame.transform.scale(canvas, (32, 18)))[:3]
            self._lum = 0.299 * r_ + 0.587 * g_ + 0.114 * b_
            self._lum_t = self.clock
        self.ray_gain = clamp(1.3 - self._lum / 170, 0.45, 1.0)
        light = pygame.Surface((w, h))
        light.fill((0, 0, 0))
        fx, fy = self.fish_pos()
        # 금빛 색조 (따뜻하게, 절정 근처에서 조금 더)
        warm = 0.10 + 0.08 * _env(t, m["scales"], m["climax"], m["card"], m["afterglow"])
        tint = pygame.Surface((w, h))
        tint.fill(tuple(int(v * warm) for v in (255, 170, 40)))
        stage.blit(tint, (0, 0), special_flags=pygame.BLEND_RGB_ADD)
        if self.intro is not None and t < 0.5:
            # 뜰채 단계에서 어두워졌던 하늘·금빛 기둥이 0.5초에 걸쳐 걷힘 (화면 전환이 튀지 않게)
            dk = 1 - smoothstep(clamp(t / 0.5, 0, 1))
            dim = pygame.Surface((w, h))
            dim.fill((10, 6, 20))
            dim.set_alpha(int(150 * dk))
            stage.blit(dim, (0, 0))
            for i in range(70):
                c = tuple(int(v * dk * 0.3 * (1 - i / 70)) for v in (255, 220, 120))
                pygame.draw.line(light, c, (w / 2 - i, 0), (w / 2 - i, h))
                pygame.draw.line(light, c, (w / 2 + i, 0), (w / 2 + i, h))
        self._draw_unique_back(stage, light)
        self._draw_rays(light, fx, fy, _env(t, m["scales"] - 0.2, m["climax"], m["afterglow"], m["wait"] + 0.8))
        self._draw_splash(stage, light, back=True)
        self._draw_net(stage, pal)
        self._draw_fish(stage, fx, fy)
        self._draw_splash(stage, light, back=False)
        self._draw_unique_front(stage, light)
        self._draw_dust(light)
        self._draw_shock(light, fx, fy)
        self._fish_light(light)
        stage.blit(light, (0, 0), special_flags=pygame.BLEND_RGB_ADD)
        self._glow(stage, light)
        # 카메라: 쾅 순간 묵직한 흔들림 1회 + 절정까지 아주 조금 다가감
        ox = oy = 0
        if self.shake > 0 and not self.reduce:
            a = self.fx["shake_px"] * self.shake ** 1.5
            ox = int(math.sin(self.clock * 61) * a)
            oy = int(math.cos(self.clock * 47) * a * 0.8)
        cam = _env(t, m["rise"], m["climax"], m["card"], m["record"])
        if cam > 0.001 and not self.reduce:
            z = 1 + self.fx["zoom"] * cam
            s2 = pygame.transform.scale(stage, (int(w * z), int(h * z)))
            out = pygame.Surface((w, h))
            out.blit(s2, (w / 2 - s2.get_width() / 2 + (1 - z) * (fx - w / 2) + ox,
                          h / 2 - s2.get_height() / 2 + (1 - z) * (fy - h / 2) + oy))
            stage = out
        elif ox or oy:
            out = pygame.Surface((w, h))
            out.blit(stage, (ox, oy))
            stage = out
        canvas.blit(stage, (0, 0))
        if t >= m["card"]:
            self._draw_card(canvas)

    def _glow(self, canvas, light) -> None:
        """환상보다 은은하게: 같은 반 해상도 블러를 glow_mult 만큼만."""
        w, h = light.get_size()
        sc = self.fx["glow_scale"] * (0.5 if self.mobile else 1.0) * (0.5 if self.low else 1.0)
        small = pygame.transform.smoothscale(light, (max(8, int(w * sc * 0.5)), max(8, int(h * sc * 0.5))))
        blur = pygame.transform.smoothscale(small, (w, h))
        g = self.fx["glow_mult"]
        blur.fill((int(170 * g), int(140 * g), int(90 * g)), special_flags=pygame.BLEND_RGB_MULT)
        canvas.blit(blur, (0, 0), special_flags=pygame.BLEND_RGB_ADD)

    def _draw_rays(self, light, fx, fy, k: float) -> None:
        """금빛 햇살: 굵고 곧은 빛줄기 (돌지 않고 숨 쉬듯 길이만)."""
        if k <= 0.01:
            return
        n = self.fx["rays"]
        L = max(self.w, self.h) * (0.6 + 0.35 * k)
        for i in range(n):
            a = -math.pi / 2 + (i - (n - 1) / 2) * (math.pi * 1.7 / n)
            wa = 0.13 + 0.03 * math.sin(self.clock * 1.5 + i * 1.3)
            col = tuple(int(v * k * self.ray_gain * (0.24 if i % 2 else 0.14)) for v in (255, 170, 50))
            pygame.draw.polygon(light, col, [(fx, fy), (fx + math.cos(a - wa / 2) * L, fy + math.sin(a - wa / 2) * L),
                                             (fx + math.cos(a + wa / 2) * L, fy + math.sin(a + wa / 2) * L)])

    def _draw_fish(self, stage, fx, fy) -> None:
        t = self.t
        L = self.length * self.fish_scale()
        ang = (-0.35 * (1 - smoothstep(clamp(t / 0.5, 0, 1)))) + math.sin(self.sx * 2.0) * 0.12
        wag = math.sin(self.sx * 10) * 0.7
        draw_fish_side(stage, fx, fy, L, ang, self.colors, -1, tail_wag=wag, shape=self.shape)
        self._fish_pose = (fx, fy, L, ang, wag)

    def _fish_light(self, light) -> None:
        """빛 층에서 몸 자리를 비우고 (빛에 묻히지 않게) 금빛 하이라이트만 한 방향으로 지나가게."""
        if self._fish_pose is None:
            return
        m, t = self.m, self.t
        fx, fy, L, ang, wag = self._fish_pose
        self._fish_pose = None
        draw_fish_side(light, fx, fy, L, ang, self.colors, -1, silhouette=(0, 0, 0), tail_wag=wag, shape=self.shape)
        k = _env(t, m["scales"], m["scales"] + 0.15, m["afterglow"], m["wait"] + 1.5)
        if k <= 0.01:
            return
        bw, bh = int(L * 1.7), int(L * 1.0)
        mask = pygame.Surface((bw, bh))
        draw_fish_side(mask, bw / 2, bh / 2, L, ang, self.colors, -1, silhouette=(255, 255, 255), tail_wag=wag,
                       shape=self.shape)
        band = pygame.Surface((bw, bh))
        per = 1.3
        u = ((t - m["scales"]) % per) / per
        x0 = lerp(-bw * 0.3, bw * 1.3, u)
        for wdt, a in ((22, 0.10), (12, 0.2), (5, 0.32)):
            c = tuple(int(v * a * k) for v in GOLD_LIGHT)
            pygame.draw.polygon(band, c, [(x0 - wdt, 0), (x0 + wdt, 0), (x0 + wdt - bh * 0.35, bh), (x0 - wdt - bh * 0.35, bh)])
        band.blit(mask, (0, 0), special_flags=pygame.BLEND_RGB_MULT)
        light.blit(band, (fx - bw / 2, fy - bh / 2), special_flags=pygame.BLEND_RGB_ADD)

    def _draw_splash(self, stage, light, back: bool) -> None:
        """물보라: 대부분 물고기 뒤, 1/4 만 앞 (몸을 가리지 않게)."""
        for i, p in enumerate(self.splash):
            if (i % 4 == 0) == back:
                continue
            x, y, s = int(p[0]), int(p[1]), max(1, int(p[7]))
            life = clamp(p[4] / p[5], 0, 1)
            pygame.draw.circle(stage, lerp_color((150, 190, 230), (235, 245, 255), life), (x, y), s)
            if i % 3 == 0:   # 물방울 금빛 반사
                light.fill(tuple(int(v * 0.7 * life) for v in GOLD), (x - 1, y - 1, 2, 2))

    def _draw_dust(self, light) -> None:
        for i, p in enumerate(self.dust):
            a = clamp(p[4] / p[5], 0, 1)
            tw = 0.6 + 0.4 * math.sin(self.clock * 9 + i)
            col = tuple(int(v * a * tw) for v in (GOLD_LIGHT if p[6] == "gold" else GOLD))
            x, y = int(p[0]), int(p[1])
            r = max(1, int(p[7]))
            if r >= 2 and p[6] == "gold":
                pygame.draw.line(light, col, (x - r, y), (x + r, y))
                pygame.draw.line(light, col, (x, y - r), (x, y + r))
            light.fill(col, (x, y, 1 + (r > 1), 1 + (r > 1)))

    def _draw_shock(self, light, fx, fy) -> None:
        """절정 1회: 금빛 빛 폭발(0.08초 차오름) + 굵은 충격파 고리 하나."""
        dt = self.t - self.m["climax"]
        if dt < 0 or dt > 1.4:
            return
        strong = 0.5 if self.reduce else 1.0
        k = min(1.0, dt / 0.08) * max(0.0, 1 - max(0.0, dt - 0.08) / 0.45) * strong
        if k > 0:
            g = 1 + dt * 1.0
            R = int(70 * g) + 1
            glow = pygame.Surface((R * 2, R * 2))
            for r, a in ((70, 0.06), (48, 0.1), (30, 0.16), (16, 0.26)):
                tmp = pygame.Surface((R * 2, R * 2))
                pygame.draw.circle(tmp, tuple(int(v * k * a) for v in (255, 230, 170)), (R, R), int(r * g))
                glow.blit(tmp, (0, 0), special_flags=pygame.BLEND_RGB_ADD)
            light.blit(glow, (int(fx) - R, int(fy) - R), special_flags=pygame.BLEND_RGB_ADD)
        u = dt / 1.1
        if u < 1:
            rx, ry = 20 + u * self.w * 0.75, 8 + u * self.h * 0.38
            col = tuple(int(v * (1 - u) ** 1.2 * strong) for v in GOLD)
            wd = max(1, int(5 * (1 - u)) + 1)
            pygame.draw.ellipse(light, col, (fx - rx, fy - ry, rx * 2, ry * 2), wd)

    # ── 고유 이펙트 ──
    def _uk(self) -> float:
        m = self.m
        return _env(self.t, m["hit"], m["rise"], m["afterglow"], m["wait"] + 1.0)

    def _spawn_unique(self, stage: str) -> None:
        kind, r = self.uq["kind"], self.rnd
        n0 = int(self.uq.get("n", 20) * (0.5 if self.reduce else 1.0))
        w, h, wy = self.w, self.h, self.water_y
        fx, fy = self.fish_pos()
        if kind == "dragon" and stage == "rise":
            self.uq["dragon_t"] = self.t
        elif kind == "crystal_pillar" and stage == "climax":
            for i in range(min(self._budget(), n0 * 10)):
                px = w / 2 + (i % n0 - (n0 - 1) / 2) * 46
                a = r.uniform(-math.pi * 0.95, -math.pi * 0.05)
                spd = r.uniform(60, 220)
                self.uniq.append([px, wy - r.uniform(10, 70), math.cos(a) * spd, math.sin(a) * spd, r.uniform(0.8, 1.6),
                                  1.6, "shard", r.uniform(0, math.tau)])
        elif kind == "fire_pillar" and stage in ("rise", "climax"):
            for _ in range(min(self._budget(), n0 // (2 if stage == "rise" else 1))):
                self.uniq.append([fx + r.uniform(-16, 16), wy, r.uniform(-30, 30), -r.uniform(50, 160), r.uniform(1.2, 2.6),
                                  2.6, "ember", r.uniform(0, math.tau)])
        elif kind == "ice_shards" and stage in ("rise", "climax"):
            for _ in range(min(self._budget(), n0 // (2 if stage == "rise" else 1))):
                a = r.uniform(0, math.tau)
                spd = r.uniform(30, 140) * (1.6 if stage == "climax" else 1.0)
                self.uniq.append([fx, fy, math.cos(a) * spd, math.sin(a) * spd * 0.7, r.uniform(1.5, 3.0), 3.0, "ice",
                                  r.uniform(0, math.tau)])
        elif kind == "claw" and stage == "climax":
            for i in range(min(self._budget(), 30 // (2 if self.reduce else 1))):
                x = w * (0.35 + 0.15 * (i % 3)) + r.uniform(-30, 30)
                self.uniq.append([x, r.uniform(h * 0.1, h * 0.5), r.uniform(-40, 40), r.uniform(-60, 10), 1.6, 1.6, "rock",
                                  r.uniform(2, 4)])
        elif kind == "rune" and stage in ("rise", "climax"):
            for _ in range(min(self._budget(), n0)):
                self.uniq.append([fx + r.uniform(-80, 80), wy + r.uniform(-4, 10), r.uniform(-6, 6), -r.uniform(14, 40),
                                  r.uniform(2.0, 3.5), 3.5, "chip", r.uniform(0, math.tau)])
        elif kind == "lightning" and stage == "climax":
            # 낙뢰 1회: 지그재그 경로를 미리 만들어 둠 (번쩍임은 절정 1회 규칙 안)
            pts = [(fx + r.uniform(-40, 40), -5)]
            y = -5
            while y < fy - 10:
                y += r.uniform(14, 26)
                pts.append((pts[-1][0] * 0.7 + fx * 0.3 + r.uniform(-18, 18), min(y, fy - 10)))
            self._bolt = pts

    def _update_unique(self, dt: float, sp: float) -> None:
        for p in self.uniq:
            p[0] += p[2] * dt * sp
            p[1] += p[3] * dt * sp
            p[4] -= dt
            kd = p[6]
            if kd in ("shard", "rock"):
                p[3] += 300 * dt * sp
            elif kd == "ember":
                p[2] += math.sin(self.clock * 3 + p[7]) * 30 * dt
            elif kd == "ice":
                p[2] *= 1 - 0.9 * dt
                p[3] = p[3] * (1 - 0.9 * dt) + 8 * dt
            elif kd == "drop_r":
                p[3] += 200 * dt
        self.uniq = [p for p in self.uniq if p[4] > 0]
        kind, k = self.uq["kind"], self._uk()
        r = self.rnd
        if k > 0.2 and self._budget() > 0:
            half = 0.5 if self.reduce else 1.0
            if kind == "gold_rain" and r.random() < 40 * k * dt * half * 2:
                for _ in range(2):
                    self.uniq.append([r.uniform(-20, self.w), -10, -40, r.uniform(260, 340), 1.2, 1.2, "rain", 0])
            elif kind == "fire_pillar" and r.random() < 20 * k * dt * half:
                fx, _ = self.fish_pos()
                self.uniq.append([fx + r.uniform(-14, 14), self.water_y, r.uniform(-20, 20), -r.uniform(40, 120),
                                  r.uniform(1.2, 2.4), 2.4, "ember", r.uniform(0, math.tau)])
            elif kind == "reeds_bow" and self.t > self.m["climax"] - 0.1 and r.random() < 26 * k * dt * half:
                self.uniq.append([-10, r.uniform(self.h * 0.2, self.h * 0.9), r.uniform(260, 380), r.uniform(-8, 8), 1.6, 1.6,
                                  "wind", 0])
            elif kind == "spear" and self.t > self.m["climax"] and r.random() < 10 * k * dt * half:
                self.uniq.append([-10, self.water_y + r.uniform(-30, 30), r.uniform(300, 420), 0, 1.4, 1.4, "wind", 0])

    def _draw_unique_back(self, stage, light) -> None:
        kind, k, col = self.uq["kind"], self._uk(), tuple(self.uq["color"])
        if k <= 0.01:
            return
        w, h, t, m, wy = self.w, self.h, self.t, self.m, self.water_y
        fx, fy = self.fish_pos()
        cl = m["climax"]
        if kind == "cloud_part":
            # 구름이 좌우로 갈라지며 가운데로 금빛 햇살
            u = smoothstep(clamp((t - m["scales"]) / (cl - m["scales"] + 0.6), 0, 1))
            for side in (-1, 1):
                cx = w / 2 + side * lerp(30, w * 0.42, u)
                for j, (dx, dy, rx, ry) in enumerate(((0, 0, 90, 26), (side * 50, 10, 70, 20), (-side * 40, 14, 60, 18), (side * 20, -12, 64, 18))):
                    c = lerp_color((150, 140, 150), (235, 228, 220), 0.4 + 0.15 * j)
                    pygame.draw.ellipse(stage, c, (cx + dx - rx, 18 + dy - ry, rx * 2, ry * 2))
            kk = k * u
            for i in range(5):
                a = math.pi / 2 + (i - 2) * 0.16
                L = h * 1.1
                wa = 0.08
                c = tuple(int(v * kk * (0.32 if i % 2 else 0.22)) for v in col)
                pygame.draw.polygon(light, c, [(w / 2, 10), (w / 2 + math.cos(a - wa) * L, 10 + math.sin(a - wa) * L),
                                               (w / 2 + math.cos(a + wa) * L, 10 + math.sin(a + wa) * L)])
        elif kind == "fire_pillar":
            g = smoothstep(clamp((t - m["rise"]) / 0.4, 0, 1)) * k
            boost = 1 + 0.5 * _env(t, cl - 0.05, cl + 0.05, cl + 0.4, cl + 1.0)
            for i in range(0, 64, 2):
                u = i / 64
                x = fx - 32 + i + math.sin(self.clock * 9 + i * 0.7) * 4
                top = lerp(wy, -10, g) + abs(math.sin(self.clock * 5 + i)) * 40 + (1 - math.sin(math.pi * u)) * 60
                c = tuple(int(v * g * boost * 0.55 * math.sin(math.pi * u)) for v in col)
                pygame.draw.line(light, c, (x, wy), (x, top), 2)
                pygame.draw.line(stage, lerp_color((120, 40, 10), (255, 140, 40), math.sin(math.pi * u) * g), (x, wy), (x, max(top, wy - (wy - top) * 0.4)), 2)
        elif kind == "sea_part":
            # 바다가 금빛으로 갈라지는 해일: 좌우 파도 벽이 밀려나고 가운데 금빛 길
            u = smoothstep(clamp((t - m["scales"]) / (cl - m["scales"] + 0.5), 0, 1)) * k
            for side in (-1, 1):
                x0 = w / 2 + side * lerp(10, w * 0.45, u)
                hh = 20 + 60 * u
                pts = [(x0, wy + 2)]
                for j in range(9):
                    px = x0 + side * j * 12
                    pts.append((px, wy - hh * (1 - j / 10) + math.sin(self.clock * 6 + j) * 3))
                pts.append((x0 + side * 110, wy + 2))
                pygame.draw.polygon(stage, (40, 70, 110), pts)
                pygame.draw.lines(stage, (200, 225, 245), False, pts[1:-1], 2)
                pygame.draw.lines(light, tuple(int(v * 0.6 * u) for v in col), False, pts[1:-1], 2)
            gw = lerp(4, w * 0.4, u)
            for j in range(10):
                c = tuple(int(v * u * 0.25 * (1 - j / 10)) for v in col)
                pygame.draw.rect(light, c, (w / 2 - gw / 2 * (1 - j / 14), wy + j * 6, gw * (1 - j / 14), 6))
        elif kind == "rune":
            # 고대의 금빛 룬 고리: 물고기 뒤에서 묵직하게 돈다 (절정에 커지고 밝아짐)
            big = 1 + 0.35 * smoothstep(clamp((t - cl) / 0.4, 0, 1))
            kk = k * (0.6 + 0.4 * _env(t, cl - 0.05, cl + 0.05, cl + 0.6, cl + 1.6))
            R = 62 * big
            c = tuple(int(v * kk * 0.55) for v in col)
            pygame.draw.ellipse(light, c, (fx - R, fy - R * 0.55, R * 2, R * 1.1), 2)
            pygame.draw.ellipse(light, tuple(int(v * 0.6) for v in c), (fx - R * 0.8, fy - R * 0.44, R * 1.6, R * 0.88), 1)
            for i in range(12):
                a = self.clock * 0.6 + i * math.tau / 12
                x1, y1 = fx + math.cos(a) * R * 0.8, fy + math.sin(a) * R * 0.44
                x2, y2 = fx + math.cos(a) * R, fy + math.sin(a) * R * 0.55
                pygame.draw.line(light, c, (x1, y1), (x2, y2), 2 if i % 3 == 0 else 1)
        elif kind == "crystal_pillar":
            # 수면에서 수정 기둥이 솟았다가 절정에 부서짐
            if t < cl:
                g = smoothstep(clamp((t - m["rise"]) / (cl - m["rise"]), 0, 1)) * k
                n = int(self.uq.get("n", 5))
                for i in range(n):
                    px = w / 2 + (i - (n - 1) / 2) * 46
                    if abs(px - w / 2) < 20:
                        px += 70
                    H = (50 + 30 * ((i * 7) % 3)) * g
                    pw = 9
                    poly = [(px - pw, wy), (px - pw, wy - H), (px, wy - H - 12 * g), (px + pw, wy - H), (px + pw, wy)]
                    pygame.draw.polygon(stage, lerp_color((90, 110, 150), col, 0.55), poly)
                    pygame.draw.polygon(light, tuple(int(v * 0.4 * g) for v in GOLD), poly, 1)

    def _draw_unique_front(self, stage, light) -> None:
        kind, k, col = self.uq["kind"], self._uk(), tuple(self.uq["color"])
        w, h, t, m, wy = self.w, self.h, self.t, self.m, self.water_y
        fx, fy = self.fish_pos()
        cl = m["climax"]
        if kind == "claw":
            d = t - cl
            if 0 <= d < 1.2:
                grow = clamp(d / 0.12, 0, 1)
                fade = 1 - clamp((d - 0.25) / 0.95, 0, 1)
                for i in range(3):
                    x0, y0 = w * (0.62 + 0.08 * i), h * 0.08 + i * 6
                    x1, y1 = w * (0.30 + 0.08 * i), h * 0.78 + i * 6
                    xe, ye = lerp(x0, x1, grow), lerp(y0, y1, grow)
                    c = tuple(int(v * fade) for v in col)
                    pygame.draw.line(light, tuple(int(v * 0.4) for v in c), (x0, y0), (xe, ye), 7)
                    pygame.draw.line(light, c, (x0, y0), (xe, ye), 3)
                    pygame.draw.line(stage, lerp_color((60, 40, 20), WHITE, fade), (x0, y0), (xe, ye), 1)
        elif kind == "lightning" and self._bolt is not None:
            d = t - cl
            if 0 <= d < 0.6:
                a = min(1.0, d / 0.05) * (1 - d / 0.6) * (0.5 if self.reduce else 1.0)
                pts = self._bolt
                pygame.draw.lines(light, tuple(int(v * a * 0.45) for v in col), False, pts, 7)
                pygame.draw.lines(light, tuple(int(v * a) for v in col), False, pts, 3)
                pygame.draw.lines(stage, WHITE, False, pts, 1)
        elif kind == "spear":
            d = t - cl
            if -0.05 <= d < 1.0:
                u = clamp((d + 0.05) / 0.25, 0, 1)
                fade = 1 - clamp((d - 0.3) / 0.7, 0, 1)
                xe = lerp(-20, w + 20, u)
                y = fy + 6
                c = tuple(int(v * fade) for v in col)
                pygame.draw.line(light, tuple(int(v * 0.35) for v in c), (0, y), (xe, y), 8)
                pygame.draw.line(light, c, (0, y), (xe, y), 2)
                pygame.draw.polygon(light, c, [(xe + 14, y), (xe - 4, y - 5), (xe - 4, y + 5)])
            # 양옆 파도 벽
            u = _env(t, cl, cl + 0.3, m["afterglow"], m["wait"])
            if u > 0.01:
                for side in (-1, 1):
                    bx = w / 2 + side * w * 0.36
                    hh = 34 * u
                    pts = [(bx - 44, wy + 2), (bx - 20, wy - hh * 0.6), (bx, wy - hh), (bx + 20, wy - hh * 0.6), (bx + 44, wy + 2)]
                    pygame.draw.polygon(stage, (60, 100, 140), pts)
                    pygame.draw.lines(light, tuple(int(v * 0.5 * u) for v in col), False, pts[1:4], 2)
        elif kind == "dragon" and "dragon_t" in self.uq:
            self._draw_dragon(stage, light, col)
        elif kind == "reeds_bow" and k > 0.01:
            # 은빛 갈대가 금빛 바람에 일제히 눕는 물결 (절정에서 왼쪽→오른쪽으로)
            n = int(self.uq.get("n", 46))
            front = lerp(-0.2, 1.3, clamp((t - cl + 0.1) / 0.9, 0, 1))
            for i in range(n):
                u = i / (n - 1)
                x = u * w
                hgt = 26 + 14 * ((i * 7) % 5) / 4
                bow = smoothstep(clamp((front - u) * 4, 0, 1)) * (0.75 + 0.1 * math.sin(self.clock * 3 + i))
                sway = 0.08 * math.sin(self.clock * 2.4 + i * 0.5)
                a = -math.pi / 2 + sway + bow * 1.15
                x2, y2 = x + math.cos(a) * hgt, h + 2 + math.sin(a) * hgt
                c = lerp_color((150, 150, 140), col, 0.6 + 0.3 * bow)
                pygame.draw.line(stage, c, (x, h + 2), (x2, y2), 2)
                if bow > 0.2:
                    light.fill(tuple(int(v * 0.5 * bow * k) for v in GOLD), (int(x2), int(y2), 2, 2))
        # 입자
        for p in self.uniq:
            kd, x, y = p[6], p[0], p[1]
            life = clamp(p[4] / p[5], 0, 1)
            if kd == "rain":
                pygame.draw.line(stage, (230, 200, 120), (x, y), (x + 4, y - 12), 1)
                light.fill(tuple(int(v * 0.35) for v in col), (int(x), int(y), 1, 2))
                if y > wy and p[4] > 0.05:
                    p[4] = 0.0
                    if self._budget() > 0:
                        self.uniq.append([x, wy + self.rnd.uniform(0, 30), 0, 0, 0.6, 0.6, "ring", 0])
            elif kd == "ring":
                rr = (1 - life) * 14 + 2
                pygame.draw.ellipse(light, tuple(int(v * 0.45 * life) for v in col), (x - rr, y - rr * 0.3, rr * 2, rr * 0.6), 1)
            elif kd == "shard":
                a = p[7] + self.clock * 6
                s = 4
                poly = [(x + math.cos(a) * s, y + math.sin(a) * s), (x + math.cos(a + 2.4) * s * 0.6, y + math.sin(a + 2.4) * s * 0.6),
                        (x + math.cos(a + 3.9) * s * 0.6, y + math.sin(a + 3.9) * s * 0.6)]
                pygame.draw.polygon(stage, lerp_color(col, GOLD, 0.5), poly)
                pygame.draw.polygon(light, tuple(int(v * 0.6 * life) for v in GOLD), poly, 1)
            elif kd == "ember":
                fl = 0.6 + 0.4 * math.sin(self.clock * 12 + p[7])
                c = lerp_color(col, GOLD, 1 - life)
                _add_circle(light, tuple(int(v * 0.3 * fl * life) for v in c), (x, y), 3)
                light.fill(tuple(int(v * fl * life) for v in c), (int(x), int(y), 2, 2))
            elif kd == "ice":
                a = p[7] + self.clock * 2
                s = 5
                pts = [(x + math.cos(a) * s, y + math.sin(a) * s), (x - math.cos(a) * s, y - math.sin(a) * s)]
                pygame.draw.line(stage, col, pts[0], pts[1], 2)
                tw = max(0.0, math.sin(self.clock * 7 + p[7] * 3))
                light.fill(tuple(int(v * tw * life) for v in GOLD), (int(x), int(y), 2, 2))
            elif kd == "rock":
                s = int(p[7])
                stage.fill(lerp_color((80, 60, 40), (150, 120, 80), life), (int(x), int(y), s, s))
                light.fill(tuple(int(v * 0.3 * life) for v in GOLD), (int(x), int(y), 1, 1))
            elif kd == "chip":
                a = p[7] + self.clock
                s = 3
                poly = [(x + math.cos(a + j * math.tau / 6) * s, y + math.sin(a + j * math.tau / 6) * s * 0.7) for j in range(6)]
                pygame.draw.polygon(stage, (150, 130, 90), poly)
                pygame.draw.polygon(light, tuple(int(v * 0.5 * life) for v in col), poly, 1)
            elif kd == "wind":
                c = tuple(int(v * 0.4 * life) for v in GOLD)
                pygame.draw.line(light, c, (x, y), (x - 26, y), 1)

    def _draw_dragon(self, stage, light, col) -> None:
        """승천: 물보라가 용의 형상(구불구불한 몸 + 뿔 머리)으로 솟아 하늘로 오르고, 절정 뒤 금빛으로 흩어짐."""
        m, t = self.m, self.t
        t0 = self.uq["dragon_t"]
        cl = m["climax"]
        wy = self.water_y
        fx, _ = self.fish_pos()
        head = clamp((t - t0) / (cl + 0.35 - t0), 0, 1.15)   # 머리 진행도 (1 = 하늘 끝)
        burst = clamp((t - cl - 0.35) / 0.8, 0, 1)              # 흩어짐
        if burst >= 1:
            return
        n = int(self.uq.get("n", 90))
        if self.reduce:
            n //= 2
        pts = []
        for i in range(n):
            u = head - i / n * 0.75
            if u < 0:
                break
            y = lerp(wy, -30, u)
            x = fx + math.sin(u * 9 + self.clock * 2) * 46 * (0.4 + u) + math.sin(u * 3.1) * 20
            pts.append((x, y, i))
        if burst > 0:
            r = self.rnd
            if "dragon_burst" not in self.uq and self._budget() > 0:
                self.uq["dragon_burst"] = True
                for x, y, i in pts[:: max(1, len(pts) // 60)]:
                    a = r.uniform(0, math.tau)
                    spd = r.uniform(30, 120)
                    self.dust.append([x, y, math.cos(a) * spd, math.sin(a) * spd, r.uniform(1.5, 3.0), 3.0, "gold", 2])
        fade = 1 - burst
        for x, y, i in reversed(pts):
            rad = max(1, int((11 - 8 * i / n) * (0.6 + 0.4 * fade)))
            c = lerp_color((200, 225, 245), GOLD_LIGHT, burst)
            pygame.draw.circle(stage, lerp_color((90, 140, 190), c, 0.5), (int(x), int(y) + 1), rad)
            pygame.draw.circle(stage, c, (int(x), int(y)), max(1, rad - 1))
            if i % 3 == 0:   # 비늘 끝 금빛
                light.fill(tuple(int(v * 0.6 * fade) for v in col), (int(x) - 1, int(y) - rad + 1, 3, 2))
        if pts:
            hx, hy, _ = pts[0]
            # 머리: 뿔 두 개 + 수염 + 금빛 눈
            pygame.draw.circle(stage, (230, 240, 250), (int(hx), int(hy)), 13)
            pygame.draw.polygon(stage, (230, 240, 250), [(hx - 8, hy + 4), (hx + 8, hy + 4), (hx, hy + 16)])  # 주둥이
            for s in (-1, 1):
                pygame.draw.line(stage, GOLD_LIGHT, (hx + s * 4, hy - 6), (hx + s * 10, hy - 18), 2)
                pygame.draw.line(stage, (200, 225, 245), (hx + s * 6, hy + 4), (hx + s * 20, hy + 10 + math.sin(self.clock * 6) * 3), 1)
            _add_circle(light, tuple(int(v * 0.8 * fade) for v in GOLD), (hx + 3, hy - 2), 3)

    # ── 카드 ──
    def reward_icons(self) -> list[tuple[str, tuple]]:
        n = self.news
        out = []
        if n.get("chest"):
            from src.save.treasure import grade_info
            out.append(("chest", tuple(grade_info(n["chest"])["color"])))
        if n.get("legend_scales"):
            out.append(("scale", (255, 214, 90)))
        if n.get("trophy"):
            out.append(("gold", (255, 214, 90)))
        return out

    def _draw_card(self, canvas) -> None:
        """금색 테두리 카드가 '쾅' 박히듯 등장 — '전설의 물고기' + 이름이 한 번에."""
        m, t = self.m, self.t
        w, h = canvas.get_size()
        d = t - m["card"]
        slam = 1.0 + 0.35 * (1 - smoothstep(clamp(d / 0.12, 0, 1)))
        a = clamp(d / 0.08, 0, 1)
        cw, ch = int(260 * slam), int(88 * slam)
        cx, cy = w // 2, int(h * 0.69)
        r = pygame.Rect(0, 0, cw, ch)
        r.center = (cx, cy)
        back = pygame.Surface(r.size, pygame.SRCALPHA)
        back.fill((30, 20, 8, int(230 * a)))
        canvas.blit(back, r.topleft)
        pulse = 0.6 + 0.4 * math.sin(self.clock * 2.2)
        pygame.draw.rect(canvas, lerp_color(GOLD_DEEP, GOLD_LIGHT, pulse), r, 3)
        pygame.draw.rect(canvas, (150, 110, 40), r.inflate(-8, -8), 1)
        for sx in (r.left + 3, r.right - 5):   # 모서리 장식
            for sy in (r.top + 3, r.bottom - 5):
                canvas.fill(GOLD_LIGHT, (sx, sy, 2, 2))
        if 0 <= d < 0.35:   # 박힐 때 금가루 먼지
            k = 1 - d / 0.35
            for i in range(14):
                ang = i / 14 * math.tau
                rr = 8 + d * 160
                px, py = cx + math.cos(ang) * (cw / 2 + rr * 0.4), cy + math.sin(ang) * (ch / 2 + rr * 0.2)
                canvas.fill(lerp_color((40, 30, 10), GOLD_LIGHT, k), (int(px), int(py), 2, 2))
        if d < 0.1:
            return
        font11, font16 = get_font(11), get_font(16)
        top = font11.render("전설의 물고기", False, GOLD)
        canvas.blit(top, (cx - top.get_width() // 2, r.y + 6))
        name = font16.render(self.fish["name"], False, WHITE)
        sh = font16.render(self.fish["name"], False, GOLD_DEEP)
        canvas.blit(sh, (cx - name.get_width() // 2 + 1, r.y + 21))
        canvas.blit(name, (cx - name.get_width() // 2, r.y + 20))
        if t >= m["record"] - 0.4:
            u = clamp((t - (m["record"] - 0.4)) / 0.5, 0, 1)
            size = self.result["size"] * (1 - (1 - u) ** 3)
            s = font16.render(f"{size:.1f}cm", False, WHITE)
            canvas.blit(s, (cx - s.get_width() // 2, r.y + 44))
        if t >= m["record"] and self.result.get("rank"):   # 랭크: 왼쪽에 묵직하게
            u = clamp((t - m["record"]) / 0.12, 0, 1)
            rk = font16.render(self.result["rank"], False, GOLD_LIGHT if self.result["rank"] == "S" else WHITE)
            rk = pygame.transform.scale(rk, (int(rk.get_width() * lerp(2.0, 1.4, u)), int(rk.get_height() * lerp(2.0, 1.4, u))))
            canvas.blit(rk, rk.get_rect(center=(r.x + 26, r.y + 30)))
        if self.news.get("new") and t >= m["record"]:
            u = clamp((t - m["record"]) / 0.12, 0, 1)
            sc = lerp(2.2, 1.0, u * u)
            sx, sy = r.right - 26, r.y + 26
            rad = int(15 * sc)
            pygame.draw.circle(canvas, (90, 60, 10), (sx, sy), rad)
            pygame.draw.circle(canvas, GOLD, (sx, sy), rad, 2)
            g = font11.render("전", False, GOLD_LIGHT)
            g = pygame.transform.scale(g, (int(g.get_width() * sc * 1.2), int(g.get_height() * sc * 1.2)))
            canvas.blit(g, g.get_rect(center=(sx, sy)))
            if u >= 1:
                nw = font11.render("NEW", False, (255, 230, 120))
                canvas.blit(nw, (sx - nw.get_width() // 2, sy + 17))
        icons = self.reward_icons()
        for i, (kind, col) in enumerate(icons):
            ti = m["rewards"] + i * 0.22
            if t < ti - 0.3:
                continue
            u = smoothstep(clamp((t - (ti - 0.3)) / 0.3, 0, 1))
            tx = cx - (len(icons) - 1) * 14 + i * 28
            ty = r.bottom + 12
            side = -1 if i % 2 == 0 else 1
            x0, y0 = cx + side * (cw // 2 + 30), r.bottom + 4
            px = lambda q: (lerp(x0, tx, q), lerp(y0, ty, q) - math.sin(math.pi * q) * 16)  # noqa: E731
            x_, y_ = px(u)
            if u < 1:   # 금빛 줄기 (카드 바깥에서 아래로 돌아 들어옴)
                pygame.draw.lines(canvas, lerp_color((80, 60, 20), GOLD, 1 - u), False,
                                  [px(max(0.0, u - 0.3 + 0.1 * j)) for j in range(4)], 2)
            self._icon(canvas, kind, int(x_), int(y_), col)
        line = []
        if self.news.get("trophy") and t >= m["rewards"] + 0.25 * len(icons):
            line.append(f"트로피 +{self.news['trophy']:,}G")
        if self.news.get("legend_scales") and t >= m["rewards"] + 0.25 * len(icons):
            line.append(f"전설 비늘 +{self.news['legend_scales']}")
        if line:
            img = font11.render(" · ".join(line), False, (255, 214, 90))
            canvas.blit(img, (cx - img.get_width() // 2, r.y + 64))
        if self.waiting() and int(self.clock * 2) % 2 == 0:
            img = font11.render("클릭해서 계속" if not self.final else "클릭해서 계속 — 그리고…", False, (220, 200, 160))
            canvas.blit(img, (cx - img.get_width() // 2, h - 14))
        elif self.can_skip() and not self.waiting():
            img = font11.render("클릭: 건너뛰기", False, (150, 130, 100))
            canvas.blit(img, (w - img.get_width() - 6, h - 14))

    def _icon(self, canvas, kind, x, y, col) -> None:
        if kind == "chest":
            canvas.fill((60, 40, 30), (x - 7, y - 4, 14, 9))
            pygame.draw.rect(canvas, col, (x - 7, y - 5, 14, 10), 1)
            canvas.fill(col, (x - 1, y - 2, 2, 3))
        elif kind == "scale":
            pygame.draw.polygon(canvas, col, [(x, y - 7), (x + 6, y - 1), (x + 3, y + 6), (x - 3, y + 6), (x - 6, y - 1)])
            pygame.draw.polygon(canvas, WHITE, [(x, y - 7), (x + 6, y - 1), (x + 3, y + 6), (x - 3, y + 6), (x - 6, y - 1)], 1)
        else:
            pygame.draw.circle(canvas, col, (x, y), 6)
            pygame.draw.circle(canvas, (120, 90, 30), (x, y), 6, 1)
            canvas.fill((150, 110, 30), (x - 1, y - 3, 2, 6))

    def particle_count(self) -> int:
        return len(self.splash) + len(self.dust) + len(self.uniq)
