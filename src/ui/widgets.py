"""메뉴·상점·도감 공통 UI 부품 (버튼, 패널, 탭)."""
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


def panel(canvas, rect, border=BORDER, fill=PANEL) -> None:
    r = pygame.Rect(rect)
    canvas.fill(SHADOW, r.move(2, 2))
    canvas.fill(fill, r)
    pygame.draw.rect(canvas, border, r, 1)


def dim(canvas, alpha: int = 150) -> None:
    s = pygame.Surface(canvas.get_size(), pygame.SRCALPHA)
    s.fill((6, 8, 20, alpha))
    canvas.blit(s, (0, 0))


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
        canvas.fill(SHADOW, self.rect.move(1, 1))
        canvas.fill(fill, self.rect)
        pygame.draw.rect(canvas, border, self.rect, 1)
        col = (TEXT if not hov else self.accent) if self.enabled else DIM
        text(canvas, self.label, self.rect.center, col, self.size, "center")

    def click(self, mouse) -> bool:
        if self.enabled and _hit(self.rect, mouse) and self.action:
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
            canvas.fill(PANEL_LIGHT if sel else PANEL, r)
            pygame.draw.rect(canvas, ACCENT if sel else (BORDER if not hov else TEXT), r, 1)
            text(canvas, label, r.center, ACCENT if sel else (TEXT if hov else DIM), 11, "center")

    def click(self, mouse) -> bool:
        for i, r in enumerate(self.rects):
            if _hit(r, mouse):
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
