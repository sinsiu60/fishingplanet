"""전설 3페이즈 컷신 — 눈빛 대치 + 각자의 필살 (CORE_UPDATE CU11). 수치는 data/legend_phase3.json.

① 눈빛 대치 1.2초 (12종 공통): 물고기 머리로 2.2배 확대 → 눈 클로즈업(동공이 원 → 세로 칼날) · 무대 색 테두리 → 무대 색 번쩍.
② 각자의 필살 1.5초 (전설마다 다른 장면, 등용은 기존 용 변신 2.4초를 ② 로) → 체력 바가 50% 까지 차오름 0.3초.
동안 파이팅은 정지 (fishing_scene 이 update 를 건너뜀). 흔들림 최대 5px, 번쩍은 ① 의 한 번. 환상 전용 표현(정적 · 멈춘 물방울 · 오로라) 없음.
좌표는 확대 전 화면 좌표, compose() 가 카드 · HUD 를 그리기 전에 캔버스에 입힘.
"""
import math
import random

import pygame

from src.core.config import load_json
from src.core.mathutil import clamp, lerp, lerp_color


def cfg() -> dict:
    return load_json("legend_phase3.json")


class Phase3Cine:
    def __init__(self, fish: dict, fish_pos: tuple[float, float], size: tuple[int, int], horizon: float,
                 stage_color: tuple | None, reduce: bool, skippable: bool):
        c = cfg()
        self.c = c
        self.fish = fish
        self.fid = fish["id"]
        self.dragon = fish["id"] == "dragon_carp"
        self.fx, self.fy = fish_pos
        self.W, self.H = size
        self.horizon = horizon
        self.stage = tuple(stage_color) if stage_color else (255, 214, 90)
        self.eye_col = tuple(c["eye_colors"].get(self.fid, self.stage))
        self.reduce = reduce
        self.skippable = skippable
        self.rnd = random.Random(hash(self.fid) & 0xFFFF)
        self.t = 0.0
        self.eye_end = c["eye_sec"]
        self.fin_end = self.eye_end + (c["dragon_sec"] if self.dragon else c["fin_sec"])
        self.end = self.fin_end + c["bar_sec"]
        self.done = False
        self.fired: set = set()
        self.parts: list[list] = []

    # ───────────────────────── 시계 ─────────────────────────
    @property
    def blocking(self) -> bool:
        return not self.done

    def can_skip(self) -> bool:
        return self.skippable and self.c["skip_after"] <= self.t < self.fin_end

    def skip(self) -> None:
        self.t = self.fin_end
        self.fired |= {"heart", "eye_flash", "fin", "dragon"}
        self.parts.clear()

    def update(self, dt: float) -> list[tuple]:
        """이벤트 [("sfx", 이름, 음량) | ("theme", 테마, 짧은이름, 음량) | ("mus", dB, 초) | ("dragon",) | ("done",)]."""
        self.t += dt
        ev = []
        c = self.c

        def at(key, when):
            if key not in self.fired and self.t >= when:
                self.fired.add(key)
                return True
            return False
        if at("heart", 0.0):
            ev.append(("mus", c["music_db"], self.fin_end))   # 보스 곡 −6dB (마지막에 원래대로 — 3페이즈 브리지와 겹침)
            for name, vol, _ in c["heart_sfx"]:
                ev.append(("sfx", name, vol))
        if at("fin", self.eye_end):
            if self.dragon:
                ev.append(("dragon",))
        for i, (name, vol, delay) in enumerate(c["fin_sfx"].get(self.fid, [])):
            if at(f"fs{i}", self.eye_end + delay):
                if name.startswith("theme:"):
                    _, th, short = name.split(":")
                    ev.append(("theme", th, short, vol))
                else:
                    ev.append(("sfx", name, vol))
        if at("end", self.end):
            self.done = True
            ev.append(("done",))
        self._tick_parts(dt)
        return ev

    def bar_value(self, before: float, after: float) -> float:
        """체력 바: 컷신 동안 진입 전 값 → 마지막 bar_sec 에 phase3_heal 까지 차오름."""
        if self.t < self.fin_end:
            return before
        k = clamp((self.t - self.fin_end) / self.c["bar_sec"], 0, 1)
        return lerp(before, after, 1 - (1 - k) ** 2)

    # ───────────────────────── 입자 ─────────────────────────
    def _tick_parts(self, dt: float) -> None:
        for p in self.parts:
            p[0] += p[2] * dt
            p[1] += p[3] * dt
            p[3] += p[5] * dt
            p[4] -= dt
        self.parts = [p for p in self.parts if p[4] > 0]

    def _emit(self, n, x, y, spread, sp, life, grav, col, up=False):
        for _ in range(n):
            a = (-math.pi / 2 if up else self.rnd.uniform(0, math.tau)) + self.rnd.uniform(-spread, spread)
            v = self.rnd.uniform(sp * 0.4, sp)
            self.parts.append([x, y, math.cos(a) * v, math.sin(a) * v, self.rnd.uniform(life * 0.5, life), grav, col])

    # ───────────────────────── 그리기 ─────────────────────────
    def compose(self, canvas) -> None:
        if self.t < self.eye_end:
            self._draw_eye(canvas)
        elif self.t < self.fin_end and not self.dragon:
            u = (self.t - self.eye_end) / (self.fin_end - self.eye_end)
            getattr(self, "_fin_" + self.fid, self._fin_default)(canvas, u)
            for p in self.parts:
                k = clamp(p[4], 0, 1)
                canvas.fill(lerp_color((0, 0, 0), p[6], 0.4 + 0.6 * k), (int(p[0]), int(p[1]), 2, 2))

    def shake(self) -> tuple[int, int]:
        """필살 순간의 흔들림 (최대 5px)."""
        if self.reduce or not (self.eye_end <= self.t < self.fin_end) or self.dragon:
            return 0, 0
        u = (self.t - self.eye_end) / (self.fin_end - self.eye_end)
        amp = self.c["shake_max"] * max(0.0, 1 - abs(u - 0.3) / 0.3) * self._shake_k()
        return int(math.sin(self.t * 53) * amp), int(math.cos(self.t * 47) * amp)

    def _shake_k(self) -> float:
        return {"tiger_mandarin": 1.0, "ignis": 1.0, "orsiel": 1.0, "silver_bass": 0.8, "coelacanth": 0.6}.get(self.fid, 0.4)

    # ① 눈빛 대치
    def _draw_eye(self, canvas) -> None:
        c, t = self.c, self.t
        W, H = self.W, self.H
        zin = c["zoom_in_sec"]
        if not self.reduce:   # 물고기 머리로 2.2배 확대 (0.25초) → 0.9~1.2 에 풀림
            if t < zin:
                z = lerp(1.0, c["zoom_eye"], 1 - (1 - t / zin) ** 2)
            elif t < c["flash_at"]:
                z = c["zoom_eye"]
            else:
                z = lerp(c["zoom_eye"], 1.0, (t - c["flash_at"]) / (self.eye_end - c["flash_at"]))
            if z > 1.01:
                cw, ch = W / z, H / z
                x0 = clamp(self.fx - cw / 2, 0, W - cw)
                y0 = clamp(self.fy - ch / 2, 0, H - ch)
                src = canvas.subsurface(pygame.Rect(int(x0), int(y0), max(1, int(cw)), max(1, int(ch)))).copy()
                canvas.blit(pygame.transform.scale(src, (W, H)), (0, 0))
        k = clamp((t - zin) / 0.15, 0, 1) * clamp((self.eye_end - t) / 0.2, 0, 1)
        if k <= 0.01:
            return
        dim = pygame.Surface((W, H), pygame.SRCALPHA)
        dim.fill((0, 0, 0, int(150 * k)))
        canvas.blit(dim, (0, 0))
        cx, cy = W // 2, H // 2 - 6
        r = int(c["eye_px"] / 2 * (0.6 + 0.4 * k))
        glow = lerp_color((0, 0, 0), self.stage, 0.8 * k)
        for i in range(3, 0, -1):   # 눈 둘레 무대 색 빛 테두리
            pygame.draw.circle(canvas, lerp_color((0, 0, 0), glow, 1 - i * 0.25), (cx, cy), r + i * 3, 2)
        pygame.draw.circle(canvas, lerp_color((20, 18, 14), self.eye_col, 0.85), (cx, cy), r)       # 홍채
        pygame.draw.circle(canvas, lerp_color(self.eye_col, (255, 255, 255), 0.5), (cx, cy), r, 1)
        s = clamp((t - zin - 0.1) / 0.3, 0, 1)   # 동공: 원 → 세로 칼날 (0.3초)
        pw = max(2, int(lerp(r * 0.6, 3, s)))
        ph = int(lerp(r * 0.6, r * 0.95, s))
        pygame.draw.ellipse(canvas, (8, 6, 4), (cx - pw, cy - ph, pw * 2, ph * 2))
        canvas.fill((255, 255, 255), (cx - r // 2, cy - r // 2, 3, 3))   # 반사광
        if not self.reduce and c["flash_at"] <= t < c["flash_at"] + 1 / 60 + 1e-3:
            ov = pygame.Surface((W, H))
            ov.fill(self.stage)
            ov.set_alpha(int(255 * c["flash_alpha"]))
            canvas.blit(ov, (0, 0))   # 무대 색 번쩍 (20%, 1프레임 — 이 컷신의 번쩍 한 번)

    # ② 각자의 필살 (u = 0~1)
    def _fin_default(self, canvas, u: float) -> None:
        pass

    def _sky_dim(self, canvas, col, a):
        ov = pygame.Surface((self.W, self.H), pygame.SRCALPHA)
        ov.fill((*col, int(a)))
        canvas.blit(ov, (0, 0))

    def _fin_golden_carp(self, canvas, u):
        """여우비: 햇빛 속 굵은 소나기 + 하늘에 무지개 + 금빛 꼬리로 수면을 침."""
        W, H, hz = self.W, self.H, int(self.horizon)
        a = clamp(u / 0.25, 0, 1) * clamp((1 - u) / 0.2, 0, 1)
        cols = [(230, 80, 80), (240, 150, 60), (245, 220, 90), (120, 210, 110), (90, 160, 240), (110, 100, 220), (170, 110, 220)]
        cx, cy, R = W // 2, hz + 30, int(W * 0.42)
        for i, col in enumerate(cols):
            pygame.draw.arc(canvas, lerp_color((0, 0, 0), col, 0.9 * a), (cx - R + i * 3, cy - R + i * 3, (R - i * 3) * 2, (R - i * 3) * 2),
                            0.15, math.pi - 0.15, 3)
        rnd = random.Random(int(self.t * 30))
        for _ in range(int(60 * a)):
            x, y = rnd.randrange(W), rnd.randrange(H)
            pygame.draw.line(canvas, (255, 240, 200), (x, y), (x - 3, y + 9), 1)
        if 0.35 < u < 0.6 and rnd.random() < 0.7:
            self._emit(6, self.fx, self.fy, 0.8, 140, 0.7, 380, (255, 215, 90), up=True)

    def _fin_tiger_mandarin(self, canvas, u):
        """산군: 계곡 안개가 확 밀려오고 그 속에서 호랑이 무늬 그림자가 포효."""
        W, H = self.W, self.H
        fog = clamp(u / 0.3, 0, 1) * clamp((1 - u) / 0.25, 0, 1)
        sweep = clamp(u / 0.3, 0, 1)   # 양옆에서 안개가 확 밀려옴 (부드러운 띠 — 가운데가 짙음)
        fogs = pygame.Surface((W, H), pygame.SRCALPHA)
        for i in range(4):
            cy = int(H * (0.3 + i * 0.16) + math.sin(self.t * 1.7 + i) * 6)
            reach = int(W * 0.5 * sweep) + 30
            for j in range(-14, 15):
                a = int(70 * fog * (1 - abs(j) / 15))
                for side in (0, 1):
                    x0 = 0 if side == 0 else W - reach
                    fogs.fill((235, 238, 240, a), (x0, cy + j, reach, 1))
        canvas.blit(fogs, (0, 0))
        k = clamp((u - 0.2) / 0.3, 0, 1) * clamp((1 - u) / 0.3, 0, 1)
        if k > 0:
            cx, cy, s = self.W // 2, int(self.horizon) - 10, 1 + 0.25 * math.sin(u * 20)
            body = pygame.Rect(0, 0, int(150 * s), int(54 * s))
            body.center = (cx, cy)
            col = lerp_color((40, 40, 46), (20, 16, 10), 0.5)
            surf = pygame.Surface(body.size, pygame.SRCALPHA)
            pygame.draw.ellipse(surf, (*col, int(200 * k)), surf.get_rect())
            for j in range(7):   # 호랑이 무늬
                x = int(surf.get_width() * (0.15 + j * 0.11))
                pygame.draw.line(surf, (230, 150, 40, int(220 * k)), (x, 4), (x - 8, surf.get_height() - 6), 3)
            canvas.blit(surf, body)
            pygame.draw.circle(canvas, lerp_color((0, 0, 0), (255, 200, 60), k), (body.left + 22, body.top + 16), 3)   # 눈

    def _fin_silver_bass(self, canvas, u):
        """일렉트로: 하늘에서 번개가 수면에 내리꽂힘 (흰 세로 줄기 2개) + 물 위 전기 스파크."""
        W, hz = self.W, int(self.horizon)
        for i, x0 in enumerate((W * 0.38, W * 0.62)):
            on = (0.05 + i * 0.12) < u < (0.3 + i * 0.12)
            if not on:
                continue
            rnd = random.Random(int(self.t * 40) + i)
            x, y = x0, 0
            pts = [(x, y)]
            while y < self.fy:
                y += rnd.randint(10, 20)
                x += rnd.randint(-9, 9)
                pts.append((x, min(y, self.fy)))
            pygame.draw.lines(canvas, (255, 255, 255), False, pts, 3)
            pygame.draw.lines(canvas, (150, 210, 255), False, pts, 1)
            self._emit(4, x, self.fy, math.pi, 120, 0.4, 0, (190, 230, 255))
        if u > 0.2:
            rnd = random.Random(int(self.t * 25))
            for _ in range(10):
                a = rnd.uniform(0, math.tau)
                r = (u - 0.2) * self.W * 0.5 * rnd.random()
                x, y = self.fx + math.cos(a) * r, self.fy + math.sin(a) * r * 0.25
                pygame.draw.line(canvas, (200, 240, 255), (x, y), (x + rnd.randint(-4, 4), y + rnd.randint(-3, 3)), 1)
        _ = hz

    def _fin_marlin(self, canvas, u):
        """일섬: 화면을 가로지르는 칼빛 (흰 선 왼→오 0.15초) → 화면이 위아래로 1px 어긋났다 붙음 · 붉은 낙관 번쩍 · 징."""
        W, H = self.W, self.H
        y = int(H * 0.45)
        k = clamp(u / 0.1, 0, 1)   # 0.15초 = 1.5초의 0.1
        if u < 0.35:
            pygame.draw.line(canvas, (255, 255, 255), (0, y), (int(W * k), y), 2)
            pygame.draw.line(canvas, (230, 240, 255), (0, y - 2), (int(W * k), y - 2), 1)
        if 0.12 < u < 0.4 and not self.reduce:   # 위아래로 1px 어긋남
            top = canvas.subsurface((0, 0, W, y)).copy()
            canvas.blit(top, (2, -1))
        if 0.15 < u < 0.7:
            a = clamp((u - 0.15) / 0.1, 0, 1) * clamp((0.7 - u) / 0.2, 0, 1)
            r = pygame.Rect(0, 0, 28, 28)
            r.center = (W - 46, int(H * 0.3))
            seal = pygame.Surface(r.size, pygame.SRCALPHA)
            seal.fill((200, 30, 30, int(220 * a)))
            pygame.draw.rect(seal, (255, 220, 200, int(200 * a)), seal.get_rect(), 1)
            pygame.draw.line(seal, (255, 220, 200, int(220 * a)), (6, 14), (22, 14), 2)   # 낙관 글자 '一'
            canvas.blit(seal, r)

    def _fin_coelacanth(self, canvas, u):
        """태고: 화면 아래에서 심연의 어둠이 차오름 (남색이 화면 60%까지) · 거대한 실루엣이 그 속을 지나감."""
        W, H = self.W, self.H
        rise = clamp(u / 0.4, 0, 1) * clamp((1 - u) / 0.25, 0, 1)
        top = int(H - H * 0.6 * rise)
        ov = pygame.Surface((W, H - top), pygame.SRCALPHA)
        for i in range(H - top):
            ov.fill((14, 22, 60, int(230 * min(1.0, i / 30 + 0.4))), (0, i, W, 1))
        canvas.blit(ov, (0, top))
        if rise > 0.3:
            x = int(lerp(-160, W + 40, clamp((u - 0.2) / 0.7, 0, 1)))
            y = top + (H - top) // 2
            pygame.draw.ellipse(canvas, (4, 8, 26), (x, y - 22, 170, 44))
            pygame.draw.polygon(canvas, (4, 8, 26), [(x, y), (x - 26, y - 18), (x - 26, y + 18)])

    def _fin_silva(self, canvas, u):
        """실바: 늪의 갈대가 일제히 물고기 쪽으로 쓰러지며 홀씨 폭풍."""
        W, H = self.W, self.H
        lean = clamp(u / 0.35, 0, 1)
        for i in range(26):
            x = int(i * W / 25)
            base = H - 4
            d = 1 if x < self.fx else -1
            ang = -math.pi / 2 + d * lean * 1.0
            ln = 70 + (i * 37) % 40
            tip = (x + math.cos(ang) * ln, base + math.sin(ang) * ln)
            pygame.draw.line(canvas, (150, 160, 110), (x, base), tip, 2)
            pygame.draw.ellipse(canvas, (200, 190, 140), (tip[0] - 3, tip[1] - 6, 6, 10))
        if 0.3 < u < 0.85:
            self._emit(8, self.rnd.uniform(0, W), H - 40, 1.2, 160, 0.9, -30, (240, 235, 200), up=True)

    def _fin_prisia(self, canvas, u):
        """프리시아: 공중의 결정들이 한꺼번에 깨지며 빛 조각이 사방으로."""
        W, H = self.W, self.H
        if u < 0.35:
            rnd = random.Random(7)
            for _ in range(14):
                x, y = rnd.uniform(30, W - 30), rnd.uniform(20, H * 0.5)
                s = 6 + rnd.random() * 6
                pts = [(x, y - s), (x + s * 0.6, y), (x, y + s), (x - s * 0.6, y)]
                pygame.draw.polygon(canvas, (200, 170, 255), pts)
                pygame.draw.polygon(canvas, (255, 255, 255), pts, 1)
        elif "shatter" not in self.fired:
            self.fired.add("shatter")
            rnd = random.Random(7)
            for _ in range(14):
                x, y = rnd.uniform(30, W - 30), rnd.uniform(20, H * 0.5)
                self._emit(9, x, y, math.pi, 150, 0.9, 120, (220, 200, 255))

    def _fin_aeris(self, canvas, u):
        """에어리스: 돌풍이 구름을 찢으며 화면을 휘감는 바람 줄."""
        W, H = self.W, self.H
        k = clamp(u / 0.2, 0, 1) * clamp((1 - u) / 0.2, 0, 1)
        for i in range(9):
            ph = self.t * 3 + i * 0.7
            cy = H * (0.15 + i * 0.09)
            pts = [(x, cy + math.sin(x / 40 + ph) * 14 + math.sin(ph * 2) * 6) for x in range(-20, W + 21, 12)]
            off = int((u * 1.6 - i * 0.05) * W) % (W + 200) - 100
            seg = [(x + off - W // 2, y) for x, y in pts]
            pygame.draw.lines(canvas, lerp_color((0, 0, 0), (235, 250, 255), 0.85 * k), False, seg, 1)

    def _fin_ignis(self, canvas, u):
        """이그니스: 수면 아래서 용암이 분출 (주홍 기둥 + 화산재) · 물에서 김."""
        H = self.H
        hgt = int(H * 0.75 * math.sin(math.pi * clamp(u / 0.75, 0, 1)))
        if hgt > 2:
            for j in range(-4, 5):
                w = 6
                h = int(hgt * (1 - abs(j) / 6))
                col = lerp_color((255, 90, 30), (255, 210, 90), 1 - abs(j) / 5)
                canvas.fill(col, (int(self.fx + j * w - w / 2), int(self.fy - h), w, h))
            self._emit(5, self.fx, self.fy - hgt, 1.0, 90, 1.0, 60, (70, 60, 60), up=True)   # 화산재
            self._emit(3, self.fx + self.rnd.uniform(-40, 40), self.fy, 0.4, 60, 0.8, -20, (225, 225, 230), up=True)   # 김

    def _fin_borealis(self, canvas, u):
        """보레알리스: 수면이 쩍쩍 얼어붙으며 금이 퍼짐 → 물고기가 얼음을 깨고 솟음 (오로라 없음)."""
        W, hz = self.W, int(self.horizon)
        ice = pygame.Surface((W, self.H - hz), pygame.SRCALPHA)
        ice.fill((210, 235, 250, int(110 * clamp(u / 0.3, 0, 1))))
        canvas.blit(ice, (0, hz))
        rnd = random.Random(3)
        reach = clamp(u / 0.6, 0, 1)
        for i in range(10):
            a = rnd.uniform(0, math.tau)
            x, y = self.fx, self.fy
            for s in range(6):
                if s / 6 > reach:
                    break
                nx = x + math.cos(a) * 22
                ny = max(hz + 2, y + math.sin(a) * 6)
                pygame.draw.line(canvas, (255, 255, 255), (x, y), (nx, ny), 1)
                x, y = nx, ny
                a += rnd.uniform(-0.6, 0.6)
        if 0.6 < u < 0.75:
            self._emit(6, self.fx, self.fy, 0.9, 170, 0.8, 380, (220, 245, 255), up=True)   # 얼음을 깨고 솟음

    def _fin_orsiel(self, canvas, u):
        """오르시엘: 수평선에서 거대한 해일이 일어 화면을 덮칠 듯 → 직전에 갈라짐."""
        W, H, hz = self.W, self.H, int(self.horizon)
        rise = clamp(u / 0.6, 0, 1)
        split = clamp((u - 0.6) / 0.3, 0, 1)
        top = int(hz - (hz + 20) * rise)
        gap = int(W * 0.6 * split)
        for side in (-1, 1):
            x0 = W // 2 + side * gap // 2
            pts = [(x0, hz)]
            for i in range(13):
                x = x0 + side * i * (W // 24)
                y = top + int(math.sin(i * 0.8 + self.t * 6) * 8) + int(i * 2 * (1 - rise))
                pts.append((x, y))
            pts.append((x0 + side * W, hz))
            surf = pygame.Surface((W, H), pygame.SRCALPHA)
            pygame.draw.polygon(surf, (30, 60, 110, 220), pts)
            pygame.draw.lines(surf, (230, 245, 255, 230), False, pts[1:-1], 2)   # 물마루 흰 거품
            canvas.blit(surf, (0, 0))
