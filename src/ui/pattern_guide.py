"""신규 패턴·루어를 직관적으로: 처음 만날 때 튜토리얼 카드(움직이는 시범 그림) + 파이팅 중 조작 방향 표시.

- 카드: tutorial.CARDS 에 "pattern:<id>"·"lure_intro"로 들어가 있고(PC 문구), 터치 문구는 TOUCH_LINES.
  카드 위쪽에 DEMO 그림이 움직이며 '무엇을 하라는지'를 보여 준다.
- 파이팅 중 표시(draw_cue): 낚싯대를 움직여야 하는 패턴(잠수 ↑, 수면 질주 ↓, 비틀기 ⟳, 머리 흔들기 = 가만히,
  역주행 = 연타, 물어뜯기 = 그 순간 Shift)은 예고·행동 동안 PC는 낚싯대 옆, 모바일은 릴 패드 위에 화살표를 그린다.
  잘하고 있으면 초록, 아니면 흰색으로 깜빡인다.
"""
import math

import pygame

from src.ui.hud import SHADOW, text

GOOD = (130, 255, 180)
WHITE = (240, 244, 252)
DIM = (150, 160, 185)
GOLD = (255, 214, 90)
RED = (255, 110, 95)
DEMO_BG = (14, 18, 34)

# 카드: (제목, PC 문구) — tutorial.CARDS 로 합쳐진다.  터치 문구는 TOUCH_LINES.
CARDS = {
    "pattern:shake": ("줄이 파르르 떨린다 → 머리 흔들기!", [
        "물고기가 바늘을 털어내려고 머리를 흔들어요.",
        "흔드는 동안 감기를 멈추고 마우스를 가만히 두세요. 움직이면 바늘이 빠지기 쉬워요.",
    ]),
    "pattern:dive": ("그림자가 작아지며 가라앉는다 → 잠수!", [
        "바닥으로 파고듭니다. 마우스를 위로 올려 낚싯대를 세우고 버티세요.",
        "세우고 있는 동안은 줄이 풀리지 않아요. 놓치면 바닥에 쓸려 줄이 상해요.",
    ]),
    "pattern:surface": ("수면에 V자 물살 → 수면 질주!", [
        "수면을 따라 달리다 뛰어오르려 해요. 마우스를 아래로 내려 낚싯대를 눕히세요.",
        "눌러 두면 거리가 확 줄어요. 놓치면 바로 점프하니 우클릭을 준비하세요.",
    ]),
    "pattern:reverse": ("정면으로 달려온다 → 역주행!", [
        "물고기가 내 쪽으로 달려와서 줄이 처집니다.",
        "좌클릭을 빠르게 연타해서 막대(회수 게이지)를 눈금 위로 유지하세요.",
    ]),
    "pattern:twist": ("몸을 빙글 → 줄 비틀기!", [
        "물고기가 몸을 돌려 줄을 꼬아요. 꼬임 게이지가 가득 차면 줄이 끊어져요.",
        "마우스로 원을 그리면 꼬임이 풀립니다. 행동이 끝난 뒤 남은 꼬임도 원으로 풀 수 있어요.",
    ]),
    "pattern:chain": ("콤보 예고!", [
        "위에 보이는 순서대로 행동 세 개가 짧은 간격으로 이어져요.",
        "하나씩 원래 방법으로 대응하세요. 세 개 모두 성공하면 물고기가 크게 지칩니다.",
    ]),
    "pattern:hide": ("바위 틈으로 → 숨기!", [
        "감기를 멈추고 줄을 풀어 주세요. 장력을 가운데 막대의 금색 칸에 맞추고 기다리면,",
        "물고기가 고개를 내밀어요(금색 번쩍). 그 순간 좌클릭으로 감으세요! 억지로 당기면 줄이 쓸려요.",
    ]),
    "pattern:pump": ("둥 둥 북소리 → 펌핑 리듬!", [
        "물고기가 박자에 맞춰 당깁니다. 박(빨간 칸)에는 감지 말고,",
        "박과 박 사이(초록 칸)에만 좌클릭으로 감으세요. 연속으로 맞히면 감기가 빨라져요.",
    ]),
    "pattern:thrash": ("크게 뛰어오른다 → 공중 몸부림!", [
        "보통 점프보다 높이 뛰고 공중에서 두 번 몸부림쳐요.",
        "정점에서 한 번, 떨어지기 직전에 한 번 더 — 우클릭(숙이기)을 두 번 하세요.",
    ]),
    "pattern:bite": ("이빨이 번쩍 → 줄 물어뜯기!", [
        "물고기가 줄을 물어뜯으려 해요. 막대가 끝까지 차는 순간 이빨이 번쩍입니다.",
        "바로 그때 Shift를 누르세요(드랙 순간 최저). 너무 일찍 누르고 있으면 안 돼요 — '새로' 눌러야 해요.",
    ]),
    "pattern:dual": ("두 가지를 동시에!", [
        "패널 두 줄에 나온 두 가지를 함께 하세요. 예: 낚싯대 세우기(마우스 위) + 원 그리기.",
        "PC는 마우스 위치와 클릭을 나눠서, 모바일은 패드와 버튼을 두 손가락으로 따로.",
    ]),
    "lure_intro": ("루어 액션!", [
        "찌가 떠 있는 동안: 짧게 클릭 = 저킹 · 누르고 있기 = 리트리브 · 가만히 = 멈춤",
        "물고기마다 좋아하는 리듬이 달라요. 그림자 위: ? 관심  ! 다가옴  ♥ 곧 문다  … 떠남",
        "안 해도 입질은 와요. 같은 물고기를 5번 잡으면 도감에 좋아하는 리듬이 나와요.",
    ]),
}

