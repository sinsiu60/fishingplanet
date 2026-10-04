"""이동 컷신 테스트 룸 (DESIGN.md 35-3): 낚시터 12곳 × 첫 방문·재방문·마을 복귀·대륙 이동을 골라 바로 재생 (기록 안 남음).
설정 → 접근성 → 테스트: 이동 컷신 (게임 중에만 — 도착 화면을 그릴 낚시 장면이 필요)."""
from src.core.config import load_json
from src.scene.base import Scene
from src.ui import widgets as ui
from src.ui.hud import draw_cursor, text

KINDS = (("first", "첫 방문 (7초)"), ("revisit", "재방문 (2초)"), ("return", "마을 복귀 (2초)"), ("voyage", "대륙 이동 (4초)"))


class TravelTestScene(Scene):
    UI_FRAME = True

    def __init__(self, game):
        super().__init__(game)
        from src.scene.fishing_scene import FishingScene
        self.fishing = next((s for s in game.scenes.stack if isinstance(s, FishingScene)), None)
        self.spots = load_json("spots.json")["spots"]
        self.si, self.ki = 0, 0
        self.mouse = (0, 0)
        self.btns = [ui.Button((120, 50, 18, 16), "◀", lambda: self._spot(-1)),
                     ui.Button((342, 50, 18, 16), "▶", lambda: self._spot(1)),
                     ui.Button((140, 76, 200, 16), "", self._kind),
                     ui.Button((180, 104, 120, 20), "재생", self._play),
                     ui.Button((404, 250, 64, 15), "뒤로", lambda: self.game.scenes.pop())]

    def _spot(self, d):
        self.si = (self.si + d) % len(self.spots)

    def _kind(self):
        self.ki = (self.ki + 1) % len(KINDS)

    def _play(self):
        if self.fishing is None:
            return
        from src.scene.travel import TravelScene
        f = self.fishing
        sp = self.spots[self.si]
        kind = KINDS[self.ki][0]
        old_spot, old_back = f.spot_id, f.backdrop
        f.backdrop = None
        if kind in ("first", "revisit"):
            f._set_spot(sp["id"])

        def done():
            f._set_spot(old_spot)
            f.backdrop = old_back
        self.game.scenes.push(TravelScene(self.game, f, kind, spot_id=sp["id"], cont=sp.get("continent", "sharmion"),
                                          on_done=done))

    def handle_action(self, a):
        if a.name == "back":
            self.game.scenes.pop()
        elif a.name == "primary":
            for b in self.btns:
                if b.click(a.pos):
                    self.game.sfx.play("ui_click")
                    break

    def update(self, dt):
        self.mouse = self.ui_pointer()

    def draw(self, canvas):
        below = self.scene_below()
        if below is not None:
            below.draw(canvas)
        ui.dim(canvas, 170)
        c = self.ui_canvas(canvas)
        ui.panel(c, (100, 20, 280, 120))
        text(c, "이동 컷신 테스트", (240, 32), ui.ACCENT, 11, "center")
        if self.fishing is None:
            text(c, "게임 중에만 볼 수 있어요 (도착 화면이 필요)", (240, 80), ui.BAD, 11, "center")
            self.btns[-1].draw(c, self.mouse)
            draw_cursor(c, self.mouse)
            return
        sp = self.spots[self.si]
        text(c, f"{self.si + 1}/{len(self.spots)}  {sp['name']}", (240, 58), ui.TEXT, 11, "center")
        self.btns[2].label = KINDS[self.ki][1]
        for b in self.btns:
            b.draw(c, self.mouse)
        draw_cursor(c, self.mouse)
