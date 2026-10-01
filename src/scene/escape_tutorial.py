"""엘드라시온 최초 도주 튜토리얼 팝업 (EXPANSION.md 7-4 문구 그대로, 대륙명은 데이터에서)."""
import pygame

from src.core.config import load_json
from src.scene.base import Scene
from src.ui import widgets as ui
from src.ui.hud import draw_cursor, text, wrap_text


def _lines(continent: str, float_name: str) -> list[str]:
    return [
        "지친 물고기가 갑자기 도망가서 당황스러우셨나요?",
        "",
        f"{continent}의 물고기들은 모두 강인한 체력을 가지고 있어, 일반적인 장비로는 잡아낼 수 없습니다.",
        "아무리 지쳐 보여도, 뭍에 끌려오기 직전 마지막 힘을 짜내 줄을 끊고 달아나 버리죠.",
        "",
        f"이 대륙에서 낚시를 하려면 물고기의 마지막 발악을 잠재울 특수 찌가 필요합니다.",
        f"{continent} 상점에서 [{float_name}]를 구매해 장착해 보세요!",
    ]


class EscapeTutorialScene(Scene):
    def __init__(self, game, fishing):
        super().__init__(game)
        self.fishing = fishing
        self.mouse = (0, 0)
        self.age = 0.0
        cont = next(c["name"] for c in load_json("continents.json")["continents"] if c["id"] == "eldrasion")
        first = next(f["name"] for f in load_json("floats.json")["floats"] if f["tier"] == 1)
        self.continent = cont.replace(" 대륙", "")
        self.lines = _lines(self.continent, first)
        self.buttons = [ui.Button((134, 214, 100, 18), "상점으로 가기", self._shop),
                        ui.Button((246, 214, 100, 18), "닫기", self._close)]

    def _finish(self) -> None:
        self.game.scenes.pop()
        if self.fishing.fight is not None:
            self.fishing._end_fight()

    def _shop(self) -> None:
        self._finish()
        self.fishing.open_menu("shop", tab="float")

    def _close(self) -> None:
        self._finish()

    def handle_event(self, event) -> None:
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and self.age > 0.4:
            m = self.game.to_canvas(event.pos)
            for b in self.buttons:
                if b.click(m):
                    self.game.sfx.play("click")
                    return
        elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE and self.age > 0.4:
            self._close()

    def update(self, dt: float) -> None:
        self.age += dt
        self.mouse = self.game.to_canvas(pygame.mouse.get_pos())

    def draw(self, canvas) -> None:
        self.fishing.draw(canvas)
        ui.dim(canvas, int(170 * min(1.0, self.age / 0.2)))
        box = pygame.Rect(40, 36, 400, 204)
        ui.panel(canvas, box, border=(255, 214, 120))
        text(canvas, "특수 찌가 필요해요", (box.centerx, box.y + 14), (255, 214, 120), 16, "center")
        y = box.y + 34
        for ln in self.lines:
            if not ln:
                y += 6
                continue
            for part in wrap_text(ln, box.w - 24):
                text(canvas, part, (box.x + 12, y), ui.TEXT, 11, "midleft")
                y += 13
        for b in self.buttons:
            b.draw(canvas, self.mouse)
        draw_cursor(canvas, self.mouse)
