"""찌, 낚싯줄, 파문, 물방울 그리기."""
import math
import random

import pygame

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

    def burst(self, x: float, y: float, scale: float, count: int = 10) -> None:
        sp = clamp(scale, 0.3, 3.0)
        for _ in range(count):
            self.items.append([
                x, y,
                random.uniform(-25, 25) * sp,
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
        pygame.draw.line(canvas, scale_color(red, 0.7), (x, top), (x, top - h // 3), 1)
        canvas.set_clip(clip)
        canvas.fill(hl, (x - w // 2 - 1, y, w + 2, 1))
    else:
        pygame.draw.ellipse(canvas, red, (x - w // 2, y - h // 2, w, h // 2 + 1))
        pygame.draw.ellipse(canvas, white, (x - w // 2, y - 1, w, h // 2))
        pygame.draw.line(canvas, scale_color(red, 0.7), (x, y - h // 2), (x, y - h // 2 - h // 3), 1)


def draw_fish_shadow(canvas, pal, cam, shadow: dict, t: float) -> None:
    """수면 아래 물고기 그림자. 읽기 쉽게 원근 압축은 약하게 (화면 공간 타원)."""
    if shadow is None or shadow["alpha"] <= 0.02:
        return
    p = cam.project(shadow["x"], shadow["z"], -0.2)
    if p is None:
        return
    sx, sy, s = p
    # 멀리서도 읽히도록 실제보다 크게 + 최소 크기 보장 (공정함 > 사실감)
    length = max(7.0, shadow["len"] * s * 1.8)
    # 진행 방향의 화면 좌우 성분 (정면/뒤로 향하면 짧아 보임)
    rel = shadow["heading"] - cam.yaw
    side = math.sin(rel)
    body_w = max(2.0, length * (0.45 + 0.55 * abs(side)))
    body_h = max(3.0, length * 0.34)
    row = clamp((sy - cam.horizon) / (cam.height - cam.horizon), 0, 1) ** 0.55
    water = lerp_color(pal["water_top"], pal["water_bottom"], row)
    color = lerp_color(water, scale_color(pal["wave_dark"], 0.8), 0.8 * shadow["alpha"])
    pygame.draw.ellipse(canvas, color, (sx - body_w / 2, sy - body_h / 2, body_w, body_h))
    # 꼬리 (진행 반대쪽, 살랑)
    direction = 1 if side >= 0 else -1
    tail_x = sx - direction * body_w / 2
    wag = math.sin(t * 9) * body_h * 0.35
    tail_len = max(2.0, body_w * 0.3)
    pygame.draw.polygon(canvas, color, [
        (tail_x, sy),
        (tail_x - direction * tail_len, sy - body_h * 0.45 + wag),
        (tail_x - direction * tail_len, sy + body_h * 0.45 + wag),
    ])


# ───────────────────────── 낚싯줄 ─────────────────────────

def draw_line(canvas, pal, start, end, sag: float, bias: float = 0.5) -> None:
    """start(낚싯대 끝) → end(찌). sag만큼 아래로 처진 2차 곡선."""
    cx = start[0] + (end[0] - start[0]) * bias
    cy = max(start[1], end[1]) + sag
    ctrl = (cx, cy)
    n = 14
    pts = []
    for i in range(n + 1):
        t = i / n
        a, b, c = (1 - t) ** 2, 2 * (1 - t) * t, t * t
        pts.append((a * start[0] + b * ctrl[0] + c * end[0], a * start[1] + b * ctrl[1] + c * end[1]))
    pygame.draw.lines(canvas, pal["line"], False, pts, 1)


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
