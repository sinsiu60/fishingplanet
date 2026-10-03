"""패턴 판정 연출 (퍼펙트·그레잇과 같은 급으로): 색 입자·고리·나선·물기둥·파편.

낚시 화면이 판정 이벤트마다 burst_*()를 부르고, 월드 위·카메라 연출 전에 draw()한다 (줌·휘청과 함께 움직임).
모든 효과는 화면 좌표 (물고기 화면 위치 기준).

  패턴        성공 (그레잇 / 퍼펙트는 더 크게)             실패
  ─────────  ──────────────────────────────────────  ─────────────────────────
  머리 흔들기  잔잔해지는 회색 물결 고리 3겹 + 흰 반짝임     붉은 떨림 불꽃 (지그재그)
  잠수        위로 솟는 기포 기둥 + 반짝임                바닥 흙먼지 (갈색 파편, 아래로)
  수면 질주    눌러 막은 물보라 왕관 + 납작한 고리           위로 터지는 큰 물보라
  역주행      초록 회수 줄기(내 쪽으로 빨려 옴)             처진 줄: 회색 먼지가 아래로
  줄 비틀기    보라 나선이 바깥으로 풀림                    보라·빨강 뜯긴 실 조각
  숨기        바위 파편 + 기포 터짐 + 금색 고리             -
  펌핑 리듬    노란 박자 고리 3번 연속 + 음표 점              엇박 붉은 고리
  물어뜯기    '팅!' 쇠 불꽃 별 + 십자 섬광                  붉은 불꽃 + 끊긴 실 조각
  가짜 지침    눈빛 반짝(십자) + 보라 고리                  어두운 보라 연기
  콤보·이중    단계 색 고리가 차례로 + 금 빛줄기              금이 간 붉은 고리
"""
import math
import random

import pygame

from src.core.mathutil import clamp, lerp_color

GOLD = (255, 214, 90)


