"""화면 크기 반투명 레이어 재사용 (v0.8.10).

매 프레임 pygame.Surface(화면 크기, SRCALPHA)를 새로 만들면 폰에서 메모리·GC 부담이 크다 →
쓰는 곳마다 이름(key)을 붙여 한 장씩 만들어 두고, 꺼낼 때 투명으로 지워서 돌려준다.
꺼낸 레이어는 그 자리에서 그리고 바로 canvas 에 붙인다 (다른 곳과 같은 key 를 동시에 쓰지 않기).
"""
import pygame

_layers: dict = {}


def layer(canvas, key: str) -> pygame.Surface:
    size = canvas.get_size()
    surf = _layers.get(key)
    if surf is None or surf.get_size() != size:
        surf = _layers[key] = pygame.Surface(size, pygame.SRCALPHA)
    surf.fill((0, 0, 0, 0))
    return surf


def solid(canvas, key: str, color) -> pygame.Surface:
    """단색 반투명 (화면 어둡게 등)."""
    surf = layer(canvas, key)
    surf.fill(color)
    return surf
