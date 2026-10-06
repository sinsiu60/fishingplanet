"""낚시터별 · 행동 반응 · 밤 디테일 (DETAILS.md A-3 · A-4 · A-5, DESIGN.md 45장 DT3). 수치는 data/details/map_details.json.

그리는 자리 (FishingScene.draw):
  draw_world   하늘 · 물 띠 바로 뒤 (물고기 그림자보다 먼저): 화산 아지랑이 · 계곡 물안개
  apply_tilt   먼바다 배 기울어짐 — 수면 · 그림자 · 물결까지 그린 뒤, 줄 · 찌 · 전경 · 낚싯대보다 먼저 (배와 나는 같이 기울고 바깥이 기운다)
  draw_fg      전경 뒤 · 낚싯대 앞: 방파제 물보라 · 은빛 반짝임 · 수정 반짝임 · 동굴 물방울 · 구름 조각 · 재 · 빛 입자 · 반딧불
  draw_screen  화면 날씨 다음: 계곡 위에서 떨어지는 물방울
공통 규칙: 파이팅 중엔 신호 보호 영역 안은 그리지 않고 나머지는 60% (점은 60%만 그림, 덩어리는 투명도). 화질 상한 [높음, 중간, 낮음].
전경(테트라포드 · 수정 · 뿌리 · 갈대)에 붙는 효과는 전경 그림과 같은 480×270 좌표.
"""
import math
import random

import pygame

from src.core.config import load_json
from src.core.mathutil import clamp, lerp, lerp_color
from src.render.screen_weather import q_index, q_val


def cfg() -> dict:
    return load_json("details/map_details.json")


_SPR: dict = {}


def _blob(w: int, h: int, col, a: int, seed: int) -> pygame.Surface:
    key = (w, h, col, a, seed)
    s = _SPR.get(key)
    if s is None:
        r = random.Random(seed)
        s = pygame.Surface((w, h), pygame.SRCALPHA)
        for _ in range(5):
            ew, eh = r.uniform(0.45, 0.8) * w, r.uniform(0.5, 0.9) * h
            pygame.draw.ellipse(s, (*col, a), (r.uniform(0, w - ew), r.uniform(0, h - eh), ew, eh))
        _SPR[key] = s
    return s


