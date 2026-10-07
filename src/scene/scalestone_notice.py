"""장비 강화 → 비늘석 안내 (SCALESTONE.md 기존 세이브, DESIGN.md 46장 S4): 옛 세이브를 처음 불러올 때 한 번.

"장비 강화가 비늘석으로 바뀌었어요! 강화에 쓴 골드와 소재는 모두 돌려드렸어요." + 환영 선물 희귀 비늘석 1개.
세이브 scalestone.welcome = {"pending", "gold", "mat", "gift" (비늘석 uid)} — 닫으면 pending = False.
"""
from src.save import scalestone as ss
from src.scene.base import Scene
from src.ui import scalestone_ui as sui
from src.ui import widgets as ui
from src.ui.hud import rich_text, text


def pending(save) -> bool:
    return bool(save.data.get("scalestone", {}).get("welcome", {}).get("pending"))


class ScalestoneNoticeScene(Scene):
    UI_FRAME = True

    def __init__(self, game):
        super().__init__(game)
        self.mouse = (-100, -100)
        self.info = game.save.data["scalestone"]["welcome"]
        self.stone = ss.by_uid(game.save, self.info.get("gift"))
        self.button = ui.Button((240 - 50, 196, 100, 22), "확인", self._close, size=13)
        game.sfx.play("ui_ss_lock", 0.6)

    def _close(self) -> None:
        self.info["pending"] = False
        self.game.save.save()
        self.game.scenes.pop()

    def handle_action(self, a) -> None:
        if a.name in ("back", "confirm"):
            self._close()
        elif a.name == "primary" and self.button.click(a.pos):
            self.game.sfx.play("ui_click")

    def update(self, dt: float) -> None:
        self.mouse = self.ui_pointer()

    def draw(self, canvas) -> None:
        under = self.scene_below()
        if under is not None:
            under.draw(canvas)
        ui.dim(canvas, 170)
        canvas = self.ui_canvas(canvas)
        ui.panel(canvas, (240 - 170, 50, 340, 178))
        rich_text(canvas, "장비 강화가 {gold}비늘석{/}으로 바뀌었어요!", (240, 70), ui.TEXT, 13, "center")
        text(canvas, "강화에 쓴 골드와 소재는 모두 돌려드렸어요.", (240, 90), ui.TEXT, 11, "center")
        if self.info.get("gold") or self.info.get("mat"):
            text(canvas, f"돌려받음: {ui.money_text(self.info.get('gold', 0))} · 소재 {self.info.get('mat', 0)}개",
                 (240, 106), ui.DIM, 11, "center")
        text(canvas, "환영 선물", (240, 126), ui.ACCENT, 11, "center")
        if self.stone is not None:
            g = ss.grade_info(self.stone["grade"])
            img = sui.icon(self.stone["grade"])
            canvas.blit(img, (240 - 16, 138))
            text(canvas, f"{g['name']} 비늘석 · {ss.option_text(self.stone['opts'][0])}", (240, 178), tuple(g["color"]), 11, "center")
        self.button.draw(canvas, self.mouse)
