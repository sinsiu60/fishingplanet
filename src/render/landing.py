"""뜰채 성공 → 획득 컷 사이의 연출 (약 2.1초).

1) 뜰채 스윙 (0~0.5초): 뜰채가 아래에서 올라와 물고기를 퍼 담는다. 닿는 순간 섬광·물보라·히트스톱.
2) 끌어올리기 (0.5~1.25초): 시선이 하늘로 올라가고(화면이 아래로 흐름), 그물 속 물고기가 퍼덕이며 물이 떨어진다.
3) 튀어 오름 (1.25~2.1초): 물고기가 그물에서 빙글 돌며 튀어 오르고, 희귀도 색 빛살 → 정점 반짝 → 하얀 섬광.
그 다음 획득 컷에서 물고기가 위에서 떨어져 두 손에 안긴다 (fish_draw.draw_catch_cut).
"""
import math
import random

import pygame

from src.core.mathutil import clamp, lerp, lerp_color, scale_color, smoothstep
from src.render.fish_draw import draw_fish_side, fish_colors

T_HIT = 0.22      # 뜰채가 물고기에 닿음
T_SCOOP = 0.5     # 퍼 담기 끝
T_LIFT = 1.25     # 끌어올리기 끝 → 튀어 오름 시작
T_APEX = 1.7      # 공중 정점
T_FLASH = 1.92    # 섬광 최대
TOTAL = 2.1
HIT_STOP = 0.07   # 닿는 순간 잠깐 멈춤

RARITY_GLOW = {"common": (255, 245, 210), "uncommon": (150, 255, 170), "rare": (140, 200, 255),
               "legend": (255, 210, 90)}


def _ease_out(k: float) -> float:
    k = clamp(k, 0, 1)
    return 1 - (1 - k) ** 3


