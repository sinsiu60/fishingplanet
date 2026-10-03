"""1인칭 낚시 장면: 캐스팅 → 입질 → 챔질 → 파이팅 → 뜰채 → 획득."""
import math
import random

import pygame

from src.core.config import game_config, load_json
from src.core.fonts import get_font
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
from src.render.dragon import DragonTransform, Embers, draw_dragon_jump, draw_dragon_shadow
from src.render.landing import LandingCinematic
from src.render.palette import Palette
from src.render.rod import draw_rod, rod_geometry
from src.render.screen_fx import ScreenFX
from src.render.weather_fx import Ambient, Fog, Lightning, Rain, themed_palette
from src.scene.base import Scene
from src.ui import fight_fx, fight_hud, hud, pattern_fx, signal_slots
from src.ui import tutorial as tut


def float_name(tier: int) -> str:
    """특수 찌 티어 → 이름."""
    return next((f["name"] for f in load_json("floats.json")["floats"] if f["tier"] == tier), "특수 찌")

HINTS = {
    CastState.READY: "좌클릭 유지: 던지기   오른쪽 버튼: 지도·상점·의뢰·도감",
    CastState.CHARGING: "놓으면 던지기   우클릭: 취소",
    CastState.SWING: "",
    CastState.FLIGHT: "",
    CastState.LANDED: "좌클릭: 챔질(쑥!)·저킹   누르고 있기: 감기   우클릭: 회수   화면 끝: 둘러보기",
    CastState.RETRIEVE: "줄 감는 중...",
    CastState.HOOKED: "좌클릭 유지: 감기   우클릭: 숙이기   Q/E·휠: 드랙   마우스: 버티기   H: 도움말",
}
GOOD = (140, 240, 150)
BAD = (255, 150, 130)
INFO = (255, 235, 170)
LOOK_STATES = (CastState.READY, CastState.LANDED)
WEATHERS = ["clear", "rain", "storm", "fog"]
GLOW = {"rare": (150, 210, 255), "legend": (255, 215, 100)}
DRAGON_LOOK = {"colors": {"body": [200, 40, 40], "belly": [255, 214, 110], "fin": [255, 170, 40],
                          "stripe": [255, 230, 140]},
               "shape": {"height": 0.13, "whiskers": True, "dorsal": "crest", "tail": "fork", "pattern": "spots"}}

# 튜토리얼 카드를 본 뒤 한 번 더 짧게 상기시킨다 (DESIGN.md 4장)
TIPS = {
    "telegraph:rush": "빛이 줄을 타고 손에 닿으면 돌진! 그 전에 Q로 드랙을 낮추세요",
    "telegraph:jump": "그림자가 커진다 = 점프! 원이 겹치는 순간 우클릭",
    "telegraph:turn": "줄이 쏠린다 = 방향 전환! 꺾는 순간 반대쪽으로 확 슬라이드",
    "telegraph:leap": "하늘색 원 = 몸털기! 원이 겹칠 때 화살표 쪽으로 슬라이드",
    "action:charge": "멈췄다 = 힘 모으기! 지금 확 감으세요",
    "tired": "지쳤다! 드랙을 올리고(E) 크게 감으세요",
    "fake_tired": "기포가 계속 올라온다 = 가짜 지침! 돌진 대비",
    "telegraph:lure": "등불만 번쩍 = 가짜 신호! 기포·판정 원이 없으면 속지 마세요",
}
# 소리 자막 (설정 '소리 자막'): 예고 소리를 글자로도 보여준다
CAPTIONS = {"telegraph:rush": "웅— 줄이 울린다 (돌진)", "telegraph:jump": "보글보글 — 기포 (점프)",
            "telegraph:leap": "촵촵 — 몸털기", "telegraph:turn": "스윽 — 긁힘 (방향 전환)",
            "action:charge": "쿵 — 힘 모으기", "telegraph:lure": "찰랑 — 등불 (가짜)",
            "telegraph:shake": "드르르 — 팽팽한 줄 떨림 (머리 흔들기)", "telegraph:dive": "꾸르륵 — 가라앉음 (잠수)",
            "telegraph:surface": "쉬이익 — 물살 (수면 질주)", "telegraph:reverse": "스르르 — 줄 처짐 (역주행)",
            "telegraph:twist": "끼릭끼릭 — 줄 꼬임 (비틀기)", "telegraph:chain": "둥 둥 둥 — 콤보",
            "telegraph:hide": "꿀렁 — 물을 빨아들임 (숨기)", "telegraph:pump": "끼익 끼익 — 낚싯대 박자 (펌핑)",
            "telegraph:thrash": "보글보글보글 — 큰 기포 (공중 몸부림)", "telegraph:bite": "꿀렁 — 물을 빨아들임 (물어뜯기)",
            "telegraph:dual": "두 소리가 겹친다 — 이중 패턴", "hide_peek": "뽀글 — 고개를 내밀었다 (지금 감기)"}
