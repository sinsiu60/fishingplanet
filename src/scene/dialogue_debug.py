"""대사 확인 화면 (DESIGN.md 35-12): NPC별 대사 목록·조건·지금 나올 수 있는지, 조건을 강제로 바꿔 미리보기.
설정 → 접근성 → 테스트: NPC 대사. 미리보기는 들은 기록을 남기지 않는다."""
import pygame

from src.core import season as seasons
from src.scene import dialogue
from src.scene.base import Scene
from src.ui import widgets as ui
from src.ui.hud import draw_cursor, text, wrap_text

NPCS = (("haru", "하루"), ("baek", "백 노인"), ("sora", "소라"), ("gull", "갈매기 박사"), ("ella", "엘라"), ("oren", "오렌"))
EVENTS = (None, "meteor", "double_rainbow", "red_moon", "silver_fog")
PERIODS = (None, "morning", "day", "evening", "night")
PER = 13


class DialogueDebugScene(Scene):
    UI_FRAME = True

    def __init__(self, game):
        super().__init__(game)
        self.mouse = (0, 0)
        self.npc = 0
        self.page = 0
        self.ov = {"season": None, "period": None, "event": None, "phantom_tutorial": None}
        self.preview = None
        self.tabs = ui.Tabs(10, 10, [n for _, n in NPCS], width=58)
        self.btns = [ui.Button((10, 234, 70, 14), "", lambda: self._cyc("season", (None,) + seasons.SEASONS)),
                     ui.Button((84, 234, 70, 14), "", lambda: self._cyc("period", PERIODS)),
                     ui.Button((158, 234, 92, 14), "", lambda: self._cyc("event", EVENTS)),
                     ui.Button((254, 234, 70, 14), "", lambda: self._cyc("phantom_tutorial", (None, False, True))),
                     ui.Button((328, 234, 70, 14), "미리보기", self._preview),
                     ui.Button((404, 252, 64, 14), "뒤로", lambda: self.game.scenes.pop()),
                     ui.Button((402, 234, 66, 14), "다음 쪽", self._next)]

    def _cyc(self, key, values):
        cur = self.ov[key]
        self.ov[key] = values[(values.index(cur) + 1) % len(values)]

    def _next(self):
        n = len(self._list())
        self.page = (self.page + 1) % max(1, (n + PER - 1) // PER)

    def _ctx(self):
        return dialogue.context(self.game, None, dict(self.ov))

    def _list(self):
        return [ln for ln in dialogue.lines() if ln["npc"] == NPCS[self.npc][0]]

    def _preview(self):
        ln = dialogue.choose(self.game.save, NPCS[self.npc][0], self._ctx(), commit=False)
        self.preview = ln["text"] if ln else "(조건에 맞는 대사 없음)"

    def handle_action(self, a):
        if a.name == "back":
            self.game.scenes.pop()
        elif a.name == "primary":
            if self.tabs.click(a.pos):
                self.npc, self.page, self.preview = self.tabs.index, 0, None
                return
            for b in self.btns:
                if b.click(a.pos):
                    return

    def update(self, dt):
        self.mouse = self.ui_pointer()

    def draw(self, canvas):
        below = self.scene_below()
        if below is not None:
            below.draw(canvas)
        c = self.ui_canvas(canvas)
        ui.panel(c, (4, 4, 472, 262))
        self.tabs.draw(c, self.mouse)
        save = self.game.save
        ctx = self._ctx()
        heard = set(dialogue.state(save)["heard"])
        lst = self._list()
        text(c, f"{len(lst)}개 · 지금: {ctx['season']} · {ctx['period']} · 이벤트 {ctx['event']}", (466, 34), ui.DIM, 11, "midright")
        for i, ln in enumerate(lst[self.page * PER:(self.page + 1) * PER]):
            y = 44 + i * 14
            ok = dialogue.cond_ok(ln["cond"], save, ctx)
            mark = ("●" if ok else "○") + (" 들음" if ln["id"] in heard else "")
            col = ui.GOOD if ok else ui.DIM
            text(c, f"{mark} p{ln['prio']}{'·1회' if ln['once'] else ''}", (10, y + 6), col, 11, "midleft")
            from src.scene.inventory import fit
            cond = ",".join(f"{k}={v}" for k, v in ln["cond"].items()) or "-"
            text(c, fit(cond, 116), (92, y + 6), (170, 170, 200), 11, "midleft")
            text(c, fit(ln["text"], 254), (214, y + 6), ui.TEXT if ok else ui.DIM, 11, "midleft")
        labels = (f"계절 {self.ov['season'] or '자동'}", f"때 {self.ov['period'] or '자동'}", f"이벤트 {self.ov['event'] or '없음'}",
                  f"환상 {'자동' if self.ov['phantom_tutorial'] is None else ('후' if self.ov['phantom_tutorial'] else '전')}")
        for b, lab in zip(self.btns, labels):
            b.label = lab
        for b in self.btns:
            b.draw(c, self.mouse)
        if self.preview:
            r = pygame.Rect(40, 200, 400, 30)
            c.fill((250, 246, 236), r)
            for j, ln in enumerate(wrap_text(self.preview, 390)[:2]):
                text(c, ln, (r.x + 6, r.y + 8 + j * 13), (40, 36, 30), 11, "midleft")
        draw_cursor(c, self.mouse)
