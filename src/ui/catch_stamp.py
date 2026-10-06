"""포획 카드 도장 (DETAILS.md D, DESIGN.md 45장 DT7): 모든 등급 카드 오른쪽 아래 "비 오는 새벽 · 계곡".

시간대 이름: 새벽(04~06시) · 아침 · 낮 · 저녁 · 밤 / 날씨 이름: 맑은 · 흐린 · 비 오는 · 폭풍 치는 · 안개 낀 · 눈 오는 (눈 = 겨울 + 맑음 · 안개).
"""
import pygame

from src.core.config import load_json
from src.core.fonts import get_font

_CACHE: dict = {}


def stamp_text(hour: float, period: str, weather: str, season: str, spot: dict) -> str:
    c = load_json("details/hands_catch.json")["stamp"]
    d0, d1 = c["dawn"]
    tkey = "dawn" if d0 <= hour < d1 else period
    wkey = "snow" if season == "winter" and weather in ("clear", "fog") else weather
    place = spot.get("short") if spot.get("short") and "?" not in spot.get("short") else spot.get("name", "")
    return f"{c['weather'].get(wkey, c['weather']['clear'])} {c['time'].get(tkey, '')} · {place}"


def draw_stamp(canvas, text: str, bottomright, col=(214, 92, 74), alpha: int = 220) -> None:
    """빨간 도장: 테두리 상자 + 글자, 살짝 기울임 (한 번 만든 그림을 다시 씀)."""
    key = (text, col, alpha)
    img = _CACHE.get(key)
    if img is None:
        if len(_CACHE) > 16:
            _CACHE.clear()
        f = get_font(11)
        t = f.render(text, False, col)
        s = pygame.Surface((t.get_width() + 10, t.get_height() + 6), pygame.SRCALPHA)
        s.blit(t, (5, 3))
        pygame.draw.rect(s, col, s.get_rect(), 1, border_radius=3)
        pygame.draw.rect(s, col, s.get_rect().inflate(-4, -4), 1, border_radius=2)
        s = pygame.transform.rotate(s, 4)
        s.set_alpha(alpha)
        img = _CACHE[key] = s
    r = img.get_rect(bottomright=bottomright)
    canvas.blit(img, r)
