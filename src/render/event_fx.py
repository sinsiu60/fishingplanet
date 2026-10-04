"""날씨 이벤트 연출 (DESIGN.md 35-14): 유성 · 쌍무지개 · 붉은 달·붉은 수면 · 은빛 안개.

파이팅 중에는 은은하게 (절반), 신호 슬롯을 가리지 않게 하늘·수평선 근처에만. 엘드라시온은 색만 대륙 분위기(청록·별빛)로.
환상 전용 표현(오로라·멈춘 물방울·보라)은 쓰지 않는다. 환상 팔레트는 이 위에 덧입혀져 우선한다.
"""
import math
import random

import pygame

from src.core.mathutil import lerp_color

RAINBOW = ((230, 80, 80), (240, 150, 60), (240, 220, 90), (110, 200, 110), (90, 160, 230), (110, 110, 210))


def event_palette(pal: dict, eid: str | None, cont: str = "sharmion") -> dict:
    if not eid:
        return pal
    out = dict(pal)
    if eid == "red_moon":
        red = (170, 40, 40) if cont == "sharmion" else (170, 50, 70)
        for key, k in (("water_top", 0.3), ("water_bottom", 0.25), ("wave_light", 0.35), ("reflection", 0.4), ("sky_top", 0.12)):
            if isinstance(out.get(key), tuple):
                out[key] = lerp_color(out[key], red, k)
    elif eid == "silver_fog":
        sil = (205, 212, 222) if cont == "sharmion" else (200, 215, 235)
        for key, v in out.items():
            if isinstance(v, tuple) and key not in ("text", "bobber", "bobber_base", "hand", "hand_shadow"):
                out[key] = lerp_color(v, sil, 0.18)
    return out


class EventFx:
    def __init__(self, rnd=None):
        self.rnd = rnd or random.Random()
        self.meteors: list[list] = []
        self.t = 0.0

    def update(self, dt: float, eid: str | None, w: int, horizon: float, fighting: bool) -> None:
        self.t += dt
        if eid != "meteor":
            self.meteors.clear()
            return
        rate = 0.7 if fighting else 1.8
        if self.rnd.random() < rate * dt:
            x = self.rnd.uniform(w * 0.1, w * 1.1)
            self.meteors.append([x, self.rnd.uniform(-10, horizon * 0.5), self.rnd.uniform(-260, -160), self.rnd.uniform(90, 150),
                                 self.rnd.uniform(0.5, 0.9)])
        for m in self.meteors:
            m[0] += m[2] * dt
            m[1] += m[3] * dt
            m[4] -= dt
        self.meteors = [m for m in self.meteors if m[4] > 0 and m[1] < horizon]

    def draw_sky(self, canvas, eid: str | None, cont: str, horizon: float, fighting: bool) -> None:
        """하늘 쪽 (산·물보다 먼저): 유성 · 쌍무지개 · 붉은 달."""
        if not eid:
            return
        w = canvas.get_width()
        k = 0.5 if fighting else 1.0
        hz = int(horizon)
        if eid == "meteor":
            head = (255, 250, 230) if cont == "sharmion" else (200, 250, 245)
            for x, y, vx, vy, life in self.meteors:
                n = (vx * vx + vy * vy) ** 0.5
                tail = 46
                a = min(1.0, life / 0.3) * k
                end = (x - vx / n * tail, y - vy / n * tail)
                base = canvas.get_at((max(0, min(w - 1, int(x))), max(0, min(hz, int(y)))))
                mid = (x - vx / n * tail * 0.4, y - vy / n * tail * 0.4)
                pygame.draw.line(canvas, lerp_color(base, head, 0.45 * a), mid, end, 1)
                pygame.draw.line(canvas, lerp_color(base, head, 0.9 * a), (x, y), mid, 2)
                canvas.fill(lerp_color(base, (255, 255, 255), a), (int(x) - 1, int(y) - 1, 3, 3))
        elif eid == "double_rainbow":
            surf = pygame.Surface((w, hz), pygame.SRCALPHA)
            cx, cy = int(w * 0.56), hz + 60
            for ring, (r0, alpha, order) in enumerate(((200, 70, RAINBOW), (236, 38, RAINBOW[::-1]))):
                for i, col in enumerate(order):
                    pygame.draw.circle(surf, (*col, int(alpha * k)), (cx, cy), r0 - i * 3, 3)
            canvas.blit(surf, (0, 0))
        elif eid == "red_moon":
            mx, my = int(w * 0.72), int(hz * 0.38)
            g = pygame.Surface((80, 80))
            for rr, a in ((38, 0.12), (26, 0.2), (18, 0.3)):
                pygame.draw.circle(g, tuple(int(v * a * k) for v in (220, 60, 50)), (40, 40), rr)
            canvas.blit(g, (mx - 40, my - 40), special_flags=pygame.BLEND_RGB_ADD)
            pygame.draw.circle(canvas, (200, 60, 50) if cont == "sharmion" else (190, 60, 80), (mx, my), 13)
            pygame.draw.circle(canvas, (230, 110, 90), (mx - 3, my - 3), 4)

    def draw_low(self, canvas, eid: str | None, cont: str, horizon: float, fighting: bool) -> None:
        """수면 쪽 (물 위): 붉은 달빛 길 · 은빛 안개 띠."""
        if not eid:
            return
        w, h = canvas.get_size()
        k = 0.5 if fighting else 1.0
        hz = int(horizon)
        if eid == "red_moon":
            mx = int(w * 0.72)
            for i in range(14):
                y = hz + 3 + i * 5
                ln = 14 + i * 2 + 4 * math.sin(self.t * 2 + i)
                canvas.fill(lerp_color(canvas.get_at((max(0, min(w - 1, mx)), min(h - 1, y))), (230, 80, 60), 0.5 * k),
                            (int(mx - ln / 2), y, int(ln), 1))
        elif eid == "silver_fog":
            fog = pygame.Surface((w, h), pygame.SRCALPHA)
            col = (225, 230, 238) if cont == "sharmion" else (215, 228, 245)
            for i in range(7):
                y = hz - 14 + i * 13 + math.sin(self.t * 0.4 + i) * 4
                a = int((90 - i * 8) * k)
                x = (self.t * (6 + i * 2)) % 120 - 120
                for xx in range(int(x), w, 120):
                    pygame.draw.ellipse(fog, (*col, max(10, a)), (xx, y, 160, 18))
            canvas.blit(fog, (0, 0))
