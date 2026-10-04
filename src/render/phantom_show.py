"""환상어 포획 연출 (DESIGN.md 33-11, PHANTOM_CATCH_SHOW.md): 전설은 '웅장', 환상은 '황홀'.

LandingCinematic 대신 환상어만. 시계는 실제 시간(+ 오디오 출력 지연·보정만큼 늦게) — 음악(환상의 노래)과 같은 마커
(data/phantom_catch_timeline.json)에 맞춰 단계를 실행한다. 슬로모션은 입자·물고기 움직임 배속으로 표현.

층 (16): 슬로모션 · 멈춘 물방울 · 보라 물기둥 · 비늘 무지개 · 빛줄기 · 오로라 커튼 · 빛 폭발 · 충격파 고리 · 별 입자 ·
       고유 이펙트(12종) · 카메라(다가가기·기울기) · 글로우(반 해상도 더하기) · 잔상 · 가장자리 어둠 · 카드 인장 · 보상 궤적
버전: full(그 종 첫 포획) / short(재포획) / extended(12종 완성 — 절정 뒤 12종 실루엣 원).
"""
import math
import random
import time

import pygame

from src.core.config import load_json
from src.core.fonts import get_font
from src.core.mathutil import clamp, lerp, lerp_color, smoothstep
from src.render.fish_draw import draw_fish_side, fish_colors, fish_shape

VIO = (190, 120, 255)
VIO_LIGHT = (225, 190, 255)
WHITE = (255, 255, 255)
RAINBOW = ((200, 120, 255), (110, 230, 230), (255, 150, 220), (200, 120, 255))


def _add_circle(light, col, pos, r: int) -> None:
    """빛 층에 원을 '더한다' (덮어쓰면 아래 빛줄기가 지워져 어두운 원판이 생김)."""
    r = max(1, int(r))
    tmp = pygame.Surface((r * 2 + 2, r * 2 + 2))
    pygame.draw.circle(tmp, col, (r + 1, r + 1), r)
    light.blit(tmp, (int(pos[0]) - r - 1, int(pos[1]) - r - 1), special_flags=pygame.BLEND_RGB_ADD)


def tl() -> dict:
    return load_json("phantom_catch_timeline.json")


def _env(t: float, a: float, b: float, c: float, d: float) -> float:
    """사다리꼴 세기: a~b 올라감, b~c 유지, c~d 내려감."""
    if t <= a or t >= d:
        return 0.0
    if t < b:
        return smoothstep((t - a) / max(1e-6, b - a))
    if t <= c:
        return 1.0
    return 1.0 - smoothstep((t - c) / max(1e-6, d - c))


