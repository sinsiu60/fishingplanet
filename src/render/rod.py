"""화면 오른쪽 아래 낚싯대 + 손 + 릴 (화면의 1/4 이내)."""
import math

import pygame

from src.core.mathutil import scale_color

HAND = (414, 236)
ROD_LEN = 136
BUTT_LEN = 34
REST_ANGLE = math.degrees(math.atan2(-110, -88))  # 손 → 낚싯대 끝 방향
AIM_DEG = 18


def rod_geometry(aim: float, swing_deg: float, bend: float, hand_offset=(0.0, 0.0), pull_x: float = 0.0) -> dict:
    """aim: -1~1 (왼쪽~오른쪽), swing_deg: 휘두르기 회전(+ = 뒤로 젖힘), bend: 휨(px, + = 아래로),
    pull_x: 낚싯대 끝이 옆으로 끌려가는 양(px, 물고기 쪽)."""
    hx, hy = HAND[0] + hand_offset[0], HAND[1] + hand_offset[1]
    ang = math.radians(REST_ANGLE + aim * AIM_DEG + swing_deg)
    dx, dy = math.cos(ang), math.sin(ang)
    # 낚싯대 아래쪽을 향하는 수직 벡터
    px, py = -dy, dx
    if py < 0:
        px, py = -px, -py
    butt = (hx - dx * BUTT_LEN, hy - dy * BUTT_LEN)
    straight_tip = (hx + dx * ROD_LEN, hy + dy * ROD_LEN)
    # 휘면 끝이 아래로 처지고 길이가 약간 줄어든다
    tip = (straight_tip[0] + px * bend * 1.2 + pull_x, straight_tip[1] + py * bend * 1.2)
    ctrl = (hx + dx * ROD_LEN * 0.55 + px * bend * 0.25 + pull_x * 0.3, hy + dy * ROD_LEN * 0.55 + py * bend * 0.25)
    return {"hand": (hx, hy), "butt": butt, "ctrl": ctrl, "tip": tip, "dir": (dx, dy), "perp": (px, py)}


def _bezier(p0, p1, p2, n):
    pts = []
    for i in range(n + 1):
        t = i / n
        a, b, c = (1 - t) ** 2, 2 * (1 - t) * t, t * t
        pts.append((a * p0[0] + b * p1[0] + c * p2[0], a * p0[1] + b * p1[1] + c * p2[1]))
    return pts


def gear_look(kind: str, tier: int) -> dict:
    """장비 티어 외형 (data/gear_looks.json). 없는 티어는 가장 가까운 아래 티어."""
    from src.core.config import load_json
    table = load_json("gear_looks.json")[kind]
    for k in range(max(1, min(8, tier)), 0, -1):
        if str(k) in table:
            return table[str(k)]
    return table["1"]


def _c(v):
    return tuple(v) if v is not None else None