class PatternVFX:
    def __init__(self):
        self.parts: list[dict] = []   # 입자
        self.rings: list[dict] = []   # 퍼지는 고리 (원·타원)
        self.stars: list[dict] = []   # 십자 섬광

    # ───────────────────────── 기본 재료 ─────────────────────────
    def particles(self, x, y, n, col, speed=(40, 100), life=(0.4, 0.8), angle=None, spread=math.tau, gravity=0.0,
                  size=2, shape="dot", col2=None, drag=0.9) -> None:
        for i in range(n):
            if angle is None:
                a = i / max(1, n) * math.tau + random.uniform(-0.2, 0.2)
            else:
                a = angle + random.uniform(-spread / 2, spread / 2)
            sp = random.uniform(*speed)
            lf = random.uniform(*life)
            self.parts.append({"x": x, "y": y, "vx": math.cos(a) * sp, "vy": math.sin(a) * sp, "life": lf, "max": lf,
                               "col": col, "col2": col2 or col, "g": gravity, "size": size, "shape": shape,
                               "drag": drag})

    def ring(self, x, y, col, r1=60, life=0.45, width=2, delay=0.0, flat=1.0, r0=4) -> None:
        self.rings.append({"x": x, "y": y, "col": col, "r0": r0, "r1": r1, "life": life, "t": -delay, "w": width,
                           "flat": flat})

    def star(self, x, y, col, size=14, life=0.35, delay=0.0) -> None:
        self.stars.append({"x": x, "y": y, "col": col, "size": size, "life": life, "t": -delay})

    def spiral(self, x, y, col, n=24, out=True, turns=1.5, speed=70) -> None:
        """나선: 각 입자가 회전하며 바깥(또는 안)으로."""
        for i in range(n):
            a = i / n * math.tau * turns
            r = 4 + i * 1.2
            sp = speed * (1 if out else -1)
            self.parts.append({"x": x + math.cos(a) * r, "y": y + math.sin(a) * r * 0.6,
                               "vx": math.cos(a + 1.2) * sp, "vy": math.sin(a + 1.2) * sp * 0.6,
                               "life": 0.5 + i * 0.012, "max": 0.5 + i * 0.012, "col": col, "col2": (255, 255, 255),
                               "g": 0.0, "size": 2, "shape": "dot", "drag": 0.93})

    # ───────────────────────── 판정별 묶음 ─────────────────────────
    def success(self, pid: str, x: float, y: float, perfect: bool, col) -> None:
        k = 2.0 if perfect else 1.3
        n = int(14 * k)
        if pid == "shake":
            for i in range(3):
                self.ring(x, y + 4, (220, 230, 240), 46 * k + i * 10, 0.6, 1, i * 0.1, flat=0.35)
            self.particles(x, y, n, (255, 255, 255), (20, 60), (0.4, 0.7), col2=col)
        elif pid == "dive":
            self.particles(x, y + 6, int(20 * k), (200, 235, 255), (50, 120), (0.5, 0.9), angle=-math.pi / 2,
                           spread=0.7, gravity=-40, col2=(255, 255, 255))
            self.ring(x, y, col, 50 * k, 0.4, 2)
        elif pid == "surface":
            self.particles(x, y, int(18 * k), (230, 245, 255), (60, 130), (0.4, 0.7), angle=-math.pi / 2,
                           spread=2.4, gravity=260)
            self.ring(x, y + 3, (230, 245, 255), 64 * k, 0.45, 2, flat=0.3)
            self.ring(x, y + 3, col, 40 * k, 0.35, 1, 0.08, flat=0.3)
        elif pid == "reverse":
            # 내 쪽(화면 아래 가운데)으로 빨려 오는 초록 줄기
            for _ in range(int(16 * k)):
                a = random.uniform(0, math.tau)
                r = random.uniform(10, 30)
                px, py = x + math.cos(a) * r, y + math.sin(a) * r * 0.5
                self.parts.append({"x": px, "y": py, "vx": 0.0, "vy": 160 + random.uniform(0, 80), "life": 0.5,
                                   "max": 0.5, "col": col, "col2": (255, 255, 255), "g": 200, "size": 2,
                                   "shape": "streak", "drag": 1.0})
            self.ring(x, y, col, 54 * k, 0.4, 2)
        elif pid == "twist":
            self.spiral(x, y, col, int(26 * k), out=True, turns=2.0, speed=60 * k)
            self.ring(x, y, col, 50 * k, 0.45, 2)
        elif pid == "hide":
            self.particles(x, y, int(12 * k), (150, 140, 130), (60, 140), (0.4, 0.7), angle=-math.pi / 2, spread=2.6,
                           gravity=300, size=3, shape="chunk")
            self.particles(x, y, int(12 * k), (210, 235, 255), (20, 60), (0.4, 0.8), angle=-math.pi / 2, spread=1.2,
                           gravity=-50)
            self.ring(x, y, GOLD, 56 * k, 0.45, 2)
        elif pid == "pump":
            for i in range(3):
                self.ring(x, y, GOLD, 40 * k, 0.35, 2, i * 0.12)
            self.particles(x, y - 6, int(8 * k), GOLD, (40, 80), (0.5, 0.8), angle=-math.pi / 2, spread=1.8,
                           gravity=-20, size=3, shape="note")
        elif pid == "bite":
            self.star(x, y, (255, 255, 255), 22 * k, 0.3)
            self.star(x, y, (200, 230, 255), 12 * k, 0.4, 0.06)
            self.particles(x, y, int(16 * k), (230, 240, 255), (90, 170), (0.25, 0.45), shape="streak",
                           col2=(255, 220, 140))
        elif pid == "fake":
            self.star(x, y - 4, (240, 220, 255), 18 * k, 0.45)
            self.ring(x, y, (190, 130, 255), 52 * k, 0.45, 2)
            self.particles(x, y, int(10 * k), (220, 190, 255), (20, 60), (0.4, 0.7))
        else:  # rush 등: 작은 반짝
            self.ring(x, y, col, 34 * k, 0.3, 1)
            self.particles(x, y, int(8 * k), col, (30, 70), (0.3, 0.5))

    def fail(self, pid: str, x: float, y: float) -> None:
        red = (255, 90, 80)
        if pid == "shake":
            for _ in range(10):
                self.parts.append({"x": x + random.uniform(-10, 10), "y": y, "vx": random.choice((-1, 1)) * 140,
                                   "vy": random.uniform(-60, 20), "life": 0.3, "max": 0.3, "col": red,
                                   "col2": (255, 200, 120), "g": 0, "size": 2, "shape": "streak", "drag": 0.8})
        elif pid == "dive":
            self.particles(x, y + 6, 16, (120, 90, 60), (40, 110), (0.5, 0.9), angle=math.pi / 2, spread=2.2,
                           gravity=120, size=3, shape="chunk", col2=(70, 55, 40))
        elif pid == "surface":
            self.particles(x, y, 26, (230, 245, 255), (90, 190), (0.5, 0.9), angle=-math.pi / 2, spread=1.0,
                           gravity=320, size=2)
            self.ring(x, y + 3, red, 50, 0.4, 2, flat=0.3)
        elif pid == "reverse":
            self.particles(x, y, 14, (150, 150, 160), (20, 60), (0.5, 0.8), angle=math.pi / 2, spread=1.4,
                           gravity=80, size=2)
        elif pid in ("twist", "bite"):
            self.particles(x, y, 18, red, (70, 150), (0.3, 0.55), shape="streak", col2=(255, 220, 140))
            self.particles(x, y, 8, (230, 230, 230) if pid == "bite" else (190, 130, 255), (30, 70), (0.6, 0.9),
                           gravity=90, shape="fiber")
        elif pid == "pump":
            for i in range(2):
                self.ring(x, y, red, 38, 0.3, 2, i * 0.1)
        elif pid == "fake":
            self.particles(x, y, 18, (70, 40, 100), (20, 50), (0.6, 1.0), gravity=-20, size=3, col2=(30, 20, 40))
        elif pid in ("chain", "combo"):
            self.ring(x, y, red, 60, 0.45, 3)
            self.particles(x, y, 12, red, (60, 120), (0.3, 0.5), shape="streak")
        self.ring(x, y, red, 44, 0.3, 1)

    def combo(self, x, y, cols: list, perfect: bool = True) -> None:
        """콤보·이중 완파: 단계 색 고리가 차례로 퍼지고 금 입자."""
        for i, c in enumerate(cols or [GOLD]):
            self.ring(x, y, c, 70, 0.5, 3, i * 0.1)
        self.ring(x, y, GOLD, 96, 0.6, 2, len(cols) * 0.1)
        self.particles(x, y, 30, GOLD, (60, 150), (0.5, 0.9), col2=(255, 255, 255))

    def tick(self, x, y, col, small=True) -> None:
        """패턴 진행 중 한 박 성공 (펌핑 박·비틀기 한 바퀴)."""
        self.ring(x, y, col, 22 if small else 34, 0.25, 1)
        self.particles(x, y, 5, col, (20, 50), (0.2, 0.35))

    # ───────────────────────── 틱·그리기 ─────────────────────────
    def update(self, dt: float) -> None:
        for p in self.parts:
            p["x"] += p["vx"] * dt
            p["y"] += p["vy"] * dt
            p["vy"] += p["g"] * dt
            p["vx"] *= p["drag"]
            p["vy"] *= p["drag"] if p["g"] == 0 else 1.0
            p["life"] -= dt
        self.parts = [p for p in self.parts if p["life"] > 0]
        for r in self.rings:
            r["t"] += dt
        self.rings = [r for r in self.rings if r["t"] < r["life"]]
        for s in self.stars:
            s["t"] += dt
        self.stars = [s for s in self.stars if s["t"] < s["life"]]

    def draw(self, canvas) -> None:
        if not (self.parts or self.rings or self.stars):
            return
        from src.ui.layers import layer as _layer
        layer = _layer(canvas, "pattern_vfx")
        for r in self.rings:
            if r["t"] < 0:
                continue
            k = r["t"] / r["life"]
            rad = r["r0"] + (r["r1"] - r["r0"]) * (1 - (1 - k) ** 2)
            a = int(255 * (1 - k))
            rect = pygame.Rect(0, 0, int(rad * 2), max(2, int(rad * 2 * r["flat"])))
            rect.center = (int(r["x"]), int(r["y"]))
            pygame.draw.ellipse(layer, (*r["col"], a), rect, max(1, int(r["w"] * (1.4 - k))))
        for p in self.parts:
            k = 1 - p["life"] / p["max"]
            col = lerp_color(p["col"], p["col2"], k)
            a = int(255 * clamp(p["life"] / p["max"] * 1.6, 0, 1))
            x, y, s = int(p["x"]), int(p["y"]), p["size"]
            shape = p["shape"]
            if shape == "streak":
                ln = clamp(math.hypot(p["vx"], p["vy"]) * 0.05, 2, 9)
                d = math.atan2(p["vy"], p["vx"])
                pygame.draw.line(layer, (*col, a), (x, y), (x - math.cos(d) * ln, y - math.sin(d) * ln), 1)
            elif shape == "chunk":
                layer.fill((*col, a), (x - 1, y - 1, s, s))
            elif shape == "fiber":
                pygame.draw.line(layer, (*col, a), (x - 3, y - 1), (x + 3, y + 1), 1)
            elif shape == "note":
                layer.fill((*col, a), (x, y, 2, 2))
                layer.fill((*col, a), (x + 1, y - 5, 1, 5))
            else:
                layer.fill((*col, a), (x, y, s if k < 0.6 else 1, s if k < 0.6 else 1))
        for s in self.stars:
            if s["t"] < 0:
                continue
            k = s["t"] / s["life"]
            sz = s["size"] * (0.4 + 0.6 * math.sin(min(1.0, k * 1.6) * math.pi / 2)) * (1 - k * 0.5)
            a = int(255 * (1 - k))
            x, y = int(s["x"]), int(s["y"])
            pygame.draw.line(layer, (*s["col"], a), (x - sz, y), (x + sz, y), 2)
            pygame.draw.line(layer, (*s["col"], a), (x, y - sz), (x, y + sz), 2)
            d = sz * 0.45
            pygame.draw.line(layer, (*s["col"], a // 2), (x - d, y - d), (x + d, y + d), 1)
            pygame.draw.line(layer, (*s["col"], a // 2), (x - d, y + d), (x + d, y - d), 1)
        canvas.blit(layer, (0, 0))
