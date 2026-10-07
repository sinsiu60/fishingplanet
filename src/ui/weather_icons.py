"""날씨 아이콘 9×9 · 3×5 숫자 (TIME_REST.md 🅰 지도 예보표, DESIGN.md 48장). 코드로 찍는 도트 — 정수배 확대만.

맑음 = 노란 해 / 비 = 하늘색 빗방울 3개 / 폭풍 = 회색 구름 + 노란 번개 / 안개 = 회색 가로줄 3개.
"""
import pygame

SUN, RAIN, CLOUD, BOLT, FOG = (255, 214, 90), (120, 200, 255), (150, 158, 176), (255, 222, 90), (170, 176, 190)

ICONS = {
    "clear": ["....y....", ".y.....y.", "...yyy...", "..yyyyy..", "y.yyyyy.y", "..yyyyy..", "...yyy...",
              ".y.....y.", "....y...."],
    "rain": [".........", "..b...b..", "..b...b..", ".........", "....b....", "....b....", ".b.......", ".b.....b.", ".......b."],
    "storm": ["..ccc....", ".ccccc...", "ccccccc..", "ccccccc..", ".....yy..", "....yy...", "...yyyy..", ".....yy..", "....y...."],
    "fog": [".........", "fffffff..", ".........", "..fffffff", ".........", "ffffff...", ".........", "...ffffff", "........."],
}
_COL = {"y": SUN, "b": RAIN, "c": CLOUD, "f": FOG}
_COL_STORM = {"y": BOLT, "c": CLOUD}

DIGITS = {
    "0": ["###", "#.#", "#.#", "#.#", "###"], "1": [".#.", "##.", ".#.", ".#.", "###"],
    "2": ["###", "..#", "###", "#..", "###"], "3": ["###", "..#", "###", "..#", "###"],
    "4": ["#.#", "#.#", "###", "..#", "..#"], "5": ["###", "#..", "###", "..#", "###"],
    "6": ["###", "#..", "###", "#.#", "###"], "7": ["###", "..#", "..#", "..#", "..#"],
    "8": ["###", "#.#", "###", "#.#", "###"], "9": ["###", "#.#", "###", "..#", "###"],
}
_CACHE: dict = {}


def icon(weather: str) -> pygame.Surface:
    img = _CACHE.get(weather)
    if img is None:
        rows = ICONS.get(weather, ICONS["clear"])
        cols = _COL_STORM if weather == "storm" else _COL
        img = pygame.Surface((9, 9), pygame.SRCALPHA)
        for y, row in enumerate(rows):
            for x, ch in enumerate(row[:9]):
                if ch in cols:
                    img.set_at((x, y), cols[ch])
        _CACHE[weather] = img
    return img


def draw(canvas, weather: str, x: int, y: int) -> None:
    canvas.blit(icon(weather), (x, y))


def digits(canvas, s: str, x: int, y: int, col) -> int:
    """3×5 숫자 (글자 사이 1px). 돌려주는 값 = 오른쪽 끝."""
    for ch in s:
        pat = DIGITS.get(ch)
        if pat:
            for yy, row in enumerate(pat):
                for xx, c in enumerate(row):
                    if c == "#":
                        canvas.set_at((x + xx, y + yy), col)
        x += 4
    return x - 1