TOUCH_LINES = {
    "pattern:shake": ["물고기가 바늘을 털어내려고 머리를 흔들어요.",
                      "흔드는 동안 릴 패드에서 손을 떼고 가만히 두세요."],
    "pattern:dive": ["바닥으로 파고듭니다. 릴 패드를 위로 밀어 낚싯대를 세우고 버티세요.",
                     "세우고 있는 동안은 줄이 풀리지 않아요. 놓치면 바닥에 쓸려 줄이 상해요."],
    "pattern:surface": ["수면을 따라 달리다 뛰어오르려 해요. 릴 패드를 아래로 밀어 낚싯대를 눕히세요.",
                        "눌러 두면 거리가 확 줄어요. 놓치면 바로 점프하니 숙이기를 준비하세요."],
    "pattern:reverse": ["물고기가 내 쪽으로 달려와서 줄이 처집니다.",
                        "릴 패드를 빠르게 연타해서 막대(회수 게이지)를 눈금 위로 유지하세요."],
    "pattern:twist": ["물고기가 몸을 돌려 줄을 꼬아요. 꼬임 게이지가 가득 차면 줄이 끊어져요.",
                      "릴 패드 위에서 손가락으로 원을 그리면 꼬임이 풀립니다."],
    "pattern:chain": ["위에 보이는 순서대로 행동 세 개가 짧은 간격으로 이어져요.",
                      "하나씩 원래 방법으로 대응하세요. 세 개 모두 성공하면 물고기가 크게 지칩니다."],
    "pattern:hide": ["릴 패드에서 손을 떼고 줄을 풀어 주세요. 장력을 금색 칸에 맞추고 기다리면,",
                     "물고기가 고개를 내밀어요(금색 번쩍). 그 순간 패드를 눌러 감으세요!"],
    "pattern:pump": ["물고기가 박자에 맞춰 당깁니다. 박(빨간 칸)에는 감지 말고,",
                     "박과 박 사이(초록 칸)에만 릴 패드를 누르세요. 연속으로 맞히면 감기가 빨라져요."],
    "pattern:thrash": ["보통 점프보다 높이 뛰고 공중에서 두 번 몸부림쳐요.",
                       "정점에서 한 번, 떨어지기 직전에 한 번 더 — 숙이기 버튼을 두 번 누르세요."],
    "pattern:bite": ["물고기가 줄을 물어뜯으려 해요. 막대가 끝까지 차는 순간 이빨이 번쩍입니다.",
                     "바로 그때 ▼ 버튼을 길게 누르세요(드랙 순간 최저). 미리 누르고 있으면 안 돼요."],
    "pattern:dual": ["패널 두 줄에 나온 두 가지를 함께 하세요.",
                     "한 손가락은 릴 패드, 다른 손가락은 버튼 — 따로따로 대응하세요."],
    "lure_intro": ["찌가 떠 있는 동안: 물 위 짧게 탭 = 저킹 · 리트리브 패드 누르기 · 가만히 = 멈춤",
                   "물고기마다 좋아하는 리듬이 달라요. 그림자 위: ? 관심  ! 다가옴  ♥ 곧 문다  … 떠남",
                   "안 해도 입질은 와요. 같은 물고기를 5번 잡으면 도감에 좋아하는 리듬이 나와요."],
}