def draw_rod(canvas: pygame.Surface, pal: dict, geo: dict, reel_angle: float, rod_look: dict | None = None,
             reel_look: dict | None = None, t: float = 0.0, hand_look: dict | None = None) -> None:
    """낚싯대(티어 외형) + 릴(티어 외형) + 낚싯대를 쥔 손. rod_look/reel_look = gear_look() (없으면 팔레트 색).
    hand_look (DETAILS C, DT7): glove = 장갑 색 | None, mitten = 두꺼운 방한 장갑, wet = 물기 점 수(0 = 마른 손), wear = 손잡이 손때 1~3."""
    hl = hand_look or {}
    hand = geo["hand"]
    dx, dy = geo["dir"]
    px, py = geo["perp"]
    rl = rod_look or {}
    rod = _c(rl.get("rod")) or pal["rod"]
    hi = _c(rl.get("hi")) or pal["rod_hi"]
    grip = _c(rl.get("grip")) or scale_color(rod, 0.8)
    wrap = _c(rl.get("wrap")) or hi
    glow = _c(rl.get("glow"))

    def at(u, v):
        """손 기준 낚싯대 좌표 (u = 낚싯대 방향, v = 아래쪽 수직)."""
        return (hand[0] + dx * u + px * v, hand[1] + dy * u + py * v)

    # 손잡이 (그립) — 손 뒤쪽으로 이어진 굵은 부분 (팔뚝 밑에 깔림)
    pygame.draw.line(canvas, scale_color(grip, 0.7), geo["butt"], hand, 6)
    pygame.draw.line(canvas, grip, geo["butt"], hand, 4)
    pygame.draw.circle(canvas, scale_color(grip, 0.6), (int(geo["butt"][0]), int(geo["butt"][1])), 3)  # 엉덩이 마개

    # 대: 손 → 끝 (손 쪽 굵고 끝으로 갈수록 가늘게)
    pts = _bezier(hand, geo["ctrl"], geo["tip"], 16)
    if glow:
        for i in range(len(pts) - 1):
            pygame.draw.line(canvas, scale_color(glow, 0.55), pts[i], pts[i + 1], 4 if i < 8 else 3)
    for i in range(len(pts) - 1):
        w = 3 if i < 4 else 2 if i < 10 else 1
        pygame.draw.line(canvas, rod, pts[i], pts[i + 1], w)
    for i in range(0, 9):
        pygame.draw.line(canvas, hi, pts[i], pts[i + 1], 1)
    if rl.get("nodes"):
        # 대나무 마디
        for i in (3, 7, 11):
            x, y = pts[i]
            pygame.draw.line(canvas, scale_color(rod, 0.55), (x - px * 2, y - py * 2), (x + px * 2, y + py * 2), 2)
    # 감개(실 감은 고리) + 가이드 링 (티어가 높을수록 많다)
    n = int(rl.get("guides", 3))
    for k in range(n):
        i = int(4 + k * (11 / max(1, n - 1))) if n > 1 else 8
        i = min(15, i)
        x, y = pts[i]
        pygame.draw.line(canvas, wrap, (x - dx * 1.5, y - dy * 1.5), (x + dx * 1.5, y + dy * 1.5), 2)
        gx, gy = int(x + px * 3), int(y + py * 3)
        pygame.draw.circle(canvas, scale_color(hi, 0.9), (gx, gy), 1)
    if rl.get("stars"):
        for k in range(4):
            i = int((t * 6 + k * 4) % 15)
            x, y = pts[i]
            if int(t * 10 + k) % 3 == 0:
                canvas.set_at((int(x), int(y)), (255, 255, 255))
    if glow:
        tx, ty = pts[-1]
        r = 2 + int(1.5 * abs(math.sin(t * 4)))
        pygame.draw.circle(canvas, glow, (int(tx), int(ty)), r)

    _draw_wear(canvas, at, grip, int(hl.get("wear", 1)))
    _draw_reel(canvas, pal, at, reel_angle, reel_look, t)
    _draw_arm(canvas, pal, at)
    _draw_hand(canvas, pal, at, hl.get("glove"), bool(hl.get("mitten")))
    if hl.get("wet"):
        _draw_wet(canvas, at, int(hl["wet"]), t)


def _draw_wear(canvas, at, grip, level: int) -> None:
    """손잡이 손때 (외형만, DT7): 손 바로 앞 앞손잡이(엄지가 닿는 곳)에. 1 새것 / 2 살짝 닳음 (반들반들한 자국) / 3 많이 닳음 (거무스름한 때 + 반들한 줄)."""
    if level <= 1:
        return
    worn = scale_color(grip, 1.3)
    dirt = scale_color(grip, 0.55)
    if level >= 3:
        pygame.draw.line(canvas, dirt, at(15, -1), at(24, -1), 3)     # 손때로 거뭇해진 앞손잡이
        pygame.draw.line(canvas, worn, at(16, -2), at(23, -2), 1)     # 엄지가 닳게 한 반들한 줄
        for u in (17, 21):
            x, y = at(u, 0)
            canvas.fill(dirt, (int(x), int(y), 2, 1))
    else:
        for u in (17, 21):
            x, y = at(u, -2)
            canvas.fill(worn, (int(x), int(y), 2, 1))


