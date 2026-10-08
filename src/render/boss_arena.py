"""보스전 무대 (BOSS_ARENA.md 🅰, DESIGN.md 51-2) — 전설 · 환상 파이팅에서만. 일반 파이팅은 이 객체가 꺼져 있어 그대로.

  등장 1.5초   시네마 띠 12px · 무대 색이 하늘 · 물 · 먼 배경에 물듦 · 비네트 · 보스 이름 카드 → 체력 바
  강도 0~3     페이즈 전환마다 0.6초에 걸쳐 한 단계 (색 · 하늘 어둡게 · 채도 · 물결 · 비네트 · 미세 흔들림 · 테마 파티클)
  위기         가장자리 빨간 맥박 (곡 박자에 맞춰, 박 정보가 없으면 일정한 맥박)
  박자 펄스    SUNO 보스 곡 마디 첫 박마다 밝기 +4% (강도 2+, 예고 중 끔)
  임팩트       큰 행동 순간 흔들림 · 물 충격파 · 강도 3 색 갈라짐 · 번쩍임(착수 · 페이즈, 3초에 1번) — 히트스톱은 game.hitstop
  받아침       퍼펙트 순간 흰 금색 테두리

그리는 자리 (규칙 '신호 보호'):
  palette()     하늘 · 물 · 먼 배경 팔레트 키에만 무대 색 → 구운 배경 띠 캐시(_bg_band)가 그대로 받아 씀 (매 프레임 비용 없음)
  vignettes()   ScreenFX.draw_edges 의 비네트에 끼움 (전설 금빛 테두리 대신, 중간 · 낮음 화질은 한 장으로 합쳐짐)
  draw_fx()     게이지 · 신호보다 먼저 — 보호 칸(holes: 가운데 · 물고기 신호 · 게이지 묶음)은 건너뜀
  draw_bars()   HUD 아래, 세계 위
  draw_card()   체력 바 자리 (카드가 끝나면 체력 바)
화면 효과 줄이기: 색 · 비네트만 (흔들림 · 번쩍임 · 박자 펄스 · 히트스톱 · 파티클 · 충격파 · 색 갈라짐 · 받아침 테두리 끔).
"""
import math
import random

import pygame

from src.core import fxq
from src.core.mathutil import clamp, lerp, lerp_color

SKY_KEYS = ("sky_top", "sky_bottom", "cloud")
FAR_KEYS = ("mountain_far", "mountain_near")
WATER_KEYS = ("water_top", "water_bottom", "wave_light", "wave_dark", "reflection")
WORLD_KEYS = SKY_KEYS + FAR_KEYS + WATER_KEYS
_CFG = None
_SOFT: dict = {}


def cfg() -> dict:
    global _CFG
    if _CFG is None:
        from src.core.config import load_json
        _CFG = load_json("boss_arena.json")
    return _CFG


def entry(fish: dict | None) -> dict | None:
    """그 물고기의 무대 (전설 = 자기 칸, 환상 = 공통 칸). 보스가 아니면 None."""
    if not fish:
        return None
    if fish.get("rarity") == "phantom":
        return cfg()["bosses"]["phantom"]
    if fish.get("rarity") != "legend":
        return None
    return cfg()["bosses"].get(fish.get("id"))


def color_of(e: dict) -> tuple:
    c = e["color"]
    if c == "phantom":
        from src.fishing import phantom
        return tuple(phantom.COLOR)
    return tuple(c)


def _lum(c) -> float:
    return 0.299 * c[0] + 0.587 * c[1] + 0.114 * c[2] + 1.0


def _toward(v, tgt, amt: float):
    """v 를 tgt 쪽으로 amt — 밝기는 원래 색을 따라감 (밤 하늘은 깊은 무대 색, 낮은 밝은 무대 색)."""
    s = clamp((_lum(v) / _lum(tgt)) ** 0.6, 0.45, 1.6)
    t2 = tuple(int(clamp(c * s, 0, 255)) for c in tgt)
    return lerp_color(v, t2, amt)


