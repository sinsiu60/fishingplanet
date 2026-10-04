"""설정 → '튜토리얼 다시 보기' 목록 (TUTORIAL.md 4번). 고르면 다음에 그 화면·낚시 때 다시 실행.

디버그(debug_keys·debug_build)면 각 줄에 [바로] 버튼 + 단계 번호(-/+) → 튜토리얼 ID·단계로 지금 바로 실행.
"""
from src.scene.base import Scene
from src.ui import widgets as ui
from src.ui.hud import draw_cursor, text

PER_PAGE = 8


class TutorialReplayScene(Scene):
    UI_FRAME = True

    def __init__(self, game):
        super().__init__(game)
        self.mouse = (0, 0)
        self.page = 0
        self.msg, self.msg_t = "", 0.0
        self.step = 0
        from src.story.debug import enabled
        self.debug = enabled()
        g = game.guide
        st = g.st()
        # 환상 비밀: 환상 튜토리얼은 본 뒤에만 목록에
        self.ids = [tid for tid in g.data if not (tid == "TG-PH" and tid not in st["done"])]
        self._build()

    def _build(self) -> None:
        w = self.game.screen.ui_rect.w
        self.x0 = w // 2 - 150
        ids = self.ids[self.page * PER_PAGE:(self.page + 1) * PER_PAGE]
        self.rows = []
        for i, tid in enumerate(ids):
            y = 74 + i * 18
            b = ui.Button((self.x0 + 196, y - 8, 52, 16), "다시 보기", lambda t=tid: self._replay(t))
            d = ui.Button((self.x0 + 252, y - 8, 40, 16), "바로", lambda t=tid: self._now(t)) if self.debug else None
            self.rows.append((tid, y, b, d))
        pages = max(1, (len(self.ids) + PER_PAGE - 1) // PER_PAGE)
        self.pages = pages
        self.buttons = [b for _, _, b, _ in self.rows] + [d for *_, d in self.rows if d is not None]
        self.prev = ui.Button((self.x0, 222, 40, 16), "◀", lambda: self._page(-1))
        self.next = ui.Button((self.x0 + 46, 222, 40, 16), "▶", lambda: self._page(1))
        self.back = ui.Button((w // 2 - 40, 222, 80, 18), "뒤로", self.game.scenes.pop)
        self.buttons += [self.prev, self.next, self.back]
        if self.debug:
            self.buttons += [ui.Button((self.x0 + 230, 222, 18, 16), "-", lambda: self._step(-1)),
                             ui.Button((self.x0 + 274, 222, 18, 16), "+", lambda: self._step(1))]

    def _page(self, d: int) -> None:
        self.page = (self.page + d) % self.pages
        self._build()

    def _step(self, d: int) -> None:
        self.step = max(0, min(20, self.step + d))

    def _replay(self, tid: str) -> None:
        st = self.game.guide.st()
        if tid not in st["replay"]:
            st["replay"].append(tid)
        self.msg, self.msg_t = "다음에 그 화면에서 다시 보여드려요 (낚시는 다음 낚시 때)", 2.5

    def _now(self, tid: str) -> None:
        """디버그: 설정을 닫고 그 튜토리얼의 그 단계부터 바로."""
        g = self.game.guide
        while type(self.game.scenes.current).__name__ in ("TutorialReplayScene", "SettingsScene", "PauseScene"):
            self.game.scenes.pop()
        g.force_debug = True
        g.start_now(tid)
        n = len(g.data[tid]["steps"])
        g.run["i"] = min(self.step, n - 1)
        g.st()["active"] = {"id": tid, "step": g.run["i"]}

    def handle_action(self, a) -> None:
        if a.name == "back":
            self.game.scenes.pop()
        elif a.name == "scroll":
            self._page(-1 if a.value > 0 else 1)
        elif a.name == "primary":
            for b in self.buttons:
                if b.click(a.pos):
                    self.game.sfx.play("ui_click")
                    break

    def update(self, dt: float) -> None:
        self.mouse = self.ui_pointer()
        self.msg_t = max(0.0, self.msg_t - dt)

    def draw(self, canvas) -> None:
        under = self.scene_below()
        if under is not None:
            under.draw(canvas)
        ui.dim(canvas, 170)
        canvas = self.ui_canvas(canvas)
        w = canvas.get_width()
        ui.panel(canvas, (self.x0 - 10, 30, 320, 218))
        text(canvas, "튜토리얼 다시 보기", (w // 2, 44), ui.ACCENT, 16, "center")
        g = self.game.guide
        st = g.st()
        for tid, y, b, d in self.rows:
            done = tid in st["done"]
            mark = "↻" if tid in st["replay"] else ("✓" if done else "·")
            text(canvas, f"{mark} {g.data[tid]['title']}", (self.x0, y), ui.TEXT if done else (150, 156, 175), 11,
                 "midleft")
            b.draw(canvas, self.mouse)
            if d is not None:
                d.draw(canvas, self.mouse)
        for b in (self.prev, self.next, self.back):
            b.draw(canvas, self.mouse)
        text(canvas, f"{self.page + 1}/{self.pages}", (self.x0 + 100, 230), ui.TEXT, 11, "midleft")
        if self.debug:
            for b in self.buttons[-2:]:
                b.draw(canvas, self.mouse)
            text(canvas, f"단계 {self.step}", (self.x0 + 261, 230), ui.TEXT, 11, "center")
        if self.msg_t > 0:
            text(canvas, self.msg, (w // 2, 210), ui.GOOD, 11, "center")
        draw_cursor(canvas, self.mouse)
