"""비늘석 일괄 분해 확인 창 (SCALESTONE.md 보관 · 분해 · 잠금, DESIGN.md 46장 S3).

조건(등급 · 강화 단계 이하)으로 고른 목록을 보여 주고 [분해] / [취소]. 잠김 · 장착 중은 목록에 들어오지 않음 (scalestone.batch_candidates).
목록이 길면 휠 · 끌기로 넘김. [분해] → scalestone.batch_salvage → on_done({"count", "mat"}).
"""
import pygame

from src.save import scalestone as ss
from src.scene.base import Scene
from src.ui import scalestone_ui as sui
from src.ui import widgets as ui
from src.ui.hud import text

ROWS = 6
ROW_H = 16


class SalvageConfirmScene(Scene):
    UI_FRAME = True

    def __init__(self, game, stones: list[dict], cont: str, on_done=None):
        super().__init__(game)
        self.stones = list(stones)
        self.cont = cont
        self.on_done = on_done
        self.mouse = (-100, -100)
        self.scroll = 0
        self.total = sum(ss.salvage_yield(s) for s in self.stones)
        self.box = pygame.Rect(240 - 150, 30, 300, 210)
        bx = self.box
        ok = bool(self.stones)
        self.buttons = [ui.Button((bx.centerx - 110, bx.bottom - 30, 100, 22), "분해", self._yes, enabled=ok, size=13, accent=ui.BAD),
                        ui.Button((bx.centerx + 10, bx.bottom - 30, 100, 22), "취소", self._no, size=13)]

    def _yes(self) -> None:
        self.game.scenes.pop()
        got = ss.batch_salvage(self.game.save, [s["uid"] for s in self.stones], self.cont)
        if got["count"]:
            self.game.sfx.play("ui_stamp", 0.5)
        if self.on_done:
            self.on_done(got)

    def _no(self) -> None:
        self.game.scenes.pop()

    def handle_action(self, a) -> None:
        if a.name == "back":
            self._no()
        elif a.name == "primary":
            for b in self.buttons:
                if b.enabled and b.click(a.pos):
                    self.game.sfx.play("ui_click")
                    return
        elif a.name == "confirm" and self.buttons[0].enabled:
            self._yes()
        elif a.name == "scroll":
            self.scroll = max(0, min(max(0, len(self.stones) - ROWS), self.scroll - a.value))

    def update(self, dt: float) -> None:
        self.mouse = self.ui_pointer()

    def draw(self, canvas) -> None:
        under = self.scene_below()
        if under is not None:
            under.draw(canvas)
        ui.dim(canvas, 160)
        canvas = self.ui_canvas(canvas)
        bx = self.box
        ui.panel(canvas, bx)
        text(canvas, f"비늘석 {len(self.stones)}개를 분해할까요?", (bx.centerx, bx.y + 8), ui.TEXT, 13, "midtop")
        # 등급별 개수
        cnt = {}
        for s in self.stones:
            cnt[s["grade"]] = cnt.get(s["grade"], 0) + 1
        parts = [(ss.grade_info(g)["name"] + f" {cnt[g]}", tuple(ss.grade_info(g)["color"])) for g in ss.grades()["order"] if cnt.get(g)]
        x = bx.x + 12
        for label, col in parts:
            r = text(canvas, label, (x, bx.y + 28), col, 11)
            x = r.right + 10
        # 목록
        ly = bx.y + 46
        lr = pygame.Rect(bx.x + 8, ly, bx.w - 16, ROWS * ROW_H)
        pygame.draw.rect(canvas, ui.PANEL_LIGHT, lr, border_radius=3)
        for i, s in enumerate(self.stones[self.scroll:self.scroll + ROWS]):
            y = ly + i * ROW_H
            col = tuple(ss.grade_info(s["grade"])["color"])
            pygame.draw.rect(canvas, col, (lr.x, y + 1, 3, ROW_H - 2))
            canvas.blit(sui.icon(s["grade"], small=True), (lr.x + 6, y))
            text(canvas, f"+{s['level']}", (lr.x + 26, y + 2), ui.TEXT, 11)
            text(canvas, ss.option_text(s["opts"][0], False), (lr.x + 48, y + 2), ui.TEXT, 11)
            sui.draw_dots(canvas, lr.right - 72, y + ROW_H // 2, s, col)
            text(canvas, f"+{ss.salvage_yield(s)}", (lr.right - 4, y + 2), ui.DIM, 11, "topright")
        if len(self.stones) > ROWS:
            text(canvas, f"{self.scroll + 1}~{min(len(self.stones), self.scroll + ROWS)} / {len(self.stones)}",
                 (lr.right, lr.bottom + 2), ui.DIM, 11, "topright")
        text(canvas, f"받는 소재 {self.total}개", (bx.x + 12, lr.bottom + 4), ui.ACCENT, 11)
        text(canvas, "잠긴 비늘석 · 장착 중인 비늘석은 빠져요", (bx.centerx, bx.bottom - 46), ui.DIM, 11, "midtop")
        for b in self.buttons:
            b.draw(canvas, self.mouse)
