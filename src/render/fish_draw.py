"""물고기 그리기: 옆모습(점프·뜰채·획득 컷), 획득 컷 전체 연출."""
import math

import pygame

from src.render.screen import opaque as _opaque

from src.core.mathutil import clamp, lerp, lerp_color, scale_color, smoothstep

DEFAULT_COLORS = {"body": [120, 130, 120], "belly": [220, 220, 210], "fin": [90, 100, 90], "stripe": None, "eye": None}
RANK_COLORS = {"S": (255, 214, 90), "A": (150, 200, 255), "B": (140, 220, 150), "C": (190, 190, 190)}
RARITY_GLOW = {"common": (255, 245, 210), "uncommon": (150, 255, 170), "rare": (140, 200, 255),
               "phantom": (210, 150, 255), "legend": (255, 210, 90)}


def fish_colors(fish: dict) -> dict:
    c = dict(DEFAULT_COLORS)
    c.update(fish.get("colors") or {})
    return {k: (tuple(v) if v else None) for k, v in c.items()}


def fish_shape(fish: dict) -> dict:
    """fish.json shape + 등급 (희귀·전설 장식을 그리려고)."""
    return dict(fish.get("shape") or {}, rarity=fish.get("rarity", "common"))


# 몸 기본 도형 (fish.json shape.form). 일반·고급은 spindle, 희귀·전설은 저마다 다른 틀.
FORM_TAIL = {"shark": "hetero", "lobe": "tri", "flyer": "flyer"}


def _profile(form: str, u: float, ribbon: bool = False) -> tuple[float, float]:
    """몸 윤곽. u: 0 = 주둥이 → 1 = 꼬리 자루. (등 쪽, 배 쪽) 높이 (H 단위)."""
    def tap(start, end=0.35):
        return lerp(1.0, end, smoothstep(clamp((u - start) / (1 - start), 0, 1)))
    if ribbon:
        k = min(1.0, u * 6) ** 0.6 * lerp(1.0, 0.25, clamp((u - 0.6) / 0.4, 0, 1))
        return max(0.2, k), max(0.2, k) * 1.08
    if form == "flathead":   # 메기: 넓적한 머리 → 쐐기처럼 가늘어짐
        s = min(1.0, u / 0.07) ** 0.5
        return s * lerp(0.75, 0.2, u ** 0.85), s * lerp(0.85, 0.2, u ** 0.85)
    if form == "arrow":      # 가물치: 뾰족한 머리 + 통나무 같은 긴 몸
        s = min(1.0, u / 0.24) ** 0.9
        return s * 0.75 * tap(0.72, 0.5), s * 0.75 * tap(0.72, 0.5)
    if form == "bass":       # 쏘가리·농어: 큰 머리, 솟은 등, 곧은 배, 튀어나온 아래턱
        return min(1.0, u / 0.3) ** 0.55 * 1.1 * tap(0.4, 0.3), min(1.0, u / 0.1) ** 0.7 * 0.85 * tap(0.5, 0.3)
    if form == "trout":      # 열목어·송어: 둥근 주둥이, 길고 고른 원통
        s = min(1.0, u / 0.14) ** 0.45
        return s * 0.7 * tap(0.62, 0.5), s * 0.75 * tap(0.62, 0.5)
    if form == "salmon":     # 연어: 송어 + 머리 뒤 혹
        s = min(1.0, u / 0.16) ** 0.5
        hump = 0.4 * math.exp(-((u - 0.32) / 0.16) ** 2)
        return s * (0.85 + hump) * tap(0.55, 0.38), s * 0.9 * tap(0.55, 0.38)
    if form == "disk":       # 감성돔·정령어: 동그란 원반
        s = math.sin(math.pi * clamp(u * 0.9 + 0.05, 0, 1)) ** 0.42
        return s * tap(0.72, 0.22), s * tap(0.72, 0.22)
    if form == "hump":       # 잉어왕: 오목한 이마 → 높은 혹 → 처지는 등
        tp = (u / 0.32) ** 1.5 * 1.3 if u < 0.32 else lerp(1.3, 0.32, smoothstep((u - 0.32) / 0.68))
        b = math.sin(math.pi * clamp(u * 0.92 + 0.06, 0, 1)) ** 0.7 * tap(0.55)
        return max(0.12, tp), b * 0.95
    if form == "blunthead":  # 만새기: 깎아지른 이마
        return min(1.0, u / 0.04) * lerp(1.25, 0.3, u ** 1.25), min(1.0, u / 0.16) ** 0.6 * lerp(0.8, 0.3, u ** 1.1)
    if form == "tuna":       # 참치: 총알 몸 + 아주 가는 꼬리 자루
        s = min(1.0, u / 0.32) ** 0.5
        return s * tap(0.4, 0.1), s * 1.05 * tap(0.4, 0.1)
    if form == "shark":      # 상어: 뾰족한 코가 위로, 배는 코 뒤에서 시작
        tp = min(1.0, u / 0.32) ** 0.75 * tap(0.35, 0.22)
        b = lerp(-0.12, 0.9, min(1.0, u / 0.3) ** 0.6) * tap(0.4, 0.22)
        return max(0.1, tp), b
    if form == "lobe":       # 실러캔스: 두툼하고 고른 통
        s = min(1.0, u / 0.2) ** 0.6
        k = s * lerp(1.0, 0.42, clamp(u, 0, 1) ** 1.4)
        return k, k
    if form == "flyer":      # 날치: 가는 몸
        s = min(1.0, u / 0.2) ** 0.6
        return s * 0.8 * tap(0.5), s * 0.9 * tap(0.5)
    if form == "serpent":    # 천해왕: 길고 고른 용 같은 몸
        s = min(1.0, u / 0.1) ** 0.6
        return s * lerp(1.0, 0.6, u), s * lerp(1.0, 0.6, u)
    prof = math.sin(math.pi * clamp(u * 0.92 + 0.06, 0, 1)) ** 0.75
    k = max(0.2, prof) * tap(0.55)
    return k, k * 1.08


def _wave(form: str, u: float, ph: float, wag: float) -> float:
    """몸 중심선 출렁임 (H 단위). 용 같은 몸만."""
    if form != "serpent":
        return 0.0
    return math.sin(u * 5.5 - ph * 4.0) * 0.45 * u


def _xf(points, cx, cy, angle, facing):
    """회전 + 좌우 반전 + 이동. facing=-1이면 머리가 왼쪽."""
    ca, sa = math.cos(angle), math.sin(angle)
    out = []
    for x, y in points:
        x *= -facing
        out.append((cx + x * ca - y * sa, cy + x * sa + y * ca))
    return out


