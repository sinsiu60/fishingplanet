"""찌, 낚싯줄, 파문, 물방울 그리기."""
import math
import random

import pygame

from src.core import fxq

from src.core.mathutil import clamp, lerp_color, scale_color


# ───────────────────────── 파문 (월드 고정) ─────────────────────────

class Ripples:
    def __init__(self):
        self.items: list[dict] = []

    def spawn(self, x: float, z: float, size: float = 1.0, life: float = 1.6, rings: int = 1) -> None:
        for i in range(rings):
            self.items.append({"x": x, "z": z, "age": -i * 0.22, "life": life, "size": size})

    def update(self, dt: float) -> None:
        for r in self.items:
            r["age"] += dt
        self.items = [r for r in self.items if r["age"] < r["life"]]

    def draw(self, canvas, pal, cam) -> None:
        for r in self.items:
            if r["age"] < 0:
                continue
            p = cam.project(r["x"], r["z"])
            if p is None:
                continue
            sx, sy, s = p
            k = r["age"] / r["life"]
            radius_m = r["size"] * (0.15 + k * 1.1)
            rx = radius_m * s
            ry = max(1.0, rx * cam.cam_h / r["z"] * 1.4)
            if rx < 1:
                continue
            water = lerp_color(pal["water_top"], pal["water_bottom"],
                               clamp((sy - cam.horizon) / (cam.height - cam.horizon), 0, 1) ** 0.55)
            color = lerp_color(pal["wave_light"], water, k)
            pygame.draw.ellipse(canvas, color, (sx - rx, sy - ry, rx * 2, ry * 2), 1)


# ───────────────────────── 물방울 (화면 공간) ─────────────────────────

class Droplets:
    def __init__(self):
        self.items: list[list[float]] = []

    def burst(self, x: float, y: float, scale: float, count: int = 10, lateral: float = 0.0) -> None:
        sp = clamp(scale, 0.3, 3.0)
        for _ in range(count):
            self.items.append([
                x, y,
                (random.uniform(-25, 25) + lateral) * sp,
                random.uniform(-70, -30) * sp,
                random.uniform(0.35, 0.7),
                y,  # 수면 높이
            ])

    def update(self, dt: float) -> None:
        for d in self.items:
            d[0] += d[2] * dt
            d[1] += d[3] * dt
            d[3] += 260 * dt
            d[4] -= dt
        self.items = [d for d in self.items if d[4] > 0 and d[1] <= d[5] + 1]

    def draw(self, canvas, pal) -> None:
        for d in self.items:
            canvas.set_at((int(d[0]), int(d[1])), pal["wave_light"])


# ───────────────────────── 찌 ─────────────────────────


_GLOW: dict = {}


def _glow_layer(size) -> pygame.Surface:
    g = _GLOW.get(size)
    if g is None:
        _GLOW.clear()
        g = _GLOW[size] = pygame.Surface(size, pygame.SRCALPHA)
    return g

