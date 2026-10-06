"""환상 2페이즈 진입 컷신 "이어짐 → 진짜 모습" (PHANTOM_PHASE2.md, DESIGN.md 33-12). 수치는 data/phantom/phase2_cutscene.json.

전체 버전 (그 환상어를 처음 2페이즈로 만났을 때):
  0.0~0.8  빛 덩어리가 줄을 타고 물고기 → 낚싯대 끝 → 손 (지나간 줄 0.3초 보랏빛)
  0.8      손 테두리 번쩍 0.1초 + 심장 박동
  0.8~1.2  보라 60 → 100% (화면 효과 줄이기 80%), 물속 장면이 위에서 아래로 덮임 (줄이기: 0.4초 페이드), 음악 → 물속 버전 0.3초
  1.2~2.6  물속: 그라데이션 · 수면 물결선 · 빛줄기 3 · 빛 알갱이 · 기포 · 환상어(도감 그림 2배, 몸 돌리기) · 고유 요소
  1.4~2.2  빛이 환상어로 빨려 들며 체력 게이지 50 → 100% (처음 빠르고 끝에서 느리게)
  2.2      게이지 하얗게 0.1초 + 2페이즈 마름모 켜짐 + 눈 빛남 + 종소리
  2.6~3.2  환상어가 위로 헤엄쳐 나감 → 물속 장면이 아래로 걷힘 → 실루엣 도약 (0.3배속, 줄이기: 정상 속도)
  3.2~재개 실루엣이 떨어지며 다음 마디 첫 박까지 늘림 (최대 1마디), 재개 0.6초 전 부풀어 오르는 소리, 재개 = 음악 원래 버전 0.15초
짧은 버전: 0~0.4 빛 · 0.4 손 + 심장 + 종 · 0.4~1.0 실루엣 도약 + 게이지 0.5초 · 다음 박에서 재개 (물속 · 먹먹함 없음).
건너뛰기: 0.5초 이후 탭 → 마지막 단계 (게이지 0.2초에 100%) → 다음 박에서 재개.

장면(FishingScene)은 이 객체가 내는 사건만 처리: ("sfx", 이름, 음량) · ("muffle", 켬, 초) · ("resume",).
컷신 시계는 실제 시간 (파이팅은 장면이 통째로 멈춤). 글자 · 물고기 이름 없음.
"""
import math
import random

import pygame

from src.core.config import load_json
from src.core.mathutil import clamp, lerp, lerp_color, smoothstep

SHADOW = (12, 10, 18)


def cfg() -> dict:
    return load_json("phantom/phase2_cutscene.json")


def _ease_out(u: float) -> float:
    u = clamp(u, 0.0, 1.0)
    return 1 - (1 - u) ** 3


def _ease_in(u: float) -> float:
    u = clamp(u, 0.0, 1.0)
    return u * u


def _win(t: float, a: float, b: float) -> float:
    return clamp((t - a) / max(1e-6, b - a), 0.0, 1.0)


def _c(v) -> tuple:
    return tuple(int(x) for x in v)


