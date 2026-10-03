"""'등용' 3페이즈: 용으로 변신한 모습 (그림자, 점프, 변신 연출, 불티)."""
import math
import random

import pygame

from src.render.screen import opaque as _opaque

from src.core.mathutil import clamp, lerp, lerp_color, smoothstep
from src.ui.fight_fx import big_text

RED = (214, 40, 36)
RED_DARK = (140, 18, 28)
GOLD = (255, 206, 96)
FLAME = (255, 150, 40)
EMBER = (255, 120, 50)


# ───────────────────────── 몸통 그리기 (공통) ─────────────────────────

def draw_dragon_body(canvas, pts: list, scale: float, t: float, facing: int = -1) -> None:
    """pts: 머리부터 꼬리까지 화면 좌표. 굵기는 scale(px)에서 꼬리로 갈수록 가늘게."""
    n = len(pts)
    if n < 2:
        return
    # 꼬리 → 머리 순으로 (머리가 위에 오도록)
    for i in range(n - 1, -1, -1):
        x, y = pts[i]
        k = i / n
        r = max(1.5, scale * (1.0 - 0.75 * k))
        body = lerp_color(RED, RED_DARK, k * 0.8)
        pygame.draw.circle(canvas, RED_DARK, (int(x), int(y) + 1), int(r) + 1)
        pygame.draw.circle(canvas, body, (int(x), int(y)), int(r))
        # 배 비늘 (금색)
        if i % 2 == 0:
            pygame.draw.circle(canvas, GOLD, (int(x), int(y + r * 0.45)), max(1, int(r * 0.45)))
        # 등 갈기 (불꽃처럼 흔들림)
        if i % 3 == 1 and i < n - 2:
            nx, ny = pts[max(0, i - 1)]
            ang = math.atan2(y - ny, x - nx) - math.pi / 2
            flick = math.sin(t * 14 + i) * 0.4
            tip = (x + math.cos(ang + flick) * r * 1.6, y + math.sin(ang + flick) * r * 1.6 - r * 0.6)
            pygame.draw.line(canvas, FLAME, (x, y - r * 0.6), tip, max(1, int(r * 0.35)))
        # 발톱 다리 (몸 1/4, 1/2 지점)
        if i in (n // 4, n // 2):
            for side in (-1, 1):
                fx = x + side * r * 1.2
                fy = y + r * 1.3
                pygame.draw.line(canvas, RED_DARK, (x, y + r * 0.5), (fx, fy), max(1, int(r * 0.4)))
                for c in (-1, 0, 1):
                    pygame.draw.line(canvas, GOLD, (fx, fy), (fx + c * r * 0.35, fy + r * 0.4), 1)
    # 꼬리 끝 불꽃
    tx, ty = pts[-1]
    pygame.draw.circle(canvas, FLAME, (int(tx), int(ty)), max(2, int(scale * 0.35)))
    # 머리
    hx, hy = pts[0]
    r = scale * 1.25
    pygame.draw.circle(canvas, RED_DARK, (int(hx), int(hy) + 1), int(r) + 1)
    pygame.draw.circle(canvas, RED, (int(hx), int(hy)), int(r))
    # 주둥이 (진행 방향)
    dx, dy = (hx - pts[1][0], hy - pts[1][1])
    ln = math.hypot(dx, dy) or 1
    dx, dy = dx / ln, dy / ln
    snout = (hx + dx * r * 1.3, hy + dy * r * 1.3)
    pygame.draw.circle(canvas, RED, (int(snout[0]), int(snout[1])), max(2, int(r * 0.7)))
    # 벌린 입
    jaw = (snout[0] + dx * r * 0.4, snout[1] + dy * r * 0.4 + r * 0.4)
    pygame.draw.line(canvas, (40, 0, 0), snout, jaw, max(1, int(r * 0.25)))
    # 뿔 두 개 (금색, 뒤로)
    for side in (-1, 1):
        base = (hx - dx * r * 0.2 + side * dy * r * 0.5, hy - dy * r * 0.2 - r * 0.7)
        tip = (base[0] - dx * r * 1.6, base[1] - r * 1.4)
        pygame.draw.line(canvas, GOLD, base, tip, max(1, int(r * 0.3)))
    # 빛나는 눈
    eye = (hx + dx * r * 0.4, hy - r * 0.35)
    pygame.draw.circle(canvas, (255, 255, 160), (int(eye[0]), int(eye[1])), max(1, int(r * 0.3)))
    # 수염 (길게 흔들림)
    for side in (-1, 1):
        w = [snout]
        for k in range(1, 5):
            w.append((snout[0] - dx * r * k * 0.9 + math.sin(t * 6 + k + side) * r * 0.5,
                      snout[1] + side * r * 0.3 * k + r * 0.4 * k))
        pygame.draw.lines(canvas, GOLD, False, w, 1)


# ───────────────────────── 수면 아래 그림자 ─────────────────────────

def draw_dragon_shadow(canvas, pal, cam, x: float, z: float, heading: float, t: float, scale: float = 1.0,
                       alpha: float = 1.0, facing: int = 1) -> None:
    """옆으로 길게 누운 용의 그림자가 S자로 꿈틀댄다 + 붉게 빛나는 테두리."""
    if alpha <= 0.02:
        return
    pts = []
    segs = 20
    for i in range(segs):
        # 머리(i=0)에서 진행 반대쪽으로 몸이 길게, 깊이 방향으로 물결치며
        wx = x - facing * i * 0.62 * scale
        wz = z + math.sin(t * 3.6 - i * 0.55) * 1.1 * scale * min(1.0, i / 2 + 0.3)
        p = cam.project(wx, wz, -0.25)
        if p is None:
            continue
        pts.append((p[0], p[1], p[2], i))
    if not pts:
        return
    water = lerp_color(pal["water_top"], pal["water_bottom"], 0.6)
    body = lerp_color(water, (20, 0, 8), 0.8 * alpha)
    glow = lerp_color(water, (255, 70, 40), (0.6 + 0.35 * math.sin(t * 6)) * alpha)
    for layer in (0, 1):
        for sx, sy, s, i in reversed(pts):
            r = max(2.0, (0.42 - i * 0.016) * s * scale)
            ry = max(1.5, r * 0.5)
            if layer == 0:
                pygame.draw.ellipse(canvas, glow, (sx - r - 2, sy - ry - 2, (r + 2) * 2, (ry + 2) * 2))
            else:
                pygame.draw.ellipse(canvas, body, (sx - r, sy - ry, r * 2, ry * 2))
    # 머리: 두 눈빛 + 뿔 그림자
    sx, sy, s, _ = pts[0]
    e = max(1, int(s * 0.05))
    for side in (-1, 1):
        canvas.fill((255, 210, 90), (int(sx + facing * s * 0.12 + side * s * 0.06), int(sy - 1), e + 1, e))
    horn = lerp_color(water, (60, 0, 10), alpha)
    pygame.draw.line(canvas, horn, (sx - facing * s * 0.1, sy - s * 0.12), (sx - facing * s * 0.45, sy - s * 0.35), 2)


# ───────────────────────── 점프 ─────────────────────────

def draw_dragon_jump(canvas, pal, cam, x: float, z: float, phase: float, height: float, t: float,
                     facing: int = 1) -> None:
    """용이 수면을 뚫고 아치 모양으로 솟구친다. 몸통은 지나온 궤적을 따라오고, 물속 부분은 숨긴다.
    머리 높이 = height (판정 원 위치와 일치)."""
    pts = []
    for i in range(30):
        ph = phase - i * 0.03
        if ph < 0:
            break
        h = 4 * height * ph * (1 - ph)
        lateral = (ph - 0.5) * 7.0 * facing  # 옆으로 크게 아치를 그리며
        p = cam.project(x + lateral, z, max(0.0, h))
        if p is None:
            continue
        pts.append((p[0], p[1]))
    if len(pts) < 2:
        return
    s = cam.project(x, z)
    scale = clamp((s[2] if s else 20) * 0.6, 9, 18)
    draw_dragon_body(canvas, pts, scale, t)
    # 뚫고 나온 자리의 물기둥
    p0 = cam.project(x - 3.5 * facing, z)
    if p0 and phase < 0.6:
        k = 1 - phase / 0.6
        pygame.draw.ellipse(canvas, (230, 240, 255), (p0[0] - 10 * k - 4, p0[1] - 30 * k, 8 + 20 * k, 30 * k + 4), 1)


# ───────────────────────── 불티 (화면 공간) ─────────────────────────

class Embers:
    def __init__(self):
        self.items: list[list[float]] = []

    def spawn(self, x: float, y: float, spread: float, n: int = 1) -> None:
        for _ in range(n):
            self.items.append([x + random.uniform(-spread, spread), y + random.uniform(-3, 3),
                               random.uniform(-8, 8), random.uniform(-40, -18), random.uniform(0.6, 1.3)])

    def update(self, dt: float) -> None:
        for e in self.items:
            e[0] += (e[2] + math.sin(e[4] * 9) * 10) * dt
            e[1] += e[3] * dt
            e[4] -= dt
        self.items = [e for e in self.items if e[4] > 0]

    def draw(self, canvas) -> None:
        for x, y, _, _, life in self.items:
            col = lerp_color((120, 20, 10), EMBER, min(1.0, life)) if life < 0.5 else (255, 210, 120)
            canvas.fill(col, (int(x), int(y), 2 if life > 0.7 else 1, 2 if life > 0.7 else 1))


# ───────────────────────── 변신 연출 ─────────────────────────

TRANSFORM_SEC = 2.4


class DragonTransform:
    """페이즈 3 진입: 소용돌이 → 붉은 빛기둥 → 붉은 번개 → 섬광 → '용이 되었다!!'"""

    def __init__(self, pos):
        self.t = 0.0
        self.pos = pos
        self.bolts: list[tuple[float, list]] = []
        self.fired: set[str] = set()

    @property
    def done(self) -> bool:
        return self.t >= TRANSFORM_SEC

    def update(self, dt: float) -> list[str]:
        self.t += dt
        events = []
        for key, at in (("swirl", 0.0), ("pillar", 0.5), ("bolt1", 0.8), ("bolt2", 1.05), ("flash", 1.3),
                        ("roar", 1.35)):
            if self.t >= at and key not in self.fired:
                self.fired.add(key)
                events.append(key)
                if key.startswith("bolt"):
                    self.bolts.append((self.t, self._bolt()))
        self.bolts = [(bt, pts) for bt, pts in self.bolts if self.t - bt < 0.25]
        return events

    def _bolt(self) -> list:
        x0, y0 = self.pos
        x = x0 + random.uniform(-90, 90)
        pts = [(x, 0)]
        y = 0
        while y < y0:
            y += random.uniform(10, 20)
            x += (x0 - x) * 0.2 + random.uniform(-10, 10)
            pts.append((x, min(y, y0)))
        return pts

    def draw(self, canvas) -> None:
        w, h = canvas.get_size()
        t = self.t
        x0, y0 = self.pos
        # 1) 화면이 어두워짐
        dark = clamp(t / 0.4, 0, 1) * (1 - clamp((t - 1.9) / 0.5, 0, 1))
        veil = pygame.Surface((w, h), pygame.SRCALPHA)
        veil.fill((30, 0, 6, int(120 * dark)))
        canvas.blit(veil, (0, 0))
        # 2) 소용돌이 (물이 빨려 들어감)
        if t < 1.6:
            rings = pygame.Surface((w, h), pygame.SRCALPHA)
            for i in range(6):
                k = ((t * 1.4 + i / 6) % 1.0)
                r = (1 - k) * 90 + 6
                a = int(200 * k * (1 - clamp((t - 1.2) / 0.4, 0, 1)))
                pygame.draw.ellipse(rings, (255, 120, 80, a), (x0 - r, y0 - r * 0.28, r * 2, r * 0.56), 2)
            canvas.blit(rings, (0, 0))
        # 3) 붉은 빛기둥
        if t > 0.5:
            pk = smoothstep((t - 0.5) / 0.6) * (1 - clamp((t - 1.9) / 0.5, 0, 1))
            pw = int(lerp(3, 46, pk) + math.sin(t * 30) * 3)
            col = pygame.Surface((pw * 2 + 2, h), pygame.SRCALPHA)
            for i in range(pw):
                a = int(200 * pk * (1 - i / pw))
                pygame.draw.line(col, (255, 90 + i * 2, 50, a), (pw - i, 0), (pw - i, y0))
                pygame.draw.line(col, (255, 90 + i * 2, 50, a), (pw + i, 0), (pw + i, y0))
            canvas.blit(col, (x0 - pw, 0))
        # 4) 붉은 번개
        for _, pts in self.bolts:
            pygame.draw.lines(canvas, (255, 80, 60), False, pts, 3)
            pygame.draw.lines(canvas, (255, 230, 200), False, pts, 1)
        # 5) 섬광 + 배너
        if 1.3 <= t < 1.6:
            fl = _opaque((w, h))
            fl.fill((255, 200, 160))
            fl.set_alpha(int(230 * (1 - (t - 1.3) / 0.3)))
            canvas.blit(fl, (0, 0))
        if t > 1.35:
            bk = t - 1.35
            pop = 1.0 + 0.9 * math.exp(-bk * 10) * math.cos(bk * 26)
            big_text(canvas, "용이 되었다!!", (w // 2, h // 2 - 30), (255, 120, 70), 3.6 * max(0.6, pop), outline=True)
