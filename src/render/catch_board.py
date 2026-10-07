"""잡은 직후 (DETAILS.md D, DESIGN.md 45장 DT7): 나무 계측판 · 놓아주기 장면. 수치는 data/details/hands_catch.json.

계측판 (일반 · 고급 · 희귀, 뜰채 장면 → 포획 카드 사이) — 눈금 간격은 늘 같고(ppc_px), 큰 물고기는 화면 밖까지 + 카메라 이동,
아주 작은 물고기는 카메라 확대 (v1.5.2):
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
from src.render.fish_draw import draw_fish_side, fish_bounds, fish_colors, fish_shape

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
    """눈금(1cm = ppc_px)은 크기와 상관없이 늘 같다. 물고기가 판보다 길면 화면 밖으로 나가고 카메라가 머리 끝 표시를 따라
    오른쪽으로 이동하며 잰다 (그만큼 길어짐). 아주 작은 물고기는 카메라가 물고기 쪽으로 확대해서 보여 준다."""

    def __init__(self, fish: dict, size_cm: float, mode: str, w: int, h: int, rnd=None):
        c = cfg()["board"]
        self.c = c
        self.fish, self.size, self.mode = fish, size_cm, mode
        self.w, self.h = w, h
        self.t = 0.0
        r = rnd or random.Random()
        self.flaps = [] if mode == "short" else sorted(r.uniform(0.42, 0.95) for _ in range(r.randint(*c["flaps"])))
        self.flap_fired = 0
        self.events: list[str] = []
        self.bx0, self.bx1 = int(w * 0.12), int(w * 0.88)
        self.view_w = self.bx1 - self.bx0 - 6           # 0 눈금부터 오른쪽 끝까지 화면 폭 (px)
        self.ppc = c["ppc_px"]                         # 1cm 눈금 간격 (고정)
        self.len_cm = max(c["min_len_cm"], (int(size_cm // 10) + 2) * 10)
        self.by = int(h * 0.5)
        fish_px = size_cm * self.ppc
        # 작은 물고기: 물고기가 화면 폭의 zoom_fill 만큼 되도록 확대 (최대 zoom_max)
        self.zoom = clamp(self.view_w * c["zoom_fill"] / max(1.0, fish_px), 1.0, c["zoom_max"]) \
            if fish_px < self.view_w * c["zoom_below"] else 1.0
        # 큰 물고기: 머리 끝 표시가 화면 pan_keep 지점을 넘으면 카메라가 따라감 → 넘는 만큼 시간을 더
        self.overflow = max(0.0, fish_px - self.view_w * c["pan_keep"])
        extra = min(c["pan_max_extra_sec"], self.overflow / c["pan_px_per_sec"])
        self.slide = c["slide_sec"] + extra
        self.slide_at = c["short_slide_at"] if mode == "short" else c["slide_at"]
        self.sec = (c["short_sec"] if mode == "short" else c["normal_sec"]) + extra + (c["zoom_hold_sec"] if self.zoom > 1 else 0.0)
        self.glints = [(r.uniform(0.1, 0.9), r.uniform(-0.35, 0.35), r.uniform(0, 6.3)) for _ in range(10)]
        shape = fish_shape(fish)
        bx, by, bw, bh = fish_bounds(shape)
        self.shape, self.fb = shape, (bx, by, bw, bh)

    @property
    def done(self) -> bool:
        return self.t >= self.sec

    def can_skip(self) -> bool:
        return self.t >= self.c["skip_after_sec"]

    def update(self, dt: float) -> list[str]:
        self.t += dt
        ev = []
        while self.flap_fired < len(self.flaps) and self.t >= self.flaps[self.flap_fired]:
            self.flap_fired += 1
            ev.append("flap")
        return ev

    def _marker_cm(self) -> float:
        u = clamp((self.t - self.slide_at) / self.slide, 0, 1)
        if self.overflow > 0:   # 길게 미끄러질 땐 거의 일정한 속도로 (끝에서만 부드럽게 멈춤)
            return self.size * (u if u < 0.85 else 0.85 + 0.15 * (1 - (1 - (u - 0.85) / 0.15) ** 2))
        return self.size * (1 - (1 - u) ** 3)

    def camera(self) -> tuple[float, float]:
        """(왼쪽 화면 기준 0 눈금에서 얼마나 오른쪽을 보고 있나 px(배율 1 기준), 배율)."""
        z = 1.0
        if self.zoom > 1:
            zk = 1.0 if self.mode == "short" else smooth(clamp((self.t - 0.4) / 0.5, 0, 1))
            z = lerp(1.0, self.zoom, zk)
        pan = 0.0
        if self.overflow > 0:
            mpx = self._marker_cm() * self.ppc
            pan = max(0.0, mpx - self.view_w * self.c["pan_keep"])
        return pan, z

    def draw(self, canvas, pal) -> None:
        w, h = self.w, self.h
        shade = pygame.Surface((w, h), pygame.SRCALPHA)
        shade.fill((10, 12, 22, 200))
        canvas.blit(shade, (0, 0))
        pan, z = self.camera()
        zx0 = self.bx0 + 6                      # 배율 1 · 이동 0 일 때 0 눈금의 화면 x
        y0 = self.by
        # 확대 중심: 물고기 가운데 (작은 물고기) — 0 눈금이 화면 안에 남도록
        fish_px = self.size * self.ppc
        if z > 1:
            fc = zx0 + fish_px / 2
            zk = (z - 1) / max(1e-6, self.zoom - 1)
            ax, ay = lerp(zx0, fc, zk), y0
        else:
            ax, ay = zx0, y0

        def X(cm: float) -> float:
            return ax + (zx0 + cm * self.ppc - pan - ax) * z

        def Y(dy: float) -> float:
            return ay + dy * z

        top, bot = Y(-34), Y(34)
        x_start = X(-1.5)
        x_end = X(self.len_cm + 4)
        # 나무판 + 결 (cm 좌표에 고정 — 카메라와 함께 움직임)
        left, right = max(-4, int(x_start)), min(w + 4, int(x_end))
        if right > left:
            canvas.fill(WOOD_D, (left + 2, int(top) + 3, right - left, int(bot - top)))
            canvas.fill(WOOD, (left, int(top), right - left, int(bot - top)))
            r = random.Random(17)
            for _ in range(max(9, int(self.len_cm / 10))):
                gy = r.uniform(-30, 31)
                g0 = r.uniform(0, max(1, self.len_cm - 15))
                g1 = g0 + r.uniform(8, 22)
                col = WOOD_L if r.random() < 0.5 else WOOD_D
                pygame.draw.line(canvas, col, (X(g0), Y(gy)), (X(g1), Y(gy)), 1)
            stop_x = X(0) - 6 * z
            if stop_x + 6 * z > -2:
                canvas.fill(WOOD_D, (int(stop_x), int(top), max(2, int(6 * z)), int(bot - top)))   # 0 쪽 멈춤 턱
        # 물고기: 코끝을 0 에 대고 (머리 왼쪽), 몸길이 = 크기 × 눈금 간격 (배율 포함). 판 위로 크면 화면 밖까지
        bx, by, bw, bh = self.fb
        L = fish_px * z / bw
        put = 1.0 if self.mode == "short" else smooth(clamp(self.t / 0.35, 0, 1))
        flap = 0.0
        for ft in self.flaps:
            d = self.t - ft
            if 0 <= d < 0.22:
                flap = max(flap, math.sin(math.pi * d / 0.22))
        cy = Y(-4) - (1 - put) * 40 - flap * 6
        nose = X(0)
        fcx = nose - bx * L
        fcy = cy - (by + bh / 2) * L
        if nose + bw * L > -10 and nose < w + 10:
            draw_fish_side(canvas, fcx, fcy, L, 0.0, fish_colors(self.fish), -1, tail_wag=flap * 6, shape=self.shape)
        # 젖은 비늘 반짝임
        fw, fh = bw * L, bh * L
        for u, v, ph in self.glints:
            if math.sin(self.t * 9 + ph * 3) > 0.55:
                gx, gy = nose + u * fw, cy + v * fh * 0.7
                if 0 <= gx < w and 0 <= gy < h:
                    canvas.fill((255, 255, 250), (int(gx), int(gy), 1, 1))
        # 줄자 띠 (판 아래쪽, 물고기 위에 — 큰 물고기도 눈금이 늘 보임). 1cm 눈금 · 5cm 중간 · 10cm 숫자 (간격 고정)
        from src.core.fonts import get_font
        font = get_font(11)
        tape_h = 16                              # 띠 굵기 · 글자는 확대와 상관없이 같게 (눈금 간격만 확대)
        tape_y0 = int(min(Y(18), h - tape_h - 6))
        if right > left:
            canvas.fill((236, 222, 176), (left, tape_y0, right - left, tape_h))
            canvas.fill((198, 176, 120), (left, tape_y0 + tape_h - 1, right - left, 1))
        step_px = self.ppc * z
        cm0 = max(0, int((0 - X(0)) / step_px) - 1)
        cm1 = min(self.len_cm, int((w - X(0)) / step_px) + 1)
        for cm in range(cm0, cm1 + 1):
            x = int(round(X(cm)))
            if cm % 10 == 0:
                pygame.draw.line(canvas, INK, (x, tape_y0), (x, tape_y0 + 8), 1)
                img = font.render(str(cm), False, INK)
                canvas.blit(img, (x - img.get_width() // 2, tape_y0 + tape_h - img.get_height() + 1))
            elif cm % 5 == 0:
                pygame.draw.line(canvas, INK, (x, tape_y0), (x, tape_y0 + 6), 1)
                if step_px >= 9:
                    img = font.render(str(cm), False, lerp_color(INK, (236, 222, 176), 0.35))
                    canvas.blit(img, (x - img.get_width() // 2, tape_y0 + tape_h - img.get_height() + 1))
            else:
                pygame.draw.line(canvas, INK, (x, tape_y0), (x, tape_y0 + 3), 1)
            if step_px >= 14:   # 크게 확대됐을 땐 1mm 대신 0.5cm 눈금
                xh = int(round(X(cm + 0.5)))
                pygame.draw.line(canvas, INK, (xh, tape_y0), (xh, tape_y0 + 2), 1)
        # 손 (올려놓는 동안만)
        if self.mode != "short" and self.t < 0.5:
            k = 1 - clamp((self.t - 0.3) / 0.2, 0, 1)
            hx = min(w * 0.6, nose + fw * 0.55)
            hy = cy - 10 - (1 - k) * 40
            skin = pal.get("hand", (230, 180, 140))
            pygame.draw.ellipse(canvas, skin, (hx - 12, hy - 6, 24, 12))
            pygame.draw.ellipse(canvas, pal.get("hand_shadow", (190, 140, 110)), (hx - 12, hy - 6, 24, 12), 1)
            pygame.draw.polygon(canvas, pal.get("sleeve", (70, 90, 140)), [(hx + 6, hy - 4), (hx + 40, hy - 40), (hx + 56, hy - 30), (hx + 12, hy + 4)])
        # 머리 끝 표시 (미끄러지며 크기에 멈춤 — 카메라가 따라감)
        mcm = self._marker_cm()
        mx = int(round(X(mcm)))
        ttop = max(2, int(top) - 6)
        canvas.fill((240, 236, 226), (mx - 1, ttop, 3, int(tape_y0 + tape_h) - ttop + 2))
        pygame.draw.polygon(canvas, (220, 70, 60), [(mx - 4, ttop - 4), (mx + 4, ttop - 4), (mx, ttop + 2)])
        if mcm > 0.1:
            label = font.render(f"{mcm:.1f}cm", False, (255, 240, 200))
            lx = min(w - 4 - label.get_width(), max(4, mx - label.get_width() // 2))
            canvas.blit(label, (lx, max(2, ttop - 18)))


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
