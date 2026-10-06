"""메뉴·상점·도감 공통 UI 부품 (버튼, 패널, 탭).

손맛 (DETAILS.md G, DESIGN.md 45장 DT10): 버튼 · 탭을 누르면 0.08초 동안 1px 아래로 + 작은 클릭 소리,
소지금은 0.5초 동안 숫자가 올라가며 동전 짤랑 한 번 (money_anim).
"""
import time

import pygame

from src.core.mathutil import lerp_color
from src.platform.detect import IS_MOBILE
from src.ui.hud import SHADOW, text

PANEL = (22, 28, 48)
PANEL_LIGHT = (34, 42, 68)
BORDER = (90, 104, 150)
ACCENT = (255, 220, 120)
TEXT = (232, 236, 245)
DIM = (140, 148, 170)
GOOD = (140, 240, 150)
BAD = (255, 140, 120)
# 모바일: 메뉴 버튼은 손가락보다 작아서(폰에서 높이 16px ≈ 4mm) 판정을 위아래·좌우 3px씩 넉넉하게
TOUCH_SLOP = 3 if IS_MOBILE else 0


def _hit(rect, pos) -> bool:
    return (rect.inflate(TOUCH_SLOP * 2, TOUCH_SLOP * 2) if TOUCH_SLOP else rect).collidepoint(pos)


# ── 손맛 (DT10) ──
SFX = None            # Game 이 넣어 줌 (효과음). 없으면 소리 없이 그림만
PRESS_SEC = 0.08
_PRESSED: dict = {}   # 눌린 버튼 자리 (x, y, w, h) → 누른 시각


def press(rect, sound: bool = True) -> None:
    """버튼이 눌렸다: 0.08초 동안 1px 아래로 + 부드러운 클릭 (같은 프레임의 다른 ui_click 은 최소 간격으로 걸러짐)."""
    now = time.perf_counter()
    if len(_PRESSED) > 64:
        for k in [k for k, t0 in _PRESSED.items() if now - t0 > PRESS_SEC]:
            del _PRESSED[k]
    _PRESSED[tuple(pygame.Rect(rect))] = now
    if sound and SFX is not None:
        SFX.play("ui_click", 0.6)


def pressed_dy(rect) -> int:
    t0 = _PRESSED.get(tuple(pygame.Rect(rect)))
    return 1 if t0 is not None and time.perf_counter() - t0 < PRESS_SEC else 0


_MONEY = {"shown": None, "from": 0, "to": 0, "t0": 0.0}
MONEY_SEC = 0.5


def money_anim(v: int) -> int:
    """지금 보여 줄 소지금: 값이 오르면 0.5초 동안 촤라락 올라감 + 동전 짤랑 한 번 (내려가면 바로).
    판매처럼 이미 동전 소리가 난 순간이면 짤랑을 다시 내지 않는다."""
    m = _MONEY
    now = time.perf_counter()
    if m["shown"] is None:
        m.update(shown=v, to=v, **{"from": v})
        return v
    if v != m["to"]:
        cur = _money_now(now)
        if v > cur:
            m.update(to=v, t0=now, **{"from": cur})
            if SFX is not None:
                last = max(SFX.last_play.get(n, -9.0) for n in ("sfx_coin", "ui_buy", "ui_coin"))
                if SFX.clock - last > 0.3:
                    SFX.play("ui_coin", 0.5)
        else:
            m.update(to=v, t0=now - MONEY_SEC, **{"from": v})
    m["shown"] = _money_now(now)
    return m["shown"]


def _money_now(now: float) -> int:
    m = _MONEY
    u = min(1.0, (now - m["t0"]) / MONEY_SEC)
    u = 1 - (1 - u) ** 3
    return int(round(m["from"] + (m["to"] - m["from"]) * u))


def panel(canvas, rect, border=BORDER, fill=PANEL) -> None:
    r = pygame.Rect(rect)
    canvas.fill(SHADOW, r.move(2, 2))
    canvas.fill(fill, r)
    pygame.draw.rect(canvas, border, r, 1)


def dim(canvas, alpha: int = 150) -> None:
    from src.ui.layers import solid
    canvas.blit(solid(canvas, "dim", (6, 8, 20, alpha)), (0, 0))


_BACK: dict = {}