def subtract(rect, holes) -> list:
    """rect 에서 holes 를 뺀 겹치지 않는 사각형들."""
    out = [pygame.Rect(rect)]
    for h in holes:
        nxt = []
        for r in out:
            if not r.colliderect(h):
                nxt.append(r)
                continue
            c = r.clip(h)
            if c.top > r.top:
                nxt.append(pygame.Rect(r.left, r.top, r.w, c.top - r.top))
            if c.bottom < r.bottom:
                nxt.append(pygame.Rect(r.left, c.bottom, r.w, r.bottom - c.bottom))
            if c.left > r.left:
                nxt.append(pygame.Rect(r.left, c.top, c.left - r.left, c.h))
            if c.right < r.right:
                nxt.append(pygame.Rect(c.right, c.top, r.right - c.right, c.h))
        out = nxt
    return out


def _soft(w: int, h: int, col, seed: int) -> pygame.Surface:
    key = (w, h, col, seed)
    s = _SOFT.get(key)
    if s is None:
        r = random.Random(seed)
        s = pygame.Surface((w, h), pygame.SRCALPHA)
        for _ in range(6):
            ew, eh = r.uniform(0.45, 0.9) * w, r.uniform(0.45, 0.9) * h
            pygame.draw.ellipse(s, (*col, 60), (r.uniform(0, w - ew), r.uniform(0, h - eh), ew, eh))
        if len(_SOFT) > 64:
            _SOFT.clear()
        _SOFT[key] = s
    return s


SOFT_KINDS = ("mist", "cloud", "dark", "steam")


