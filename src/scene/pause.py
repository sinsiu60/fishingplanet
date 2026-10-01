"""일시정지 메뉴 (ESC)."""
import pygame

from src.scene.base import Scene
from src.ui import widgets as ui
from src.ui.hud import draw_cursor, text


class PauseScene(Scene):
    def __init__(self, game, fishing):
        super().__init__(game)
        self.fishing = fishing
        self.mouse = (0, 0)
        self.age = 0.0  # 열림 애니메이션
        w = game.screen.width
        bx, bw = w // 2 - 70, 140
        can_shop = fishing.can_open_menus()
        items = [("계속하기", self._resume, True),
                 ("지도 (M)", lambda: self._open("map"), can_shop),
                 ("상점 (B)", lambda: self._open("shop"), can_shop),
                 ("도감 (Tab)", lambda: self._open("dex"), True),
                 ("보물상자 (C)", lambda: self._open("chest"), can_shop),
                 ("설정", self._settings, True),
                 ("저장하고 타이틀로", self._to_title, True),
                 ("저장하고 종료", game.quit, True)]
        self.buttons = [ui.Button((bx, 64 + i * 20, bw, 17), label, act, en) for i, (label, act, en) in
                        enumerate(items)]
        self.saved_msg = 0.0

    def _resume(self) -> None:
        self.game.scenes.pop()

    def _open(self, which: str) -> None:
        self.game.scenes.pop()
        self.fishing.open_menu(which)

    def _settings(self) -> None:
        from src.scene.settings_scene import SettingsScene
        self.game.scenes.push(SettingsScene(self.game))

    def _to_title(self) -> None:
        from src.scene.menu import TitleScene
        self.game.save_now()
        self.game.sfx.stop_all()
        self.game.save = None
        self.game.scenes.stack.clear()
        self.game.scenes.push(TitleScene(self.game))
        self.game.fade_in(0.6)

    def handle_event(self, event) -> None:
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self._resume()
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            m = self.game.to_canvas(event.pos)
            for b in self.buttons:
                if b.click(m):
                    self.game.sfx.play("click")
                    break

    def update(self, dt: float) -> None:
        self.age += dt
        self.mouse = self.game.to_canvas(pygame.mouse.get_pos())

    def draw(self, canvas) -> None:
        self.fishing.draw(canvas)
        ui.dim(canvas, int(160 * min(1.0, self.age / 0.15)))
        w = canvas.get_width()
        ui.panel(canvas, (w // 2 - 90, 30, 180, 200))
        text(canvas, "일시정지", (w // 2, 50), ui.ACCENT, 16, "center")
        for b in self.buttons:
            b.draw(canvas, self.mouse)
        s = self.game.save
        if s:
            text(canvas, f"소지금 {ui.money_text(s.money)} · 도감 {s.dex_count()}종 · {ui.time_text(s.data['playtime'])}",
                 (w // 2, 240), ui.DIM, 11, "center")
        draw_cursor(canvas, self.mouse)
