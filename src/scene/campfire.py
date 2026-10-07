"""모닥불 타임랩스 (TIME_REST.md 🅲 · 🅳, DESIGN.md 48장): 골라 쉬기 → 2.5초 동안 그 낚시터 배경에서 시계를 목표 시각까지 돌림.

  0.0~0.3  화면 아래쪽부터 어둑하게 (검정 30%) + 모닥불 나타남
  0.3~2.2  게임 시계를 easeInOut 으로 지금 → 목표 (하늘 · 해/달 · 별 · 조명 · 날씨 그림이 예보표대로)
  2.2~2.5  어둑함 걷힘, 모닥불 사라짐 → 도착 토스트 (+ 모닥불의 작은 일 한 줄)
그 동안 FishingScene.update 를 부르지 않음 → 물고기 · 입질 · 수면 징후 · 소리 이벤트(천둥 등) 멈춤, 그림(비 · 안개 · 번개 빛)만 갱신.
첫 쉬기(세이브 rest_seen 없음)는 끝까지, 그 뒤엔 0.4초 이후 탭 · 클릭 · 아무 키 = 남은 시간을 0.4초에 몰아서 끝.
화면 효과 줄이기 = 0.3초 어두워짐 → 시계 한 번에 → 0.3초 밝아짐 (모닥불 · 소리는 그대로). 모바일 · 저화질 = 불티 끔.
"""
import math
import random

import pygame

from src.core.config import game_config, load_json
from src.platform.detect import IS_MOBILE
from src.core.mathutil import clamp
from src.core.weather import WEATHER_KO
from src.render import campsite
from src.scene.base import Scene
from src.ui.hud import text

LOG = (0x6B, 0x4A, 0x2E)
FLAME = ((0xE8, 0x74, 0x3B), (0xF6, 0xB1, 0x4A), (0xFF, 0xF1, 0xA8))
DIM_IN, DIM_OUT_AT = 0.3, 2.2


def ease(u: float) -> float:
    u = max(0.0, min(1.0, u))
    return u * u * (3 - 2 * u)


def campfire_cfg() -> dict:
    return load_json("campfire.json")


def pick_event(save, fishing, hours: float, rnd=random) -> dict | None:
    """모닥불의 작은 일 (🅳): 조건이 맞는 것 중 표 순서대로 확률을 굴려 처음 걸린 하나."""
    from src.core.game_clock import PERIODS
    from src.render import village_life as vl
    ws = fishing.weather_sys
    now = ws.abs_time(fishing.clock.day, fishing.clock.hour)
    # 지나는 시간의 시각들 (30분 간격): 밤 여부 · 날씨
    samples = []
    t = now
    while t <= now + hours + 1e-6:
        h = t % 24
        pid = PERIODS[-1][1]
        for start, p, _ in PERIODS:
            if h >= start:
                pid = p
        samples.append((pid, ws.at_time(t)))
        t += 0.5
    passes_night = any(p == "night" for p, _ in samples)
    season = getattr(fishing, "season", None)
    spot = fishing.spot_id
    for ev in campfire_cfg()["events"]:
        c = ev["cond"]
        ok = True
        if "cat_affection" in c and vl.affection(save) < c["cat_affection"]:
            ok = False
        if "spots" in c and spot not in c["spots"]:
            ok = False
        if c.get("passes_night") and not passes_night:
            ok = False
        if c.get("passes_night_clear") and not any(p == "night" and w == "clear" for p, w in samples):
            ok = False
        if "passes_weather" in c and not any(w in c["passes_weather"] for _, w in samples):
            ok = False
        if "season" in c and season not in c["season"]:
            ok = False
        if "season_or_spots" in c:
            so = c["season_or_spots"]
            if season not in so.get("season", []) and spot not in so.get("spots", []):
                ok = False
        if ok and rnd.random() < ev["chance"]:
            return ev
    return None


