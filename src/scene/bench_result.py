"""벤치마크 B1~B6 결과 화면 (OPTIMIZATION.md O1): 장면별 fps · 프레임 시간(평균 · 상위 5% · 최대) · 그리기 · 멈칫함."""

from src.scene.base import Scene
from src.ui import widgets as ui
from src.ui.hud import draw_cursor, text


class BenchResultScene(Scene):
    UI_FRAME = True

    def __init__(self, game, summary: dict):
        super().__init__(game)
        self.summary = summary
        self.msg, self.msg_t = "", 0.0
        self.btn_close = ui.Button((300, 236, 70, 20), "닫기", self._close)
        self.btn_export = ui.Button((190, 236, 100, 20), "로그 내보내기", self._export)

    def _close(self) -> None:
        self.game.scenes.pop()

    def _export(self) -> None:
        self.msg, self.msg_t = self.game.perf.export(), 4.0

    def handle_action(self, a) -> None:
        if a.name == "back":
            self._close()
        elif a.name == "primary":
            for b in (self.btn_close, self.btn_export):
                b.click(a.pos)

    def update(self, dt: float) -> None:
        self.msg_t = max(0.0, self.msg_t - dt)

    def draw(self, canvas) -> None:
        below = self.scene_below()
        if below is not None:
            ui.backdrop(canvas, below, 190, "bench_result")
        c = self.ui_canvas(canvas)
        ui.panel(c, (14, 14, 452, 248))
        text(c, "벤치마크 결과 (각 %.0f초)" % self.summary.get("secs", 30), (240, 26), ui.ACCENT, 16, "center")
        text(c, self.summary.get("device", ""), (240, 42), ui.DIM, 11, "center")
        cols = [("장면", 22), ("fps", 190), ("평균", 232), ("상위5%", 276), ("최대", 322), ("그리기", 366), ("멈칫", 412)]
        for label, x in cols:
            text(c, label, (x, 58), ui.DIM, 11, "midleft")
        y = 74
        for r in self.summary.get("results", []):
            ok = r["fps"] >= 30 and r["frame_p95"] <= 40
            col = ui.GOOD if ok else ui.BAD
            text(c, f"{r['bench']} {r['name'][:17]}", (22, y), ui.TEXT, 11, "midleft")
            text(c, f"{r['fps']:.0f}", (190, y), col, 11, "midleft")
            text(c, f"{r['frame_ms']:.0f}", (232, y), ui.TEXT, 11, "midleft")
            text(c, f"{r['frame_p95']:.0f}", (276, y), col, 11, "midleft")
            text(c, f"{r['frame_max']:.0f}", (322, y), ui.TEXT, 11, "midleft")
            text(c, f"{r['draw_ms']:.0f}", (366, y), ui.TEXT, 11, "midleft")
            text(c, f"{r['stall_ms']:.0f}" if "stall_ms" in r else "-", (412, y), ui.TEXT, 11, "midleft")
            y += 16
        text(c, "ms 단위 · 목표: 폰 30fps · 상위 5% 40ms 이하 · 멈칫 100ms 이하", (240, 186), ui.DIM, 11, "center")
        text(c, f"로그: {self.summary.get('log', '')}"[-70:], (240, 204), ui.DIM, 11, "center")
        if self.msg_t > 0:
            text(c, self.msg[:70], (240, 222), ui.GOOD, 11, "center")
        for b in (self.btn_export, self.btn_close):
            b.draw(c, self.ui_pointer())
        draw_cursor(canvas, self.game.input.pointer)
