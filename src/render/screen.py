"""저해상도 캔버스(480x270)에 그리고 정수 배율로 확대해 창에 출력한다.

pygame.transform.scale은 최근접 보간이라 픽셀이 뭉개지지 않는다.
"""
import pygame


class PixelScreen:
    def __init__(self, width: int, height: int, scale: int | None, title: str):
        self.width = width
        self.height = height
        self.canvas = pygame.Surface((width, height))
        self.scale = scale or self._best_scale()
        self.window = pygame.display.set_mode((width * self.scale, height * self.scale))
        pygame.display.set_caption(title)

    def _best_scale(self) -> int:
        """모니터에 들어가는 가장 큰 정수 배율 (작업표시줄 여유 고려)."""
        sizes = pygame.display.get_desktop_sizes()
        if not sizes:
            return 3
        dw, dh = sizes[0]
        return max(1, min((dw - 80) // self.width, (dh - 120) // self.height))

    def set_scale(self, scale: int) -> None:
        self.scale = max(1, scale)
        self.window = pygame.display.set_mode((self.width * self.scale, self.height * self.scale))

    def to_canvas(self, pos: tuple[int, int]) -> tuple[int, int]:
        """창 좌표(마우스) → 캔버스 좌표."""
        return pos[0] // self.scale, pos[1] // self.scale

    def present(self) -> None:
        pygame.transform.scale(self.canvas, self.window.get_size(), self.window)
        pygame.display.flip()
