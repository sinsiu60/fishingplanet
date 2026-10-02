"""모바일 '가방' 버튼: 지도·상점·도감·보물상자·의뢰·도움말을 큰 버튼으로 (PC는 단축키 M/B/Tab/C/J/H)."""
from src.scene.base import Scene
from src.ui import widgets as ui
from src.ui.hud import text


class QuickMenuScene(Scene):
    UI_FRAME = True

    def __init__(self, game, fishing):
        super().__init__(game)
        self.fishing = fishing
        self.mouse = (-100, -100)
        self.age = 0.0
        items = [("지도", "map"), ("상점", "shop"), ("도감", "dex"), ("보물상자", "chest"), ("의뢰", "quests")]
        bw, bh, gap = 104, 36, 8
        x0 = 240 - (bw * 3 + gap * 2) // 2
        self.buttons = []
        for i, (label, which) in enumerate(items):
            x, y = x0 + (i % 3) * (bw + gap), 70 + (i // 3) * (bh + gap)
            self.buttons.append(ui.Button((x, y, bw, bh), label, lambda w=which: self._open(w), size=16))
        x, y = x0 + 2 * (bw + gap), 70 + (bh + gap)
        self.buttons.append(ui.Button((x, y, bw, bh), "도움말", self._help, size=16))
        self.buttons.append(ui.Button((240 - bw // 2, 70 + 2 * (bh + gap), bw, 30), "닫기", self._close))

    def _open(self, which: str) -> None:
        self.game.scenes.pop()
        self.fishing.open_menu(which)

    def _help(self) -> None:
        self.game.scenes.pop()
        self.fishing.help = True

    def _close(self) -> None:
        self.game.scenes.pop()

    def handle_action(self, a) -> None:
        if a.name in ("back", "menu"):
            self._close()
        elif a.name == "primary":
            for b in self.buttons:
                if b.click(a.pos):
                    self.game.sfx.play("click")
                    return
            self._close()  # 바깥을 누르면 닫기

    def update(self, dt: float) -> None:
        self.age += dt
        self.mouse = self.ui_pointer()

    def draw(self, canvas) -> None:
        self.fishing.draw(canvas)
        ui.dim(canvas, int(150 * min(1.0, self.age / 0.15)))
        canvas = self.ui_canvas(canvas)
        ui.panel(canvas, (240 - 176, 34, 352, 194))
        text(canvas, "가방", (240, 50), ui.ACCENT, 16, "center")
        for b in self.buttons:
            b.draw(canvas, self.mouse)
