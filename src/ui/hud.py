"""HUD: 시계, 조작 안내, 파워 게이지, 둘러보기 화살표, 커서."""
import math

import pygame

from src.core.fonts import get_font
from src.core.mathutil import lerp_color, scale_color
from src.platform.hints import localize

SHADOW = (10, 12, 24)


def text(canvas, s: str, pos, color, size: int = 11, anchor: str = "topleft", shadow: bool | None = None) -> pygame.Rect:
    """shadow = None: 글자색이 밝으면 어두운 그림자, 어두운 글자(밝은 종이·말풍선 위)면 그림자 없음 — 검은 글자에 검은 그림자가
    겹치면 획이 뭉개져 읽기 힘들다."""
    img, sh = _rendered(s, color, size, shadow)
    rect = img.get_rect(**{anchor: pos})
    if sh is not None:
        canvas.blit(sh, rect.move(1, 1))
    canvas.blit(img, rect)
    return rect


_TXT: dict = {}


def _rendered(s: str, color, size: int, shadow):
    """(글자 그림, 그림자 그림 또는 None) — 같은 글자·색·크기는 한 번만 그린다 (폰에서 Font.render 가 프레임당 수 ms, DESIGN.md 44)."""
    key = (s, tuple(color), size, shadow)
    hit = _TXT.get(key)
    if hit is None:
        if len(_TXT) > 600:
            _TXT.clear()
        t = localize(s)  # 모바일이면 PC 조작 문구를 터치 문구로 (PC는 그대로)
        font = get_font(size)
        img = font.render(t, False, color)
        if shadow is None:
            shadow = 0.299 * color[0] + 0.587 * color[1] + 0.114 * color[2] >= 120
        hit = _TXT[key] = (img, font.render(t, False, SHADOW) if shadow else None)
    return hit


# ── 색 태그 글자: "{purple}물이 조용해지거든{/}, 줄을…" (대사 강조 — 환상 힌트 등) ──
TAG_RE = __import__("re").compile(r"\{(purple|gold|/)\}")
TAG_COLORS_DARK_BG = {"purple": (205, 150, 255), "gold": (255, 214, 110)}    # 어두운 대화창 위
TAG_COLORS_LIGHT_BG = {"purple": (120, 50, 190), "gold": (150, 100, 20)}     # 밝은 말풍선·종이 위


def strip_tags(s: str) -> str:
    return TAG_RE.sub("", s)


def wrap_rich(s: str, max_w: int, size: int = 11) -> list[str]:
    """wrap_text 와 같지만 색 태그는 폭에서 뺀다. 줄을 넘는 태그는 다음 줄 앞에 다시 열어 준다."""
    font = get_font(size)
    lines, cur = [], ""
    for word in localize(s).split(" "):
        cand = f"{cur} {word}".strip()
        if cur and font.size(strip_tags(cand))[0] > max_w:
            lines.append(cur)
            cur = word
        else:
            cur = cand
    if cur:
        lines.append(cur)
    out, open_tag = [], None
    for ln in lines:
        body = (f"{{{open_tag}}}" if open_tag else "") + ln
        for m in TAG_RE.finditer(ln):
            open_tag = None if m.group(1) == "/" else m.group(1)
        out.append(body)
    return out


def rich_text(canvas, s: str, pos, color, size: int = 11, anchor: str = "midleft", visible: int | None = None,
              tag_colors: dict | None = None) -> pygame.Rect:
    """색 태그가 섞인 한 줄. visible = 보이는 글자 수 (한 글자씩 출력, 태그 제외)."""
    tag_colors = tag_colors or TAG_COLORS_DARK_BG
    font = get_font(size)
    plain = strip_tags(s)
    rect = font.render(plain, False, color).get_rect(**{anchor: pos})
    x, cur, left = rect.x, color, (len(plain) if visible is None else visible)
    pieces = TAG_RE.split(s)   # 텍스트, 태그이름, 텍스트, …
    for i, part in enumerate(pieces):
        if i % 2 == 1:
            cur = color if part == "/" else tag_colors.get(part, color)
            continue
        if not part or left <= 0:
            continue
        seg = part[:left]
        left -= len(seg)
        r = text(canvas, seg, (x, rect.centery), cur, size, "midleft")
        x = r.right
    return rect


