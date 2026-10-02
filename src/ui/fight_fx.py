"""파이팅 연출 UI: 점프 판정 원(리듬게임식), 행동 아이콘, 판정 텍스트, 힘 모으기/지침 연출."""
import math
import random

import pygame

from src.core.fonts import get_font
from src.core.mathutil import clamp, lerp, lerp_color
from src.ui.hud import SHADOW

GOLD = (255, 214, 90)
GREAT_COL = (130, 255, 180)
MISS_COL = (255, 110, 95)
ICON_COL = {"rush": (255, 150, 60), "jump": (110, 220, 255), "turn": (255, 230, 90), "charge": (210, 150, 255),
            "tired": (110, 255, 140), "leap": (120, 255, 240),
            # 신규 패턴 (U3)
            "shake": (255, 120, 200), "dive": (90, 150, 255), "surface": (150, 240, 255), "reverse": (255, 190, 120),
            "twist": (200, 255, 120), "chain": (255, 214, 90),
            # U4
            "hide": (190, 170, 140), "pump": (255, 160, 90), "thrash": (120, 200, 255), "bite": (255, 80, 80),
            "dual": (230, 140, 255), "fake": (180, 220, 255)}
SWIPE = (120, 255, 240)

RING_R = 13          # 판정 원 반지름
RING_SPREAD = 58     # 예고 시작 시 접근 원이 판정 원보다 얼마나 큰지


# ───────────────────────── 점프 판정 원 ─────────────────────────

