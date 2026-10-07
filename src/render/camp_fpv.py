"""모닥불 1인칭 캠프 장면 (CAMPFIRE_FPV.md, DESIGN.md 48-3b). 낚시터와 상관없는 산속 숲 빈터 하나.

좌표는 480×270 기준 (문서 🅰 표). 폰처럼 화면이 넓으면 가운데에 두고 양옆(나무 · 땅)을 이어 그림 (ox = (W − 480) // 2).
층 (뒤 → 앞): 하늘(가운데만 트임, 매 프레임) → 먼 산등성이 2겹 · 중간 숲 (구움 far) → 땅 · 가까운 나무 · 텐트 · 소품 · 불 뒤쪽 돌 (구움 near)
→ 장작 · 불꽃 · 걸이 · 주전자 (매 프레임) → 불 앞쪽 돌 · 머그컵 (구움 front) → 두 손 (매 프레임).
가까운 물체만 1px 외곽선 #2A2238, 먼 것은 외곽선 없음. 보라 없음 (밤하늘 남색).
계절(눈 쌓임 · 낙엽 · 들꽃 · 연두 가지 끝)은 구울 때 반영.
"""
import math
import random

import pygame

from src.core.mathutil import clamp, lerp_color, scale_color
from src.render import world

OUT = (0x2A, 0x22, 0x38)
BASE_W = 480
HORIZON = 118
FIRE = (252, 226)          # 불 중심 (돌 테두리 중심)
SKY_OPEN = (150, 330)      # 하늘이 트인 가로 구간
HAND_TOP = 196             # 손이 그려지는 띠 (이 아래만)

RIDGE_BACK = (0x5A, 0x6E, 0x86)
RIDGE_FRONT = (0x3E, 0x55, 0x60)
FOREST = ((0x2E, 0x4A, 0x40), (0x25, 0x40, 0x3A))
NEEDLE = ((34, 62, 44), (26, 50, 38))      # 가까운 나무 잎 2색
NEEDLE_TIP = (96, 150, 84)
BARK = ((112, 78, 52), (88, 60, 40), (64, 44, 30))   # 줄기 3단 (밝 · 중 · 어둠)
SOIL = ((132, 104, 74), (104, 80, 56))
GRASS = ((70, 98, 54), (44, 66, 40))   # 숲 바닥 (먼 쪽 → 가까운 쪽)
TENT = ((0xD9, 0x81, 0x3F), (0x9C, 0x52, 0x26), (0x7A, 0x3E, 0x1C))   # 불 쪽 · 그늘 · 이음매
STONE = ((150, 148, 144), (118, 116, 114), (84, 82, 84))
LOG = ((126, 92, 60), (96, 68, 44), (60, 42, 28))
SNOW = (236, 242, 250)


def _outlined(s: pygame.Surface) -> pygame.Surface:
    """그려진 픽셀 둘레 1px 외곽선."""
    m = pygame.mask.from_surface(s)
    o = m.to_surface(setcolor=OUT, unsetcolor=(0, 0, 0, 0))
    out = pygame.Surface(s.get_size(), pygame.SRCALPHA)
    for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
        out.blit(o, (dx, dy))
    out.blit(s, (0, 0))
    return out


def _crop(s: pygame.Surface) -> tuple[pygame.Surface, tuple[int, int]]:
    """그려진 칸만 잘라 (그림, 놓을 자리)."""
    r = s.get_bounding_rect()
    if r.w == 0 or r.h == 0:
        return pygame.Surface((1, 1), pygame.SRCALPHA), (0, 0)
    return s.subsurface(r).copy(), r.topleft


def no_purple(c) -> tuple:
    """보라는 환상 전용: 붉은기 + 푸른기가 함께 센 색(저녁 하늘 위쪽)은 남색 쪽으로."""
    r, g, b = c
    if b > g + 25 and r > g + 8:
        return (int(g * 0.8 + r * 0.2 * 0.5), int(g + (b - g) * 0.25), b)
    return (r, g, b)