class LandingCinematic:
    def __init__(self, fish: dict, size_cm: float, start_x: float):
        self.fish = fish
        self.colors = fish_colors(fish)
        self.shape = fish.get("shape")
        self.length = clamp(size_cm * 3.4, 80, 210)
        self.t = 0.0
        self.x0 = start_x
        self.y0 = 200.0
        self.drips: list[list[float]] = []
        self.splash: list[list[float]] = []
        self.sparks: list[list[float]] = []
        self.fired: set[str] = set()
        self.hold = 0.0
        self.glow = RARITY_GLOW.get(fish["rarity"], (255, 255, 255))

    @property
    def done(self) -> bool:
        return self.t >= TOTAL

    def skip(self) -> None:
        if self.t > 0.3:
            self.t = TOTAL

    # ───────────────────────── 틱 ─────────────────────────
    def update(self, dt: float) -> list[str]:
        """진행. 이번 틱에 일어난 연출 이벤트(소리용)를 돌려준다."""
        events = []
        if self.hold > 0:
            self.hold -= dt
        else:
            self.t += dt
        for key, at in (("hit", T_HIT), ("lift", T_SCOOP), ("launch", T_LIFT), ("apex", T_APEX), ("done", TOTAL)):
            if self.t >= at and key not in self.fired:
                self.fired.add(key)
                events.append(key)
                if key == "hit":
                    self.hold = HIT_STOP
                    fx, fy = self.fish_pos()
                    for _ in range(26):
                        a = random.uniform(math.pi * 1.05, math.pi * 1.95)
                        sp = random.uniform(60, 170)
                        self.splash.append([fx + random.uniform(-30, 30), fy, math.cos(a) * sp, math.sin(a) * sp,
                                            random.uniform(0.4, 0.8)])
                elif key == "apex":
                    fx, fy = self.fish_pos()
                    for i in range(28):
                        a = i / 28 * math.tau
                        sp = random.uniform(60, 140)
                        self.sparks.append([fx, fy, math.cos(a) * sp, math.sin(a) * sp, random.uniform(0.3, 0.6)])
        # 물방울: 끌어올리는 동안 그물에서 뚝뚝
        if T_HIT < self.t < T_LIFT + 0.2:
            nx, ny, r = self.net_pos()
            for _ in range(2):
                self.drips.append([nx + random.uniform(-r * 0.5, r * 0.5), ny + r * 0.75, random.uniform(-8, 8),
                                   random.uniform(10, 40), 1.0])
        for d in self.drips:
            d[0] += d[2] * dt
            d[1] += d[3] * dt
            d[3] += 420 * dt
            d[4] -= dt
        self.drips = [d for d in self.drips if d[4] > 0 and d[1] < 280]
        for p in self.splash + self.sparks:
            p[0] += p[2] * dt
            p[1] += p[3] * dt
            p[3] += (380 if p in self.splash else 0) * dt
            p[2] *= 0.96
            p[4] -= dt
        self.splash = [p for p in self.splash if p[4] > 0]
        self.sparks = [p for p in self.sparks if p[4] > 0]
        return events

    # ───────────────────────── 위치 계산 ─────────────────────────
    def tilt_offset(self) -> float:
        """시선을 들어 올리는 양 (화면이 아래로 흐르는 픽셀)."""
        if self.t < T_SCOOP:
            return 0.0
        return smoothstep((self.t - T_SCOOP) / (T_LIFT - T_SCOOP + 0.3)) * 150

    def net_pos(self):
        """뜰채 고리 중심과 반지름."""
        r = self.length * 0.58
        t = self.t
        if t < T_HIT:
            k = _ease_out(t / T_HIT)
            return lerp(430, self.x0, k), lerp(300, self.y0 + 6, k), r
        if t < T_SCOOP:
            k = (t - T_HIT) / (T_SCOOP - T_HIT)
            dip = math.sin(k * math.pi) * 8
            return self.x0, lerp(self.y0 + 6, self.y0 - 20, smoothstep(k)) + dip, r
        if t < T_LIFT:
            k = smoothstep((t - T_SCOOP) / (T_LIFT - T_SCOOP))
            return lerp(self.x0, 240, k), lerp(self.y0 - 20, 128, k), r
        # 튀어 오르면 뜰채는 아래로 빠짐
        k = (t - T_LIFT) / (TOTAL - T_LIFT)
        return 240, 128 + 260 * k * k, r

    def fish_pos(self):
        t = self.t
        if t < T_HIT:
            return self.x0, self.y0
        if t < T_LIFT:
            nx, ny, r = self.net_pos()
            return nx, ny + r * 0.32
        k = clamp((t - T_LIFT) / (T_APEX - T_LIFT), 0, 1)
        start_y = 128 + self.length * 0.58 * 0.32
        y = lerp(start_y, 78, _ease_out(k))
        if t > T_APEX:
            y += math.sin((t - T_APEX) * 6) * 2
        return 240, y

    # ───────────────────────── 그리기 ─────────────────────────
    def draw(self, canvas: pygame.Surface, pal: dict) -> None:
        w, h = canvas.get_size()
        t = self.t
        # 1) 시선 들어올리기: 아래로 흐르고 위는 하늘로 채움
        off = int(self.tilt_offset())
        if off > 0:
            canvas.scroll(0, off)
            top = scale_color(pal["sky_top"], 0.9)
            for y in range(0, off, 3):
                canvas.fill(lerp_color(top, pal["sky_top"], y / max(1, off)), (0, y, w, 3))
        water_line = int(self.y0 + self.length * 0.1) + off
        if t < T_SCOOP + 0.1:
            # 물고기가 잠긴 수면 (뜰채 단계와 같은 화면)
            water = lerp_color(pal["water_top"], pal["water_bottom"], 0.85)
            canvas.fill(water, (0, water_line, w, h - water_line))
            for i in range(6):
                yy = water_line + 3 + i * 6
                canvas.fill(pal["wave_light"], (int((t * 30 + i * 50) % 80) + i * 60, yy, 22, 1))

        # 2) 튀어 오를 때 뒤로 퍼지는 빛살
        if t > T_LIFT:
            k = clamp((t - T_LIFT) / 0.35, 0, 1)
            fx, fy = self.fish_pos()
            sky = pal["sky_top"]
            for i in range(14):
                a = t * 0.8 + i * math.tau / 14
                ln = 320 * k
                col = lerp_color(sky, self.glow, 0.55 if i % 2 else 0.3)
                pygame.draw.polygon(canvas, col, [(fx, fy), (fx + math.cos(a) * ln, fy + math.sin(a) * ln),
                                                  (fx + math.cos(a + 0.13) * ln, fy + math.sin(a + 0.13) * ln)])
            pygame.draw.circle(canvas, lerp_color(sky, self.glow, 0.7), (int(fx), int(fy)), int(30 * k + 6))

        # 3) 물고기 + 뜰채
        nx, ny, r = self.net_pos()
        fx, fy = self.fish_pos()
        in_net = T_HIT <= t < T_LIFT
        flap = math.sin(t * 34)
        if t < T_HIT:
            # 아직 물속에서 몸부림
            draw_fish_side(canvas, fx, fy, self.length, flap * 0.08, self.colors, -1, tail_wag=flap, shape=self.shape)
            water = lerp_color(pal["water_top"], pal["water_bottom"], 0.85)
            canvas.fill(water, (0, water_line, w, h - water_line))
            self._draw_net(canvas, pal, nx, ny, r, in_net=False, fish=None)
        elif in_net:
            self._draw_net(canvas, pal, nx, ny, r, in_net=True, fish=(fx, fy, flap))
        else:
            # 그물에서 튀어 올라 빙글
            k = clamp((t - T_LIFT) / (T_APEX - T_LIFT), 0, 1)
            spin = _ease_out(k) * math.tau * 1.0
            scale = lerp(1.0, 1.25, _ease_out(k))
            self._draw_net(canvas, pal, nx, ny, r, in_net=False, fish=None)
            draw_fish_side(canvas, fx, fy, self.length * scale, spin, self.colors, -1,
                           tail_wag=math.sin(t * 20) * (1 - k * 0.7), shape=self.shape)

        # 4) 입자
        drip_col = lerp_color(pal["wave_light"], (255, 255, 255), 0.4)
        for x, y, _, _, _ in self.drips:
            canvas.fill(drip_col, (int(x), int(y), 1, 2))
        for x, y, _, _, life in self.splash:
            s = 2 if life > 0.3 else 1
            canvas.fill(drip_col, (int(x), int(y), s, s))
        for x, y, _, _, life in self.sparks:
            canvas.fill((255, 255, 255) if life > 0.25 else self.glow, (int(x), int(y), 2, 2))

        # 5) 섬광: 닿는 순간 짧게, 마지막엔 하얗게 덮음
        flash = 0.0
        if T_HIT <= t < T_HIT + 0.12:
            flash = 0.55 * (1 - (t - T_HIT) / 0.12)
        if t > T_APEX:
            flash = max(flash, clamp((t - T_APEX) / (T_FLASH - T_APEX), 0, 1))
        if flash > 0.01:
            fl = pygame.Surface((w, h))
            fl.fill((255, 255, 250))
            fl.set_alpha(int(255 * flash))
            canvas.blit(fl, (0, 0))

    def _draw_net(self, canvas, pal, x, y, r, in_net: bool, fish) -> None:
        frame = (190, 196, 205)
        frame_dark = (110, 116, 130)
        mesh = (225, 228, 235)
        hw, hh = r, r * 0.28
        # 손잡이 + 두 손
        handle_end = (x + r * 1.9, y + r * 1.9)
        pygame.draw.line(canvas, frame_dark, (x + hw, y), handle_end, 4)
        pygame.draw.line(canvas, frame, (x + hw, y - 1), handle_end, 2)
        skin, shadow = pal["hand"], pal["hand_shadow"]
        if skin[0] < 90:
            skin, shadow = (225, 175, 140), (180, 125, 100)
        for k in (0.45, 0.8):
            hx = lerp(x + hw, handle_end[0], k)
            hy = lerp(y, handle_end[1], k)
            pygame.draw.ellipse(canvas, shadow, (hx - 9, hy - 5, 18, 13))
            pygame.draw.ellipse(canvas, skin, (hx - 9, hy - 7, 18, 11))
        # 그물 주머니 (뒤쪽 테두리 → 물고기 → 앞쪽 그물코)
        depth = r * 0.95
        bag = [(x - hw, y), (x - hw * 0.7, y + depth * 0.7), (x, y + depth), (x + hw * 0.7, y + depth * 0.7), (x + hw, y)]
        bag_col = lerp_color(pal["water_bottom"], mesh, 0.25)
        pygame.draw.polygon(canvas, bag_col, bag)
        pygame.draw.ellipse(canvas, frame_dark, (x - hw, y - hh, hw * 2, hh * 2), 2)
        if fish is not None:
            fx, fy, flap = fish
            draw_fish_side(canvas, fx, fy, self.length * 0.9, flap * 0.12, self.colors, -1, tail_wag=flap,
                           shape=self.shape)
        # 그물코
        for i in range(1, 8):
            u = i / 8
            top = (x - hw + u * hw * 2, y + hh * 0.2)
            pygame.draw.line(canvas, mesh, top, (x + (u - 0.5) * hw * 0.5, y + depth * 0.95), 1)
        for j in range(1, 4):
            v = j / 4
            yy = y + depth * v * 0.8
            half = hw * (1 - v * 0.55)
            pygame.draw.line(canvas, mesh, (x - half, yy), (x + half, yy), 1)
        # 앞쪽 테두리
        pygame.draw.arc(canvas, frame, (x - hw, y - hh, hw * 2, hh * 2), math.pi, math.tau, 3)
