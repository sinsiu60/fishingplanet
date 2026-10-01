"""메인 루프. 게임 로직은 초당 60틱 고정, 렌더링은 그와 분리된다."""
import pygame

from src.core.config import game_config
from src.render.screen import PixelScreen
from src.scene.base import SceneManager
from src.scene.fishing_scene import FishingScene

MAX_FRAME_TIME = 0.25  # 창 드래그 등으로 멈췄을 때 틱이 폭주하지 않게


class Game:
    def __init__(self, max_frames: int | None = None):
        cfg = game_config()
        pygame.init()
        self.tick_rate = cfg["tick_rate"]
        self.tick_dt = 1.0 / self.tick_rate
        self.fps_cap = cfg.get("fps_cap", 144)
        self.screen = PixelScreen(cfg["width"], cfg["height"], cfg.get("scale"), cfg["title"])
        self.clock = pygame.time.Clock()
        self.scenes = SceneManager()
        self.scenes.push(FishingScene(self))
        # 슬로우모션용 (퍼펙트 0.3초 슬로우 등). 틱 간격은 그대로, 쌓이는 시간만 줄인다.
        self.time_scale = 1.0
        self.running = True
        self.max_frames = max_frames  # 자동 테스트용

    def run(self) -> None:
        accumulator = 0.0
        frames = 0
        while self.running:
            frame_time = min(self.clock.tick(self.fps_cap) / 1000.0, MAX_FRAME_TIME)
            accumulator += frame_time * self.time_scale

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                    self.running = False
                elif self.scenes.current:
                    self.scenes.current.handle_event(event)

            while accumulator >= self.tick_dt:
                if self.scenes.current:
                    self.scenes.current.update(self.tick_dt)
                accumulator -= self.tick_dt

            if self.scenes.current:
                self.scenes.current.draw(self.screen.canvas)
            self.screen.present()

            frames += 1
            if self.max_frames is not None and frames >= self.max_frames:
                self.running = False

        pygame.quit()

