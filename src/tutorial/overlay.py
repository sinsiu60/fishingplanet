"""가이드 그리기 (TUTORIAL.md 1·2번): 어둡게 + 강조 구멍 · 안내 상자 · 조작 그림 · 건너뛰기 · 확인 창 · '좋아요!'."""
import math

import pygame

from src.core.fonts import get_font
from src.ui import hud

DIM_ALPHA = 178            # 검정 70%
YELLOW = (255, 220, 120)   # #FFDC78
BOX_BG = (16, 20, 36)      # #101424
TEXT = (235, 238, 248)
FACE = 40
LINE_H = 14

_dim_cache: dict = {}
_faces: dict = {}


def _blink(t: float) -> float:
    return 0.5 + 0.5 * math.sin(t * math.tau / 1.6)   # 천천히 (1.6초 주기)


def dim(canvas, rects, t: float, strong: bool = True) -> None:
    size = canvas.get_size()
    sh = _dim_cache.get(size)
    if sh is None:
        sh = _dim_cache[size] = pygame.Surface(size, pygame.SRCALPHA)
    sh.fill((0, 0, 0, DIM_ALPHA))
    holes = [r.inflate(6, 6) for r in rects]
    for r in holes:
        sh.fill((0, 0, 0, 0), r)
    canvas.blit(sh, (0, 0))
    k = _blink(t)
    col = tuple(int(c * (0.45 + 0.55 * k)) for c in YELLOW)
    for r in holes:
        pygame.draw.rect(canvas, col, r, 1, border_radius=3)


def face(who: str, expr: str) -> pygame.Surface | None:
    key = (who, expr)
    if key in _faces:
        return _faces[key]
    from src.core.paths import asset_path
    img = None
    for e in (expr, "neutral", "happy"):
        try:
            raw = pygame.image.load(str(asset_path("portraits", f"npc_{who}_{e}.png")))
            img = raw.subsurface((12, 4, FACE, FACE)).copy()   # 64x64 초상화의 얼굴 부분
            break
        except (pygame.error, FileNotFoundError, ValueError):
            continue
    _faces[key] = img
    return img


def _union(rects):
    if not rects:
        return None
    u = rects[0].copy()
    for r in rects[1:]:
        u.union_ip(r)
    return u


