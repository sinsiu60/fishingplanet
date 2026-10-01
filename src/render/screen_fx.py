"""화면 연출: 가짜 FOV(줌·패닝·기울기)와 화면 테두리 VFX.

물고기 행동을 한눈에 읽을 수 있도록 상태마다 화면 전체의 '느낌'을 바꾼다.

  행동            카메라(가짜 FOV)              테두리 VFX
  ─────────────  ───────────────────────────  ─────────────────────────────
  돌진 예고/돌진   줌 아웃(뒤로 확 당겨짐)·흔들림   주황 비네트 + 집중선(스피드 라인)
  점프 예고/점프   물고기 쪽으로 줌 인            하늘색 테두리 맥동
  방향 전환        전환 방향으로 패닝 + 기울기     그쪽 가장자리에 화살표(>>>) 흐름
  힘 모으기(멈춤)  천천히 줌 인                  어두운 비네트가 조여옴 + 심장 박동
  지침/완전 지침    살짝 풀림                     초록 테두리 맥동 ("기회!")
  빨간 구간        -                            빨간 비네트
  퍼펙트          줌 펀치                       화면 섬광 + 충격파
"""
import math
import random

import numpy as np
import pygame

from src.core.mathutil import clamp, lerp

BASE_FIGHT_ZOOM = 1.035  # 파이팅 중 기본 줌 (줌 아웃 연출의 여유)

COL_RUSH = (255, 150, 60)
COL_JUMP = (110, 220, 255)
COL_TURN = (255, 230, 90)
COL_CHARGE = (24, 0, 34)
COL_TIRED = (110, 255, 140)
COL_RED = (230, 40, 40)