_WET = ((-6, -3), (-1, -5), (4, -4), (6, 2), (-3, 3), (1, 7))


def _draw_wet(canvas, at, n: int, t: float) -> None:
    """젖은 손: 손 위에 반짝이는 물기 점 n개 (번갈아 반짝)."""
    for i, (u, v) in enumerate(_WET[:max(0, min(len(_WET), n))]):
        x, y = at(u, v)
        on = int(t * 3 + i * 1.7) % 3 != 0
        canvas.fill((235, 248, 255) if on else (170, 200, 225), (int(x), int(y), 1, 1))
        if on and (i + int(t * 2)) % 4 == 0:
            canvas.fill((255, 255, 255), (int(x) - 1, int(y), 3, 1))


def _draw_arm(canvas, pal, at) -> None:
    """팔뚝: 손목에서 그립을 따라 화면 오른쪽 아래 밖으로 (그립은 팔뚝 밑에 깔린다). 소매 끝동 + 손목 살."""
    sleeve = pal["sleeve"]
    dark = scale_color(sleeve, 0.72)
    wrist_top, wrist_bot = at(-8, -6), at(-8, 9)
    far_top, far_bot = at(-150, -14), at(-150, 22)
    # 손목 살 (끝동과 주먹 사이)
    pygame.draw.polygon(canvas, pal["hand_shadow"], [wrist_top, wrist_bot, at(-14, 10), at(-14, -6)])
    # 소매
    cuff_top, cuff_bot = at(-13, -8), at(-13, 12)
    pygame.draw.polygon(canvas, dark, [(cuff_top[0] + 1, cuff_top[1] + 2), (cuff_bot[0] + 1, cuff_bot[1] + 2),
                                       far_bot, far_top])
    pygame.draw.polygon(canvas, sleeve, [cuff_top, cuff_bot, far_bot, far_top])
    pygame.draw.line(canvas, dark, at(-20, 6), at(-150, 14), 2)               # 주름
    pygame.draw.line(canvas, scale_color(sleeve, 1.15), cuff_top, cuff_bot, 3)  # 끝동


def _draw_reel(canvas, pal, at, reel_angle: float, look: dict | None, t: float) -> None:
    """릴: 낚싯대 아래에 매달림. 모양 spin(스피닝) / bait(베이트: 대 위에 납작) / large(큰 스피닝) / ornate(장식)."""
    look = look or {}
    body = _c(look.get("body")) or pal["reel"]
    spool = _c(look.get("spool")) or scale_color(body, 1.25)
    knob = _c(look.get("knob")) or scale_color(body, 1.3)
    k = float(look.get("size", 1.0))
    shape = look.get("shape", "spin")
    glow = _c(look.get("glow"))
    if shape == "bait":
        # 베이트 릴: 대 위(손 앞)에 납작하게 얹힘, 옆 손잡이
        c = at(12, -6)
        r = pygame.Rect(0, 0, int(14 * k), int(9 * k))
        r.center = (int(c[0]), int(c[1]))
        pygame.draw.ellipse(canvas, scale_color(body, 0.6), r.move(1, 1))
        pygame.draw.ellipse(canvas, body, r)
        pygame.draw.ellipse(canvas, spool, r.inflate(-6, -4))
        hx = c[0] + math.cos(reel_angle) * 7 * k
        hy = c[1] + math.sin(reel_angle) * 4 * k
        pygame.draw.line(canvas, scale_color(body, 0.8), c, (hx, hy), 1)
        pygame.draw.rect(canvas, knob, (hx - 1, hy - 1, 3, 3))
        return
    stem0, stem1 = at(14, 2), at(14, 9 * k)
    rc = stem1
    pygame.draw.line(canvas, scale_color(body, 0.7), stem0, stem1, 2)
    R = 7 * k
    if glow:
        pygame.draw.circle(canvas, scale_color(glow, 0.6), (int(rc[0]), int(rc[1])), int(R + 2 + abs(math.sin(t * 3))))
    pygame.draw.circle(canvas, scale_color(body, 0.6), (int(rc[0]), int(rc[1])), int(R))
    pygame.draw.circle(canvas, body, (int(rc[0]), int(rc[1])), int(R - 2))
    pygame.draw.circle(canvas, spool, (int(rc[0]), int(rc[1])), max(2, int(R - 4)))       # 스풀 (줄 감긴 부분)
    pygame.draw.circle(canvas, scale_color(body, 1.3), (int(rc[0] - 1), int(rc[1] - 1)), max(1, int(R * 0.25)))
    if shape == "ornate":
        for a in range(4):
            ang = a * math.pi / 2 + t * 0.5
            canvas.set_at((int(rc[0] + math.cos(ang) * (R - 1)), int(rc[1] + math.sin(ang) * (R - 1))), knob)
    arm = R + (3 if shape == "large" else 1)
    hx = rc[0] + math.cos(reel_angle) * arm
    hy = rc[1] + math.sin(reel_angle) * arm
    pygame.draw.line(canvas, scale_color(body, 0.8), rc, (hx, hy), 2 if shape == "large" else 1)
    pygame.draw.circle(canvas, knob, (int(hx), int(hy)), 2 if shape in ("large", "ornate") else 1)


