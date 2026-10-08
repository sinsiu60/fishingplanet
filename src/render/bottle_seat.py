"""숨은 자리 '해강의 자리' (CORE_UPDATE CU9 → CU13): 유리병 편지 12장을 다 모으면 동네 저수지 물가 말뚝 옆에 낡은 낚시 의자 ·
낚싯대 받침 · 빈 병이 보인다. 던지기 전 누르면 모은 편지를 차례로 다시 읽음 (외형 · 이야기만). 위치는 data/core.json variety.bottle_seat."""
import pygame

from src.core.config import load_json
from src.core.mathutil import lerp_color, scale_color


def cfg() -> dict:
    return load_json("core.json")["variety"]["bottle_seat"]


def open_(save, spot_id: str) -> bool:
    from src.save import bottles
    return spot_id == cfg()["spot"] and not bottles.remaining(save)


def draw(canvas, save, spot_id: str, pal) -> None:
    if not open_(save, spot_id):
        return
    c = cfg()
    x, y = c["x"], c["y"]
    wood = lerp_color(pal.get("rod", (120, 90, 60)), (104, 76, 50), 0.55)
    dark = scale_color(wood, 0.7)
    canvas.fill(dark, (x, y - 8, 2, 10))              # 의자 다리 (뒤)
    canvas.fill(dark, (x + 11, y - 8, 2, 10))
    canvas.fill(wood, (x - 1, y - 10, 15, 3))         # 앉는 판
    canvas.fill(lerp_color(wood, (230, 210, 170), 0.3), (x - 1, y - 10, 15, 1))
    canvas.fill(wood, (x + 2, y - 8, 2, 10))           # 의자 다리 (앞)
    canvas.fill(wood, (x + 9, y - 8, 2, 10))
    canvas.fill(wood, (x + 20, y - 14, 1, 16))         # 낚싯대 받침 (Y자)
    pygame.draw.line(canvas, wood, (x + 20, y - 14), (x + 17, y - 18))
    pygame.draw.line(canvas, wood, (x + 20, y - 14), (x + 23, y - 18))
    glass = lerp_color(pal.get("water", (90, 140, 170)), (200, 235, 240), 0.55)   # 빈 병 (눕힘)
    canvas.fill(glass, (x - 9, y - 1, 6, 3))
    canvas.fill(glass, (x - 3, y, 2, 1))
    canvas.fill(lerp_color(glass, (255, 255, 255), 0.6), (x - 8, y - 1, 3, 1))


def hit(save, spot_id: str, pos, touch: bool = False) -> bool:
    if pos is None or not open_(save, spot_id):
        return False
    c = cfg()
    pad = 10 if touch else 6
    return pygame.Rect(c["x"] - 10 - pad, c["y"] - 18 - pad, 34 + pad * 2, 21 + pad * 2).collidepoint(pos)


def next_letter(save) -> dict:
    """모은 순서대로 한 장씩 (마지막 다음은 처음)."""
    from src.save import bottles
    by = {b["id"]: b for b in bottles.letters()}
    ids = [i for i in bottles.collected(save) if i in by]
    d = save.data.setdefault("details", {})
    i = d.get("bottle_seat_i", 0) % len(ids)
    d["bottle_seat_i"] = i + 1
    return by[ids[i]]
