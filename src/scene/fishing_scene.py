"""1인칭 낚시 장면: 캐스팅 → 입질 → 챔질 → 파이팅 → 뜰채 → 획득."""
import math
import random
import time

import pygame

from src.audio import reel_audio
from src.core.config import game_config, load_json
from src.core.fonts import get_font
from src.core.game_clock import PERIODS, GameClock
from src.core.weather import WEATHER_KO, Weather
from src.core.mathutil import clamp, lerp, lerp_color, scale_color, smoothstep
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
from src.render.phantom_fx import PhantomFx, phantom_palette
from src.fishing import phantom
from src.render.rod import draw_rod, rod_geometry
from src.render.screen_fx import ScreenFX
from src.render.boss_arena import BossArena
from src.save.scalestone import frac as _ss_frac
from src.audio import theme_sfx
from src.render.weather_fx import Ambient, Fog, Lightning, Rain, themed_palette
from src.scene.base import Scene
from src.ui import fight_fx, fight_hud, hud, pattern_fx, signal_slots
from src.ui import tutorial as tut
from src.ui import widgets as ui_w


def float_name(tier: int) -> str:
    """특수 찌 티어 → 이름."""
    return next((f["name"] for f in load_json("floats.json")["floats"] if f["tier"] == tier), "특수 찌")

HINTS = {
    CastState.READY: "좌클릭 유지: 던지기   오른쪽 버튼: 지도·상점·의뢰·수집",
    CastState.CHARGING: "놓으면 던지기   우클릭: 취소",
    CastState.SWING: "",
    CastState.FLIGHT: "",
    CastState.LANDED: "좌클릭: 챔질(쑥!)   우클릭: 회수   화면 끝: 둘러보기",
    CastState.RETRIEVE: "줄 감는 중...",
    CastState.HOOKED: "좌클릭 유지: 감기   우클릭: 숙이기   Q/E·휠: 드랙   마우스: 버티기   H: 도움말",
}
GOOD = (140, 240, 150)
BAD = (255, 150, 130)
INFO = (255, 235, 170)
LOOK_STATES = (CastState.READY, CastState.LANDED)
WEATHERS = ["clear", "rain", "storm", "fog"]
GLOW = {"rare": (150, 210, 255), "legend": (255, 215, 100), "phantom": (210, 150, 255)}
DRAGON_LOOK = {"colors": {"body": [200, 40, 40], "belly": [255, 214, 110], "fin": [255, 170, 40],
                          "stripe": [255, 230, 140]},
               "shape": {"height": 0.13, "whiskers": True, "dorsal": "crest", "tail": "fork", "pattern": "spots"}}

