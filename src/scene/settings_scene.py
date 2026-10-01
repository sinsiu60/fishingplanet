"""설정: 음량, 화면 연출, 화면 배율, 튜토리얼 다시 보기."""
import pygame

from src.scene.base import Scene
from src.ui import widgets as ui
from src.ui.hud import draw_cursor, text


class SettingsScene(Scene):
    def __init__(self, game):
        super().__init__(game)
        self.mouse = (0, 0)
        self.msg = ""
        self.msg_t = 0.0
        w = game.screen.width
        self.x0 = w // 2 - 140
        rows_y = [70, 100, 130, 160]
        x = self.x0 + 150
        self.buttons = [
            ui.Button((x, rows_y[0] - 8, 18, 16), "-", lambda: self._volume(-0.1)),
            ui.Button((x + 104, rows_y[0] - 8, 18, 16), "+", lambda: self._volume(0.1)),
            ui.Button((x, rows_y[1] - 8, 122, 16), "", self._toggle_fx),
            ui.Button((x, rows_y[2] - 8, 18, 16), "-", lambda: self._scale(-1)),
            ui.Button((x + 104, rows_y[2] - 8, 18, 16), "+", lambda: self._scale(1)),
            ui.Button((x, rows_y[3] - 8, 122, 16), "처음부터 다시 보기", self._reset_tutorial),
            ui.Button((w // 2 - 40, 212, 80, 18), "뒤로", self._back),
        ]
        self.rows_y = rows_y

    @property
    def s(self):
        return self.game.settings

    def _volume(self, d: float) -> None:
        v = round(min(1.0, max(0.0, self.s.get("volume") + d)), 1)
        self.s.set("volume", v)
        self.game.sfx.volume = v

    def _toggle_fx(self) -> None:
        self.s.set("screen_shake", not self.s.get("screen_shake"))
        for scene in self.game.scenes.stack:
            if hasattr(scene, "apply_settings"):
                scene.apply_settings()

    def _max_scale(self) -> int:
        return max(1, self.game.screen._best_scale())

    def _scale(self, d: int) -> None:
        cur = self.game.screen.scale
        new = min(self._max_scale(), max(1, cur + d))
        if new != cur:
            self.game.screen.set_scale(new)
            self.s.set("scale", new)

    def _reset_tutorial(self) -> None:
        self.s.set("tutorial_seen", [])
        for scene in self.game.scenes.stack:
            if hasattr(scene, "tutorial"):
                scene.tutorial.seen.clear()
        self.msg, self.msg_t = "튜토리얼을 처음부터 다시 보여드려요", 2.0

    def _back(self) -> None:
        self.game.scenes.pop()

    def handle_event(self, event) -> None:
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self._back()
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            m = self.game.to_canvas(event.pos)
            for b in self.buttons:
                if b.click(m):
                    self.game.sfx.play("click")
                    break

    def update(self, dt: float) -> None:
        self.mouse = self.game.to_canvas(pygame.mouse.get_pos())
        self.msg_t = max(0.0, self.msg_t - dt)
        under = self.game.scenes.stack[0]
        if hasattr(under, "bg"):
            under.bg.update(dt)

    def draw(self, canvas) -> None:
        stack = self.game.scenes.stack
        under = stack[-2] if len(stack) >= 2 else None
        if under is not None:
            under.draw(canvas)
        ui.dim(canvas, 170)
        w = canvas.get_width()
        ui.panel(canvas, (self.x0 - 10, 30, 300, 210))
        text(canvas, "설정", (w // 2, 44), ui.ACCENT, 16, "center")
        labels = ["음량", "화면 연출 (흔들림·줌)", "화면 배율", "튜토리얼"]
        for y, label in zip(self.rows_y, labels):
            text(canvas, label, (self.x0, y), ui.TEXT, 11, "midleft")
        x = self.x0 + 150
        ui.bar(canvas, (x + 22, self.rows_y[0] - 4, 78, 8), self.s.get("volume"), (140, 200, 255))
        self.buttons[2].label = "켬" if self.s.get("screen_shake") else "끔"
        text(canvas, f"{self.game.screen.scale}배 (최대 {self._max_scale()})", (x + 61, self.rows_y[2]), ui.TEXT, 11,
             "center")
        for b in self.buttons:
            b.draw(canvas, self.mouse)
        if self.msg_t > 0:
            text(canvas, self.msg, (w // 2, 192), ui.GOOD, 11, "center")
        draw_cursor(canvas, self.mouse)
