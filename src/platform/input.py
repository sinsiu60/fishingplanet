"""입력 추상화 (DESIGN.md 26-5). 씬은 마우스·키보드·터치를 직접 읽지 않고 '행동'만 받는다.

이벤트형 행동 (Action, 씬의 handle_action 으로 전달)
  primary / primary_up   주 입력 누름·뗌 (캐스팅·챔질·뜰채·버튼)     PC: 좌클릭       모바일: 탭
  secondary              보조 입력 (파이팅=숙이기, 대기=회수)          PC: 우클릭       모바일: 버튼
  click_other            그 밖의 마우스 버튼 (도움말·카드 닫기용)      PC: 가운데·휠 버튼
  scroll (value=±n)      목록 스크롤 / 낚시 중엔 드랙                  PC: 휠           모바일: 드래그
  drag (value=±1)        드랙 올리기·내리기                           PC: E / Q        모바일: ▲▼
  item (value=1|2)       소모품                                      PC: 1 / 2        모바일: 🧪
  menu (value=shop|dex|map|chest)                                    PC: B/Tab/M/C    모바일: 🎒
  back                   뒤로·일시정지                                PC: ESC          모바일: 뒤로 가기
  confirm                연출 넘기기                                  PC: Space/Enter  모바일: 탭
  help / time_fast / debug(value=F1~F6)                              PC: H / T / F1~F6
상태형 (매 틱 읽기)
  pointer       캔버스 좌표 (화면 밖이면 가장자리로)   pointer_raw  자르지 않은 좌표
  held("reel")  릴 감기 유지                         PC: 좌클릭 유지
"""
from dataclasses import dataclass

import pygame

KEY_ACTIONS = {
    pygame.K_ESCAPE: ("back", 0),
    pygame.K_b: ("menu", "shop"),
    pygame.K_TAB: ("menu", "dex"),
    pygame.K_m: ("menu", "map"),
    pygame.K_c: ("menu", "chest"),
    pygame.K_h: ("help", 0),
    pygame.K_t: ("time_fast", 0),
    pygame.K_q: ("drag", -1),
    pygame.K_e: ("drag", +1),
    pygame.K_1: ("item", 1),
    pygame.K_2: ("item", 2),
    pygame.K_SPACE: ("confirm", 0),
    pygame.K_RETURN: ("confirm", 0),
    pygame.K_F1: ("debug", "F1"),
    pygame.K_F2: ("debug", "F2"),
    pygame.K_F3: ("debug", "F3"),
    pygame.K_F4: ("debug", "F4"),
    pygame.K_F5: ("debug", "F5"),
    pygame.K_F6: ("debug", "F6"),
}


@dataclass
class Action:
    name: str
    value: object = 0
    pos: tuple[int, int] | None = None  # 캔버스 좌표 (포인터 행동만)

    def is_(self, name: str, value=None) -> bool:
        return self.name == name and (value is None or self.value == value)

    @property
    def any_press(self) -> bool:
        """아무 버튼이나 누름 (카드·도움말 닫기)."""
        return self.name in ("primary", "secondary", "click_other")


class PcInput:
    """PC: 지금까지의 마우스·키보드 조작 그대로."""
    kind = "pc"

    def __init__(self, game):
        self.game = game

    def translate(self, event) -> Action | None:
        et = event.type
        if et == pygame.MOUSEBUTTONDOWN:
            pos = self.game.to_canvas(event.pos)
            name = {1: "primary", 3: "secondary"}.get(event.button, "click_other")
            return Action(name, event.button, pos)
        if et == pygame.MOUSEBUTTONUP and event.button == 1:
            return Action("primary_up", 1, self.game.to_canvas(event.pos))
        if et == pygame.MOUSEWHEEL:
            return Action("scroll", event.y)
        if et == pygame.KEYDOWN and event.key in KEY_ACTIONS:
            name, value = KEY_ACTIONS[event.key]
            return Action(name, value)
        return None

    @property
    def pointer(self) -> tuple[int, int]:
        return self.game.to_canvas(pygame.mouse.get_pos())

    @property
    def pointer_raw(self) -> tuple[int, int]:
        return self.game.screen.to_canvas(pygame.mouse.get_pos())

    def held(self, name: str) -> bool:
        if name == "reel":
            return bool(pygame.mouse.get_pressed()[0])
        return False


class TouchInput(PcInput):
    """모바일 터치 (Phase M3에서 구현). 지금은 PC와 같은 마우스 흉내로 동작하는 껍데기."""
    kind = "touch"


def create_input(game):
    from src.platform.detect import IS_MOBILE
    return TouchInput(game) if IS_MOBILE else PcInput(game)
