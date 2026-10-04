"""강조 대상 고정 ID → 캔버스 좌표 (DESIGN.md 40-2).

장면이 그릴 때 mark(game, ID, rect) 로 자리를 알려 준다 (UI 상자 장면은 mark_ui). 매 프레임 그리기 시작 때 begin 으로 비우고,
가이드는 그 프레임(또는 다음 입력 처리 때)의 자리를 읽는다. 몇 개는 상황에 따라 다른 ID 로 바뀐다 (dex.open = 수집 → 도감).
"""
import pygame

_marks: dict[str, list[pygame.Rect]] = {}

# 대상을 누르는 것과 같은 '위치 없는' 행동 (터치 버튼·단축키)
ACTIONS = {
    "dex.open": ["menu:dex", "menu:bag"],
    "fish.bag": ["menu:bag"],
    "fight.reel": ["reel_tap"],
    "chest.menu": ["menu:chest", "menu:bag"],
    "dex.close": ["menu:dex", "back"],
    "shop.close": ["back"],
}


def begin() -> None:
    _marks.clear()


def mark(tid: str, rect) -> None:
    r = pygame.Rect(rect)
    if r.w > 0 and r.h > 0:
        _marks.setdefault(tid, []).append(r)


def mark_ui(scene, tid: str, rect) -> None:
    """UI 상자(480x270) 좌표 → 캔버스 좌표."""
    o = scene.game.screen.ui_rect
    mark(tid, pygame.Rect(rect).move(o.x, o.y))


def has(tid: str) -> bool:
    return tid in _marks


def resolve(game, tid: str) -> str:
    """상황에 따라 바뀌는 대상."""
    if tid == "dex.open":
        cur = game.scenes.current
        name = type(cur).__name__ if cur is not None else ""
        if name == "QuickMenuScene":
            return "fish.quick.dex" if getattr(cur, "collect", False) else "fish.quick.collection"
        if game.input.kind == "touch":
            return "fish.bag"
        return "fish.menu.dex" if has("fish.menu.dex") else "fish.menu.collection"
    if tid.startswith("home.menu."):
        return "interior.menu." + tid[10:]
    if tid == "chest.menu" and type(game.scenes.current).__name__ == "QuickMenuScene":
        return "fish.quick.chest"
    if tid.startswith("shop.tab.") and not has(tid) and has("interior.menu.buy"):
        return "interior.menu.buy"   # TG-18: 상점을 열기 전엔 '사기' 메뉴부터
    if tid == "fight.reel" and game.input.kind == "touch" and has("fight.pad"):
        return "fight.pad"
    if tid == "fight.slots":
        return "fight.slots" if has("fight.slots") else "fight.slot.left"
    return tid


def rects(game, target, run=None) -> list[pygame.Rect]:
    if not target:
        return []
    ids = target if isinstance(target, list) else [target]
    out = []
    for t in ids:
        rid = resolve(game, t)
        if rid in _marks:
            out += _marks[rid]
        else:   # 접두어 (dex.card.* · shop.row.*)
            pre = rid + "."
            for k, v in _marks.items():
                if k.startswith(pre):
                    out += v
    return out


def actions(game, target) -> list[str]:
    ids = target if isinstance(target, list) else [target]
    out = []
    for t in ids:
        out += ACTIONS.get(t, []) + ACTIONS.get(resolve(game, t), [])
    return out
