"""환상 2페이즈 진입 컷신 개정판 "어둠 속의 그것 → 각성" (PHANTOM_PHASE2.md, DESIGN.md 33-12). 수치는 data/phantom/phase2_cutscene.json.

전체 버전 (그 환상어를 처음 2페이즈로 만났을 때, 약 8~10초):
  A 0.0~2.6  수면 아래로: 고개 숙임(손 · 낚싯대가 아래로 빠짐) → 수면에 다가감 → 수면 경계선이 아래에서 위로 지나감
             (1.4초 '꼬르륵' + 음악 0.5초에 물속 버전) → 물속에서 계속 가라앉음 (점점 어두워짐)
  B 2.6~4.0  어둠 속의 그것: 눈 높이 위쪽이 완전히 어둠에 가린 환상어가 아래에서 드러남 (회전 없음), 고유 요소가 보이기 시작
  C 4.0~5.6  기를 모음: 빛 알갱이 · 빛줄기 · 고유 요소가 빨려 듦, 오므라드는 고리 3번 (0.6 → 0.45 → 0.3초 간격),
             5.0초부터 부풀어 오르는 소리 — 폭발이 다음 마디 첫 박에 떨어지도록 최대 1마디 늘림
  D (1.5초)  솟구쳐 수면을 뚫음(0.3) → 마디 첫 박에 찌 자리에서 보랏빛 폭발 (고리 · 빛줄기 · 번쩍 1번, 음악 0.15초에 원래 버전)
             → 체력 바 2페이즈 모습으로 → 체력 50 → 100% (1.2초) → 반짝 + 종
  E (1.0초)  빛이 사그라듦, 보라 100 → 60%, 뒷배경 보랏빛 오라가 남음 → 재개 (1초 유예)
짧은 버전 (두 번째부터): 같은 흐름을 짧게 (폭발은 다음 '박'). 건너뛰기: 1초 이후 탭 → 바로 D (D · E 는 반드시 재생).
흔들림: 0 → 0.5 → 1 → 2 → 4px(폭발) → 0, 정수 픽셀 초당 20번, 게임 장면만 (체력 바 · HUD 는 흔들지 않음).

장면(FishingScene)은 이 객체가 내는 사건만 처리: ("sfx", 이름, 음량) · ("muffle", 켬, 초) · ("resume",).
그림: compose() = HUD 전에 게임 장면을 카메라 · 물속 · 폭발 · 흔들림으로 바꿔 그림 / draw_top() = HUD 위 체력 바 (D · E).
컷신 시계는 실제 시간 (파이팅은 장면이 통째로 멈춤). 글자 · 물고기 이름 없음.
"""
import math
import random

import pygame

from src.core.config import load_json
from src.core.mathutil import clamp, lerp, lerp_color, smoothstep


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


def _pl(pts, x: float) -> float:
    """[(x, y), ...] 꺾은선 값."""
    if x <= pts[0][0]:
        return pts[0][1]
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        if x <= x1:
            return lerp(y0, y1, (x - x0) / max(1e-6, x1 - x0))
    return pts[-1][1]


