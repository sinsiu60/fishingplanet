"""1인칭 낚시 장면: 캐스팅 → 입질 → 챔질 → 파이팅 → 뜰채 → 획득."""
import math
import random

import pygame

from src.core.config import game_config, load_json
from src.core.game_clock import PERIODS, GameClock
from src.core.weather import WEATHER_KO, Weather, roll_weather
from src.core.mathutil import clamp, lerp, lerp_color, smoothstep
from src.fishing.bite import BiteController, BiteState, roll_size
from src.fishing.casting import CastController, CastState
from src.fishing.fight import LOSE_REASONS, Fight
from src.render import world
from src.render.camera import Camera
from src.render.effects import (Bubbles, Droplets, Ripples, Sparkles, draw_bobber, draw_fish_shadow, draw_ink,
                                draw_line, landing_marker, rod_tip_drop)
from src.render.fish_draw import draw_catch_cut, draw_jump, draw_net_scene
from src.render.landing import LandingCinematic
from src.render.palette import Palette
from src.render.rod import draw_rod, rod_geometry
from src.render.screen_fx import ScreenFX
from src.render.weather_fx import Ambient, Lightning, Rain, themed_palette
from src.scene.base import Scene
from src.ui import fight_fx, fight_hud, hud
from src.ui import tutorial as tut

HINTS = {
    CastState.READY: "좌클릭 유지: 던지기   M: 지도   B: 상점   Tab: 도감   H: 도움말   ESC: 메뉴",
    CastState.CHARGING: "놓으면 던지기   우클릭: 취소",
    CastState.SWING: "",
    CastState.FLIGHT: "",
    CastState.LANDED: "좌클릭: 챔질 (찌가 쑥 잠길 때!)   우클릭: 줄 회수   화면 끝: 둘러보기",
    CastState.RETRIEVE: "줄 감는 중...",
    CastState.HOOKED: "좌클릭 유지: 감기   우클릭: 숙이기   Q/E·휠: 드랙   마우스: 버티기   H: 도움말",
}
NET_HINT = "몸부림이 멈춘 순간 좌클릭!"
GOOD = (140, 240, 150)
BAD = (255, 150, 130)
INFO = (255, 235, 170)
LOOK_STATES = (CastState.READY, CastState.LANDED)
WEATHERS = ["clear", "rain", "storm"]
GLOW = {"rare": (150, 210, 255), "legend": (255, 215, 100)}
DRAGON_LOOK = {"colors": {"body": [200, 40, 40], "belly": [255, 214, 110], "fin": [255, 170, 40],
                          "stripe": [255, 230, 140]},
               "shape": {"height": 0.13, "whiskers": True, "dorsal": "crest", "tail": "fork", "pattern": "spots"}}

# 튜토리얼 카드를 본 뒤 한 번 더 짧게 상기시킨다 (DESIGN.md 4장)
TIPS = {
    "telegraph:rush": "꼬리 물보라 = 돌진! Q로 드랙을 낮추세요",
    "telegraph:jump": "그림자가 커진다 = 점프! 원이 겹치는 순간 우클릭",
    "telegraph:turn": "줄이 쏠린다 = 방향 전환! 마우스를 반대쪽으로",
    "action:charge": "멈췄다 = 힘 모으기! 지금 확 감으세요",
    "tired": "지쳤다! 드랙을 올리고(E) 크게 감으세요",
    "fake_tired": "기포가 계속 올라온다 = 가짜 지침! 돌진 대비",
}
TIP_REPEAT = 1
SLACK_RED_CARD_SEC = 0.6  # 이 시간 이상 느슨/빨강이면 튜토리얼 카드


