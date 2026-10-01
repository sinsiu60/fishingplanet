"""물고기 그리기: 옆모습(점프·뜰채·획득 컷), 획득 컷 전체 연출."""
import math

import pygame

from src.core.mathutil import clamp, lerp, lerp_color, scale_color

DEFAULT_COLORS = {"body": [120, 130, 120], "belly": [220, 220, 210], "fin": [90, 100, 90], "stripe": None}
RANK_COLORS = {"S": (255, 214, 90), "A": (150, 200, 255), "B": (140, 220, 150), "C": (190, 190, 190)}


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
                   facing: int = -1, silhouette=None, tail_wag: float = 0.0) -> None:
    """옆모습 물고기. 기본은 머리가 왼쪽(-x). silhouette 색을 주면 단색 실루엣."""
    L = length
    H = L * 0.17
    top, bot = [], []
    n = 10
    tail_base = -L / 2 + L * 0.8
    for i in range(n + 1):
        u = i / n
        x = -L / 2 + u * L * 0.8
        prof = math.sin(math.pi * clamp(u * 0.92 + 0.06, 0, 1)) ** 0.75
        taper = lerp(1.0, 0.35, clamp((u - 0.55) / 0.45, 0, 1))
        h = H * max(0.2, prof) * taper
        top.append((x, -h))
        bot.append((x, h * 1.08))
    wag = tail_wag * H * 0.6
    tail = [(L / 2, -H * 0.85 + wag), (L / 2 - L * 0.06, wag * 0.5), (L / 2, H * 0.85 + wag)]
    body = top + tail + bot[::-1]

    if silhouette is not None:
        pygame.draw.polygon(canvas, silhouette, _xf(body, cx, cy, angle, facing))
        fin = [(-L * 0.05, -H * 0.9), (L * 0.15, -H * 1.5), (L * 0.22, -H * 0.7)]
        pygame.draw.polygon(canvas, silhouette, _xf(fin, cx, cy, angle, facing))
        return

    base, belly, fin_c, stripe = colors["body"], colors["belly"], colors["fin"], colors["stripe"]
    # 등지느러미 (몸 뒤에)
    dorsal = [(-L * 0.16, -H * 0.8), (-L * 0.07, -H * 1.3), (L * 0.06, -H * 1.05), (L * 0.16, -H * 1.25),
              (L * 0.25, -H * 0.55)]
    pygame.draw.polygon(canvas, fin_c, _xf(dorsal, cx, cy, angle, facing))
    pygame.draw.polygon(canvas, base, _xf(body, cx, cy, angle, facing))
    # 배
    belly_poly = [(x, h * 0.25) for x, h in [(p[0], -p[1]) for p in top[1:-2]]] + bot[1:-2][::-1]
    pygame.draw.polygon(canvas, belly, _xf(belly_poly, cx, cy, angle, facing))
    # 등 쪽 어두운 음영
    back_poly = top[1:-1] + [(x, -h * 0.55) for x, h in [(p[0], -p[1]) for p in top[1:-1]]][::-1]
    pygame.draw.polygon(canvas, scale_color(base, 0.8), _xf(back_poly, cx, cy, angle, facing))
    # 옆줄 무늬
    if stripe:
        pts = _xf([(-L * 0.3, -H * 0.05), (tail_base - L * 0.04, H * 0.05)], cx, cy, angle, facing)
        pygame.draw.line(canvas, stripe, pts[0], pts[1], max(1, int(L / 60)))
    # 가슴지느러미
    pec = [(-L * 0.26, H * 0.2), (-L * 0.17, H * 0.55), (-L * 0.13, H * 0.25)]
    pygame.draw.polygon(canvas, fin_c, _xf(pec, cx, cy, angle, facing))
    # 꼬리 색
    pygame.draw.polygon(canvas, fin_c, _xf(tail + [(tail_base + L * 0.02, 0)], cx, cy, angle, facing))
    # 눈·입
    eye = _xf([(-L * 0.4, -H * 0.3)], cx, cy, angle, facing)[0]
    r = max(1, int(L / 40))
    pygame.draw.circle(canvas, (250, 250, 240), eye, r + 1)
    pygame.draw.circle(canvas, (20, 20, 20), eye, r)
    mouth = _xf([(-L / 2 + L * 0.01, H * 0.05), (-L * 0.42, H * 0.25)], cx, cy, angle, facing)
    pygame.draw.line(canvas, scale_color(base, 0.55), mouth[0], mouth[1], 1)
    # 아가미 선
    gill = _xf([(-L * 0.33, -H * 0.55), (-L * 0.3, 0), (-L * 0.33, H * 0.6)], cx, cy, angle, facing)
    pygame.draw.lines(canvas, scale_color(base, 0.7), False, gill, 1)


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
    if length < 26:
        draw_fish_side(canvas, sx, sy, length, angle, colors, facing, silhouette=dark)
    else:
        draw_fish_side(canvas, sx, sy, length, angle, colors, facing)
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
                   tail_wag=0.0 if still else math.sin(t * 30))
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
    ray = lerp_color((40, 46, 80), rc, 0.25)
    for i in range(12):
        a = t * 0.4 + i * math.tau / 12
        pts = [(cx, cy),
               (cx + math.cos(a) * 300, cy + math.sin(a) * 300),
               (cx + math.cos(a + 0.12) * 300, cy + math.sin(a + 0.12) * 300)]
        pygame.draw.polygon(canvas, ray, pts)

    lo, hi = fish["size_cm"]
    k = clamp((result["size"] - lo) / max(1, hi - lo), 0, 1.2)
    length = lerp(150, 240, k)
    pop = 1 + 0.15 * max(0.0, 1 - t / 0.25)
    bob = math.sin(t * 2.5) * 2
    colors = fish_colors(fish)
    draw_fish_side(canvas, cx, cy + bob, length * pop, 0.0, colors, facing=-1, tail_wag=math.sin(t * 6) * 0.4)
    # 두 손 (아래에서 받쳐 듦)
    skin, shadow = pal["hand"], pal["hand_shadow"]
    if pal["hand"][0] < 90:  # 밤·노을엔 손이 너무 어두우니 밝힘
        skin, shadow = (225, 175, 140), (180, 125, 100)
    for hx in (cx - length * 0.22, cx + length * 0.2):
        hy = cy + bob + length * 0.12
        pygame.draw.ellipse(canvas, shadow, (hx - 15, hy - 4, 30, 18))
        pygame.draw.ellipse(canvas, skin, (hx - 15, hy - 7, 30, 15))
        for i in range(4):
            pygame.draw.line(canvas, shadow, (hx - 10 + i * 6, hy - 6), (hx - 10 + i * 6, hy - 1), 1)
        out = -1 if hx < cx else 1
        sleeve = [(hx - 12, hy + 6), (hx + 12, hy + 6), (hx + 12 + out * 34, h), (hx - 12 + out * 34, h)]
        pygame.draw.polygon(canvas, (60, 80, 120), sleeve)
        pygame.draw.line(canvas, (44, 60, 94), (hx + out * 10, hy + 8), (hx + out * 44, h), 2)