class Phase2Cine:
    def __init__(self, fish: dict, full: bool, reduce: bool, level: int, hp_from: float, size,
                 wait_fn=None, seed: int | None = None):
        """wait_fn(kind, lead) → 지금부터 lead 초 뒤 이후 첫 'bar'/'beat' 까지 초 (곡이 없으면 None)."""
        self.c = cfg()
        self.fish = fish
        self.fc = self.c["fish"].get(fish.get("id"), {"unique": "spirits", "eye": [-0.4, -0.05]})
        self.full = full
        self.T = self.c["full" if full else "short"]
        self.reduce = reduce
        self.level = max(0, min(2, level))
        self.hp_from = clamp(hp_from, 0.0, 1.0)
        self.w, self.h = size
        self.wait_fn = wait_fn
        self.t = 0.0
        self.skipped = False
        self.boom: float | None = None          # 폭발 시각 (= 다음 마디 첫 박)
        self.resumed = False
        self.resume_t = 0.0
        self.finished = False
        self.fired: set = set()
        self.rng = random.Random(seed if seed is not None else hash(fish.get("id", "")) & 0xFFFF)
        r = self.rng
        cap = self.c["particles"][("low", "medium", "high")[self.level]]
        self.parts = [(r.uniform(0, self.w), r.uniform(14, self.h), r.uniform(4, 11), r.uniform(0, 6.28),
                       r.uniform(0, 0.3)) for _ in range(cap)]
        n_bub = (6, 8, 10)[self.level]
        self.cam_bubbles = [(r.uniform(0.02, 0.98), r.uniform(0, 1), r.uniform(90, 160), r.randint(1, 3)) for _ in range(n_bub)]
        self.shake_off = (0, 0)
        self.shake_next = 0.0
        self.drops = [(r.uniform(0, 1), r.uniform(0, 1), r.uniform(0.6, 1.4), r.randint(1, 2)) for _ in range((8, 14, 20)[self.level])]
        self._grad = None
        self.fill_zoom = None                    # 수면이 화면을 가득 채우는 배율 (찌와 수평선 거리로 첫 그림 때 정함)
        self._fish_cache = None
        self._fish_tick = -1

    # ── 시간표 ──
    @property
    def blocking(self) -> bool:
        return not self.resumed

    def d0(self) -> float | None:
        """D 시작 (솟구침)."""
        return None if self.boom is None else self.boom - self.T["rise"]

    def d_end(self) -> float | None:
        return None if self.boom is None else self.boom + self.T["fill_sec"]

    def e_end(self) -> float | None:
        return None if self.boom is None else self.d_end() + self.T["e_sec"]

    def can_skip(self) -> bool:
        d0 = self.d0()
        return (not self.resumed and not self.skipped and self.t >= self.c["skip_after"]
                and (d0 is None or self.t < d0))

    def skip(self) -> None:
        """1초 이후 탭: 바로 D 단계 (D · E 는 정상 재생)."""
        if not self.can_skip():
            return
        self.skipped = True
        self.boom = self.t + self.T["rise"]
        for name in ("lap", "sub", "uw", "rumble", "gather", "swell"):
            self.fired.add(name)

    def _ring_starts(self) -> list:
        rs = list(self.T["rings"])
        end = self.d0() if self.d0() is not None else self.T["gather"][1]
        nxt = max(self.T["gather"][1], rs[-1] + self.T["ring_every_after"])
        while nxt < end:      # 박자 맞춤으로 늘어난 동안 고리가 계속 오므라듦
            rs.append(nxt)
            nxt += self.T["ring_every_after"]
        return rs

    def update(self, dt: float) -> list:
        """dt = 실제 시간. 돌려주는 값 = 사건 목록."""
        ev = []
        if self.finished:
            return ev
        prev, self.t = self.t, self.t + dt
        t, T = self.t, self.T

        def at(name, when, *e):
            if prev < when <= t + 1e-9 and name not in self.fired:
                self.fired.add(name)
                ev.append(e)

        if self.boom is None or t < self.d0():
            at("lap", T["approach"][0] + 1e-4, "sfx", "sfx_p2_lap", 0.6)
            at("sub", T["boundary"][0], "sfx", "sfx_p2_submerge", 0.7)
            at("muffle", T["boundary"][0], "muffle", True, self.c["music"]["to_muffled_sec"])
            at("uw", T["sink"][0], "sfx", "sfx_p2_underwater", 0.35)
            at("rumble", T["reveal"][0], "sfx", "sfx_p2_rumble", 0.6)
            at("gather", T["gather"][0], "sfx", "sfx_p2_gather", 0.55)
        # 폭발 시각: 부풀어 오르는 소리를 시작하기 전에 정함 (C 끝 + 솟구침 이후 첫 마디 · 박)
        decide = T["swell_from"] if self.full else T["gather"][0]
        if self.boom is None and t >= decide:
            lead = T["gather"][1] + T["rise"] - t
            w = self.wait_fn(T["sync"], lead) if self.wait_fn else None
            self.boom = t + (w if w is not None else lead)
        if self.boom is not None and not self.skipped:
            swell_at = max(T["swell_from"], self.boom - self.c["swell_sec"])
            if t >= swell_at and "swell" not in self.fired:
                self.fired.add("swell")
                ev.append(("sfx", "sfx_p2_swell", 0.7))
        if self.boom is not None:
            at("breach", self.d0() + 1e-4, "sfx", "sfx_p2_breach", 0.75)
            if "boom" not in self.fired and t + dt * 0.5 >= self.boom:   # 가장 가까운 틱 = 마디 첫 박
                self.fired.add("boom")
                ev.append(("sfx", "sfx_p2_burst", 1.0))
                ev.append(("muffle", False, self.c["music"]["back_sec"]))
            at("clang", self.boom + 0.15, "sfx", "sfx_p2_clang", 0.6)
            at("arp", self.boom + 0.35, "sfx", "sfx_p2_arp", 0.45)
            at("bell", self.d_end(), "sfx", "sfx_phantom_icon0", 0.75)
            if not self.resumed and t + dt * 0.5 >= self.e_end():
                self.resumed = True
                self.resume_t = t
                ev.append(("resume",))
        if self.resumed and t - self.resume_t >= 0.3:
            self.finished = True
        if t >= self.shake_next:
            self.shake_next = t + 1.0 / self.c["shake"]["hz"]
            a = 0.0 if self.reduce else self.shake_amp()
            self.shake_off = (int(round(self.rng.uniform(-a, a))), int(round(self.rng.uniform(-a, a))))
        return ev

    # ── 값 ──
    def gauge_value(self) -> float:
        """연출 게이지 (실제 체력은 재개 순간에 100%로 확정)."""
        if self.boom is None or self.t < self.boom:
            return self.hp_from
        return lerp(self.hp_from, 1.0, _ease_out((self.t - self.boom) / self.T["fill_sec"]))

    def k(self) -> float | None:
        """보라 강도: 폭발 순간 100% → E 동안 60%. 그 전엔 컷신이 잡지 않음."""
        if self.boom is None or self.t < self.boom:
            return None
        K = self.c["k"]
        return lerp(K["peak"], K["fight"], smoothstep(_win(self.t, self.d_end(), self.e_end())))

    def aura_in(self) -> float:
        """뒷배경 오라: E 동안 서서히 나타남."""
        if self.boom is None:
            return 0.0
        return smoothstep(_win(self.t, self.d_end(), self.d_end() + self.c["aura"]["fade_in"]))

    def amb_db(self) -> float:
        """주변 소리가 잦아듦 (고개 숙이는 동안 → 폭발 때 돌아옴)."""
        if self.boom is not None and self.t >= self.boom:
            return 0.0
        return self.c["amb_duck_db"] * smoothstep(_win(self.t, *self.T["tilt"]))

    def shake_amp(self) -> float:
        S, T, t = self.c["shake"], self.T, self.t
        d0 = self.d0()
        if d0 is not None and t >= d0:
            if t < self.d_end():
                return _pl(S["d"], t - d0)
            return lerp(S["e"][0], S["e"][1], _win(t, self.d_end(), self.e_end()))
        a = S["a"]
        if t < T["approach"][0]:
            return a[0]
        if t < T["approach"][1]:
            return lerp(a[1], a[2], _win(t, *T["approach"]))
        if t < T["reveal"][0]:
            return a[3]
        if t < T["hold"][0]:
            return lerp(S["b"][0], S["b"][1], _win(t, *T["reveal"]))
        if t < T["gather"][0]:
            return S["b"][1]
        return lerp(S["c"][0], S["c"][1], _win(t, *T["gather"]))

    def rod_drop(self) -> float | None:
        """낚싯대 · 손을 아래로 얼마나 (px). None = 그리지 않음."""
        T, t, R = self.T, self.t, self.c["camera"]["rod_drop_px"]
        d0 = self.d0()
        if d0 is not None and t >= d0:
            return R * (1 - _ease_out(_win(t, d0, self.boom)))
        if self.reduce:
            return 0.0 if t < T["approach"][0] else None
        if t < T["tilt"][1]:
            return R * smoothstep(_win(t, *T["tilt"]))
        return None

    # ── 카메라 (수면 위 장면) ──
    def _view(self) -> tuple[float, float, float] | None:
        """(배율, 고정점이 갈 화면 x, y) — None = 물 위 장면을 안 씀(완전히 물속). 고정점 = 찌 자리."""
        T, t, C = self.T, self.t, self.c["camera"]
        w, h = self.w, self.h
        d0 = self.d0()
        if d0 is not None and t >= d0:
            u = _ease_out(_win(t, d0, self.boom))
            return lerp(C["rise_zoom"], 1.0, u), None, None    # None = 찌 제자리로 돌아감 (아래에서 처리)
        fz = self.fill_zoom or C["approach_zoom"]
        if self.reduce:
            return (1.0, None, None) if t < T["boundary"][0] else (fz, w / 2, h * C["approach_y"])
        if t < T["tilt"][1]:
            u = smoothstep(_win(t, *T["tilt"]))
            return lerp(1.0, C["tilt_zoom"], u), ("tilt", u), None
        if t < T["approach"][1]:
            u = smoothstep(_win(t, *T["approach"]))
            return lerp(C["tilt_zoom"], fz, u), ("approach", u), None
        if t < T["sink"][0]:
            u = _win(t, *T["boundary"])
            return lerp(fz, fz * C["boundary_zoom"] / C["approach_zoom"], u), ("boundary", u), None
        return None

    def _world_view(self, world, P, out) -> None:
        """world(게임 장면)를 카메라대로 out 에 그림."""
        w, h = self.w, self.h
        C = self.c["camera"]
        v = self._view()
        if v is None:
            return
        s, qa, qb = v
        if isinstance(qa, tuple):
            kind, u = qa
            if kind == "tilt":
                q = (lerp(P[0], w / 2, u), lerp(P[1], h * C["tilt_y"], u))
            else:
                q = (w / 2, lerp(h * C["tilt_y"], h * C["approach_y"], u if kind == "approach" else 1.0))
        elif qa is None:
            d0 = self.d0()
            if d0 is not None and self.t >= d0:
                u = _ease_out(_win(self.t, d0, self.boom))
                q = (lerp(w / 2, P[0], u), lerp(h * C["approach_y"], P[1], u))
            else:
                q = P
        else:
            q = (qa, qb)
        if s <= 1.001 and abs(q[0] - P[0]) < 0.5 and abs(q[1] - P[1]) < 0.5:
            out.blit(world, (0, 0))
            return
        # 화면 = (원본 - P) × s + q → 원본 사각형 (화면 밖은 가장자리로 맞춤)
        sw, sh = w / s, h / s
        x0 = clamp(P[0] - q[0] / s, 0, w - sw)
        y0 = clamp(P[1] - q[1] / s, 0, h - sh)
        src = world.subsurface(pygame.Rect(int(x0), int(y0), max(1, int(sw)), max(1, int(sh))))
        out.blit(pygame.transform.scale(src, (w, h)), (0, 0))
        # 찌 주변의 느린 파문 (확대돼도 1px 로 세밀하게)
        if s > 1.2:
            px, py = (P[0] - x0) * s, (P[1] - y0) * s
            light = _c(self.c["colors"]["light"])
            for i in range(3):
                k = ((self.t * 0.45 + i / 3) % 1.0)
                rx = 6 + 70 * k
                col = lerp_color(light, (60, 40, 110), k)
                pygame.draw.ellipse(out, col, (px - rx, py - rx * 0.22, rx * 2, rx * 0.44), 1)

    # ── 그리기: HUD 전 게임 장면 ──
    def compose(self, canvas, P, horizon: int, rod_fn=None) -> None:
        """canvas = 지금까지 그린 게임 장면 (낚싯대 · 줄 제외). P = 찌(물고기) 자리 화면 좌표."""
        w, h = canvas.get_size()
        self.w, self.h = w, h
        T, t = self.T, self.t
        world = canvas.copy()
        out = canvas
        if self.fill_zoom is None:   # 찌 위쪽이 전부 물이 되도록: (화면에서 찌 높이) / (찌 − 수평선) 배 이상
            C = self.c["camera"]
            gap = max(4.0, P[1] - horizon - 2)
            self.fill_zoom = clamp(h * C["approach_y"] / gap, C["approach_zoom"], C["max_zoom"])
        d0 = self.d0()
        rising = d0 is not None and t >= d0
        if self.reduce:
            self._compose_reduce(world, out, P, rod_fn)
        else:
            v = self._view()
            if v is None and not rising:
                out.blit(self._underwater(), (0, 0))
            else:
                self._world_view(world, P, out)
                yb = None
                if rising and t < self.boom:
                    yb = int(h * _ease_out(_win(t, d0, self.boom)))         # 솟구침: 경계선이 위에서 아래로
                    uw = self._underwater()
                    out.blit(uw, (0, yb), (0, yb, w, h - yb))
                elif not rising and T["boundary"][0] <= t < T["sink"][0]:
                    yb = int(h * (1 - smoothstep(_win(t, *T["boundary"]))))  # 경계선이 아래에서 위로
                    uw = self._underwater()
                    out.blit(uw, (0, yb), (0, yb, w, h - yb))
                if yb is not None and 0 < yb < h:
                    self._surface_edge(out, yb)
                if rod_fn is not None:
                    drop = self.rod_drop()
                    if drop is not None:
                        rod_fn(out, drop)
        if rising:
            self._draw_splash(out)
            if t >= self.boom:
                self._draw_burst(out, P)
        # 흔들림: 게임 장면만 (HUD 는 이 뒤에 그림)
        ox, oy = self.shake_off
        if ox or oy:
            snap = out.copy()
            out.blit(snap, (ox, oy))

    def _compose_reduce(self, world, out, P, rod_fn) -> None:
        """화면 효과 줄이기: 카메라 이동 대신 0.8초 페이드 2번 (수면 → 경계 → 물속), 솟구침 대신 0.3초 페이드."""
        T, t = self.T, self.t
        f = self.c["reduce"]["fade_sec"]
        d0 = self.d0()
        if d0 is not None and t >= d0:
            out.blit(world, (0, 0))
            if rod_fn is not None and self.rod_drop() is not None:
                rod_fn(out, self.rod_drop())
            if t < self.boom:
                uw = self._underwater()
                uw.set_alpha(int(255 * (1 - _win(t, d0, d0 + self.c["reduce"]["rise_fade"]))))
                out.blit(uw, (0, 0))
                uw.set_alpha(None)
            return
        a0 = T["approach"][0]
        split = self._split_frame(world, P)
        if t < a0:
            out.blit(world, (0, 0))
            if rod_fn is not None:
                rod_fn(out, 0.0)
        elif t < a0 + f:
            out.blit(world, (0, 0))
            split.set_alpha(int(255 * smoothstep(_win(t, a0, a0 + f))))
            out.blit(split, (0, 0))
        elif t < a0 + 2 * f:
            out.blit(split, (0, 0))
            uw = self._underwater()
            uw.set_alpha(int(255 * smoothstep(_win(t, a0 + f, a0 + 2 * f))))
            out.blit(uw, (0, 0))
            uw.set_alpha(None)
        else:
            out.blit(self._underwater(), (0, 0))

    def _split_frame(self, world, P) -> pygame.Surface:
        """줄이기용 정지 장면: 위 = 확대된 수면, 아래 = 물속 (경계선 가운데)."""
        w, h = self.w, self.h
        s = pygame.Surface((w, h))
        C = self.c["camera"]
        sc = C["approach_zoom"]
        sw, sh = w / sc, h / sc
        x0 = clamp(P[0] - (w / 2) / sc, 0, w - sw)
        y0 = clamp(P[1] - (h * C["approach_y"]) / sc, 0, h - sh)
        s.blit(pygame.transform.scale(world.subsurface(pygame.Rect(int(x0), int(y0), int(sw), int(sh))), (w, h)), (0, 0))
        yb = h // 2
        s.blit(self._underwater(), (0, yb), (0, yb, w, h - yb))
        self._surface_edge(s, yb)
        return s

    def _surface_edge(self, out, y: int) -> None:
        """수면 경계선 (물 위 · 물속이 동시에 보이는 선) + 선을 따라 맺힌 작은 기포."""
        w = out.get_width()
        rim, light = _c(self.c["colors"]["rim"]), _c(self.c["colors"]["light"])
        pts = [(x, y + 2 * math.sin(x * 0.07 + self.t * 6)) for x in range(0, w + 8, 8)]
        pygame.draw.lines(out, rim, False, pts, 2)
        pygame.draw.lines(out, light, False, [(x, yy - 1) for x, yy in pts], 1)
        r = random.Random(5)
        for _ in range(14):
            bx = r.uniform(0, w)
            by = y + 3 + r.uniform(0, 5) + 2 * math.sin(bx * 0.07 + self.t * 6)
            pygame.draw.circle(out, lerp_color(light, rim, 0.4), (int(bx), int(by)), r.choice((1, 1, 2)), 1)

    # ── 물속 장면 ──
    def _bg(self, w: int, h: int) -> pygame.Surface:
        if self._grad is None or self._grad.get_size() != (w, h):
            top, bot = _c(self.c["colors"]["bg_top"]), _c(self.c["colors"]["bg_bottom"])
            g = pygame.Surface((w, h))
            for y in range(h):
                g.fill(lerp_color(top, bot, y / max(1, h - 1)), (0, y, w, 1))
            self._grad = g
            self._uw = pygame.Surface((w, h))
            dk = pygame.Surface((w, h), pygame.SRCALPHA)
            for y in range(h):
                dk.fill((0, 0, 0, int(150 * (y / max(1, h - 1)) ** 1.4)), (0, y, w, 1))
            self._dark = dk
        return self._grad

    def fish_center(self) -> tuple:
        T, t = self.T, self.t
        x, y = self.w / 2, self.h * self.c["fish_y"]
        y += 24 * (1 - smoothstep(_win(t, *T["reveal"])))          # 아래 어둠에서 떠오르며 드러남
        d0 = self.d0()
        if d0 is not None and t >= d0:
            y -= (self.h * 0.8) * _ease_in(_win(t, d0, self.boom))  # 위로 확 치솟음
        return x, y

    def _gather(self) -> float:
        """기를 모으는 정도 0~1 (C 시작 → D 시작)."""
        T = self.T
        end = self.d0() if self.d0() is not None else T["gather"][1]
        return _ease_in(_win(self.t, T["gather"][0], max(T["gather"][0] + 0.1, end)))

    def _underwater(self) -> pygame.Surface:
        w, h = self.w, self.h
        bg = self._bg(w, h)
        uw = self._uw
        uw.blit(bg, (0, 0))
        T, t = self.T, self.t
        light, rim = _c(self.c["colors"]["light"]), _c(self.c["colors"]["rim"])
        dk = smoothstep(_win(t, T["sink"][0], T["reveal"][1]))      # 깊어질수록 아래가 더 어두워짐
        if dk > 0.01:
            self._dark.set_alpha(int(255 * dk))
            uw.blit(self._dark, (0, 0))
        fx, fy = self.fish_center()
        gk = self._gather()
        sink = _win(t, T["sink"][0], T["reveal"][0])
        show_u = smoothstep(_win(t, T["hold"][0], T["hold"][0] + 0.4))   # 고유 요소가 보이기 시작
        uq = self.fc.get("unique")
        if show_u > 0:
            self._unique(uw, uq, "back", fx, fy, show_u, gk)
        # 빛줄기 3개 (더하기 15%) — 깊어지면 약해지고, 기를 모을 때 환상어로 기울며 빨려 듦
        rk = (1 - 0.4 * sink) * (1 - gk)
        if rk > 0.02:
            ray = getattr(self, "_ray", None)
            if ray is None or ray.get_size() != (w, h):
                ray = self._ray = pygame.Surface((w, h))
            ray.fill((0, 0, 0))
            rc = tuple(int(c * 0.15 * rk) for c in light)
            for i, bx in enumerate((0.26, 0.52, 0.78)):
                x0 = w * bx + 10 * math.sin(t * 0.7 + i * 2.1)
                x1 = lerp(x0 - 70, fx + (i - 1) * 10, gk)
                y1 = lerp(h, fy, gk)
                pygame.draw.polygon(ray, rc, [(x0 - 7, 0), (x0 + 7, 0), (x1 + 22 - 18 * gk, y1), (x1 - 22 + 18 * gk, y1)])
            uw.blit(ray, (0, 0), special_flags=pygame.BLEND_RGB_ADD)
        # 빛 알갱이 (1px, 떠오름 → C 에 환상어로 빨려 듦)
        g0 = T["gather"][0]
        for (x0, y0, sp, ph, dl) in self.parts:
            def drift(tt):
                return x0 + 3 * math.sin(tt * 0.9 + ph), (y0 - sp * tt) % (h - 14) + 14
            if t < g0 + dl:
                x, y = drift(t)
                a = 1.0
            else:
                u = _win(t, g0 + dl, g0 + dl + max(0.3, (self.d0() or T["gather"][1]) - g0 - dl))
                if u >= 1:
                    continue
                sx, sy = drift(g0 + dl)
                e = _ease_in(u)
                x, y = lerp(sx, fx, e), lerp(sy, fy, e)
                a = 1 - u * u
            col = lerp_color((30, 18, 50), light, (0.35 + 0.65 * a * (0.7 + 0.3 * math.sin(t * 5 + ph))) * (1 - 0.5 * sink))
            uw.fill(col, (int(x), int(y), 1, 1))
        # 환상어 (B 부터) + 가림
        if t >= T["reveal"][0]:
            self._draw_fish(uw, fx, fy)
        # 오므라드는 보랏빛 고리 (C)
        rs = self.c["ring_r"]
        for st in self._ring_starts():
            u = (t - st) / self.c["ring_sec"]
            if 0 <= u < 1:
                rr = lerp(rs[0], rs[1], _ease_in(u))
                col = lerp_color((60, 30, 110), rim, 0.4 + 0.6 * u)
                pygame.draw.circle(uw, col, (int(fx), int(fy)), max(2, int(rr)), 2 if u < 0.7 else 1)
        if show_u > 0:
            self._unique(uw, uq, "front", fx, fy, show_u, gk)
        # 기포: A = 카메라 옆을 스쳐 올라감 / B · C = 환상어 주변
        if T["boundary"][0] <= t < T["reveal"][0] + 0.3:
            ka = 1 - _win(t, T["reveal"][0], T["reveal"][0] + 0.3)
            for (bx, by, sp, r) in self.cam_bubbles:
                y = h - ((by * h + sp * (t - T["boundary"][0])) % (h + 20))
                x = (bx * w + 6 * math.sin(t * 4 + by * 9)) % w
                if ka > 0.1:
                    pygame.draw.circle(uw, lerp_color((40, 24, 70), light, 0.7 * ka), (int(x), int(y)), r + 1, 1)
        if t >= T["reveal"][0]:
            for i in range(4):
                per = 1.6 + i * 0.3
                u = ((t + i * 0.45) % per) / per
                bx = fx + (-38, -14, 22, 44)[i] + 2 * math.sin(t * 3 + i)
                by = fy + 18 - 70 * u
                pygame.draw.circle(uw, lerp_color(rim, light, 0.3), (int(bx), int(by)), 1 + (i % 2), 1)
        # 올려다본 수면 (맨 위 12px 물결선, #B48CF0 50%) — 가라앉을수록 옅어짐
        top = pygame.Surface((w, 14), pygame.SRCALPHA)
        line_col = _c(self.c["colors"]["dusk"][0]) if uq == "dusk" else rim
        a_line = int(128 * (1 - 0.5 * sink))
        pts = [(x, 6 + 2.5 * math.sin(x * 0.06 + t * 2.2) + 1.5 * math.sin(x * 0.13 - t * 1.3)) for x in range(0, w + 6, 6)]
        pygame.draw.polygon(top, (*line_col, a_line // 3), [(0, 0)] + pts + [(w, 0)])
        pygame.draw.lines(top, (*line_col, a_line), False, pts, 2)
        uw.blit(top, (0, 0))
        if show_u > 0 and uq in ("moon", "aurora", "dusk"):
            self._unique(uw, uq, "sky", fx, fy, show_u, gk)
        return uw

    def _build_fish(self) -> tuple:
        """환상어(도감 그림 2배) + 보랏빛 테두리 1px — 눈 높이 위쪽을 잘라 낸 그림 (윤곽선도 남지 않음)."""
        from src.render.fish_draw import draw_fish_side, fish_colors, fish_shape
        L = self.c["fish_len"]
        sw, sh = int(L * 1.35), int(L * 0.95)
        s = pygame.Surface((sw, sh), pygame.SRCALPHA)
        draw_fish_side(s, sw / 2, sh / 2, L, 0.0, fish_colors(self.fish), facing=-1, tail_wag=0.5, shape=fish_shape(self.fish))
        rim = _c(self.c["colors"]["rim"])
        m = pygame.mask.from_surface(s)
        out = pygame.Surface((sw, sh), pygame.SRCALPHA)
        g = m.to_surface(setcolor=(*rim, 255), unsetcolor=(0, 0, 0, 0))
        for d in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            out.blit(g, d)
        out.blit(s, (0, 0))
        # 가림: 눈(가로선) + 눈 반지름 위쪽 전체를 지우고, 아래 4px 는 부드럽게
        ex, ey = self.fc["eye"]
        eye_r = max(2, int(L * 0.03))
        cut = int(sh / 2 + L * ey) + eye_r + 1
        fade = self.c["cover_fade_px"]
        mask = pygame.Surface((sw, sh), pygame.SRCALPHA)
        mask.fill((255, 255, 255, 255))
        mask.fill((255, 255, 255, 0), (0, 0, sw, max(0, cut)))
        for i in range(fade):
            mask.fill((255, 255, 255, int(255 * (i + 1) / (fade + 1))), (0, cut + i, sw, 1))
        out.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
        return out, cut

    def _draw_fish(self, surf, fx: float, fy: float) -> None:
        T, t = self.T, self.t
        if self._fish_cache is None or int(t * 8) != self._fish_tick:
            self._fish_tick = int(t * 8)               # 지느러미 · 꼬리 흔들림 (그림 안 흔들림을 1/8초마다 다시)
            self._fish_cache = self._build_fish()
        img, cut = self._fish_cache
        lo, hi = self.c["fish_bright"]
        b = lerp(lo, hi, 0.5 + 0.5 * math.sin(t * 1.7))
        b *= smoothstep(_win(t, *T["reveal"]))       # 어둠에서 서서히
        b = b + (1 - b) * 0.6 * self._gather() ** 2  # 기를 모을수록 밝아짐
        if b <= 0.01:
            return
        im = img.copy()
        v = int(255 * clamp(b, 0, 1))
        im.fill((v, v, v, 255), special_flags=pygame.BLEND_RGBA_MULT)
        x, y = int(fx - im.get_width() / 2), int(fy - im.get_height() / 2)
        if self.fc.get("unique") == "echoes":   # 4마리로 겹쳐 보이다가 C 마지막 고리에서 하나로
            k = 1 - _win(t, T["gather"][0], T["rings"][-1])
            if k > 0.01:
                for ox, oy in ((-26, -8), (24, -4), (-18, 10), (28, 8)):
                    ghost = im.copy()
                    ghost.set_alpha(int(90 * k))
                    surf.blit(ghost, (int(x + ox * k), int(y + oy * k)))
        surf.blit(im, (x, y))
        # 가린 쪽 어둠: 위쪽으로 넓게 이어지는 부드러운 그림자 (배경 어둠과 이어짐)
        dark = getattr(self, "_shade", None)
        if dark is None:
            dw, dh = int(img.get_width() * 1.7), int(img.get_height() * 1.6)
            dark = self._shade = pygame.Surface((dw, dh), pygame.SRCALPHA)
            for i in range(12, 0, -1):
                k = i / 12
                pygame.draw.ellipse(dark, (0, 0, 0, int(255 * (1 - k) ** 1.2)),
                                    (dw * (1 - k) / 2, dh * (1 - k) / 2, dw * k, dh * k))
        cy = y + cut
        dx = int(fx - dark.get_width() / 2)
        dy = int(cy - dark.get_height() * 0.62)
        ch = min(dark.get_height(), int(cy + 1 - dy))
        if ch > 0:
            part = dark.subsurface((0, 0, dark.get_width(), ch)).copy()
            fade = min(ch, 14)   # 아래 끝은 가림선까지 부드럽게 옅어짐 (곧은 경계가 안 보이게)
            for i in range(fade):
                part.fill((255, 255, 255, int(255 * (fade - i) / (fade + 1))), (0, ch - 1 - i, part.get_width(), 1),
                          special_flags=pygame.BLEND_RGBA_MULT)
            surf.blit(part, (dx, dy))

    def _layer(self, w: int, h: int) -> pygame.Surface:
        """투명 그림판 재사용 (매 프레임 새로 만들지 않음, 휴대폰 성능)."""
        lay = getattr(self, "_lay", None)
        if lay is None or lay.get_size() != (w, h):
            lay = self._lay = pygame.Surface((w, h), pygame.SRCALPHA)
        lay.fill((0, 0, 0, 0))
        return lay

    # ── 환상어별 고유 요소 (B 에서 보이기 시작, C 에 빨려 듦) ──
    def _unique(self, s, kind: str, layer: str, fx: float, fy: float, show: float, gk: float) -> None:
        t, w, h = self.t, s.get_width(), s.get_height()
        light, rim = _c(self.c["colors"]["light"]), _c(self.c["colors"]["rim"])
        lay = self._layer(w, h)
        A = show                                   # 전체 투명도 배율
        drew = False

        def suck(x, y):
            return lerp(x, fx, gk), lerp(y, fy, gk)

        if kind == "moon" and layer == "sky":
            mx = int(w * 0.68)
            pygame.draw.circle(lay, (*light, int(60 * A)), (mx, 3), 14)
            pygame.draw.circle(lay, (*light, int(210 * A)), (mx, 3), 9)
            drew = True
        elif kind == "moon" and layer == "back":
            mx = w * 0.68
            beam = pygame.Surface((w, h))
            beam.fill((0, 0, 0))
            tail = fx + 40                          # 달빛 기둥은 꼬리 쪽까지 (윗부분 어둠은 그대로)
            pygame.draw.polygon(beam, tuple(int(c * 0.13 * A) for c in light),
                                [(mx - 7, 8), (mx + 7, 8), (tail + 18, fy + 14), (tail - 18, fy + 14)])
            s.blit(beam, (0, 0), special_flags=pygame.BLEND_RGB_ADD)
        elif kind == "mist":
            for i in range(7):
                a = i / 7 * math.tau + t * 0.5
                if (math.sin(a) > 0) != (layer == "front"):
                    continue
                rad = 1 - gk
                cx, cy = fx + 78 * rad * math.cos(a), fy + 26 * rad * math.sin(a)
                pygame.draw.ellipse(lay, (200, 170, 240, int(46 * A * (1 - 0.6 * gk))), (cx - 18 * rad - 3, cy - 6, 36 * rad + 6, 12))
                drew = True
        elif kind == "dusk" and layer == "sky":
            c0, c1 = _c(self.c["colors"]["dusk"][0]), _c(self.c["colors"]["dusk"][1])
            band = int(h * 0.3)
            for y in range(0, band, 2):
                u = y / band
                lay.fill((*lerp_color(c0, c1, u), int(140 * (1 - u) * A)), (0, y, w, 2))
            drew = True
        elif kind == "meteors" and layer == "back":
            T = self.T
            for i, st in enumerate((T["hold"][0], T["hold"][0] + 0.35, T["hold"][0] + 0.7)):
                u = (t - st) / 0.7
                if u <= 0:
                    continue
                x0 = w * (0.62 + 0.13 * i)
                hx, hy = (x0 - 110 * min(u, 1), -6 + h * 0.5 * min(u, 1))
                if u >= 1:   # 떨어진 뒤: 환상어로 빨려 듦
                    if gk >= 0.98:
                        continue
                    hx, hy = suck(hx, hy)
                for j in range(6):
                    tx, ty = hx + j * 4.5, hy - j * 4.5 * h * 0.5 / 110
                    pygame.draw.circle(lay, (*lerp_color(light, rim, j / 6), int(220 * (1 - j / 6) * A)), (int(tx), int(ty)), 1)
                pygame.draw.circle(lay, (*light, int(255 * A)), (int(hx), int(hy)), 2)
                drew = True
        elif kind == "lanterns" and layer == "back":
            for i, (lx, ly) in enumerate(((0.14, 0.9), (0.31, 0.84), (0.55, 0.92), (0.72, 0.86), (0.88, 0.9))):
                a = _win(t, self.T["hold"][0] + 0.2 * i, self.T["hold"][0] + 0.15 + 0.2 * i)
                if a <= 0 or gk >= 0.98:
                    continue
                a *= (0.85 + 0.15 * math.sin(t * 6 + i)) * A
                x, y = suck(w * lx, h * ly)
                pygame.draw.circle(lay, (*rim, int(70 * a)), (int(x), int(y)), 7)
                pygame.draw.circle(lay, (*light, int(230 * a)), (int(x), int(y)), 2)
                drew = True
        elif kind == "reeds" and layer == "back":
            for i in range(8):
                bx = w * (0.06 + i * 0.125)
                hh = 60 + (i * 37) % 55
                lean = (fx - bx) * 0.35 * gk          # C: 환상어 쪽으로 휨
                pts = [(bx + (math.sin(t * 1.5 + i) * 7 + lean) * (j / 4) ** 2, h - hh * j / 4) for j in range(5)]
                pygame.draw.lines(lay, (150, 100, 210, int(190 * A)), False, pts, 2)
                tx, ty = pts[-1]
                pygame.draw.line(lay, (190, 140, 240, int(200 * A)), (tx, ty), (tx + 4, ty - 6), 1)
            drew = True
        elif kind == "crystals" and layer == "back":
            h0 = self.T["hold"][0]
            for i, (cx, ch, cw) in enumerate(((0.2, 46, 9), (0.36, 30, 7), (0.66, 54, 10), (0.82, 36, 8))):
                g = smoothstep(_win(t, h0 + 0.15 * i, h0 + 0.7 + 0.15 * i))
                if g <= 0:
                    continue
                x, hh = w * cx, ch * g
                body = [(x - cw / 2, h), (x - cw / 2, h - hh * 0.75), (x, h - hh), (x + cw / 2, h - hh * 0.75), (x + cw / 2, h)]
                pygame.draw.polygon(lay, (150, 90, 220, int(235 * A)), body)
                pygame.draw.polygon(lay, (210, 170, 255, int(235 * A)), [(x, h - hh), (x + cw / 2, h - hh * 0.75), (x + 1, h)])
                pygame.draw.lines(lay, (*light, int(220 * A)), False, body[1:4], 1)
                if gk > 0.05:   # C: 빛을 내뿜음 (환상어 쪽으로 빛줄기)
                    pygame.draw.line(lay, (*light, int(160 * gk * A)), (x, h - hh), (fx, fy), 1)
                    pygame.draw.circle(lay, (*light, int(90 * gk * A)), (int(x), int(h - hh)), 5)
            drew = True
        elif kind == "butterflies":
            for i in range(6):
                a = i / 6 * math.tau + t * 0.9
                if (math.sin(a) > 0) != (layer == "front") or gk >= 0.98:
                    continue
                cx, cy = suck(fx + 82 * math.cos(a), fy + 34 * math.sin(a) - 6)
                f = abs(math.sin(t * 12 + i)) * 4 + 1
                col = (*lerp_color(light, rim, 0.3), int(220 * A))
                pygame.draw.polygon(lay, col, [(cx, cy), (cx - f, cy - 4), (cx - f, cy + 2)])
                pygame.draw.polygon(lay, col, [(cx, cy), (cx + f, cy - 4), (cx + f, cy + 2)])
                drew = True
        elif kind == "embers" and layer == "front":
            for i in range(12):
                per = 2.2 + (i % 4) * 0.4
                u = ((t + i * 0.37) % per) / per
                x = w * ((i * 0.083 + 0.04) % 1) + 6 * math.sin(t * 2 + i)
                y = h + 4 - (h * 0.75) * u
                if gk >= 0.98:
                    continue
                x, y = suck(x, y)
                a = (1 - u) * (0.6 + 0.4 * math.sin(t * 14 + i * 3)) * A
                lay.fill((*lerp_color((200, 120, 255), light, 0.35), int(255 * clamp(a, 0, 1))), (int(x), int(y), 2, 2))
            drew = True
        elif kind == "aurora" and layer == "sky":
            for x in range(0, w, 2):
                a = 0.5 + 0.5 * math.sin(x * 0.045 + t * 1.6) * math.sin(x * 0.017 - t * 0.7)
                col = lerp_color((140, 90, 216), (120, 220, 210), 0.5 + 0.5 * math.sin(x * 0.02 + t))
                lay.fill((*col, int((60 + 120 * a) * A)), (x, 0, 2, int(10 + 14 * a)))
            lay.fill((214, 224, 255, int(45 * A)), (0, 0, w, 12))
            for i in range(5):
                x = w * (0.1 + i * 0.2)
                pygame.draw.line(lay, (235, 240, 255, int(120 * A)), (x, 0), (x + 9, 11), 1)
            drew = True
        elif kind == "spirits":
            rad = 1 - gk
            for i in range(7):
                a = i / 7 * math.tau + t * (1.2 + 2.0 * gk)
                if (math.sin(a) > 0) != (layer == "front"):
                    continue
                for j in range(3):
                    aa = a - j * 0.09
                    x, y = fx + 60 * rad * math.cos(aa), fy + 30 * rad * math.sin(aa)
                    pygame.draw.circle(lay, (*light, int(200 * (1 - j / 3) * A)), (int(x), int(y)), 2 if j == 0 else 1)
                drew = True
        if drew:
            s.blit(lay, (0, 0))

    # ── 솟구침 물보라 · 보랏빛 폭발 (수면 위) ──
    def _draw_splash(self, out) -> None:
        d0 = self.d0()
        u = _win(self.t, d0, self.boom + 0.4)
        if u <= 0 or u >= 1:
            return
        w, h = self.w, self.h
        light = _c(self.c["colors"]["light"])
        for (x0, y0, sp, r) in self.drops:   # 물보라가 화면을 스침 (아래 → 위)
            y = h * (1.1 - (y0 * 0.4 + u * sp))
            if -4 < y < h:
                pygame.draw.line(out, lerp_color(light, (255, 255, 255), 0.4), (x0 * w, y), (x0 * w + 1, y + 5 + 3 * r), r)

    def _draw_burst(self, out, P) -> None:
        t, w, h = self.t, self.w, self.h
        B = self.c["burst"]
        light, rim = _c(self.c["colors"]["light"]), _c(self.c["colors"]["rim"])
        fade = 1 - smoothstep(_win(t, self.d_end(), self.e_end()))   # E: 천천히 사그라듦
        if fade <= 0:
            return
        layer = self._layer(w, h)
        px, py = P
        # 수면을 따라 퍼지는 큰 고리 (2겹)
        for k, dl in ((1.0, 0.0), (0.6, 0.12)):
            u = _win(t, self.boom + dl, self.boom + dl + B["ring_sec"])
            if 0 < u:
                rx = lerp(8, w * 0.9, _ease_out(u))
                a = int(230 * k * fade * (1 - 0.6 * u))
                pygame.draw.ellipse(layer, (*lerp_color(light, rim, u), a), (px - rx, py - rx * 0.16, rx * 2, rx * 0.32), 2)
        # 사방으로 뻗는 빛줄기
        u = _ease_out(_win(t, self.boom, self.boom + B["ray_sec"]))
        n = B["rays"]
        L = max(w, h) * 1.2 * u
        for i in range(n):
            a = i / n * math.tau + 0.2
            ex, ey = px + math.cos(a) * L, py + math.sin(a) * L * 0.75
            pygame.draw.line(layer, (*light, int(150 * fade)), (px, py), (ex, ey), 2 if i % 2 == 0 else 1)
        pygame.draw.circle(layer, (*light, int(200 * fade)), (int(px), int(py)), int(4 + 10 * fade))
        out.blit(layer, (0, 0))
        # 화면 전체 보랏빛 번쩍 (1번만, 최대 60% · 줄이기 30%, 0.15초에 사라짐)
        F = self.c["flash"]
        fu = (t - self.boom) / F["sec"]
        if 0 <= fu < 1:
            mx = F["reduce_max"] if self.reduce else F["max"]
            fl = pygame.Surface((w, h))
            fl.fill(lerp_color(rim, (255, 255, 255), 0.5))
            fl.set_alpha(int(255 * mx * (1 - fu)))
            out.blit(fl, (0, 0))

    # ── 그리기: HUD 위 체력 바 (D · E) ──
    def draw_top(self, canvas, hud_x=None) -> None:
        if self.boom is None or self.t < self.boom:
            return
        Bc = self.c["bar"]
        w = canvas.get_width()
        x = (w - Bc["w"]) // 2
        u = self.t - self.boom
        morph = _win(u, 0.0, Bc["morph_sec"]) if u >= 0 else 0.0
        deco_u = _win(u, *Bc["deco"])
        deco = 0.0 if deco_u <= 0 else (lerp(0, 1.2, deco_u / 0.6) if deco_u < 0.6 else lerp(1.2, 1.0, (deco_u - 0.6) / 0.4))
        flash = 1.0 if u < Bc["flash_sec"] else 0.0
        shine = 1.0 if abs(self.t - self.d_end()) < 0.12 else None   # 100%: 바 전체가 한 번 밝게 반짝
        draw_p2_bar(canvas, x, Bc["y"], Bc["w"], Bc["h"], self.gauge_value(), self.t, morph=morph, flash=flash,
                    deco=deco, dots=deco_u > 0, glow=shine)


# ───────────────────────── 체력 바 2페이즈 모습 (6번) ─────────────────────────
OLD_FILL = (235, 90, 80)
OLD_BG = (50, 30, 36)


def draw_p2_bar(canvas, x: int, y: int, bw: int, bh: int, frac: float, t: float, morph: float = 1.0, flash: float = 0.0,
                deco: float = 1.0, dots: bool = True, glow=None, old_border=(190, 120, 255)) -> None:
    """보라 그라데이션 · 짙은 보라 바탕 · 2px 이중 테두리 · 양끝 마름모 · 3초마다 훑는 반짝 · 오른쪽 밖 점 2개.
    morph 0 → 1 = 기존 모습 → 2페이즈 모습 (0.2초)."""
    B = cfg()["bar"]
    g0, g1 = _c(B["grad"][0]), _c(B["grad"][1])
    tipc = _c(B["tip"])
    canvas.fill((12, 10, 18), (x - 1, y - 1, bw + 2, bh + 2))
    canvas.fill(lerp_color(OLD_BG, _c(B["bg"]), morph), (x, y, bw, bh))
    fw = int(bw * clamp(frac, 0, 1))
    if morph >= 0.999:
        for i in range(0, fw, 2):
            canvas.fill(lerp_color(g0, g1, i / max(1, bw - 1)), (x + i, y, min(2, fw - i), bh))
    else:
        for i in range(0, fw, 2):
            col = lerp_color(OLD_FILL, lerp_color(g0, g1, i / max(1, bw - 1)), morph)
            canvas.fill(col, (x + i, y, min(2, fw - i), bh))
    if fw > 0:
        canvas.fill(lerp_color((255, 170, 150), (220, 200, 255), morph), (x, y, fw, 1))
    tp = B["tip_px"]
    if fw > tp and morph > 0.5:
        canvas.fill(tipc, (x + fw - tp, y, tp, bh))
    # 3초마다 밝은 빛이 왼쪽 → 오른쪽으로 한 번
    ph = (t % B["shine_every"]) / B["shine_sec"]
    if morph >= 0.999 and ph < 1 and fw > 0:
        sx = int(x - 8 + ph * (bw + 16))
        band = pygame.Surface((8, bh), pygame.SRCALPHA)
        for i in range(8):
            band.fill((255, 255, 255, int(110 * math.sin(math.pi * (i + 0.5) / 8))), (i, 0, 1, bh))
        old = canvas.get_clip()
        canvas.set_clip(pygame.Rect(x, y, fw, bh).clip(old) if old else pygame.Rect(x, y, fw, bh))
        canvas.blit(band, (sx, y))
        canvas.set_clip(old)
    if glow:   # 100%: 바 전체 반짝
        gl = pygame.Surface((bw, bh), pygame.SRCALPHA)
        gl.fill((255, 255, 255, 140))
        canvas.blit(gl, (x, y))
    # 테두리: 1px → 2px 이중선 (바깥 #E2D2FF + 안쪽 #7A4FD0), 바뀌는 순간 하얗게 0.1초
    if flash > 0:
        pygame.draw.rect(canvas, (255, 255, 255), (x - 3, y - 3, bw + 6, bh + 6), 2)
    elif morph < 0.5:
        pygame.draw.rect(canvas, old_border, (x - 2, y - 2, bw + 4, bh + 4), 1)
    else:
        pygame.draw.rect(canvas, _c(B["outer"]), (x - 3, y - 3, bw + 6, bh + 6), 1)
        pygame.draw.rect(canvas, _c(B["inner"]), (x - 2, y - 2, bw + 4, bh + 4), 1)
    # 양끝 마름모 장식 (5×5) · 오른쪽 밖 페이즈 점 2개
    if deco > 0.01:
        r = B["deco_px"] / 2 * deco
        for cx in (x - 8, x + bw + 7):
            cy = y + bh / 2
            pygame.draw.polygon(canvas, tipc, [(cx, cy - r), (cx + r, cy), (cx, cy + r), (cx - r, cy)])
    if dots:
        dc = _c(B["dot_color"])
        for i in range(2):
            canvas.fill(dc, (x + bw + 13 + i * 5, y + bh // 2 - 1, 3, 3))


# ───────────────────────── 뒷배경 보랏빛 오라 (7번) ─────────────────────────
_AURA_CACHE: dict = {}


def draw_aura(canvas, horizon: int, t: float, k: float, level: int, holes=()) -> None:
    """수평선을 따라 일렁이는 보랏빛 띠 (아래 진하고 위로 옅게, 화면 높이 40%) + 양옆 가장자리 옅은 보라.
    밝기 30 ↔ 45% (4초 주기) × k. 신호 보호 영역(holes)은 밝기를 바꾸지 않음. 화질: 높음 일렁임 / 중간 단순 / 낮음 정지."""
    if k <= 0.005:
        return
    A = cfg()["aura"]
    w, h = canvas.get_size()
    col = _c(A["color"])
    band_h = int(h * A["band_frac"])
    pulse = A["lo"] + (A["hi"] - A["lo"]) * (0.5 - 0.5 * math.cos(math.tau * t / A["period"]))
    key = (w, h, horizon, level, int(t * 15) if level >= 1 else 0, tuple(map(tuple, holes)))
    lay = _AURA_CACHE.get("lay")
    if _AURA_CACHE.get("key") != key or lay is None:
        # 더하기 합성용 (검정 = 변화 없음): 아래쪽이 진하고 위로 옅어지는 띠 + 양옆 가장자리
        static = _AURA_CACHE.get("static")
        skey = (w, h, horizon, tuple(map(tuple, holes)))
        if static is None or _AURA_CACHE.get("skey") != skey:
            col_s = pygame.Surface((2, band_h + 16))             # 띠 한 줄 (위 0 → 아래 진하게), 일렁임은 줄을 위아래로 옮겨 붙임
            col_s.fill((0, 0, 0))
            for y in range(band_h):
                u = (y / max(1, band_h - 1)) ** 1.6
                col_s.fill(tuple(int(c * u) for c in col), (0, 16 + y, 2, 1))
            edge = pygame.Surface((w, h))
            edge.fill((0, 0, 0))
            e = A["edge_px"]
            for i in range(e):
                c_e = tuple(int(c * A["edge_k"] * (1 - i / e) ** 2) for c in col)
                edge.fill(c_e, (i, 0, 1, h))
                edge.fill(c_e, (w - 1 - i, 0, 1, h))
            hole = pygame.Surface((w, h))
            hole.fill((255, 255, 255))
            for r in holes:   # 신호 슬롯 · 조준점 주변: 밝기를 바꾸지 않음 (가장자리 16px 부드럽게)
                r = pygame.Rect(r)
                for i in range(16, 0, -1):
                    hole.fill((226, 226, 226), r.inflate(i * 2, i * 2), special_flags=pygame.BLEND_RGB_MULT)
                hole.fill((0, 0, 0), r)
            _AURA_CACHE.update(static=True, skey=skey, col=col_s, edge=edge, hole=hole,
                               lay=pygame.Surface((w, h)), work=pygame.Surface((w, h)))
        lay = _AURA_CACHE["lay"]
        lay.blit(_AURA_CACHE["edge"], (0, 0))
        col_s = _AURA_CACHE["col"]
        top0 = horizon - band_h - 16
        for x in range(0, w, 2):
            if level >= 2:
                wave = 7 * math.sin(x * 0.03 + t * 0.9) + 4 * math.sin(x * 0.071 - t * 1.3)
            elif level == 1:
                wave = 6 * math.sin(x * 0.03 + t * 0.7)
            else:
                wave = 0.0
            yy = int(top0 + wave)
            lay.blit(col_s, (x, yy), (0, 0, 2, max(0, horizon - yy)), special_flags=pygame.BLEND_RGB_MAX)
        lay.blit(_AURA_CACHE["hole"], (0, 0), special_flags=pygame.BLEND_RGB_MULT)
        _AURA_CACHE["key"] = key
    work = _AURA_CACHE["work"]
    work.blit(lay, (0, 0))
    v = int(255 * pulse * clamp(k, 0, 1))
    work.fill((v, v, v), special_flags=pygame.BLEND_RGB_MULT)
    canvas.blit(work, (0, 0), special_flags=pygame.BLEND_RGB_ADD)
