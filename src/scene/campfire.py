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
from src.core.mathutil import clamp, lerp_color
from src.core.weather import WEATHER_KO
from src.render import camp_fpv
from src.render.palette import Palette
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
        self.low = game.settings.get("quality") == "low"   # 화질 '낮음': 불티 절반 · 아지랑이 끔
        self.rnd = random.Random()
        # 캠프 장면: 무거운 층은 장면 시작 때 한 번 굽기 (CAMPFIRE_FPV 공통 규칙)
        w, h = game.screen.canvas.get_size()
        self.camp = camp_fpv.CampFPV(w, h, fishing.season, snowy=fishing.spot_id == "ice_sea")
        self.hand_pal = Palette().sample(13.0)   # 손 기본색 (밤 어둠 · 불빛은 조명이 입힘)
        self.hand_look = fishing._hand_look()
        self.snowy = fishing.season == "winter" or fishing.spot_id == "ice_sea"
        self.height_k = 1.0
        for _ in range(90):   # 처음부터 불티 · 연기가 올라가 있게 (1.5초 미리)
            self.camp.update(1 / 60, fishing.wind.x, self.low)
        self.amb_t = 0.8   # 숲 공기 (낮 새 · 밤 귀뚜라미)
        self.skip_to: tuple[float, float] | None = None   # (건너뛴 순간 t, 끝 시각) — 남은 시간을 0.4초에
        self.pop_t = 0.6
        self.done = False
        cf = campfire_cfg()
        if force_event:
            self.event = next((e for e in cf["events"] if e["id"] == force_event), None)
        else:
            self.event = pick_event(game.save, fishing, self.hours)
        # 달력으로 하루 넘게 쉬면 (CORE_UPDATE CU1, 최대 14일): 앞부분은 장면이 열리기 전에 넘기고 마지막 24시간만 타임랩스 —
        # 2초 안에 낮밤이 여러 번 바뀌며 화면이 깜빡이지 않게 (작은 일은 위에서 전체 구간으로 이미 골랐음)
        jump = max(0.0, self.hours - 24.0)
        if jump > 0:
            fishing._advance_hours(jump)
            self.hours -= jump
        self.ev_at = cf.get("at_sec", 1.2)
        self.ev_started = False
        self.ev_t = 0.0
        self.ev_data: dict = {}
        fishing.toasts.items.clear()   # 낚시 화면이 멈춰 있으니 남은 토스트가 그대로 얼어 보임
        game.adaptive.suspend(True)   # 배경 음악 멈춤 → 끝나면 그 시간대 음악으로 다시
        game.sfx.loop("room_fire", True, 0.5)

    # ── 진행 ──
    REDUCE_SEC = 1.5   # 화면 효과 줄이기: 타임랩스 대신 가운데에서 한 번 어두워졌다 밝아지며 시계가 넘어감

    def _progress(self) -> float:
        """0..1 시계 진행 (easeInOut). 줄이기 = 가운데(0.75초) 페이드 바닥에서 한 번에."""
        if self.reduce:
            return 1.0 if self.t >= self.REDUCE_SEC / 2 else 0.0
        span = DIM_OUT_AT - DIM_IN
        return ease((self.t - DIM_IN) / span)

    def _end_time(self) -> float:
        return self.REDUCE_SEC if self.reduce else self.total

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
        real_dt = dt   # 불 · 불티 · 연기 · 숯은 실제 시간으로 (타임랩스 · 건너뛰기와 상관없이)
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
        self.real_t = getattr(self, "real_t", 0.0) + real_dt
        rain = f.weather in ("rain", "storm")
        self.height_k = 0.85 if rain else 1.0   # 비: 불꽃 높이 −15%
        self.camp.update(real_dt, f.wind.x, self.low, self.height_k)
        roof = 2.0 if (self.event is not None and self.event["id"] == "rain_roof" and self.ev_started) else 1.0
        self.camp.update_weather(real_dt, f.weather, self.snowy, f.season == "autumn", f.wind.x, roof)
        self._ambience(real_dt)
        self.pop_t -= dt
        if self.pop_t <= 0 and self.t < self._end_time() - 0.3:
            self.pop_t = 0.6
            self.game.sfx.play(f"room_fire_pop{self.rnd.randrange(3)}", 0.35)
        # 모닥불의 작은 일
        if self.event is not None and not self.ev_started and self.t >= (self.ev_at if not self.reduce else DIM_IN):
            self.ev_started = True
            snd = self.event.get("sound")
            if snd:
                self.game.sfx.play(snd[0], snd[1])
            r = self.rnd
            if self.event["id"] == "fireflies":   # 텐트 앞 · 나무 줄기 사이 6~10점
                pts = [[r.uniform(118, 206), r.uniform(150, 214), r.uniform(0, 6.28)] for _ in range(r.randint(3, 5))]
                pts += [[r.uniform(332, 440), r.uniform(140, 200), r.uniform(0, 6.28)] for _ in range(r.randint(3, 5))]
                self.ev_data = {"pts": pts}
        if self.ev_started:
            self.ev_t += dt
        if self.t >= self._end_time() and not self.done:
            self._finish()

    def _ambience(self, dt: float) -> None:
        """숲 공기 (🅲-3): 낮 amb_bird 드물게 · 밤 amb_cricket (여름 · 가을). 새 효과음 없음."""
        self.amb_t -= dt
        if self.amb_t > 0:
            return
        self.amb_t = self.rnd.uniform(0.9, 1.6)
        f = self.fishing
        h = f.clock.hour % 24
        if 6 <= h < 18 and f.weather == "clear" and self.rnd.random() < 0.35:
            self.game.sfx.play(f"amb_bird#{self.rnd.randrange(3)}", 0.25)   # 단계 = 다른 새 (amb_bird#0~2)
        elif (h >= 20 or h < 5) and f.season in ("summer", "autumn") and f.weather != "storm":
            self.game.sfx.play("amb_cricket", 0.22)

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
        if self.reduce:   # 가운데 페이드 (0.2초 어두워짐 → 시계 → 0.2초 밝아짐)
            return True, clamp(1 - abs(self.t - end / 2) / 0.2, 0.0, 1.0)
        return True, 0.0

    def draw(self, canvas) -> None:
        camp, black = self._black()
        if not camp:
            self.fishing.draw(canvas)   # 들어가고 나올 때만 낚시 화면
        else:
            f = self.fishing
            cam = self.camp
            hour, t = f.clock.hour, getattr(self, "real_t", self.t)
            pal = f.scene_palette()
            ls = cam.light_state(hour, f.weather, t)
            cam.draw_world(canvas, pal, hour, t, ls, cloud_shift=self.applied * 18, sun=f.weather == "clear",
                           weather=f.weather, wind=f.wind.x)
            f.rain.draw(canvas, pal)   # 빗줄기 (낚시 화면 날씨 효과 그대로)
            self._draw_event_under(canvas, cam, ls)
            cam.draw_light(canvas, ls, t)
            cam.draw_top(canvas, ls, t, self.height_k, haze=not self.low)
            cam.draw_weather_top(canvas, f.weather, ls["nk"], self.reduce)
            self._draw_event_over(canvas, cam, ls)
            # 두 손: 0.3초에 올라오고 끝나기 직전 내려감 · 1.6초 주기 1px 숨쉬기 · 가끔 손가락 오므림
            end = self._end_time()
            k_in = ease((self.t - DIM_IN / 2) / 0.3) * ease((end - DIM_IN / 2 - self.t) / 0.15)
            dy = int(round((1 - k_in) * 48)) + (1 if math.sin(t * math.tau / 1.6) > 0 else 0)
            curl = (t % 2.3) < 0.2
            cam.draw_hands(canvas, self.hand_pal, self.hand_look, dy, curl, light=1 - 0.55 * ls["nk"],
                           glow=max(ls["nk"], ls["glow"] / 40))
            if f.weather in ("rain", "storm"):
                self._draw_wet(canvas, cam, dy, t)
            self._draw_event_palm(canvas, cam, dy)
            text(canvas, f"{f.clock.label()} · {WEATHER_KO[f.weather]}", (8, 6), (240, 236, 220), 11, "topleft")
        if black > 0:
            veil = pygame.Surface(canvas.get_size())
            veil.set_alpha(int(255 * clamp(black, 0.0, 1.0)))
            canvas.blit(veil, (0, 0))

    # ── 모닥불의 작은 일 (CAMPFIRE_FPV 🅳 위치 · 모습, 확률 · 문구는 TIME_REST 🅳) ──
    def _ev(self, eid: str) -> bool:
        return self.event is not None and self.ev_started and self.event["id"] == eid

    def _draw_event_under(self, canvas, cam, ls) -> None:
        """덮개 아래 (불빛 · 어둠을 받음): 나비."""
        if self._ev("cat"):
            from src.render import village_life as vl
            walk = min(1.0, self.ev_t / 0.9)
            x = cam.X(392 - 72 * walk)   # 오른쪽 풀밭에서 걸어와 불 오른쪽 돌 옆 (320, 238) 에 동그랗게
            vl.draw_cat(canvas, x, 242, "walk" if walk < 1.0 else "sleep", -1, self.t, step=self.ev_t * 6)
            self._cat_x = x

    def _draw_event_over(self, canvas, cam, ls) -> None:
        """덮개 위: 나비 등의 불빛 · 별똥별 · 반딧불 · 올빼미."""
        nk = ls["nk"]
        if self._ev("cat") and nk > 0.05 and self.ev_t >= 0.9:
            x = getattr(self, "_cat_x", cam.X(320))
            col = lerp_color((60, 40, 30), (255, 160, 90), min(1.0, nk))
            canvas.fill(col, (x - 4, 235, 7, 1))   # 불빛 받은 등 (불 쪽)
        if self._ev("meteor") and self.ev_t < 0.7:
            u = min(1.0, self.ev_t / 0.4)   # 하늘 트인 구간 안, 오른쪽 위 → 왼쪽 아래 0.4초
            x0, y0 = cam.X(312), 18
            x1, y1 = cam.X(312 - 120 * u), 18 + 52 * u
            tail = max(0.0, u - 0.35)
            pygame.draw.line(canvas, (240, 245, 255), (int(x0 - 120 * tail), int(y0 + 52 * tail)), (int(x1), int(y1)), 1)
            if u >= 1.0 and self.ev_t < 0.55:
                canvas.set_at((int(x1), int(y1)), (255, 255, 255))
                canvas.set_at((int(x1) + 1, int(y1)), (200, 210, 240))
        if self._ev("fireflies"):
            from src.render.map_fx import cfg as map_cfg
            col = tuple(map_cfg()["fireflies"]["color"])   # 반딧불 (DETAILS A-5) 색 그대로
            for p in self.ev_data.get("pts", []):
                k = math.sin(self.real_t * 2.4 + p[2])
                if k > -0.3:
                    x = cam.X(p[0]) + int(math.sin(self.real_t * 0.9 + p[2]) * 5)
                    y = int(p[1] + math.sin(self.real_t * 1.3 + p[2] * 2) * 3)
                    if k > 0.2:   # 밝을 때 둘레 번짐
                        halo = lerp_color((40, 50, 30), col, 0.45)
                        canvas.fill(halo, (x - 1, y, 4, 2))
                        canvas.fill(halo, (x, y - 1, 2, 4))
                    canvas.fill(col if k > 0.2 else lerp_color(col, (60, 60, 30), 0.5), (x, y, 2, 2))
        if self._ev("owl"):
            # 오른쪽 가까운 나뭇가지 위 실루엣 (8×10, 눈 2px 노랑) 이 고개를 한 번 돌림
            bx, by = cam.X(356), 132
            rim = lerp_color((30, 26, 32), (120, 132, 170), 0.6)   # 달빛 받은 테두리 (어둠 속 실루엣이 보이게)
            pygame.draw.line(canvas, (40, 30, 24), (bx - 18, by + 1), (bx + 14, by - 1), 2)   # 가지
            body = (30, 26, 32)
            pygame.draw.ellipse(canvas, rim, (bx - 5, by - 11, 10, 12))
            pygame.draw.ellipse(canvas, body, (bx - 4, by - 10, 8, 10))
            canvas.fill(rim, (bx - 5, by - 13, 2, 2))   # 귀깃
            canvas.fill(rim, (bx + 3, by - 13, 2, 2))
            canvas.fill(body, (bx - 4, by - 12, 2, 2))
            canvas.fill(body, (bx + 2, by - 12, 2, 2))
            turn = 0 if self.ev_t < 0.5 else (1 if self.ev_t < 1.1 else 0)
            ex = bx - 3 + turn * 2
            canvas.fill((255, 214, 90), (ex, by - 8, 2, 2))
            if turn == 0:
                canvas.fill((255, 214, 90), (ex + 4, by - 8, 2, 2))   # 정면: 두 눈 / 옆으로: 한 눈

    def _draw_event_palm(self, canvas, cam, dy) -> None:
        """눈: 손바닥 위에 눈송이 하나가 내려앉아 녹음."""
        if not self._ev("snow"):
            return
        palm_x, palm_y = cam.X(172), 270 + dy - 21
        u = self.ev_t
        if u < 0.9:
            y = 120 + (palm_y - 120) * (u / 0.9)
            x = palm_x + math.sin(u * 6) * 4
            canvas.fill((250, 252, 255), (int(x), int(y), 2, 2))
        elif u < 1.6:
            k = 1 - (u - 0.9) / 0.7
            canvas.fill(lerp_color((200, 220, 240), (250, 252, 255), k), (palm_x, palm_y, 2 if k > 0.5 else 1, 1))

    def _draw_wet(self, canvas, cam, dy, t) -> None:
        """비: 손 위 물기 점 3~5개 (DETAILS '젖은 손', 번갈아 반짝)."""
        pts = ((166, -18), (178, -24), (184, -14), (318, -22), (330, -16))
        n = 3 + int(t * 0.2) % 3
        for i, (x, y) in enumerate(pts[:n]):
            on = int(t * 3 + i * 1.7) % 3 != 0
            canvas.fill((235, 248, 255) if on else (170, 200, 225), (cam.X(x), 270 + dy + y, 1, 1))