class CampfireScene(Scene):
    """낚시 화면 위에 올림. fishing.rest_begin() 은 부르는 쪽(지도)이 이미 함."""

    def __init__(self, game, fishing, hours: float, force_event: str | None = None):
        super().__init__(game)
        self.fishing = fishing
        self.hours = max(0.0, hours)
        tc = game_config()["time"]
        self.total = tc.get("campfire_sec", 2.5)
        self.skip_sec = tc.get("campfire_skip_sec", 0.4)
        self.t = 0.0
        self.applied = 0.0
        self.reduce = bool(game.settings.get("reduce_fx"))
        self.first = not game.save.data.get("rest_seen")
        self.embers_on = not IS_MOBILE and game.settings.get("quality") != "low"
        self.rnd = random.Random()
        self.embers: list[list] = []
        self.skip_to: tuple[float, float] | None = None   # (건너뛴 순간 t, 끝 시각) — 남은 시간을 0.4초에
        self.flick_t = 0.0
        self.flick = [0, 0, 0]
        self.pop_t = 0.6
        self.done = False
        cf = campfire_cfg()
        if force_event:
            self.event = next((e for e in cf["events"] if e["id"] == force_event), None)
        else:
            self.event = pick_event(game.save, fishing, self.hours)
        self.ev_at = cf.get("at_sec", 1.2)
        self.ev_started = False
        self.ev_t = 0.0
        self.ev_data: dict = {}
        fishing.toasts.items.clear()   # 낚시 화면이 멈춰 있으니 남은 토스트가 그대로 얼어 보임
        game.adaptive.suspend(True)   # 배경 음악 멈춤 → 끝나면 그 시간대 음악으로 다시
        game.sfx.loop("room_fire", True, 0.5)

    # ── 진행 ──
    def _progress(self) -> float:
        """0..1 시계 진행 (easeInOut). 줄이기 = 0.3초 어두워진 뒤 한 번에."""
        if self.reduce:
            return 1.0 if self.t >= DIM_IN else 0.0
        span = DIM_OUT_AT - DIM_IN
        return ease((self.t - DIM_IN) / span)

    def _end_time(self) -> float:
        return (2 * DIM_IN + 0.0) if self.reduce else self.total

    def handle_action(self, a) -> None:
        if a.name in ("primary", "confirm", "back") or getattr(a, "any_press", False):
            self._try_skip()

    def handle_event(self, event) -> None:
        if event.type == pygame.KEYDOWN:
            self._try_skip()
            return
        super().handle_event(event)

    def _try_skip(self) -> None:
        if self.first or self.skip_to is not None or self.t < self.skip_sec:
            return
        self.skip_to = (self.t, self.t + self.skip_sec)

    def update(self, dt: float) -> None:
        f = self.fishing
        if self.skip_to is not None:
            # 남은 타임랩스를 skip_sec 에 몰아서: 시간을 그만큼 빨리 흘림
            s0, s1 = self.skip_to
            remain = max(1e-3, self._end_time() - s0)
            dt = dt * remain / max(1e-3, s1 - s0)
        self.t += dt
        # 시계: 목표까지 진행분만큼 _advance_hours (날짜 · 예보표 날씨)
        want = self.hours * self._progress()
        if want - self.applied > 1e-6:
            f._advance_hours(want - self.applied)
            self.applied = want
        f.weather_sys.events.clear()
        self._visuals(dt)
        # 모닥불 흔들림 · 불티 · 탁탁 소리
        self.flick_t += dt
        if self.flick_t >= 0.12:
            self.flick_t = 0.0
            self.flick = [self.rnd.choice((-1, 0, 1)) for _ in range(3)]
        self.pop_t -= dt
        if self.pop_t <= 0 and self.t < self._end_time() - 0.3:
            self.pop_t = 0.6
            self.game.sfx.play(f"room_fire_pop{self.rnd.randrange(3)}", 0.35)
        if self.embers_on:
            if len(self.embers) < 4 and self.rnd.random() < dt * 4:
                self.embers.append([self.rnd.uniform(-5, 5), 0.0, self.rnd.uniform(-4, 4), self.rnd.uniform(14, 24), 0.0])
            for e in self.embers:
                e[0] += e[2] * dt
                e[1] += e[3] * dt
                e[4] += dt
            self.embers = [e for e in self.embers if e[4] < 1.0]
        # 모닥불의 작은 일
        if self.event is not None and not self.ev_started and self.t >= (self.ev_at if not self.reduce else DIM_IN):
            self.ev_started = True
            snd = self.event.get("sound")
            if snd:
                self.game.sfx.play(snd[0], snd[1])
            if self.event["id"] == "meteor":
                w = self.game.screen.canvas.get_width()
                self.ev_data = {"x": self.rnd.uniform(w * 0.3, w * 0.8), "y": self.rnd.uniform(14, 40)}
            elif self.event["id"] in ("fireflies", "snow"):
                n = self.rnd.randint(5, 8)
                self.ev_data = {"pts": [[self.rnd.uniform(-34, 34), self.rnd.uniform(-30, -4), self.rnd.uniform(0, 6.28)]
                                        for _ in range(n)]}
        if self.ev_started:
            self.ev_t += dt
        if self.t >= self._end_time() and not self.done:
            self._finish()

    def _visuals(self, dt: float) -> None:
        """그림만: 비 · 안개 · 번개 빛 (소리 · 천둥 이벤트는 버림)."""
        f = self.fishing
        try:
            f.wind.update(dt, f.weather)
            f.rain.update(dt, f.weather, f.ripples, f.cam)
            f.fog.update(dt, f.weather)
            f.lightning.reduce = True   # 타임랩스 중엔 번쩍임 없이
            f.lightning.update(dt, f.weather, f.cam.horizon, f.cam.width)
            f.lightning.events.clear()
        except Exception:
            pass

    def _finish(self) -> None:
        self.done = True
        g = self.game
        f = self.fishing
        if self.hours - self.applied > 1e-6:
            f._advance_hours(self.hours - self.applied)
            self.applied = self.hours
        g.sfx.loop("room_fire", False)
        g.adaptive.suspend(False)
        g.save.data["rest_seen"] = True
        f.lightning.reduce = bool(g.settings.get("reduce_fx"))
        label = f.rest_end()
        f.toasts.show(f"텐트에서 쉬었다 → {label}", (140, 240, 150), 2.4)
        if self.event is not None:
            seen = g.save.data.setdefault("campfire_seen", [])
            if self.event["id"] not in seen:
                seen.append(self.event["id"])
            f.campfire_line = (self.event["line"], f.t + campfire_cfg().get("line_sec", 2.4))
            from src.save import achievements
            from src.save.quests import cosmetics
            achievements.check(g.save)
            if len(set(seen)) >= len(campfire_cfg()["events"]) and "campfire_friend" not in cosmetics(g.save)["titles"]:
                cosmetics(g.save)["titles"].append("campfire_friend")   # 업적 '모닥불 친구' = 칭호만
            g.save_now()
        if g.scenes.current is self:
            g.scenes.pop()

    # ── 그리기 ──
    def _black(self) -> tuple[bool, float]:
        """(야영지를 그릴지, 검정 덮개 0..1): 0~0.15 낚시 화면 → 검정, 0.15~0.3 검정 → 야영지, 끝도 거꾸로."""
        end = self._end_time()
        half = DIM_IN / 2
        if self.t < DIM_IN:
            return (self.t >= half, self.t / half if self.t < half else 1 - (self.t - half) / half)
        if self.t > end - DIM_IN:
            u = self.t - (end - DIM_IN)
            return (u < half, u / half if u < half else 1 - (u - half) / half)
        return True, 0.0

    def draw(self, canvas) -> None:
        camp, black = self._black()
        if not camp:
            self.fishing.draw(canvas)   # 들어가고 나올 때만 낚시 화면
        else:
            w, h = canvas.get_size()
            campsite.draw(canvas, self.fishing, self.t)
            cx, by = campsite.fire_pos(w, h)
            self._draw_event_back(canvas, cx, by, 1.0)
            self._draw_fire(canvas, cx, by, 1.0)
            self._draw_event_front(canvas, cx, by, 1.0)
            f = self.fishing
            text(canvas, f"{f.clock.label()} · {WEATHER_KO[f.weather]}", (8, 6), (240, 236, 220), 11, "topleft")
        if black > 0:
            veil = pygame.Surface(canvas.get_size())
            veil.set_alpha(int(255 * clamp(black, 0.0, 1.0)))
            canvas.blit(veil, (0, 0))

    def _draw_fire(self, canvas, cx: int, by: int, k: float) -> None:
        s = 2   # 야영지에선 2배 (도트 그대로)
        # 장작 2개 X 자 (16×6 → ×2)
        pygame.draw.line(canvas, LOG, (cx - 8 * s, by + 3 * s), (cx + 8 * s, by - 2 * s), 3 * s)
        pygame.draw.line(canvas, LOG, (cx - 8 * s, by - 2 * s), (cx + 8 * s, by + 3 * s), 3 * s)
        # 불꽃 3겹 (높이 10~14px, 0.12초마다 1px씩)
        heights = (14, 11, 7)
        widths = (10, 7, 4)
        for i, col in enumerate(FLAME):
            hh = (heights[i] + self.flick[i]) * s
            ww = widths[i] * s
            dx = self.flick[(i + 1) % 3] * s
            pts = [(cx - ww // 2 + dx, by - s), (cx + ww // 2 + dx, by - s), (cx + dx + (s if i % 2 else -s), by - s - hh)]
            pygame.draw.polygon(canvas, col, pts)
        for e in self.embers:   # 불티 점 2~4개
            a = 1.0 - e[4]
            col = (255, int(180 + 60 * a), int(90 * a))
            canvas.fill(col, (int(cx + e[0] * s), int(by - 24 - e[1] * s), 2, 2))

    def _draw_event_back(self, canvas, cx: int, by: int, k: float) -> None:
        ev = self.event
        if ev is None or not self.ev_started:
            return
        if ev["id"] == "meteor" and self.ev_t < 0.6:
            u = min(1.0, self.ev_t / 0.4)
            x0, y0 = self.ev_data["x"], self.ev_data["y"]
            x1, y1 = x0 - 46 * u, y0 + 22 * u
            pygame.draw.line(canvas, (240, 245, 255), (int(x0 - 46 * max(0.0, u - 0.5)), int(y0 + 22 * max(0.0, u - 0.5))),
                             (int(x1), int(y1)), 1)
            if u >= 1.0:
                canvas.set_at((int(x1), int(y1)), (255, 255, 255))

    def _draw_event_front(self, canvas, cx: int, by: int, k: float) -> None:
        ev = self.event
        if ev is None or not self.ev_started:
            return
        eid = ev["id"]
        if eid == "cat":
            from src.render import village_life as vl
            walk = min(1.0, self.ev_t / 0.8)
            x = cx + 96 - 60 * walk   # 오른쪽 풀밭에서 걸어와 불 앞에서 잠
            vl.draw_cat(canvas, x, by + 14, "walk" if walk < 1.0 else "sleep", -1, self.t, step=self.ev_t * 6)
        elif eid == "fireflies":
            from src.render.map_fx import cfg as map_cfg
            col = tuple(map_cfg()["fireflies"]["color"])   # 반딧불 (DETAILS A-5) 색 그대로
            for p in self.ev_data["pts"]:
                if math.sin(self.t * 3 + p[2]) > -0.2:
                    canvas.fill(col, (int(cx + p[0] * 1.8 + math.sin(self.t + p[2]) * 4), int(by + p[1] * 1.6 - 6), 2, 2))
        elif eid == "snow":
            for p in self.ev_data["pts"]:
                y = by - 90 + ((self.ev_t * 30 + p[2] * 13) % 70)
                if y < by - 26:   # 불 위에서 녹음
                    canvas.fill((250, 252, 255), (int(cx + p[0] * 0.8), int(y), 2, 2))
