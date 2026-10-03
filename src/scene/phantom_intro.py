"""첫 환상어 포획 안내 (DESIGN.md 33장 P6): 포획 컷이 끝난 뒤 한 번. 이때 도감 [환상] 탭이 처음 생긴다."""
import math

import pygame

from src.core.config import load_json
from src.fishing import phantom
from src.scene.base import Scene
from src.ui import widgets as ui
from src.ui.hud import draw_cursor, text, wrap_text


class PhantomIntroScene(Scene):
    UI_FRAME = True

    def __init__(self, game, fishing):
        super().__init__(game)
        self.fishing = fishing
        self.mouse = (0, 0)
        self.age = 0.0
        tut = load_json("phantom_hints.json")["tutorial"]
        self.title, self.lines = tut["title"], tut["lines"]
        phantom.state(game.save)["tutorial"] = True  # 튜토리얼 표시 여부 저장 (탭·업적·칭호 공개)
        game.save_now()
        w = game.screen.ui_rect.w
        self.btn_dex = ui.Button((w // 2 - 116, 214, 110, 18), "환상 도감 보기", self._dex)
        self.btn_close = ui.Button((w // 2 + 6, 214, 110, 18), "닫기", self._close)

    def _close(self) -> None:
        self.game.scenes.pop()

    def _dex(self) -> None:
        from src.scene.dex import DexScene
        self.game.scenes.pop()
        self.game.scenes.push(DexScene(self.game, self.fishing, phantom_tab=True))

    def handle_action(self, a) -> None:
        if a.name == "back":
            self._close()
        elif a.name == "primary" and self.age > 0.4:
            for b in (self.btn_dex, self.btn_close):
                if b.click(a.pos):
                    self.game.sfx.play("ui_click")
                    break

    def update(self, dt: float) -> None:
        self.age += dt
        self.mouse = self.ui_pointer()

    def draw(self, canvas) -> None:
        self.fishing.draw(canvas)
        ui.dim(canvas, int(190 * min(1.0, self.age / 0.3)))
        canvas = self.ui_canvas(canvas)
        w = canvas.get_width()
        box = pygame.Rect(w // 2 - 200, 30, 400, 210)
        canvas.fill((12, 8, 24), box)
        k = 0.6 + 0.4 * math.sin(self.age * 2.5)
        pygame.draw.rect(canvas, (int(110 + 80 * k), int(70 + 50 * k), 255), box, 2)
        pygame.draw.rect(canvas, (80, 50, 120), box.inflate(-6, -6), 1)
        text(canvas, self.title, (w // 2, box.y + 18), phantom.COLOR_LIGHT, 16, "center")
        y = box.y + 42
        for ln in self.lines:
            if not ln:
                y += 6
                continue
            for sub in wrap_text(ln, box.w - 28):
                bold = "환상의 물고기" in sub or "[환상]" in sub
                text(canvas, sub, (w // 2, y), (235, 220, 255) if bold else (210, 214, 230), 11, "center")
                y += 14
        self.btn_dex.draw(canvas, self.mouse)
        self.btn_close.draw(canvas, self.mouse)
        draw_cursor(canvas, self.mouse)