def box(canvas, text: str, who: str, expr: str, rects, kind: str, t: float, small: bool = False,
        more: bool = False) -> pygame.Rect:
    """안내 상자: 얼굴 40x40 + 최대 2줄 (폭 220~400 자동) + 강조 쪽 화살표 + 강조를 가리지 않는 쪽에 자동 배치."""
    W, H = canvas.get_size()
    size = 11
    fs = 24 if small else FACE
    lines = []
    for w in (220, 300, 400):
        lines = hud.wrap_rich(text, w - fs - 16, size)
        if len(lines) <= 2:
            break
    lines = lines[:2] if len(lines) <= 2 else lines[:2]
    font = get_font(size)
    tw = max(font.size(hud.strip_tags(ln))[0] for ln in lines) if lines else 0
    bw = max(160 if small else 220, min(W - 16, tw + fs + 18 + (10 if more else 0)))
    bh = max(fs + 4, len(lines) * LINE_H + 10)
    u = _union(rects)
    gap = 12
    if small:
        x, y = (W - bw) // 2, 32
        if u is not None and pygame.Rect(x, y, bw, bh).colliderect(u):
            y = min(H - bh - 6, u.bottom + gap)
    elif u is None:
        x, y = (W - bw) // 2, H - bh - 44
    else:
        x = max(6, min(W - bw - 6, u.centerx - bw // 2))
        below = u.bottom + gap
        above = u.top - gap - bh
        if below + bh <= H - 6 and (above < 6 or u.centery < H * 0.55):
            y = below
        elif above >= 6:
            y = above
        else:   # 위아래 모두 자리가 없으면 옆으로
            y = max(6, min(H - bh - 6, u.centery - bh // 2))
            x = u.right + gap if u.right + gap + bw <= W - 6 else max(6, u.left - gap - bw)
    r = pygame.Rect(x, y, bw, bh)
    canvas.fill(BOX_BG, r)
    pygame.draw.rect(canvas, YELLOW, r, 1)
    f = face(who, expr)
    if f is not None:
        img = f if fs == FACE else pygame.transform.scale(f, (fs, fs))
        canvas.blit(img, (r.x + 2, r.y + (bh - fs) // 2))
    tx = r.x + fs + 8
    y0 = r.centery - (len(lines) - 1) * LINE_H // 2
    for i, ln in enumerate(lines):
        hud.rich_text(canvas, ln, (tx, y0 + i * LINE_H), TEXT, size, "midleft")
    if more and int(t * 2.5) % 2 == 0:
        hud.text(canvas, "▼", (r.right - 4, r.bottom - 2), YELLOW, 11, "bottomright")
    if u is not None:
        _arrow(canvas, r, u)
    return r


def _arrow(canvas, r: pygame.Rect, u: pygame.Rect) -> None:
    if r.colliderect(u):
        return
    if u.bottom <= r.top:
        cx = max(r.x + 8, min(r.right - 8, u.centerx))
        pts = [(cx - 5, r.top), (cx + 5, r.top), (cx, r.top - 6)]
    elif u.top >= r.bottom:
        cx = max(r.x + 8, min(r.right - 8, u.centerx))
        pts = [(cx - 5, r.bottom - 1), (cx + 5, r.bottom - 1), (cx, r.bottom + 5)]
    elif u.right <= r.left:
        cy = max(r.y + 6, min(r.bottom - 6, u.centery))
        pts = [(r.left, cy - 5), (r.left, cy + 5), (r.left - 6, cy)]
    else:
        cy = max(r.y + 6, min(r.bottom - 6, u.centery))
        pts = [(r.right - 1, cy - 5), (r.right - 1, cy + 5), (r.right + 5, cy)]
    pygame.draw.polygon(canvas, BOX_BG, pts)
    pygame.draw.lines(canvas, YELLOW, False, [pts[0], pts[2], pts[1]])


# ── 조작 그림 ──
def _mouse(canvas, x, y, left: bool, right: bool, glow: float = 0.0) -> None:
    body = pygame.Rect(x - 6, y - 8, 12, 17)
    pygame.draw.rect(canvas, (20, 22, 34), body.inflate(2, 2), border_radius=5)
    pygame.draw.rect(canvas, (230, 232, 240), body, border_radius=5)
    if left:
        pygame.draw.rect(canvas, YELLOW, (body.x + 1, body.y + 1, 5, 6), border_top_left_radius=4)
    if right:
        pygame.draw.rect(canvas, YELLOW, (body.centerx + 1, body.y + 1, 5, 6), border_top_right_radius=4)
    canvas.fill((60, 64, 80), (body.centerx, body.y + 1, 1, 6))
    canvas.fill((60, 64, 80), (body.x + 1, body.y + 7, body.w - 2, 1))


def _finger(canvas, x, y, down: bool) -> None:
    dy = 2 if down else 0
    pygame.draw.circle(canvas, (20, 22, 34), (x, y + dy), 6)
    pygame.draw.circle(canvas, (248, 222, 196), (x, y + dy), 5)
    pygame.draw.rect(canvas, (248, 222, 196), (x - 4, y + dy, 8, 12))
    pygame.draw.rect(canvas, (20, 22, 34), (x - 5, y + dy, 10, 13), 1)
    if down:
        pygame.draw.circle(canvas, YELLOW, (x, y - 4), 9, 1)


def _key(canvas, x, y, label: str, down: bool) -> None:
    w = max(16, get_font(11).size(label)[0] + 8)
    r = pygame.Rect(x - w // 2, y - 8 + (2 if down else 0), w, 15)
    canvas.fill((20, 22, 34), r.move(0, 2) if not down else r.inflate(2, 2))
    canvas.fill(YELLOW if down else (230, 232, 240), r)
    hud.text(canvas, label, r.center, (20, 22, 34), 11, "center", shadow=False)


def _dir_arrow(canvas, x, y, dx, dy, k: float) -> None:
    ex, ey = x + dx * 16, y + dy * 16
    pygame.draw.line(canvas, YELLOW, (x, y), (ex, ey), 2)
    px, py = -dy, dx
    pygame.draw.polygon(canvas, YELLOW, [(ex + dx * 4, ey + dy * 4), (ex + px * 4, ey + py * 4), (ex - px * 4, ey - py * 4)])


SWIPE = {"swipe_l": (-1, 0), "swipe_r": (1, 0), "swipe_u": (0, -1), "swipe_d": (0, 1)}
KEYS = {"key_q": "Q", "key_e": "E", "key_shift": "Shift"}


def input_anim(canvas, how: str, pos, t: float, touch: bool, nudge: float = 0.0) -> None:
    """PC = 마우스 그림 (버튼 눌림·움직임 화살표), 모바일 = 손가락 그림 (탭·누르기·스와이프·원)."""
    x, y = int(pos[0]), int(pos[1])
    if nudge > 0:   # 틀린 조작: 한 번 더 강조 (노란 고리가 크게 퍼짐)
        k = 1 - nudge / 0.8
        pygame.draw.circle(canvas, YELLOW, (x, y), int(10 + 18 * k), 2)
    ph = (t % 1.0)
    if how in KEYS and not touch:
        _key(canvas, x, y, KEYS[how], ph < 0.45 if how != "key_shift" else True)
        return
    if how in SWIPE:
        dx, dy = SWIPE[how]
        k = (t % 1.2) / 1.2
        ox, oy = int(dx * 18 * k) - dx * 8, int(dy * 18 * k) - dy * 8
        _dir_arrow(canvas, x + dx * 14, y + dy * 14, dx, dy, k)
        if touch:
            _finger(canvas, x + ox, y + oy, True)
        else:
            _mouse(canvas, x + ox, y + oy, False, False)
        return
    if how == "circle":
        a = t * math.tau / 1.2
        cx, cy = x + int(math.cos(a) * 12), y + int(math.sin(a) * 12)
        pygame.draw.circle(canvas, YELLOW, (x, y), 12, 1)
        (_finger(canvas, cx, cy, True) if touch else _mouse(canvas, cx, cy, False, False))
        return
    if how == "mash":
        down = (t * 6) % 1.0 < 0.5
    elif how == "hold":
        down = True
        r = int(8 + 6 * ph)
        pygame.draw.circle(canvas, YELLOW, (x, y), r, 1)
    elif how == "release":
        down = ph < 0.4
        if not down:
            _dir_arrow(canvas, x + 12, y + 4, 0, -1, ph)
    else:   # tap · right · 터치의 버튼 누르기
        down = ph < 0.35
    if touch:
        _finger(canvas, x, y, down)
    else:
        _mouse(canvas, x, y, down and how != "right", down and how == "right")


def skip_button(canvas, rect: pygame.Rect, pointer) -> None:
    hov = rect.collidepoint(pointer)
    canvas.fill((10, 12, 22), rect)
    pygame.draw.rect(canvas, YELLOW if hov else (120, 124, 140), rect, 1)
    hud.text(canvas, "건너뛰기", rect.center, YELLOW if hov else (200, 204, 216), 11, "center")


def modal(canvas, box_r: pygame.Rect, b_skip: pygame.Rect, b_cont: pygame.Rect) -> None:
    sh = pygame.Surface(canvas.get_size(), pygame.SRCALPHA)
    sh.fill((0, 0, 0, 120))
    canvas.blit(sh, (0, 0))
    canvas.fill(BOX_BG, box_r)
    pygame.draw.rect(canvas, YELLOW, box_r, 1)
    hud.text(canvas, "이 튜토리얼을 건너뛸까요?", (box_r.centerx, box_r.y + 18), TEXT, 11, "center")
    for r, label in ((b_skip, "건너뛰기"), (b_cont, "계속하기")):
        canvas.fill((34, 40, 64), r)
        pygame.draw.rect(canvas, YELLOW, r, 1)
        hud.text(canvas, label, r.center, TEXT, 11, "center")


def ok_banner(canvas, text: str, k: float) -> None:
    """정지 지시 성공: 위쪽에 '좋아요!' 1초 (k = 남은 비율)."""
    W = canvas.get_width()
    img = get_font(16).render(text, False, YELLOW)
    sh = get_font(16).render(text, False, (20, 16, 6))
    a = int(255 * min(1.0, k * 3))
    img.set_alpha(a)
    sh.set_alpha(a)
    y = 72 - int((1 - k) * 6)
    canvas.blit(sh, (W // 2 - img.get_width() // 2 + 1, y + 1))
    canvas.blit(img, (W // 2 - img.get_width() // 2, y))


def badge(canvas, text: str, pos) -> None:
    """작은 표시 (연타 0/6 · 참는 중… · 이중 패턴 조작 이름)."""
    font = get_font(11)
    w = font.size(hud.strip_tags(text))[0] + 10
    r = pygame.Rect(0, 0, w, 15)
    r.center = (int(pos[0]), int(pos[1]))
    r.clamp_ip(canvas.get_rect())
    canvas.fill(BOX_BG, r)
    pygame.draw.rect(canvas, YELLOW, r, 1)
    hud.text(canvas, text, r.center, YELLOW, 11, "center")


def progress_ring(canvas, pos, k: float) -> None:
    """원 그리기 진행 (0~1)."""
    x, y = int(pos[0]), int(pos[1])
    rect = pygame.Rect(x - 18, y - 18, 36, 36)
    pygame.draw.circle(canvas, (60, 64, 80), (x, y), 18, 2)
    if k > 0.01:
        pygame.draw.arc(canvas, YELLOW, rect, math.pi / 2 - k * math.tau, math.pi / 2, 3)