def draw_bobber(canvas, pal, x: float, y: float, size: float, floating: bool, dip: float = 0.0) -> None:
    """size: 찌 전체 높이(px). floating이면 아래쪽은 물에 잠김. dip: 0~1 추가 잠김."""
    x, y = int(x), int(y)
    red, white = pal["bobber"], pal["bobber_base"]
    hl = lerp_color(pal["wave_light"], white, 0.5)
    if size < 3:
        canvas.fill(red, (x - 1, y - 1, 2, 2))
        return
    w = max(2, int(size * 0.45))
    h = int(size)
    if floating:
        if dip >= 0.95:
            # 완전히 잠김: 수면에 동그란 물결만
            canvas.fill(hl, (x - w // 2 - 1, y, w + 2, 1))
            return
        # 수면 위로 머리만: 빨간 몸통 + 흰 띠 + 안테나. dip만큼 아래로 가라앉으며 잘림
        sink = int(round(h * 0.75 * dip))
        top = y - h // 2 + sink
        body = pygame.Rect(x - w // 2, top, w, h // 2 + 1)
        clip = canvas.get_clip()
        canvas.set_clip(pygame.Rect(0, 0, canvas.get_width(), y).clip(clip))
        pygame.draw.ellipse(canvas, red, body)
        canvas.fill(white, (x - w // 2, top + h // 2 - max(1, h // 8), w, max(1, h // 8)))
        if pal.get("bobber_band"):   # 해강의 찌: 가운데 대나무색 띠 (외형만)
            canvas.fill(pal["bobber_band"], (x - w // 2, top + h // 5, w, max(1, h // 9)))
        pygame.draw.line(canvas, scale_color(red, 0.7), (x, top), (x, top - h // 3), 1)
        if pal.get("bobber_dot"):    # 맨 위 작은 빨간 점 (생일 축하 찌: 작은 별)
            _dot(canvas, pal, x, top - h // 3 - 1)
        canvas.set_clip(clip)
        canvas.fill(hl, (x - w // 2 - 1, y, w + 2, 1))
    else:
        pygame.draw.ellipse(canvas, red, (x - w // 2, y - h // 2, w, h // 2 + 1))
        pygame.draw.ellipse(canvas, white, (x - w // 2, y - 1, w, h // 2))
        if pal.get("bobber_band"):
            canvas.fill(pal["bobber_band"], (x - w // 2, y - h // 4, w, max(1, h // 9)))
        pygame.draw.line(canvas, scale_color(red, 0.7), (x, y - h // 2), (x, y - h // 2 - h // 3), 1)
        if pal.get("bobber_dot"):
            _dot(canvas, pal, x, y - h // 2 - h // 3 - 1)


def _dot(canvas, pal, x: int, y: int) -> None:
    if pal.get("bobber_star"):   # 생일 축하 찌 (DT11): 안테나 끝 작은 별 (+ 모양 5px)
        c = pal["bobber_dot"]
        canvas.fill(c, (x - 2, y, 5, 1))
        canvas.fill(c, (x, y - 2, 1, 5))
        canvas.fill(c, (x - 1, y - 1, 3, 3))
    else:
        canvas.fill(pal["bobber_dot"], (x - 1, y, 2, 2))


def draw_fish_shadow(canvas, pal, cam, shadow: dict, t: float) -> None:
    """수면 아래 물고기 그림자. 읽기 쉽게 원근 압축은 약하게 (화면 공간 타원)."""
    if shadow is None or shadow["alpha"] <= 0.02:
        return
    p = cam.project(shadow["x"], shadow["z"], -0.2)
    if p is None:
        return
    sx, sy, s = p
    # 멀리서도 읽히도록 실제보다 크게 + 최소 크기 보장 (공정함 > 사실감)
    length = max(7.0, shadow["len"] * s * 1.8) * shadow.get("scale", 1.0)
    # 진행 방향의 화면 좌우 성분 (정면/뒤로 향하면 짧아 보임)
    rel = shadow["heading"] - cam.yaw
    side = math.sin(rel)
    body_w = max(2.0, length * (0.45 + 0.55 * abs(side)))
    body_w *= shadow.get("squash", 1.0) * (1 + shadow.get("stretch", 0.0))  # 돌진: 웅크림 압축 / 돌진 늘어남 (31-14)
    body_h = max(3.0, length * 0.34)
    row = clamp((sy - cam.horizon) / (cam.height - cam.horizon), 0, 1) ** 0.55
    water = lerp_color(pal["water_top"], pal["water_bottom"], row)
    color = lerp_color(water, scale_color(pal["wave_dark"], 0.8), 0.8 * shadow["alpha"])
    glow = shadow.get("glow")
    if glow:
        # 희귀 이상: 그림자 테두리가 은은하게 빛남
        k = 0.45 + 0.35 * math.sin(t * 3.0)
        gcol = lerp_color(water, glow, k * shadow["alpha"])
        pygame.draw.ellipse(canvas, gcol, (sx - body_w / 2 - 2, sy - body_h / 2 - 2, body_w + 4, body_h + 4), 1)
    pygame.draw.ellipse(canvas, color, (sx - body_w / 2, sy - body_h / 2, body_w, body_h))
    # 꼬리 (진행 반대쪽, 살랑)
    direction = 1 if side >= 0 else -1
    tail_x = sx - direction * body_w / 2
    wag = math.sin(t * shadow.get("wag", 9.0)) * body_h * 0.35
    tail_len = max(2.0, body_w * 0.3)
    curl = shadow.get("curl", 0.0)
    if curl > 0.05:
        # 웅크림: 꼬리가 S자로 말림 (위로 꺾였다 아래로)
        tl = tail_len * 1.4
        pts = [(tail_x, sy), (tail_x - direction * tl * 0.45, sy - body_h * 0.55 * curl),
               (tail_x - direction * tl * 0.8, sy + body_h * 0.1 * curl),
               (tail_x - direction * tl, sy + body_h * 0.5 * curl)]
        pygame.draw.lines(canvas, color, False, pts, max(2, int(body_h * 0.35)))
        ex, ey = pts[-1]
        pygame.draw.polygon(canvas, color, [(ex, ey), (ex - direction * tail_len * 0.5, ey - body_h * 0.4),
                                            (ex - direction * tail_len * 0.5, ey + body_h * 0.3)])
        return
    pygame.draw.polygon(canvas, color, [
        (tail_x, sy),
        (tail_x - direction * tail_len, sy - body_h * 0.45 + wag),
        (tail_x - direction * tail_len, sy + body_h * 0.45 + wag),
    ])
    if shadow.get("spray"):
        _draw_spray_tail(canvas, water, tail_x - direction * tail_len, sy, direction, body_h, shadow["alpha"], t)


def _draw_spray_tail(canvas, water, x: float, y: float, direction: int, body_h: float, alpha: float, t: float) -> None:
    """들뜬 물고기 (CU9): 꼬리 뒤로 작은 물보라 점 4개가 튀었다 사라짐 (하얀 1~2px)."""
    for i in range(4):
        ph = (t * 3.2 + i * 0.27) % 1.0
        dx = -direction * (2 + ph * (6 + i * 2))
        dy = -ph * (3 + body_h * 0.4) + (i - 1.5) * 1.2
        a = alpha * (1 - ph)
        if a <= 0.05:
            continue
        col = lerp_color(water, (250, 252, 255), 0.85 * a)
        r = 1 if ph > 0.5 or i % 2 else 2
        pygame.draw.circle(canvas, col, (int(x + dx), int(y + dy)), r)


# ───────────────────────── 낚싯줄 ─────────────────────────

def draw_line(canvas, pal, start, end, sag: float, bias: float = 0.5, dx: float = 0.0,
              color=None, cracks: float = 0.0, t: float = 0.0) -> list:
    """start(낚싯대 끝) → end(찌). sag만큼 아래로 처진 2차 곡선.
    dx: 줄 쏠림(좌우 휨), cracks: 0~1 실금 정도."""
    cx = start[0] + (end[0] - start[0]) * bias + dx
    cy = max(start[1], end[1]) + sag
    ctrl = (cx, cy)
    n = 16
    pts = []
    for i in range(n + 1):
        u = i / n
        a, b, c = (1 - u) ** 2, 2 * (1 - u) * u, u * u
        pts.append((a * start[0] + b * ctrl[0] + c * end[0], a * start[1] + b * ctrl[1] + c * end[1]))
    col = color or pal["line"]
    if pal.get("line_glow") and color in (None, pal["line"]):
        # 고티어 줄: 은은한 빛 — 화면 크기 투명 레이어는 재사용하고, 줄이 지나는 상자만 지우고 그리고 붙인다 (O2)
        g = _glow_layer(canvas.get_size())
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        box = pygame.Rect(int(min(xs)) - 8, int(min(ys)) - 8, int(max(xs) - min(xs)) + 17, int(max(ys) - min(ys)) + 17)
        box = box.clip(g.get_rect())
        if box.w > 0 and box.h > 0:
            g.set_clip(box)
            g.fill((0, 0, 0, 0))
            pygame.draw.lines(g, (*pal["line_glow"], 70), False, pts, 3)
            g.set_clip(None)
            canvas.blit(g, box.topleft, box)
    pygame.draw.lines(canvas, col, False, pts, 1)
    if pal.get("line_marks") and color in (None, pal["line"]):
        # PE 합사처럼 색 마디
        for i in range(1, n, 3):
            pygame.draw.line(canvas, pal["line_marks"], pts[i], pts[i + 1], 1)
    if cracks > 0:
        crack_col = lerp_color(col, (255, 60, 50), 0.6)
        step = max(1, int(5 - cracks * 3))
        for i in range(2, n - 1, step):
            (x0, y0), (x1, y1) = pts[i], pts[i + 1]
            nx, ny = -(y1 - y0), (x1 - x0)
            ln = math.hypot(nx, ny) or 1
            k = (2 + cracks * 2) * (1 if (i + int(t * 10)) % 2 else -1)
            canvas.fill(crack_col, (int(x0 + nx / ln * k), int(y0 + ny / ln * k), 1, 1))
            canvas.fill(crack_col, (int(x0 + nx / ln * k * 0.5), int(y0 + ny / ln * k * 0.5), 1, 1))
    return pts


def landing_marker(canvas, pal, cam, x: float, z: float, t: float) -> None:
    p = cam.project(x, z)
    if p is None:
        return
    sx, sy, s = p
    rx = max(2.0, 0.6 * s)
    ry = max(1.0, rx * cam.cam_h / z * 1.4)
    if int(t * 4) % 2 == 0:
        color = lerp_color(pal["wave_light"], (255, 255, 255), 0.6)
    else:
        color = pal["wave_light"]
    pygame.draw.ellipse(canvas, color, (sx - rx, sy - ry, rx * 2, ry * 2), 1)
    canvas.set_at((int(sx), int(sy)), color)


def rod_tip_drop(tip, t: float) -> tuple[float, float]:
    """낚싯대 끝에 매달린 찌 위치 (살짝 흔들림)."""
    return tip[0] + math.sin(t * 2.3) * 1.5, tip[1] + 15


# ───────────────────────── 기포 · 반짝 (화면 공간) ─────────────────────────

class Bubbles:
    def __init__(self):
        self.items: list[list[float]] = []

    def spawn(self, x: float, y: float, spread: float) -> None:
        self.items.append([x + random.uniform(-spread, spread), y + random.uniform(-1, 2), random.uniform(0.25, 0.5)])

    def update(self, dt: float) -> None:
        for b in self.items:
            b[1] -= 6 * dt
            b[2] -= dt
        self.items = [b for b in self.items if b[2] > 0]

    def draw(self, canvas, pal) -> None:
        col = lerp_color(pal["wave_light"], (255, 255, 255), 0.5)
        for x, y, life in self.items:
            if life < 0.08:
                canvas.fill(col, (int(x) - 1, int(y), 3, 1))  # 톡 터짐
            else:
                canvas.fill(col, (int(x), int(y), 1, 1))


class Sparkles:
    """퍼펙트 반짝 이펙트."""

    def __init__(self):
        self.items: list[list[float]] = []
        self.rings: list[list[float]] = []

    def burst(self, x: float, y: float, count: int = 18, speed: float = 1.0, ring: bool = True) -> None:
        if fxq.level() < 2:
            count = max(2, round(count * fxq.particles()))   # 중간 · 낮음 (O4)
        for i in range(count):
            a = i / count * math.tau + random.uniform(-0.15, 0.15)
            sp = random.uniform(50, 110) * speed
            self.items.append([x, y, math.cos(a) * sp, math.sin(a) * sp, random.uniform(0.4, 0.8)])
        if ring:
            self.rings.append([x, y, 0.0])

    def update(self, dt: float) -> None:
        for p in self.items:
            p[0] += p[2] * dt
            p[1] += p[3] * dt
            p[2] *= 0.9
            p[3] *= 0.9
            p[4] -= dt
        self.items = [p for p in self.items if p[4] > 0]
        for r in self.rings:
            r[2] += dt
        self.rings = [r for r in self.rings if r[2] < 0.35]

    def draw(self, canvas) -> None:
        for x, y, age in self.rings:
            pygame.draw.circle(canvas, (255, 240, 170), (int(x), int(y)), int(4 + age * 90), 1)
        for x, y, _, _, life in self.items:
            col = (255, 255, 255) if life > 0.3 else (255, 220, 90)
            canvas.fill(col, (int(x), int(y), 2 if life > 0.3 else 1, 2 if life > 0.3 else 1))


def draw_ink(canvas, pal, cam, x: float, z: float, amount: float, t: float) -> None:
    """대왕오징어 먹물: 물고기 주변 수면을 검게 덮는다."""
    p = cam.project(x, z)
    if p is None or amount <= 0:
        return
    sx, sy, s = p
    r = max(10.0, 2.2 * s) * (0.6 + 0.4 * amount)
    ink = lerp_color(pal["water_bottom"], (5, 5, 12), 0.7)
    for i in range(5):
        a = i * 1.3 + t * 0.4
        ox = math.cos(a) * r * 0.35
        oy = math.sin(a) * r * 0.08
        pygame.draw.ellipse(canvas, ink, (sx + ox - r / 2, sy + oy - r * 0.12, r, r * 0.24))
