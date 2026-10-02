"""신규 패턴(U3·U4) 화면 표시 중 물고기·줄 쪽 연출 (줄 나선) + 패턴 이름 (도감·결과·디버그용).

대응 신호(예고·진행 막대·콤보 줄·꼬임 게이지)는 31장 C3부터 src/ui/signal_slots.py 의 신호 슬롯 두 칸으로 옮겼다.
"""
import math

import pygame

from src.core.config import load_json
from src.ui.fight_fx import ICON_COL

ACTION_KO = {"rush": "돌진", "jump": "점프", "leap": "몸털기", "turn": "방향 전환", "charge": "멈춤"}


def names() -> dict:
    return load_json("patterns.json")["names"]


def action_name(a: str) -> str:
    return names().get(a) or ACTION_KO.get(a, a)


def draw_line_twist(canvas, p0, p1, amount: float, t: float) -> None:
    """줄 비틀기: 줄을 따라 감기는 나선 무늬 (amount 0~1)."""
    if amount <= 0.02:
        return
    x0, y0 = p0
    x1, y1 = p1
    dx, dy = x1 - x0, y1 - y0
    length = math.hypot(dx, dy)
    if length < 4:
        return
    nx, ny = -dy / length, dx / length
    n = max(6, int(length / 6))
    col = ICON_COL["twist"]
    amp = 1.5 + 2.5 * amount
    prev = None
    for i in range(n + 1):
        k = i / n
        if k < 0.15:
            continue  # 낚싯대 끝 근처는 비운다
        off = math.sin(k * 26 - t * 16) * amp * min(1.0, k * 2)
        pt = (x0 + dx * k + nx * off, y0 + dy * k + ny * off)
        if prev is not None:
            pygame.draw.line(canvas, col, prev, pt, 1)
        prev = pt
