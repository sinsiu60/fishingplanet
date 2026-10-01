"""화면 오른쪽 아래 낚싯대 + 손 + 릴 (화면의 1/4 이내)."""
import math

import pygame

from src.core.mathutil import scale_color

HAND = (414, 236)
ROD_LEN = 136
BUTT_LEN = 34
REST_ANGLE = math.degrees(math.atan2(-110, -88))  # 손 → 낚싯대 끝 방향
AIM_DEG = 18


def rod_geometry(aim: float, swing_deg: float, bend: float, hand_offset=(0.0, 0.0)) -> dict:
    """aim: -1~1 (왼쪽~오른쪽), swing_deg: 휘두르기 회전(+ = 뒤로 젖힘), bend: 휨(px, + = 아래로)."""
    hx, hy = HAND[0] + hand_offset[0], HAND[1] + hand_offset[1]
    ang = math.radians(REST_ANGLE + aim * AIM_DEG + swing_deg)
    dx, dy = math.cos(ang), math.sin(ang)
    # 낚싯대 아래쪽을 향하는 수직 벡터
    px, py = -dy, dx
    if py < 0:
        px, py = -px, -py
    butt = (hx - dx * BUTT_LEN, hy - dy * BUTT_LEN)
    straight_tip = (hx + dx * ROD_LEN, hy + dy * ROD_LEN)
    # 휘면 끝이 아래로 처지고 길이가 약간 줄어든다
    tip = (straight_tip[0] + px * bend * 1.2, straight_tip[1] + py * bend * 1.2)
    ctrl = (hx + dx * ROD_LEN * 0.55 + px * bend * 0.25, hy + dy * ROD_LEN * 0.55 + py * bend * 0.25)
    return {"hand": (hx, hy), "butt": butt, "ctrl": ctrl, "tip": tip, "dir": (dx, dy), "perp": (px, py)}


def _bezier(p0, p1, p2, n):
    pts = []
    for i in range(n + 1):
        t = i / n
        a, b, c = (1 - t) ** 2, 2 * (1 - t) * t, t * t
        pts.append((a * p0[0] + b * p1[0] + c * p2[0], a * p0[1] + b * p1[1] + c * p2[1]))
    return pts


def draw_rod(canvas: pygame.Surface, pal: dict, geo: dict, reel_angle: float) -> None:
    hand = geo["hand"]
    dx, dy = geo["dir"]
    px, py = geo["perp"]

    # 소매 (화면 오른쪽 아래 밖으로 이어짐)
    sleeve = pal["sleeve"]
    pygame.draw.polygon(canvas, sleeve, [
        (hand[0] + 2, hand[1] + 6), (hand[0] + 12, hand[1] - 4),
        (486, hand[1] + 6), (486, 276), (hand[0] + 18, 276),
    ])
    pygame.draw.line(canvas, scale_color(sleeve, 0.75), (hand[0] + 14, hand[1] + 8), (486, hand[1] + 26), 2)

    # 낚싯대: 손잡이 → 손 → 끝 (손 쪽 굵고 끝으로 갈수록 가늘게)
    rod, hi = pal["rod"], pal["rod_hi"]
    pygame.draw.line(canvas, scale_color(rod, 0.8), geo["butt"], hand, 4)
    pts = _bezier(hand, geo["ctrl"], geo["tip"], 16)
    for i in range(len(pts) - 1):
        w = 3 if i < 4 else 2 if i < 10 else 1
        pygame.draw.line(canvas, rod, pts[i], pts[i + 1], w)
    for i in range(0, 9):
        pygame.draw.line(canvas, hi, pts[i], pts[i + 1], 1)
    # 가이드 링
    for i in (5, 9, 13):
        x, y = pts[i]
        canvas.set_at((int(x + px * 2), int(y + py * 2)), hi)

    # 릴 (낚싯대 아래에 매달림)
    reel = pal["reel"]
    rc = (hand[0] + dx * 14 + px * 9, hand[1] + dy * 14 + py * 9)
    pygame.draw.line(canvas, scale_color(reel, 0.7), (hand[0] + dx * 14, hand[1] + dy * 14), rc, 2)
    pygame.draw.circle(canvas, scale_color(reel, 0.6), rc, 7)
    pygame.draw.circle(canvas, reel, rc, 5)
    pygame.draw.circle(canvas, scale_color(reel, 1.25), (rc[0] - 1, rc[1] - 1), 2)
    hx = rc[0] + math.cos(reel_angle) * 7
    hy = rc[1] + math.sin(reel_angle) * 7
    pygame.draw.line(canvas, scale_color(reel, 0.8), rc, (hx, hy), 1)
    pygame.draw.rect(canvas, scale_color(reel, 1.3), (hx - 1, hy - 1, 3, 3))

    # 주먹 (손가락이 낚싯대를 감싼 모양)
    skin, shadow = pal["hand"], pal["hand_shadow"]
    hx0, hy0 = int(hand[0]), int(hand[1])
    pygame.draw.ellipse(canvas, shadow, (hx0 - 13, hy0 - 6, 28, 21))
    pygame.draw.ellipse(canvas, skin, (hx0 - 13, hy0 - 9, 27, 18))
    for i in range(4):
        fx = hx0 - 8 + i * 5
        pygame.draw.line(canvas, shadow, (fx, hy0 - 1), (fx + 1, hy0 + 6), 1)
    # 엄지 (낚싯대 위에 얹힘)
    pygame.draw.ellipse(canvas, skin, (hx0 - 17, hy0 - 12, 13, 7))
    pygame.draw.line(canvas, shadow, (hx0 - 15, hy0 - 6), (hx0 - 6, hy0 - 7), 1)
