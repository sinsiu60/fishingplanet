"""물고기 그리기: 옆모습(점프·뜰채·획득 컷), 획득 컷 전체 연출."""
import math

import pygame

from src.core.mathutil import clamp, lerp, lerp_color, scale_color, smoothstep

DEFAULT_COLORS = {"body": [120, 130, 120], "belly": [220, 220, 210], "fin": [90, 100, 90], "stripe": None}
RANK_COLORS = {"S": (255, 214, 90), "A": (150, 200, 255), "B": (140, 220, 150), "C": (190, 190, 190)}
RARITY_GLOW = {"common": (255, 245, 210), "uncommon": (150, 255, 170), "rare": (140, 200, 255),
               "legend": (255, 210, 90)}


def fish_colors(fish: dict) -> dict:
    c = dict(DEFAULT_COLORS)
    c.update(fish.get("colors") or {})
    return {k: (tuple(v) if v else None) for k, v in c.items()}


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
    L = length
    H = L * shape.get("height", 0.17)
    tail_type = shape.get("tail", "fork")
    ribbon = tail_type == "ribbon"
    body_frac = 0.92 if ribbon else 0.82 if tail_type == "round" else 0.8
    top, bot = [], []
    n = 12
    tail_base = -L / 2 + L * body_frac
    for i in range(n + 1):
        u = i / n
        x = -L / 2 + u * L * body_frac
        if ribbon:
            prof = min(1.0, u * 6) ** 0.6
            taper = lerp(1.0, 0.25, clamp((u - 0.6) / 0.4, 0, 1))
        else:
            prof = math.sin(math.pi * clamp(u * 0.92 + 0.06, 0, 1)) ** 0.75
            taper = lerp(1.0, 0.35, clamp((u - 0.55) / 0.45, 0, 1))
        h = H * max(0.2, prof) * taper
        top.append((x, -h))
        bot.append((x, h * 1.08))
    wag = tail_wag * H * 0.6
    tx = L / 2
    if tail_type == "round":
        tail = [(tail_base + L * 0.1, -H * 0.55 + wag), (tx, -H * 0.2 + wag), (tx, H * 0.25 + wag),
                (tail_base + L * 0.1, H * 0.6 + wag)]
    elif tail_type == "lunate":
        tail = [(tx + L * 0.02, -H * 1.05 + wag), (tail_base + L * 0.1, wag * 0.5), (tx + L * 0.02, H * 1.05 + wag)]
    elif ribbon:
        tail = [(tx, -H * 0.15 + wag), (tx, H * 0.15 + wag)]
    else:
        tail = [(tx, -H * 0.85 + wag), (tx - L * 0.06, wag * 0.5), (tx, H * 0.85 + wag)]
    body = top + tail + bot[::-1]
    pts_body = _xf(body, cx, cy, angle, facing)

    if silhouette is not None:
        pygame.draw.polygon(canvas, silhouette, pts_body)
        fin = [(-L * 0.05, -H * 0.9), (L * 0.15, -H * 1.5), (L * 0.22, -H * 0.7)]
        pygame.draw.polygon(canvas, silhouette, _xf(fin, cx, cy, angle, facing))
        if shape.get("bill"):
            pygame.draw.line(canvas, silhouette, *_xf([(-L / 2, 0), (-L / 2 - L * 0.22, -H * 0.1)], cx, cy, angle,
                                                      facing), max(1, int(L / 50)))
        return

    base, belly, fin_c, stripe = colors["body"], colors["belly"], colors["fin"], colors["stripe"]
    # 등지느러미 (몸 뒤에)
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
    pygame.draw.polygon(canvas, fin_c, _xf(dorsal, cx, cy, angle, facing))
    # 뒷지느러미
    if not ribbon:
        anal = [(L * 0.12, H * 0.7), (L * 0.19, H * 1.05), (L * 0.25, H * 0.5)]
        pygame.draw.polygon(canvas, fin_c, _xf(anal, cx, cy, angle, facing))
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
    # 가슴지느러미
    pec = [(-L * 0.26, H * 0.2), (-L * 0.17, H * 0.55), (-L * 0.13, H * 0.25)]
    pygame.draw.polygon(canvas, fin_c, _xf(pec, cx, cy, angle, facing))
    # 꼬리 색
    pygame.draw.polygon(canvas, fin_c, _xf(tail + [(tail_base + L * 0.02, 0)], cx, cy, angle, facing))
    # 주둥이 (청새치)
    if shape.get("bill"):
        bill = _xf([(-L / 2 + L * 0.02, -H * 0.1), (-L / 2 - L * 0.25, -H * 0.2)], cx, cy, angle, facing)
        pygame.draw.line(canvas, scale_color(base, 0.7), bill[0], bill[1], max(1, int(L / 45)))
    # 눈
    eye_r = max(1, int(L / (22 if shape.get("eye_big") else 40)))
    eye = _xf([(-L * 0.4, -H * 0.3)], cx, cy, angle, facing)[0]
    pygame.draw.circle(canvas, (255, 220, 90) if shape.get("eye_big") else (250, 250, 240), eye, eye_r + 1)
    pygame.draw.circle(canvas, (20, 20, 20), eye, eye_r)
    mouth = _xf([(-L / 2 + L * 0.01, H * 0.05), (-L * 0.42, H * 0.25)], cx, cy, angle, facing)
    pygame.draw.line(canvas, scale_color(base, 0.55), mouth[0], mouth[1], 1)
    # 아가미 선
    gill = _xf([(-L * 0.33, -H * 0.55), (-L * 0.3, 0), (-L * 0.33, H * 0.6)], cx, cy, angle, facing)
    pygame.draw.lines(canvas, scale_color(base, 0.7), False, gill, 1)
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
    shape = fish.get("shape")
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
                   tail_wag=0.0 if still else math.sin(t * 30), shape=fish.get("shape"))
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
    frame = scale_color(pal["reel"], 1.1)
    mesh = lerp_color(pal["reel"], pal["water_bottom"], 0.4)
    rect = pygame.Rect(0, 0, radius * 2, radius * 0.8)
    rect.center = (x, y)
    for i in range(1, 6):
        xx = rect.left + rect.width * i / 6
        pygame.draw.line(canvas, mesh, (xx, rect.top + 2), (xx - 4, rect.bottom + radius * 0.4), 1)
    pygame.draw.ellipse(canvas, frame, rect, 2)
    pygame.draw.line(canvas, frame, rect.midright, (x + radius * 1.6, y + radius * 1.4), 3)


