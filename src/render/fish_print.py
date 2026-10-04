"""어탁 (물고기 탁본, DESIGN.md 35-2 · CONTENT_EXPANSION.md A-3): 물고기 그림 → 실루엣 → 먹물 번짐 + 크기·날짜·낚시터 도장.

그림은 저장하지 않고 기록(save.data["prints"][fid])에서 매번 만든다 (같은 기록 = 같은 그림: 종 id 로 고정된 난수).
종류: ink(일반 먹) / gold_leaf(금박 테두리, 숙련 4+) / legend(금색 먹) / phantom(보라 먹).
"""
import random

import pygame

from src.core.fonts import get_font
from src.core.mathutil import lerp_color
from src.render.fish_draw import draw_fish_fit

PAPER = (236, 226, 204)
PAPER_DARK = (214, 200, 172)
INK = {"ink": (28, 26, 30), "gold_leaf": (28, 26, 30), "legend": (176, 130, 40), "phantom": (110, 60, 170)}
SEAL = (190, 40, 36)
SEASON_KO = {"spring": "봄", "summer": "여름", "autumn": "가을", "winter": "겨울"}
_CACHE: dict = {}


def print_kind(fish: dict, mastery: int) -> str:
    if fish.get("rarity") == "phantom":
        return "phantom"
    if fish.get("rarity") == "legend":
        return "legend"
    return "gold_leaf" if mastery >= 4 else "ink"


def cost(fish: dict) -> int:
    """먹물과 종이 값: 기본가의 10% (20~2,000원)."""
    return int(max(20, min(2000, round(fish.get("base_price", 100) * 0.1, -1))))


def make(fish: dict, rec: dict, w: int = 220, h: int = 120) -> pygame.Surface:
    """rec = {size, date, spot, season, kind}."""
    key = (fish["id"], rec.get("size"), rec.get("date"), rec.get("kind"), w, h)
    if key in _CACHE:
        return _CACHE[key]
    rnd = random.Random(f"{fish['id']}{rec.get('size')}")
    kind = rec.get("kind", "ink")
    ink = INK.get(kind, INK["ink"])
    surf = pygame.Surface((w, h))
    # 한지: 바탕 + 섬유 결
    surf.fill(PAPER)
    for _ in range(w * h // 40):
        x, y = rnd.randrange(w), rnd.randrange(h)
        surf.fill(lerp_color(PAPER, PAPER_DARK, rnd.random() * 0.6), (x, y, rnd.randint(1, 4), 1))
    # 실루엣 (2배로 그려 줄임 = 부드러운 가장자리)
    fw, fh = int(w * 0.78), int(h * 0.62)
    big = pygame.Surface((fw * 2, fh * 2), pygame.SRCALPHA)
    big.fill((0, 0, 0, 0))
    draw_fish_fit(big, pygame.Rect(4, 4, fw * 2 - 8, fh * 2 - 8), fish, fw * 1.9, silhouette=(255, 255, 255))
    mask = pygame.transform.smoothscale(big, (fw, fh))
    ox, oy = int(w * 0.07), int(h * 0.12)
    # 먹물 번짐: 크게 흐린 가장자리 (옅게)
    bleed = pygame.transform.smoothscale(pygame.transform.smoothscale(mask, (max(4, fw // 6), max(4, fh // 6))), (fw, fh))
    halo = pygame.Surface((fw, fh), pygame.SRCALPHA)
    halo.fill((*ink, 255))
    halo.blit(bleed, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
    halo.set_alpha(70)
    surf.blit(halo, (ox + 1, oy + 1))
    # 본 먹: 실루엣 + 탁본 결 (점점이 빈 곳)
    core = pygame.Surface((fw, fh), pygame.SRCALPHA)
    core.fill((*ink, 235))
    core.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
    for _ in range(fw * fh // 14):
        x, y = rnd.randrange(fw), rnd.randrange(fh)
        a = core.get_at((x, y)).a
        if a > 40:
            core.set_at((x, y), (*lerp_color(ink, PAPER, rnd.uniform(0.25, 0.7)), a))
    # 비늘·지느러미 결: 몸통 안 가는 세로 줄 (탁본에서 비늘이 찍힌 느낌)
    for i in range(0, fw, 5):
        for j in range(0, fh, 4):
            if core.get_at((i, j)).a > 120 and rnd.random() < 0.55:
                core.set_at((i, j), (*lerp_color(ink, PAPER, 0.45), 220))
    surf.blit(core, (ox, oy))
    if kind == "gold_leaf":  # 금박 테두리
        for i, col in enumerate(((200, 160, 60), (240, 210, 120), (170, 130, 40))):
            pygame.draw.rect(surf, col, (i * 2, i * 2, w - i * 4, h - i * 4), 2 if i == 1 else 1)
    else:
        pygame.draw.rect(surf, PAPER_DARK, (0, 0, w, h), 1)
    # 글씨: 이름·크기(세로 느낌으로 오른쪽 위), 날짜, 낚시터 도장
    f11 = get_font(11)
    name = f11.render(fish["name"].split(" '")[0], False, ink)
    surf.blit(name, (w - name.get_width() - 8, 6))
    sz = f11.render(f"{rec.get('size', 0):.1f}cm", False, ink)
    surf.blit(sz, (w - sz.get_width() - 8, 20))
    dt = f11.render(rec.get("date", ""), False, lerp_color(ink, PAPER, 0.35))
    surf.blit(dt, (8, h - 16))
    _seal(surf, (w - 22, h - 22), rec.get("spot", "")[:2], SEAL)
    season = rec.get("season")
    if season in SEASON_KO:
        _seal(surf, (w - 46, h - 22), SEASON_KO[season][:1], (60, 110, 60))
    _CACHE[key] = surf
    return surf


def _seal(surf, center, label: str, col) -> None:
    r = pygame.Rect(0, 0, 18, 18)
    r.center = center
    pygame.draw.rect(surf, col, r, 0, border_radius=2)
    pygame.draw.rect(surf, lerp_color(col, PAPER, 0.4), r.inflate(-4, -4), 1)
    img = get_font(11).render(label, False, PAPER)
    if img.get_width() > 16:
        img = pygame.transform.scale(img, (16, img.get_height()))
    surf.blit(img, img.get_rect(center=r.center))