def draw_jump_ring(canvas, center, time_to_apex: float, total: float, perfect_w: float, good_w: float,
                   t: float, spread: float | None = None) -> None:
    """바깥 원이 줄어들어 판정 원과 겹치는 순간 = 점프 정점 = 퍼펙트."""
    sp = spread or RING_SPREAD  # 신호 슬롯 안에선 작게 (31장 C3)
    if center is None or total <= 0:
        return
    cx, cy = int(center[0]), int(center[1])
    k = sp / total          # 초당 줄어드는 픽셀
    r_approach = RING_R + time_to_apex * k
    if r_approach < RING_R - good_w * k - 2:
        return
    size = (RING_R + sp + 8) * 2
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
        alpha = int(clamp(255 * (1.2 - (r_approach - RING_R) / sp), 90, 255))
        pygame.draw.circle(surf, (*SHADOW, alpha // 2), (o + 1, o + 1), int(r_approach), 2)
        pygame.draw.circle(surf, (*col, alpha), (o, o), int(r_approach), 2)
    canvas.blit(surf, (cx - o, cy - o))


# ───────────────────────── 행동 아이콘 ─────────────────────────

# ───────────────────────── 판정 텍스트 ─────────────────────────

class JudgePopups:
    # 파이팅 중 글자 예산 (31장): 화면 전체 동시 1개, 6글자 이하 → 판정 글자도 짧게, 한 번에 하나만
    STYLE = {
        "perfect": ("퍼펙트!", GOLD, 2.0),
        "good": ("좋아!", GREAT_COL, 1.6),
        "miss_early": ("빠름!", MISS_COL, 1.0),
        "miss_late": ("늦음!", MISS_COL, 1.0),
        "miss_none": ("놓침!", MISS_COL, 1.0),
        "flick_perfect": ("퍼펙트!", GOLD, 2.0),
        "flick_good": ("꺾기!", SWIPE, 1.6),
        "flick_miss": ("헛꺾기!", MISS_COL, 1.2),
        "swipe_perfect": ("퍼펙트!", SWIPE, 2.0),
        "swipe_good": ("좋아!", SWIPE, 1.6),
        # 신규 패턴 (U3)
        "ok_shake": ("버텼다!", GREAT_COL, 1.6),
        "ok_dive": ("버텼다!", GREAT_COL, 1.6),
        "ok_surface": ("막았다!", GREAT_COL, 1.6),
        "ok_reverse": ("따라잡음!", GREAT_COL, 1.6),
        "ok_twist": ("풀었다!", GREAT_COL, 1.6),
        "fail_shake": ("흔들림!", MISS_COL, 1.2),
        "fail_dive": ("쓸렸다!", MISS_COL, 1.2),
        "fail_surface": ("뛴다!", MISS_COL, 1.2),
        "fail_reverse": ("처졌다!", MISS_COL, 1.2),
        "fail_twist": ("꼬임!", MISS_COL, 1.2),
        "combo_ok": ("콤보!", GOLD, 2.0),
        # U4
        "ok_hide": ("끌어냄!", GREAT_COL, 1.6),
        "ok_pump": ("박자!", GREAT_COL, 1.6),
        "fail_pump": ("엇박!", MISS_COL, 1.2),
        "ok_bite": ("헛물!", GREAT_COL, 1.6),
        "fail_bite": ("물렸다!", MISS_COL, 1.2),
        "ok_fake": ("간파!", GREAT_COL, 1.6),
        "fail_fake": ("속았다!", MISS_COL, 1.2),
        "hide_peek": ("지금!", GOLD, 1.6),
        "double_perfect": ("더블!", GOLD, 2.4),
        "dual_ok": ("이중!", GOLD, 2.0),
    }

    def __init__(self):
        self.items: list[dict] = []

    def add(self, kind: str, pos, streak: int = 0) -> None:
        s, c, scale = self.STYLE[kind]
        self.say(s, c, pos, scale, streak, kind)

    def say(self, s: str, color, pos, scale: float = 1.4, streak: int = 0, kind: str = "say") -> None:
        """글자 슬롯은 하나뿐: 새 글자가 오면 이전 것은 바로 사라진다 (6글자 넘으면 잘라 냄)."""
        self.items = [{"text": s[:6], "color": color, "scale": scale, "x": pos[0], "y": pos[1] - 26, "t": 0.0,
                       "streak": streak, "kind": kind}]

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
                from src.ui import icons
                icons.pips(canvas, int(x), int(y + 14 * scale * 0.6 + 6), min(it["streak"], 8), GOLD)  # 연속: 숫자 대신 점


def big_text(canvas, s: str, center, color, scale: float, outline: bool = False) -> None:
    """픽셀 느낌 그대로 키운 큰 글씨 (테두리 포함)."""
    from src.platform.hints import localize
    s = localize(s)
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


def _arrow(canvas, cx: float, cy: float, direction: int, length: float, color, width: int = 3) -> None:
    x0, x1 = cx - direction * length / 2, cx + direction * length / 2
    pygame.draw.line(canvas, SHADOW, (x0 + 1, cy + 1), (x1 + 1, cy + 1), width + 1)
    pygame.draw.line(canvas, color, (x0, cy), (x1, cy), width)
    head = length * 0.35
    for sgn in (-1, 1):
        pygame.draw.line(canvas, SHADOW, (x1 + 1, cy + 1), (x1 - direction * head + 1, cy + sgn * head * 0.7 + 1), width)
        pygame.draw.line(canvas, color, (x1, cy), (x1 - direction * head, cy + sgn * head * 0.7), width)


def draw_swipe_ring(canvas, center, time_to_apex: float, total: float, perfect_w: float, good_w: float,
                    need: int, t: float, spread: float | None = None) -> None:
    """몸털기 점프: 하늘색 판정 원 + 안쪽 화살표. 원이 겹치는 순간 화살표 방향으로 슬라이드."""
    sp = spread or RING_SPREAD  # 신호 슬롯 안에선 작게 (31장 C3)
    if center is None or total <= 0:
        return
    cx, cy = int(center[0]), int(center[1])
    k = sp / total
    r_approach = RING_R + time_to_apex * k
    if r_approach < RING_R - good_w * k - 2:
        return
    size = (RING_R + sp + 8) * 2
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
        _flick_arrow(canvas, cx + need * 6, cy + RING_R + 12, need, SWIPE)
        _arrow(canvas, cx - need * 26, cy + RING_R + 12, need, 12, SWIPE, 2)


def _flick_arrow(canvas, x, y, d: int, col) -> None:
    """'확 꺾기!'·'슬라이드' 글자 대신: 그쪽으로 튀는 굵은 화살표 두 개."""
    d = d or 1
    for k in (0, 6):
        pts = [(x - 4 * d + k * d, y - 5), (x + 2 * d + k * d, y), (x - 4 * d + k * d, y + 5)]
        pygame.draw.lines(canvas, SHADOW, False, [(px + 1, py + 1) for px, py in pts], 3)
        pygame.draw.lines(canvas, col, False, pts, 3)

