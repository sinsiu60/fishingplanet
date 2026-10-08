"""C3-02 '용문 폭포의 바위' 전용 컷신 그리기 (STORY_ROCK.md — 15초, 장면 A~E). 낚시 화면 스냅샷을 쓰지 않는다.

A 0.0~3.0  폭포 전경 (와이드, 오른쪽으로 40px 팬 → 오른쪽 끝 안개 속 바위 실루엣)
B 3.0~5.5  1인칭으로 안개 속 젖은 바위 길을 걸어 바위 앞으로 (바위 80 → 140px, 5.0 받침대 2개 · 걸음 멈춤)
C 5.5~8.5  바위 미디엄 샷 — 오른손이 이끼를 두 번 쓸어내 새김이 드러남
D 8.5~11.0 '해강' 클로즈업 — 손가락이 '해' 홈을 따라 쓸어 내림 → 물방울 한 방울
E 11.0~15.0 앉은 시점 — 두 손이 할아버지의 대나무 낚싯대를 받침대 둘에 걸쳐 놓음 → 자막

좌표는 480×270 기준. 폰처럼 화면이 넓으면 가운데(cx)를 기준으로 하늘 · 절벽 · 땅을 양옆으로 이어 그린다.
위아래 시네마 띠 18px, 자막은 아래 띠 위. 무거운 층(하늘 · 절벽 · 웅덩이 · 바위 · 바위 표면 · 먼 폭포 · 손)은 처음에 한 번 굽고,
매 프레임은 물줄기 줄무늬 · 안개 · 물보라 · 손 위치만. 손 = 낚시 화면 손 색(팔레트 hand · hand_shadow · sleeve) + 계절 장갑 규칙 (fishing._hand_look).
"""
import math
import random

import pygame

from src.core.fonts import get_font
from src.core.mathutil import clamp, lerp_color, scale_color

LENGTH = 15.0
BAR = 18
OUT = (24, 28, 36)
SKY = ((30, 44, 60), (96, 120, 132))
CLIFF = ((40, 50, 62), (58, 70, 84), (82, 96, 108))           # 어둠 · 중 · 밝 (짙은 청회색)
MOSS = ((0x3E, 0x6B, 0x3A), (40, 72, 40), (96, 142, 82))       # 기본 #3E6B3A · 어둠 · 밝
FALL = ((236, 246, 248), (164, 216, 218), (100, 168, 176), (64, 122, 134))
POOL = ((36, 78, 92), (54, 106, 118), (130, 188, 194))
MIST = (222, 232, 236)
ROCK = ((146, 146, 156), (0x6E, 0x6E, 0x78), (80, 80, 90))    # 밝 · 기본 #6E6E78 · 어둠
GROOVE = (48, 48, 58)
RIM = (164, 164, 174)
STAND = ((0x5A, 0x3D, 0x2A), (124, 90, 62), (58, 38, 26))      # 기본 #5A3D2A · 밝 · 어둠
CORD = (178, 154, 114)
BAMBOO = ((0xC9, 0xA8, 0x6A), (0xA8, 0x88, 0x49), (150, 120, 70))
SUB = "할아버지도, 여기 앉아 있었다."


def ease(u: float) -> float:
    u = clamp(u, 0.0, 1.0)
    return u * u * (3 - 2 * u)


def _seg(t: float, a: float, b: float) -> float:
    return clamp((t - a) / (b - a), 0.0, 1.0)


def _lerp(a, b, u):
    return (a[0] + (b[0] - a[0]) * u, a[1] + (b[1] - a[1]) * u)


def _outline(s: pygame.Surface, col=OUT) -> pygame.Surface:
    """그려진 픽셀 둘레 1px 외곽선 (가까운 물체만)."""
    m = pygame.mask.from_surface(s)
    o = pygame.Surface(s.get_size(), pygame.SRCALPHA)
    for p in m.outline():
        o.set_at(p, col)
    o.blit(s, (0, 0))
    return o


def _clip_to(s: pygame.Surface, shape: pygame.Surface) -> None:
    """s 의 알파를 shape 의 그려진 부분으로 자름."""
    m = pygame.mask.from_surface(shape).to_surface(setcolor=(255, 255, 255, 255), unsetcolor=(0, 0, 0, 0))
    s.blit(m, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)


