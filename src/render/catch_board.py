"""잡은 직후 (DETAILS.md D, DESIGN.md 45장 DT7): 나무 계측판 · 놓아주기 장면. 수치는 data/details/hands_catch.json.

계측판 (일반 · 고급 · 희귀, 뜰채 장면 → 포획 카드 사이):
  보통 1.6초: 손이 물고기를 계측판(1cm 눈금, 10cm 마다 숫자)에 올림(0~0.35) → 파닥 2~3번 → 머리 끝 표시가 미끄러지며 크기에 멈춤(1.0~1.45)
  짧게 0.6초: 파닥 없이 눈금만 (물고기는 바로 놓여 있고 표시가 미끄러짐)
  0.3초 이후 탭 = 바로 카드. 젖은 비늘: 물고기 몸에 반짝임 점이 무작위로 깜빡임.
놓아주기 (1초): 물고기가 물로 돌아가 헤엄쳐 사라짐.
"""
import math
import random

import pygame

from src.core.config import load_json
from src.core.mathutil import clamp, lerp, lerp_color
from src.render.fish_draw import draw_fish_fit, draw_fish_side, fish_bounds, fish_colors, fish_shape

WOOD = (176, 128, 78)
WOOD_D = (128, 88, 50)
WOOD_L = (206, 160, 104)
INK = (58, 38, 22)


def cfg() -> dict:
    return load_json("details/hands_catch.json")


def size_class(size_cm: float) -> str:
    """퍼덕 소리 3단계 (뜰채 크기 4단계 small · mid · big · huge 를 작음 · 중간 · 큼으로)."""
    from src.render.landing import size_class as cls
    c = cls(size_cm)[0]
    return {"small": "small", "mid": "mid"}.get(c, "big")


