"""씬 기본 클래스. 로직(update)은 고정 틱으로, 그리기(draw)는 프레임마다 호출된다."""
import pygame


class Scene:
    def __init__(self, game):
        self.game = game

    def handle_event(self, event: pygame.event.Event) -> None:
        """원시 이벤트 → 입력 계층이 '행동'으로 바꿔 handle_action 으로 넘긴다 (src/platform/input.py)."""
        action = self.game.input.translate(event)
        if action is not None:
            self.handle_action(action)

    def handle_action(self, a) -> None:
        """입력 행동 처리 (마우스·키보드·터치를 직접 보지 않는다)."""

    def update(self, dt: float) -> None:
        """고정 틱마다 호출. dt는 항상 1/60초 (슬로우모션 시에도 틱 간격은 동일)."""

    def draw(self, canvas: pygame.Surface) -> None:
        pass


class SceneManager:
    def __init__(self):
        self.stack: list[Scene] = []

    @property
    def current(self) -> Scene | None:
        return self.stack[-1] if self.stack else None

    def push(self, scene: Scene) -> None:
        self.stack.append(scene)

    def pop(self) -> None:
        if self.stack:
            self.stack.pop()

    def replace(self, scene: Scene) -> None:
        self.stack[-1:] = [scene]