def _blob(w: int, h: int, col, alpha: int) -> pygame.Surface:
    """부드러운 안개 덩어리: 절반 크기에 옅은 타원 14겹(가운데로 갈수록 진함) → 두 배로 부드럽게 키움."""
    sw, sh = max(8, w // 2), max(4, h // 2)
    s = pygame.Surface((sw, sh), pygame.SRCALPHA)
    n = 14
    for k in range(n):
        f = 1 - k / n
        r = pygame.Rect(0, 0, max(2, int(sw * f)), max(2, int(sh * f)))
        r.center = (sw // 2, sh // 2)
        e = pygame.Surface(r.size, pygame.SRCALPHA)
        pygame.draw.ellipse(e, (*col, max(1, int(alpha / n))), e.get_rect())
        s.blit(e, r.topleft)
    return pygame.transform.smoothscale(s, (w, h))


def _vgrad(s: pygame.Surface, rect: pygame.Rect, top, bot) -> None:
    for y in range(rect.h):
        s.fill(lerp_color(top, bot, y / max(1, rect.h - 1)), (rect.x, rect.y + y, rect.w, 1))


def rock_sprite(w: int, h: int, seed: int, cracks: int = 2, moss: float = 1.0, outline: bool = True) -> pygame.Surface:
    """물가의 큰 바위: 위가 둥근 덩어리, 3단 음영(왼쪽 위 밝게), 갈라진 금, 물이 흘러내린 어두운 줄, 아래쪽 이끼."""
    rnd = random.Random(seed)
    shape = pygame.Surface((w, h), pygame.SRCALPHA)
    pts = []
    n = 22
    for i in range(n + 1):
        a = math.pi + math.pi * i / n
        r = 1 - 0.07 * rnd.random() - (0.05 if i in (4, 15) else 0)
        pts.append((w / 2 + math.cos(a) * (w / 2 - 1) * r, h - 1 + math.sin(a) * (h - 2) * r))
    pygame.draw.polygon(shape, (255, 255, 255), pts)
    s = pygame.Surface((w, h), pygame.SRCALPHA)
    s.fill(ROCK[2])
    pygame.draw.ellipse(s, ROCK[1], (-w * 0.1, -h * 0.05, w * 0.92, h * 1.6))
    pygame.draw.ellipse(s, ROCK[0], (w * 0.1, h * 0.08, w * 0.42, h * 0.42))
    for _ in range(int(w * h / 60)):   # 결 (밝은 / 어두운 점)
        x, y = rnd.randrange(w), rnd.randrange(h)
        c = s.get_at((x, y))[:3]
        s.fill(scale_color(c, rnd.choice((0.88, 1.08))), (x, y, rnd.choice((1, 2)), 1))
    for k in range(max(2, w // 40)):   # 물이 흘러내린 어두운 줄
        x = int(w * (0.25 + 0.55 * rnd.random()))
        y0 = int(h * (0.1 + 0.2 * rnd.random()))
        for y in range(y0, h):
            xx = x + int(math.sin(y * 0.18 + k) * 1.2)
            c = s.get_at((xx, y))[:3]
            s.fill(scale_color(c, 0.84), (xx, y, 2, 1))
    for _ in range(cracks):   # 갈라진 금 (위에서 아래로 꺾이며)
        x, y = rnd.uniform(w * 0.25, w * 0.75), rnd.uniform(h * 0.1, h * 0.35)
        pts_c = [(x, y)]
        for _ in range(rnd.randint(4, 7)):
            x += rnd.uniform(-w * 0.05, w * 0.05)
            y += rnd.uniform(h * 0.06, h * 0.12)
            pts_c.append((x, y))
        pygame.draw.lines(s, GROOVE, False, pts_c, 1)
        pygame.draw.lines(s, RIM, False, [(px + 1, py + 1) for px, py in pts_c], 1)
    if moss > 0:   # 아래쪽 이끼 덩어리
        for _ in range(int(w / 5 * moss)):
            mx = rnd.uniform(0, w)
            my = h - rnd.uniform(1, h * 0.22) * (1.2 - abs(mx / w - 0.5))
            r = rnd.uniform(2, max(3, w / 28))
            pygame.draw.ellipse(s, rnd.choice(MOSS[:2]), (mx - r, my - r * 0.6, r * 2, r * 1.2))
            if rnd.random() < 0.5:
                s.fill(MOSS[2], (int(mx - r * 0.4), int(my - r * 0.5), 2, 1))
    _clip_to(s, shape)
    return _outline(s) if outline else s


def draw_stand(canvas, x: float, base_y: float, h: float, alpha: int = 255) -> None:
    """낡은 나무 받침대 (Y자 나뭇가지 #5A3D2A, 끈으로 묶인 자국 · 갈라진 결). h = 땅에서 갈래 끝까지."""
    k = h / 26
    w = max(2, int(round(3 * k)))
    s = pygame.Surface((int(26 * k) + 8, int(h) + 6), pygame.SRCALPHA)
    ox, oy = s.get_width() / 2, s.get_height() - 2
    fork = oy - h * 0.62
    pygame.draw.line(s, STAND[0], (ox, oy), (ox, fork), w)                          # 줄기
    pygame.draw.line(s, STAND[0], (ox, fork + 1), (ox - 7 * k, oy - h), max(2, w - 1))   # 갈래 둘
    pygame.draw.line(s, STAND[0], (ox, fork + 1), (ox + 6 * k, oy - h + 1), max(2, w - 1))
    pygame.draw.line(s, STAND[1], (ox - w / 2 + 0.5, oy - 1), (ox - w / 2 + 0.5, fork + 2), 1)   # 밝은 결
    for j in range(2):   # 끈으로 묶인 자국
        yy = fork + 3 * k + j * 2 * k
        pygame.draw.line(s, CORD, (ox - w / 2 - 1, yy), (ox + w / 2 + 1, yy - 1), 1)
    pygame.draw.line(s, STAND[2], (ox + 1, fork + 6 * k), (ox, oy - 4 * k), 1)       # 갈라진 결
    o = _outline(s)
    if alpha < 255:
        o.set_alpha(alpha)
    canvas.blit(o, (int(x - ox), int(base_y - oy)))


def draw_bamboo(canvas, a, b, w0: float = 5, w1: float = 2, node: int = 18) -> None:
    """할아버지의 대나무 낚싯대 (#C9A86A, 마디 #A88849 18px 간격) — a = 손잡이, b = 끝. 굵기 w0 → w1."""
    dx, dy = b[0] - a[0], b[1] - a[1]
    ln = math.hypot(dx, dy) or 1
    ux, uy = dx / ln, dy / ln
    nx, ny = -uy, ux
    steps = int(ln // 6) + 1
    for i in range(steps):
        u0, u1 = i / steps, (i + 1) / steps
        wd = w0 + (w1 - w0) * u0
        p0 = (a[0] + dx * u0, a[1] + dy * u0)
        p1 = (a[0] + dx * u1, a[1] + dy * u1)
        pygame.draw.line(canvas, BAMBOO[0], p0, p1, max(1, int(round(wd))))
        if wd >= 3:   # 아래쪽 그늘
            off = wd / 2 - 0.5
            pygame.draw.line(canvas, BAMBOO[2], (p0[0] + nx * off, p0[1] + ny * off), (p1[0] + nx * off, p1[1] + ny * off), 1)
    d = node
    while d < ln - 4:
        wd = w0 + (w1 - w0) * d / ln
        c = (a[0] + ux * d, a[1] + uy * d)
        h = wd / 2 + 0.5
        pygame.draw.line(canvas, BAMBOO[1], (c[0] - nx * h, c[1] - ny * h), (c[0] + nx * h, c[1] + ny * h), 1)
        d += node
    for j in range(5):   # 손잡이 감은 끈
        c = (a[0] + ux * (20 + j * 3), a[1] + uy * (20 + j * 3))
        h = w0 / 2 + 0.5
        pygame.draw.line(canvas, STAND[2], (c[0] - nx * h, c[1] - ny * h), (c[0] + nx * h, c[1] + ny * h), 1)


# ───────────────────────── 손 (낚시 화면 손 색 · 장갑 규칙) ─────────────────────────
def _hand_cols(hand_pal: dict, look: dict | None, light: float = 0.86):
    look = look or {}
    skin, shadow = tuple(hand_pal["hand"]), tuple(hand_pal["hand_shadow"])
    glove = look.get("glove")
    if glove is not None:
        skin = tuple(glove)
        shadow = scale_color(skin, 0.72)
    return scale_color(skin, light), scale_color(shadow, light), scale_color(tuple(hand_pal["sleeve"]), light * 0.9), glove is not None


def make_open_hand(hand_pal, look, size: float = 1.0) -> tuple[pygame.Surface, tuple[int, int], tuple[int, int]]:
    """오른손 손등 (손가락을 왼쪽 위로 펴고 쓸어내는 모양). 돌려줌: (그림, 손바닥 중심, 손끝 중심)."""
    skin, shadow, _, gloved = _hand_cols(hand_pal, look)
    mitten = bool((look or {}).get("mitten"))
    k = size
    s = pygame.Surface((int(64 * k), int(56 * k)), pygame.SRCALPHA)
    pc = (int(38 * k), int(36 * k))                                                # 손등 가운데
    d = (-0.62, -0.78)                                                             # 손가락 방향
    if mitten:
        tip = (pc[0] + d[0] * 26 * k, pc[1] + d[1] * 26 * k)
        pygame.draw.line(s, shadow, (pc[0] + 2, pc[1] + 2), (tip[0] + 2, tip[1] + 2), int(17 * k))
        pygame.draw.line(s, skin, pc, tip, int(16 * k))
        pygame.draw.circle(s, skin, (int(tip[0]), int(tip[1])), int(8 * k))
    else:
        base = [(-9, 3), (-4, -2), (2, -5), (8, -6)]                               # 손가락 뿌리 (검지 → 새끼, 손등 기준)
        lens = [17, 19, 17, 13]
        for (bx, by), ln in zip(base, lens):
            a = (pc[0] + bx * k, pc[1] + by * k)
            b = (a[0] + d[0] * ln * k, a[1] + d[1] * ln * k)
            pygame.draw.line(s, shadow, (a[0] + 1, a[1] + 1), (b[0] + 1, b[1] + 1), max(3, int(5 * k)))
            pygame.draw.line(s, skin, a, b, max(3, int(5 * k)))
            pygame.draw.circle(s, skin, (int(b[0]), int(b[1])), max(1, int(2.4 * k)))
        tip = (pc[0] + (-4 + d[0] * 20) * k, pc[1] + (-2 + d[1] * 20) * k)
    pygame.draw.ellipse(s, shadow, (pc[0] - 13 * k, pc[1] - 9 * k, 28 * k, 22 * k))  # 손등
    pygame.draw.ellipse(s, skin, (pc[0] - 14 * k, pc[1] - 10 * k, 26 * k, 20 * k))
    pygame.draw.line(s, skin, (pc[0] - 10 * k, pc[1] + 6 * k), (pc[0] - 21 * k, pc[1] + 1 * k), max(3, int(6 * k)))  # 엄지 (왼쪽)
    if gloved:   # 니트 짜임 줄
        for j in range(3):
            y = pc[1] - 5 * k + j * 5 * k
            pygame.draw.line(s, scale_color(skin, 0.82), (pc[0] - 9 * k, y), (pc[0] + 8 * k, y - 2 * k), 1)
    else:   # 손가락 마디 밝게
        for bx, by in [(-9, 3), (-4, -2), (2, -5)]:
            s.fill(scale_color(skin, 1.1), (int(pc[0] + bx * k), int(pc[1] + by * k), 2, 1))
    return _outline(s), pc, (int(tip[0]), int(tip[1]))


def make_point_hand(hand_pal, look, size: float = 1.0) -> tuple[pygame.Surface, tuple[int, int]]:
    """오른손 검지 하나를 펴서 왼쪽 위로 (나머지는 쥠). 돌려줌: (그림, 손끝)."""
    skin, shadow, _, gloved = _hand_cols(hand_pal, look)
    k = size
    s = pygame.Surface((int(70 * k), int(70 * k)), pygame.SRCALPHA)
    fist = (int(42 * k), int(50 * k))
    d = (-0.5, -0.86)
    tip = (fist[0] - 6 * k + d[0] * 34 * k, fist[1] - 8 * k + d[1] * 34 * k)
    pygame.draw.line(s, shadow, (fist[0] - 5 * k, fist[1] - 7 * k), (tip[0] + 1, tip[1] + 1), max(3, int(6 * k)))
    pygame.draw.line(s, skin, (fist[0] - 6 * k, fist[1] - 8 * k), tip, max(3, int(6 * k)))
    pygame.draw.circle(s, skin, (int(tip[0]), int(tip[1])), max(2, int(3 * k)))
    if not gloved:
        s.fill(scale_color(skin, 1.16), (int(tip[0]) - 1, int(tip[1]) - 2, 2, 1))   # 손톱
    pygame.draw.ellipse(s, shadow, (fist[0] - 13 * k, fist[1] - 11 * k, 28 * k, 24 * k))
    pygame.draw.ellipse(s, skin, (fist[0] - 14 * k, fist[1] - 12 * k, 26 * k, 22 * k))
    for j in range(3):   # 쥔 손가락 마디
        y = fist[1] - 4 * k + j * 4 * k
        pygame.draw.line(s, scale_color(skin, 0.8), (fist[0] - 10 * k, y), (fist[0] - 3 * k, y + 1), 1)
    return _outline(s), (int(tip[0]), int(tip[1]))


def make_fist(hand_pal, look, size: float = 1.0, left: bool = False) -> pygame.Surface:
    """낚싯대를 아래에서 쥔 주먹 (손가락이 대를 감싸 위로 보임). 가운데 = 대를 쥔 자리."""
    skin, shadow, _, gloved = _hand_cols(hand_pal, look)
    k = size
    s = pygame.Surface((int(34 * k), int(30 * k)), pygame.SRCALPHA)
    c = (s.get_width() // 2, s.get_height() // 2)
    pygame.draw.ellipse(s, shadow, (c[0] - 12 * k, c[1] - 7 * k, 26 * k, 20 * k))
    pygame.draw.ellipse(s, skin, (c[0] - 13 * k, c[1] - 8 * k, 24 * k, 18 * k))
    for j in range(4):   # 대를 감싼 손가락 4개
        x = c[0] - 9 * k + j * 5 * k
        pygame.draw.line(s, scale_color(skin, 0.78), (x, c[1] - 6 * k), (x, c[1] + 2 * k), 1)
    tx = c[0] + (9 if left else -9) * k
    pygame.draw.line(s, skin, (tx, c[1] + 4 * k), (c[0], c[1] - 5 * k), max(3, int(5 * k)))   # 엄지가 대 위로
    if gloved:
        pygame.draw.line(s, scale_color(skin, 0.82), (c[0] - 10 * k, c[1] + 5 * k), (c[0] + 9 * k, c[1] + 5 * k), 1)
    return _outline(s)


def _sleeve(canvas, col, wrist, out, width: float) -> None:
    """손목에서 화면 밖까지 소매 (굵은 사각 띠)."""
    dx, dy = out[0] - wrist[0], out[1] - wrist[1]
    ln = math.hypot(dx, dy) or 1
    nx, ny = -dy / ln * width / 2, dx / ln * width / 2
    poly = [(wrist[0] + nx, wrist[1] + ny), (out[0] + nx * 1.3, out[1] + ny * 1.3),
            (out[0] - nx * 1.3, out[1] - ny * 1.3), (wrist[0] - nx, wrist[1] - ny)]
    pygame.draw.polygon(canvas, col, poly)
    pygame.draw.polygon(canvas, OUT, poly, 1)
    pygame.draw.line(canvas, scale_color(col, 1.18), (wrist[0] + nx * 0.6, wrist[1] + ny * 0.6),
                     (out[0] + nx * 0.8, out[1] + ny * 0.8), 1)


class StoryRock:
    """장면 A~E 를 t(초)로 그림. hand_pal = 팔레트(hand · hand_shadow · sleeve), hand_look = fishing._hand_look() (계절 장갑)."""

    def __init__(self, w: int, h: int, hand_pal: dict, hand_look: dict | None = None, reduce: bool = False):
        self.w, self.h = w, h
        self.cx = w // 2
        self.ox = (w - 480) // 2
        self.reduce = reduce
        self.hand_pal = hand_pal
        self.look = hand_look or {}
        self.sleeve = _hand_cols(hand_pal, hand_look)[2]
        self.rnd = random.Random(302)
        self._bake_a()
        self._bake_b()
        self._bake_c()
        self._bake_d()
        self._bake_e()
        self.hand_open = make_open_hand(hand_pal, hand_look, 1.5)
        self.hand_point = make_point_hand(hand_pal, hand_look, 1.9)
        self.fist_r = make_fist(hand_pal, hand_look, 1.4)
        self.fist_l = make_fist(hand_pal, hand_look, 1.4, left=True)
        self.blobs = [_blob(220, 46, MIST, 150), _blob(160, 34, MIST, 170), _blob(260, 60, MIST, 120)]
        self._tmp = pygame.Surface((w, h))

    # ───────── 굽기 ─────────
    def _bake_a(self) -> None:
        """장면 A 배경 (가로 w + 60 — 팬 40px + 여유): 하늘 · 협곡 절벽 · 폭포 뒤 바위벽 · 웅덩이 · 물가 바위 · 오른쪽 끝 바위 실루엣."""
        W, H = self.w + 60, self.h
        rnd = random.Random(11)
        s = pygame.Surface((W, H))
        _vgrad(s, pygame.Rect(0, 0, W, 130), SKY[0], SKY[1])
        s.fill(SKY[1], (0, 130, W, H - 130))
        fc = W // 2                                   # 폭포 가운데 (월드)
        self.fall_x = fc
        self.fall_rect = pygame.Rect(fc - 62, 20, 124, 166)
        for i, col in enumerate((lerp_color(CLIFF[1], SKY[1], 0.55), lerp_color(CLIFF[1], SKY[1], 0.3))):   # 먼 능선 2겹
            pts = [(0, H)]
            for x in range(0, W + 20, 20):
                pts.append((x, 70 + i * 22 + 16 * math.sin(x * 0.013 + i * 2) + rnd.uniform(-4, 4)))
            pts.append((W, H))
            pygame.draw.polygon(s, col, pts)
        s.fill(CLIFF[0], (fc - 84, 14, 168, 180))     # 폭포 뒤 바위벽
        for side in (-1, 1):                          # 양옆 절벽 (짙은 청회색 + 이끼 점)
            edge = fc + side * 64
            pts = [(edge, 10)]
            y = 10
            while y < 214:
                y += rnd.randint(10, 22)
                pts.append((edge + side * rnd.randint(-6, 14) + side * (y - 10) * 0.08, min(214, y)))
            far = 0 if side < 0 else W
            pts += [(far, 214), (far, 10)]
            pygame.draw.polygon(s, CLIFF[1], pts)
            for _ in range(160):
                x = rnd.randint(min(edge, far), max(edge, far))
                yy = rnd.randint(14, 210)
                inside = (x - edge) * side > 6
                if inside:
                    c = rnd.choice((CLIFF[0], CLIFF[2], CLIFF[0]))
                    s.fill(c, (x, yy, rnd.randint(2, 7), 1))
            for _ in range(70):
                x = rnd.randint(min(edge, far), max(edge, far))
                if (x - edge) * side > 4:
                    yy = rnd.randint(30, 212)
                    s.fill(rnd.choice(MOSS), (x, yy, rnd.randint(1, 3), rnd.randint(1, 2)))
            for _ in range(12):                       # 세로 결 (물이 흘러내린 골, 구불구불)
                x = rnd.randint(min(edge, far), max(edge, far))
                if (x - edge) * side > 8:
                    y = rnd.randint(14, 120)
                    for _ in range(rnd.randint(8, 20)):
                        s.fill(CLIFF[0], (x, y, 1, 4))
                        x += rnd.choice((-1, 0, 0, 1))
                        y += 4
            for _ in range(7):                        # 바위 턱 (기울어진 밝은 윗면 + 그늘 + 이끼)
                y = rnd.randint(30, 200)
                x0 = edge + side * rnd.randint(10, 40)
                ln = rnd.randint(24, 70)
                pts_l = [(x0 + side * j * ln / 4, y + rnd.randint(-2, 2) + j * rnd.choice((-1, 1))) for j in range(5)]
                pygame.draw.lines(s, CLIFF[2], False, pts_l, 1)
                pygame.draw.lines(s, CLIFF[0], False, [(x, yy + 1) for x, yy in pts_l], 2)
                for _ in range(ln // 5):
                    px_, py_ = pts_l[rnd.randrange(5)]
                    s.fill(rnd.choice(MOSS), (int(px_ + rnd.randint(-6, 6)), int(py_) - 1, rnd.randint(2, 4), 1))
            pygame.draw.lines(s, CLIFF[2], False, pts[:-2], 1)   # 절벽 끝 밝은 선
        shade = pygame.Surface((W, 200), pygame.SRCALPHA)      # 아래로 갈수록 어둡게 (물보라 그늘)
        for y in range(200):
            shade.fill((14, 20, 28, int(70 * (y / 200) ** 2)), (0, y, W, 1))
        s.blit(shade, (0, 14))
        _vgrad(s, pygame.Rect(0, 190, W, H - 190), POOL[1], POOL[0])   # 웅덩이
        for _ in range(60):
            x, y = rnd.randint(0, W), rnd.randint(196, H - 20)
            s.fill(POOL[2] if rnd.random() < 0.4 else lerp_color(POOL[1], POOL[2], 0.4), (x, y, rnd.randint(4, 14), 1))
        for wx, by, rw, rh, sd in ((fc - 150, 232, 70, 34, 1), (fc - 205, 248, 96, 40, 2), (fc + 120, 238, 64, 28, 3),
                                   (fc + 60, 252, 110, 34, 4), (fc - 60, 258, 80, 22, 5), (fc - 112, 200, 40, 14, 6),
                                   (fc + 90, 204, 34, 12, 7)):   # 물가 바위들
            r = rock_sprite(rw, rh, sd, cracks=1, moss=0.8)
            s.blit(r, (wx - rw // 2, by - rh))
        sil = rock_sprite(92, 58, 99, cracks=0, moss=0.4, outline=False)   # 오른쪽 끝 바위 (안개 속 흐릿한 실루엣)
        wash = pygame.Surface(sil.get_size(), pygame.SRCALPHA)
        wash.fill((*lerp_color(ROCK[1], MIST, 0.5), 255))
        _clip_to(wash, sil)
        wash.set_alpha(150)
        self.sil_x = fc + 222
        s.blit(wash, (self.sil_x - 46, 214 - 58))
        self.bg_a = s
        tile = pygame.Surface((124, 64))               # 물줄기 줄무늬 (아래로 흐름, 줄기 5개)
        strips = [(-62, -41, FALL[2]), (-41, -15, FALL[1]), (-15, 11, FALL[0]), (11, 36, FALL[1]), (36, 62, FALL[2])]
        for x0, x1, base in strips:
            tile.fill(base, (x0 + 62, 0, x1 - x0, 64))
            for _ in range((x1 - x0) * 3):
                x = rnd.randint(x0 + 62, x1 + 61)
                y = rnd.randint(0, 63)
                ln = rnd.randint(4, 14)
                c = rnd.choice((FALL[0], FALL[1], FALL[3], FALL[0]))
                for yy in range(ln):
                    tile.set_at((x, (y + yy) % 64), c)
            tile.fill(FALL[3], (x1 + 61, 0, 1, 64))    # 줄기 사이 그늘
        self.fall_tile = tile

    def _bake_b(self) -> None:
        """장면 B: 안개 · 젖은 바위 길(아래 1/3, 소실점으로 모임) · 양옆 얕은 물. 바위 스프라이트(140×88)는 크기만 바꿔 씀."""
        W, H = self.w, self.h
        rnd = random.Random(21)
        s = pygame.Surface((W, H))
        _vgrad(s, pygame.Rect(0, 0, W, 180), lerp_color(SKY[1], MIST, 0.3), lerp_color(MIST, SKY[1], 0.15))
        for side in (-1, 1):                           # 안개 속 절벽 그림자
            col = lerp_color(CLIFF[1], MIST, 0.72)
            pts = [(self.cx + side * 120, 180), (self.cx + side * 150, 40), (self.cx + side * (W // 2 + 10), 30), (self.cx + side * (W // 2 + 10), 180)]
            pygame.draw.polygon(s, col, pts)
        for x in range(26):                              # 먼 폭포 (왼쪽 안개 속 흰 띠, 가장자리 옅게 · 아래로 퍼짐)
            k = 1 - abs(x - 12.5) / 13
            col = lerp_color(lerp_color(CLIFF[1], MIST, 0.72), lerp_color(FALL[0], MIST, 0.4), k)
            pygame.draw.line(s, col, (self.cx - 175 + x, 34), (self.cx - 175 + x + (x - 12.5) * 0.4, 180))
        vp = (self.cx, 172)
        self.vp = vp
        _vgrad(s, pygame.Rect(0, 172, W, H - 172), lerp_color(POOL[1], MIST, 0.4), POOL[0])   # 얕은 물
        path = [(vp[0] - 26, vp[1]), (vp[0] + 26, vp[1]), (self.cx + 210, H), (self.cx - 210, H)]
        pygame.draw.polygon(s, (60, 66, 74), path)       # 젖은 바위 길
        for k in range(1, 9):                            # 판석 이음매 (원근)
            y = vp[1] + (H - vp[1]) * (k / 9) ** 1.7
            half = 26 + (210 - 26) * (y - vp[1]) / (H - vp[1])
            pygame.draw.line(s, (42, 46, 54), (self.cx - half, y), (self.cx + half, y), 1)
            for j in range(-2, 3):
                xx = self.cx + j * half * 0.4 + (k % 2) * half * 0.2
                pygame.draw.line(s, (42, 46, 54), (xx, y), (xx + (xx - self.cx) * 0.12, y + 3 + k), 1)
        for _ in range(140):                             # 물기 반짝임
            y = rnd.uniform(vp[1] + 2, H)
            half = 26 + (210 - 26) * (y - vp[1]) / (H - vp[1])
            x = self.cx + rnd.uniform(-half, half)
            s.fill(rnd.choice(((150, 170, 178), (110, 124, 134))), (int(x), int(y), rnd.randint(1, 4), 1))
        self.bg_b = s
        self.rock_b = rock_sprite(140, 88, 7, cracks=2, moss=1.0)

    def _bake_c(self) -> None:
        """장면 C: 바위 미디엄 샷 (가운데 2/3), 가운데 이끼 덮인 네모 — 그 밑에 새김(작게)이 미리 그려짐."""
        W, H = self.w, self.h
        s = pygame.Surface((W, H))
        _vgrad(s, pygame.Rect(0, 0, W, H), lerp_color(SKY[1], MIST, 0.45), lerp_color(POOL[1], MIST, 0.25))
        rock = rock_sprite(340, 240, 7, cracks=3, moss=1.4)
        rx, ry = self.cx - 170, 34
        s.blit(rock, (rx, ry))
        self.patch = pygame.Rect(self.cx - 52, 104, 104, 52)
        p = self.patch
        s.fill(scale_color(ROCK[1], 0.94), p)              # 새김 자리는 조금 매끈하게
        self._carve(s, p.center, 16, small=True)
        self.bg_c = s
        rnd = random.Random(31)                            # 이끼 칸 (4×4) — 쓸릴 때 사라짐
        self.cells = []
        cols, rows = p.w // 4, p.h // 4
        for r in range(rows):
            for c in range(cols):
                x, y = p.x + c * 4, p.y + r * 4
                edge = c in (0, cols - 1) or r in (0, rows - 1)
                keep = edge and rnd.random() < 0.35         # 가장자리 몇 칸은 남음 (새김은 덮지 않게)
                sweep = 0 if r < rows // 2 else 1
                self.cells.append((x, y, rnd.choice(MOSS), sweep, keep, rnd.random()))

    def _carve(self, s, center, size: int, small: bool = False) -> pygame.Rect:
        """'해강' 새김 + 오른쪽 선 3개 물고기. 홈 = 어두운 선 + 아래쪽 밝은 테두리 1px. 돌려줌: '해' 글자 영역."""
        f = get_font(size)
        word = "해강"
        dark = f.render(word, False, GROOVE)
        lite = f.render(word, False, RIM)
        fw = int(size * 1.25)                               # 물고기 폭
        tw = dark.get_width() + 8 + fw
        x0 = center[0] - tw // 2
        y0 = center[1] - dark.get_height() // 2
        s.blit(lite, (x0, y0 + 1))
        s.blit(dark, (x0, y0))
        if not small:                                       # 2px 굵기 (가로로 한 번 더)
            s.blit(dark, (x0 + 1, y0))
        fx, fy = x0 + dark.get_width() + 8, center[1]
        k = fw / 30
        lw = 1 if small else 2
        for col, dy in ((RIM, 1), (GROOVE, 0)):
            pygame.draw.arc(s, col, (fx, fy - 9 * k + dy, 24 * k, 18 * k), 0.2, math.pi - 0.2, lw)        # 등
            pygame.draw.arc(s, col, (fx, fy - 9 * k + dy, 24 * k, 18 * k), math.pi + 0.2, math.tau - 0.2, lw)   # 배
            pygame.draw.line(s, col, (fx + 24 * k, fy + dy), (fx + 31 * k, fy - 6 * k + dy), lw)          # 꼬리
            pygame.draw.line(s, col, (fx + 24 * k, fy + dy), (fx + 31 * k, fy + 6 * k + dy), lw)
        hae = f.render("해", False, GROOVE)
        return pygame.Rect(x0, y0, hae.get_width(), hae.get_height())

    def _bake_d(self) -> None:
        """장면 D: 바위 표면이 화면 가득 + '해강'(높이 40px) + 물고기. 손가락이 따라갈 '해' 홈 = 가장 긴 세로획."""
        W, H = self.w, self.h
        rnd = random.Random(41)
        s = pygame.Surface((W, H))
        s.fill(ROCK[1])
        for _ in range(W * H // 18):
            x, y = rnd.randrange(W), rnd.randrange(H)
            s.fill(scale_color(ROCK[1], rnd.choice((0.86, 0.92, 1.07, 1.12))), (x, y, rnd.choice((1, 2, 3)), 1))
        pygame.draw.ellipse(s, scale_color(ROCK[1], 1.08), (self.cx - 260, -80, 360, 220))   # 왼쪽 위 빛
        for _ in range(W * H // 60):
            x, y = rnd.randrange(W), rnd.randrange(H)
            s.fill(scale_color(ROCK[1], rnd.choice((0.9, 1.1))), (x, y, 2, 1))
        for k in range(2):                                  # 갈라진 금 · 물 흐른 줄
            x = self.cx + (-170 if k == 0 else 175)
            pts = [(x, 18)]
            y = 18
            while y < H:
                y += rnd.randint(12, 26)
                x += rnd.randint(-8, 8)
                pts.append((x, y))
            pygame.draw.lines(s, GROOVE, False, pts, 1)
            pygame.draw.lines(s, RIM, False, [(px + 1, py + 1) for px, py in pts], 1)
        for y in range(18, H):
            xx = self.cx + 128 + int(math.sin(y * 0.1) * 2)
            s.fill(scale_color(ROCK[1], 0.84), (xx, y, 3, 1))
        size = 40
        f = get_font(size)
        hae_s = f.render("해", False, GROOVE)
        hae = self._carve(s, (self.cx, 128), size)
        for _ in range(6):                                  # 홈 둘레 이끼 남은 자국
            x = rnd.randint(hae.x - 10, hae.x + 160)
            y = rnd.choice((hae.y - 6, hae.bottom + 4))
            s.fill(rnd.choice(MOSS), (x, y, rnd.randint(2, 4), 2))
        m = pygame.mask.from_surface(hae_s)                # '해' 의 가장 긴 세로획 (오른쪽 40% 안)
        best, bx = -1, 0
        for x in range(int(hae_s.get_width() * 0.6), hae_s.get_width()):
            n = sum(1 for y in range(hae_s.get_height()) if m.get_at((x, y)))
            if n > best:
                best, bx = n, x
        ys = [y for y in range(hae_s.get_height()) if m.get_at((bx, y))]
        self.groove = (hae.x + bx, hae.y + min(ys), hae.y + max(ys))
        self.bg_d = s

    def _bake_e(self) -> None:
        """장면 E: 앉은 시점 — 멀리 작게 안개 낀 폭포(장면 A 의 물줄기를 줄여서), 협곡 절벽, 웅덩이, 앞쪽 젖은 바위, 받침대 2개."""
        W, H = self.w, self.h
        rnd = random.Random(51)
        s = pygame.Surface((W, H))
        _vgrad(s, pygame.Rect(0, 0, W, 150), SKY[0], lerp_color(SKY[1], MIST, 0.3))
        fall = pygame.Rect(self.cx - 34, 46, 68, 100)
        self.e_fall = fall
        self.e_tile = pygame.transform.scale(self.fall_tile, (68, 35))
        s.fill(lerp_color(CLIFF[0], MIST, 0.25), fall.inflate(16, 6))      # 폭포 뒤 바위벽
        for side in (-1, 1):                                               # 협곡 절벽 (멀리 → 안개로 옅게)
            col = lerp_color(CLIFF[1], MIST, 0.35)
            edge = self.cx + side * 36
            pts = [(edge, 40)]
            y = 40
            while y < 150:
                y += rnd.randint(8, 16)
                pts.append((edge + side * (rnd.randint(-2, 8) + (y - 40) * 0.25), min(150, y)))
            far = -2 if side < 0 else W + 2
            pts += [(far, 150), (far, 34 + rnd.randint(0, 20))]
            pygame.draw.polygon(s, col, pts)
            pygame.draw.lines(s, lerp_color(CLIFF[2], MIST, 0.3), False, pts[:-2], 1)
            for _ in range(60):
                x = rnd.randint(min(edge, far), max(edge, far))
                if (x - edge) * side > 6:
                    s.fill(rnd.choice((lerp_color(MOSS[0], MIST, 0.4), lerp_color(CLIFF[0], MIST, 0.3))),
                           (x, rnd.randint(46, 148), rnd.randint(1, 4), 1))
        _vgrad(s, pygame.Rect(0, 146, W, 54), lerp_color(POOL[1], MIST, 0.4), POOL[1])   # 웅덩이
        for _ in range(50):
            s.fill(lerp_color(POOL[2], MIST, 0.3), (rnd.randint(0, W), rnd.randint(150, 198), rnd.randint(4, 12), 1))
        for wx, by, rw, rh, sd in ((self.cx - 150, 292, 280, 110, 61), (self.cx + 150, 300, 300, 118, 62),
                                   (self.cx - 10, 280, 150, 68, 63)):   # 앞쪽 젖은 바위 (앉은 자리)
            r = rock_sprite(rw, rh, sd, cracks=2, moss=1.2)
            s.blit(r, (wx - rw // 2, by - rh))
        self.f1 = (self.cx + 74, 214)                       # 받침대 갈래 (낚싯대가 걸리는 곳) — 대는 오른쪽 아래에서 폭포 쪽으로
        self.f2 = (self.cx + 6, 182)
        draw_stand(s, self.f1[0], self.f1[1] + 52, 52)
        draw_stand(s, self.f2[0], self.f2[1] + 36, 36)
        self.bg_e = s

    # ───────── 장면 ─────────
    def _bars(self, canvas) -> None:
        canvas.fill((0, 0, 0), (0, 0, self.w, BAR))
        canvas.fill((0, 0, 0), (0, self.h - BAR, self.w, BAR))

    def _mist(self, canvas, t: float, specs) -> None:
        for i, (bi, x, y, amp, spd) in enumerate(specs):
            b = self.blobs[bi]
            canvas.blit(b, (int(x + math.sin(t * spd + i * 1.7) * amp - b.get_width() / 2), int(y - b.get_height() / 2)))

    def _fall(self, canvas, t: float, x0: int, rect: pygame.Rect) -> None:
        """물줄기 4~5겹 줄무늬가 아래로 (초당 40px)."""
        clip = canvas.get_clip()
        r = pygame.Rect(x0, rect.y, rect.w, rect.h)
        canvas.set_clip(r)
        off = int(t * 40) % 64
        y = rect.y - 64 + off
        while y < rect.bottom:
            canvas.blit(self.fall_tile, (x0, y))
            y += 64
        canvas.set_clip(clip)
        canvas.fill(FALL[0], (x0, rect.y, rect.w, 3))       # 폭포 머리 흰 거품
        canvas.fill(FALL[1], (x0 + 3, rect.y + 3, rect.w - 6, 1))

    def scene_a(self, canvas, t: float) -> None:
        pan = 10 + 40 * ease(t / 3.0)
        px = int(round(pan))
        canvas.blit(self.bg_a, (-px, 0))
        fr = self.fall_rect
        self._fall(canvas, t, fr.x - px, fr)
        base = fr.bottom - px
        for i in range(16):                                 # 폭포 밑 흰 물거품 띠 (크기가 다른 덩어리가 출렁)
            bx = fr.x - px - 10 + i * 9
            bw = 14 + 6 * math.sin(t * 3.1 + i * 1.3)
            bh = 6 + 3 * math.sin(t * 2.3 + i * 0.7)
            col = FALL[0] if i % 3 else FALL[1]
            pygame.draw.ellipse(canvas, col, (bx - bw / 2 + 5, fr.bottom - 4 - bh / 2 + (i % 2) * 2, bw, bh))
        self._mist(canvas, t, [(2, self.fall_x - px, 188, 26, 0.35), (0, self.fall_x - px - 70, 200, 18, 0.5),
                               (1, self.fall_x - px + 80, 196, 22, 0.42), (0, self.sil_x - px + 6, 196, 8, 0.3),
                               (1, self.sil_x - px - 20, 178, 10, 0.25)])
        rnd = random.Random(5)
        for i in range(44):                                 # 물보라 점 (폭포 밑에서 튀어 오름)
            life = rnd.uniform(0.8, 1.4)
            age = (t + rnd.uniform(0, life)) % life
            x = self.fall_x - px + rnd.uniform(-70, 70) + rnd.uniform(-24, 24) * age
            y = base - 2 - rnd.uniform(30, 64) * age + 46 * age * age
            if 0 <= x < self.w and BAR <= y < self.h - BAR:
                canvas.fill(FALL[0], (int(x), int(y), 1, 1))
        for i in range(22):                                 # 공중 물방울 (천천히 날림)
            x = (rnd.uniform(0, self.w + 60) + t * 9) % (self.w + 60) - px
            y = (rnd.uniform(BAR, self.h) + t * 14) % (self.h - 2 * BAR) + BAR
            canvas.fill(lerp_color(FALL[1], MIST, 0.5), (int(x), int(y), 1, 1))

    def scene_b(self, canvas, t: float) -> None:
        u = _seg(t, 3.0, 5.0)
        walking = t < 5.0 and not self.reduce
        dy = int(round(math.sin(math.tau * (t - 3.0) / 0.5))) if walking else 0
        tmp = self._tmp
        tmp.blit(self.bg_b, (0, 0))
        vp = self.vp
        rnd = random.Random(8)
        for i in range(26):                                 # 지나가는 길바닥 반짝임 (소실점에서 앞으로)
            ph = (rnd.random() + (t - 3.0) * 0.55 * (1 - _seg(t, 4.8, 5.1))) % 1.0
            side = rnd.uniform(-1, 1)
            y = vp[1] + (self.h - vp[1]) * ph ** 1.8
            half = 26 + 184 * (y - vp[1]) / (self.h - vp[1])
            tmp.fill((156, 174, 182), (int(self.cx + side * half * 0.9), int(y), 1 + int(ph * 3), 1))
        rw = int(80 + 60 * ease(u))                         # 바위가 점점 커짐 (80 → 140)
        rh = int(88 * rw / 140)
        rock = pygame.transform.scale(self.rock_b, (rw, rh))
        rock.set_alpha(int(255 * (0.4 + 0.6 * ease(u))))
        tmp.blit(rock, (self.cx - rw // 2, vp[1] + 6 - rh))
        if t >= 4.8:                                        # 받침대 2개 (안개에서 나타남)
            al = int(255 * ease(_seg(t, 4.8, 5.2)))
            for x in (-34, 30):
                draw_stand(tmp, self.cx + x, vp[1] + 16, 26, al)
        veil = 0.6 * (1 - ease(u)) + 0.12                   # 앞쪽 안개 (옅어짐)
        mv = pygame.Surface((self.w, self.h), pygame.SRCALPHA)
        mv.fill((*MIST, int(255 * veil * 0.55)))
        tmp.blit(mv, (0, 0))
        k = len(self.blobs)
        for i in range(6):                                  # 안개가 양옆으로 갈라지며 지나감
            ph = ((t - 3.0) * 0.7 + i / 6) % 1.0
            if t >= 5.0:
                ph = ((5.0 - 3.0) * 0.7 + i / 6) % 1.0 + (t - 5.0) * 0.15
                if ph > 1:
                    continue
            side = -1 if i % 2 else 1
            sc = 0.35 + 1.9 * ph
            b = self.blobs[i % k]
            bw, bh = int(b.get_width() * sc), int(b.get_height() * sc)
            if bw < 4 or bh < 2:
                continue
            img = pygame.transform.scale(b, (bw, bh))
            img.set_alpha(int(255 * math.sin(math.pi * ph)))
            x = self.cx + side * (12 + 300 * ph * ph) - bw / 2
            y = vp[1] - 24 - 30 * ph - bh / 2
            tmp.blit(img, (int(x), int(y)))
        canvas.fill((0, 0, 0))
        canvas.blit(tmp, (0, dy))

    def _moss(self, canvas, t: float) -> None:
        p = self.patch
        x0, x1 = p.x - 4, p.right + 4
        for x, y, col, sweep, keep, r in self.cells:
            ta = 6.3 if sweep == 0 else 7.2
            tc = ta + 0.6 * (x - x0) / (x1 - x0)
            if keep or t < tc:
                canvas.fill(col, (x, y, 4, 4))
                if r < 0.3:
                    canvas.fill(MOSS[2], (x + 1, y, 2, 1))
            elif r < 0.07 and t - tc < 0.9:                 # 떨어지는 이끼 조각 (쓸릴 때 몇 개만)
                a = t - tc
                canvas.fill(col, (int(x + 6 * a), int(y + 30 * a + 70 * a * a), 2, 2))

    def scene_c(self, canvas, t: float) -> None:
        canvas.blit(self.bg_c, (0, 0))
        self._moss(canvas, t)
        p = self.patch
        img, pc, tip = self.hand_open
        lt, rt = (p.x - 2, p.y + 12), (p.right + 4, p.y + 12)
        lb, rb = (p.x - 2, p.y + 38), (p.right + 4, p.y + 38)
        off_in, off_out = (self.w + 40, self.h + 40), (self.w + 30, self.h + 70)
        if t < 6.0 or t >= 8.5:
            return
        if t < 6.3:
            f = _lerp(off_in, lt, ease(_seg(t, 6.0, 6.3)))
        elif t < 6.9:
            f = _lerp(lt, rt, _seg(t, 6.3, 6.9))
        elif t < 7.2:
            u = _seg(t, 6.9, 7.2)
            f = _lerp(rt, lb, ease(u))
            f = (f[0], f[1] - 10 * math.sin(math.pi * u))   # 들어 올렸다 다시 대기
        elif t < 7.8:
            f = _lerp(lb, rb, _seg(t, 7.2, 7.8))
        elif t < 8.1:
            f = rb
        else:
            f = _lerp(rb, off_out, ease(_seg(t, 8.1, 8.5)))
        hx, hy = f[0] - tip[0], f[1] - tip[1]               # 손끝이 f 에
        wrist = (hx + pc[0] + 18, hy + pc[1] + 13)
        _sleeve(canvas, self.sleeve, wrist, (wrist[0] + 90, wrist[1] + 110), 28)
        canvas.blit(img, (int(hx), int(hy)))

    def scene_d(self, canvas, t: float) -> None:
        canvas.blit(self.bg_d, (0, 0))
        gx, gy0, gy1 = self.groove
        stop = gy0 + (gy1 - gy0) * 0.62
        if t >= 10.2:                                       # 물방울 한 방울이 홈을 따라 아래로 (+ 젖은 자국)
            u = _seg(t, 10.2, 11.0)
            y = stop + (gy1 + 30 - stop) * u * u
            canvas.fill(scale_color(GROOVE, 0.7), (gx - 1, int(stop), 2, max(0, int(y - stop) - 2)))   # 젖은 자국
            canvas.fill((150, 182, 190), (gx - 1, int(y) - 3, 2, 2))
            canvas.fill((236, 248, 250), (gx - 1, int(y) - 1, 2, 3))                                    # 물방울
            canvas.fill((255, 255, 255), (gx - 1, int(y) - 1, 1, 1))
        if 8.95 <= t < 10.75:
            img, tip = self.hand_point
            if t < 9.35:
                f = _lerp((gx + 70, self.h + 30), (gx, gy0 + 2), ease(_seg(t, 8.95, 9.35)))
            elif t < 10.2:
                f = (gx, gy0 + 2 + (stop - gy0 - 2) * ease(_seg(t, 9.35, 10.2)))
            elif t < 10.3:
                f = (gx, stop)
            else:   # 손가락이 비켜 물방울이 보이게
                f = _lerp((gx, stop), (gx + 110, self.h + 80), ease(_seg(t, 10.3, 10.75)))
            hx, hy = f[0] - tip[0] + 1, f[1] - tip[1] + 1
            wrist = (hx + img.get_width() * 0.62, hy + img.get_height() * 0.86)
            _sleeve(canvas, self.sleeve, wrist, (wrist[0] + 80, wrist[1] + 100), 32)
            canvas.blit(img, (int(hx), int(hy)))

    def _rod_pose(self, t: float):
        """대 손잡이 · 끝 (받침대 두 갈래를 지나는 대각선). 11.4~12.2 아래에서 들어와 걸쳐짐, 12.6~ 끝이 바람에 1px."""
        f1, f2 = self.f1, self.f2
        d = (f2[0] - f1[0], f2[1] - f1[1])
        butt = (f1[0] - 1.9 * d[0], f1[1] - 1.9 * d[1] - 2)
        tip = (f1[0] + 2.7 * d[0], f1[1] + 2.7 * d[1] - 2)
        u = ease(_seg(t, 11.4, 12.2))
        drop = (1 - u) * 80
        rot = (1 - u) * 22
        butt = (butt[0], butt[1] + drop)
        tip = (tip[0] + rot, tip[1] + drop + rot * 0.9)
        if t >= 12.2:
            bounce = 1 if 12.2 <= t < 12.32 else 0
            sway = round(math.sin((t - 12.6) * 2.4)) if t >= 12.6 else 0
            butt = (butt[0], butt[1] + bounce)
            tip = (tip[0] + sway, tip[1] + bounce)
        return butt, tip

    def scene_e(self, canvas, t: float) -> None:
        canvas.blit(self.bg_e, (0, 0))
        fr = self.e_fall
        clip = canvas.get_clip()
        canvas.set_clip(fr)
        y = fr.y - 35 + int(t * 20) % 35
        while y < fr.bottom:
            canvas.blit(self.e_tile, (fr.x, y))
            y += 35
        canvas.set_clip(clip)
        canvas.fill(FALL[0], (fr.x, fr.y, fr.w, 2))
        self._mist(canvas, t, [(2, self.cx, 142, 16, 0.2), (0, self.cx - 80, 132, 22, 0.16), (1, self.cx + 90, 150, 18, 0.22),
                               (0, self.cx + 10, 96, 30, 0.12)])
        if t < 11.4:
            return
        butt, tip = self._rod_pose(t)
        if t >= 12.2:                                       # 끝에서 늘어진 줄 (물로)
            end = (tip[0] - 14, 176)
            pts = [_lerp(tip, end, u) for u in (0, 0.25, 0.5, 0.75, 1)]
            pts = [(x, y + 6 * math.sin(math.pi * i / 4)) for i, (x, y) in enumerate(pts)]
            pygame.draw.lines(canvas, (206, 214, 218), False, pts, 1)
        draw_bamboo(canvas, butt, tip, 5, 2)
        if t < 12.6:                                        # 두 손이 대를 쥐고 올렸다가 빠짐
            out = ease(_seg(t, 12.25, 12.6)) * 90
            for uu, img, sx in ((0.24, self.fist_r, 1), (0.5, self.fist_l, -1)):
                c = _lerp(butt, tip, uu)
                c = (c[0], c[1] + out)
                wrist = (c[0] + sx * 4, c[1] + 10)
                _sleeve(canvas, self.sleeve, wrist, (wrist[0] + sx * 40, wrist[1] + 120), 18)
                canvas.blit(img, (int(c[0] - img.get_width() / 2), int(c[1] - img.get_height() / 2)))

    def subtitle(self, canvas, t: float) -> None:
        if not 12.8 <= t < 14.6:
            return
        k = min(1.0, (t - 12.8) / 0.4, (14.6 - t) / 0.4)
        f = get_font(11)
        img = f.render(SUB, True, (236, 236, 240))
        img.set_alpha(int(255 * k))
        canvas.blit(img, (self.cx - img.get_width() // 2, self.h - BAR // 2 - img.get_height() // 2))

    def draw(self, canvas, t: float) -> None:
        if t < 3.0:
            self.scene_a(canvas, t)
        elif t < 5.5:
            self.scene_b(canvas, t)
            if t < 3.3:                                     # 0.3초 디졸브 (A → B)
                self._dissolve(canvas, self.scene_a, 2.99, 1 - _seg(t, 3.0, 3.3))
        elif t < 8.5:
            self.scene_c(canvas, t)
            if t < 5.75:
                self._dissolve(canvas, self.scene_b, 5.49, 1 - _seg(t, 5.5, 5.75))
        elif t < 11.0:
            self.scene_d(canvas, t)
        else:
            self.scene_e(canvas, t)
            if t < 11.4:                                    # 0.4초 디졸브 (D → E)
                self._dissolve(canvas, self.scene_d, 10.99, 1 - _seg(t, 11.0, 11.4))
        self._bars(canvas)
        self.subtitle(canvas, t)
        if t < 0.6:                                         # 검은 화면에서 0.6초 페이드 인
            s = pygame.Surface((self.w, self.h))
            s.set_alpha(int(255 * (1 - t / 0.6)))
            canvas.blit(s, (0, 0))

    def _dissolve(self, canvas, fn, at: float, a: float) -> None:
        if a <= 0:
            return
        tmp = pygame.Surface((self.w, self.h))
        fn(tmp, at)
        tmp.set_alpha(int(255 * a))
        canvas.blit(tmp, (0, 0))
