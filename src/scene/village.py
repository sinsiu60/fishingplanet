"""마을 (DESIGN.md 35-3, CONTENT_EXPANSION.md B-1·B-2): 윤슬 마을(샤르미온) · 아스테라 항구(엘드라시온).

낚시 장면(루트: 시간·날씨·팔레트·소리) 위에 push 하는 좌우 파노라마. 건물·NPC 를 눌러 상점·의뢰·어탁 갤러리·대화·계절 알림판·부두(지도).
마을이 열려 있는 동안 낚시 장면의 '배경'을 마을로 바꿔 둔다 (fishing.backdrop) → 위에 겹치는 상점·도감 화면 뒤로도 마을이 보인다.
"""
import math

import pygame

from src.core import season as seasons
from src.core.config import load_json
from src.core.mathutil import clamp
from src.render import village as vr
from src.render.weather_fx import themed_palette
from src.scene.base import Scene
from src.ui import widgets as ui
from src.ui import hud
from src.ui.hud import draw_cursor, text

DRAG_SLOP = 6


def village_for(save, spot_id: str | None = None) -> str:
    """지금 낚시터 대륙의 마을 (엘드라시온이 아직이면 윤슬 마을)."""
    from src.save.save_game import spot_continent
    cont = spot_continent(spot_id or save.data.get("spot", "reservoir"))
    return cont if cont in save.data.get("unlocked_continents", ["sharmion"]) else "sharmion"


