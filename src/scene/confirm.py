"""예/아니오 확인 창 (모바일: 타이틀에서 뒤로 가기 → '종료할까요?')."""
from src.scene.base import Scene
from src.ui import widgets as ui
from src.ui.hud import text


class ConfirmScene(Scene):
    UI_FRAME = True

    def __init__(self, game, message: str, on_yes, yes: str = "예", no: str = "아니오"):
        super().__init__(game)
        self.message = message
        self.on_yes = on_yes
        self.mouse = (-100, -100)
        self.buttons = [ui.Button((240 - 110, 140, 100, 26), yes, self._yes, size=16),
                        ui.Button((240 + 10, 140, 100, 26), no, self._no, size=16)]

    def _yes(self) -> None:
        self.game.scenes.pop()
        self.on_yes()

    def _no(self) -> None:
        self.game.scenes.pop()

    def handle_action(self, a) -> None:
        if a.name == "back":
            self._no()
        elif a.name == "primary":
            for b in self.buttons:
                if b.click(a.pos):
                    self.game.sfx.play("ui_click")
                    return

    def update(self, dt: float) -> None:
        self.mouse = self.ui_pointer()
        under = self.game.scenes.stack[0]
        if hasattr(under, "bg"):
            under.bg.update(dt)

    def draw(self, canvas) -> None:
        under = self.scene_below()
        if under is not None:
            under.draw(canvas)
        ui.dim(canvas, 160)
        canvas = self.ui_canvas(canvas)
        ui.panel(canvas, (240 - 130, 90, 260, 90))
        text(canvas, self.message, (240, 114), ui.TEXT, 16, "center")
        for b in self.buttons:
            b.draw(canvas, self.mouse)
