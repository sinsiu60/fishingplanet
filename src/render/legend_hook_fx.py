"""전설 입질 연출 그림 (DETAILS.md B-3 · B-4, DESIGN.md 45장 DT5). 시간 · 소리 표는 data/details/hook_cinematics.json.

HookCine 의 ② 사건 'fx' · 'unique' 를 장면이 여기로 넘긴다. 시간은 실제 초 (슬로모션과 무관).
그리는 자리: draw_world = 찌 · 줄보다 먼저 (거대한 그림자 · 빨려 드는 물결 — 찌를 가리지 않음)
             draw_screen = 카메라 연출 뒤 (물기둥 · 증기 · 수정 빛 · 전기 · 칼선 · 안개 · 돌풍 · 구름 · 가장자리 어둠 · 얼음 금)
남는 효과: 여우비 빗줄기(rain_fight) = 파이팅 내내 화면 효과로만 (실제 날씨는 그대로), 파이팅이 끝나면 끔.
환상 전용 표현(정적 · 공중에 멈춘 물방울 · 오로라)은 쓰지 않는다. 일렉트로 번개는 Lightning.strike (번쩍임 3초 · 화면 효과 줄이기 규칙 그대로).
"""
import math
import random

import pygame

from src.core.mathutil import clamp, lerp, lerp_color

GOLD = (255, 220, 120)
CRYSTAL_TIPS = [(14, 46, -0.2), (36, 64, 0.1), (60, 38, 0.3), (82, 26, 0.5), (452, 40, -0.4), (470, 58, -0.15)]
_SPR: dict = {}


def _soft(w: int, h: int, col, a: int, seed: int) -> pygame.Surface:
    key = ("soft", w, h, col, a, seed)
    s = _SPR.get(key)
    if s is None:
        r = random.Random(seed)
        s = pygame.Surface((w, h), pygame.SRCALPHA)
        for _ in range(7):
            ew, eh = r.uniform(0.4, 0.85) * w, r.uniform(0.45, 0.9) * h
            pygame.draw.ellipse(s, (*col, a), (r.uniform(0, w - ew), r.uniform(0, h - eh), ew, eh))
        _SPR[key] = s
    return s


def _edge_dark(w: int, h: int) -> pygame.Surface:
    """가장자리 어둠 (소나): 바깥 1.0 → 안쪽 0, 폭 48px 계단 그라데이션 (한 번만)."""
    key = ("edge", w, h)
    s = _SPR.get(key)
    if s is None:
        s = pygame.Surface((w, h), pygame.SRCALPHA)
        n = 48
        for i in range(n):
            a = int(255 * (1 - i / n) ** 1.6)
            pygame.draw.rect(s, (0, 0, 0, a), (i, i, w - 2 * i, h - 2 * i), 1)
        _SPR[key] = s
    return s