class VillageScene(Scene):
    def __init__(self, game, fishing, cont: str = "sharmion"):
        super().__init__(game)
        self.fishing = fishing
        self.save = game.save
        self.cont = cont
        self.cfg = load_json("villages.json")[cont]
        self.width = self.cfg["width"]
        self.ox = 0.0
        self.vx = 0.0
        self.t = 0.0
        self.mouse = (0, 0)
        self.press = None          # (pos, ox) 끌기 시작
        self.dragged = False
        self.hits: list = []
        self.hover = None
        self.bubble = None         # {"npc", "lines", "i", "t"}
        self.panel = None          # 계절 알림판 {"t"}
        self.sign_panel = None     # 시우 공방 문 팻말 {"t"} (DT11)
        self.siwoo_taps = (0, -9.0)   # 시우 공방 연타 (횟수, 마지막 시각) — 5번이면 숨은 한마디
        self.siwoo_door = None     # 문이 열린 공방: 크레딧까지 남은 초 (그 사이 연타를 셈)
        self.siwoo_egg = None      # {"t"} '신시우 잘생김'
        fishing.backdrop = self.draw_world
        fishing._tut_spot = None   # 마을에서 다시 낚시터로 가면 '낚시터 입장' (가이드 튜토리얼)
        fishing.bite.stop()
        fishing.cast.reset()
        game.adaptive.set_context(cont, None)   # 마을: 대륙 테마
        game.adaptive.set("menu")
        self.season = seasons.current(game.settings)
        from src.render.season_fx import SeasonParticles
        from src.render.event_fx import EventFx
        self.particles = SeasonParticles()
        self.efx = EventFx()
        self.ev_banner = None
        self.btns = []
        self.collect_open = False   # 위 '수집' 버튼 서랍
        # 마을 생활감 (DT9): 고양이 나비 (윤슬 마을만) · 빗방울 파문 · 고양이 먹이 버튼 · 알림 한 줄
        import random as _r
        from src.render import village_life as vl
        self.rnd = _r.Random()
        w0 = game.screen.canvas.get_width()
        self.cat = vl.VillageCat(self.save, self.width, self.ox + w0 / 2, self.rnd) if cont in vl.cfg()["cat"]["villages"] else None
        self.cat_pop = None         # {"t"} [작은 물고기 주기] 버튼
        self.ripples: list = []
        self.life_msg = None        # (문장, 남은 시간, 색)
        # 스토리 (DESIGN.md 36): 휴대폰 알림 1개 · 아스테라 첫 도착(C4-01)
        from src.story import story
        self.phone = None           # {"id", "t", "after"(이어지는 자막 남은 시간)}
        self.story_seq = None       # C4-01: {"step", "t"}
        if story.active(self.save):
            story.poll(self.save)
            if cont == "eldrasion" and not story.seen(self.save, "C4-01"):
                self.story_seq = {"step": 0, "t": 0.0}
            elif "M6" not in story.state(self.save)["phone_shown"]:
                mid = story.next_phone(self.save)
                if mid:
                    self.phone = {"id": mid, "t": 0.0, "after": None}
                    game.sfx.play("st_vibrate", 0.45)
                    game.haptics.vibrate("phone")
        # 계절이 바뀐 뒤 처음 들어옴: 계절 알림 + 상점 주인의 계절 대사 (35-4)
        self.season_banner = 0.0
        self.season_changed = False   # 가이드 TG-15: 계절이 바뀐 뒤 처음 들어옴
        if self.save.data.get("season_seen") != self.season:
            first = self.save.data.get("season_seen") is None
            self.save.data["season_seen"] = self.season
            if not first:
                self.season_changed = True
                self.season_banner = 3.5
                host = "haru" if cont == "sharmion" else "ella"
                from src.scene import dialogue
                self.bubble = {"npc": host, "lines": dialogue.pick(game, host, cont, prefer_season=True), "i": 0, "t": -1.0}
                self.ox = max(0, self.cfg["npcs"][host]["x"] - game.screen.canvas.get_width() // 2)
        # 날짜 인사 · 생일 (DT11): 그날 마을 첫 입장 — 해당 NPC 말풍선 (계절 대사가 있으면 그 뒤에 차례로)
        from src.render import date_events
        self.bubble_queue: list = []
        self.snow = date_events.LightSnow(date_events.cfg()["scene"]["christmas"]["snow"])
        gr = date_events.village_greetings(self.save, cont)
        for npc, line in gr["lines"]:
            if npc in self.cfg["npcs"]:
                self.bubble_queue.append({"npc": npc, "lines": [line], "i": 0, "t": 0.0})
        if self.bubble is None and self.bubble_queue:
            self.bubble = self.bubble_queue.pop(0)
            self.ox = max(0, self.cfg["npcs"][self.bubble["npc"]]["x"] - game.screen.canvas.get_width() // 2)
        if gr["gift"]:
            self.life_msg = (date_events.cfg()["birthday"]["gift_line"], 5.0, (255, 200, 220))
        game.guide.flags["season_changed"] = self.season_changed   # 아직 장면 스택에 올라가기 전이라 직접 알려 줌
        game.guide.event("village_enter")   # 가이드 TG-15 (계절이 바뀐 뒤 처음)
        if self.cat is not None and self.cat.greet > 0:   # 마중: 지금 보는 자리 가장자리에서 달려옴
            self.cat.x = clamp(self.ox + game.screen.canvas.get_width() / 2 + 90, 20, self.width - 20)

    def tut_cond(self, name: str):
        if name == "season_changed":
            return self.season_changed
        return None

    # ── 장소 · 행동 ──
    def leave(self) -> None:
        """마을을 떠남 (낚시터로)."""
        if self.fishing.backdrop == self.draw_world:
            self.fishing.backdrop = None
        if self in self.game.scenes.stack:
            self.game.scenes.stack.remove(self)

    INTERIOR = ("haru", "baek", "ella", "oren")   # 건물 안 대화 화면 (35-3a) — 소라·갈매기 박사는 말풍선

    def enter(self, npc_id: str, **kw):
        """건물 안으로: 문 소리 + 0.4초 페이드 → 내부 대화 화면."""
        from src.scene.interior import InteriorScene
        self.bubble = None
        sc = InteriorScene(self.game, self.fishing, npc_id, village=self, **kw)
        self.game.scenes.push(sc)
        return sc

    def _act(self, kind: str, pid: str) -> None:
        self.game.sfx.play("ui_click")
        if kind == "npc":
            if pid in self.INTERIOR:
                self.enter(pid)
            else:
                self._talk(pid)
            return
        place = next(p for p in self.cfg["places"] if p["id"] == pid)
        a = place["action"]
        if place.get("npc") in self.INTERIOR and a in ("shop", "talk"):
            self.enter(place["npc"])
            return
        if a == "home":   # 주인공의 집 (스토리): 낚시 일지 · 추억 · 수첩 · 나가기
            from src.story.home import HomeScene
            self.game.scenes.push(HomeScene(self.game, self.fishing, village=self))
            return
        if a == "dock":
            from src.scene.map_scene import MapScene
            self.game.scenes.push(MapScene(self.game, self.fishing, from_village=self))
        elif a in ("shop", "quests"):
            self.fishing.open_menu(a)
        elif a == "gallery":
            from src.scene.print_gallery import PrintGalleryScene
            keeper = self._gallery_line if self.cont == "sharmion" else None
            if place.get("npc"):
                self._talk(place["npc"], quiet=True)
            self.game.scenes.push(PrintGalleryScene(self.game, self.fishing, keeper_line=keeper))
        elif a == "talk":
            self._talk(place["npc"])
        elif a == "season":
            self.panel = {"t": 0.0}
        elif a == "siwoo":   # 시우 공방 (DT11): 등용을 잡았으면 제작자 한마디 + 크레딧, 아니면 문에 걸린 팻말
            if self._siwoo_open():   # 잠깐 뒤 크레딧 (그 사이 연타 → 숨은 한마디)
                self.siwoo_door = load_json("details/siwoo_workshop.json")["door_delay_sec"]
            else:
                self.sign_panel = {"t": 0.0}

    def _siwoo_tap(self, pos) -> bool:
        """시우 공방을 연달아 누르면 셈 → egg_taps번째에 숨은 한마디. True = 이 누름은 여기서 끝."""
        r = next((r for k, pid, r in self.hits if k == "place" and pid == "siwoo"), None)
        if r is None or not r.collidepoint(pos) or self.panel or self.bubble or self.cat_pop:
            return False
        c = load_json("details/siwoo_workshop.json")
        n, last = self.siwoo_taps
        n = n + 1 if self.t - last <= c["egg_gap_sec"] else 1
        self.siwoo_taps = (n, self.t)
        if n >= c["egg_taps"]:
            self.siwoo_taps = (0, -9.0)
            self.sign_panel = self.siwoo_door = None
            self.siwoo_egg = {"t": 0.0}
            self.game.sfx.play("ui_star", 0.7)
            return True
        if n == 1:
            return False   # 첫 누름은 평소대로 (팻말 / 문)
        self.game.sfx.play("ui_click")
        if self.siwoo_door is not None:
            self.siwoo_door = c["door_delay_sec"]
        elif not self._siwoo_open() and self.sign_panel is None:
            self.sign_panel = {"t": 0.0}
        return True

    def _siwoo_open(self) -> bool:
        from src.save.save_game import fish_by_id
        from src.save import dexbook
        fid = load_json("details/siwoo_workshop.json")["unlock_fish"]
        try:
            return dexbook.entry(self.save, fish_by_id(fid)) is not None
        except (KeyError, StopIteration):
            return False

    def _gallery_line(self, fish: dict) -> str:
        """갈매기 박사: 어탁마다 한마디."""
        from src.scene import dialogue
        return dialogue.gallery_comment(self.save, fish)

    def _talk(self, npc_id: str, quiet: bool = False) -> None:
        from src.scene import dialogue
        lines = dialogue.pick(self.game, npc_id, self.cont)
        if not quiet:
            self.bubble = {"npc": npc_id, "lines": lines, "i": 0, "t": 0.0}

    # ── 입력 ──
    def handle_action(self, a) -> None:
        if a.name == "back":
            if self.bubble or self.panel or self.cat_pop or self.sign_panel:
                self.bubble = self.panel = self.cat_pop = self.sign_panel = None
                self.bubble_queue = []
                return
            from src.scene.pause import PauseScene
            self.game.scenes.push(PauseScene(self.game, self.fishing))
        elif a.name == "menu":
            if a.value == "map":
                self._act("place", "dock")
            elif a.value in ("dex", "inventory", "shop", "quests", "chest", "achievements"):
                self.fishing.open_menu(a.value)
        elif a.name == "debug" and a.value == "F12":
            from src.core.config import load_json as _lj
            if _lj("fishing_config.json").get("debug_keys") or _lj("mobile_config.json").get("debug_build"):
                seasons.cycle_forced()
                self.season = seasons.current(self.game.settings)
        elif a.name == "scroll":
            self.ox -= a.value * 50
        elif a.name == "drag":
            self.ox += a.value * 80
        elif a.name == "flick":
            self.vx -= a.value * 900
        elif a.name == "primary":
            self.press = (a.pos, self.ox)
            self.dragged = False
        elif a.name == "primary_up":
            pos = a.pos
            was_drag = self.dragged
            self.press = None
            self.dragged = False
            if was_drag or pos is None:
                return
            self._click(pos)

    def _click(self, pos) -> None:
        if self.story_seq is not None:
            return
        if self.phone is not None and self.phone["after"] is None:
            w, h = self.game.screen.canvas.get_size()
            if pygame.Rect(w - 146, h - 66, 140, 60).collidepoint(pos):
                self._close_phone()
                return
        if self._siwoo_tap(pos):
            return
        if self.panel is not None:
            self.panel = None
            return
        if self.sign_panel is not None:
            self.sign_panel = None
            return
        if self.bubble is not None:
            b = self.bubble
            b["i"] += 1
            if b["i"] >= len(b["lines"]):
                self.bubble = self._next_bubble()
            return
        for b in self.btns:
            if b.click(pos):
                return
        if self.cat_pop is not None:   # [작은 물고기 주기] (다른 곳을 누르면 닫힘)
            hit = self._cat_btn().collidepoint(pos)
            self.cat_pop = None
            if hit:
                self._feed_cat()
                return
        w = self.game.screen.canvas.get_width()
        if pos[0] < 22:
            self.vx -= 700
            return
        if pos[0] > w - 22:
            self.vx += 700
            return
        if self.cat is not None and self.cat.rect(self.ox, vr.FEET + 8).collidepoint(pos):
            self.game.sfx.play("sfx_cat_meow", 0.45)
            self.cat_pop = {"t": 0.0}
            return
        for kind, pid, r in reversed(self.hits):   # 앞(NPC)부터
            if r.collidepoint(pos):
                self._act(kind, pid)
                return

    def _next_bubble(self):
        """다음 차례 말풍선 (날짜 인사 · 생일, DT11) — 그 NPC 쪽으로 화면을 옮김."""
        if not getattr(self, "bubble_queue", None):
            return None
        b = self.bubble_queue.pop(0)
        w = self.game.screen.canvas.get_width()
        self.ox = clamp(self.cfg["npcs"][b["npc"]]["x"] - w // 2, 0, max(0, self.width - w))
        return b

    # ── 고양이 (DT9) ──
    def _cat_btn(self) -> pygame.Rect:
        sx = int(self.cat.x - self.ox)
        w = self.game.screen.canvas.get_width()
        r = pygame.Rect(0, 0, 112, 22 if self.game.input.kind == "touch" else 18)   # 터치: 손가락 크기
        r.midbottom = (int(clamp(sx, 60, w - 60)), vr.FEET - 18)
        return r

    def _feed_cat(self) -> None:
        from src.render import village_life as vl
        c = vl.cfg()["cat"]
        res = vl.feed_cat(self.save)
        L = c["lines"]
        if res["result"] == "fed":
            self.cat.fed(self.game.sfx)
            self._say(L["feed"].replace("{n}", str(res["n"])), (255, 220, 180))
            if res["title"]:
                self._say(L["title"], (255, 214, 90), after=True)
            self.game.save_now()
        else:
            self.game.sfx.play("ui_click")
            self._say(L[res["result"]], (220, 214, 200))

    def _say(self, s: str, col, after: bool = False) -> None:
        if after and self.life_msg is not None:
            self.life_msg = (self.life_msg[0] + "  ·  " + s, 3.2, col)
        else:
            self.life_msg = (s, 2.6, col)

    # ── 시간 ──
    def _close_phone(self) -> None:
        msg = load_json("story/phone.json")["messages"][self.phone["id"]]
        if msg.get("after"):   # 이어지는 자막 (M5: 단톡방을 조용히 나왔다)
            self.phone["after"] = 3.0
        else:
            self.phone = None

    def _story_update(self, dt: float) -> None:
        if self.phone is not None:
            self.phone["t"] += dt
            if self.phone["after"] is None and self.phone["t"] >= 5.0:
                self._close_phone()
            elif self.phone is not None and self.phone["after"] is not None:
                self.phone["after"] -= dt
                if self.phone["after"] <= 0:
                    self.phone = None
        sq = self.story_seq
        if sq is not None:   # C4-01: 자막 3초 → 휴대폰 '전파 없음'(막대 0개) → 자막 → 일지 J10
            sq["t"] += dt
            if sq["step"] == 0 and sq["t"] >= 3.0:
                sq.update(step=1, t=0.0)
                self.game.sfx.play("st_vibrate", 0.35)
            elif sq["step"] == 1 and sq["t"] >= 2.5:
                sq.update(step=2, t=0.0)
            elif sq["step"] == 2 and sq["t"] >= 3.0:
                from src.story import story
                self.story_seq = None
                story.complete(self.game, "C4-01")

    def update(self, dt: float) -> None:
        self.t += dt
        self._story_update(dt)
        if self.game.scenes.current is self and self.story_seq is None and self.game.guide.run is None:
            from src.scene.exam_scene import ExamNoticeScene, notice_ready
            if notice_ready(self.game):   # 미뤄 둔 백 노인 시험 변경 공지 (이야기 튜토리얼이 끝난 뒤 마을에서, 🅲-1)
                self.game.scenes.push(ExamNoticeScene(self.game))
        from src.ui import achv_toast
        achv_toast.update(self.game, dt, self.game.scenes.current is self and self.story_seq is None)
        f = self.fishing
        f.clock.update(dt)      # 마을에서도 시간은 흐른다 (등불·창문 불빛)
        f.ambience.update(dt, self.cfg["ambience"], f.clock.period()[0], f.weather, season=self.season)
        from src.fishing import weather_events
        new = weather_events.tick(self.save, f.clock.day, f.clock.hour, f.weather)
        if new:   # 마을에서 이벤트가 시작됨: 위쪽 배너
            self.ev_banner = {"id": new, "t": 0.0}
        if getattr(self, "ev_banner", None):
            self.ev_banner["t"] += dt
            if self.ev_banner["t"] > 3.5:
                self.ev_banner = None
        self.efx.update(dt, self._eid(), self.game.screen.canvas.get_width(), vr.HORIZON, False)
        self.particles.update(dt, self.season, self.cont, self.game.screen.canvas.get_width(), self.game.screen.canvas.get_height(),
                              f.clock.period()[0], f.weather, mobile=self.game.input.kind == "touch")
        self.game.adaptive.set_context(self.cont, None)
        self.game.adaptive.set("menu")
        self.mouse = self.game.input.pointer
        held = pygame.mouse.get_pressed()[0] if self.game.input.kind != "touch" else bool(getattr(self.game.input, "fingers", None))
        if self.press is not None and held:
            dx = self.mouse[0] - self.press[0][0]
            if abs(dx) > DRAG_SLOP:
                self.dragged = True
            if self.dragged:
                self.ox = self.press[1] - dx
        self.ox += self.vx * dt
        self.vx *= max(0.0, 1 - 6 * dt)
        w = self.game.screen.canvas.get_width()
        self.ox = clamp(self.ox, 0, max(0, self.width - w))
        if self.bubble:
            self.bubble["t"] += dt
        if self.cat is not None:
            self.cat.update(dt, self.ox + w / 2, self.game.sfx)
        if self.cat_pop is not None:
            self.cat_pop["t"] += dt
            if self.cat_pop["t"] > 4.0:
                self.cat_pop = None
        if self.life_msg is not None:
            m, left, col = self.life_msg
            self.life_msg = (m, left - dt, col) if left - dt > 0 else None
        if self.siwoo_door is not None:
            self.siwoo_door -= dt
            if self.siwoo_door <= 0:
                self.siwoo_door = None
                from src.scene.credits import CreditsScene
                self.game.sfx.play("ui_door", 0.6)
                self.game.scenes.push(CreditsScene(self.game))
        if self.siwoo_egg is not None:
            self.siwoo_egg["t"] += dt
            if self.siwoo_egg["t"] > 2.8:
                self.siwoo_egg = None
        from src.render import village_life as vl
        if self.cont in vl.cfg()["rain"]["puddle_villages"]:
            self.ripples = vl.tick_ripples(self.ripples, dt, self.fishing.weather, self.rnd)
        self.season_banner = max(0.0, self.season_banner - dt)
        if self.panel:
            self.panel["t"] += dt
        self.hover = None
        for kind, pid, r in reversed(self.hits):
            if r.collidepoint(self.mouse):
                self.hover = (kind, pid)
                break

    # ── 그리기 ──
    def _pal(self) -> dict:
        from src.render.season_fx import season_palette
        from src.render.event_fx import event_palette
        f = self.fishing
        pal = season_palette(themed_palette(f.palette.sample(f.clock.hour), {}, f.weather), self.season, self.cont)
        return event_palette(pal, self._eid(), self.cont)

    def _eid(self):
        from src.fishing import weather_events
        ev = weather_events.active(self.save)
        return ev["id"] if ev else None

    def draw_world(self, canvas) -> None:
        """마을 풍경 (상점·도감 같은 겹친 화면 뒤에도 이것이 보인다)."""
        w, h = canvas.get_size()
        pal = self._pal()
        hour = self.fishing.clock.hour
        night = vr._night(hour)
        style = self.cfg["style"]
        ox = self.ox
        from src.render import date_events
        ev = date_events.events()
        vr.SKY.clear()
        vr.SKY.update(date_events.sky_tweak(hour))   # 추석 보름달 (DT11)
        vr._sky(canvas, pal, w)
        sun_x = vr._celestial(canvas, pal, hour, ox, w, self.t)
        sc = date_events.cfg()["scene"]
        if "seollal" in ev and self.cont in sc["seollal"]["villages"]:   # 설날 연
            date_events.draw_kites(canvas, ox, w, self.t, sc["seollal"]["kites"])
        self.efx.draw_sky(canvas, self._eid(), self.cont, vr.HORIZON, False)
        vr._far(canvas, pal, ox, w, style)
        vr._sea(canvas, pal, ox, w, self.t, sun_x, night)
        if style == "wood":
            vr.draw_gulls(canvas, w, self.t)
        self.efx.draw_low(canvas, self._eid(), self.cont, vr.HORIZON, False)
        vr._ground(canvas, pal, ox, w, h, style)
        from src.render import village_life as vl
        lc = vl.cfg()
        wet = self.fishing.weather in ("rain", "storm")
        if wet and self.cont in lc["rain"]["puddle_villages"]:   # 물웅덩이 (윤슬 마을)
            vl.draw_puddles(canvas, pal, ox, w, self.t, self.fishing.weather, self.ripples)
        hits = []
        from src.story.story import player_name
        for p in self.cfg["places"]:
            sx = p["x"] - ox
            if -200 < sx < w + 200:
                if "{player}" in p["name"]:
                    p = dict(p, label=p["name"].replace("{player}", player_name(self.save)))
                if p["kind"] == "workshop":
                    p = dict(p, open=self._siwoo_open())
                r = vr.draw_place(canvas, p, sx, pal, night, self.t, style, self.season,
                                  self.hover == ("place", p["id"]))
                hits.append(("place", p["id"], r))
                sk = vl.smoke_on(hour)
                top = vl.chimney_pos(p, sx, vr.GROUND) if sk > 0 else None
                if top is not None:   # 굴뚝 연기 17~19시
                    vl.draw_smoke(canvas, top, self.t, sk, int(p["x"]), 0.3 + (0.6 if wet else 0.0))
        from src.render.season_fx import draw_village_decor
        draw_village_decor(canvas, self.cfg["places"], ox, self.season, night, self.t, vr.GROUND)   # 계절 장식
        if "christmas" in ev:   # 크리스마스: 처마 전구 (DT11)
            date_events.draw_bulbs(canvas, self.cfg["places"], ox, w, self.t, vr.GROUND, night)
        vr.draw_lamps(canvas, ox, w, style, night, self.t, self.width)
        for nid, n in self.cfg["npcs"].items():
            sx = n["x"] - ox
            if -30 < sx < w + 30:
                r = vr.draw_npc(canvas, sx, n, self.t, self.season, self.hover == ("npc", nid), night,
                                rain=wet and self.cont in lc["rain"]["umbrella_villages"])
                hits.append(("npc", nid, r))
        if self.cat is not None:
            self.cat.draw(canvas, ox, vr.FEET + 8, night)
        if style == "stone":
            vr.draw_motes(canvas, w, self.t, night)
        self._weather(canvas, w, h)
        self.particles.draw(canvas)
        if "christmas" in ev:   # 가볍게 눈 내리는 풍경 (실제 날씨와 별개, 화면 효과만)
            self.snow.draw(canvas, self.t)
        self.hits = hits

    def _weather(self, canvas, w, h) -> None:
        wt = self.fishing.weather
        if wt in ("rain", "storm"):
            n = 60 if wt == "rain" else 110
            for i in range(n):
                x = (i * 53 + self.t * 220) % (w + 40) - 20
                y = (i * 97 + self.t * 380) % h
                pygame.draw.line(canvas, (170, 180, 200), (x, y), (x - 3, y + 8), 1)
        elif wt == "fog":
            fog = pygame.Surface((w, h), pygame.SRCALPHA)
            fog.fill((210, 214, 222, 70))
            canvas.blit(fog, (0, 0))

    def draw(self, canvas) -> None:
        self.draw_world(canvas)
        w, h = canvas.get_size()
        # 위: 마을 이름 · 계절 · 시간 · 돈
        bar = pygame.Surface((w, 22), pygame.SRCALPHA)
        bar.fill((10, 12, 24, 150))
        canvas.blit(bar, (0, 0))
        sname = seasons.name(self.season, self.cont)
        text(canvas, f"{self.cfg['name']} · {sname} · {self.fishing.clock.label()}", (8, 11), (255, 240, 200), 11, "midleft")
        text(canvas, ui.money_text(ui.money_anim(self.save.money)), (w - 150, 11), ui.ACCENT, 11, "midright")
        labels = (("수집", "collection"), ("가방", "inventory"), ("설정", "settings"))
        self.btns = []
        for i, (lab, key) in enumerate(labels):
            b = ui.Button((w - 142 + i * 46, 4, 42, 14), lab, lambda k=key: self._menu(k))
            b.draw(canvas, self.mouse, selected=key == "collection" and self.collect_open)
            self.btns.append(b)
        if self.collect_open:   # 수집 서랍: 수집 버튼 아래에서 왼쪽으로 (도감 · 업적 · 어탁 · 수조)
            items = (("도감", "dex"), ("업적", "achievements"), ("어탁", "prints"), ("수조", "tank"))
            x0 = w - 142 + 42
            back = pygame.Surface((4 * 46 + 4, 20), pygame.SRCALPHA)
            back.fill((10, 12, 24, 190))
            canvas.blit(back, (x0 - 4 * 46 - 2, 22))
            for i, (lab, key) in enumerate(items):
                b = ui.Button((x0 - (i + 1) * 46 + 4, 25, 42, 14), lab, lambda k=key: self._menu(k))
                b.draw(canvas, self.mouse)
                self.btns.insert(0, b)
        self._draw_story(canvas)
        from src.ui import achv_toast
        achv_toast.draw(self.game, canvas)
        # 양 끝 화살표
        for side in (-1, 1):
            if (side < 0 and self.ox > 1) or (side > 0 and self.ox < self.width - w - 1):
                cx = 10 if side < 0 else w - 10
                k = 0.6 + 0.4 * math.sin(self.t * 3)
                pygame.draw.polygon(canvas, (int(255 * k), int(240 * k), int(200 * k)),
                                    [(cx - 4 * side, h // 2 - 8), (cx + 4 * side, h // 2), (cx - 4 * side, h // 2 + 8)])
        if self.t < 6 and self.bubble is None:
            text(canvas, "끌어서 둘러보기 · 건물과 사람을 눌러 보세요", (w // 2, h - 10), (230, 225, 210), 11, "center")
        if self.ev_banner:
            from src.fishing import weather_events
            ev = weather_events.by_id(self.ev_banner["id"])
            a = min(1.0, self.ev_banner["t"] / 0.4, (3.5 - self.ev_banner["t"]) / 0.6)
            band = pygame.Surface((w, 26), pygame.SRCALPHA)
            band.fill((10, 12, 26, int(160 * a)))
            canvas.blit(band, (0, 58))
            text(canvas, f"{ev['banner']} — {ev['benefit_text']}", (w // 2, 71), tuple(int(v * a) for v in (255, 240, 210)), 11, "center", shadow=True)
        if self.season_banner > 0:
            a = min(1.0, self.season_banner / 0.5, (3.5 - self.season_banner) / 0.4)
            band = pygame.Surface((w, 26), pygame.SRCALPHA)
            band.fill((20, 16, 10, int(170 * a)))
            canvas.blit(band, (0, 30))
            text(canvas, f"계절이 바뀌었어요 — {sname}", (w // 2, 43), tuple(int(v * a) for v in (255, 230, 170)), 16, "center", shadow=True)
        if self.cat_pop is not None:
            r = self._cat_btn()
            hov = r.collidepoint(self.mouse)
            canvas.fill((250, 240, 220) if hov else (236, 226, 204), r)
            pygame.draw.rect(canvas, (110, 80, 50), r, 1)
            text(canvas, "작은 물고기 주기", r.center, (70, 50, 30), 11, "center")
        if self.life_msg is not None:
            m, left, col = self.life_msg
            a = min(1.0, left / 0.4)
            band = pygame.Surface((w, 18), pygame.SRCALPHA)
            band.fill((10, 12, 24, int(150 * a)))
            canvas.blit(band, (0, 24))   # 위쪽 (고양이 · 사람 발치를 가리지 않게)
            text(canvas, m, (w // 2, 33), tuple(int(v * a) for v in col), 11, "center", shadow=True)
        if self.bubble is not None and self.bubble["t"] >= 0:
            self._draw_bubble(canvas)
        if self.panel is not None:
            self._draw_season_panel(canvas)
        if self.sign_panel is not None:   # 문에 걸린 나무 팻말 (가까이서)
            msg = load_json("details/siwoo_workshop.json")["closed"]
            from src.core.fonts import get_font
            tw = get_font(16).size(msg)[0] + 28
            r = pygame.Rect(0, 0, tw, 44)
            r.center = (w // 2, h // 2 - 10)
            pygame.draw.line(canvas, (80, 60, 40), (r.x + 20, r.y), (w // 2, r.y - 22), 2)
            pygame.draw.line(canvas, (80, 60, 40), (r.right - 20, r.y), (w // 2, r.y - 22), 2)
            canvas.fill((70, 50, 32), r.move(2, 3))
            canvas.fill((226, 210, 176), r)
            pygame.draw.rect(canvas, (120, 88, 56), r, 2)
            text(canvas, msg, r.center, (70, 50, 30), 16, "center")
            text(canvas, "누르면 닫기", (w // 2, r.bottom + 12), (230, 225, 210), 11, "center", shadow=True)
        if self.siwoo_egg is not None:
            self._draw_siwoo_egg(canvas)
        draw_cursor(canvas, self.mouse)

    def _draw_siwoo_egg(self, canvas) -> None:
        """숨은 한마디: 공방 위에서 통 튀어 오르는 금빛 글자 + 반짝이 (2.8초)."""
        w, h = canvas.get_size()
        t = self.siwoo_egg["t"]
        r = next((r for k, pid, r in self.hits if k == "place" and pid == "siwoo"), None)
        cx = int(clamp(r.centerx, 70, w - 70)) if r is not None else w // 2
        pop = min(1.0, t / 0.25)
        y = int((r.top - 18 if r is not None else h // 3) - 14 * math.sin(pop * math.pi / 2))
        fade = clamp((2.8 - t) / 0.5, 0.0, 1.0)
        size = 18 if t > 0.25 else 12 + int(10 * math.sin(t / 0.25 * math.pi))   # 살짝 커졌다 제자리
        col = tuple(int(v * fade) for v in (255, 214, 90))
        text(canvas, load_json("details/siwoo_workshop.json")["egg"], (cx, y), col, size, "center", shadow=True)
        for i in range(6):   # 글자 둘레 반짝이
            a = t * 2.2 + i * math.tau / 6
            px, py = cx + int(math.cos(a) * 62), y + int(math.sin(a) * 16)
            if (int(t * 12) + i) % 3 and fade > 0.2:
                canvas.fill((255, 246, 200), (px - 1, py, 3, 1))
                canvas.fill((255, 246, 200), (px, py - 1, 1, 3))

    def _draw_story(self, canvas) -> None:
        """다음 목표 (왼쪽 위 한 줄 + 찌 아이콘) · 휴대폰 알림 · C4-01 자막."""
        from src.story import story
        from src.story import ui as sui
        if not story.active(self.save):
            return
        g = story.goal(self.save)
        if g and self.story_seq is None:
            x, y = 10, 30
            canvas.fill((255, 255, 255), (x, y - 4, 4, 3))      # 작은 찌 (빨강·흰색)
            canvas.fill((232, 74, 74), (x, y - 1, 4, 4))
            canvas.fill((200, 200, 200), (x + 1, y - 7, 1, 3))
            text(canvas, g, (x + 9, y), (240, 236, 220), 11, "midleft")
        msgs = load_json("story/phone.json")["messages"]
        if self.phone is not None:
            m = msgs[self.phone["id"]]
            if self.phone["after"] is None:
                sui.draw_phone(canvas, m["from"], m["text"], self.phone["t"])
            else:
                sui.subtitle(canvas, m["after"], min(1.0, self.phone["after"] / 0.3))
        sq = self.story_seq
        if sq is not None:
            sc = story.scene("C4-01")
            if sq["step"] == 0:
                sui.subtitle(canvas, sc["subs"][0], min(1.0, sq["t"] / 0.3, (3.0 - sq["t"]) / 0.3))
            elif sq["step"] == 1:
                sui.draw_phone(canvas, None, msgs["M6"]["text"], sq["t"])
            else:
                sui.subtitle(canvas, msgs["M6"]["after"], min(1.0, sq["t"] / 0.3, (3.0 - sq["t"]) / 0.3))

    def _menu(self, key: str) -> None:
        if key == "collection":
            self.game.sfx.play("ui_click")
            self.collect_open = not self.collect_open
            return
        self.collect_open = False
        if key == "tank":
            self.game.sfx.play("ui_click")
            self.fishing.start_training()   # 마을을 떠나 지금 낚시터의 훈련 수조로
            return
        if key == "settings":
            from src.scene.settings_scene import SettingsScene
            self.game.sfx.play("ui_click")
            self.game.scenes.push(SettingsScene(self.game))
        else:
            self.fishing.open_menu(key)

    def _draw_bubble(self, canvas) -> None:
        b = self.bubble
        n = self.cfg["npcs"][b["npc"]]
        sx = n["x"] - self.ox
        line = b["lines"][min(b["i"], len(b["lines"]) - 1)]
        rows = hud.wrap_rich(line, 220)[:2]
        bw = 236
        bx = int(clamp(sx - bw / 2, 6, canvas.get_width() - bw - 6))
        by = vr.FEET - 92
        r = pygame.Rect(bx, by, bw, 18 + 13 * len(rows))
        canvas.fill((250, 246, 236), r)
        pygame.draw.rect(canvas, (60, 50, 40), r, 1)
        tip_x = int(clamp(sx, r.x + 10, r.right - 10))
        pygame.draw.polygon(canvas, (250, 246, 236), [(tip_x - 5, r.bottom - 1), (tip_x + 5, r.bottom - 1), (tip_x, r.bottom + 7)])
        text(canvas, n["name"], (r.x + 6, r.y + 7), (150, 90, 40), 11, "midleft")
        shown = int(b["t"] * 40)
        for j, ln in enumerate(rows):
            vis = max(0, shown - sum(len(hud.strip_tags(x)) for x in rows[:j]))
            hud.rich_text(canvas, ln, (r.x + 6, r.y + 20 + j * 13), (40, 36, 30), 11, "midleft", visible=vis,
                          tag_colors=hud.TAG_COLORS_LIGHT_BG)
        if len(b["lines"]) > 1:
            text(canvas, f"{b['i'] + 1}/{len(b['lines'])} ▶", (r.right - 4, r.y + 7), (150, 140, 120), 11, "midright")

    def _draw_season_panel(self, canvas) -> None:
        """계절 알림판: 지금 계절 · 남은 날 · 계절 한정 물고기 실루엣 · 진행 중인 날씨 이벤트."""
        from src.render.fish_draw import draw_fish_fit
        from src.save import dexbook
        w = canvas.get_width()
        r = pygame.Rect(w // 2 - 170, 40, 340, 170)
        ui.panel(canvas, r, (230, 200, 140), (30, 24, 18))
        from src.tutorial import targets as T   # TG-15
        T.mark("village.season", r)
        s = self.season
        text(canvas, f"계절 알림판 — {seasons.name(s, self.cont)}", (r.centerx, r.y + 14), (255, 230, 170), 16, "center")
        if seasons.locked(self.game.settings):
            sub = "설정에서 계절을 고정했어요 (계절 한정 물고기는 나오지 않아요)"
        else:
            sub = f"이번 계절은 {seasons.days_left()}일 남았어요 (실제 날짜 1주 = 계절 1개)"
        text(canvas, sub, (r.centerx, r.y + 34), (220, 210, 190), 11, "center")
        lim = [f for f in dexbook.limited_fish() if f.get("season") == s and f.get("continent", self.cont) == self.cont]
        y = r.y + 52
        if lim:
            text(canvas, "이 계절에만 나타나는 물고기", (r.x + 12, y), (255, 214, 140), 11, "midleft")
            for i, f in enumerate(lim[:3]):
                box = pygame.Rect(r.x + 12 + i * 106, y + 10, 100, 48)
                ui.panel(canvas, box, (120, 100, 70), (20, 16, 12))
                T.mark("village.season.fish", box)
                got = dexbook.entry(self.save, f) is not None
                draw_fish_fit(canvas, box.inflate(-8, -16), f, 70, silhouette=None if got else (8, 8, 12))
                text(canvas, f["name"] if got else "???", (box.centerx, box.bottom - 7), (230, 220, 200), 11, "center")
            y += 66
        ev = self._event_line()
        if ev:
            text(canvas, ev, (r.centerx, y + 8), (200, 230, 255), 11, "center")
        text(canvas, "누르면 닫기", (r.centerx, r.bottom - 10), (150, 140, 120), 11, "center")

    def _event_line(self) -> str | None:
        try:
            from src.fishing import weather_events
        except ImportError:
            return None
        return weather_events.board_line(self.save, self.fishing)
