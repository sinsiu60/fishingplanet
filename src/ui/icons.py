"""파이팅 HUD용 작은 그림 아이콘 (DESIGN.md 31장 C2: 파이팅 중엔 글자 대신 그림).

모두 (canvas, 중심 x, y, 색) — 12×12 안쪽 크기. 게이지 이름표·드랙·거리·의뢰·터치 버튼 이름 대신 쓴다.
"""
import math

import pygame

from src.ui.hud import SHADOW


def tension(canvas, x, y, col) -> None:
    """장력: 팽팽한 줄 (지그재그)."""
    for c, o in ((SHADOW, 1), (col, 0)):
        pygame.draw.lines(canvas, c, False, [(x - 5 + o, y + 3 + o), (x - 2 + o, y - 3 + o), (x + 1 + o, y + 3 + o),
                                             (x + 4 + o, y - 3 + o)], 2)


def line(canvas, x, y, col) -> None:
    """줄 내구도: 실타래."""
    for c, o in ((SHADOW, 1), (col, 0)):
        pygame.draw.circle(canvas, c, (x + o, y + o), 5, 2)
    canvas.fill(col, (x - 1, y - 1, 2, 2))


def hook(canvas, x, y, col) -> None:
    """바늘."""
    for c, o in ((SHADOW, 1), (col, 0)):
        pygame.draw.line(canvas, c, (x + 2 + o, y - 6 + o), (x + 2 + o, y + 2 + o), 2)
        pygame.draw.arc(canvas, c, (x - 4 + o, y - 2 + o, 8, 8), math.pi, math.tau, 2)
        pygame.draw.line(canvas, c, (x - 4 + o, y + 2 + o), (x - 4 + o, y + o), 2)


def snag(canvas, x, y, col) -> None:
    """걸림: 바위."""
    pts = [(x - 6, y + 4), (x - 3, y - 3), (x + 2, y - 5), (x + 6, y + 4)]
    pygame.draw.polygon(canvas, SHADOW, [(px + 1, py + 1) for px, py in pts])
    pygame.draw.polygon(canvas, col, pts, 2)


def tangle(canvas, x, y, col) -> None:
    """엉킴: 갈대 두 줄기."""
    for dx in (-3, 2):
        pygame.draw.line(canvas, SHADOW, (x + dx + 1, y + 6), (x + dx + 2, y - 4), 2)
        pygame.draw.line(canvas, col, (x + dx, y + 5), (x + dx + 1, y - 5), 2)


def heat(canvas, x, y, col) -> None:
    """열: 불꽃."""
    pts = [(x, y - 6), (x + 4, y), (x + 3, y + 5), (x - 3, y + 5), (x - 4, y)]
    pygame.draw.polygon(canvas, SHADOW, [(px + 1, py + 1) for px, py in pts])
    pygame.draw.polygon(canvas, col, pts)


def twist(canvas, x, y, col) -> None:
    """꼬임: 나선."""
    pts = [(x + math.cos(a * 0.55) * a * 0.42, y + math.sin(a * 0.55) * a * 0.42) for a in range(0, 14)]
    pygame.draw.lines(canvas, SHADOW, False, [(px + 1, py + 1) for px, py in pts], 2)
    pygame.draw.lines(canvas, col, False, pts, 2)


def reel(canvas, x, y, col) -> None:
    """릴(드랙·감기): 동그란 스풀 + 손잡이."""
    for c, o in ((SHADOW, 1), (col, 0)):
        pygame.draw.circle(canvas, c, (x + o, y + o), 5, 2)
        pygame.draw.line(canvas, c, (x + o, y + o), (x + 6 + o, y - 4 + o), 2)


def dip(canvas, x, y, col) -> None:
    """숙이기: 휘는 낚싯대 + 아래 화살표."""
    for c, o in ((SHADOW, 1), (col, 0)):
        pygame.draw.arc(canvas, c, (x - 8 + o, y - 6 + o, 16, 14), math.pi * 0.5, math.pi, 2)
        pygame.draw.lines(canvas, c, False, [(x - 3 + o, y + 1 + o), (x + 1 + o, y + 5 + o), (x + 5 + o, y + 1 + o)], 2)


def distance(canvas, x, y, w: int, frac: float, col) -> None:
    """거리: 가로 막대 위 물고기 점 (왼쪽 = 가까움)."""
    canvas.fill(SHADOW, (x - 1, y - 1, w + 2, 4))
    canvas.fill((60, 66, 90), (x, y, w, 2))
    fx = x + int(w * max(0.0, min(1.0, frac)))
    pygame.draw.circle(canvas, SHADOW, (fx + 1, y + 2), 3)
    pygame.draw.circle(canvas, col, (fx, y + 1), 3)
    canvas.fill((230, 236, 250), (x - 3, y - 3, 2, 8))  # 나 (낚싯대 쪽)


def quest_fail(canvas, x, y) -> None:
    """의뢰 조건이 깨졌다: 두루마리 + 빨간 X."""
    pygame.draw.rect(canvas, SHADOW, (x - 5, y - 6, 12, 14))
    pygame.draw.rect(canvas, (235, 220, 180), (x - 6, y - 7, 12, 14))
    for i in range(3):
        canvas.fill((150, 130, 100), (x - 4, y - 4 + i * 3, 8, 1))
    pygame.draw.line(canvas, (255, 80, 70), (x - 1, y + 1), (x + 7, y + 9), 2)
    pygame.draw.line(canvas, (255, 80, 70), (x + 7, y + 1), (x - 1, y + 9), 2)


def bag(canvas, x, y, col) -> None:
    pygame.draw.rect(canvas, col, (x - 6, y - 3, 12, 9), 1)
    pygame.draw.arc(canvas, col, (x - 4, y - 8, 8, 9), 0, math.pi, 1)


def pips(canvas, x, y, n: int, col, gap: int = 5) -> None:
    """작은 점 n개 (연속·콤보 수 대신 — 숫자 금지)."""
    x0 = x - (n - 1) * gap // 2
    for i in range(n):
        pygame.draw.circle(canvas, SHADOW, (x0 + i * gap + 1, y + 1), 2)
        pygame.draw.circle(canvas, col, (x0 + i * gap, y), 2)


def release(canvas, x, y, col, s: int = 4) -> None:
    """풀기(▼▼): 드랙 순간 최저 등."""
    for dy in (-s, s // 2 + 1):
        pts = [(x - s - 1, y + dy - s // 2), (x + s + 1, y + dy - s // 2), (x, y + dy + s // 2 + 1)]
        pygame.draw.polygon(canvas, SHADOW, [(px + 1, py + 1) for px, py in pts])
        pygame.draw.polygon(canvas, col, pts)
