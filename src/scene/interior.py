"""건물 내부 대화 화면 (DESIGN.md 35-3a, INTERIOR_NPC.md): 하루 아저씨 · 백 노인 · 엘라 · 오렌.

위: 건물 내부 배경 + 카운터 뒤 초상화(64x64 → 2배) · 왼쪽 위 간판 / 아래 왼쪽: 대화창(이름 + 최대 2줄) / 아래 오른쪽: 메뉴(찌 모양 커서).
살아 있게: 대사마다 표정(expr) · 3~5초마다 눈 깜빡임 · 글자가 나오는 동안 입 프레임 교대 · 숨쉬기 1px · 한 글자씩(탭 1번 전체, 2번 다음) · NPC별 말소리.
사기·팔기·강화 = 기존 상점을 이 화면 안 패널로 (ShopScene host=self: 초상화는 왼쪽 창에 계속 보이고, 사면 웃음 + 짧은 반응 대사).
대본(script) 모드: 스토리 장면이 [(화자, 표정, 대사)] 를 넘기면 메뉴 없이 대사만 (끝나면 on_done).
"""
import math
import random

import pygame

from src.core import season as seasons
from src.core.config import load_json
from src.render import interior as ir
from src.render import village as vr
from src.scene.base import Scene
from src.ui import hud
from src.ui.hud import draw_cursor, text

NAME_COL = (242, 196, 107)    # #F2C46B
SIGN_BG, SIGN_FG = (42, 30, 26), (242, 230, 200)
BOX_H = 84
_PORTRAITS: dict = {}


def cfg() -> dict:
    return load_json("interiors.json")


def portrait(npc: str, expr: str, blink: bool = False, talk: bool = False) -> pygame.Surface:
    """assets/portraits/npc_<npc>_<expr>[_blink][_talk].png 를 2배로 (128x128). 없으면 기본 표정."""
    key = (npc, expr, blink, talk)
    img = _PORTRAITS.get(key)
    if img is None:
        from src.core.paths import asset_path
        suf = ("_blink" if blink else "") + ("_talk" if talk else "")
        try:
            raw = pygame.image.load(str(asset_path("portraits", f"npc_{npc}_{expr}{suf}.png")))
        except (FileNotFoundError, pygame.error):
            raw = pygame.image.load(str(asset_path("portraits", f"npc_{npc}_neutral.png"))) if expr != "neutral" or suf \
                else pygame.Surface((64, 64), pygame.SRCALPHA)
        try:
            raw = raw.convert_alpha()
        except pygame.error:
            pass
        img = pygame.transform.scale(raw, (128, 128))
        _PORTRAITS[key] = img
    return img


