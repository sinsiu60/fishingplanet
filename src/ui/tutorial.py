"""튜토리얼: 처음 보는 상황마다 게임을 멈추고 설명 카드를 띄운다 (한 번씩만).

- 카드(card): 일시정지 + 대상 강조 + 설명. 클릭하면 계속.
- 가이드(guide): 멈추지 않는 상단 안내 배너 (캐스팅·입질 단계).
- 도움말(help): H키로 언제든 조작법·예고 신호 표.
"""
import math

import pygame

from src.ui.hud import SHADOW, text, wrap_text

CARDS = {
    "welcome": ("낚시 게임에 오신 걸 환영해요!", [
        "던지기 → 입질 기다리기 → 챔질 → 파이팅 → 뜰채 순서로 진행돼요.",
        "물고기는 행동하기 전에 반드시 신호를 보내요. 신호를 읽으면 이깁니다.",
        "처음 보는 상황마다 잠깐 멈추고 설명해 드릴게요. (H키: 도움말)",
    ]),
    "fight_intro": ("파이팅 시작!", [
        "왼쪽 장력 게이지를 초록 구간에 유지하세요.",
        "위 빨강 = 줄이 상함(줄 게이지↓) / 아래 = 느슨해서 바늘이 빠짐(바늘 게이지↑)",
        "좌클릭 유지: 감기   Q/E·휠: 드랙   마우스: 물고기 반대로 버티기",
    ]),
    "telegraph:rush": ("꼬리 물보라 → 돌진!", [
        "곧 세게 끌고 도망갑니다.",
        "Q로 드랙을 낮추고 감기를 멈춰서 줄이 풀리게 두세요.",
    ]),
    "telegraph:jump": ("그림자가 커진다 → 점프!", [
        "물고기가 수면 위로 뛰어오릅니다.",
        "가장 높이 떴을 때 우클릭(낚싯대 숙이기) = PERFECT! 놓치면 바늘이 빠지기 쉬워요.",
    ]),
    "telegraph:turn": ("줄이 한쪽으로 쏠린다 → 방향 전환!", [
        "줄이 휘는 쪽으로 도망갑니다.",
        "마우스를 반대쪽으로 옮겨 버티면 장력이 덜 오르고 덜 끌려가요.",
    ]),
    "action:charge": ("움직임이 멈췄다 → 힘 모으기", [
        "지금이 기회! 좌클릭으로 확 감으세요 (평소보다 훨씬 빨리 감겨요).",
        "멈춤이 끝나면 곧 돌진하니 대비하세요.",
    ]),
    "tired": ("지쳤다 → 빈틈!", [
        "저항이 약해졌어요. 계속 감으면 장력은 초록에 유지됩니다.",
        "E로 드랙을 올리면 더 빨리 감겨요. 감기를 멈추면 줄이 느슨해져요.",
    ]),
    "slack": ("줄이 느슨해요!", [
        "장력이 초록 아래면 바늘 게이지가 차오릅니다. 가득 차면 바늘이 빠져요.",
        "좌클릭으로 감아서 장력을 올리세요.",
    ]),
    "red": ("빨간 구간!", [
        "장력이 너무 높아서 줄이 상하고 있어요. 줄 게이지가 0이면 끊어집니다.",
        "감기를 멈추거나 Q로 드랙을 낮추세요.",
    ]),
    "net_start": ("뜰채!", [
        "물고기가 눈앞에서 좌우로 몸부림칩니다.",
        "몸부림이 딱 멈춘 순간 좌클릭으로 뜨세요. 놓치면 다시 도망가요.",
    ]),
}

GUIDES = {
    "guide_cast": "좌클릭을 누르고 있으면 파워가 차요. 원하는 거리에서 놓으면 던집니다! (마우스: 방향)",
    "guide_wait": "찌를 지켜보세요. 톡톡 살짝 = 가짜 입질(무시!) / 찌가 쑥 잠기면 바로 좌클릭!",
}

HELP_CONTROLS = [
    ("던지기", "좌클릭 유지 → 놓기 (마우스로 방향)"),
    ("챔질", "찌가 쑥 잠길 때 좌클릭 (톡톡은 가짜)"),
    ("감기", "좌클릭 유지"),
    ("낚싯대 숙이기", "우클릭 (점프 정점 = PERFECT)"),
    ("드랙", "Q 낮추기 / E 올리기 / 휠"),
    ("버티기", "마우스를 물고기 반대쪽으로"),
    ("기타", "우클릭: 줄 회수  T: 시간 가속  F1: 수치  F2: 흔들림"),
]
HELP_SIGNALS = [
    ("꼬리 물보라", "돌진", "드랙 낮추고 감기 멈춤"),
    ("그림자 커짐 + 기포", "점프", "정점에 우클릭"),
    ("줄 쏠림", "방향 전환", "마우스 반대로"),
    ("멈춤", "힘 모으기", "확 감기"),
    ("지침", "빈틈", "드랙 올리고 크게 감기"),
]