def backdrop(canvas, below, alpha: int, key: str = "menu") -> None:
    """메뉴 뒤 배경 = 아래 화면 + 어둡게 (dim). 메뉴가 떠 있는 동안 아래 화면은 업데이트되지 않아 멈춘 그림이므로,
    다 어두워진 뒤엔 한 번 그린 것을 붙여 쓴다 (30프레임마다 다시 · 어둡기가 바뀌면 바로 다시, DESIGN.md 44).
    아래 화면이 알려 준 튜토리얼 강조 자리(targets)도 그대로 다시 알려 준다."""
    from src.render.screen import opaque
    from src.tutorial import targets
    c = _BACK.get(key)
    sig = (id(below), canvas.get_size(), int(alpha))
    if c is None or c["sig"] != sig or c["n"] >= 30:
        before = {k: len(v) for k, v in targets._marks.items()}
        below.draw(canvas)
        dim(canvas, alpha)
        surf = c["surf"] if c is not None and c["surf"].get_size() == canvas.get_size() else opaque(canvas.get_size())
        surf.blit(canvas, (0, 0))
        marks = {k: list(v[before.get(k, 0):]) for k, v in targets._marks.items() if len(v) > before.get(k, 0)}
        _BACK[key] = {"sig": sig, "surf": surf, "n": 0, "marks": marks}
        return
    canvas.blit(c["surf"], (0, 0))
    c["n"] += 1
    for k, v in c["marks"].items():
        targets._marks.setdefault(k, []).extend(v)


class Button:
    def __init__(self, rect, label: str, action=None, enabled: bool = True, size: int = 11, accent=ACCENT):
        self.rect = pygame.Rect(rect)
        self.label = label
        self.action = action
        self.enabled = enabled
        self.size = size
        self.accent = accent

    def hovered(self, mouse) -> bool:
        return self.rect.collidepoint(mouse)

    def draw(self, canvas, mouse, selected: bool = False) -> None:
        hov = self.enabled and self.hovered(mouse)
        fill = PANEL_LIGHT if hov or selected else PANEL
        border = self.accent if (hov or selected) and self.enabled else BORDER
        dy = pressed_dy(self.rect)
        r = self.rect.move(0, dy)   # 눌림: 버튼 전체가 1px 아래로 (그림자는 그대로)
        canvas.fill(SHADOW, self.rect.move(1, 1))
        canvas.fill(fill, r)
        pygame.draw.rect(canvas, border, r, 1)
        col = (TEXT if not hov else self.accent) if self.enabled else DIM
        text(canvas, self.label, r.center, col, self.size, "center")

    def click(self, mouse) -> bool:
        if self.enabled and _hit(self.rect, mouse) and self.action:
            press(self.rect)
            self.action()
            return True
        return False


class Tabs:
    def __init__(self, x: int, y: int, labels: list[str], width: int = 56, height: int = 16):
        self.labels = labels
        self.index = 0
        self.rects = [pygame.Rect(x + i * (width + 2), y, width, height) for i in range(len(labels))]

    def draw(self, canvas, mouse) -> None:
        for i, (r, label) in enumerate(zip(self.rects, self.labels)):
            sel = i == self.index
            hov = r.collidepoint(mouse)
            r = r.move(0, pressed_dy(r))
            canvas.fill(PANEL_LIGHT if sel else PANEL, r)
            pygame.draw.rect(canvas, ACCENT if sel else (BORDER if not hov else TEXT), r, 1)
            text(canvas, label, r.center, ACCENT if sel else (TEXT if hov else DIM), 11, "center")

    def click(self, mouse) -> bool:
        for i, r in enumerate(self.rects):
            if _hit(r, mouse):
                press(r, sound=False)   # 탭 소리(ui_tab)는 부르는 쪽이
                self.index = i
                return True
        return False


def money_text(v: int) -> str:
    return f"{v:,}원"


def time_text(sec: float) -> str:
    sec = int(sec)
    h, m = sec // 3600, sec % 3600 // 60
    return f"{h}시간 {m:02d}분" if h else f"{m}분 {sec % 60:02d}초"


def bar(canvas, rect, frac: float, color) -> None:
    r = pygame.Rect(rect)
    canvas.fill((36, 40, 56), r)
    canvas.fill(color, (r.x, r.y, int(r.w * max(0.0, min(1.0, frac))), r.h))
    pygame.draw.rect(canvas, lerp_color(color, (0, 0, 0), 0.4), r, 1)
