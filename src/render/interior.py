"""건물 내부 배경 (DESIGN.md 35-3a, INTERIOR_NPC.md): 하루네 낚시점 · 노인 어부의 오두막 · 아스테라 수정 공방 · 오렌의 서재.

레이어별 함수로 나눈다 (나중에 그림 파일로 바꾸기 쉽게): back(벽·창·소품) → [초상화] → counter(카운터·카운터 위 소품) → light(시간대 조명·불빛).
좌표는 목업(tools/art/make_mockups.py, 480x270)의 값을 화면 가운데(cx) 기준으로 옮긴 것. 위쪽 영역 높이 top_h (기본 175) — 화면비가 달라도
벽은 화면 끝까지 이어지고(좌우 확장), 카운터는 대화창 바로 위에 붙는다(위아래 확장: 위로 벽이 더 보임).
env: {"w", "top_h", "t", "night"(0~1), "pal"(마을과 같은 하늘·물 팔레트), "season", "cont"}.
"""
import math
import random

import pygame

from src.core.mathutil import lerp_color


def _c(h: str) -> tuple:
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def _glow(canvas, pos, r: int, col, k: float = 1.0) -> None:
    if r <= 0 or k <= 0:
        return
    tmp = pygame.Surface((r * 2 + 2, r * 2 + 2))
    steps = 10   # 바깥에서 안으로 갈수록 조금씩 밝은 원 (누적값으로 그려 단단한 고리가 안 보이게)
    acc = 0.0
    for i in range(steps):
        u = 1 - i / steps
        acc += 0.11 * (1 - u) ** 0.7 + 0.02
        pygame.draw.circle(tmp, tuple(min(255, int(v * acc * k)) for v in col), (r + 1, r + 1), max(1, int(r * u)))
    canvas.blit(tmp, (int(pos[0]) - r - 1, int(pos[1]) - r - 1), special_flags=pygame.BLEND_RGB_ADD)


def _geo(env) -> tuple[int, int]:
    """(cx, by): 화면 가운데 x, 목업 좌표 y를 옮기는 값 (top_h 가 175보다 크면 아래로)."""
    return env["w"] // 2, env["top_h"] - 175


