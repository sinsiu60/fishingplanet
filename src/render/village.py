"""마을 파노라마 그리기 (DESIGN.md 35-3): 윤슬 마을(나무 포구) · 아스테라 항구(돌길·수정 등불).

좌표: 파노라마 x (0 ~ width) − 보는 위치 ox = 화면 x. 하늘·먼 산·바다는 느리게(원근), 건물·NPC 는 1배.
시간대 팔레트(pal)·날씨·계절(장식·옷차림)을 낚시터와 함께 쓴다. 돌려주는 값 = 클릭 영역 [(id, kind, Rect)].
"""
import math
import random

import pygame

from src.core.mathutil import clamp, lerp_color
from src.core.fonts import get_font

HORIZON = 118
SEA_BOTTOM = 166
GROUND = 206      # 건물 바닥 (부두 판자 위)
FEET = 236        # NPC 발


def _night(hour: float) -> float:
    """밤 정도 0~1 (등불·창문 불빛)."""
    if 7 <= hour <= 17:
        return 0.0
    if hour > 17:
        return clamp((hour - 17) / 2.5, 0, 1)
    return clamp((7 - hour) / 1.5, 0, 1)


def _add_glow(canvas, pos, r: int, col) -> None:
    tmp = pygame.Surface((r * 2 + 2, r * 2 + 2))
    for rr, a in ((r, 0.25), (r * 0.6, 0.45), (r * 0.3, 0.8)):
        pygame.draw.circle(tmp, tuple(int(v * a) for v in col), (r + 1, r + 1), max(1, int(rr)))
    canvas.blit(tmp, (int(pos[0]) - r - 1, int(pos[1]) - r - 1), special_flags=pygame.BLEND_RGB_ADD)


# ───────────────────────── 배경 ─────────────────────────
def _sky(canvas, pal, w):
    top, bot = pal["sky_top"], pal["sky_bottom"]
    for y in range(0, HORIZON, 3):
        canvas.fill(lerp_color(top, bot, y / HORIZON), (0, y, w, 3))


def _celestial(canvas, pal, hour, ox, w, t):
    # 해: 6~18시 왼쪽→오른쪽, 달: 반대
    if 6 <= hour <= 18:
        u = (hour - 6) / 12
        x = lerp(-40, w + 40, u) - ox * 0.08
        y = HORIZON - 70 * math.sin(math.pi * u) - 4
        _add_glow(canvas, (x, y), 22, (255, 220, 160))
        pygame.draw.circle(canvas, (255, 240, 200), (int(x), int(y)), 9)
        return x
    hh = hour - 18 if hour >= 18 else hour + 6
    u = hh / 12
    x = lerp(-40, w + 40, u) - ox * 0.08
    y = HORIZON - 70 * math.sin(math.pi * u) - 4
    pygame.draw.circle(canvas, (230, 230, 245), (int(x), int(y)), 7)
    pygame.draw.circle(canvas, pal["sky_top"], (int(x) + 3, int(y) - 2), 6)
    rnd = random.Random(4)
    for _ in range(40):
        sx, sy = rnd.uniform(0, w), rnd.uniform(0, HORIZON - 20)
        if (math.sin(t * 2 + sx) + 1) * 0.5 > 0.3:
            canvas.fill((220, 225, 240), (int(sx), int(sy), 1, 1))
    return x


def lerp(a, b, k):
    return a + (b - a) * k


def _far(canvas, pal, ox, w, style):
    col = pal.get("mountain_far", (90, 100, 120))
    pts = [(0, HORIZON)]
    for x in range(0, w + 20, 20):
        u = (x + ox * 0.3) * 0.01
        hgt = 22 + 14 * math.sin(u * 1.3) + 9 * math.sin(u * 3.1 + 1)
        if style == "stone":   # 아스테라: 먼 섬 위 고대 탑
            hgt = 14 + 8 * math.sin(u * 1.7)
        pts.append((x, HORIZON - hgt))
    pts.append((w, HORIZON))
    pygame.draw.polygon(canvas, col, pts)
    if style == "stone":
        for k in range(3):
            tx = (180 + k * 380 - ox * 0.3) % (w + 200) - 100
            pygame.draw.rect(canvas, lerp_color(col, (40, 40, 70), 0.3), (tx, HORIZON - 46, 8, 40))
            pygame.draw.polygon(canvas, lerp_color(col, (40, 40, 70), 0.3), [(tx - 3, HORIZON - 46), (tx + 4, HORIZON - 58), (tx + 11, HORIZON - 46)])