def _draw_hand(canvas, pal, at, glove=None, mitten: bool = False) -> None:
    """낚싯대를 쥔 주먹: 손등이 대를 덮고, 손가락 넷이 대 아래로 말려 감싸며, 엄지는 대 위에 길게 얹힘.
    glove = 장갑 색 (겨울 니트 · 빙해 방한, DT7) — 밤 · 날씨 팔레트의 손 밝기를 따라 어둡게."""
    skin, shadow = pal["hand"], pal["hand_shadow"]
    if glove is not None:
        lum = (skin[0] + skin[1] + skin[2]) / (3 * 200.0)   # 기본 낮 손 밝기 ≈ 200
        skin = scale_color(tuple(glove), max(0.35, min(1.1, lum)))
        shadow = scale_color(skin, 0.72)
    dark = scale_color(shadow, 0.8)
    if mitten:
        # 두꺼운 방한 장갑: 손가락 구분 없이 둥근 덩어리 + 손목 띠
        fist = [at(-10, -6), at(-3, -8), at(6, -7), at(10, -2), at(10, 7), at(6, 11), at(-4, 12), at(-11, 7)]
        pygame.draw.polygon(canvas, shadow, [(x + 1, y + 1) for x, y in fist])
        pygame.draw.polygon(canvas, skin, fist)
        pygame.draw.polygon(canvas, scale_color(skin, 1.12), [at(-8, -5), at(-2, -7), at(5, -6), at(1, -2), at(-6, -1)])
        pygame.draw.line(canvas, scale_color(skin, 0.6), at(-9, -5), at(-9, 9), 2)   # 손목 띠
        thumb = [at(-1, -6), at(10, -7), at(13, -4), at(11, -2), at(2, -2)]
        pygame.draw.polygon(canvas, shadow, [(x + 1, y + 1) for x, y in thumb])
        pygame.draw.polygon(canvas, skin, thumb)
        return
    # 손등·주먹 (대를 감싼 둥근 덩어리, 낚싯대 방향으로 기울어짐)
    fist = [at(-9, -5), at(-3, -7), at(5, -6), at(8, -2), at(8, 5), at(5, 9), at(-4, 10), at(-10, 6)]
    pygame.draw.polygon(canvas, shadow, [(x + 1, y + 1) for x, y in fist])
    pygame.draw.polygon(canvas, skin, fist)
    # 대 아래로 말린 손가락 넷 (둥근 마디가 줄지어 보임)
    for i in range(4):
        u = -6 + i * 4
        c = at(u, 8)
        pygame.draw.circle(canvas, shadow, (int(c[0] + 1), int(c[1] + 1)), 3)
        pygame.draw.circle(canvas, skin, (int(c[0]), int(c[1])), 3)
        a, b = at(u + 2, 5), at(u + 2, 10)
        pygame.draw.line(canvas, dark, a, b, 1)  # 손가락 사이 주름
    # 손등 위 밝은 면 (빛)
    hi = scale_color(skin, 1.08)
    pygame.draw.polygon(canvas, hi, [at(-7, -4), at(-2, -6), at(4, -5), at(1, -2), at(-6, -1)])
    # 엄지: 대 위를 따라 끝 쪽으로 길게 얹힘
    thumb = [at(-1, -5), at(9, -6), at(13, -4), at(12, -2), at(2, -2)]
    pygame.draw.polygon(canvas, shadow, [(x + 1, y + 1) for x, y in thumb])
    pygame.draw.polygon(canvas, skin, thumb)
    if glove is not None:
        # 니트 장갑: 손등에 짜임 줄무늬 + 손목 고무단
        for u in (-6, -2, 2, 6):
            pygame.draw.line(canvas, scale_color(skin, 0.82), at(u, -5), at(u, 4), 1)
        pygame.draw.line(canvas, scale_color(skin, 1.15), at(-9, -4), at(-9, 8), 2)
        return
    nail = at(11, -4)
    pygame.draw.circle(canvas, scale_color(skin, 1.15), (int(nail[0]), int(nail[1])), 1)


