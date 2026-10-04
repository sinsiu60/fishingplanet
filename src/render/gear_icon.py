"""상점 장비 그림 (SHOP_UI.md: 목록 14x14 · 상세 64x64). 코드로 그린 픽셀 그림 — 색은 data/gear_looks.json 티어 외형.

draw(canvas, kind, item, rect, dark=False): rect 가운데에 맞춰 그린다. 큰 그림(>=32)은 절반 크기로 그려 2배 확대(픽셀 느낌).
dark=True 면 잠긴 장비: 어두운 실루엣.
"""
import zlib

import pygame

from src.render.rod import gear_look

DARK = (44, 48, 66)
_cache: dict = {}


def _c(v, dark: bool):
    return DARK if dark else tuple(v)


def _shade(c, k: float):
    return tuple(max(0, min(255, int(x * k))) for x in c)


def _rod(s, n, look, dark):
    rod, hi, grip, wrap = (_c(look["rod"], dark), _c(look["hi"], dark), _c(look["grip"], dark), _c(look["wrap"], dark))
    a, b = (1, n - 2), (n - 2, 1)
    pygame.draw.line(s, rod, a, b, max(1, n // 12))
    g = (a[0] + (b[0] - a[0]) * 0.3, a[1] + (b[1] - a[1]) * 0.3)
    pygame.draw.line(s, grip, a, g, max(2, n // 8))
    w = (a[0] + (b[0] - a[0]) * 0.34, a[1] + (b[1] - a[1]) * 0.34)
    pygame.draw.circle(s, wrap, (int(w[0]), int(w[1])), max(1, n // 14))
    k = look.get("guides", 3)
    for i in range(k):
        t = 0.45 + 0.5 * i / max(1, k - 1)
        p = (int(a[0] + (b[0] - a[0]) * t), int(a[1] + (b[1] - a[1]) * t))
        s.fill(hi, (p[0], p[1] - 1, 1, 1))
        if n >= 24:
            s.fill(wrap, (p[0] + 1, p[1] - 1, 1, 1))


def _reel(s, n, look, dark):
    body, spool, knob = _c(look["body"], dark), _c(look["spool"], dark), _c(look["knob"], dark)
    cx, cy, r = n // 2 - n // 10, n // 2 + n // 12, max(3, int(n * 0.32 * min(1.15, look.get("size", 1.0))))
    pygame.draw.circle(s, _shade(body, 0.6), (cx + 1, cy + 1), r)
    pygame.draw.circle(s, body, (cx, cy), r)
    pygame.draw.circle(s, spool, (cx, cy), max(1, r * 6 // 10))
    pygame.draw.circle(s, _shade(spool, 0.7), (cx, cy), max(1, r * 3 // 10))
    hx, hy = cx + r + n // 8, cy - r // 2 - n // 10
    pygame.draw.line(s, body, (cx, cy), (hx, hy), max(1, n // 14))
    pygame.draw.circle(s, knob, (hx, hy), max(1, n // 12))
    s.fill(body, (cx - n // 16, cy - r - n // 8, max(2, n // 8), n // 8))   # 다리


def _line(s, n, look, dark):
    col = _c(look["color"], dark)
    frame = DARK if dark else (120, 124, 140)
    r = pygame.Rect(n // 6, n // 5, n - n // 3, n - n * 2 // 5)
    s.fill(frame, r)
    inner = r.inflate(-max(2, n // 6), -max(2, n // 8))
    s.fill(col, inner)
    for y in range(inner.y + 1, inner.bottom, max(2, n // 8)):
        s.fill(_shade(col, 0.75), (inner.x, y, inner.w, 1))
    if look.get("marks") and not dark:
        s.fill(tuple(look["marks"]), (inner.centerx, inner.y, 1, inner.h))
    s.fill(frame, (r.centerx - 1, r.y - n // 10, 2, n // 10))


def _net(s, n, look, dark):
    frame, mesh, handle = _c(look["frame"], dark), _c(look["mesh"], dark), _c(look["handle"], dark)
    hoop = pygame.Rect(1, 1, n * 6 // 10, n * 6 // 10)
    clip = s.get_clip()
    s.set_clip(hoop)
    for i in range(-n, n, max(2, n // 6)):
        pygame.draw.line(s, _shade(mesh, 0.8), (hoop.x + i, hoop.y), (hoop.x + i + n, hoop.y + n), 1)
        pygame.draw.line(s, _shade(mesh, 0.8), (hoop.x + i, hoop.bottom), (hoop.x + i + n, hoop.bottom - n), 1)
    s.set_clip(clip)
    pygame.draw.ellipse(s, frame, hoop, max(1, n // 14))
    pygame.draw.line(s, handle, (hoop.right - n // 10, hoop.bottom - n // 10), (n - 2, n - 2), max(1, n // 10))
    if look.get("trim") and not dark:
        s.fill(tuple(look["trim"]), (n - n // 5, n - n // 5, max(1, n // 12), max(1, n // 12)))


def _bait(s, n, item, dark):
    if item.get("tier") is None:      # 전설 미끼: 금빛
        col = (255, 214, 110)
    else:
        h = zlib.crc32(item["id"].encode())
        col = ((h >> 16) % 120 + 120, (h >> 8) % 120 + 100, h % 100 + 90)
    col = _c(col, dark)
    if item["id"] == "worm":
        pts = [(n // 6 + i, n // 2 + int(((i // max(1, n // 8)) % 2) * 2 - 1) * n // 8) for i in range(0, n * 2 // 3, max(1, n // 8))]
        if len(pts) > 1:
            pygame.draw.lines(s, col, False, pts, max(2, n // 7))
        return
    r = max(2, n // 4)
    pygame.draw.circle(s, _shade(col, 0.6), (n // 2 + 1, n // 2 + 1), r)
    pygame.draw.circle(s, col, (n // 2, n // 2), r)
    s.fill(_shade(col, 1.25), (n // 2 - r // 2, n // 2 - r // 2, max(1, r // 2), max(1, r // 2)))
    pygame.draw.line(s, (200, 200, 210) if not dark else DARK, (n // 2, n // 2 - r), (n // 2 + r, n // 8), 1)   # 바늘


def _float(s, n, item, dark):
    col = _c(item.get("color", (230, 80, 70)), dark)
    cx = n // 2
    body = pygame.Rect(cx - n // 6, n // 4, n // 3, n // 2)
    pygame.draw.ellipse(s, col, body)
    s.fill(DARK if dark else (245, 245, 240), (body.x, body.centery, body.w, max(1, n // 10)))
    s.fill(_shade(col, 0.6), (cx, 1, max(1, n // 16), n // 4))
    s.fill(_shade(col, 0.6), (cx, body.bottom, max(1, n // 16), n // 6))


def _paint(kind: str, item: dict, n: int, dark: bool) -> pygame.Surface:
    s = pygame.Surface((n, n), pygame.SRCALPHA)
    if kind == "bait":
        _bait(s, n, item, dark)
    elif kind == "float":
        _float(s, n, item, dark)
    else:
        look = gear_look(kind, int(item.get("tier") or 1))
        {"rod": _rod, "reel": _reel, "line": _line, "net": _net}[kind](s, n, look, dark)
    return s


def draw(canvas, kind: str, item: dict, rect, dark: bool = False) -> None:
    r = pygame.Rect(rect)
    size = min(r.w, r.h)
    key = (kind, item.get("id"), item.get("tier"), size, dark)
    img = _cache.get(key)
    if img is None:
        if size >= 32:   # 절반 크기로 그려 정수배 확대 (픽셀 느낌 유지)
            img = pygame.transform.scale(_paint(kind, item, size // 2, dark), (size // 2 * 2, size // 2 * 2))
        else:
            img = _paint(kind, item, size, dark)
        _cache[key] = img
    canvas.blit(img, img.get_rect(center=r.center))
