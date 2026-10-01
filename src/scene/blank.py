"""0단계 실행 확인용 빈 화면. Phase 1에서 낚시 장면으로 교체된다."""
import pygame

from src.core.fonts import get_font
from src.scene.base import Scene


class BlankScene(Scene):
    def __init__(self, game):
        super().__init__(game)
        self.ticks = 0

    def update(self, dt: float) -> None:
        self.ticks += 1

    def draw(self, canvas: pygame.Surface) -> None:
        w, h = canvas.get_size()
        horizon = h * 45 // 100
        canvas.fill((150, 200, 230), (0, 0, w, horizon))
        canvas.fill((60, 120, 160), (0, horizon, w, h - horizon))

        title = get_font(16).render("낚시 게임 - 준비 완료", False, (255, 255, 255))
        canvas.blit(title, title.get_rect(center=(w // 2, horizon // 2)))
        info = get_font(12).render(
            f"틱 {self.ticks}  /  FPS {self.game.clock.get_fps():.0f}  /  ESC 종료",
            False, (230, 240, 250),
        )
        canvas.blit(info, info.get_rect(center=(w // 2, horizon + 40)))