def hand_outline(canvas, geo: dict, color, alpha: float, mitten: bool = False) -> None:
    """손(주먹 · 엄지 · 손가락) 바깥 테두리 1px — 환상 2페이즈 표시 (PHANTOM_PHASE2.md 5). alpha 0~1."""
    if alpha <= 0.01:
        return
    hand = geo["hand"]
    dx, dy = geo["dir"]
    px, py = geo["perp"]
    pad = 18
    ox, oy = int(hand[0]) - pad, int(hand[1]) - pad

    def at(u, v):
        return (hand[0] + dx * u + px * v - ox, hand[1] + dy * u + py * v - oy)

    if mitten:
        fist = [at(-10, -6), at(-3, -8), at(6, -7), at(10, -2), at(10, 7), at(6, 11), at(-4, 12), at(-11, 7)]
        thumb = [at(-1, -6), at(10, -7), at(13, -4), at(11, -2), at(2, -2)]
        knuckles = []
    else:
        fist = [at(-9, -5), at(-3, -7), at(5, -6), at(8, -2), at(8, 5), at(5, 9), at(-4, 10), at(-10, 6)]
        thumb = [at(-1, -5), at(9, -6), at(13, -4), at(12, -2), at(2, -2)]
        knuckles = [at(-6 + i * 4, 8) for i in range(4)]
    size = (pad * 2 + 1, pad * 2 + 1)
    body = pygame.Surface(size, pygame.SRCALPHA)
    for poly in (fist, thumb):
        pygame.draw.polygon(body, (255, 255, 255), poly)
        pygame.draw.polygon(body, (255, 255, 255), [(x + 1, y + 1) for x, y in poly])   # 그림자까지 손으로
    for c in knuckles:
        pygame.draw.circle(body, (255, 255, 255), (int(c[0]), int(c[1])), 3)
        pygame.draw.circle(body, (255, 255, 255), (int(c[0] + 1), int(c[1] + 1)), 3)
    m = pygame.mask.from_surface(body)
    ring = pygame.Surface(size, pygame.SRCALPHA)
    col = (*tuple(color)[:3], max(0, min(255, int(255 * alpha))))
    grown = m.to_surface(setcolor=col, unsetcolor=(0, 0, 0, 0))
    for ddx, ddy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        ring.blit(grown, (ddx, ddy))
    inner = m.to_surface(setcolor=(0, 0, 0, 0), unsetcolor=(255, 255, 255, 255))
    ring.blit(inner, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)   # 손 안쪽은 비움 → 바깥 1px 만
    canvas.blit(ring, (ox, oy))