# 카드 키 → 시범 그림 종류
DEMO = {k: k.split(":", 1)[1] for k in CARDS if k.startswith("pattern:")}
DEMO["lure_intro"] = "lure"
CUE = ("shake", "dive", "surface", "twist", "reverse", "bite")  # 파이팅 중 방향 표시를 그리는 패턴


# ───────────────────────── 그림 조각 ─────────────────────────

def _chevrons(canvas, cx, cy, direction: int, t: float, col, size: int = 10) -> None:
    """세 겹 꺾쇠가 direction(-1 위, +1 아래) 쪽으로 흘러간다."""
    for i in range(3):
        ph = (t * 1.8 + i / 3) % 1.0
        y = cy + direction * (ph - 0.5) * size * 2.4
        a = int(255 * math.sin(ph * math.pi))
        s = pygame.Surface((size * 2 + 2, size + 2), pygame.SRCALPHA)
        tipy = 1 if direction < 0 else size
        basey = size if direction < 0 else 1
        pygame.draw.lines(s, (*col, a), False, [(1, basey), (size + 1, tipy), (size * 2 + 1, basey)], 3)
        canvas.blit(s, (cx - size - 1, int(y) - size // 2 - 1))


def _ring_arrow(canvas, cx, cy, r: int, t: float, col, width: int = 3) -> None:
    """돌아가는 원 화살표 (비틀기 풀기)."""
    start = t * 4.0
    span = math.tau * 0.78
    pts = [(cx + math.cos(start + span * k / 24) * r, cy + math.sin(start + span * k / 24) * r) for k in range(25)]
    pygame.draw.lines(canvas, col, False, pts, width)
    ang = start + span
    hx, hy = cx + math.cos(ang) * r, cy + math.sin(ang) * r
    tx, ty = -math.sin(ang), math.cos(ang)  # 진행 방향
    nx, ny = math.cos(ang), math.sin(ang)
    s = 5 + width
    pygame.draw.polygon(canvas, col, [(hx + tx * s, hy + ty * s), (hx + nx * s * 0.7, hy + ny * s * 0.7),
                                      (hx - nx * s * 0.7, hy - ny * s * 0.7)])


def _mouse(canvas, cx, cy, col, left_on: bool = False) -> None:
    r = pygame.Rect(cx - 7, cy - 10, 14, 20)
    pygame.draw.rect(canvas, col, r, 1, border_radius=6)
    canvas.fill(col, (cx, cy - 10, 1, 8))
    if left_on:
        canvas.fill(GOLD, (cx - 6, cy - 9, 6, 7))


def _pad(canvas, cx, cy, r, col, knob=(0.0, 0.0)) -> None:
    pygame.draw.circle(canvas, col, (cx, cy), r, 1)
    pygame.draw.circle(canvas, col, (int(cx + knob[0] * r * 0.6), int(cy + knob[1] * r * 0.6)), max(3, r // 3))


def _key(canvas, cx, cy, label: str, lit: bool) -> None:
    w = max(26, 8 + 7 * len(label))
    r = pygame.Rect(cx - w // 2, cy - 8, w, 16)
    canvas.fill(GOLD if lit else (40, 46, 70), r)
    pygame.draw.rect(canvas, WHITE, r, 1, border_radius=3)
    text(canvas, label, r.center, (20, 20, 30) if lit else WHITE, 11, "center")


def _hand_still(canvas, cx, cy, t: float, col) -> None:
    """가만히: 일시정지 두 막대 + 옆에 떨리는 줄."""
    canvas.fill(col, (cx - 7, cy - 9, 4, 18))
    canvas.fill(col, (cx + 3, cy - 9, 4, 18))
    for i in range(10):
        x = cx + 14 + i * 2
        y = cy + math.sin(t * 40 + i) * 3
        canvas.fill(DIM, (x, int(y), 2, 2))


# ───────────────────────── 카드 시범 그림 ─────────────────────────

def draw_demo(canvas, kind: str, rect: pygame.Rect, t: float, touch: bool) -> None:
    """카드 위쪽 시범 그림 (rect 안)."""
    canvas.fill(DEMO_BG, rect)
    pygame.draw.rect(canvas, (60, 70, 100), rect, 1)
    cx, cy = rect.center
    loop = t % 2.0
    dev_x = cx - 40
    if kind in ("dive", "surface"):
        d = -1 if kind == "dive" else 1
        k = min(1.0, loop / 0.8)
        if touch:
            _pad(canvas, dev_x, cy, 18, WHITE, (0, d * k))
        else:
            _mouse(canvas, dev_x, int(cy + d * k * 12), WHITE)
        _chevrons(canvas, cx + 6, cy - 6, d, t, GOOD if k >= 1 else WHITE, 12)
        _rod_icon(canvas, cx + 50, cy + 4, -d * 0.6 * k)
        text(canvas, "낚싯대 세우기" if d < 0 else "낚싯대 눕히기", (cx + 6, rect.bottom - 7), DIM, 11, "center")
    elif kind == "twist":
        a = t * 4.0
        if touch:
            _pad(canvas, dev_x, cy, 18, WHITE, (math.cos(a), math.sin(a)))
        else:
            _mouse(canvas, int(dev_x + math.cos(a) * 10), int(cy + math.sin(a) * 10), WHITE)
        _ring_arrow(canvas, cx + 30, cy - 6, 14, t, GOOD)
        text(canvas, "원 그리기", (cx + 30, rect.bottom - 7), DIM, 11, "center")
    elif kind == "shake":
        if touch:
            _pad(canvas, dev_x, cy, 18, DIM)
        else:
            _mouse(canvas, dev_x, cy, WHITE)
        _hand_still(canvas, cx + 10, cy - 6, t, GOOD)
        text(canvas, "감기 멈춤 · 가만히", (cx + 30, rect.bottom - 7), DIM, 11, "center")
    elif kind == "reverse":
        on = int(t * 8) % 2 == 0
        if touch:
            _pad(canvas, dev_x, cy, 18, GOLD if on else WHITE)
        else:
            _mouse(canvas, dev_x, cy, WHITE, left_on=on)
        fill = 0.55 + 0.25 * math.sin(t * 3)
        bx, bw = cx + 4, 70
        canvas.fill((40, 44, 62), (bx, cy - 2, bw, 5))
        canvas.fill(GOOD, (bx, cy - 2, int(bw * fill), 5))
        canvas.fill(WHITE, (bx + int(bw * 0.5), cy - 5, 1, 11))
        text(canvas, "연타!", (cx + 40, rect.bottom - 7), DIM, 11, "center")
    elif kind == "hide":
        bx, bw = cx - 60, 120
        canvas.fill((40, 44, 62), (bx, cy - 3, bw, 6))
        canvas.fill((70, 140, 90), (bx + 40, cy - 3, 50, 6))
        canvas.fill(GOLD, (bx + 34, cy - 5, 14, 1))
        canvas.fill(GOLD, (bx + 34, cy + 4, 14, 1))
        k = min(1.0, loop / 1.0)
        mx = bx + int(bw * (0.7 - 0.12 - 0.42 * k * 0.9))
        canvas.fill(WHITE, (mx, cy - 6, 2, 12))
        peek = loop > 1.3
        text(canvas, "! 지금 감기" if peek else "풀어 주고 기다리기", (cx, cy + 16), GOLD if peek else DIM, 11, "center")
    elif kind == "pump":
        n, w = 4, 140
        x0 = cx - w // 2
        cw = w / n
        for i in range(n):
            x = int(x0 + i * cw)
            canvas.fill((40, 44, 62), (x + 1, cy - 3, int(cw) - 2, 8))
            canvas.fill((200, 90, 80), (x + 1, cy - 3, int(cw * 0.25), 8))
            canvas.fill((70, 140, 90), (x + int(cw * 0.3), cy - 3, int(cw * 0.4), 8))
        k = (t * 1.6) % n
        mx = int(x0 + k * cw)
        canvas.fill(WHITE, (mx, cy - 6, 1, 14))
        in_gap = 0.3 <= (k % 1) <= 0.7
        text(canvas, "감기!" if in_gap else "멈춤", (cx, cy + 16), GOOD if in_gap else RED, 11, "center")
    elif kind == "thrash":
        x0, x1 = cx - 50, cx + 50
        pts = [(x0 + (x1 - x0) * k / 20, cy + 14 - math.sin(math.pi * k / 20) * 26) for k in range(21)]
        pygame.draw.lines(canvas, DIM, False, pts, 1)
        k = (t * 0.6) % 1.0
        fx, fy = pts[int(k * 20)]
        pygame.draw.circle(canvas, WHITE, (int(fx), int(fy)), 3)
        for mk, label in ((0.5, "1"), (0.85, "2")):
            px, py = pts[int(mk * 20)]
            hit = abs(k - mk) < 0.06
            pygame.draw.circle(canvas, GOLD if hit else (120, 110, 70), (int(px), int(py)), 6, 1)
            text(canvas, label, (int(px), int(py) - 11), GOLD, 11, "center")
        text(canvas, "숙이기" if touch else "우클릭", (cx, rect.bottom - 7), DIM, 11, "center")
    elif kind == "bite":
        k = (t % 1.6) / 1.2
        bw = 100
        bx = cx - bw // 2 - 20
        canvas.fill((40, 44, 62), (bx, cy - 2, bw, 5))
        canvas.fill((255, 160, 120), (bx, cy - 2, int(bw * min(1.0, k)), 5))
        canvas.fill(WHITE, (bx + bw - 1, cy - 6, 2, 13))
        lit = 1.0 <= k <= 1.15
        if lit:
            pygame.draw.line(canvas, WHITE, (bx + bw - 6, cy - 9), (bx + bw + 4, cy + 1), 1)
        _key(canvas, cx + 52, cy, "▼" if touch else "Shift", lit)
        text(canvas, "번쩍이는 순간!", (cx, rect.bottom - 7), DIM, 11, "center")
    elif kind == "chain":
        labels = ["돌진", "잠수", "점프"]
        cur = int(t * 1.2) % 3
        x = cx - 70
        for i, lb in enumerate(labels):
            r = text(canvas, lb, (x, cy), GOLD if i == cur else (DIM if i < cur else WHITE), 11, "midleft")
            x = r.right + 6
            if i < 2:
                text(canvas, "→", (x + 4, cy), DIM, 11, "center")
                x += 14
    elif kind == "dual":
        _chevrons(canvas, cx - 30, cy, -1, t, GOOD, 10)
        text(canvas, "+", (cx, cy), WHITE, 16, "center")
        _ring_arrow(canvas, cx + 34, cy, 12, t, GOOD, 2)
    elif kind == "lure":
        _lure_demo(canvas, rect, t, touch)


def _rod_icon(canvas, x, y, lift: float) -> None:
    ang = math.radians(-35 - lift * 30)
    ex, ey = x + math.cos(ang) * 30, y + math.sin(ang) * 30
    pygame.draw.line(canvas, (190, 160, 110), (x, y), (ex, ey), 2)


def _lure_demo(canvas, rect, t: float, touch: bool) -> None:
    """루어: 세 가지 액션이 차례로 + 그림자 반응 표시."""
    cx, cy = rect.center
    phase = int(t / 2.0) % 3
    names = ["저킹 (짧게 톡)", "리트리브 (누르고 있기)", "멈춤 (가만히)"]
    for i, nm in enumerate(names):
        text(canvas, nm, (rect.x + 8, rect.y + 10 + i * 13), GOLD if i == phase else DIM, 11, "midleft")
    fx, fy = cx + 50, cy + 2
    if phase == 0:
        hop = 4 if (t * 2) % 1.0 < 0.15 else 0
        pygame.draw.circle(canvas, (255, 90, 80), (fx, fy - hop), 3)
    elif phase == 1:
        off = int(((t % 2.0) / 2.0) * 16)
        pygame.draw.circle(canvas, (255, 90, 80), (fx - off, fy), 3)
    else:
        pygame.draw.circle(canvas, (255, 90, 80), (fx, fy), 3)
    sx = fx + 26 - int(min(1.0, (t % 6.0) / 6.0) * 16)
    pygame.draw.ellipse(canvas, (50, 70, 90), (sx - 8, fy - 3, 16, 7))
    marks = ["?", "!", "♥"]
    text(canvas, marks[min(2, int((t % 6.0) / 2.0))], (sx, fy - 12), GOLD, 11, "center")


# ───────────────────────── 카드 ─────────────────────────

def draw_card(canvas, key: str, title: str, lines_pc: list, focus, t: float, touch: bool) -> None:
    from src.ui import tutorial as tut
    from src.ui.hud import wrap_text
    raw = TOUCH_LINES.get(key, lines_pc) if touch else lines_pc
    w, h = canvas.get_size()
    pw = 440
    lines = [ln for r in raw for ln in wrap_text(r, pw - 24)]
    tut._dim(canvas)
    demo_h = 58
    ph = 34 + demo_h + 8 + len(lines) * 15 + 18
    x = (w - pw) // 2
    y = max(8, (h - ph) // 2 - 10)
    canvas.fill(SHADOW, (x + 2, y + 2, pw, ph))
    canvas.fill(tut.PANEL, (x, y, pw, ph))
    pygame.draw.rect(canvas, tut.BORDER, (x, y, pw, ph), 1)
    text(canvas, title, (w // 2, y + 14), tut.BORDER, 16, "center")
    demo = pygame.Rect(x + 60, y + 28, pw - 120, demo_h)
    draw_demo(canvas, DEMO.get(key, ""), demo, t, touch)
    ty = demo.bottom + 10
    for i, ln in enumerate(lines):
        text(canvas, ln, (w // 2, ty + i * 15), (232, 236, 245), 11, "center")
    if t > 0.35 and int(t * 2) % 2 == 0:
        text(canvas, "탭해서 계속" if touch else "클릭해서 계속", (w // 2, y + ph - 9), (160, 170, 195), 11, "center")


# ───────────────────────── 파이팅 중 조작 방향 ─────────────────────────

def _doing_ok(pat, pitch: float) -> bool:
    if pat.id == "dive":
        return pitch >= pat.c["pitch_need"]
    if pat.id == "surface":
        return pitch <= -pat.c["pitch_need"]
    if pat.id in ("shake", "reverse"):
        return bool(getattr(pat, "last_ok", False)) or (pat.id == "reverse" and pat.gauge >= pat.c["keep_level"])
    return False


def draw_cue(canvas, fight, pitch: float, anchor, t: float, touch: bool, bite_anchor=None) -> None:
    """예고·행동 중인 '조작형' 패턴의 방향 표시. anchor = PC 낚싯대 옆 / 모바일 릴 패드 위.
    bite_anchor: 모바일에서 물어뜯기는 ▼ 버튼 옆에 (누를 곳 바로 옆)."""
    b = fight.brain
    if b.sound_only:
        return
    pats = [p for p in fight.pats if p.id in CUE]
    if bite_anchor is not None and any(p.id == "bite" for p in pats):
        p = next(p for p in pats if p.id == "bite")
        _cue_one(canvas, p, int(bite_anchor[0]), int(bite_anchor[1]), t, WHITE, touch)
        pats = [q for q in pats if q.id != "bite"]
    if not pats:
        return
    cx, cy = int(anchor[0]), int(anchor[1])
    n = len(pats)
    for i, p in enumerate(pats):
        x = cx + (i - (n - 1) / 2) * 46
        ok = p.active and _doing_ok(p, pitch)
        blink = p.active or int(t * 6) % 2 == 0
        col = GOOD if ok else (WHITE if blink else DIM)
        _cue_one(canvas, p, int(x), cy, t, col, touch)


def _cue_one(canvas, p, x: int, y: int, t: float, col, touch: bool) -> None:
    pid = p.id
    back = pygame.Surface((46, 56), pygame.SRCALPHA)
    pygame.draw.rect(back, (10, 14, 28, 120), back.get_rect(), border_radius=8)
    canvas.blit(back, (x - 23, y - 32))
    if pid == "dive":
        _chevrons(canvas, x, y - 6, -1, t, col, 12)
        label = "위로"
    elif pid == "surface":
        _chevrons(canvas, x, y - 6, 1, t, col, 12)
        label = "아래로"
    elif pid == "twist":
        _ring_arrow(canvas, x, y - 11, 10, t, col, 2)
        label = "원"
    elif pid == "shake":
        _hand_still(canvas, x - 6, y - 6, t, col)
        label = "가만히"
    elif pid == "reverse":
        on = int(t * 10) % 2 == 0
        pygame.draw.circle(canvas, col, (x, y - 6), 9 if on else 6, 2)
        label = "연타"
    else:  # bite
        b = p.fight.brain
        lit = b.state != "telegraph" or b.timer < 0.15
        _key(canvas, x, y - 6, "▼" if touch else "Shift", lit)
        label = "지금!" if lit else "준비"
    text(canvas, label, (x, y + 16), col, 11, "center")