class MapFx:
    def __init__(self, w: int, h: int, rnd=None):
        self.w, self.h = w, h
        self.rnd = rnd or random.Random()
        self.spot = None
        self.t = 0.0
        self.timers: dict = {}
        self.spray: list[list] = []     # [x, y, vx, vy, life, max]   방파제 · 뱃전 물보라
        self.parts: list[list] = []     # [x, y, vx, vy, age, life, kind]   재 · 빛 입자 · 구름 조각
        self.drips: list[list] = []     # [x, y, vy, target_y, wx, wz]   동굴 천장 물방울
        self.top_drips: list[list] = [] # [x, y, vy]   계곡 위에서 떨어지는 물방울
        self.sparks: list[list] = []    # [x, y, age, life]   은빛 · 수정 반짝임
        self.flies: list[list] = []     # [x, y, vx, vy, phase]   반딧불
        self.tilt = 0.0                 # 지금 기울기 (도)
        self.haze = None                # 아지랑이 가로줄 표 [프레임][줄]
        self.fighting = False
        self.protect = None
        self.ctx: dict = {}

    def _timer(self, key: str, rng) -> bool:
        t = self.timers.get(key)
        if t is None:
            self.timers[key] = self.rnd.uniform(rng[0] * 0.3, rng[1])
            return False
        t -= self._dt
        if t <= 0:
            self.timers[key] = self.rnd.uniform(*rng)
            return True
        self.timers[key] = t
        return False

    # ── 갱신 ──
    def update(self, dt: float, ctx: dict) -> None:
        """ctx: spot · season · period · weather · fighting · reduce · horizon · bobber(화면 좌표 | None) · cam · ripples · bubbles ·
        droplets · sfx · screen(ScreenWeather) · played(이번 프레임 환경음 조각) · wind(-1~1) · t."""
        C = cfg()
        r = self.rnd
        self._dt = dt
        self.ctx = ctx
        self.t += dt
        spot = ctx["spot"]
        if spot != self.spot:
            self.spot = spot
            self.timers.clear()
            self.spray.clear(); self.parts.clear(); self.drips.clear(); self.top_drips.clear(); self.sparks.clear()
        self.fighting = ctx["fighting"]
        sw = ctx["screen"]
        self.protect = sw.protect
        w, h, hz = self.w, self.h, ctx["horizon"]

        # 방파제: 환경음 '파도 부서짐' 조각과 같은 순간 물보라, 10%는 화면에 몇 방울
        if spot == "breakwater":
            b = C["breakwater"]
            if "amb_wave_crash" in ctx["played"]:
                (x0, x1), (y0, y1) = b["origin"]
                ox, oy = r.uniform(x0, x1), r.uniform(y0, y1)
                for _ in range(b["spray"]):
                    life = r.uniform(0.6, 1.1)
                    self.spray.append([ox + r.uniform(-10, 10), oy, r.uniform(-30, 45), r.uniform(-120, -55), life, life])
                if r.random() < b["screen_chance"]:
                    sw.add_drops(r.randint(*b["screen_drops"]), (0, h * 0.45, w * 0.45, h * 0.9))
        # 먼바다: 수평선 ±2도 (주기 6초), 가끔 뱃전 물보라
        self.tilt = 0.0
        if spot == "offshore":
            o = C["offshore"]
            if not ctx["reduce"]:
                self.tilt = o["tilt_deg"] * math.sin(math.tau * self.t / o["period_sec"])
            if self._timer("boat_spray", o["spray_every_sec"]):
                side = r.choice((0.12, 0.88))
                ox = w * side + r.uniform(-30, 30)
                for _ in range(o["spray"]):
                    life = r.uniform(0.45, 0.8)
                    self.spray.append([ox + r.uniform(-8, 8), h - 26, r.uniform(-25, 25), r.uniform(-110, -60), life, life])
        # 심해: 찌 주변 작은 기포
        if spot == "deep" and ctx["bobber"] is not None and self._timer("bubble", C["deep"]["every_sec"]):
            bx, by = ctx["bobber"]
            for _ in range(r.randint(*C["deep"]["count"])):
                ctx["bubbles"].spawn(bx, by + 2, 5)
        # 계곡: 위에서 가끔 물방울
        if spot == "valley" and self._timer("drip", C["valley"]["drip_every_sec"]):
            self.top_drips.append([r.uniform(20, w - 20), -2.0, r.uniform(20, 40)])
        # 은빛 갈대 습지: 갈대 사이 은빛 반짝임
        if spot == "marsh":
            want = q_val(C["marsh"]["count"])
            while len(self.sparks) < want:
                self.sparks.append([r.uniform(0, 90), r.uniform(h - 64, h - 6), 0.0, r.uniform(0.25, 0.7)])
        # 수정 동굴: 천장 물방울 → 수면 파문 · 수정 반짝
        if spot == "crystal_cave":
            cc = C["crystal_cave"]
            if self._timer("drip", cc["drip_every_sec"]):
                cam = ctx["cam"]
                ang = r.uniform(-0.45, 0.45) + cam.yaw
                dist = r.uniform(4, 16)
                wx, wz = math.sin(ang) * dist, math.cos(ang) * dist
                p = cam.project(wx, wz)
                if p is not None:
                    self.drips.append([p[0], -2.0, 0.0, p[1], wx, wz])
            if self._timer("sparkle", cc["sparkle_every_sec"]):
                tips = [(14, 46, -0.2), (36, 64, 0.1), (60, 38, 0.3), (82, 26, 0.5), (452, 40, -0.4), (470, 58, -0.15)]
                x, hh, lean = r.choice(tips)
                base = 262 if x < 240 else 270
                self.sparks.append([x + lean * hh * r.uniform(0.3, 1.0), base - hh * r.uniform(0.3, 0.95), 0.0, 0.5])
        # 부유섬 폭포: 화면 옆 구름 조각 아래 → 위
        if spot == "sky_falls":
            sk = C["sky_falls"]
            cap = q_val(sk["cap"])
            if cap and self._timer("cloud", sk["every_sec"]) and sum(1 for p in self.parts if p[6] == "cloud") < cap:
                x = r.uniform(-8, 30) if r.random() < 0.5 else r.uniform(w - 50, w - 10)
                sp = r.uniform(*sk["speed_px_s"])
                self.parts.append([x, h + 14, r.uniform(-2, 2), -sp, 0.0, (h + 40) / sp, "cloud"])
        # 화산: 재 날림 + 아지랑이 표 (한 번만)
        if spot == "volcano":
            v = C["volcano"]
            cap = q_val(v["ash_cap"])
            if sum(1 for p in self.parts if p[6] == "ash") < cap and r.random() < v["ash_rate"] * dt:
                self.parts.append([r.uniform(-20, w + 20), -3, ctx["wind"] * 14 + r.uniform(-4, 4), r.uniform(10, 20), 0.0,
                                   r.uniform(8, 14), "ash"])
            if self.haze is None:
                rows = int((h - hz) * v["haze_rows_frac"]) + 1
                F = v["haze_frames"]
                rr = random.Random(5)
                ph = [rr.uniform(0, math.tau) for _ in range(rows)]
                self.haze = [[int(round(v["haze_amp_px"] * (1 - i / rows) * math.sin(math.tau * f / F + ph[i] * 0.35 + i * 0.7)))
                              for i in range(rows)] for f in range(F)]
        # 극광 빙해: 서리 상시 8px (소리는 환경음 조각 간격 10~20초)
        sw.frost_base = C["ice_sea"]["frost_px"] if spot == "ice_sea" else 0.0
        # 세계수 뿌리 샘: 빛 입자
        if spot == "world_tree":
            wt = C["world_tree"]
            if sum(1 for p in self.parts if p[6] == "light") < q_val(wt["cap"]) and r.random() < wt["rate"] * dt:
                x = r.uniform(10, 120) if r.random() < 0.5 else r.uniform(380, 470)
                self.parts.append([x, r.uniform(232, 262), r.uniform(-3, 3), -r.uniform(7, 13), 0.0, r.uniform(3.5, 6.0), "light"])
        # 반딧불: 여름 밤, 저수지 · 계곡 · 습지
        ff = C["fireflies"]
        on = ctx["season"] == "summer" and ctx["period"] == "night" and spot in ff["spots"] and ctx["weather"] in ("clear", "fog")
        n = min(q_val(ff["cap"]), int(lerp(ff["count"][0], ff["count"][1], 0.5 + 0.5 * math.sin(self.t * 0.05)))) if on else 0
        while len(self.flies) < n:
            self.flies.append([r.uniform(0, w), r.uniform(hz + 6, h - 24), r.uniform(-6, 6), r.uniform(-3, 3), r.uniform(0, 6.3)])
        del self.flies[n:]
        for f in self.flies:
            f[4] += dt
            f[2] += math.sin(f[4] * 1.1) * 6 * dt
            f[3] += math.cos(f[4] * 0.9) * 4 * dt
            f[2] = clamp(f[2] * 0.99, -8, 8)
            f[3] = clamp(f[3] * 0.99, -5, 5)
            f[0] = (f[0] + f[2] * dt) % w
            f[1] = clamp(f[1] + f[3] * dt, hz - 30, h - 10)

        # 움직임
        for s in self.spray:
            s[0] += s[2] * dt
            s[1] += s[3] * dt
            s[3] += 240 * dt
            s[4] -= dt
        self.spray = [s for s in self.spray if s[4] > 0]
        for p in self.parts:
            p[4] += dt
            p[0] += p[2] * dt + (math.sin(p[4] * 1.7 + p[5]) * 6 * dt if p[6] == "ash" else 0)
            p[1] += p[3] * dt
        self.parts = [p for p in self.parts if p[4] < p[5] and -30 < p[1] < h + 30]
        keep = []
        for d in self.drips:
            d[2] += 300 * dt
            d[1] += d[2] * dt
            if d[1] >= d[3]:
                ctx["ripples"].spawn(d[4], d[5], size=0.5, life=1.4, rings=2)
                if ctx.get("sfx") is not None:
                    ctx["sfx"].play("amb_drop", 0.25)
            else:
                keep.append(d)
        self.drips = keep
        for d in self.top_drips:
            d[2] += 260 * dt
            d[1] += d[2] * dt
        self.top_drips = [d for d in self.top_drips if d[1] < h + 6]
        for s in self.sparks:
            s[2] += dt
        self.sparks = [s for s in self.sparks if s[2] < s[3]]

    # ── 기울기 (먼바다) ──
    def tilt_dy(self, x: float) -> int:
        """배 기울기에 따른 그 열의 세로 밀림(px). 줄 · 찌 위치를 수면과 맞출 때."""
        if abs(self.tilt) < 0.01:
            return 0
        return int(round((x - self.w / 2) * math.tan(math.radians(self.tilt))))

    def apply_tilt(self, canvas, pal) -> None:
        """수평선 기울기: 회전 대신 같은 밀림 값의 열 묶음을 제자리에서 세로로 민다 (최대 ±8px → 묶음 17개 이하, 폰도 가벼움)."""
        if abs(self.tilt) < 0.01:
            return
        w, h = self.w, self.h
        top, bot = pal["sky_top"], pal["water_bottom"]
        tan = math.tan(math.radians(self.tilt))
        cx = w / 2
        kmax = int(abs(cx * tan)) + 1
        # 밀림 값이 바뀌는 경계: (x - cx)·tan = k + 0.5 → 열마다 계산하지 않고 경계만
        cuts = sorted({0, w} | {int(math.ceil(cx + (k + 0.5) / tan)) for k in range(-kmax - 1, kmax + 1)
                                 if 0 < cx + (k + 0.5) / tan < w})
        for x0, x1 in zip(cuts, cuts[1:]):
            if x1 <= x0:
                continue
            dy = self.tilt_dy((x0 + x1 - 1) / 2)
            if dy:
                col = canvas.subsurface((x0, 0, x1 - x0, h))
                col.scroll(0, dy)
                if dy > 0:
                    col.fill(top, (0, 0, x1 - x0, dy))
                else:
                    col.fill(bot, (0, h + dy, x1 - x0, -dy))

    # ── 그리기 ──
    def _skip(self, x, y, i: int = 0, pad: int = 2) -> bool:
        """파이팅 중: 보호 영역 안 · 점의 40% 는 그리지 않음 (= 투명도 60%)."""
        if not self.fighting:
            return False
        if i % 5 in (1, 3):
            return True
        return self.protect is not None and self.protect.hit_pt(x, y, pad)

    def draw_world(self, canvas, pal) -> None:
        C = cfg()
        hz = self.ctx.get("horizon", 120)
        if self.spot == "volcano" and self.haze is not None and q_val(C["volcano"]["haze"]):
            f = int(self.t * C["volcano"]["haze_fps"]) % len(self.haze)
            row = self.haze[f]
            w = self.w
            for i, dx in enumerate(row):
                y = hz + i
                if dx and y < self.h:
                    canvas.subsurface((0, y, w, 1)).scroll(dx, 0)
        if self.spot == "valley":
            n = q_val(C["valley"]["mist"])
            a = C["valley"]["mist_alpha"]
            col = lerp_color(pal["sky_bottom"], (232, 238, 240), 0.6)
            for i in range(n):
                bw, bh = 150, 22
                span = self.w + bw
                x = (self.t * (4 + 2 * i) + i * span / max(1, n)) % span - bw
                y = hz + 6 + i * 13
                s = _blob(bw, bh, col, a, 40 + i)
                if self.fighting:
                    if self.protect is not None and self.protect.hit(pygame.Rect(int(x), y, bw, bh)):
                        continue
                    s.set_alpha(153)
                else:
                    s.set_alpha(255)
                canvas.blit(s, (int(x), y))

    def draw_fg(self, canvas, pal) -> None:
        wl = lerp_color(pal["wave_light"], (255, 255, 255), 0.7)
        for i, s in enumerate(self.spray):
            if self._skip(s[0], s[1], i):
                continue
            k = s[4] / s[5]
            canvas.fill(wl if k > 0.4 else pal["wave_light"], (int(s[0]), int(s[1]), 2 if k > 0.6 else 1, 2 if k > 0.6 else 1))
        for i, p in enumerate(self.parts):
            x, y, kind = p[0], p[1], p[6]
            if kind == "cloud":
                s = _blob(26, 12, (250, 252, 255), 150, 7 + i % 3)
                if self.fighting and self.protect is not None and self.protect.hit(pygame.Rect(int(x), int(y), 26, 12)):
                    continue
                s.set_alpha(153 if self.fighting else 255)
                canvas.blit(s, (int(x), int(y)))
                continue
            if self._skip(x, y, i):
                continue
            if kind == "ash":
                canvas.fill((96, 92, 92) if i % 3 else (150, 140, 136), (int(x), int(y), 1 + (i % 4 == 0), 1))
            elif kind == "light":
                k = math.sin(math.pi * p[4] / p[5])
                tw = 0.6 + 0.4 * math.sin(p[4] * 5 + i)
                c = lerp_color((150, 255, 190), (255, 255, 220), tw)
                if k > 0.15:
                    canvas.fill(lerp_color(pal["water_bottom"], c, min(1.0, k * 1.4)), (int(x), int(y), 1 + (k > 0.6), 1 + (k > 0.6)))
        for i, s in enumerate(self.sparks):
            k = math.sin(math.pi * s[2] / s[3])
            if k < 0.3 or self._skip(s[0], s[1], i):
                continue
            x, y = int(s[0]), int(s[1])
            col = (236, 242, 250) if self.spot == "marsh" else (230, 245, 255)
            canvas.fill(col, (x, y, 1, 1))
            if k > 0.75:
                canvas.fill(col, (x - 1, y, 3, 1))
                canvas.fill(col, (x, y - 1, 1, 3))
        for d in self.drips:
            if self._skip(d[0], d[1]):
                continue
            canvas.fill((200, 225, 255), (int(d[0]), int(d[1]), 1, 2))
        col = tuple(cfg()["fireflies"]["color"])
        for i, f in enumerate(self.flies):
            glow = 0.5 + 0.5 * math.sin(self.t * 2.0 + f[4] * 3)
            if glow < 0.3 or self._skip(f[0], f[1], i):
                continue
            x, y = int(f[0]), int(f[1])
            canvas.fill(lerp_color(pal["water_bottom"], col, glow), (x, y, 1, 1))
            if glow > 0.8:
                halo = lerp_color(pal["water_bottom"], col, 0.35)
                canvas.fill(halo, (x - 1, y, 1, 1)); canvas.fill(halo, (x + 1, y, 1, 1))
                canvas.fill(halo, (x, y - 1, 1, 1)); canvas.fill(halo, (x, y + 1, 1, 1))

    def draw_screen(self, canvas) -> None:
        for d in self.top_drips:
            if self._skip(d[0], d[1], pad=3):
                continue
            canvas.fill((214, 232, 250), (int(d[0]), int(d[1]), 1, 3))
            canvas.fill((255, 255, 255), (int(d[0]), int(d[1]) + 2, 1, 1))