class ScreenFX:
    def __init__(self, width: int, height: int):
        self.w, self.h = width, height
        # 카메라 상태 (부드럽게 목표로 이동)
        self.zoom = 1.0
        self.pan_x = 0.0
        self.tilt = 0.0
        self.focus = (width / 2, height / 2)
        self.punch = 0.0          # 퍼펙트 줌 펀치
        self.enabled = True
        # 테두리 효과 세기 0~1
        self.v_rush = self.v_jump = self.v_charge = self.v_tired = self.v_red = 0.0
        self.turn_dir = 0
        self.v_turn = 0.0
        self.flash = 0.0
        self.flash_color = (255, 255, 255)
        self.speed_lines: list[list[float]] = []
        self.shockwaves: list[list] = []
        self.rays: list[list] = []
        self.t = 0.0
        self.layer = pygame.Surface((width, height), pygame.SRCALPHA)
        self._mask = self._make_vignette_mask()
        self._vignettes: dict[tuple, pygame.Surface] = {}
        self._map = None

    # ───────────────────────── 준비 ─────────────────────────
    def _make_vignette_mask(self) -> np.ndarray:
        xs = (np.arange(self.w) - self.w / 2) / (self.w / 2)
        ys = (np.arange(self.h) - self.h / 2) / (self.h / 2)
        d = np.sqrt(xs[:, None] ** 2 * 0.85 + ys[None, :] ** 2 * 1.15)
        return np.clip((d - 0.55) / 0.6, 0, 1) ** 1.6

    def _vignette(self, color) -> pygame.Surface:
        if color not in self._vignettes:
            surf = pygame.Surface((self.w, self.h), pygame.SRCALPHA)
            surf.fill((*color, 0))
            alpha = pygame.surfarray.pixels_alpha(surf)
            alpha[:] = (self._mask * 255).astype(np.uint8)
            del alpha
            self._vignettes[color] = surf
        return self._vignettes[color]

    # ───────────────────────── 이벤트 ─────────────────────────
    def perfect(self, pos) -> None:
        self.punch = 0.09
        self.flash = 0.75
        self.flash_color = (255, 250, 220)
        for i in range(3):
            self.shockwaves.append([pos[0], pos[1], -i * 0.06, (255, 220, 110), 0.5, 3])
        for i in range(14):
            a = i / 14 * math.tau + random.uniform(-0.1, 0.1)
            self.rays.append([pos[0], pos[1], a, 0.0, random.uniform(70, 140)])

    def great(self, pos) -> None:
        self.punch = 0.04
        self.flash = 0.3
        self.flash_color = (200, 255, 230)
        self.shockwaves.append([pos[0], pos[1], 0.0, (140, 255, 190), 0.4, 2])

    def miss(self, pos) -> None:
        self.flash = 0.25
        self.flash_color = (255, 60, 50)
        self.shockwaves.append([pos[0], pos[1], 0.0, (255, 80, 70), 0.3, 1])

    def reset(self) -> None:
        self.v_rush = self.v_jump = self.v_charge = self.v_tired = self.v_red = self.v_turn = 0.0
        self.speed_lines.clear()

    # ───────────────────────── 틱 ─────────────────────────
    def update(self, dt: float, fight, fish_pos) -> None:
        self.t += dt
        self.punch = max(0.0, self.punch - dt * 0.35)
        self.flash = max(0.0, self.flash - dt * 3.0)
        for s in self.shockwaves:
            s[2] += dt
        self.shockwaves = [s for s in self.shockwaves if s[2] < s[4]]
        for r in self.rays:
            r[3] += dt
        self.rays = [r for r in self.rays if r[3] < 0.3]

        zoom_t, pan_t, tilt_t = 1.0, 0.0, 0.0
        focus_k = 0.0
        tgt = dict(rush=0.0, jump=0.0, charge=0.0, tired=0.0, red=0.0, turn=0.0)
        if fight is not None and fight.phase == "fight":
            b = fight.brain
            sig, state = b.signal, b.state
            prog = b.signal_progress()
            zoom_t = BASE_FIGHT_ZOOM
            if sig == "rush" or state == "rush":
                k = prog if sig == "rush" else 1.0
                zoom_t = lerp(BASE_FIGHT_ZOOM, 1.0, k)  # 뒤로 확 당겨지는 느낌
                tgt["rush"] = 0.35 + 0.65 * k
            elif sig == "jump" or state == "jump":
                k = prog if sig == "jump" else 1.0
                zoom_t = lerp(BASE_FIGHT_ZOOM, 1.09, k)
                focus_k = 0.55 * k
                tgt["jump"] = 0.4 + 0.6 * k
            elif sig == "turn" or state == "turn":
                k = prog if sig == "turn" else 1.0
                pan_t = b.turn_dir * 7 * k
                tilt_t = -b.turn_dir * 1.4 * k
                zoom_t = BASE_FIGHT_ZOOM + 0.025 * k
                tgt["turn"] = 0.4 + 0.6 * k
                self.turn_dir = b.turn_dir
            elif state == "charge":
                k = clamp(b.state_t / 1.2, 0, 1)
                zoom_t = lerp(BASE_FIGHT_ZOOM, 1.075, k)
                focus_k = 0.35 * k
                tgt["charge"] = 0.5 + 0.5 * k
            elif state in ("tired", "fake_tired", "exhausted"):
                zoom_t = 1.02
                tgt["tired"] = 0.8 if state == "exhausted" else 0.65
            if fight.zone() == "red":
                tgt["red"] = 0.45 + 0.4 * clamp((fight.tension - fight.green_high) / 30, 0, 1)
            elif fight.line_frac < 0.3:
                tgt["red"] = 0.35
        if not self.enabled:
            zoom_t, pan_t, tilt_t, focus_k = 1.0, 0.0, 0.0, 0.0

        ease = 1 - math.exp(-dt / 0.12)
        self.zoom = lerp(self.zoom, zoom_t, ease)
        self.pan_x = lerp(self.pan_x, pan_t, ease)
        self.tilt = lerp(self.tilt, tilt_t, ease)
        cx, cy = self.w / 2, self.h / 2
        fx = cx + (fish_pos[0] - cx) * focus_k if fish_pos else cx
        fy = cy + (fish_pos[1] - cy) * focus_k if fish_pos else cy
        self.focus = (lerp(self.focus[0], fx, ease), lerp(self.focus[1], fy, ease))

        fe = 1 - math.exp(-dt / 0.1)
        self.v_rush = lerp(self.v_rush, tgt["rush"], fe)
        self.v_jump = lerp(self.v_jump, tgt["jump"], fe)
        self.v_charge = lerp(self.v_charge, tgt["charge"], fe)
        self.v_tired = lerp(self.v_tired, tgt["tired"], fe)
        self.v_red = lerp(self.v_red, tgt["red"], fe)
        self.v_turn = lerp(self.v_turn, tgt["turn"], fe)

        # 집중선: 돌진 중 가장자리에서 중심으로 뻗는 선
        if self.v_rush > 0.25:
            for _ in range(int(7 * self.v_rush)):
                a = random.uniform(0, math.tau)
                self.speed_lines.append([a, random.uniform(0.8, 1.05), random.uniform(0.22, 0.45), 0.0,
                                         random.uniform(0.1, 0.2)])
        for s in self.speed_lines:
            s[3] += dt
        self.speed_lines = [s for s in self.speed_lines if s[3] < s[4]]

    # ───────────────────────── 가짜 FOV ─────────────────────────
    def apply_camera(self, canvas: pygame.Surface) -> None:
        z = self.zoom + self.punch
        tilt = self.tilt
        if abs(z - 1.0) < 0.002 and abs(self.pan_x) < 0.3 and abs(tilt) < 0.05:
            self._map = None
            return
        w, h = self.w, self.h
        z = max(z, 1.0 + abs(tilt) * 0.035)  # 기울일 때 빈 모서리가 안 보이게
        sw, sh = w / z, h / z
        left = clamp(self.focus[0] - sw / 2 + self.pan_x, 0, w - sw)
        top = clamp(self.focus[1] - sh / 2, 0, h - sh)
        rect = pygame.Rect(int(left), int(top), int(math.ceil(sw)), int(math.ceil(sh)))
        rect = rect.clip(canvas.get_rect())
        zoomed = pygame.transform.scale(canvas.subsurface(rect), (w, h))
        if abs(tilt) >= 0.05:
            rot = pygame.transform.rotate(zoomed, tilt)
            canvas.fill((0, 0, 0))
            canvas.blit(rot, rot.get_rect(center=(w / 2, h / 2)))
        else:
            canvas.blit(zoomed, (0, 0))
        self._map = (rect.left, rect.top, w / rect.width, h / rect.height, math.radians(tilt))

    def map(self, pos):
        """카메라 연출 전 좌표 → 연출 후 화면 좌표 (UI를 물고기 위치에 붙일 때)."""
        if self._map is None or pos is None:
            return pos
        left, top, kx, ky, a = self._map
        x = (pos[0] - left) * kx
        y = (pos[1] - top) * ky
        if a:
            cx, cy = self.w / 2, self.h / 2
            vx, vy = x - cx, y - cy
            ca, sa = math.cos(a), math.sin(a)
            x = cx + vx * ca + vy * sa
            y = cy - vx * sa + vy * ca
        return x, y

    # ───────────────────────── 테두리 VFX ─────────────────────────
    def draw_edges(self, canvas: pygame.Surface) -> None:
        t = self.t
        w, h = self.w, self.h
        if self.v_red > 0.02:
            pulse = 0.75 + 0.25 * math.sin(t * 14)
            self._blit_vignette(canvas, COL_RED, self.v_red * pulse)
        if self.v_rush > 0.02:
            self._blit_vignette(canvas, COL_RUSH, self.v_rush * 0.7)
        if self.v_jump > 0.02:
            pulse = 0.6 + 0.4 * math.sin(t * 16)
            self._blit_vignette(canvas, COL_JUMP, self.v_jump * 0.6 * pulse)
        if self.v_charge > 0.02:
            # 심장 박동: 두 번 쿵쿵
            ph = (t * 1.3) % 1.0
            beat = max(math.exp(-((ph - 0.0) / 0.06) ** 2), 0.7 * math.exp(-((ph - 0.18) / 0.06) ** 2))
            self._blit_vignette(canvas, COL_CHARGE, clamp(self.v_charge * (0.8 + 0.35 * beat), 0, 1))
        if self.v_turn > 0.02 and self.turn_dir:
            # 전환 방향 쪽 가장자리만 노랗게 빛남
            pulse = 0.7 + 0.3 * math.sin(t * 18)
            self._blit_side(canvas, self.turn_dir, self.v_turn * 0.75 * pulse)
        if self.v_tired > 0.02:
            pulse = 0.55 + 0.45 * math.sin(t * 4)
            self._blit_vignette(canvas, COL_TIRED, self.v_tired * 0.55 * pulse)

        layer = self.layer
        layer.fill((0, 0, 0, 0))
        cx, cy = w / 2, h / 2
        # 집중선
        for a, r0, ln, age, life in self.speed_lines:
            k = 1 - age / life
            ex, ey = math.cos(a), math.sin(a)
            rx, ry = w * 0.62, h * 0.62
            p0 = (cx + ex * rx * r0 * 1.2, cy + ey * ry * r0 * 1.2)
            p1 = (cx + ex * rx * (r0 * 1.2 - ln), cy + ey * ry * (r0 * 1.2 - ln))
            pygame.draw.line(layer, (255, 248, 230, int(230 * k)), p0, p1, 2 if ln > 0.35 else 1)
        # 충격파 (퍼펙트·그레잇)
        for x, y, age, col, life, width in self.shockwaves:
            if age < 0:
                continue
            k = age / life
            r = 6 + k * 120
            pygame.draw.circle(layer, (*col, int(255 * (1 - k))), (int(x), int(y)), int(r), width)
        # 빛줄기 (퍼펙트)
        for x, y, a, age, ln in self.rays:
            k = age / 0.3
            r0 = 10 + k * 40
            p0 = (x + math.cos(a) * r0, y + math.sin(a) * r0)
            p1 = (x + math.cos(a) * (r0 + ln * (1 - k)), y + math.sin(a) * (r0 + ln * (1 - k)))
            pygame.draw.line(layer, (255, 240, 170, int(230 * (1 - k))), p0, p1, 2)
        canvas.blit(layer, (0, 0))
        # 섬광
        if self.flash > 0.01:
            fl = pygame.Surface((w, h))
            fl.fill(self.flash_color)
            fl.set_alpha(int(150 * self.flash))
            canvas.blit(fl, (0, 0))

    def _blit_side(self, canvas, direction: int, amount: float) -> None:
        key = ("side", direction)
        if key not in self._vignettes:
            surf = pygame.Surface((self.w, self.h), pygame.SRCALPHA)
            surf.fill((*COL_TURN, 0))
            xs = np.arange(self.w) / self.w
            k = np.clip((xs - 0.72) / 0.28, 0, 1) if direction > 0 else np.clip((0.28 - xs) / 0.28, 0, 1)
            alpha = pygame.surfarray.pixels_alpha(surf)
            alpha[:] = (np.repeat((k ** 1.5)[:, None], self.h, axis=1) * 200).astype(np.uint8)
            del alpha
            self._vignettes[key] = surf
        v = self._vignettes[key]
        v.set_alpha(int(255 * clamp(amount, 0, 1)))
        canvas.blit(v, (0, 0))

    def _blit_vignette(self, canvas, color, amount: float) -> None:
        v = self._vignette(color)
        v.set_alpha(int(255 * clamp(amount, 0, 1)))
        canvas.blit(v, (0, 0))