PANEL = (22, 28, 48)
BORDER = (255, 220, 120)


class Tutorial:
    def __init__(self, settings):
        self.settings = settings
        self.seen = set(settings.get("tutorial_seen"))

    def is_seen(self, key: str) -> bool:
        return key in self.seen

    def want(self, key: str) -> bool:
        """처음이면 True를 돌려주고 본 것으로 기록."""
        if key in self.seen:
            return False
        self.mark(key)
        return True

    def mark(self, key: str) -> None:
        if key not in self.seen:
            self.seen.add(key)
            self.settings.set("tutorial_seen", sorted(self.seen))

    def reset(self) -> None:
        self.seen.clear()
        self.settings.set("tutorial_seen", [])


def _dim(canvas, focus=None, radius: int = 0, alpha: int = 150) -> None:
    w, h = canvas.get_size()
    shade = pygame.Surface((w, h), pygame.SRCALPHA)
    shade.fill((6, 8, 20, alpha))
    if focus:
        pygame.draw.circle(shade, (0, 0, 0, 0), (int(focus[0]), int(focus[1])), radius)
    canvas.blit(shade, (0, 0))


def draw_card(canvas, key: str, focus, t: float) -> None:
    title, raw = CARDS[key]
    w, h = canvas.get_size()
    pw = 440
    lines = [ln for r in raw for ln in wrap_text(r, pw - 24)]
    radius = 0
    if focus:
        radius = 22 + int(2 * math.sin(t * 6))
    _dim(canvas, focus, radius)
    if focus:
        pygame.draw.circle(canvas, BORDER, (int(focus[0]), int(focus[1])), radius, 1)
    ph = 34 + len(lines) * 15 + 18
    x = (w - pw) // 2
    # 강조 대상과 겹치지 않게 위/아래 선택
    y = 150 if not focus or focus[1] < 130 else 30
    canvas.fill(SHADOW, (x + 2, y + 2, pw, ph))
    canvas.fill(PANEL, (x, y, pw, ph))
    pygame.draw.rect(canvas, BORDER, (x, y, pw, ph), 1)
    text(canvas, title, (w // 2, y + 14), BORDER, 16, "center")
    for i, ln in enumerate(lines):
        text(canvas, ln, (w // 2, y + 36 + i * 15), (232, 236, 245), 11, "center")
    if t > 0.35 and int(t * 2) % 2 == 0:
        text(canvas, "클릭해서 계속", (w // 2, y + ph - 9), (160, 170, 195), 11, "center")


def draw_guide(canvas, key: str, t: float) -> None:
    w = canvas.get_width()
    s = GUIDES[key]
    pw, ph = 452, 20
    x, y = (w - pw) // 2, 22
    canvas.fill(SHADOW, (x + 1, y + 1, pw, ph))
    canvas.fill(PANEL, (x, y, pw, ph))
    border = BORDER if int(t * 2) % 2 == 0 else (200, 170, 90)
    pygame.draw.rect(canvas, border, (x, y, pw, ph), 1)
    text(canvas, s, (w // 2, y + ph // 2), (240, 240, 250), 11, "center")


def draw_help(canvas) -> None:
    w, h = canvas.get_size()
    _dim(canvas, alpha=190)
    pw, ph = 450, 250
    x, y = (w - pw) // 2, (h - ph) // 2
    canvas.fill(PANEL, (x, y, pw, ph))
    pygame.draw.rect(canvas, BORDER, (x, y, pw, ph), 1)
    text(canvas, "도움말", (w // 2, y + 11), BORDER, 16, "center")
    yy = y + 24
    text(canvas, "조작", (x + 10, yy), (150, 200, 255), 11)
    yy += 13
    for name, desc in HELP_CONTROLS:
        text(canvas, name, (x + 14, yy), (255, 240, 200), 11)
        text(canvas, desc, (x + 100, yy), (230, 232, 240), 11)
        yy += 12
    yy += 4
    text(canvas, "예고 신호 → 행동 → 대응", (x + 10, yy), (150, 200, 255), 11)
    yy += 13
    for sig, act, resp in HELP_SIGNALS:
        text(canvas, sig, (x + 14, yy), (255, 240, 200), 11)
        text(canvas, act, (x + 140, yy), (255, 170, 150), 11)
        text(canvas, resp, (x + 220, yy), (230, 232, 240), 11)
        yy += 12
    yy += 6
    text(canvas, "장력은 초록 구간 유지! 빨강 = 줄 손상, 아래 = 바늘 빠짐", (w // 2, yy + 4), (140, 230, 150), 11,
         "center")
    text(canvas, "H 또는 클릭: 닫기", (w // 2, y + ph - 9), (160, 170, 195), 11, "center")
