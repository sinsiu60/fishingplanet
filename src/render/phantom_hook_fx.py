"""환상 입질 연출 그림 (DETAILS.md B-5 · B-6, DESIGN.md 45장 DT6). 시간 · 소리 표는 data/details/hook_cinematics.json.

전설과 반대로 조용하고 신비롭게. 정적(숨 멎음) · 공중에 멈춘 물방울 · 오로라 = 환상 전용 표현 (여기서만 쓴다).
HookCine 의 ② 사건 'fx' · 'unique' 를 장면이 여기로 넘긴다 (시간은 실제 초).
그리는 자리: draw_world = 찌 · 줄보다 먼저 (보라 터짐 고리 · 깊은 등불 · 달 조각) / draw_screen = 카메라 연출 뒤 (나머지)
"""
import math
import random

import pygame

from src.core.mathutil import clamp, lerp, lerp_color

VIOLET = (180, 140, 240)
_SPR: dict = {}


def _soft(w: int, h: int, col, a: int, seed: int) -> pygame.Surface:
    key = (w, h, col, a, seed)
    s = _SPR.get(key)
    if s is None:
        r = random.Random(seed)
        s = pygame.Surface((w, h), pygame.SRCALPHA)
        for _ in range(6):
            ew, eh = r.uniform(0.45, 0.85) * w, r.uniform(0.5, 0.9) * h
            pygame.draw.ellipse(s, (*col, a), (r.uniform(0, w - ew), r.uniform(0, h - eh), ew, eh))
        _SPR[key] = s
    return s


def contract_rings(canvas, x: float, y: float, u: float, n: int, radius: float) -> None:
    """① 환상: 보랏빛 파문이 거꾸로 오므라들며 찌로 빨려 들어감 (u 0→1)."""
    for k in range(n):
        v = clamp(u * 1.3 - k * 0.15, 0, 1)
        rx = (1 - v) * radius + 1
        if v >= 1:
            continue
        ry = max(1, rx * 0.3)
        col = lerp_color((90, 70, 140), VIOLET, 0.4 + 0.6 * v)
        pygame.draw.ellipse(canvas, col, (x - rx, y - ry, rx * 2, ry * 2), 1)