class InteriorScene(Scene):
    def __init__(self, game, fishing, npc_id: str, village=None, script: list | None = None, on_done=None,
                 menu: bool = True, greet: bool = True, replay: bool = False):
        super().__init__(game)
        self.fishing = fishing
        self.save = game.save
        self.village = village
        self.npc = npc_id
        self.c = cfg()
        self.nc = self.c["npcs"][npc_id]
        self.cont = self.nc["cont"]
        vcfg = load_json("villages.json")[self.cont]["npcs"].get(npc_id, {"name": ""})
        self.name = vcfg.get("name", npc_id)
        self.t = 0.0
        self.mouse = (0, 0)
        self.rnd = random.Random()
        self.season = seasons.current(game.settings)
        # 대화 상태
        self.queue: list[tuple] = []      # [(화자 npc_id 또는 None(자막), 표정, 문장)]
        self.line = None                   # 지금 대사
        self.shown = 0.0                   # 보인 글자 수 (태그 제외)
        self.voice_n = 0
        self.expr = "neutral"
        self.wait_menu = False
        self.menu_on = menu
        self.menu_sel = 0
        self.replay = replay                # 추억에서 다시 보기 (결과 없음)
        self.fade_col = (0, 0, 0)
        self.story_sid = None
        if script is None and not replay:   # 스토리: 이 건물에서 재생할 대기 장면이 있으면 그것부터 (DESIGN.md 36)
            from src.story import story
            sid = story.take_interior(game.save, npc_id)
            if sid is not None:
                from src.story.runner import interior_script
                script = interior_script(game, sid)
                self.story_sid = sid
                menu = story.scene(sid).get("menu", True) and menu
                on_done = self._story_done
        self.script = script is not None
        self.on_done = on_done
        # 연출
        self.blink_t = self.rnd.uniform(*self.c["blink_every"])
        self.blink_left = 0.0
        self.fade_in = self.c["fade_sec"]
        self.leaving = None                # 작별 대사 뒤 페이드 아웃 남은 시간
        self.leave_wait = 0.0
        self.shop = None                   # 열린 상점 패널 (ShopScene)
        self.react_line = None             # 상점 패널 옆 반응 대사 (표정, 문장, 시각)
        fishing.bite.stop()   # 문 소리·실내 소리는 소리 구역(game.zones)이 (DESIGN.md 39)
        # 밤 하품 (DT9): 하루 아저씨 내부에서 밤이면 가끔 하품 · 그 게임 날 밤 처음 들어오면 대사 1개 추가
        self.yawn_t = self.rnd.uniform(4, 8)
        self.yawn_left = 0.0
        if script is not None:
            self.say(script)
        elif greet:
            self._greet()
            self._night_line()

    # ── 대사 ──
    def _story_done(self, sc) -> None:
        from src.story import story
        story.complete(self.game, self.story_sid)

    def say(self, lines) -> None:
        """[(화자, 표정, 문장)] 또는 [(표정, 문장)] (화자 = 이 NPC) 를 이어서 말한다. {do: …} 는 대본 특수 단계."""
        for ln in lines:
            if isinstance(ln, dict):
                self.queue.append(ln)
                continue
            if len(ln) == 2:
                ln = (self.npc, ln[0], ln[1])
            self.queue.append(tuple(ln))
        if self.line is None or self.wait_menu:   # 메뉴를 기다리던 중이면 바로 새 대사
            self._next()

    def _next(self) -> None:
        if self.queue and isinstance(self.queue[0], dict):   # 이름 입력 · 클로즈업 · 편지
            item = self.queue.pop(0)
            from src.story.runner import step
            step(self, item, self._next)
            return
        if self.queue:
            self.line = self.queue.pop(0)
            self.shown = 0.0
            self.voice_n = 0
            if self.line[0] == self.npc:
                self.expr = self.line[1] or "neutral"
            self.wait_menu = False
            return
        self.line_done_all()

    def line_done_all(self) -> None:
        if self.leaving is not None:
            return
        if self.script:
            self.script = False
            cb, self.on_done = self.on_done, None
            if cb is not None:
                cb(self)
            if self not in self.game.scenes.stack:   # 콜백이 다음 화면으로 넘겼으면 끝
                return
            if not self.menu_on:
                self._begin_leave(farewell=False)
                return
        self.wait_menu = True
        if self.menu_on and not self.replay:
            self.game.guide.event(f"interior_ready:{self.npc}")
            if self.npc == "home":
                self.game.guide.event("home_ready")   # 가이드 튜토리얼 (TG-06 판매 · TG-12 강화 · TG-18)

    def tut_busy(self) -> bool:
        """대사가 진행 중이면 가이드는 기다림 (메뉴가 뜬 뒤 시작)."""
        return not self.wait_menu or self.leaving is not None or self.fade_in > 0
    def _plain(self) -> str:
        return hud.strip_tags(self._text()) if self.line else ""

    def _text(self) -> str:
        if not self.line:
            return ""
        from src.story.story import player_name
        return self.line[2].replace("{player}", player_name(self.save))

    def typing(self) -> bool:
        return self.line is not None and self.shown < len(self._plain())

    def _ctx(self):
        from src.scene import dialogue
        return dialogue.context(self.game, self.cont)

    def _greet(self) -> None:
        from src.scene import dialogue
        seq = dialogue.pick_seq(self.game, self.npc, self.cont, kind="greet_first") or \
            dialogue.pick_seq(self.game, self.npc, self.cont)
        self.say(seq)

    def _is_night(self) -> bool:
        return self.fishing.clock.period()[0] == "night"

    def _night_line(self) -> None:
        from src.render.village_life import cfg as vl_cfg
        c = vl_cfg()["night"]
        if self.npc != c["yawn_npc"] or self.replay or not self._is_night():
            return
        clock = self.fishing.clock
        key = clock.day - 1 if clock.hour < 6 else clock.day   # 자정 넘긴 새벽도 같은 밤
        det = self.save.data.setdefault("details", {})
        if det.get("haru_night_day") == key:
            return
        det["haru_night_day"] = key
        self.say([("surprised", c["first_night_line"])])

    def react(self, kind: str) -> None:
        """상점 패널에서 사기·팔기·강화 → 웃음 표정 + 짧은 반응 대사 (dialogue.json react_*)."""
        from src.scene import dialogue
        seq = dialogue.pick_seq(self.game, self.npc, self.cont, kind=f"react_{kind}")
        if seq:
            e, t = seq[0]
            self.expr = e
            self.react_line = (e, t, self.t)
            self._voice_burst(len(hud.strip_tags(t)))

    def _voice_burst(self, n: int) -> None:
        if self.game.settings.get("voice_blips"):
            v = self.nc["voice"]
            self.game.sfx.play(f"{v['sound']}{self.rnd.randrange(3)}", v.get("vol", 0.5))

    # ── 메뉴 ──
    def _menu_items(self) -> list[str]:
        if not self.menu_on:
            return []
        from src.save import exam
        return [m for m in self.nc["menu"] if m != "letter" or exam.letter_menu(self.save)]   # 엘라 편지: T6 시험부터

    def _choose(self, item: str) -> None:
        self.game.sfx.play("ui_click")
        from src.scene import dialogue
        if item in ("buy", "sell", "scalestone"):
            self._open_shop(item)
        elif item == "talk":
            self.say(dialogue.pick_seq(self.game, self.npc, self.cont))
        elif item in ("old_tales", "legend_tales", "season_tales"):
            ln = dialogue.tale(self.save, self.npc, item, self._ctx())
            self.say(dialogue.seq_of(ln) if ln else [("neutral", "…")])
        elif item in ("exam", "letter"):
            from src.scene.exam_scene import ExamScene   # 백 노인의 시험 (49-3)
            self.react_line = None
            self.shop = ExamScene(self.game, self.fishing, self, letter=item == "letter")
            self.game.scenes.push(self.shop)
        elif item == "leave":
            self._begin_leave()

    def _open_shop(self, mode: str, tabs: list | None = None, tab: str | None = None) -> None:
        from src.scene.shop import ShopScene
        tabs = tabs or self.c["shop_tabs"][mode]
        g = self.game.guide
        if mode == "buy" and g.run is not None and g.run["id"] == "TG-18" and "sell" not in tabs:
            tabs = ["sell"] + list(tabs)   # 특수 찌 튜토리얼: 돈이 모자라면 같은 창에서 팔 수 있게
        title = {"buy": "사기", "sell": "팔기", "scalestone": "비늘석"}[mode]
        frame = (8, 6, 464, 258) if mode == "scalestone" else (130, 6, 342, 258)   # 비늘석 탭은 넓은 틀 (장착 칸 · 목록 · 상세)
        self.shop = ShopScene(self.game, self.fishing, tab=tab or tabs[0], frame=frame, host=self, tabs=tabs,
                              title=f"{self.nc['sign']} · {title}")
        self.react_line = None
        self.game.scenes.push(self.shop)

    def shop_closed(self) -> None:
        self.shop = None
        if self.react_line:
            self.say([(self.react_line[0], self.react_line[1])])
            self.react_line = None

    def _begin_leave(self, farewell: bool = True) -> None:
        from src.scene import dialogue
        self.wait_menu = False
        if farewell:
            seq = dialogue.pick_seq(self.game, self.npc, self.cont, kind="bye")
            self.queue.clear()
            self.line = None
            self.say(seq[:1] or [("neutral", "…")])
        self.leaving = -1.0   # 작별 대사가 끝나면 페이드 시작

    def _finish_leave(self) -> None:
        if self in self.game.scenes.stack:
            self.game.scenes.stack.remove(self)
        self.game.fade_in(self.c["fade_sec"] / 2)
        self.game.save_now()

    # ── 입력 ──
    def handle_event(self, event) -> None:
        if event.type == pygame.KEYDOWN and event.key in (pygame.K_UP, pygame.K_DOWN, pygame.K_w, pygame.K_s):
            items = self._menu_items()
            if self.wait_menu and items:
                d = -1 if event.key in (pygame.K_UP, pygame.K_w) else 1
                self.menu_sel = (self.menu_sel + d) % len(items)
                self.game.sfx.play("ui_click", 0.5)
            return
        super().handle_event(event)

    def handle_action(self, a) -> None:
        if self.fade_in > self.c["fade_sec"] * 0.5:
            return
        if a.name == "back":
            if self.leaving is None and not self.script:
                self._begin_leave()
            return
        if a.name == "drag" and self.wait_menu and self._menu_items():   # Q/E 로도 메뉴 이동
            self.menu_sel = (self.menu_sel + (1 if a.value > 0 else -1)) % len(self._menu_items())
            return
        if a.name == "confirm":
            self._advance(None)
        elif a.name == "primary":
            self._advance(a.pos)

    def _advance(self, pos) -> None:
        if self.leaving is not None and self.leaving >= 0:
            return
        if self.wait_menu:
            items = self._menu_items()
            if pos is None:
                if items:
                    self._choose(items[self.menu_sel])
                return
            for i, r in enumerate(self._menu_rects()):
                if r.collidepoint(pos):
                    self.menu_sel = i
                    self._choose(items[i])
                    return
            return
        if self.typing():
            self.shown = len(self._plain())     # 탭 1번: 전체 표시
            return
        if self.leaving == -1.0 and not self.queue:
            self.leaving = self.c["fade_sec"]
            return
        self._next()                             # 탭 2번: 다음 대사

    # ── 갱신 ──
    def update(self, dt: float) -> None:
        self.t += dt
        self.mouse = self.game.input.pointer   # 전체 화면 씬 (UI 상자 아님)
        self.fade_in = max(0.0, self.fade_in - dt)
        self.game.adaptive.set("menu")
        # 눈 깜빡임 (3~5초 랜덤)
        self.blink_t -= dt
        if self.blink_t <= 0:
            self.blink_left = self.c["blink_sec"]
            self.blink_t = self.rnd.uniform(*self.c["blink_every"])
        self.blink_left = max(0.0, self.blink_left - dt)
        self.yawn_left = max(0.0, self.yawn_left - dt)
        if self.npc == "haru" and self.wait_menu and self.shop is None and self.leaving is None and self._is_night():
            self.yawn_t -= dt
            if self.yawn_t <= 0:
                from src.render.village_life import cfg as vl_cfg
                c = vl_cfg()["night"]
                self.yawn_t = self.rnd.uniform(*c["yawn_every"])
                self.yawn_left = c["yawn_sec"]
        # 한 글자씩 + 말소리
        if self.typing() and self.fade_in <= 0:
            v = self.nc["voice"]
            cps = v.get("excited_cps", v["cps"]) if self.expr == "excited" else v["cps"]
            before = int(self.shown)
            self.shown = min(len(self._plain()), self.shown + cps * dt)
            plain = self._plain()
            for i in range(before, int(self.shown)):
                if plain[i].strip() and plain[i] not in "….,!?" and self.line[0] == self.npc:
                    self.voice_n += 1
                    if (self.voice_n - 1) % v["every"] == 0 and self.game.settings.get("voice_blips"):
                        self.game.sfx.play(f"{v['sound']}{self.rnd.randrange(3)}", v.get("vol", 0.5))
        elif self.leaving == -1.0 and self.line is not None and not self.typing():
            self.leave_wait += dt
            if self.leave_wait > 1.1:            # 작별 대사는 잠깐 보여 주고 저절로
                self.leaving = self.c["fade_sec"]
        if self.leaving is not None and self.leaving >= 0:
            self.leaving -= dt
            if self.leaving <= 0:
                self._finish_leave()

    # ── 그리기 ──
    def _geom(self, canvas) -> dict:
        w, h = canvas.get_size()
        top_h = h - BOX_H - 11
        cx = w // 2
        return {"w": w, "h": h, "top_h": top_h, "cx": cx,
                "talk": pygame.Rect(cx - 234, h - BOX_H - 6, 312, BOX_H),
                "menu": pygame.Rect(cx + 86, h - BOX_H - 6, 148, BOX_H)}

    def _menu_rects(self) -> list[pygame.Rect]:
        g = self._geom(self.game.screen.canvas)
        m = g["menu"]
        items = self._menu_items()
        step = min(17, (m.h - 8) // max(1, len(items)))
        return [pygame.Rect(m.x + 4, m.y + 4 + i * step, m.w - 8, step) for i in range(len(items))]

    def env(self, w: int, top_h: int) -> dict:
        from src.render.season_fx import season_palette
        from src.render.event_fx import event_palette
        from src.render.weather_fx import themed_palette
        from src.fishing import weather_events
        f = self.fishing
        pal = season_palette(themed_palette(f.palette.sample(f.clock.hour), {}, f.weather), self.season, self.cont)
        ev = weather_events.active(self.save)
        pal = event_palette(pal, ev["id"] if ev else None, self.cont)
        return {"w": w, "top_h": top_h, "t": self.t, "night": vr._night(f.clock.hour), "pal": pal,
                "season": self.season, "cont": self.cont,
                "flash": self.game.zones.window_flash if hasattr(self.game, "zones") else 0.0,   # 실내 천둥: 창밖 번쩍
                "exam_passed": self._exam_passed()}   # 백 노인 오두막 합격 목패 (49-5)

    def _exam_passed(self) -> int:
        from src.save import exam
        return exam.passed(self.save) if self.npc == "baek" and self.save is not None else 1

    def _portrait_img(self) -> pygame.Surface:
        if self.yawn_left > 0:   # 하품: 눈 감고 입 크게 (놀람 표정의 눈 감은 · 말하는 그림)
            return portrait(self.npc, "surprised", True, True)
        talking = self.typing() and self.line[0] == self.npc and int(self.t / self.c["mouth_sec"]) % 2 == 0
        if self.shop is not None and self.react_line and self.t - self.react_line[2] < 0.6:
            talking = int(self.t / self.c["mouth_sec"]) % 2 == 0
        return portrait(self.npc, self.expr, self.blink_left > 0, talking)

    def _breath(self) -> int:
        return 1 if math.sin(self.t * 2 * math.pi / self.c["breath_sec"]) > 0.3 else 0

    def draw_room(self, canvas, px: int | None = None) -> dict:
        """배경 + 초상화 + 카운터 + 조명 (px = 초상화 x, 기본 가운데)."""
        g = self._geom(canvas)
        env = self.env(g["w"], g["top_h"])
        canvas.fill((0, 0, 0))
        kind = self.nc["bg"]
        ir.draw_back(canvas, kind, env)
        x = g["cx"] - 64 if px is None else px
        canvas.blit(self._portrait_img(), (x, g["top_h"] - 153 + self._breath()))
        ir.draw_counter(canvas, kind, env)
        ir.draw_light(canvas, kind, env)
        return g

    def draw(self, canvas) -> None:
        g = self.draw_room(canvas)
        # 간판
        from src.story.story import player_name
        sign = self.nc["sign"].replace("{player}", player_name(self.save))
        sw = hud.get_font(11).size(sign)[0] + 16
        canvas.fill(SIGN_BG, (8, 7, sw, 18))
        text(canvas, sign, (16, 16), SIGN_FG, 11, "midleft")
        # 대화창 + 메뉴
        self._draw_talk(canvas, g["talk"])
        if self.menu_on and self.leaving is None:
            self._draw_menu(canvas, g["menu"])
            from src.tutorial import targets as T
            for it, rr in zip(self._menu_items(), self._menu_rects()):
                T.mark(f"interior.menu.{it}", rr)
        from src.tutorial import targets as T
        T.mark("interior.portrait", (g["cx"] - 56, g["top_h"] - 150, 112, 140))
        if self.yawn_left > 0:   # 하품 글자: 초상화 옆에서 떠오르며 흐려짐
            from src.render.village_life import cfg as vl_cfg
            u = 1 - self.yawn_left / vl_cfg()["night"]["yawn_sec"]
            a = min(1.0, (1 - u) / 0.3)
            text(canvas, "하아암~", (g["cx"] + 58, g["top_h"] - 118 - int(u * 10)), tuple(int(v * a) for v in (255, 240, 210)), 11,
                 "midleft", shadow=True)
        self._draw_fade(canvas)
        draw_cursor(canvas, self.mouse)

    def _box(self, canvas, r) -> None:
        canvas.fill((0, 0, 0), r)
        pygame.draw.rect(canvas, (255, 255, 255), r, 2)

    def _draw_talk(self, canvas, r) -> None:
        self._box(canvas, r)
        if not self.line:
            return
        who = self.line[0]
        y = r.y + 12
        if who is not None:
            nm = self.name if who == self.npc else load_json("villages.json")[self.cont]["npcs"].get(who, {}).get("name", who)
            text(canvas, nm, (r.x + 12, y), NAME_COL, 11, "midleft")
            col = (255, 255, 255)
        else:
            col = (200, 205, 220)   # 자막 (주인공 속마음)
        rows = hud.wrap_rich(self._text(), r.w - 24)[:2]   # 대사창 최대 2줄
        left = int(self.shown)
        for j, ln in enumerate(rows):
            hud.rich_text(canvas, ln, (r.x + 12, y + 20 + j * 18), col, 11, "midleft", visible=max(0, left))
            left -= len(hud.strip_tags(ln))
        if not self.typing() and (self.queue or (not self.wait_menu and self.leaving is None)) and int(self.t * 3) % 2:
            pygame.draw.polygon(canvas, (255, 255, 255), [(r.right - 16, r.bottom - 12), (r.right - 8, r.bottom - 12),
                                                         (r.right - 12, r.bottom - 7)])

    def _draw_menu(self, canvas, r) -> None:
        self._box(canvas, r)
        names = self.c["menu_names"]
        items = self._menu_items()
        active = self.wait_menu
        for i, (it, rr) in enumerate(zip(items, self._menu_rects())):
            if active and rr.collidepoint(self.mouse):
                self.menu_sel = i
            sel = active and i == self.menu_sel
            col = NAME_COL if sel else ((255, 255, 255) if active else (120, 120, 130))
            text(canvas, names[it], (rr.x + 22, rr.centery), col, 11, "midleft")
            if sel:
                self._bobber(canvas, rr.x + 8, rr.centery - 4)

    def _bobber(self, canvas, x: int, y: int) -> None:
        """메뉴 커서: 작은 찌 (빨강·흰색), 살짝 까딱."""
        y += int(math.sin(self.t * 5) * 1)
        canvas.fill((221, 221, 221), (x + 2, y - 3, 1, 3))
        canvas.fill((255, 255, 255), (x, y, 5, 4))
        canvas.fill((232, 74, 74), (x, y + 4, 5, 4))

    def _draw_fade(self, canvas) -> None:
        a = 0.0
        fs = self.c["fade_sec"]
        if self.fade_in > 0:
            a = self.fade_in / fs
        if self.leaving is not None and self.leaving >= 0:
            a = max(a, 1 - self.leaving / fs)
        if a > 0:
            s = pygame.Surface(canvas.get_size())
            s.fill(self.fade_col)
            s.set_alpha(int(255 * min(1.0, a)))
            canvas.blit(s, (0, 0))

    # ── 상점 패널 뒤 (ShopScene 이 부름) ──
    def draw_shop_backdrop(self, canvas) -> None:
        """상점 패널이 열려 있을 때: 같은 방 + 초상화는 왼쪽 창에, 그 아래 반응 대사."""
        ui_r = self.game.screen.ui_rect
        self.draw_room(canvas, px=ui_r.x + 2)
        canvas.fill((0, 0, 0), (0, canvas.get_height() - BOX_H - 11, canvas.get_width(), BOX_H + 11))
        box = pygame.Rect(ui_r.x + 6, ui_r.bottom - BOX_H - 6, 120, BOX_H)
        self._box(canvas, box)
        text(canvas, self.name, (box.x + 8, box.y + 12), NAME_COL, 11, "midleft")
        if self.react_line:
            for j, ln in enumerate(hud.wrap_rich(self.react_line[1], box.w - 16)[:4]):
                hud.rich_text(canvas, ln, (box.x + 8, box.y + 28 + j * 15), (255, 255, 255), 11, "midleft")