class MeasureBoard:
    def __init__(self, fish: dict, size_cm: float, mode: str, w: int, h: int, rnd=None):
        c = cfg()["board"]
        self.fish, self.size, self.mode = fish, size_cm, mode
        self.w, self.h = w, h
        self.t = 0.0
        self.sec = c["short_sec"] if mode == "short" else c["normal_sec"]
        r = rnd or random.Random()
        self.flaps = [] if mode == "short" else sorted(r.uniform(0.42, 0.95) for _ in range(r.randint(*c["flaps"])))
        self.flap_fired = 0
        self.events: list[str] = []
        # 판 길이: 크기보다 10~20cm 길게, 10cm 단위
        self.len_cm = (int(size_cm // 10) + 2) * 10
        self.bx0, self.bx1 = int(w * 0.12), int(w * 0.88)
        self.ppc = (self.bx1 - self.bx0 - 10) / self.len_cm
        self.by = int(h * 0.5)
        self.glints = [(r.uniform(0.1, 0.9), r.uniform(-0.35, 0.35), r.uniform(0, 6.3)) for _ in range(10)]
        shape = fish_shape(fish)
        bx, by, bw, bh = fish_bounds(shape)
        self.shape, self.fb = shape, (bx, by, bw, bh)

    @property
    def done(self) -> bool:
        return self.t >= self.sec

    def can_skip(self) -> bool:
        return self.t >= cfg()["board"]["skip_after_sec"]

    def update(self, dt: float) -> list[str]:
        self.t += dt
        ev = []
        while self.flap_fired < len(self.flaps) and self.t >= self.flaps[self.flap_fired]:
            self.flap_fired += 1
            ev.append("flap")
        return ev

    def _marker_cm(self) -> float:
        if self.mode == "short":
            u = clamp((self.t - 0.05) / 0.45, 0, 1)
        else:
            u = clamp((self.t - 1.0) / 0.45, 0, 1)
        return self.size * (1 - (1 - u) ** 3)

    def draw(self, canvas, pal) -> None:
        w, h = self.w, self.h
        shade = pygame.Surface((w, h), pygame.SRCALPHA)
        shade.fill((10, 12, 22, 200))
        canvas.blit(shade, (0, 0))
        x0, x1, y = self.bx0, self.bx1, self.by
        top, bot = y - 34, y + 34
        # 나무판 + 결
        canvas.fill(WOOD_D, (x0 + 2, top + 3, x1 - x0, bot - top))
        canvas.fill(WOOD, (x0, top, x1 - x0, bot - top))
        r = random.Random(17)
        for _ in range(9):
            gy = r.randint(top + 4, bot - 3)
            gx = r.randint(x0, x1 - 60)
            pygame.draw.line(canvas, WOOD_L if r.random() < 0.5 else WOOD_D, (gx, gy), (gx + r.randint(30, 90), gy), 1)
        canvas.fill(WOOD_D, (x0, top, 6, bot - top))   # 0 쪽 멈춤 턱
        zx = x0 + 6
        font = None
        from src.core.fonts import get_font
        font = get_font(11)
        for cm in range(0, self.len_cm + 1):
            x = zx + int(cm * self.ppc)
            if x > x1 - 2:
                break
            if cm % 10 == 0:
                pygame.draw.line(canvas, INK, (x, top), (x, top + 9), 1)
                if cm:
                    img = font.render(str(cm), False, INK)
                    canvas.blit(img, (x - img.get_width() // 2, top + 9))
            elif cm % 5 == 0:
                pygame.draw.line(canvas, INK, (x, top), (x, top + 6), 1)
            elif self.ppc >= 2.0:
                pygame.draw.line(canvas, INK, (x, top), (x, top + 3), 1)
        # 물고기: 코끝을 0 에 대고 (머리 왼쪽) — 몸길이(그림 폭) = 크기 × 눈금 간격. 가로로 꽉 맞추는 draw_fish_fit 사용
        bx, by, bw, bh = self.fb
        L = self.size * self.ppc / bw
        fw, fh = int(round(self.size * self.ppc)), int(bh * L) + 4
        put = 1.0 if self.mode == "short" else smooth(clamp(self.t / 0.35, 0, 1))
        flap = 0.0
        for ft in self.flaps:
            d = self.t - ft
            if 0 <= d < 0.22:
                flap = max(flap, math.sin(math.pi * d / 0.22))
        cy = y + 2 - (1 - put) * 40 - flap * 6
        draw_fish_fit(canvas, pygame.Rect(zx, int(cy - fh / 2), fw, fh), self.fish, L * 1.001, tail_wag=flap * 6)
        # 젖은 비늘 반짝임
        for u, v, ph in self.glints:
            if math.sin(self.t * 9 + ph * 3) > 0.55:
                gx = zx + u * fw
                gy = cy + v * fh * 0.7
                canvas.fill((255, 255, 250), (int(gx), int(gy), 1, 1))
        # 손 (올려놓는 동안만)
        if self.mode != "short" and self.t < 0.5:
            k = 1 - clamp((self.t - 0.3) / 0.2, 0, 1)
            hx = zx + self.size * self.ppc * 0.55
            hy = cy - 10 - (1 - k) * 40
            skin = pal.get("hand", (230, 180, 140))
            pygame.draw.ellipse(canvas, skin, (hx - 12, hy - 6, 24, 12))
            pygame.draw.ellipse(canvas, pal.get("hand_shadow", (190, 140, 110)), (hx - 12, hy - 6, 24, 12), 1)
            pygame.draw.polygon(canvas, pal.get("sleeve", (70, 90, 140)), [(hx + 6, hy - 4), (hx + 40, hy - 40), (hx + 56, hy - 30), (hx + 12, hy + 4)])
        # 머리 끝 표시 (미끄러지며 크기에 멈춤)
        mcm = self._marker_cm()
        mx = zx + int(mcm * self.ppc)
        canvas.fill((240, 236, 226), (mx - 1, top - 6, 3, bot - top + 8))
        pygame.draw.polygon(canvas, (220, 70, 60), [(mx - 4, top - 10), (mx + 4, top - 10), (mx, top - 4)])
        if mcm > 0.1:
            label = font.render(f"{mcm:.1f}cm", False, (255, 240, 200))
            canvas.blit(label, (min(x1 - label.get_width(), max(x0, mx - label.get_width() // 2)), top - 24))


def smooth(u: float) -> float:
    return u * u * (3 - 2 * u)


class ReleaseScene:
    """놓아주기 1초: 물고기가 물로 돌아가 헤엄쳐 사라짐 (수면 아래로 내려가며 멀어지고 작아짐)."""

    def __init__(self, fish: dict, size_cm: float, w: int, h: int):
        self.fish, self.size, self.w, self.h = fish, size_cm, w, h
        self.t = 0.0
        self.sec = cfg()["release"]["sec"]
        shape = fish_shape(fish)
        self.shape, self.fb = shape, fish_bounds(shape)

    @property
    def done(self) -> bool:
        return self.t >= self.sec

    def update(self, dt: float) -> None:
        self.t += dt

    def draw(self, canvas, pal) -> None:
        w, h = self.w, self.h
        u = clamp(self.t / self.sec, 0, 1)
        shade = pygame.Surface((w, h), pygame.SRCALPHA)
        shade.fill((10, 16, 30, int(150 * (1 - u))))
        canvas.blit(shade, (0, 0))
        surf_y = int(h * 0.56)
        bx, by, bw, bh = self.fb
        L0 = min(w * 0.36, 40 + self.size * 1.2) / bw
        L = L0 * lerp(1.0, 0.35, u)
        cx = lerp(w * 0.5, w * 0.78, u)
        cy = lerp(surf_y - 18, surf_y + 26, smooth(min(1.0, u * 1.4)))
        wag = math.sin(self.t * 22) * 8
        col = fish_colors(self.fish)
        if u > 0.25:   # 물에 들어간 뒤: 물빛으로 흐려짐
            k = clamp((u - 0.25) / 0.6, 0, 1)
            sil = lerp_color(col.get("body", (120, 140, 160)) if isinstance(col, dict) else (120, 140, 160),
                             pal["water_bottom"], k)
            draw_fish_side(canvas, cx, cy, L, 0.05, col, 1, silhouette=sil if k > 0.5 else None, tail_wag=wag, shape=self.shape)
        else:
            draw_fish_side(canvas, cx, cy, L, -0.3 + u, col, 1, tail_wag=wag, shape=self.shape)
        # 수면 · 물보라 고리
        pygame.draw.line(canvas, lerp_color(pal["wave_light"], (255, 255, 255), 0.3), (0, surf_y), (w, surf_y), 1)
        if 0.18 < u < 0.7:
            k = (u - 0.18) / 0.52
            rx = 6 + 40 * k
            pygame.draw.ellipse(canvas, lerp_color((255, 255, 255), pal["water_top"], k),
                                (w * 0.58 - rx, surf_y - rx * 0.18, rx * 2, rx * 0.36), 1)