class Phase2Cine:
    def __init__(self, fish: dict, full: bool, reduce: bool, level: int, hp_from: float, size,
                 wait_fn=None, seed: int | None = None):
        """wait_fn(kind, lead) → 지금부터 lead 초 뒤 이후 첫 'bar'/'beat' 까지 초 (곡이 없으면 None)."""
        self.c = cfg()
        self.fish = fish
        self.fc = self.c["fish"].get(fish.get("id"), {"unique": "spirits", "eye": [-0.4, -0.05]})
        self.full = full
        self.reduce = reduce
        self.level = level
        self.hp_from = clamp(hp_from, 0.0, 1.0)
        self.w, self.h = size
        self.wait_fn = wait_fn
        self.t = 0.0
        self.skipped = False
        self.skip_t = 0.0
        self.skip_g0 = 0.0
        self.skip_cover = 0.0
        self.resume_at: float | None = None
        self.resumed = False
        self.resume_t = 0.0
        self.finished = False
        self.full_hit_t: float | None = None    # 게이지 100% 도달 (컷신 시각)
        self.fired: set = set()
        self.rng = random.Random(seed if seed is not None else hash(fish.get("id", "")) & 0xFFFF)
        cap = self.c["particles"][("low", "medium", "high")[max(0, min(2, level))]]
        r = self.rng
        self.parts = [(r.uniform(0, self.w), r.uniform(14, self.h), r.uniform(4, 11), r.uniform(0, 6.28),
                       r.uniform(0, 0.3)) for _ in range(cap)]
        self.drops: list = []        # 물방울 [x, y, vx, vy, 수명, 최대]
        self.ripples: list = []      # 물결 고리 [x, y, 나이]
        self.sparks: list = []       # 게이지 끝 반짝임 [x, y, vy, 나이]
        self.spark_acc = 0.0
        self.splashed = set()
        self.jump_d: float | None = None
        self._grad = None
        self._ray = None
        self._lut = [smoothstep(i / 64) for i in range(65)]
        self.base_pos = None         # 물고기 화면 위치 (도약 자리)

    # ── 시간표 ──
    @property
    def blocking(self) -> bool:
        """파이팅 정지 · 입력 무시 중."""
        return not self.resumed

    def can_skip(self) -> bool:
        return not self.resumed and not self.skipped and self.t >= self.c["skip_after"]

    def _orb_sec(self) -> float:
        return self.c["full" if self.full else "short"]["orb_sec"]

    def _heal_win(self) -> tuple:
        return tuple(self.c["full" if self.full else "short"]["heal"])

    def skip(self) -> None:
        if not self.can_skip():
            return
        self.skipped = True
        self.skip_t = self.t
        self.skip_g0 = self.gauge_value()
        self.skip_cover = self._cover_amount()
        sec = self.c["skip_heal_sec"]
        w = self.wait_fn("beat", sec) if self.wait_fn else None
        self.resume_at = self.t + (w if w is not None else sec)
        self.jump_d = None

    def update(self, dt: float) -> list:
        """dt = 실제 시간. 돌려주는 값 = 사건 목록."""
        ev = []
        if self.finished:
            return ev
        prev, self.t = self.t, self.t + dt
        t = self.t
        F = self.c["full"]

        def at(name, when, *e):
            if prev < when <= t and name not in self.fired:
                self.fired.add(name)
                ev.append(e)

        if not self.resumed and not self.skipped:
            if self.full:
                at("rise", 0.0001, "sfx", "sfx_p2_rise", 0.7)
                at("heart", F["orb_sec"], "sfx", "sfx_p2_heart", 0.9)
                at("muffle", F["dive"][0], "muffle", True, self.c["music"]["to_muffled_sec"])
                at("sub", F["dive"][0] + 0.1, "sfx", "sfx_p2_submerge", 0.7)
                at("uw", F["underwater"][0], "sfx", "sfx_p2_underwater", 0.35)
                at("arp", F["heal"][0], "sfx", "sfx_p2_arp", 0.5)
                at("bell", F["heal"][1], "sfx", "sfx_phantom_icon0", 0.8)
                at("breach", F["rise"][0] + 0.25, "sfx", "sfx_p2_breach", 0.75)
                if self.resume_at is None and t >= F["rise"][0]:
                    # 재개 = 3.2초 이후 첫 마디 첫 박 (최대 1마디) — 부풀어 오르는 소리를 0.6초 앞에 둘 수 있게 미리 정함
                    lead = F["rise"][1] - t
                    w = self.wait_fn("bar", lead) if self.wait_fn else None
                    self.resume_at = t + (w if w is not None else lead + 0.4)
                if self.resume_at is not None and t >= self.resume_at - F["swell_before"] and "swell" not in self.fired:
                    self.fired.add("swell")   # 재개 0.6초 전부터 거꾸로 부풀어 오르는 소리
                    ev.append(("sfx", "sfx_p2_swell", 0.7))
            else:
                S = self.c["short"]
                at("rise", 0.0001, "sfx", "sfx_p2_rise", 0.5)
                at("heart", S["orb_sec"], "sfx", "sfx_p2_heart", 0.9)
                at("bell", S["orb_sec"] + 0.02, "sfx", "sfx_phantom_icon0", 0.7)
                at("splash", S["jump"][0] + 0.12, "sfx", "sfx_p2_breach", 0.45)
                if self.resume_at is None and t >= S["jump"][1]:
                    w = self.wait_fn("beat", 0.0) if self.wait_fn else None
                    self.resume_at = t + (w if w is not None else 0.0)
        if self.full_hit_t is None and self._gauge_done():
            self.full_hit_t = t
            if self.skipped and "bell" not in self.fired:
                self.fired.add("bell")
                ev.append(("sfx", "sfx_phantom_icon0", 0.7))
        if not self.resumed and self.resume_at is not None and t + dt * 0.5 >= self.resume_at:   # 가장 가까운 틱
            self.resumed = True
            self.resume_t = t
            ev.append(("muffle", False, self.c["music"]["back_sec"]))
            ev.append(("resume",))
        if self.resumed and t - self.resume_t >= max(self.c["k"]["back_sec"], 0.6):
            self.finished = True
        self._update_bits(dt)
        return ev

    # ── 값 ──
    def gauge_value(self) -> float:
        """연출 게이지 (실제 체력은 재개 순간에 100%로 확정)."""
        if self.skipped:
            return lerp(self.skip_g0, 1.0, _ease_out((self.t - self.skip_t) / self.c["skip_heal_sec"]))
        a, b = self._heal_win()
        return lerp(self.hp_from, 1.0, _ease_out(_win(self.t, a, b)))

    def _gauge_done(self) -> bool:
        if self.skipped:
            return self.t >= self.skip_t + self.c["skip_heal_sec"]
        return self.t >= self._heal_win()[1]

    def k(self) -> float | None:
        """보라 강도 (None = 컷신이 잡지 않음)."""
        if not self.full:
            return None
        K = self.c["k"]
        peak = K["reduce_peak"] if self.reduce else K["peak"]
        d0, d1 = self.c["full"]["dive"]
        if self.resumed:
            from_k = self._k_at(self.resume_t, peak)
            return lerp(from_k, K["fight"], smoothstep(_win(self.t, self.resume_t, self.resume_t + K["back_sec"])))
        return self._k_at(self.t, peak)

    def _k_at(self, t: float, peak: float) -> float:
        K = self.c["k"]
        d0, d1 = self.c["full"]["dive"]
        if self.skipped and self.skip_t < d0:
            return K["fight"]
        return lerp(K["fight"], peak, smoothstep(_win(min(t, self.skip_t if self.skipped else t), d0, d1)))

    def hand_alpha(self) -> float:
        """손 테두리 번쩍 (0.1초)."""
        o = self._orb_sec()
        if self.skipped and self.skip_t < o:
            return 0.0
        return 1.0 if o <= self.t < o + self.c["full"]["hand_flash_sec"] else 0.0

    def _cover_amount(self) -> float:
        """물속 장면이 화면을 덮은 정도 0~1 (건너뛰기 순간 값 기록용)."""
        if not self.full:
            return 0.0
        F = self.c["full"]
        t = self.t
        if t < F["dive"][0]:
            return 0.0
        if t < F["dive"][1]:
            return smoothstep(_win(t, *F["dive"]))
        return 1.0 - smoothstep(_win(t, F["rise"][0] + 0.15, F["rise"][0] + 0.45))

    # ── 입자 ──
    def _update_bits(self, dt: float) -> None:
        js = self._jump_speed()
        for d in self.drops:
            d[0] += d[2] * dt * js
            d[1] += d[3] * dt * js
            d[3] += 260 * dt * js
            d[4] += dt * js
        self.drops = [d for d in self.drops if d[4] < d[5]]
        for r in self.ripples:
            r[2] += dt
        self.ripples = [r for r in self.ripples if r[2] < 0.9]
        for s in self.sparks:
            s[1] += s[2] * dt
            s[3] += dt
        self.sparks = [s for s in self.sparks if s[3] < 0.3]
        g = self.gauge_value()
        if not self._gauge_done() and (self.skipped or _win(self.t, *self._heal_win()) > 0):
            self.spark_acc += dt
            G = self.c["gauge"]
            while self.spark_acc >= 0.05:
                self.spark_acc -= 0.05
                x = (self.w - G["w"]) // 2 + G["w"] * g
                self.sparks.append([x + self.rng.uniform(-1, 1), G["y"] + self.rng.uniform(0, G["h"]),
                                    self.rng.uniform(-40, -15), 0.0])

    def _jump_speed(self) -> float:
        """도약 슬로모션 배율 (전체 버전 · 효과 줄이기 아님)."""
        if self.full and not self.reduce and not self.skipped and self.t >= self.c["full"]["rise"][0]:
            return 0.45   # 물방울도 도약과 같은 느린 시간
        return 1.0

    def _burst(self, x: float, y: float, n: int, up: float) -> None:
        n = max(3, int(n * (0.4, 0.7, 1.0)[max(0, min(2, self.level))]))
        r = self.rng
        for _ in range(n):
            a = r.uniform(math.pi * 1.1, math.pi * 1.9)
            sp = r.uniform(40, 110) * up
            self.drops.append([x + r.uniform(-6, 6), y, math.cos(a) * sp, math.sin(a) * sp, 0.0, r.uniform(0.5, 0.9)])

    # ── 그리기: 빛 덩어리 (세계 위, HUD 아래) ──
    def draw_line_orb(self, canvas, line_pts, geo) -> None:
        """line_pts = 낚싯대 끝 → 물고기 (draw_line 이 돌려준 점), geo = 낚싯대 모양 (손 · 끝)."""
        o = self._orb_sec()
        glow = self.c["full"]["line_glow_sec"]
        if self.t > o + glow + 0.05 or (self.skipped and self.skip_t < o and self.t > self.skip_t + glow):
            return
        path = list(reversed(line_pts or [])) or [geo["tip"]]
        hand, ctrl, tip = geo["hand"], geo["ctrl"], geo["tip"]
        for i in range(1, 9):   # 낚싯대 끝 → 손 (대의 휜 모양)
            u = i / 8
            a, b, c = u * u, 2 * (1 - u) * u, (1 - u) ** 2
            path.append((a * hand[0] + b * ctrl[0] + c * tip[0], a * hand[1] + b * ctrl[1] + c * tip[1]))
        cum = [0.0]
        for p, q in zip(path, path[1:]):
            cum.append(cum[-1] + math.hypot(q[0] - p[0], q[1] - p[1]))
        total = max(1.0, cum[-1])
        rim, light = _c(self.c["colors"]["rim"]), _c(self.c["colors"]["light"])
        tnow = self.t if not (self.skipped and self.skip_t < o) else self.skip_t
        layer = pygame.Surface(canvas.get_size(), pygame.SRCALPHA)
        for i in range(1, len(path)):
            ta = o * self._inv(cum[i] / total)
            if ta > tnow:
                break
            a = 1.0 - (self.t - ta) / glow
            if a <= 0:
                continue
            col = (*lerp_color(rim, light, a * 0.5), int(230 * a))
            pygame.draw.line(layer, col, path[i - 1], path[i], 2 if a > 0.5 else 1)
        canvas.blit(layer, (0, 0))
        if tnow < o:
            s = total * smoothstep(tnow / o)
            j = next((i for i in range(1, len(cum)) if cum[i] >= s), len(cum) - 1)
            p, q = path[j - 1], path[j]
            u = (s - cum[j - 1]) / max(1e-6, cum[j] - cum[j - 1])
            x, y = lerp(p[0], q[0], u), lerp(p[1], q[1], u)
            d = self.c["full"]["orb_d"]
            halo = pygame.Surface((d * 3, d * 3), pygame.SRCALPHA)
            pygame.draw.circle(halo, (*rim, 70), (d * 3 // 2, d * 3 // 2), d * 3 // 2)
            canvas.blit(halo, (int(x) - d * 3 // 2, int(y) - d * 3 // 2))
            pygame.draw.circle(canvas, rim, (int(x), int(y)), d // 2)
            pygame.draw.circle(canvas, light, (int(x), int(y)), d // 2 - 1)

    def _inv(self, f: float) -> float:
        """smoothstep 역함수 (표)."""
        lut = self._lut
        for i in range(1, 65):
            if lut[i] >= f:
                a, b = lut[i - 1], lut[i]
                return (i - 1 + (f - a) / max(1e-6, b - a)) / 64
        return 1.0

    # ── 그리기: 물속 · 도약 · 게이지 (맨 위) ──
    def draw_top(self, canvas, fish_pos, rim_color=None) -> None:
        w, h = canvas.get_size()
        self.w, self.h = w, h
        if self.base_pos is None:
            self.base_pos = fish_pos
        if self.full:
            cov = self._cover_amount()
            if self.skipped:
                cov = self.skip_cover * (1 - _win(self.t, self.skip_t, self.skip_t + 0.15))
            if cov > 0.001:
                uw = self._underwater(w, h)
                F = self.c["full"]
                rising = self.t >= F["rise"][0] and not self.skipped
                if self.reduce or self.skipped:
                    uw.set_alpha(int(255 * cov))
                    canvas.blit(uw, (0, 0))
                elif not rising:     # 위에서 아래로 덮임 (시점이 수면을 뚫고 내려감)
                    hc = int(h * cov)
                    canvas.blit(uw, (0, 0), (0, 0, w, hc))
                    self._edge(canvas, hc)
                else:                # 아래로 걷힘 (시점이 수면 위로 솟구침)
                    y0 = int(h * (1 - cov))
                    canvas.blit(uw, (0, y0), (0, y0, w, h - y0))
                    self._edge(canvas, y0)
        self._draw_jump(canvas)
        self._draw_gauge(canvas)

    def _edge(self, canvas, y: int) -> None:
        """덮이는 경계 = 수면을 뚫는 밝은 물결선."""
        if y <= 0 or y >= canvas.get_height():
            return
        rim, light = _c(self.c["colors"]["rim"]), _c(self.c["colors"]["light"])
        w = canvas.get_width()
        pts = [(x, y + 2 * math.sin(x * 0.08 + self.t * 9)) for x in range(0, w + 8, 8)]
        pygame.draw.lines(canvas, rim, False, pts, 2)
        pygame.draw.lines(canvas, light, False, [(x, yy - 1) for x, yy in pts], 1)

    def _bg(self, w: int, h: int) -> pygame.Surface:
        if self._grad is None or self._grad.get_size() != (w, h):
            top, bot = _c(self.c["colors"]["bg_top"]), _c(self.c["colors"]["bg_bottom"])
            g = pygame.Surface((w, h))
            for y in range(h):
                g.fill(lerp_color(top, bot, y / max(1, h - 1)), (0, y, w, 1))
            self._grad = g
            self._uw = pygame.Surface((w, h))
        return self._grad

    def fish_center(self, w: int, h: int) -> tuple:
        F = self.c["full"]
        bob = 2 * math.sin(self.t * math.pi)          # 2px, 주기 2초
        x, y = w / 2, h / 2 + 6 + bob
        u = _win(self.t, F["rise"][0] + 0.05, F["rise"][0] + 0.4)
        return x, y - (h / 2 + 90) * _ease_in(u)

    def _turn(self) -> float:
        a, b = self.c["full"]["turn"]
        return math.cos(math.pi * _win(self.t, a, b))   # 가로 크기 1 → 0 → -1

    def _underwater(self, w: int, h: int) -> pygame.Surface:
        bg = self._bg(w, h)
        uw = self._uw
        uw.blit(bg, (0, 0))
        t = self.t
        F = self.c["full"]
        light, rim = _c(self.c["colors"]["light"]), _c(self.c["colors"]["rim"])
        fx, fy = self.fish_center(w, h)
        hk = _ease_out(_win(t, *F["heal"]))   # 빨려 드는 정도
        uq = self.fc.get("unique")
        self._unique(uw, uq, "back", fx, fy)
        # 빛줄기 3개 (더하기 합성 15%, 천천히 흔들림, 회복 때 환상어 쪽으로 기울어짐)
        ray = self._ray
        if ray is None or ray.get_size() != (w, h):
            ray = self._ray = pygame.Surface((w, h))
        ray.fill((0, 0, 0))
        rc = tuple(int(c * 0.15) for c in light)
        for i, bx in enumerate((0.26, 0.52, 0.78)):
            sway = 10 * math.sin(t * 0.7 + i * 2.1)
            x0 = w * bx + sway
            x1 = lerp(x0 - 70, fx + (i - 1) * 14, hk)
            y1 = lerp(h, fy, hk * 0.6)
            pygame.draw.polygon(ray, rc, [(x0 - 7, 0), (x0 + 7, 0), (x1 + 22 - 10 * hk, y1), (x1 - 22 + 10 * hk, y1)])
        uw.blit(ray, (0, 0), special_flags=pygame.BLEND_RGB_ADD)
        # 빛 알갱이 (1px, 천천히 떠오름 → 회복 동안 환상어 가운데로 모여 사라짐)
        h0, h1 = F["heal"]
        for (x0, y0, sp, ph, dl) in self.parts:
            def drift(tt):
                yy = (y0 - sp * tt) % (h - 14) + 14
                return x0 + 3 * math.sin(tt * 0.9 + ph), yy
            if t < h0 + dl:
                x, y = drift(t)
                a = 1.0
            else:
                u = _win(t, h0 + dl, h1)
                if u >= 1:
                    continue
                sx, sy = drift(h0 + dl)
                e = _ease_in(u)
                x, y = lerp(sx, fx, e), lerp(sy, fy, e)
                a = 1 - u * u
            col = lerp_color(_c(self.c["colors"]["bg_top"]), light, 0.35 + 0.65 * a * (0.7 + 0.3 * math.sin(t * 5 + ph)))
            uw.fill(col, (int(x), int(y), 1, 1))
        # 기포 (환상어 주변 4개)
        for i in range(4):
            per = 1.6 + i * 0.3
            u = ((t + i * 0.45) % per) / per
            bx = fx + (-38, -14, 22, 44)[i] + 2 * math.sin(t * 3 + i)
            by = fy + 18 - 70 * u
            pygame.draw.circle(uw, lerp_color(rim, light, 0.5), (int(bx), int(by)), 1 + (i % 2), 1)
        self._draw_fish(uw, fx, fy)
        self._unique(uw, uq, "front", fx, fy)
        # 수면 (맨 위 12px 일렁이는 밝은 물결선, #B48CF0 50%)
        top = pygame.Surface((w, 14), pygame.SRCALPHA)
        line_col = _c(self.c["colors"]["dusk"][0]) if uq == "dusk" else rim
        pts = [(x, 6 + 2.5 * math.sin(x * 0.06 + t * 2.2) + 1.5 * math.sin(x * 0.13 - t * 1.3)) for x in range(0, w + 6, 6)]
        pygame.draw.polygon(top, (*line_col, 50), [(0, 0)] + pts + [(w, 0)])
        pygame.draw.lines(top, (*line_col, 128), False, pts, 2)
        uw.blit(top, (0, 0))
        if uq in ("moon", "aurora"):
            self._unique(uw, uq, "sky", fx, fy)
        return uw

    def _fish_surface(self, L: float, silhouette=None, rim=None) -> pygame.Surface:
        from src.render.fish_draw import draw_fish_side, fish_colors, fish_shape
        sw, sh = int(L * 1.35), int(L * 0.95)
        s = pygame.Surface((sw, sh), pygame.SRCALPHA)
        draw_fish_side(s, sw / 2, sh / 2, L, 0.0, fish_colors(self.fish), facing=-1, silhouette=silhouette,
                       tail_wag=0.5, shape=fish_shape(self.fish))
        if rim is not None:   # 보랏빛 테두리 1px (바깥)
            m = pygame.mask.from_surface(s)
            out = pygame.Surface((sw, sh), pygame.SRCALPHA)
            g = m.to_surface(setcolor=(*rim, 255), unsetcolor=(0, 0, 0, 0))
            for d in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                out.blit(g, d)
            out.blit(s, (0, 0))
            s = out
        return s

    def _draw_fish(self, surf, fx: float, fy: float) -> None:
        F = self.c["full"]
        L = 104
        rim, light = _c(self.c["colors"]["rim"]), _c(self.c["colors"]["light"])
        base = self._fish_surface(L, rim=rim)
        sx = self._turn()
        ang = 90 * smoothstep(_win(self.t, F["rise"][0], F["rise"][0] + 0.15))   # 머리를 위로 (돈 뒤엔 머리가 오른쪽)

        def place(img, cx, cy, alpha=255):
            if alpha < 255:
                img = img.copy()
                img.set_alpha(alpha)
            surf.blit(img, (int(cx - img.get_width() / 2), int(cy - img.get_height() / 2)))

        sw = max(1, int(base.get_width() * abs(sx)))
        img = pygame.transform.scale(base, (sw, base.get_height()))
        if sx < 0:
            img = pygame.transform.flip(img, True, False)
        if ang > 0.5:
            img = pygame.transform.rotate(img, ang)
        if self.fc.get("unique") == "echoes":   # 4마리로 겹쳐 보였다가 몸을 돌릴 때 하나로
            k = 1 - _win(self.t, *F["turn"])
            if k > 0.01:
                for ox, oy in ((-26, -10), (24, -6), (-18, 12), (28, 10)):
                    place(img, fx + ox * k, fy + oy * k, int(90 * k))
        place(img, fx, fy)
        # 눈 빛남 (2px, 0 → 100% → 60%, 0.4초)
        e0, e1 = F["eye"]
        if self.t >= e0:
            a = _win(self.t, e0, e0 + 0.1) if self.t < e0 + 0.1 else 1 - 0.4 * _win(self.t, e0 + 0.1, e1)
            ex, ey = self.fc["eye"]
            lx, ly = L * ex * sx, L * ey
            th = math.radians(ang)
            px = fx + lx * math.cos(th) + ly * math.sin(th)
            py = fy - lx * math.sin(th) + ly * math.cos(th)
            halo = pygame.Surface((9, 9), pygame.SRCALPHA)
            pygame.draw.circle(halo, (*light, int(110 * a)), (4, 4), 4)
            surf.blit(halo, (int(px) - 4, int(py) - 4))
            surf.fill(lerp_color(_c(self.c["colors"]["bg_top"]), light, a), (int(px) - 1, int(py) - 1, 2, 2))

    # ── 환상어별 고유 요소 ──
    def _unique(self, s, kind: str, layer: str, fx: float, fy: float) -> None:
        t, w, h = self.t, s.get_width(), s.get_height()
        light, rim = _c(self.c["colors"]["light"]), _c(self.c["colors"]["rim"])
        lay = pygame.Surface((w, h), pygame.SRCALPHA)
        drew = False
        if kind == "moon" and layer == "sky":
            mx = int(w * 0.68)
            pygame.draw.circle(lay, (*light, 60), (mx, 3), 14)
            pygame.draw.circle(lay, (*light, 210), (mx, 3), 9)
            drew = True
        elif kind == "moon" and layer == "back":
            mx = w * 0.68
            beam = pygame.Surface((w, h))
            beam.fill((0, 0, 0))
            pygame.draw.polygon(beam, tuple(int(c * 0.13) for c in light),
                                [(mx - 7, 8), (mx + 7, 8), (fx + 26, fy + 6), (fx - 26, fy + 6)])
            s.blit(beam, (0, 0), special_flags=pygame.BLEND_RGB_ADD)
        elif kind == "mist":
            for i in range(7):
                a = i / 7 * math.tau + t * 0.5
                front = math.sin(a) > 0
                if front != (layer == "front"):
                    continue
                cx, cy = fx + 78 * math.cos(a), fy + 26 * math.sin(a)
                pygame.draw.ellipse(lay, (200, 170, 240, 46), (cx - 18, cy - 6, 36, 12))
                drew = True
        elif kind == "dusk" and layer == "back":
            c0, c1 = _c(self.c["colors"]["dusk"][0]), _c(self.c["colors"]["dusk"][1])
            band = int(h * 0.38)
            for y in range(0, band, 2):
                u = y / band
                lay.fill((*lerp_color(c0, c1, u), int(150 * (1 - u))), (0, y, w, 2))
            drew = True
        elif kind == "meteors" and layer == "back":
            for i, st in enumerate((1.25, 1.6, 1.95)):
                u = _win(t, st, st + 0.7)
                if 0 < u < 1:
                    x0 = w * (0.62 + 0.13 * i)
                    hx, hy = x0 - 110 * u, -6 + h * 0.62 * u
                    for j in range(6):
                        tx, ty = hx + j * 4.5, hy - j * 4.5 * h * 0.62 / 110
                        pygame.draw.circle(lay, (*lerp_color(light, rim, j / 6), int(220 * (1 - j / 6))), (int(tx), int(ty)), 1)
                    pygame.draw.circle(lay, (*light, 255), (int(hx), int(hy)), 2)
                    drew = True
        elif kind == "lanterns" and layer == "back":
            for i, (lx, ly) in enumerate(((0.14, 0.9), (0.31, 0.84), (0.55, 0.92), (0.72, 0.86), (0.88, 0.9))):
                a = _win(t, 1.3 + 0.2 * i, 1.45 + 0.2 * i)
                if a <= 0:
                    continue
                a *= 0.85 + 0.15 * math.sin(t * 6 + i)
                x, y = int(w * lx), int(h * ly)
                pygame.draw.circle(lay, (*rim, int(70 * a)), (x, y), 7)
                pygame.draw.circle(lay, (*light, int(230 * a)), (x, y), 2)
                drew = True
        elif kind == "reeds" and layer == "back":
            for i in range(8):
                bx = w * (0.06 + i * 0.125)
                hh = 60 + (i * 37) % 55
                pts = []
                for j in range(5):
                    u = j / 4
                    pts.append((bx + math.sin(t * 1.5 + i) * 7 * u * u, h - hh * u))
                pygame.draw.lines(lay, (150, 100, 210, 190), False, pts, 2)
                tx, ty = pts[-1]
                pygame.draw.line(lay, (190, 140, 240, 200), (tx, ty), (tx + 4, ty - 6), 1)
            drew = True
        elif kind == "crystals" and layer == "back":
            for i, (cx, ch, cw) in enumerate(((0.2, 46, 9), (0.36, 30, 7), (0.66, 54, 10), (0.82, 36, 8))):
                g = smoothstep(_win(t, 1.3 + 0.15 * i, 2.0 + 0.15 * i))
                if g <= 0:
                    continue
                x, hh = w * cx, ch * g
                body = [(x - cw / 2, h), (x - cw / 2, h - hh * 0.75), (x, h - hh), (x + cw / 2, h - hh * 0.75), (x + cw / 2, h)]
                pygame.draw.polygon(lay, (150, 90, 220, 235), body)
                pygame.draw.polygon(lay, (210, 170, 255, 235), [(x, h - hh), (x + cw / 2, h - hh * 0.75), (x + 1, h)])
                pygame.draw.lines(lay, (*light, 220), False, body[1:4], 1)
            drew = True
        elif kind == "butterflies":
            for i in range(6):
                a = i / 6 * math.tau + t * 0.9
                front = math.sin(a) > 0
                if front != (layer == "front"):
                    continue
                cx, cy = fx + 82 * math.cos(a), fy + 34 * math.sin(a) - 6
                f = abs(math.sin(t * 12 + i)) * 4 + 1
                col = (*lerp_color(light, rim, 0.3), 220)
                pygame.draw.polygon(lay, col, [(cx, cy), (cx - f, cy - 4), (cx - f, cy + 2)])
                pygame.draw.polygon(lay, col, [(cx, cy), (cx + f, cy - 4), (cx + f, cy + 2)])
                drew = True
        elif kind == "embers" and layer == "front":
            for i in range(12):
                per = 2.2 + (i % 4) * 0.4
                u = ((t + i * 0.37) % per) / per
                x = w * ((i * 0.083 + 0.04) % 1) + 6 * math.sin(t * 2 + i)
                y = h + 4 - (h * 0.75) * u
                a = (1 - u) * (0.6 + 0.4 * math.sin(t * 14 + i * 3))
                lay.fill((*lerp_color((200, 120, 255), light, 0.35), int(255 * clamp(a, 0, 1))), (int(x), int(y), 2, 2))
            drew = True
        elif kind == "aurora" and layer == "sky":
            for x in range(0, w, 2):
                a = 0.5 + 0.5 * math.sin(x * 0.045 + t * 1.6) * math.sin(x * 0.017 - t * 0.7)
                col = lerp_color((140, 90, 216), (120, 220, 210), 0.5 + 0.5 * math.sin(x * 0.02 + t))
                hh = 10 + 14 * a
                lay.fill((*col, int(60 + 120 * a)), (x, 0, 2, int(hh)))
            lay.fill((214, 224, 255, 45), (0, 0, w, 12))           # 얼음 (반투명)
            for i in range(5):
                x = w * (0.1 + i * 0.2)
                pygame.draw.line(lay, (235, 240, 255, 120), (x, 0), (x + 9, 11), 1)
            drew = True
        elif kind == "spirits":
            for i in range(7):
                a = i / 7 * math.tau + t * 1.2
                front = math.sin(a) > 0
                if front != (layer == "front"):
                    continue
                for j in range(3):
                    aa = a - j * 0.09
                    x, y = fx + 60 * math.cos(aa), fy + 30 * math.sin(aa)
                    pygame.draw.circle(lay, (*light, int(200 * (1 - j / 3))), (int(x), int(y)), 2 if j == 0 else 1)
                pygame.draw.circle(lay, (*rim, 60), (int(fx + 60 * math.cos(a)), int(fy + 30 * math.sin(a))), 4)
                drew = True
        if drew:
            s.blit(lay, (0, 0))

    # ── 도약 실루엣 (수면 위) ──
    def _jump_win(self) -> tuple | None:
        if self.skipped:
            return None
        if self.full:
            j0 = self.c["full"]["rise"][0] + 0.3
            if self.reduce:
                return j0, 0.8
            if self.jump_d is None and self.resume_at is not None:
                self.jump_d = max(0.8, self.resume_at - j0)   # 0.3배속 느낌 · 재개(마디 첫 박)에 물로 떨어짐
            return j0, self.jump_d or 0.8 / self.c["full"]["jump_speed"]
        a, b = self.c["short"]["jump"]
        return a, b - a

    def _draw_jump(self, canvas) -> None:
        win = self._jump_win()
        if win is not None and self.base_pos is not None:
            j0, d = win
            bx, by = self.base_pos
            if j0 <= self.t:
                u = _win(self.t, j0, j0 + d)
                if "launch" not in self.splashed:
                    self.splashed.add("launch")
                    self._burst(bx, by, 16, 1.0)
                    self.ripples.append([bx, by, 0.0])
                if u >= 1 and "land" not in self.splashed:
                    self.splashed.add("land")
                    self._burst(bx + 30 * self._jdir(), by, 12, 0.8)
                    self.ripples.append([bx + 30 * self._jdir(), by, 0.0])
                if u < 1:
                    H = min(80.0, max(30.0, by - 40))
                    x = bx + 30 * self._jdir() * u
                    y = by - 4 * H * u * (1 - u)
                    L = 64
                    img = self._sil_cache()
                    if self._jdir() > 0:
                        img = pygame.transform.flip(img, True, False)
                    ang = lerp(55, -60, u) * (1 if self._jdir() > 0 else -1)
                    img = pygame.transform.rotate(img, ang)
                    canvas.blit(img, (int(x - img.get_width() / 2), int(y - img.get_height() / 2 - L * 0.1)))
        light, rim = _c(self.c["colors"]["light"]), _c(self.c["colors"]["rim"])
        for x, y, age in self.ripples:
            k = age / 0.9
            rw, rh = 6 + 34 * k, 2 + 6 * k
            pygame.draw.ellipse(canvas, lerp_color(rim, light, 1 - k), (x - rw, y - rh, rw * 2, rh * 2), 1)
        for d in self.drops:
            a = 1 - d[4] / d[5]
            canvas.fill(lerp_color(rim, light, a), (int(d[0]), int(d[1]), 2 if a > 0.6 else 1, 2 if a > 0.6 else 1))

    def _jdir(self) -> int:
        return -1 if (self.base_pos or (self.w / 2, 0))[0] > self.w / 2 else 1   # 화면 가운데 쪽으로 뛴다

    def _sil_cache(self) -> pygame.Surface:
        s = getattr(self, "_sil", None)
        if s is None:
            s = self._sil = self._fish_surface(64, silhouette=(36, 18, 64), rim=_c(self.c["colors"]["rim"]))
        return s

    # ── 체력 게이지 (기존 자리 · 맨 앞) ──
    def _draw_gauge(self, canvas) -> None:
        from src.ui.fight_hud import RARITY_COLOR
        G = self.c["gauge"]
        w = canvas.get_width()
        bw, bh, y = G["w"], G["h"], G["y"]
        x = (w - bw) // 2
        rim, light = _c(self.c["colors"]["rim"]), _c(self.c["colors"]["light"])
        g = self.gauge_value()
        flash = self.full_hit_t is not None and self.t - self.full_hit_t < G["flash_sec"]
        lit2 = self.full_hit_t is not None
        for i in range(2):   # 페이즈 마름모 (2번째 = 100% 도달 때 켜짐)
            cx, cy = x + bw // 2 - 6 + i * 12, y + 13
            col = (190, 120, 255) if (i == 0 or lit2) else (80, 70, 50)
            pygame.draw.polygon(canvas, col, [(cx, cy - 3), (cx + 3, cy), (cx, cy + 3), (cx - 3, cy)])
        canvas.fill(SHADOW, (x - 1, y - 1, bw + 2, bh + 2))
        canvas.fill((50, 30, 36), (x, y, bw, bh))
        fw = int(bw * g)
        if flash:
            canvas.fill((255, 255, 255), (x, y, fw, bh))
        else:
            canvas.fill(rim, (x, y, fw, bh))
            canvas.fill(lerp_color(rim, light, 0.6), (x, y, fw, 1))
            tp = G["tip_px"]
            if fw > tp:
                canvas.fill(light, (x + fw - tp, y, tp, bh))
        pygame.draw.rect(canvas, RARITY_COLOR.get("phantom", rim), (x - 2, y - 2, bw + 4, bh + 4), 1)
        for sx, sy, _, age in self.sparks:
            a = 1 - age / 0.3
            canvas.fill(lerp_color(rim, light, a), (int(sx), int(sy), 1, 1))