class LegendHookFx:
    def __init__(self, rnd=None):
        self.rnd = rnd or random.Random()
        self.items: list[dict] = []
        self.rain_fight = False   # 여우비: 파이팅 내내 가는 빗줄기 (화면 효과만)
        self.rain_burst = 0.0     # 여우비: 쏟아지는 순간 (굵게)
        self.reeds_k = 0.0        # 실바: 갈대가 찌 쪽으로 고개 숙임 (0~1)

    def start(self, name: str, ctx: dict, sec: float = 0.6) -> None:
        """ctx: bobber(화면 좌표) · w · h · horizon · scene(FishingScene)."""
        it = {"name": name, "t": 0.0, "sec": sec, "ctx": ctx}
        r = self.rnd
        if name == "sudden_rain":
            self.rain_fight = True
            self.rain_burst = sec
        elif name == "horizon_bolt":
            sc = ctx["scene"]
            sc.lightning.strike(sc.cam.horizon, sc.cam.width)   # 번쩍임은 3초 규칙 · 줄이기 설정을 따름
        elif name == "ice_crack_corners":
            w, h = ctx["w"], ctx["h"]
            cracks = []
            for cx, cy, sx, sy in ((0, 0, 1, 1), (w, 0, -1, 1), (0, h, 1, -1), (w, h, -1, -1)):
                for _ in range(3):
                    pts = [(cx, cy)]
                    ang = r.uniform(0.15, 1.4)
                    x, y = cx, cy
                    for _k in range(6):
                        ang += r.uniform(-0.35, 0.35)
                        step = r.uniform(7, 13)
                        x += sx * math.cos(ang) * step
                        y += sy * math.sin(ang) * step
                        pts.append((x, y))
                    cracks.append(pts)
            it["cracks"] = cracks
        elif name == "water_dragon":
            it["phase"] = r.uniform(0, 6.3)
        elif name == "updraft":
            w, h = ctx["w"], ctx["h"]
            it["streaks"] = [[r.uniform(0, w), h + r.uniform(0, 60), r.uniform(260, 420), r.uniform(6, 14)] for _ in range(36)]
        self.items.append(it)

    @property
    def active(self) -> bool:
        return bool(self.items)

    def update(self, dt: float) -> None:
        for it in self.items:
            it["t"] += dt
            if it["name"] == "updraft":
                for s in it["streaks"]:
                    s[1] -= s[2] * dt
        self.items = [it for it in self.items if it["t"] < it["sec"]]
        self.rain_burst = max(0.0, self.rain_burst - dt)
        rb = next((it for it in self.items if it["name"] == "reeds_bow"), None)
        self.reeds_k = math.sin(math.pi * min(1.0, rb["t"] / rb["sec"])) if rb else 0.0

    def clear(self) -> None:
        """파이팅 시작 (건너뛰기 포함): 순간 연출은 모두 정리 — 보레알리스 얼음 금은 파이팅 전에 사라짐. 여우비 빗줄기만 남음."""
        self.items.clear()
        self.reeds_k = 0.0
        self.rain_burst = 0.0

    def end_fight(self) -> None:
        self.rain_fight = False
        self.rain_burst = 0.0

    # ── 그리기 ──
    def draw_world(self, canvas, pal) -> None:
        for it in self.items:
            n, t, sec, ctx = it["name"], it["t"], it["sec"], it["ctx"]
            u = clamp(t / sec, 0, 1)
            bx, by = ctx["bobber"]
            w, h, hz = ctx["w"], ctx["h"], ctx["horizon"]
            if n == "giant_shadow":
                # 화면보다 큰 검은 그림자가 찌 아래를 지나감 (왼쪽 → 오른쪽)
                bw = int(w * 1.5)
                bh = max(18, int((h - hz) * 0.42))
                x = lerp(-bw * 0.9, w - bw * 0.1, u)
                s = _SPR.get(("shadow", bw, bh))
                if s is None:
                    s = pygame.Surface((bw + bh, bh), pygame.SRCALPHA)
                    pygame.draw.ellipse(s, (0, 0, 0, 255), (bh // 2, 0, bw, bh))
                    pygame.draw.polygon(s, (0, 0, 0, 255), [(bh // 2 + 8, bh // 2), (0, 0), (0, bh)])   # 꼬리
                    _SPR[("shadow", bw, bh)] = s
                s.set_alpha(int(120 * math.sin(math.pi * u) ** 0.5))
                canvas.blit(s, (int(x), int(by + 6 - bh / 2)))
            elif n == "great_bell":
                # 수면 전체가 찌 쪽으로 빨려 드는 물결 (바깥 → 찌)
                col = lerp_color(pal["wave_light"], (255, 246, 214), 0.5)
                for k in range(4):
                    v = clamp(u * 1.4 - k * 0.12, 0, 1)
                    if v <= 0 or v >= 1:
                        continue
                    rx = (1 - v) * w * 0.75 + 4
                    ry = rx * 0.16
                    pygame.draw.ellipse(canvas, col, (bx - rx, by - ry, rx * 2, ry * 2), 1)

    def draw_screen(self, canvas, pal) -> None:
        for it in self.items:
            n, t, sec, ctx = it["name"], it["t"], it["sec"], it["ctx"]
            u = clamp(t / sec, 0, 1)
            bx, by = ctx["bobber"]
            w, h, hz = ctx["w"], ctx["h"], ctx["horizon"]
            if n == "tiger_roar":
                # 산안개가 화면 양옆에서 밀려옴
                k = math.sin(math.pi * u)
                col = lerp_color(pal["sky_bottom"], (226, 232, 236), 0.6)
                bw, bh = int(w * 0.36), int(h * 0.8)
                s = _soft(bw, bh, col, 70, 61)
                s.set_alpha(int(255 * k))
                canvas.blit(s, (int(-bw + bw * 0.85 * k), int(h * 0.12)))
                canvas.blit(pygame.transform.flip(s, True, False), (int(w - bw * 0.85 * k), int(h * 0.12)))
            elif n == "horizon_bolt":
                # 낚싯줄을 따라 하얀 전기가 찌직
                pts = getattr(ctx["scene"], "last_line_pts", None)
                if pts and len(pts) > 2 and t < 0.4:
                    r = random.Random(int(t * 30))
                    zig = [(x + r.uniform(-2, 2), y + r.uniform(-2, 2)) for x, y in pts]
                    pygame.draw.lines(canvas, (200, 220, 255), False, zig, 2)
                    pygame.draw.lines(canvas, (255, 255, 255), False, zig, 1)
            elif n == "white_slash":
                # 하얀 선 하나가 왼쪽 아래 → 오른쪽 위로 가름 (0.15초), 선 자리에서 물보라
                a, b = (w * 0.04, h * 0.92), (w * 0.96, h * 0.1)
                grow = clamp(t / 0.15, 0, 1)
                fade = 1 - clamp((t - 0.15) / 0.35, 0, 1)
                if fade > 0:
                    e = (lerp(a[0], b[0], grow), lerp(a[1], b[1], grow))
                    col = lerp_color(pal["sky_bottom"], (255, 255, 255), fade)
                    pygame.draw.line(canvas, col, a, e, 3 if fade > 0.5 else 1)
                    pygame.draw.line(canvas, (255, 255, 255), a, e, 1)
                if t >= 0.15 and not it.get("splashed"):
                    it["splashed"] = True
                    dr = ctx["scene"].droplets
                    for i in range(10):
                        v = 0.08 + 0.84 * i / 9
                        x, y = lerp(a[0], b[0], v), lerp(a[1], b[1], v)
                        if y > hz:
                            dr.burst(x, y, 0.7, count=3)
            elif n == "sonar_ping":
                # 가장자리가 수압에 눌리듯 어두워졌다(30%) 돌아옴
                e = _edge_dark(w, h)
                e.set_alpha(int(255 * 0.3 * math.sin(math.pi * u)))
                canvas.blit(e, (0, 0))
            elif n == "water_dragon":
                # 물기둥이 용처럼 솟구쳤다 흩어짐
                rise = clamp(t / 0.38, 0, 1)
                top = lerp(by, hz - 70, rise)
                col = lerp_color(pal["wave_light"], (240, 250, 255), 0.6)
                if t < 0.45:
                    n_seg = 16
                    for i in range(n_seg):
                        v = i / (n_seg - 1)
                        y = lerp(by, top, v)
                        x = bx + math.sin(v * 5.0 + it["phase"] + t * 8) * 10 * v
                        rad = max(1, int(lerp(6, 3, v)))
                        pygame.draw.circle(canvas, col, (int(x), int(y)), rad)
                    hx = bx + math.sin(5.0 + it["phase"] + t * 8) * 10
                    pygame.draw.circle(canvas, (255, 255, 255), (int(hx), int(top)), 5)
                elif not it.get("burst"):
                    it["burst"] = True
                    dr = ctx["scene"].droplets
                    for i in range(8):
                        y = lerp(by, hz - 70, i / 7)
                        dr.burst(bx + math.sin(i / 7 * 5 + it["phase"]) * 10, y, 1.0, count=4)
            elif n == "crystal_resonance":
                # 동굴 수정들이 동시에 빛나며 울림
                k = math.sin(math.pi * u) * (0.75 + 0.25 * math.sin(t * 40))
                g = _SPR.get("cglow")
                if g is None:
                    g = _SPR["cglow"] = pygame.Surface((25, 25))
                    for rr, v in ((12, 40), (8, 80), (4, 140)):
                        pygame.draw.circle(g, (int(v * 0.7), int(v * 0.85), v), (12, 12), rr)
                gg = g.copy()
                gg.fill((int(255 * k),) * 3, special_flags=pygame.BLEND_RGB_MULT)
                for x, hh, lean in CRYSTAL_TIPS:
                    base = 262 if x < 240 else 270
                    for f in (0.35, 0.8):
                        canvas.blit(gg, (int(x + lean * hh * f) - 12, int(base - hh * f) - 12), special_flags=pygame.BLEND_RGB_ADD)
            elif n == "updraft":
                # 아래에서 돌풍이 치솟고 화면 위 구름이 갈라짐
                col = lerp_color(pal["sky_bottom"], (255, 255, 255), 0.7)
                for x, y, sp, ln in it["streaks"]:
                    if -ln < y < h:
                        pygame.draw.line(canvas, col, (x, y), (x, y + ln), 1)
                k = math.sin(math.pi * min(1.0, u * 1.2))
                bw, bh = int(w * 0.55), int(h * 0.16)
                s = _soft(bw, bh, (250, 252, 255), 175, 77)
                s.set_alpha(int(255 * k))
                gap = u * w * 0.35
                canvas.blit(s, (int(w / 2 - bw - gap * 0.5 + bw * 0.1), -bh // 4))
                canvas.blit(pygame.transform.flip(s, True, False), (int(w / 2 + gap * 0.5 - bw * 0.1), -bh // 4))
            elif n == "steam_burst":
                # 찌 주변 물이 부글부글 끓다가 증기 폭발
                sc = ctx["scene"]
                if t < 0.35:
                    if int(t * 60) % 2 == 0:
                        sc.bubbles.spawn(bx, by + 2, 10)
                else:
                    v = clamp((t - 0.35) / 0.25, 0, 1)
                    rad = int(lerp(6, 46, v))
                    s = _soft(rad * 2 + 2, rad + 2, (246, 246, 250), 190, 91)
                    s.set_alpha(int(255 * (1 - v) ** 0.7))
                    canvas.blit(s, (int(bx - rad), int(by - rad)))
                    if not it.get("burst"):
                        it["burst"] = True
                        sc.droplets.burst(bx, by, 1.2, count=12)
            elif n == "ice_crack_corners":
                # 네 모서리부터 얼음이 쩍 (0.3초) → 파이팅 전에 사라짐
                grow = clamp(t / 0.3, 0, 1)
                fade = 1 - clamp((t - 0.3) / 0.28, 0, 1)
                if fade <= 0:
                    continue
                col = lerp_color(pal["sky_bottom"], (235, 248, 255), fade)
                for i, pts in enumerate(it["cracks"]):
                    m = max(2, int(len(pts) * grow))
                    pygame.draw.lines(canvas, col, False, pts[:m], 2 if i % 3 == 0 else 1)


def bulge(canvas, pal, x: float, y: float, k: float, px: int) -> None:
    """① 전설: 찌 주변 수면이 불룩 솟아오름 (찌보다 먼저 그림)."""
    rx = max(4, int(px * (0.6 + 0.6 * k)))
    ry = max(2, int(rx * 0.32))
    col = lerp_color(pal["water_top"], pal["wave_light"], 0.35 + 0.35 * k)
    pygame.draw.ellipse(canvas, col, (x - rx, y - ry - int(2 * k), rx * 2, ry * 2 + 2))
    pygame.draw.ellipse(canvas, lerp_color(col, (255, 255, 255), 0.4), (x - rx, y - ry - int(2 * k), rx * 2, ry * 2 + 2), 1)