class CampFPV:
    def __init__(self, w: int, h: int, season: str | None = None, snowy: bool = False, seed: int = 5):
        self.w, self.h = w, h
        self.ox = (w - BASE_W) // 2
        self.season = season
        self.snowy = snowy or season == "winter"
        self.rnd = random.Random(seed)
        self.far = pygame.Surface((w, h), pygame.SRCALPHA)
        self.ground = pygame.Surface((w, h), pygame.SRCALPHA)
        self.near = pygame.Surface((w, h), pygame.SRCALPHA)
        self.front = pygame.Surface((w, h), pygame.SRCALPHA)
        self._bake_far()
        self._bake_near()
        self._bake_front()
        self._bake_light()
        # 그리기 횟수 줄이기: 안 움직이는 층은 합치고 (먼 산 + 땅 / 가까운 것 + 장작 · 걸이 + 앞 돌), 빛 · 그림자 층은 쓰는 칸만
        self.back = self.far.copy()
        self.back.blit(self.ground, (0, 0))
        self.logs = self._bake_logs()
        self.mid = self.near.copy()
        self.mid.blit(self.logs, (0, 0))
        self.mid.blit(self.front, (0, 0))
        self.far = self.ground = self.near = self.front = None   # 합친 뒤엔 안 씀 (메모리)
        # 땅 쪽(y 124~)은 투명한 곳이 없으니 불투명 그림으로 (알파 섞기보다 빠름)
        bot = pygame.Surface((w, h - 124))
        bot.blit(self.back, (0, 0), (0, 124, w, h - 124))
        self.back_bot = bot
        self.back_top = self.back.subsurface((0, 0, w, 124)).copy()
        self.back = None
        self.lit, self.lit_at = _crop(self.lit)
        self.shadow_night, self.shadow_at = _crop(self.shadow_night)
        self.rim, self.rim_at = _crop(self.rim)
        # 움직임 (실제 시간) — CF2
        self.embers: list[list] = []     # [x, y, vy, life, age, phase]
        self.bits: list[list] = []       # 불꽃 조각 [x, y, age]
        self.smoke: list[list] = []      # [x, y, age, life, phase]
        self.ember_acc = self.smoke_acc = 0.0
        self.bit_t = 1.0
        self.prand = random.Random(seed + 9)
        self._cache: dict = {}
        self._dayshadow = pygame.Surface((w, h - 124), pygame.SRCALPHA)   # 땅 (y 124~) 만
        self._smoke_imgs = {}
        self._hand_cache: dict = {}
        # 하늘 별 (트인 구간 안, 40~60개)
        r = random.Random(seed + 1)
        self.stars = [(r.uniform(SKY_OPEN[0] + 4, SKY_OPEN[1] - 4), r.uniform(4, 96), r.uniform(0.5, 2.0), r.random())
                      for _ in range(r.randint(40, 60))]
        self.clouds = [(r.uniform(0, 1), r.uniform(10, 50), r.randint(18, 34)) for _ in range(3)]

    # ── 좌표 ──
    def X(self, x: float) -> int:
        return int(round(x + self.ox))

    # ───────────────── 구움: 먼 산 · 중간 숲 ─────────────────
    def _bake_far(self) -> None:
        s, w = self.far, self.w
        rnd = random.Random(21)

        def ridge(y0, y1, rise, col, top_y):
            pts = [(0, top_y + 30)]
            ys = []
            for x in range(0, w + 4, 4):
                u = x / w
                y = y0 - rise * u + 5 * math.sin(x * 0.021 + 0.7) + 3 * math.sin(x * 0.067)
                y = max(top_y, min(y1 - 6, y))
                pts.append((x, y))
                ys.append((x, y))
            pts += [(w, y1 + 8), (0, y1 + 8)]
            pygame.draw.polygon(s, col, pts)
            # 능선 위 2~3px 작은 침엽수 실루엣 줄
            for x, y in ys:
                if rnd.random() < 0.7:
                    hh = rnd.randint(2, 3)
                    pygame.draw.polygon(s, col, [(x - 1, y + 1), (x + 1, y - hh), (x + 3, y + 1)])
            return ys

        self.ridge_back = ridge(112, 118, 26, RIDGE_BACK, 82)
        self.ridge_front = ridge(122, 124, 20, RIDGE_FRONT, 96)
        if self.snowy:   # 먼 산 꼭대기 눈 (흐리게)
            for x, y in self.ridge_back[::2]:
                s.fill(lerp_color(RIDGE_BACK, SNOW, 0.55), (x, int(y), 4, 2))
        # 중간 숲 (y 100~140, 높이 24~40px, 2색, 줄기 안 보임)
        for k in range(2):
            col = FOREST[k]
            x = -8 + k * 7
            while x < w + 10:
                hh = rnd.randint(24, 40)
                base = 140 - k * 4 + rnd.randint(-2, 2)
                half = hh * 0.28
                pygame.draw.polygon(s, col, [(x - half, base), (x, base - hh), (x + half, base)])
                if self.snowy and rnd.random() < 0.6:
                    s.fill(lerp_color(col, SNOW, 0.6), (int(x - 1), base - hh + 3, 3, 1))
                x += rnd.randint(7, 13)
        s.fill(FOREST[1], (0, 134, w, 10))
        # 빈터 가장자리 중간 크기 나무 (외곽선 없음 — 공기 원근): 양옆이 닫힌 숲속 느낌
        for x, hh, base in ((176, 62, 160), (196, 46, 154), (306, 50, 156), (330, 66, 162), (-20 + self.ox * 0, 70, 166)):
            X = x + self.ox
            col = lerp_color(FOREST[0], (34, 58, 46), 0.4)
            s.fill((70, 54, 40), (X - 2, base - 12, 4, 12))
            for k in range(4):
                yy = base - 10 - k * hh / 4.5
                half = (hh * 0.32) * (1 - k * 0.2)
                pygame.draw.polygon(s, col if k % 2 else FOREST[1], [(X - half, yy), (X, yy - hh * 0.36), (X + half, yy)])
            if self.snowy:
                s.fill(SNOW, (X - 2, int(base - 10 - 3 * hh / 4.5 - hh * 0.3), 4, 1))
        for _ in range(int(w / 6)):   # 숲 가장자리 덤불 · 고사리 (평지처럼 안 보이게)
            x = rnd.uniform(0, w)
            r = pygame.Rect(0, 0, rnd.randint(10, 22), rnd.randint(6, 10))
            r.midbottom = (int(x), 146 + rnd.randint(-2, 3))
            pygame.draw.ellipse(s, lerp_color(FOREST[1], (40, 70, 44), rnd.random() * 0.5), r)

    # ───────────────── 구움: 땅 · 나무 · 텐트 · 소품 ─────────────────
    # 그림자 · 불빛 받는 면을 만들 때 쓰는 물체 자리: (바닥 x, 바닥 y, 반폭, 그림자 길이)
    SHADOW_OBJS = ((60, 232, 60, 70), (24, 214, 11, 90), (138, 182, 7, 60), (404, 206, 8, 90), (460, 262, 13, 90),
                   (168, 226, 11, 40), (396, 216, 20, 50), (336, 242, 5, 20), (392, 236, 2, 60))
    TREES = ((24, 22, 120, 214, 156), (138, 14, 104, 182, 112), (404, 16, 122, 206, 140), (460, 26, -10, 262, 70))   # 마지막 = 잎 아래 끝

    def _bake_near(self) -> None:
        self._ground(self.ground)
        self._ground_details(self.ground)
        self._rock_ledge(self.ground)
        trees = pygame.Surface((self.w, self.h), pygame.SRCALPHA)
        # 가까운 나무 4그루: 왼쪽 2 (하나는 텐트 뒤), 오른쪽 2 (하나는 화면 오른쪽 끝을 세로로)
        self._tree(trees, 24, 22, 120, 214, foliage=(-90, 140, -40, 156), kind="fir")
        self._tree(trees, 138, 14, 104, 182, foliage=(92, 186, -30, 112), kind="fir")
        self._tree(trees, 404, 16, 122, 206, foliage=(330, 476, -20, 140), kind="fir")
        self._tree(trees, 460, 26, -10, 262, foliage=(420, 580, -40, 70), kind="pine")
        self._canopy_edge(trees)
        self.near.blit(_outlined(trees), (0, 0))
        props = pygame.Surface((self.w, self.h), pygame.SRCALPHA)
        self._rod(props)
        self._woodpile(props)
        self.near.blit(_outlined(props), (0, 0))
        self._tent_lines(self.near)
        tent = pygame.Surface((self.w, self.h), pygame.SRCALPHA)
        self._tent(tent)
        self._backpack(tent)
        self.near.blit(_outlined(tent), (0, 0))
        stones = pygame.Surface((self.w, self.h), pygame.SRCALPHA)
        self._stones(stones, back=True)
        self.near.blit(_outlined(stones), (0, 0))

    def _ground(self, s) -> None:
        w, h = self.w, self.h
        top = 124
        g0, g1 = (lerp_color(SNOW, (200, 210, 225), 0.3), (176, 186, 204)) if self.snowy else GRASS
        for y in range(top, h, 2):
            u = (y - top) / (h - top)
            s.fill(lerp_color(g0, g1, u ** 0.8), (0, y, w, 2))
        # 빈터 (흙 타원 x 60~430, y 180~300)
        cx, cy = self.X(245), 240
        soil = SOIL if not self.snowy else ((170, 156, 140), (140, 126, 112))
        for k in range(4):   # 가장자리 들쭉날쭉 · 안쪽일수록 진함
            rx, ry = 185 - k * 12, 60 - k * 6
            col = lerp_color(soil[0], soil[1], k / 3)
            pts = []
            for i in range(48):
                a = i / 48 * math.tau
                j = 1 + 0.04 * math.sin(a * 7 + k) + 0.03 * math.sin(a * 13)
                pts.append((cx + math.cos(a) * rx * j, cy + math.sin(a) * ry * j))
            pygame.draw.polygon(s, col, pts)

    def _ground_details(self, s) -> None:
        rnd = random.Random(33)
        w, h = self.w, self.h
        cx, cy = self.X(245), 240
        leaf_cols = [(196, 92, 48), (222, 170, 64), (160, 70, 40)] if self.season == "autumn" else [(120, 96, 56), (98, 84, 50)]
        for _ in range(220):
            x, y = rnd.uniform(0, w), rnd.uniform(128, h)
            inside = ((x - cx) / 185) ** 2 + ((y - cy) / 60) ** 2 < 1
            if inside:
                if rnd.random() < 0.25:   # 빈터: 작은 돌 · 흙 알갱이
                    s.fill(scale_color(SOIL[1], 0.8), (int(x), int(y), 1, 1))
                continue
            r = rnd.random()
            near_k = (y - 128) / (h - 128)
            if self.snowy:
                if r < 0.3:
                    s.fill((210, 220, 236), (int(x), int(y), 2, 1))
                continue
            if r < 0.55:   # 풀 포기
                gc = lerp_color(GRASS[0], (40, 64, 34), 0.5)
                n = 1 + int(near_k * 3)
                for d in (-1, 0, 1):
                    pygame.draw.line(s, gc, (x, y), (x + d * n, y - 2 - n), 1)
            elif r < 0.78:   # 낙엽
                s.fill(rnd.choice(leaf_cols), (int(x), int(y), 2, 1))
            elif r < 0.86 and self.season == "spring":   # 들꽃 (흰 · 노랑)
                s.fill(rnd.choice([(250, 250, 240), (250, 220, 80)]), (int(x), int(y), 1, 1))
        # 나무 아래 솔방울 · 이끼 바위
        for x, y in ((40, 214), (64, 220), (380, 210), (420, 218), (446, 232)):
            pc = pygame.Rect(self.X(x), y, 4, 3)
            pygame.draw.ellipse(s, (110, 74, 44), pc)
            s.fill((150, 108, 64), (pc.x + 1, pc.y, 1, 1))
            pygame.draw.ellipse(s, OUT, pc.inflate(2, 2), 1)
        for x, y, rw in ((18, 238, 16), (350, 202, 12)):
            r = pygame.Rect(self.X(x), y, rw, rw // 2 + 2)
            pygame.draw.ellipse(s, STONE[1], r)
            pygame.draw.ellipse(s, STONE[0], (r.x + 2, r.y, r.w - 5, r.h // 2))
            s.fill((88, 132, 70), (r.x + 3, r.y + 1, 3, 1))   # 이끼
            s.fill((88, 132, 70), (r.x + rw - 5, r.y + 2, 2, 1))
            if self.snowy:
                s.fill(SNOW, (r.x + 2, r.y, r.w - 4, 1))
            pygame.draw.ellipse(s, OUT, r, 1)

    def _rock_ledge(self, s) -> None:
        """오른쪽 아래로 살짝 내리막 + 바위 턱 하나."""
        x0 = self.X(392)
        pts = [(x0, 270), (x0 + 6, 252), (x0 + 24, 246), (x0 + 50, 249), (self.w, 244), (self.w, 270)]
        low = pygame.Surface((self.w, self.h), pygame.SRCALPHA)
        pygame.draw.polygon(low, (0, 0, 0, 46), [(x0 + 30, 270), (x0 + 40, 256), (self.w, 252), (self.w, 270)])
        s.blit(low, (0, 0))
        rock = pygame.Surface((self.w, self.h), pygame.SRCALPHA)
        pygame.draw.polygon(rock, STONE[1], pts)
        pygame.draw.polygon(rock, STONE[0], [(x0 + 6, 252), (x0 + 24, 246), (x0 + 50, 249), (x0 + 30, 252)])
        pygame.draw.line(rock, STONE[2], (x0 + 12, 258), (x0 + 30, 264), 1)   # 금
        if self.snowy:
            pygame.draw.line(rock, SNOW, (x0 + 7, 251), (x0 + 48, 248), 1)
        s.blit(_outlined(rock), (0, 0))

    def _tree(self, s, x: float, tw: int, top: float, base: float, foliage, kind: str) -> None:
        """줄기(3단 음영 + 세로 껍질 무늬 + 드러난 뿌리) + 가지 덩어리 (위쪽을 덮음)."""
        X = self.X(x)
        rnd = random.Random(int(x * 7 + tw))
        # 줄기
        y0 = int(max(-2, top))
        trunk = pygame.Rect(X - tw // 2, y0, tw, int(base - y0))
        s.fill(BARK[1], trunk)
        s.fill(BARK[0], (trunk.x + tw - max(3, tw // 4) - 1, trunk.y, max(3, tw // 4), trunk.h))   # 오른쪽(불 쪽) 밝게
        s.fill(BARK[2], (trunk.x, trunk.y, max(2, tw // 5), trunk.h))
        for bx in range(trunk.x + 2, trunk.right - 1, 2):   # 세로 나무껍질 무늬, 군데군데 끊김
            y = trunk.y + rnd.randint(0, 6)
            while y < trunk.bottom - 2:
                ln = rnd.randint(5, 14)
                pygame.draw.line(s, BARK[2], (bx, y), (bx, min(trunk.bottom - 1, y + ln)), 1)
                y += ln + rnd.randint(2, 6)
        # 드러난 뿌리 (양옆 2~3갈래)
        for d in (-1, 1):
            for k in range(rnd.randint(2, 3) if d > 0 else 2):
                rx = trunk.centerx + d * (tw // 2 - 2 - k * 3)
                ex = rx + d * (6 + k * 5)
                pygame.draw.polygon(s, BARK[1], [(rx - 2, base - 6), (rx + 2, base - 6), (ex, base + 2 + k)])
        # 가지 덩어리
        fx0, fx1, fy0, fy1 = foliage
        cx = (fx0 + fx1) / 2
        tiers = 6 if kind == "fir" else 4
        for i in range(tiers):
            u = i / max(1, tiers - 1)
            y = fy0 + (fy1 - fy0) * u
            half = (fx1 - fx0) / 2 * (0.45 + 0.55 * u)
            col = NEEDLE[i % 2]
            if kind == "pine":   # 소나무: 둥근 덩어리 여러 개
                for j in range(5):
                    ex = cx + (j - 2) * half * 0.42 + rnd.uniform(-6, 6)
                    rr = pygame.Rect(0, 0, int(half * 0.62), int(18 + 8 * u))
                    rr.center = (self.X(ex), int(y))
                    pygame.draw.ellipse(s, col, rr)
                    pygame.draw.ellipse(s, NEEDLE[(i + 1) % 2], rr.move(0, 3).inflate(-6, -6))
            else:   # 전나무: 들쭉날쭉 아래로 처지는 층
                pts = [(self.X(cx), y - 26)]
                n = 9
                for j in range(n + 1):
                    v = j / n
                    px = cx - half + 2 * half * v
                    py = y + 8 + (4 if j % 2 else -2) + rnd.uniform(-2, 2) + 6 * (1 - abs(v - 0.5) * 2) * 0.3
                    pts.append((self.X(px), py))
                pygame.draw.polygon(s, col, pts)
                pygame.draw.polygon(s, NEEDLE[(i + 1) % 2], [(self.X(cx), y - 18), (self.X(cx - half * 0.7), y + 6),
                                                             (self.X(cx + half * 0.7), y + 6)])
            # 끝에 밝은 초록 1px 점 (봄엔 연두를 더 많이)
            for _ in range(10 if self.season == "spring" else 5):
                px = self.X(cx + rnd.uniform(-half, half))
                s.fill(NEEDLE_TIP if self.season != "spring" else (150, 210, 96), (px, int(y + rnd.uniform(0, 8)), 1, 1))
            if self.snowy:   # 가지 윗면 눈
                for _ in range(8):
                    px = self.X(cx + rnd.uniform(-half * 0.9, half * 0.9))
                    s.fill(SNOW, (px, int(y - 4 + rnd.uniform(-3, 3)), rnd.randint(2, 4), 1))

    def _canopy_edge(self, s) -> None:
        """양옆에서 하늘을 덮는 가지 (가운데 x 150~330 만 트이게, 경계는 들쭉날쭉)."""
        rnd = random.Random(44)
        for side, (a, b) in ((-1, (-self.ox - 10, 158)), (1, (322, BASE_W + self.ox + 10))):
            for _ in range(46):
                x = rnd.uniform(a, b)
                edge = 158 if side < 0 else 322
                dist = abs(x - edge)
                y = rnd.uniform(-10, 34 + min(90, dist * 0.9))
                rw, rh = rnd.randint(16, 34), rnd.randint(8, 14)
                r = pygame.Rect(0, 0, rw, rh)
                r.center = (self.X(x), int(y))
                pygame.draw.ellipse(s, NEEDLE[rnd.randint(0, 1)], r)
                for _ in range(3):
                    s.fill(NEEDLE_TIP if self.season != "spring" else (150, 210, 96),
                           (r.x + rnd.randint(2, max(3, rw - 3)), r.bottom - rnd.randint(1, 3), 1, 1))
                if self.snowy:
                    s.fill(SNOW, (r.x + 3, r.y + 1, max(2, rw - 8), 1))

    def _tent(self, s) -> None:
        """텐트 (왼쪽, 꼭대기 x 112 · y 96, 아래 x −30~190 · y 232). 입구가 불 쪽(오른쪽)을 향해 열림."""
        X = self.X
        lit, shade, seam = TENT
        apex = (X(112), 96)
        back_top = (X(-70), 108)
        fl, fr = (X(30), 232), (X(190), 232)
        bl = (X(-90), 232)
        # 옆면 (그늘, 왼쪽으로 화면 밖에서 잘림) — 꼭대기 줄이 가운데로 살짝 처짐
        ridge = [apex] + [(X(112 - 182 * u), 96 + 12 * u + 4 * math.sin(math.pi * u)) for u in (0.25, 0.5, 0.75)] + [back_top]
        pygame.draw.polygon(s, shade, ridge + [bl, fl])
        # 앞면 (불 쪽 · 밝음): 양 옆선이 아래로 처지는 곡선
        left_edge = [(apex[0] + (fl[0] - apex[0]) * u + 3 * math.sin(math.pi * u), apex[1] + (fl[1] - apex[1]) * u) for u in
                     (0.0, 0.33, 0.66, 1.0)]
        right_edge = [(apex[0] + (fr[0] - apex[0]) * u - 4 * math.sin(math.pi * u), apex[1] + (fr[1] - apex[1]) * u) for u in
                      (1.0, 0.66, 0.33, 0.0)]
        pygame.draw.polygon(s, lit, left_edge + right_edge)
        # 이음매 (옆선 · 꼭대기)
        pygame.draw.lines(s, seam, False, left_edge, 1)
        pygame.draw.lines(s, seam, False, ridge, 1)
        # 옆면 비스듬한 주름 4~5줄
        for k in range(5):
            u = 0.15 + k * 0.17
            x0, y0 = X(112 - 182 * u), 98 + 12 * u
            pygame.draw.line(s, scale_color(shade, 0.82), (x0, y0 + 4), (x0 + 14 + k * 3, y0 + 52 + k * 8), 1)
        # 앞면 주름 (꼭대기에서 아래로 처지는 곡선)
        for k in range(4):
            u = 0.25 + k * 0.18
            pts = [(apex[0] + 2 + (fr[0] - apex[0] - 8) * u * v, apex[1] + 6 + (fr[1] - apex[1] - 10) * v + 3 * math.sin(math.pi * v))
                   for v in (0.1, 0.4, 0.7)]
            pygame.draw.lines(s, scale_color(lit, 0.86), False, pts, 1)
        # 입구 (어두운 안 + 침낭 끝)
        door = [(X(116), 128), (X(84), 232), (X(160), 232)]
        pygame.draw.polygon(s, (36, 26, 22), door)
        pygame.draw.polygon(s, (52, 38, 30), [(X(116), 136), (X(100), 232), (X(122), 232)])   # 안쪽 벽 희미하게
        bag = pygame.Rect(X(98), 218, 34, 12)
        pygame.draw.ellipse(s, (44, 60, 104), bag)   # 침낭 끝 (남색 · 체크 2px)
        for yy in range(bag.y + 2, bag.bottom - 1, 4):
            for xx in range(bag.x + 3 + (yy // 4) % 2 * 2, bag.right - 3, 4):
                s.fill((70, 90, 140), (xx, yy, 2, 2))
        # 지퍼 문: 왼쪽 반은 닫힌 천(지퍼 줄), 오른쪽 문은 말려 올라가 끈으로 묶임
        pygame.draw.polygon(s, scale_color(lit, 0.92), [(X(116), 128), (X(84), 232), (X(96), 232), (X(114), 150)])
        for k in range(10):   # 지퍼 이빨
            y = 134 + k * 10
            x = X(116 - (116 - 92) * (y - 128) / 104)
            s.fill(seam, (x, y, 1, 2))
        roll = pygame.Rect(0, 0, 11, 20)
        roll.center = (X(158), 186)
        pygame.draw.ellipse(s, scale_color(lit, 0.95), roll)
        for k in range(3):
            pygame.draw.arc(s, seam, roll.inflate(-k * 3, -k * 4), 0.5, 3.6, 1)
        pygame.draw.line(s, (232, 222, 196), (roll.left, roll.centery - 1), (roll.right, roll.centery + 1), 1)   # 끈
        pygame.draw.line(s, (232, 222, 196), (roll.right - 1, roll.centery + 1), (roll.right + 2, roll.centery + 6), 1)
        # 그라운드시트 2px · 꼭대기 폴 끝 4px
        s.fill((84, 96, 70), (X(-40), 232, X(196) - X(-40), 2))
        pygame.draw.line(s, (150, 150, 156), (apex[0], apex[1] - 1), (apex[0], apex[1] - 5), 1)
        if self.snowy:   # 꼭대기 · 옆면 윗줄 눈
            pygame.draw.lines(s, SNOW, False, [(p[0], p[1] - 1) for p in ridge], 2)
            pygame.draw.line(s, SNOW, (apex[0] - 3, apex[1]), (apex[0] + 6, apex[1] + 12), 2)

    def _tent_lines(self, s) -> None:
        """폴 끝에서 당김줄 2개 → 말뚝 (1px 회색, 살짝 처짐) + 말뚝 3개 (외곽선 없음 — 가는 것)."""
        X = self.X
        top = (X(112), 92)
        for end in ((X(214), 240), (X(-14), 200)):
            pts = []
            for k in range(9):
                u = k / 8
                pts.append((top[0] + (end[0] - top[0]) * u, top[1] + (end[1] - top[1]) * u + 5 * math.sin(math.pi * u)))
            pygame.draw.lines(s, (176, 176, 170), False, pts, 1)
        for x, y in ((X(214), 240), (X(36), 236), (X(194), 236)):
            pygame.draw.line(s, (90, 70, 50), (x, y - 4), (x + 1, y + 1), 2)
            s.fill((200, 196, 186), (x, y - 5, 2, 1))

    def _backpack(self, s) -> None:
        """배낭 (텐트 입구 옆 x 168 · y 214): 초록 갈색 천 · 덮개 · 끈 · 앞주머니."""
        x, y = self.X(168), 214
        body = pygame.Rect(x - 10, y - 14, 22, 26)
        pygame.draw.rect(s, (86, 104, 70), body, border_radius=5)
        pygame.draw.rect(s, (70, 86, 58), (body.x, body.y + 14, body.w, body.h - 14), border_radius=4)
        pygame.draw.rect(s, (104, 124, 84), (body.x + 1, body.y - 2, body.w - 2, 10), border_radius=4)   # 덮개
        pygame.draw.rect(s, (66, 80, 54), (body.x + 5, body.y + 15, 12, 8), border_radius=2)          # 앞주머니
        for bx in (body.x + 6, body.x + 15):
            s.fill((54, 44, 34), (bx, body.y + 4, 2, 9))   # 끈
            s.fill((200, 180, 110), (bx, body.y + 11, 2, 2))   # 버클
        s.fill((150, 70, 46), (body.right - 3, body.y + 2, 2, 12))   # 매달린 빨간 끈

    def _rod(self, s) -> None:
        """나무(x 410)에 기대 세운 낚싯대 — 위로 화면 밖까지. 릴 · 손잡이."""
        X = self.X
        a, b = (X(392), 236), (X(410) + 3, -12)
        pygame.draw.line(s, (40, 36, 44), a, b, 2)
        pygame.draw.line(s, (90, 86, 104), (a[0] + 1, a[1] - 2), (b[0] + 1, b[1]), 1)
        s.fill((120, 82, 50), (a[0] - 1, a[1] - 22, 4, 16))   # 코르크 손잡이
        pygame.draw.circle(s, (70, 74, 90), (a[0] - 3, a[1] - 28), 4)   # 릴
        s.fill((150, 156, 170), (a[0] - 4, a[1] - 29, 2, 2))
        for k in (60, 110, 160):   # 가이드
            u = k / 248
            p = (a[0] + (b[0] - a[0]) * u, a[1] + (b[1] - a[1]) * u)
            s.fill((170, 174, 186), (int(p[0]) - 2, int(p[1]), 2, 1))

    def _woodpile(self, s) -> None:
        """장작 더미 3개 (x 372~420, y 212): 둘 깔고 하나 얹음, 단면(나이테)이 이쪽을 봄."""
        X = self.X
        for i, (x, y) in enumerate(((380, 214), (398, 214), (389, 205))):
            body = pygame.Rect(X(x) - 12, y - 4, 16, 9)
            pygame.draw.rect(s, LOG[1], body, border_radius=2)   # 뒤로 뻗은 몸통 (껍질)
            pygame.draw.line(s, LOG[2], (body.x + 1, body.y + 3), (body.right - 2, body.y + 3), 1)
            pygame.draw.line(s, LOG[0], (body.x + 1, body.y + 1), (body.right - 4, body.y + 1), 1)
            end = pygame.Rect(0, 0, 10, 10)
            end.center = (X(x) + 4, y)
            pygame.draw.ellipse(s, LOG[2], end.inflate(2, 2))   # 껍질 테
            pygame.draw.ellipse(s, (206, 166, 114), end)
            pygame.draw.ellipse(s, (164, 120, 76), end.inflate(-4, -4), 1)   # 나이테
            s.fill((140, 100, 62), (end.centerx, end.centery, 1, 1))
            if self.snowy and i == 2:
                s.fill(SNOW, (body.x + 1, body.y - 1, body.w + 4, 1))

    # ───────────────── 불 둘레 돌 ─────────────────
    def stone_list(self) -> list[tuple[int, int, int, int]]:
        """(x, y, 폭, 높이): 크기가 다른 돌 11개가 타원으로 (앞쪽이 더 크고 아래)."""
        cx, cy = FIRE
        rnd = random.Random(55)
        out = []
        for i in range(11):
            a = math.pi * 2 * i / 11 + 0.2
            front = math.sin(a)   # +1 = 앞
            rx, ry = 60, 16
            sw = int(13 + 7 * (front + 1) / 2 + rnd.randint(-2, 2))
            sh = int(8 + 5 * (front + 1) / 2 + rnd.randint(-1, 1))
            out.append((cx + math.cos(a) * rx, cy + math.sin(a) * ry + 2 * front, sw, sh))
        return out

    def _stones(self, s, back: bool) -> None:
        for x, y, sw, sh in self.stone_list():
            if (y >= FIRE[1]) == back:
                continue
            r = pygame.Rect(0, 0, sw, sh)
            r.center = (self.X(x), int(y))
            pygame.draw.ellipse(s, STONE[1], r)
            pygame.draw.ellipse(s, STONE[2], (r.x + 1, r.centery, r.w - 2, r.h // 2))   # 아랫면 어둡게
            pygame.draw.ellipse(s, STONE[0], (r.x + 2, r.y + 1, r.w - 5, max(2, r.h // 3)))   # 윗면 밝게
            s.fill((60, 52, 50), (r.centerx - 1, r.y + 2, 2, 1))   # 그을음
            if self.snowy and not back and sw > 16:
                s.fill(SNOW, (r.x + 3, r.y, r.w - 7, 1))

    # ───────────────── 구움: 불 앞쪽 돌 · 머그컵 ─────────────────
    def _bake_front(self) -> None:
        stones = pygame.Surface((self.w, self.h), pygame.SRCALPHA)
        self._stones(stones, back=False)
        # 머그컵 받침 돌 + 법랑 머그컵 (x 336, y 240)
        X = self.X
        base = pygame.Rect(X(326), 238, 22, 9)
        pygame.draw.ellipse(stones, STONE[1], base)
        pygame.draw.ellipse(stones, STONE[0], (base.x + 2, base.y + 1, base.w - 6, 3))
        mug = pygame.Rect(X(331), 227, 10, 12)
        pygame.draw.rect(stones, (236, 230, 214), mug, border_radius=2)
        pygame.draw.rect(stones, (196, 188, 170), (mug.x, mug.y + 7, mug.w, 5), border_radius=2)
        stones.fill((42, 60, 104), (mug.x, mug.y, mug.w, 2))   # 남색 테두리
        stones.fill((42, 60, 104), (mug.x + 2, mug.y + 6, 2, 2))   # 법랑 깨진 점
        pygame.draw.arc(stones, (236, 230, 214), (mug.right - 2, mug.y + 3, 6, 6), -1.6, 1.6, 2)   # 손잡이
        self.front.blit(_outlined(stones), (0, 0))

    # ───────────────── 구움: 불빛 받는 면 · 밤 그림자 · 석양 테두리 (CF2) ─────────────────
    def _bake_light(self) -> None:
        w, h = self.w, self.h
        X = self.X
        fx, fy = X(FIRE[0]), FIRE[1]
        # 불빛 받는 면 마스크 (흰색 = 받음)
        m = pygame.Surface((w, h), pygame.SRCALPHA)
        white = (255, 255, 255, 255)
        for x, tw, top, base, leaf in self.TREES:   # 줄기의 불 쪽 2~4px (잎 아래로 드러난 부분만)
            side = 1 if X(x) < fx else -1
            edge = X(x) + side * (tw // 2 - 1)
            sw = 3 if tw < 20 else 4
            rx = edge - sw + 1 if side > 0 else edge
            y0 = int(max(top, leaf))
            m.fill(white, (rx, y0, sw, int(base - y0)))
        # 텐트 · 배낭이 가리는 곳은 지우고 (뒤 나무 줄기가 비치지 않게) 텐트 앞면을 칠함
        clear = (0, 0, 0, 0)
        pygame.draw.polygon(m, clear, [(X(112), 92), (X(-70), 104), (X(-90), 236), (X(196), 236)])
        pygame.draw.rect(m, clear, (X(156), 196, 26, 34))
        pygame.draw.polygon(m, white, [(X(112), 100), (X(190), 232), (X(160), 232), (X(116), 128)])   # 텐트 앞면 불 쪽 끝
        pygame.draw.polygon(m, (255, 255, 255, 150), [(X(112), 96), (X(84), 232), (X(30), 232)])    # 텐트 앞면 나머지 (약하게)
        for x, y, sw, sh in self.stone_list():   # 돌 윗면
            r = pygame.Rect(0, 0, sw - 4, max(2, sh // 3))
            r.midtop = (X(x), int(y - sh / 2) + 1)
            pygame.draw.ellipse(m, white, r)
        for x, y in ((380, 214), (398, 214), (389, 205)):   # 장작 더미 단면
            pygame.draw.ellipse(m, white, (X(x) - 1, y - 5, 10, 10))
        m.fill(white, (X(168) - 1 + 10, 200, 3, 24))   # 배낭 불 쪽
        mug = pygame.Rect(X(331), 227, 3, 12)
        m.fill(white, mug)
        self.lit = self._radial((255, 154, 74), 170, 280, fx, fy)
        self.lit.blit(m, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
        # 밤 그림자: 불 반대쪽으로 길게 (반투명 검정 30%, 땅 위에만)
        sh = pygame.Surface((w, h), pygame.SRCALPHA)
        for bx, by, hw, ln in self.SHADOW_OBJS:
            self._shadow_poly(sh, X(bx), by, hw, ln, X(bx) - fx, (by - fy) + 8)
        sh.fill((0, 0, 0, 0), (0, 0, w, 124))
        self.shadow_night = sh
        # 해 질 무렵 산등성이 윗면 1px 주황 테두리
        rim = pygame.Surface((w, h), pygame.SRCALPHA)
        pygame.draw.lines(rim, (255, 150, 80, 255), False, [(x, int(y)) for x, y in self.ridge_back], 1)
        self.rim = rim

    @staticmethod
    def _shadow_poly(s, bx, by, hw, ln, dx, dy, alpha: int = 77) -> None:
        d = math.hypot(dx, dy) or 1.0
        ux, uy = dx / d, dy / d * 0.45   # 땅 위로 납작하게
        n = math.hypot(ux, uy) or 1.0
        ux, uy = ux / n, uy / n
        px, py = -uy, ux
        pts = [(bx + px * hw, by + py * hw * 0.3), (bx - px * hw, by - py * hw * 0.3),
               (bx - px * hw * 1.5 + ux * ln, by - py * hw * 0.45 + uy * ln),
               (bx + px * hw * 1.5 + ux * ln, by + py * hw * 0.45 + uy * ln)]
        pygame.draw.polygon(s, (0, 0, 0, alpha), pts)

    def _radial(self, col, amax: int, R: float, cx: int, cy: int) -> pygame.Surface:
        """불 중심 원형 알파 그라데이션 (가운데 amax → R 밖 0), 계단식."""
        g = pygame.Surface((self.w, self.h), pygame.SRCALPHA)
        steps = 20
        for i in range(steps):
            r = R * (1 - i / steps)
            a = int(amax * (i + 1) / steps)
            pygame.draw.ellipse(g, (*col, a), (cx - r, cy - r * 0.8, r * 2, r * 1.6))
        return g

    # ───────────────── 조명 (CF2, 🅲-1) ─────────────────
    @staticmethod
    def darkness(hour: float) -> float:
        """어둠 덮개 0..0.72: 낮 10~17 = 0 · 아침 6~10 · 저녁 17~20 = 0~0.35 · 밤 = 0.72 (경계 1시간에 걸쳐 이어짐)."""
        h = hour % 24
        if 10 <= h <= 17:
            return 0.0
        if 17 < h < 19.5:
            return 0.35 * (h - 17) / 2.5
        if 19.5 <= h < 20.5:
            return 0.35 + 0.37 * (h - 19.5)
        if 6.5 < h < 10:
            return 0.35 * (10 - h) / 3.5
        if 5.5 <= h <= 6.5:
            return 0.35 + 0.37 * (6.5 - h)
        return 0.72

    def _cached(self, key, make):
        img = self._cache.get(key)
        if img is None:
            if len(self._cache) > 24:
                self._cache.clear()
            img = self._cache[key] = make()
        return img

    def _hole(self, R: int) -> pygame.Surface:
        """밤 덮개 (남색 #0E1426): 불 중심 구멍 — 가운데 0% → 가장자리(R) 100% (이 값 × 덮개 세기)."""
        def make():
            g = pygame.Surface((self.w, self.h), pygame.SRCALPHA)
            g.fill((0x0E, 0x14, 0x26, 255))
            fx, fy = self.X(FIRE[0]), FIRE[1] - 20
            steps = 22
            for i in range(steps):
                r = R * (1 - i / steps)
                a = int(255 * (r / R) ** 1.25)
                pygame.draw.ellipse(g, (0x0E, 0x14, 0x26, a), (fx - r, fy - r * 0.82, r * 2, r * 1.64))
            return g
        return self._cached(("hole", R), make)

    def _warm(self, R: int, k: int) -> pygame.Surface:
        """불빛 구멍 안을 따뜻하게 (곱하기): 낮 색 그대로 드러난 풀이 초록으로 뜨지 않게. k = 0..4 (세기 4단)."""
        def make():
            g = pygame.Surface((R * 2 + 2, int(R * 1.64) + 2))
            g.fill((255, 255, 255))
            steps = 12
            for i in range(steps):
                r = R * (1 - i / steps)
                u = (i + 1) / steps * k / 4
                col = lerp_color((255, 255, 255), (255, 176, 120), u)
                pygame.draw.ellipse(g, col, (R + 1 - r, R * 0.82 + 1 - r * 0.82, r * 2, r * 1.64))
            return g
        return self._cached(("warm", R, k), make)

    def _glow(self, R: int, inten: int) -> pygame.Surface:
        """불빛 더하기 (주황 #FF9A4A × 세기, 가운데 밝고 R 에서 0)."""
        def make():
            g = pygame.Surface((R * 2 + 2, int(R * 1.64) + 2))
            g.fill((0, 0, 0))
            steps = 16
            for i in range(steps):
                r = R * (1 - i / steps)
                k = inten / 100 * (i + 1) / steps
                pygame.draw.ellipse(g, (int(0xFF * k), int(0x9A * k), int(0x4A * k)),
                                    (R + 1 - r, R * 0.82 + 1 - r * 0.82, r * 2, r * 1.64))
            return g
        return self._cached(("glow", R, inten), make)

    def light_state(self, hour: float, weather: str, t: float) -> dict:
        d = self.darkness(hour) + {"rain": 0.10, "storm": 0.18, "fog": 0.06}.get(weather, 0.0) * (1 if hour % 24 < 20 else 0.3)
        d = min(0.78, d)
        hole_k = clamp((d - 0.35) / 0.37, 0.0, 1.0)
        flick = random.Random(int(t / 0.12)).uniform(-4, 4)   # 0.12초마다 반경 ±4px
        R = 90 + 60 * hole_k + flick
        glow = 0.0 if d < 0.02 else (15 * min(1.0, d / 0.35) + 10 * hole_k)
        return {"d": d, "hole_k": hole_k, "R": R, "glow": glow, "nk": clamp(d / 0.72, 0.0, 1.0)}

    # ───────────────── 매 프레임 ─────────────────
    def draw_sky(self, canvas, pal: dict, hour: float, t: float, cloud_shift: float = 0.0, visible: bool = True) -> None:
        cam = _Cam(self.w, HORIZON)
        p = dict(pal, sky_top=no_purple(pal["sky_top"]), sky_bottom=no_purple(pal["sky_bottom"]))
        world.draw_sky(canvas, p, cam)
        canvas.fill(p["sky_bottom"], (0, HORIZON, self.w, 124 - HORIZON))   # 지평선 ~ 땅 사이 6줄만
        sa = float(pal.get("stars", 0.0))
        if sa > 0.02:   # 별: 1px, 0.5~2초 주기로 깜빡임
            for x, y, per, ph in self.stars:
                k = 0.55 + 0.45 * math.sin((t / per + ph) * math.tau)
                c = lerp_color(p["sky_top"], (240, 244, 255), clamp(sa * k, 0, 1))
                canvas.set_at((self.X(x), int(y)), c)
        # 해 / 달: 트인 구간 안에서 왼쪽 아래 → 위 → 오른쪽 아래 호 (맑을 때만)
        self._body(canvas, p, pal, hour, visible)
        self._clouds(canvas, pal, cloud_shift)

    def _body(self, canvas, p, pal, hour, visible) -> None:
        if not visible:
            return
        a, b = SKY_OPEN
        if 6.0 <= hour <= 20.0:
            u = (hour - 6.0) / 14.0
            col, rad, glow = pal["sun"], 7, 24
        else:
            u = ((hour - 20.0) % 24) / 10.0
            col, rad, glow = (232, 236, 248), 5, 12
        x = self.X(a + 8 + (b - a - 16) * u)
        y = int(108 - 86 * math.sin(math.pi * u))
        sky_here = lerp_color(p["sky_top"], p["sky_bottom"], clamp(y / HORIZON, 0, 1) ** 1.3)
        for r_add, k in ((glow, 0.14), (glow * 0.6, 0.26), (glow * 0.3, 0.42)):
            pygame.draw.circle(canvas, lerp_color(sky_here, col, k), (x, y), int(rad + r_add))
        pygame.draw.circle(canvas, col, (x, y), rad)
        if not (6.0 <= hour <= 20.0):
            pygame.draw.circle(canvas, lerp_color(sky_here, col, 0.42), (x + 3, y - 2), rad)   # 초승달 그림자 (후광 안쪽 색)

    def _clouds(self, canvas, pal, cloud_shift) -> None:
        """구름 (트인 하늘)."""
        a, b = SKY_OPEN
        cc = pal["cloud"]
        for cxu, cy, cw in self.clouds:
            cx = self.X(a - 30 + ((cxu * (b - a + 60) + cloud_shift) % (b - a + 60)))
            for dx, dy, rr in ((0, 0, cw // 3), (cw // 3, -3, cw // 4), (-cw // 3, 1, cw // 5)):
                pygame.draw.ellipse(canvas, cc, (cx + dx - rr, cy + dy - rr // 2, rr * 2, rr))

    def draw_fire(self, canvas, frame: int = 0, t: float = 0.0) -> None:
        """장작 · 숯 · 걸이 · 주전자 + 불꽃 (한 번에 — 조명 없는 미리보기용)."""
        self.draw_logs(canvas, t)
        self._flame(canvas, self.X(FIRE[0]), FIRE[1] - 2, frame)

    def draw_logs(self, canvas, t: float = 0.0, nk: float = 0.0) -> None:
        """장작 · 재 · 걸이 · 주전자 (구움) + 밤에 주전자 아랫면 불빛."""
        if getattr(self, "logs", None) is None:
            self.logs = self._bake_logs()
        canvas.blit(self.logs, (0, 0))
        if nk > 0.05:
            pot = self.pot_rect
            canvas.fill(lerp_color((30, 30, 36), (232, 120, 60), 0.6 * min(1.0, nk)), (pot.x + 2, pot.bottom - 2, pot.w - 4, 2))

    def _bake_logs(self) -> pygame.Surface:
        """장작(티피 5 + 누운 2) · 재 · 걸이 · 주전자 — 한 번만 그림 (외곽선 마스크가 무거움)."""
        out = pygame.Surface((self.w, self.h), pygame.SRCALPHA)
        cx, cy = self.X(FIRE[0]), FIRE[1]
        logs = pygame.Surface((self.w, self.h), pygame.SRCALPHA)
        # 누운 장작 2개
        for (x0, y0, x1, y1) in ((-34, 6, 26, 2), (-22, -2, 36, 7)):
            pygame.draw.line(logs, LOG[1], (cx + x0, cy + y0), (cx + x1, cy + y1), 7)
            pygame.draw.line(logs, LOG[0], (cx + x0, cy + y0 - 2), (cx + x1, cy + y1 - 2), 1)
            end = pygame.Rect(0, 0, 7, 7)
            end.center = (cx + x1, cy + y1)
            pygame.draw.ellipse(logs, (204, 164, 112), end)
            logs.fill((150, 108, 66), (end.centerx, end.centery, 1, 1))
        # 티피 (원뿔로 세운 장작 5개)
        top = (cx, cy - 34)
        for bx in (-22, -11, 0, 12, 23):
            base = (cx + bx, cy + 2 + abs(bx) // 6)
            pygame.draw.line(logs, LOG[1], base, top, 4)
            pygame.draw.line(logs, LOG[2], (base[0] + 1, base[1]), (top[0] + 1, top[1]), 1)
            # 타는 부분 (위쪽 절반) 검게 + 갈라진 틈 주황
            mid = ((base[0] + top[0]) / 2, (base[1] + top[1]) / 2)
            pygame.draw.line(logs, (34, 26, 24), mid, top, 4)
            q = ((mid[0] * 2 + top[0]) / 3, (mid[1] * 2 + top[1]) / 3)
            logs.fill((232, 116, 59), (int(q[0]), int(q[1]), 1, 2))
        out.blit(_outlined(logs), (0, 0))
        rnd = random.Random(78)
        for i in range(10):   # 회색 재 점
            out.fill((150, 146, 140), (cx + rnd.randint(-30, 30), cy + rnd.randint(3, 9), 1, 1))
        self._hanger(out, cx, cy, 0.0)
        return out

    def draw_coals(self, canvas, t: float) -> None:
        """숯만 다시 (어둠 덮개 위 — 숯은 스스로 빛남)."""
        cx, cy = self.X(FIRE[0]), FIRE[1]
        rnd = random.Random(77)
        for i in range(8):
            x, y = cx + rnd.randint(-26, 26), cy + rnd.randint(2, 8)
            k = 0.5 + 0.5 * math.sin(t * math.tau + i * 1.3)
            canvas.fill(lerp_color((0x5A, 0x1E, 0x10), (0xE8, 0x74, 0x3B), k), (x, y, rnd.randint(2, 4), 2))

    def flame_top(self, height_k: float = 1.0) -> int:
        return int(FIRE[1] - 2 - 64 * height_k)

    def _flame(self, canvas, cx: int, by: int, frame: int, height_k: float = 1.0) -> None:
        """불꽃 3겹 (바깥 #E8743B · 가운데 #F6B14A · 속 #FFF1A8) + 맨 아래 파란 기운 2px. 혀 모양 3~4갈래."""
        rnd = random.Random(900 + frame)
        tongues = [(-12, 0.78), (-2, 1.0), (9, 0.86), (17, 0.6)]
        cols = ((0xE8, 0x74, 0x3B), (0xF6, 0xB1, 0x4A), (0xFF, 0xF1, 0xA8))
        H = 64 * height_k
        for li, col in enumerate(cols):
            scale = (1.0, 0.72, 0.44)[li]
            for dx, hk in tongues:
                h = H * hk * scale * (1 + rnd.uniform(-0.08, 0.08))
                wbase = (16, 11, 6)[li] * (0.8 + 0.4 * hk)
                sway = rnd.uniform(-3, 3) * (1 - li * 0.3)
                x = cx + dx * scale
                pts = [(x - wbase / 2, by), (x - wbase / 3 + sway * 0.3, by - h * 0.45), (x + sway, by - h),
                       (x + wbase / 3 + sway * 0.5, by - h * 0.5), (x + wbase / 2, by)]
                pygame.draw.polygon(canvas, col, pts)
        blue = lerp_color((0x5A, 0x7A, 0xCF), (0xF6, 0xB1, 0x4A), 0.25)
        for k in range(-6, 7, 2):   # 파란 기운 (장작 바로 위 2px, 띄엄띄엄)
            if (k + frame) % 4:
                canvas.fill(blue, (cx + k, by - 2, 2, 2))

    def _hanger(self, canvas, cx: int, cy: int, t: float, nk: float = 0.0) -> None:
        """Y자 나뭇가지 2개 + 가로 막대 + 작은 검은 법랑 주전자 (주둥이에서 김 한 줄)."""
        s = pygame.Surface((self.w, self.h), pygame.SRCALPHA)
        top = 134
        for x in (cx - 48, cx + 46):
            pygame.draw.line(s, LOG[1], (x + (-6 if x < cx else 6), cy + 6), (x, top + 2), 3)   # 바깥으로 벌려 박음
            pygame.draw.line(s, LOG[1], (x, top + 6), (x - 4, top - 4), 2)   # Y 갈래
            pygame.draw.line(s, LOG[1], (x, top + 6), (x + 4, top - 4), 2)
        pygame.draw.line(s, LOG[0], (cx - 52, top), (cx + 50, top), 2)   # 가로 막대
        pygame.draw.line(s, (60, 60, 66), (cx, top + 1), (cx, top + 8), 1)   # 철사
        pot = pygame.Rect(cx - 8, top + 8, 16, 11)
        pygame.draw.ellipse(s, (30, 30, 36), pot)
        s.fill((30, 30, 36), (pot.x + 1, pot.y + 3, pot.w - 2, 6))
        s.fill((70, 72, 84), (pot.x + 3, pot.y + 2, 4, 2))   # 법랑 반짝
        pygame.draw.line(s, (30, 30, 36), (pot.right - 1, pot.y + 4), (pot.right + 4, pot.y + 1), 2)   # 주둥이
        pygame.draw.arc(s, (60, 60, 66), (pot.x + 2, top + 2, 12, 12), 0.3, 2.8, 1)   # 손잡이 고리
        self.pot_rect = pot
        canvas.blit(_outlined(s), (0, 0))
        self.steam_at = (pot.right + 5, pot.y)

    def draw_steam(self, canvas, t: float) -> None:
        """주전자 김 한 줄 (덮개 위 — 밝게 보이게)."""
        if not hasattr(self, "steam_at"):
            return
        sx, sy = self.steam_at
        for k in range(6):
            y = sy - k * 3
            x = sx + int(2 * math.sin(t * 3 + k * 0.9)) + k // 2
            canvas.fill((232, 236, 240), (x, y, 1, 2))

    # ───────────────── 움직임 (실제 시간, 타임랩스와 상관없이) ─────────────────
    def update(self, dt: float, wind: float = 0.0, low: bool = False, height_k: float = 1.0) -> None:
        r = self.prand
        cx = self.X(FIRE[0])
        top = self.flame_top(height_k)
        # 불티: 초당 4~6개 (화질 낮음 = 절반), 40~120px 올라가며 좌우로 흔들리다 꺼짐
        self.ember_acc += dt * (5.0 if not low else 2.5)
        while self.ember_acc >= 1.0:
            self.ember_acc -= 1.0
            vy = r.uniform(40, 70)
            self.embers.append([cx + r.uniform(-10, 10), top + r.uniform(6, 18), vy, r.uniform(40, 120) / vy, 0.0,
                                r.uniform(0, 6.28)])
        for e in self.embers:
            e[4] += dt
            e[1] -= e[2] * dt
            e[0] += (math.sin(e[4] * 5 + e[5]) * 14 + wind * 18) * dt
        self.embers = [e for e in self.embers if e[4] < e[3]]
        # 불꽃 조각: 가끔 꼭대기에서 떨어져 올라가 사라짐
        self.bit_t -= dt
        if self.bit_t <= 0:
            self.bit_t = r.uniform(0.7, 1.6)
            self.bits.append([cx + r.uniform(-8, 8), top + 4, 0.0])
        for b in self.bits:
            b[2] += dt
            b[1] -= 46 * dt
        self.bits = [b for b in self.bits if b[2] < 0.32]
        # 연기: 바람 방향으로 기울며 올라가 하늘에서 흩어짐
        self.smoke_acc += dt
        while self.smoke_acc >= 0.22:
            self.smoke_acc -= 0.22
            self.smoke.append([cx + r.uniform(-4, 4), top - 2, 0.0, r.uniform(3.0, 4.0), r.uniform(0, 6.28)])
        for m in self.smoke:
            m[2] += dt
            m[1] -= 20 * dt
            m[0] += (wind * 16 + math.sin(m[2] * 1.7 + m[4]) * 4) * dt
        self.smoke = [m for m in self.smoke if m[2] < m[3]]

    def _smoke_img(self, rad: int) -> pygame.Surface:
        img = self._smoke_imgs.get(rad)
        if img is None:
            img = pygame.Surface((rad * 2, rad * 2), pygame.SRCALPHA)
            pygame.draw.circle(img, (150, 150, 156, 255), (rad, rad), rad)
            pygame.draw.circle(img, (176, 176, 180, 255), (rad - rad // 3, rad - rad // 3), max(1, rad // 2))
            self._smoke_imgs[rad] = img
        return img

    def draw_smoke(self, canvas, nk: float) -> None:
        """낮엔 잘 보이고 밤엔 불빛 받은 아랫부분만 (덮개 아래에 그려서 자연스럽게)."""
        for x, y, age, life, ph in self.smoke:
            u = age / life
            rad = int(3 + 10 * u)
            a = 80 * (1 - u) * (1 - 0.55 * nk)
            if a < 4:
                continue
            img = self._smoke_img(rad)
            img.set_alpha(int(a))
            canvas.blit(img, (int(x) - rad, int(y) - rad))

    def draw_flame_fx(self, canvas, t: float, height_k: float = 1.0) -> None:
        """불꽃 6프레임(초당 8) · 불꽃 조각 · 불티 (덮개 위)."""
        frame = int(t * 8) % 6
        self._flame(canvas, self.X(FIRE[0]), FIRE[1] - 2, frame, height_k)
        for x, y, age in self.bits:
            k = 1 - age / 0.32
            w = max(1, int(3 * k))
            pygame.draw.polygon(canvas, (0xF6, 0xB1, 0x4A) if k > 0.5 else (0xE8, 0x74, 0x3B),
                                [(x - w, y), (x + w, y), (x, y - 2 - 3 * k)])
        for x, y, vy, life, age, ph in self.embers:
            u = age / life
            if u > 0.85 and int(age * 30) % 2:
                continue
            col = lerp_color((0xE8, 0x74, 0x3B), (0xFF, 0xE0, 0x70), min(1.0, u * 1.6))
            canvas.set_at((int(x), int(y)), col)

    def draw_haze(self, canvas, t: float, height_k: float = 1.0) -> None:
        """열기 아지랑이: 불꽃 바로 위 30px 의 배경을 1px 좌우로 흔듦 (화질 '낮음'에서 끔)."""
        cx, top = self.X(FIRE[0]), self.flame_top(height_k)
        rect = pygame.Rect(cx - 24, top - 30, 48, 30).clip(canvas.get_rect())
        if rect.w <= 2 or rect.h <= 0:
            return
        src = canvas.subsurface(rect).copy()
        for yy in range(rect.h):
            off = int(round(math.sin(t * 18 + yy * 0.7) * (yy / rect.h)))
            if off:
                canvas.blit(src, (rect.x + off, rect.y + yy), (0, yy, rect.w, 1))

    def draw_light(self, canvas, ls: dict, t: float) -> None:
        """어둠 덮개 (밤 = 불 중심 구멍) + 불빛 더하기 + 불빛 받는 면."""
        d, hole_k = ls["d"], ls["hole_k"]
        if d > 0.01:
            plain = d * (1 - hole_k)
            if plain > 0.01:
                cov = self._cached(("plain",), lambda: self._plain())
                cov.set_alpha(int(255 * plain))
                canvas.blit(cov, (0, 0))
            if hole_k > 0.01:
                R = int(round(ls["R"] / 2) * 2)
                wk = int(round(hole_k * 4))
                if wk > 0:
                    fx, fy = self.X(FIRE[0]), FIRE[1] - 20
                    canvas.blit(self._warm(R, wk), (fx - R - 1, int(fy - R * 0.82) - 1), special_flags=pygame.BLEND_RGB_MULT)
                hole = self._hole(R)
                hole.set_alpha(int(255 * d * hole_k))
                canvas.blit(hole, (0, 0))
        if ls["glow"] > 0.5:
            R = int(round(ls["R"] / 2) * 2)
            g = self._glow(R, int(round(ls["glow"])))
            fx, fy = self.X(FIRE[0]), FIRE[1] - 20
            canvas.blit(g, (fx - R - 1, int(fy - R * 0.82) - 1), special_flags=pygame.BLEND_RGB_ADD)
        if ls["nk"] > 0.02:
            self.lit.set_alpha(int(255 * ls["nk"]))
            canvas.blit(self.lit, self.lit_at)

    def _plain(self) -> pygame.Surface:
        s = pygame.Surface((self.w, self.h))
        s.fill((0x0E, 0x14, 0x26))
        return s

    def draw_shadows(self, canvas, ls: dict, hour: float, sun: bool) -> None:
        """밤: 불 반대쪽 긴 그림자 (구움) / 낮: 해 반대쪽 짧은 그림자."""
        if ls["nk"] > 0.02:
            self.shadow_night.set_alpha(int(255 * ls["nk"]))
            canvas.blit(self.shadow_night, self.shadow_at)
        dayk = (1 - ls["nk"]) * (1.0 if sun else 0.4)
        if dayk > 0.05 and 6.0 <= hour % 24 <= 20.0:
            u = (hour % 24 - 6.0) / 14.0
            sun_x = self.X(SKY_OPEN[0] + 8 + (SKY_OPEN[1] - SKY_OPEN[0] - 16) * u)
            ds = self._dayshadow
            ds.fill((0, 0, 0, 0))
            for bx, by, hw, ln in self.SHADOW_OBJS:
                X = self.X(bx)
                self._shadow_poly(ds, X, by - 124, hw, 8 + 10 * abs(u - 0.5) * 2, X - sun_x, 6, alpha=int(60 * dayk))
            canvas.blit(ds, (0, 124))

    def draw_rim(self, canvas, hour: float) -> None:
        """해 질 무렵(17~19시) 산등성이 윗면 1px 주황 (석양 받는 면)."""
        h = hour % 24
        k = clamp(1 - abs(h - 18.0), 0.0, 1.0)
        if k > 0.03:
            self.rim.set_alpha(int(255 * k))
            canvas.blit(self.rim, self.rim_at)

    def draw_hands(self, canvas, pal_hand: dict, look: dict | None = None, dy: int = 0, curl: bool = False,
                   light: float = 1.0, glow: float = 0.0) -> None:
        """두 손이 불 쪽으로 손바닥을 펼침 (왼손 x 150~200, 오른손 x 300~350, y 236~270). 같은 모양은 캐시."""
        light, glow = round(light * 20) / 20, round(glow * 20) / 20
        key = ("hands", dy, curl, light, glow, (look or {}).get("glove"), bool((look or {}).get("mitten")))
        hc = self._hand_cache
        img = hc.get(key)
        if img is None:
            if len(hc) > 40:
                hc.clear()
            img = hc[key] = self._make_hands(pal_hand, look, dy, curl, light, glow).subsurface(
                (0, HAND_TOP, self.w, self.h - HAND_TOP)).copy()   # 화면 아래 띠만 보관
        canvas.blit(img, (0, HAND_TOP))

    def _make_hands(self, pal_hand, look, dy, curl, light, glow) -> pygame.Surface:
        look = look or {}
        skin, shadow = pal_hand["hand"], pal_hand["hand_shadow"]
        sleeve = pal_hand["sleeve"]
        glove = look.get("glove")
        if glove is not None:
            skin = tuple(glove)
            shadow = scale_color(skin, 0.74)
        # 밤: 어둡게 + 손바닥이 불빛으로 주황
        fire = (255, 154, 74)
        skin = lerp_color(scale_color(skin, light), fire, 0.32 * glow)
        shadow = lerp_color(scale_color(shadow, light), scale_color(fire, 0.7), 0.25 * glow)
        sleeve = scale_color(sleeve, max(0.3, light))
        s = pygame.Surface((self.w, self.h), pygame.SRCALPHA)
        for side in (-1, 1):
            cx = self.X(175 if side < 0 else 325)
            base = 270 + dy
            # 소매 (화면 아래 밖에서)
            pygame.draw.polygon(s, sleeve, [(cx - 22, base + 4), (cx + 22, base + 4), (cx + 15 + side * 3, base - 10),
                                            (cx - 15 + side * 3, base - 10)])
            s.fill(scale_color(sleeve, 0.75), (cx - 16 + side * 3, base - 11, 32, 3))   # 끝동
            # 손바닥 (손목 → 위로)
            palm = pygame.Rect(0, 0, 30, 22)
            palm.midbottom = (cx + side * 3, base - 10)
            pygame.draw.ellipse(s, skin, palm)
            pygame.draw.ellipse(s, scale_color(skin, 1.06), palm.inflate(-8, -8).move(-side, 1))   # 손바닥 가운데 밝게
            pygame.draw.arc(s, shadow, palm.inflate(-6, -2).move(side * 2, 2), 3.6, 5.6, 1)   # 손금
            if look.get("mitten"):
                mit = pygame.Rect(0, 0, 22, 16)
                mit.midbottom = (palm.centerx, palm.top + 4)
                pygame.draw.ellipse(s, skin, mit)
                s.fill(scale_color(skin, 0.6), (palm.x + 2, palm.bottom - 3, palm.w - 4, 2))   # 손목 띠
            else:
                # 손가락 넷 (불 쪽으로 살짝 기울어 펼침) + 엄지 (안쪽)
                for i in range(4):
                    fx = palm.x + 5 + i * 6 + (2 if side > 0 else 0)
                    ln = (12, 15, 14, 11)[i if side > 0 else 3 - i] - (5 if curl else 0)
                    tilt = (i - 1.5) * 1.2
                    pygame.draw.line(s, skin, (fx, palm.y + 5), (fx + tilt, palm.y + 5 - ln), 5)
                    pygame.draw.line(s, shadow, (fx + 3, palm.y + 4), (fx + 3 + tilt, palm.y + 8 - ln), 1)   # 손가락 사이
                    s.fill(scale_color(skin, 1.1), (int(fx + tilt) - 1, palm.y + 6 - ln, 2, 1))   # 손가락 끝 볼록
                tx = palm.right - 3 if side < 0 else palm.left + 3
                pygame.draw.line(s, skin, (tx, palm.bottom - 6), (tx - side * 8, palm.y + 2), 5)   # 엄지 (안쪽)
                if glove is not None:   # 니트 짜임 줄
                    for k in range(3):
                        s.fill(scale_color(skin, 0.82), (palm.x + 4, palm.y + 5 + k * 4, palm.w - 8, 1))
        out = _outlined(s)
        if glow > 0.05:   # 손가락 사이로 새는 불빛: 외곽선 위쪽을 주황으로
            rim = pygame.mask.from_surface(s).outline()
            col = lerp_color(OUT, (255, 170, 96), min(1.0, glow))
            for x, y in rim:
                if y < 262 + dy and (x + y) % 2 == 0:
                    out.set_at((x, y - 1), col)
        return out

    def draw(self, canvas, pal: dict, hour: float, t: float, hand_pal: dict, hand_look: dict | None = None,
             hand_dy: int = 0) -> None:
        """미리보기용 한 번에 그리기 (조명 포함)."""
        ls = self.light_state(hour, "clear", t)
        self.draw_world(canvas, pal, hour, t, ls)
        self.draw_light(canvas, ls, t)
        self.draw_top(canvas, ls, t)
        self.draw_hands(canvas, hand_pal, hand_look, hand_dy, light=1 - 0.55 * ls["nk"], glow=ls["nk"])

    def draw_world(self, canvas, pal: dict, hour: float, t: float, ls: dict, cloud_shift: float = 0.0,
                   sun: bool = True) -> None:
        """덮개 아래: 하늘 → 먼 산 (+석양 테두리) → 땅 → 그림자 → 가까운 것 → 장작 · 걸이 → 앞 돌 → 연기."""
        self.draw_sky(canvas, pal, hour, t, cloud_shift, visible=sun)
        canvas.blit(self.back_top, (0, 0))   # 먼 산 + 중간 숲
        canvas.blit(self.back_bot, (0, 124))   # 땅 (불투명)
        if sun:
            self.draw_rim(canvas, hour)
        self.draw_shadows(canvas, ls, hour, sun)
        canvas.blit(self.mid, (0, 0))    # 나무 · 텐트 · 소품 · 돌 · 장작 · 걸이 · 앞 돌 · 머그컵
        nk = ls["nk"]
        if nk > 0.05:   # 밤: 주전자 아랫면 불빛
            pot = self.pot_rect
            canvas.fill(lerp_color((30, 30, 36), (232, 120, 60), 0.6 * min(1.0, nk)), (pot.x + 2, pot.bottom - 2, pot.w - 4, 2))
        self.draw_smoke(canvas, nk)

    def draw_top(self, canvas, ls: dict, t: float, height_k: float = 1.0, haze: bool = True) -> None:
        """덮개 위: 숯 · 불꽃 · 불티 · 아지랑이 · 김."""
        self.draw_coals(canvas, t)
        self.draw_flame_fx(canvas, t, height_k)
        if haze:
            self.draw_haze(canvas, t, height_k)
        self.draw_steam(canvas, t)


class _Cam:
    def __init__(self, width: int, horizon: int):
        self.width, self.horizon = width, horizon