# 튜토리얼 카드를 본 뒤 한 번 더 짧게 상기시킨다 (DESIGN.md 4장)
TIPS = {
    "telegraph:rush": "빛이 줄을 타고 손에 닿는 순간 돌진! 그때 Q(풀기) 한 번",
    "telegraph:jump": "그림자가 커진다 = 점프! 원이 겹치는 순간 우클릭",
    "telegraph:turn": "줄이 쏠린다 = 방향 전환! 꺾는 순간 반대쪽으로 확 슬라이드",
    "telegraph:leap": "하늘색 원 = 몸털기! 원이 겹칠 때 화살표 쪽으로 슬라이드",
    "action:charge": "멈췄다 = 힘 모으기! 지금 확 감으세요",
    "tired": "지쳤다! 지금 크게 감으세요",
    "fake_tired": "기포가 계속 올라온다 = 가짜 지침! 돌진 대비",
    "telegraph:lure": "등불만 번쩍 = 가짜 신호! 기포·판정 원이 없으면 속지 마세요",
    "gap_open": "땀방울 = 틈! 지금 꾹 감으면 크게 지쳐요",            # CU4-3
    "overtime": "너무 오래 끌었다 — 줄이 닳기 시작! 신호를 받아내 지치게 하세요",   # CU4-2
    "arm_out": "팔 힘이 바닥! 날뛸 땐 손을 놓고 쉬다가, 쉬거나 지칠 때 감으세요",   # CU5-1
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
SUCC_RESET = ("miss_early", "miss_late", "miss_none", "flick_miss", "rush_fail", "combo_fail", "combo_break", "pump_miss")
SUCC_MID = ("hide", "reverse", "twist")  # 성공음 mid: 숨기 기습·역주행 회수·꼬임 완전 해소 — 그 밖의 패턴 성공은 small
FORCE_PATTERNS = ("shake", "dive", "surface", "reverse", "twist", "chain", "hide", "pump", "thrash", "bite", "fake", "dual")
PATTERN_EVENTS = ("twist_snap", "twist_turn", "combo_break", "combo_ok", "pump_hit", "pump_miss", "hide_peek",
                  "double_perfect", "thrash_second_miss", "stiff", "dual_ok", "fake_tired")
TIP_REPEAT = 1
SLACK_RED_CARD_SEC = 0.6  # 이 시간 이상 느슨/빨강이면 튜토리얼 카드


GUIDE_FIRST = ("telegraph:rush", "telegraph:jump", "telegraph:turn", "action:charge", "fake_tired")


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
        self.exam_fish = None   # 백 노인의 시험 (49-3): 이번 착수의 시험 물고기 (시험 찌 · 시험 낚시터)
        self.exam_run = None    # 시험 판 진행 중 {"tier", "miss": {패턴: 놓친 수}}
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
        self.school: dict | None = None    # 물고기 떼 지나감 (CU9): {"x", "z", "t", "life"}
        self.breach = None                 # 전설 등장 도약 (CU10, LEGEND_BREACH): 동안 파이팅 정지
        self.p3 = None                     # 전설 3페이즈 컷신 (CU11): 눈빛 대치 + 각자의 필살
        self.school_next = random.uniform(*load_json("core.json")["variety"]["school_interval_sec"])
        self.popups = fight_fx.JudgePopups()
        self.gather = fight_fx.GatherFX()
        self.screen_fx = ScreenFX(canvas.get_width(), canvas.get_height())
        self.arena = BossArena(canvas.get_width(), canvas.get_height())   # 보스전 무대 (BOSS_ARENA.md, 51-2)
        self.crisis_now = False
        self.fish_cfg = load_json("fishing_config.json")
        self.core_arm = load_json("core.json")["arm"]   # 팔 힘 · 무게 단서 (CU5)
        from src.ui.progress_line import EarnRate
        self.earn_rate = EarnRate()        # 진행 막대 (CU8-②): 최근 30분 시간당 수입
        self.prog_rect = None
        self.prog_open_t = 0.0
        self.spots = {sp["id"]: sp for sp in load_json("spots.json")["spots"]}
        self.spot_ids = list(self.spots)
        self.force_i = -1          # F3 테스트: 고정할 물고기 인덱스 (-1 = 없음)
        self.all_fish = load_json("fish.json")["fish"]
        force = self.fish_cfg.get("debug_force_fish")
        if force:
            self.force_i = next((i for i, x in enumerate(self.all_fish) if x["id"] == force), -1)
        self._set_spot(self.save.data["spot"] if self.save.data["spot"] in self.spots else "reservoir")
        d = self.save.data
        # 날씨 = 정해진 예보표 (TIME_REST 🅰, DESIGN 48장): 세이브 weather_seed 하나로 (낚시터, 3시간 칸)마다 정해짐
        self.weather_sys = Weather(d, self.spot_id, self.spot["weather"])
        self.weather_sys.update(self.clock.day, self.clock.hour)
        self.rain = Rain(canvas.get_width(), canvas.get_height())
        self.fog = Fog(canvas.get_width(), canvas.get_height())
        self.lightning = Lightning()
        from src.render.screen_weather import ScreenWeather, Wind
        self.wind = Wind()   # 바람 (DETAILS A-2, DESIGN.md 45장): 줄 휨 · 빗줄기 각도 · 날림 · 갈대 방향
        self.screen_weather = ScreenWeather(canvas.get_width(), canvas.get_height())   # 화면에 맺히는 날씨 (A-1)
        from src.render.map_fx import MapFx
        self.map_fx = MapFx(canvas.get_width(), canvas.get_height())   # 낚시터별 · 행동 반응 · 반딧불 (A-3 · A-4 · A-5)
        self.cast_drops = [0, 0.0]   # 캐스팅 물방울 [남은 수, 다음까지]
        from src.render.hook_cine import HookCine
        self.hook_cine = HookCine()   # 고등급 입질 연출 ① 예고 · ② 챔질 연출 (DETAILS B, DT4~DT6)
        self.cine_full = False        # 디버그 Shift+F3: 본 종이어도 늘 전체 버전
        # 환상 2페이즈 컷신 (PHANTOM_PHASE2.md, DESIGN.md 33-12)
        self.p2 = None              # Phase2Cine (재생 중 · 재개 뒤 보라 강도 되돌리는 0.5초까지)
        self.p2_pending = None      # 2페이즈 진입 → 패턴 판정이 끝나면 시작 {"mode", "t"}
        self.p2_force = None        # 디버그 Shift+F4/F6: 다음 2페이즈 컷신 버전 강제
        self.p2_card = None         # 첫 만남 신호 카드 (컷신이 끝난 뒤, 재개 전)
        self.p2_on = False          # 2페이즈 뒷배경 보랏빛 오라 켜짐 (2페이즈 내내)
        self.p2_aura = 0.0          # 오라 페이드 0~1 (포획 0.5초 · 실패 · 도주 1초에 사라짐)
        self.p2_aura_fade = 1.0
        self.p2_log: list = []      # 컷신 전후 수치 (검증용)
        self.sig_dim_t = 0.0
        self.cine_clock = time.perf_counter   # 입질 연출 시계 (실제 시간, 시험에선 바꿔 끼움)
        # 손 · 장비 · 잡은 직후 (DETAILS C · D, DT7)
        self.wet_t = 0.0            # 뜰채로 건진 뒤 젖은 손 남은 시간
        self.bait_anim = None       # 미끼 끼우기 0.8초 (남은 시간)
        self.last_bait = self.save.data.get("gear", {}).get("bait")
        self.board = None           # 계측판 (MeasureBoard)
        self.release_scene = None   # 놓아주기 1초 장면
        self.release_item = None    # 놓아줄 수 있는 살림망 항목 (방금 잡은 일반 · 고급 · 희귀)
        from src.render.ambient_life import AmbientLife
        self.life = AmbientLife()   # 살아 있는 주변 (DETAILS E, DT8) — 그림 · 소리만
        from src.render.legend_hook_fx import LegendHookFx
        self.legend_fx = LegendHookFx()   # 전설 입질 연출 그림 (DT5)
        from src.render.phantom_hook_fx import PhantomHookFx
        self.phantom_hfx = PhantomHookFx()   # 환상 입질 연출 그림 (DT6)
        self.cine_ran = False             # 방금 ② 챔질 연출이 있었나 (파이팅 시작 '전설!' 소리 · 흔들림 생략)
        self.last_line_pts = None
        self.reel_drop_t = 0.0
        self.thrash_t = 0.0
        from src.render.ilseom_fx import IlseomFX
        self.ilseom_fx = IlseomFX()   # 청새치 '일섬' 칼 연출 (ILSEOM.md, DESIGN.md 43-15)
        self.ambient = Ambient(canvas.get_width(), canvas.get_height(), self.cam.horizon)
        from src.audio.ambience import Ambience
        self.ambience = Ambience(self.sfx)  # 환경음: 바탕 + 무작위 조각 + 날씨 + 천둥 시간차 (32장 S7)
        self.legend_on = False   # 전설 등장 중 (BGM·색감·금빛 테두리)
        self.legend_k = 0.0
        self.red_t = self.crisis_hold = 0.0  # Z4 파이팅 음악 위기 판정 (빨강 지속·해소 뒤 유지)
        self.dragon_k = 0.0      # '등용' 3페이즈: 진홍빛 하늘
        self.phantom_fx = PhantomFx(phantom.spawn_cfg())  # 환상의 물고기 보랏빛 파장 (33장)
        self.force_phantom = False   # 디버그 F7: 다음 착수 환상 강제
        self.glints: list[list[float]] = []  # 먼 수면 보라빛 물결 (x, z, t)
        from src.render.season_fx import SeasonParticles
        from src.render.event_fx import EventFx
        self.season_fx = SeasonParticles()   # 계절 파티클 (35-4)
        self.event_fx = EventFx()            # 날씨 이벤트 연출 (35-14)
        self.event_banner = None             # {"id", "t"} 이벤트 시작 배너 (파이팅 중이 아닐 때만)
        self.event_pending = None
        self.backdrop = None       # 마을이 열려 있으면 마을 풍경 (src/scene/village.py) — 겹친 화면 뒤 배경
        self.catch_show = None     # 환상·전설 포획 연출 (src/render/phantom_show.py · legend_show.py)
        self.phantom_song_ch = self.phantom_loop_ch = None
        self.show_pity = False       # 디버그 F8: 낚시터별 천장 카운트
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
        self.collect_open = False        # 오른쪽 메뉴 '수집' 서랍 (도감·업적·어탁·수조)
        self.collect_k = 0.0
        self.slack_t = self.red_t = 0.0
        self.shake_on = self.settings.get("screen_shake")
        self.screen_fx.enabled = self.shake_on
        self.shake_kick = 0.0
        from src.audio.fight_audio import FightAudio
        self.fight_audio = FightAudio(self.sfx)  # 상태 연동 연속음 (32장 S4)
        self.fight_audio.reel.prepare()  # 릴·돌진·챔질 소리 (오디오 최종 팩)
        self.rt_fx: list[list] = []      # [실제 시각, 함수] — 성공음 타격 시점(impact_ms)에 맞춘 연출·진동
        from src.audio.signal_audio import SignalAudio
        self.signal_audio = SignalAudio(self.sfx, lambda: self.settings.get("signal_sound"),
                                        lambda: self.settings.get("signal_mode"),
                                        lambda: self.save.data.get("pattern_mastery", {}) if self.save else None,  # 신호 6계열 (S5, 모드 N2)
                                        boss=lambda fight: self.arena.active and self.arena.end_t is None,   # 보스 예고음 (51-3)
                                        on_hit=lambda kind: self._arena_event(kind) if self.arena.active else None)
        self.signal_audio.accent = self._boss_accent   # 보스별 악센트 (BA4)
        self.cast_far = self.fish_cfg["cast"]["max_distance"]  # 소리 거리 감쇠 기준
        self.cast_loops: dict[str, str | None] = {"charge": None, "line": None}
        self.captions = None     # [글자, 남은 시간] 소리 자막
        self.t = 0.0
        self.campfire_line = None   # (글자, 끝 self.t) — 모닥불의 작은 일 한 줄 (TIME_REST 🅳)
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
        if getattr(self, "weather_sys", None) is not None:
            self.weather_sys.set_spot(spot_id, self.spot["weather"])   # 그 낚시터의 예보표 (DESIGN 48장)
        self.theme = self.spot["theme"]
        self.hazard_decor = world.HazardDecor(self.spot["hazards"])
        self.screen_fx.sway = self.theme.get("sway", 0)
        self.game.sfx.set_space(spot_id)  # N5: 낚시터 잔향·먹먹함 (공간별로 미리 구운 소리)
        # 전설 등장 '드론' · 환상 파장 울림: 처음 울리는 순간 파일 읽느라 멈추지 않게 미리 (DESIGN.md 44)
        self.game.sfx.prefetch(("sfx_legend_appear", "sfx_phantom_hum"))
        self.game.boss.prepare_for_spot(spot_id, self.all_fish)   # 이 낚시터 전설의 SUNO 곡을 미리 (BOSS_BGM_SUNO.md)
        from src.core import gcwatch
        gcwatch.settle(collect=True)   # 낚시터 준비 끝: 한 번 치우고 얼림 → 플레이 중 GC 가 이 객체들을 다시 훑지 않게 (O6)

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
        """지도에서 이동: 1시간 흐름. 도착한 낚시터의 예보표 그대로 (다시 뽑지 않음, TIME_REST 🅰) — 도착 토스트에 날씨."""
        self.bite.stop()
        self.cast.reset()
        self.cam.yaw = 0.0
        self._set_spot(spot_id)
        self.save.data["continent"] = self.spot.get("continent", "sharmion")
        self._advance_hours(1.0)
        self.toasts.show(f"{self.spot['name']}에 도착했다 · {WEATHER_KO[self.weather]}", GOOD, 2.0)
        left = sum(1 for f in self.all_fish if f["spot"] == spot_id and not self.save.caught(f["id"]))   # 남은 미지 (CU9)
        self.toasts.show(f"이 물에 아직 못 본 물고기 {left}종" if left else "이 물의 물고기를 모두 만났어요",
                         (190, 225, 255) if left else (255, 214, 90), 2.6, 11)
        line = phantom.rumor()  # 가끔 소문 한 줄 (로딩 문구 풀, 33장 P6)
        if line:
            self.toasts.show(line, (190, 160, 235), 3.2, 11)
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

    def _draw_progress(self, canvas, x: int, y: int) -> None:
        """진행 막대 (CU8-②): "다음: 시험 자격 2/3 · 장비까지 12,400원 (약 25분)", 누르면 4초 동안 자격 · 장비 목록."""
        self.prog_rect = None
        if not self.settings.get("progress_line") or self.training is not None or self.exam_run is not None:
            return
        from src.ui.progress_line import summary
        info = summary(self.save, self.earn_rate.per_hour())
        if info is None:
            return
        line, more = info
        self.prog_rect = hud.text(canvas, line, (x, y), (205, 210, 225), anchor="topleft")
        if self.prog_open_t > 0:
            for i, ln in enumerate(more):
                hud.text(canvas, ln, (x + 6, y + 12 + i * 11), (175, 182, 200), anchor="topleft")

    def _draw_tide(self, canvas, clock_rect, t: float) -> None:
        """시계 옆 소라 아이콘 + 남은 실제 시간 9:41 (끝나기 blink_sec 전부터 깜빡)."""
        from src.save import item_use
        left = item_use.tide_left(self.save)
        if left <= 0 or clock_rect is None:
            return
        if left < item_use.tide_cfg()["blink_sec"] and int(t * 3) % 2:
            return
        x, y = clock_rect.right + 8, clock_rect.centery
        hud.draw_conch(canvas, x, y)
        m, sec = divmod(int(left), 60)
        hud.text(canvas, f"{m}:{sec:02d}", (x + 8, y), (170, 210, 255), 11, "midleft")

    def _tide_tick(self) -> bool:
        """물때 멈춤 소라가 켜져 있으면 True (시계 정지). 방금 끝났으면 덮어쓴 날씨를 지우고 False."""
        from src.save import item_use
        if item_use.tide_left(self.save) > 0:
            return True
        if "tide_until" in self.save.data.get("buffs", {}):
            item_use.tide_end(self.game, self)
        return False

    def can_rest(self) -> bool:
        """파이팅 중 · 환상 대기 연출 중엔 못 쉼."""
        return self.fight is None and self.bite.phantom is None and self.landing is None

    def rest_begin(self) -> None:
        """쉬기 시작: 찌 · 입질 초기화 (모닥불 타임랩스가 시계를 옮김)."""
        self.bite.stop()
        self.cast.reset()

    def rest_end(self) -> str:
        """쉬기 끝: 날씨 이벤트 비우고 저장, 도착 시각 · 날씨 글자."""
        self.weather_sys.events.clear()
        self.game.save_now()
        return f"{self.clock.label()} · {WEATHER_KO[self.weather]}"

    def rest(self) -> str:
        """(예전 호환) 다음 시간대로 바로 — 지금은 달력의 골라 쉬기 + 모닥불 장면을 씀 (CU1)."""
        self.rest_begin()
        start, name = self._next_period()
        self._advance_hours(start - self.clock.hour)
        return self.rest_end()

    def _campfire_debug(self) -> None:
        from src.scene.campfire import CampfireScene, campfire_cfg
        if not self.can_rest():
            return
        evs = [e["id"] for e in campfire_cfg()["events"]]
        self.dbg_camp_i = (getattr(self, "dbg_camp_i", -1) + 1) % len(evs)
        self.rest_begin()
        self.game.scenes.push(CampfireScene(self.game, self, 3.0, force_event=evs[self.dbg_camp_i]))

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

    def _tick_events(self, dt: float, f) -> None:
        """날씨 이벤트 (35-14): 시작 확인 → 배너(파이팅이 끝난 뒤) · 연출 갱신."""
        from src.fishing import weather_events
        new = weather_events.tick(self.save, self.clock.day, self.clock.hour, self.weather)
        if new:
            self.event_pending = new
        busy = f is not None or self.catch_show is not None or self.landing is not None
        if self.event_pending and not busy:
            ev = weather_events.by_id(self.event_pending)
            self.event_banner = {"id": self.event_pending, "t": 0.0}
            self.event_pending = None
            self.game.guide.event("weather_event")   # TG-16
            snd, vol = ev.get("start_sound", ["amb_gust", 0.25])
            self.sfx.play(snd, vol)   # 짧은 자연음 (SOUND_CLEANUP)
        if self.event_banner is not None:
            self.event_banner["t"] += dt
            if self.event_banner["t"] > 3.5:
                self.event_banner = None
        ev = weather_events.active(self.save)
        self.event_fx.update(dt, ev["id"] if ev else None, self.cam.width, self.cam.horizon,
                             f is not None and f.phase in ("fight", "net"))

    def _event_id(self):
        from src.fishing import weather_events
        ev = weather_events.active(self.save)
        return ev["id"] if ev else None

    def _draw_event_banner(self, canvas) -> None:
        b = self.event_banner
        if b is None:
            return
        from src.fishing import weather_events
        ev = weather_events.by_id(b["id"])
        w = canvas.get_width()
        a = min(1.0, b["t"] / 0.4, (3.5 - b["t"]) / 0.6)
        band = pygame.Surface((w, 34), pygame.SRCALPHA)
        band.fill((10, 12, 26, int(150 * a)))
        canvas.blit(band, (0, 26))
        hud.text(canvas, ev["banner"], (w // 2, 38), tuple(int(v * a) for v in (255, 240, 210)), 16, "center", shadow=True)
        hud.text(canvas, f"{ev['name']} · {ev['benefit_text']}", (w // 2, 53), tuple(int(v * a) for v in (200, 220, 255)), 11, "center", shadow=True)

    @property
    def season(self) -> str:
        from src.core import season as seasons
        return seasons.current(self.settings)

    def _extra_fish(self) -> list:
        """이번 착수에 더해지는 한정 물고기 [(물고기, 가중치)]: 계절 한정(계절 고정 중엔 없음) + 날씨 이벤트 물고기."""
        from src.core import season as seasons
        from src.core.config import load_json as _lj
        out = []
        cont = self.spot.get("continent", "sharmion")
        if not seasons.locked(self.settings):
            sf = _lj("seasonal_fish.json")
            s = self.season
            out += [(f, sf["weights"][f["rarity"]]) for f in sf["fish"] if f["season"] == s and f["continent"] == cont]
        try:
            from src.fishing import weather_events
            out += weather_events.extra_fish(self.save, cont)
        except ImportError:
            pass
        return out

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
                "items": items, "drag": (f.drag, f.drag_steps) if fighting else None,
                "manual_drag": f.manual_drag if fighting else True,   # 자동 드랙(CU3)이면 ▲▼ 대신 '풀기' 버튼 하나
                "release_blink": fighting and fight_hud.release_ready(f) and int(self.t * 6) % 2 == 0,
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
            nxt = WEATHERS[(WEATHERS.index(w.current) + 1) % len(WEATHERS)]
            now = w.abs_time(self.clock.day, self.clock.hour)
            w.set_override(nxt, now, w.next_change if w.next_change > now else now + 3)   # 이번 칸 끝까지 덮어쓰기
            w.update(self.clock.day, self.clock.hour)
            w.events.clear()
            self.toasts.show(f"[테스트] 날씨: {WEATHER_KO[w.current]}", INFO, 1.5, 11)

    def _quest_events(self, qr) -> None:
        """의뢰 진행 알림: 실패는 작게, 완료는 보상과 함께."""
        for ev in qr.events:
            if ev == "quest_fail":
                from src.scene import dialogue
                dialogue.note(self.save, "quest_fail_streak", 1)   # 소라: 의뢰 연속 실패 위로 (35-12)
                pass  # N3: 낚시 화면에선 의뢰 소리 없음 (화면 알림만)
            elif ev == "quest_done":
                from src.scene import dialogue
                dialogue.note(self.save, "quest_fail_streak", value=0)
                it = next((x for x in qr.items if x[1] == "done" and len(x) > 3 and not x[3].get("_shown")), None)
                if it is not None:
                    got = it[3]
                    got["_shown"] = True
                    from src.save.quests import reward_text
                    self.toasts.show(f"의뢰 완료! {reward_text(it[0]['reward'])}", (255, 214, 90), 3.0, 11)  # 소리 없이 (N3)
                    from src.save import scalestone
                    for info in got.get("scalestones", []):   # 비늘석 (46장): 어느 등급 · 첫 옵션인지
                        txt, col = scalestone.news_line(info)
                        self.toasts.show(txt, col, 3.0, 11)
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

    def tut_busy(self) -> bool:
        """가이드 튜토리얼이 기다릴 때: 카드·도움말·환상·전설 포획 연출 중 (src/tutorial/conds.py)."""
        show = self.catch_show is not None and not self.catch_show.waiting()   # 연출 카드가 떠서 기다리는 중이면 가이드 가능 (TG-PH)
        return self.card is not None or self.help or show or self.voyage_pending

    def _guide_first(self, key: str) -> bool:
        """패턴 첫 만남 신호 → 가이드 (패턴 사전 등록은 그대로). 이번에 패턴 튜토리얼이 시작됐으면 True."""
        if self.training is not None:
            return False
        self.tutorial.mark(key)   # 패턴 사전·훈련 수조 '본 신호' 기록
        if key == "fake_tired":
            seen = self.save.data.setdefault("patterns_seen", [])
            if "fake" not in seen:
                seen.append("fake")
        g = self.game.guide
        g.event(f"first:{key}")
        return g.run is not None and g.data[g.run["id"]].get("start") == f"event:first:{key}"

    def _open_card(self, key: str, focus: str | None) -> None:
        if self.game.guide.run is not None and key != "welcome":
            self.tutorial.seen.discard(key)   # 가이드 튜토리얼 중엔 예전 카드를 띄우지 않음 (다음 기회에)
            self.settings.set("tutorial_seen", sorted(self.tutorial.seen))
            return
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
        if self.p3 is not None and self.p3.blocking and a.name != "back":
            # 전설 3페이즈 컷신: 입력 무시, 그 전설 3페이즈를 두 번째부터 0.5초 뒤 탭 = 마지막 0.3초(체력 바)로
            if a.name in ("primary", "confirm", "reel_tap") and self.p3.can_skip():
                self.p3.skip()
                if self.dragon_fx is not None and self.fight is not None and self.fight.brain.dragon:
                    self.dragon_fx = None
            return
        if self.breach is not None and self.breach.blocking and a.name != "back":
            # 전설 도약: 입력 무시, 그 전설을 두 번째부터는 0.5초 뒤 탭 = 착수 순간으로
            if a.name in ("primary", "confirm", "reel_tap") and self.breach.can_skip():
                self.breach.skip()
                self.arena.t = self.breach.t
            return
        if self.p2 is not None and self.p2.blocking and a.name != "back":
            # 2페이즈 컷신: 입력 무시, 0.5초 이후 탭 = 건너뛰기 (마지막 단계 → 다음 박에서 재개)
            if a.name in ("primary", "confirm", "reel_tap") and self.p2.can_skip():
                self.p2.skip()
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
            elif a.value in ("dex", "quests", "achievements", "calendar"):
                if self.fight is None:
                    self.open_menu(a.value)
            elif self.can_open_menus():
                self.open_menu(a.value)
        elif n == "debug":
            if a.value == "F5" and pygame.key.get_mods() & pygame.KMOD_SHIFT:
                if self.fish_cfg.get("debug_keys") or load_json("mobile_config.json").get("debug_build"):
                    # Shift+F5: 시간대 강제 (새벽 5시 → 아침 7시 → 낮 13시 → 저녁 18시 → 밤 22시, DT2 디버그)
                    marks = (5.0, 7.0, 13.0, 18.0, 22.0)
                    nxt = next((m for m in marks if m > self.clock.hour + 0.01), marks[0])
                    self.clock.hour = nxt
                    self.toasts.show(f"[테스트] 시간: {self.clock.label()}", INFO, 1.5, 11)
            elif a.value == "F3" and pygame.key.get_mods() & pygame.KMOD_SHIFT:
                if self.fish_cfg.get("debug_keys") or load_json("mobile_config.json").get("debug_build"):
                    self.cine_full = not self.cine_full   # Shift+F3: 입질 연출 늘 전체 버전 (DT4 디버그)
                    self.toasts.show(f"[테스트] 입질 연출 늘 전체 버전: {'켬' if self.cine_full else '끔'}", INFO, 1.5, 11)
            elif a.value == "F8" and pygame.key.get_mods() & pygame.KMOD_SHIFT:
                if self.fish_cfg.get("debug_keys") or load_json("mobile_config.json").get("debug_build"):
                    # Shift+F8: 비늘석 디버그 생성 — 등급 순환, 부옵션 1~5개 무작위 (46장)
                    from src.save import scalestone
                    gs = scalestone.grades()["order"]
                    self.dbg_stone_i = (getattr(self, "dbg_stone_i", -1) + 1) % len(gs)
                    n = random.randint(1, 5)
                    ids = random.sample(scalestone.options()["order"], n)
                    s = scalestone.debug_make(self.save, gs[self.dbg_stone_i], ids)
                    g = scalestone.grade_info(s["grade"])
                    self.toasts.show(f"[테스트] 비늘석 {g['name']} +{s['level']} · " +
                                     ", ".join(scalestone.option_text(o) for o in s["opts"]), tuple(g["color"]), 2.5, 11)
            elif a.value == "F7" and pygame.key.get_mods() & pygame.KMOD_SHIFT:
                if self.fish_cfg.get("debug_keys") or load_json("mobile_config.json").get("debug_build"):
                    self._campfire_debug()   # Shift+F7: 모닥불의 작은 일 6종 차례로 강제 (3시간 쉬기, 48장)
            elif a.value in ("F4", "F6") and pygame.key.get_mods() & pygame.KMOD_SHIFT:
                if self.fish_cfg.get("debug_keys") or load_json("mobile_config.json").get("debug_build"):
                    self._p2_debug("full" if a.value == "F4" else "short")   # 환상 2페이즈 컷신 바로 보기
            elif a.value in ("F3", "F4", "F5", "F6"):
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
            elif a.value == "F7":
                if self.fish_cfg.get("debug_keys") or load_json("mobile_config.json").get("debug_build"):
                    self.force_phantom = not self.force_phantom
                    self.toasts.show(f"[테스트] 다음 착수 환상 강제: {'켬' if self.force_phantom else '끔'}", INFO, 1.5, 11)
            elif a.value == "F8":
                if self.fish_cfg.get("debug_keys") or load_json("mobile_config.json").get("debug_build"):
                    self.show_pity = not self.show_pity
            elif a.value == "F12":
                if self.fish_cfg.get("debug_keys") or load_json("mobile_config.json").get("debug_build"):
                    if pygame.key.get_mods() & pygame.KMOD_SHIFT:
                        # Shift+F12: 신호 보호 영역 표시 (DT2 디버그)
                        sw = self.screen_weather
                        sw.show_protect = not sw.show_protect
                        self.toasts.show(f"[테스트] 신호 보호 영역 표시: {'켬' if sw.show_protect else '끔'}", INFO, 1.5, 11)
                    else:
                        from src.core import season as seasons
                        self.toasts.show(f"[테스트] 계절: {seasons.cycle_forced()}", INFO, 1.5, 11)
            elif a.value == "F1":
                self.debug = not self.debug
            elif a.value == "F2":
                self.shake_on = not self.shake_on
                self.screen_fx.enabled = self.shake_on
                self.settings.set("screen_shake", self.shake_on)
                self.toasts.show("화면 연출(흔들림·줌) " + ("켬" if self.shake_on else "끔"), INFO, 1.2, 11)
        elif n == "time_fast":
            self.clock.fast = not self.clock.fast
        elif n == "drag":   # Q/E · 모바일 ▲▼ — 자동 드랙(CU3)이면 Q · '풀기' 버튼 = 풀기
            if f:
                if f.manual_drag:
                    f.change_drag(a.value)
                elif a.value < 0:
                    f.release()
        elif n == "scroll":   # 휠 — 자동 드랙이면 아래 = 풀기
            if f:
                if f.manual_drag:
                    f.change_drag(1 if a.value > 0 else -1)
                elif a.value < 0:
                    f.release()
        elif n == "flick":
            if f is not None and f.phase == "fight":
                self.sfx.play("sfx_cast_swing", 0.3)  # 휘두르는 소리 (판정과 상관없이)
                f.flick(a.value)
        elif n == "reel_tap":
            if f is not None and f.phase == "fight":
                self.ctl.tap(self.t)  # 터치: 릴 패드를 누를 때마다
        elif n == "primary":
            if a.pos is not None:
                self.mouse = a.pos   # 누른 자리 그대로 (어탁 버튼 등 — 다음 틱 포인터를 기다리지 않게)
            if self._side_menu_click(a.pos):
                return
            if not self.touch and f is not None and f.phase == "fight":
                self.ctl.tap(self.t)  # PC: 파이팅 중 좌클릭 하나하나가 연타
            if self._grandpa_click(a.pos):
                return
            if (f is None and a.pos is not None and self.prog_rect is not None
                    and self.prog_rect.inflate(4, 6).collidepoint(a.pos)):
                self.prog_open_t = 0.0 if self.prog_open_t > 0 else 4.0   # 진행 막대: 자격 · 장비 목록 펼치기
                self.game.sfx.play("ui_click")
                return
            self._left_click()
        elif n == "secondary":
            self._right_click()

    # ───────────────────────── 메뉴 · 저장 ─────────────────────────
    def _side_menu_on(self) -> bool:
        """PC 오른쪽 메뉴 버튼: 파이팅·던지는 중·카드·도움말·훈련 수조에선 숨김."""
        return (not self.touch and self.fight is None and self.card is None and not self.help
                and self.landing is None and self.training is None
                and self.cast.state in (CastState.READY, CastState.LANDED, CastState.RETRIEVE))

    def side_chest_rect(self):
        """보물상자 버튼 자리 (TG-10): PC 오른쪽 메뉴의 상자 / 모바일 가방 버튼."""
        if self.touch:
            return next((ct.rect for ct in getattr(self.game.input, "controls", []) if ct.id == "bag"), None)
        if not self._side_menu_on():
            return None
        return next((r for k, r in self._side_menu_rects() if k == "chest"), None)

    def _side_menu_rects(self):
        from src.ui import side_menu
        return side_menu.layout(self.cam.width, self.cam.height, self.hud_inset)

    def _side_menu_click(self, pos) -> bool:
        if not self._side_menu_on():
            return False
        from src.ui import side_menu
        rects = self._side_menu_rects()
        k = side_menu.hit(rects, pos)
        if k is None and self.collect_open:
            k = side_menu.hit(side_menu.drawer_layout(rects), pos)
            self.collect_open = False   # 서랍 바깥을 눌러도 닫힘
            if k is None:
                return True
        if k is None:
            return False
        if k == "collection":
            self.sfx.play("ui_click")
            self.collect_open = not self.collect_open
            return True
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
        elif which == "inventory":
            if not self.can_open_menus():
                return
            from src.scene.inventory import InventoryScene
            self.game.scenes.push(InventoryScene(self.game, self))
        elif which == "quests":
            if self.fight is not None:
                return
            from src.scene.quest_board import QuestBoardScene
            self.game.scenes.push(QuestBoardScene(self.game, self))
        elif which == "achievements":
            if self.fight is not None:
                return
            from src.scene.achievements_scene import AchievementsScene
            self.game.scenes.push(AchievementsScene(self.game, self))
        elif which == "prints":
            if self.fight is not None:
                return
            from src.scene.print_gallery import PrintGalleryScene
            self.game.scenes.push(PrintGalleryScene(self.game, self))
        elif which == "tank":
            self.start_training()
        elif which == "calendar":   # 달력 (CU1): 14일 예보 · 3시간 칸 골라 쉬기
            if self.fight is not None:
                return
            from src.scene.calendar_scene import CalendarScene
            self.game.scenes.push(CalendarScene(self.game, self))
        self.fight_audio.stop()
        self.signal_audio.stop()

    def start_training(self, pattern: str | None = None) -> None:
        """훈련 수조 (31장 C5): 해금 패턴 무한 반복, 보상·패널티 없음. 지도·수집 서랍에서.
        pattern = 그 패턴을 골라 둔 채로 (백 노인 시험 3번 불합격 뒤 바로가기, 49-3)."""
        if self.fight is not None or self.training is not None:
            return
        from src.scene.training import TrainingTank
        stack = self.game.scenes.stack
        while stack and stack[-1] is not self:   # 위에 열린 화면(지도·마을 등)은 닫고
            top = stack[-1]
            if hasattr(top, "leave"):
                top.leave()
            else:
                stack.pop()
        self.training = TrainingTank(self, pattern)
        self.training.start()

    def write_save(self) -> None:
        d = self.save.data
        d["hour"], d["day"] = self.clock.hour, self.clock.day
        d["spot"] = self.spot_id
        d.update(self.weather_sys.to_save())

    def apply_settings(self) -> None:
        self.shake_on = self.settings.get("screen_shake")
        self.screen_fx.enabled = self.shake_on

    def _start_phantom_show(self, f) -> None:
        """환상어 포획 연출 (33-11): 음악 '환상의 노래'가 주인공 — 다른 소리는 0.15초 안에 비킨다."""
        from src.render.phantom_show import PhantomShow, pick_variant
        from src.audio import phantom_song
        variant = pick_variant(self.catch_news)
        cont = self.spot.get("continent", "sharmion")
        sfx = self.sfx
        delay = getattr(sfx, "latency", 0.0) + getattr(sfx, "offset_s", 0.0)
        w, h = self.cam.width, self.cam.height
        self.catch_show = PhantomShow(f.fish, f.result, self.catch_news, variant, w, h, mobile=self.touch,
                                        reduce=self.settings.get("reduce_fx"), delay=delay,
                                        low=getattr(self.game, "slow_device", False) or self.settings.get("fps") == 30)
        self.fight_audio.stop()
        self.signal_audio.stop()
        self.game.boss.stop()   # 전용 곡: 즉시 완전히 멈춤 → 숨 멎음 정적 → 환상의 노래 (DESIGN.md 43)
        sfx.duck_levels({"mus": -60, "amb": -40, "sfx": -18}, hold=0.5, release=0.15)
        name = phantom_song.preload(sfx, variant, cont)
        self.phantom_song_ch = sfx.play(name, 1.0) if name else None
        self.phantom_loop_ch = None
        self.phantom_fx.k_from = self.phantom_fx.k = 1.0  # 연출 동안 보라 100%

    def _start_legend_show(self, f, intro=None) -> None:
        """전설 포획 연출 (34장): 보스 테마는 끊기지 않고 '전설의 노래' 끝맺음 타격(같은 으뜸음)으로 이어진다."""
        from src.render.legend_show import LegendShow, pick_variant
        from src.audio import legend_song
        variant = pick_variant(f.fish, self.catch_news, self.save)
        cont = self.spot.get("continent", "sharmion")
        sfx = self.sfx
        delay = getattr(sfx, "latency", 0.0) + getattr(sfx, "offset_s", 0.0)
        w, h = self.cam.width, self.cam.height
        self.catch_show = LegendShow(f.fish, f.result, self.catch_news, variant, w, h, mobile=self.touch,
                                     reduce=self.settings.get("reduce_fx"), delay=delay,
                                     low=getattr(self.game, "slow_device", False) or self.settings.get("fps") == 30,
                                     intro=intro)
        self.fight_audio.stop()
        self.signal_audio.stop()
        sid = self.game.boss.song_for(f.fish["id"])
        boss = self.game.boss
        if boss.is_suno(sid) and boss.suno.active:
            # SUNO 곡 (BOSS_BGM_SUNO.md 포획 순간): 다음 박(일섬은 즉시)에서 ending_hit, impact_sec = 연출의 첫 '쾅',
            # card_sec = 포획 카드 등장. 전설의 노래는 틀지 않는다 (마지막 타격이 팡파르).
            info = boss.catch_info(sid)
            wait = boss.catch()
            sh = self.catch_show
            sh.t = -(wait + delay + float(info.get("impact_sec", 0.0)))   # 0초('쾅') = 타격 파일의 impact_sec
            card = float(info.get("card_sec", sh.m["card"]))
            if card > 0.2 and card != sh.m["card"]:
                m0 = dict(sh.m)
                k = card / m0["card"]
                sh.m = {name: (v * k if v <= m0["card"] else v + (card - m0["card"])) for name, v in m0.items()}
            self.suno_catch = True
            sfx.duck_levels({"amb": -40, "sfx": -18}, hold=0.5, release=0.15)   # 음악 버스는 덕킹하지 않음 — 타격이 음악 채널에서 난다
            self.phantom_song_ch = None
            self.phantom_loop_ch = None
        else:
            self.suno_catch = False
            self.game.boss.stop(fade_ms=150)   # 전용 곡의 마지막 화음 → 같은 조성 전설의 노래 첫 타격음 (DESIGN.md 43)
            sfx.duck_levels({"mus": -60, "amb": -40, "sfx": -18}, hold=0.5, release=0.15)
            name = legend_song.preload(sfx, variant, cont, sid)
            self.phantom_song_ch = sfx.play(name, 1.0) if name else None
            self.phantom_loop_ch = None
        self.game.haptics.vibrate("perfect", 1.0)  # 쾅: 강하게 1회

    def _update_catch_show(self, dt: float) -> None:
        sh = self.catch_show
        if sh is not None and sh.waiting() and getattr(sh, "kind", "phantom") == "phantom" and not getattr(sh, "tut_sent", False):
            sh.tut_sent = True
            if not phantom.state(self.save)["tutorial"] and self.game.guide.enabled() and not self.game.guide.done("TG-PH"):
                phantom.state(self.save)["tutorial"] = True   # 도감 [환상] 탭이 이때 생김
                self.game.guide.event("phantom_caught")   # TG-PH (예전 PhantomIntroScene 대신)
        sh = self.catch_show
        if getattr(sh, "kind", "phantom") == "legend":
            self._update_legend_show(dt)
            return
        for ev in sh.update(dt):
            if ev == "breath":
                self.game.haptics.vibrate("nibble", 0.4)  # 숨 멎음: 심장 박동 1회
            elif ev == "climax":
                self.game.haptics.vibrate("legend", 0.6)  # 절정: 길고 부드럽게
            elif ev == "record" and sh.news.get("phantom_new"):
                self.game.haptics.vibrate("nibble", 0.6)  # 인장
            elif ev.startswith("icon:"):
                k = min(3, int(ev.split(":")[1]))
                self.sfx.play(f"sfx_phantom_icon{k}", 0.6)
            elif ev in ("wait", "skip"):
                if ev == "skip" and self.phantom_song_ch is not None:
                    self.phantom_song_ch.fadeout(300)
                if self.phantom_loop_ch is None:
                    from src.audio import phantom_song
                    name = phantom_song.preload(self.sfx, "loop", self.spot.get("continent", "sharmion"))
                    if name:
                        self.phantom_loop_ch = self.sfx.play(name, 0.55)
                        if self.phantom_loop_ch is not None:
                            self.phantom_loop_ch.play(self.sfx.sounds[name], loops=-1, fade_ms=600)
        # 연출 동안 음악이 주인공: 파이팅 음악·환경음·효과음은 계속 비켜 있음
        self.sfx.duck_levels({"mus": -60, "amb": -40, "sfx": -18}, hold=0.3, release=1.5)
        self.phantom_fx.k = 1.0

    def _update_legend_show(self, dt: float) -> None:
        sh = self.catch_show
        for ev in sh.update(dt):
            if ev == "climax":
                self.game.haptics.vibrate("legend", 0.8)   # 절정: 길게
            elif ev == "record" and sh.news.get("new"):
                self.game.haptics.vibrate("nibble", 0.7)   # 금 인장: 짧게
            elif ev.startswith("icon:"):
                self.sfx.play(f"sfx_legend_icon{min(3, int(ev.split(':')[1]))}", 0.6)
            elif ev in ("wait", "skip"):
                if ev == "skip" and self.phantom_song_ch is not None:
                    self.phantom_song_ch.fadeout(300)
                if ev == "skip" and getattr(self, "suno_catch", False):
                    self.game.boss.stop(300)   # SUNO 타격을 건너뛰면 사라짐
                if self.phantom_loop_ch is None and not getattr(self, "suno_catch", False):
                    from src.audio import legend_song
                    sid = self.game.boss.song_for(getattr(sh, "fish", {}).get("id")) if getattr(sh, "fish", None) else None
                    name = legend_song.preload(self.sfx, "loop", self.spot.get("continent", "sharmion"), sid)
                    if name:
                        self.phantom_loop_ch = self.sfx.play(name, 0.55)
                        if self.phantom_loop_ch is not None:
                            self.phantom_loop_ch.play(self.sfx.sounds[name], loops=-1, fade_ms=600)
        if getattr(self, "suno_catch", False):
            self.sfx.duck_levels({"amb": -40, "sfx": -18}, hold=0.3, release=1.5)   # SUNO 타격은 음악 버스 → 음악은 덕킹 안 함
        else:
            self.sfx.duck_levels({"mus": -60, "amb": -40, "sfx": -18}, hold=0.3, release=1.5)

    def _close_catch_show(self) -> None:
        """카드 닫기: 노래·여운 정리 → 1.5초에 걸쳐 원래 색·대기 음악 (덕킹 1.5초 복귀) → 튜토리얼(첫 포획)."""
        sh = self.catch_show
        final = getattr(sh, "final", False)
        for ch in (getattr(self, "phantom_song_ch", None), getattr(self, "phantom_loop_ch", None)):
            if ch is not None:
                ch.fadeout(1500 if final else 600)  # 최종 보스: 노래 여운이 엔딩 음악 위로 이어지며 사라짐
        self.catch_show = None
        if getattr(sh, "kind", "phantom") == "phantom":
            self.phantom_fx.mode, self.phantom_fx.k = "fight", 1.0
        self._end_fight()
        if final:
            self.game.fade_in(load_json("legend_catch_timeline.json")["ending_fade_sec"])
        elif getattr(sh, "kind", "") == "legend" and sh.news.get("legend_line"):
            self.toasts.show(sh.news["legend_line"], phantom.COLOR_LIGHT, 3.5, 11)  # 환상 복선 한 줄 (첫 전설 포획)
        if not final:
            bd = fight_hud.dex_badges(sh.news)   # 도감 별·숙련 (35-2): 연출 카드를 닫은 뒤 한 줄로
            if bd:
                self.toasts.show(" · ".join(b[0] for b in bd), bd[0][1], 3.5, 11)
            offer = getattr(self, "print_offer", None)
            if offer is not None:
                # 환상·전설: 연출 카드를 닫은 뒤 어탁 제안 (최종 보스는 엔딩이 먼저 — 다음 기록 때)
                from src.scene.confirm import ConfirmScene
                fish, size = sh.fish, sh.result["size"]
                msg = f"어탁을 {'남길' if offer['replace'] is None else '바꿀'}까요? ({offer['cost']:,}원)"
                self.game.scenes.push(ConfirmScene(self.game, msg, lambda: self._make_print(None, fish, size),
                                                   "남기기", "괜찮아요"))

    def _phantom_retreat(self, x: float, z: float) -> None:
        """환상어가 떠났다 (놓침·직접 회수·챔질 놓침): 사라진 지점으로 보라가 빨려 들어감 + 한 줄."""
        p = self.cam.project(x, z)
        self.phantom_fx.retreat((p[0], p[1]) if p else self.phantom_fx.center)
        self.phantom_lost_t = 3.2
        if self.fight is None:  # 파이팅에서 놓친 건 결과 화면에 같은 문장
            self.toasts.show(phantom.LOST_LINE, phantom.COLOR_LIGHT, 3.2, 11)
        self.sfx.set_base_duck("fight" if self.fight is not None else None)

    def _grandpa_click(self, pos) -> bool:
        """할아버지의 흔적 (DT11): 던지기 전(대기) · 파이팅 아닐 때 'ㅎ' 새김을 누르면 찾음."""
        if pos is None or self.fight is not None or self.cast.state != CastState.READY or self.training is not None:
            return False
        if self.catch_show is not None or self.board is not None or self.release_scene is not None:
            return False
        from src.render import bottle_seat, grandpa_marks
        if bottle_seat.hit(self.save, self.spot_id, pos, self.touch):   # 해강의 자리: 모은 편지 다시 읽기 (CU13)
            from src.save import bottles
            from src.story.ui import PaperScene
            self.sfx.play("st_paper", 0.5)
            self.toasts.show("해강의 자리 — 편지를 다시 읽는다", (240, 220, 170), 2.0, 11)
            self.game.scenes.push(PaperScene(self.game, bottles.body(bottle_seat.next_letter(self.save)), backdrop=self.draw))
            return True
        if not grandpa_marks.hit(self.spot_id, pos, self.touch):
            return False
        res = grandpa_marks.find(self.save, self.spot_id, self.clock.day, self.season)
        if res is None:
            self.toasts.show(f"할아버지의 흔적 — {grandpa_marks.mark_at(self.spot_id)['where']}", (220, 200, 160), 2.0, 11)
            return True
        self.sfx.play("st_paper", 0.5)
        self.toasts.show(f"해강의 흔적 {res['n']}/{res['total']} — {res['line']}", (240, 220, 170), 3.6, 11)
        if res["title"]:
            from src.save.quests import shop_item
            self.toasts.show(f"칭호 「{shop_item(res['title'])['name']}」", (255, 214, 90), 3.0, 11)
        self.game.save_now()
        return True

    def _left_click(self) -> None:
        c, f = self.cast, self.fight
        if self.release_scene is not None:
            return   # 놓아주기 장면 (1초) 중
        if self.board is not None:
            if self.board.can_skip():   # 계측판: 0.3초 이후 탭 = 바로 포획 카드
                self.board = None
                self.end_t = 0.0
            return
        if self.bait_anim is not None:
            self.bait_anim = None   # 미끼 끼우기: 탭하면 건너뛰기
            return
        if self.hook_cine.active:
            # ② 챔질 연출 중: 입력 무시, 0.5초 이후 탭하면 건너뛰기
            if self.hook_cine.can_skip():
                self.hook_cine.finish()
                self._begin_fight()
            return
        if self.catch_show is not None:
            sh = self.catch_show
            if sh.waiting():
                self._close_catch_show()
            elif sh.can_skip():
                sh.skip()  # 건너뛰어도 보상·도감은 이미 처리됨
            return
        if self.phantom_fx.locked():
            return  # 파장이 퍼지는 동안 입력 무시
        if self.landing is not None:
            self.landing.skip()
            return
        if f is not None:
            if f.phase == "net":
                self.net_anim = 0.3
                f.net_click()
            elif f.phase in ("caught", "lost") and self.end_t > fight_hud.CATCH_READY_T:
                if f.phase == "caught" and self._print_btn() is not None and self._print_btn().collidepoint(self.mouse):
                    self._make_print(f)
                    return
                if f.phase == "caught" and self._release_btn() is not None and self._release_btn().collidepoint(self.mouse):
                    self._release(f)
                    return
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
            if (self.bite.bait or {}).get("live"):   # 생미끼: 물렸을 때만 한 번 줄어듦, 다 쓰면 원래 미끼로
                from src.fishing import live_bait
                if live_bait.consume(self.save):
                    self.toasts.show(f"생미끼를 다 썼다 — {self.save.equipped('bait')['name']}(으)로", INFO, 2.0)
            if self.bite.fish is not None and self.bite.fish.get("bottle"):
                self._bottle_catch()   # 유리병 편지 (CU9): 파이팅 없이 건져 올림
                return
            if self.school is not None and self.bite.school_fish is None and self.bite.fish is not None \
                    and self.bite.fish["rarity"] in ("common", "uncommon", "rare"):
                base = next((f for f in self.all_fish if f["id"] == self.bite.fish["id"]), None)
                self.bite.school_fish = base   # 떼가 지나가는 동안: 처음 문 종이 연달아 (CU9)
            c.hooked()
            heavy = sum(self.bite.fish["size_cm"]) / 2 >= 100 if self.bite.fish else False
            self.sfx.play("sfx_hook_heavy" if heavy else "sfx_hook_success")  # 딱 + 쿵 + 팅 + 물보라 (큰 물고기는 더 깊게)
            self.sfx.duck("hook")
            self.toasts.show("챔질 성공!", GOOD, 1.0)
            self._splash_at(c.bx, c.bz, big=0.6)
            from src.render import hook_cine
            pl = hook_cine.plan(self.save, self.bite.fish, self.cine_full) \
                if self.training is None and self.exam_fish is None else {"post": None}
            if pl.get("post") and self.hook_cine.start_post(pl["rarity"], self.bite.fish, pl["post"]):
                self.cine_ran = True
                # ② 챔질 연출: 끝날 때까지 파이팅을 만들지 않는다 (물고기가 당기지 않음) — update 에서 _begin_fight
                seen = hook_cine.seen_list(self.save)
                if pl["post"] == "full" and self.bite.fish["id"] not in seen:
                    seen.append(self.bite.fish["id"])
            else:
                self._begin_fight()
        elif result == "scared":
            self.sfx.play("sfx_hook_success", 0.4)
            self.sfx.play("sfx_flee")
            self.toasts.show("물고기가 놀라 도망갔다...", BAD, 2.4)
        else:
            self.sfx.play("sfx_cast_swing", 0.4)
            if self.bite.state == BiteState.MISSED:
                self.toasts.show("미끼가 없어요. 우클릭으로 회수", INFO, 2.0, 11)

    def _right_click(self) -> None:
        if self.hook_cine.active:
            return   # ② 챔질 연출 중 입력 무시
        if self.fight is not None:
            if self.fight.phase == "fight":
                self.sfx.play("sfx_cast_swing", 0.35)
                self.fight.dip()
            return
        if self.phantom_fx.locked():
            return  # 파장이 퍼지는 동안 회수 무시
        if self.cast.state == CastState.LANDED and self.exam_fish is not None and self.bite.state != BiteState.HOOKED:
            # 시험 찌를 낀 채 회수: "시험을 미루겠나?" — 예 = 시험 찌 반납 (불합격 아님), 둘 다 줄은 걷는다 (49-3)
            from src.save import exam
            from src.scene.confirm import ConfirmScene

            def yes():
                exam.postpone(self.save)
                self.game.save_now()
                self.toasts.show("시험 찌를 돌려줬다 (백 노인에게 다시 받을 수 있음)", INFO, 2.6, 11)
            self.bite.stop()
            self.cast.cancel_or_retrieve()
            self.exam_fish = None
            self.game.scenes.push(ConfirmScene(self.game, "시험을 미루겠나?", yes, yes="예 (반납)", no="아니요"))
            return
        if self.cast.state == CastState.LANDED:
            if self.bite.phantom is not None and self.bite.state != BiteState.HOOKED:
                # 대사 이후 직접 회수: 보라가 찌로 빨려 들어감 (천장 카운트는 유지)
                self._phantom_retreat(self.cast.bx, self.cast.bz)
            self.bite.stop()
        self.cast.cancel_or_retrieve()

    # ───────────────────────── 파이팅 시작·끝 ─────────────────────────
    def _begin_fight(self) -> None:
        """챔질 성공 → (② 챔질 연출이 있으면 끝난 뒤) 파이팅 시작."""
        self.legend_fx.clear()   # 순간 연출 정리 (보레알리스 얼음 금은 파이팅 전에 사라짐) — 여우비 빗줄기만 남음
        self.phantom_hfx.clear()
        self._start_fight()
        self.cine_ran = False
        if self.fight is not None:
            self.fight_audio.reel.hook(self.fight.size_cm)  # 챔질 임팩트 reel_burst_heavy (클수록 크게)

    def _run_cine_event(self, ev: dict) -> None:
        """② 챔질 연출 사건 실행 (hook_cinematics.json events)."""
        reduce = bool(self.settings.get("reduce_fx"))
        do = ev["do"]
        if self._run_cine_legend(ev):
            return
        if do == "slowmo":
            if not reduce:   # 화면 효과 줄이기: 슬로모션 없음 (45장 📐)
                self.game.slowmo(ev["real_sec"], ev["scale"])
        elif do == "sfx":
            self.sfx.play(ev["name"], ev.get("vol", 1.0))
        elif do == "haptic":
            self.game.haptics.vibrate(ev["name"], ev.get("strength", 1.0))
        elif do == "line_drops":
            c = self.cast
            tip = self._rod_geo()["tip"]
            p = self.cam.project(c.bx, c.bz)
            if p is not None:
                for i in range(ev["count"]):
                    u = 0.15 + 0.6 * i / max(1, ev["count"] - 1)
                    self.droplets.burst(lerp(tip[0], p[0], u), lerp(tip[1], p[1], u) + 4 * math.sin(math.pi * u), 0.45,
                                        count=1)

    def _tick_cine(self) -> None:
        """입질 연출 시계 = 실제 시간, 매 프레임 그리기에서 (DT4~DT6).
        게임 틱은 고정 간격이라 0.05배속이면 update 가 0.33초에 한 번만 불린다 → update 에서 돌리면 정지 연출이 초당 3장으로 끊김."""
        now = self.cine_clock()
        last = getattr(self, "_cine_last", None)
        self._cine_last = now
        if last is None or self.game.scenes.current is not self:
            return   # 일시정지 · 다른 화면이 위에 있으면 멈춤
        real = min(0.1, max(0.0, now - last))
        if self.legend_fx.active:
            self.legend_fx.update(real)
        if self.phantom_hfx.active:
            self.phantom_hfx.update(real)
        if self.hook_cine.pre is not None or self.hook_cine.active:
            if self.hook_cine.update(real, self._run_cine_event):
                self._begin_fight()

    def _cine_ctx(self) -> dict:
        c = self.cast
        p = self.cam.project(c.bx, c.bz)
        # 달 반영 자리 (환상 '달그림자 잉어'): 달이 화면에 있으면 그 아래 수면, 없으면 왼쪽 앞 수면
        moon = None
        for body in world.celestial_bodies(self.clock.hour):
            if body["kind"] == "moon":
                x = self.cam.angle_to_x(body["az"])
                if x is not None and 0 <= x <= self.cam.width:
                    moon = (x, self.cam.horizon + 16)
        return {"bobber": (p[0], p[1]) if p else (self.cam.cx, self.cam.horizon + 30), "w": self.cam.width,
                "h": self.cam.height, "horizon": self.cam.horizon, "scene": self,
                "bobber_size": max(3.5, 0.36 * p[2]) if p else 6,
                "moon": moon or (self.cam.width * 0.3, self.cam.horizon + 16)}

    def _run_cine_legend(self, ev: dict) -> bool:
        """② 전설 사건 (DT5): fx · unique · reel_zing · gold_splash. 처리했으면 True."""
        from src.render import hook_cine
        do = ev["do"]
        rar = self.hook_cine.post["rarity"] if self.hook_cine.post else "legend"
        target = self.phantom_hfx if rar == "phantom" else self.legend_fx   # 전설 (DT5) · 환상 (DT6) 그림
        if do == "fx":
            target.start(ev["name"], self._cine_ctx(), ev.get("sec", 0.6))
        elif do == "silence":
            # 환상: 정적 (숨 멎음) — 환경음 · 음악 · 효과음을 잠시 거의 끔 (환상 전용 표현)
            self.sfx.duck_levels({"amb": -40.0, "mus": -40.0, "sfx": -20.0}, hold=ev.get("sec", 0.6), release=0.3)
        elif do == "phantom_k":
            self.phantom_fx.to_fight()   # 보라 100% → 파이팅용 60% (0.8초)
        elif do == "unique":
            fish = self.hook_cine.post["fish"] if self.hook_cine.post else self.bite.fish
            u = hook_cine.cfg()[f"{rar}_unique"].get(fish["id"]) if fish else None
            if u:
                target.start(u["id"], self._cine_ctx(), hook_cine.cfg()[rar]["unique_sec"])
                for snd in u.get("sfx", []):
                    name, vol, delay = snd[0], snd[1], (snd[2] if len(snd) > 2 else 0.0)
                    if name.startswith("theme:"):
                        _, th, short = name.split(":")
                        fn = (lambda th=th, short=short, vol=vol: theme_sfx.play(self.sfx, th, short, vol))
                    else:
                        fn = (lambda name=name, vol=vol: self.sfx.play(name, vol))
                    self._at(delay, fn)
        elif do == "reel_zing":
            self.fight_audio.reel.rush_begin()   # 릴 '지이잉'
        elif do == "gold_splash":
            lo, hi = ev["count"]
            self.screen_weather.add_drops(random.randint(lo, hi), style="gold", protect=True, size=ev.get("size"))   # 보호 영역 제외
        else:
            return False
        return True

    def _start_fight(self) -> None:
        self.succ_streak = 0  # 성공음 연속 단계 (같은 파이팅, 0~2 — 실패하면 0)
        from src.core import gcwatch
        gcwatch.settle()  # 낚시터 장면 객체를 얼려 파이팅 중 GC 부담을 줄인다 (v0.8.10)
        c = self.cast
        fish = self.bite.fish
        from src.save import scalestone as _ss
        ex = self.training is None and bool(fish.get("exam"))   # 백 노인의 시험 판 (49-3): 순수 실력
        if ex:
            self.exam_run = {"tier": int(fish["exam"]), "miss": {}}
        size = roll_size(fish, self.bite.cast_distance, trophy=0.0 if ex else _ss.frac(self.save, "trophy_chance"))
        # 변이 (U5): 챔질 순간 굴림 (테스트: F10 강제 지정)
        from src.fishing import mutation, weather_events
        force = getattr(self, "force_mut", None)
        train = self.training is not None
        muts = [] if train or ex else mutation.roll(self.save, fish, self.weather, force=force if force else None,
                             chance_mult=(self.bite.sign_mods.get("mutation_mult", 1.0) if self.bite.sign_mods else 1.0)
                             * weather_events.benefit(self.save, "mutation_mult", 1.0))   # 붉은 달: 변이 ×1.5
        if muts:
            fish = mutation.apply(fish, muts)
            if "giant" in muts:
                size = round(size * mutation.cfg()["kinds"]["giant"]["size_mult"], 1)
        angle = math.atan2(c.bx, c.bz)
        if ex:   # 빌린 다음 티어 기본 장비 — 비늘석 · 부적 · 상자 장비 효과 없음, 찌 부족 도주 · 기믹 없음
            from src.save import exam as _exam
            gear, gim, fneed = _exam.borrowed_gear(self.exam_run["tier"]), None, 0
        else:
            gear = self.save.fight_gear(self.clock.period()[0])
            gim = None if train else self.current_gimmick()
            fneed = self.save.float_need(fish, self.spot)
        self.fight = Fight(fish, size, c.current_distance(), angle, self.cam.yaw, gear=gear,
                           hazards=[] if train else self.spot["hazards"], gimmick=gim,
                           float_need=fneed, float_tier=self.save.float_tier(),
                           touch_lead=load_json("mobile_config.json")["touch_lead_sec"] if self.touch else 0.0)
        self.fight.manual_drag = bool(self.settings.get("drag_manual"))   # 설정 '드랙 직접 조절' (CU3, 기본 끔 = 자동 드랙 + 풀기)
        # 정체 숨김 (CU6-1): 일반~희귀는 건져 올릴 때까지 '???' — 전설 · 환상 · 시험 · 훈련 · 설정 '파이팅 중 이름 보기' 는 그대로
        hide = (fish.get("rarity") in ("common", "uncommon", "rare") and not ex and not train
                and not self.settings.get("fight_name_show"))
        self.fight.name_hidden = hide
        from src.save import dexbook
        self.fight.name_hint = fish["name"] if hide and dexbook.mastery(self.save, fish) >= 3 else None   # 숙련 3: "…○○ 같다?"
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
        from src.save.quests import QuestRun
        self.quest_run = None if ex else QuestRun(self.save, self.fight, fish["id"], self.spot_id, self.weather,
                                                  self.clock.period()[0])
        if muts:
            kinds = mutation.cfg()["kinds"]
            col = tuple(kinds[muts[0]]["color"])
            self.toasts.show(f"{kinds[muts[0]]['name']} 변이", col, 3.2, 11)
            # 변이 등장은 소리 없이 화면 연출만 (N3, 강조 등급 '없음')
            self.sparkles.burst(*self._fish_screen(), count=16, speed=0.9)
        from src.fishing.rank import line_allow
        if not train and line_allow(fish) > 0:
            self.game.guide.event("first:heavy_fish")   # TG-20 대형 물고기: 줄은 반드시 닳고 랭크는 봐줌 (49-4)
        for g in sorted(self.fight.gim.kinds(self.fight.brain)):
            key = f"gimmick:{g}"
            if not train:
                self.tutorial.mark(key)
                self.game.guide.event(f"first:{key}")   # TG-19 (예전 기믹 카드 대신)
        from src.fishing.fight import fish_gear_tier
        need_rod = fish_gear_tier(fish)
        if ex:
            self.toasts.show("시험!", (242, 196, 107), 2.4, 11)
        elif not train and self.save.gear_tier("rod") < need_rod and fish["rarity"] != "common":
            # 낚싯대가 약하면 울렁임이 커진다 — 왜 어려운지 알려 준다
            self.toasts.show("버겁다!", BAD, 2.6, 11)
        if fish["rarity"] == "phantom":
            phantom.reset_pity(self.save, self.spot_id)  # 환상어와 파이팅까지 갔다 → 천장 카운트 0
            self.phantom_fx.to_fight()
            self.game.haptics.vibrate("bite", 0.6)
        arena_on = not train and not ex and self.arena.start(fish)   # 전설 · 환상: 무대 (이름 카드가 '전설!' 글자 대신)
        self.breach = None
        if arena_on and fish["rarity"] == "legend":
            self._breach_start(fish)   # 전설 등장 도약 (CU10): 이름 카드가 떠 있는 동안 하늘로 솟구쳤다 착수
        if fish["rarity"] == "legend":
            if not arena_on:
                self.toasts.show("전설!", (255, 214, 90), 3.0)
            if not self.cine_ran:   # ② 챔질 연출이 있었으면 그게 등장 소리 · 흔들림 (한 순간 주인공 소리 하나)
                self.sfx.play("sfx_legend_appear", 1.0, haptic="legend")  # 깊은 드론 + 심장박동 + 수면 울림
                self.shake_kick = 2.5
        if self.fight.brain.sound_only:
            self.toasts.show("소리로!", (200, 220, 255), 3.0, 11)
        self.ink_t = 0.0
        self.ctl.reset()
        self.bite.shadow = None
        self.end_t = 0.0
        self.slack_t = self.red_t = 0.0
        if self.training is None:
            self.game.guide.event("fight_start")   # TG-02 (예전 'fight_intro' 카드 대신)
        self._preload_catch_song(fish)

    # ── 어탁 (35-2) ──
    def _print_btn(self):
        offer = getattr(self, "print_offer", None)
        if offer is None or self.end_t < fight_hud.CATCH_READY_T:
            return None
        return pygame.Rect(self.cam.width - 134, 118, 124, 18)

    def _release_btn(self):
        """포획 카드 [놓아주기] (일반 · 고급 · 희귀, DETAILS D)."""
        if self.release_item is None or self.release_scene is not None or self.end_t < fight_hud.CATCH_READY_T:
            return None
        return pygame.Rect(self.cam.width - 134, 150, 124, 18)

    def _draw_release_btn(self, canvas) -> None:
        r = self._release_btn()
        if r is None:
            return
        hov = r.collidepoint(self.mouse)
        canvas.fill((24, 44, 52) if hov else (18, 32, 40), r)
        pygame.draw.rect(canvas, (150, 210, 220), r, 1)
        hud.text(canvas, "놓아주기", r.center, (210, 240, 245), 11, "center")

    def _release(self, f) -> None:
        """놓아주기: 살림망에서 빼고(판매 안 됨) 도감 포인트 +1 (하루 20) → 헤엄쳐 사라지는 1초 장면 → 카드 닫기."""
        from src.render.catch_board import ReleaseScene
        got = self.save.release_last(self.release_item)
        self.release_item = None
        self.release_scene = ReleaseScene(f.result["fish"], f.result["size"], self.cam.width, self.cam.height)
        self.sfx.play("sfx_splash_small", 0.7)
        msg = "물로 돌려보냈다 · 도감 포인트 +1" if got["point"] else "물로 돌려보냈다 (오늘 도감 포인트는 다 받음)"
        self.toasts.show(msg, (170, 230, 240), 2.4, 11)
        if got["title"]:
            from src.save.quests import shop_item
            self.toasts.show(f"칭호 「{shop_item(got['title'])['name']}」", (255, 214, 90), 3.0, 11)
        self.game.save_now()

    def _draw_print_btn(self, canvas) -> None:
        r = self._print_btn()
        if r is None:
            return
        offer = self.print_offer
        hov = r.collidepoint(self.mouse)
        canvas.fill((44, 36, 28) if hov else (30, 26, 22), r)
        pygame.draw.rect(canvas, (210, 190, 150), r, 1)
        label = f"어탁 남기기 {offer['cost']:,}원" if offer["replace"] is None else f"어탁 갱신 {offer['cost']:,}원"
        hud.text(canvas, label, r.center, (240, 226, 200), 11, "center")
        if offer["replace"] is not None:
            hud.text(canvas, f"(지금 어탁 {offer['replace']:.1f}cm)", (r.centerx, r.bottom + 7), (170, 160, 140), 11, "center")

    def _make_print(self, f, fish: dict | None = None, size: float | None = None) -> None:
        from src.save import prints
        fish = fish or f.fish
        size = size if size is not None else f.result["size"]
        if prints.make(self.save, fish, size, self.spot["name"]):
            self.print_offer = None
            self.game.guide.event("print_made")   # TG-13
            self.sfx.play("ui_buy", 0.8)
            self.toasts.show("어탁을 남겼다! (도감 · 마을 어탁 갤러리)", (240, 226, 200), 2.5, 11)
            self.game.save_now()
        else:
            self.sfx.play("ui_error")
            self.toasts.show("돈이 모자라요", BAD, 1.5, 11)

    def _preload_catch_song(self, fish: dict) -> None:
        """환상·전설 파이팅 시작 때 포획 곡을 일꾼 스레드에 맡겨 둔다 (포획 순간 파일 읽기로 끊기지 않게 — 맡기기만 하고
        기다리지 않음, 다가올 때 이미 맡겼으면 그대로. 포획 순간 preload 가 다 읽힌 것을 가져감, DESIGN.md 44)."""
        cont = self.spot.get("continent", "sharmion")
        if phantom.is_phantom(fish):
            from src.audio import phantom_song
            phantom_song.prefetch(self.sfx, cont)
        elif fish.get("rarity") == "legend":
            from src.audio import legend_song
            sid_ = self.game.boss.song_for(fish["id"])
            if not self.game.boss.is_suno(sid_):   # SUNO 곡은 전설의 노래를 쓰지 않는다 (BOSS_BGM_SUNO.md)
                legend_song.prefetch(self.sfx, cont, sid_)   # 전설마다 그 파이팅 곡 조성 (DESIGN.md 43)

    def _bottle_catch(self) -> None:
        """유리병 편지 (CU9): 물고기 대신 유리병 — 편지 한 장을 펼쳐 보여 주고 일지에 모음, 12장이면 칭호."""
        from src.save import bottles
        from src.story.ui import PaperScene
        self.sfx.play("sfx_splash_small", 0.6)
        self._splash_at(self.cast.bx, self.cast.bz, big=0.3)
        b, done = bottles.take(self.save)
        self.bite.stop()
        self.cast.reset()
        if b is None:
            return
        self.toasts.show(f"유리병을 건졌다! ({len(bottles.collected(self.save))}/12)", (190, 225, 255), 2.6)
        if done:
            self.toasts.show("칭호 '유리병을 읽는 자'", (255, 214, 90), 3.0, 11)
            self.toasts.show("동네 저수지 물가에 '해강의 자리'가 생겼다", (240, 220, 170), 3.4, 11)
        self.game.scenes.push(PaperScene(self.game, bottles.body(b), backdrop=self.draw))
        self.game.save_now()

    def _end_fight(self) -> None:
        last = self.fight.result if self.fight is not None else None
        exam_res = (self.exam_run or {}).get("result")
        if self.fight is not None and load_json("fishing_config.json").get("debug_keys"):
            # 디버그 빌드: 파이팅 로그를 세이브 폴더/fight_logs/날짜.jsonl 에 (tools/fight_log.py read 로 분석)
            from src.core.paths import save_dir
            self.fight.log.spot = self.spot_id
            self.fight.log.save(str(save_dir() / "fight_logs"))
        self.fight = None
        self.breach = None
        self.p3 = None
        self._p2_clear()
        self.landing = None
        self.dragon_fx = None
        self.legend_fx.end_fight()   # 여우비 빗줄기 끝
        self.arena.stop()
        self.board = None
        self.release_scene = None
        self.release_item = None
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
            from src.story import runner

            def final():
                self.game.scenes.push(EndingScene(self.game, self, kind="final"))
            # 스토리 C5-05: 오르시엘 포획 연출 직후, 기존 최종 엔딩 직전에 선택 (건너뛰기 없음)
            if not runner.before_final_ending(self.game, self, last["fish"], last.get("size", 0.0), final):
                final()
        self.screen_fx.reset()
        if last and phantom.is_phantom(last["fish"]):
            self.phantom_fx.restore()  # 포획 컷이 끝나면 1.5초에 걸쳐 원래 색
            if not phantom.state(self.save)["tutorial"]:
                # 첫 환상어 포획: 도감 [환상] 탭이 이때 생김 (33장 P6). 안내는 가이드 TG-PH — 튜토리얼 안내를 껐으면 예전 안내 창
                if self.game.guide.enabled():
                    phantom.state(self.save)["tutorial"] = True
                else:
                    from src.scene.phantom_intro import PhantomIntroScene
                    self.game.scenes.push(PhantomIntroScene(self.game, self))
        self.bite.stop()
        self.cast.reset()
        self.game.screen.shake = (0, 0)
        if getattr(self, "exam_ready_toast", False):
            self.exam_ready_toast = False
            from src.save import exam
            self.toasts.show(exam.cfg()["ready_toast"], (242, 196, 107), 3.5, 11)   # 하루 목소리 (🅲-3)
        if self.exam_run is not None or self.exam_fish is not None:
            self._exam_end(exam_res)

    # ───────────────────────── 로직 (60틱 고정) ─────────────────────────
    def update(self, dt: float) -> None:
        self._run_rt_fx()
        if getattr(self, "voyage_pending", False) and self.game.scenes.current is self:
            self.voyage_pending = False
            from src.scene.voyage import VoyageScene
            self.game.scenes.push(VoyageScene(self.game, self))
            return
        if self.game.scenes.current is self and self.backdrop is None and getattr(self, "_tut_spot", None) != self.spot_id:
            self._tut_spot = self.spot_id
            self.game.guide.event(f"spot_enter:{self.spot_id}")   # 가이드 튜토리얼 (TG-01: 동네 저수지 첫 입장)
        if self.card is not None or self.help or self.game.guide.frozen():
            # 튜토리얼 카드·도움말·가이드 정지 지시: 게임 정지 (예고 시간도 흐르지 않음)
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
        from src.ui import achv_toast
        achv_toast.update(self.game, dt, self.fight is None and self.landing is None and self.catch_show is None
                          and self.game.scenes.current is self)   # 업적 확인·알림 (파이팅·포획 연출 중엔 대기)
        self.collect_k = min(1.0, self.collect_k + dt * 6) if self.collect_open and self._side_menu_on() \
            else max(0.0, self.collect_k - dt * 8)
        if not self._side_menu_on():
            self.collect_open = False
        self.ctl.begin_tick()
        self.earn_rate.update(self.save)   # 진행 막대 (CU8-②)
        self.prog_open_t = max(0.0, self.prog_open_t - dt)
        if not self._tide_tick():   # 물때 멈춤 소라 (CU1-4): 효과 중엔 게임 시계가 멈춤
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
        self.signal_audio.update(dt, self.fight if self.fight is not None and self.fight.phase == "fight"
                                 and not (self.p2 is not None and self.p2.blocking) else None)
        self._p2_aura_tick(dt)
        self._rush_audio()
        fighting = self.fight is not None and self.fight.phase in ("fight", "net")
        if not fighting:  # N5 거리감: 파이팅 중엔 fight_audio 가 물고기 거리로, 그 밖엔 찌(루어)까지 거리로
            self.sfx.fish_dist = min(1.0, self.cast.current_distance() / max(1.0, self.cast_far)) \
                if self.cast.state != CastState.READY else 0.3
        amb_key = (fighting, self.game.boss.active)
        if amb_key != getattr(self, "_amb_fight", (False, False)):
            self._amb_fight = amb_key
            # 파이팅 중 환경음 −4dB, 전설·환상 전용 곡이 도는 동안 −6dB (DESIGN.md 43)
            self.sfx.set_base_duck((("boss_fight" if self.game.boss.active else "fight") if fighting else None))
            # 동시 재생 한도 (N3): 일반 파이팅 3 (주인공 1 + 보조 2) / 전설 4, 파이팅 밖은 없음
            legend = fighting and (self.fight.fish.get("rarity") == "legend" or self.game.boss.active)
            self.sfx.set_budget(("legend" if legend else "fight") if fighting else None)
        self.drag_seen_t = max(0.0, getattr(self, "drag_seen_t", 0.0) - dt)
        signal_slots.configure(self.settings)
        signal_slots.OPTS["phantom"] = self.phantom_fx.active and self.phantom_fx.k > 0.3
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
        self.wet_t = max(0.0, self.wet_t - dt)
        if self.legend_fx.rain_fight and not self.hook_cine.active and (self.fight is None or self.fight.phase not in ("fight", "net")):
            self.legend_fx.end_fight()   # 여우비 빗줄기: 파이팅(뜰채 포함)이 끝나면 사라짐 (DT5)
        cur_bait = self.save.data.get("gear", {}).get("bait")
        if cur_bait != self.last_bait:
            # 미끼를 바꿨다 → 낚싯대가 매달린 상태면 0.8초 미끼 끼우기 (DETAILS C)
            self.last_bait = cur_bait
            if self.cast.state == CastState.READY and self.fight is None and self.training is None:
                self.bait_anim = load_json("details/hands_catch.json")["bait_anim"]["sec"]
        if self.bait_anim is not None:
            self.bait_anim -= dt
            if self.bait_anim <= 0 or self.cast.state != CastState.READY:
                self.bait_anim = None
        self.cast.update(dt, aim)
        for ev in self.cast.events:
            if ev == "splash":
                self._splash()
            elif ev == "launch":
                self.sfx.play("sfx_cast_swing", 0.45 + 0.55 * self.cast.power)  # 휙 (파워만큼 크게)
                lo, hi = load_json("details/map_details.json")["actions"]["cast_drops"]
                self.cast_drops = [random.randint(lo, hi), 0.05]   # 날아가는 궤적을 따라 물방울 5~8개 (A-4)
                if self.training is None:   # 낚싯대별 캐스팅 횟수 → 손잡이 손때 (C)
                    rc = self.save.data.setdefault("details", {}).setdefault("rod_casts", {})
                    rid = self.save.data["gear"]["rod"]
                    rc[rid] = rc.get(rid, 0) + 1
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
        self._update_phantom(dt)
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

    def _update_phantom(self, dt: float) -> None:
        """환상의 물고기 파장 (33-5): 시간·진동·환경음/음악 잦아듦."""
        fx = self.phantom_fx
        fx.update(dt)
        for ev in fx.events:
            if ev == "bloom_start":
                self.game.haptics.vibrate("nibble", 0.3)   # 파장 시작: 아주 약하게
                self.sfx.play("sfx_phantom_hum", 0.35)     # 아주 낮고 부드러운 울림 (작게)
                b_ = self.game.boss   # 환상 공통 곡 (PHANTOM_BGM.md): 파장이 시작되는 순간 백그라운드 로딩 시작
                ph = self.bite.phantom
                sid_ = b_.song_for(ph["id"]) if ph and b_.enabled and self.training is None else None
                if sid_ and not b_.active:
                    b_.prepare(sid_)
            elif ev == "bloom_line":
                self.game.haptics.vibrate("nibble", 0.7)   # 대사 등장 한 번
        fx.events.clear()
        if fx.mode == "bloom" and self.bite.phantom is not None:
            # 환경음 0.2초부터 잦아듦 → 음악 2.2초에 완전히 (정적이 신호)
            b = fx.cfg["bloom"]
            u = clamp((fx.t - b["start"]) / (b["full"] - b["start"]), 0, 1)
            self.sfx.duck_levels({"amb": -30 * u, "mus": -45 * u}, hold=0.3, release=1.5)
        elif fx.mode == "bloom" and self.bite.phantom is None and self.fight is None:
            fx.retreat(fx.center)  # 줄을 걷는 등 다른 길로 끝남
        self.phantom_lost_t = max(0.0, getattr(self, "phantom_lost_t", 0.0) - dt)
        for g in self.glints:
            g[2] += dt
        self.glints = [g for g in self.glints if g[2] < 1.6]

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
        self._update_music(on, dt)
        ph_on = f is not None and f.phase in ("fight", "net") and f.fish.get("rarity") == "phantom"
        self.screen_fx.legend = (on or ph_on) and not self.arena.active   # 무대가 있으면 무대 비네트가 대신 (51-2)
        self.screen_fx.legend_alpha = 0.35 if ph_on else 1.0  # 환상: 화면 가장자리 아주 옅은 보라
        if ph_on:
            self.screen_fx.legend_color = phantom.COLOR
        self.legend_k += ((1.0 if on else 0.0) - self.legend_k) * min(1.0, dt / 0.8)

    def _update_music(self, legend: bool, dt: float = 0.0) -> None:
        """적응형 음악 층 (src/audio/adaptive_music.py, 32장 S6 + N4 음악 절제 + 32-16 Z4 파이팅 음악):
        대기(간헐적 — 울림/정적) → 입질은 그대로 낮추기만 → 일반 파이팅 = 대륙 파이팅 층 (대형 무겁게 / 지침·뜰채 밝게)
        + 위기(빨강 2초 이상 또는 줄 내구도 30% 이하) 층 / 전설은 보스 테마 (장력 타악은 전설만)
        → 포획 스팅은 희귀 이상만, 일반 1초 페이드 / 실패 1.5초 페이드. 낮 밝기만큼 높은 반짝임.
        설정 '파이팅 음악' 끔 = fight_calm (대기 층 낮추기만)."""
        am = self.game.adaptive
        f = self.fight
        am.set_context(self.spot.get("continent", "sharmion"), self.spot_id, legend)
        intensity, phase, rarity, crisis = 0.0, 0, None, False
        if f is not None and f.phase in ("fight", "net"):
            if legend:
                # v0.8.14 롤백: 지침(기회!) 동안 음악이 바뀌지 않게 — 전설만 뜰채 단계에서 상승 멜로디
                state = "legend_tired" if f.phase == "net" else "legend"
            elif not self.settings.get("fight_music"):
                state = "fight_calm"
            elif f.phase == "net" or f.brain.state in ("tired", "exhausted"):
                state = "tired"   # 진짜 지침만 밝게 (가짜 지침은 그대로 — 속임수를 음악이 들키지 않게)
            else:
                state = "fight_big" if f.size_cm >= 100 else "fight"
            fm = am.cfg.get("fight_music", {})
            self.red_t = self.red_t + dt if f.phase == "fight" and f.zone() == "red" else 0.0
            danger = self.red_t >= fm.get("red_sec", 2.0) or f.line_frac <= fm.get("line_frac", 0.3)
            self.crisis_hold = fm.get("hold_sec", 1.5) if danger else max(0.0, self.crisis_hold - dt)
            crisis = self.crisis_hold > 0 and f.phase == "fight"
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
        if f is None or f.phase not in ("fight", "net"):
            self.red_t = self.crisis_hold = 0.0
        self.crisis_now = crisis   # 보스전 무대 위기 덧씌움 (51-2)
        am.set(state, intensity, phase, am.daylight_of(self.clock.hour, tuple(am.cfg["night_hours"])), rarity=rarity,
               crisis=crisis)
        self._update_boss(crisis)

    def _update_boss(self, crisis: bool) -> None:
        """전설·환상 전용 파이팅 곡 (DESIGN.md 43, BOSS_BGM.md B5): 다가올 때 미리 불러오기 → 챔질 = 곡 시작(인트로 → 1페이즈)
        → 페이즈·위기·지침 → 실패 = 즉시 정지 + '쿵' / 포획 = 연출이 넘겨받음 (전설의 노래 · 환상 정적 → 환상의 노래).
        구운 곡이 없으면 예전 보스 테마(적응형 음악 전설 층) 그대로."""
        b = self.game.boss
        if not b.enabled or self.training is not None:
            return
        f = self.fight
        fish = f.fish if f is not None else (self.bite.fish if self.bite.state in (BiteState.APPROACH, BiteState.NIBBLE, BiteState.BITE) else None)
        sid = b.song_for(fish["id"]) if fish and (fish.get("rarity") == "legend" or phantom.is_phantom(fish)) else None
        if sid and not b.active and b.loaded_for != sid:
            b.prepare(sid)   # 다가오는 동안·파장 동안 일꾼 스레드가 읽음 (src/audio/loader.py)
            # 포획 순간·테마 연출에 쓸 소리도 지금 맡겨 둠 — 절정에서 파일 읽느라 멈추지 않게 (DESIGN.md 44)
            from src.audio import legend_song, phantom_song, theme_sfx
            cont = self.spot.get("continent", "sharmion")
            if phantom.is_phantom(fish):
                phantom_song.prefetch(self.sfx, cont)
            elif not b.is_suno(sid):   # SUNO 곡은 전설의 노래를 쓰지 않는다
                legend_song.prefetch(self.sfx, cont, sid)
            theme_sfx.prefetch(self.sfx, fish.get("theme"))
            self.sfx.prefetch(("sfx_legend_fanfare", "sfx_chest_legend", "sfx_phantom_hum"))
        if f is not None and f.phase in ("fight", "net"):
            if sid and not b.active and getattr(self, "boss_fight", None) is not f:
                if b.start(sid):
                    self.boss_fight = f
                    self.boss_tired = False
            if b.active and getattr(self, "boss_fight", None) is f:
                b.set_phase(f.brain.phase)
                b.set_crisis(crisis)
                tired = f.phase == "net" or f.brain.state in ("tired", "exhausted")
                if tired and not self.boss_tired:
                    b.tired()   # 지친 순간: 2마디 동안 주선율 한 옥타브 위 (해방감)
                self.boss_tired = tired
        elif b.active:
            if f is not None and f.phase == "lost":
                b.fail()        # 줄 끊김·도주: 바로 멈춤 + 낮은 '쿵' + 1.5초 잔향
            elif f is not None and f.phase == "caught":
                pass            # 전설: 뜰채 연출 동안 계속 → 전설의 노래가 이어받음 / 환상: 연출 시작에서 멈춤
            else:
                b.stop(400)

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
        self._update_school(dt)
        self.wind.update(dt, self.weather)
        self.rain.dir = 1 if self.wind.x >= 0 else -1   # 빗줄기 기울기 = 바람 방향
        lf = self.legend_fx   # 여우비: 실제 날씨는 그대로, 화면 빗줄기만 (쏟아지는 순간 굵게 → 파이팅 내내 가늘게)
        rain_w = "storm" if lf.rain_burst > 0 else ("rain" if lf.rain_fight and self.weather in ("clear", "fog") else self.weather)
        self.rain.update(dt, rain_w, self.ripples, self.cam)
        self.fog.update(dt, self.weather)
        reduce = bool(self.settings.get("reduce_fx"))
        self.lightning.reduce = reduce   # 화면 효과 줄이기: 번쩍임 없음 (45장 📐)
        self.lightning.update(dt, self.weather, self.cam.horizon, self.cam.width)
        self.ilseom_fx.update(dt)
        for ev in self.lightning.events:
            if ev == "strike":
                self.ambience.strike()  # 천둥은 번개 뒤 거리만큼 늦게 (가까우면 쩍, 멀면 우르릉)
            elif ev == "thunder" and not reduce:
                # 천둥 소리와 함께 화면 1px 흔들림 0.2초 (DETAILS A-1, 45-D 확정 3: 번쩍임은 그대로)
                self.thunder_shake = load_json("details/weather_screen.json")["lightning"]["shake_sec"]
        self.lightning.events.clear()
        self.ambient.update(dt, self.clock.period()[0], self.weather, self.theme.get("sea", False))
        f = self.fight
        self.ambience.update(dt, self.spot_id, self.clock.period()[0], self.weather,
                             fighting=f is not None and f.phase in ("fight", "net"), legend=self.legend_on, season=self.season)
        self.season_fx.update(dt, self.season, self.spot.get("continent", "sharmion"), self.cam.width, self.cam.height,
                              self.clock.period()[0], self.weather, mobile=self.touch,
                              fighting=f is not None and f.phase in ("fight", "net"),
                              enabled=self.theme["terrain"] != "cave" and self.theme.get("dark", 0) < 0.5,
                              wind=self.wind.x, protect=self.screen_weather.protect,
                              fireflies=False)   # 낚시터 반딧불은 MapFx (여름 밤 3곳, 45-D 확정 6)
        self._update_screen_weather(dt)   # 환경음 조각(파도 부서짐) 다음에 — 같은 순간 물보라
        self._tick_events(dt, f)

    def _update_screen_weather(self, dt: float) -> None:
        """화면에 맺히는 날씨 · 수면 구름 그림자 · 윤슬 (DT2)."""
        cam, f = self.cam, self.fight
        sun = sun_x = None
        for body in world.celestial_bodies(self.clock.hour):
            if body["kind"] == "sun":
                sun = world.body_screen_pos(cam, body)
                if sun is not None and body["elev"] > math.radians(-1.0):
                    sun_x = sun[0]
        open_sky = self.theme["terrain"] != "cave" and self.theme.get("dark", 0) < 0.5
        self.screen_weather.update(dt, {
            "weather": self.weather, "season": self.season, "cont": self.spot.get("continent", "sharmion"),
            "period": self.clock.period()[0], "spot": self.spot_id, "sea": self.theme.get("sea", False),
            "fighting": f is not None and f.phase in ("fight", "net"), "reduce": bool(self.settings.get("reduce_fx")),
            "wind": self.wind, "touch": self.touch, "left": bool(self.touch and self.settings.get("touch_left")),
            "horizon": cam.horizon, "sun": sun, "sun_x": sun_x, "enabled": open_sky,
            "cave": self.theme["terrain"] == "cave", "t": self.t})
        c = self.cast
        bob = None
        if c.state == CastState.LANDED and f is None:
            p = cam.project(c.bx, c.bz)
            bob = (p[0], p[1]) if p else None
        self.map_fx.update(dt, {
            "spot": self.spot_id, "season": self.season, "period": self.clock.period()[0], "weather": self.weather,
            "fighting": f is not None and f.phase in ("fight", "net"), "reduce": bool(self.settings.get("reduce_fx")),
            "horizon": cam.horizon, "bobber": bob, "cam": cam, "ripples": self.ripples, "bubbles": self.bubbles,
            "droplets": self.droplets, "sfx": self.sfx, "screen": self.screen_weather,
            "played": getattr(self.ambience, "played", []), "wind": self.wind.x, "t": self.t})
        lc = load_json("details/ambient_life.json")["dragonfly"]
        self.ambient.flies_ok = (self.season in lc["seasons"] and self.clock.period()[0] in lc["periods"]
                                 and self.spot_id in lc["spots"])   # 기존 날아다니는 잠자리도 문서 조건으로 (확정 6)
        self.life.update(dt, {
            "spot": self.spot_id, "season": self.season, "period": self.clock.period()[0], "weather": self.weather,
            "fighting": f is not None, "cam": cam, "ripples": self.ripples, "sfx": self.sfx,
            "reeling": (c.state == CastState.RETRIEVE
                        or (f is not None and f.phase == "fight" and f.reeling)),
            "bobber_xz": (c.bx, c.bz) if c.state == CastState.LANDED and f is None else None})
        self._update_action_drops(dt)

    def _update_action_drops(self, dt: float) -> None:
        """행동에 반응하는 물방울 (DETAILS A-4): 캐스팅 궤적 · 빠르게 감기 · 수면 몸부림. 뜰채는 _update_landing 'hit'."""
        A = load_json("details/map_details.json")["actions"]
        c, f, cam = self.cast, self.fight, self.cam
        cd = self.cast_drops
        if cd[0] > 0 and c.state == CastState.FLIGHT:
            cd[1] -= dt
            if cd[1] <= 0:
                p = cam.project(c.bx, c.bz, c.bh)
                if p is not None:
                    k = smoothstep(c.flight_s / 0.3)
                    tip = rod_tip_drop(self._rod_geo()["tip"], self.t)
                    x, y = lerp(tip[0], p[0], k), lerp(tip[1], p[1], k)
                    self.droplets.burst(x, y + 6, 0.5, count=1, lateral=random.uniform(-20, 20))
                cd[0] -= 1
                cd[1] = c.flight_dur / max(1, A["cast_drops"][1]) if getattr(c, "flight_dur", 0) else 0.08
        elif c.state != CastState.FLIGHT:
            cd[0] = 0
        if f is None or f.phase != "fight":
            return
        # 빠르게 감기: 감는 속도가 최대의 70% 이상이면 낚싯대 끝 근처 줄에서 물방울 (초당 4개)
        cfg = self.fish_cfg["fight"]
        top = f.gear["reel_speed"] * (cfg["reel_speed_drag_min"] + cfg["reel_speed_drag_add"])
        if top > 0 and f.reel_speed_now >= A["reel_fast_frac"] * top:
            self.reel_drop_t -= dt
            if self.reel_drop_t <= 0:
                self.reel_drop_t = 1.0 / A["reel_drops_per_sec"]
                tip = self._rod_geo()["tip"]
                self.droplets.burst(tip[0] - random.uniform(4, 16), tip[1] + random.uniform(2, 10), 0.45, count=1)
        # 수면 질주 · 점프 · 공중 몸부림: 화면에 물보라 (2초에 1번 이하, 보호 영역 제외)
        self.thrash_t = max(0.0, self.thrash_t - dt)
        if f.brain.state in A["thrash_states"] and self.thrash_t <= 0:
            self.thrash_t = A["thrash_gap_sec"]
            self.screen_weather.add_drops(random.randint(*A["thrash_drops"]))

    def _update_waiting(self, dt: float) -> None:
        if (self.cast.state == CastState.READY and self.training is None and self.game.scenes.current is self
                and self._exam_float_on()):
            self.game.guide.event("exam_spot")   # TG-24 첫 시험 (시험 찌를 받고 시험 낚시터에 섬, 49-6)
        self.bite.set_conditions(self.clock.period()[0], self.weather, self.spot_id)
        from src.fishing import live_bait
        live = live_bait.bait_dict(self.save, self.spot_id) if self.training is None and self.exam_fish is None else None
        self.bite.bait = live or self.save.equipped("bait")   # 생미끼 (CU7-2): 끼우면 영구 미끼 효과는 꺼짐
        from src.scene.map_scene import gear_ok
        self.bite.legend_block = not gear_ok(self.save, self.spot)   # 미리 맛보기 (CU8-⑤): 장비 조건 전엔 전설 없음
        self.bite.force_fish = self.exam_fish if self.exam_fish is not None else \
            (self.all_fish[self.force_i] if self.force_i >= 0 else None)
        landed = self.cast.state == CastState.LANDED   # 대기 = 기다리기만 (루어 액션 저킹 · 리트리브는 삭제, DESIGN 47장)
        self.bite.sign_mods = self.signs.mods(self.cast.bx, self.cast.bz) if landed else {}
        from src.save import bottles
        self.bite.bottle_ok = self.training is None and self.exam_fish is None and bool(bottles.remaining(self.save))
        sc = self.school
        near = (sc is not None and landed
                and math.hypot(self.cast.bx - sc["x"], self.cast.bz - sc["z"]) <= load_json("core.json")["variety"]["school_radius_m"])
        self.bite.school_mult = load_json("core.json")["variety"]["school_wait_mult"] if near else 1.0
        if sc is None:
            self.bite.school_fish = None
        self.bite.update(dt)
        for ev in self.bite.events:
            self._on_bite_event(ev)
        self.bite.events.clear()
        if (landed and self.bite.state == BiteState.WAIT and self.bite.phantom is None and self.training is None
                and random.random() < phantom.glint_rate(self.save, self.spot_id) * dt):
            # 존재 힌트: 먼 수면에 보라빛 물결이 한 번 (화면은 물들지 않는다 — 진짜 등장 파장과 구분)
            ang = random.uniform(-0.6, 0.6) + self.cam.yaw
            d = random.uniform(40, 70)
            self.glints.append([math.sin(ang) * d, math.cos(ang) * d, 0.0])
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

    def _update_signs(self, dt: float) -> None:
        """수면 징후: 생기고 사라짐 + 물 위 연출 (새 떼·물거품·점프·반짝임)."""
        waiting = self.fight is None and self.cast.state in LOOK_STATES and self.landing is None
        kind = self.signs.update(dt, waiting, self.cam.yaw)
        if kind == "birds" and self.training is None:
            self.game.guide.event("sign_seen")   # TG-09 (문구가 새 떼 것뿐이라 새 떼에서만)
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

    def _update_school(self, dt: float) -> None:
        """물고기 떼 지나감 (CU9): 실제 3~6분마다 25% — 찌 근처 수면에 작은 물고기 떼 반짝임 20초.
        수면 징후와 겹치지 않게 (징후가 있으면 다음으로 미루고, 떼가 있는 동안 징후는 안 생김)."""
        v = load_json("core.json")["variety"]
        sc = self.school
        if sc is not None:
            sc["t"] += dt
            self.signs.next_t = max(self.signs.next_t, sc["life"] - sc["t"] + 5.0)
            if sc["t"] >= sc["life"]:
                self.school = None
                return
            sc["fx"] = sc.get("fx", 0.0) + dt
            if sc["fx"] > 0.12:
                sc["fx"] = 0.0
                if random.random() < 0.25:
                    self.ripples.spawn(sc["x"] + random.uniform(-1, 1), sc["z"] + random.uniform(-1, 1), size=0.25, life=0.7)
                ang = random.uniform(0, math.tau)
                r = random.uniform(0.2, 1.0) * v["school_radius_m"] * 0.6
                p = self.cam.project(sc["x"] + math.cos(ang) * r, sc["z"] + math.sin(ang) * r)
                if p:
                    self.sparkles.burst(p[0], p[1], count=1, speed=0.2, ring=False)
            return
        landed = self.cast.state == CastState.LANDED and self.bite.state == BiteState.WAIT and self.fight is None
        if not landed or self.training is not None or self.exam_fish is not None or self.bite.phantom is not None:
            return
        self.school_next -= dt
        if self.school_next > 0:
            return
        self.school_next = random.uniform(*v["school_interval_sec"])
        if self.signs.sign is not None or random.random() >= v["school_chance"]:
            return
        ang = random.uniform(0, math.tau)
        self.school = {"x": self.cast.bx + math.cos(ang) * 1.2, "z": self.cast.bz + math.sin(ang) * 1.2,
                       "t": 0.0, "life": v["school_sec"], "dir": random.uniform(0, math.tau)}
        self.toasts.show("물고기 떼가 지나간다!", (190, 225, 255), 2.2, 11)

    def _draw_school(self, canvas) -> None:
        """떼: 은빛 작은 물고기 12마리가 원을 그리며 반짝 (수면 바로 아래)."""
        sc = self.school
        if sc is None:
            return
        fade = min(1.0, sc["t"] / 1.0, (sc["life"] - sc["t"]) / 1.5)
        if fade <= 0.05:
            return
        rad = load_json("core.json")["variety"]["school_radius_m"] * 0.55
        for i in range(12):
            a = sc["dir"] + self.t * (0.9 + (i % 3) * 0.15) + i * (math.tau / 12)
            rr = rad * (0.55 + 0.45 * math.sin(i * 1.7 + self.t * 0.7))
            p = self.cam.project(sc["x"] + math.cos(a) * rr, sc["z"] + math.sin(a) * rr, -0.05)
            if p is None:
                continue
            flash = 0.5 + 0.5 * math.sin(self.t * 9 + i * 2.3)
            col = tuple(int(c) for c in (170 + 85 * flash, 190 + 65 * flash, 205 + 50 * flash))
            ln = max(3, int(p[2] * 0.45))
            dx = int(-math.sin(a) * ln) or 3
            if fade < 1.0 and (i / 12) > fade:
                continue
            x0, y0 = int(p[0]), int(p[1])
            pygame.draw.line(canvas, (40, 60, 80), (x0, y0 + 1), (x0 + dx, y0 + 1), 1)   # 물속 그림자 한 줄
            pygame.draw.line(canvas, col, (x0, y0), (x0 + dx, y0), 2 if flash > 0.7 else 1)   # 은빛 몸 (반짝일 때 두껍게)

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
            if self.catch_show is not None:
                self._update_catch_show(dt)
                return
            if self.landing is not None:
                self._update_landing(dt)
                return
            if self.release_scene is not None:
                self.release_scene.update(dt)
                if self.release_scene.done:
                    self.release_scene = None
                    self._end_fight()
                return
            if self.board is not None:
                from src.render.catch_board import size_class
                for ev in self.board.update(dt):
                    if ev == "flap":   # 크기 3단계 퍼덕 소리
                        name = load_json("details/hands_catch.json")["board"]["flap_sfx"][size_class(self.board.size)]
                        self.sfx.play(name, 0.8)
                if self.board.done:
                    self.board = None
                    self.end_t = 0.0
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
                if news.get("record") and not news.get("new"):
                    self.sfx.play("sfx_record", 0.85)  # 최대 크기 경신 배지와 함께
            if f.phase == "caught":   # 도감 새 칸 = 도장 쾅 + 종이 툭 · 도감 별 = 작은 반짝 (DT10, 배지가 뜨는 순간)
                for at, kind in fight_hud.badge_times(news):
                    if prev < at <= self.end_t:
                        self.sfx.play("ui_stamp" if kind == "stamp" else "ui_star", 0.6)
            if f.phase == "caught" and prev < 1.6 <= self.end_t and self.training is None and self.exam_run is None:
                self.game.guide.event("catch_shown")   # TG-03: 배지까지 다 뜬 뒤
                if getattr(self, "print_offer", None) is not None and news.get("record"):
                    self.game.guide.event("record_card")   # TG-13 (첫 포획이 아닌 크기 신기록)
                if news.get("mutations"):
                    self.game.guide.event("mutation_card")   # TG-17
                if news.get("chest"):
                    self.game.guide.event("chest_card")   # TG-10
            return
        if self._breach_tick(dt):
            return   # 전설 도약: 파이팅 완전 정지 (두뇌 · 체력 · 장력 · 줄 · 팔 힘 · 패턴 시계, CU10)
        if self._p3_tick(dt):
            return   # 전설 3페이즈 컷신: 파이팅 완전 정지 (CU11)
        if self._p2_tick(dt):
            return   # 2페이즈 컷신: 파이팅 완전 정지 (물고기 · 장력 · 줄 · 바늘 · 꼬임 · 패턴 시계)
        reeling = self.game.input.held("reel") and f.phase == "fight"
        fp = getattr(self, "tut_force_pattern", None)
        if fp and f.phase == "fight" and f.elapsed > 1.5 and f.brain.state in ("idle", "tired", "recover"):
            # 디버그 (설정 → 튜토리얼 다시 보기 → 바로): 이번 파이팅에 그 패턴을 띄워 패턴 튜토리얼 실행
            self.tut_force_pattern = None
            if fp == "chain" and not getattr(f.brain, "chain_seq", None):
                f.brain.chain_seq = ["shake", "surface", "jump"]
            if fp == "dual" and not getattr(f.brain, "dual_pairs", None):
                f.brain.dual_pairs = [["dive", "bite"]]
            if fp == "charge":
                f.brain._start_action("charge")
            else:
                f.brain.force_pattern(fp)
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
            if f.manual_drag:   # 자동 드랙이면 Shift(▼ 길게)는 물어뜯기 판정에만 (PatternInput.drag_min)
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
        if zone == "red" and getattr(self, "_tut_zone", None) != "red" and self.training is None:
            self.game.guide.event("tension_red")   # TG-02
        self._tut_zone = zone
        self.slack_t = self.slack_t + dt if zone == "slack" else 0.0
        self.red_t = self.red_t + dt if zone == "red" else 0.0
        if self.card is None and self.game.guide.run is None:
            if self.slack_t > SLACK_RED_CARD_SEC and self.tutorial.want("slack"):
                self._open_card("slack", "gauge")
            elif self.red_t > SLACK_RED_CARD_SEC and self.tutorial.want("red"):
                self._open_card("red", "gauge")

        # 예고 신호 연출
        b = f.brain
        self.fx_t += dt
        self.pump_flash = max(0.0, getattr(self, "pump_flash", 0.0) - dt)
        self.gap_flash = max(0.0, getattr(self, "gap_flash", 0.0) - dt)
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
        handoff = getattr(self.landing, "legend_handoff", False)
        for ev in self.landing.update(dt * getattr(self.landing, "speed", 1.0)):
            if handoff and ev in ("launch", "done"):
                # 그물에서 튀어 오르는 순간 = 전설의 노래 '쾅' (팡파르 대신, 보스 테마는 여기까지 이어짐)
                intro = self.landing
                self.landing = None
                self.end_t = 0.0
                self._start_legend_show(self.fight, intro)
                return
            if handoff and ev == "fanfare":
                continue
            if ev == "hit":
                self.wet_t = load_json("details/hands_catch.json")["wet_hand"]["after_net_sec"]   # 젖은 손 10초 (C)
                cls = self.landing.cls
                # 뜰채로 건질 때: 화면 아래쪽 1/4 에 물방울 6~10개가 맺혔다가 흘러내림 (A-4)
                W, H = self.cam.width, self.cam.height
                self.screen_weather.add_drops(random.randint(*load_json("details/map_details.json")["actions"]["net_drops"]),
                                              (6, H * 0.75, W - 6, H - 8))
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
                if self.landing.tier >= 3:  # N3: 들어 올림 상승음은 전설만 (화음은 팡파르가)
                    self.sfx.play("sfx_rise", 0.9)
                    self.shake_kick = 1.5
            elif ev == "fanfare":
                # 전설을 건져 올리는 순간: 팀파니 롤·금관 → 정점에 큰 화음 (음악 승리 스팅 대신)
                self.sfx.play("sfx_legend_fanfare", 1.0)
                self.sfx.duck("perfect", hold=2.2, release=0.6)
                self.game.haptics.vibrate("perfect", 1.0, delay=0.4)
            elif ev == "launch":
                self.sfx.play("sfx_launch", 0.9)
                self.sfx.play("sfx_splash_small", 0.6)
            elif ev == "apex" and phantom.is_phantom(self.landing.fish):
                # 환상: 퍼펙트 '팽·팡' + 길게 늘어진 반짝임 (전용 스팅, 강조 '크게' 예외 허용) + 길게 진동
                self.sfx.play("succ_phantom", 1.0)
                self.sfx.duck("perfect", hold=2.0, release=0.6)
                self.game.haptics.vibrate("legend", 1.0)
                self.shake_kick = 2.0
                if self.landing.chest:
                    self.sfx.play("sfx_coin", 0.9)
            elif ev == "apex":
                if self.landing.tier == 2:  # N3: 정점 '챙'·화음은 희귀만 (전설은 팡파르 안에 쿵·화음·반짝임)
                    self.sfx.play("sfx_perfect", 0.45)
                    self.sfx.play("sfx_chord_rare", 0.9)
                if self.landing.chest:
                    self.sfx.play("sfx_coin", 0.9)  # 물고기가 상자를 물고 나왔다
                if self.landing.tier >= 3:
                    self.shake_kick = 3.0
        if self.landing.done:
            chest = self.landing.chest
            lf = self.landing.fish
            self.landing = None
            self.end_t = 0.0
            # 계측판 (일반 · 고급 · 희귀): 포획 카드 전에 1.6초 (설정 '포획 장면' 보통 · 짧게 · 끄기)
            mode = self.settings.get("catch_scene") or "normal"
            hc = load_json("details/hands_catch.json")["board"]
            if mode != "off" and self.fight is not None and lf.get("rarity") in hc["for"]:
                from src.render.catch_board import MeasureBoard
                self.board = MeasureBoard(self.fight.result["fish"], self.fight.result["size"], mode, self.cam.width, self.cam.height)
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
        if perfect:   # 퍼펙트 '팡' + 노란 빛·히트스톱·흔들림은 타격 시점에
            self._success("big_pop", lambda: (self.screen_fx.glow(self._glow_sec()), self.game.slowmo(0.18, 0.25),
                                              setattr(self, "shake_kick", max(self.shake_kick, 2.5))))
        else:
            self._success("small", lambda: setattr(self, "shake_kick", max(self.shake_kick, 1.4)))


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
        ac = self.core_arm
        fighting = f is not None and f.phase == "fight"
        # 무게 단서 (CU5-2): 큰 물고기 = 낮은 릴 소리 + 줄 긁힘, 진동 세기 (작은 물고기 약하게 · 큰 물고기 세게)
        heavy = fighting and f.weight > ac["heavy_above"]
        fa.reel.low = heavy
        self.game.haptics.weight_k = (0.6 if f.weight < ac["light_below"] else 1.4 if heavy else 1.0) if fighting else 1.0
        if fighting:
            if f.name_hint and f.elapsed >= 3.0:   # 숙련 3 (CU6-1): 3초 뒤 체력 바 아래 글자 슬롯에 2초 "…쏘가리 같다?"
                self.toasts.show(f"…{f.name_hint} 같다?", (170, 172, 182), 2.0, 11)
                f.name_hint = None
            f.heavy_text_t = max(0.0, getattr(f, "heavy_text_t", 0.0) - dt)
            self.scrape_t = getattr(self, "scrape_t", 0.0) - dt
            if heavy and f.arm_wrong and self.scrape_t <= 0:
                self.scrape_t = 1.1
                self.sfx.play("sfx_scrape", ac["scrape_vol"])   # 잘못 감으면 줄이 긁히는 소리
        if self.p2 is not None and self.p2.blocking:
            fa.stop()   # 컷신 동안 파이팅 연속음 없음
        elif f is not None and f.phase == "fight":
            far = self.cast_far
            zone = f.zone()
            if zone == "green" and f.tension >= f.green_high - fa.fc["yellow_frac"] * (f.green_high - f.green_low):
                zone = "yellow"  # 소리용 노란 구간: 초록 위쪽 끝 (N3 연속음 주인공)
            fa.update(dt, {"reel": f.reel_speed_now if f.reeling else 0.0,
                           "payout": min(1.0, f.payout_now / self.fish_cfg["fight"]["payout_max_speed"]),
                           "tension": f.tension, "line": f.line_frac, "drag": (f.drag - 1) if f.manual_drag else None,   # 자동 드랙(CU3): 단계 딸깍 없음
                           "near": max(0.0, 1 - f.distance / far), "zone": zone},
                      red_at=f.green_high, active=f.brain.is_active and not f.brain.sound_only)
        elif self.cast.state == CastState.RETRIEVE:
            fa.update(dt, {"reel": 1.6}, active=False)  # 회수: 릴만 감김
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
        if f is not None and f.phase == "fight" and f.tension > fc["shake_start_tension"] \
                and not (self.p2 is not None and self.p2.blocking):
            amp += (f.tension - fc["shake_start_tension"]) / 30 * fc["shake_max_px"]
        if getattr(self, "thunder_shake", 0.0) > 0:
            self.thunder_shake -= dt
            amp = max(amp, 1.0)   # 천둥 1px
        if self.hook_cine.active and self.shake_on and not self.settings.get("reduce_fx"):
            # ② 화면이 물(찌) 쪽으로 끌려갔다 돌아옴
            c = self.cast
            p = self.cam.project(c.bx, c.bz)
            vx, vy = ((p[0] - self.cam.cx), (p[1] - self.cam.height / 2)) if p else (0.0, 1.0)
            ln = math.hypot(vx, vy) or 1.0
            off = self.hook_cine.pull_offset((vx / ln, vy / ln))
            if off != (0, 0):
                self.game.screen.shake = off
                return
        ax, ay = self.arena.shake_offset()   # 보스전 무대: 강도별 미세 흔들림 · 임팩트 방향 흔들림 (끄기 · 줄이기 반영)
        if not self.shake_on or amp < 0.3:
            self.game.screen.shake = (ax, ay)
            return
        a = int(round(amp))
        self.game.screen.shake = (max(-5, min(5, random.randint(-a, a) + ax)), max(-5, min(5, random.randint(-a, a) + ay)))

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
        if self.exam_run is not None:
            self.toasts.show("시험 중!", BAD, 1.4, 11)   # 시험 판: 소모품 효과 끔 (49-3)
        elif self.save.consumable_count(item_id) <= 0:
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
        if phantom.blessing_active(self.save):
            self.bite.rare_bonus += phantom.reward_cfg()["blessing_rare"]  # 물결의 축복: 희귀 이상 +3%p (떡밥과 더해짐)
        from src.fishing import weather_events
        self.bite.rare_bonus += weather_events.benefit(self.save, "rare_bonus")   # 쌍무지개: 희귀 이상 +2%p
        if buffs.get("lucky_casts", 0) > 0:
            buffs["lucky_casts"] -= 1
        self.bite.window_extra = 0.95 if self.save.charm_on("pinwheel_float") else 1.0
        from src.save import scalestone as _ss
        self.bite.window_add = _ss.effect(self.save, "hook_window")   # 비늘석 챔질 여유 (늘리기만)
        self.bite.rare_pp = _ss.effect(self.save, "rare_chance")      # 비늘석 희귀 확률 (희귀 등급만)
        ph = None
        from src.tutorial import scripts
        self.bite.script = scripts.plan(self.game, "bite") if self.training is None else None   # TG-01 대본 입질
        self.exam_fish = None
        from src.save import exam
        act = exam.active(self.save) if self.training is None and not self.bite.script else None
        if act and exam.on_exam_spot(self.save, self.spot_id):
            self.exam_fish = exam.exam_fish(int(act["tier"]))   # 시험 찌: 3초 뒤 시험 물고기 (날씨 · 시간 · 미끼 무시)
        elif act:
            names = exam.spot_names(exam.passed(self.save))
            self.toasts.show(f"시험 찌는 {', '.join(names)}에서", INFO, 2.4, 11)
        if self.training is None and self.force_i < 0 and not self.bite.script and self.exam_fish is None:
            test = self.settings.get("test_phantom")  # 설정 → 접근성 '테스트: 다음 착수에 환상 물고기'
            ph = phantom.roll(self.save, self.spot_id, force=self.force_phantom or test)
            self.force_phantom = False
            if test:
                self.settings.set("test_phantom", False)
        if ph is not None:
            # 환상어: 착수 지점에서 보랏빛 파장 → 대사 → 가짜 입질 없이 진짜 입질 (33-5)
            sc = phantom.spawn_cfg()
            self.bite.start_phantom((c.bx, c.bz), c.current_distance(), ph, sc["bite_delay_sec"], sc["approach_sec"])
            p = self.cam.project(c.bx, c.bz)
            self.phantom_fx.bloom((p[0], p[1]) if p else (self.cam.cx, self.cam.horizon + 20),
                                  reduce=self.settings.get("reduce_fx"))
        else:
            self.bite.season = self.season
            self.bite.extra_pool = self._extra_fish()   # 계절·날씨 이벤트 한정 물고기 (35-4)
            self.bite.start((c.bx, c.bz), c.current_distance())
            if self.exam_fish is not None:
                self.bite.timer = exam.cfg()["bite_delay_sec"]
        self.idle_ripple_t = 0.0
        self.life.on_cast_landed(self.season, self.clock.period()[0], self.spot_id)   # 잠자리 15% (E)
        self.game.guide.event("cast_landed")

    def _splash_at(self, x: float, z: float, big: float) -> None:
        self.ripples.spawn(x, z, size=big, life=1.8, rings=3 if big >= 0.8 else 2)
        p = self.cam.project(x, z)
        if p:
            self.droplets.burst(p[0], p[1], max(0.5, p[2] / 20 * big), count=int(6 + 6 * big))

    def _on_bite_event(self, ev: str) -> None:
        c = self.cast
        if self.training is None:
            self.game.guide.event(ev)   # nibble · bite (TG-01)
        if ev == "legend_approach":
            self.toasts.show("수면 아래 거대한 그림자가...!", (255, 214, 120), 3.0)
            fish = self.bite.fish
            need = self.save.float_need(fish, self.spot) if fish else 0
            if need > self.save.float_tier() and self.save.data["flags"].get("eldra_escape_tutorial"):
                self.toasts.show(f"이 물고기를 잡으려면 [{float_name(need)}] 이상 필요", BAD, 3.0, 11)
            if fish and fish.get("theme") == "ilseom":
                # 일섬: 환경음이 줄고 바람 소리만 (완전한 정적은 환상 전용) + 수면에 칼날 같은 물결 한 줄
                self.sfx.duck_levels({"amb": -14.0}, hold=2.6, release=1.2)
                theme_sfx.play(self.sfx, "ilseom", "wind", 0.8)
                p = self.cam.project(c.bx, c.bz)
                self.ilseom_fx.blade_ripple(p[1] if p else self.cam.horizon + 30)
            else:
                self.sfx.play("sfx_roar", 0.6)
            self.shake_kick = 1.5
        elif ev == "nibble":
            self.life.scare_fly()   # 입질이 오면 잠자리가 날아감 (E)
            self.sfx.play("sfx_nibble", 0.8, haptic="nibble")
            big = self.save.cosmetic_on("sparkle_float")  # 반짝이 찌: 입질 파문이 더 잘 보임
            self.ripples.spawn(c.bx, c.bz, size=0.5 if big else 0.35, life=1.0 if big else 0.8)
        elif ev == "bite":
            self.life.scare_fly()
            from src.render import hook_cine
            pl = hook_cine.plan(self.save, self.bite.fish, self.cine_full) \
                if self.training is None and self.exam_fish is None else {"pre": False}
            pre = hook_cine.cfg().get(pl.get("rarity") or "", {}).get("pre") if pl["pre"] else None
            if isinstance(pre, dict):
                # ① 입질 예고 (희귀: 물속 파란 빛 + 묵직한 '쑥' / 전설: 수면 불룩 + 쿵 / 환상: 소리 없이) — 그림 · 소리만, 챔질 창은 그대로
                self.hook_cine.start_pre(pl["rarity"], c.bx, c.bz, self.sfx)
                if pre.get("haptic_only"):
                    self.game.haptics.vibrate(*pre["haptic_only"])   # 환상: 소리는 없고 손에만 (기존 'bite')
            else:
                self.sfx.play("sfx_bite_real", haptic="bite")
            if pl.get("rarity") != "phantom" or not isinstance(pre, dict):   # 환상 ①: 물보라 없이
                self.ripples.spawn(c.bx, c.bz, size=1.3, life=1.5, rings=3)
                p = self.cam.project(c.bx, c.bz)
                if p:
                    self.droplets.burst(p[0], p[1], max(0.6, p[2] / 20), count=10)
        elif ev == "missed":
            self.sfx.play("sfx_flee", 0.6)
            if self.bite.phantom is not None:
                self._phantom_retreat(self.cast.bx, self.cast.bz)
            else:
                self.toasts.show("미끼만 먹고 도망갔다... (우클릭: 회수)", BAD, 2.6)
        elif ev == "phantom_approach":
            self.ripples.spawn(c.bx, c.bz, size=0.6, life=1.6, rings=2)
            fish = self.bite.fish
            need = self.save.float_need(fish, self.spot) if fish else 0
            if need > self.save.float_tier() and self.save.data["flags"].get("eldra_escape_tutorial"):
                self.toasts.show(f"이 물고기를 잡으려면 [{float_name(need)}] 이상 필요", BAD, 3.0, 11)

    def _on_pattern_event(self, ev: str, kind: str, pid: str) -> None:
        """신규 패턴(U3): 예고 소리·진동·첫 만남 안내, 판정 결과 연출."""
        pos = self._fish_screen()
        f = self.fight
        if ev == "fake_tired":
            kind, pid = "telegraph", "fake"  # 가짜 지침은 예고 없이 상태가 곧 신호 — 첫 만남 안내만
            if f is not None and f.fish.get("theme") == "yeoubi" and f.brain.phase >= 2:
                theme_sfx.play(self.sfx, "yeoubi", "piano", 0.35)   # 여우비 3페이즈: 기존 신호 그대로 + 아주 작은 피아노 '띵—' (능청)
        if kind == "telegraph":
            # 신호 소리·진동은 계열별로 _signal_cue 가 낸다 (31장 C3). 여기선 물고기 몸짓 소리·연출만.
            if pid == "thrash":
                self.sfx.play("sfx_splash_small", 0.6)
            if pid == "bite" and not f.brain.sound_only:
                self.sparkles.burst(*pos, count=6, speed=0.5, ring=False)  # 이빨 반짝
            seen = self.save.data.setdefault("patterns_seen", [])
            card = f"pattern:{pid}"
            first = pid not in seen
            if pid != "fake" and card in tut.CARDS:
                # 패턴 튜토리얼 (TG-P5~14·16): 예고 순간 가이드가 멈추고 설명 (예전 첫 만남 정지 카드 대신)
                if self._guide_first(card) and first:
                    seen.append(pid)
                    first = False
            if first:
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
            self._judge_burst(pos, perfect, col, "mid" if pid in SUCC_MID else "small")
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
            self._judge_burst(pos, True, (255, 214, 90), "big")  # 콤보 완료·이중 패턴 = 성공음 big
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
            # 더블 퍼펙트 '팡·팡': 노란 이펙트 두 번 = impact_ms · second_impact_ms (오디오 최종 팩)
            mp = self.screen_fx.map(pos)

            def first():
                self.popups.add("double_perfect", pos)
                self.screen_fx.perfect(mp, glow=self._glow_sec())
                self.sparkles.burst(*pos, count=36, speed=1.6)
                self.pvfx.combo(pos[0], pos[1], [(255, 214, 90), (255, 255, 255), (255, 214, 90)])
                self.game.slowmo(0.9, 0.25)  # 강한 슬로우
                self.shake_kick = 3.0

            def second():
                self.screen_fx.perfect(mp, glow=self._glow_sec())
                self.sparkles.burst(*pos, count=24, speed=1.4)
                self.shake_kick = max(self.shake_kick, 2.5)
            self._success("double_pop", first, second)
            st = self.save.data["stats"]
            st["double_perfects"] = st.get("double_perfects", 0) + 1
        elif ev == "thrash_second_miss":
            self.toasts.show("착수 직전을 놓쳤다! 바늘이 크게 흔들린다", BAD, 1.8, 11)
        elif ev == "stiff":
            self.toasts.show("헛물었다! 잠깐 굳었다 — 지금 크게 감으세요", GOOD, 1.8, 11)
            self.game.haptics.vibrate("bite", 0.6)
        elif ev == "dual_ok":
            self._judge_burst(pos, True, (255, 214, 90), "big")  # 콤보 완료·이중 패턴 = 성공음 big
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

    def _judge_burst(self, pos, perfect: bool, col, grade: str = "small") -> None:
        """판정 성공 공통 연출: 원래 PERFECT / GREAT 와 같은 급 (섬광·충격파·빛줄기·줌 펀치·반짝임·소리·진동).
        소리 = 오디오 최종 팩 성공음 (grade: small / mid / big — 퍼펙트면 big_pop), 연출은 그 소리의 타격 시점에."""
        mp = self.screen_fx.map(pos)
        if perfect:
            theme = self.fight.fish.get("theme") if self.fight is not None else None

            def fx():
                if theme == "ilseom":   # 일섬: 짧은 '챙!' + 화면 위쪽 절반 사선 베기 선 (화면 효과 줄이기면 선은 끔)
                    theme_sfx.play(self.sfx, "ilseom", "chaeng", 0.7)
                    if not self.settings.get("reduce_fx"):
                        self.ilseom_fx.slash()
                elif theme == "yeoubi":   # 여우비: 짧은 금화 '띵'
                    theme_sfx.play(self.sfx, "yeoubi", "coin", 0.55)
                elif theme == "sangun":   # 산군: 짧은 발톱 '촥'
                    theme_sfx.play(self.sfx, "sangun", "claw", 0.55)
                elif theme == "taego":    # 태고: 맑은 작은 종 '딩'
                    theme_sfx.play(self.sfx, "taego", "bell", 0.5)
                self.sparkles.burst(*pos, count=40, speed=1.7)
                self.sparkles.burst(*pos, count=16, speed=0.6, ring=False)
                self.screen_fx.perfect(mp, glow=self._glow_sec())
                self.screen_fx.shockwaves.append([mp[0], mp[1], -0.1, col, 0.5, 2])
                self.shake_kick = max(self.shake_kick, 2.5)
                fc = self.fish_cfg["fight"]
                self.game.slowmo(fc["slowmo_real_sec"] * 0.6, fc["slowmo_scale"])
            self._success("big" if grade == "big" else "big_pop", fx)
        else:
            def fx():
                self.sparkles.burst(*pos, count=16, speed=1.0)
                self.screen_fx.great(mp)
                self.screen_fx.shockwaves.append([mp[0], mp[1], -0.06, col, 0.4, 1])
                self.shake_kick = max(self.shake_kick, 1.2)
            self._success(grade, fx)

    def _glow_sec(self) -> float:
        return reel_audio.manifest().get("perfect_effect", {}).get("glow_duration_ms", 300) / 1000

    def _at(self, sec: float, fn) -> None:
        """실제 시간 sec초 뒤 fn (슬로우모션과 상관없이 — 소리는 실제 시간으로 흐른다)."""
        if fn is None:
            return
        if sec <= 0.002:
            fn()
        else:
            self.rt_fx.append([time.perf_counter() + sec, fn])

    def _run_rt_fx(self) -> None:
        if not getattr(self, "rt_fx", None):
            return
        now = time.perf_counter()
        due = [e for e in self.rt_fx if e[0] <= now]
        if due:
            self.rt_fx = [e for e in self.rt_fx if e[0] > now]
            for _, fn in sorted(due, key=lambda e: e[0]):
                fn()

    def _success(self, grade: str, fx=None, fx2=None, vol: float = 1.0) -> None:
        """패턴 성공음 (오디오 최종 팩 assets/sfx/success, manifest success_mapping):
        small 일반 대응 / mid 꼬임 해소·역주행 회수·숨기 기습 / big 콤보 완료·이중 패턴 / big_pop 퍼펙트 / double_pop 더블 퍼펙트.
        같은 파이팅 연속 성공 0~2단계(3번째부터 2 유지, 실패하면 0). 판정 순간 바로 재생(파일 앞에 impact_ms 만큼 앞부분),
        연출 fx·진동은 impact_ms(+ 오디오 지연 보정) 뒤, 더블은 fx2 를 second_impact_ms 에.
        small 은 1.5초 쿨다운(겹치면 소리 생략 — 연출은 바로). 울리는 동안 릴·환경음·음악 −3dB, 끝나면 0.3초에 걸쳐 복귀."""
        if grade == "small" and self.t - getattr(self, "succ_small_t", -9.0) < 1.5:
            self._at(0.0, fx)
            return
        if grade == "small":
            self.succ_small_t = self.t
        st = min(2, getattr(self, "succ_streak", 0))
        self.succ_streak = getattr(self, "succ_streak", 0) + 1
        info = reel_audio.success_info(grade, st)
        off = self.settings.get("audio_offset_ms") / 1000.0
        t1 = max(0.0, info["impact_ms"] / 1000.0 + off)
        if self.settings.get("success_sfx"):
            self.sfx.play(reel_audio.success_name(grade, st), vol)
            self.sfx.duck("success", hold=info["duration_sec"], release=0.3)
        hp = self.game.haptics
        if grade in ("double_pop", "double"):
            t2 = max(0.0, (info["second_impact_ms"] or 460) / 1000.0 + off)
            hp.vibrate("perfect", 1.0, delay=t1)
            hp.vibrate("perfect", 1.0, delay=t2)
            self._at(t1, fx)
            self._at(t2, fx2)
            return
        kind, k = {"small": ("pump", 0.35), "mid": ("bite", 0.6), "big": ("perfect", 0.85)}.get(grade, ("perfect", 1.0))
        hp.vibrate(kind, k, delay=t1)   # 일반 성공은 짧게, 퍼펙트는 강하게
        self._at(t1, fx)

    def _tip(self, key: str) -> None:
        n = self.tip_counts.get(key, 0)
        if key in TIPS and n < TIP_REPEAT:
            self.tip_counts[key] = n + 1
            self.toasts.show(TIPS[key], INFO, 2.2, 11)

    # ───────────────────────── 환상 2페이즈 컷신 (PHANTOM_PHASE2.md) ─────────────────────────
    # ───────────────────────── 전설 등장 도약 (CU10, LEGEND_BREACH.md) ─────────────────────────
    def _breach_start(self, fish: dict) -> None:
        from src.render.legend_breach import LegendBreach, cfg as bcfg
        p = self.cam.project(self.cast.bx, self.cast.bz)
        bob = (p[0], p[1]) if p else (self.cam.width / 2, self.cam.horizon + 30)
        seen = self.save.data.setdefault("breach_seen", [])
        bc = bcfg()
        impact = None
        suno = self.game.boss.suno
        if suno.active:   # SUNO 마디 첫 박이 착수 예정 ±0.35초 안이면 착수를 그 박에
            tb = suno.until_bar_after(max(0.0, bc["impact_at"] - bc["beat_window"]))
            if tb is not None and abs(tb - bc["impact_at"]) <= bc["beat_window"]:
                impact = tb
        self.breach = LegendBreach(fish, bob, (self.cam.width, self.cam.height), bool(self.settings.get("reduce_fx")),
                                   fish["id"] in seen, self.arena.color if self.arena.active else None, impact)
        self.arena.card_hold = self.breach.impact_at                 # 카드는 착수 순간 올라가기 시작
        self.arena.card_end = self.breach.impact_at + bc["card_rise_sec"]

    def _breach_tick(self, dt: float) -> bool:
        """True = 이번 틱 파이팅을 멈춤."""
        br = self.breach
        if br is None:
            return False
        if not br.blocking:
            self.breach = None
            return False
        for ev in br.update(dt):
            if ev[0] == "sfx":
                self.sfx.play(ev[1], ev[2])
            elif ev[0] == "reel":
                self.fight_audio.reel.rush_begin()   # 줄이 끌려 나가는 릴 소리
            elif ev[0] == "duck":
                self.sfx.duck_levels({"amb": ev[1], "sfx": ev[1]}, hold=ev[2], release=0.2)   # 정점: 짧은 정적
            elif ev[0] == "impact":
                self.game.haptics.vibrate("legend", 1.0)
                self._boss_accent()
            elif ev[0] == "done":
                self._breach_end()
        self.fight_audio.stop()
        return True

    def _breach_end(self) -> None:
        """끝: 파이팅 시작 (첫 신호는 grace_sec 뒤부터) · 그 전설 도약을 본 기록."""
        from src.render.legend_breach import cfg as bcfg
        f = self.fight
        seen = self.save.data.setdefault("breach_seen", [])
        if f is not None:
            if f.fish["id"] not in seen:
                seen.append(f.fish["id"])
            b = f.brain
            g = bcfg()["grace_sec"]
            if b.state == "idle":
                b.timer = max(b.timer, g)
            else:
                b._enter("idle", g)
        self.arena.card_hold = self.arena.card_end = None
        self.breach = None

    # ───────────────────────── 전설 3페이즈 컷신 (CU11) ─────────────────────────
    def _p3_start(self) -> None:
        from src.render.legend_phase3 import Phase3Cine
        f = self.fight
        seen = self.save.data.setdefault("p3_seen", [])
        pos = self.screen_fx.map(self._fish_screen())
        self.p3 = Phase3Cine(f.fish, pos, (self.cam.width, self.cam.height), self.cam.horizon,
                             self.arena.color if self.arena.active else None, bool(self.settings.get("reduce_fx")),
                             f.fish["id"] in seen)
        ph = f.fish.get("phase_at", self.fish_cfg["legend"]["phase_at"])
        self.p3_before = min(f.stamina_frac, ph[min(1, len(ph) - 1)])   # 진입 직전 체력 (바가 여기서 차오름)
        self.toasts.items.clear()
        self.fight_audio.stop()
        self.signal_audio.stop()

    def _p3_tick(self, dt: float) -> bool:
        """True = 이번 틱 파이팅을 멈춤."""
        cine, f = self.p3, self.fight
        if cine is None or f is None:
            return False
        from src.audio import theme_sfx
        for ev in cine.update(dt):
            if ev[0] == "sfx":
                self.sfx.play(ev[1], ev[2])
            elif ev[0] == "theme":
                theme_sfx.play(self.sfx, ev[1], ev[2], ev[3])
            elif ev[0] == "mus":
                self.sfx.duck_levels({"mus": ev[1]}, hold=ev[2], release=0.3)   # 보스 곡 −6dB → 마지막에 원래대로
            elif ev[0] == "dragon":   # 등용: 기존 용 변신이 ② (2.4초)
                pos = self._fish_screen()
                self.dragon_fx = DragonTransform(self.screen_fx.map(pos))
            elif ev[0] == "done":
                self._p3_end()
                return True
        f.bar_override = cine.bar_value(self.p3_before, f.stamina_frac)
        self.fight_audio.stop()
        return True

    def _p3_end(self) -> None:
        """끝: 체력 바 50% · 무대 강도 3 (페이즈로 자동) · 신호는 grace_sec 뒤부터 · 본 기록."""
        from src.render.legend_phase3 import cfg as p3cfg
        f = self.fight
        self.p3 = None
        if f is None:
            return
        f.bar_override = None
        seen = self.save.data.setdefault("p3_seen", [])
        if f.fish["id"] not in seen:
            seen.append(f.fish["id"])
        b = f.brain
        g = p3cfg()["grace_sec"]
        if b.state == "idle":
            b.timer = max(b.timer, g)
        else:
            b._enter("idle", g)
        if not b.dragon:
            self.toasts.show(f"기운을 되찾았다! 체력 {f.stamina_frac * 100:.0f}%", (255, 140, 120), 2.6, 11)

    def _p2_values(self) -> dict:
        """컷신 전후 비교용 파이팅 수치 (체력만 바뀌어야 함)."""
        f = self.fight
        return {"tension": round(f.tension, 4), "line": round(f.line_frac, 4), "twist": round(f.twist.value, 4),
                "distance": round(f.distance, 4), "stamina": round(f.stamina_frac, 4), "drag": f.drag,
                "brain": f.brain.state, "elapsed": round(f.elapsed, 4), "phase": f.brain.phase}

    def _p2_music(self):
        """환상 공통 곡이 돌고 있으면 그 재생기 (물속 버전 · 마디 · 박), 아니면 None."""
        sb = self.game.boss.suno
        return sb if sb.active and sb.song and sb.is_phantom(sb.song) else None

    def _p2_start(self) -> None:
        from src.core import fxq
        from src.render.phantom_phase2 import Phase2Cine
        f = self.fight
        mode = (self.p2_pending or {}).get("mode")
        self.p2_pending = None
        full = mode != "short"   # 다시 만나도 첫 만남과 같은 전체 컷신 (사용자 요청) — 짧은 버전은 Shift+F6 디버그만

        def wait(kind, lead):
            m = self._p2_music()
            if m is None:
                return None
            return m.until_bar_after(lead) if kind == "bar" else m.until_beat_after(lead)

        self.p2 = Phase2Cine(f.fish, full, bool(self.settings.get("reduce_fx")), fxq.level(), f.stamina_frac,
                             (self.cam.width, self.cam.height), wait)
        self.p2_log = [{"at": "start", "full": full, **self._p2_values()}]
        self.fight_audio.stop()
        self.signal_audio.stop()
        self.toasts.items.clear()

    def _p2_tick(self, dt: float) -> bool:
        """True = 이번 틱 파이팅을 멈춤."""
        f = self.fight
        if getattr(self, "p2_dbg_wait", 0) > 0:
            self.p2_dbg_wait -= dt
            if self.p2_dbg_wait <= 0 and f.brain.phase == 0:
                f.stamina = min(f.stamina, f.stamina_max * (f.fish.get("phase_at", [0.5])[0] - 0.01))
        if self.p2_pending is not None and self.p2 is None:
            self.p2_pending["t"] += dt
            if f.phase == "fight" and (not f.pats or self.p2_pending["t"] > 2.0):   # 패턴 판정이 난 직후
                self._p2_start()
        cine = self.p2
        if cine is None:
            return False
        was = cine.blocking
        for ev in cine.update(dt):
            if ev[0] == "sfx":
                self.sfx.play(ev[1], ev[2])
            elif ev[0] == "muffle":
                m = self._p2_music()
                if m is not None:
                    m.set_muffle(ev[1], ev[2])
            elif ev[0] == "resume":
                self._p2_resume()
        k = cine.k()
        self.phantom_fx.k_override = k
        db = cine.amb_db() if cine.blocking else 0.0
        if db < -0.5:
            self.sfx.duck_levels({"amb": db}, hold=0.1, release=1.0)   # 주변 소리가 잦아듦 → 폭발 때 돌아옴
        if cine.blocking:
            self.p2_aura = max(self.p2_aura, cine.aura_in())          # E: 빛이 사그라들며 뒷배경 오라가 남음
            if cine.boom is not None and cine.t >= cine.boom:
                f.p2_shift = True
        if cine.finished:
            self.p2 = None
            self.phantom_fx.k_override = None
        return was

    def _p2_resume(self) -> None:
        """재개: 체력 정확히 100% · 1초 유예 · 2페이즈 체력 바 · 뒷배경 오라 · 첫 만남 카드 · 세이브."""
        f = self.fight
        c = load_json("phantom/phase2_cutscene.json")
        f.stamina = f.stamina_max * c["phase2_hp_percent"] / 100.0
        b = f.brain
        if b.state == "idle":
            b.timer = c["grace_sec"]   # 새 패턴을 시작하지 않음 (장력 · 감기는 정상)
        else:
            b._enter("idle", c["grace_sec"])
        self.p2_on = True
        self.p2_aura = 1.0
        f.p2_bar = True   # 체력 바 2페이즈 모습 (fight_hud.draw_boss_bar)
        if self.p2 is not None and self.p2.full:
            seen = phantom.state(self.save)["phase2_seen"]
            if f.fish["id"] not in seen:
                seen.append(f.fish["id"])
        self.p2_log.append({"at": "resume", **self._p2_values()})
        if self.p2_card and self.card is None:
            self._open_card(self.p2_card, "fish")   # 고유 패턴 첫 만남: 정지 카드 (컷신 뒤, 재개 전)
        self.p2_card = None

    def _p2_clear(self) -> None:
        if self.p2 is not None or self.p2_pending is not None:
            m = self._p2_music()
            if m is not None:
                m.set_muffle(False, 0.15)
        self.p2 = None
        self.p2_pending = None
        self.p2_card = None
        self.p2_on = False   # 오라는 남은 만큼 페이드 (_p2_aura_tick)
        self.p2_dbg_wait = 0.0
        self.phantom_fx.k_override = None

    def _p2_aura_tick(self, dt: float) -> None:
        """뒷배경 오라: 2페이즈 내내. 포획 성공(환상 포획 연출 시작) 0.5초 · 실패 · 도주 1초에 사라짐."""
        f = self.fight
        on = self.p2_on and f is not None and f.phase in ("fight", "net")
        A = load_json("phantom/phase2_cutscene.json")["aura"]
        if self.p2_on and not on:
            self.p2_on = False
            self.p2_aura_fade = A["fade_catch"] if f is not None and f.phase == "caught" else A["fade_fail"]
        if not on and not (self.p2 is not None and self.p2.blocking):
            self.p2_aura = max(0.0, self.p2_aura - dt / self.p2_aura_fade)

    def _p2_draw_rod(self, canvas, drop: float) -> None:
        """컷신: 고개를 숙이며 손 · 낚싯대가 화면 아래로 천천히 빠짐 (drop px), 솟구친 뒤 다시 올라옴."""
        from src.render.rod import draw_rod, gear_look
        from src.save.quests import skin_colors
        geo = self._rod_geo()
        if drop > 0.5:
            geo = {k: ((v[0], v[1] + drop) if k in ("hand", "butt", "ctrl", "tip") else v) for k, v in geo.items()}
        else:
            self._draw_fight_line(canvas, self._p2_pal, geo["tip"])
        rod_l = gear_look("rod", self.save.gear_tier("rod"))
        reel_l = gear_look("reel", self.save.gear_tier("reel"))
        skin = skin_colors(self.save, "rod_skin")
        if skin:
            rod_l = dict(rod_l, rod=skin[0], hi=skin[1])
            reel_l = dict(reel_l, body=skin[2])
        draw_rod(canvas, self._p2_pal, geo, self.cast.reel_angle, rod_l, reel_l, self.t, hand_look=self._hand_look())

    def _p2_debug(self, mode: str) -> None:
        """디버그 Shift+F4(전체) / Shift+F6(짧은): 환상어 파이팅이면 곧바로 2페이즈 컷신, 아니면 다음 환상어로 파이팅을 열고 컷신."""
        f = self.fight
        if f is not None and f.phase == "fight" and f.fish.get("rarity") == "phantom":
            if self.p2 is not None or self.p2_pending is not None:
                return
            if f.brain.phase == 0:
                self.p2_force = mode
                f.stamina = f.stamina_max * (f.fish.get("phase_at", [0.5])[0] - 0.01)   # 다음 틱에 2페이즈 진입
            else:
                self.p2_pending = {"mode": mode, "t": 0.0}
            self.toasts.show(f"[테스트] 2페이즈 컷신 ({'전체' if mode == 'full' else '짧은'})", INFO, 1.2, 11)
            return
        if f is not None:
            return
        import copy
        lst = phantom.all_phantoms()
        i = getattr(self, "p2_dbg_i", -1) + 1
        self.p2_dbg_i = i % len(lst)
        fish = lst[self.p2_dbg_i]
        self.bite.fish = copy.deepcopy(fish)
        self.bite.cast_distance = 20.0
        self.cast.bx, self.cast.bz = 2.0, 20.0   # 찌가 있던 자리 = 물고기 시작 위치
        self.cast.state = CastState.HOOKED
        self.phantom_fx.mode, self.phantom_fx.t, self.phantom_fx.k = "fight", 0.0, 1.0
        self.phantom_fx.k_from = 1.0
        self._start_fight()
        self.p2_dbg_wait = 1.5   # 파이팅이 1.5초 흐른 뒤 체력을 2페이즈 기준 아래로 → 컷신
        self.p2_force = mode
        self.toasts.show(f"[테스트] 2페이즈 컷신 ({'전체' if mode == 'full' else '짧은'}) {self.p2_dbg_i + 1}/12 {fish['id']}",
                         INFO, 2.0, 11)

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
        if self.exam_run is not None:
            # 시험 판: 숙련도 · 연속 실패는 건드리지 않고, 놓친 패턴만 (3번 불합격 뒤 힌트, 49-3)
            if not ok:
                m = self.exam_run["miss"]
                m[pid] = m.get(pid, 0) + 1
                if pid not in self.missed_signals:
                    self.missed_signals.append(pid)
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
        if self.training is None:
            self.game.guide.event(ev)   # tired · net_start … (가이드 튜토리얼)
            if ev == "net_start":
                self.game.guide.event("net_phase")
        self._mastery_event(ev)
        self.signal_audio.on_event(ev)
        if self.arena.active:
            self._arena_event(ev)
        self.sfx.boost = 2 if "clear" in f.mutations and ev.startswith("telegraph:") else 1  # 투명: 예고 소리 +6dB
        if ev in SUCC_RESET or ev.startswith(("pattern_fail", "lost:")):
            self.succ_streak = 0  # 연속 성공 끊김
        if ev == "arm_heavy":   # 처음 한 번 "무겁다…!" (세이브당, CU5-2)
            seen = self.save.data.setdefault("flags", {})
            if not seen.get("arm_heavy_seen"):
                seen["arm_heavy_seen"] = True
                f.heavy_text_t = self.core_arm["heavy_text_sec"]
        if ev == "arm_out":   # 팔 힘 바닥 (CU5-1): 진동 한 번 (게이지 빨강 깜빡 · 손 떨림은 그리기에서)
            self.game.haptics.vibrate("tension", 0.6)
        if ev == "gap_hit":   # 틈 공략 성공 (CU4-3): 흰 금색 짧은 번쩍 + 작은 반짝
            self.gap_flash = 0.18
            p = self._fish_screen()
            self._success("small", lambda: self.pvfx.success("rush", p[0], p[1], False, (255, 236, 170)))
        if ev == "rush_ok":
            p = self._fish_screen()
            self._success("small", lambda: self.pvfx.success("rush", p[0], p[1], False, (255, 170, 90)))  # 돌진을 버텼다: 작은 반짝
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
        if ev in GUIDE_FIRST:
            self._guide_first(ev)   # 돌진·점프·방향 전환·힘 모으기·가짜 지침 첫 만남 → 패턴 튜토리얼 (TG-P1~4·15)
        elif ev in ("tired", "net_start"):
            pass   # 첫 지침·첫 뜰채 카드는 가이드 튜토리얼(TG-02)로 바뀜
        elif ev in tut.CARDS and self.card is None and self.tutorial.want(ev):
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
            if f.fish.get("theme") == "ilseom":   # 일섬: 수면에 물고기 방향 얇은 흰 선 (신호 표현은 그대로, 덧붙이기만)
                fx_, fy_ = self._fish_screen()
                dx, dy = fx_ - self.cam.width / 2, fy_ - self.cam.height
                ln = max(1.0, (dx * dx + dy * dy) ** 0.5)
                self.ilseom_fx.rush_line((fx_ - dx / ln * 70, fy_ - dy / ln * 70), (fx_ - dx / ln * 14, fy_ - dy / ln * 14))
        elif ev == "telegraph:jump":
            self.sfx.play("sfx_bubbles", 0.8)
            if f.brain.lightning_cue:
                # 전설 '일렉트로': 번개 섬광이 점프 박자
                self.lightning.strike(self.cam.horizon, self.cam.width)
        elif ev.startswith("phase:"):
            n = int(ev.split(":")[1])
            if (f.fish.get("rarity") == "legend" and n == 3   # 3페이즈 진입 (오르시엘은 4페이즈까지 — 4페이즈 전환은 공통 연출)
                    and self.training is None and self.exam_run is None):
                self._p3_start()   # 전설 3페이즈: 공통 페이즈 연출 대신 눈빛 대치 + 각자의 필살 (CU11)
                return
            if f.fish.get("theme") == "ilseom" and n == len(f.fish.get("phases", [])):
                theme_sfx.play(self.sfx, "ilseom", "jing", 0.9)   # 일섬 3페이즈: 징 + 가장자리 0.3초 어둡게
                if not self.settings.get("reduce_fx"):
                    self.ilseom_fx.vignette()
            if f.fish.get("rarity") == "phantom":
                # 환상 2페이즈: 공통 페이즈 연출(거세짐 · 포효 · 번쩍 · 흔들림 · 슬로모션) 대신 전용 컷신 (PHANTOM_PHASE2.md).
                # 지금 패턴 판정이 끝나면 시작, 첫 만남 신호 카드는 컷신이 끝난 뒤 재개 전에.
                key = f"phantom:{f.fish['id']}"
                self.p2_card = key if self.tutorial.want(key) and self.settings.get("signal_cards") else None
                self.p2_pending = {"mode": self.p2_force, "t": 0.0}
                self.p2_force = None
                return
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
        elif ev == "phase_heal":
            # 전설 3페이즈: 기운을 되찾는다 (체력 50%, 등용 100%) — 용 변신은 배너가 대신 알림 · 3페이즈 컷신은 끝에 (CU11)
            if not f.brain.dragon and self.p3 is None:
                self.toasts.show(f"기운을 되찾았다! 체력 {f.stamina_frac * 100:.0f}%", (255, 140, 120), 2.6, 11)
        elif ev == "telegraph:turn":
            self.sfx.play("sfx_scrape", 0.8)
        elif ev == "action:rush":
            # 펄스가 손에 닿음 = 돌진: zing_rise(C·A·B 무작위) → 줄이 풀리는 동안 loop_fast → 정점 drag_fast → 끝 reel_stop
            # (오디오 최종 팩). 신호음 '강조' 모드만 예전 '쉬익'(legacy_rush_go)도 같이.
            self.fight_audio.reel.rush_begin()
            if self.signal_audio.boss(f):
                self.signal_audio.boss_go()   # 보스 '쾅!' — 화면 임팩트(_arena_event, 같은 이벤트)와 같은 틱
            elif self.settings.get("signal_mode") == 2:
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
            self.arena.parry(self.screen_fx.map(pos))
            self.popups.add("swipe_perfect", pos, f.perfect_streak)
        elif ev == "good" and f.last_judge_kind == "swipe":
            self._swipe_vfx(False)
            self.popups.add("swipe_good", self._fish_screen())
        elif ev == "perfect":
            # 퍼펙트 '팡': 성공음(big_pop) 타격 시점에 노란 섬광(glow 0.3초) + 충격파 + 빛줄기 + 반짝임 + 슬로우
            pos = self._fish_screen()
            ps = f.perfect_streak

            def fx():
                self.sparkles.burst(*pos, count=40, speed=1.7)
                self.sparkles.burst(*pos, count=16, speed=0.6, ring=False)
                self.screen_fx.perfect(self.screen_fx.map(pos), glow=self._glow_sec())
                self.arena.parry(self.screen_fx.map(pos))   # 보스전: 받아쳤다 — 흰 금색 테두리 + 물보라
                self.popups.add("perfect", pos, ps)
                self.shake_kick = 2.5
                fc = self.fish_cfg["fight"]
                self.game.slowmo(fc["slowmo_real_sec"], fc["slowmo_scale"])
            self._success("big_pop", fx)
        elif ev == "good":
            # 그레잇: 작은 섬광 + 충격파 + 반짝임 (성공음 small 타격 시점에)
            pos = self._fish_screen()

            def fx():
                self.sparkles.burst(*pos, count=16, speed=1.0)
                self.screen_fx.great(self.screen_fx.map(pos))
                self.popups.add("good", pos)
                self.shake_kick = 1.2
            self._success("small", fx)
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
        elif ev == "caught" and self.exam_run is not None:
            self._exam_caught(f)
        elif ev.startswith("lost:") and self.exam_run is not None:
            self._exam_lost(f, ev)
        elif ev == "caught":
            pose, _ = f.net_pose()
            shown = self._display_fish(f.fish)
            from src.save import treasure
            golden = self.save.equipped("net")["id"] == "golden_net"
            if golden:
                # 황금 뜰채: 크기 +3% (판매가도 그만큼)
                f.result["size"] = round(f.result["size"] * 1.03, 1)
                f.result["price"] = int(round(f.result["price"] * 1.03))
            sp = _ss_frac(self.save, "sell_price")
            if sp > 0:   # 비늘석 판매가 +% (합계 상한 10%, 46장 S4)
                f.result["price"] = int(round(f.result["price"] * (1 + sp)))
            muts = f.result.get("mutations") or []
            from src.fishing import mutation
            mk = mutation.cfg()["kinds"]
            bonus = mk["frenzy"]["chest_bonus"] if "frenzy" in muts else 0.0  # 광폭: 상자 +2%p
            if phantom.blessing_active(self.save):
                bonus += phantom.reward_cfg()["blessing_chest"]  # 물결의 축복: 상자 +1%p
            from src.fishing import weather_events
            bonus += weather_events.benefit(self.save, "chest_bonus")   # 유성우 밤: 상자 +1%p
            sb = weather_events.benefit(self.save, "s_sale_bonus")
            if sb and f.result["rank"] == "S":   # 은빛 안개: S랭크 판매가 +10%
                f.result["price"] = int(round(f.result["price"] * (1 + sb)))
            ph_first = phantom.is_phantom(f.fish) and not phantom.caught(self.save, f.fish["id"])
            self.chest_drop = treasure.roll_drop(self.save, f.fish, f.result["rank"], bonus=bonus, first=ph_first)
            legend_scales = 0
            if f.fish["rarity"] == "legend" and self.spot.get("continent") == "eldrasion":
                # 전설 비늘: 첫 포획 5개, 이후 2개 (T7·T8, 봉인 찌 재료) — 전설 포획 카드에 보상 아이콘으로
                legend_scales = 2 if self.save.caught(f.fish["id"]) else 5
                self.save.data["scales"] += legend_scales
            if not phantom.is_phantom(f.fish):  # 환상어는 전용 포획 연출 (아래 PhantomShow)
                self.landing = LandingCinematic(shown, f.result["size"], 240 + pose * 46, chest=self.chest_drop,
                                                golden=golden)
                if getattr(f, "name_hidden", False):   # 정체 공개 (CU6-1): 물 밖으로 나오는 순간 이름 '쾅' + 처음이면 NEW!
                    self.landing.reveal = {"name": shown["name"], "color": fight_hud.RARITY_COLOR.get(shown["rarity"]),
                                           "new": not self.save.caught(shown["id"])}
                # 전설: 뜰채로 끌어올린 뒤 그물에서 튀어 오르는 순간(launch) 전설 포획 연출로 넘어감 (34장)
                self.landing.legend_handoff = f.fish["rarity"] == "legend"
            f.result["fish"] = shown
            self.end_t = 0.0
            self.catch_news = self.save.record_catch(f.result | {"perfects": f.perfects})
            self._check_exam_ready()
            hc = load_json("details/hands_catch.json")
            self.release_item = (self.save.data["keepnet"][-1] if f.fish.get("rarity") in hc["release"]["for"]
                                 and self.training is None and self.save.data["keepnet"] else None)
            from src.ui.catch_stamp import stamp_text
            self.catch_news["stamp"] = stamp_text(self.clock.hour, self.clock.period()[0], self.weather, self.season, self.spot)
            self.catch_news["chest"] = self.chest_drop
            if muts:
                self.catch_news["mutations"] = list(muts)
            if legend_scales:
                self.catch_news["legend_scales"] = legend_scales
            self.catch_news["title_frame"] = phantom.state(self.save)["title_frame"]
            if f.fish["rarity"] == "legend" and self.catch_news.get("new"):
                self.catch_news["legend_line"] = phantom.hints()["legend_line"]
            if phantom.is_phantom(f.fish):
                self.catch_news.update(phantom.on_catch(self.save, f.fish, ph_first))
            from src.save import dexbook
            self.catch_news.update(dexbook.on_catch(self.save, f.fish))   # 도감 별·숙련·도감 보상 (35-2, 결과 화면에서만)
            from src.save import prints
            self.print_offer = prints.offer(self.save, f.fish, f.result["size"])   # 어탁 (35-2): 크기 신기록이면 결과 화면에 버튼
            if getattr(self.landing, "legend_handoff", False):
                # 다시 잡은 전설: 뜰채 끌어올리기도 빠르게 (환상 재포획 3.5초보다 짧게 — 희귀함 순서)
                from src.render.legend_show import pick_variant as _lv
                if _lv(f.fish, self.catch_news, self.save) == "short":
                    self.landing.speed = load_json("legend_catch_timeline.json")["short_landing_speed"]
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
            self.game.save_now()  # 보상·도감은 연출 전에 저장 (건너뛰기·백그라운드에도 안전)
            if phantom.is_phantom(f.fish):
                self._start_phantom_show(f)
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
            if phantom.is_phantom(f.fish):
                self._phantom_retreat(*f.fish_xz())
            self.game.save_now()  # N3: 놓침 하강음 없음
            self.end_t = 0.0
            self.escape_tutorial_pending = True
        elif ev.startswith("lost:"):
            self.save.record_loss()
            if phantom.is_phantom(f.fish):
                self._phantom_retreat(*f.fish_xz())
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

    # ── 백 노인의 시험 판 (49-3) ──
    def _exam_caught(self, f) -> None:
        """시험 물고기 포획: 가방 · 도감 · 의뢰 · 업적 · 통계 · 상자 · 어탁 없음 → 합격 판정만."""
        from src.save import exam
        pose, _ = f.net_pose()
        shown = self._display_fish(f.fish)
        self.chest_drop = None
        self.landing = LandingCinematic(shown, f.result["size"], 240 + pose * 46, chest=None, golden=False)
        f.result["fish"] = shown
        self.end_t = 0.0
        t = self.exam_run["tier"]
        ok = exam.judge(t, f.result)
        res = exam.finish(self.save, ok, self.clock.day, self.exam_run["miss"])
        self.exam_run["result"] = res
        self.catch_news = {"exam": res | {"need": exam.pass_text(t)}}
        self.print_offer = None
        self.release_item = None
        self.game.save_now()

    def _exam_lost(self, f, ev: str) -> None:
        """시험 물고기를 놓침 = 불합격 (기록 · 통계 없음)."""
        from src.save import exam
        res = exam.finish(self.save, False, self.clock.day, self.exam_run["miss"])
        self.exam_run["result"] = res
        self.game.save_now()
        self.game.haptics.vibrate("lose")
        self.sfx.play("sfx_line_snap" if ev == "lost:snap" else "sfx_flee")
        if ev == "lost:snap":
            self.sfx.duck("snap")
        self.end_t = 0.0
        self.shake_kick = 4.0 if ev == "lost:snap" else 0.0

    def _check_exam_ready(self) -> None:
        """자격을 처음 다 채운 순간 (시험 안내 TG-22 를 본 세이브): 파이팅이 끝나면 토스트 '백 노인이 자네를 찾던데?' (티어마다 한 번)."""
        from src.save import exam
        t = exam.next_tier(self.save)
        st = exam.state(self.save)
        if t is None or t in st["goal_toast"] or not self.game.guide.done("TG-22") or not exam.eligible(self.save):
            return
        st["goal_toast"].append(t)
        self.exam_ready_toast = True

    def _exam_end(self, res: dict | None) -> None:
        """시험 판 결과 화면을 닫은 뒤: 백 노인 대사 (T6 부터는 편지)."""
        self.exam_run = None
        self.exam_fish = None
        if not res:
            return
        from src.scene.exam_scene import ExamResultScene
        self.game.scenes.push(ExamResultScene(self.game, self, res))   # 닫히면 가이드 'exam_end' (TG-24)

    # ───────────────────────── 그리기 ─────────────────────────
    WATER_MARGIN = 6   # 물결 마루가 수평선 위로 올라올 수 있는 최대 픽셀 (진폭 2 × 폭풍 1.9 × 바다 1.3)

    def _bg_band(self, canvas, pal, name: str, key, paint):
        """배경 띠 캐시 (OPTIMIZATION.md O3): 팔레트 · 시점이 같으면 1/bg_fps 초마다만 다시 그리고 그 사이엔 붙여 쓴다.
        도트 게임의 배경 애니메이션은 원래 12~15fps 라 티가 안 나고, 폰에서 물결 · 반사광 · 별 계산이 프레임마다 수 ms 였다.
        key 가 바뀌면(둘러보기 · 번개 · 전설 색 · 환상 팔레트) 바로 다시 그린다. bg_fps 0 = 매 프레임 (예전과 픽셀 동일)."""
        slots = self.__dict__.setdefault("_bands", {})
        skey = (name, canvas.get_flags() & pygame.SRCALPHA, canvas.get_size())
        slot = slots.get(skey)
        fps = self.settings.get("bg_fps") or 0
        if slot is None:
            if len(slots) > 6:
                slots.clear()
            slot = slots[skey] = {"surf": pygame.Surface(canvas.get_size(), canvas.get_flags() & pygame.SRCALPHA, canvas),
                                  "key": None, "t": -1.0}
        if slot["key"] != key or fps <= 0 or self.t - slot["t"] >= 1.0 / fps or self.t < slot["t"]:
            paint(slot["surf"])
            slot["key"], slot["t"] = key, self.t
        return slot["surf"]

    @staticmethod
    def _pal_key(pal: dict) -> tuple:
        # 색(정수 튜플)만 — 별 · 반사 세기 같은 실수값은 시각과 함께 매 프레임 조금씩 변해 열쇠로 쓰면 캐시가 전혀 안 맞는다 (갱신 때 반영됨)
        return tuple(sorted((k, v) for k, v in pal.items() if isinstance(v, tuple)))

    def scene_palette(self) -> dict:
        """지금 시각 · 낚시터 · 날씨 · 계절 · 이벤트를 입힌 팔레트 (모닥불 야영지 배경도 같이 씀)."""
        pal = themed_palette(self.palette.sample(self.clock.hour), self.theme, self.weather, self.lightning.flash,
                             *self._legend_tint())
        from src.render.season_fx import season_palette
        pal = season_palette(pal, self.season, self.spot.get("continent", "sharmion"))   # 계절 색감 (은은하게)
        from src.render.event_fx import event_palette
        pal = event_palette(pal, self._event_id(), self.spot.get("continent", "sharmion"))   # 붉은 달·은빛 안개 (환상 팔레트가 위)
        pal = self._line_pal(pal)
        if self.dragon_k > 0.01:
            from src.render.boss_arena import WORLD_KEYS   # 용의 붉은 하늘 · 물 (낚싯대 · 손은 원래 색, 51-2)
            for key in WORLD_KEYS:
                v = pal.get(key)
                if isinstance(v, tuple):
                    pal[key] = lerp_color(v, (120, 16, 26), 0.28 * self.dragon_k)
        return pal

    def _legend_tint(self) -> tuple:
        """전설 등장 황혼: 그 보스의 무대 색 (어둡게). 파이팅 무대가 물들기 시작하면 무대 색이 넘겨받음."""
        k = self.legend_k
        if k <= 0.001:
            return 0.0, (70, 36, 96)
        from src.render import boss_arena
        f = self.fight
        e = boss_arena.entry(f.fish if f is not None else self.bite.fish)
        col = lerp_color(boss_arena.color_of(e), (20, 14, 30), 0.45) if e else (70, 36, 96)
        if self.arena.active:
            k *= 1.0 - self.arena.entrance_k()
        return k, col

    def _draw_world(self, canvas, pal: dict) -> None:
        """하늘·별·해달·구름·산·물 (환상 파장은 이걸 두 번 그려 마스크로 합성).
        하늘~구름 과 물은 띠 캐시(_bg_band, 15fps); 이벤트 하늘(유성) · 번개 · 산 · 배 등불은 매 프레임."""
        cam, t, hour, theme, weather = self.cam, self.t, self.clock.hour, self.theme, self.weather
        W, H, hz = cam.width, cam.height, cam.horizon
        pk = self._pal_key(pal)
        eid = self._event_id()
        sky_vis = weather == "clear" and theme["terrain"] != "cave" and eid != "red_moon"   # 붉은 달 이벤트: 달은 붉은 달 하나만

        def paint_sky(s):
            world.draw_sky(s, pal, cam)
            self.stars.draw(s, pal, cam, t)
            world.draw_celestial(s, pal, cam, hour, t, visible=sky_vis)
            if theme.get("aurora"):
                from src.render.eldra_world import draw_aurora
                draw_aurora(s, pal, cam, t)
            self.clouds.draw(s, pal, cam)
        sky = self._bg_band(canvas, pal, "sky", (pk, round(cam.yaw, 5), sky_vis, bool(theme.get("aurora"))), paint_sky)
        canvas.blit(sky, (0, 0), (0, 0, W, hz))
        if theme["terrain"] != "cave":   # 날씨 이벤트 하늘 (유성·쌍무지개·붉은 달) — 산보다 먼저
            self.event_fx.draw_sky(canvas, eid, self.spot.get("continent", "sharmion"), cam.horizon,
                                   self.fight is not None)
        self.lightning.draw(canvas)
        world.draw_mountains(canvas, pal, cam, theme["terrain"], t)
        amp = {"clear": 1.0, "rain": 1.25, "storm": 1.9, "fog": 0.8}[weather] * (1.3 if theme.get("sea") else 1.0)
        amp *= 1.0 - 0.8 * self.phantom_fx.calm()  # 환상: 물결이 숨을 죽인다
        amp *= self.arena.wave_mult()               # 보스전 무대: 강도별 물결 (51-2)
        refl = weather == "clear" and theme["terrain"] != "cave"
        top = max(0, hz - self.WATER_MARGIN)

        def paint_water(s):
            s.blit(canvas, (0, top), (0, top, W, hz - top))   # 수평선 바로 위 몇 줄 (산): 마루가 올라와도 밑그림이 맞게
            self.water.draw(s, pal, t, hour, amp_mult=amp, show_reflection=refl)
        water = self._bg_band(canvas, pal, "water", (pk, round(cam.yaw, 5), round(amp, 5), refl), paint_water)
        canvas.blit(water, (0, top), (0, top, W, H - top))
        if theme.get("lamp"):
            world.draw_ship_lamp(canvas, pal, cam)

    def draw(self, canvas: pygame.Surface) -> None:
        if self.backdrop is not None:
            self.backdrop(canvas)   # 마을에 있는 동안: 상점·도감 같은 겹친 화면 뒤로 마을이 보이게
            return
        self._run_rt_fx()   # 슬로우모션 중엔 update 가 드물게 불리므로 그리기에서도 (타격 시점 정확히)
        self._tick_cine()
        hour = self.clock.hour
        from src.render import date_events
        world.SKY.clear()
        world.SKY.update(date_events.sky_tweak(hour))   # 새해 아침 해돋이 · 추석 보름달 (DT11)
        theme, weather = self.theme, self.weather
        self._arena_tick()
        pal = self.arena.palette(self.scene_palette())   # 보스전 무대 색: 하늘 · 물 · 먼 배경 키에만 (51-2)
        cam, c, t, f = self.cam, self.cast, self.t, self.fight
        pfx = self.phantom_fx
        base_pal = pal
        if pfx.active:
            pal = phantom_palette(base_pal, pfx.k)   # 환상 팔레트 덧입히기 (UI·HUD·신호 슬롯 제외)
        self._draw_world(canvas, pal)
        if self.season == "winter" and self.spot.get("continent", "sharmion") == "sharmion" and not theme.get("sea") \
                and theme["terrain"] != "cave":
            from src.render.season_fx import draw_ice_edges
            draw_ice_edges(canvas, pal, cam.horizon, t)   # 겨울: 수면 가장자리 살얼음
        self.screen_weather.draw_water(canvas)   # 구름 그림자 · 윤슬 (DT2)
        self.map_fx.draw_world(canvas, pal)      # 화산 아지랑이 · 계곡 물안개 (DT3)
        if pfx.active:
            m = pfx.mask(canvas.get_width(), canvas.get_height(), int(cam.horizon))
            if m is not None:
                # 파장이 지나간 자리만 환상 팔레트로 한 번 더 그려 합성 (지나간 자리는 0.3초에 걸쳐 보라로)
                layer = getattr(self, "_bloom_layer", None)   # 재사용 (O4)
                if layer is None or layer.get_size() != canvas.get_size():
                    layer = self._bloom_layer = pygame.Surface(canvas.get_size(), pygame.SRCALPHA)
                layer.fill((0, 0, 0, 0))
                self._draw_world(layer, phantom_palette(base_pal, pfx.inner_k()))
                layer.blit(m, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
                canvas.blit(layer, (0, 0))
            pfx.draw_ring(canvas, int(cam.horizon))
        if self.p2_aura > 0.005:
            # 환상 2페이즈: 뒷배경 보랏빛 오라 (하늘 · 먼 산 · 수평선 — 물고기 · 찌 · 줄 · 손 · 신호 · HUD 뒤)
            from src.core import fxq
            from src.render.phantom_phase2 import draw_aura
            holes = getattr(self.screen_weather.protect, "rects", None) or []
            draw_aura(canvas, int(cam.horizon), t, self.p2_aura, fxq.level(), holes)
        if self.catch_show is not None:
            self.catch_show.draw(canvas, pal)  # 환상어 포획 연출 (카드까지)
            if self.catch_show.waiting():
                from src.tutorial import targets as T   # TG-PH: 포획 카드
                W, H = canvas.get_size()
                T.mark("catch.card", (W // 2 - 170, 12, 340, H - 40))
            return
        if self.landing is not None:
            self.landing.draw(canvas, pal)
            self.screen_weather.draw_screen(canvas)   # 뜰채 물방울 · 날씨 (DT3)
            return
        if self.board is not None:
            self.board.draw(canvas, pal)              # 계측판 (DT7)
            self.screen_weather.draw_screen(canvas)
            return
        if self.release_scene is not None:
            self.release_scene.draw(canvas, pal)      # 놓아주기 1초 (DT7)
            return
        if f is None:
            sh = self.bite.shadow if weather != "fog" else None  # 안개: 다가오는 그림자가 안 보인다
            if sh is not None and self.bite.fish is not None:
                sh = dict(sh, glow=GLOW.get(self.bite.fish["rarity"]))
            draw_fish_shadow(canvas, pal, cam, sh, t)
            for gx, gz, gt in self.glints:
                # 먼 수면 보라빛 물결 한 번: 납작한 고리가 퍼지며 사라짐
                p = cam.project(gx, gz)
                if p:
                    k = gt / 1.6
                    rw, rh = 4 + 26 * k * p[2] / 10, 1 + 5 * k * p[2] / 10
                    col = lerp_color(pal["water_top"], (215, 170, 255), (1 - k) * 0.9)
                    pygame.draw.ellipse(canvas, col, (p[0] - rw, p[1] - rh, rw * 2, rh * 2), 1)
            if sh is not None and self.bite.fish is not None and self.save.charm_on("abyss_eye"):
                # 심연의 눈: 도감에 등록된 물고기면 이름이 보인다
                p = cam.project(sh["x"], sh["z"])
                if p and sh.get("alpha", 1) > 0.2:
                    fish = self.bite.fish
                    known = self.save.caught(fish["id"]) if not phantom.is_phantom(fish) else phantom.caught(self.save, fish["id"])
                    name = fish["name"] if known else "???"
                    hud.text(canvas, name, (p[0], p[1] - 10), (190, 170, 255), anchor="center")
        elif f.phase == "fight" and self.breach is not None and self.breach.t < self.breach.impact_at:
            pass   # 전설 도약 중: 물고기는 하늘에 (그림자 없음)
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
                if f.gap_t > 0:
                    fight_hud.draw_sweat(canvas, cam.project(sh["x"], sh["z"], -0.2), t)   # 틈: 땀방울 2개 (CU4-3)
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
        self.ilseom_fx.draw(canvas, "world")
        self._draw_birds(canvas)
        self._draw_school(canvas)
        self.bubbles.draw(canvas, pal)
        self.hazard_decor.draw(canvas, pal, cam, t, f.in_hazard if f is not None and f.phase == "fight" else None)
        self.ambient.draw(canvas, pal, self.clock.period()[0], weather, theme.get("sea", False), t)
        self.map_fx.apply_tilt(canvas, pal)   # 먼바다: 수평선 ±2도 (줄 · 찌 · 배 · 낚싯대는 기울지 않음)
        self.hook_cine.draw_pre(canvas, cam, pal)  # ① 입질 예고 (찌 · 줄보다 먼저 → 찌를 가리지 않음)
        self.legend_fx.draw_world(canvas, pal)      # ② 전설: 거대한 그림자 · 빨려 드는 물결 (찌보다 먼저)
        self.phantom_hfx.draw_world(canvas, pal)    # ② 환상: 보라 터짐 · 깊은 등불 · 달 조각
        self.life.draw_world(canvas, pal, t)        # 먼 낚시꾼 · 배 · 물새 · 먼 점프 (DT8)

        geo = self._rod_geo()
        tip = geo["tip"]
        if self.breach is not None:
            self.breach.draw_world(canvas, tip)   # 전설 도약: 수면 솟음 · 물기둥 · 하늘로 팽팽한 줄 · 전설 · 물방울 · 금빛 고리

        if c.state == CastState.CHARGING:
            ang = c.aim_angle(cam.yaw)
            d = c.distance_for_power(c.power)
            landing_marker(canvas, pal, cam, math.sin(ang) * d, math.cos(ang) * d, t)

        hanging = c.state in (CastState.READY, CastState.CHARGING, CastState.SWING)
        p2_cam = self.p2 is not None and self.p2.blocking and f is not None
        if f is not None and f.phase in ("fight", "net") and not p2_cam and self.breach is None:
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
            rk = self.legend_fx.reeds_k   # 실바: 갈대가 일제히 찌 쪽으로 고개를 숙임
            vk = self.phantom_hfx.reeds_k   # 보랏빛 갈대잉어: 갈대가 보랏빛으로 일렁임
            if vk > 0:
                rpal = dict(rpal, reed=lerp_color(rpal["reed"], (180, 140, 240), 0.8 * vk))
                rk = max(rk, 0.25 * vk)
            self.reeds.draw(canvas, rpal, t, wind=self.wind.reed_mult(weather) + 6.0 * rk, lean=1 if rk > 0 else self.wind.dir)
        else:
            world.FOREGROUND[fg](canvas, pal, t)
        self.map_fx.draw_fg(canvas, pal)   # 물보라 · 반짝임 · 재 · 빛 입자 · 구름 조각 · 반딧불 (DT3)
        if self.training is None:
            from src.render import grandpa_marks
            grandpa_marks.draw(canvas, self.spot_id, pal)   # 할아버지의 흔적 'ㅎ' (DT11)
            from src.render import bottle_seat
            bottle_seat.draw(canvas, self.save, self.spot_id, pal)   # 유리병 12장 → 해강의 자리 (CU13)
        from src.render.rod import gear_look
        from src.save.quests import skin_colors
        rod_l = gear_look("rod", self.save.gear_tier("rod"))       # 티어별 외형 (gear_looks.json)
        reel_l = gear_look("reel", self.save.gear_tier("reel"))
        skin = skin_colors(self.save, "rod_skin")
        if skin:  # 의뢰 상점 낚싯대 외형이 색은 우선
            rod_l = dict(rod_l, rod=skin[0], hi=skin[1])
            reel_l = dict(reel_l, body=skin[2])
        self._draw_trail(canvas, "rod_skin", geo["tip"], 2)
        if not p2_cam:   # 2페이즈 컷신: 낚싯대 · 손 · 줄은 컷신이 카메라에 맞춰 그림
            draw_rod(canvas, pal, geo, c.reel_angle, rod_l, reel_l, t, hand_look=self._hand_look())
        self.life.draw_fly(canvas, geo["tip"], t)   # 낚싯대 끝 잠자리 (DT8)
        if f is not None and f.phase == "fight" and f.align < -0.3 and not p2_cam:
            fight_hud.draw_side_wake(canvas, geo["tip"], -f.fish_side(), t)   # 측면 압박: 낚싯대 끝 흰 물살 (CU4-4)
        if self.bait_anim is not None and hanging:
            self._draw_bait_anim(canvas, pal, tip)

        if hanging:
            bx, by = rod_tip_drop(tip, t)
            draw_line(canvas, pal, tip, (bx, by - 3), 0)
            draw_bobber(canvas, pal, bx, by, 7, floating=False)
        self.droplets.draw(canvas, pal)
        self.rain.draw(canvas, pal)
        self.fog.draw(canvas, pal, cam.horizon, t)
        self.season_fx.draw(canvas)   # 계절 파티클 (파이팅 중엔 위쪽에 1/3만)
        self.event_fx.draw_low(canvas, self._event_id(), self.spot.get("continent", "sharmion"), cam.horizon,
                               f is not None and f.phase == "fight")
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
        self.ilseom_fx.draw(canvas, "screen")
        self.screen_weather.draw_screen(canvas)   # 화면에 맺히는 날씨 (빗방울 · 김 서림 · 성에 · 날림 · 입김 · 빛 번짐, DT2)
        self.map_fx.draw_screen(canvas)           # 계곡: 위에서 떨어지는 물방울 (DT3)
        self.legend_fx.draw_screen(canvas, pal)   # ② 전설 고유 연출 (DT5)
        self.phantom_hfx.draw_screen(canvas, pal)  # ② 환상 고유 연출 (DT6)
        if self.breach is not None:
            self.breach.compose(canvas)   # 전설 도약: 1.7배 확대가 전설을 따라감 · 착수 흔들림 · 노란 번쩍 (카드 · HUD 는 이 뒤 — 확대 안 함)
        if self.p3 is not None:
            self.p3.compose(canvas)       # 전설 3페이즈: 눈빛 대치 · 각자의 필살 (HUD · 체력 바는 이 뒤)
            dx, dy = self.p3.shake()
            if dx or dy:
                canvas.scroll(dx, dy)
        if p2_cam:
            # 2페이즈 컷신: 카메라(고개 숙임 · 수면 · 물속 · 솟구침) · 폭발 · 흔들림 — HUD 는 이 뒤에 (흔들지 않음)
            self._p2_pal = pal
            self.p2.compose(canvas, self._fish_screen(), int(cam.horizon), self._p2_draw_rod)
        if getattr(self, "scenic", False):
            return   # 이동 컷신의 도착 전경: 풍경·낚싯대까지만 (HUD·카드 없음)
        self._draw_event_banner(canvas)
        if f is None or f.phase not in ("fight", "net"):
            self.arena.draw_bars(canvas)   # 시네마 띠가 빠지는 중 (파이팅 중엔 _draw_fight_overlay 에서 비네트 뒤 · HUD 아래)

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
            cr = hud.draw_clock(canvas, pal, label, self.clock.fast, self.clock.fast_mult, 6 + inset)
            self._draw_tide(canvas, cr, t)
            bless = phantom.blessing_active(self.save)
            if bless:
                hud.draw_blessing(canvas, 12 + inset, 32, phantom.blessing_left(self.save), t)
            self._draw_progress(canvas, 6 + inset, 44 if bless else (29 if warn else 17))
            if c.state == CastState.CHARGING:
                hud.draw_power_gauge(canvas, pal, c.power, c.distance_for_power(c.power))
            if c.state == CastState.LANDED:
                hud.text(canvas, f"찌 거리 {c.current_distance():.0f}m", (cam.width - 6 - inset, 30), pal["text"],
                         anchor="topright")
            sv = self.save.data
            hud.text(canvas, f"{ui_w.money_anim(sv['money']):,}원", (cam.width - 6 - inset, 4), (255, 228, 140), anchor="topright")
            from src.fishing import live_bait
            bait = live_bait.label(self.save) or self.save.equipped("bait")["name"]   # 생미끼: "피라미 ×2"
            hud.text(canvas, f"살림망 {len(sv['keepnet'])} · 미끼 {bait}", (cam.width - 6 - inset, 17), pal["text"],
                     anchor="topright")
            hint = HINTS[c.state]
            if hint:
                hud.draw_hint(canvas, pal, hint, center=self.touch)
            side = self._side_menu_on()
            hud.draw_look_arrows(canvas, pal, self.look_left, self.look_right, t, right_inset=30 if side else 0)
            if side:
                from src.ui import side_menu
                chests = sum(self.save.data.get("chests", {}).values())
                side_menu.draw(canvas, self._side_menu_rects(), self.mouse, t, {"chest": chests}, drawer=self.collect_k)
            from src.ui import achv_toast
            achv_toast.draw(self.game, canvas)
        self.toasts.draw(canvas)
        if self.campfire_line is not None:
            line, end = self.campfire_line
            if self.t >= end:
                self.campfire_line = None
            elif end - self.t > 0.4 or int(self.t * 20) % 2 == 0:
                hud.text(canvas, line, (self.cam.width // 2, self.cam.height - 34), (255, 222, 170), anchor="center")
        la = self.phantom_fx.line_alpha()
        if la > 0:
            # 환상 등장 대사 (위쪽 가운데, 연보라 페이드)
            img = get_font(16).render(phantom.LINE, False, phantom.COLOR_LIGHT)
            sh = get_font(16).render(phantom.LINE, False, (30, 10, 50))
            img.set_alpha(int(255 * la))
            sh.set_alpha(int(200 * la))
            x = self.cam.cx - img.get_width() // 2
            canvas.blit(sh, (x + 1, 47))
            canvas.blit(img, (x, 46))
        if self.show_pity:
            ph = phantom.state(self.save)
            lines = [f"[환상 천장] {sid} {n}회 · {phantom.chance(self.save, sid) * 100:.2f}%"
                     for sid, n in sorted(ph["casts"].items())] or ["[환상 천장] 기록 없음"]
            fight_hud.draw_debug_lines(canvas, lines)
        if self.captions:
            cap, left = self.captions
            w = get_font(11).size(cap)[0] + 12
            r = pygame.Rect(self.cam.cx - w // 2, 72, w, 14)
            canvas.fill((10, 14, 28), r)
            pygame.draw.rect(canvas, (150, 200, 255), r, 1)
            hud.text(canvas, cap, r.center, (200, 230, 255), anchor="center")
        if self.debug and f is None and c.state == CastState.LANDED:
            fight_hud.draw_debug_lines(canvas, ["루어 (대기 중)"] + self.ctl.debug_lines(self.t)[2:])
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
        if self.p2 is not None and self.p2.blocking and f is not None:
            # 2페이즈 컷신: 물속 장면 · 도약 · 체력 게이지 (맨 앞 — 터치 조작도 덮음, 화면 어디를 눌러도 건너뛰기)
            self.p2.draw_top(canvas)
        self._mark_targets(canvas)
        hud.draw_cursor(canvas, self.mouse)

    def _rod_geo(self) -> dict:
        c, f = self.cast, self.fight
        if f is None or f.phase in ("caught", "lost"):
            return rod_geometry(c.aim, c.swing_deg + c.jerk_offset(), c.bend + self.bite.tip_pull + self.hook_cine.bend_extra(),
                                c.rod_hand_offset())
        # 파이팅: 장력만큼 휘고, 끝이 물고기 쪽으로 끌려감. 우클릭이면 숙임.
        tension = f.tension
        dip = math.sin(math.pi * (f.dip_t / 0.35)) if f.dip_t > 0 else 0.0
        ac = self.core_arm
        wk = 0.8 + 0.15 * f.weight   # 무게 단서 (CU5-2): 큰 물고기일수록 크게 휨
        bend = 5 + tension * 0.24 * wk + (math.sin(self.t * 31) * tension / 40 if tension > 60 else 0)
        if self.breach is not None:
            bend = max(bend, self.breach.rod_bend())   # 전설 도약: 줄이 하늘로 팽팽 → 최대 휨
        if f.hook_kick_t > 0:   # 큰 물고기 챔질 순간 '훅' 한 번 크게 꺾임 (0.2초)
            bend += 16 * math.sin(math.pi * (1 - f.hook_kick_t / ac["hook_kick_sec"]))
        pull_x = f.fish_side() * tension * 0.25
        swing = 10 - 24 * dip
        hand = [0.0, 2 * dip]
        if f.phase == "fight":
            swing += self.ctl.pitch * self.ctl.cfg["rod_pitch_deg"]  # 낚싯대 상하 (+ = 끝이 위로)
            amp = 0.0
            if f.arm_out_t > 0:
                amp = ac["shake_px"]                                         # 팔 힘 바닥: 부들부들 2px
            elif f.reeling and f.weight > ac["light_below"]:
                amp = ac["shake_px"] * min(1.0, f.weight / ac["weight_max"]) * (1.0 if f.arm_wrong else 0.5)
            if amp > 0 and not self.settings.get("reduce_fx"):              # 화면 효과 줄이기: 떨림 끔
                hand[0] += math.sin(self.t * 47) * amp
                hand[1] += math.sin(self.t * 39 + 1.3) * amp * 0.6
        return rod_geometry(c.aim, swing + c.jerk_offset(), bend, tuple(hand), pull_x=pull_x)

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
        if f.stagger_t > 0:   # 퍼펙트 뒤 휘청 (CU4-2): 그림자가 비틀거림
            heading += math.sin(self.t * 9.0) * 0.35 * min(1.0, f.stagger_t / 0.4)
        if f.gap_t > 0:       # 틈 (CU4-3): 헐떡이며 느려짐
            wag *= f.atk["gap"]["shadow_speed"]
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
                "scale": scale, "wag": wag, "glow": glow, "spray": bool(f.fish.get("excited")), **mods}

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
        from src.save.quests import skin_colors
        ns = skin_colors(self.save, "net_skin")
        if ns:  # 환상 뜰채 외형 (33장 P5): 테·그물 색
            out["net_frame"], out["net_mesh"] = ns[0], ns[1]
            out["net_trim"] = ns[1]
        return out

    def _rush_audio(self) -> None:
        """돌진 소리: 예고(줄 펄스)마다 '힘 모으는 소리'(sfx_rush_charge — 낮은 울림·바람이 커지며 올라감), 돌진 silence_sec 전에 끊김
        → 돌진 순간 zing_rise ('action:rush', 오디오 최종 팩) → 돌진이 끝나면 reel_stop.
        신호음 '강조' 모드만 예전 울림 음(legacy_rush_hum)도 같이. 진동은 약하게 시작해 점점 세게."""
        reel = self.fight_audio.reel
        reel.tease = 0.0
        f = self.fight
        if reel.rushing and (f is None or f.phase != "fight" or f.brain.state != "rush"):
            reel.rush_end()   # 돌진 끝 = reel_stop
        ph = self._rush_ph(visual=False)
        from src.ui import rush_cue
        c = rush_cue.cfg()
        ch = getattr(self, "rush_charge_ch", None)
        if ph is None or ph["stage"] != "pulse" or ph["left"] <= c["silence_sec"]:
            if ch is not None:   # 돌진 직전 무음 (또는 예고가 끝남)
                ch.fadeout(60)
                self.rush_charge_ch = None
            if ph is None or ph["stage"] != "pulse":
                self.rush_charge_idx = -1
            return
        boss = self.signal_audio.boss(f)
        if ph["idx"] != getattr(self, "rush_charge_idx", -1):   # 펄스마다 (대형은 2번)
            self.rush_charge_idx = ph["idx"]
            if ch is not None:
                ch.fadeout(40)
            if boss:   # 보스전: '힘 모으는 소리' 대신 보스 빌드업 '두-둥' (아래 단계마다)
                self.rush_charge_ch = None
            elif self.settings.get("signal_sound"):   # 펄스 길이에 맞는 것 (짧으면 0.55초에 다 올라가는 버전)
                pulse_left = ph["left"] / max(1, ph["n"] - ph["idx"])
                self.rush_charge_ch = self.sfx.play("sfx_rush_charge" if pulse_left >= 0.8 else "sfx_rush_charge_short", 0.85)
            else:
                self.rush_charge_ch = None
        steps = 8
        i = min(steps - 1, int(ph["q"] * steps))
        if i > getattr(self, "rush_hum_i", -1):
            self.rush_hum_i = i
            if boss:
                self.signal_audio._bplay(f"sig_boss_release_hum#{i}", 0.8 + 0.2 * ph["q"])
            elif self.settings.get("signal_sound") and self.settings.get("signal_mode") == 2:
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
        sy += self.map_fx.tilt_dy(sx)
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
        if not f.reeling:   # 감지 않을 때 느슨한 처짐은 최대 8px (DETAILS C)
            sag = min(sag, load_json("details/hands_catch.json")["line_slack"]["max_px"])
        if (d := self._pat_k(b, "reverse")) is not None and not b.doing("reverse"):
            sag += 10 * d  # 역주행 예고: 줄이 처진다
        from src.ui import rush_cue
        rph = self._rush_ph()
        lph = rush_cue.light_phase(f) if self._rush_ph_ok() else None  # 점프·방향 전환: 가벼운 줄 펄스
        sag = max(0.5, sag + rush_cue.line_sag(rph) + rush_cue.light_sag(lph))  # 웅크림: 느슨 / 돌진 순간: 팽팽
        dx += self._wind_bend()   # 바람 쪽으로 휨 (A-2)
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

    # ───────────────────────── 보스전 무대 (BOSS_ARENA.md, DESIGN 51-2) ─────────────────────────
    def _arena_target(self, f) -> int:
        from src.render.boss_arena import cfg as arena_cfg
        c = arena_cfg()
        if f.fish.get("rarity") == "phantom":
            return c["phase_levels"]["phantom"][1 if getattr(self, "p2_on", False) else 0]
        phases = f.brain.phases or []
        if len(phases) <= 1:
            fr = f.stamina_frac
            return 3 if fr <= c["hp_levels"]["3"] else 2 if fr <= c["hp_levels"]["2"] else 1
        lv = c["phase_levels"]["legend"]
        return lv[min(len(lv) - 1, max(0, f.brain.phase))]

    def _arena_tick(self) -> None:
        """그리기마다 실제 시간으로 (슬로우모션 · 히트스톱과 무관하게 등장 · 강도 전환이 흐름)."""
        ar, f = self.arena, self.fight
        now = time.perf_counter()
        dt = min(0.1, max(0.0, now - getattr(self, "_arena_rt", now)))
        self._arena_rt = now
        suno = self.game.boss.suno
        beats = list(getattr(suno, "beat_events", ()))
        if beats:
            suno.beat_events.clear()
        if ar.active and (f is None or f.phase not in ("fight", "net")):
            ar.finish()
        if ar.active:
            fighting = f is not None and f.phase == "fight"
            ar.update(dt, {"target": self._arena_target(f) if f is not None else 0, "crisis": self.crisis_now,
                           "telegraph": fighting and f.brain.state == "telegraph",
                           "reduce": bool(self.settings.get("reduce_fx")), "shake_on": self.shake_on,
                           "horizon": self.cam.horizon, "beats": beats if fighting else (),
                           "beats_live": suno.active and suno.seg is not None})
        self.screen_fx.extra_vignettes = ar.vignettes()
        fight_hud.TOP_PAD = ar.bar_px()

    def _arena_holes(self) -> list:
        """무대 효과가 건드리지 않는 칸: 신호 보호 영역 + 물고기에 붙은 신호 자리 + 게이지 묶음."""
        holes = list(self.screen_weather.protect.rects)
        f = self.fight
        W, H = self.cam.width, self.cam.height
        if f is not None and f.phase == "fight":
            ax, ay = self.screen_fx.map(self._fish_screen())
            x, y = int(clamp(ax, 70, W - 70)), int(clamp(ay - 30, 62, H - 74))
            holes.append(pygame.Rect(x - 62, y - 42, 124, 84))
            holes.append(pygame.Rect(int(ax) - 30, int(ay) - 20, 60, 38))
            gw = self.GAUGE_W if f.gim.kinds(f.brain) else 80
            ox = self.game.screen.safe_x
            if self.touch and self.settings.get("touch_left"):
                ox = W - gw - ox
            holes.append(pygame.Rect(ox, 30, gw, 184))
        return holes

    def _boss_bar(self, canvas, pal, f) -> None:
        if self.arena.card_on:
            self.arena.draw_card(canvas)   # 이름 카드 → 위로 올라가 체력 바가 됨
        else:
            fight_hud.draw_boss_bar(canvas, pal, f)

    def _boss_accent(self) -> None:
        """보스별 악센트 (BOSS_ARENA 🅱-3): 행동 순간('쾅' · '챙')에만 테마 소리 한 겹 0.35 — 기존 소리 재사용 우선."""
        from src.render.boss_arena import cfg as arena_cfg
        e = self.arena.e if self.arena.active else None
        key = e.get("accent") if e else None
        if not key or not self.settings.get("signal_sound"):
            return
        snd = arena_cfg()["sound"]
        name = snd["accents"].get(key)
        if not name:
            return
        vol = snd["accent_vol"]
        self.signal_audio.log.append((round(self.signal_audio.clock, 4), "accent:" + key))
        if name.startswith("theme:"):
            _, theme, short = name.split(":")
            theme_sfx.play(self.sfx, theme, short, vol)
        else:
            self.sfx.play(name, vol)

    def _arena_event(self, ev: str) -> None:
        """큰 행동 순간 임팩트 (🅰-4): 히트스톱 · 흔들림 · 충격파 · (강도 3) 색 갈라짐 · (착수 · 페이즈) 번쩍임."""
        from src.render.boss_arena import cfg as arena_cfg
        f = self.fight
        kind = "phase" if ev.startswith("phase:") else ev
        if kind not in arena_cfg()["impact"]["events"] or f is None:
            return
        if kind == "phase" and f.fish.get("rarity") == "phantom":
            return   # 환상 2페이즈는 전용 컷신
        pos = self.screen_fx.map(self._fish_screen())
        d = 1.0 if pos[0] >= self.cam.width / 2 else -1.0
        res = self.arena.impact(kind, pos, d)
        self.signal_audio.log.append((round(self.signal_audio.clock, 4), "impact:" + kind))
        if res["hitstop"] > 0:
            self.game.hitstop(res["hitstop"])

    def _draw_fight_overlay(self, canvas, pal) -> None:
        f, t = self.fight, self.t
        if f.phase != "fight":
            self.screen_fx.draw_edges(canvas)  # 섬광이 남아 있으면 마저 사라지게
        if f.phase == "net":
            pose, still = f.net_pose()
            draw_net_scene(canvas, pal, self._display_fish(f.fish), f.size_cm, pose, still, t, self.net_anim, self.mouse)
            self.arena.draw_bars(canvas)
            self._boss_bar(canvas, pal, f)
            self.popups.draw(canvas, self.screen_fx.map)  # 뜰채 중 한 단어 ("뜰채!")
            return
        qr = getattr(self, "quest_run", None)
        if f.phase == "caught":
            draw_catch_cut(canvas, pal, f.result, self.end_t)
            fight_hud.draw_catch_info(canvas, f.result, self.end_t, self.catch_news)
            self._draw_print_btn(canvas)
            self._draw_release_btn(canvas)
            if qr is not None and qr.items and self.end_t > 1.0:
                fight_hud.draw_quests(canvas, qr.hud_lines(), self.hud_inset if self.touch else 0)  # 의뢰 상세는 결과 화면에
            if self.end_t > 1.2:   # 왼쪽 위 기록 배지(최대 4줄) 아래 세로 — 가운데 글자를 가리지 않게
                signal_slots.draw_result_icons_column(canvas, self.missed_signals, self.mastery_ups,
                                                      (12 + (self.hud_inset if self.touch else 0),
                                                       max(96, 24 + len(fight_hud.catch_badges(self.catch_news)) * 15 + 12)),
                                                      self.t)
            self._draw_access_mark(canvas)
            return
        if f.phase == "lost":
            fight_hud.draw_lose_panel(canvas, f, LOSE_REASONS[f.lose_reason], self.end_t)
            if self.exam_run is not None and self.end_t > 0.6:
                hud.text(canvas, f"T{self.exam_run['tier']} 시험 불합격 — 게임 하루 뒤 다시", (canvas.get_width() // 2, 58),
                         BAD, 11, "center")
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
            self.arena.draw_fx(canvas, self._arena_holes())
            self.arena.draw_bars(canvas)
            fight_hud.draw_gauges(self._gauge_canvas(canvas), pal, f, t)
            return
        self._draw_behavior_ui(canvas)
        self.popups.draw(canvas, self.screen_fx.map)
        self.screen_fx.draw_edges(canvas)
        self.arena.draw_fx(canvas, self._arena_holes())   # 무대 파티클 · 충격파 · 박자 · 번쩍임 — 게이지 · 신호보다 먼저, 보호 칸 제외
        self.arena.draw_bars(canvas)                       # 시네마 띠 (HUD 는 그 위 · 안쪽)
        # HUD 우선순위 (31장 C6): 1 신호 칸 / 2 장력·내구도 / 3 드랙(필요할 때만 진하게) / 4 거리(작게) / 5 의뢰·소모품(반투명).
        # 신호가 막 뜨면 3 이하는 잠깐 더 흐려진다.
        if getattr(self, "gap_flash", 0.0) > 0:   # 틈 공략 성공: 흰 금색 번쩍 10% (BOSS_ARENA 받아침 테두리처럼 짧게)
            fight_hud.draw_gap_flash(canvas, self.gap_flash / 0.18)
        fight_hud.draw_gauges(self._gauge_canvas(canvas), pal, f, t)
        self._boss_bar(canvas, pal, f)
        dim = 1.0 - 0.55 * min(1.0, self.sig_dim_t / 0.3)
        qr = getattr(self, "quest_run", None)
        w = self.cam.width
        inset = self.hud_inset if self.touch else 0
        if qr is not None and qr.items:   # 칸 = 각 HUD 가 그리는 자리 + 여유 (fight_hud · icons 좌표)
            self._faded(canvas, 150 * dim, lambda c: fight_hud.draw_quest_icon(c, qr.hud_lines(), inset),
                        (w - inset - 32, 8, 32, 30))
        dist_area = (w - inset - 64, fight_hud.TOP_PAD, 64, 18)
        if self.touch:
            # 드랙·소모품·조작 안내는 터치 버튼이 대신한다
            self._faded(canvas, 200 * dim, lambda c: fight_hud.draw_distance(c, pal, f, self.hud_inset), dist_area)
        else:
            need = self._drag_needed(f)
            self._faded(canvas, 255 if need else 120 * dim, lambda c: fight_hud.draw_drag(c, pal, f, need, t),
                        (0, 212, 40 + 7 * f.drag_steps, 26))
            self._faded(canvas, 200 * dim, lambda c: fight_hud.draw_distance(c, pal, f), dist_area)
            self._faded(canvas, 150 * dim, lambda c: self._draw_fight_items(c, pal, f), (0, 228, 120, 28))
        if phantom.blessing_active(self.save):
            hud.draw_blessing(canvas, self.cam.width - 64 - (self.hud_inset if self.touch else 0), 12, None, t)  # 아이콘만
        if f.phase == "fight":
            self._draw_fish_cues(canvas)  # 물고기 자리 행동 UI — 가장 위 (가장 선명)
        if self.debug:
            pad_side = self.touch and not self.settings.get("touch_left")
            fight_hud.draw_debug(canvas, f, self.ctl.debug_lines(self.t), 100 if pad_side else 4)

    def _mark_targets(self, canvas) -> None:
        """튜토리얼 강조 대상 자리 (DESIGN.md 40-2)."""
        from src.tutorial import targets as T
        cam, c, f = self.cam, self.cast, self.fight
        W, H = canvas.get_size()
        hz = int(cam.horizon)
        mp = self.screen_fx.map
        if f is None:
            T.mark("fish.water", (0, hz, W, H - hz))
            T.mark("fish.clock", (6 + (self.hud_inset if self.touch else 0), 1, 150, 14))   # TG-24 불합격: 시계
            if self._exam_float_on() and c.state == CastState.READY:
                tx, ty = self._rod_geo()["tip"]
                T.mark("fish.exam_float", (int(tx) - 14, int(ty) - 6, 28, 30))   # TG-24: 끼워진 시험 찌
            if c.state not in (CastState.READY, CastState.CHARGING, CastState.SWING):
                p = cam.project(c.bx, c.bz, c.bh)
                if p:
                    x, y = mp((p[0], p[1]))
                    T.mark("fish.bobber", (x - 12, y - 14, 24, 24))
            if self._side_menu_on():
                from src.ui import side_menu
                rects = self._side_menu_rects()
                for k, r in rects:
                    T.mark("fish.menu." + k, r)
                if self.collect_k > 0.9:
                    for k, r in side_menu.drawer_layout(rects):
                        T.mark("fish.menu." + k, r)
            if self.touch:
                for ct in getattr(self.game.input, "controls", []):
                    if ct.id == "bag":
                        T.mark("fish.bag", ct.rect)
                    elif ct.id == "pad":
                        T.mark("fight.pad", ct.rect)
            else:
                hx, hy = self._rod_geo()["hand"]
                T.mark("fight.reel", (hx - 26, hy - 22, 52, 44))
            sh = self.bite.shadow
            if sh is not None and sh.get("alpha", 1) > 0.15:
                p = cam.project(sh["x"], sh["z"])
                if p:
                    x, y = mp((p[0], p[1]))
                    T.mark("fish.shadow", (x - 26, y - 12, 52, 24))
            sg = self.signs.sign
            if sg is not None:
                p = cam.project(sg["x"], sg["z"])
                if p:
                    x, y = mp((p[0], p[1]))
                    rw = max(30, int(self.signs.radius * p[2]))
                    T.mark("fish.signs", (x - rw, y - 30, rw * 2, 44))
            if self.event_banner is not None:
                T.mark("village.sky", (0, 0, W, max(20, hz - 2)))
                T.mark("village.banner", (0, 26, W, 34))
            if self.side_chest_rect() is not None:
                T.mark("chest.menu", self.side_chest_rect())
            return
        if self.touch:
            for ct in getattr(self.game.input, "controls", []):
                if ct.id == "pad":
                    T.mark("fight.pad", ct.rect)
        if f.phase == "fight":
            ox = self.game.screen.safe_x
            if self.touch and self.settings.get("touch_left"):
                ox = W - self.GAUGE_W - ox
            y, h = 44, 140
            T.mark("fight.gauge.tension", (ox + 4, y - 2, 20, h + 18))
            red_h = int(h - f.green_high / 100 * h)
            T.mark("fight.gauge.tension.red", (ox + 6, y, 16, max(4, red_h)))
            T.mark("fight.gauge.line", (ox + 32, y - 2, 13, h + 18))
            fx, fy = mp(self._fish_screen())
            T.mark("fight.fish", (fx - 22, fy - 16, 44, 30))
            T.mark("fight.slots", (fx - 34, fy - 52, 68, 40))
            T.mark("fight.slot.reel", (fx - 34, fy - 52, 68, 40))
            T.mark("fight.distance", (W - 60 - (self.hud_inset if self.touch else 0), 2 + fight_hud.TOP_PAD, 52, 14))
            # 엘드라시온 기믹 게이지 (fight_hud.draw_gauges 와 같은 자리)
            kinds = f.gim.kinds(f.brain)
            gx = 116 if f.hazards else 88
            for gk in ("tangle", "heat"):
                if gk in kinds:
                    T.mark(f"fight.gimmick.{gk}", (ox + gx - 6, y - 2, 17, h + 18))
                    gx += 28
            if "current" in kinds:
                T.mark("fight.gimmick.current", (ox + 100, y + h - 20, 56, 26))
            if "ice" in kinds:
                T.mark("fight.gimmick.ice", (ox + 4, y - 4, 20, h + 8))
            if "dark" in kinds:
                fx2, fy2 = mp(self._fish_screen())
                T.mark("fight.gimmick.dark", (fx2 - 50, fy2 - 40, 100, 70))
            if not self.touch:
                hx, hy = self._rod_geo()["hand"]
                T.mark("fight.reel", (hx - 26, hy - 22, 52, 44))
        elif f.phase == "net":
            T.mark("fight.net", (W // 2 - 70, H // 2 - 40, 140, 100))
            T.mark("fight.fish", (W // 2 - 50, H // 2 - 30, 100, 70))
        elif f.phase == "caught":
            T.mark("catch.card", (W // 2 - 110, 12, 220, 60))
            T.mark("catch.size", (W // 2 - 40, 36, 80, 16))
            T.mark("catch.rank", (W - 70 - 22, 54 - 22, 44, 50))
            if "signal_pts" in (f.result.get("score") or {}):   # TG-25 새 랭크 (49-6): 막대 4개 · 가장 모자란 막대
                bars = fight_hud.rank_bars_rect(W - 70, 54 + 36)
                T.mark("catch.rank_bars", bars.inflate(12, 6))
                ratios = fight_hud.rank_ratios(f.result)
                weak = min(fight_hud.BAR_KEYS, key=lambda k: ratios[k])
                if f.result["rank"] != "S" and ratios[weak] < 0.999:
                    i = fight_hud.BAR_KEYS.index(weak)
                    T.mark("catch.rank_bars.weak", (bars.x - 2, bars.y + i * 8 - 2, bars.w + 4, 9))
                else:
                    T.mark("catch.rank_bars.weak", bars.inflate(12, 6))
            from src.core.fonts import get_font
            for i, (label, _) in enumerate(fight_hud.catch_badges(self.catch_news)):
                r = (8, 24 + i * 15 - 8, get_font(11).size(label)[0] + 8, 16)
                if label.startswith("NEW!"):
                    T.mark("catch.dex_new", r)
                elif label.endswith(" 변이"):
                    T.mark("catch.mutation", r)
                elif "보물상자" in label:
                    T.mark("catch.chest", r)
            pr = self._print_btn()
            if pr is not None:
                T.mark("catch.print_btn", pr)

    def _equipped_float(self) -> dict | None:
        """엘드라시온에서 장착한 특수 찌 (샤르미온에선 효과도 외형도 없음)."""
        fid = self.save.data["float"].get("equipped")
        if not fid or self.spot.get("continent") != "eldrasion" or self._exam_float_on():
            return None   # 시험 찌가 끼워져 있으면 그 찌 대신 (49-3)
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
            from src.save.quests import equipped, shop_item
            it = shop_item(equipped(self.save)["float_skin"]) or {}
            if it.get("band"):   # 해강의 찌 (스토리 C4-05): 대나무색 띠 + 빨간 점
                out = dict(out, bobber_band=tuple(it["band"]), bobber_dot=tuple(it["dot"]), bobber_star=bool(it.get("star")))
        if self.save.cosmetic_on("sparkle_float"):
            glint = 0.5 + 0.5 * math.sin(self.t * 6)
            out = dict(out, bobber=lerp_color((255, 196, 60), (255, 250, 200), glint * 0.5))
        if (self.save.charm_on("pinwheel_float") and self.bite.state == BiteState.NIBBLE and self.bite.dip > 0.03):
            out = dict(out, bobber=(90, 220, 255))
        if self.training is None and self._exam_float_on():
            # 백 노인의 시험 찌 (49-3): 장착 중인 찌 대신 — 누런 오동나무색 + 갈색 띠 + 빨간 점
            out = dict(out, bobber=(232, 196, 120), bobber_base=(150, 104, 52), bobber_band=(110, 70, 36),
                       bobber_dot=(232, 74, 74), bobber_star=False)
        return out

    def _exam_float_on(self) -> bool:
        from src.save import exam
        return exam.active(self.save) is not None and exam.on_exam_spot(self.save, self.spot_id)

    def _draw_trail(self, canvas, kind: str, pos, width: int) -> None:
        """환상 외형 (33장 P5): 찌·낚싯대 끝이 지나간 자리에 보랏빛 잔상 (움직일 때만 보임)."""
        from src.save.quests import skin_trail
        col = skin_trail(self.save, kind)
        trails = self.__dict__.setdefault("trails", {})
        if col is None:
            trails.pop(kind, None)
            return
        pts = trails.setdefault(kind, [])
        pts.append((pos[0], pos[1], self.t))
        while pts and self.t - pts[0][2] > 0.35:
            pts.pop(0)
        for (x0, y0, t0), (x1, y1, _) in zip(pts, pts[1:]):
            if abs(x1 - x0) + abs(y1 - y0) < 0.6:
                continue
            a = 1 - (self.t - t0) / 0.35
            pygame.draw.line(canvas, lerp_color((40, 20, 70), col, a), (x0, y0), (x1, y1), max(1, int(width * a + 0.5)))

    def _fight_text_mode(self) -> bool:
        """파이팅(뜰채 포함) 중: 글자 예산 1개·6글자 (31장)."""
        return self.fight is not None and self.fight.phase in ("fight", "net")

    def _say(self, s: str, color) -> None:
        """파이팅 중 한 단어: 판정 글자와 같은 슬롯 하나 (새 글자가 이전 글자를 바로 지운다)."""
        self.popups.say(s, color, (self.cam.width // 2, 78), 1.2)

    GAUGE_W = 170  # 파이팅 게이지 묶음 폭 (fight_hud.draw_gauges 가 왼쪽 0~170px에 그림, 물살 표시 포함)

    _PARTICLE_LISTS = ("items", "drops", "dust", "sparks", "parts", "particles", "fireflies", "flakes", "ring_fish",
                       "shockwaves", "rays", "speed_lines", "slashes", "bolts", "petals", "leaves", "snow", "motes")

    def perf_particles(self) -> int:
        """지금 살아 있는 파티클 수 (성능 로그 · 표시, OPTIMIZATION.md O1): 효과 객체들의 목록 길이 합."""
        n = 0
        for name in ("ripples", "splashes", "bubbles", "sparkles", "rain", "season_fx", "event_fx", "screen_fx", "landing",
                     "catch_show", "phantom_fx", "lightning", "dragon_fx", "pattern_vfx", "rush_cue"):
            obj = getattr(self, name, None)
            if obj is None:
                continue
            for ln in self._PARTICLE_LISTS:
                v = getattr(obj, ln, None)
                if isinstance(v, list):
                    n += len(v)
        return n

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
                                "fight_cfg": f.cfg,
                                "judge_busy": any(it["t"] < 0.8 for it in self.popups.items)})

    def _layer(self, canvas, area=None) -> pygame.Surface:
        lay = getattr(self, "_fade_layer", None)
        if lay is None or lay.get_size() != canvas.get_size():
            lay = self._fade_layer = pygame.Surface(canvas.get_size(), pygame.SRCALPHA)
        lay.set_alpha(255)  # None 이면 픽셀 알파 섞기가 꺼져 투명 칸이 검게 덮인다
        lay.fill((0, 0, 0, 0), area)
        return lay

    def _faded(self, canvas, alpha: float, fn, area=None) -> None:
        """우선순위 낮은 HUD를 반투명으로 (31장 C6).
        area = 그 HUD 가 그려지는 칸 (x, y, w, h): 그 칸만 지우고 섞는다 — 화면 전체 반투명 섞기는 pygame 2.6(폰)에서
        한 번에 수 ms 라서 (DESIGN.md 44). 없으면 화면 전체."""
        if alpha >= 250:
            fn(canvas)
            return
        lay = self._layer(canvas, area)
        fn(lay)
        lay.set_alpha(int(max(0, alpha)))
        if area is None:
            canvas.blit(lay, (0, 0))
        else:
            r = pygame.Rect(area).clip(lay.get_rect())
            canvas.blit(lay, r.topleft, r)

    def _drag_needed(self, f) -> bool:
        """드랙 칸을 진하게: 돌진·힘 모으기·장력 빨강, 또는 방금 드랙을 바꿨을 때.
        자동 드랙 (CU3): 릴이 스스로 바꾸니 '방금 바꿈'은 빼고, 돌진 예고('Q 풀기' 깜빡) 동안 진하게."""
        if not f.manual_drag:
            return fight_hud.release_ready(f) or f.brain.state == "rush" or f.zone() == "red"
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

    def _hand_look(self) -> dict:
        """손 · 장비 디테일 (DETAILS C): 계절 장갑 · 젖은 손 · 손잡이 손때."""
        hc = load_json("details/hands_catch.json")
        g = hc["gloves"]
        glove, mitten = None, False
        if self.spot_id in g["mitten_spots"]:
            glove, mitten = tuple(g["mitten"]), True
        elif self.season == "winter":
            glove = tuple(g["knit"])
        wet = 0
        wh = hc["wet_hand"]
        if self.weather in wh["weathers"] or self.wet_t > 0:
            lo, hi = wh["dots"]
            wet = lo + (int(self.t * 0.2) % (hi - lo + 1))
        rid = self.save.data["gear"]["rod"]
        rw = hc["rod_wear"]
        n = self.save.data.get("details", {}).get("rod_casts", {}).get(rid, 0)
        wear = 3 if rid in rw["always_worn"] else 1 + sum(1 for lv in rw["levels"][1:] if n >= lv)
        return {"glove": glove, "mitten": mitten, "wet": wet, "wear": wear}

    def _draw_bait_anim(self, canvas, pal, tip) -> None:
        """미끼 끼우기 0.8초 (DETAILS C): 왼손이 아래에서 올라와 낚싯대 끝에 매달린 바늘에 미끼를 끼우고 내려감."""
        sec = load_json("details/hands_catch.json")["bait_anim"]["sec"]
        u = 1 - self.bait_anim / sec
        bx, by = rod_tip_drop(tip, self.t)
        hook = (bx, by + 6)
        k = math.sin(math.pi * min(1.0, u))   # 올라왔다 내려감
        start = (hook[0] - 70, canvas.get_height() + 20)
        hx, hy = lerp(start[0], hook[0] - 6, k), lerp(start[1], hook[1] + 4, k)
        skin, shadow = pal["hand"], pal["hand_shadow"]
        g = self._hand_look()
        if g["glove"] is not None:
            from src.core.mathutil import scale_color as _sc
            skin = _sc(g["glove"], 0.9)
            shadow = _sc(skin, 0.72)
        pygame.draw.polygon(canvas, pal["sleeve"], [(hx - 8, hy + 6), (hx + 2, hy + 8), (hx - 30, hy + 80), (hx - 48, hy + 70)])
        pygame.draw.ellipse(canvas, shadow, (hx - 7, hy - 3, 14, 10))
        pygame.draw.ellipse(canvas, skin, (hx - 8, hy - 4, 14, 10))
        if 0.3 < u < 0.75:   # 손끝에 잡은 미끼가 바늘에 꿰어짐
            wig = math.sin(self.t * 30) * 1
            pygame.draw.line(canvas, (190, 110, 100), (hx + 4, hy - 2), (hook[0] + wig, hook[1] + 2), 2)
        pygame.draw.line(canvas, scale_color(pal["line"], 0.9), (bx, by), hook, 1)
        pygame.draw.arc(canvas, (200, 200, 210), (hook[0] - 2, hook[1] - 1, 4, 5), math.pi, math.tau, 1)   # 바늘

    def _wind_bend(self) -> float:
        """낚싯줄 휨: 줄 가운데가 바람 쪽으로 바람 세기에 비례해 최대 6px (DETAILS A-2)."""
        mx = load_json("details/weather_screen.json")["line_bend"]["max_px"]
        return clamp(self.wind.x, -1.0, 1.0) * mx

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
            self._draw_trail(canvas, "float_skin", (sx, sy), max(1, int(size * 0.4)))
            draw_bobber(canvas, pal, sx, sy, size, floating=False)
            return
        sy += self.map_fx.tilt_dy(sx)   # 먼바다 기울기: 찌가 기운 수면에 붙어 있게
        ox, oy = self.hook_cine.bobber_offset()   # ① 전설: 찌가 거칠게 끌려 들어감
        if c.state == CastState.LANDED:
            ox += self.life.wake_dx()   # 지나간 배의 물결: 찌 그림만 좌우로 (입질 · 판정 무관, E)
        sx += ox
        sy += oy
        bob = 0.0
        dip = self.bite.dip if c.state in (CastState.LANDED, CastState.HOOKED) else 0.0
        if c.state == CastState.LANDED:
            # 살랑살랑: 위아래 + 좌우로 아주 조금
            bob = math.sin(self.t * 2.0) * max(0.5, s * 0.012)
            sx += math.sin(self.t * 1.3) * max(0.3, s * 0.006)
        if c.state == CastState.RETRIEVE or dip > 0.5:
            sag = 3  # 팽팽
        else:
            # 감지 않고 장력이 낮으면 아래로 처진 곡선, 최대 8px (DETAILS C) — 바람 휨(dx)과 합쳐짐
            sag = min(load_json("details/hands_catch.json")["line_slack"]["max_px"], 6 + abs(tip[0] - sx) * 0.04)
        self.last_line_pts = draw_line(canvas, pal, tip, (sx, sy + bob - size * 0.5 * (1 - dip)), sag, bias=0.6, dx=self._wind_bend())
        self._draw_trail(canvas, "float_skin", (sx, sy + bob), max(1, int(size * 0.3)))
        draw_bobber(canvas, self._bobber_pal(pal), sx, sy + bob, size, floating=True, dip=dip)
        self._draw_float_mark(canvas, sx, sy + bob, size, dip)
        pfx_hide = self.phantom_fx.mode == "bloom" and self.phantom_fx.t < self.phantom_fx.cfg["bloom"]["line_out"] + 0.4
        if c.state == CastState.LANDED and self.fight is None and self.settings.get("bobber_zoom") and not pfx_hide:
            self._draw_bobber_zoom(canvas, pal, sx, sy, size, dip)

    ZOOM_W, ZOOM_H = 84, 58

    def _draw_bobber_zoom(self, canvas, pal, sx: float, sy: float, size: float, dip: float) -> None:
        """찌 확대 말풍선: 화면이 작거나 어두워 찌가 잘 안 보일 때 — 찌에서 나온 말풍선 안에 확대한 찌 + 물고기 그림자.
        그림자는 진짜 그림자와 같은 그리기(draw_fish_shadow)를 '확대 카메라'로: 찌 둘레의 실제 위치·방향 그대로 배율만 크게."""
        W, H = self.ZOOM_W, self.ZOOM_H
        cam = self.cam
        bp = cam.project(self.cast.bx, self.cast.bz, 0.0)
        if bp is None:
            return
        m = clamp(20.0 / max(1.0, size), 2.0, 7.0)          # 확대 배율 (찌가 약 20px 이 되게)
        bcx, bcy = W / 2, H * 0.56                          # 말풍선 안 찌 위치 (수면)

        class ZoomCam:
            yaw, horizon, height = cam.yaw, -9999, H

            def project(self, x, z, h=0.0):
                p = cam.project(x, z, h)
                if p is None:
                    return None
                return bcx + (p[0] - bp[0]) * m, bcy + (p[1] - bp[1]) * m, p[2] * m
        surf = getattr(self, "_zoom_surf", None)
        if surf is None:
            surf = self._zoom_surf = pygame.Surface((W, H)).convert()
        top, bot = tuple(pal["water_top"]), tuple(pal["water_bottom"])
        gk = (top, bot, W, H)
        if getattr(self, "_zoom_gk", None) != gk:   # 물빛 그라데이션은 색이 바뀔 때만 (O2)
            grad = self._zoom_grad = pygame.Surface((W, H)).convert()
            for y in range(0, H, 2):
                grad.fill(lerp_color(top, bot, y / H), (0, y, W, 2))
            self._zoom_gk = gk
        surf.blit(self._zoom_grad, (0, 0))
        t = self.t
        for i in range(5):                                  # 잔물결
            yy = int(6 + i * 11 + math.sin(t * 1.4 + i) * 2)
            xx = int((t * 8 + i * 23) % (W + 30)) - 30
            surf.fill(pal["wave_light"], (xx, yy, 14, 1))
        sh = self.bite.shadow if self.weather != "fog" else None
        if sh is not None and self.bite.fish is not None:
            draw_fish_shadow(surf, pal, ZoomCam(), dict(sh, glow=GLOW.get(self.bite.fish["rarity"])), t)
        if dip > 0.08:                                      # 입질 물결 (찌 둘레로 퍼짐)
            for k in range(2):
                ph = (t * 1.8 + k * 0.5) % 1.0
                rw = 8 + ph * 26
                col = lerp_color(pal["wave_light"], top, ph)
                pygame.draw.ellipse(surf, col, (bcx - rw, bcy - rw * 0.28, rw * 2, rw * 0.56), 1)
        bob = math.sin(t * 2.0) * 1.2
        draw_bobber(surf, self._bobber_pal(pal), bcx, bcy + bob, 22, floating=True, dip=dip)
        # 말풍선 자리: 찌 위 (위 HUD·오른쪽 메뉴를 피해), 자리가 없으면 아래
        cw, ch = canvas.get_size()
        x = clamp(sx - W / 2, 6, cw - W - 34)
        y = sy - size - 14 - H
        below = y < 26
        if below:
            y = sy + size + 14
        x, y = int(x), int(y)
        biting = self.bite.state == BiteState.BITE
        edge = (255, 214, 90) if biting and int(t * 8) % 2 == 0 else (230, 236, 248)
        tip_y = int(sy - size * 0.6) if not below else int(sy + size * 0.6)
        base_y = y + H if not below else y
        bx0 = int(clamp(sx, x + 10, x + W - 10))
        tail = [(bx0 - 6, base_y), (bx0 + 6, base_y), (int(sx), tip_y)]
        pygame.draw.polygon(canvas, (14, 18, 34), [(p[0] + 1, p[1] + 1) for p in tail])
        pygame.draw.polygon(canvas, edge, tail)
        canvas.fill((14, 18, 34), (x - 2, y - 2, W + 4, H + 4))
        canvas.blit(surf, (x, y))
        from src.tutorial import targets
        targets.mark("fish.bobber", (x, y, W, H))   # 찌 확대 창도 찌 강조에 포함
        pygame.draw.rect(canvas, edge, (x - 2, y - 2, W + 4, H + 4), 2, border_radius=4)
        if biting:
            hud.text(canvas, "!", (x + W - 8, y + 8), (255, 214, 90), 16, "center")
