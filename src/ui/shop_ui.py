"""상점 화면 그리기 도구 (SHOP_UI.md): 색 · 굵은 글자 · 동전 · 자물쇠 · 체크 · 찌 커서 · 배지 · 꽉 찬 버튼 · 작은 물고기."""
import pygame

from src.core.fonts import get_font
from src.platform.hints import localize
from src.ui.hud import SHADOW, text


def _h(s: str) -> tuple:
    s = s.lstrip("#")
    return tuple(int(s[i:i + 2], 16) for i in (0, 2, 4))


# 유지할 것 (현재 게임 값)
WIN_BG, CELL_BG, BORDER, SEL_BG = _h("#161C30"), _h("#101424"), _h("#5A6896"), _h("#222A44")
YELLOW, WHITE, RED, GRAY = _h("#FFDC78"), _h("#E8ECF5"), _h("#FF8C78"), _h("#8C94AA")
# 새로 쓰는 색
GREEN, MUT, SUB = _h("#7ED68A"), _h("#78C8FF"), _h("#6E7691")
RARITY = {"common": _h("#D8DDE6"), "uncommon": _h("#7ED68A"), "rare": _h("#6FB7FF"), "phantom": _h("#B48CF0"),
          "legend": _h("#FFDC78")}
RARITY_KO = {"common": "일반", "uncommon": "고급", "rare": "희귀", "phantom": "환상", "legend": "전설"}
PIC_BG, PIC_BORDER = _h("#161E36"), _h("#2E3A5C")
CYAN = (110, 230, 220)
DARK_TEXT = (40, 30, 10)


_BT: dict = {}


def btext(canvas, s: str, pos, color, size: int = 11, anchor: str = "topleft", shadow: bool = True) -> pygame.Rect:
    """굵은 글자 (픽셀 글꼴을 1px 옆으로 한 번 더). 그림자는 1px 오른쪽 아래."""
    key = (s, tuple(color), size)
    hit = _BT.get(key)   # 같은 글자 · 색 · 크기는 한 번만 그린다 (O2 — 상점 · 도감 목록의 굵은 글자가 매 프레임 render)
    if hit is None:
        if len(_BT) > 400:
            _BT.clear()
        t_ = localize(s)
        font = get_font(size)
        hit = _BT[key] = (font.render(t_, False, color), font.render(t_, False, SHADOW))
    img, sh = hit
    w, h = img.get_size()
    r = pygame.Rect(0, 0, w + 1, h)
    setattr(r, anchor, pos)
    if shadow:
        canvas.blit(sh, (r.x + 1, r.y + 1))
        canvas.blit(sh, (r.x + 2, r.y + 1))
    canvas.blit(img, r.topleft)
    canvas.blit(img, (r.x + 1, r.y))
    return r


def width(s: str, size: int = 11, bold: bool = False) -> int:
    return get_font(size).size(localize(s))[0] + (1 if bold else 0)


def fit(s: str, w: int, size: int = 11) -> str:
    """폭을 넘으면 뒤를 줄이고 '…'."""
    f = get_font(size)
    if f.size(s)[0] <= w:
        return s
    while len(s) > 1 and f.size(s + "…")[0] > w:
        s = s[:-1]
    return s + "…"


def coin(canvas, x: int, cy: int, big: bool = False) -> int:
    """작은 동전 (왼쪽 x, 세로 가운데 cy). 돌려주는 값 = 동전 오른쪽 끝 + 여백."""
    r = 3 if big else 2
    pygame.draw.circle(canvas, (150, 110, 30), (x + r + 1, cy + 1), r + 1)
    pygame.draw.circle(canvas, (255, 214, 90), (x + r, cy), r + 1)
    canvas.fill((200, 150, 40), (x + r, cy - (r - 1), 1, 2 * r - 1))
    return x + 2 * r + 5


def price(canvas, v: int, pos, color=WHITE, anchor: str = "midright", bold: bool = False, big: bool = False,
          prefix: str = "") -> pygame.Rect:
    """동전 + 가격 "6,000원". anchor 는 midright / midleft."""
    s = f"{prefix}{v:,}원"
    tw = width(s, 11, bold)
    cw = (7 if big else 5) + 3
    x, cy = pos
    if anchor == "midright":
        x -= tw + cw
    coin(canvas, x, cy, big)
    (btext if bold else text)(canvas, s, (x + cw, cy), color, 11, "midleft")
    return pygame.Rect(x, cy - 6, tw + cw, 12)


