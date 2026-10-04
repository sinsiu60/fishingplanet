"""개발사 시작 화면 '시우 공방' (SPLASH.md). 게임을 켜면 이 화면 → 타이틀.

시간표 (전체 2.8초):
  0.0  검은 화면 → 배경 #0E1220 (0.3초)
  0.3  로고(창 불 꺼짐 #5A3A22) 0.4초 페이드 인
  0.8  창에 불 (0.15초) + 굴뚝 연기 시작(0.25초마다 3프레임) + '똑·딩'
  1.0  '시우 공방' · 'SIU GONGBANG' 0.3초 페이드 인
  2.4  전체 0.4초 페이드 아웃 → 2.8 타이틀 (타이틀 음악은 타이틀 화면이 시작)
설정 '시작 로고 짧게' = 불 켜짐부터 1.2초. 0.5초 뒤 아무 입력이나 건너뛰기 (0.2초 페이드).
로고가 나오는 동안 타이틀 화면을 미리 만들어 두고, 다 못 만들었으면 로고를 유지하며 기다린다 (최대 5초).
배치는 480x270 UI 상자 기준 (모바일은 상자가 가운데) — 로고 32x32 를 정수 2배, 보간 없이.
"""
import pygame

from src.core.paths import asset_path
from src.scene.base import Scene

BG = (0x0E, 0x12, 0x20)
LOGO_POS = (208, 82)        # UI 상자 안 (64x64)
TEXT_Y = 150                # 글자 띠 (480x60) 위치 — tools/art/make_logo.py splash
FULL = {"bg": 0.3, "logo": (0.3, 0.4), "light": (0.8, 0.15), "text": (1.0, 0.3), "out": (2.4, 0.4)}
SHORT_START, SHORT_OUT = 0.8, 1.6   # 짧게: 불 켜짐(0.8)부터, 1.6 에 페이드 아웃 → 1.2초
SKIP_AFTER = 0.5
SKIP_FADE = 0.2
MAX_WAIT = 5.0              # 로딩이 길면 로고를 이만큼까지 유지
SMOKE_STEP = 0.25


def _img(name: str) -> pygame.Surface:
    s = pygame.image.load(str(asset_path("branding", name)))
    try:
        return s.convert_alpha()
    except pygame.error:   # 화면 없는 테스트
        return s


def _x2(s: pygame.Surface) -> pygame.Surface:
    return pygame.transform.scale(s, (s.get_width() * 2, s.get_height() * 2))   # 최근접 (보간 없음)


def _k(t: float, start: float, length: float) -> float:
    return max(0.0, min(1.0, (t - start) / length)) if length > 0 else float(t >= start)


class SplashScene(Scene):
    UI_FRAME = True

    def __init__(self, game):
        super().__init__(game)
        self.short = bool(game.settings.get("splash_short"))
        self.t = SHORT_START if self.short else 0.0   # 시간표 위의 시각
        self.real = 0.0                                # 실제로 지난 시간 (건너뛰기·최대 대기)
        self.out_at = SHORT_OUT if self.short else FULL["out"][0]
        self.skip_t = None                             # 건너뛰기 페이드 시작 (실제 시간)
        self.dark = _x2(_img("siu_mark_32_dark_base.png"))
        self.lit = _x2(_img("siu_mark_32_base.png"))
        self.smoke = [_x2(_img(f"siu_smoke_{k}.png")) for k in range(3)]
        self.text_band = _img("siu_splash_text.png")
        self.layer = pygame.Surface((480, 270), pygame.SRCALPHA)
        self.sounded = False
        self.title = None
        self._steps = self._preload()
        self.loaded = False

    # ── 타이틀 미리 만들기 (한 번에 한 단계씩, 프레임이 멈추지 않게) ──
    def _preload(self):
        from src.core.fonts import get_font
        for size in (9, 10, 11, 12, 14, 16):
            get_font(size)
        yield
        from src.scene.menu import TitleScene
        self.title = TitleScene(self.game)
        yield
        self.title.draw(pygame.Surface(self.game.screen.canvas.get_size()))   # 첫 그리기 캐시
        yield

    def _load_step(self) -> None:
        if self.loaded:
            return
        try:
            next(self._steps)
        except StopIteration:
            self.loaded = True

    def _finish_loading(self) -> None:
        while not self.loaded:
            self._load_step()

    # ── 진행 ──
    def handle_action(self, a) -> None:
        pass

    def handle_event(self, event) -> None:
        if event.type in (pygame.KEYDOWN, pygame.MOUSEBUTTONDOWN, pygame.FINGERDOWN):
            if self.real >= SKIP_AFTER and self.skip_t is None:
                self.skip_t = self.real   # 아무 키·클릭·탭
            return
        super().handle_event(event)

    def update(self, dt: float) -> None:
        dt = min(dt, 1 / 30)
        self.real += dt
        self._load_step()
        light = FULL["light"][0]
        if not self.sounded and self.t + dt >= light:
            self.sounded = True
            self.game.sfx.play("ui_splash")
        # 페이드 아웃 직전까지 왔는데 로딩이 남았으면 그 자리에서 기다림 (최대 5초)
        if self.t + dt >= self.out_at and not self.loaded and self.real < MAX_WAIT and self.skip_t is None:
            self.t = self.out_at
        else:
            self.t += dt
        if self.skip_t is not None and self.real - self.skip_t >= SKIP_FADE:
            self._go()
        elif self.t >= self.out_at + FULL["out"][1]:
            self._go()

    def _go(self) -> None:
        self._finish_loading()
        self.game.scenes.replace(self.title)
        self.game.fade, self.game.fade_total = 0.25, 0.25

    # ── 그리기 ──
    def _alpha(self) -> float:
        """전체(배경 제외) 진하기: 페이드 인·아웃·건너뛰기."""
        a = 1.0 - _k(self.t, self.out_at, FULL["out"][1])
        if self.skip_t is not None:
            a = min(a, 1.0 - _k(self.real - self.skip_t, 0.0, SKIP_FADE))
        return a

    def draw(self, canvas) -> None:
        bg_k = _k(self.t, 0.0, FULL["bg"])
        out = self._alpha()
        bg = tuple(int(c * bg_k * out) for c in BG)
        canvas.fill(bg)
        lay = self.layer
        lay.fill((0, 0, 0, 0))
        t = self.t
        logo_k = _k(t, *FULL["logo"])
        light_k = _k(t, *FULL["light"])
        if logo_k > 0:
            if light_k < 1:
                self._blit(lay, self.dark, LOGO_POS, logo_k)
            if light_k > 0:
                self._blit(lay, self.lit, LOGO_POS, light_k * logo_k)
            if t >= FULL["light"][0]:
                f = int((t - FULL["light"][0]) / SMOKE_STEP) % 3
                self._blit(lay, self.smoke[f], LOGO_POS, logo_k)
        text_k = _k(t, *FULL["text"])
        if text_k > 0:
            self._blit(lay, self.text_band, (0, TEXT_Y), text_k)
        if out < 1:
            lay.fill((255, 255, 255, int(255 * out)), special_flags=pygame.BLEND_RGBA_MULT)
        self.ui_canvas(canvas).blit(lay, (0, 0))

    @staticmethod
    def _blit(dst, src, pos, k: float) -> None:
        if k >= 1:
            dst.blit(src, pos)
            return
        s = src.copy()
        s.fill((255, 255, 255, int(255 * k)), special_flags=pygame.BLEND_RGBA_MULT)
        dst.blit(s, pos)