def _sea(canvas, pal, ox, w, t, sun_x, night):
    top, bot = pal["water_top"], pal["water_bottom"]
    for y in range(HORIZON, SEA_BOTTOM, 2):
        canvas.fill(lerp_color(top, bot, (y - HORIZON) / (SEA_BOTTOM - HORIZON)), (0, y, w, 2))
    # 윤슬: 해(달) 아래 반짝이는 물결 조각
    rnd = random.Random(7)
    light = pal.get("wave_light", (220, 230, 240))
    for i in range(70):
        bx = rnd.uniform(-60, 60)
        y = rnd.uniform(HORIZON + 3, SEA_BOTTOM - 2)
        spread = 0.4 + (y - HORIZON) / (SEA_BOTTOM - HORIZON)
        x = sun_x + bx * spread * 2.2
        k = (math.sin(t * 3 + i * 1.7) + 1) * 0.5
        if k > 0.55:
            ln = 2 + int(5 * spread)
            canvas.fill(lerp_color(top, light, k * (0.6 if night > 0.5 else 1.0)), (int(x), int(y), ln, 1))
    for i in range(14):   # 먼 물결 줄
        x = (i * 83 - ox * 0.6 + t * 6) % (w + 40) - 20
        y = HORIZON + 8 + (i * 7) % (SEA_BOTTOM - HORIZON - 10)
        canvas.fill(lerp_color(top, light, 0.35), (int(x), int(y), 14, 1))


def _ground(canvas, pal, ox, w, h, style):
    if style == "wood":
        base = lerp_color((120, 88, 60), pal.get("sky_bottom", (200, 200, 200)), 0.08)
        dark = lerp_color(base, (40, 30, 20), 0.35)
        canvas.fill(base, (0, SEA_BOTTOM, w, h - SEA_BOTTOM))
        for y in range(SEA_BOTTOM, h, 7):
            canvas.fill(dark, (0, y, w, 1))
            off = (y * 37) % 60
            for x in range(-off - int(ox) % 60, w, 60):
                canvas.fill(dark, (x, y, 1, 7))
        canvas.fill(lerp_color(base, (255, 255, 255), 0.15), (0, SEA_BOTTOM, w, 2))
    else:
        base = lerp_color((96, 100, 120), pal.get("sky_bottom", (200, 200, 200)), 0.1)
        dark = lerp_color(base, (30, 30, 50), 0.4)
        canvas.fill(base, (0, SEA_BOTTOM, w, h - SEA_BOTTOM))
        for row, y in enumerate(range(SEA_BOTTOM, h, 12)):
            canvas.fill(dark, (0, y, w, 1))
            off = 24 if row % 2 else 0
            for x in range(-int(ox) % 48 - 48 + off, w, 48):
                canvas.fill(dark, (x, y, 1, 12))
        # 마력이 흐르는 돌길: 이음매를 따라 옅은 청록 빛
        canvas.fill(lerp_color(base, (120, 230, 230), 0.25), (0, SEA_BOTTOM, w, 2))


