"""씬 기본 클래스. 로직(update)은 고정 틱으로, 그리기(draw)는 프레임마다 호출된다."""
import pygame


class Scene:
    # True = 메뉴처럼 가운데 480x270 'UI 상자'에 그리는 씬 (모바일에서 화면비가 달라도 가운데). PC에선 상자 = 캔버스 전체.
    UI_FRAME = False

    def __init__(self, game):
        self.game = game

    def handle_event(self, event: pygame.event.Event) -> None:
        """원시 이벤트 → 입력 계층이 '행동'으로 바꿔 handle_action 으로 넘긴다 (src/platform/input.py)."""
        result = self.game.input.translate(event)
        if result is None:
            return
        for action in (result if isinstance(result, list) else (result,)):
            if self.game.scenes.current is not self:
                break  # 앞 행동으로 화면이 바뀌었으면 나머지는 버린다 (탭 = 누름+뗌)
            if self.UI_FRAME and action.pos is not None:
                r = self.game.screen.ui_rect
                action.pos = (action.pos[0] - r.x, action.pos[1] - r.y)
            self.handle_action(action)

    def ui_canvas(self, canvas: pygame.Surface) -> pygame.Surface:
        """UI 상자 영역 (PC에선 캔버스 그대로)."""
        r = self.game.screen.ui_rect
        return canvas if r.size == canvas.get_size() else canvas.subsurface(r)

    def ui_pointer(self) -> tuple[int, int]:
        """UI 상자 기준 포인터 좌표."""
        x, y = self.game.input.pointer
        r = self.game.screen.ui_rect
        return x - r.x, y - r.y

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