def _window_view(canvas, rect, env, sea: bool = True) -> None:
    """창밖: 마을과 같은 하늘·바다 색 (시간대·날씨·계절·이벤트), 밤엔 별."""
    pal, r = env["pal"], pygame.Rect(rect)
    sky_h = int(r.h * (0.66 if sea else 1.0))
    for i in range(0, sky_h, 2):
        canvas.fill(lerp_color(pal["sky_top"], pal["sky_bottom"], i / max(1, sky_h)), (r.x, r.y + i, r.w, 2))
    if sea:
        canvas.fill(pal["water_top"], (r.x, r.y + sky_h, r.w, r.h - sky_h))
        for k in range(3):   # 윤슬
            x = r.x + int((env["t"] * 9 + k * 23) % max(1, r.w - 6))
            canvas.fill(lerp_color(pal["water_top"], (255, 255, 255), 0.5), (x, r.y + sky_h + 3 + k * 4, 5, 1))
    if env["night"] > 0.4:
        rnd = random.Random(r.x * 7 + r.y)
        for _ in range(max(2, r.w * sky_h // 220)):
            x, y = r.x + rnd.randrange(r.w), r.y + rnd.randrange(max(1, sky_h - 2))
            tw = 0.5 + 0.5 * math.sin(env["t"] * 2 + x)
            canvas.fill(lerp_color(pal["sky_top"], (255, 255, 230), 0.4 + 0.5 * tw), (x, y, 1, 1))


def _frost(canvas, rect) -> None:
    """겨울: 창 아래 눈 + 모서리 성에."""
    r = pygame.Rect(rect)
    canvas.fill((240, 246, 252), (r.x, r.bottom - 4, r.w, 4))
    for i in range(0, r.w, 6):
        canvas.fill((240, 246, 252), (r.x + i, r.bottom - 6 + (i // 6) % 2, 4, 2))
    for cx_, cy_ in ((r.x, r.y), (r.right - 1, r.y)):
        for k in range(5):
            canvas.fill((225, 236, 248), (cx_ + (k if cx_ == r.x else -k), cy_ + k, 1, 1))


def _shade(canvas, env, top_h: int, warm=(255, 200, 140)) -> None:
    """시간대 조명: 밤엔 실내가 어두워지고(초상화도 함께, 너무 어둡진 않게), 저녁엔 따뜻한 빛."""
    n = env["night"]
    if n <= 0.02:
        return
    k = 1 - 0.33 * n
    tint = lerp_color((255, 255, 255), warm, 0.25 * n)
    mul = tuple(int(v * k) for v in tint)
    canvas.fill(mul, (0, 0, env["w"], top_h), special_flags=pygame.BLEND_RGB_MULT)


# ───────────────────────── 하루네 낚시점 (목업) ─────────────────────────
def haru_back(canvas, env) -> None:
    w, cx, (_, by) = env["w"], env["w"] // 2, _geo(env)
    th = env["top_h"]
    canvas.fill(_c("#6B4A33"), (0, 0, w, th))
    for y in range(by % 14, th, 14):
        canvas.fill(_c("#5A3D2A"), (0, y, w, 1))
    for x in range((cx - 210) % 70, w, 70):
        canvas.fill(_c("#5A3D2A"), (x, 0, 1, th))
    for sx in (cx - 220, cx + 110, cx - 440, cx + 330):   # 넓은 화면이면 선반이 더 보임
        canvas.fill(_c("#8A5A3A"), (sx, by + 40, 110, 4))
        canvas.fill(_c("#8A5A3A"), (sx, by + 95, 110, 4))
        for i, col in enumerate(("#C9A86A", "#4F7FB0", "#2B2B2B", "#B8B8C8", "#9C6A40")):
            x = sx + 10 + i * 20
            pygame.draw.line(canvas, _c(col), (x, by + 8), (x + 4, by + 40), 2)
        for i in range(4):
            pygame.draw.ellipse(canvas, _c("#4A4A55"), (sx + 12 + i * 25, by + 80, 14, 14))
            pygame.draw.ellipse(canvas, _c("#8A8A99"), (sx + 16 + i * 25, by + 84, 6, 6))
    win = pygame.Rect(cx - 44, by + 14, 88, 46)
    _window_view(canvas, win, env)
    pygame.draw.line(canvas, _c("#5A3D2A"), (cx, win.y), (cx, win.bottom), 2)
    pygame.draw.rect(canvas, _c("#4A3020"), win.inflate(4, 4), 2)
    s = env["season"]
    if s == "winter":
        _frost(canvas, win)
    elif s == "autumn":   # 곶감 줄
        for i in range(5):
            pygame.draw.circle(canvas, _c("#E07A2E"), (win.right + 10, by + 16 + i * 8), 3)
        pygame.draw.line(canvas, _c("#6B4A2B"), (win.right + 10, by + 10), (win.right + 10, by + 50), 1)
    for lx in (cx - 90, cx + 90):
        pygame.draw.line(canvas, _c("#2A1E1A"), (lx, 0), (lx, by + 18))
        canvas.fill(_c("#F2C46B"), (lx - 6, by + 18, 12, 14))


def haru_counter(canvas, env) -> None:
    w, cx, (_, by) = env["w"], env["w"] // 2, _geo(env)
    canvas.fill(_c("#6A4128"), (0, by + 140, w, 35))
    canvas.fill(_c("#8A5A3A"), (0, by + 136, w, 7))
    canvas.fill(_c("#4A3020"), (0, by + 143, w, 1))
    canvas.fill(_c("#C9A86A"), (cx - 180, by + 126, 32, 10))   # 미끼 상자
    canvas.fill(_c("#4A4A55"), (cx + 140, by + 122, 20, 14))   # 계산대
    _season_counter(canvas, env, cx - 140, by + 136)


def haru_light(canvas, env) -> None:
    cx, (_, by) = env["w"] // 2, _geo(env)
    _shade(canvas, env, env["top_h"])
    k = 0.35 + 0.65 * env["night"]
    for lx in (cx - 90, cx + 90):
        _glow(canvas, (lx, by + 25), 34, (255, 190, 100), k)


# ───────────────────────── 아스테라 수정 공방 (목업) ─────────────────────────
CRYSTALS = [(40, 60, 14), (70, 110, 10), (400, 50, 16), (440, 120, 10), (150, 22, 8), (360, 110, 9), (-40, 80, 12), (520, 70, 12)]


def ella_back(canvas, env) -> None:
    w, cx, (_, by) = env["w"], env["w"] // 2, _geo(env)
    th, ox = env["top_h"], env["w"] // 2 - 240
    canvas.fill(_c("#1E2A44"), (0, 0, w, th))
    for y in range(by % 18 - 18, th, 18):
        row = ((y - by) // 18) % 2
        for x in range((ox + row * 20) % 40 - 40, w, 40):
            pygame.draw.rect(canvas, _c("#283656"), (x, y, 39, 17), 1)
    win = pygame.Rect(cx - 150, by + 30, 30, 30)   # 둥근 창 (시간대)
    view = pygame.Surface(win.size)
    _window_view(view, view.get_rect(), dict(env, t=env["t"]))
    mask = pygame.Surface(win.size, pygame.SRCALPHA)
    pygame.draw.circle(mask, (255, 255, 255, 255), (15, 15), 14)
    view.set_colorkey((0, 0, 0))
    view.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
    canvas.blit(view, win)
    pygame.draw.circle(canvas, _c("#D9B45A"), win.center, 15, 2)
    if env["season"] == "winter":
        canvas.fill((240, 246, 252), (win.x + 4, win.bottom - 6, 22, 3))
    pulse = 0.85 + 0.15 * math.sin(env["t"] * 1.4)
    boost = 1.25 if env["season"] == "summer" else 1.0   # 성하기: 마력이 짙음
    for (x, y, s) in CRYSTALS:
        x, y = x + ox, y + by
        for k, mix in ((2.0, 0.12), (1.3, 0.25)):
            col = tuple(int(b + (t - b) * mix * pulse * boost) for b, t in zip((30, 42, 68), (63, 191, 179)))
            pygame.draw.circle(canvas, col, (x, y), int(s * k))
        pygame.draw.polygon(canvas, _c("#3FBFB3"), [(x, y - s), (x + s // 2, y), (x, y + s), (x - s // 2, y)])
        canvas.fill(_c("#C8FFF8"), (x - 1, y - s // 2, 1, 1))
    for lx in (cx - 80, cx + 80):
        pygame.draw.line(canvas, _c("#D9B45A"), (lx, 0), (lx, by + 16))
        pygame.draw.polygon(canvas, _c("#7FE6DC"), [(lx, by + 16), (lx + 6, by + 24), (lx, by + 32), (lx - 6, by + 24)])
    pygame.draw.arc(canvas, _c("#D9B45A"), (cx - 60, by + 6, 120, 84), 0, math.pi, 2)
    if env["season"] == "winter":   # 극야기: 별 장식
        for i, x in enumerate((cx - 120, cx + 120, cx - 190, cx + 190)):
            yy = by + 30 + (i % 2) * 14
            pygame.draw.line(canvas, _c("#D9B45A"), (x, 0), (x, yy))
            _star(canvas, x, yy + 3, _c("#FFE9A0"))


def _star(canvas, x, y, col) -> None:
    for dx, dy in ((0, -3), (0, 3), (-3, 0), (3, 0), (0, 0), (-1, -1), (1, 1), (1, -1), (-1, 1)):
        canvas.fill(col, (x + dx, y + dy, 1, 1))


def ella_counter(canvas, env) -> None:
    w, cx, (_, by) = env["w"], env["w"] // 2, _geo(env)
    canvas.fill(_c("#24304E"), (0, by + 140, w, 35))
    canvas.fill(_c("#3A4A6E"), (0, by + 136, w, 7))
    canvas.fill(_c("#D9B45A"), (0, by + 143, w, 1))
    canvas.fill(_c("#C9A86A"), (cx - 180, by + 126, 32, 10))
    canvas.fill(_c("#4A4A55"), (cx + 140, by + 122, 20, 14))
    _season_counter(canvas, env, cx - 140, by + 136)


def ella_light(canvas, env) -> None:
    cx, (_, by) = env["w"] // 2, _geo(env)
    _shade(canvas, env, env["top_h"], warm=(160, 220, 255))
    k = 0.3 + 0.5 * env["night"]
    for lx in (cx - 80, cx + 80):
        _glow(canvas, (lx, by + 24), 26, (120, 240, 230), k)


# ───────────────────────── 노인 어부의 오두막 (새로 그림) ─────────────────────────
def baek_back(canvas, env) -> None:
    """낮은 천장(들보), 걸린 그물과 낡은 삿갓, 벽의 오래된 어탁 한 장, 작은 창, 화로 불빛은 light 에서."""
    w, cx, (_, by) = env["w"], env["w"] // 2, _geo(env)
    th = env["top_h"]
    canvas.fill(_c("#5A4632"), (0, 0, w, th))
    rnd = random.Random(5)
    x = (cx - 240) % 26 - 26
    while x < w:   # 고르지 않은 판자벽
        ww = 22 + rnd.randrange(8)
        canvas.fill(_c("#4E3C2A"), (x, 0, 1, th))
        canvas.fill(lerp_color(_c("#5A4632"), _c("#66513A"), rnd.random() * 0.6), (x + 1, 0, ww - 1, th))
        x += ww
    canvas.fill(_c("#3A2A1E"), (0, 0, w, by + 12))   # 낮은 천장 (화면이 위로 길면 서까래가 더 보임)
    for y in range(by + 4, -8, -16):
        canvas.fill(_c("#32241A"), (0, y, w, 2))
    for bx in range((cx - 200) % 90 - 90, w, 90):
        canvas.fill(_c("#2E2118"), (bx, by + 8, 10, 10))
    canvas.fill(_c("#2E2118"), (0, by + 12, w, 3))
    # 작은 창 (오른쪽)
    win = pygame.Rect(cx + 78, by + 26, 44, 34)
    _window_view(canvas, win, env)
    pygame.draw.line(canvas, _c("#3A2A1E"), (win.centerx, win.y), (win.centerx, win.bottom), 2)
    pygame.draw.rect(canvas, _c("#3A2A1E"), win.inflate(4, 4), 2)
    if env["season"] == "winter":
        _frost(canvas, win)
    elif env["season"] == "autumn":   # 곶감
        for i in range(4):
            pygame.draw.circle(canvas, _c("#E07A2E"), (win.x - 8, by + 26 + i * 8), 3)
        pygame.draw.line(canvas, _c("#6B4A2B"), (win.x - 8, by + 18), (win.x - 8, by + 54), 1)
    # 벽의 오래된 어탁 (왼쪽)
    pr = pygame.Rect(cx - 214, by + 34, 78, 48)
    canvas.fill(_c("#2E2118"), pr.move(2, 2))
    canvas.fill(_c("#E3D6B8"), pr)
    pygame.draw.ellipse(canvas, _c("#2B2622"), (pr.x + 12, pr.y + 15, 44, 17))
    pygame.draw.polygon(canvas, _c("#2B2622"), [(pr.x + 54, pr.y + 23), (pr.x + 68, pr.y + 13), (pr.x + 66, pr.y + 34)])
    canvas.fill(_c("#E3D6B8"), (pr.x + 19, pr.y + 20, 2, 2))   # 눈
    canvas.fill(_c("#B03A2E"), (pr.right - 12, pr.bottom - 11, 7, 7))   # 도장
    # 걸린 그물 (오른쪽 끝) + 찌
    nx0, ny0 = cx + 150, by + 16
    for i in range(0, 90, 9):
        pygame.draw.line(canvas, _c("#8A7A5A"), (nx0 + i, ny0), (nx0 + i - 30, ny0 + 100), 1)
        pygame.draw.line(canvas, _c("#8A7A5A"), (nx0 + i - 30, ny0), (nx0 + i, ny0 + 100), 1)
    for i, (fx, fy) in enumerate(((nx0 + 6, ny0 + 30), (nx0 + 40, ny0 + 55), (nx0 + 70, ny0 + 20))):
        pygame.draw.circle(canvas, _c("#E84A4A") if i % 2 == 0 else _c("#F2F2EE"), (fx, fy), 3)
    # 낡은 삿갓 (못에 걸림)
    hx, hy = cx + 152, by + 60
    canvas.fill(_c("#2E2118"), (hx - 1, hy - 18, 2, 3))
    pygame.draw.polygon(canvas, _c("#A0823F"), [(hx - 26, hy + 2), (hx, hy - 16), (hx + 26, hy + 2)])
    pygame.draw.polygon(canvas, _c("#C9A86A"), [(hx - 24, hy), (hx, hy - 15), (hx + 24, hy)])
    for k in range(-20, 21, 6):
        pygame.draw.line(canvas, _c("#A0823F"), (hx, hy - 14), (hx + k, hy), 1)


def baek_counter(canvas, env) -> None:
    """낮은 나무 탁자 + 화로(오른쪽) + 주전자."""
    w, cx, (_, by) = env["w"], env["w"] // 2, _geo(env)
    canvas.fill(_c("#5A3D2A"), (0, by + 140, w, 35))
    canvas.fill(_c("#7A5A3A"), (0, by + 136, w, 7))
    canvas.fill(_c("#3A2A1E"), (0, by + 143, w, 1))
    for x in range((cx - 240) % 60, w, 60):
        canvas.fill(_c("#4E3424"), (x, by + 146, 1, 29))
    bx, byy = cx + 160, by + 118   # 화로
    canvas.fill(_c("#3A3A40"), (bx - 16, byy + 6, 32, 12))
    canvas.fill(_c("#2A2A30"), (bx - 18, byy + 4, 36, 3))
    for i in range(5):
        fl = math.sin(env["t"] * 9 + i * 1.7)
        canvas.fill(_c("#F28A2E") if fl > 0 else _c("#E8532A"), (bx - 10 + i * 5, byy + 1 - int(2 + fl * 2), 3, 4))
    kx = bx - 2   # 주전자
    pygame.draw.ellipse(canvas, _c("#4A4A55"), (kx - 9, byy - 14, 18, 14))
    canvas.fill(_c("#4A4A55"), (kx + 8, byy - 10, 6, 2))
    if env["season"] == "winter":   # 김
        for i in range(3):
            yy = byy - 18 - ((env["t"] * 10 + i * 6) % 18)
            canvas.fill((220, 220, 225), (kx - 2 + int(math.sin(env["t"] * 2 + i) * 2), int(yy), 2, 2))
    canvas.fill(_c("#C9A86A"), (cx - 180, by + 128, 26, 8))   # 낡은 미끼통
    _season_counter(canvas, env, cx - 140, by + 136)


def baek_light(canvas, env) -> None:
    cx, (_, by) = env["w"] // 2, _geo(env)
    _shade(canvas, env, env["top_h"], warm=(255, 170, 110))
    fl = 0.85 + 0.15 * math.sin(env["t"] * 7) * math.sin(env["t"] * 3.1)
    _glow(canvas, (cx + 160, by + 116), 46, (255, 140, 60), (0.45 + 0.5 * env["night"]) * fl)   # 화로 불빛


# ───────────────────────── 오렌의 서재 (새로 그림) ─────────────────────────
BOOK_COLS = ["#7A3A2E", "#2F5D4A", "#3A4E7A", "#8A6B2F", "#5A3D5A", "#9C6A40", "#4A6A6A", "#6B2020"]


def oren_back(canvas, env) -> None:
    """책장 가득한 벽, 높은 둥근 창, 수정 지구본·촛불·펼쳐진 고서는 카운터에."""
    w, cx, (_, by) = env["w"], env["w"] // 2, _geo(env)
    th = env["top_h"]
    canvas.fill(_c("#3E2A1C"), (0, 0, w, th))
    rnd = random.Random(11)
    for row, y in enumerate(range(by + 6 - 42 * 3, th - 30, 42)):   # 위로 늘어난 화면이면 책장도 위로
        if y < -40:
            continue
        canvas.fill(_c("#5A3D2A"), (0, y + 34, w, 5))
        x = (cx - 240) % 13 - 13
        while x < w:
            bw = 5 + rnd.randrange(5)
            bh = 20 + rnd.randrange(12)
            if rnd.random() < 0.07:   # 비스듬히 기댄 책
                pygame.draw.polygon(canvas, _c(rnd.choice(BOOK_COLS)), [(x, y + 34), (x + bw, y + 34), (x + bw + 8, y + 34 - bh), (x + 8, y + 34 - bh)])
                x += bw + 10
                continue
            col = _c(rnd.choice(BOOK_COLS))
            canvas.fill(col, (x, y + 34 - bh, bw, bh))
            canvas.fill(lerp_color(col, (255, 230, 160), 0.35), (x + 1, y + 34 - bh + 4, bw - 2, 1))
            x += bw + 1
    # 가운데 높은 둥근 창 (책장 위)
    win = pygame.Rect(cx - 30, by + 2, 60, 34)
    canvas.fill(_c("#2E2118"), win.inflate(8, 6))
    _window_view(canvas, win, env)
    pygame.draw.line(canvas, _c("#2E2118"), (cx, win.y), (cx, win.bottom), 2)
    pygame.draw.line(canvas, _c("#2E2118"), (win.x, win.y + 17), (win.right, win.y + 17), 1)
    if env["season"] == "winter":
        _frost(canvas, win)


def oren_counter(canvas, env) -> None:
    w, cx, (_, by) = env["w"], env["w"] // 2, _geo(env)
    canvas.fill(_c("#3E2A1C"), (0, by + 140, w, 35))
    canvas.fill(_c("#5A3D2A"), (0, by + 136, w, 7))
    canvas.fill(_c("#2E2118"), (0, by + 143, w, 1))
    # 펼쳐진 고서
    bx, byy = cx - 150, by + 128
    pygame.draw.polygon(canvas, _c("#E8DCC4"), [(bx, byy + 8), (bx + 22, byy + 4), (bx + 22, byy + 10), (bx, byy + 12)])
    pygame.draw.polygon(canvas, _c("#DDD0B4"), [(bx + 22, byy + 4), (bx + 44, byy + 8), (bx + 44, byy + 12), (bx + 22, byy + 10)])
    for k in range(2):   # 글줄
        canvas.fill(_c("#8A7A60"), (bx + 5, byy + 8 + k * 2, 12, 1))
        canvas.fill(_c("#8A7A60"), (bx + 27, byy + 7 + k * 2, 12, 1))
    # 촛불 2개
    for x in (cx - 186, cx + 120):
        canvas.fill(_c("#EFE6D2"), (x, by + 122, 5, 14))
        fl = math.sin(env["t"] * 10 + x)
        canvas.fill(_c("#F2C46B"), (x + 1, by + 117 - int(fl), 3, 5))
    # 수정 지구본
    gx, gy = cx + 168, by + 112
    canvas.fill(_c("#B8863B"), (gx - 8, gy + 14, 16, 4))
    canvas.fill(_c("#B8863B"), (gx - 1, gy + 9, 2, 6))
    pygame.draw.circle(canvas, _c("#3FBFB3"), (gx, gy), 11)
    rot = env["t"] * 0.6
    for k in range(3):   # 천천히 도는 경선
        xx = int(math.sin(rot + k * 2.1) * 9)
        if math.cos(rot + k * 2.1) > 0:
            pygame.draw.line(canvas, _c("#C8FFF8"), (gx + xx, gy - 8), (gx + xx, gy + 8), 1)
    pygame.draw.arc(canvas, _c("#D9B45A"), (gx - 13, gy - 13, 26, 26), -0.6, 3.6, 1)
    _season_counter(canvas, env, cx - 96, by + 136)


def oren_light(canvas, env) -> None:
    cx, (_, by) = env["w"] // 2, _geo(env)
    _shade(canvas, env, env["top_h"], warm=(255, 190, 120))
    for x in (cx - 184, cx + 122):
        _glow(canvas, (x, by + 118), 24, (255, 180, 90), 0.35 + 0.55 * env["night"])
    _glow(canvas, (cx + 168, by + 112), 22, (90, 220, 210), 0.3)


# ───────────────────────── 계절 장식 (카운터 위 작은 소품) ─────────────────────────
def _season_counter(canvas, env, x: int, y: int) -> None:
    """봄 꽃병 · 여름 부채 · 가을 곡식(금빛 갈대) 다발 · 겨울 귤 바구니. y = 카운터 윗면."""
    s, eld = env["season"], env.get("cont") == "eldrasion"
    if s == "spring":
        canvas.fill(_c("#5E7A9A") if eld else _c("#8A6A9A"), (x, y - 9, 7, 9))
        for i, col in enumerate(((200, 240, 255), (230, 245, 255), (200, 240, 255)) if eld else
                                ((255, 170, 200), (255, 220, 120), (255, 190, 210))):
            pygame.draw.circle(canvas, col, (x + 1 + i * 3, y - 12 - (i % 2) * 2), 2)
    elif s == "summer":
        pygame.draw.polygon(canvas, _c("#7FE6DC") if eld else _c("#F2F2EE"), [(x, y - 1), (x + 14, y - 12), (x + 16, y - 1)])
        for k in range(3):
            pygame.draw.line(canvas, _c("#3A6EA5"), (x + 2, y - 1), (x + 8 + k * 3, y - 8 + k), 1)
    elif s == "autumn":
        for k in range(4):
            pygame.draw.line(canvas, _c("#E0B850"), (x + 4, y), (x + k * 3, y - 16 + k), 1)
        canvas.fill(_c("#A0782F"), (x + 1, y - 6, 8, 2))
    elif s == "winter":
        pygame.draw.ellipse(canvas, _c("#8A6A45"), (x - 2, y - 6, 16, 7))
        for i in range(3):
            pygame.draw.circle(canvas, _c("#F29A2E"), (x + 2 + i * 4, y - 7 - (i % 2)), 3)


LAYERS = {
    "haru_shop": (haru_back, haru_counter, haru_light),
    "baek_hut": (baek_back, baek_counter, baek_light),
    "ella_workshop": (ella_back, ella_counter, ella_light),
    "oren_study": (oren_back, oren_counter, oren_light),
}


def draw_back(canvas, kind: str, env) -> None:
    LAYERS[kind][0](canvas, env)


def draw_counter(canvas, kind: str, env) -> None:
    LAYERS[kind][1](canvas, env)


def draw_light(canvas, kind: str, env) -> None:
    LAYERS[kind][2](canvas, env)
