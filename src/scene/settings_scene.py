"""설정: 음량, 화면 연출, 화면 배율(PC) / 터치 버튼 크기·투명도·왼손잡이(모바일), 튜토리얼 다시 보기, 소리 자막."""
import pygame

from src.platform.detect import IS_MOBILE
from src.scene.base import Scene
from src.ui import widgets as ui
from src.ui.hud import draw_cursor, text


class SettingsScene(Scene):
    UI_FRAME = True

    def __init__(self, game):
        super().__init__(game)
        self.mouse = (0, 0)
        self.msg = ""
        self.msg_t = 0.0
        w = game.screen.ui_rect.w
        self.x0 = w // 2 - 140
        rows_y = [66, 92, 118, 144, 170]
        x = self.x0 + 150
        self.buttons = [
            ui.Button((x, rows_y[0] - 8, 18, 16), "-", lambda: self._volume(-0.1)),
            ui.Button((x + 104, rows_y[0] - 8, 18, 16), "+", lambda: self._volume(0.1)),
            ui.Button((x, rows_y[1] - 8, 122, 16), "", self._toggle_fx),
            ui.Button((x, rows_y[2] - 8, 18, 16), "-", lambda: self._scale(-1)),
            ui.Button((x + 104, rows_y[2] - 8, 18, 16), "+", lambda: self._scale(1)),
            ui.Button((x, rows_y[3] - 8, 122, 16), "처음부터 다시 보기", self._reset_tutorial),
            ui.Button((x, rows_y[4] - 8, 122, 16), "", self._toggle_captions),
            ui.Button((w // 2 - 40, 212, 80, 18), "뒤로", self._back),
        ]
        self.rows_y = rows_y
        self.labels = ["음량", "화면 연출 (흔들림·줌)", "화면 배율", "튜토리얼", "소리 자막 (예고음 글자로)"]
        if IS_MOBILE:
            self._mobile_rows(w)

    def _mobile_rows(self, w: int) -> None:
        """모바일: 화면 배율 대신 터치 버튼 크기·투명도·왼손잡이 (MOBILE.md 1번)."""
        self.rows_y = rows_y = [62, 84, 106, 128, 150, 172, 194]
        x = self.x0 + 150
        self.labels = ["음량", "화면 연출 (흔들림·줌)", "터치 버튼 크기", "터치 버튼 진하기", "왼손잡이 (버튼 좌우 반전)",
                       "튜토리얼", "소리 자막 (예고음 글자로)"]
        self.buttons = [
            ui.Button((x, rows_y[0] - 8, 18, 16), "-", lambda: self._volume(-0.1)),
            ui.Button((x + 104, rows_y[0] - 8, 18, 16), "+", lambda: self._volume(0.1)),
            ui.Button((x, rows_y[1] - 8, 122, 16), "", self._toggle_fx),
            ui.Button((x, rows_y[2] - 8, 18, 16), "-", lambda: self._step("touch_size", -1)),
            ui.Button((x + 104, rows_y[2] - 8, 18, 16), "+", lambda: self._step("touch_size", 1)),
            ui.Button((x, rows_y[5] - 8, 122, 16), "처음부터 다시 보기", self._reset_tutorial),
            ui.Button((x, rows_y[6] - 8, 122, 16), "", self._toggle_captions),
            ui.Button((w // 2 - 40, 218, 80, 18), "뒤로", self._back),
            ui.Button((x, rows_y[3] - 8, 18, 16), "-", lambda: self._step("touch_alpha", -1)),
            ui.Button((x + 104, rows_y[3] - 8, 18, 16), "+", lambda: self._step("touch_alpha", 1)),
            ui.Button((x, rows_y[4] - 8, 122, 16), "", lambda: self.s.set("touch_left", not self.s.get("touch_left"))),
        ]

    def _step(self, key: str, d: int) -> None:
        self.s.set(key, max(0, min(2, self.s.get(key) + d)))

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

    def _toggle_captions(self) -> None:
        self.s.set("sound_captions", not self.s.get("sound_captions"))

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

    def handle_action(self, a) -> None:
        if a.name == "back":
            self._back()
        elif a.name == "primary":
            m = a.pos
            for b in self.buttons:
                if b.click(m):
                    self.game.sfx.play("click")
                    break

    def update(self, dt: float) -> None:
        self.mouse = self.ui_pointer()
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
        canvas = self.ui_canvas(canvas)
        w = canvas.get_width()
        ui.panel(canvas, (self.x0 - 10, 30, 300, 210 if not IS_MOBILE else 216))
        text(canvas, "설정", (w // 2, 44), ui.ACCENT, 16, "center")
        for y, label in zip(self.rows_y, self.labels):
            text(canvas, label, (self.x0, y), ui.TEXT, 11, "midleft")
        x = self.x0 + 150
        ui.bar(canvas, (x + 22, self.rows_y[0] - 4, 78, 8), self.s.get("volume"), (140, 200, 255))
        self.buttons[2].label = "켬" if self.s.get("screen_shake") else "끔"
        self.buttons[6].label = "켬" if self.s.get("sound_captions") else "끔"
        if IS_MOBILE:
            names = ("작게", "보통", "크게"), ("흐리게", "보통", "진하게")
            text(canvas, names[0][self.s.get("touch_size")], (x + 61, self.rows_y[2]), ui.TEXT, 11, "center")
            text(canvas, names[1][self.s.get("touch_alpha")], (x + 61, self.rows_y[3]), ui.TEXT, 11, "center")
            self.buttons[10].label = "켬" if self.s.get("touch_left") else "끔"
        else:
            text(canvas, f"{self.game.screen.scale}배 (최대 {self._max_scale()})", (x + 61, self.rows_y[2]), ui.TEXT, 11,
                 "center")
        for b in self.buttons:
            b.draw(canvas, self.mouse)
        if self.msg_t > 0:
            text(canvas, self.msg, (w // 2, 192), ui.GOOD, 11, "center")
        draw_cursor(canvas, self.mouse)
