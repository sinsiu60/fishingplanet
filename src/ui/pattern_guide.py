"""신규 패턴·루어를 직관적으로: 처음 만날 때 튜토리얼 카드(움직이는 시범 그림).

- 카드: tutorial.CARDS 에 "pattern:<id>"로 들어가 있고(PC 문구), 터치 문구는 TOUCH_LINES.
  카드 위쪽에 DEMO 그림이 움직이며 '무엇을 하라는지'를 보여 준다.
- 파이팅 중 조작 방향 표시는 31장 C3부터 신호 슬롯(src/ui/signal_slots.py)이 맡는다.
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

# 첫 만남 정지 카드 (31장 C5): 신호 아이콘(물고기 자리 배지와 같은 그림) + 손동작 애니메이션 + 한 줄.
# (제목, [PC 한 줄]) — tutorial.CARDS 로 합쳐진다. 터치 한 줄은 TOUCH_LINES. 기존 행동(돌진·점프·방향 전환·몸털기) 카드도 같은 모양으로.
CARDS = {
    "telegraph:rush": ("돌진!", ["웅크린 뒤 빛이 줄을 타고 손에 닿으면 돌진 — 그 순간 Q(풀기) 한 번"]),
    "telegraph:jump": ("점프!", ["줄에 하늘색 빛이 오면 점프 — 링이 겹치는 순간 우클릭 (낚싯대 숙이기)"]),
    "telegraph:turn": ("방향 전환!", ["줄에 노란 빛 + 갈매기표 쪽으로 — 막대가 가운데일 때 마우스를 확"]),
    "telegraph:leap": ("몸털기 점프!", ["링이 겹치는 순간 화살표 쪽으로 마우스를 확"]),
    "pattern:shake": ("머리 흔들기!", ["흔드는 동안 감기를 멈추고 마우스를 가만히"]),
    "pattern:dive": ("잠수!", ["마우스를 위로 — 낚싯대를 세워 버틴다"]),
    "pattern:surface": ("수면 질주!", ["마우스를 아래로 — 낚싯대를 눕혀 누른다"]),
    "pattern:reverse": ("역주행!", ["좌클릭 연타로 막대를 눈금 위로"]),
    "pattern:twist": ("줄 비틀기!", ["마우스로 원을 그려 꼬임을 푼다"]),
    "pattern:chain": ("콤보!", ["위에 뜬 아이콘 순서대로 하나씩 대응"]),
    "pattern:hide": ("숨기!", ["감기를 멈추고 장력 줄 금색 칸까지 풀었다가, 번쩍이면 감기"]),
    "pattern:pump": ("펌핑 리듬!", ["빨간 박엔 멈추고, 박 사이에만 좌클릭"]),
    "pattern:thrash": ("공중 몸부림!", ["정점에 한 번, 떨어지기 직전에 한 번 더 우클릭"]),
    "pattern:bite": ("줄 물어뜯기!", ["막대가 다 차는 순간 Shift (드랙 순간 최저)"]),
    "pattern:dual": ("두 가지 동시에!", ["물고기 옆에 나란히 뜬 두 신호를 각각 함께"]),
}

TOUCH_LINES = {
    "telegraph:rush": ["웅크린 뒤 빛이 줄을 타고 손에 닿으면 돌진 — 그 순간 '풀기' 버튼 한 번"],
    "telegraph:jump": ["줄에 하늘색 빛이 오면 점프 — 링이 겹치는 순간 숙이기 버튼"],
    "telegraph:turn": ["줄에 노란 빛 + 갈매기표 쪽으로 — 막대가 가운데일 때 패드를 확"],
    "telegraph:leap": ["링이 겹치는 순간 화살표 쪽으로 패드를 확"],
    "pattern:shake": ["흔드는 동안 패드에서 손을 떼고 가만히"],
    "pattern:dive": ["패드를 위로 밀어 낚싯대를 세운다"],
    "pattern:surface": ["패드를 아래로 밀어 낚싯대를 눕힌다"],
    "pattern:reverse": ["패드 연타로 막대를 눈금 위로"],
    "pattern:twist": ["패드 위에서 원을 그려 꼬임을 푼다"],
    "pattern:chain": ["위에 뜬 아이콘 순서대로 하나씩 대응"],
    "pattern:hide": ["패드에서 손을 떼고 기다렸다가, 번쩍이면 패드"],
    "pattern:pump": ["빨간 박엔 멈추고, 박 사이에만 패드"],
    "pattern:thrash": ["정점에 한 번, 떨어지기 직전에 한 번 더 숙이기"],
    "pattern:bite": ["막대가 다 차는 순간 ▼ 길게 (드랙 순간 최저)"],
    "pattern:dual": ["나란히 뜬 두 신호를 손가락 둘로 각각"],
}

# 카드 키 → 시범 그림 종류
DEMO = {k: k.split(":", 1)[1] for k in CARDS if k.startswith(("pattern:", "telegraph:"))}


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
        # 콤보: 물고기 위 순서 줄과 같은 아이콘 줄 — 하나씩 꺼진다
        from src.ui import signal_slots as ss
        seq = [("release", (1, 0)), ("direction", (0, -1)), ("timing", (1, 0))]
        cur = int(t * 1.2) % 4
        for i, (fam, dirv) in enumerate(seq):
            px = cx - 40 + i * 40
            if i < cur:
                pygame.draw.circle(canvas, (60, 66, 90), (px, cy), 4)
                continue
            if i == cur:
                pygame.draw.circle(canvas, WHITE, (px, cy), 13, 1)
            ss.family_icon(canvas, fam, px, cy, ss.color_of(fam), t, dir=dirv)
    elif kind == "dual":
        _chevrons(canvas, cx - 30, cy, -1, t, GOOD, 10)
        text(canvas, "+", (cx, cy), WHITE, 16, "center")
        _ring_arrow(canvas, cx + 34, cy, 12, t, GOOD, 2)
    elif kind == "rush":
        # 돌진 예고 = 줄 펄스 (31-14): 웅크림 → 빛이 줄을 타고 물고기→손 → 닿는 순간 돌진. 그 전에 드랙↓
        loop = t % 2.6
        fx, fy = rect.x + 34, cy + 8            # 물고기 (왼쪽 아래)
        hx, hy = rect.right - 46, rect.y + 12   # 낚싯대 끝 (오른쪽 위)
        crouch = min(1.0, loop / 0.7)
        rushing = loop > 1.9
        # 그림자: 웅크림(압축 + 꼬리 S) → 돌진(길게 늘어나며 멀어짐)
        sq = 1 - 0.38 * crouch if not rushing else 1.6
        sx = fx - (loop - 1.9) * 20 if rushing else fx
        bw = int(26 * sq)
        pygame.draw.ellipse(canvas, (30, 44, 70), (sx - bw // 2, fy - 5, bw, 10))
        if not rushing:
            tx = sx + bw // 2
            pygame.draw.lines(canvas, (30, 44, 70), False, [(tx, fy), (tx + 5, fy - 4 * crouch), (tx + 9, fy + 1),
                                                           (tx + 12, fy + 4 * crouch)], 3)
            # 안쪽으로 빨려드는 점선 물결
            for i in range(3):
                k = 1 - ((t / 0.6 + i / 3) % 1.0)
                rx, ry = 10 + 22 * k, (10 + 22 * k) * 0.32
                for j in range(0, 14, 2):
                    a0, a1 = j / 14 * math.tau, (j + 1) / 14 * math.tau
                    pygame.draw.line(canvas, (150, 175, 210), (fx + math.cos(a0) * rx, fy + math.sin(a0) * ry),
                                     (fx + math.cos(a1) * rx, fy + math.sin(a1) * ry), 1)
        else:
            for s_ in (-1, 1):
                pygame.draw.line(canvas, (220, 235, 255), (sx + bw // 2, fy), (sx + bw // 2 + 18, fy + s_ * 7), 1)
        # 줄 (느슨 → 팽팽)
        sag = 10 * crouch * (1 if loop < 1.9 else 0) + (2 if loop < 1.9 else 0)
        pts = []
        for i in range(17):
            u = i / 16
            x = hx + (sx - hx) * u
            y = hy + (fy - hy) * u + math.sin(u * math.pi) * sag
            pts.append((x, y))
        pygame.draw.lines(canvas, (255, 255, 255) if rushing and loop < 2.15 else (200, 205, 215), False, pts, 1)
        _rod_icon(canvas, hx + 22, hy + 16, 0.6)
        # 빛 펄스: 물고기 → 손
        if 0.7 <= loop < 1.9:
            q = (loop - 0.7) / 1.2
            i = int((1 - q) * 16)
            px, py = pts[min(16, i)]
            pygame.draw.circle(canvas, (255, 236, 160), (int(px), int(py)), 5, 1)
            pygame.draw.circle(canvas, (255, 255, 255), (int(px), int(py)), 2)
        # Q(▼): 펄스가 손에 가까워지면 눌러 둔다
        _key(canvas, rect.x + 14, rect.y + 12, "▼" if touch else "Q", 1.4 <= loop < 2.4)
    elif kind in ("jump", "leap"):
        from src.ui import fight_fx
        tta = 1.0 - (t % 1.6)
        if kind == "jump":
            fight_fx.draw_jump_ring(canvas, (cx + 20, cy), tta, 1.0, 0.08, 0.16, t, spread=24)
        else:
            fight_fx.draw_swipe_ring(canvas, (cx + 20, cy), tta, 1.0, 0.08, 0.16, 1, t, spread=24)
        hit = abs(tta) < 0.1
        if touch:
            _pad(canvas, dev_x, cy, 14, GOLD if hit else WHITE, (0.8 if (hit and kind == "leap") else 0, 0))
        elif kind == "jump":
            r = pygame.Rect(dev_x - 7, cy - 10, 14, 20)
            pygame.draw.rect(canvas, WHITE, r, 1, border_radius=6)
            canvas.fill(WHITE, (dev_x, cy - 10, 1, 8))
            if hit:
                canvas.fill(GOLD, (dev_x + 1, cy - 9, 6, 7))  # 우클릭
        else:
            _mouse(canvas, dev_x + (8 if hit else 0), cy, WHITE)
    elif kind == "turn":
        ph = (t % 1.6) / 1.6
        mx = dev_x + (10 if 0.45 < ph < 0.7 else 0)
        if touch:
            _pad(canvas, dev_x, cy, 14, WHITE, (0.8 if 0.45 < ph < 0.7 else 0, 0))
        else:
            _mouse(canvas, mx, cy, WHITE)
        bx, bw = cx - 4, 70
        canvas.fill((40, 44, 62), (bx, cy + 8, bw, 3))
        canvas.fill(GOLD, (bx + bw // 2 - 4, cy + 8, 8, 3))
        canvas.fill(WHITE, (bx + int(bw * ph), cy + 5, 2, 9))
        pygame.draw.line(canvas, WHITE, (bx + 20, cy - 6), (bx + 46, cy - 6), 3)
        pygame.draw.polygon(canvas, WHITE, [(bx + 52, cy - 6), (bx + 44, cy - 11), (bx + 44, cy - 1)])


def _rod_icon(canvas, x, y, lift: float) -> None:
    ang = math.radians(-35 - lift * 30)
    ex, ey = x + math.cos(ang) * 30, y + math.sin(ang) * 30
    pygame.draw.line(canvas, (190, 160, 110), (x, y), (ex, ey), 2)


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
    demo = pygame.Rect(x + 96, y + 28, pw - 156, demo_h)
    draw_demo(canvas, DEMO.get(key, ""), demo, t, touch)
    # 왼쪽: 파이팅 중 물고기 자리 배지에 뜨는 아이콘 그대로 (31장 C5)
    kind = DEMO.get(key, "")
    if kind:
        from src.ui import signal_slots as ss
        fam = ss.family_of(kind)
        if fam in ss.cfg()["families"]:
            col = ss.color_of(fam)
            box = pygame.Rect(0, 0, 44, 44)
            box.center = (x + 60, demo.centery)
            canvas.fill((12, 16, 30), box)
            pygame.draw.rect(canvas, col, box, 2, border_radius=8)
            dirv = (0, -1) if kind == "dive" else (0, 1) if kind == "surface" else (1, 0)
            ss.family_icon(canvas, fam, box.centerx, box.centery, col, t, dir=dirv)
        elif kind in ("chain", "dual"):
            from src.ui import icons
            icons.pips(canvas, x + 60, demo.centery, 3 if kind == "chain" else 2, GOLD, 8)
    ty = demo.bottom + 10
    for i, ln in enumerate(lines):
        text(canvas, ln, (w // 2, ty + i * 15), (232, 236, 245), 11, "center")
    if t > 0.35 and int(t * 2) % 2 == 0:
        text(canvas, "탭해서 계속" if touch else "클릭해서 계속", (w // 2, y + ph - 9), (160, 170, 195), 11, "center")