class FishingScene(Scene):
    def __init__(self, game):
        super().__init__(game)
        cfg = game_config()
        self.cam_cfg = cfg["camera"]
        canvas = game.screen.canvas
        self.cam = Camera(canvas.get_width(), canvas.get_height(), self.cam_cfg)
        self.save = game.save
        self.clock = GameClock()
        self.clock.hour = self.save.data["hour"]
        self.clock.day = self.save.data["day"]
        self.palette = Palette()
        self.stars = world.StarField(self.cam)
        self.clouds = world.Clouds(self.cam)
        self.water = world.Water(self.cam)
        self.reeds = world.Reeds(self.cam)
        self.cast = CastController()
        self.bite = BiteController()
        self.sfx = game.sfx
        self.toasts = hud.Toasts()
        self.ripples = Ripples()
        self.droplets = Droplets()
        self.bubbles = Bubbles()
        self.sparkles = Sparkles()
        self.popups = fight_fx.JudgePopups()
        self.gather = fight_fx.GatherFX()
        self.screen_fx = ScreenFX(canvas.get_width(), canvas.get_height())
        self.fish_cfg = load_json("fishing_config.json")
        self.spots = {sp["id"]: sp for sp in load_json("spots.json")["spots"]}
        self.spot_ids = list(self.spots)
        self.force_i = -1          # F3 테스트: 고정할 물고기 인덱스 (-1 = 없음)
        self.all_fish = load_json("fish.json")["fish"]
        force = self.fish_cfg.get("debug_force_fish")
        if force:
            self.force_i = next((i for i, x in enumerate(self.all_fish) if x["id"] == force), -1)
        self._set_spot(self.save.data["spot"] if self.save.data["spot"] in self.spots else "reservoir")
        d = self.save.data
        self.weather_sys = Weather(d.get("weather", "clear"),
                                   d.get("weather_next") or roll_weather(self.spot["weather"]),
                                   d.get("weather_change", 0.0))
        self.rain = Rain(canvas.get_width(), canvas.get_height())
        self.lightning = Lightning()
        self.ambient = Ambient(canvas.get_width(), canvas.get_height(), self.cam.horizon)
        self.amb_loops: set[str] = set()
        self.legend_on = False   # 전설 등장 중 (BGM·색감·금빛 테두리)
        self.legend_k = 0.0
        self.catch_news: dict | None = None
        self.ink_t = 0.0
        self.fake_bubble_t = 0.0
        self.fight: Fight | None = None
        self.landing: LandingCinematic | None = None   # 뜰채 성공 → 획득 컷 사이 연출
        self.end_t = 0.0             # 결과 화면 경과 시간
        self.net_anim = 0.0
        self.jump_facing = -1
        self.fx_t = 0.0
        self.tip_counts: dict[str, int] = {}
        self.debug = False
        self.settings = game.settings
        self.tutorial = tut.Tutorial(self.settings)
        self.card: dict | None = None    # 튜토리얼 카드 (표시 중엔 게임 정지)
        self.help = False                # H 도움말 (표시 중엔 게임 정지)
        self.slack_t = self.red_t = 0.0
        self.shake_on = self.settings.get("screen_shake")
        self.screen_fx.enabled = self.shake_on
        self.shake_kick = 0.0
        self.reel_loop = None
        self.t = 0.0
        self.mouse = (canvas.get_width() // 2, canvas.get_height() // 2)
        self.look_left = self.look_right = False
        self.idle_ripple_t = 0.0
        self.wake_t = 0.0
        if self.tutorial.want("welcome"):
            self._open_card("welcome", None)

    def _set_spot(self, spot_id: str) -> None:
        self.spot_id = spot_id
        self.spot = self.spots[spot_id]
        self.theme = self.spot["theme"]
        self.hazard_decor = world.HazardDecor(self.spot["hazards"])
        self.screen_fx.sway = self.theme.get("sway", 0)

    @property
    def weather(self) -> str:
        return self.weather_sys.current

    def _display_fish(self, fish: dict) -> dict:
        """용으로 변신한 '등용'은 붉은 용의 모습으로 그린다."""
        f = self.fight
        if f is not None and f.brain.dragon:
            return {**fish, **DRAGON_LOOK}
        return fish

    # ───────────────────────── 이동 · 휴식 ─────────────────────────
    def travel(self, spot_id: str) -> None:
        """지도에서 이동: 1시간 흐르고, 그 지역 기후로 예보가 바뀐다."""
        self.bite.stop()
        self.cast.reset()
        self.cam.yaw = 0.0
        self._set_spot(spot_id)
        self._advance_hours(1.0)
        self.weather_sys.reroll_upcoming(self.spot["weather"])
        self.toasts.show(f"{self.spot['name']}에 도착했다", GOOD, 2.0)
        self.game.save_now()

    def next_period_name(self) -> str:
        return self._next_period()[1]

    def _next_period(self) -> tuple[float, str]:
        h = self.clock.hour
        starts = [(p[0], p[2]) for p in PERIODS]
        for start, name in starts:
            if start > h + 0.01:
                return start, name
        return starts[0][0] + 24.0, starts[0][1]

    def rest(self) -> str:
        """텐트에서 쉬기: 다음 시간대 시작까지 시간을 넘긴다 (날씨도 그만큼 진행)."""
        self.bite.stop()
        self.cast.reset()
        start, name = self._next_period()
        self._advance_hours(start - self.clock.hour)
        self.game.save_now()
        return f"{self.clock.label()} · {WEATHER_KO[self.weather]}"

    def _advance_hours(self, hours: float) -> None:
        self.clock.hour += hours
        while self.clock.hour >= 24.0:
            self.clock.hour -= 24.0
            self.clock.day += 1
        self.weather_sys.update(self.clock.day, self.clock.hour, self.spot["weather"])
        self.weather_sys.events.clear()

    def _check_new_spots(self) -> None:
        """비용 빼고 해금 조건을 처음 채운 낚시터가 있으면 알린다."""
        from src.scene.map_scene import can_unlock_soon
        notified = self.save.data.setdefault("notified_spots", [])
        for sp in self.spots.values():
            if sp["id"] in self.save.data["unlocked_spots"] or sp["id"] in notified:
                continue
            if can_unlock_soon(self.save, sp):
                notified.append(sp["id"])
                name = sp["name"] if sp["id"] != "secret" else "숨겨진 장소"
                self.toasts.show(f"새 낚시터 '{name}'을(를) 열 수 있어요! (M: 지도)", GOOD, 3.5, 11)
                self.sfx.play("great", 0.7)
                return

    def _cycle_debug(self, key: int) -> None:
        """F3 물고기 고정 / F4 낚시터 / F5 날씨 (테스트용)."""
        if key == pygame.K_F3:
            self.force_i = self.force_i + 1 if self.force_i + 1 < len(self.all_fish) else -1
            name = self.all_fish[self.force_i]["name"] if self.force_i >= 0 else "없음 (자연 출현)"
            self.toasts.show(f"[테스트] 물고기 고정: {name}", INFO, 1.5, 11)
        elif key == pygame.K_F4:
            i = (self.spot_ids.index(self.spot_id) + 1) % len(self.spot_ids)
            self._set_spot(self.spot_ids[i])
            self.toasts.show(f"[테스트] 낚시터: {self.spot['name']} (해금 무시)", INFO, 1.5, 11)
        elif key == pygame.K_F5:
            w = self.weather_sys
            w.current = WEATHERS[(WEATHERS.index(w.current) + 1) % len(WEATHERS)]
            self.toasts.show(f"[테스트] 날씨: {WEATHER_KO[w.current]}", INFO, 1.5, 11)

    def _open_card(self, key: str, focus: str | None) -> None:
        self.card = {"key": key, "focus": focus, "t": 0.0}

    def _card_focus(self):
        focus = self.card["focus"]
        if focus == "gauge":
            return (14, 114)
        if focus == "fish" and self.fight is not None:
            return self._fish_screen()
        return None

    # ───────────────────────── 입력 ─────────────────────────
    def handle_event(self, event: pygame.event.Event) -> None:
        f = self.fight
        if event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            self.cast.release(self.cam.yaw)
            return
        if self.help:
            if event.type == pygame.MOUSEBUTTONDOWN or (event.type == pygame.KEYDOWN and event.key == pygame.K_h):
                self.help = False
            return
        if self.card is not None:
            if event.type == pygame.MOUSEBUTTONDOWN and self.card["t"] > 0.35:
                self.card = None
            return
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_h:
                self.help = True
            elif event.key == pygame.K_ESCAPE and self.landing is None:
                self.sfx.play("click")
                from src.scene.pause import PauseScene
                self.game.scenes.push(PauseScene(self.game, self))
            elif event.key == pygame.K_b and self.can_open_menus():
                self.open_menu("shop")
            elif event.key == pygame.K_TAB and self.fight is None:
                self.open_menu("dex")
            elif event.key == pygame.K_m and self.can_open_menus():
                self.open_menu("map")
            elif event.key in (pygame.K_F3, pygame.K_F4, pygame.K_F5) and f is None and self.fish_cfg.get("debug_keys"):
                self._cycle_debug(event.key)
            elif event.key == pygame.K_t:
                self.clock.fast = not self.clock.fast
            elif event.key == pygame.K_F1:
                self.debug = not self.debug
            elif event.key == pygame.K_F2:
                self.shake_on = not self.shake_on
                self.screen_fx.enabled = self.shake_on
                self.settings.set("screen_shake", self.shake_on)
                self.toasts.show("화면 연출(흔들림·줌) " + ("켬" if self.shake_on else "끔"), INFO, 1.2, 11)
            elif f and event.key == pygame.K_q:
                f.change_drag(-1)
            elif f and event.key == pygame.K_e:
                f.change_drag(+1)
        elif event.type == pygame.MOUSEWHEEL and f:
            f.change_drag(1 if event.y > 0 else -1)
        elif event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 1:
                self._left_click()
            elif event.button == 3:
                self._right_click()

    # ───────────────────────── 메뉴 · 저장 ─────────────────────────
    def can_open_menus(self) -> bool:
        return self.fight is None and self.cast.state in (CastState.READY, CastState.LANDED, CastState.RETRIEVE)

    def open_menu(self, which: str) -> None:
        self.sfx.play("click")
        if which == "shop":
            if not self.can_open_menus():
                return
            # 상점에 가면 줄은 걷는다
            self.bite.stop()
            self.cast.reset()
            from src.scene.shop import ShopScene
            self.game.scenes.push(ShopScene(self.game, self))
        elif which == "dex":
            from src.scene.dex import DexScene
            self.game.scenes.push(DexScene(self.game, self))
        elif which == "map":
            if not self.can_open_menus():
                return
            from src.scene.map_scene import MapScene
            self.game.scenes.push(MapScene(self.game, self))
        if self.reel_loop:
            self.sfx.loop(self.reel_loop, False)
            self.reel_loop = None

    def write_save(self) -> None:
        d = self.save.data
        d["hour"], d["day"] = self.clock.hour, self.clock.day
        d["spot"] = self.spot_id
        d.update(self.weather_sys.to_save())

    def apply_settings(self) -> None:
        self.shake_on = self.settings.get("screen_shake")
        self.screen_fx.enabled = self.shake_on

    def _left_click(self) -> None:
        c, f = self.cast, self.fight
        if self.landing is not None:
            self.landing.skip()
            return
        if f is not None:
            if f.phase == "net":
                self.net_anim = 0.3
                f.net_click()
            elif f.phase in ("caught", "lost") and self.end_t > fight_hud.CATCH_READY_T:
                self._end_fight()
            return
        if c.state != CastState.LANDED:
            c.press()
            return
        # 챔질
        c.jerk()
        result = self.bite.hookset()
        if result == "hooked":
            self.tutorial.mark("guide_wait")
            c.hooked()
            self.sfx.play("hookset")
            self.toasts.show("챔질 성공!", GOOD, 1.0)
            self._splash_at(c.bx, c.bz, big=0.6)
            self._start_fight()
        elif result == "scared":
            self.sfx.play("hookset", 0.5)
            self.sfx.play("flee")
            self.toasts.show("물고기가 놀라 도망갔다...", BAD, 2.4)
        else:
            self.sfx.play("cast", 0.4)
            if self.bite.state == BiteState.MISSED:
                self.toasts.show("미끼가 없어요. 우클릭으로 회수", INFO, 2.0, 11)

    def _right_click(self) -> None:
        if self.fight is not None:
            if self.fight.phase == "fight":
                self.sfx.play("cast", 0.35)
                self.fight.dip()
            return
        if self.cast.state == CastState.LANDED:
            self.bite.stop()
        self.cast.cancel_or_retrieve()

    # ───────────────────────── 파이팅 시작·끝 ─────────────────────────
    def _start_fight(self) -> None:
        c = self.cast
        fish = self.bite.fish
        size = roll_size(fish, self.bite.cast_distance)
        angle = math.atan2(c.bx, c.bz)
        self.fight = Fight(fish, size, c.current_distance(), angle, self.cam.yaw, gear=self.save.fight_gear(),
                           hazards=self.spot["hazards"])
        if fish["rarity"] == "legend":
            self.toasts.show(f"전설 등장! {fish['name']}", (255, 214, 90), 3.0)
            self.sfx.play("impact", 1.0)
            self.sfx.play("chord_legend", 0.7)
            self.shake_kick = 2.5
        self.ink_t = 0.0
        self.bite.shadow = None
        self.end_t = 0.0
        self.slack_t = self.red_t = 0.0
        if self.tutorial.want("fight_intro"):
            self._open_card("fight_intro", "gauge")

    def _end_fight(self) -> None:
        last = self.fight.result if self.fight is not None else None
        self.fight = None
        self.landing = None
        self._check_new_spots()
        if last and last["fish"]["id"] == "dragon_carp" and not self.save.data.get("ending_seen"):
            self.save.data["ending_seen"] = True
            self.game.save_now()
            from src.scene.ending import EndingScene
            self.game.scenes.push(EndingScene(self.game, self))
        self.screen_fx.reset()
        self.bite.stop()
        self.cast.reset()
        self.game.screen.shake = (0, 0)

    # ───────────────────────── 로직 (60틱 고정) ─────────────────────────
    def update(self, dt: float) -> None:
        if self.card is not None or self.help:
            # 튜토리얼 카드·도움말: 게임 정지 (예고 시간도 흐르지 않음)
            if self.card is not None:
                self.card["t"] += dt
            mx, my = self.game.screen.to_canvas(pygame.mouse.get_pos())
            self.mouse = (int(clamp(mx, 0, self.cam.width - 1)), int(clamp(my, 0, self.cam.height - 1)))
            if self.reel_loop:
                self.sfx.loop(self.reel_loop, False)
                self.reel_loop = None
            self.game.screen.shake = (0, 0)
            return
        self.t += dt
        self.clock.update(dt)
        self.clouds.update(dt)
        self._update_weather(dt)
        self.ripples.update(dt)
        self.droplets.update(dt)
        self.bubbles.update(dt)
        self.sparkles.update(dt)
        self.popups.update(dt)
        self.toasts.update(dt)
        self.net_anim = max(0.0, self.net_anim - dt)

        mx, my = self.game.screen.to_canvas(pygame.mouse.get_pos())
        w = self.cam.width
        self.mouse = (int(clamp(mx, 0, w - 1)), int(clamp(my, 0, self.cam.height - 1)))

        # 둘러보기: 대기 중에만, 화면 좌우 끝에 마우스
        edge = self.cam_cfg["edge_px"]
        can_look = self.cast.state in LOOK_STATES
        self.look_left = can_look and mx < edge and self.cam.yaw > -self.cam.max_yaw
        self.look_right = can_look and mx > w - edge and self.cam.yaw < self.cam.max_yaw
        speed = math.radians(self.cam_cfg["look_speed_deg"]) * dt
        if self.look_left:
            self.cam.yaw = max(-self.cam.max_yaw, self.cam.yaw - speed)
        if self.look_right:
            self.cam.yaw = min(self.cam.max_yaw, self.cam.yaw + speed)

        aim = clamp((mx - self.cam.cx) / (self.cam.cx - edge), -1.0, 1.0)
        self.cast.update(dt, aim)
        for ev in self.cast.events:
            if ev == "splash":
                self._splash()
            elif ev == "launch":
                self.sfx.play("cast")
        self.cast.events.clear()

        if self.fight is not None:
            self._update_fight(dt, aim)
        else:
            self._update_waiting(dt)

        self._update_reel_sound()
        self._update_shake(dt)
        self._update_legend(dt)
        f = self.fight
        fighting = f is not None and f.phase == "fight"
        fish_pos = self._fish_screen() if fighting else None
        self.screen_fx.update(dt, f, fish_pos)
        scale = 1.0
        if fighting:
            p = self.cam.project(*f.fish_xz())
            scale = p[2] / 20 if p else 1.0
        self.gather.update(dt, fighting and f.brain.state == "charge" and self.ink_t <= 0, fish_pos, scale)

    def _update_legend(self, dt: float) -> None:
        f = self.fight
        if f is not None:
            on = f.fish["rarity"] == "legend" and f.phase in ("fight", "net")
        else:
            on = self.bite.legend and self.bite.state in (BiteState.APPROACH, BiteState.NIBBLE, BiteState.BITE)
        if on != self.legend_on:
            self.legend_on = on
            self.sfx.loop("bgm_legend", on, 0.55)
        self.screen_fx.legend = on
        self.legend_k += ((1.0 if on else 0.0) - self.legend_k) * min(1.0, dt / 0.8)

    def _update_weather(self, dt: float) -> None:
        w = self.weather_sys
        w.update(self.clock.day, self.clock.hour, self.spot["weather"])
        for ev in w.events:
            msg = {"clear": "비가 그치고 하늘이 갰다", "rain": "비가 내리기 시작했다 (입질 증가)",
                   "storm": "폭풍이 몰아친다! (희귀어 증가)"}[ev.split(":")[1]]
            self.toasts.show(msg, INFO, 2.6, 11)
        w.events.clear()
        self.rain.update(dt, self.weather, self.ripples, self.cam)
        self.lightning.update(dt, self.weather, self.cam.horizon, self.cam.width)
        for ev in self.lightning.events:
            if ev == "thunder":
                self.sfx.play("thunder", 0.9)
            elif ev == "strike":
                self.shake_kick = max(self.shake_kick, 1.0)
        self.lightning.events.clear()
        self.ambient.update(dt, self.clock.period()[0], self.weather, self.theme.get("sea", False))
        # 환경음: 낚시터 + 비
        want = {self.theme["ambient"]}
        if self.weather != "clear":
            want.add("amb_rain")
        for name in self.amb_loops - want:
            self.sfx.loop(name, False)
        for name in want:
            vol = 0.35 if name != "amb_rain" else (0.4 if self.weather == "rain" else 0.65)
            if self.legend_on:
                vol *= 0.4  # 전설 BGM이 들리게
            self.sfx.loop(name, True, vol)
        self.amb_loops = want

    def _update_waiting(self, dt: float) -> None:
        self.bite.set_conditions(self.clock.period()[0], self.weather, self.spot_id)
        self.bite.bait = self.save.equipped("bait")
        self.bite.force_fish = self.all_fish[self.force_i] if self.force_i >= 0 else None
        self.bite.update(dt)
        for ev in self.bite.events:
            self._on_bite_event(ev)
        self.bite.events.clear()

        if self.cast.state == CastState.LANDED and self.bite.state != BiteState.BITE:
            self.idle_ripple_t += dt
            if self.idle_ripple_t > 2.2:
                self.idle_ripple_t = 0.0
                self.ripples.spawn(self.cast.bx, self.cast.bz, size=0.5, life=1.8)
        elif self.cast.state == CastState.RETRIEVE:
            self.wake_t += dt
            if self.wake_t > 0.12:
                self.wake_t = 0.0
                self.ripples.spawn(self.cast.bx, self.cast.bz, size=0.35, life=0.9)

    def _update_fight(self, dt: float, aim: float) -> None:
        f = self.fight
        # 클릭(뜰채·우클릭)으로 생긴 이벤트는 틱 밖에서 발생하므로 먼저 처리
        for ev in f.events:
            self._on_fight_event(ev)
        f.events.clear()
        if f.phase in ("caught", "lost"):
            if self.landing is not None:
                self._update_landing(dt)
                return
            prev = self.end_t
            self.end_t += dt
            if f.phase == "caught" and prev < fight_hud.STAMP_T <= self.end_t:
                # 랭크 도장 쾅
                self.sfx.play("impact", 0.8)
                self.shake_kick = 2.5
                if f.result["rank"] == "S":
                    self.sfx.play("perfect", 0.6)
            return
        reeling = pygame.mouse.get_pressed()[0] and f.phase == "fight"
        f.update(dt, reeling, aim)
        x, z = f.fish_xz()
        self.cast.bx, self.cast.bz = x, z
        for ev in f.events:
            self._on_fight_event(ev)
        f.events.clear()
        if f.phase != "fight":
            return
        # 처음으로 느슨/빨간 구간에 머물면 설명
        zone = f.zone()
        self.slack_t = self.slack_t + dt if zone == "slack" else 0.0
        self.red_t = self.red_t + dt if zone == "red" else 0.0
        if self.card is None:
            if self.slack_t > SLACK_RED_CARD_SEC and self.tutorial.want("slack"):
                self._open_card("slack", "gauge")
            elif self.red_t > SLACK_RED_CARD_SEC and self.tutorial.want("red"):
                self._open_card("red", "gauge")

        # 예고 신호 연출
        b = f.brain
        self.fx_t += dt
        self.ink_t = max(0.0, self.ink_t - dt)
        p = self.cam.project(x, z)
        sig = b.signal
        if b.state == "fake_tired" and p and self.ink_t <= 0:
            # 가짜 지침의 단서: 기포가 계속 올라온다 (진짜 지침은 기포 없음)
            self.fake_bubble_t += dt
            if self.fake_bubble_t > 0.12:
                self.fake_bubble_t = 0.0
                self.bubbles.spawn(p[0], p[1], max(2.0, f.fish["shadow_len_m"] * p[2] * 0.6))
        if sig == "rush" and self.fx_t > 0.12:
            # 꼬리 물보라: 물고기 뒤쪽에서 하얀 물방울
            self.fx_t = 0.0
            back = math.atan2(x, z)
            self.ripples.spawn(x + math.sin(back) * 0.4, z + math.cos(back) * 0.4, size=0.45, life=0.7)
            if p:
                self.droplets.burst(p[0] + random.uniform(-3, 3), p[1], max(0.5, p[2] / 25), count=4)
        elif sig == "jump" and p and self.ink_t <= 0 and not b.dark:
            # 그림자 커짐 + 기포
            self.bubbles.spawn(p[0], p[1], max(3.0, f.fish["shadow_len_m"] * p[2]))
        elif b.state in ("idle", "rush", "turn", "recover") and self.fx_t > (0.15 if b.state == "rush" else 0.6):
            self.fx_t = 0.0
            self.ripples.spawn(x, z, size=0.4 if b.state != "rush" else 0.6, life=0.9)
            if b.state == "rush" and p:
                self.droplets.burst(p[0], p[1], max(0.5, p[2] / 25), count=3)

    def _update_landing(self, dt: float) -> None:
        for ev in self.landing.update(dt):
            if ev == "hit":
                self.sfx.play("splash", 1.0)
                self.sfx.play("impact", 0.5)
                self.shake_kick = 2.0
            elif ev == "lift":
                self.sfx.play("rise", 0.9)
                if self.landing.tier >= 3:
                    self.sfx.play("chord_legend", 0.9)   # 하늘이 어두워지며 금빛 기둥
                    self.shake_kick = 1.5
            elif ev == "launch":
                self.sfx.play("launch", 0.9)
                self.sfx.play("splash_small", 0.6)
            elif ev == "apex":
                self.sfx.play("perfect", 0.5)
                if self.landing.tier == 2:
                    self.sfx.play("chord_rare", 0.9)
                elif self.landing.tier >= 3:
                    self.sfx.play("impact", 1.0)
                    self.sfx.play("chord_rare", 0.8)
                    self.shake_kick = 3.0
        if self.landing.done:
            self.landing = None
            self.end_t = 0.0
            self.sfx.play("catch")

    def _update_reel_sound(self) -> None:
        name = None
        f = self.fight
        if f is not None and f.phase == "fight" and f.reeling:
            v = f.reel_speed_now
            name = "reel0" if v < 0.6 else "reel1" if v < 1.2 else "reel2" if v < 2.0 else "reel3"
        elif self.cast.state == CastState.RETRIEVE:
            name = "reel2"
        if name != self.reel_loop:
            if self.reel_loop:
                self.sfx.loop(self.reel_loop, False)
            if name:
                self.sfx.loop(name, True, 0.5)
            self.reel_loop = name

    def _update_shake(self, dt: float) -> None:
        self.shake_kick = max(0.0, self.shake_kick - dt * 6)
        amp = self.shake_kick
        f = self.fight
        fc = self.fish_cfg["fight"]
        if f is not None and f.phase == "fight" and f.tension > fc["shake_start_tension"]:
            amp += (f.tension - fc["shake_start_tension"]) / 30 * fc["shake_max_px"]
        if not self.shake_on or amp < 0.3:
            self.game.screen.shake = (0, 0)
            return
        a = int(round(amp))
        self.game.screen.shake = (random.randint(-a, a), random.randint(-a, a))

    # ───────────────────────── 이벤트 ─────────────────────────
    def _splash(self) -> None:
        self.tutorial.mark("guide_cast")
        c = self.cast
        self._splash_at(c.bx, c.bz, big=1.0)
        self.sfx.play("splash")
        self.bite.start((c.bx, c.bz), c.current_distance())
        self.idle_ripple_t = 0.0

    def _splash_at(self, x: float, z: float, big: float) -> None:
        self.ripples.spawn(x, z, size=big, life=1.8, rings=3 if big >= 0.8 else 2)
        p = self.cam.project(x, z)
        if p:
            self.droplets.burst(p[0], p[1], max(0.5, p[2] / 20 * big), count=int(6 + 6 * big))

    def _on_bite_event(self, ev: str) -> None:
        c = self.cast
        if ev == "legend_approach":
            self.toasts.show("수면 아래 거대한 그림자가...!", (255, 214, 120), 3.0)
            self.sfx.play("roar", 0.6)
            self.shake_kick = 1.5
        elif ev == "nibble":
            self.sfx.play("nibble")
            self.ripples.spawn(c.bx, c.bz, size=0.35, life=0.8)
        elif ev == "bite":
            self.sfx.play("bite")
            self.ripples.spawn(c.bx, c.bz, size=1.3, life=1.5, rings=3)
            p = self.cam.project(c.bx, c.bz)
            if p:
                self.droplets.burst(p[0], p[1], max(0.6, p[2] / 20), count=10)
        elif ev == "missed":
            self.sfx.play("flee", 0.6)
            self.toasts.show("미끼만 먹고 도망갔다... (우클릭: 회수)", BAD, 2.6)

    def _tip(self, key: str) -> None:
        n = self.tip_counts.get(key, 0)
        if key in TIPS and n < TIP_REPEAT:
            self.tip_counts[key] = n + 1
            self.toasts.show(TIPS[key], INFO, 2.2, 11)

    def _fish_screen(self, h: float = 0.0):
        f = self.fight
        x, z = f.fish_xz()
        if h == 0.0 and f.brain.state == "jump":
            ph = f.brain.jump_phase()
            h = 4 * f.brain.jump_height * ph * (1 - ph)
        p = self.cam.project(x, z, h)
        return (p[0], p[1]) if p else (self.cam.cx, self.cam.horizon + 20)

    def _on_fight_event(self, ev: str) -> None:
        f = self.fight
        x, z = f.fish_xz()
        if ev in tut.CARDS and self.card is None and self.tutorial.want(ev):
            self._open_card(ev, None if ev == "net_start" else "fish")
        elif ev == "hazard_enter":
            self.toasts.show(f"{f.in_hazard['name']}에 걸리려 해요! 반대로 당기세요", BAD, 1.5, 11)
        else:
            self._tip(ev)
        if ev == "telegraph:rush":
            self.sfx.play("splash_small", 0.7)
        elif ev == "telegraph:jump":
            self.sfx.play("bubbles", 0.8)
            if f.brain.lightning_cue:
                # 전설 '번개': 번개 섬광이 점프 박자
                self.lightning.strike(self.cam.horizon, self.cam.width)
        elif ev.startswith("phase:"):
            n = int(ev.split(":")[1])
            pos = self._fish_screen()
            self.toasts.show(f"페이즈 {n}/{len(f.brain.phases)} — {f.brain.phase_desc}", (255, 214, 90), 3.2, 11)
            self.sfx.play("roar", 1.0)
            self.sfx.play("impact", 0.8)
            self.screen_fx.great(self.screen_fx.map(pos))
            self.sparkles.burst(*pos, count=30, speed=1.4)
            self.shake_kick = 3.0
            lc = self.fish_cfg["legend"]
            self.game.slowmo(lc["phase_slowmo_real"], lc["phase_slowmo_scale"])
            if f.brain.dragon:
                self.toasts.show("용이 되었다!!", (255, 120, 80), 3.2)
        elif ev == "telegraph:turn":
            self.sfx.play("scrape", 0.8)
        elif ev == "action:rush":
            self.sfx.play("splash_small", 1.0)
            self._splash_at(x, z, 0.6)
        elif ev == "action:jump":
            self.jump_facing = -1 if f.fish_side() > 0 else 1
            self.sfx.play("splash", 0.7)
            self._splash_at(x, z, 0.8)
        elif ev == "jump_land":
            self.sfx.play("splash", 0.9)
            self._splash_at(x, z, 1.0)
        elif ev == "ink":
            self.ink_t = self.fish_cfg["fight"]["ink_sec"]
            self.sfx.play("splash_small", 0.5)
        elif ev == "bolt":
            self.toasts.show("아직 힘이 남았다! 다시 도망친다", BAD, 1.8, 11)
        elif ev == "exhausted":
            self.toasts.show("완전히 지쳤다! 끝까지 감으세요", GOOD, 2.0, 11)
        elif ev == "perfect":
            # 퍼펙트: 섬광 + 충격파 + 빛줄기 + 줌 펀치 + 큰 반짝임 + 슬로우 + 묵직한 타격음
            pos = self._fish_screen()
            self.sfx.play("perfect")
            self.sfx.play("impact", 0.9)
            self.sparkles.burst(*pos, count=40, speed=1.7)
            self.sparkles.burst(*pos, count=16, speed=0.6, ring=False)
            self.screen_fx.perfect(self.screen_fx.map(pos))
            self.popups.add("perfect", pos, f.perfect_streak)
            self.shake_kick = 2.5
            fc = self.fish_cfg["fight"]
            self.game.slowmo(fc["slowmo_real_sec"], fc["slowmo_scale"])
        elif ev == "good":
            # 그레잇: 작은 섬광 + 충격파 + 반짝임
            pos = self._fish_screen()
            self.sfx.play("great")
            self.sparkles.burst(*pos, count=16, speed=1.0)
            self.screen_fx.great(self.screen_fx.map(pos))
            self.popups.add("good", pos)
            self.shake_kick = 1.2
        elif ev in ("miss_early", "miss_late", "miss_none"):
            pos = self._fish_screen()
            self.sfx.play("miss")
            self.popups.add(ev, pos)
            self.screen_fx.miss(self.screen_fx.map(pos))
            self.shake_kick = 3.0
        elif ev == "creak":
            self.sfx.play("creak", 0.8)
        elif ev == "net_start":
            self.sfx.play("splash", 0.8)
            self.toasts.show("뜰채! " + NET_HINT, INFO, 1.6, 11)
        elif ev == "net_fail":
            self.sfx.play("flee")
            self.sfx.play("splash")
            self.toasts.show("뜰채 실패! 물고기가 거리를 벌린다", BAD, 2.0, 11)
            self._splash_at(x, z, 1.0)
        elif ev == "caught":
            pose, _ = f.net_pose()
            shown = self._display_fish(f.fish)
            self.landing = LandingCinematic(shown, f.result["size"], 240 + pose * 46)
            f.result["fish"] = shown
            self.end_t = 0.0
            self.catch_news = self.save.record_catch(f.result | {"perfects": f.perfects})
            self.game.save_now()
        elif ev.startswith("lost:"):
            self.save.record_loss()
            self.game.save_now()
            self.sfx.play("snap" if ev == "lost:snap" else "flee")
            self.sfx.play("lose", 0.8)
            self.end_t = 0.0
            self.shake_kick = 4.0 if ev == "lost:snap" else 0.0

    # ───────────────────────── 그리기 ─────────────────────────
    def draw(self, canvas: pygame.Surface) -> None:
        hour = self.clock.hour
        theme, weather = self.theme, self.weather
        pal = themed_palette(self.palette.sample(hour), theme, weather, self.lightning.flash, self.legend_k)
        cam, c, t, f = self.cam, self.cast, self.t, self.fight

        world.draw_sky(canvas, pal, cam)
        self.stars.draw(canvas, pal, cam, t)
        world.draw_celestial(canvas, pal, cam, hour, t, visible=weather == "clear")
        self.clouds.draw(canvas, pal, cam)
        self.lightning.draw(canvas)
        world.draw_mountains(canvas, pal, cam, theme["terrain"], t)
        amp = {"clear": 1.0, "rain": 1.25, "storm": 1.9}[weather] * (1.3 if theme.get("sea") else 1.0)
        self.water.draw(canvas, pal, t, hour, amp_mult=amp, show_reflection=weather == "clear")
        if theme.get("lamp"):
            world.draw_ship_lamp(canvas, pal, cam)
        if self.landing is not None:
            self.landing.draw(canvas, pal)
            return
        if f is None:
            sh = self.bite.shadow
            if sh is not None and self.bite.fish is not None:
                sh = dict(sh, glow=GLOW.get(self.bite.fish["rarity"]))
            draw_fish_shadow(canvas, pal, cam, sh, t)
        elif f.phase == "fight":
            if self.ink_t > 0:
                x, z = f.fish_xz()
                draw_ink(canvas, pal, cam, x, z, min(1.0, self.ink_t), t)
            elif not f.brain.dark:
                draw_fish_shadow(canvas, pal, cam, self._fight_shadow(), t)
        self.ripples.draw(canvas, pal, cam)
        self.bubbles.draw(canvas, pal)
        self.hazard_decor.draw(canvas, pal, cam, t, f.in_hazard if f is not None and f.phase == "fight" else None)
        self.ambient.draw(canvas, pal, self.clock.period()[0], weather, theme.get("sea", False), t)

        geo = self._rod_geo()
        tip = geo["tip"]

        if c.state == CastState.CHARGING:
            ang = c.aim_angle(cam.yaw)
            d = c.distance_for_power(c.power)
            landing_marker(canvas, pal, cam, math.sin(ang) * d, math.cos(ang) * d, t)

        hanging = c.state in (CastState.READY, CastState.CHARGING, CastState.SWING)
        if f is not None and f.phase in ("fight", "net"):
            self._draw_fight_line(canvas, pal, tip)
        elif not hanging and f is None:
            self._draw_line_and_bobber(canvas, pal, tip)

        if f is not None and f.phase == "fight" and f.brain.state == "jump":
            x, z = f.fish_xz()
            draw_jump(canvas, pal, cam, self._display_fish(f.fish), f.size_cm, x, z, f.brain.jump_phase(), self.jump_facing,
                      f.brain.jump_height)

        fg = theme["foreground"]
        if fg == "reeds":
            self.reeds.draw(canvas, pal, t, wind={"clear": 1.0, "rain": 1.4, "storm": 2.2}[weather])
        else:
            world.FOREGROUND[fg](canvas, pal, t)
        draw_rod(canvas, pal, geo, c.reel_angle)

        if hanging:
            bx, by = rod_tip_drop(tip, t)
            draw_line(canvas, pal, tip, (bx, by - 3), 0)
            draw_bobber(canvas, pal, bx, by, 7, floating=False)
        self.droplets.draw(canvas, pal)
        self.rain.draw(canvas, pal)
        if f is not None and f.phase == "fight":
            # 수면 위 행동 연출 (카메라 연출 전에 그려서 함께 확대됨)
            pos = self._fish_screen()
            p = cam.project(*f.fish_xz())
            sc = p[2] / 20 if p else 1.0
            self.gather.draw(canvas)
            if f.brain.state in ("tired", "fake_tired", "exhausted"):
                fight_fx.draw_tired_ring(canvas, pos, sc, t)
        self.sparkles.draw(canvas)
        # 가짜 FOV (줌·패닝·기울기)
        self.screen_fx.apply_camera(canvas)

        if f is not None:
            self._draw_fight_overlay(canvas, pal)
        else:
            label = f"{self.clock.label()} · {self.spot['name']} · {WEATHER_KO[weather]}"
            hud.draw_clock(canvas, pal, label, self.clock.fast, self.clock.fast_mult)
            if c.state == CastState.CHARGING:
                hud.draw_power_gauge(canvas, pal, c.power, c.distance_for_power(c.power))
            if c.state == CastState.LANDED:
                hud.text(canvas, f"찌 거리 {c.current_distance():.0f}m", (cam.width - 6, 30), pal["text"],
                         anchor="topright")
            sv = self.save.data
            hud.text(canvas, f"{sv['money']:,}원", (cam.width - 6, 4), (255, 228, 140), anchor="topright")
            bait = self.save.equipped("bait")["name"]
            hud.text(canvas, f"살림망 {len(sv['keepnet'])} · 미끼 {bait}", (cam.width - 6, 17), pal["text"],
                     anchor="topright")
            hint = HINTS[c.state]
            if hint:
                hud.draw_hint(canvas, pal, hint)
            hud.draw_look_arrows(canvas, pal, self.look_left, self.look_right, t)
        self.toasts.draw(canvas)
        if f is None and self.card is None:
            if not self.tutorial.is_seen("guide_cast") and c.state in (CastState.READY, CastState.CHARGING):
                tut.draw_guide(canvas, "guide_cast", t)
            elif not self.tutorial.is_seen("guide_wait") and c.state == CastState.LANDED:
                tut.draw_guide(canvas, "guide_wait", t)
        if self.card is not None:
            tut.draw_card(canvas, self.card["key"], self._card_focus(), self.card["t"])
        if self.help:
            tut.draw_help(canvas)
        hud.draw_cursor(canvas, self.mouse)

    def _rod_geo(self) -> dict:
        c, f = self.cast, self.fight
        if f is None or f.phase in ("caught", "lost"):
            return rod_geometry(c.aim, c.swing_deg + c.jerk_offset(), c.bend + self.bite.tip_pull,
                                c.rod_hand_offset())
        # 파이팅: 장력만큼 휘고, 끝이 물고기 쪽으로 끌려감. 우클릭이면 숙임.
        tension = f.tension
        dip = math.sin(math.pi * (f.dip_t / 0.35)) if f.dip_t > 0 else 0.0
        bend = 5 + tension * 0.24 + (math.sin(self.t * 31) * tension / 40 if tension > 60 else 0)
        pull_x = f.fish_side() * tension * 0.25
        swing = 10 - 24 * dip
        return rod_geometry(c.aim, swing + c.jerk_offset(), bend, (0, 2 * dip), pull_x=pull_x)

    def _fight_shadow(self) -> dict:
        f = self.fight
        b = f.brain
        x, z = f.fish_xz()
        heading = math.atan2(x, z)
        if b.state == "turn":
            heading += b.turn_dir * 1.2
        wag = {"rush": 22.0, "idle": 12.0, "telegraph": 14.0, "turn": 16.0, "recover": 8.0,
               "tired": 3.0, "fake_tired": 3.0, "charge": 0.0, "exhausted": 2.0}.get(b.state, 10.0)
        scale = 1.0 + 0.9 * b.signal_progress() if b.signal == "jump" else 1.0
        alpha = 0.0 if b.state == "jump" else 0.7 if b.state in ("tired", "fake_tired", "exhausted") else 1.0
        if f.fish["rarity"] == "legend":
            scale *= self.fish_cfg["legend"]["shadow_scale"] * 0.55
        return {"x": x, "z": z, "heading": heading, "alpha": alpha, "len": f.fish["shadow_len_m"],
                "scale": scale, "wag": wag, "glow": GLOW.get(f.fish["rarity"])}

    def _draw_fight_line(self, canvas, pal, tip) -> None:
        f, cam = self.fight, self.cam
        x, z = f.fish_xz()
        p = cam.project(x, z)
        if p is None:
            return
        sx, sy, s = p
        b = f.brain
        size = max(3.5, 0.36 * s)
        still = b.state == "charge"
        bob = 0.0 if still else math.sin(self.t * 9) * max(0.5, s * 0.01)
        # 줄 쏠림 (방향 전환 예고/진행)
        dx = 0.0
        if b.signal == "turn":
            dx = b.turn_dir * (6 + 22 * b.signal_progress()) + math.sin(self.t * 40) * 1.5
        elif b.state == "turn":
            dx = b.turn_dir * 22
        lf = f.line_frac
        color = pal["line"] if lf >= 0.5 else lerp_color(pal["line"], (235, 70, 55), (0.5 - lf) * 2)
        if lf < 0.25 and int(self.t * 8) % 2 == 0:
            color = (255, 90, 70)
        cracks = 0.0 if lf >= 0.5 else (0.5 - lf) * 2
        sag = max(0.0, (45 - f.tension) * 0.35) + 1
        draw_line(canvas, pal, tip, (sx, sy + bob - size * 0.25), sag, bias=0.6, dx=dx, color=color,
                  cracks=cracks, t=self.t)
        if f.phase == "fight":
            draw_bobber(canvas, pal, sx, sy + bob, size, floating=True, dip=0.55)

    def _draw_fight_overlay(self, canvas, pal) -> None:
        f, t = self.fight, self.t
        if f.phase != "fight":
            self.screen_fx.draw_edges(canvas)  # 섬광이 남아 있으면 마저 사라지게
        if f.phase == "net":
            pose, still = f.net_pose()
            draw_net_scene(canvas, pal, self._display_fish(f.fish), f.size_cm, pose, still, t, self.net_anim, self.mouse)
            fight_hud.draw_boss_bar(canvas, pal, f)
            hud.draw_hint(canvas, pal, NET_HINT)
            return
        if f.phase == "caught":
            draw_catch_cut(canvas, pal, f.result, self.end_t)
            fight_hud.draw_catch_info(canvas, f.result, self.end_t, self.catch_news)
            return
        if f.phase == "lost":
            fight_hud.draw_lose_panel(canvas, f, LOSE_REASONS[f.lose_reason], self.end_t)
            return
        self._draw_behavior_ui(canvas)
        self.popups.draw(canvas, self.screen_fx.map)
        self.screen_fx.draw_edges(canvas)
        fight_hud.draw_gauges(canvas, pal, f, t)
        fight_hud.draw_boss_bar(canvas, pal, f)
        fight_hud.draw_drag(canvas, pal, f)
        fight_hud.draw_distance(canvas, pal, f)
        hud.draw_hint(canvas, pal, HINTS[CastState.HOOKED])
        if self.debug:
            fight_hud.draw_debug(canvas, f)

    def _draw_behavior_ui(self, canvas) -> None:
        """물고기 머리 위 행동 아이콘 + 점프 판정 원."""
        f, b, t = self.fight, self.fight.brain, self.t
        mapped = self.screen_fx.map(self._fish_screen())
        inked = self.ink_t > 0 or b.dark
        sig = b.signal
        if sig in ("rush", "turn"):
            fight_fx.draw_behavior_icon(canvas, mapped, sig, b.signal_progress(), b.turn_dir, t)
        if sig == "turn" or b.state == "turn":
            amount = b.signal_progress() if sig == "turn" else 1.0
            fight_fx.draw_turn_chevrons(canvas, mapped, b.turn_dir, 0.4 + 0.6 * amount, t)
        elif b.state == "charge":
            prog = b.state_t / max(0.01, b.state_t + b.timer)
            fight_fx.draw_behavior_icon(canvas, mapped, "charge", prog, 0, t)
        elif b.state in ("tired", "fake_tired", "exhausted"):
            fight_fx.draw_behavior_icon(canvas, mapped, "tired", 0.0, 0, t)
        # 점프 판정 원: 바깥 원이 줄어들어 판정 원과 만나는 순간 = 정점
        jumping = b.state == "jump" and not b.jump_judged
        if (sig == "jump" and not inked and not f.pre_judged) or jumping:
            x, z = f.fish_xz()
            apex = self.cam.project(x, z, b.jump_height)
            if apex:
                total = b.cur_telegraph + b.jump_air / 2
                fc = self.fish_cfg["fight"]
                fight_fx.draw_jump_ring(canvas, self.screen_fx.map((apex[0], apex[1])), b.time_to_apex(), total,
                                        fc["perfect_window_sec"], fc["good_window_sec"], t)

    def _draw_line_and_bobber(self, canvas, pal, tip) -> None:
        c, cam = self.cast, self.cam
        p = cam.project(c.bx, c.bz, c.bh)
        if p is None:
            return
        sx, sy, s = p
        size = max(3.5, 0.36 * s)
        if c.state == CastState.FLIGHT:
            # 낚싯대 끝에서 출발하는 느낌이 나게 처음엔 화면 좌표를 섞는다
            k = smoothstep(c.flight_s / 0.3)
            start = rod_tip_drop(tip, self.t)
            sx = lerp(start[0], sx, k)
            sy = lerp(start[1], sy, k)
            size = lerp(7, size, k)
            draw_line(canvas, pal, tip, (sx, sy), 3 * (1 - c.flight_s))
            draw_bobber(canvas, pal, sx, sy, size, floating=False)
            return
        bob = 0.0
        dip = self.bite.dip if c.state in (CastState.LANDED, CastState.HOOKED) else 0.0
        if c.state == CastState.LANDED:
            # 살랑살랑: 위아래 + 좌우로 아주 조금
            bob = math.sin(self.t * 2.0) * max(0.5, s * 0.012)
            sx += math.sin(self.t * 1.3) * max(0.3, s * 0.006)
        if c.state == CastState.RETRIEVE or dip > 0.5:
            sag = 3  # 팽팽
        else:
            sag = 10 + abs(tip[0] - sx) * 0.04
        draw_line(canvas, pal, tip, (sx, sy + bob - size * 0.5 * (1 - dip)), sag, bias=0.6)
        draw_bobber(canvas, pal, sx, sy + bob, size, floating=True, dip=dip)