# ───────────────────────── 획득 컷 ─────────────────────────

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
    tier = {"common": 0, "uncommon": 1, "rare": 2, "legend": 3}.get(fish["rarity"], 0)
    glow = RARITY_GLOW[fish["rarity"]]
    if tier >= 3:
        # 전설: 배경 전체가 금빛으로 물듦
        gold = pygame.Surface((w, h))
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

    lo, hi = fish["size_cm"]
    k = clamp((result["size"] - lo) / max(1, hi - lo), 0, 1.2)
    length = lerp(150, 240, k)
    # 위에서 떨어져 두 손에 탁 안김 (0~0.3초), 안기는 순간 살짝 눌림
    drop = clamp(t / 0.3, 0, 1)
    fall_y = lerp(-90, 0, drop * drop)
    squash = 0.12 * math.sin(clamp((t - 0.3) / 0.18, 0, 1) * math.pi) if t > 0.3 else 0.0
    bob = math.sin(t * 2.5) * 2 if t > 0.5 else 0.0
    colors = fish_colors(fish)
    draw_fish_side(canvas, cx, cy + bob + fall_y, length * (1 + squash), 0.0, colors, facing=-1,
                   tail_wag=math.sin(t * (14 if t < 0.6 else 6)) * 0.5, shape=fish.get("shape"))
    # 두 손 (아래에서 올라와 받쳐 듦)
    skin, shadow = pal["hand"], pal["hand_shadow"]
    if pal["hand"][0] < 90:  # 밤·노을엔 손이 너무 어두우니 밝힘
        skin, shadow = (225, 175, 140), (180, 125, 100)
    rise = (1 - smoothstep(t / 0.28)) * 70
    for hx in (cx - length * 0.22, cx + length * 0.2):
        hy = cy + bob + length * 0.12 + rise + squash * 20
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
        fl = pygame.Surface((w, h))
        fl.fill((255, 255, 250))
        fl.set_alpha(int(255 * (1 - t / 0.25)))
        canvas.blit(fl, (0, 0))
