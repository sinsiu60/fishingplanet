"""스토리 화면 부품 (DESIGN.md 36 / STORY.md '장면 표시 방식'·'공통 규칙').

자막: 화면 아래 가운데, 흰 글자, 뒤에 높이 28 검은 띠 60% (최대 2줄) · 편지·종이: 가운데 종이 #F2EBD8, 글자 #3A2E22, 탭하면 닫힘
이름 입력: 제목 "이름을 입력하세요", 기본값 "하늘", 한글·영문 1~6자 (건너뛰기 없음) · 휴대폰: 140x60 검은 둥근 사각형 #1A1A1E
"""
import re

import pygame

from src.scene.base import Scene
from src.ui import hud
from src.ui import widgets as ui
from src.ui.hud import draw_cursor, text

PAPER, INK = (0xF2, 0xEB, 0xD8), (0x3A, 0x2E, 0x22)
PHONE_BG, PHONE_FROM = (0x1A, 0x1A, 0x1E), (0xF2, 0xC4, 0x6B)
NAME_RE = re.compile(r"^[가-힣A-Za-z]{1,6}$")


def subtitle(canvas, s: str, alpha: float = 1.0) -> None:
    """자막 (STORY.md 공통 규칙): 아래 가운데 흰 글자 + 높이 28 검은 띠 60%. 최대 2줄."""
    if not s or alpha <= 0:
        return
    w, h = canvas.get_size()
    rows = hud.wrap_text(s, w - 40)[:2]
    band_h = 28 if len(rows) == 1 else 40
    band = pygame.Surface((w, band_h), pygame.SRCALPHA)
    band.fill((0, 0, 0, int(255 * 0.6 * alpha)))
    y0 = h - band_h - 10
    canvas.blit(band, (0, y0))
    for i, r in enumerate(rows):
        col = tuple(int(255 * alpha) for _ in range(3))
        text(canvas, r, (w // 2, y0 + band_h // 2 + (i - (len(rows) - 1) / 2) * 14), col, 11, "center", shadow=True)


def skip_rect(canvas) -> pygame.Rect:
    w = canvas.get_width()
    return pygame.Rect(w - 62, 6, 56, 16)


def draw_skip(canvas, mouse) -> None:
    r = skip_rect(canvas)
    hov = r.collidepoint(mouse)
    canvas.fill((0, 0, 0), r)
    pygame.draw.rect(canvas, (230, 230, 230) if hov else (140, 140, 150), r, 1)
    text(canvas, "건너뛰기", r.center, (255, 255, 255) if hov else (200, 200, 210), 11, "center")


def draw_paper(canvas, body: str, k: float = 1.0) -> pygame.Rect:
    """가운데 종이 한 장 (줄바꿈 그대로). 높이는 줄 수에 맞춤."""
    w, h = canvas.get_size()
    lines = body.split("\n")
    ph = min(h - 30, 24 + 15 * len(lines))
    pw = 300
    r = pygame.Rect(w // 2 - pw // 2, h // 2 - ph // 2 + int((1 - k) * 12), pw, ph)
    canvas.fill((20, 16, 12), r.move(3, 3))
    canvas.fill(PAPER, r)
    pygame.draw.rect(canvas, (200, 188, 160), r, 1)
    for i, ln in enumerate(lines):
        if ln:
            text(canvas, ln, (r.x + 20, r.y + 18 + i * 15), INK, 11, "midleft")
    return r


class PaperScene(Scene):
    """편지·종이 화면: 탭하면 닫힘 (닫으면 on_done)."""

    def __init__(self, game, body: str, on_done=None, backdrop=None):
        super().__init__(game)
        self.body = body
        self.on_done = on_done
        self.backdrop = backdrop
        self.t = 0.0
        game.sfx.play("st_paper", 0.6)

    def handle_action(self, a) -> None:
        if a.name in ("primary", "confirm", "back") and self.t > 0.6:
            self.game.sfx.play("st_paper", 0.4)
            if self in self.game.scenes.stack:
                self.game.scenes.stack.remove(self)
            if self.on_done:
                self.on_done()

    def update(self, dt: float) -> None:
        self.t += dt

    def draw(self, canvas) -> None:
        if self.backdrop is not None:
            self.backdrop(canvas)
        else:
            canvas.fill((0, 0, 0))
        dim = pygame.Surface(canvas.get_size(), pygame.SRCALPHA)
        dim.fill((0, 0, 0, 150))
        canvas.blit(dim, (0, 0))
        r = draw_paper(canvas, self.body, min(1.0, self.t / 0.3))
        if self.t > 1.0 and int(self.t * 2) % 2:
            text(canvas, "탭하면 닫기" if self.game.input.kind == "touch" else "클릭하면 닫기", (r.centerx, r.bottom + 10),
                 (200, 200, 200), 11, "center")


class NameInputScene(Scene):
    """이름 입력 창 (건너뛰기 없음): 제목 "이름을 입력하세요", 기본값 "하늘", 한글·영문 1~6자."""
    UI_FRAME = True

    def __init__(self, game, on_done, backdrop=None):
        super().__init__(game)
        from src.story.story import DEFAULT_NAME
        self.name = DEFAULT_NAME
        self.fresh = True           # 처음 입력하면 기본값을 지우고 새로
        self.compose = ""           # 한글 조합 중인 글자 (IME)
        self.on_done = on_done
        self.backdrop = backdrop
        self.t = 0.0
        self.mouse = (0, 0)
        self.msg = ""
        self.ok_btn = ui.Button((240 - 40, 170, 80, 18), "확인", self._ok)
        try:
            pygame.key.start_text_input()   # 모바일: 화면 키보드
            pygame.key.set_text_input_rect(pygame.Rect(140, 120, 200, 20))
        except (pygame.error, AttributeError):
            pass

    def _ok(self) -> None:
        nm = (self.name + self.compose).strip()
        if not NAME_RE.match(nm):
            self.msg = "한글·영문 1~6자로 입력해 주세요"
            self.game.sfx.play("ui_error")
            return
        try:
            pygame.key.stop_text_input()
        except (pygame.error, AttributeError):
            pass
        self.game.sfx.play("ui_click")
        if self in self.game.scenes.stack:
            self.game.scenes.stack.remove(self)
        self.on_done(nm)

    def handle_event(self, event) -> None:
        if event.type == pygame.TEXTEDITING:
            self.compose = event.text
            return
        if event.type == pygame.TEXTINPUT:
            if self.fresh:
                self.name, self.fresh = "", False
            add = "".join(ch for ch in event.text if re.match(r"[가-힣A-Za-z]", ch))
            self.name = (self.name + add)[:6]
            self.compose = ""
            self.msg = ""
            return
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_BACKSPACE:
                if self.compose:
                    return
                if self.fresh:
                    self.name, self.fresh = "", False
                else:
                    self.name = self.name[:-1]
                return
            if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER) and not self.compose:
                self._ok()
                return
            if event.key == pygame.K_ESCAPE:
                return   # 건너뛰기 없음
        super().handle_event(event)

    def handle_action(self, a) -> None:
        if a.name == "primary":
            if self.ok_btn.click(a.pos):
                return
            box = pygame.Rect(150, 112, 180, 26)
            if box.collidepoint(a.pos):   # 입력 칸 탭 → 키보드 다시
                try:
                    pygame.key.start_text_input()
                except (pygame.error, AttributeError):
                    pass

    def update(self, dt: float) -> None:
        self.t += dt
        self.mouse = self.ui_pointer()

    def draw(self, canvas) -> None:
        if self.backdrop is not None:
            self.backdrop(canvas)
        dim = pygame.Surface(canvas.get_size(), pygame.SRCALPHA)
        dim.fill((0, 0, 0, 140))
        canvas.blit(dim, (0, 0))
        c = self.ui_canvas(canvas)
        ui.panel(c, (120, 70, 240, 130))
        text(c, "이름을 입력하세요", (240, 90), ui.ACCENT, 16, "center")
        box = pygame.Rect(150, 112, 180, 26)
        c.fill((10, 12, 22), box)
        pygame.draw.rect(c, ui.ACCENT, box, 1)
        shown = self.name + self.compose
        col = ui.DIM if self.fresh else ui.TEXT
        r = text(c, shown, box.center, col, 16, "center")
        if int(self.t * 2) % 2 == 0:
            c.fill(ui.TEXT, (r.right + 1, box.y + 5, 1, box.h - 10))
        text(c, f"{len(shown)}/6 · 한글·영문", (240, 148), ui.DIM, 11, "center")
        if self.msg:
            text(c, self.msg, (240, 160), ui.BAD, 11, "center")
        self.ok_btn.draw(c, self.mouse)
        draw_cursor(c, self.mouse)


def draw_phone(canvas, sender: str | None, msg: str, t: float, extra=None) -> pygame.Rect:
    """휴대폰 알림 (마을 오른쪽 아래, 140x60): 검은 둥근 사각형 + 보낸 사람(굵게 #F2C46B) + 메시지(흰색).
    sender 가 None 이면 '전파 없음' (막대 0개)."""
    w, h = canvas.get_size()
    k = min(1.0, t / 0.25)
    r = pygame.Rect(w - 146, h - 66 + int((1 - k) * 30), 140, 60)
    pygame.draw.rect(canvas, (0, 0, 0), r.move(1, 1), border_radius=8)
    pygame.draw.rect(canvas, PHONE_BG, r, border_radius=8)
    pygame.draw.rect(canvas, (70, 70, 80), r, 1, border_radius=8)
    if sender is None:   # 전파 없음: 막대 0개
        for i in range(4):
            pygame.draw.rect(canvas, (90, 90, 100), (r.x + 12 + i * 6, r.y + 28 - i * 3, 4, 6 + i * 3), 1)
        text(canvas, msg, (r.x + 44, r.y + 26), (255, 255, 255), 11, "midleft")
        return r
    text(canvas, sender, (r.x + 10, r.y + 12), PHONE_FROM, 11, "midleft")
    text(canvas, sender, (r.x + 11, r.y + 12), PHONE_FROM, 11, "midleft")   # 굵게
    for i, ln in enumerate(hud.wrap_text(msg, r.w - 20)[:2]):
        text(canvas, ln, (r.x + 10, r.y + 30 + i * 13), (255, 255, 255), 11, "midleft")
    return r