FORCE_PATTERNS = ("shake", "dive", "surface", "reverse", "twist", "chain", "hide", "pump", "thrash", "bite", "fake", "dual")
PATTERN_EVENTS = ("twist_snap", "twist_turn", "combo_break", "combo_ok", "pump_hit", "pump_miss", "hide_peek",
                  "double_perfect", "thrash_second_miss", "stiff", "dual_ok", "fake_tired")
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
        self.training = None  # 훈련 수조 (src/scene/training.py, 31장 C5)
        self.sfx = game.sfx
        self.toasts = hud.Toasts()
        self.ripples = Ripples()
        self.droplets = Droplets()
        self.bubbles = Bubbles()
        self.sparkles = Sparkles()
        from src.ui.pattern_vfx import PatternVFX
        self.pvfx = PatternVFX()  # 패턴 판정 연출 (색 입자·고리·나선)
        import time as _time
        from src.fishing.lure import SurfaceSigns
        # 수면 징후 (U7): 전용 난수 (씨앗 = 시계, 다른 난수 흐름을 건드리지 않게)
        self.signs = SurfaceSigns(random.Random(int(_time.time() * 1000) + 7))
        self.sign_fx_t = 0.0
        self.recast_told = False
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
        self.fog = Fog(canvas.get_width(), canvas.get_height())
        self.lightning = Lightning()
        self.ambient = Ambient(canvas.get_width(), canvas.get_height(), self.cam.horizon)
        from src.audio.ambience import Ambience
        self.ambience = Ambience(self.sfx)  # 환경음: 바탕 + 무작위 조각 + 날씨 + 천둥 시간차 (32장 S7)
        self.legend_on = False   # 전설 등장 중 (BGM·색감·금빛 테두리)
        self.legend_k = 0.0
        self.dragon_k = 0.0      # '등용' 3페이즈: 진홍빛 하늘
        self.dragon_fx: DragonTransform | None = None
        self.embers = Embers()
        self.flick_hist: list[tuple[float, int]] = []   # (시간, 마우스 x) — 슬라이드 감지
        self.flick_cd = 0.0
        self.flick_cfg = self.fish_cfg["flick"]
        self.catch_news: dict | None = None
        self.ink_t = 0.0
        self.fake_bubble_t = 0.0
        self.fight: Fight | None = None
        self.missed_signals: list[str] = []   # 결과 화면: 놓친 신호 (31장 C5)
        self.mastery_ups: list[str] = []      # 결과 화면: 숙련도가 오른 패턴
        self.landing: LandingCinematic | None = None   # 뜰채 성공 → 획득 컷 사이 연출
        self.end_t = 0.0             # 결과 화면 경과 시간
        self.net_anim = 0.0
        self.jump_facing = -1
        self.fx_t = 0.0
        self.tip_counts: dict[str, int] = {}
        self.debug = False
        from src.platform.gesture import Controls
        self.ctl = Controls(load_json("fishing_config.json")["controls"])  # 낚싯대 상하·연타·원·순간 최저 드랙·루어
        self.settings = game.settings
        self.tutorial = tut.Tutorial(self.settings)
        self.card: dict | None = None    # 튜토리얼 카드 (표시 중엔 게임 정지)
        self.help = False                # H 도움말 (표시 중엔 게임 정지)
        self.slack_t = self.red_t = 0.0
        self.shake_on = self.settings.get("screen_shake")
        self.screen_fx.enabled = self.shake_on
        self.shake_kick = 0.0
        from src.audio.fight_audio import FightAudio
        self.fight_audio = FightAudio(self.sfx)  # 상태 연동 연속음 (32장 S4)
        self.fight_audio.reel.prepare(self._reel_tier())  # 합성 릴 루프 (32-16 Z2) — 이 낚시터 공간·장착 릴 티어
        from src.audio.signal_audio import SignalAudio
        self.signal_audio = SignalAudio(self.sfx, lambda: self.settings.get("signal_sound"),
                                        lambda: self.settings.get("signal_mode"),
                                        lambda: self.save.data.get("pattern_mastery", {}) if self.save else None)  # 신호 6계열 (S5, 모드 N2)
        self.cast_far = self.fish_cfg["cast"]["max_distance"]  # 소리 거리 감쇠 기준
        self.cast_loops: dict[str, str | None] = {"charge": None, "line": None}
        self.captions = None     # [글자, 남은 시간] 소리 자막
        self.t = 0.0
        self.mouse = (canvas.get_width() // 2, canvas.get_height() // 2)
        self.look_left = self.look_right = False
        self.idle_ripple_t = 0.0
        self.wake_t = 0.0
        if self.tutorial.want("welcome"):
            self._open_card("welcome", None)
        # 확장 전 세이브로 이미 '등용'을 잡았다면: 새 대륙 소식을 한 번 보여준다 (첫 업데이트에서)
        self.voyage_pending = self.save.data["flags"].pop("voyage_pending", False)

    def _set_spot(self, spot_id: str) -> None:
        self.spot_id = spot_id
        self.spot = self.spots[spot_id]
        self.theme = self.spot["theme"]
        self.hazard_decor = world.HazardDecor(self.spot["hazards"])
        self.screen_fx.sway = self.theme.get("sway", 0)
        self.game.sfx.set_space(spot_id)  # N5: 낚시터 잔향·먹먹함 (공간별로 미리 구운 소리)
        if hasattr(self, "fight_audio"):
            self.fight_audio.reel.prepare(self._reel_tier())  # 합성 릴 루프도 이 공간 버전으로 (Z2)

    def _reel_tier(self) -> str:
        """장착한 릴 티어 → 릴 소리 음색 (T1 나무 / T2~T5 보통 / T6~T8 수정)."""
        from src.audio.reel_audio import tier_of
        save = getattr(self, "save", None)
        return tier_of(save.gear_tier("reel")) if save is not None else "mid"

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
        self.save.data["continent"] = self.spot.get("continent", "sharmion")
        self._advance_hours(1.0)
        self.weather_sys.reroll_upcoming(self.spot["weather"])
        self.toasts.show(f"{self.spot['name']}에 도착했다", GOOD, 2.0)
        if self.float_warning():
            self.toasts.show(self.float_warning(), BAD, 3.0, 11)
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
                name = sp["name"] if not sp.get("secret") else "숨겨진 장소"
                self.toasts.show(f"새 낚시터 '{name}'을(를) 열 수 있어요! (M: 지도)", GOOD, 3.5, 11)  # 소리 없이 (N3)
                return

    @property
    def touch(self) -> bool:
        return self.game.input.kind == "touch"

    def touch_context(self) -> dict:
        """터치 버튼 배치에 필요한 지금 상황 (src/platform/touch_ui.py)."""
        f, c = self.fight, self.cast
        fighting = f is not None and f.phase == "fight"
        overlay = self.card is not None or self.help
        items = []
        if fighting:
            for slot, iid, name in ((1, "repair_spool", "실타래"), (2, "calm_charm", "잔잔한 물")):
                n = self.save.consumable_count(iid)
                if n and not f.consumable_used:
                    items.append((slot, name, n))
        free = not overlay and self.landing is None
        ending = f is not None and f.phase in ("caught", "lost")  # 결과 화면: 탭하면 넘어가니 버튼은 숨김
        return {"fight": fighting, "overlay": overlay, "horizon": self.cam.horizon,
                "can_look": free and f is None and c.state in LOOK_STATES,
                "show_pause": free and not ending and not fighting,  # 파이팅 중 메뉴 숨김 (뒤로 가기로 멈춤, 31장 C6)
                "show_bag": free and self.can_open_menus(),
                "can_retrieve": free and f is None and c.state == CastState.LANDED,
                "lure": free and f is None and c.state == CastState.LANDED and self.bite.state == BiteState.WAIT,
                "items": items, "drag": (f.drag, f.drag_steps) if fighting else None,
                "safe_x": self.game.screen.safe_x}

    def _cycle_debug(self, key: str) -> None:
        """F3 물고기 고정 / F4 낚시터 / F5 날씨 / F6 상자 지급 (테스트용)."""
        if key == "F3":
            self.force_i = self.force_i + 1 if self.force_i + 1 < len(self.all_fish) else -1
            name = self.all_fish[self.force_i]["name"] if self.force_i >= 0 else "없음 (자연 출현)"
            self.toasts.show(f"[테스트] 물고기 고정: {name}", INFO, 1.5, 11)
        elif key == "F4":
            i = (self.spot_ids.index(self.spot_id) + 1) % len(self.spot_ids)
            self._set_spot(self.spot_ids[i])
            self.toasts.show(f"[테스트] 낚시터: {self.spot['name']} (해금 무시)", INFO, 1.5, 11)
        elif key == "F6":
            from src.save import treasure
            self.debug_chest = (getattr(self, "debug_chest", -1) + 1) % len(treasure.GRADES)
            grade = treasure.GRADES[self.debug_chest]
            treasure.give_chest(self.save, grade)
            self.toasts.show(f"[테스트] {treasure.grade_info(grade)['name']} 상자 지급 (C: 열기)", INFO, 1.5, 11)
        elif key == "F5":
            w = self.weather_sys
            w.current = WEATHERS[(WEATHERS.index(w.current) + 1) % len(WEATHERS)]
            self.toasts.show(f"[테스트] 날씨: {WEATHER_KO[w.current]}", INFO, 1.5, 11)

    def _quest_events(self, qr) -> None:
        """의뢰 진행 알림: 실패는 작게, 완료는 보상과 함께."""
        for ev in qr.events:
            if ev == "quest_fail":
                pass  # N3: 낚시 화면에선 의뢰 소리 없음 (화면 알림만)
            elif ev == "quest_done":
                it = next((x for x in qr.items if x[1] == "done" and len(x) > 3 and not x[3].get("_shown")), None)
                if it is not None:
                    got = it[3]
                    got["_shown"] = True
                    from src.save.quests import reward_text
                    self.toasts.show(f"의뢰 완료! {reward_text(it[0]['reward'])}", (255, 214, 90), 3.0, 11)  # 소리 없이 (N3)
        qr.events.clear()

    def _record_mutation(self, f, muts: list) -> None:
        """변이 포획: 살림망 표시·쌍둥이 두 번째·각성 소재·변이 도감과 수집 보상."""
        from src.fishing import mutation
        from src.save.save_game import spot_continent
        net = self.save.data["keepnet"]
        net[-1]["mut"] = list(muts)
        if f.result.get("twin"):
            # 쌍둥이: 같은 종 한 마리 더 (크기는 조금 다르게, 도감 횟수도 +1)
            twin = dict(net[-1], size=round(f.result["size"] * random.uniform(0.9, 1.05), 1))
            net.append(twin)
            self.save.data["dex"][f.fish["id"]]["count"] += 1
            self.save.data["stats"]["catches"] += 1
            self.toasts.show("쌍둥이! 두 마리를 함께 낚았다", (150, 255, 200), 2.4, 11)
        if "awake" in muts:
            mats = self.save.data["materials"]
            cont = spot_continent(f.fish["spot"])
            n = mutation.cfg()["kinds"]["awake"]["material_add"]
            mats[cont] = mats.get(cont, 0) + n
        st = self.save.data["stats"]
        st["mutations_caught"] = st.get("mutations_caught", 0) + 1
        for rw in mutation.record(self.save, f.fish["id"], muts):
            self.toasts.show(f"변이 도감 {rw['count']}종 달성! 보상: {rw['name']}", (255, 214, 90), 3.4, 11)  # 소리 없이 (N3)

    def _cycle_mutation(self) -> None:
        """[테스트] F10: 다음 물고기 변이 강제 지정 순환 (없음 → 7종 → 거대+교활)."""
        from src.fishing import mutation
        opts = [None] + [[m] for m in mutation.ORDER] + [["giant", "cunning"]]
        self.force_mut_i = (getattr(self, "force_mut_i", 0) + 1) % len(opts)
        self.force_mut = opts[self.force_mut_i]
        name = mutation.label(self.force_mut) if self.force_mut else "없음 (자연 출현)"
        self.toasts.show(f"[테스트] 다음 물고기 변이: {name}", INFO, 1.5, 11)

    def _force_pattern(self) -> None:
        """[테스트] F9: 신규 패턴을 차례로 지금 바로 발동 (파이팅 중)."""
        f = self.fight
        if f is None or f.phase != "fight":
            self.toasts.show("[테스트] F9는 파이팅 중에 패턴을 발동해요", INFO, 1.5, 11)
            return
        self.force_pat_i = (getattr(self, "force_pat_i", -1) + 1) % len(FORCE_PATTERNS)
        pid = FORCE_PATTERNS[self.force_pat_i]
        f.brain.force_pattern(pid)
        self.toasts.show(f"[테스트] 패턴 발동: {pattern_fx.action_name(pid)}", INFO, 1.2, 11)

    def _open_card(self, key: str, focus: str | None) -> None:
        self.card = {"key": key, "focus": focus, "t": 0.0}

    def _open_signal_card(self, key: str) -> None:
        """신호 첫 만남: 예고 순간 완전히 멈추고 카드 → 닫으면 바로 재개, 그 첫 예고는 시간 2배 (31장 C5)."""
        self._open_card(key, None)
        b = self.fight.brain if self.fight is not None else None
        if b is not None and b.state == "telegraph":
            b.timer += b.cur_telegraph
            b.cur_telegraph *= 2

    def _card_focus(self):
        focus = self.card["focus"]
        if focus == "gauge":
            sx = self.game.screen.safe_x
            if self.touch and self.settings.get("touch_left"):
                return (self.cam.width - self.GAUGE_W - sx + 14, 114)
            return (14 + sx, 114)
        if focus == "fish" and self.fight is not None:
            return self._fish_screen()
        return None

    # ───────────────────────── 입력 ─────────────────────────
    def handle_action(self, a) -> None:
        """입력 행동 (src/platform/input.py). PC: 좌클릭=primary, 우클릭=secondary, 휠=scroll, Q/E=drag 등."""
        f = self.fight
        if a.name == "primary_up":
            self.cast.release(self.cam.yaw)
            return
        if self.help:
            if a.any_press or a.name == "help":
                # 1쪽(조작·기존 신호) → 2쪽(신규 패턴, 하나라도 봤으면) → 닫기
                if getattr(self, "help_page", 0) == 0 and self.save.data.get("patterns_seen"):
                    self.help_page = 1
                else:
                    self.help = False
            return
        if self.card is not None:
            if a.any_press and self.card["t"] > 0.35:
                self.card = None
            return
        if self.training is not None and self.training.handle(a):
            return
        n = a.name
        if n == "item":
            if f is not None and f.phase == "fight":
                self._use_fight_item("repair_spool" if a.value == 1 else "calm_charm")
        elif n == "help":
            self.help = True
            self.help_page = 0
        elif n == "back":
            if self.landing is None:
                if f is None or f.phase not in ("fight", "net"):
                    self.sfx.play("ui_click")  # N3: 파이팅 중엔 UI 소리 없음
                from src.scene.pause import PauseScene
                self.game.scenes.push(PauseScene(self.game, self))
        elif n == "menu":
            if a.value == "bag":
                if self.can_open_menus():
                    from src.scene.quick_menu import QuickMenuScene
                    self.sfx.play("ui_click")
                    self.game.scenes.push(QuickMenuScene(self.game, self))
            elif a.value in ("dex", "quests"):
                if self.fight is None:
                    self.open_menu(a.value)
            elif self.can_open_menus():
                self.open_menu(a.value)
        elif n == "debug":
            if a.value in ("F3", "F4", "F5", "F6"):
                if f is None and self.fish_cfg.get("debug_keys"):
                    self._cycle_debug(a.value)
            elif a.value == "F11":
                if self.fish_cfg.get("debug_keys") or load_json("mobile_config.json").get("debug_build"):
                    from src.save import quests
                    quests.force_new_day(self.save, quests.spot_cont(self.spot_id))
                    self.toasts.show("[테스트] 의뢰를 새로 받았어요 (J: 게시판)", INFO, 1.5, 11)
            elif a.value == "F10":
                if self.fish_cfg.get("debug_keys") or load_json("mobile_config.json").get("debug_build"):
                    self._cycle_mutation()
            elif a.value == "F9":
                if self.fish_cfg.get("debug_keys") or load_json("mobile_config.json").get("debug_build"):
                    self._force_pattern()
            elif a.value == "F1":
                self.debug = not self.debug
            elif a.value == "F2":
                self.shake_on = not self.shake_on
                self.screen_fx.enabled = self.shake_on
                self.settings.set("screen_shake", self.shake_on)
                self.toasts.show("화면 연출(흔들림·줌) " + ("켬" if self.shake_on else "끔"), INFO, 1.2, 11)
        elif n == "time_fast":
            self.clock.fast = not self.clock.fast
        elif n == "drag":
            if f:
                f.change_drag(a.value)
        elif n == "scroll":
            if f:
                f.change_drag(1 if a.value > 0 else -1)
        elif n == "flick":
            if f is not None and f.phase == "fight":
                self.sfx.play("sfx_cast_swing", 0.3)  # 휘두르는 소리 (판정과 상관없이)
                f.flick(a.value)
        elif n == "reel_tap":
            if f is not None and f.phase == "fight":
                self.ctl.tap(self.t)  # 터치: 릴 패드를 누를 때마다
        elif n == "primary":
            if self._side_menu_click(a.pos):
                return
            if not self.touch and f is not None and f.phase == "fight":
                self.ctl.tap(self.t)  # PC: 파이팅 중 좌클릭 하나하나가 연타
            self._left_click()
        elif n == "secondary":
            self._right_click()

    # ───────────────────────── 메뉴 · 저장 ─────────────────────────
    def _side_menu_on(self) -> bool:
        """PC 오른쪽 메뉴 버튼: 파이팅·던지는 중·카드·도움말·훈련 수조에선 숨김."""
        return (not self.touch and self.fight is None and self.card is None and not self.help
                and self.landing is None and self.training is None
                and self.cast.state in (CastState.READY, CastState.LANDED, CastState.RETRIEVE))

    def _side_menu_rects(self):
        from src.ui import side_menu
        return side_menu.layout(self.cam.width, self.cam.height, self.hud_inset)

    def _side_menu_click(self, pos) -> bool:
        if not self._side_menu_on():
            return False
        from src.ui import side_menu
        k = side_menu.hit(self._side_menu_rects(), pos)
        if k is None:
            return False
        if k == "help":
            self.sfx.play("ui_click")
            self.help = True
            self.help_page = 0
        elif k == "settings":
            self.sfx.play("ui_click")
            from src.scene.settings_scene import SettingsScene
            self.game.scenes.push(SettingsScene(self.game))
        else:
            self.open_menu(k)
        return True

    def can_open_menus(self) -> bool:
        return self.fight is None and self.cast.state in (CastState.READY, CastState.LANDED, CastState.RETRIEVE)

    def open_menu(self, which: str, tab: str | None = None) -> None:
        self.sfx.play("ui_click")
        if which == "shop":
            if not self.can_open_menus():
                return
            # 상점에 가면 줄은 걷는다
            self.bite.stop()
            self.cast.reset()
            from src.scene.shop import ShopScene
            self.game.scenes.push(ShopScene(self.game, self, tab=tab))
        elif which == "dex":
            from src.scene.dex import DexScene
            self.game.scenes.push(DexScene(self.game, self))
        elif which == "map":
            if not self.can_open_menus():
                return
            from src.scene.map_scene import MapScene
            self.game.scenes.push(MapScene(self.game, self))
        elif which == "chest":
            if not self.can_open_menus():
                return
            from src.scene.chest_scene import ChestScene
            self.game.scenes.push(ChestScene(self.game, self))
        elif which == "quests":
            if self.fight is not None:
                return
            from src.scene.quest_board import QuestBoardScene
            self.game.scenes.push(QuestBoardScene(self.game, self))
        self.fight_audio.stop()
        self.signal_audio.stop()

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
            heavy = sum(self.bite.fish["size_cm"]) / 2 >= 100 if self.bite.fish else False
            self.sfx.play("sfx_hook_heavy" if heavy else "sfx_hook_success")  # 딱 + 쿵 + 팅 + 물보라 (큰 물고기는 더 깊게)
            self.sfx.duck("hook")
            self.toasts.show("챔질 성공!", GOOD, 1.0)
            self._splash_at(c.bx, c.bz, big=0.6)
            self._start_fight()
        elif result == "scared":
            self.sfx.play("sfx_hook_success", 0.4)
            self.sfx.play("sfx_flee")
            self.toasts.show("물고기가 놀라 도망갔다...", BAD, 2.4)
        else:
            self.sfx.play("sfx_cast_swing", 0.4)
            if self.bite.state == BiteState.MISSED:
                self.toasts.show("미끼가 없어요. 우클릭으로 회수", INFO, 2.0, 11)

    def _right_click(self) -> None:
        if self.fight is not None:
            if self.fight.phase == "fight":
                self.sfx.play("sfx_cast_swing", 0.35)
                self.fight.dip()
            return
        if self.cast.state == CastState.LANDED:
            self.bite.stop()
        self.cast.cancel_or_retrieve()

    # ───────────────────────── 파이팅 시작·끝 ─────────────────────────
    def _start_fight(self) -> None:
        from src.core import gcwatch
        gcwatch.settle()  # 낚시터 장면 객체를 얼려 파이팅 중 GC 부담을 줄인다 (v0.8.10)
        c = self.cast
        fish = self.bite.fish
        size = roll_size(fish, self.bite.cast_distance)
        # 변이 (U5): 챔질 순간 굴림 (테스트: F10 강제 지정)
        from src.fishing import mutation
        force = getattr(self, "force_mut", None)
        train = self.training is not None
        muts = [] if train else mutation.roll(self.save, fish, self.weather, force=force if force else None,
                             chance_mult=self.bite.sign_mods.get("mutation_mult", 1.0) if self.bite.sign_mods else 1.0)
        if muts:
            fish = mutation.apply(fish, muts)
            if "giant" in muts:
                size = round(size * mutation.cfg()["kinds"]["giant"]["size_mult"], 1)
        angle = math.atan2(c.bx, c.bz)
        self.fight = Fight(fish, size, c.current_distance(), angle, self.cam.yaw, gear=self.save.fight_gear(self.clock.period()[0]),
                           hazards=[] if train else self.spot["hazards"], gimmick=None if train else self.current_gimmick(),
                           float_need=self.save.float_need(fish, self.spot), float_tier=self.save.float_tier(),
                           touch_lead=load_json("mobile_config.json")["touch_lead_sec"] if self.touch else 0.0)
        self.toasts.items.clear()
        self.toasts.sink = self._say  # 파이팅 중 글자 슬롯 하나 (31장)
        # 패턴 숙련도·연속 실패 보조 (31장 C5) — 세이브 값을 두뇌가 바로 쓴다
        self.fight.brain.mastery = self.save.data.setdefault("pattern_mastery", {})
        self.fight.brain.fail_streak = self.save.data.setdefault("pattern_fail_streak", {})
        from src.save.settings import TELE_MULTS
        self.fight.brain.access_mult = TELE_MULTS[self.settings.get("tele_mult")]  # 접근성 예고 배율 (31장 C6)
        self.missed_signals: list[str] = []   # 결과 화면: 놓친 신호
        self.mastery_ups: list[str] = []      # 결과 화면: 숙련도가 오른 패턴
        lat = load_json("mobile_config.json")["pump_latency_sec"] if self.touch else 0.0
        # 오디오 지연 보정 (설정 → 소리, 32장 S3): 소리가 늦게 들리는 기기면 박자 판정을 그만큼 늦춘다
        self.fight.input_latency = lat + self.settings.get("audio_offset_ms") / 1000
        self.fight.lure_info = {"bite": self.bite.lure_bite, "used": set(self.bite.lure_used),
                                "profile": getattr(self.bite, "lure_profile", None)}
        from src.save.quests import QuestRun
        self.quest_run = QuestRun(self.save, self.fight, fish["id"], self.spot_id, self.weather, self.clock.period()[0])
        if muts:
            kinds = mutation.cfg()["kinds"]
            col = tuple(kinds[muts[0]]["color"])
            self.toasts.show(f"{kinds[muts[0]]['name']} 변이", col, 3.2, 11)
            # 변이 등장은 소리 없이 화면 연출만 (N3, 강조 등급 '없음')
            self.sparkles.burst(*self._fish_screen(), count=16, speed=0.9)
        for g in sorted(self.fight.gim.kinds(self.fight.brain)):
            key = f"gimmick:{g}"
            if self.card is None and self.tutorial.want(key):
                self._open_card(key, "gauge")
        from src.fishing.fight import fish_gear_tier
        need_rod = fish_gear_tier(fish)
        if not train and self.save.gear_tier("rod") < need_rod and fish["rarity"] != "common":
            # 낚싯대가 약하면 울렁임이 커진다 — 왜 어려운지 알려 준다
            self.toasts.show("버겁다!", BAD, 2.6, 11)
        if fish["rarity"] == "legend":
            self.toasts.show("전설!", (255, 214, 90), 3.0)
            self.sfx.play("sfx_legend_appear", 1.0, haptic="legend")  # 깊은 드론 + 심장박동 + 수면 울림
            self.shake_kick = 2.5
        if self.fight.brain.sound_only:
            self.toasts.show("소리로!", (200, 220, 255), 3.0, 11)
        self.ink_t = 0.0
        self.ctl.reset()
        self.bite.shadow = None
        self.end_t = 0.0
        self.slack_t = self.red_t = 0.0
        if self.tutorial.want("fight_intro"):
            self._open_card("fight_intro", "gauge")

    def _end_fight(self) -> None:
        last = self.fight.result if self.fight is not None else None
        if self.fight is not None and load_json("fishing_config.json").get("debug_keys"):
            # 디버그 빌드: 파이팅 로그를 세이브 폴더/fight_logs/날짜.jsonl 에 (tools/fight_log.py read 로 분석)
            from src.core.paths import save_dir
            self.fight.log.spot = self.spot_id
            self.fight.log.save(str(save_dir() / "fight_logs"))
        self.fight = None
        self.landing = None
        self.dragon_fx = None
        self._check_new_spots()
        if last and last["fish"]["id"] == "dragon_carp" and not self.save.data.get("ending_seen"):
            self.save.data["ending_seen"] = True
            self.game.save_now()
            from src.scene.ending import EndingScene
            self.game.scenes.push(EndingScene(self.game, self))
        elif last and last["fish"]["id"] == "orsiel" and not self.save.data["flags"].get("final_ending_seen"):
            self.save.data["flags"]["final_ending_seen"] = True
            self.game.save_now()
            from src.scene.ending import EndingScene
            self.game.scenes.push(EndingScene(self.game, self, kind="final"))
        self.screen_fx.reset()
        self.bite.stop()
        self.cast.reset()
        self.game.screen.shake = (0, 0)

    # ───────────────────────── 로직 (60틱 고정) ─────────────────────────
    def update(self, dt: float) -> None:
        if getattr(self, "voyage_pending", False) and self.game.scenes.current is self:
            self.voyage_pending = False
            from src.scene.voyage import VoyageScene
            self.game.scenes.push(VoyageScene(self.game, self))
            return
        if self.card is not None or self.help:
            # 튜토리얼 카드·도움말: 게임 정지 (예고 시간도 흐르지 않음)
            if self.card is not None:
                self.card["t"] += dt
            mx, my = self.game.input.pointer_raw
            self.mouse = (int(clamp(mx, 0, self.cam.width - 1)), int(clamp(my, 0, self.cam.height - 1)))
            self.fight_audio.stop()
            self.signal_audio.stop()
            self._cast_loop("charge", None)
            self._cast_loop("line", None)
            self.game.screen.shake = (0, 0)
            return
        self.t += dt
        self.ctl.begin_tick()
        self.clock.update(dt)
        self.clouds.update(dt)
        self._update_weather(dt)
        self.ripples.update(dt)
        self.droplets.update(dt)
        self.bubbles.update(dt)
        self.sparkles.update(dt)
        self.pvfx.update(dt)
        self.popups.update(dt)
        self.toasts.update(dt)
        self.toasts.sink = self._say if self._fight_text_mode() else None
        self.sig_dim_t = max(0.0, getattr(self, "sig_dim_t", 0.0) - dt)
        self.signal_audio.update(dt, self.fight if self.fight is not None and self.fight.phase == "fight" else None)
        self._rush_audio()
        fighting = self.fight is not None and self.fight.phase in ("fight", "net")
        if not fighting:  # N5 거리감: 파이팅 중엔 fight_audio 가 물고기 거리로, 그 밖엔 찌(루어)까지 거리로
            self.sfx.fish_dist = min(1.0, self.cast.current_distance() / max(1.0, self.cast_far)) \
                if self.cast.state != CastState.READY else 0.3
        if fighting != getattr(self, "_amb_fight", False):
            self._amb_fight = fighting
            self.sfx.set_base_duck("fight" if fighting else None)  # 파이팅 중 환경음 −4dB
            # 동시 재생 한도 (N3): 일반 파이팅 3 (주인공 1 + 보조 2) / 전설 4, 파이팅 밖은 없음
            legend = fighting and self.fight.fish.get("rarity") == "legend"
            self.sfx.set_budget(("legend" if legend else "fight") if fighting else None)
        self.drag_seen_t = max(0.0, getattr(self, "drag_seen_t", 0.0) - dt)
        signal_slots.configure(self.settings)
        if self.captions:
            self.captions[1] -= dt
            if self.captions[1] <= 0:
                self.captions = None
        self.net_anim = max(0.0, self.net_anim - dt)

        mx, my = self.game.input.pointer_raw
        w = self.cam.width
        self.mouse = (int(clamp(mx, 0, w - 1)), int(clamp(my, 0, self.cam.height - 1)))

        # 둘러보기: 대기 중에만. PC = 화면 좌우 끝에 마우스 / 터치 = 하늘을 좌우로 끌기
        edge = self.cam_cfg["edge_px"]
        can_look = self.cast.state in LOOK_STATES
        if self.touch:
            self.look_left = self.look_right = False
            d = self.game.input.consume_look()
            if can_look and d:
                k = load_json("mobile_config.json")["look_rad_per_px"]
                self.cam.yaw = clamp(self.cam.yaw - d * k, -self.cam.max_yaw, self.cam.max_yaw)
        else:
            self.look_left = can_look and mx < edge and self.cam.yaw > -self.cam.max_yaw
            self.look_right = can_look and mx > w - edge and self.cam.yaw < self.cam.max_yaw
            speed = math.radians(self.cam_cfg["look_speed_deg"]) * dt
            if self.look_left:
                self.cam.yaw = max(-self.cam.max_yaw, self.cam.yaw - speed)
            if self.look_right:
                self.cam.yaw = min(self.cam.max_yaw, self.cam.yaw + speed)

        aim = clamp((mx - self.cam.cx) / (self.cam.cx - edge), -1.0, 1.0)
        override = self.game.input.aim_override(self.fight is not None and self.fight.phase == "fight")
        if override is not None:
            aim = override  # 터치: 파이팅 중엔 릴 패드 노브가 방향
        self.cast.update(dt, aim)
        for ev in self.cast.events:
            if ev == "splash":
                self._splash()
                self.recast_told = False
            elif ev == "launch":
                self.sfx.play("sfx_cast_swing", 0.45 + 0.55 * self.cast.power)  # 휙 (파워만큼 크게)
        self.cast.events.clear()
        self._cast_audio()

        if self.fight is not None:
            self._update_fight(dt, aim)
        else:
            self._update_waiting(dt)

        self._update_fight_audio(dt)
        self._maybe_escape_tutorial()
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

    def _update_dragon(self, dt: float) -> None:
        f = self.fight
        dragon = f is not None and f.phase in ("fight", "net") and f.brain.dragon
        self.dragon_k += ((1.0 if dragon else 0.0) - self.dragon_k) * min(1.0, dt / 0.7)
        self.screen_fx.legend_color = (255, 80, 45) if dragon else (255, 196, 70)
        self.embers.update(dt)
        if dragon and f.phase == "fight":
            pos = self._fish_screen()
            p = self.cam.project(*f.fish_xz())
            spread = max(8.0, (p[2] if p else 10) * 1.2)
            self.embers.spawn(pos[0], pos[1], spread, 3 if self.dragon_fx else 1)
        if self.dragon_fx is not None:
            for ev in self.dragon_fx.update(dt):
                if ev == "swirl":
                    self.sfx.play("sfx_roar", 0.6)
                    self.sfx.play("sfx_bubbles", 1.0)
                elif ev == "pillar":
                    self.sfx.play("sfx_rise", 1.0)
                    self.shake_kick = 2.0
                elif ev.startswith("bolt"):
                    self.sfx.play("amb_thunder_near", 0.9)
                    self.shake_kick = 3.0
                elif ev == "flash":
                    self.sfx.play("sfx_impact", 1.0)
                elif ev == "roar":
                    self.sfx.play("sfx_roar", 1.0)
                    self.sfx.play("sfx_chord_legend", 0.8)
                    self.shake_kick = 4.0
            if self.dragon_fx.done:
                self.dragon_fx = None

    def _update_legend(self, dt: float) -> None:
        self._update_dragon(dt)
        f = self.fight
        if f is not None:
            on = f.fish["rarity"] == "legend" and f.phase in ("fight", "net")
        else:
            on = self.bite.legend and self.bite.state in (BiteState.APPROACH, BiteState.NIBBLE, BiteState.BITE)
        # 음악: 전설 테마 > 파이팅 > 낚시터 (data/music/ 에 파일이 있는 것만)
        music = self.game.music
        legend_id = None
        if on:
            legend_id = "legend_" + (f.fish["id"] if f is not None else self.bite.fish["id"])
        fighting = f is not None and f.phase in ("fight", "net")
        if legend_id:
            music.play(legend_id)
        elif fighting:
            music.play(f"fight_{self.spot_id}")
        else:
            music.play(f"spot_{self.spot_id}")
        self.legend_on = on
        self._update_music(on)
        self.screen_fx.legend = on
        self.legend_k += ((1.0 if on else 0.0) - self.legend_k) * min(1.0, dt / 0.8)

    def _update_music(self, legend: bool) -> None:
        """적응형 음악 층 (src/audio/adaptive_music.py, 32장 S6 + N4 음악 절제):
        대기(간헐적 — 울림/정적) → 입질·일반 파이팅은 그대로 낮추기만 / 대형(100cm+)은 낮은 긴장 층 하나 / 전설은 보스 테마
        (장력 타악은 전설만) → 포획 스팅은 희귀 이상만 / 실패 페이드. 낮 밝기만큼 높은 반짝임."""
        am = self.game.adaptive
        f = self.fight
        am.set_context(self.spot.get("continent", "sharmion"), self.spot_id, legend)
        intensity, phase, rarity = 0.0, 0, None
        if f is not None and f.phase in ("fight", "net"):
            if legend:
                # v0.8.14 롤백: 지침(기회!) 동안 음악이 바뀌지 않게 — 전설만 뜰채 단계에서 상승 멜로디
                state = "legend_tired" if f.phase == "net" else "legend"
            else:
                state = "fight_big" if f.size_cm >= 100 else "fight"  # 일반: 층 변화 없음 (뜰채 단계도 그대로)
            intensity = (f.tension - 30) / max(1.0, f.green_high - 30)
            phase = f.brain.phase
        elif f is not None and f.phase == "caught":
            state = "win"
            rarity = f.fish.get("rarity")
        elif f is not None and f.phase == "lost":
            state = "fail"
        elif self.bite.state == BiteState.BITE or (legend and f is None):
            state = "bite"
        else:
            state = "idle"
        am.set(state, intensity, phase, am.daylight_of(self.clock.hour, tuple(am.cfg["night_hours"])), rarity=rarity)

    def _update_weather(self, dt: float) -> None:
        w = self.weather_sys
        w.update(self.clock.day, self.clock.hour, self.spot["weather"])
        for ev in w.events:
            msg = {"clear": "비가 그치고 하늘이 갰다", "rain": "비가 내리기 시작했다 (입질 증가)",
                   "storm": "폭풍이 몰아친다! (희귀어 증가)",
                   "fog": "짙은 안개가 내려앉았다 (그림자가 안 보여요)"}[ev.split(":")[1]]
            self.toasts.show(msg, INFO, 2.6, 11)
        w.events.clear()
        self._update_signs(dt)
        self.lure_hop = max(0.0, getattr(self, "lure_hop", 0.0) - dt)
        self.rain.update(dt, self.weather, self.ripples, self.cam)
        self.fog.update(dt, self.weather)
        self.lightning.update(dt, self.weather, self.cam.horizon, self.cam.width)
        for ev in self.lightning.events:
            if ev == "strike":
                self.ambience.strike()  # 천둥은 번개 뒤 거리만큼 늦게 (가까우면 쩍, 멀면 우르릉)
                self.shake_kick = max(self.shake_kick, 1.0)
        self.lightning.events.clear()
        self.ambient.update(dt, self.clock.period()[0], self.weather, self.theme.get("sea", False))
        f = self.fight
        self.ambience.update(dt, self.spot_id, self.clock.period()[0], self.weather,
                             fighting=f is not None and f.phase in ("fight", "net"), legend=self.legend_on)

    def _update_waiting(self, dt: float) -> None:
        self.bite.set_conditions(self.clock.period()[0], self.weather, self.spot_id)
        self.bite.bait = self.save.equipped("bait")
        self.bite.force_fish = self.all_fish[self.force_i] if self.force_i >= 0 else None
        landed = self.cast.state == CastState.LANDED
        if landed and self.bite.state == BiteState.WAIT:
            # 루어 (U7): 짧은 클릭·탭 = 저킹, 누르고 있기 = 리트리브, 가만히 = 멈춤
            self.ctl.update_lure(dt, self.t, self.game.input.held("press"))
            jerk = "lure_jerk" in self.ctl.events
            retrieving = self.ctl.lure == "retrieve"
            if retrieving:
                retrieving = self._retrieve_lure(dt)
            self.bite.lure_in = (jerk, retrieving)
            if jerk:
                self._jerk_fx()
            if self.bite.lure.engaged and self.card is None and self.tutorial.want("lure_intro"):
                self._open_card("lure_intro", None)
        else:
            self.ctl.reset()
        self.bite.sign_mods = self.signs.mods(self.cast.bx, self.cast.bz) if landed else {}
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

    def _retrieve_lure(self, dt: float) -> bool:
        """리트리브: 찌가 일정 속도로 다가온다. 너무 가까우면 멈추고 다시 던지라고 안내."""
        lc = self.bite.lcfg
        c = self.cast
        d = math.hypot(c.bx, c.bz)
        if d <= lc["recast_distance"]:
            if not self.recast_told:
                self.recast_told = True
                hint = "회수 버튼" if self.touch else "우클릭"
                self.toasts.show(f"찌가 너무 가까워요 — {hint}으로 걷고 다시 던지세요", INFO, 2.4, 11)
            return False
        k = max(0.0, d - lc["retrieve_speed"] * dt) / d
        c.bx, c.bz = c.bx * k, c.bz * k
        self.bite.bobber = (c.bx, c.bz)
        self.wake_t = getattr(self, "wake_t", 0.0) + dt
        if self.wake_t > 0.25:
            self.wake_t = 0.0
            self.ripples.spawn(c.bx, c.bz, size=0.3, life=0.8)
        return True

    def _jerk_fx(self) -> None:
        self.sfx.play("sfx_jerk", 0.7)
        """저킹: 찌가 톡 튀며 작은 물결 + 아래쪽에 '톡! 저킹 (간격)' (리듬을 맞추기 쉽게)."""
        prev = getattr(self, "last_jerk_t", None)
        self.last_jerk_t = self.t
        gap = self.t - prev if prev is not None and self.t - prev < 4.0 else None
        self.lure_fb = ("톡! 저킹" + (f"  · 간격 {gap:.1f}초" if gap else ""), self.t)
        c = self.cast
        self.ripples.spawn(c.bx, c.bz, size=0.4, life=0.7)
        p = self.cam.project(c.bx, c.bz)
        if p:
            self.droplets.burst(p[0], p[1], max(0.4, p[2] / 30), count=2)
        self.lure_hop = 0.18

    def _update_signs(self, dt: float) -> None:
        """수면 징후: 생기고 사라짐 + 물 위 연출 (새 떼·물거품·점프·반짝임)."""
        waiting = self.fight is None and self.cast.state in LOOK_STATES and self.landing is None
        kind = self.signs.update(dt, waiting, self.cam.yaw)
        if kind == "sparkle":
            pass  # N3: 전조 반짝은 소리 없이 (대기 중 정적)
        s = self.signs.sign
        if s is None:
            return
        self.sign_fx_t += dt
        r = self.signs.radius
        fade = min(1.0, s["t"] / 1.0, (s["life"] - s["t"]) / 1.0)
        rx = lambda: s["x"] + random.uniform(-r, r) * 0.7
        rz = lambda: s["z"] + random.uniform(-r, r) * 0.7
        kind = s["kind"]
        if kind == "bubbles" and self.sign_fx_t > 0.07:
            # 물거품: 보글보글 큰 거품이 계속 올라옴
            self.sign_fx_t = 0.0
            for _ in range(2):
                p = self.cam.project(rx(), rz())
                if p:
                    self.bubbles.spawn(p[0], p[1], max(3.0, p[2] * 0.6 * fade))
            if random.random() < 0.3:
                self.ripples.spawn(rx(), rz(), size=0.35, life=0.8)
        elif kind == "jump" and self.sign_fx_t > 1.3:
            # 물고기 점프: 은빛이 튀어 오르고 물보라
            self.sign_fx_t = 0.0
            x, z = rx(), rz()
            self._splash_at(x, z, 0.9)
            p = self.cam.project(x, z, 0.5)
            if p:
                self.sparkles.burst(p[0], p[1], count=3, speed=0.5, ring=False)
            self.sfx.play("sfx_splash_small", 0.3)
        elif kind == "sparkle" and self.sign_fx_t > 0.08:
            # 반짝이는 물결: 넓게 반짝임
            self.sign_fx_t = 0.0
            p = self.cam.project(rx(), rz())
            if p:
                self.sparkles.burst(p[0], p[1], count=2, speed=0.25, ring=False)
        elif kind == "birds" and self.sign_fx_t > 0.9:
            self.sign_fx_t = 0.0
            self._splash_at(rx(), rz(), 0.4)  # 새가 물을 찍는다

    def _draw_birds(self, canvas) -> None:
        s = self.signs.sign
        if s is None or s["kind"] != "birds":
            return
        fade = min(1.0, s["t"] / 1.0, (s["life"] - s["t"]) / 1.0)
        if fade <= 0:
            return
        col = (30, 32, 40)
        for i in range(7):
            a = self.t * (0.8 + i * 0.07) + i * 1.05
            x = s["x"] + math.cos(a) * (1.2 + i * 0.25)
            z = s["z"] + math.sin(a) * (1.2 + i * 0.25)
            p = self.cam.project(x, z, 2.5 + 0.4 * math.sin(a * 2))
            if p is None or fade < 0.2:
                continue
            w = max(4, int(p[2] * 0.3))
            flap = int(w * 0.6 * math.sin(self.t * 12 + i))
            px, py = int(p[0]), int(p[1])
            pygame.draw.lines(canvas, col, False, [(px - w, py - flap), (px, py), (px + w, py - flap)], 2)

    def _update_fight(self, dt: float, aim: float) -> None:
        if self.training is not None:
            self.training.update(dt)  # 끝나면 바로 다시, 게이지는 계속 채움
            if self.training is None or self.fight is None:
                return
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
                # 랭크 도장 쾅 — 랭크마다 다른 소리 (C 담백 / B 밝음 / A 화음 / S 화음 + 반짝 + 저음)
                if f.result["rank"] == "S":  # N3: 랭크 소리·도장 저음은 S랭크만 (나머지는 화면 도장만)
                    self.sfx.play("sfx_impact", 0.6)
                    self.sfx.play("sfx_rank_s", 0.9)
                self.shake_kick = 2.5
            news = getattr(self, "catch_news", None) or {}
            if f.phase == "caught" and prev < 1.0 <= self.end_t:
                if news.get("new"):
                    self.sfx.play("ui_dex_new", 0.5)  # NEW! 도감 등록 배지와 함께 (N3: 작게)
                elif news.get("record"):
                    self.sfx.play("sfx_record", 0.85)  # 최대 크기 경신 배지와 함께
            return
        reeling = self.game.input.held("reel") and f.phase == "fight"
        if f.phase == "fight" and f.zone() == "red":
            # 장력 빨강: 빨간 정도에 비례한 약한 진동을 0.3초마다
            self.red_buzz_t = getattr(self, "red_buzz_t", 0.0) - dt
            if self.red_buzz_t <= 0:
                self.red_buzz_t = 0.3
                self.game.haptics.vibrate("tension", min(1.0, max(0.2, (f.tension - f.green_high) / 30)))
        if f.phase == "fight" and not self.touch:
            self._detect_flick(dt)  # 터치는 릴 패드에서 튕기기 → "flick" 행동
        if f.phase == "fight":
            self.ctl.update_fight(dt, self.t, self.game.input)
            f.set_drag_min(self.ctl.drag_min)
            f.ctl = self.ctl
        from src.fishing.patterns import PatternInput
        f.update(dt, reeling, aim, PatternInput.from_controls(self.ctl) if f.phase == "fight" else None)
        x, z = f.fish_xz()
        self.cast.bx, self.cast.bz = x, z
        for ev in f.events:
            self._on_fight_event(ev)
        f.events.clear()
        self.sfx.boost = 1
        qr = getattr(self, "quest_run", None)
        if qr is not None and f.phase == "fight":
            qr.update(f)
            self._quest_events(qr)
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
        self.pump_flash = max(0.0, getattr(self, "pump_flash", 0.0) - dt)
        self.ink_t = max(0.0, self.ink_t - dt)
        p = self.cam.project(x, z)
        sig = b.signal
        if b.state == "fake_tired" and p and self.ink_t <= 0:
            # 가짜 지침의 단서: 기포가 계속 올라온다 (진짜 지침은 기포 없음)
            self.fake_bubble_t += dt
            if self.fake_bubble_t > 0.12:
                self.fake_bubble_t = 0.0
                self.bubbles.spawn(p[0], p[1], max(2.0, f.fish["shadow_len_m"] * p[2] * 0.6))
        if b.sound_only:
            sig = None  # 소리로만 예고: 물보라·기포 연출 없음
        if sig == "lure" and p and self.fx_t > 0.25:
            # 초롱아귀 가짜 예고: 등불이 번쩍 (기포 없음)
            self.fx_t = 0.0
            self.sparkles.burst(p[0], p[1] - 2, count=3, speed=0.4, ring=False)
        if sig in ("rush", "fake_rush"):
            pass  # 돌진 예고는 웅크림·안쪽 물결·줄 펄스로 (rush_cue, 31-14)
        elif sig == "leap" and p and self.ink_t <= 0 and not b.dark:
            # 몸털기 점프 예고: 그림자 커짐 + 몸을 던질 쪽으로 튀는 물보라
            self.bubbles.spawn(p[0], p[1], max(3.0, f.fish["shadow_len_m"] * p[2]))
            if self.fx_t > 0.1:
                self.fx_t = 0.0
                self.droplets.burst(p[0], p[1], max(0.5, p[2] / 25), count=3, lateral=b.leap_dir * 50)
        elif sig in ("jump", "thrash") and p and self.ink_t <= 0 and not b.dark:
            # 그림자 커짐 + 기포 (공중 몸부림은 더 크게)
            big = 1.6 if sig == "thrash" else 1.0
            self.bubbles.spawn(p[0], p[1], max(3.0, f.fish["shadow_len_m"] * p[2]) * big)
        elif self._pattern_cue_fx(b, sig, x, z, p):
            pass
        elif b.state in ("idle", "rush", "turn", "recover") and self.fx_t > (0.15 if b.state == "rush" else 0.6):
            self.fx_t = 0.0
            self.ripples.spawn(x, z, size=0.4 if b.state != "rush" else 0.6, life=0.9)
            if b.state == "rush" and p:
                self.droplets.burst(p[0], p[1], max(0.5, p[2] / 25), count=3)

    def _pattern_cue_fx(self, b, sig, x: float, z: float, p) -> bool:
        """신규 패턴 예고·행동의 물 위 연출. 처리했으면 True (기본 잔물결 대신)."""
        kinds = [k for k in ("shake", "surface", "reverse", "twist", "hide", "pump", "bite", "dive")
                 if b.doing(k) or (sig is not None and b.telegraphing(k))]
        if not kinds:
            return False
        for kind in kinds:
            self._pattern_fx_one(b, kind, b.doing(kind), x, z, p)
        return True

    def _pattern_fx_one(self, b, kind: str, strong: bool, x: float, z: float, p) -> None:
        if kind == "shake":
            # 줄이 떨리며 물방울이 잘게 튄다
            if p and self.fx_t > (0.06 if strong else 0.1):
                self.fx_t = 0.0
                self.droplets.burst(p[0] + random.uniform(-3, 3), p[1], max(0.4, p[2] / 30), count=2 if strong else 1)
        elif kind == "surface":
            # V자 물살: 물고기 뒤로 좌우 두 갈래
            if self.fx_t > 0.09:
                self.fx_t = 0.0
                back = math.atan2(x, z)
                bx, bz = math.sin(back), math.cos(back)
                for side in (-1, 1):
                    k = 0.35 if strong else 0.25
                    self.ripples.spawn(x + bx * 0.3 + bz * side * k, z + bz * 0.3 - bx * side * k, size=0.35, life=0.8)
                if strong and p:
                    self.droplets.burst(p[0], p[1], max(0.5, p[2] / 25), count=2)
        elif kind == "reverse":
            # 다가오는 물고기 앞쪽으로 퍼지는 물결
            if self.fx_t > 0.25:
                self.fx_t = 0.0
                fwd = math.atan2(x, z)
                self.ripples.spawn(x - math.sin(fwd) * 0.5, z - math.cos(fwd) * 0.5, size=0.5, life=0.9)
        elif kind == "twist":
            # 제자리에서 도는 소용돌이
            if self.fx_t > 0.12:
                self.fx_t = 0.0
                a = self.t * 9
                self.ripples.spawn(x + math.cos(a) * 0.3, z + math.sin(a) * 0.3, size=0.3, life=0.7)
        elif kind == "hide":
            # 바위 쪽으로 파고들며 흙탕물 (숨은 동안엔 조용)
            if not strong and p and self.fx_t > 0.2:
                self.fx_t = 0.0
                self.droplets.burst(p[0], p[1], max(0.5, p[2] / 25), count=2)
        elif kind == "pump":
            # 박마다 물이 출렁 (pump_beat 이벤트가 pump_flash를 켬)
            if getattr(self, "pump_flash", 0) > 0.12:
                self.ripples.spawn(x, z, size=0.55, life=0.6)
        elif kind == "bite":
            if p and self.fx_t > 0.18:
                self.fx_t = 0.0
                self.sparkles.burst(p[0], p[1] - 3, count=2, speed=0.3, ring=False)
        # dive: 기포·물결이 멈춘다 (아무것도 안 그림 — 그게 신호)

    def _update_landing(self, dt: float) -> None:
        for ev in self.landing.update(dt):
            if ev == "hit":
                cls = self.landing.cls
                # 뜰채 성공: 물보라 + 퍼덕임 + 짧은 승리음 (크기 등급만큼 크게·묵직하게)
                self.sfx.play("sfx_net_success", {"small": 0.6, "mid": 0.8, "big": 0.95, "huge": 1.0}[cls])
                if cls in ("big", "huge"):  # N3: 저음 '퍽'은 대형만
                    self.sfx.play("sfx_impact", {"big": 0.6, "huge": 0.85}[cls])
                self.shake_kick = {"small": 0.8, "mid": 2.0, "big": 3.0, "huge": 4.0}[cls]
            elif ev.startswith("heave"):
                # 큰 물고기 '영차': 처졌다가 확 들어 올림
                self.sfx.play("sfx_impact", 0.7)
                self.sfx.play("sfx_splash", 0.6)
                self.shake_kick = 3.0 if self.landing.cls == "big" else 4.0
                self.game.haptics.vibrate("lose", 0.5)
            elif ev == "lift":
                if self.landing.tier >= 3:  # N3: 들어 올림 상승음은 전설만
                    self.sfx.play("sfx_rise", 0.9)
                    self.sfx.play("sfx_chord_legend", 0.9)   # 하늘이 어두워지며 금빛 기둥
                    self.shake_kick = 1.5
            elif ev == "launch":
                self.sfx.play("sfx_launch", 0.9)
                self.sfx.play("sfx_splash_small", 0.6)
            elif ev == "apex":
                if self.landing.tier >= 2:  # N3: 정점 '챙'은 희귀 이상만 (일반 포획은 자연음만)
                    self.sfx.play("sfx_perfect#0", 0.45)
                if self.landing.chest:
                    self.sfx.play("sfx_coin", 0.9)  # 물고기가 상자를 물고 나왔다
                if self.landing.tier == 2:
                    self.sfx.play("sfx_chord_rare", 0.9)
                elif self.landing.tier >= 3:
                    self.sfx.play("sfx_impact", 1.0)
                    self.sfx.play("sfx_chord_rare", 0.8)
                    self.shake_kick = 3.0
        if self.landing.done:
            chest = self.landing.chest
            self.landing = None
            self.end_t = 0.0
            self.sfx.play("sfx_catch")
            if chest:
                from src.save import treasure
                info = treasure.grade_info(chest)
                self.toasts.show(f"{info['name']} 보물상자 획득! (C: 열기)", tuple(info["color"]), 3.0, 11)

    def _detect_flick(self, dt: float) -> None:
        """마우스를 짧은 시간에 좌우로 크게 움직이면 슬라이드(꺾기)."""
        fc = self.flick_cfg
        self.flick_cd = max(0.0, self.flick_cd - dt)
        self.flick_hist.append((self.t, self.mouse[0]))
        self.flick_hist = [(tt, x) for tt, x in self.flick_hist if self.t - tt <= fc["sec"]]
        if self.flick_cd > 0 or len(self.flick_hist) < 2:
            return
        dx = self.flick_hist[-1][1] - self.flick_hist[0][1]
        if abs(dx) >= fc["px"]:
            d = 1 if dx > 0 else -1
            self.flick_cd = fc["cooldown_sec"]
            self.flick_hist.clear()
            self.sfx.play("sfx_cast_swing", 0.3)  # 휘두르는 소리 (판정과 상관없이)
            self.fight.flick(d)

    def _swipe_vfx(self, perfect: bool) -> None:
        """꺾기·몸털기 받아치기 성공: 참격 + 휘청 + 옆으로 튀는 물보라 + 채찍 소리."""
        f = self.fight
        d = f.last_flick_dir or 1
        pos = self._fish_screen()
        mpos = self.screen_fx.map(pos)
        self.screen_fx.slash(d, mpos[1] - 6, perfect)
        x, z = f.fish_xz()
        p = self.cam.project(x, z)
        if p:
            self.droplets.burst(p[0], p[1], max(0.8, p[2] / 18), count=22 if perfect else 12, lateral=d * 70)
        self.ripples.spawn(x, z, size=0.9, life=1.0, rings=2)
        self.sparkles.burst(*pos, count=30 if perfect else 14, speed=1.5 if perfect else 1.0)
        self.sfx.play("sfx_whip", 1.0)
        if perfect:
            self._perfect_sound(0.9)
            self.game.slowmo(0.18, 0.25)  # 히트스톱
            self.shake_kick = 2.5
        else:
            self.sfx.play("sfx_great", 0.7)
            self.shake_kick = 1.4


    def _cast_loop(self, slot: str, name: str | None, vol: float = 1.0) -> None:
        cur = self.cast_loops[slot]
        if cur != name and cur is not None:
            self.sfx.loop(cur, False)
        if name is not None:
            self.sfx.loop(name, True, vol)
        self.cast_loops[slot] = name

    def _cast_audio(self) -> None:
        """캐스팅: 파워 충전(삐걱 + 상승 바람, 파워 단계), 비행 중 줄 풀림 래칫 (32장 S4)."""
        c = self.cast
        if c.state == CastState.CHARGING:
            self._cast_loop("charge", f"sfx_cast_charge#{min(3, int(c.power * 4))}", 0.25 + 0.45 * c.power)
        else:
            self._cast_loop("charge", None)
        if c.state == CastState.FLIGHT:
            self._cast_loop("line", "sfx_line_out", 0.3 + 0.35 * c.power)
        else:
            self._cast_loop("line", None)

    def _update_fight_audio(self, dt: float) -> None:
        """파이팅 연속음: 릴 클릭·드랙 풀림·장력 삐걱임·줄 실금·드랙 딸깍·몸부림 (src/audio/fight_audio.py)."""
        f = self.fight
        fa = self.fight_audio
        if f is not None and f.phase == "fight":
            far = self.cast_far
            zone = f.zone()
            if zone == "green" and f.tension >= f.green_high - fa.fc["yellow_frac"] * (f.green_high - f.green_low):
                zone = "yellow"  # 소리용 노란 구간: 초록 위쪽 끝 (N3 연속음 주인공)
            fa.update(dt, {"reel": f.reel_speed_now if f.reeling else 0.0,
                           "payout": min(1.0, f.payout_now / self.fish_cfg["fight"]["payout_max_speed"]),
                           "tension": f.tension, "line": f.line_frac, "drag": f.drag - 1,
                           "near": max(0.0, 1 - f.distance / far), "zone": zone, "tier": self._reel_tier()},
                      red_at=f.green_high, active=f.brain.is_active and not f.brain.sound_only)
        elif self.cast.state == CastState.RETRIEVE:
            fa.update(dt, {"reel": 1.6, "tier": self._reel_tier()}, active=False)  # 회수: 릴만 감김
        else:
            fa.stop()

    def _maybe_escape_tutorial(self) -> None:
        if getattr(self, "escape_tutorial_pending", False) and self.end_t > 1.2:
            self.escape_tutorial_pending = False
            from src.scene.escape_tutorial import EscapeTutorialScene
            self.game.scenes.push(EscapeTutorialScene(self.game, self))

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
    def float_warning(self) -> str | None:
        """엘드라시온: 장착한 찌가 이 낚시터 요구 티어보다 낮으면 경고 문구."""
        need = self.spot.get("float_req", 0) if self.spot.get("continent") == "eldrasion" else 0
        if need and self.save.float_tier() < need and self.save.data["flags"].get("eldra_escape_tutorial"):
            return f"찌 부족: {float_name(need)} 이상 필요"
        return None

    def current_gimmick(self) -> str | None:
        """이 낚시터의 환경 기믹 (세계수는 시간대·날씨에 따라)."""
        g = self.spot.get("gimmick")
        if g == "cycle":
            from src.fishing.gimmick import cycle_gimmick
            return cycle_gimmick(self.clock.period()[0], self.weather)
        return g

    def _use_fight_item(self, item_id: str) -> None:
        """파이팅 중 소모품 (1: 수리용 실타래 / 2: 잔잔한 물 부적), 파이팅당 1개."""
        f = self.fight
        if self.save.consumable_count(item_id) <= 0:
            self.toasts.show("없음!", BAD, 1.2, 11)
        elif f.consumable_used:
            self.toasts.show("1개만!", BAD, 1.4, 11)
        elif f.use_consumable(item_id):
            self.save.use_consumable(item_id)
            self.sfx.play("sfx_great", 0.6)
            self.toasts.show("사용!", GOOD, 1.8, 11)
            self.sparkles.burst(*self._fish_screen(), count=10, speed=0.7, ring=False)

    def _splash(self) -> None:
        self.tutorial.mark("guide_cast")
        c = self.cast
        self._splash_at(c.bx, c.bz, big=1.0)
        far = self.cast_far
        self.sfx.play("sfx_land", max(0.25, 1.0 - 0.7 * c.current_distance() / far))  # 퐁 — 멀수록 작게
        # 행운의 떡밥: 남은 캐스팅 동안 희귀 이상 +3%p
        buffs = self.save.data["buffs"]
        self.bite.rare_bonus = 0.03 if buffs.get("lucky_casts", 0) > 0 else 0.0
        if buffs.get("lucky_casts", 0) > 0:
            buffs["lucky_casts"] -= 1
        self.bite.window_extra = 0.95 if self.save.charm_on("pinwheel_float") else 1.0
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
            fish = self.bite.fish
            need = self.save.float_need(fish, self.spot) if fish else 0
            if need > self.save.float_tier() and self.save.data["flags"].get("eldra_escape_tutorial"):
                self.toasts.show(f"이 물고기를 잡으려면 [{float_name(need)}] 이상 필요", BAD, 3.0, 11)
            self.sfx.play("sfx_roar", 0.6)
            self.shake_kick = 1.5
        elif ev == "nibble":
            self.sfx.play("sfx_nibble", 0.8, haptic="nibble")
            big = self.save.cosmetic_on("sparkle_float")  # 반짝이 찌: 입질 파문이 더 잘 보임
            self.ripples.spawn(c.bx, c.bz, size=0.5 if big else 0.35, life=1.0 if big else 0.8)
        elif ev == "bite":
            self.sfx.play("sfx_bite_real", haptic="bite")
            self.ripples.spawn(c.bx, c.bz, size=1.3, life=1.5, rings=3)
            p = self.cam.project(c.bx, c.bz)
            if p:
                self.droplets.burst(p[0], p[1], max(0.6, p[2] / 20), count=10)
        elif ev == "missed":
            self.sfx.play("sfx_flee", 0.6)
            self.toasts.show("미끼만 먹고 도망갔다... (우클릭: 회수)", BAD, 2.6)

    def _on_pattern_event(self, ev: str, kind: str, pid: str) -> None:
        """신규 패턴(U3): 예고 소리·진동·첫 만남 안내, 판정 결과 연출."""
        pos = self._fish_screen()
        f = self.fight
        if ev == "fake_tired":
            kind, pid = "telegraph", "fake"  # 가짜 지침은 예고 없이 상태가 곧 신호 — 첫 만남 안내만
        if kind == "telegraph":
            # 신호 소리·진동은 계열별로 _signal_cue 가 낸다 (31장 C3). 여기선 물고기 몸짓 소리·연출만.
            if pid == "thrash":
                self.sfx.play("sfx_splash_small", 0.6)
            if pid == "bite" and not f.brain.sound_only:
                self.sparkles.burst(*pos, count=6, speed=0.5, ring=False)  # 이빨 반짝
            seen = self.save.data.setdefault("patterns_seen", [])
            card = f"pattern:{pid}"
            if card in tut.CARDS and self.card is None and self.tutorial.want(card) and self.settings.get("signal_cards"):
                # 처음 보는 패턴: 예고 순간 멈추고 시범 그림이 있는 설명 카드
                if pid not in seen:
                    seen.append(pid)
                self._open_signal_card(card)
            elif pid not in seen:
                # 첫 만남(카드는 이미 봤음): 잠깐 느려지며 한 줄 안내 (이후 도감에 패턴 힌트)
                seen.append(pid)
                pc = load_json("patterns.json")
                fm = pc["first_meet"]
                self.game.slowmo(fm["real_sec"], fm["scale"])
                self.toasts.show(f"새 패턴 · {pc['names'][pid]} — {pc['guide'][pid]}", (255, 214, 90), 3.4, 11)
        elif kind == "action":
            if pid == "surface":
                self.sfx.play("sfx_splash_small", 0.8)
            elif pid == "dive":
                self.sfx.play("sfx_bubbles", 0.5)
        elif kind == "pattern_ok":
            # 퍼펙트·그레잇과 같은 급: 공통 섬광·충격파·반짝임 + 패턴마다 다른 연출 (깔끔하면 PERFECT)
            perfect = getattr(f, "last_grade", "good") == "perfect"
            col = self._pattern_col(pid)
            self._judge_burst(pos, perfect, col)
            self.pvfx.success(pid, pos[0], pos[1], perfect, col)
            self.popups.pattern(pid, perfect, pos, col)
        elif kind == "pattern_fail":
            self.sfx.play("sfx_judge_miss")  # N3: 놓침에 저음 '퍽' 없음
            self.popups.add(f"fail_{pid}", pos)
            self.screen_fx.miss(self.screen_fx.map(pos))
            self.pvfx.fail(pid, pos[0], pos[1])
            self.shake_kick = max(self.shake_kick, 2.5)
            self.game.haptics.vibrate("tension", 0.8)
            if pid == "dive":
                self.toasts.show("바닥에 쓸렸다! 줄 손상 · 거리 +3m", BAD, 1.6, 11)
            elif pid == "surface":
                self.toasts.show("수면을 박차고 뛰어오른다! 점프 대비", BAD, 1.6, 11)
        elif kind == "twist_step":
            self.game.haptics.vibrate("twist", 0.4 + 0.2 * int(pid))
            self.sfx.play(f"sfx_twist_step#{max(0, min(2, int(pid)))}", 0.5 + 0.15 * int(pid))  # 꼬일수록 높게
        elif ev == "twist_snap":
            self.sfx.play("sfx_scrape", 1.0)
            self.sfx.play("sfx_twist_snap", 1.0)
            self.toasts.show("꼬인 줄이 상했다! (줄 -25%) 원을 그려 꼬임을 푸세요", BAD, 2.0, 11)
            self.shake_kick = max(self.shake_kick, 2.5)
            self.game.haptics.vibrate("lose", 0.4)
        elif ev == "twist_turn":
            self.sfx.play("sfx_twist_turn", 0.8)
            self.pvfx.tick(pos[0], pos[1], self._pattern_col("twist"))
        elif ev == "combo_break":
            self.toasts.show("콤보가 끊겼다! 남은 행동이 더 거세진다", BAD, 1.8, 11)
            self.pvfx.fail("chain", pos[0], pos[1])
            self.screen_fx.miss(self.screen_fx.map(pos))
            self.sfx.play("sfx_judge_miss", 0.8)
            self.shake_kick = max(self.shake_kick, 2.0)
        elif ev == "combo_ok":
            self._judge_burst(pos, True, (255, 214, 90))
            seq = list(getattr(f.combo, "seq", []) or []) if f.combo else []
            self.pvfx.combo(pos[0], pos[1], [self._pattern_col(a) for a in seq])
            self.popups.add("combo_ok", pos)
        elif kind == "pump_beat":
            # 북 박자: 소리 = 판정 박자 (같은 틱에 낸다)
            for name, k in self.signal_audio.pick("pump", self.fight, "sig_drum", "sig_nat_drum", "sig_aux_timing"):
                self.sfx.play(name, (0.9 if pid == "preview" else 0.75) * k)  # 강조 '둥' / 자연음 낚싯대 '끼익' 한 박
            self.game.haptics.vibrate("pump")
            self.pump_flash = 0.15
        elif ev == "pump_hit":
            self.sfx.play("sfx_reel_click", 0.35)
            self.pvfx.tick(pos[0], pos[1], (255, 214, 90))
        elif ev == "pump_miss":
            self.sfx.play("sfx_judge_miss", 0.35)  # 박자 놓침
            self.pvfx.tick(pos[0], pos[1], (255, 90, 80))
        elif ev == "hide_peek":
            self.sfx.play("sfx_bubbles", 0.8)
            self.popups.add("hide_peek", pos)
            self.bubbles.spawn(pos[0], pos[1], 4.0)
            self.pvfx.ring(pos[0], pos[1], (255, 214, 90), 40, 0.4, 2)
            self.pvfx.star(pos[0], pos[1] - 6, (255, 240, 170), 12, 0.35)
        elif ev == "double_perfect":
            self.sfx.play("sfx_double_perfect", 1.0, haptic="double_perfect")
            self.sfx.duck("perfect")
            self.popups.add("double_perfect", pos)
            self.screen_fx.perfect(self.screen_fx.map(pos))
            self.sparkles.burst(*pos, count=36, speed=1.6)
            self.pvfx.combo(pos[0], pos[1], [(255, 214, 90), (255, 255, 255), (255, 214, 90)])
            self.game.slowmo(0.9, 0.25)  # 강한 슬로우
            self.shake_kick = 3.0
            st = self.save.data["stats"]
            st["double_perfects"] = st.get("double_perfects", 0) + 1
        elif ev == "thrash_second_miss":
            self.toasts.show("착수 직전을 놓쳤다! 바늘이 크게 흔들린다", BAD, 1.8, 11)
        elif ev == "stiff":
            self.toasts.show("헛물었다! 잠깐 굳었다 — 지금 크게 감으세요", GOOD, 1.8, 11)
            self.game.haptics.vibrate("bite", 0.6)
        elif ev == "dual_ok":
            self._judge_burst(pos, True, (255, 214, 90))
            pair = list(f.brain.dual_pair or ())
            self.pvfx.combo(pos[0], pos[1], [self._pattern_col(a) for a in pair])
            self.popups.add("dual_ok", pos)
        if kind == "pattern_fail" and pid == "bite":
            self.sfx.play("sfx_line_crack", 1.0, haptic="bite_tear")
            self.toasts.show("줄을 물어뜯겼다! (줄 -30%) 이빨이 번쩍이면 드랙 순간 최저", BAD, 2.0, 11)
        elif kind == "pattern_fail" and pid == "fake":
            self.toasts.show("가짜 지침에 속았다! 이어지는 돌진이 거세다 — 꼬리가 까딱이면 가짜", BAD, 2.2, 11)
            self.game.haptics.vibrate("perfect")

    def _pattern_col(self, pid: str):
        fam = signal_slots.family_of(pid)
        return signal_slots.color_of(fam) if fam in signal_slots.cfg()["families"] else (255, 214, 90)

    def _judge_burst(self, pos, perfect: bool, col) -> None:
        """판정 성공 공통 연출: 원래 PERFECT / GREAT 와 같은 급 (섬광·충격파·빛줄기·줌 펀치·반짝임·소리·진동)."""
        mp = self.screen_fx.map(pos)
        if perfect:
            self._perfect_sound()
            self.sparkles.burst(*pos, count=40, speed=1.7)
            self.sparkles.burst(*pos, count=16, speed=0.6, ring=False)
            self.screen_fx.perfect(mp)
            self.screen_fx.shockwaves.append([mp[0], mp[1], -0.1, col, 0.5, 2])
            self.shake_kick = max(self.shake_kick, 2.5)
            fc = self.fish_cfg["fight"]
            self.game.slowmo(fc["slowmo_real_sec"] * 0.6, fc["slowmo_scale"])
        else:
            self.game.haptics.vibrate("perfect", 0.5)
            self.sfx.play("sfx_great")
            self.sparkles.burst(*pos, count=16, speed=1.0)
            self.screen_fx.great(mp)
            self.screen_fx.shockwaves.append([mp[0], mp[1], -0.06, col, 0.4, 1])
            self.shake_kick = max(self.shake_kick, 1.2)

    def _perfect_sound(self, vol: float = 1.0) -> None:
        """퍼펙트: 주변 먹먹(덕킹) + '챙!' + 저음 '쿵', 연속 퍼펙트일수록 한 단계씩 높게 (32장 S5)."""
        f = self.fight
        n = max(0, min(4, (f.perfect_streak if f is not None else 1) - 1))
        self.sfx.play(f"sfx_perfect#{n}", vol, haptic="perfect")
        self.sfx.duck("perfect")

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
            h = 4 * f.brain.air_height * ph * (1 - ph)
        p = self.cam.project(x, z, h)
        return (p[0], p[1]) if p else (self.cam.cx, self.cam.horizon + 20)

    def _signal_cue(self, action: str) -> None:
        """신호 사전: 같은 대응 계열 = 같은 소리·진동 (가짜 예고·콤보 머리는 없음). 소리는 src/audio/signal_audio.py (32장 S5)."""
        sig = signal_slots.cfg()
        acts = list(self.fight.brain.dual_pair or ()) if action == "dual" else [action]
        for a in acts:
            fam = sig["actions"].get(a, {}).get("family")
            if fam in sig["families"]:
                self.signal_audio.start(a, fam, self.fight)

    def _mastery_event(self, ev: str) -> None:
        """판정 이벤트 → 패턴별 성공/실패 (숙련도·연속 실패·결과 화면 아이콘)."""
        f, b = self.fight, self.fight.brain
        pid, ok = None, None
        if ev.startswith("pattern_ok:"):
            pid, ok = ev.split(":", 1)[1], True
        elif ev.startswith("pattern_fail:"):
            pid, ok = ev.split(":", 1)[1], False
        elif ev in ("perfect", "good", "miss_early", "miss_late", "miss_none"):
            pid = "thrash" if b.jump_kind == "thrash" else "leap" if f.last_judge_kind == "swipe" else "jump"
            ok = ev in ("perfect", "good")
        elif ev in ("flick_perfect", "flick_good", "flick_miss"):
            pid, ok = "turn", ev != "flick_miss"
        elif ev in ("combo_ok", "combo_fail"):
            pid, ok = "chain", ev == "combo_ok"
        elif ev == "dual_ok":
            pid, ok = "dual", True
        elif ev in ("rush_ok", "rush_fail"):
            pid, ok = "rush", ev == "rush_ok"
        if pid is None:
            return
        if self.training is not None:
            self.training.count(pid, ok)  # 훈련은 성공률만, 세이브는 건드리지 않음
            return
        mastery = self.save.data.setdefault("pattern_mastery", {})
        streak = self.save.data.setdefault("pattern_fail_streak", {})
        if ok:
            before = mastery.get(pid, 0)
            mastery[pid] = before + 1
            streak[pid] = 0
            tiers = [n for n, _ in signal_slots.cfg()["mastery"]["tiers"] if n > 0]
            if any(before < n <= before + 1 for n in tiers) and pid not in self.mastery_ups:
                self.mastery_ups.append(pid)
        else:
            streak[pid] = streak.get(pid, 0) + 1
            if pid not in self.missed_signals:
                self.missed_signals.append(pid)

    def _on_fight_event(self, ev: str) -> None:
        f = self.fight
        x, z = f.fish_xz()
        self._mastery_event(ev)
        self.signal_audio.on_event(ev)
        self.sfx.boost = 2 if "clear" in f.mutations and ev.startswith("telegraph:") else 1  # 투명: 예고 소리 +6dB
        if ev == "rush_ok":
            p = self._fish_screen()
            self.pvfx.success("rush", p[0], p[1], False, (255, 170, 90))  # 돌진을 버텼다: 작은 반짝
        if ev.startswith("telegraph:"):
            self._signal_cue(ev.split(":", 1)[1])
            self.sig_dim_t = 0.9  # 신호가 뜨는 순간: 하위 HUD 잠깐 더 흐리게
        elif ev == "tired":
            # v0.8.14 롤백: 지침(기회!)은 사운드 개편 전 그대로 — '딸깍' 두 번 + 감기 계열 진동 바로
            if self.settings.get("signal_sound"):
                self.sfx.play("legacy_sig_reel", 0.8)
            self.game.haptics.vibrate("sig_reel")
        elif ev in ("action:charge", "hide_peek"):
            self._signal_cue("charge")  # 감기 계열 (빈틈·고개 내밂)
        qr = getattr(self, "quest_run", None)
        if qr is not None:
            qr.on_event(ev)
        if ev in tut.CARDS and self.card is None and self.tutorial.want(ev):
            if ev.startswith("telegraph:"):
                if self.settings.get("signal_cards"):  # 접근성: 첫 만남 카드 끄기 (31장 C6)
                    self._open_signal_card(ev)
            else:
                self._open_card(ev, None if ev == "net_start" else "fish")
        elif ev == "hazard_enter":
            self.toasts.show("걸린다!", BAD, 1.5, 11)
        elif not f.brain.sound_only and "dark" not in f.gim.kinds(f.brain):
            self._tip(ev)  # 소리 전용·동굴(어둠)에선 그림자 기준 팁을 띄우지 않는다
        sound_only = f.brain.sound_only
        if ev.startswith("telegraph:") and self.save.charm_on("ear_bell"):
            self.sfx.play("sig_bell", 0.7)  # 소리귀 방울
        if ev == "scale_heal":
            self.toasts.show("회복!", (255, 214, 90), 0.9, 11)
        elif ev == "gimmick:tangle_full":
            self.sfx.play("sfx_scrape", 1.0)
            self.sfx.play("sfx_twist_snap", 0.8)
            self.toasts.show("엉킴!", BAD, 1.8, 11)
            self.shake_kick = max(self.shake_kick, 2.0)
        elif ev == "gimmick:ice_scrape":
            self.sfx.play("sfx_scrape", 0.6)
        clear = "clear" in f.mutations
        if ev in CAPTIONS and (self.settings.get("sound_captions") or clear):
            self.captions = [CAPTIONS[ev], 1.2]  # 투명 변이: 소리 자막 강제
        kind, _, pid = ev.partition(":")
        if pid in FORCE_PATTERNS or kind in ("pattern_ok", "pattern_fail", "pattern_neutral", "twist_step", "pump_beat") or \
                ev in PATTERN_EVENTS:
            self._on_pattern_event(ev, kind, pid)
        if ev == "telegraph:lure":
            for name, k in self.signal_audio.pick("lure", f, "sig_lure", "sig_nat_lure"):
                self.sfx.play(name, 0.8 * k)  # 강조 '우웅~' / 자연음 수면 '찰랑'
            pos = self._fish_screen()
            self.sparkles.burst(*pos, count=8, speed=0.6, ring=False)  # 등불 번쩍 (판정 원과 헷갈리지 않게 고리 없음)
        elif ev == "action:charge" and sound_only:
            pass  # 소리 전용이어도 감기 계열 소리(sig_reel)가 이미 알림 (32장 S8: cue_charge 정리)
        elif ev in ("telegraph:rush", "telegraph:fake_rush"):
            self.sfx.play("legacy_bubbles", 0.45)  # 웅크림: 물을 빨아들이는 소리 (v0.8.14 롤백: 예전 소리)
            self.rush_hum_i = -1
        elif ev == "telegraph:jump":
            self.sfx.play("sfx_bubbles", 0.8)
            if f.brain.lightning_cue:
                # 전설 '번개': 번개 섬광이 점프 박자
                self.lightning.strike(self.cam.horizon, self.cam.width)
        elif ev.startswith("phase:"):
            n = int(ev.split(":")[1])
            pos = self._fish_screen()
            self.toasts.show("거세짐!", (255, 214, 90), 3.2, 11)
            self.sfx.play("sfx_roar", 1.0)
            self.sfx.play("sfx_impact", 0.8)
            self.screen_fx.great(self.screen_fx.map(pos))
            self.sparkles.burst(*pos, count=30, speed=1.4)
            self.shake_kick = 3.0
            lc = self.fish_cfg["legend"]
            self.game.slowmo(lc["phase_slowmo_real"], lc["phase_slowmo_scale"])
            if f.brain.dragon:
                self.toasts.items.clear()  # 배너가 대신 알림
                self.dragon_fx = DragonTransform(self.screen_fx.map(pos))
                self.game.slowmo(1.2, 0.4)
        elif ev == "telegraph:turn":
            self.sfx.play("sfx_scrape", 0.8)
        elif ev == "action:rush":
            # 펄스가 손에 닿음 = 돌진: 쉬익 + 물보라 + 툭 (v0.8.14 롤백: 사운드 개편 전 그대로)
            self.sfx.play("legacy_rush_go", 1.0)
            self.sfx.play("legacy_splash_small", 0.8)
            self.game.haptics.vibrate("bite", 1.0)
            self._splash_at(x, z, 0.9)
            self.shake_kick = max(self.shake_kick, 1.5)
        elif ev == "action:jump":
            self.jump_facing = -1 if f.fish_side() > 0 else 1
            self.sfx.play("sfx_jump_out", 0.8)
            self._splash_at(x, z, 0.8)
        elif ev == "telegraph:leap":
            if sound_only:
                for name, k in self.signal_audio.pick("leap", f, "sig_leap", "sig_nat_leap", "sig_aux_timing"):
                    self.sfx.play(name, 1.0 * k)  # 강조 '휙-팅' / 자연음 짧게 끓어오름 → 물 터짐
            else:
                self.sfx.play("sfx_bubbles", 0.8)
                self.sfx.play("sfx_splash_small", 0.5)
        elif ev == "action:leap":
            self.jump_facing = f.brain.leap_dir  # 몸을 던지는 쪽으로 비튼다
            self.sfx.play("sfx_jump_out", 0.85)
            self._splash_at(x, z, 0.9)
        elif ev in ("flick_perfect", "flick_good"):
            self._swipe_vfx(ev == "flick_perfect")
            self.popups.add(ev, self._fish_screen(), f.perfect_streak if ev == "flick_perfect" else 0)
        elif ev.startswith("hook_floor:"):
            n = int(ev.split(":")[1])
            if n < 3:
                self.toasts.show("헐거움!", BAD, 2.2, 11)
        elif ev == "flick_miss":
            pos = self._fish_screen()
            self.sfx.play("sfx_judge_miss")
            self.sfx.play("sfx_scrape", 1.0)
            self.popups.add("flick_miss", pos)
            self.screen_fx.miss(self.screen_fx.map(pos))
            self.shake_kick = 3.0
        elif ev == "jump_land":
            self.sfx.play("sfx_jump_land", 0.95)  # 철썩
            self._splash_at(x, z, 1.0)
        elif ev == "ink":
            self.ink_t = self.fish_cfg["fight"]["ink_sec"]
            self.sfx.play("sfx_splash_small", 0.5)
        elif ev == "bolt":
            self.toasts.show("또 도망!", BAD, 1.8, 11)
        elif ev == "exhausted":
            self.toasts.show("지쳤다!", GOOD, 2.0, 11)
        elif ev == "perfect" and f.last_judge_kind == "swipe":
            self._swipe_vfx(True)
            pos = self._fish_screen()
            self.screen_fx.perfect(self.screen_fx.map(pos))
            self.popups.add("swipe_perfect", pos, f.perfect_streak)
        elif ev == "good" and f.last_judge_kind == "swipe":
            self._swipe_vfx(False)
            self.popups.add("swipe_good", self._fish_screen())
        elif ev == "perfect":
            # 퍼펙트: 섬광 + 충격파 + 빛줄기 + 줌 펀치 + 큰 반짝임 + 슬로우 + 묵직한 타격음
            pos = self._fish_screen()
            self._perfect_sound()
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
            self.sfx.play("sfx_great")
            self.sparkles.burst(*pos, count=16, speed=1.0)
            self.screen_fx.great(self.screen_fx.map(pos))
            self.popups.add("good", pos)
            self.shake_kick = 1.2
        elif ev in ("miss_early", "miss_late", "miss_none"):
            pos = self._fish_screen()
            self.sfx.play("sfx_judge_miss")
            self.popups.add(ev, pos)
            self.screen_fx.miss(self.screen_fx.map(pos))
            self.shake_kick = 3.0
        elif ev == "creak":
            # v0.8.14 롤백: 장력 소리는 예전처럼 빨강 + 줄 50% 아래에서만 가끔 '끼익' (상시 삐걱임 반복음 없앰)
            self.sfx.play(random.choice(("legacy_creak", "legacy_creak2", "legacy_creak3")), random.uniform(0.45, 0.65))
        elif ev == "net_start":
            self.sfx.play("sfx_splash", 0.8)
            self.toasts.show("뜰채!", INFO, 1.6, 11)
        elif ev == "net_fail":
            self.sfx.play("sfx_flee")
            self.sfx.play("sfx_splash")
            self.toasts.show("놓쳤다!", BAD, 2.0, 11)
            self._splash_at(x, z, 1.0)
        elif ev == "caught":
            pose, _ = f.net_pose()
            shown = self._display_fish(f.fish)
            from src.save import treasure
            golden = self.save.equipped("net")["id"] == "golden_net"
            if golden:
                # 황금 뜰채: 크기 +3% (판매가도 그만큼)
                f.result["size"] = round(f.result["size"] * 1.03, 1)
                f.result["price"] = int(round(f.result["price"] * 1.03))
            muts = f.result.get("mutations") or []
            from src.fishing import mutation
            mk = mutation.cfg()["kinds"]
            bonus = mk["frenzy"]["chest_bonus"] if "frenzy" in muts else 0.0  # 광폭: 상자 +2%p
            self.chest_drop = treasure.roll_drop(self.save, f.fish, f.result["rank"], bonus=bonus)
            if f.fish["rarity"] == "legend" and self.spot.get("continent") == "eldrasion":
                # 전설 비늘: 첫 포획 5개, 이후 2개 (T7·T8, 봉인 찌 재료)
                n = 2 if self.save.caught(f.fish["id"]) else 5
                self.save.data["scales"] += n
                self.toasts.show(f"전설 비늘 +{n} (보유 {self.save.data['scales']})", (255, 214, 90), 3.0, 11)
            self.landing = LandingCinematic(shown, f.result["size"], 240 + pose * 46, chest=self.chest_drop,
                                            golden=golden)
            f.result["fish"] = shown
            self.end_t = 0.0
            self.catch_news = self.save.record_catch(f.result | {"perfects": f.perfects})
            self.catch_news["chest"] = self.chest_drop
            if muts:
                self._record_mutation(f, muts)
            qr = getattr(self, "quest_run", None)
            if qr is not None:
                qr.on_caught(f, f.result)
                self._quest_events(qr)
            from src.save.quests import title_name
            self.catch_news["title"] = title_name(self.save)
            if (self.save.charm_on("twin_hook") and f.fish["rarity"] != "legend" and random.random() < 0.05):
                # 쌍둥이 바늘: 같은 물고기 한 마리 더 (판매·소재용, 도감·랭크 기록 없음)
                self.save.data["keepnet"].append(dict(self.save.data["keepnet"][-1], twin=True))
                self.toasts.show("쌍둥이 바늘! 한 마리 더 걸려 올라왔다", (200, 150, 255), 2.5, 11)
            self.game.save_now()
        elif ev == "escape_start":
            # 마지막 발악: 눈이 번쩍 + 물보라 폭발 + 화면 흔들림
            pos = self._fish_screen()
            self.sparkles.burst(pos[0], pos[1] - 4, count=14, speed=1.2, ring=False)
            self._splash_at(x, z, 1.6)
            self.sfx.play("sfx_roar", 0.7)
            self.sfx.play("sfx_splash", 1.0)
            self.shake_kick = 4.0
        elif ev == "escape_snap":
            # 찌 부족 도주: 투둑 + 멀어지는 물소리 + 허탈한 하강음
            self.sfx.play("sfx_float_flee", 1.0, haptic="sfx_lose")
            self.sfx.duck("snap")
            self.screen_fx.miss(self.screen_fx.map(self._fish_screen()))
            self.game.slowmo(1.0, 0.35)
            self.shake_kick = 3.0
        elif ev == "lost:escape" and not self.save.data["flags"].get("eldra_escape_tutorial"):
            # 최초 도주: 실패 기록 없음, 도감에 '목격', 튜토리얼 팝업
            self.save.data["flags"]["eldra_escape_tutorial"] = True
            self.save.data["flags"]["float_highlight"] = True
            self.save.record_seen(f.fish["id"])
            self.game.save_now()  # N3: 놓침 하강음 없음
            self.end_t = 0.0
            self.escape_tutorial_pending = True
        elif ev.startswith("lost:"):
            self.save.record_loss()
            if ev == "lost:escape":
                self.save.record_seen(f.fish["id"])
                self.toasts.show(f"이 물고기를 붙잡으려면 [{float_name(f.float_need)}] 이상이 필요합니다.", BAD, 3.5, 11)
            self.game.save_now()
            if ev != "lost:escape":  # 도주는 '투둑' 순간(escape_snap)에 이미 진동
                self.game.haptics.vibrate("lose")
            self.sfx.play("sfx_line_snap" if ev == "lost:snap" else "sfx_flee")
            if ev == "lost:snap":
                self.sfx.duck("snap")  # 팅! 뒤 잠깐 무음 (N3: 놓침 하강음 없음 — 끊김·달아남 소리로 충분)
            self.end_t = 0.0
            self.shake_kick = 4.0 if ev == "lost:snap" else 0.0

    # ───────────────────────── 그리기 ─────────────────────────
    def draw(self, canvas: pygame.Surface) -> None:
        hour = self.clock.hour
        theme, weather = self.theme, self.weather
        pal = themed_palette(self.palette.sample(hour), theme, weather, self.lightning.flash, self.legend_k)
        pal = self._line_pal(pal)
        if self.dragon_k > 0.01:
            for key, v in pal.items():
                if isinstance(v, tuple) and key not in ("text", "bobber", "bobber_base"):
                    pal[key] = lerp_color(v, (120, 16, 26), 0.28 * self.dragon_k)
        cam, c, t, f = self.cam, self.cast, self.t, self.fight

        world.draw_sky(canvas, pal, cam)
        self.stars.draw(canvas, pal, cam, t)
        world.draw_celestial(canvas, pal, cam, hour, t, visible=weather == "clear" and theme["terrain"] != "cave")
        if theme.get("aurora"):
            from src.render.eldra_world import draw_aurora
            draw_aurora(canvas, pal, cam, t)
        self.clouds.draw(canvas, pal, cam)
        self.lightning.draw(canvas)
        world.draw_mountains(canvas, pal, cam, theme["terrain"], t)
        amp = {"clear": 1.0, "rain": 1.25, "storm": 1.9, "fog": 0.8}[weather] * (1.3 if theme.get("sea") else 1.0)
        self.water.draw(canvas, pal, t, hour, amp_mult=amp,
                        show_reflection=weather == "clear" and theme["terrain"] != "cave")
        if theme.get("lamp"):
            world.draw_ship_lamp(canvas, pal, cam)
        if self.landing is not None:
            self.landing.draw(canvas, pal)
            return
        if f is None:
            sh = self.bite.shadow if weather != "fog" else None  # 안개: 다가오는 그림자가 안 보인다
            if sh is not None and self.bite.fish is not None:
                sh = dict(sh, glow=GLOW.get(self.bite.fish["rarity"]))
            draw_fish_shadow(canvas, pal, cam, sh, t)
            self._draw_lure_mark(canvas, sh, t)
            if sh is not None and self.bite.fish is not None and self.save.charm_on("abyss_eye"):
                # 심연의 눈: 도감에 등록된 물고기면 이름이 보인다
                p = cam.project(sh["x"], sh["z"])
                if p and sh.get("alpha", 1) > 0.2:
                    fish = self.bite.fish
                    name = fish["name"] if self.save.caught(fish["id"]) else "???"
                    hud.text(canvas, name, (p[0], p[1] - 10), (190, 170, 255), anchor="center")
        elif f.phase == "fight":
            if self.ink_t > 0:
                x, z = f.fish_xz()
                draw_ink(canvas, pal, cam, x, z, min(1.0, self.ink_t), t)
            elif f.brain.dragon:
                sh = self._fight_shadow()
                facing = 1 if f.fish_side() <= 0 else -1  # 화면 가운데 쪽을 향해 머리를 둔다
                draw_dragon_shadow(canvas, pal, cam, sh["x"], sh["z"], sh["heading"], t, 1.0, sh["alpha"], facing)
            elif not f.brain.dark:
                sh = self._fight_shadow()
                draw_fish_shadow(canvas, pal, cam, sh, t)
                from src.ui import rush_cue
                rph = self._rush_ph()
                if rph is not None:
                    p = cam.project(sh["x"], sh["z"], -0.2)
                    if p:
                        rush_cue.draw_ripples(canvas, (p[0], p[1]), p[2] / 20, rph, t)   # 안쪽으로 빨려드는 물결
                        rush_cue.draw_wake(canvas, (p[0], p[1]), math.sin(sh["heading"] - cam.yaw), p[2] / 20, rph, t)
                tx = f.twin_xz()
                if tx is not None:
                    # 쌍둥이: 쉬는 녀석의 그림자 (조금 흐리게)
                    draw_fish_shadow(canvas, pal, cam, dict(sh, x=tx[0], z=tx[1], alpha=sh["alpha"] * 0.6, wag=6.0), t)
        self.ripples.draw(canvas, pal, cam)
        self._draw_birds(canvas)
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

        if f is not None and f.phase == "fight" and f.brain.state == "jump" and f.brain.dragon:
            x, z = f.fish_xz()
            draw_dragon_jump(canvas, pal, cam, x, z, f.brain.jump_phase(), f.brain.air_height, t,
                             1 if f.fish_side() <= 0 else -1)
        elif f is not None and f.phase == "fight" and f.brain.state == "jump":
            x, z = f.fish_xz()
            draw_jump(canvas, pal, cam, self._display_fish(f.fish), f.size_cm, x, z, f.brain.jump_phase(), self.jump_facing,
                      f.brain.air_height)

        fg = theme["foreground"]
        if fg in ("reeds", "silver_reeds"):
            rpal = pal if fg == "reeds" else dict(pal, reed=lerp_color(pal["reed"], (215, 222, 235), 0.65))
            self.reeds.draw(canvas, rpal, t, wind={"clear": 1.0, "rain": 1.4, "storm": 2.2, "fog": 0.6}[weather])
        else:
            world.FOREGROUND[fg](canvas, pal, t)
        from src.render.rod import gear_look
        from src.save.quests import skin_colors
        rod_l = gear_look("rod", self.save.gear_tier("rod"))       # 티어별 외형 (gear_looks.json)
        reel_l = gear_look("reel", self.save.gear_tier("reel"))
        skin = skin_colors(self.save, "rod_skin")
        if skin:  # 의뢰 상점 낚싯대 외형이 색은 우선
            rod_l = dict(rod_l, rod=skin[0], hi=skin[1])
            reel_l = dict(reel_l, body=skin[2])
        draw_rod(canvas, pal, geo, c.reel_angle, rod_l, reel_l, t)

        if hanging:
            bx, by = rod_tip_drop(tip, t)
            draw_line(canvas, pal, tip, (bx, by - 3), 0)
            draw_bobber(canvas, pal, bx, by, 7, floating=False)
        self.droplets.draw(canvas, pal)
        self.rain.draw(canvas, pal)
        self.fog.draw(canvas, pal, cam.horizon, t)
        if f is not None and f.phase == "fight":
            # 수면 위 행동 연출 (카메라 연출 전에 그려서 함께 확대됨)
            pos = self._fish_screen()
            p = cam.project(*f.fish_xz())
            sc = p[2] / 20 if p else 1.0
            self.gather.draw(canvas)
            if f.brain.state in ("tired", "fake_tired", "exhausted"):
                fight_fx.draw_tired_ring(canvas, pos, sc, t)
        self.sparkles.draw(canvas)
        self.pvfx.draw(canvas)
        self.embers.draw(canvas)
        self._draw_gimmick_world(canvas, pal)
        # 가짜 FOV (줌·패닝·기울기)
        self.screen_fx.apply_camera(canvas)

        inset = self.hud_inset
        if f is not None:
            self._draw_fight_overlay(canvas, pal)
        else:
            warn = self.float_warning()
            if warn:
                blink = int(self.t * 3) % 2 == 0
                hud.text(canvas, ("! " if blink else "  ") + warn, (6 + inset, 17), (255, 120, 110), anchor="topleft")
            if self.save.data["flags"].get("float_highlight") and int(self.t * 4) % 2 == 0:
                hud.text(canvas, "B: 상점에서 마비 찌!", (cam.width - 6 - inset, 43), (255, 230, 120), anchor="topright")
            label = f"{self.clock.label()} · {self.spot['name']} · {WEATHER_KO[weather]}"
            g = self.current_gimmick()
            if g:
                from src.fishing.gimmick import KO
                label += f" · {KO[g]}"
            hud.draw_clock(canvas, pal, label, self.clock.fast, self.clock.fast_mult, 6 + inset)
            if c.state == CastState.CHARGING:
                hud.draw_power_gauge(canvas, pal, c.power, c.distance_for_power(c.power))
            if c.state == CastState.LANDED:
                hud.text(canvas, f"찌 거리 {c.current_distance():.0f}m", (cam.width - 6 - inset, 30), pal["text"],
                         anchor="topright")
            sv = self.save.data
            hud.text(canvas, f"{sv['money']:,}원", (cam.width - 6 - inset, 4), (255, 228, 140), anchor="topright")
            bait = self.save.equipped("bait")["name"]
            hud.text(canvas, f"살림망 {len(sv['keepnet'])} · 미끼 {bait}", (cam.width - 6 - inset, 17), pal["text"],
                     anchor="topright")
            hint = HINTS[c.state]
            if hint:
                hud.draw_hint(canvas, pal, hint, center=self.touch)
            self._draw_lure_status(canvas)
            side = self._side_menu_on()
            hud.draw_look_arrows(canvas, pal, self.look_left, self.look_right, t, right_inset=30 if side else 0)
            if side:
                from src.ui import side_menu
                chests = sum(self.save.data.get("chests", {}).values())
                side_menu.draw(canvas, self._side_menu_rects(), self.mouse, t, {"chest": chests})
        self.toasts.draw(canvas)
        if self.captions:
            cap, left = self.captions
            w = get_font(11).size(cap)[0] + 12
            r = pygame.Rect(self.cam.cx - w // 2, 72, w, 14)
            canvas.fill((10, 14, 28), r)
            pygame.draw.rect(canvas, (150, 200, 255), r, 1)
            hud.text(canvas, cap, r.center, (200, 230, 255), anchor="center")
        if self.debug and f is None and c.state == CastState.LANDED:
            fight_hud.draw_debug_lines(canvas, ["루어 (대기 중)"] + self.ctl.debug_lines(self.t)[2:])
        if f is None and self.card is None:
            if not self.tutorial.is_seen("guide_cast") and c.state in (CastState.READY, CastState.CHARGING):
                tut.draw_guide(canvas, "guide_cast", t)
            elif not self.tutorial.is_seen("guide_wait") and c.state == CastState.LANDED:
                tut.draw_guide(canvas, "guide_wait", t)
        if self.training is not None:
            self.training.draw(canvas, self.mouse)
        if self.card is not None:
            tut.draw_card(canvas, self.card["key"], self._card_focus(), self.card["t"], self.touch)
        if self.help:
            if getattr(self, "help_page", 0) == 1:
                tut.draw_help_patterns(canvas, self.save.data.get("patterns_seen", []), self.touch)
            else:
                tut.draw_help(canvas, more=bool(self.save.data.get("patterns_seen")))
        if self.touch:
            self._draw_touch_controls(canvas)
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
        if f.phase == "fight":
            swing += self.ctl.pitch * self.ctl.cfg["rod_pitch_deg"]  # 낚싯대 상하 (+ = 끝이 위로)
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
        scale = 1.0 + 0.9 * b.signal_progress() if b.signal in ("jump", "leap", "lure") else 1.0
        if b.signal == "thrash":
            scale = 1.0 + 1.4 * b.signal_progress()  # 공중 몸부림: 평소 점프보다 크게
        alpha = 0.0 if b.state == "jump" else 0.7 if b.state in ("tired", "fake_tired", "exhausted") else 1.0
        # 신규 패턴: 잠수 = 작아지며 흐려짐, 역주행 = 이쪽을 향함, 비틀기 = 빙글빙글, 흔들기 = 머리를 좌우로
        k = self._pat_k
        if (d := k(b, "dive")) is not None:
            scale *= 1 - 0.45 * d
            alpha *= 1 - 0.4 * d
        if (d := k(b, "reverse")) is not None:
            heading += math.pi * d
        if (d := k(b, "twist")) is not None:
            heading += self.t * (4 + 8 * d)
        if (d := k(b, "shake")) is not None:
            heading += math.sin(self.t * 38) * (0.15 + 0.1 * d)
            wag = 30.0
        if b.doing("surface"):
            alpha = min(1.0, alpha * 1.2)
        if (d := k(b, "hide")) is not None:
            # 바위 틈으로 파고들어 흐려짐 — 고개를 내밀면 다시 보인다
            j = f._judge("hide")
            alpha *= 1.0 if j is not None and j.active and j.peeking else 1 - 0.65 * d
            wag = 2.0
        if b.doing("bite") or (b.telegraphing("bite") and b.signal_progress() > 0.6):
            heading += 0.5 * math.sin(self.t * 20)  # 고개 돌림
        if b.state == "fake_tired":
            # 가짜 지침: 꼬리지느러미가 까딱 (진짜는 축 처짐 = 꼬리 멈춤)
            wag = 16.0 if (self.t * 2.2) % 1.0 < 0.18 else 3.0
        elif b.state == "tired":
            wag = 0.5
        if f.fish["rarity"] == "legend":
            scale *= self.fish_cfg["legend"]["shadow_scale"] * 0.55
        alpha *= f.fish.get("shadow_alpha", 1.0)  # 투명 변이
        glow = GLOW.get(f.fish["rarity"])
        muts = f.mutations
        if muts:
            # 변이: 그림자 테두리가 변이 색으로 빛난다 (투명은 빼고)
            from src.fishing.mutation import cfg as mcfg
            shown = [m for m in muts if m != "clear"]
            if shown:
                glow = tuple(mcfg()["kinds"][shown[int(self.t * 1.5) % len(shown)]]["color"])
        from src.ui import rush_cue
        mods = rush_cue.shadow_mods(self._rush_ph())  # 돌진: 웅크림 압축·꼬리 S자 / 돌진 늘어남
        if mods.get("curl"):
            wag = 0.0
        return {"x": x, "z": z, "heading": heading, "alpha": alpha, "len": f.fish["shadow_len_m"],
                "scale": scale, "wag": wag, "glow": glow, **mods}

    def _line_pal(self, pal: dict) -> dict:
        """낚싯줄·뜰채 티어 외형: 줄 색(시간대 밝기와 섞음)·PE 색 마디·빛, 뜰채 테·그물·손잡이·장식·빛."""
        from src.render.rod import gear_look
        lk = gear_look("line", self.save.gear_tier("line"))
        col = lerp_color(pal["line"], tuple(lk["color"]), 0.75)
        out = dict(pal, line=col)
        if lk.get("marks"):
            out["line_marks"] = lerp_color(pal["line"], tuple(lk["marks"]), 0.8)
        if lk.get("glow"):
            out["line_glow"] = col
        nk = gear_look("net", self.save.gear_tier("net"))  # 뜰채 티어 외형
        for key in ("frame", "mesh", "handle", "trim", "glow"):
            if nk.get(key):
                out[f"net_{key}"] = tuple(nk[key])
        return out

    def _rush_audio(self) -> None:
        """v0.8.14 롤백 (사운드 개편 전 그대로): 줄 펄스 동안 울림 음이 단계마다 높아지고 돌진 silence_sec 전 무음,
        진동은 약하게 시작해 점점 세게."""
        ph = self._rush_ph(visual=False)
        if ph is None or ph["stage"] != "pulse":
            return
        from src.ui import rush_cue
        c = rush_cue.cfg()
        if ph["left"] <= c["silence_sec"]:
            return
        steps = 8
        i = min(steps - 1, int(ph["q"] * steps))
        if i > getattr(self, "rush_hum_i", -1):
            self.rush_hum_i = i
            if self.settings.get("signal_sound"):
                self.sfx.play(f"legacy_rush_hum{i}", 0.55 + 0.35 * ph["q"])
            self.game.haptics.vibrate("pump", c["haptic_min"] + (c["haptic_max"] - c["haptic_min"]) * ph["q"])

    def _rush_ph_ok(self) -> bool:
        """줄 펄스 같은 그림 예고를 보여도 되나 (소리 전용·동굴 어둠·먹물이면 숨김)."""
        f = self.fight
        b = f.brain
        return not (b.sound_only or b.dark or self.ink_t > 0 or "dark" in f.gim.kinds(b))

    def _rush_ph(self, visual: bool = True):
        """돌진 줄 펄스 단계 (src/ui/rush_cue.py). visual=True면 소리 전용·동굴 어둠·먹물에선 None (소리는 따로)."""
        f = self.fight
        if f is None or f.phase != "fight":
            return None
        b = f.brain
        if visual and (b.sound_only or b.dark or self.ink_t > 0 or "dark" in f.gim.kinds(b)):
            return None
        from src.ui import rush_cue
        return rush_cue.phase(f)

    @staticmethod
    def _pat_k(b, pid: str):
        """패턴 연출 세기: 행동 중 1, 예고 중엔 진행도, 아니면 None (소리 전용 물고기는 예고를 안 보여 줌)."""
        if b.doing(pid):
            return 1.0
        if b.telegraphing(pid) and not b.sound_only:
            return b.signal_progress()
        return None

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
        if (d := self._pat_k(b, "shake")) is not None:
            dx += math.sin(self.t * 70) * (1.5 + 1.5 * d)
        lf = f.line_frac
        color = pal["line"] if lf >= 0.5 else lerp_color(pal["line"], (235, 70, 55), (0.5 - lf) * 2)
        if lf < 0.25 and int(self.t * 8) % 2 == 0:
            color = (255, 90, 70)
        cracks = 0.0 if lf >= 0.5 else (0.5 - lf) * 2
        sag = max(0.0, (45 - f.tension) * 0.35) + 1
        if (d := self._pat_k(b, "reverse")) is not None and not b.doing("reverse"):
            sag += 10 * d  # 역주행 예고: 줄이 처진다
        from src.ui import rush_cue
        rph = self._rush_ph()
        lph = rush_cue.light_phase(f) if self._rush_ph_ok() else None  # 점프·방향 전환: 가벼운 줄 펄스
        sag = max(0.5, sag + rush_cue.line_sag(rph) + rush_cue.light_sag(lph))  # 웅크림: 느슨 / 돌진 순간: 팽팽
        pts = draw_line(canvas, pal, tip, (sx, sy + bob - size * 0.25), sag, bias=0.6, dx=dx, color=color,
                        cracks=cracks, t=self.t)
        rush_cue.draw_pulse(canvas, pts, rph, self.t)   # 빛 펄스: 물고기 → 손
        rush_cue.draw_taut(canvas, pts, rph, self.t)    # 돌진 순간 줄이 튕김
        rush_cue.draw_light_pulse(canvas, pts, lph, self.t)
        tw = f.twist.value / 100
        if b.telegraphing("twist") and not b.sound_only:
            tw = max(tw, 0.3 * b.signal_progress())
        if not b.sound_only or b.state == "twist" or f.twist.value > 0:
            pattern_fx.draw_line_twist(canvas, tip, (sx, sy + bob - size * 0.25), tw, self.t)
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
            self.popups.draw(canvas, self.screen_fx.map)  # 뜰채 중 한 단어 ("뜰채!")
            return
        qr = getattr(self, "quest_run", None)
        if f.phase == "caught":
            draw_catch_cut(canvas, pal, f.result, self.end_t)
            fight_hud.draw_catch_info(canvas, f.result, self.end_t, self.catch_news)
            if qr is not None and qr.items and self.end_t > 1.0:
                fight_hud.draw_quests(canvas, qr.hud_lines(), self.hud_inset if self.touch else 0)  # 의뢰 상세는 결과 화면에
            if self.end_t > 1.2:
                signal_slots.draw_result_icons(canvas, self.missed_signals, self.mastery_ups,
                                               (12 + (self.hud_inset if self.touch else 0), 214), self.t)
            self._draw_access_mark(canvas)
            return
        if f.phase == "lost":
            fight_hud.draw_lose_panel(canvas, f, LOSE_REASONS[f.lose_reason], self.end_t)
            if self.missed_signals or self.mastery_ups:
                signal_slots.draw_result_icons(canvas, self.missed_signals, self.mastery_ups,
                                               (canvas.get_width() // 2 - 110, 194), self.t)
            if qr is not None and qr.items:
                fight_hud.draw_quests(canvas, qr.hud_lines(), self.hud_inset if self.touch else 0)
            self._draw_access_mark(canvas)
            return
        if self.dragon_fx is not None:
            self.dragon_fx.draw(canvas)
        if f.escape_t is not None:
            self._draw_escape(canvas, f)
            self.screen_fx.draw_edges(canvas)
            fight_hud.draw_gauges(self._gauge_canvas(canvas), pal, f, t)
            return
        self._draw_behavior_ui(canvas)
        self.popups.draw(canvas, self.screen_fx.map)
        self.screen_fx.draw_edges(canvas)
        # HUD 우선순위 (31장 C6): 1 신호 칸 / 2 장력·내구도 / 3 드랙(필요할 때만 진하게) / 4 거리(작게) / 5 의뢰·소모품(반투명).
        # 신호가 막 뜨면 3 이하는 잠깐 더 흐려진다.
        fight_hud.draw_gauges(self._gauge_canvas(canvas), pal, f, t)
        fight_hud.draw_boss_bar(canvas, pal, f)
        dim = 1.0 - 0.55 * min(1.0, self.sig_dim_t / 0.3)
        qr = getattr(self, "quest_run", None)
        if qr is not None and qr.items:
            self._faded(canvas, 150 * dim, lambda c: fight_hud.draw_quest_icon(c, qr.hud_lines(),
                                                                                  self.hud_inset if self.touch else 0))
        if self.touch:
            # 드랙·소모품·조작 안내는 터치 버튼이 대신한다
            self._faded(canvas, 200 * dim, lambda c: fight_hud.draw_distance(c, pal, f, self.hud_inset))
        else:
            need = self._drag_needed(f)
            self._faded(canvas, 255 if need else 120 * dim, lambda c: fight_hud.draw_drag(c, pal, f, need, t))
            self._faded(canvas, 200 * dim, lambda c: fight_hud.draw_distance(c, pal, f))
            self._faded(canvas, 150 * dim, lambda c: self._draw_fight_items(c, pal, f))
        if f.phase == "fight":
            self._draw_fish_cues(canvas)  # 물고기 자리 행동 UI — 가장 위 (가장 선명)
        if self.debug:
            pad_side = self.touch and not self.settings.get("touch_left")
            fight_hud.draw_debug(canvas, f, self.ctl.debug_lines(self.t), 100 if pad_side else 4)

    def _equipped_float(self) -> dict | None:
        """엘드라시온에서 장착한 특수 찌 (샤르미온에선 효과도 외형도 없음)."""
        fid = self.save.data["float"].get("equipped")
        if not fid or self.spot.get("continent") != "eldrasion":
            return None
        return next((f for f in load_json("floats.json")["floats"] if f["id"] == fid), None)

    def _draw_float_mark(self, canvas, x: float, y: float, size: float, dip: float) -> None:
        """특수 찌 문양: 마비=노란 번개, 심마비=이중 번개, 결박=은빛 사슬, 봉인=푸른 봉인진, 천해=별빛 봉인진."""
        fl = self._equipped_float()
        if fl is None or size < 4 or dip >= 0.95:
            return
        col = tuple(fl["color"])
        x, y = int(x), int(y - size * 0.35)
        pat, t = fl["pattern"], self.t
        if pat in ("zigzag", "double_zigzag"):
            for k in range(2 if pat == "double_zigzag" else 1):
                ox = -3 + k * 6 if pat == "double_zigzag" else 0
                pts = [(x + ox - 2, y - 4), (x + ox + 1, y - 1), (x + ox - 1, y + 1), (x + ox + 2, y + 4)]
                pygame.draw.lines(canvas, col, False, pts, 1)
        elif pat == "chain":
            for k in range(3):
                pygame.draw.ellipse(canvas, col, (x - 2, y - 5 + k * 3, 4, 3), 1)
        else:
            r = 5 + int(1.5 * math.sin(t * 3))
            pygame.draw.circle(canvas, col, (x, y), r, 1)
            if pat == "star_seal":
                for k in range(5):
                    a = t * 0.8 + k * math.tau / 5
                    canvas.fill((255, 255, 255), (int(x + math.cos(a) * r), int(y + math.sin(a) * r), 1, 1))

    def _bobber_pal(self, pal: dict) -> dict:
        """찌 색: 반짝이 찌(외형) / 바람개비 찌(가짜 입질 때 하늘색 깜빡)."""
        out = pal
        fl = self._equipped_float()
        if fl is not None:
            out = dict(out, bobber=tuple(fl["color"]))
        from src.save.quests import skin_colors
        skin = skin_colors(self.save, "float_skin")
        if skin:
            out = dict(out, bobber=skin[0], bobber_base=skin[1])  # 의뢰 상점 찌 외형
        if self.save.cosmetic_on("sparkle_float"):
            glint = 0.5 + 0.5 * math.sin(self.t * 6)
            out = dict(out, bobber=lerp_color((255, 196, 60), (255, 250, 200), glint * 0.5))
        if (self.save.charm_on("pinwheel_float") and self.bite.state == BiteState.NIBBLE and self.bite.dip > 0.03):
            out = dict(out, bobber=(90, 220, 255))
        return out

    def _draw_lure_mark(self, canvas, sh, t: float) -> None:
        """루어로 꾀는 중인 그림자 위 반응: ? 관심 / ! 다가옴 / ♥ 곧 문다 / … 떠남 (관심도 숫자는 안 보인다)."""
        if sh is None or not self.bite.lure.engaged or not (sh.get("lurk") or sh.get("leaving")):
            return
        p = self.cam.project(sh["x"], sh["z"])
        if not p or sh.get("alpha", 1) < 0.2:
            return
        from src.fishing.lure import cfg as lure_cfg
        lc = lure_cfg()
        k = self.bite.interest()
        if sh.get("leaving"):
            mark, col = "…", (170, 180, 200)
        elif k >= lc["circle_at"]:
            mark, col = "♥", (255, 130, 160)
        elif k >= lc["approach_at"]:
            mark, col = "!", (255, 214, 90)
        elif k >= lc["turn_at"]:
            mark, col = "?", (220, 230, 245)
        else:
            return
        bob = math.sin(t * 5) * 1.5
        hud.text(canvas, mark, (p[0], int(p[1] - 12 + bob)), col, 16, "center")

    def _draw_lure_status(self, canvas) -> None:
        """찌가 떠 있는 동안 내 입력이 어떻게 읽혔는지: 톡! 저킹(간격) / 리트리브 중 / 멈춤…"""
        if self.cast.state != CastState.LANDED or self.bite.state == BiteState.BITE or not self.bite.lure.engaged:
            return
        msg, col = None, (190, 220, 255)
        fb = getattr(self, "lure_fb", None)
        if self.ctl.lure == "retrieve":
            msg = "리트리브 중 (천천히 감기)"
        elif fb is not None and self.t - fb[1] < 1.2:
            msg = fb[0]
        elif self.ctl.lure == "pause":
            msg, col = "멈춤…", (170, 180, 200)
        if msg:
            w, h = canvas.get_size()
            hud.text(canvas, msg, (w // 2, h - 30), col, 11, "center")

    def _fight_text_mode(self) -> bool:
        """파이팅(뜰채 포함) 중: 글자 예산 1개·6글자 (31장)."""
        return self.fight is not None and self.fight.phase in ("fight", "net")

    def _say(self, s: str, color) -> None:
        """파이팅 중 한 단어: 판정 글자와 같은 슬롯 하나 (새 글자가 이전 글자를 바로 지운다)."""
        self.popups.say(s, color, (self.cam.width // 2, 78), 1.2)

    GAUGE_W = 170  # 파이팅 게이지 묶음 폭 (fight_hud.draw_gauges 가 왼쪽 0~170px에 그림, 물살 표시 포함)

    def _gauge_canvas(self, canvas):
        """왼손잡이 터치 모드면 게이지를 오른쪽 가장자리에 (왼쪽 아래는 릴 패드 자리)."""
        sx = self.game.screen.safe_x
        if self.touch and self.settings.get("touch_left"):
            w, h = canvas.get_size()
            return canvas.subsurface((w - self.GAUGE_W - sx, 0, self.GAUGE_W, h))
        if sx:
            return canvas.subsurface((sx, 0, self.GAUGE_W, canvas.get_height()))
        return canvas

    @property
    def hud_inset(self) -> int:
        """모바일: 위쪽 HUD 글자를 일시정지·가방 버튼만큼 안쪽으로."""
        if not self.touch:
            return 0
        return load_json("mobile_config.json")["hud_inset_px"] + self.game.screen.safe_x

    def _draw_touch_controls(self, canvas) -> None:
        from src.platform import touch_ui
        inp = self.game.input
        ctx = self.touch_context()
        controls = touch_ui.layout(canvas.get_width(), canvas.get_height(), ctx, self.settings, inp.items_open)
        inp.controls = controls
        touch_ui.draw(canvas, controls, inp.pressed_controls(), self.settings, inp.aim, ctx["drag"],
                      inp.pitch)

    def _draw_fight_items(self, canvas, pal, f) -> None:
        """파이팅 중 쓸 수 있는 소모품 표시 (왼쪽 아래, 드랙 밑)."""
        # 글자 대신 그림 (31장): 실타래·부적 아이콘 + 개수는 점, 이번 파이팅에 썼으면 흐리게. 키(1·2)는 도움말에.
        from src.ui import icons
        col = pal["text"] if not f.consumable_used else (110, 116, 130)
        x = 14
        for iid, draw in (("repair_spool", icons.line), ("calm_charm", icons.tension)):
            n = self.save.consumable_count(iid)
            if not n:
                continue
            draw(canvas, x, 242, col)
            icons.pips(canvas, x + 14, 242, min(n, 3), col, 4)
            x += 34

    def _draw_gimmick_world(self, canvas, pal) -> None:
        """기믹 연출 (월드): 동굴 어둠, 얼음 구멍 가장자리, 엉킨 갈대, 열수 김."""
        f, cam, t = self.fight, self.cam, self.t
        fighting = f is not None and f.phase == "fight"
        kinds = f.gim.kinds(f.brain) if fighting else ({self.current_gimmick()} - {None})
        if "ice" in kinds:
            # 얼음 구멍: 정면 ±0.25rad 경계선
            hole = self.fish_cfg["gimmick"]["ice_hole"]
            out = fighting and f.gim.ice_out and int(t * 8) % 2 == 0
            col = (255, 120, 120) if out else lerp_color(pal["sky_bottom"], (230, 245, 255), 0.6)
            yaw = f.yaw if fighting else 0.0
            for s in (-1, 1):
                pts = []
                for z in range(4, 46, 3):
                    p = cam.project(math.sin(yaw + s * hole) * z, math.cos(yaw + s * hole) * z)
                    if p:
                        pts.append((p[0], p[1]))
                if len(pts) > 1:
                    pygame.draw.lines(canvas, col, False, pts, 2)
                    # 얼음 가장자리: 바깥쪽으로 삐죽한 얼음 조각
                    for i, (px, py) in enumerate(pts[::2]):
                        ln = 3 + (i * 7) % 5
                        pygame.draw.line(canvas, col, (px, py), (px + s * ln, py - 1), 1)
        if fighting and "tangle" in kinds and f.gim.tangle > 45:
            # 엉킨 갈대가 줄을 감는다
            x, y = self._fish_screen()
            k = f.gim.tangle / 100
            col = lerp_color((200, 210, 225), (255, 130, 120), max(0.0, k - 0.6) * 2.5)
            for i in range(int(3 + 6 * k)):
                a = i * 1.7 + t
                pygame.draw.line(canvas, col, (x + math.cos(a) * 6, y + 4), (x + math.cos(a) * 12, y - 10 - i % 3 * 4), 1)
        if fighting and "heat" in kinds and f.gim.heat_dmg > 0 and int(t * 10) % 3 == 0:
            x, y = self._fish_screen()
            self.bubbles.spawn(x + random.uniform(-8, 8), y, 3.0)
        if "dark" in kinds or self.theme.get("terrain") == "cave":
            # 어둠: 찌(또는 물고기) 주변만 보인다
            if fighting:
                cx, cy = self._fish_screen()
            else:
                p = cam.project(self.cast.bx, self.cast.bz) if self.cast.state != CastState.READY else None
                cx, cy = (p[0], p[1]) if p else (cam.cx, cam.horizon + 40)
            veil = pygame.Surface((cam.width, cam.height), pygame.SRCALPHA)
            veil.fill((4, 6, 18, 175))
            for r, a in ((78, 140), (60, 100), (44, 60), (28, 25)):
                pygame.draw.circle(veil, (4, 6, 18, a), (int(cx), int(cy)), r)
            canvas.blit(veil, (0, 0))

    def _draw_escape(self, canvas, f) -> None:
        """마지막 발악: 눈이 번쩍 → '투둑!' → 깊은 곳으로."""
        x, y = self.screen_fx.map(self._fish_screen())
        x, y = clamp(x, 50, self.cam.width - 50), clamp(y, 60, self.cam.height - 60)  # 화면 밖이어도 보이게
        e = f.escape_t
        if e < 0.7:
            blink = int(e * 20) % 2 == 0
            if blink:
                for dx in (-3, 3):
                    pygame.draw.circle(canvas, (255, 60, 50), (int(x + dx), int(y - 3)), 2)
                    canvas.fill((255, 255, 255), (int(x + dx), int(y - 3), 1, 1))
            text_k = e / 0.7
            fight_fx.big_text(canvas, "!!", (x, y - 22 - 6 * text_k), (255, 90, 80), 1.6, outline=True)
        else:
            k = min(1.0, (e - 0.7) / 0.3)
            pop = 1.0 + 0.6 * math.exp(-(e - 0.7) * 8)
            fight_fx.big_text(canvas, "투둑!", (x, y - 30), (255, 110, 90), 2.4 * pop, outline=True)
            if k < 1:
                fl = pygame.Surface(canvas.get_size(), pygame.SRCALPHA)
                fl.fill((255, 60, 40, int(90 * (1 - k))))
                canvas.blit(fl, (0, 0))

    def _draw_ceiling_cues(self, canvas) -> None:
        """수정 동굴(어둠): 예고 신호가 천장 수정에 반사광으로 비친다. 가짜(등불)는 깜빡인다."""
        f, b, t = self.fight, self.fight.brain, self.t
        if "dark" not in f.gim.kinds(b) or b.sound_only:
            return
        sig = b.signal
        if sig is None and getattr(self, "pump_flash", 0) > 0 and b.doing("pump"):
            # 펌핑 박자: 박마다 천장 수정이 번쩍 (프리시아 '천장 반사광 박자')
            x = int(clamp(self._fish_screen()[0], 30, self.cam.width - 30))
            r = int(4 + 40 * self.pump_flash)
            pygame.draw.circle(canvas, fight_fx.ICON_COL["pump"], (x, 84), r, 2)
            return
        if sig is None:
            return
        x = int(clamp(self._fish_screen()[0], 30, self.cam.width - 30))
        y = 84  # 천장 수정 (수평선 위)
        prog = b.signal_progress()
        if sig == "lure" and int(t * 12) % 2 == 0:
            return  # 가짜 반사광은 깜빡인다
        col = {"jump": (255, 214, 90), "lure": (255, 214, 90), "leap": (120, 220, 255), "rush": (240, 245, 255),
               "turn": (200, 180, 255)}.get(sig, fight_fx.ICON_COL.get(sig, (255, 255, 255)))
        r = int(4 + 6 * prog)
        glow = pygame.Surface((60, 60), pygame.SRCALPHA)
        pygame.draw.circle(glow, (*col, 70), (30, 30), r + 10)
        canvas.blit(glow, (x - 30, y - 30))
        pts = [(x, y - r - 2), (x + r, y), (x, y + r + 2), (x - r, y)]
        pygame.draw.polygon(canvas, col, pts)
        pygame.draw.polygon(canvas, (255, 255, 255), pts, 1)
        if sig == "leap":
            d = -b.leap_dir
            pygame.draw.polygon(canvas, col, [(x + d * (r + 14), y), (x + d * (r + 6), y - 5), (x + d * (r + 6), y + 5)])
        elif sig == "turn":
            d = b.turn_dir
            pygame.draw.polygon(canvas, col, [(x + d * (r + 14), y), (x + d * (r + 6), y - 5), (x + d * (r + 6), y + 5)])
        elif sig == "rush":
            pygame.draw.line(canvas, col, (x, y + r + 4), (x, y + r + 16 * prog + 6), 2)

    def _draw_behavior_ui(self, canvas) -> None:
        """대응 신호는 신호 슬롯 두 칸에만 (31장 C3). 여기선 물고기 몸짓 쪽 연출(동굴 천장 반사광)만."""
        self._draw_ceiling_cues(canvas)

    def _draw_fish_cues(self, canvas) -> None:
        """물고기 자리 행동 UI (31-11): 예고 카운트다운 → 진행 장치 → 판정이 물고기에 붙어서 진행."""
        from src.ui import fish_cues
        f, b = self.fight, self.fight.brain
        dark = "dark" in f.gim.kinds(b)
        inked = self.ink_t > 0 or b.dark
        sigs = signal_slots.collect(f, b.sound_only, inked, dark)
        x, z = f.fish_xz()
        mp = self.screen_fx.map

        def apex(hgt):
            p = self.cam.project(x, z, hgt)
            return mp((p[0], p[1])) if p else None

        fish_cues.draw(canvas, {"fight": f, "sigs": sigs, "anchor": mp(self._fish_screen()), "apex": apex,
                                "touch": self.touch, "t": self.t, "flick_cfg": self.flick_cfg,
                                "fight_cfg": self.fish_cfg["fight"],
                                "judge_busy": any(it["t"] < 0.8 for it in self.popups.items)})

    def _layer(self, canvas) -> pygame.Surface:
        lay = getattr(self, "_fade_layer", None)
        if lay is None or lay.get_size() != canvas.get_size():
            lay = self._fade_layer = pygame.Surface(canvas.get_size(), pygame.SRCALPHA)
        lay.set_alpha(255)  # None 이면 픽셀 알파 섞기가 꺼져 투명 칸이 검게 덮인다
        lay.fill((0, 0, 0, 0))
        return lay

    def _faded(self, canvas, alpha: float, fn) -> None:
        """우선순위 낮은 HUD를 반투명으로 (31장 C6)."""
        if alpha >= 250:
            fn(canvas)
            return
        lay = self._layer(canvas)
        fn(lay)
        lay.set_alpha(int(max(0, alpha)))
        canvas.blit(lay, (0, 0))

    def _drag_needed(self, f) -> bool:
        """드랙 칸을 진하게: 돌진·힘 모으기·장력 빨강, 또는 방금 드랙을 바꿨을 때."""
        if f.drag != getattr(self, "_drag_last", f.drag):
            self.drag_seen_t = 1.2
        self._drag_last = f.drag
        return f.brain.state in ("rush", "charge") or f.zone() == "red" or getattr(self, "drag_seen_t", 0.0) > 0

    def _draw_access_mark(self, canvas) -> None:
        """접근성 예고 배율을 썼으면 결과 화면 오른쪽 아래에 작게 (랭크 판정은 그대로)."""
        m = getattr(self.fight.brain, "access_mult", 1.0)
        if m != 1.0 and self.end_t > 1.0:
            inset = self.hud_inset if self.touch else 0
            hud.text(canvas, f"예고 ×{m:g}", (canvas.get_width() - 8 - inset, canvas.get_height() - 8), (150, 158, 180),
                     11, "bottomright")

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
            # 살랑살랑: 위아래 + 좌우로 아주 조금 (저킹이면 톡 튐)
            bob = math.sin(self.t * 2.0) * max(0.5, s * 0.012)
            hop = getattr(self, "lure_hop", 0.0)
            if hop > 0:
                bob -= math.sin(math.pi * hop / 0.18) * max(1.5, s * 0.05)
            sx += math.sin(self.t * 1.3) * max(0.3, s * 0.006)
        if c.state == CastState.RETRIEVE or dip > 0.5:
            sag = 3  # 팽팽
        else:
            sag = 10 + abs(tip[0] - sx) * 0.04
        draw_line(canvas, pal, tip, (sx, sy + bob - size * 0.5 * (1 - dip)), sag, bias=0.6)
        draw_bobber(canvas, self._bobber_pal(pal), sx, sy + bob, size, floating=True, dip=dip)
        self._draw_float_mark(canvas, sx, sy + bob, size, dip)