def draw_fish_side(canvas, cx: float, cy: float, length: float, angle: float, colors: dict,
                   facing: int = -1, silhouette=None, tail_wag: float = 0.0, shape: dict | None = None) -> None:
    """옆모습 물고기. 기본은 머리가 왼쪽(-x). silhouette 색을 주면 단색 실루엣.

    shape (fish.json): height(몸 높이 비율), tail(fork/round/lunate/ribbon), pattern(stripe/bars/spots),
    dorsal(normal/long/crest), whiskers, eye_big, bill, lure, finlets, kind(squid)
    """
    shape = shape or {}
    if shape.get("kind") == "squid":
        draw_squid(canvas, cx, cy, length, angle, colors, facing, silhouette, tail_wag)
        return
    if shape.get("kind") == "manta":
        draw_manta(canvas, cx, cy, length, angle, colors, facing, silhouette, tail_wag)
        return
    L = length
    H = L * shape.get("height", 0.17)
    form = shape.get("form", "spindle")
    tail_type = FORM_TAIL.get(form, shape.get("tail", "fork"))
    ribbon = tail_type == "ribbon"
    body_frac = 0.92 if ribbon else 0.84 if form in ("serpent", "lobe") else 0.82 if tail_type in ("round", "tri") else 0.8
    top, bot = [], []
    n = 14
    tail_base = -L / 2 + L * body_frac
    ph = pygame.time.get_ticks() / 1000.0
    for i in range(n + 1):
        u = i / n
        x = -L / 2 + u * L * body_frac
        t_k, b_k = _profile(form, u, ribbon)
        off = _wave(form, u, ph, tail_wag) * H
        top.append((x, -H * t_k + off))
        bot.append((x, H * b_k + off))
    wag = tail_wag * H * 0.6 + _wave(form, 1.0, ph, tail_wag) * H
    tx = L / 2
    if tail_type == "round":
        tail = [(tail_base + L * 0.1, -H * 0.55 + wag), (tx, -H * 0.2 + wag), (tx, H * 0.25 + wag),
                (tail_base + L * 0.1, H * 0.6 + wag)]
    elif tail_type == "tri":  # 실러캔스: 둥근 꼬리 + 가운데 작은 꼬리
        tail = [(tail_base + L * 0.08, -H * 0.7 + wag), (tx - L * 0.03, -H * 0.3 + wag), (tx + L * 0.05, -H * 0.1 + wag),
                (tx + L * 0.05, H * 0.1 + wag), (tx - L * 0.03, H * 0.3 + wag), (tail_base + L * 0.08, H * 0.7 + wag)]
    elif tail_type == "hetero":  # 상어: 위쪽 꼬리가 길게
        tail = [(tx + L * 0.03, -H * 1.55 + wag), (tail_base + L * 0.07, -H * 0.05 + wag * 0.5),
                (tx - L * 0.04, H * 0.75 + wag)]
    elif tail_type == "flyer":  # 날치: 아래 꼬리가 길게
        tail = [(tx - L * 0.02, -H * 0.8 + wag), (tx - L * 0.07, wag * 0.5), (tx + L * 0.06, H * 1.35 + wag)]
    elif tail_type == "lunate":
        tail = [(tx + L * 0.02, -H * 1.05 + wag), (tail_base + L * 0.1, wag * 0.5), (tx + L * 0.02, H * 1.05 + wag)]
    elif ribbon:
        tail = [(tx, -H * 0.15 + wag), (tx, H * 0.15 + wag)]
    else:
        tail = [(tx, -H * 0.85 + wag), (tx - L * 0.06, wag * 0.5), (tx, H * 0.85 + wag)]
    body = top + tail + bot[::-1]
    pts_body = _xf(body, cx, cy, angle, facing)
    tier = {"rare": 2, "phantom": 2, "legend": 3}.get(shape.get("rarity"), 0)
    phantom = shape.get("rarity") == "phantom"  # 환상: 보랏빛 오라 + 보라 테두리
    xf = lambda pts: _xf(pts, cx, cy, angle, facing)  # noqa: E731

    back, front = _fins(form, shape, L, H, top, bot, tail_base, ribbon, ph)

    if silhouette is not None:
        if tier >= 3:
            _rarity_back(canvas, xf, L, H, top, tail, tail_wag, tier, silhouette, silhouette, silhouette)
        for poly in back:
            pygame.draw.polygon(canvas, silhouette, xf(poly))
        pygame.draw.polygon(canvas, silhouette, pts_body)
        for poly in front:
            pygame.draw.polygon(canvas, silhouette, xf(poly))
        if shape.get("bill"):
            pygame.draw.line(canvas, silhouette, *_xf([(-L / 2, 0), (-L / 2 - L * 0.22, -H * 0.1)], cx, cy, angle,
                                                      facing), max(1, int(L / 50)))
        return

    base, belly, fin_c, stripe = colors["body"], colors["belly"], colors["fin"], colors["stripe"]
    if phantom:
        _aura(canvas, pts_body, RARITY_GLOW["phantom"], 0.6 + 0.4 * math.sin(ph * 2.4))
    if tier >= 3:
        _aura(canvas, pts_body, RARITY_GLOW["legend"], 0.5 + 0.5 * math.sin(ph * 3.2))
        _rarity_back(canvas, xf, L, H, top, tail, tail_wag, tier, fin_c, base, stripe)
    for poly in back:  # 등·뒷지느러미 (몸 뒤에)
        pygame.draw.polygon(canvas, fin_c, xf(poly))
    pygame.draw.polygon(canvas, base, pts_body)
    # 배
    belly_poly = [(p[0], -p[1] * 0.25) for p in top[1:-2]] + bot[1:-2][::-1]
    pygame.draw.polygon(canvas, belly, _xf(belly_poly, cx, cy, angle, facing))
    # 등 쪽 어두운 음영
    back_poly = top[1:-1] + [(p[0], p[1] * 0.55) for p in top[1:-1]][::-1]
    pygame.draw.polygon(canvas, scale_color(base, 0.8), _xf(back_poly, cx, cy, angle, facing))
    # 무늬
    pattern = shape.get("pattern")
    if stripe and pattern == "bars":
        for i in range(5):
            x = -L * 0.25 + i * L * 0.11
            pts = _xf([(x, -H * 0.85), (x + L * 0.03, H * 0.45)], cx, cy, angle, facing)
            pygame.draw.line(canvas, stripe, pts[0], pts[1], max(1, int(L / 45)))
    elif stripe and pattern == "spots":
        for i in range(9):
            x = -L * 0.25 + (i % 5) * L * 0.11 + (i // 5) * L * 0.05
            y = -H * 0.45 + (i // 5) * H * 0.5
            p = _xf([(x, y)], cx, cy, angle, facing)[0]
            pygame.draw.circle(canvas, stripe, p, max(1, int(L / 55)))
    elif stripe:
        pts = _xf([(-L * 0.3, -H * 0.05), (tail_base - L * 0.04, H * 0.05)], cx, cy, angle, facing)
        pygame.draw.line(canvas, stripe, pts[0], pts[1], max(1, int(L / 60)))
    # 꼬리 쪽 작은 지느러미 (참치)
    if shape.get("finlets"):
        for i in range(4):
            x = L * 0.1 + i * L * 0.05
            for sgn in (-1, 1):
                p = _xf([(x, sgn * H * 0.5)], cx, cy, angle, facing)[0]
                canvas.fill((235, 210, 90), (int(p[0]), int(p[1]), 2, 2))
    # 가슴지느러미 · 날개 (몸 앞에)
    for poly in front:
        pygame.draw.polygon(canvas, fin_c, xf(poly))
        if len(poly) >= 4 and form == "flyer":  # 날개 살
            for q in poly[1:3]:
                pygame.draw.line(canvas, scale_color(fin_c, 0.75), xf([poly[0]])[0], xf([q])[0], 1)
    # 꼬리 색
    pygame.draw.polygon(canvas, fin_c, _xf(tail + [(tail_base + L * 0.02, 0)], cx, cy, angle, facing))
    # 주둥이 (청새치)
    if shape.get("bill"):
        bill = _xf([(-L / 2 + L * 0.02, -H * 0.1), (-L / 2 - L * 0.25, -H * 0.2)], cx, cy, angle, facing)
        pygame.draw.line(canvas, scale_color(base, 0.7), bill[0], bill[1], max(1, int(L / 45)))
    # 눈
    eye_r = max(1, int(L / (22 if shape.get("eye_big") else 40)))
    ex, ey = EYE_AT.get(form, (-0.4, -0.3))
    eye = xf([(L * ex, H * ey + _wave(form, 0.1, ph, 0) * H)])[0]
    ring = colors.get("eye") or ((255, 220, 90) if shape.get("eye_big") else (250, 250, 240))
    pygame.draw.circle(canvas, ring, eye, eye_r + 1)  # 광폭 변이: 붉은 눈
    pygame.draw.circle(canvas, (20, 20, 20), eye, eye_r)
    _head(canvas, xf, form, L, H, top, bot, base)
    if tier >= 2:
        _rarity_front(canvas, xf, L, H, tail_base, pts_body, eye, eye_r, tier, base,
                      RARITY_GLOW["phantom"] if phantom else None)
    # 수염 (잉어·메기)
    if shape.get("whiskers"):
        wc = scale_color(base, 0.6)
        for k in (0.3, 0.7):
            w = _xf([(-L / 2 + L * 0.02, H * 0.15), (-L / 2 - L * 0.06, H * (0.4 + k)),
                     (-L / 2 - L * 0.02, H * (0.8 + k))], cx, cy, angle, facing)
            pygame.draw.lines(canvas, wc, False, w, 1)
    # 등불 (아귀)
    if shape.get("lure"):
        lp = _xf([(-L * 0.4, -H * 0.9), (-L * 0.48, -H * 1.8), (-L * 0.55, -H * 1.6)], cx, cy, angle, facing)
        pygame.draw.lines(canvas, scale_color(base, 0.7), False, lp, 1)
        pygame.draw.circle(canvas, (255, 240, 150), lp[2], max(2, int(L / 40)))


GOLD = (255, 214, 90)
EYE_AT = {"flathead": (-0.43, -0.25), "arrow": (-0.41, -0.3), "bass": (-0.39, -0.38), "shark": (-0.39, -0.32),
          "blunthead": (-0.44, -0.55), "hump": (-0.42, -0.2), "lobe": (-0.4, -0.35), "tuna": (-0.38, -0.25)}


def _surf(pts, x: float) -> float:
    """윤곽선 pts(x 오름차순)에서 x 위치의 y."""
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        if x0 <= x <= x1:
            return lerp(y0, y1, (x - x0) / max(1e-6, x1 - x0))
    return pts[0][1] if x < pts[0][0] else pts[-1][1]


def _strip(pts, x0: float, x1: float, h0: float, h1: float, sign: int = -1, k: int = 6) -> list:
    """윤곽선을 따라 붙는 띠 지느러미: x0→x1, 높이 h0→h1 (sign -1 = 위로)."""
    out = [(x0, _surf(pts, x0))]
    for i in range(k + 1):
        u = i / k
        x = lerp(x0, x1, u)
        out.append((x, _surf(pts, x) + sign * lerp(h0, h1, u) * min(1.0, u / 0.18) ** 0.6))
    out.append((x1, _surf(pts, x1)))
    return out


def _fins(form, shape, L, H, top, bot, tail_base, ribbon, ph):
    """도형별 지느러미 (몸 기준 좌표). (몸 뒤 polygons, 몸 앞 polygons)."""
    T = lambda x: _surf(top, x)  # noqa: E731
    B = lambda x: _surf(bot, x)  # noqa: E731
    pec = [(-L * 0.26, H * 0.2), (-L * 0.17, H * 0.55), (-L * 0.13, H * 0.25)]
    anal = [(L * 0.12, B(L * 0.12) - H * 0.2), (L * 0.19, B(L * 0.19) + H * 0.35), (L * 0.25, B(L * 0.25) - H * 0.1)]
    if form == "flathead":
        return ([[(-L * 0.24, T(-L * 0.24)), (-L * 0.2, T(-L * 0.2) - H * 0.55), (-L * 0.12, T(-L * 0.12))],
                 _strip(bot, -L * 0.02, tail_base, H * 0.3, H * 0.25, 1)],
                [[(-L * 0.3, H * 0.25), (-L * 0.12, H * 0.85), (-L * 0.16, H * 0.3)]])
    if form == "arrow":
        return ([_strip(top, -L * 0.18, tail_base - L * 0.01, H * 0.35, H * 0.45),
                 _strip(bot, L * 0.02, tail_base - L * 0.01, H * 0.3, H * 0.4, 1)], [pec])
    if form == "bass":
        spiny = [(-L * 0.24, T(-L * 0.24))]
        for i in range(6):
            x = lerp(-L * 0.22, L * 0.0, i / 5)
            spiny += [(x, T(x) - H * (0.85 - i * 0.07)), (x + L * 0.018, T(x + L * 0.018) - H * 0.4)]
        spiny.append((L * 0.02, T(L * 0.02)))
        soft = _strip(top, L * 0.02, L * 0.24, H * 0.55, H * 0.35)
        return [spiny, soft, anal], [pec]
    if form in ("trout", "salmon"):
        dors = [(-L * 0.12, T(-L * 0.12)), (-L * 0.07, T(-L * 0.07) - H * 0.75), (L * 0.06, T(L * 0.06) - H * 0.35),
                (L * 0.05, T(L * 0.05))]
        adip = [(L * 0.22, T(L * 0.22)), (L * 0.25, T(L * 0.25) - H * 0.28), (L * 0.28, T(L * 0.28))]
        return [dors, adip, anal], [pec]
    if form == "disk":
        dors = _strip(top, -L * 0.12, L * 0.22, H * 0.12, H * 0.32)
        dors.insert(-1, (L * 0.33, T(L * 0.22) - H * 0.22))
        an = _strip(bot, L * 0.02, L * 0.22, H * 0.1, H * 0.28, 1)
        an.insert(-1, (L * 0.33, B(L * 0.22) + H * 0.2))
        return [dors, an], [[(-L * 0.2, H * 0.1), (-L * 0.05, H * 0.45), (-L * 0.08, H * 0.12)]]
    if form == "hump":  # 혹 뒤에서 시작해 둥글게 누운 등지느러미
        x0, x1 = -L * 0.12, L * 0.24
        dors = [(x0, T(x0))]
        for i in range(1, 9):
            u = i / 8
            x = lerp(x0, x1, u)
            dors.append((x + L * 0.03 * u, T(x) - H * 0.42 * math.sin(math.pi * min(1.0, u * 0.85 + 0.1)) ** 0.7))
        dors.append((x1, T(x1)))
        return [dors, anal], [pec]
    if form == "blunthead":
        return ([_strip(top, -L * 0.43, tail_base - L * 0.01, H * 0.3, H * 0.2),
                 _strip(bot, L * 0.02, tail_base - L * 0.01, H * 0.25, H * 0.2, 1)], [pec])
    if form == "tuna":
        d1 = [(-L * 0.16, T(-L * 0.16)), (-L * 0.11, T(-L * 0.11) - H * 0.55), (L * 0.0, T(L * 0.0))]
        d2 = [(L * 0.04, T(L * 0.04)), (L * 0.13, T(L * 0.04) - H * 1.1), (L * 0.11, T(L * 0.12))]
        a2 = [(L * 0.05, B(L * 0.05)), (L * 0.14, B(L * 0.05) + H * 1.0), (L * 0.12, B(L * 0.13))]
        return [d1, d2, a2], [[(-L * 0.27, H * 0.0), (-L * 0.05, H * 0.15), (-L * 0.22, H * 0.25)]]
    if form == "shark":
        d1 = [(-L * 0.08, T(-L * 0.08)), (L * 0.04, T(L * 0.0) - H * 1.45), (L * 0.1, T(L * 0.1) - H * 0.1),
              (L * 0.14, T(L * 0.14))]
        d2 = [(L * 0.24, T(L * 0.24)), (L * 0.28, T(L * 0.26) - H * 0.4), (L * 0.31, T(L * 0.31))]
        a2 = [(L * 0.22, B(L * 0.22)), (L * 0.26, B(L * 0.24) + H * 0.35), (L * 0.29, B(L * 0.29))]
        pect = [(-L * 0.24, B(-L * 0.24) - H * 0.2), (-L * 0.06, B(-L * 0.1) + H * 1.0), (-L * 0.13, B(-L * 0.13))]
        return [d1, d2, a2], [pect]
    if form == "lobe":
        def leaf(x, y_surf, sign, h):
            """살덩이 자루 + 뒤로 누운 둥근 잎 (실러캔스 지느러미)."""
            out = [(x - L * 0.015, y_surf), (x - L * 0.01, y_surf + sign * h * 0.35)]
            for i in range(9):
                a = math.pi * i / 8
                out.append((x + L * 0.03 - math.cos(a) * L * 0.045 + math.sin(a) * L * 0.02,
                            y_surf + sign * (h * 0.35 + math.sin(a) * h * 0.65)))
            out += [(x + L * 0.02, y_surf + sign * h * 0.3), (x + L * 0.02, y_surf)]
            return out
        return ([leaf(-L * 0.08, T(-L * 0.08), -1, H * 0.9), leaf(L * 0.18, T(L * 0.18), -1, H * 0.8),
                 leaf(L * 0.18, B(L * 0.18), 1, H * 0.8), leaf(-L * 0.02, B(-L * 0.02), 1, H * 0.85)],
                [leaf(-L * 0.24, H * 0.3, 1, H * 0.95)])
    if form == "flyer":
        w = math.sin(ph * 6.0) * H * 0.25
        wing = [(-L * 0.24, -H * 0.05), (L * 0.18, -H * 2.3 + w), (L * 0.36, -H * 1.5 + w), (-L * 0.02, H * 0.2)]
        dors = [(L * 0.14, T(L * 0.14)), (L * 0.18, T(L * 0.14) - H * 0.6), (L * 0.24, T(L * 0.24))]
        return [dors, [(p[0], -p[1] * 0.6 + H * 0.4) for p in wing], anal], [wing]
    if form == "serpent":
        crest = [(-L * 0.36, T(-L * 0.36))]
        k = 14
        for i in range(k + 1):
            x = lerp(-L * 0.34, tail_base - L * 0.01, i / k)
            crest.append((x, T(x) - H * (0.9 if i % 2 == 0 else 0.45) * lerp(1.2, 0.6, i / k)))
        crest.append((tail_base, T(tail_base)))
        return [crest, _strip(bot, L * 0.05, tail_base - L * 0.01, H * 0.3, H * 0.25, 1)], [pec]
    # spindle (일반·고급 기본 틀): fish.json dorsal 값
    dorsal_type = shape.get("dorsal", "normal")
    if dorsal_type == "long":
        dorsal = [(-L * 0.38, -H * 0.7), (-L * 0.3, -H * 1.45), (L * 0.1, -H * 1.3), (L * 0.28, -H * 0.9),
                  (L * 0.3, -H * 0.4)]
    elif dorsal_type == "crest":
        dorsal = [(-L * 0.45, -H * 0.6), (-L * 0.4, -H * 3.2), (-L * 0.3, -H * 1.6), (L * 0.35, -H * 1.5),
                  (L * 0.4, -H * 0.6)]
    else:
        dorsal = [(-L * 0.16, -H * 0.8), (-L * 0.07, -H * 1.3), (L * 0.06, -H * 1.05), (L * 0.16, -H * 1.25),
                  (L * 0.25, -H * 0.55)]
    back = [dorsal] if ribbon else [dorsal, [(L * 0.12, H * 0.7), (L * 0.19, H * 1.05), (L * 0.25, H * 0.5)]]
    return back, [pec]


def _head(canvas, xf, form, L, H, top, bot, base) -> None:
    """입·아가미 (도형별)."""
    dark, line = scale_color(base, 0.55), scale_color(base, 0.7)
    sx = -L / 2
    if form == "shark":
        for i in range(5):  # 아가미 구멍 다섯
            x = -L * 0.3 + i * L * 0.025
            pygame.draw.line(canvas, line, *xf([(x, -H * 0.25), (x - L * 0.01, H * 0.35)]), 1)
        pygame.draw.lines(canvas, dark, False, xf([(sx + L * 0.06, H * 0.35), (-L * 0.38, H * 0.55), (-L * 0.34, H * 0.45)]), 1)
        return
    if form == "bass":  # 큰 입 + 튀어나온 아래턱
        pygame.draw.lines(canvas, dark, False, xf([(sx - L * 0.01, -H * 0.05), (-L * 0.36, H * 0.05),
                                                    (-L * 0.38, H * 0.2)]), 1)
    elif form == "salmon":  # 갈고리 턱
        pygame.draw.polygon(canvas, scale_color(base, 0.8), xf([(sx + L * 0.02, H * 0.15), (sx - L * 0.03, H * 0.0),
                                                                 (sx - L * 0.02, -H * 0.25), (sx + L * 0.05, H * 0.1)]))
        pygame.draw.line(canvas, dark, *xf([(sx + L * 0.01, H * 0.08), (-L * 0.4, H * 0.22)]), 1)
    elif form == "flathead":  # 넓은 입
        pygame.draw.line(canvas, dark, *xf([(sx, H * 0.15), (-L * 0.41, H * 0.3)]), max(1, int(L / 60)))
    elif form == "hump":  # 아래로 향한 작은 입
        pygame.draw.line(canvas, dark, *xf([(sx + L * 0.005, H * 0.12), (-L * 0.45, H * 0.3)]), 1)
    else:
        pygame.draw.line(canvas, dark, *xf([(sx + L * 0.01, H * 0.05), (-L * 0.42, H * 0.25)]), 1)
    gx = -L * (0.26 if form in ("bass", "lobe") else 0.33)
    gill = xf([(gx, _surf(top, gx) * 0.75), (gx + L * 0.03, 0), (gx, _surf(bot, gx) * 0.75)])
    pygame.draw.lines(canvas, line, False, gill, 1)


def _rarity_back(canvas, xf, L, H, top, tail, wag, tier, fin_c, base, stripe) -> None:
    """전설 몸 뒤 장식: 꼬리 끝에서 흐르는 꼬리깃 두 가닥 (실루엣으로도 보임)."""
    ph = pygame.time.get_ticks() / 1000.0
    tip = lerp_color(fin_c, GOLD, 0.5) if fin_c != base else fin_c
    reach = L * 0.2
    for k, (x0, y0) in enumerate((tail[0], tail[-1])):
        pts = []
        for j in range(7):
            u = j / 6
            pts.append((x0 + reach * u, y0 * (1 + 0.15 * u) + math.sin(ph * 3 + u * 3 + k * 1.5) * H * 0.18 * u
                        + wag * H * 0.3 * u))
        pygame.draw.lines(canvas, tip, False, xf(pts), 1)


def _aura(canvas, pts_body, glow, k: float) -> None:
    """전설: 몸 둘레 은은한 빛 (몸보다 조금 큰 윤곽을 더하기 합성 → 어두운 곳에서도 그림자 아닌 빛으로 보임)."""
    xs, ys = [p[0] for p in pts_body], [p[1] for p in pts_body]
    mx, my = sum(xs) / len(xs), sum(ys) / len(ys)
    pad = 3
    x0, y0 = int(min(xs)) - pad - 2, int(min(ys)) - pad - 2
    surf = pygame.Surface((int(max(xs)) - x0 + pad + 3, int(max(ys)) - y0 + pad + 3))
    surf.fill((0, 0, 0))
    for grow, a in ((pad, 0.12 + 0.08 * k), (pad * 0.5, 0.12 + 0.1 * k)):
        pts = []
        for x, y in pts_body:
            dx, dy = x - mx, y - my
            d = max(1e-6, math.hypot(dx, dy))
            pts.append((x + dx / d * grow - x0, y + dy / d * grow - y0))
        col = tuple(int(c * a) for c in glow)
        pygame.draw.polygon(surf, col, pts)
    canvas.blit(surf, (x0, y0), special_flags=pygame.BLEND_RGB_ADD)


def _rarity_front(canvas, xf, L, H, tail_base, pts_body, eye, eye_r, tier, base, glow_override=None) -> None:
    """몸 위 장식. 희귀: 푸른 테 + 등 비늘 반짝임. 전설: 금빛 테(맥동) + 비늘 무늬 + 빛나는 눈."""
    ph = pygame.time.get_ticks() / 1000.0
    glow = glow_override or RARITY_GLOW["legend" if tier >= 3 else "rare"]
    if tier >= 3 and L >= 90:  # 작게 그릴 땐 비늘 무늬가 잡음이 돼서 뺌
        sc = lerp_color(base, (255, 255, 255), 0.22)
        step = L * 0.075
        x = -L * 0.27
        while x < tail_base - L * 0.12:
            for y in (-H * 0.35, H * 0.15):
                a, b, c = xf([(x + step * 0.45, y - H * 0.18), (x, y), (x + step * 0.45, y + H * 0.18)])
                pygame.draw.lines(canvas, sc, False, (a, b, c), 1)
            x += step
    k = 0.5 + 0.5 * math.sin(ph * (3.2 if tier >= 3 else 2.0))
    rim = lerp_color(base, glow, (0.55 + 0.4 * k) if tier >= 3 else 0.5)
    pygame.draw.polygon(canvas, rim, pts_body, 1)
    # 등 비늘 반짝임: 머리 → 꼬리로 빛이 훑고 지나감
    n = 6
    hot = (ph * 2.2) % (n + 3)
    for i in range(n):
        x = -L * 0.24 + i * (tail_base + L * 0.14) / n
        p = xf([(x, -H * 0.5)])[0]
        lit = max(0.0, 1 - abs(i - hot))
        col = lerp_color(lerp_color(base, (255, 255, 255), 0.35), glow if tier >= 3 else (255, 255, 255), lit)
        r = 1 + (1 if lit > 0.5 and L >= 60 else 0)
        canvas.fill(col, (int(p[0]) - r // 2, int(p[1]) - r // 2, r, r))
    if tier >= 3:
        pygame.draw.circle(canvas, lerp_color(GOLD, (255, 255, 255), k * 0.5), eye, eye_r + 2, 1)


_BOUNDS: dict = {}


def fish_bounds(shape: dict) -> tuple[float, float, float, float]:
    """길이 1 기준 물고기 그림 범위 (왼, 위, 폭, 높이; 중심 기준). 지느러미·꼬리깃·주둥이까지 포함."""
    key = repr(sorted(shape.items()))
    if key not in _BOUNDS:
        ref = 100
        surf = pygame.Surface((ref * 4, ref * 4), pygame.SRCALPHA)
        for wag in (-1.0, 0.0, 1.0):
            draw_fish_side(surf, ref * 2, ref * 2, ref, 0.0, fish_colors({}), -1, silhouette=(255, 255, 255),
                           tail_wag=wag, shape=shape)
        r = surf.get_bounding_rect()
        pad = 2
        _BOUNDS[key] = ((r.x - pad - ref * 2) / ref, (r.y - pad - ref * 2) / ref, (r.w + pad * 2) / ref,
                        (r.h + pad * 2) / ref)
    return _BOUNDS[key]


def draw_fish_fit(canvas, rect, fish: dict, max_len: float, silhouette=None, tail_wag: float = 0.0) -> None:
    """rect 안에 다 들어가게 (최대 max_len) 가운데 맞춰 옆모습을 그린다. 도감 칸·상점 상세용."""
    rect = pygame.Rect(rect)
    shape = fish_shape(fish)
    bx, by, bw, bh = fish_bounds(shape)
    L = min(max_len, rect.w / bw, rect.h / bh)
    cx = rect.centerx - (bx + bw / 2) * L
    cy = rect.centery - (by + bh / 2) * L
    old = canvas.get_clip()
    canvas.set_clip(rect.clip(old) if old else rect)
    draw_fish_side(canvas, cx, cy, L, 0.0, fish_colors(fish), -1, silhouette=silhouette, tail_wag=tail_wag,
                   shape=shape)
    canvas.set_clip(old)


def draw_manta(canvas, cx, cy, length, angle, colors, facing, silhouette=None, tail_wag: float = 0.0) -> None:
    """가오리 (옆에서 본 모습): 넓은 날개를 펄럭이는 마름모 + 가는 꼬리."""
    L = length
    body = silhouette or colors["body"]
    belly = silhouette or colors["belly"]
    fin = silhouette or colors["fin"]
    flap = math.sin(tail_wag * 2) * 0.12
    wing = [(L * 0.45, 0), (0, -L * (0.32 + flap)), (-L * 0.25, -L * 0.05), (-L * 0.25, L * 0.05), (0, L * (0.18 - flap * 0.5))]
    pygame.draw.polygon(canvas, body, _xf(wing, cx, cy, angle, facing))
    pygame.draw.polygon(canvas, belly, _xf([(L * 0.4, L * 0.02), (0, L * 0.16), (-L * 0.2, L * 0.04)], cx, cy, angle, facing))
    tail = [(-L * 0.25, 0), (-L * 0.62, tail_wag * L * 0.04)]
    pygame.draw.lines(canvas, fin, False, _xf(tail, cx, cy, angle, facing), max(1, int(L / 60)))
    if not silhouette:
        eye = _xf([(L * 0.3, -L * 0.04)], cx, cy, angle, facing)[0]
        pygame.draw.circle(canvas, (20, 20, 25), (int(eye[0]), int(eye[1])), max(1, int(L / 45)))


def draw_squid(canvas, cx, cy, length, angle, colors, facing, silhouette=None, tail_wag: float = 0.0) -> None:
    """대왕오징어: 몸통(외투막) + 지느러미 + 다리."""
    L = length
    H = L * 0.13
    col = silhouette or colors["body"]
    dark = silhouette or scale_color(colors["body"], 0.75)
    # 외투막: 머리가 오른쪽(+x) 끝이 뾰족
    mantle = [(-L * 0.05, -H), (L * 0.3, -H * 0.8), (L * 0.5, 0), (L * 0.3, H * 0.8), (-L * 0.05, H)]
    fin = [(L * 0.32, -H * 0.7), (L * 0.42, -H * 1.6), (L * 0.5, 0), (L * 0.42, H * 1.6), (L * 0.32, H * 0.7)]
    pygame.draw.polygon(canvas, dark, _xf(fin, cx, cy, angle, facing))
    # 다리 (왼쪽으로 늘어짐)
    for i in range(6):
        y0 = -H * 0.7 + i * H * 0.28
        w = math.sin(tail_wag * 2 + i) * H * 0.4
        pts = _xf([(-L * 0.08, y0), (-L * 0.28, y0 * 1.3 + w), (-L * 0.5, y0 * 1.6 - w)], cx, cy, angle, facing)
        pygame.draw.lines(canvas, dark, False, pts, max(1, int(L / 70)))
    pygame.draw.polygon(canvas, col, _xf(mantle, cx, cy, angle, facing))
    head = _xf([(-L * 0.08, 0)], cx, cy, angle, facing)[0]
    pygame.draw.circle(canvas, col, head, int(H * 0.9))
    if silhouette is None:
        eye = _xf([(-L * 0.08, -H * 0.2)], cx, cy, angle, facing)[0]
        pygame.draw.circle(canvas, (250, 240, 210), eye, max(2, int(L / 30)))
        pygame.draw.circle(canvas, (20, 20, 20), eye, max(1, int(L / 50)))


# ───────────────────────── 점프 ─────────────────────────

def draw_jump(canvas, pal, cam, fish: dict, size_cm: float, x: float, z: float, phase: float,
              facing: int, height_m: float) -> tuple[float, float] | None:
    """점프 중인 물고기 실루엣. 화면 위치 반환."""
    h = 4 * height_m * phase * (1 - phase)
    p = cam.project(x, z, h)
    if p is None:
        return None
    sx, sy, s = p
    length = max(12.0, size_cm / 100 * s * 1.8)
    angle = lerp(-0.9, 0.9, phase) * (-facing)
    colors = fish_colors(fish)
    # 노을·밤엔 실루엣처럼 어둡게
    dark = lerp_color(colors["body"], pal["rod"], 0.55)
    shape = fish_shape(fish)
    if length < 26:
        draw_fish_side(canvas, sx, sy, length, angle, colors, facing, silhouette=dark, shape=shape)
    else:
        draw_fish_side(canvas, sx, sy, length, angle, colors, facing, shape=shape)
    return sx, sy


# ───────────────────────── 뜰채 단계 ─────────────────────────

def draw_net_scene(canvas, pal, fish: dict, size_cm: float, pose: float, still: bool, t: float,
                   net_anim: float, mouse) -> tuple[float, float]:
    w, h = canvas.get_size()
    length = clamp(size_cm * 3.4, 80, 210)
    cx = w / 2 + pose * 46
    cy = h * 0.74 + (0 if still else math.sin(t * 20) * 3)
    angle = 0.0 if still else pose * 0.35
    colors = fish_colors(fish)
    # 물 튀김 고리
    water_ring = lerp_color(pal["wave_light"], (255, 255, 255), 0.3)
    pygame.draw.ellipse(canvas, pal["wave_dark"], (cx - length * 0.62, cy + 4, length * 1.24, 16))
    pygame.draw.ellipse(canvas, water_ring, (cx - length * 0.62, cy + 4, length * 1.24, 16), 1)
    draw_fish_side(canvas, cx, cy, length, angle, colors, facing=-1,
                   tail_wag=0.0 if still else math.sin(t * 30), shape=fish_shape(fish))
    # 수면 (몸 아래쪽은 물에 잠김)
    water = lerp_color(pal["water_top"], pal["water_bottom"], 0.85)
    canvas.fill(water, (0, int(cy + length * 0.1), w, h))
    for i in range(6):
        y = int(cy + length * 0.1 + 3 + i * 6)
        canvas.fill(pal["wave_light"], (int((t * 30 + i * 50) % 80) + i * 60, y, 22, 1))
    if still:
        # 멈춘 순간 반짝 (몸 위 하이라이트)
        hl = (255, 255, 255)
        canvas.fill(hl, (int(cx - length * 0.15), int(cy - length * 0.1), int(length * 0.25), 1))
    # 뜰채
    if net_anim > 0:
        k = 1 - net_anim / 0.3
        nx = lerp(w * 0.85, cx, k)
        ny = lerp(h + 30, cy, k)
        draw_net(canvas, pal, nx, ny, length * 0.45)
    else:
        draw_net(canvas, pal, w * 0.86, h + 18, 70)
    return cx, cy


def draw_net(canvas, pal, x: float, y: float, radius: float) -> None:
    """뜰채 (파이팅 '뜰채!' 단계). 색은 장착 뜰채 티어 외형 (pal net_*, 없으면 릴 색)."""
    frame = pal.get("net_frame") or scale_color(pal["reel"], 1.1)
    mesh = lerp_color(pal.get("net_mesh") or pal["reel"], pal["water_bottom"], 0.35)
    handle = pal.get("net_handle") or frame
    rect = pygame.Rect(0, 0, radius * 2, radius * 0.8)
    rect.center = (x, y)
    if pal.get("net_glow"):
        pygame.draw.ellipse(canvas, lerp_color(pal["water_bottom"], pal["net_glow"], 0.6), rect.inflate(6, 4), 2)
    for i in range(1, 6):
        xx = rect.left + rect.width * i / 6
        pygame.draw.line(canvas, mesh, (xx, rect.top + 2), (xx - 4, rect.bottom + radius * 0.4), 1)
    pygame.draw.line(canvas, handle, rect.midright, (x + radius * 1.6, y + radius * 1.4), 3)
    pygame.draw.ellipse(canvas, frame, rect, 2)
    if pal.get("net_trim"):
        pygame.draw.arc(canvas, pal["net_trim"], rect, math.pi, math.tau, 1)


# ───────────────────────── 획득 컷 ─────────────────────────

ONE_HAND_CM = 30  # 이보다 작으면 한 손으로 쥔다


def catch_length(size_cm: float, w: int = 480) -> float:
    """획득 컷 물고기 길이(px): 실제 크기에 비례 — 30cm까지 4px/cm, 30~100cm 1px/cm, 그 위 0.55px/cm (화면 안으로)."""
    cm = max(1.0, size_cm)
    if cm <= 30:
        px = 4.0 * cm
    elif cm <= 100:
        px = 120 + (cm - 30) * 1.0
    else:
        px = 190 + (cm - 100) * 0.55
    return clamp(px, 26, w * 0.88)


def draw_catch_cut(canvas, pal, result: dict, t: float) -> None:
    w, h = canvas.get_size()
    fish = result["fish"]
    rank = result["rank"]
    rc = RANK_COLORS[rank]
    # 배경 어둡게 + 회전하는 빛살
    shade = pygame.Surface((w, h), pygame.SRCALPHA)
    shade.fill((8, 10, 24, 190))
    canvas.blit(shade, (0, 0))
    cx, cy = w // 2, 112
    tier = {"common": 0, "uncommon": 1, "rare": 2, "phantom": 2, "legend": 3}.get(fish["rarity"], 0)
    glow = RARITY_GLOW[fish["rarity"]]
    phantom = fish["rarity"] == "phantom"
    if phantom:
        # 환상: 배경이 보랏빛으로 + 보라 테두리 카드 (두 겹, 맥동)
        vio = _opaque((w, h))
        vio.fill((60, 24, 96))
        vio.set_alpha(120)
        canvas.blit(vio, (0, 0))
        k = 0.6 + 0.4 * math.sin(t * 3)
        pygame.draw.rect(canvas, lerp_color((90, 50, 140), (210, 150, 255), k), (6, 6, w - 12, h - 12), 2)
        pygame.draw.rect(canvas, (120, 70, 180), (10, 10, w - 20, h - 20), 1)
        for x0, y0 in ((6, 6), (w - 7, 6), (6, h - 7), (w - 7, h - 7)):
            pygame.draw.polygon(canvas, (225, 180, 255), [(x0, y0 - 4), (x0 + 4, y0), (x0, y0 + 4), (x0 - 4, y0)])
    if tier >= 3:
        # 전설: 배경 전체가 금빛으로 물듦
        gold = _opaque((w, h))
        gold.fill((90, 60, 10))
        gold.set_alpha(110)
        canvas.blit(gold, (0, 0))
    ray_col = rc if tier < 2 else lerp_color(rc, glow, 0.6)
    ray = lerp_color((40, 46, 80), ray_col, 0.25 + 0.12 * tier)
    for i in range(12 + 4 * tier):
        a = t * 0.4 + i * math.tau / (12 + 4 * tier)
        pts = [(cx, cy),
               (cx + math.cos(a) * 300, cy + math.sin(a) * 300),
               (cx + math.cos(a + 0.12) * 300, cy + math.sin(a + 0.12) * 300)]
        pygame.draw.polygon(canvas, ray, pts)
    if tier >= 2:
        pygame.draw.circle(canvas, lerp_color((40, 46, 80), glow, 0.45), (cx, cy), 70 + int(4 * math.sin(t * 3)))

    # 실제 크기에 비례 (손은 실제 크기 그대로라 크기 차이가 한눈에 보인다): 30cm까지 4px/cm, 그 위로는 점점 눌러 담음
    length = catch_length(result["size"], w)
    one_hand = result["size"] < ONE_HAND_CM
    # 위에서 떨어져 손에 탁 안김 (0~0.3초), 안기는 순간 살짝 눌림 — 작은 건 손에서 파닥
    drop = clamp(t / 0.3, 0, 1)
    fall_y = lerp(-90, 0, drop * drop)
    squash = 0.12 * math.sin(clamp((t - 0.3) / 0.18, 0, 1) * math.pi) if t > 0.3 else 0.0
    bob = math.sin(t * 2.5) * 2 if t > 0.5 else 0.0
    flap = math.sin(t * 22) * 0.18 * math.exp(-max(0.0, t - 0.3) * 1.5) if one_hand else 0.0
    colors = fish_colors(fish)
    skin, shadow = pal["hand"], pal["hand_shadow"]
    if pal["hand"][0] < 90:  # 밤·노을엔 손이 너무 어두우니 밝힘
        skin, shadow = (225, 175, 140), (180, 125, 100)
    rise = (1 - smoothstep(t / 0.28)) * 70
    fy = cy + bob + fall_y
    if phantom:
        # 보랏빛 잔상: 좌우로 흔들리며 옅어지는 실루엣 두 겹
        for i, dx in enumerate((-1, 1)):
            off = dx * (6 + 4 * math.sin(t * 2 + i))
            draw_fish_side(canvas, cx + off, fy - 2, length * 1.04, 0.0, colors, facing=-1,
                           silhouette=lerp_color((60, 30, 100), (190, 120, 255), 0.45 + 0.2 * math.sin(t * 3 + i)),
                           shape=fish_shape(fish))
    if one_hand:
        # 한 손: 손바닥이 배를 받치고, 손가락이 몸통을 감싸 쥠 (엄지는 위쪽)
        body_h = length * (fish.get("shape") or {}).get("height", 0.17)
        hx, hy = cx + 4, fy + body_h * 0.5 + 5 + rise  # 손바닥은 배 아래
        sleeve = [(hx - 9, hy + 10), (hx + 11, hy + 10), (hx + 50, h + 60), (hx + 26, h + 60)]
        pygame.draw.polygon(canvas, (60, 80, 120), sleeve)
        pygame.draw.line(canvas, (44, 60, 94), (hx + 8, hy + 12), (hx + 44, h), 2)
        pygame.draw.ellipse(canvas, shadow, (hx - 13, hy - 2, 26, 18))
        pygame.draw.ellipse(canvas, skin, (hx - 13, hy - 4, 26, 16))  # 손바닥 (물고기 뒤)
        draw_fish_side(canvas, cx, fy, length * (1 + squash), flap, colors, facing=-1,
                       tail_wag=math.sin(t * (18 if t < 0.8 else 8)) * 0.7, shape=fish_shape(fish))
        # 앞쪽 손가락 네 개가 몸통 아래쪽을 감쌈
        top = fy + body_h * 0.05 + rise
        for i in range(4):
            fx = hx - 8 + i * 5
            fl = hy - top + 2
            pygame.draw.ellipse(canvas, shadow, (fx - 2, top + 1, 5, fl))
            pygame.draw.ellipse(canvas, skin, (fx - 3, top, 5, fl))
        # 엄지: 위쪽에서 걸침
        pygame.draw.ellipse(canvas, shadow, (hx - 3, fy - body_h * 0.62 + rise, 10, 7))
        pygame.draw.ellipse(canvas, skin, (hx - 4, fy - body_h * 0.66 + rise, 10, 6))
    else:
        body_h = length * (fish.get("shape") or {}).get("height", 0.17)
        draw_fish_side(canvas, cx, fy, length * (1 + squash), 0.0, colors, facing=-1,
                       tail_wag=math.sin(t * (14 if t < 0.6 else 6)) * 0.5, shape=fish_shape(fish))
        # 두 손 (아래에서 올라와 받쳐 듦) — 손 크기는 그대로, 간격만 물고기 길이에 맞춤
        spread = clamp(length * 0.21, 26, 150)
        for hx in (cx - spread, cx + spread * 0.92):
            hy = cy + bob + body_h * 0.62 + rise + squash * 20  # 배 아래를 받침
            pygame.draw.ellipse(canvas, shadow, (hx - 15, hy - 4, 30, 18))
            pygame.draw.ellipse(canvas, skin, (hx - 15, hy - 7, 30, 15))
            for i in range(4):
                pygame.draw.line(canvas, shadow, (hx - 10 + i * 6, hy - 6), (hx - 10 + i * 6, hy - 1), 1)
            out = -1 if hx < cx else 1
            sleeve = [(hx - 12, hy + 6), (hx + 12, hy + 6), (hx + 12 + out * 34, h + 60), (hx - 12 + out * 34, h + 60)]
            pygame.draw.polygon(canvas, (60, 80, 120), sleeve)
            pygame.draw.line(canvas, (44, 60, 94), (hx + out * 10, hy + 8), (hx + out * 44, h), 2)
    # 희귀 이상: 별 반짝임 / 전설: 금가루 + 금테
    if tier >= 2:
        for i in range(10 + 6 * tier):
            a = i * 2.39 + t * 0.3
            rr = 70 + (i * 23) % 90
            tw = 0.5 + 0.5 * math.sin(t * 7 + i * 1.3)
            sx, sy = int(cx + math.cos(a) * rr * 1.4), int(cy + math.sin(a) * rr * 0.8)
            r = int(1 + tw * (1 + tier))
            col = lerp_color(glow, (255, 255, 255), tw)
            pygame.draw.line(canvas, col, (sx - r, sy), (sx + r, sy), 1)
            pygame.draw.line(canvas, col, (sx, sy - r), (sx, sy + r), 1)
    if tier >= 3:
        for i in range(60):
            x = (i * 73 + int(math.sin(i) * 40)) % w
            y = (t * (40 + i % 5 * 15) + i * 37) % (h + 20) - 10
            tw = 0.5 + 0.5 * math.sin(t * 8 + i)
            canvas.fill(lerp_color((200, 150, 40), (255, 240, 170), tw), (x, int(y), 2, 2 if tw > 0.5 else 1))
        pulse = 0.6 + 0.4 * math.sin(t * 4)
        frame = lerp_color((150, 100, 20), (255, 220, 110), pulse)
        pygame.draw.rect(canvas, frame, (2, 2, w - 4, h - 4), 2)
        pygame.draw.rect(canvas, lerp_color(frame, (60, 40, 0), 0.5), (6, 6, w - 12, h - 12), 1)
    # 연출에서 넘어온 하얀 섬광이 걷힘
    if t < 0.25:
        fl = _opaque((w, h))
        fl.fill((255, 255, 250))
        fl.set_alpha(int(255 * (1 - t / 0.25)))
        canvas.blit(fl, (0, 0))
