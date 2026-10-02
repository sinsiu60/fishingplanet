"""PC에서 모바일 UI 미리보기 (Phase M4, DESIGN.md 26-11). run_mobile_preview.bat / main.py --mobile-preview

  마우스 왼쪽 = 손가락 하나 (누르기·끌기·떼기)
  F7  다음 화면 프리셋 (폰 18:9 → 20:9 → 21:9 → 태블릿 16:10 → 4:3)   F8  노치·둥근 모서리 표시 켜기/끄기
  손가락 하나로는 멀티터치를 못 하니 키보드가 두 번째 손가락 (낚시 화면의 버튼을 누른 것과 같음):
  스페이스 = 숙이기   ↑/↓ = 드랙   F(누르고 있기) = 릴 패드 감기   R = 회수
  진동은 창 아래에 '[진동] 종류'로 표시.
"""
import pygame

from src.platform import detect

ORDER = ["phone18", "phone20", "phone21", "tab1610", "tab43"]
NAMES = {"phone18": "폰 18:9", "phone20": "폰 20:9", "phone21": "폰 21:9", "tab1610": "태블릿 16:10", "tab43": "태블릿 4:3"}
NOTCH_PX = 30  # 미리보기 노치 크기 (창 픽셀, 폰 실제 크기의 대략 절반 축소)


class Preview:
    def __init__(self, game):
        self.game = game
        self.notch = False
        self.font = None

    def handle_event(self, event) -> bool:
        """미리보기 전용 키를 처리했으면 True."""
        if event.type != pygame.KEYDOWN:
            return False
        if event.key == pygame.K_F7:
            i = (ORDER.index(detect.current_preset()) + 1) % len(ORDER)
            self.game.switch_preset(ORDER[i])
            return True
        if event.key == pygame.K_F8:
            self.notch = not self.notch
            return True
        return False

    def caption(self) -> str:
        p = detect.current_preset()
        return f"낚시 게임 — 모바일 미리보기: {NAMES[p]} (F7 프리셋, F8 노치)"

    def draw(self, window) -> None:
        """창 위에 덧그리기 (캔버스 밖): 노치·둥근 모서리, 진동 표시."""
        if self.font is None:
            from src.core.fonts import get_font
            self.font = get_font(16)
        w, h = window.get_size()
        if self.notch:
            # 가로 화면에서 카메라 구멍은 보통 왼쪽 가장자리 가운데쯤, 모서리는 둥글게 잘린다
            pygame.draw.circle(window, (0, 0, 0), (NOTCH_PX // 2 + 8, h // 2), NOTCH_PX // 2)
            r = 36
            for cx, cy in ((0, 0), (w, 0), (0, h), (w, h)):
                mask = pygame.Surface((r, r), pygame.SRCALPHA)
                mask.fill((0, 0, 0, 255))
                ox, oy = (r if cx == 0 else 0), (r if cy == 0 else 0)
                pygame.draw.circle(mask, (0, 0, 0, 0), (ox, oy), r)
                window.blit(mask, (0 if cx == 0 else w - r, 0 if cy == 0 else h - r))
            band = pygame.Surface((NOTCH_PX + 16, h), pygame.SRCALPHA)
            band.fill((255, 60, 60, 40))
            window.blit(band, (0, 0))
        now = pygame.time.get_ticks()
        y = h - 8
        for label, t in reversed(self.game.haptics.log):
            age = now - t
            if age > 900:
                continue
            img = self.font.render(f"[진동] {label}", True, (255, 230, 120))
            bg = pygame.Surface((img.get_width() + 12, img.get_height() + 4), pygame.SRCALPHA)
            bg.fill((0, 0, 0, 170))
            y -= bg.get_height() + 2
            window.blit(bg, (w // 2 - bg.get_width() // 2, y))
            window.blit(img, (w // 2 - img.get_width() // 2, y + 2))