def lock(canvas, x: int, cy: int, col=GRAY) -> int:
    """작은 자물쇠 (5x7). 돌려주는 값 = 오른쪽 끝 + 여백."""
    pygame.draw.rect(canvas, col, (x + 1, cy - 4, 4, 4), 1)
    canvas.fill(col, (x, cy - 1, 6, 5))
    canvas.fill(CELL_BG, (x + 2, cy + 1, 2, 2))
    return x + 9


def check(canvas, x: int, cy: int, col=WHITE) -> int:
    pygame.draw.lines(canvas, col, False, [(x, cy), (x + 2, cy + 2), (x + 6, cy - 3)], 1)
    return x + 9


def bobber_cursor(canvas, x: int, cy: int) -> None:
    """선택 줄 왼쪽의 작은 찌 (위 흰 · 아래 빨강)."""
    canvas.fill((245, 245, 240), (x, cy - 3, 3, 3))
    canvas.fill((235, 70, 60), (x, cy, 3, 3))


def row_bg(canvas, r: pygame.Rect, sel: bool, hover: bool) -> None:
    if sel:
        canvas.fill(SEL_BG, r)
        pygame.draw.rect(canvas, YELLOW, r, 1)
        bobber_cursor(canvas, r.x + 3, r.centery)
    elif hover:
        canvas.fill(SEL_BG, r)


def badge(canvas, s: str, pos, col, anchor: str = "midright", fill=None, bold: bool = False) -> pygame.Rect:
    """테두리 배지 (글자 + 테두리 같은 색)."""
    tw = width(s, 11, bold)
    r = pygame.Rect(0, 0, tw + 6, 13)
    setattr(r, anchor, pos)
    if fill:
        canvas.fill(fill, r)
    pygame.draw.rect(canvas, col, r, 1)
    (btext if bold else text)(canvas, s, (r.x + 3, r.centery), DARK_TEXT if fill else col, 11, "midleft",
                              **({} if bold else {"shadow": not fill}))
    return r


def button(canvas, r: pygame.Rect, label: str, style: str, mouse) -> None:
    """style: fill(노랑 꽉 참) · outline(노랑 테두리) · dim(흐림, 못 누름)."""
    hov = r.collidepoint(mouse) and style != "dim"
    canvas.fill(SHADOW, r.move(1, 1))
    from src.ui.widgets import pressed_dy
    r = r.move(0, pressed_dy(r))   # 눌림 1px (DT10)
    if style == "fill":
        canvas.fill((255, 232, 150) if hov else YELLOW, r)
        btext(canvas, label, r.center, DARK_TEXT, 11, "center", shadow=False)
    elif style == "outline":
        canvas.fill(SEL_BG if hov else WIN_BG, r)
        pygame.draw.rect(canvas, YELLOW, r, 1)
        btext(canvas, label, r.center, YELLOW, 11, "center")
    else:
        canvas.fill(CELL_BG, r)
        pygame.draw.rect(canvas, (54, 62, 90), r, 1)
        text(canvas, label, r.center, SUB, 11, "center")


def fish_icon(canvas, x: int, cy: int, col) -> None:
    """작은 물고기 (14x7, 등급 색)."""
    pygame.draw.ellipse(canvas, col, (x + 3, cy - 3, 9, 7))
    pygame.draw.polygon(canvas, col, [(x + 3, cy), (x, cy - 3), (x, cy + 3)])
    canvas.fill((20, 22, 34), (x + 9, cy - 1, 1, 1))


def pic_box(canvas, r: pygame.Rect) -> None:
    canvas.fill(PIC_BG, r)
    pygame.draw.rect(canvas, PIC_BORDER, r, 1)


def chip(canvas, s: str, x: int, cy: int, col, on: bool) -> pygame.Rect:
    """필터 칩 (선택 = 색 배경)."""
    tw = width(s)
    r = pygame.Rect(x, cy - 6, tw + 4, 12)
    if on:
        canvas.fill(col, r)
        text(canvas, s, (r.x + 2, cy), DARK_TEXT, 11, "midleft", shadow=False)
    else:
        canvas.fill(CELL_BG, r)
        pygame.draw.rect(canvas, col, r, 1)
        text(canvas, s, (r.x + 2, cy), col, 11, "midleft")
    return r
