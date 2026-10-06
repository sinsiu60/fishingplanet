"""시우 공방 크레딧 (DETAILS.md H-4, DESIGN.md 45장 DT11): 등용을 잡은 뒤 마을의 시우 공방 문을 누르면.

제작자 한마디 + 크레딧이 천천히 올라감. 누르면(또는 끝나면) 닫힘. 문구는 data/details/siwoo_workshop.json.
"""
import pygame

from src.core.config import load_json
from src.scene.base import Scene
from src.ui.hud import draw_cursor, text

BG = (0x0E, 0x12, 0x20)
SPEED = 16   # px/초


class CreditsScene(Scene):
    def __init__(self, game):
        super().__init__(game)
        self.c = load_json("details/siwoo_workshop.json")
        self.t = 0.0
        self.mouse = (0, 0)
        try:
            from src.core.paths import asset_path
            img = pygame.image.load(str(asset_path("branding", "siu_mark_32_base.png")))
            self.logo = pygame.transform.scale(img, (64, 64))
        except (OSError, pygame.error, FileNotFoundError):
            self.logo = None

    def handle_action(self, a) -> None:
        if a.name in ("back", "confirm") or (a.name == "primary" and self.t > 1.0):
            self._close()

    def _close(self) -> None:
        if self in self.game.scenes.stack:
            self.game.scenes.stack.remove(self)
        self.game.fade_in(0.4)

    def update(self, dt: float) -> None:
        self.t += dt
        self.mouse = self.game.input.pointer
        if self._y0(270) + self._height() < -10 and self.t > 6:
            self._close()

    def _height(self) -> int:
        return 150 + len(self.c["credits"]) * 30

    def _y0(self, h: int) -> float:
        hold = 3.5   # 한마디를 먼저 잠깐 보여 주고 올라가기 시작
        return h * 0.36 - max(0.0, self.t - hold) * SPEED

    def draw(self, canvas) -> None:
        w, h = canvas.get_size()
        canvas.fill(BG)
        a = min(1.0, self.t / 0.8)
        y = self._y0(h)
        if self.logo is not None:
            lg = self.logo.copy()
            lg.set_alpha(int(255 * a))
            canvas.blit(lg, (w // 2 - 32, int(y) - 70))
        text(canvas, self.c["thanks"], (w // 2, int(y + 6)), tuple(int(v * a) for v in (255, 236, 200)), 11, "center")
        yy = y + 60
        for role, who in self.c["credits"]:
            if not who:
                text(canvas, role, (w // 2, int(yy)), (255, 220, 140), 16, "center")
            else:
                text(canvas, role, (w // 2, int(yy)), (150, 160, 190), 11, "center")
                text(canvas, who, (w // 2, int(yy + 13)), (235, 236, 245), 11, "center")
            yy += 30
        text(canvas, "누르면 닫기", (w // 2, h - 8), (110, 116, 140), 11, "center")
        draw_cursor(canvas, self.mouse)
