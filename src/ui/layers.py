"""화면 크기 반투명 레이어 재사용 (v0.8.10).

매 프레임 pygame.Surface(화면 크기, SRCALPHA)를 새로 만들면 폰에서 메모리·GC 부담이 크다 →
쓰는 곳마다 이름(key)을 붙여 한 장씩 만들어 두고, 꺼낼 때 투명으로 지워서 돌려준다.
꺼낸 레이어는 그 자리에서 그리고 바로 canvas 에 붙인다 (다른 곳과 같은 key 를 동시에 쓰지 않기).
"""
import pygame

_layers: dict = {}


def layer(canvas, key: str, rects=None) -> pygame.Surface:
    """rects 를 주면 그 칸들만 투명으로 지움 (put_rects 와 짝 — 그 칸 밖엔 그리지 않을 때)."""
    size = canvas.get_size()
    surf = _layers.get(key)
    if surf is None or surf.get_size() != size:
        surf = _layers[key] = pygame.Surface(size, pygame.SRCALPHA)
    if rects is None:
        surf.fill((0, 0, 0, 0))
    else:
        for r in rects:
            surf.fill((0, 0, 0, 0), r)
    return surf


def merged(rects) -> list:
    """겹치는 칸끼리 합쳐 서로 안 겹치는 칸 목록으로 (두 번 섞이지 않게)."""
    out = [pygame.Rect(r) for r in rects]
    changed = True
    while changed:
        changed = False
        for i in range(len(out)):
            for j in range(i + 1, len(out)):
                if out[i].colliderect(out[j]):
                    out[i] = out[i].union(out.pop(j))
                    changed = True
                    break
            if changed:
                break
    return out


def put_rects(canvas, surf: pygame.Surface, rects) -> None:
    """층의 그 칸들만 섞는다 — 화면 전체 반투명 섞기는 폰(pygame 2.6)에서 수 ms (DESIGN.md 44)."""
    bounds = surf.get_rect()
    for r in rects:
        r = pygame.Rect(r).clip(bounds)
        if r.w and r.h:
            canvas.blit(surf, r.topleft, r)


def solid(canvas, key: str, color) -> pygame.Surface:
    """단색 반투명 (화면 어둡게 등)."""
    surf = layer(canvas, key)
    surf.fill(color)
    return surf



def put(canvas, surf: pygame.Surface) -> None:
    """층을 캔버스에 섞는다. (그린 부분만 잘라 섞기는 get_bounding_rect 훑기가 섞기보다 더 느려서 안 씀)"""
    canvas.blit(surf, (0, 0))