class PhantomHookFx:
    def __init__(self, rnd=None):
        self.rnd = rnd or random.Random()
        self.items: list[dict] = []
        self.reeds_k = 0.0   # 보랏빛 갈대잉어: 갈대가 보랏빛으로 일렁임 (0~1)

    def start(self, name: str, ctx: dict, sec: float = 0.6) -> None:
        r = self.rnd
        it = {"name": name, "t": 0.0, "sec": sec, "ctx": ctx}
        bx, by = ctx["bobber"]
        if name == "frozen_drops":
            n = r.randint(8, 16)
            it["drops"] = [[bx + r.uniform(-26, 26), by + r.uniform(-1, 2), r.uniform(12, 40), r.uniform(0, 0.12)] for _ in range(n)]
        elif name == "mist_inhale":
            it["blobs"] = [(r.uniform(0, math.tau), r.uniform(90, 150)) for _ in range(7)]
        elif name == "butterflies":
            it["b"] = [[bx + r.uniform(-40, 40), by + r.uniform(-2, 4), r.uniform(-14, 14), r.uniform(30, 60), r.uniform(0, 6)]
                       for _ in range(12)]
        elif name == "violet_embers":
            w = ctx["w"]
            it["e"] = [[bx + r.uniform(-w * 0.3, w * 0.3), by + r.uniform(-4, 10), r.uniform(-6, 6), r.uniform(18, 36), r.uniform(0, 6)]
                       for _ in range(22)]
        elif name == "amethyst_bloom":
            it["c"] = [(i / 6 * math.tau + r.uniform(-0.2, 0.2), r.uniform(10, 18), r.uniform(0, 0.15)) for i in range(6)]
        elif name == "moon_shatter":
            it["shards"] = [(r.uniform(0, math.tau), r.uniform(10, 22), r.uniform(-3, 3)) for _ in range(9)]
        self.items.append(it)

    @property
    def active(self) -> bool:
        return bool(self.items)

    def update(self, dt: float) -> None:
        for it in self.items:
            it["t"] += dt
        self.items = [it for it in self.items if it["t"] < it["sec"]]
        vr = next((it for it in self.items if it["name"] == "violet_reeds"), None)
        self.reeds_k = math.sin(math.pi * min(1.0, vr["t"] / vr["sec"])) if vr else 0.0

    def clear(self) -> None:
        self.items.clear()
        self.reeds_k = 0.0

    # ── 그리기 ──
    def draw_world(self, canvas, pal) -> None:
        for it in self.items:
            n, t, sec, ctx = it["name"], it["t"], it["sec"], it["ctx"]
            u = clamp(t / sec, 0, 1)
            bx, by = ctx["bobber"]
            w = ctx["w"]
            if n == "violet_burst":
                # 오므라들었던 보랏빛이 한꺼번에 터짐 (찌 → 바깥)
                for k in range(3):
                    v = clamp(u * 1.3 - k * 0.12, 0, 1)
                    if 0 < v < 1:
                        rx = v * w * 0.6 + 2
                        ry = rx * 0.22
                        col = lerp_color(VIOLET, pal["water_top"], v * 0.8)
                        pygame.draw.ellipse(canvas, col, (bx - rx, by - ry, rx * 2, ry * 2), 2 if v < 0.4 else 1)
            elif n == "deep_lantern":
                # 찌 아래 깊은 곳에서 등불 하나가 켜졌다 꺼짐
                k = math.sin(math.pi * u)
                g = _SPR.get("lantern")
                if g is None:
                    g = _SPR["lantern"] = pygame.Surface((31, 21))
                    for rr, v in ((15, 30), (10, 70), (5, 150), (2, 230)):
                        pygame.draw.ellipse(g, (v, int(v * 0.82), int(v * 0.55)), (15 - rr, 10 - rr * 0.66, rr * 2, rr * 1.33))
                gg = g.copy()
                gg.fill((int(255 * k),) * 3, special_flags=pygame.BLEND_RGB_MULT)
                canvas.blit(gg, (int(bx) - 15, int(by) + 12), special_flags=pygame.BLEND_RGB_ADD)
            elif n == "moon_shatter":
                # 수면에 비친 달이 조각조각 부서졌다 다시 모임
                mx, my = ctx["moon"]
                spread = math.sin(math.pi * u)
                col = lerp_color((236, 236, 214), VIOLET, 0.35)
                if spread < 0.15:
                    pygame.draw.ellipse(canvas, col, (mx - 7, my - 2, 14, 4))
                for ang, dist, rot in it["shards"]:
                    x = mx + math.cos(ang) * dist * spread
                    y = my + math.sin(ang) * dist * spread * 0.35
                    canvas.fill(col, (int(x) - 2, int(y), 4, 1))
                    canvas.fill(col, (int(x) - 1 + int(rot * spread), int(y) + 1, 3, 1))

    def draw_screen(self, canvas, pal) -> None:
        for it in self.items:
            n, t, sec, ctx = it["name"], it["t"], it["sec"], it["ctx"]
            u = clamp(t / sec, 0, 1)
            bx, by = ctx["bobber"]
            w, h, hz = ctx["w"], ctx["h"], ctx["horizon"]
            if n == "frozen_drops":
                # 0~0.6초: 수면에서 물방울이 위로 떠오른 채 멈춤 / 0.6~: 한꺼번에 쏟아짐 (환상 전용)
                col = lerp_color((230, 220, 255), VIOLET, 0.3)
                for x, y0, hgt, delay in it["drops"]:
                    if t < 0.6:
                        k = clamp((t - delay) / 0.12, 0, 1)
                        y = y0 - hgt * (1 - (1 - k) ** 3)   # 빠르게 솟다가 그 자리에 멈춤
                    else:
                        ft = t - 0.6
                        y = y0 - hgt + 0.5 * 420 * ft * ft
                        if y >= y0:
                            continue
                    canvas.fill(col, (int(x), int(y), 1, 2))
                    canvas.fill((255, 255, 255), (int(x), int(y), 1, 1))
            elif n == "mist_inhale":
                # 보라 안개가 찌로 한꺼번에 빨려 들어감
                for i, (ang, dist) in enumerate(it["blobs"]):
                    d = dist * (1 - u) ** 1.5
                    x, y = bx + math.cos(ang) * d, by + math.sin(ang) * d * 0.4
                    sz = max(4, int(46 * (1 - u) + 6))
                    s = _soft(sz * 2, sz, VIOLET, 60, 11 + i % 3)
                    s.set_alpha(int(255 * min(1.0, (1 - u) * 1.6)))
                    canvas.blit(s, (int(x - sz), int(y - sz / 2)))
            elif n == "violet_dusk":
                # 하늘이 0.5초 동안 보라 노을로 물듦
                k = math.sin(math.pi * clamp(t / 0.5, 0, 1))
                if k > 0.01:
                    s = _SPR.get(("dusk", w, hz))
                    if s is None:
                        s = _SPR[("dusk", w, hz)] = pygame.Surface((w, max(1, hz)), pygame.SRCALPHA)
                        for y in range(max(1, hz)):
                            v = y / max(1, hz)
                            s.fill((*lerp_color((120, 70, 190), (230, 120, 200), v), int(150 * (0.35 + 0.65 * v))), (0, y, w, 1))
                    s.set_alpha(int(255 * k))
                    canvas.blit(s, (0, 0))
            elif n == "meteor":
                # 하늘을 유성 하나가 가로지름
                v = clamp(t / 0.5, 0, 1)
                x, y = lerp(-20, w + 20, v), lerp(hz * 0.15, hz * 0.55, v)
                for k in range(22):
                    tx, ty = x - k * 3, y - k * 3 * (hz * 0.4) / (w + 40)
                    c = lerp_color((255, 245, 255), (120, 90, 200), k / 22)
                    th = 3 if k < 2 else 2 if k < 9 else 1
                    canvas.fill(c, (int(tx), int(ty) - th // 2, 3 if k == 0 else 2, th))
            elif n == "echo_bobbers":
                # 찌가 4개로 겹쳐 보였다가 하나로 합쳐짐
                from src.render.effects import draw_bobber
                spread = (1 - u) * 30
                size = ctx.get("bobber_size", 6)
                s = _SPR.get(("bob", size))
                if s is None:
                    s = _SPR[("bob", size)] = pygame.Surface((int(size * 3), int(size * 4)), pygame.SRCALPHA)
                    draw_bobber(s, pal, s.get_width() / 2, s.get_height() * 0.7, size, floating=True)
                s.set_alpha(int(210 * (1 - u) ** 0.7))
                for dx in (-1.5, -0.5, 0.5, 1.5):
                    if abs(dx) < 0.6 and u < 0.05:
                        continue
                    canvas.blit(s, (int(bx + dx * spread - s.get_width() / 2), int(by - s.get_height() * 0.7)))
            elif n == "amethyst_bloom":
                # 찌 주변에 작은 자수정 결정이 반짝 생겼다 사라짐
                for ang, dist, delay in it["c"]:
                    k = math.sin(math.pi * clamp((t - delay) / (sec - 0.15), 0, 1))
                    if k <= 0.05:
                        continue
                    x, y = bx + math.cos(ang) * dist, by + math.sin(ang) * dist * 0.4
                    s = 1 + 4 * k
                    pts = [(x, y - s * 1.4), (x + s * 0.6, y), (x, y + s * 0.4), (x - s * 0.6, y)]
                    pygame.draw.polygon(canvas, (176, 110, 226), pts)
                    canvas.fill((240, 220, 255), (int(x), int(y - s), 1, 1))
            elif n == "butterflies":
                # 수면에서 보랏빛 나비 떼가 날아오름
                for x0, y0, vx, vy, ph in it["b"]:
                    x = x0 + vx * t + math.sin(t * 6 + ph) * 3
                    y = y0 - vy * t
                    flap = int(t * 18 + ph) % 2
                    c = (214, 170, 255) if flap else (160, 112, 232)
                    ix, iy = int(x), int(y)
                    if flap:   # 날개 펼침: 위아래 2쌍
                        canvas.fill(c, (ix - 3, iy - 2, 3, 2)); canvas.fill(c, (ix + 1, iy - 2, 3, 2))
                        canvas.fill(c, (ix - 2, iy, 2, 2)); canvas.fill(c, (ix + 1, iy, 2, 2))
                    else:      # 날개 접힘
                        canvas.fill(c, (ix - 1, iy - 3, 1, 3)); canvas.fill(c, (ix + 1, iy - 3, 1, 3))
                    canvas.fill((250, 240, 255), (ix, iy - 2, 1, 3))
            elif n == "violet_embers":
                # 보랏빛 불씨가 수면 위로 흩날림
                for x0, y0, vx, vy, ph in it["e"]:
                    x = x0 + vx * t + math.sin(t * 5 + ph) * 4
                    y = y0 - vy * t
                    fl = 0.5 + 0.5 * math.sin(t * 20 + ph * 3)
                    c = lerp_color((140, 80, 210), (245, 200, 255), fl)
                    canvas.fill(c, (int(x), int(y), 2, 2))
                    if fl > 0.7:
                        canvas.fill((255, 240, 255), (int(x), int(y) - 1, 1, 1))
            elif n == "aurora_ribbon":
                # 하늘에 오로라 한 줄기가 흐름 (환상 전용 표현)
                k = math.sin(math.pi * u)
                s = _SPR.get(("aur", w, hz))
                if s is None:
                    s = _SPR[("aur", w, hz)] = pygame.Surface((int(w * 1.2), max(1, hz)), pygame.SRCALPHA)
                    for x in range(0, int(w * 1.2), 2):
                        yc = hz * 0.5 + math.sin(x * 0.03) * hz * 0.1
                        for j in range(18):
                            c = lerp_color((150, 255, 210), (200, 150, 255), j / 18)
                            s.fill((*c, int(200 * (1 - j / 18))), (x, int(yc + j), 2, 1))
                s.set_alpha(int(255 * k))
                canvas.blit(s, (int(-w * 0.15 + u * w * 0.15), 0))
            elif n == "spirit_ring":
                # 작은 정령 빛들이 찌 주위를 한 바퀴 돌고 사라짐
                fade = 1 - clamp((u - 0.8) / 0.2, 0, 1)
                for i in range(5):
                    a = u * math.tau + i / 5 * math.tau
                    x, y = bx + math.cos(a) * 16, by - 4 + math.sin(a) * 6
                    c = lerp_color(pal["water_top"], (235, 245, 255), fade)
                    halo = lerp_color(pal["water_top"], (190, 210, 255), fade * 0.6)
                    canvas.fill(halo, (int(x) - 1, int(y) - 1, 4, 4))
                    canvas.fill(c, (int(x), int(y), 2, 2))