class BossArena:
    def __init__(self, w: int, h: int):
        self.w, self.h = w, h
        self.rnd = random.Random(11)
        self.reset()

    def reset(self) -> None:
        self.active = False
        self.e = None
        self.t = 0.0
        self.end_t = None
        self.level = 0.0
        self.target = 0
        self.parts: list[list] = []
        self.acc: dict = {}
        self.rings: list[list] = []
        self.kick = None            # (dx, dy, 남은 초, 처음 초)
        self.rgb_t = 0.0
        self.flash_t = 0.0
        self.last_flash = -99.0
        self.parry_t = 0.0
        self.bright_t = 0.0
        self.pulse_t = 0.0
        self.crisis = False
        self.crisis_k = 0.0
        self.tele = 1.0
        self.reduce = False
        self.shake_on = True
        self.beats_live = False
        self.horizon = self.h // 2
        self.fish_pos = None
        self.flashes = 0            # 기록 (깜빡임 횟수 로그)
        self.flash_times: list = []  # 번쩍임 시각 (무대 시계) — 3초에 1번 검사
        self.card_hold = None       # 전설 도약 (CU10): 카드가 올라가기 시작하는 시각 = 착수 (없으면 entrance 값)
        self.card_end = None

    # ───────────────────────── 수명 ─────────────────────────
    def start(self, fish: dict) -> bool:
        e = entry(fish)
        self.reset()
        if e is None:
            return False
        self.active = True
        self.e = e
        self.fish = fish
        self.phantom = fish.get("rarity") == "phantom"
        self.color = color_of(e)
        self.color2 = tuple(e["color2"]) if e.get("color2") else None
        self.level = 1.0
        self.target = 1
        return True

    def finish(self) -> None:
        """파이팅이 끝남(잡음 · 놓침): 띠가 빠지고 색이 0.6초에 걸쳐 돌아감."""
        if self.active and self.end_t is None:
            self.end_t = self.t
            self.target = 0
            self.parts.clear()
            self.rings.clear()

    def stop(self) -> None:
        self.reset()

    # ───────────────────────── 값 ─────────────────────────
    def lv(self, key: str) -> float:
        L = cfg()["levels"]
        a = int(clamp(math.floor(self.level), 0, 3))
        b = min(3, a + 1)
        return lerp(L[str(a)][key], L[str(b)][key], self.level - a)

    def level_int(self) -> int:
        return int(self.level + 0.001)

    def entrance_k(self) -> float:
        en = cfg()["entrance"]
        return clamp((self.t - en["color_from"]) / en["color_sec"], 0, 1)

    def color_amt(self) -> float:
        if not self.active:
            return 0.0
        amt = self.lv("color") * self.entrance_k()
        if self.phantom:
            amt *= cfg()["phantom_color_mult"]
        return amt

    def bar_px(self) -> int:
        if not self.active:
            return 0
        en = cfg()["entrance"]
        k = clamp(self.t / en["bar_in"], 0, 1)
        if self.end_t is not None:
            k = min(k, 1 - clamp((self.t - self.end_t) / en["bar_out"], 0, 1))
        return int(round(en["bar_px"] * (1 - (1 - k) ** 2)))

    @property
    def card_on(self) -> bool:
        return self.active and self.end_t is None and self.t < (self.card_end or cfg()["entrance"]["card_end"])

    def wave_mult(self) -> float:
        return lerp(1.0, self.lv("wave"), self.entrance_k()) if self.active else 1.0

    def palette(self, pal: dict) -> dict:
        """하늘 · 물 · 먼 배경 키에만 무대 색 (32단계로 양자화 — 강도가 바뀌는 0.6초 동안에도 배경 띠를 몇 번만 다시 굽게)."""
        if not self.active:
            return pal
        amt, dark, desat = self._pal_vals()
        if amt <= 0 and dark <= 0 and desat <= 0:
            return pal
        ck = (amt, dark, desat, tuple(pal.get(k) for k in WORLD_KEYS))
        hit = getattr(self, "_pal_cache", None)
        if hit is not None and hit[0] == ck:
            out = dict(pal)
            out.update(hit[1])
            return out
        out = dict(pal)
        c1, c2 = self.color, self.color2
        for key in WORLD_KEYS:
            v = pal.get(key)
            if not isinstance(v, tuple):
                continue
            tgt = c1
            if c2 is not None and key == "wave_light":
                tgt = c2
            elif c2 is not None and key == "sky_bottom":
                tgt = lerp_color(c1, c2, 0.35)
            out[key] = _toward(v, tgt, amt)
        if dark > 0:
            for key in SKY_KEYS:
                if isinstance(out.get(key), tuple):
                    out[key] = lerp_color(out[key], (0, 0, 0), dark)
        if desat > 0:
            for key in FAR_KEYS:
                v = out.get(key)
                if isinstance(v, tuple):
                    g = int(_lum(v) - 1)
                    out[key] = lerp_color(v, (g, g, g), desat)
        self._pal_cache = (ck, {k: out[k] for k in WORLD_KEYS if k in out})
        return out

    PAL_HZ = 12   # 무대 색이 바뀌는 동안 팔레트 갱신 횟수/초 — 배경 띠를 원래 굽는 빈도(bg_fps 8~15) 이상으로 다시 굽지 않게

    def _pal_vals(self) -> tuple:
        last = getattr(self, "_pal_last", None)
        if last is not None and self.t - last[0] < 1.0 / self.PAL_HZ and self.t >= last[0]:
            return last[1]
        ek = self.entrance_k()
        vals = (round(self.color_amt() * 32) / 32, round(self.lv("sky_dark") * ek * 32) / 32,
                round(self.lv("desat") * ek * 32) / 32)
        if last is None or vals != last[1]:
            self._pal_last = (self.t, vals)
        return vals

    def vignettes(self) -> list:
        """ScreenFX.draw_edges 에 끼울 비네트 [(색, 세기)]."""
        if not self.active:
            return []
        out = []
        ek = self.entrance_k()
        amt = self.lv("vignette") * ek * self.tele
        if self.bright_t > 0 and not self.reduce:
            amt += cfg()["beat"]["vignette_add"] * (self.bright_t / cfg()["beat"]["sec"])
        if amt > 0.01:
            out.append((lerp_color(self.color, (0, 0, 0), 0.45), amt))
        if self.crisis_k > 0.01:
            cc = cfg()["crisis"]
            pulse = 0.0
            if not self.reduce:
                if self.beats_live:
                    pulse = clamp(self.pulse_t / cc["pulse_sec"], 0, 1)
                else:
                    pulse = 0.5 + 0.5 * math.sin(self.t * math.tau * cc["fallback_hz"])
            out.append((tuple(cc["color"]), self.crisis_k * (cc["vignette_add"] + cc["pulse"] * pulse) * self.tele))
        if self.parry_t > 0 and not self.reduce:
            pc = cfg()["impact"]["parry"]
            out.append((tuple(pc["color"]), pc["amount"] * self.parry_t / pc["sec"]))
        return out

    def shake_offset(self) -> tuple[int, int]:
        if not self.active or self.reduce or not self.shake_on:
            return 0, 0
        s = self.lv("shake") * self.entrance_k() * self.tele
        dx = int(round(math.sin(self.t * 5.3) * s * 1.2))
        dy = int(round(math.sin(self.t * 6.7 + 1.3) * s * 0.8)) if s >= 0.9 else 0
        if self.kick is not None:
            kx, ky, left, total = self.kick
            k = left / total
            dx += int(round(kx * k))
            dy += int(round(ky * k))
        return dx, dy

    # ───────────────────────── 틱 ─────────────────────────
    def update(self, dt: float, ctx: dict) -> None:
        """dt = 실제 초. ctx: target(강도) · crisis · telegraph · reduce · shake_on · horizon · fish_pos · beats(['bar'|'beat']) ·
        beats_live(박 정보 있음) · holes."""
        if not self.active:
            return
        self.t += dt
        self.reduce = bool(ctx.get("reduce"))
        self.shake_on = bool(ctx.get("shake_on", True))
        self.horizon = int(ctx.get("horizon", self.horizon))
        self.fish_pos = ctx.get("fish_pos")
        self.beats_live = bool(ctx.get("beats_live"))
        if self.end_t is None:
            self.target = int(ctx.get("target", self.target))
            self.crisis = bool(ctx.get("crisis"))
        else:
            self.crisis = False
        step = dt / cfg()["level_sec"]
        if self.level < self.target:
            self.level = min(float(self.target), self.level + step)
        elif self.level > self.target:
            self.level = max(float(self.target), self.level - step)
        tm = cfg()["telegraph_mult"] if ctx.get("telegraph") else 1.0
        self.tele += (tm - self.tele) * min(1.0, dt / 0.15)
        self.crisis_k += ((1.0 if self.crisis else 0.0) - self.crisis_k) * min(1.0, dt / 0.25)
        for name in ("rgb_t", "flash_t", "parry_t", "bright_t", "pulse_t"):
            setattr(self, name, max(0.0, getattr(self, name) - dt))
        if self.kick is not None:
            kx, ky, left, total = self.kick
            left -= dt
            self.kick = None if left <= 0 else (kx, ky, left, total)
        for ev in ctx.get("beats", ()):
            self.beat(ev, bool(ctx.get("telegraph")))
        for r in self.rings:
            r[2] += dt
        ring_sec = cfg()["impact"]["ring_sec"]
        self.rings = [r for r in self.rings if r[2] < ring_sec]
        if self.end_t is not None and self.t - self.end_t > max(cfg()["level_sec"], cfg()["entrance"]["bar_out"]) + 0.05:
            self.reset()
            return
        self._particles(dt)

    def beat(self, kind: str, telegraph: bool = False) -> None:
        if not self.active or self.end_t is not None:
            return
        b = cfg()["beat"]
        if kind == "beat" and self.crisis:
            self.pulse_t = cfg()["crisis"]["pulse_sec"]
        if kind != "bar" or self.reduce or telegraph or self.level_int() < 2:
            return
        self.bright_t = b["sec"]
        if self.level_int() >= 3:
            for _ in range(int(b["edge_spray"] * fxq.particles() + 0.5)):
                self._spray_edge()

    # ───────────────────────── 이벤트 ─────────────────────────
    def impact(self, kind: str, pos=None, direction: float = 0.0) -> dict:
        """큰 행동 순간. 돌려주는 값 = {'hitstop': 초} (장면이 game.hitstop 으로 — 화면 효과 줄이기면 0)."""
        if not self.active or self.end_t is not None:
            return {"hitstop": 0.0}
        ic = cfg()["impact"]
        if self.reduce:
            return {"hitstop": 0.0}
        lvl = max(1, self.level_int())
        px = ic["shake_px"][str(min(3, lvl))]
        d = direction or self.rnd.choice((-1.0, 1.0))
        self.kick = (d * px, px * 0.35, ic["shake_sec"], ic["shake_sec"])
        if pos is not None:
            self.rings.append([pos[0], pos[1], 0.0])
        if lvl >= 3:
            self.rgb_t = ic["rgb_sec"]
        if kind in ic["flash_events"] and self.t - self.last_flash >= ic["flash_gap"]:
            self.flash_t = 1e-3 + 1 / 60   # 1프레임
            self.last_flash = self.t
            self.flashes += 1
            self.flash_times.append(round(self.t, 3))
        return {"hitstop": 0.0 if kind in ic.get("no_hitstop", ()) else ic["hitstop"]}

    def parry(self, pos=None) -> None:
        if not self.active or self.reduce or self.end_t is not None:
            return
        pc = cfg()["impact"]["parry"]
        self.parry_t = pc["sec"]
        if pos is not None:
            for _ in range(int(pc["spray"] * fxq.particles() + 0.5)):
                a = self.rnd.uniform(math.pi * 1.1, math.pi * 1.9)
                v = self.rnd.uniform(60, 130)
                self.parts.append(["spray", pos[0], pos[1], math.cos(a) * v, math.sin(a) * v, 0.0,
                                   self.rnd.uniform(0.25, 0.4), 1, (255, 248, 225), None, self.rnd.random(), None])

    # ───────────────────────── 파티클 ─────────────────────────
    def _area(self, name: str) -> pygame.Rect:
        w, h, hz = self.w, self.h, self.horizon
        return {"sky": pygame.Rect(0, 0, w, hz), "water": pygame.Rect(0, hz, w, h - hz),
                "horizon": pygame.Rect(0, hz - 34, w, 44), "bottom": pygame.Rect(0, int(h * 0.72), w, h - int(h * 0.72))
                }.get(name, pygame.Rect(0, 0, w, h))

    def _spray_edge(self) -> None:
        side = self.rnd.choice((-1, 1))
        x = 2 if side < 0 else self.w - 2
        y = self.rnd.uniform(self.horizon, self.h - 20)
        self.parts.append(["spray", x, y, -side * self.rnd.uniform(-90, -40), self.rnd.uniform(-90, -40), 0.0,
                           self.rnd.uniform(0.3, 0.5), 1, (235, 245, 255), None, self.rnd.random(), None])

    def _emitters(self) -> list:
        return list(self.e.get("emitters", [])) + list(cfg()["water_fx"]["emitters"])

    def _particles(self, dt: float) -> None:
        r = self.rnd
        mv = dt * self.tele
        live = []
        for p in self.parts:
            p[5] += dt
            if p[5] >= p[6]:
                continue
            p[1] += p[3] * mv
            p[2] += p[4] * mv
            if p[0] in ("mote", "leaf"):
                p[1] += math.sin(p[5] * 3.0 + p[10] * 6.0) * 10 * mv
            if p[0] == "spray":
                p[4] += 260 * mv
            live.append(p)
        self.parts = live
        if self.reduce:
            self.parts.clear()
            return
        if self.end_t is not None:
            return
        lv = self.level_int()
        mult = self.lv("particles") * self.entrance_k() * fxq.particles()
        cap = int(cfg()["particle_cap"] * fxq.particles())
        if mult <= 0:
            return
        for i, em in enumerate(self._emitters()):
            if lv < em.get("min_level", 1):
                continue
            key = (i, em["kind"])
            self.acc[key] = self.acc.get(key, 0.0) + em["rate"] * mult * dt
            while self.acc[key] >= 1.0:
                self.acc[key] -= 1.0
                if len(self.parts) >= cap:
                    break
                if "max" in em and sum(1 for p in self.parts if p[11] == key) >= em["max"]:
                    continue
                self.parts.append(self._spawn(em, key, lv, r))

    def _spawn(self, em: dict, key, lv: int, r) -> list:
        area = self._area(em.get("area", "full"))
        life = r.uniform(*em["life"])
        vx = r.uniform(*em["vx"]) if "vx" in em else 0.0
        vy = r.uniform(*em["vy"]) if "vy" in em else 0.0
        lo, hi = em.get("size", [1, 1])
        size = r.uniform(lo, hi) + (1 if lv >= 3 and hi <= 3 and em["kind"] in ("mote", "flake", "twinkle") and r.random() < 0.3 else 0)
        kind = em["kind"]
        if kind in SOFT_KINDS or kind in ("twinkle", "bolt", "crystal", "foam") or (abs(vx) < 1 and abs(vy) < 1):
            x, y = r.uniform(area.left, area.right), r.uniform(area.top, area.bottom)
        elif abs(vy) >= abs(vx):
            x = r.uniform(area.left - vx * life * 0.5, area.right - vx * life * 0.3)
            y = area.top - 2 if vy > 0 else area.bottom + 2
            if kind in ("mote", "streak", "bubble") and vy < 0:
                y = r.uniform(area.top + area.h * 0.4, area.bottom)
        else:
            x = area.left - size if vx > 0 else area.right + size
            y = r.uniform(area.top, area.bottom)
        col = tuple(em["color"])
        if em.get("color2") and r.random() < 0.35:
            col = tuple(em["color2"])
        extra = None
        if kind == "bolt":
            pts, cx, cy = [], x, self.horizon - r.uniform(2, 14)
            n = r.randint(4, 6)
            for j in range(n):
                pts.append((cx + r.uniform(-4, 4), cy - size * (1 - j / (n - 1))))
            extra = pts
        return [kind, x, y, vx, vy, 0.0, life, size, col, extra, r.random(), key]

    # ───────────────────────── 그리기 ─────────────────────────
    def draw_bars(self, canvas) -> None:
        b = self.bar_px()
        if b <= 0:
            return
        w, h = canvas.get_size()
        canvas.fill((0, 0, 0), (0, 0, w, b))
        canvas.fill((0, 0, 0), (0, h - b, w, b))

    def draw_fx(self, canvas, holes=()) -> None:
        """게이지 · 신호보다 먼저. holes = 보호 칸 (그 안은 건드리지 않음)."""
        if not self.active:
            return
        holes = [pygame.Rect(hh) for hh in holes]
        if self.rgb_t > 0 and fxq.level() >= 1 and not self.reduce:
            self._rgb_split(canvas, holes)
        if not self.reduce:
            self._draw_parts(canvas, holes)
            self._draw_rings(canvas, holes)
        full = canvas.get_rect()
        if self.bright_t > 0 and not self.reduce:
            v = int(255 * cfg()["beat"]["bright"] * (self.bright_t / cfg()["beat"]["sec"]))
            if v > 0:
                for rr in subtract(full, holes):
                    canvas.fill((v, v, v), rr, special_flags=pygame.BLEND_RGB_ADD)
        if self.flash_t > 0 and not self.reduce:
            fl = getattr(self, "_flash_surf", None)
            if fl is None or fl.get_size() != canvas.get_size():
                from src.render.screen import opaque
                fl = self._flash_surf = opaque(canvas.get_size())
            fl.fill(self.color)
            fl.set_alpha(int(255 * cfg()["impact"]["flash"]))
            for rr in subtract(full, holes):
                canvas.blit(fl, rr.topleft, rr)

    def _hit(self, holes, x: float, y: float, pad: int = 2) -> bool:
        r = pygame.Rect(int(x) - pad, int(y) - pad, pad * 2 + 1, pad * 2 + 1)
        return any(h.colliderect(r) for h in holes)

    def _draw_parts(self, canvas, holes) -> None:
        dim = self.tele < 0.99
        w, h = canvas.get_size()
        for p in self.parts:
            kind, x, y, vx, vy, age, life, size, col, extra, seed, _ = p
            if dim and seed > 0.7:
                continue   # 예고 중: 30% 덜 그림
            u = age / life
            if kind in SOFT_KINDS:
                self._draw_soft(canvas, holes, p, u)
                continue
            if not (-20 < x < w + 20 and -20 < y < h + 20) or self._hit(holes, x, y):
                continue
            ix, iy, s = int(x), int(y), max(1, int(size))
            if kind == "streak" or kind == "wind":
                sp = math.hypot(vx, vy) or 1.0
                canvas.fill(col, (ix, iy, 1, 1)) if s <= 1 else \
                    pygame.draw.line(canvas, col, (ix, iy), (int(x - vx / sp * s), int(y - vy / sp * s)), 1)
            elif kind == "twinkle":
                if 0.1 < u < 0.9:
                    canvas.fill(col, (ix, iy, s, s))
                    if s >= 2 and 0.35 < u < 0.65:
                        canvas.fill(col, (ix - 1, iy + s // 2, s + 2, 1))
            elif kind == "leaf":
                canvas.fill(col, (ix, iy, 2, 1) if int(age * 6 + seed * 4) % 2 else (ix, iy, 1, 2))
            elif kind == "bubble":
                pygame.draw.circle(canvas, col, (ix, iy), s, 1)
            elif kind == "ink":
                pygame.draw.line(canvas, col, (ix, iy), (ix - s, iy + int(s * 0.25)), 2)
            elif kind == "slash":
                k = 1 - u
                pygame.draw.line(canvas, col, (ix, iy), (int(x + s * k), int(y - s * 0.45 * k)), 1)
            elif kind == "crystal":
                c2 = (255, 255, 255) if int(age * 5 + seed * 7) % 4 == 0 else col
                pygame.draw.polygon(canvas, c2, [(ix, iy - s), (ix + s - 1, iy), (ix, iy + s), (ix - s + 1, iy)])
            elif kind == "foam":
                if 0.08 < u < 0.92:
                    canvas.fill(col, (ix, iy, s, 1))
            elif kind == "bolt":
                if extra and len(extra) > 1:
                    if any(self._hit(holes, px_, py_, 1) for px_, py_ in extra):
                        continue
                    pygame.draw.lines(canvas, col, False, extra, 1)
            else:   # mote · flake · ash · spray
                canvas.fill(col, (ix, iy, s, s))

    def _draw_soft(self, canvas, holes, p, u: float) -> None:
        kind, x, y, _, _, _, _, size, col, _, seed, _ = p
        sw, sh = int(size), int(size * (0.35 if kind in ("mist", "dark") else 0.55))
        spr = _soft(max(4, sw), max(3, sh), col, int(seed * 5))
        fade = clamp(min(u / 0.25, (1 - u) / 0.3), 0, 1)
        base = {"mist": 0.9, "cloud": 1.0, "dark": 1.3, "steam": 0.8}.get(kind, 1.0)
        spr.set_alpha(int(255 * clamp(base * fade * self.tele, 0, 1)))
        rect = pygame.Rect(int(x - sw / 2), int(y - sh / 2), spr.get_width(), spr.get_height())
        for rr in subtract(rect, holes):
            canvas.blit(spr, rr.topleft, rr.move(-rect.x, -rect.y))

    def _draw_rings(self, canvas, holes) -> None:
        if not self.rings:
            return
        ic = cfg()["impact"]
        r0, r1 = ic["ring_px"]
        for x, y, age in self.rings:
            k = age / ic["ring_sec"]
            rw = int(lerp(r0, r1, k ** 0.7))
            rh = max(2, int(rw * 0.28))
            s = pygame.Surface((rw * 2 + 2, rh * 2 + 2), pygame.SRCALPHA)
            pygame.draw.ellipse(s, (255, 255, 255, int(230 * (1 - k))), s.get_rect(), 1)
            rect = s.get_rect(center=(int(x), int(y)))
            for rr in subtract(rect, holes):
                canvas.blit(s, rr.topleft, rr.move(-rect.x, -rect.y))

    def _rgb_split(self, canvas, holes) -> None:
        """강도 3 임팩트: 빨강 채널 오른쪽 · 파랑 채널 왼쪽 1px (보호 칸은 원래대로)."""
        size = canvas.get_size()
        src = getattr(self, "_rgb_src", None)
        if src is None or src.get_size() != size:
            from src.render.screen import opaque
            src = self._rgb_src = opaque(size)
            self._rgb_tmp = opaque(size)
        tmp = self._rgb_tmp
        px = cfg()["impact"]["rgb_px"]
        src.blit(canvas, (0, 0))
        tmp.blit(src, (0, 0))
        tmp.fill((255, 0, 0), special_flags=pygame.BLEND_RGB_MULT)
        canvas.fill((0, 255, 255), special_flags=pygame.BLEND_RGB_MULT)
        canvas.blit(tmp, (px, 0), special_flags=pygame.BLEND_RGB_ADD)
        tmp.blit(src, (0, 0))
        tmp.fill((0, 0, 255), special_flags=pygame.BLEND_RGB_MULT)
        canvas.fill((255, 255, 0), special_flags=pygame.BLEND_RGB_MULT)
        canvas.blit(tmp, (-px, 0), special_flags=pygame.BLEND_RGB_ADD)
        for hh in holes:
            canvas.blit(src, hh.topleft, hh)

    def draw_card(self, canvas) -> None:
        """보스 이름 카드 (🅰-1): 금색 선이 펼쳐짐 → 1.0초 머묾 → 위로 올라가며 체력 바 자리로."""
        if not self.card_on:
            return
        from src.core.fonts import get_font
        from src.fishing import phantom
        en = cfg()["entrance"]
        t = self.t - en["card_from"]
        if t < 0:
            return
        w = canvas.get_width()
        gold = tuple(phantom.COLOR) if self.phantom else tuple(en["gold"])
        light = tuple(phantom.COLOR_LIGHT) if self.phantom else (255, 236, 170)
        name = "???" if self.phantom else self.fish.get("name", "")
        sub = self.e.get("title_sub", "")
        hold = self.card_hold if self.card_hold is not None else en["card_hold_until"]
        end = self.card_end if self.card_end is not None else en["card_end"]
        rise = clamp((self.t - hold) / (end - hold), 0, 1)
        y = int(lerp(en["card_y"], 20, rise * rise))
        alpha = int(255 * clamp(t / 0.15, 0, 1) * (1 - rise))
        key = (name, sub, light)
        if getattr(self, "_card_imgs", (None,))[0] != key:   # 글자는 한 번만 그려 둠
            f1, f2 = get_font(en["title_px"]), get_font(en["sub_px"])
            self._card_imgs = (key, f1.render(name, False, light), f1.render(name, False, (16, 10, 6)),
                               f2.render(sub, False, (225, 225, 235)), f2.render(sub, False, (16, 10, 6)))
        _, t1, s1, t2, s2 = self._card_imgs
        for img in (t1, s1, t2, s2):
            img.set_alpha(alpha)
        cx = w // 2
        canvas.blit(s1, (cx - t1.get_width() // 2 + 1, y - 9))
        canvas.blit(t1, (cx - t1.get_width() // 2, y - 10))
        line_k = clamp(t / en["card_line_sec"], 0, 1)
        half = int((max(t1.get_width(), t2.get_width()) // 2 + 34) * (1 - (1 - line_k) ** 2) * (1 - rise * 0.5))
        ly = y + 9
        if half > 0 and alpha > 8:
            col = lerp_color((0, 0, 0), gold, alpha / 255)
            pygame.draw.line(canvas, col, (cx - half, ly), (cx + half, ly), 1)
            canvas.fill(col, (cx - half - 2, ly - 1, 2, 3))
            canvas.fill(col, (cx + half + 1, ly - 1, 2, 3))
        if rise < 0.6:
            canvas.blit(s2, (cx - t2.get_width() // 2 + 1, ly + 4))
            canvas.blit(t2, (cx - t2.get_width() // 2, ly + 3))