# ───────────────────────── 건물 ─────────────────────────
def _window(canvas, x, y, ww, hh, night, frame):
    col = lerp_color((60, 70, 90), (255, 210, 120), night)
    canvas.fill(col, (x, y, ww, hh))
    pygame.draw.rect(canvas, frame, (x, y, ww, hh), 1)
    canvas.fill(frame, (x + ww // 2, y, 1, hh))


def _sign(canvas, cx, y, label, col_bg, col_fg):
    f = get_font(11)
    img = f.render(label, False, col_fg)
    r = pygame.Rect(0, 0, img.get_width() + 8, 13)
    r.center = (cx, y)
    canvas.fill(col_bg, r)
    pygame.draw.rect(canvas, lerp_color(col_bg, (0, 0, 0), 0.4), r, 1)
    canvas.blit(img, img.get_rect(center=r.center))
    return r


def draw_place(canvas, p: dict, sx: float, pal, night: float, t: float, style: str, season: str, hover: bool) -> pygame.Rect:
    kind, w = p["kind"], p["w"]
    x0 = int(sx - w / 2)
    wall = tuple(p.get("wall", (150, 110, 80)))
    roof = tuple(p.get("roof", (110, 60, 40)))
    shade = lambda c, k: lerp_color(c, pal.get("sky_top", (0, 0, 0)), k)  # noqa: E731  저녁·밤 색 섞기
    k = 0.15 + 0.35 * night
    hit = pygame.Rect(x0, GROUND - 80, w, 84)
    if kind in ("house", "hut"):
        hh = 62 if kind == "house" else 44
        canvas.fill(shade(wall, k), (x0, GROUND - hh, w, hh))
        for yy in range(GROUND - hh, GROUND, 6):   # 판자 결
            canvas.fill(shade(lerp_color(wall, (0, 0, 0), 0.15), k), (x0, yy, w, 1))
        pygame.draw.polygon(canvas, shade(roof, k), [(x0 - 8, GROUND - hh), (x0 + w // 2, GROUND - hh - 30), (x0 + w + 8, GROUND - hh)])
        canvas.fill(shade(lerp_color(wall, (0, 0, 0), 0.5), k), (x0 + w // 2 - 9, GROUND - 26, 18, 26))   # 문
        _window(canvas, x0 + 12, GROUND - hh + 14, 18, 14, night, shade(lerp_color(wall, (0, 0, 0), 0.5), k))
        _window(canvas, x0 + w - 30, GROUND - hh + 14, 18, 14, night, shade(lerp_color(wall, (0, 0, 0), 0.5), k))
        if kind == "hut":   # 그물 말리는 틀
            px = x0 + w + 6
            pygame.draw.line(canvas, (90, 70, 50), (px, GROUND), (px, GROUND - 40), 2)
            pygame.draw.line(canvas, (90, 70, 50), (px + 30, GROUND), (px + 30, GROUND - 40), 2)
            for j in range(6):
                pygame.draw.line(canvas, (170, 160, 130), (px, GROUND - 38 + j * 5), (px + 30, GROUND - 36 + j * 5), 1)
            hit = pygame.Rect(x0, GROUND - hh - 30, w + 40, hh + 34)
        else:
            hit = pygame.Rect(x0 - 8, GROUND - hh - 30, w + 16, hh + 34)
        if p.get("sign") == "fish":   # 물고기 모양 간판
            fx, fy = x0 + w // 2, GROUND - hh - 8
            pygame.draw.ellipse(canvas, (230, 220, 190), (fx - 14, fy - 5, 24, 10))
            pygame.draw.polygon(canvas, (230, 220, 190), [(fx + 9, fy), (fx + 16, fy - 5), (fx + 16, fy + 5)])
            canvas.fill((40, 40, 40), (fx - 9, fy - 1, 2, 2))
        _sign(canvas, x0 + w // 2, GROUND - hh - 18 if p.get("sign") != "fish" else GROUND - hh + 4, p["name"],
              (60, 44, 30) if style == "wood" else (40, 46, 80), (250, 236, 200))
        if night > 0.2:
            _add_glow(canvas, (x0 + 21, GROUND - hh + 21), 14, tuple(int(v * night) for v in (255, 190, 100)))
            _add_glow(canvas, (x0 + w - 21, GROUND - hh + 21), 14, tuple(int(v * night) for v in (255, 190, 100)))
    elif kind == "arch":
        hh = 66
        canvas.fill(shade(wall, k), (x0, GROUND - hh, w, hh))
        for yy in range(GROUND - hh, GROUND, 11):
            canvas.fill(shade(lerp_color(wall, (0, 0, 0), 0.2), k), (x0, yy, w, 1))
        pygame.draw.rect(canvas, shade(roof, k), (x0 - 6, GROUND - hh - 10, w + 12, 10))
        pygame.draw.polygon(canvas, shade(roof, k), [(x0 + w // 2 - 30, GROUND - hh - 10), (x0 + w // 2, GROUND - hh - 30), (x0 + w // 2 + 30, GROUND - hh - 10)])
        door = pygame.Rect(x0 + w // 2 - 13, GROUND - 34, 26, 34)
        canvas.fill(shade((30, 30, 50), k * 0.5), door)
        pygame.draw.ellipse(canvas, shade((30, 30, 50), k * 0.5), (door.x, door.y - 13, 26, 26))
        # 수정 등불 (낮에도 은은, 밤엔 환하게)
        for lx in (x0 + 10, x0 + w - 10):
            ly = GROUND - hh + 18
            pygame.draw.polygon(canvas, (140, 240, 240), [(lx, ly - 6), (lx + 4, ly), (lx, ly + 6), (lx - 4, ly)])
            _add_glow(canvas, (lx, ly), 16, tuple(int(v * (0.35 + 0.65 * night) * (0.85 + 0.15 * math.sin(t * 2 + lx))) for v in (90, 220, 230)))
        if p.get("sign") == "fish":
            fx, fy = x0 + w // 2, GROUND - hh - 18
            pygame.draw.ellipse(canvas, (200, 230, 240), (fx - 14, fy - 5, 24, 10))
            pygame.draw.polygon(canvas, (200, 230, 240), [(fx + 9, fy), (fx + 16, fy - 5), (fx + 16, fy + 5)])
        _sign(canvas, x0 + w // 2, GROUND - hh + 8, p["name"], (36, 40, 76), (220, 240, 255))
        hit = pygame.Rect(x0 - 6, GROUND - hh - 30, w + 12, hh + 34)
    elif kind in ("board", "notice"):
        bw = w - 10
        for px in (x0 + 6, x0 + w - 8):
            canvas.fill(shade((90, 66, 44), k), (px, GROUND - 52, 3, 52))
        r = pygame.Rect(x0 + 2, GROUND - 56, bw + 6, 32)
        canvas.fill(shade((150, 112, 72), k), r)
        pygame.draw.rect(canvas, shade((90, 66, 44), k), r, 2)
        if kind == "board":
            for j, (dx, dy) in enumerate(((6, 4), (24, 6), (40, 3), (14, 16), (34, 17))):
                if dx + 12 < r.w:
                    canvas.fill((240, 236, 220) if j % 2 else (250, 240, 200), (r.x + dx, r.y + dy, 11, 10))
                    canvas.fill((200, 60, 60), (r.x + dx + 5, r.y + dy, 2, 2))
        else:
            from src.core.season import ICON
            col = {"spring": (255, 170, 200), "summer": (120, 200, 90), "autumn": (230, 140, 60), "winter": (200, 230, 255)}[season]
            pygame.draw.circle(canvas, col, (r.centerx, r.centery), 9)
            img = get_font(11).render(ICON[season], False, (40, 40, 40))
            canvas.blit(img, img.get_rect(center=r.center))
        _sign(canvas, x0 + w // 2, GROUND - 64, p["name"], (60, 44, 30) if style == "wood" else (40, 46, 80), (250, 236, 200))
        hit = pygame.Rect(x0 - 4, GROUND - 72, w + 8, 76)
    elif kind == "dock":
        canvas.fill(shade((110, 80, 54), k), (x0 - 40, SEA_BOTTOM - 12, w + 40, 12))
        for px in range(x0 - 36, x0 + w, 22):
            canvas.fill(shade((80, 58, 40), k), (px, SEA_BOTTOM - 12, 4, 22))
        if p.get("ship"):   # 범선
            bx, by = x0 + 10, SEA_BOTTOM - 22
            pygame.draw.polygon(canvas, shade((90, 60, 40), k), [(bx - 30, by), (bx + 70, by), (bx + 58, by + 14), (bx - 22, by + 14)])
            canvas.fill(shade((80, 60, 40), k), (bx + 18, by - 62, 3, 62))
            pygame.draw.polygon(canvas, shade((235, 230, 215), k), [(bx + 21, by - 58), (bx + 52, by - 22), (bx + 21, by - 18)])
            pygame.draw.polygon(canvas, shade((235, 230, 215), k), [(bx + 17, by - 52), (bx - 10, by - 22), (bx + 17, by - 20)])
            _add_glow(canvas, (bx + 66, by - 4), 10, tuple(int(v * (0.3 + 0.7 * night)) for v in (90, 220, 230)))
        else:   # 작은 고깃배
            bx, by = x0 + 20 + math.sin(t * 1.3) * 1.5, SEA_BOTTOM - 6 + math.sin(t * 1.7) * 1.2
            pygame.draw.polygon(canvas, shade((170, 70, 50), k), [(bx - 26, by - 6), (bx + 30, by - 6), (bx + 22, by + 4), (bx - 18, by + 4)])
            canvas.fill(shade((240, 230, 210), k), (int(bx - 6), int(by - 14), 14, 8))
        _sign(canvas, x0 + w // 2, SEA_BOTTOM - 30, p["name"], (60, 44, 30) if style == "wood" else (40, 46, 80), (250, 236, 200))
        hit = pygame.Rect(x0 - 40, SEA_BOTTOM - 40, w + 40, 60)
    if hover:
        pygame.draw.rect(canvas, (255, 236, 170), hit, 1)
    return hit


# ───────────────────────── NPC ─────────────────────────
def draw_npc(canvas, sx: float, spec: dict, t: float, season: str, hover: bool, night: float) -> pygame.Rect:
    """단순한 실루엣·도형 사람: 몸통 사다리꼴 + 머리 + 모자 + 소품, 계절 옷차림 (겨울 목도리 등)."""
    body, skin, hat_col = tuple(spec["body"]), tuple(spec["skin"]), tuple(spec.get("hat_col", (80, 80, 80)))
    sit = spec.get("sit", False)
    bob = math.sin(t * 2 + sx * 0.1) * 0.8
    fy = FEET
    if season == "autumn":
        body = lerp_color(body, (140, 90, 50), 0.35)
    k = 0.15 + 0.3 * night
    dim = lambda c: lerp_color(c, (20, 20, 40), k)  # noqa: E731
    if sit:   # 나무 상자에 앉음
        canvas.fill(dim((110, 80, 50)), (sx - 9, fy - 12, 18, 12))
        hip = fy - 12
    else:
        canvas.fill(dim((50, 46, 60)), (sx - 5, fy - 14, 4, 14))
        canvas.fill(dim((50, 46, 60)), (sx + 1, fy - 14, 4, 14))
        hip = fy - 14
    top = hip - 18 + bob
    pygame.draw.polygon(canvas, dim(body), [(sx - 8, hip), (sx + 8, hip), (sx + 6, top), (sx - 6, top)])
    arm = skin if season == "summer" else body
    canvas.fill(dim(lerp_color(arm, (0, 0, 0), 0.1)), (sx - 10, top + 2, 3, 12))
    canvas.fill(dim(lerp_color(arm, (0, 0, 0), 0.1)), (sx + 7, top + 2, 3, 12))
    head = (int(sx), int(top - 6))
    pygame.draw.circle(canvas, dim(skin), head, 6)
    blink = (t * 0.7 + sx) % 4 < 0.12
    if not blink:
        canvas.fill((30, 30, 40), (head[0] - 3, head[1] - 1, 1, 2))
        canvas.fill((30, 30, 40), (head[0] + 2, head[1] - 1, 1, 2))
    hat = spec.get("hat")
    if hat == "cap":
        pygame.draw.ellipse(canvas, dim(hat_col), (head[0] - 6, head[1] - 9, 12, 7))
        canvas.fill(dim(hat_col), (head[0] - 9, head[1] - 4, 8, 2))
    elif hat == "straw" or season == "summer" and hat in (None, "band"):
        pygame.draw.ellipse(canvas, dim((210, 190, 120)), (head[0] - 11, head[1] - 6, 22, 5))
        pygame.draw.ellipse(canvas, dim((210, 190, 120)), (head[0] - 5, head[1] - 10, 10, 7))
    elif hat == "band":
        canvas.fill(dim(hat_col), (head[0] - 6, head[1] - 5, 12, 2))
    elif hat == "feather":
        canvas.fill(dim((70, 60, 50)), (head[0] - 6, head[1] - 9, 12, 5))
        pygame.draw.line(canvas, dim(hat_col), (head[0] + 4, head[1] - 9), (head[0] + 10, head[1] - 17), 2)
    elif hat == "hood":
        pygame.draw.polygon(canvas, dim(hat_col), [(head[0] - 8, head[1] + 4), (head[0], head[1] - 10), (head[0] + 8, head[1] + 4)], 0)
        pygame.draw.circle(canvas, dim(skin), (head[0], head[1] + 1), 4)
    if season == "spring" and hat not in ("hood",):   # 모자에 꽃
        pygame.draw.circle(canvas, (255, 170, 200), (head[0] - 4, head[1] - 7), 2)
    if season == "winter":   # 목도리
        canvas.fill((200, 60, 60), (sx - 7, top - 1, 14, 3))
        canvas.fill((200, 60, 60), (sx + 3, top + 1, 3, 7))
    prop = spec.get("prop")
    if prop == "rod":
        pygame.draw.line(canvas, dim((90, 70, 50)), (sx + 9, top + 10), (sx + 20, top - 26), 1)
    elif prop == "papers":
        canvas.fill((245, 240, 225), (sx - 13, top + 6, 6, 8))
    elif prop == "glasses":
        pygame.draw.circle(canvas, (40, 40, 50), (head[0] - 2, head[1]), 2, 1)
        pygame.draw.circle(canvas, (40, 40, 50), (head[0] + 3, head[1]), 2, 1)
    elif prop == "pipe":
        canvas.fill((80, 60, 40), (head[0] + 4, head[1] + 3, 4, 1))
        for j in range(3):
            yy = head[1] - 2 - j * 4 - (t * 6) % 4
            pygame.draw.circle(canvas, (200, 200, 205), (int(head[0] + 9 + j * 2), int(yy)), 1 + j // 2)
    elif prop == "crystal":
        cx, cy = sx + 12, top + 8
        pygame.draw.polygon(canvas, (140, 240, 240), [(cx, cy - 5), (cx + 3, cy), (cx, cy + 5), (cx - 3, cy)])
        _add_glow(canvas, (cx, cy), 8, (60, 160, 170))
    elif prop == "scroll":
        canvas.fill((220, 200, 150), (sx - 14, top + 7, 8, 4))
    hit = pygame.Rect(sx - 12, top - 18, 24, fy - top + 18)
    if hover:
        pygame.draw.rect(canvas, (255, 236, 170), hit, 1)
        img = get_font(11).render(spec["name"], False, (255, 240, 200))
        r = img.get_rect(midbottom=(sx, hit.y - 2))
        canvas.fill((20, 20, 30), r.inflate(4, 2))
        canvas.blit(img, r)
    return hit


def draw_lamps(canvas, ox, w, style, night, t, width):
    for px in range(130, width, 190):
        sx = px - ox
        if not -20 < sx < w + 20:
            continue
        if style == "wood":
            canvas.fill((60, 50, 40), (sx, GROUND - 46, 2, 46))
            canvas.fill((60, 50, 40), (sx - 3, GROUND - 48, 8, 3))
            col = (255, 200, 120)
        else:
            canvas.fill((80, 84, 110), (sx, GROUND - 50, 3, 50))
            col = (90, 220, 230)
        lamp = (sx + 1, GROUND - 52)
        canvas.fill(lerp_color((80, 80, 80), col, max(0.25, night)), (lamp[0] - 2, lamp[1] - 3, 5, 6))
        if night > 0.1:
            _add_glow(canvas, lamp, 22, tuple(int(v * night * (0.9 + 0.1 * math.sin(t * 3 + px))) for v in col))


def draw_gulls(canvas, w, t):
    for i in range(4):
        x = (i * 140 + t * (18 + i * 4)) % (w + 80) - 40
        y = 30 + i * 13 + math.sin(t * 1.5 + i) * 6
        flap = math.sin(t * 6 + i * 2) * 3
        pygame.draw.lines(canvas, (240, 240, 245), False, [(x - 6, y + flap), (x, y), (x + 6, y + flap)], 1)


def draw_motes(canvas, w, t, night: float = 0.0):
    """아스테라: 떠오르는 마력 알갱이 (낮엔 드물고 옅게, 밤엔 또렷하게)."""
    rnd = random.Random(11)
    n = int(6 + 10 * night)
    k = 0.35 + 0.65 * night
    for i in range(n):
        x = (rnd.uniform(0, w) + math.sin(t * 0.4 + i) * 20) % w
        y = (rnd.uniform(20, 200) - t * (6 + i % 4)) % 200 + 10
        _add_glow(canvas, (x, y), 4, tuple(int(v * k) for v in (60, 160, 170)))
