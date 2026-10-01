"""게임 아이콘(물고기)을 코드로 그린다.

창 아이콘(set_icon)과 빌드용 .ico(tools/make_icon.py)가 같은 그림을 쓴다.
32x32 픽셀아트로 그린 뒤 정수 배율(최근접)로 키워 픽셀 느낌을 유지한다.
"""
import pygame

BG = (24, 52, 84)
BG_RIM = (12, 28, 48)
BODY = (236, 150, 52)
BELLY = (255, 214, 130)
DARK = (168, 82, 30)
FIN = (214, 96, 40)
EYE_W = (250, 250, 240)
EYE = (20, 20, 28)
BUBBLE = (150, 210, 240)


def draw_icon_32() -> pygame.Surface:
    s = pygame.Surface((32, 32), pygame.SRCALPHA)
    # 둥근 사각 배경 (물속)
    pygame.draw.rect(s, BG_RIM, (0, 0, 32, 32), border_radius=7)
    pygame.draw.rect(s, BG, (1, 1, 30, 30), border_radius=6)
    pygame.draw.line(s, (40, 80, 120), (4, 26), (27, 26))  # 수면 아래 빛줄기
    # 꼬리
    pygame.draw.polygon(s, FIN, [(9, 16), (2, 9), (4, 16), (2, 23)])
    pygame.draw.polygon(s, DARK, [(9, 16), (2, 9), (4, 16), (2, 23)], 1)
    # 등지느러미 / 배지느러미
    pygame.draw.polygon(s, FIN, [(12, 11), (17, 5), (21, 11)])
    pygame.draw.polygon(s, FIN, [(15, 21), (18, 25), (20, 21)])
    # 몸통
    pygame.draw.ellipse(s, BODY, (7, 9, 22, 14))
    pygame.draw.ellipse(s, BELLY, (12, 16, 14, 6))
    pygame.draw.ellipse(s, DARK, (7, 9, 22, 14), 1)
    # 줄무늬
    for x in (14, 18):
        pygame.draw.line(s, DARK, (x, 11), (x - 1, 15))
    # 아가미, 눈
    pygame.draw.arc(s, DARK, (19, 11, 6, 10), -1.2, 1.2, 1)
    pygame.draw.rect(s, EYE_W, (23, 13, 3, 3))
    pygame.draw.rect(s, EYE, (24, 14, 2, 2))
    # 물방울
    pygame.draw.circle(s, BUBBLE, (28, 7), 2, 1)
    pygame.draw.rect(s, BUBBLE, (25, 3, 1, 1))
    return s


def icon_surface(size: int) -> pygame.Surface:
    base = draw_icon_32()
    if size == 32:
        return base
    if size > 32 and size % 32 == 0:
        return pygame.transform.scale(base, (size, size))
    return pygame.transform.smoothscale(base, (size, size))