def wrap_text(s: str, max_w: int, size: int = 11) -> list[str]:
    """픽셀 폭 기준 줄바꿈 (공백 단위)."""
    s = localize(s)
    font = get_font(size)
    lines, cur = [], ""
    for word in s.split(" "):
        cand = f"{cur} {word}".strip()
        if cur and font.size(cand)[0] > max_w:
            lines.append(cur)
            cur = word
        else:
            cur = cand
    if cur:
        lines.append(cur)
    return lines


def draw_clock(canvas, pal, label: str, fast: bool, mult: int, x: int = 6) -> None:
    r = text(canvas, label, (x, 4), pal["text"])
    if fast:
        text(canvas, f"▶▶ ×{mult}", (r.right + 6, 4), (255, 220, 120))


def draw_hint(canvas, pal, s: str, center: bool = False) -> None:
    if center:  # 모바일: 왼쪽 아래는 터치 버튼 자리
        text(canvas, s, (canvas.get_width() // 2, canvas.get_height() - 6), pal["text"], anchor="midbottom")
        return
    text(canvas, s, (6, canvas.get_height() - 6), pal["text"], anchor="bottomleft")


def draw_power_gauge(canvas, pal, power: float, distance: float) -> None:
    x, y, w, h = canvas.get_width() - 28, 132, 8, 72  # 오른쪽 가장자리 기준 (PC 480 → 452)
    canvas.fill(SHADOW, (x - 1, y - 1, w + 2, h + 2))
    canvas.fill((40, 44, 60), (x, y, w, h))
    fill = int(h * power)
    low, high = (120, 200, 255), (255, 230, 90)
    for i in range(fill):
        canvas.fill(lerp_color(low, high, i / h), (x, y + h - 1 - i, w, 1))
    # 최대 파워 눈금
    canvas.fill((255, 255, 255), (x - 2, y, w + 4, 1))
    text(canvas, f"{distance:.0f}m", (x + w // 2, y - 3), pal["text"], anchor="midbottom")


def draw_look_arrows(canvas, pal, left: bool, right: bool, t: float, right_inset: int = 0) -> None:
    h = canvas.get_height()
    cy = h // 2 - 20
    blink = int(t * 4) % 2 == 0
    color = pal["text"] if blink else scale_color(pal["text"], 0.7)
    if left:
        pygame.draw.polygon(canvas, color, [(4, cy), (11, cy - 6), (11, cy + 6)])
    if right:
        w = canvas.get_width() - right_inset
        pygame.draw.polygon(canvas, color, [(w - 5, cy), (w - 12, cy - 6), (w - 12, cy + 6)])


SHOW_CURSOR = True  # 터치 기기에선 Game이 끈다 (손가락이 커서)


def draw_cursor(canvas, pos) -> None:
    if not SHOW_CURSOR:
        return
    x, y = pos
    for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
        canvas.fill(SHADOW, (x - 3 + dx, y + dy, 7, 1))
        canvas.fill(SHADOW, (x + dx, y - 3 + dy, 1, 7))
    canvas.fill((255, 255, 255), (x - 3, y, 7, 1))
    canvas.fill((255, 255, 255), (x, y - 3, 1, 7))


class Toasts:
    """화면 위쪽 가운데 알림 메시지 (서서히 사라짐)."""

    def __init__(self):
        self.items: list[dict] = []
        self.sink = None  # 파이팅 중: 6글자 이하만 이 함수로(글자 슬롯 하나), 문장은 버린다 (31장)

    def show(self, s: str, color=(255, 255, 255), duration: float = 2.0, size: int = 16) -> None:
        if self.sink is not None and not s.startswith("[테스트]"):
            if len(s) <= 6:
                self.sink(s, color)
            return
        self.items = [{"text": s, "color": color, "life": duration, "dur": duration, "size": size}]

    def update(self, dt: float) -> None:
        for it in self.items:
            it["life"] -= dt
        self.items = [it for it in self.items if it["life"] > 0]

    def draw(self, canvas, max_w: int | None = None) -> None:
        """max_w: 이 폭을 넘으면 여러 줄로 (파이팅 중엔 왼쪽 게이지·오른쪽 의뢰 사이 가운데 칸에 맞춘다)."""
        for it in self.items:
            age = it["dur"] - it["life"]
            # 처음 0.15초 위에서 툭 떨어지며 등장
            dy = -6 * max(0.0, 1 - age / 0.15)
            if it["life"] < 0.4 and int(it["life"] * 20) % 2 == 0:
                continue
            lines = [it["text"]]
            if max_w and get_font(it["size"]).size(localize(it["text"]))[0] > max_w:
                lines = wrap_text(it["text"], max_w, it["size"])
            lh = it["size"] + 2
            # 여러 줄이면 위로 쌓는다 (아래 패턴 안내 패널(69~)을 가리지 않게, 마지막 줄 62)
            y = 58 + dy if len(lines) == 1 else 62 + dy - (len(lines) - 1) * lh
            for ln in lines:
                text(canvas, ln, (canvas.get_width() // 2, int(y)), it["color"], it["size"], "center")
                y += lh


def draw_catch_card(canvas, pal, fish_name: str, size_cm: float, rarity: str, t: float) -> None:
    """임시 획득 카드 (Phase 3에서 두 손으로 드는 컷으로 교체)."""
    w, h = 190, 84
    x = (canvas.get_width() - w) // 2
    y = 74
    rarity_color = {"common": (220, 220, 220), "uncommon": (120, 220, 140),
                    "rare": (120, 180, 255), "legend": (255, 210, 90)}.get(rarity, (255, 255, 255))
    rarity_name = {"common": "일반", "uncommon": "고급", "rare": "희귀", "legend": "전설"}.get(rarity, "")
    canvas.fill(SHADOW, (x + 2, y + 2, w, h))
    canvas.fill((28, 34, 56), (x, y, w, h))
    pygame.draw.rect(canvas, rarity_color, (x, y, w, h), 1)
    cx = x + w // 2
    text(canvas, "획득!", (cx, y + 13), (255, 230, 120), 16, "center")
    text(canvas, fish_name, (cx, y + 36), (255, 255, 255), 16, "center")
    text(canvas, f"{size_cm:.1f}cm  ·  {rarity_name}", (cx, y + 56), rarity_color, 11, "center")
    if int(t * 2) % 2 == 0:
        text(canvas, "클릭해서 계속", (cx, y + 73), (170, 180, 200), 11, "center")


def draw_blessing(canvas, x: int, y: int, left_sec: float | None, t: float) -> None:
    """물결의 축복 (환상 보상): 작은 보라 물결 아이콘 + 남은 시간 (파이팅 중엔 left_sec=None → 아이콘만)."""
    col = (200, 150, 255)
    k = 0.6 + 0.4 * math.sin(t * 2.5)
    pygame.draw.circle(canvas, (30, 16, 52), (x, y), 6)
    pygame.draw.circle(canvas, col, (x, y), 6, 1)
    for i, r in enumerate((2, 4)):
        pygame.draw.arc(canvas, lerp_color((90, 60, 140), (235, 210, 255), k if i else 1 - k),
                        (x - r, y - r + 1, r * 2, r * 2), 0.3, 2.8, 1)
    if left_sec is not None:
        m, sec = divmod(int(left_sec), 60)
        text(canvas, f"축복 {m}:{sec:02d}", (x + 9, y), col, 11, "midleft")
