"""낚시 화면 오른쪽 가장자리 메뉴 버튼 (PC): 인벤토리·지도·상점·의뢰·수집·보물상자·도움말·설정.
'수집'을 누르면 그 왼쪽으로 서랍이 열려 도감·업적(트로피)·어탁·수조(훈련 수조)가 나온다 (오른쪽 줄이 꽉 차서 묶음, v1.1).

단축키(I·M·B·J·Tab·C·H·Esc)는 그대로 — 버튼은 그림 아이콘, 마우스를 올리면 '이름 (키)' 말풍선.
파이팅 중·던지는 중엔 숨긴다. 보물상자는 가진 개수 점, 의뢰는 받을 보상이 있으면 느낌표.
모바일은 원래대로 '가방' 버튼 하나 (src/scene/quick_menu.py).
"""
import math

import pygame

from src.ui.hud import SHADOW, text

ITEMS = (("inventory", "인벤토리", "I"), ("map", "지도", "M"), ("shop", "상점", "B"), ("quests", "의뢰", "J"),
         ("collection", "수집", ""), ("chest", "보물상자", "C"), ("help", "도움말", "H"), ("settings", "설정", "Esc"))
DRAWER = (("dex", "도감", "Tab"), ("achievements", "업적", "U"), ("prints", "어탁", ""), ("tank", "수조", ""))
SIZE = 22
GAP = 4
BG = (14, 18, 34)
EDGE = (120, 130, 160)
HOVER = (255, 214, 90)
ICON = (236, 240, 248)


