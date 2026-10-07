"""일시정지 메뉴 (ESC): 계속하기 · 사진 찍기 · 비늘석 보기 · 설정 · 저장 후 타이틀 · 저장 후 바탕화면 (지도·상점 등은 오른쪽 메뉴·단축키로).
사진 찍기 (DT11): 낚시터 · 마을에서만, 파이팅 · 컷신 중엔 흐리게 (누를 수 없음)."""
from src.scene.base import Scene
from src.ui import widgets as ui
from src.ui.hud import draw_cursor, text


PANEL_Y, PANEL_H = 38, 198   # 버튼 6개가 창 안에 (예전 9개는 창 밖으로 넘쳤음)


class PauseScene(Scene):
    UI_FRAME = True

    def __init__(self, game, fishing):
        super().__init__(game)
        self.fishing = fishing
        self.mouse = (0, 0)
        self.age = 0.0  # 열림 애니메이션
        w = game.screen.ui_rect.w
        bx, bw = w // 2 - 70, 140
        items = [("계속하기", self._resume),
                 ("사진 찍기", self._photo),
                 ("비늘석 보기", self._stones),
                 ("설정", self._settings),
                 ("저장 후 타이틀", self._to_title),
                 ("저장 후 바탕화면", self._to_desktop)]
        self.buttons = [ui.Button((bx, PANEL_Y + 34 + i * 26, bw, 20), label, act) for i, (label, act) in
                        enumerate(items)]
        self.saved_msg = 0.0
        from src.scene.photo_mode import can_open
        try:
            self.buttons[1].enabled = can_open(fishing)
        except AttributeError:
            self.buttons[1].enabled = False

    def _photo(self) -> None:
        from src.scene.photo_mode import PhotoScene
        self.game.scenes.pop()   # 일시정지 창은 닫고 풍경만
        self.game.scenes.push(PhotoScene(self.game, self.fishing))

    def _stones(self) -> None:
        """장착 중인 비늘석 4개 + 합계 효과 보기 (46장 S5, 변경은 마을 상점에서만)."""
        from src.scene.scalestone_view import ScalestoneViewScene
        self.game.scenes.push(ScalestoneViewScene(self.game, self.fishing))

    def _to_desktop(self) -> None:
        self.game.save_now()
        self.game.quit()

    def _resume(self) -> None:
        self.game.scenes.pop()

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

    def handle_action(self, a) -> None:
        if a.name == "back":
            self._resume()
        elif a.name == "primary":
            m = a.pos
            for b in self.buttons:
                if b.click(m):
                    self.game.sfx.play("ui_click")
                    break

    def update(self, dt: float) -> None:
        self.age += dt
        self.mouse = self.ui_pointer()

    def draw(self, canvas) -> None:
        ui.backdrop(canvas, self.fishing, int(160 * min(1.0, self.age / 0.15)), "pause")
        canvas = self.ui_canvas(canvas)
        w = canvas.get_width()
        ui.panel(canvas, (w // 2 - 90, PANEL_Y, 180, PANEL_H))
        text(canvas, "일시정지", (w // 2, PANEL_Y + 18), ui.ACCENT, 16, "center")
        for b in self.buttons:
            b.draw(canvas, self.mouse)
        s = self.game.save
        if s:
            text(canvas, f"소지금 {ui.money_text(ui.money_anim(s.money))} · 도감 {s.dex_count()}종 · {ui.time_text(s.data['playtime'])}",
                 (w // 2, PANEL_Y + PANEL_H + 12), ui.DIM, 11, "center")
        draw_cursor(canvas, self.mouse)
