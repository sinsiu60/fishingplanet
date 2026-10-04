"""모바일 '가방' 버튼: 인벤토리·지도·상점·도감·보물상자·의뢰·도움말을 큰 버튼으로 (PC는 단축키 I/M/B/Tab/C/J/H)."""
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
        self.collect = False   # '수집'을 누르면 같은 판이 도감·업적·어탁·수조로 바뀜
        items = [("인벤토리", "inventory"), ("지도", "map"), ("상점", "shop"), ("수집", "collection"), ("보물상자", "chest"),
                 ("의뢰", "quests")]
        bw, bh, gap = 104, 32, 6
        x0 = 240 - (bw * 3 + gap * 2) // 2
        self.buttons = []
        for i, (label, which) in enumerate(items):
            x, y = x0 + (i % 3) * (bw + gap), 66 + (i // 3) * (bh + gap)
            self.buttons.append(ui.Button((x, y, bw, bh), label, lambda w=which: self._open(w), size=16))
        y = 66 + 2 * (bh + gap)
        self.buttons.append(ui.Button((x0 + bw + gap, y, bw, bh), "도움말", self._help, size=16))
        self.buttons.append(ui.Button((240 - bw // 2, y + bh + gap, bw, 28), "닫기", self._close))
        sub = [("도감", "dex"), ("업적", "achievements"), ("어탁", "prints"), ("수조", "tank")]
        self.sub_buttons = []
        for i, (label, which) in enumerate(sub):
            x, y2 = 240 - (bw * 2 + gap) // 2 + (i % 2) * (bw + gap), 66 + (i // 2) * (bh + gap)
            self.sub_buttons.append(ui.Button((x, y2, bw, bh), label, lambda w=which: self._open(w), size=16))
        self.sub_buttons.append(ui.Button((240 - bw // 2, 66 + 2 * (bh + gap) + bh + gap, bw, 28), "뒤로", self._back))

    def _back(self) -> None:
        self.collect = False

    @property
    def active(self) -> list:
        return self.sub_buttons if self.collect else self.buttons

    def _open(self, which: str) -> None:
        if which == "collection":
            self.collect = True
            return
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
            for b in self.active:
                if b.click(a.pos):
                    self.game.sfx.play("ui_click")
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
        text(canvas, "수집" if self.collect else "가방", (240, 50), ui.ACCENT, 16, "center")
        from src.tutorial import targets
        for b in self.active:
            b.draw(canvas, self.mouse)
            tid = {"수집": "fish.quick.collection", "도감": "fish.quick.dex"}.get(b.label)
            if tid:
                targets.mark_ui(self, tid, b.rect)
