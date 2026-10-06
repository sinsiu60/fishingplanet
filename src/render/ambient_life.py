"""살아 있는 주변 (DETAILS.md E, DESIGN.md 45장 DT8). 수치는 data/details/ambient_life.json.

잠자리(낚싯대 끝에 앉음) · 물새(오리 · 백로) · 먼 점프 · 지나가는 배(물결 → 찌 그림만 좌우) · 개구리(감기 시작하면 뚝) · 먼 낚시꾼.
모두 그림 · 소리만: 입질 · 판정 · 확률 · 보상과 무관 (bite.py 는 건드리지 않고, 찌는 그릴 때만 옆으로 민다).
"""
import math
import random

import pygame

from src.core.config import load_json
from src.core.mathutil import clamp, lerp, lerp_color


def cfg() -> dict:
    return load_json("details/ambient_life.json")


class AmbientLife:
    def __init__(self, rnd=None):
        self.rnd = rnd or random.Random()
        self.spot = None
        self.timers: dict = {}
        self.fly = None        # 낚싯대 끝 잠자리 {"state": wait|in|perch|out, "t", "from"}
        self.bird = None       # {"kind", "x", "z", "state": in|stay|out, "t", "stay"}
        self.jumps: list[dict] = []
        self.boat = None       # {"x", "dir", "passed", "wake_t"}
        self.wake = None       # {"t"} 찌 좌우 흔들림
        self.frog_ch = None
        self.frog_quiet = 0.0
        self.was_reeling = False
        self.angler = {"lift": -1.0}
        self.ctx: dict = {}
        self._dt = 0.0

    def _timer(self, key: str, rng) -> bool:
        t = self.timers.get(key)
        if t is None:
            self.timers[key] = self.rnd.uniform(rng[0] * 0.25, rng[1])
            return False
        t -= self._dt
        if t <= 0:
            self.timers[key] = self.rnd.uniform(*rng)
            return True
        self.timers[key] = t
        return False

    # ── 장면이 알려 주는 사건 ──
    def on_cast_landed(self, season: str, period: str, spot: str) -> None:
        """캐스팅마다 15%: 잠자리가 날아와 낚싯대 끝에 앉음 (조건이 맞을 때)."""
        c = cfg()["dragonfly"]
        self.fly = None
        if season in c["seasons"] and period in c["periods"] and spot in c["spots"] and self.rnd.random() < c["chance"]:
            self.fly = {"state": "wait", "t": self.rnd.uniform(*c["land_delay_sec"]), "from": self.rnd.choice((-1, 1))}

    def scare_fly(self) -> None:
        """입질이 오거나 감기 시작하면 날아감."""
        if self.fly is not None and self.fly["state"] in ("in", "perch"):
            self.fly = {"state": "out", "t": 0.0, "from": self.fly["from"], "pos": self.fly.get("pos")}
        elif self.fly is not None and self.fly["state"] == "wait":
            self.fly = None

    # ── 갱신 ──
    def update(self, dt: float, ctx: dict) -> None:
        """ctx: spot · season · period · weather · fighting · reeling · bobber_xz(찌 월드 좌표 | None) · cam · ripples · sfx · tip(낚싯대 끝 화면)."""
        C = cfg()
        r = self.rnd
        self._dt = dt
        self.ctx = ctx
        spot, period, season = ctx["spot"], ctx["period"], ctx["season"]
        if spot != self.spot:
            self.spot = spot
            self.timers.clear()
            self.bird, self.boat, self.wake, self.fly = None, None, None, None
            self.jumps.clear()
        reeling = ctx["reeling"]
        if reeling and not self.was_reeling:
            self.scare_fly()
            if self.frog_ch is not None:   # 개구리: 감기 시작하면 뚝, 10초 뒤 다시
                self.frog_ch.stop()
                self.frog_ch = None
            self.frog_quiet = C["frog"]["quiet_sec"]
        self.was_reeling = reeling

        # 잠자리
        f = self.fly
        if f is not None:
            f["t"] = f["t"] - dt if f["state"] == "wait" else f["t"] + dt
            if f["state"] == "wait" and f["t"] <= 0:
                f.update(state="in", t=0.0)
            elif f["state"] == "in" and f["t"] >= 1.2:
                f.update(state="perch", t=0.0)
            elif f["state"] == "out" and f["t"] >= 1.2:
                self.fly = None
            if ctx.get("bobber_xz") is None and self.fly is not None and self.fly["state"] != "out":
                self.scare_fly()   # 찌를 걷었다

        # 물새
        bc = C["waterbird"]
        cam = ctx["cam"]
        if self.bird is None:
            if period in bc["periods"] and spot in bc["spots"] and ctx["weather"] != "storm" and self._timer("bird", bc["every_sec"]):
                ang = cam.yaw + r.uniform(-0.45, 0.45)
                dist = r.uniform(*bc["dist_m"])
                self.bird = {"kind": r.choice(("duck", "heron")), "x": math.sin(ang) * dist, "z": math.cos(ang) * dist,
                             "state": "in", "t": 0.0, "stay": r.uniform(*bc["stay_sec"]), "dir": r.choice((-1, 1))}
        else:
            b = self.bird
            b["t"] += dt
            bxz = ctx.get("bobber_xz")
            near = bxz is not None and math.hypot(bxz[0] - b["x"], bxz[1] - b["z"]) < bc["near_m"]
            if b["state"] == "in" and b["t"] >= 1.6:
                b.update(state="stay", t=0.0)
            elif b["state"] == "stay" and (b["t"] >= b["stay"] or near or period not in bc["periods"]):
                b.update(state="out", t=0.0)
            elif b["state"] == "out" and b["t"] >= 2.0:
                self.bird = None

        # 먼 점프
        jc = C["far_jump"]
        if spot not in jc["exclude"] and not ctx["fighting"] and self._timer("jump", jc["every_sec"]):
            ang = cam.yaw + r.uniform(-0.5, 0.5)
            dist = r.uniform(*jc["dist_m"])
            x, z = math.sin(ang) * dist, math.cos(ang) * dist
            self.jumps.append({"x": x, "z": z, "t": 0.0, "dx": r.uniform(-0.8, 0.8)})
            ctx["ripples"].spawn(x, z, size=0.35, life=1.0)
        for j in self.jumps:
            j["t"] += dt
            if j["t"] >= 0.55 and not j.get("land"):
                j["land"] = True
                ctx["ripples"].spawn(j["x"] + j["dx"], j["z"], size=0.45, life=1.2, rings=2)
        self.jumps = [j for j in self.jumps if j["t"] < 0.6]

        # 지나가는 배
        oc = C["boat"]
        w = cam.width
        if self.boat is None and spot in oc["spots"] and self._timer("boat", oc["every_sec"]):
            d = r.choice((-1, 1))
            self.boat = {"x": -30.0 if d > 0 else w + 30.0, "dir": d, "passed": False, "wake_t": None}
        if self.boat is not None:
            b = self.boat
            b["x"] += b["dir"] * oc["speed_px_s"] * dt
            if not b["passed"] and ((b["dir"] > 0 and b["x"] > w * 0.5) or (b["dir"] < 0 and b["x"] < w * 0.5)):
                b["passed"] = True
                b["wake_t"] = oc["wake_delay_sec"]
            if b["wake_t"] is not None:
                b["wake_t"] -= dt
                if b["wake_t"] <= 0:
                    self.wake = {"t": 0.0}
                    b["wake_t"] = None
            if b["x"] < -60 or b["x"] > w + 60:
                if b["wake_t"] is None:
                    self.boat = None
        if self.wake is not None:
            self.wake["t"] += dt
            if self.wake["t"] >= oc["wake_sec"]:
                self.wake = None

        # 개구리
        fc = C["frog"]
        self.frog_quiet = max(0.0, self.frog_quiet - dt)
        if season in fc["seasons"] and period in fc["periods"] and spot in fc["spots"] and not reeling and self.frog_quiet <= 0:
            if self._timer("frog", fc["every_sec"]) and ctx.get("sfx") is not None:
                self.frog_ch = ctx["sfx"].play("amb_frog", fc["vol"] * r.uniform(0.7, 1.0), pan=r.uniform(-0.6, 0.6))

        # 먼 낚시꾼
        ac = C["angler"]
        if spot in ac["spots"]:
            if self.angler["lift"] >= 0:
                self.angler["lift"] += dt
                if self.angler["lift"] >= ac["lift_sec"]:
                    self.angler["lift"] = -1.0
            elif self._timer("angler", ac["every_sec"]):
                self.angler["lift"] = 0.0

    # ── 찌 그림만 옆으로 (판정 무관) ──
    def wake_dx(self) -> float:
        if self.wake is None:
            return 0.0
        c = cfg()["boat"]
        u = self.wake["t"] / c["wake_sec"]
        return math.sin(self.wake["t"] * 7.0) * c["wake_px"] * (1 - u)

    # ── 그리기 ──
    def draw_world(self, canvas, pal, t: float) -> None:
        """수면 위 (찌 · 줄보다 먼저): 먼 낚시꾼 · 배 · 물새 · 먼 점프."""
        cam = self.ctx.get("cam")
        if cam is None:
            return
        hz = cam.horizon
        far = lerp_color(pal["mountain_near"], (12, 14, 20), 0.45)
        # 먼 낚시꾼 (건너편 물가 실루엣)
        ac = cfg()["angler"]
        if self.spot in ac["spots"]:
            x = cam.angle_to_x(math.radians(ac["angle_deg"][self.spot]))
            if x is not None and -10 < x < cam.width + 10:
                x, y = int(x), hz - 1
                canvas.fill(far, (x, y - 6, 2, 6))         # 몸
                canvas.fill(far, (x, y - 8, 2, 2))         # 머리
                lift = self.angler["lift"]
                k = math.sin(math.pi * clamp(lift / ac["lift_sec"], 0, 1)) if lift >= 0 else 0.0
                tip = (x + 9 - 4 * k, y - 9 - 6 * k)
                pygame.draw.line(canvas, far, (x + 1, y - 5), tip, 1)
        # 배
        if self.boat is not None:
            bx, y = int(self.boat["x"]), hz - 1
            pygame.draw.polygon(canvas, far, [(bx - 8, y - 2), (bx + 8, y - 2), (bx + 6, y + 1), (bx - 6, y + 1)])
            canvas.fill(far, (bx - 2, y - 6, 5, 4))
            canvas.fill(lerp_color(far, (255, 230, 160), 0.4), (bx, y - 5, 1, 1))
        # 물새
        b = self.bird
        if b is not None:
            p = cam.project(b["x"], b["z"])
            if p is not None:
                s = max(0.6, p[2] / 12)
                x, y = p[0], p[1]
                if b["state"] == "in":
                    u = clamp(b["t"] / 1.6, 0, 1)
                    x += (1 - u) * -b["dir"] * 40 * s
                    y -= (1 - u) ** 1.5 * 40 * s
                elif b["state"] == "out":
                    u = clamp(b["t"] / 2.0, 0, 1)
                    x += u * b["dir"] * 60 * s
                    y -= u ** 0.8 * 50 * s
                flying = b["state"] != "stay"
                self._bird(canvas, pal, b["kind"], x, y + math.sin(t * 1.5) * 0.5 * (not flying), s, flying, t)
        # 먼 점프
        for j in self.jumps:
            u = clamp(j["t"] / 0.55, 0, 1)
            p = cam.project(j["x"] + j["dx"] * u, j["z"], 0.6 * math.sin(math.pi * u))
            if p is not None:
                col = lerp_color(pal["wave_light"], (230, 236, 240), 0.5)
                canvas.fill(col, (int(p[0]) - 1, int(p[1]), 3, 1))
                canvas.fill(col, (int(p[0]), int(p[1]) - 1, 1, 1))

    def _bird(self, canvas, pal, kind: str, x: float, y: float, s: float, flying: bool, t: float) -> None:
        x, y = int(x), int(y)
        if kind == "heron":
            col = lerp_color(pal["sky_bottom"], (238, 240, 242), 0.75)
            if flying:
                flap = int(3 * s * math.sin(t * 7))
                pygame.draw.lines(canvas, col, False, [(x - int(6 * s), y - flap), (x, y), (x + int(6 * s), y - flap)], 1)
                canvas.fill(col, (x - 1, y, 3, 1))
            else:
                canvas.fill(col, (x - 1, y - int(4 * s), 3, int(3 * s) + 1))    # 몸
                canvas.fill(col, (x + 1, y - int(8 * s), 1, int(4 * s)))        # 긴 목
                canvas.fill(col, (x + 1, y - int(8 * s), 2, 1))                 # 부리
                canvas.fill(lerp_color(col, (40, 40, 40), 0.6), (x, y - 1, 1, 2))
        else:
            col = lerp_color(pal["mountain_near"], (60, 50, 40), 0.5)
            head = lerp_color(col, (40, 90, 60), 0.5)
            if flying:
                flap = int(2 * s * math.sin(t * 10))
                pygame.draw.lines(canvas, col, False, [(x - int(4 * s), y - flap), (x, y), (x + int(4 * s), y - flap)], 1)
            else:
                canvas.fill(col, (x - 2, y - 2, 5, 2))                          # 몸 (물 위)
                canvas.fill(head, (x + 2, y - 4, 2, 2))                         # 머리

    def draw_fly(self, canvas, tip, t: float) -> None:
        """잠자리: 날아와 낚싯대 끝에 앉음 → 날개 접고 쉼 → 날아감 (낚싯대보다 나중에 그림)."""
        f = self.fly
        if f is None or f["state"] == "wait":
            return
        tx, ty = tip[0], tip[1] - 2
        if f["state"] == "in":
            u = clamp(f["t"] / 1.2, 0, 1)
            sx = tx + f["from"] * 120 * (1 - u) + math.sin(f["t"] * 9) * 6 * (1 - u)
            sy = ty - 50 * (1 - u) ** 1.3
        elif f["state"] == "out":
            u = clamp(f["t"] / 1.2, 0, 1)
            sx = tx - f["from"] * 140 * u
            sy = ty - 70 * u
        else:
            sx, sy = tx, ty
        f["pos"] = (sx, sy)
        body = (40, 80, 170)
        wing = (220, 235, 250)
        x, y = int(sx), int(sy)
        canvas.fill(body, (x - 4, y, 7, 1))           # 긴 꼬리 몸
        canvas.fill((30, 50, 110), (x + 2, y - 1, 2, 2))   # 머리 · 가슴
        if f["state"] == "perch":
            canvas.fill(wing, (x - 1, y - 1, 3, 1))   # 날개 접고 쉼
        elif int(t * 30) % 2:
            canvas.fill(wing, (x - 1, y - 2, 1, 2))
            canvas.fill(wing, (x + 1, y - 2, 1, 2))
        else:
            canvas.fill(wing, (x - 2, y + 1, 2, 1))
            canvas.fill(wing, (x + 1, y + 1, 2, 1))
