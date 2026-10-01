"""파이팅 연출 UI: 점프 판정 원(리듬게임식), 행동 아이콘, 판정 텍스트, 힘 모으기/지침 연출."""
import math
import random

import pygame

from src.core.fonts import get_font
from src.core.mathutil import clamp, lerp, lerp_color
from src.ui.hud import SHADOW, text

GOLD = (255, 214, 90)
GREAT_COL = (130, 255, 180)
MISS_COL = (255, 110, 95)
ICON_COL = {"rush": (255, 150, 60), "jump": (110, 220, 255), "turn": (255, 230, 90), "charge": (210, 150, 255),
            "tired": (110, 255, 140), "leap": (120, 255, 240)}
SWIPE = (120, 255, 240)

RING_R = 13          # 판정 원 반지름
RING_SPREAD = 58     # 예고 시작 시 접근 원이 판정 원보다 얼마나 큰지


# ───────────────────────── 점프 판정 원 ─────────────────────────

def draw_jump_ring(canvas, center, time_to_apex: float, total: float, perfect_w: float, good_w: float,
                   t: float) -> None:
    """바깥 원이 줄어들어 판정 원과 겹치는 순간 = 점프 정점 = 퍼펙트."""
    if center is None or total <= 0:
        return
    cx, cy = int(center[0]), int(center[1])
    k = RING_SPREAD / total          # 초당 줄어드는 픽셀
    r_approach = RING_R + time_to_apex * k
    if r_approach < RING_R - good_w * k - 2:
        return
    size = (RING_R + RING_SPREAD + 8) * 2
    surf = pygame.Surface((size, size), pygame.SRCALPHA)
    o = size // 2
    # GREAT 구간 (옅은 띠)
    good_in = max(2, int(RING_R - good_w * k))
    good_out = int(RING_R + good_w * k)
    pygame.draw.circle(surf, (*GREAT_COL, 45), (o, o), good_out)
    pygame.draw.circle(surf, (0, 0, 0, 0), (o, o), good_in)
    pygame.draw.circle(surf, (*GREAT_COL, 110), (o, o), good_out, 1)
    # 판정 원 (PERFECT 두께)
    pw = max(2, int(perfect_w * k * 2))
    in_perfect = abs(time_to_apex) <= perfect_w
    in_good = abs(time_to_apex) <= good_w
    glow = 0.5 + 0.5 * math.sin(t * 20)
    ring_col = lerp_color(GOLD, (255, 255, 255), glow) if in_perfect else GOLD
    pygame.draw.circle(surf, (*ring_col, 255), (o, o), RING_R + pw // 2, pw)
    pygame.draw.circle(surf, (255, 255, 255, 200), (o, o), 2)
    # 접근 원
    if r_approach > 1:
        col = (255, 255, 255) if not in_good else (GOLD if in_perfect else GREAT_COL)
        alpha = int(clamp(255 * (1.2 - (r_approach - RING_R) / RING_SPREAD), 90, 255))
        pygame.draw.circle(surf, (*SHADOW, alpha // 2), (o + 1, o + 1), int(r_approach), 2)
        pygame.draw.circle(surf, (*col, alpha), (o, o), int(r_approach), 2)
    canvas.blit(surf, (cx - o, cy - o))
    if time_to_apex > 0.2:
        text(canvas, "우클릭", (cx, cy + RING_R + 10), (230, 240, 255), 11, "center")


# ───────────────────────── 행동 아이콘 ─────────────────────────

def draw_behavior_icon(canvas, pos, kind: str, progress: float, turn_dir: int, t: float) -> None:
    """물고기 머리 위 배지: 무엇을 할지 + 예고 남은 시간(테두리 원호)."""
    if pos is None:
        return
    x, y = int(pos[0]), int(pos[1] - 20)
    col = ICON_COL[kind]
    pop = 1.0 + 0.4 * max(0.0, 1 - progress / 0.15) if progress < 0.15 else 1.0
    r = int(9 * pop)
    pygame.draw.circle(canvas, SHADOW, (x + 1, y + 1), r + 1)
    pygame.draw.circle(canvas, (24, 28, 46), (x, y), r)
    # 남은 예고 시간: 원호가 줄어든다
    if kind != "tired":
        remain = 1 - progress
        if remain > 0.02:
            rect = pygame.Rect(0, 0, (r + 2) * 2, (r + 2) * 2)
            rect.center = (x, y)
            pygame.draw.arc(canvas, col, rect, math.pi / 2, math.pi / 2 + math.tau * remain, 2)
    else:
        pygame.draw.circle(canvas, col, (x, y), r + 1, 1)
    # 아이콘
    if kind == "rush":
        for dy in (-2, 3):
            pygame.draw.lines(canvas, col, False, [(x - 4, y + dy + 2), (x, y + dy - 2), (x + 4, y + dy + 2)], 2)
    elif kind == "jump":
        pygame.draw.line(canvas, col, (x, y + 5), (x, y - 4), 2)
        pygame.draw.lines(canvas, col, False, [(x - 4, y), (x, y - 5), (x + 4, y)], 2)
    elif kind == "turn":
        d = turn_dir or 1
        pygame.draw.line(canvas, col, (x - 5 * d, y), (x + 4 * d, y), 2)
        pygame.draw.lines(canvas, col, False, [(x + 1 * d, y - 4), (x + 5 * d, y), (x + 1 * d, y + 4)], 2)
    elif kind == "charge":
        canvas.fill(col, (x - 4, y - 4, 3, 8))
        canvas.fill(col, (x + 1, y - 4, 3, 8))
    elif kind == "tired":
        canvas.fill(col, (x - 1, y - 5, 3, 7))
        canvas.fill(col, (x - 1, y + 3, 3, 2))
        if int(t * 3) % 2 == 0:
            text(canvas, "기회!", (x, y + r + 8), col, 11, "center")


# ───────────────────────── 판정 텍스트 ─────────────────────────

class JudgePopups:
    STYLE = {
        "perfect": ("PERFECT!", GOLD, 2.0),
        "good": ("GREAT!", GREAT_COL, 1.6),
        "miss_early": ("빠름!", MISS_COL, 1.0),
        "miss_late": ("늦음!", MISS_COL, 1.0),
        "miss_none": ("놓침!", MISS_COL, 1.0),
        "flick_perfect": ("PERFECT 꺾기!", GOLD, 2.0),
        "flick_good": ("꺾기!", SWIPE, 1.6),
        "flick_miss": ("꺾기 실패!", MISS_COL, 1.2),
        "swipe_perfect": ("PERFECT!", SWIPE, 2.0),
        "swipe_good": ("GREAT!", SWIPE, 1.6),
    }

    def __init__(self):
        self.items: list[dict] = []

    def add(self, kind: str, pos, streak: int = 0) -> None:
        s, c, scale = self.STYLE[kind]
        self.items = [it for it in self.items if it["t"] > 0.25]  # 겹치면 이전 것 정리
        self.items.append({"text": s, "color": c, "scale": scale, "x": pos[0], "y": pos[1] - 26, "t": 0.0,
                           "streak": streak, "kind": kind})

    def update(self, dt: float) -> None:
        for it in self.items:
            it["t"] += dt
        self.items = [it for it in self.items if it["t"] < 1.1]

    def draw(self, canvas, mapper=lambda p: p) -> None:
        for it in self.items:
            age = it["t"]
            # 튀어나오며 커졌다가 자리잡음
            pop = 1.0 + 0.6 * math.exp(-age * 14) * math.cos(age * 30)
            scale = it["scale"] * max(0.6, pop)
            x, y = mapper((it["x"], it["y"]))
            y -= age * 14
            x = clamp(x, 60, canvas.get_width() - 60)
            if age > 0.85 and int(age * 20) % 2 == 0:
                continue
            big_text(canvas, it["text"], (x, y), it["color"], scale,
                     outline=it["kind"] in ("perfect", "good", "flick_perfect", "flick_good", "swipe_perfect",
                                            "swipe_good"))
            if it["streak"] >= 2:
                big_text(canvas, f"×{it['streak']} 연속", (x, y + 14 * scale * 0.6 + 6), GOLD, 1.0, outline=True)


def big_text(canvas, s: str, center, color, scale: float, outline: bool = False) -> None:
    """픽셀 느낌 그대로 키운 큰 글씨 (테두리 포함)."""
    font = get_font(16 if scale >= 1.5 else 11)
    img = font.render(s, False, color)
    edge = font.render(s, False, (30, 18, 10) if outline else SHADOW)
    k = scale if scale < 1.5 else scale / 1.6
    if abs(k - 1.0) > 0.05:
        size = (max(1, int(img.get_width() * k)), max(1, int(img.get_height() * k)))
        img = pygame.transform.scale(img, size)
        edge = pygame.transform.scale(edge, size)
    rect = img.get_rect(center=(int(center[0]), int(center[1])))
    offs = ((-1, 0), (1, 0), (0, -1), (0, 1), (1, 1)) if outline else ((1, 1),)
    for dx, dy in offs:
        canvas.blit(edge, rect.move(dx, dy))
    canvas.blit(img, rect)


# ───────────────────────── 힘 모으기 / 지침 (수면 연출) ─────────────────────────

class GatherFX:
    """힘 모으기: 물고기 쪽으로 빨려 들어가는 입자. 지침: 물고기 아래 초록 고리."""

    def __init__(self):
        self.parts: list[list[float]] = []
        self.spawn_t = 0.0

    def update(self, dt: float, active: bool, pos, scale: float) -> None:
        if active and pos is not None:
            self.spawn_t += dt
            while self.spawn_t > 0.03:
                self.spawn_t -= 0.03
                a = random.uniform(0, math.tau)
                r = random.uniform(16, 26) * clamp(scale, 0.6, 1.6)
                self.parts.append([pos[0] + math.cos(a) * r, pos[1] + math.sin(a) * r * 0.45, pos[0], pos[1], 0.0])
        for p in self.parts:
            p[4] += dt
            k = min(1.0, p[4] / 0.4)
            p[0] = lerp(p[0], p[2], k * 0.25)
            p[1] = lerp(p[1], p[3], k * 0.25)
        self.parts = [p for p in self.parts if p[4] < 0.4]

    def draw(self, canvas) -> None:
        for x, y, _, _, age in self.parts:
            col = lerp_color((210, 150, 255), (255, 255, 255), age / 0.4)
            canvas.fill(col, (int(x), int(y), 2, 2))


def draw_tired_ring(canvas, pos, scale: float, t: float) -> None:
    if pos is None:
        return
    k = (t * 1.5) % 1.0
    r = (8 + k * 14) * clamp(scale, 0.6, 1.6)
    col = lerp_color((110, 255, 140), (40, 80, 60), k)
    pygame.draw.ellipse(canvas, col, (pos[0] - r, pos[1] - r * 0.3, r * 2, r * 0.6), 1)


def draw_turn_chevrons(canvas, pos, direction: int, amount: float, t: float) -> None:
    """방향 전환: 물고기 옆에 진행 방향으로 흐르는 화살표 (>>>)."""
    if pos is None or not direction:
        return
    x0, y0 = pos
    for i in range(3):
        off = (t * 2.5 + i / 3) % 1.0
        x = x0 + direction * (14 + off * 34)
        a = amount * (1 - abs(off - 0.5) * 1.4)
        if a <= 0.05:
            continue
        col = lerp_color((60, 50, 20), ICON_COL["turn"], a)
        pts = [(x - direction * 4, y0 - 6), (x + direction * 2, y0), (x - direction * 4, y0 + 6)]
        pygame.draw.lines(canvas, SHADOW, False, [(p[0] + 1, p[1] + 1) for p in pts], 2)
        pygame.draw.lines(canvas, col, False, pts, 2)


# ───────────────────────── 슬라이드 (꺾기 · 몸털기) ─────────────────────────

def _arrow(canvas, cx: float, cy: float, direction: int, length: float, color, width: int = 3) -> None:
    x0, x1 = cx - direction * length / 2, cx + direction * length / 2
    pygame.draw.line(canvas, SHADOW, (x0 + 1, cy + 1), (x1 + 1, cy + 1), width + 1)
    pygame.draw.line(canvas, color, (x0, cy), (x1, cy), width)
    head = length * 0.35
    for sgn in (-1, 1):
        pygame.draw.line(canvas, SHADOW, (x1 + 1, cy + 1), (x1 - direction * head + 1, cy + sgn * head * 0.7 + 1), width)
        pygame.draw.line(canvas, color, (x1, cy), (x1 - direction * head, cy + sgn * head * 0.7), width)


def draw_turn_prompt(canvas, pos, need: int, offset: float, before: float, after: float, perfect: float,
                     t: float) -> None:
    """방향 전환 꺾기: 물고기 옆 큰 화살표 + 타이밍 막대 (가운데 = 전환 순간 = PERFECT)."""
    if pos is None:
        return
    x, y = pos
    in_perfect = abs(offset) <= perfect
    in_window = -before <= offset <= after
    col = GOLD if in_perfect else (SWIPE if in_window else (200, 210, 220))
    pulse = 1.0 + (0.25 * math.sin(t * 30) if in_window else 0.0)
    _arrow(canvas, x + need * 34, y - 10, need, 30 * pulse, col, 3)
    big_text(canvas, "확 꺾기!", (x + need * 34, y - 26), col, 1.0, outline=True)
    # 타이밍 막대
    bw = 70
    bx, by = x + need * 34 - bw // 2, y + 6
    canvas.fill(SHADOW, (bx - 1, by - 1, bw + 2, 7))
    canvas.fill((30, 36, 56), (bx, by, bw, 5))
    span = before + after
    zero = bx + bw * before / span
    pz = bw * perfect / span
    canvas.fill((70, 140, 150), (bx + int(bw * 0 / span), by, int(bw * (before + after) / span), 5))
    canvas.fill((60, 70, 90), (bx, by, int(zero - bx - pz), 5))
    canvas.fill(GOLD, (int(zero - pz), by, max(2, int(pz * 2)), 5))
    k = clamp((offset + before) / span, -0.4, 1.0)
    mx = bx + bw * k
    canvas.fill((255, 255, 255), (int(mx) - 1, by - 3, 3, 11))


def draw_swipe_ring(canvas, center, time_to_apex: float, total: float, perfect_w: float, good_w: float,
                    need: int, t: float) -> None:
    """몸털기 점프: 하늘색 판정 원 + 안쪽 화살표. 원이 겹치는 순간 화살표 방향으로 슬라이드."""
    if center is None or total <= 0:
        return
    cx, cy = int(center[0]), int(center[1])
    k = RING_SPREAD / total
    r_approach = RING_R + time_to_apex * k
    if r_approach < RING_R - good_w * k - 2:
        return
    size = (RING_R + RING_SPREAD + 8) * 2
    surf = pygame.Surface((size, size), pygame.SRCALPHA)
    o = size // 2
    good_out = int(RING_R + good_w * k)
    pygame.draw.circle(surf, (*SWIPE, 40), (o, o), good_out)
    pygame.draw.circle(surf, (0, 0, 0, 0), (o, o), max(2, int(RING_R - good_w * k)))
    in_perfect = abs(time_to_apex) <= perfect_w
    in_good = abs(time_to_apex) <= good_w
    ring_col = lerp_color(SWIPE, (255, 255, 255), 0.5 + 0.5 * math.sin(t * 20)) if in_perfect else SWIPE
    pygame.draw.circle(surf, (*ring_col, 255), (o, o), RING_R + 2, max(2, int(perfect_w * k * 2)))
    if r_approach > 1:
        col = (255, 255, 255) if not in_good else (GOLD if in_perfect else SWIPE)
        pygame.draw.circle(surf, (*col, 230), (o, o), int(r_approach), 2)
    canvas.blit(surf, (cx - o, cy - o))
    _arrow(canvas, cx, cy, need, 16, (255, 255, 255) if not in_good else GOLD, 2)
    if time_to_apex > 0.15:
        big_text(canvas, "슬라이드", (cx + need * 6, cy + RING_R + 12), SWIPE, 1.0, outline=True)
        _arrow(canvas, cx - need * 26, cy + RING_R + 12, need, 12, SWIPE, 2)