def layout(w: int, h: int, inset: int = 0) -> list[tuple[str, pygame.Rect]]:
    x = w - 6 - inset - SIZE
    total = len(ITEMS) * SIZE + (len(ITEMS) - 1) * GAP
    y0 = max(58, (h - total) // 2 + 10)
    return [(k, pygame.Rect(x, y0 + i * (SIZE + GAP), SIZE, SIZE)) for i, (k, _, _) in enumerate(ITEMS)]


def drawer_layout(rects) -> list[tuple[str, pygame.Rect]]:
    """수집 버튼 왼쪽으로 펼쳐지는 서랍 (가까운 것부터 도감 → 업적 → 어탁 → 수조)."""
    r = dict(rects).get("collection")
    if r is None:
        return []
    return [(k, pygame.Rect(r.x - (i + 1) * (SIZE + GAP) - 4, r.y, SIZE, SIZE)) for i, (k, _, _) in enumerate(DRAWER)]


def hit(rects, pos) -> str | None:
    for k, r in rects:
        if r.collidepoint(pos):
            return k
    return None


def draw(canvas, rects, mouse, t: float, badges: dict | None = None, drawer: float = 0.0) -> None:
    """drawer = 수집 서랍 열림 정도 0~1 (왼쪽으로 미끄러져 나옴)."""
    badges = badges or {}
    hov = hit(rects, mouse)
    if drawer > 0:
        _draw_drawer(canvas, rects, mouse, t, drawer, badges)
    for k, r in rects:
        on = k == hov or (k == "collection" and drawer > 0.5)
        back = pygame.Surface(r.size, pygame.SRCALPHA)
        pygame.draw.rect(back, (*BG, 225 if on else 170), back.get_rect(), border_radius=5)
        canvas.blit(back, r.topleft)
        pygame.draw.rect(canvas, HOVER if on else EDGE, r, 1, border_radius=5)
        col = HOVER if on else ICON
        cx, cy = r.center
        if on:
            cy -= 1  # 살짝 떠오름
        ICONS[k](canvas, cx, cy, col, t)
        b = badges.get(k)
        if b:
            bx, by = r.right - 3, r.top + 3
            pygame.draw.circle(canvas, SHADOW, (bx + 1, by + 1), 4)
            pygame.draw.circle(canvas, (255, 90, 80), (bx, by), 4)
            if b == "!":
                canvas.fill((255, 255, 255), (bx, by - 2, 1, 3))
                canvas.fill((255, 255, 255), (bx, by + 2, 1, 1))
            elif isinstance(b, int) and b < 10:
                text(canvas, str(b), (bx, by), (255, 255, 255), 11, "center")
    if hov:
        _, label, key = next(it for it in ITEMS if it[0] == hov)
        r = dict(rects)[hov]
        s = f"{label} ({key})" if key else label
        from src.core.fonts import get_font
        tw = get_font(11).size(s)[0] + 10
        tip = pygame.Rect(r.left - 6 - tw, r.centery - 7, tw, 14)
        canvas.fill(SHADOW, tip.move(1, 1))
        canvas.fill(BG, tip)
        pygame.draw.rect(canvas, HOVER, tip, 1)
        text(canvas, s, tip.center, ICON, 11, "center")


def _draw_drawer(canvas, rects, mouse, t, k: float, badges) -> None:
    items = drawer_layout(rects)
    if not items:
        return
    ease = 1 - (1 - min(1.0, k)) ** 3
    r0 = dict(rects)["collection"]
    full = pygame.Rect(items[-1][1].x - 4, r0.y - 4, r0.x - items[-1][1].x + 4, SIZE + 8)
    vis_w = int(full.w * ease)
    clip = pygame.Rect(full.right - vis_w, full.y, vis_w, full.h)
    back = pygame.Surface(clip.size, pygame.SRCALPHA)
    pygame.draw.rect(back, (*BG, 200), back.get_rect(), border_radius=6)
    canvas.blit(back, clip.topleft)
    pygame.draw.rect(canvas, EDGE, clip, 1, border_radius=6)
    old = canvas.get_clip()
    canvas.set_clip(clip)
    hov = hit(items, mouse) if ease > 0.9 else None
    off = full.w - vis_w
    for key, r in items:
        r = r.move(off, 0)
        on = key == hov
        pygame.draw.rect(canvas, HOVER if on else EDGE, r, 1, border_radius=5)
        ICONS[key](canvas, r.centerx, r.centery - (1 if on else 0), HOVER if on else ICON, t)
        b = badges.get(key)
        if b:
            pygame.draw.circle(canvas, (255, 90, 80), (r.right - 3, r.top + 3), 3)
    canvas.set_clip(old)
    if hov:
        _, label, key = next(it for it in DRAWER if it[0] == hov)
        r = dict(items)[hov]
        s = f"{label} ({key})" if key else label
        from src.core.fonts import get_font
        tw = get_font(11).size(s)[0] + 10
        tip = pygame.Rect(r.centerx - tw // 2, r.y - 18, tw, 14)
        canvas.fill(SHADOW, tip.move(1, 1))
        canvas.fill(BG, tip)
        pygame.draw.rect(canvas, HOVER, tip, 1)
        text(canvas, s, tip.center, ICON, 11, "center")


# ───────────────────────── 아이콘 (12×12 안쪽, 픽셀 느낌) ─────────────────────────

def _map(c, x, y, col, t):
    """접힌 지도 + 빨간 핀."""
    pts = [(x - 7, y - 4), (x - 3, y - 6), (x + 2, y - 4), (x + 7, y - 6), (x + 7, y + 4), (x + 2, y + 6),
           (x - 3, y + 4), (x - 7, y + 6)]
    pygame.draw.polygon(c, (60, 110, 90), pts)
    pygame.draw.polygon(c, col, pts, 1)
    pygame.draw.line(c, col, (x - 3, y - 6), (x - 3, y + 4), 1)
    pygame.draw.line(c, col, (x + 2, y - 4), (x + 2, y + 6), 1)
    bob = int(math.sin(t * 4) * 1)
    pygame.draw.circle(c, (255, 90, 80), (x + 4, y - 2 + bob), 2)
    c.fill((255, 90, 80), (x + 4, y + bob, 1, 3))


def _shop(c, x, y, col, t):
    """가게: 줄무늬 차양 + 진열대."""
    for i in range(4):
        c.fill((255, 110, 90) if i % 2 == 0 else (250, 240, 230), (x - 8 + i * 4, y - 6, 4, 4))
    pygame.draw.polygon(c, col, [(x - 8, y - 2), (x + 8, y - 2), (x + 8, y - 1), (x - 8, y - 1)])
    pygame.draw.rect(c, col, (x - 7, y - 1, 14, 8), 1)
    c.fill((255, 214, 90), (x - 2, y + 2, 4, 5))  # 문
    pygame.draw.circle(c, (255, 214, 90), (x + 5, y + 2), 1)


def _quests(c, x, y, col, t):
    """두루마리 + 느낌표."""
    c.fill((235, 220, 180), (x - 5, y - 6, 10, 13))
    pygame.draw.rect(c, (150, 120, 80), (x - 6, y - 7, 12, 2))
    pygame.draw.rect(c, (150, 120, 80), (x - 6, y + 6, 12, 2))
    for i in range(3):
        c.fill((150, 130, 100), (x - 3, y - 3 + i * 3, 6, 1))
    pygame.draw.rect(c, col, (x - 6, y - 7, 12, 15), 1)


def _dex(c, x, y, col, t):
    """책 + 물고기."""
    c.fill((70, 90, 150), (x - 7, y - 6, 14, 12))
    pygame.draw.rect(c, col, (x - 7, y - 6, 14, 12), 1)
    c.fill(col, (x, y - 6, 1, 12))
    # 오른쪽 면에 작은 물고기
    pygame.draw.ellipse(c, (130, 220, 255), (x + 1, y - 2, 5, 3))
    pygame.draw.polygon(c, (130, 220, 255), [(x + 6, y - 1), (x + 8, y - 3), (x + 8, y + 1)])
    for i in range(3):
        c.fill((200, 210, 235), (x - 5, y - 3 + i * 3, 4, 1))


def _chest(c, x, y, col, t):
    """보물상자 (뚜껑 반짝)."""
    c.fill((140, 90, 50), (x - 7, y - 2, 14, 8))
    pygame.draw.ellipse(c, (170, 110, 60), (x - 7, y - 7, 14, 9))
    c.fill((140, 90, 50), (x - 7, y - 3, 14, 2))
    pygame.draw.rect(c, col, (x - 7, y - 3, 14, 9), 1)
    c.fill((255, 214, 90), (x - 1, y - 2, 3, 4))
    if int(t * 2) % 3 == 0:
        c.fill((255, 255, 255), (x + 4, y - 7, 1, 1))


def _inventory(c, x, y, col, t):
    """배낭 (위 고리 + 둥근 몸통 + 덮개 + 앞주머니) — 보물상자 아이콘과 헷갈리지 않게 청록."""
    pygame.draw.arc(c, col, (x - 3, y - 9, 6, 5), 0, math.pi, 1)
    pygame.draw.rect(c, (60, 128, 140), (x - 6, y - 6, 12, 13), border_radius=4)
    pygame.draw.rect(c, (84, 160, 170), (x - 6, y - 6, 12, 6), border_top_left_radius=4, border_top_right_radius=4)
    pygame.draw.rect(c, col, (x - 6, y - 6, 12, 13), 1, border_radius=4)
    pygame.draw.rect(c, (40, 92, 104), (x - 3, y + 1, 6, 5), border_radius=1)
    c.fill((255, 214, 90), (x - 1, y - 1, 2, 2))


def _help(c, x, y, col, t):
    """물음표 원."""
    pygame.draw.circle(c, (60, 110, 180), (x, y), 7)
    pygame.draw.circle(c, col, (x, y), 7, 1)
    pygame.draw.arc(c, (255, 255, 255), (x - 3, y - 5, 6, 6), -math.pi * 0.5, math.pi, 2)
    c.fill((255, 255, 255), (x, y, 2, 2))
    c.fill((255, 255, 255), (x, y + 3, 2, 2))


def _settings(c, x, y, col, t):
    """톱니바퀴 (천천히 돎)."""
    for i in range(8):
        a = i / 8 * math.tau + t * 0.6
        px, py = x + math.cos(a) * 6, y + math.sin(a) * 6
        c.fill(col, (int(px) - 1, int(py) - 1, 3, 3))
    pygame.draw.circle(c, col, (x, y), 5)
    pygame.draw.circle(c, BG, (x, y), 2)


def trophy(c, x, y, col, t, gold=(255, 204, 70), dark=(176, 124, 30)):
    """트로피 (업적): 손잡이 달린 컵 + 받침. 다른 화면(업적·알림)도 이 그림을 쓴다."""
    pygame.draw.polygon(c, gold, [(x - 5, y - 6), (x + 5, y - 6), (x + 4, y - 1), (x + 1, y + 1), (x - 1, y + 1), (x - 4, y - 1)])
    pygame.draw.arc(c, gold, (x - 8, y - 6, 5, 6), math.pi * 0.5, math.pi * 1.5, 1)
    pygame.draw.arc(c, gold, (x + 3, y - 6, 5, 6), -math.pi * 0.5, math.pi * 0.5, 1)
    c.fill(gold, (x - 1, y + 1, 2, 3))
    c.fill(dark, (x - 4, y + 4, 8, 2))
    c.fill(col, (x - 3, y - 5, 1, 3))   # 반짝
    if int(t * 2) % 4 == 0:
        c.fill((255, 255, 255), (x + 2, y - 5, 1, 1))


def _achievements(c, x, y, col, t):
    trophy(c, x, y, col, t)


def _collection(c, x, y, col, t):
    """수집: 별이 달린 보관함 (서랍)."""
    c.fill((96, 70, 140), (x - 7, y - 3, 14, 9))
    pygame.draw.rect(c, col, (x - 7, y - 3, 14, 9), 1)
    c.fill(col, (x - 2, y + 1, 4, 1))
    for dx, dy in ((0, -8), (0, -4), (-2, -6), (2, -6), (0, -6)):   # 별
        c.fill((255, 214, 90), (x + dx, y + dy, 1, 1))
    c.fill((255, 214, 90), (x - 1, y - 7, 3, 3))


def _prints(c, x, y, col, t):
    """어탁: 종이 위 먹 물고기 + 빨간 도장."""
    c.fill((236, 226, 200), (x - 7, y - 6, 14, 12))
    pygame.draw.rect(c, col, (x - 7, y - 6, 14, 12), 1)
    pygame.draw.ellipse(c, (40, 36, 34), (x - 5, y - 2, 7, 4))
    pygame.draw.polygon(c, (40, 36, 34), [(x + 2, y), (x + 5, y - 2), (x + 5, y + 2)])
    c.fill((200, 60, 50), (x + 3, y + 3, 2, 2))


def _tank(c, x, y, col, t):
    """수조: 유리 상자 + 물 + 헤엄치는 물고기."""
    c.fill((50, 110, 160), (x - 7, y - 3, 14, 9))
    pygame.draw.rect(c, col, (x - 7, y - 6, 14, 12), 1)
    fx = x - 3 + int((t * 4) % 6)
    pygame.draw.ellipse(c, (255, 170, 80), (fx - 2, y, 5, 3))
    c.fill((255, 170, 80), (fx - 4, y + 1, 2, 1))
    if int(t * 3) % 2:
        c.fill((200, 230, 255), (x + 4, y - 2, 1, 1))


ICONS = {"inventory": _inventory, "map": _map, "shop": _shop, "quests": _quests, "dex": _dex, "chest": _chest, "help": _help,
         "settings": _settings, "collection": _collection, "achievements": _achievements, "prints": _prints, "tank": _tank}