class PhantomShow:
    def __init__(self, fish: dict, result: dict, news: dict, variant: str, w: int, h: int, *,
                 mobile: bool = False, reduce: bool = False, delay: float = 0.0, rnd: random.Random | None = None,
                 low: bool = False):
        self.fish, self.result, self.news = fish, result, news or {}
        self.variant = variant
        c = tl()
        self.v = c["variants"][variant]
        self.m = self.v["markers"]
        self.fx = c["fx"]
        self.uq = c["unique"].get(fish["id"], {"kind": "spirits", "color": [230, 210, 255], "n": 8})
        self.w, self.h = w, h
        self.mobile, self.reduce = mobile, reduce
        self.cap = c["caps"]["mobile" if mobile else "pc"] // (2 if reduce else 1)
        # 화질: 느린 기기·초당 30번 설정이면 처음부터 낮음, 모바일에서 그리기가 22ms 넘게 이어지면 자동으로 낮춤
        self.low = False
        self.draw_ms = 0.0
        if low:
            self._lower()
        self.delay = delay          # 오디오 출력 지연 + 보정: 그림을 그만큼 늦게
        self.clock = 0.0            # 실제 시간
        self.t = -delay             # 연출 시각 (음악 시각)
        self.rnd = rnd or random.Random()
        self.colors = fish_colors(fish)
        self.shape = fish_shape(fish)
        self.length = clamp(w * 0.32, 120, 170)
        self.fired: set = set()
        self.events: list[str] = []
        # 입자: [x, y, vx, vy, life, max_life, kind, size]
        self.drops: list[list] = []
        self.stars: list[list] = []
        self.uniq: list[list] = []
        self.icons_landed = 0
        self.skipped = False
        self.closing = False
        self.sx = 0.0               # 슬로모션 시계 (물방울·물고기 움직임용)
        self.water_y = int(h * 0.62)
        self.ring_fish = []
        if variant == "extended":
            from src.fishing.phantom import all_phantoms
            self.ring_fish = all_phantoms()

    def _lower(self) -> None:
        """낮은 화질: 입자 상한 절반, 글로우 해상도 절반, 오로라 열 굵게."""
        if not self.low:
            self.low = True
            self.cap //= 2

    # ── 시간 ──
    @property
    def speed(self) -> float:
        """슬로모션 배속 (화면 효과 줄이기: 절정에서 바로 풀림)."""
        a, b, s = self.v["slow"]
        if self.reduce:
            b = min(b, self.m["climax"])
        if self.t < b:
            return s
        return lerp(s, 1.0, smoothstep((self.t - b) / 0.4))

    def can_skip(self) -> bool:
        return self.t >= self.v["skip_after"] and self.t < self.m["wait"]

    def waiting(self) -> bool:
        return self.t >= self.m["wait"]

    def skip(self) -> None:
        """건너뛰기: 카드가 다 펼쳐진 상태로 (보상·도감은 이미 처리됨)."""
        self.t = self.m["wait"]
        self.skipped = True
        self.events.append("skip")
        self.drops.clear()

    def update(self, dt: float) -> list[str]:
        self.clock += dt
        self.t += dt
        sp = self.speed
        self.sx += dt * sp
        m = self.m
        for name in ("rise", "scales", "rays", "climax", "return", "card", "record", "rewards", "afterglow", "wait",
                     "ring"):
            if name in m and self.t >= m[name] and name not in self.fired:
                self.fired.add(name)
                if not self.skipped or name in ("wait",):
                    self.events.append(name)
                    self._on(name)
        if self.t >= 0 and "breath" not in self.fired:
            self.fired.add("breath")
            self.events.append("breath")
        # 보상 아이콘: rewards 부터 0.25초 간격으로 착지
        n_icons = len(self.reward_icons())
        if self.t >= m["rewards"]:
            k = min(n_icons, int((self.t - m["rewards"]) / 0.25) + 1)
            while self.icons_landed < k:
                self.events.append(f"icon:{self.icons_landed}")
                self.icons_landed += 1
        self._update_particles(dt, sp)
        out, self.events = self.events, []
        return out

    def _budget(self) -> int:
        return self.cap - len(self.drops) - len(self.stars) - len(self.uniq)

    def _on(self, name: str) -> None:
        fx, fy = self.fish_pos()
        r = self.rnd
        if name == "rise":
            # 수면을 뚫고 오르며 튄 물방울 — 공중에 멈춰 반짝인다
            n = min(self._budget(), self.fx["droplets"] // (2 if self.reduce else 1))
            for _ in range(max(0, n)):
                a = r.uniform(-math.pi * 0.95, -math.pi * 0.05)
                sp = r.uniform(40, 170)
                self.drops.append([self.w / 2 + r.uniform(-30, 30), self.water_y, math.cos(a) * sp, math.sin(a) * sp,
                                   99.0, 99.0, "drop", r.uniform(1, 2.6)])
            self._spawn_unique(0.5)
        elif name == "climax":
            # 공중의 물방울이 일제히 빛 입자로 터짐 + 중앙 빛 폭발 입자
            for d in self.drops:
                for _ in range(2):
                    if self._budget() <= 0:
                        break
                    a = r.uniform(0, math.tau)
                    sp = r.uniform(20, 70)
                    self.stars.append([d[0], d[1], math.cos(a) * sp, math.sin(a) * sp - 10, r.uniform(1.2, 2.6), 2.6,
                                       "star", r.uniform(1, 2.5)])
            self.drops.clear()
            n = min(self._budget(), self.fx["burst_particles"] // (2 if self.reduce else 1))
            for _ in range(max(0, n)):
                a = r.uniform(0, math.tau)
                sp = r.uniform(30, 220)
                self.stars.append([fx, fy, math.cos(a) * sp, math.sin(a) * sp * 0.7, r.uniform(1.0, 2.8), 2.8, "star",
                                   r.uniform(1, 3)])
            self._spawn_unique(1.0)

    # ── 입자 ──
    def _update_particles(self, dt: float, sp: float) -> None:
        r = self.rnd
        for d in self.drops:   # 멈춘 물방울: 슬로모션 배속으로만 움직임 (거의 정지)
            d[0] += d[2] * dt * sp * 0.25
            d[1] += d[3] * dt * sp * 0.25
            d[3] += 60 * dt * sp * 0.25
        for p in self.stars:
            p[0] += p[2] * dt * sp
            p[1] += p[3] * dt * sp
            p[2] *= 1 - 0.8 * dt
            p[3] = p[3] * (1 - 0.8 * dt) + 6 * dt   # 천천히 내려옴
            p[4] -= dt
        self.stars = [p for p in self.stars if p[4] > 0]
        # 은은한 별 입자 (빛줄기 ~ 대기까지)
        m = self.m
        if m["rays"] <= self.t and self._budget() > 0:
            rate = self.fx["star_rate"] * (0.5 if self.reduce else 1.0) * (0.4 if self.t > m["afterglow"] else 1.0)
            if r.random() < rate * dt:
                self.stars.append([r.uniform(0, self.w), r.uniform(self.h * 0.1, self.h * 0.7), r.uniform(-6, 6),
                                   r.uniform(-14, -4), r.uniform(1.5, 3.0), 3.0, "dust", r.uniform(1, 2)])
        self._update_unique(dt, sp)

    # ── 위치 ──
    def fish_pos(self) -> tuple[float, float]:
        m = self.m
        rise = smoothstep(clamp((self.t - m["rise"]) / max(0.2, m["scales"] - m["rise"] + 0.3), 0, 1))
        y = lerp(self.water_y + 30, self.h * 0.40, rise)
        if self.t > m["return"]:
            y = lerp(y, self.h * 0.30, smoothstep((self.t - m["return"]) / 0.6))
        bob = math.sin(self.clock * 1.6) * 3 * rise
        return self.w / 2, y + bob

    def fish_scale(self) -> float:
        m = self.m
        k = smoothstep(clamp((self.t - m["return"]) / 0.6, 0, 1))
        return lerp(1.0, 0.72, k)

    # ── 그리기 ──
    def draw(self, canvas: pygame.Surface, pal: dict) -> None:
        t0 = time.perf_counter()
        self._draw(canvas, pal)
        ms = (time.perf_counter() - t0) * 1000
        self.draw_ms = ms if self.draw_ms == 0 else self.draw_ms * 0.9 + ms * 0.1
        if self.mobile and self.draw_ms > 22 and self.t > 0.5:
            self._lower()

    def _draw(self, canvas: pygame.Surface, pal: dict) -> None:
        w, h = canvas.get_size()
        m, t = self.m, self.t
        stage = canvas.copy()
        light = pygame.Surface((w, h))
        light.fill((0, 0, 0))
        fx, fy = self.fish_pos()
        # 가장자리 어둠 (숨 멎음)
        dark = _env(t, -0.2, 0.1, m["return"], m["card"] + 0.4) * 0.45 + 0.15 * (t < m["rise"])
        if dark > 0:
            sh = pygame.Surface((w, h), pygame.SRCALPHA)
            sh.fill((10, 4, 20, int(150 * dark)))
            stage.blit(sh, (0, 0))
        k_aur = _env(t, m["rays"], m["climax"], m["afterglow"], m["wait"] + 1.0)
        if self.uq["kind"] == "snow":
            k_aur = min(1.0, k_aur * 1.6)
        self._draw_aurora(light, k_aur)
        self._draw_unique_back(stage, light)
        self._draw_rays(light, fx, fy, _env(t, m["rays"], m["climax"], m["return"] + 0.6, m["afterglow"] + 0.8))
        self._draw_column(stage, light, _env(t, m["rise"], m["rise"] + 0.25, m["climax"], m["return"] + 0.3))
        if self.ring_fish and "ring" in m:
            self._draw_ring(stage, light)
        self._draw_fish(stage, light, fx, fy)
        self._draw_unique_front(stage, light)
        self._draw_drops(stage, light)
        self._draw_stars(light)
        self._draw_burst(light, fx, fy)
        self._fish_light(light)
        # 카메라: 물고기 쪽으로 살짝 다가가며 아주 약간 기울어짐 (화면 효과 줄이기: 없음)
        stage.blit(light, (0, 0), special_flags=pygame.BLEND_RGB_ADD)
        self._glow(stage, light)
        cam = _env(t, m["rise"], m["climax"], m["return"], m["card"] + 0.4)
        if cam > 0.001 and not self.reduce:
            z = 1 + self.fx["zoom"] * cam
            ang = self.fx["tilt_deg"] * cam * (0 if self.mobile else 1)
            stage = self._camera(stage, z, ang, fx, fy)
        canvas.blit(stage, (0, 0))
        if t >= m["card"]:
            self._draw_card(canvas)

    def _camera(self, surf, z, ang, fx, fy):
        """화면 가운데 기준으로 확대·회전한 뒤, 물고기 자리가 제자리에 오도록 옮긴다."""
        w, h = surf.get_size()
        if abs(ang) > 0.05:
            s2 = pygame.transform.rotozoom(surf, ang, z)
        else:
            s2 = pygame.transform.scale(surf, (int(w * z), int(h * z)))
        out = pygame.Surface((w, h))
        bx = w / 2 - s2.get_width() / 2 + (1 - z) * (fx - w / 2)
        by = h / 2 - s2.get_height() / 2 + (1 - z) * (fy - h / 2)
        out.blit(s2, (bx, by))
        return out

    def _glow(self, canvas, light) -> None:
        """밝은 부분 주변이 은은하게 번짐: 반(모바일 ¼) 해상도로 줄였다 키운 빛을 더한다."""
        w, h = light.get_size()
        sc = self.fx["glow_scale"] * (0.5 if self.mobile else 1.0) * (0.5 if self.low else 1.0)
        small = pygame.transform.smoothscale(light, (max(8, int(w * sc * 0.5)), max(8, int(h * sc * 0.5))))
        blur = pygame.transform.smoothscale(small, (w, h))
        blur.fill((150, 140, 170), special_flags=pygame.BLEND_RGB_MULT)
        canvas.blit(blur, (0, 0), special_flags=pygame.BLEND_RGB_ADD)

    def _draw_aurora(self, light, k: float) -> None:
        """오로라 커튼: 하늘 위쪽에서 흔들리며 내려온다 (열 6px, 밝기 16단계 색표)."""
        if k <= 0.01:
            return
        w, h = light.get_size()
        drop = lerp(-50, 0, k)
        cl = self.clock
        for b in range(self.fx["aurora_bands"]):
            col = lerp_color((140, 70, 220), (90, 200, 200) if b % 2 else (230, 120, 220), 0.35)
            lut = [tuple(int(v * i / 15) for v in col) for i in range(16)]
            base = 18 + b * 12 + drop
            sp, ph = 0.6 + 0.1 * b, 1.3 * cl + b
            cw = 10 if self.low else 6
            for x in range(0, w, cw):
                top = base + math.sin(x * 0.02 + cl * sp + b) * 10 + math.sin(x * 0.051 - cl) * 5
                ln = 26 + 14 * math.sin(x * 0.013 + b * 1.7 + cl * 0.4)
                a = k * (0.35 + 0.25 * math.sin(x * 0.04 + ph))
                if a > 0.02:
                    light.fill(lut[min(15, int(a * 15))], (x, int(top), cw, int(ln)))

    def _draw_rays(self, light, fx, fy, k: float) -> None:
        if k <= 0.01:
            return
        n = self.fx["rays"]
        L = max(self.w, self.h) * 0.9
        for i in range(n):
            a = self.clock * 0.25 + i * math.tau / n
            wa = 0.07 + 0.03 * math.sin(self.clock * 2 + i)
            col = tuple(int(v * k * (0.32 if i % 2 else 0.16)) for v in VIO)
            pygame.draw.polygon(light, col, [(fx, fy), (fx + math.cos(a) * L, fy + math.sin(a) * L),
                                             (fx + math.cos(a + wa) * L, fy + math.sin(a + wa) * L)])

    def _draw_column(self, stage, light, k: float) -> None:
        """보라 물기둥: 물고기가 뚫고 나온 자리에서 솟는다."""
        if k <= 0.01:
            return
        fx, fy = self.fish_pos()
        top = lerp(self.water_y, fy - 10, k)
        cw = 26 + 10 * k
        for i in range(int(cw)):
            u = i / cw
            edge = math.sin(math.pi * u)
            col = tuple(int(v * k * edge * 0.6) for v in (120, 80, 220))
            wob = math.sin(self.clock * 7 + i * 0.6) * 2
            pygame.draw.line(light, col, (fx - cw / 2 + i, top + wob), (fx - cw / 2 + i, self.water_y + 6), 1)
        # 기둥 밑동 물보라 고리
        pygame.draw.ellipse(light, tuple(int(v * k * 0.8) for v in VIO_LIGHT),
                            (fx - cw * 1.4, self.water_y - 4, cw * 2.8, 10), 1)

    def _draw_fish(self, stage, light, fx, fy) -> None:
        m, t = self.m, self.t
        if t < m["rise"] - 0.05:
            return
        L = self.length * self.fish_scale()
        ang = math.sin(self.sx * 2.2) * 0.25 + (0.0 if t > m["return"] else math.sin(self.sx * 6) * 0.08)
        wag = math.sin(self.sx * 9) * 0.6
        # 잔향어: 4겹 잔상이 하나로 모임 (고유)
        draw_fish_side(stage, fx, fy, L, ang, self.colors, -1, tail_wag=wag, shape=self.shape)
        self._fish_pose = (fx, fy, L, ang, wag)

    def _fish_light(self, light) -> None:
        """빛 층의 물고기 자리: 모든 빛을 그린 뒤 몸을 비우고 (빛줄기·폭발에 묻히지 않게) 무지갯빛 띠만 얹는다."""
        if getattr(self, "_fish_pose", None) is None:
            return
        m, t = self.m, self.t
        fx, fy, L, ang, wag = self._fish_pose
        self._fish_pose = None
        draw_fish_side(light, fx, fy, L, ang, self.colors, -1, silhouette=(0, 0, 0), tail_wag=wag, shape=self.shape)
        k = _env(t, m["scales"], m["scales"] + 0.3, m["afterglow"], m["wait"] + 2)
        if k <= 0.01:
            return
        bw, bh = int(L * 1.7), int(L * 1.0)
        mask = pygame.Surface((bw, bh))
        draw_fish_side(mask, bw / 2, bh / 2, L, ang, self.colors, -1, silhouette=(255, 255, 255), tail_wag=wag,
                       shape=self.shape)
        band = pygame.Surface((bw, bh))
        off = (self.clock * 90) % (bw * 1.5) - bw * 0.25
        for i, col in enumerate(RAINBOW):
            x0 = off + i * 5 - bw * 0.25
            c = tuple(int(v * 0.28 * k) for v in col)
            pygame.draw.polygon(band, c, [(x0, 0), (x0 + 5, 0), (x0 - bh * 0.5 + 5, bh), (x0 - bh * 0.5, bh)])
        band.blit(mask, (0, 0), special_flags=pygame.BLEND_RGB_MULT)
        light.blit(band, (fx - bw / 2, fy - bh / 2), special_flags=pygame.BLEND_RGB_ADD)

    def _draw_drops(self, stage, light) -> None:
        tw = self.clock * 8
        for i, d in enumerate(self.drops):
            x, y = int(d[0]), int(d[1])
            s = max(1, int(d[7]))
            pygame.draw.circle(stage, (200, 190, 240), (x, y), s)
            k = 0.5 + 0.5 * math.sin(tw + i * 1.3)
            pygame.draw.circle(light, tuple(int(v * k) for v in VIO), (x, y), s + 1)

    def _draw_stars(self, light) -> None:
        for p in self.stars:
            a = clamp(p[4] / p[5], 0, 1)
            col = tuple(int(v * a) for v in (VIO_LIGHT if p[6] == "star" else (170, 140, 230)))
            x, y, r = int(p[0]), int(p[1]), max(1, int(p[7] * (0.6 + 0.4 * a)))
            if p[6] == "star" and r >= 2:
                pygame.draw.line(light, col, (x - r, y), (x + r, y))
                pygame.draw.line(light, col, (x, y - r), (x, y + r))
            light.fill(col, (x, y, 1 + (r > 1), 1 + (r > 1)))

    def _draw_burst(self, light, fx, fy) -> None:
        """절정 1회만: 중앙 빛 폭발 + 충격파 고리 (등장 파장과 같은 납작한 타원) — 밝기 급변 제한."""
        m, t = self.m, self.t
        dt = t - m["climax"]
        if dt < 0 or dt > 1.6:
            return
        strong = 0.5 if self.reduce else 1.0
        k = min(1.0, dt / 0.08) * max(0.0, 1 - max(0.0, dt - 0.08) / 0.5) * strong  # 0.08초 동안 차오름 (밝기 급변 제한)
        if k > 0:
            g = 1 + dt * 1.2
            R = int(84 * g) + 1
            glow = pygame.Surface((R * 2, R * 2))
            for r, a in ((84, 0.06), (62, 0.08), (44, 0.1), (30, 0.14), (18, 0.2), (9, 0.3)):
                c = tuple(int(v * k * a) for v in (255, 235, 255))
                tmp = pygame.Surface((R * 2, R * 2))
                pygame.draw.circle(tmp, c, (R, R), int(r * g))
                glow.blit(tmp, (0, 0), special_flags=pygame.BLEND_RGB_ADD)
            light.blit(glow, (int(fx) - R, int(fy) - R), special_flags=pygame.BLEND_RGB_ADD)
        for i in range(self.fx["shock_rings"]):
            d = dt - i * 0.18
            if d <= 0:
                continue
            u = d / 1.3
            if u >= 1:
                continue
            rx, ry = u * self.w * 0.9, u * self.h * 0.45
            col = tuple(int(v * (1 - u) * strong) for v in (226, 170, 255))
            pygame.draw.ellipse(light, col, (fx - rx, fy - ry, rx * 2, ry * 2), 2)

    def _draw_ring(self, stage, light) -> None:
        """12종 완성: 절정 뒤 12종 실루엣이 원을 그리며 나타났다 사라짐."""
        m, t = self.m, self.t
        if not (m["ring"] <= t <= m["ring_end"] + 0.6):
            return
        fx, fy = self.fish_pos()
        R = min(self.w, self.h) * 0.42
        span = m["ring_end"] - m["ring"]
        for i, f in enumerate(self.ring_fish):
            ti = m["ring"] + span * i / 12
            if t < ti:
                continue
            a = -math.pi / 2 + i * math.tau / 12 + (t - m["ring"]) * 0.3
            k = min(1.0, (t - ti) / 0.3) * (1 - smoothstep((t - m["ring_end"]) / 0.6))
            x, y = fx + math.cos(a) * R, fy + math.sin(a) * R * 0.75
            col = lerp_color((40, 20, 70), (225, 190, 255), k)
            draw_fish_side(stage, x, y, 34, 0.0, fish_colors(f), -1, silhouette=col, shape=fish_shape(f))
            pygame.draw.circle(light, tuple(int(v * k * 0.5) for v in VIO), (int(x), int(y)), 16, 1)

    # ── 고유 이펙트 (V5) ──
    def _uk(self) -> float:
        m = self.m
        return _env(self.t, m["rise"], m["climax"], m["afterglow"], m["wait"] + 0.8)

    def _spawn_unique(self, k: float) -> None:
        kind, r, n = self.uq["kind"], self.rnd, int(self.uq.get("n", 10) * (0.5 if self.reduce else 1.0) * k)
        n = min(n, max(0, self._budget()))
        w, h = self.w, self.h
        for _ in range(n):
            if kind == "meteors":
                self.uniq.append([r.uniform(w * 0.2, w * 1.2), r.uniform(-20, h * 0.3), -r.uniform(180, 300),
                                  r.uniform(60, 120), r.uniform(0.6, 1.2), 1.2, kind, r.uniform(0, 1.2)])
            elif kind == "orbs":
                self.uniq.append([r.uniform(0, w), h + 10, 0, -r.uniform(20, 50), 6.0, 6.0, kind, r.uniform(0, math.tau)])
            elif kind == "reeds":
                self.uniq.append([r.uniform(-w * 0.3, 0), r.uniform(h * 0.15, h * 0.85), r.uniform(80, 160),
                                  r.uniform(-15, 15), 6.0, 6.0, kind, r.uniform(0, math.tau)])
            elif kind == "butterflies":
                self.uniq.append([r.uniform(w * 0.2, w * 0.8), self.water_y + r.uniform(0, 20), r.uniform(-30, 30),
                                  -r.uniform(25, 60), 6.0, 6.0, kind, r.uniform(0, math.tau)])
            elif kind == "embers":
                self.uniq.append([r.uniform(0, w), h + r.uniform(0, 20), r.uniform(-10, 10), -r.uniform(25, 70),
                                  r.uniform(3, 6), 6.0, kind, r.uniform(0, math.tau)])
            elif kind == "snow":
                self.uniq.append([r.uniform(0, w), -r.uniform(0, h * 0.5), r.uniform(-8, 8), r.uniform(12, 30),
                                  8.0, 8.0, kind, r.uniform(0, math.tau)])
            elif kind == "mist":
                self.uniq.append([0, 0, 0, 0, 7.0, 7.0, kind, r.uniform(0, math.tau)])
            elif kind in ("spirits", "crystals", "echo"):
                self.uniq.append([0, 0, 0, 0, 7.0, 7.0, kind, len(self.uniq)])

    def _update_unique(self, dt: float, sp: float) -> None:
        for p in self.uniq:
            p[0] += p[2] * dt * max(0.35, sp)
            p[1] += p[3] * dt * max(0.35, sp)
            p[4] -= dt
            if p[6] == "butterflies":
                p[2] += math.sin(self.clock * 3 + p[7]) * 40 * dt
            if p[6] == "embers":
                p[2] += math.sin(self.clock * 2 + p[7]) * 20 * dt
        self.uniq = [p for p in self.uniq if p[4] > 0]
        # 계속 생기는 종류 (유성·불씨·눈·나비)
        kind = self.uq["kind"]
        if kind in ("meteors", "embers", "snow", "butterflies", "reeds", "orbs") and self._uk() > 0.2 and self._budget() > 0:
            rate = {"meteors": 3, "embers": 30, "snow": 30, "butterflies": 4, "reeds": 24, "orbs": 2}[kind]
            if self.rnd.random() < rate * self._uk() * dt * (0.5 if self.reduce else 1.0):
                n0 = self.uq.get("n", 10)
                self.uq["n"] = 1
                self._spawn_unique(1.0)
                self.uq["n"] = n0

    def _draw_unique_back(self, stage, light) -> None:
        kind, k, col = self.uq["kind"], self._uk(), tuple(self.uq["color"])
        if k <= 0.01:
            return
        w, h, t, m = self.w, self.h, self.t, self.m
        fx, fy = self.fish_pos()
        if kind == "moon":
            # 보름달이 떠오르고 수면에 달빛 길
            rise = smoothstep(clamp((t - m["rise"]) / (m["climax"] - m["rise"] + 0.4), 0, 1))
            mx, my = w * 0.26, lerp(self.water_y + 10, h * 0.2, rise)
            for r, a in ((46, 0.1), (36, 0.15), (28, 0.75)):
                _add_circle(light, tuple(int(v * k * a) for v in col), (mx, my), r)
            for i in range(16):
                y = self.water_y + 4 + i * 6
                if y > h:
                    break
                ln = 18 - i * 0.6 + 6 * math.sin(self.clock * 3 + i)
                c = tuple(int(v * k * (0.7 - i * 0.03)) for v in col)
                pygame.draw.line(light, c, (mx - ln / 2, y), (mx + ln / 2, y), 1)
        elif kind == "dusk":
            sky = pygame.Surface((w, int(h * 0.62)), pygame.SRCALPHA)
            sh_ = sky.get_height()
            for y in range(0, sh_, 3):
                u = y / sh_
                c = lerp_color((150, 60, 170), (255, 150, 200), u)
                sky.fill((*c, int(120 * k * (1 - u) ** 1.5)), (0, y, w, 3))
            stage.blit(sky, (0, 0))
            d = t - m["climax"]
            if 0 <= d < 1.0:  # 해 번쩍 (절정과 같은 1회, 0.1초 동안 차오름)
                kk = min(1.0, d / 0.1) * (1 - d) * (0.5 if self.reduce else 1.0)
                _add_circle(light, tuple(int(v * kk) for v in (255, 200, 230)), (w * 0.72, self.water_y - 6), 22)
        elif kind == "crystals":
            # 화면 가장자리에 자수정 결정이 자라남
            g = smoothstep(clamp((t - m["rise"]) / (m["climax"] - m["rise"]), 0, 1)) * k
            for i in range(int(self.uq.get("n", 12))):
                side = i % 4
                u = (i * 0.37) % 1.0
                L = (30 + 26 * ((i * 7) % 5) / 4) * g
                if side == 0:
                    base, ang = (u * w, h), -math.pi / 2 + (u - 0.5) * 0.8
                elif side == 1:
                    base, ang = (u * w, 0), math.pi / 2 + (u - 0.5) * 0.8
                elif side == 2:
                    base, ang = (0, u * h), (u - 0.5) * 0.8
                else:
                    base, ang = (w, u * h), math.pi + (u - 0.5) * 0.8
                tip = (base[0] + math.cos(ang) * L, base[1] + math.sin(ang) * L)
                px, py = -math.sin(ang) * L * 0.18, math.cos(ang) * L * 0.18
                poly = [(base[0] + px, base[1] + py), tip, (base[0] - px, base[1] - py)]
                pygame.draw.polygon(stage, lerp_color((60, 30, 90), col, 0.6), poly)
                pygame.draw.polygon(light, tuple(int(v * 0.45 * g) for v in col), poly, 1)

    def _draw_unique_front(self, stage, light) -> None:
        kind, k, col = self.uq["kind"], self._uk(), tuple(self.uq["color"])
        fx, fy = self.fish_pos()
        t, m = self.t, self.m
        if kind == "mist" and k > 0.01:
            # 보라 안개가 소용돌이치다 걷힘
            spread = 1 + smoothstep(clamp((t - m["climax"]) / 1.5, 0, 1)) * 1.6
            surf = pygame.Surface((self.w, self.h), pygame.SRCALPHA)
            for p in self.uniq:
                if p[6] != "mist":
                    continue
                a = p[7] + self.clock * 0.8
                R = 70 * spread * (0.6 + 0.4 * math.sin(p[7] * 3))
                x, y = fx + math.cos(a) * R, fy + math.sin(a) * R * 0.5
                pygame.draw.ellipse(surf, (*col, int(60 * k)), (x - 34, y - 13, 68, 26))
                pygame.draw.ellipse(light, tuple(int(v * 0.1 * k) for v in col), (x - 22, y - 8, 44, 16))
            stage.blit(surf, (0, 0))
        if kind == "echo" and k > 0.01:
            # 잔상 4겹이 하나로 모임
            conv = 1 - smoothstep(clamp((t - m["rise"]) / (m["climax"] - m["rise"]), 0, 1))
            L = self.length * self.fish_scale()
            for i in range(int(self.uq.get("n", 4))):
                a = i * math.tau / 4 + 0.6
                off = 60 * conv
                draw_fish_side(stage, fx + math.cos(a) * off, fy + math.sin(a) * off * 0.6, L, 0.0, self.colors, -1,
                               silhouette=lerp_color((50, 26, 80), col, 0.35 + 0.4 * k), shape=self.shape)
            # 절정 뒤: 잔상이 좌우로 번갈아 퍼져 나가며 사라짐 (메아리)
            if t > m["climax"]:
                for j in range(2):
                    ph = ((self.clock * 0.8) + j * 0.5) % 1.0
                    side = 1 if (int(self.clock * 0.8 + j * 0.5) + j) % 2 else -1
                    c = tuple(int(v * k * 0.4 * (1 - ph)) for v in col)
                    draw_fish_side(light, fx + side * (14 + 46 * ph), fy, L * (1 + 0.15 * ph), 0.0, self.colors, -1,
                                   silhouette=c, shape=self.shape)
        if kind == "spirits" and k > 0.01:
            for i in range(int(self.uq.get("n", 10))):
                a = self.clock * 1.4 + i * math.tau / 10
                R = 70 + 16 * math.sin(self.clock * 2 + i)
                x, y = fx + math.cos(a) * R, fy + math.sin(a) * R * 0.55 + math.sin(self.clock * 4 + i) * 4
                for r, aa in ((6, 0.2), (3, 0.4), (1, 0.6)):
                    _add_circle(light, tuple(int(v * k * aa) for v in col), (x, y), r)
        for p in self.uniq:
            kd = p[6]
            life = clamp(p[4] / p[5], 0, 1)
            x, y = p[0], p[1]
            if kd == "meteors":
                tail = 40
                c = tuple(int(v * life) for v in col)
                n = math.hypot(p[2], p[3])
                pygame.draw.line(light, c, (x, y), (x - p[2] / n * tail, y - p[3] / n * tail), 2)
                light.fill(WHITE, (int(x), int(y), 2, 2))
            elif kd == "orbs":
                a = p[7] + self.clock
                ox = math.cos(a) * 30
                for r, aa in ((7, 0.2), (4, 0.4), (2, 0.6)):
                    _add_circle(light, tuple(int(v * aa * life) for v in col), (x + ox, y), r)
            elif kd == "reeds":
                c = lerp_color((90, 90, 110), col, 0.8)
                sway = math.sin(self.clock * 6 + p[7]) * 3
                pygame.draw.line(stage, c, (x, y), (x + 14, y - 4 + sway), 1)
                pygame.draw.line(light, tuple(int(v * 0.35 * life) for v in col), (x, y), (x + 14, y - 4 + sway), 1)
                pygame.draw.circle(light, tuple(int(v * 0.6 * life) for v in col), (int(x + 14), int(y - 4 + sway)), 2)
            elif kd == "butterflies":
                flap = abs(math.sin(self.clock * 12 + p[7]))
                c = col
                pygame.draw.polygon(stage, c, [(x, y), (x - 6, y - 5 * flap - 1), (x - 5, y + 2)])
                pygame.draw.polygon(stage, c, [(x, y), (x + 6, y - 5 * flap - 1), (x + 5, y + 2)])
                light.fill(tuple(int(v * 0.6) for v in col), (int(x), int(y), 1, 2))
            elif kd == "embers":
                fl = 0.6 + 0.4 * math.sin(self.clock * 10 + p[7])
                pygame.draw.circle(light, tuple(int(v * fl * life * 0.3) for v in col), (int(x), int(y)), 3)
                light.fill(tuple(int(v * fl * life) for v in col), (int(x), int(y), 2, 2))
            elif kd == "snow":
                r = 2 + (int(p[7] * 10) % 2)
                c = tuple(int(v * 0.9) for v in col)
                pygame.draw.line(light, c, (x - r, y), (x + r, y))
                pygame.draw.line(light, c, (x, y - r), (x, y + r))

    # ── 카드 ──
    def reward_icons(self) -> list[tuple[str, tuple]]:
        n = self.news
        out = []
        if n.get("chest"):
            from src.save.treasure import grade_info
            out.append(("chest", tuple(grade_info(n["chest"])["color"])))
        if n.get("phantom_scales"):
            out.append(("scale", (200, 140, 255)))
        if n.get("blessing"):
            out.append(("bless", (200, 150, 255)))
        if n.get("phantom_gold"):
            out.append(("gold", (255, 214, 90)))
        return out

    def _draw_card(self, canvas) -> None:
        m, t = self.m, self.t
        w, h = canvas.get_size()
        k = smoothstep(clamp((t - m["card"]) / 0.4, 0, 1))
        cw, ch = int(260 * (0.4 + 0.6 * k)), int(88 * k)
        cx, cy = w // 2, int(h * 0.69)
        r = pygame.Rect(0, 0, cw, max(2, ch))
        r.center = (cx, cy)
        back = pygame.Surface(r.size, pygame.SRCALPHA)
        back.fill((18, 8, 34, int(225 * k)))
        canvas.blit(back, r.topleft)
        pulse = 0.6 + 0.4 * math.sin(self.clock * 2.5)
        pygame.draw.rect(canvas, lerp_color((90, 50, 140), (225, 170, 255), pulse), r, 2)
        pygame.draw.rect(canvas, (120, 70, 180), r.inflate(-6, -6), 1)
        if k < 0.9:
            return
        font11, font16 = get_font(11), get_font(16)
        top = font11.render("환상의 물고기", False, VIO_LIGHT)
        canvas.blit(top, (cx - top.get_width() // 2, r.y + 6))
        # 이름: 한 글자씩 빛나며
        name = self.fish["name"]
        widths = [font16.size(ch_)[0] for ch_ in name]
        x = cx - sum(widths) // 2
        for i, ch_ in enumerate(name):
            ti = m["card"] + 0.25 + i * 0.07
            if t < ti:
                break
            a = clamp((t - ti) / 0.18, 0, 1)
            glow = 1 - clamp((t - ti) / 0.5, 0, 1)
            col = lerp_color(WHITE, (240, 225, 255), 1 - glow)
            img = font16.render(ch_, False, col)
            img.set_alpha(int(255 * a))
            canvas.blit(img, (x, r.y + 20))
            x += widths[i]
        # 크기 숫자 올라감
        if t >= m["record"] - 0.4:
            u = clamp((t - (m["record"] - 0.4)) / 0.6, 0, 1)
            size = self.result["size"] * (1 - (1 - u) ** 3)
            s = font16.render(f"{size:.1f}cm", False, WHITE)
            canvas.blit(s, (cx - s.get_width() // 2, r.y + 44))
        # 첫 포획: 도감에 보라 인장 + NEW
        if self.news.get("phantom_new") and t >= m["record"]:
            u = clamp((t - m["record"]) / 0.18, 0, 1)
            sc = lerp(2.4, 1.0, u * u)
            sx, sy = r.right - 26, r.y + 26
            rad = int(15 * sc)
            pygame.draw.circle(canvas, (60, 20, 90), (sx, sy), rad)
            pygame.draw.circle(canvas, VIO, (sx, sy), rad, 2)
            g = font11.render("환", False, VIO_LIGHT)
            g = pygame.transform.scale(g, (int(g.get_width() * sc * 1.2), int(g.get_height() * sc * 1.2)))
            canvas.blit(g, g.get_rect(center=(sx, sy)))
            if u >= 1:
                nw = font11.render("NEW", False, (255, 230, 120))
                canvas.blit(nw, (sx - nw.get_width() // 2, sy + 17))
        # 보상 아이콘: 빛줄기를 따라 날아와 카드 아래 정렬
        icons = self.reward_icons()
        for i, (kind, col) in enumerate(icons):
            ti = m["rewards"] + i * 0.25
            if t < ti - 0.35:
                continue
            u = smoothstep(clamp((t - (ti - 0.35)) / 0.35, 0, 1))
            tx = cx - (len(icons) - 1) * 14 + i * 28
            ty = r.bottom + 12
            x0, y0 = tx + (i - (len(icons) - 1) / 2) * 40, h + 12
            x_ = lerp(x0, tx, u)
            y_ = lerp(y0, ty, u) - math.sin(math.pi * u) * 14
            self._icon(canvas, kind, int(x_), int(y_), col)
        lines = self.news.get("phantom_rewards", [])
        for i, ln in enumerate(lines[:2]):
            if t >= m["rewards"] + 0.3 * len(icons):
                img = font11.render(f"수집 보상: {ln}", False, (255, 214, 90))
                canvas.blit(img, (cx - img.get_width() // 2, r.y + 64 + i * 11))
        if self.waiting() and int(self.clock * 2) % 2 == 0:
            img = font11.render("클릭해서 계속", False, (190, 180, 210))
            canvas.blit(img, (cx - img.get_width() // 2, h - 14))
        elif self.can_skip() and not self.waiting():
            img = font11.render("클릭: 건너뛰기", False, (120, 110, 140))
            canvas.blit(img, (w - img.get_width() - 6, h - 14))

    def _icon(self, canvas, kind, x, y, col) -> None:
        if kind == "chest":
            canvas.fill((60, 40, 30), (x - 7, y - 4, 14, 9))
            pygame.draw.rect(canvas, col, (x - 7, y - 5, 14, 10), 1)
            canvas.fill(col, (x - 1, y - 2, 2, 3))
        elif kind == "scale":
            pygame.draw.polygon(canvas, col, [(x, y - 7), (x + 5, y), (x, y + 7), (x - 5, y)])
            pygame.draw.polygon(canvas, WHITE, [(x, y - 7), (x + 5, y), (x, y + 7), (x - 5, y)], 1)
        elif kind == "bless":
            pygame.draw.circle(canvas, (30, 16, 52), (x, y), 7)
            pygame.draw.circle(canvas, col, (x, y), 7, 1)
            pygame.draw.arc(canvas, VIO_LIGHT, (x - 4, y - 3, 8, 8), 0.3, 2.8, 1)
        else:
            pygame.draw.circle(canvas, col, (x, y), 6)
            pygame.draw.circle(canvas, (120, 90, 30), (x, y), 6, 1)

    def particle_count(self) -> int:
        return len(self.drops) + len(self.stars) + len(self.uniq)


def pick_variant(news: dict) -> str:
    """첫 포획 = full, 12종 완성 순간 = extended, 재포획 = short."""
    if news.get("phantom_new"):
        if any("환상을 낚은 자" in r for r in news.get("phantom_rewards", [])):
            return "extended"
        return "full"
    return "short"
