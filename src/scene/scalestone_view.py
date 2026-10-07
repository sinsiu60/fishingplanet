"""낚시터 일시정지 메뉴 → 비늘석 보기 (SCALESTONE.md 화면 4, DESIGN.md 46장 S5): 장착 중인 비늘석 4개 + 합계 효과. 보기만 (변경은 마을 상점에서만)."""
import pygame

from src.render import gear_icon
from src.save import scalestone as ss
from src.scene.base import Scene
from src.scene.scalestone_tab import SLOT_KO, unit
from src.ui import scalestone_ui as sui
from src.ui import shop_ui as su
from src.ui import widgets as ui
from src.ui.hud import draw_cursor, text


class ScalestoneViewScene(Scene):
    UI_FRAME = True

    def __init__(self, game, fishing):
        super().__init__(game)
        self.fishing = fishing
        self.mouse = (0, 0)
        self.age = 0.0
        self.close_btn = ui.Button((240 - 40, 244, 80, 18), "닫기", self._close)

    def _close(self) -> None:
        self.game.scenes.pop()

    def handle_action(self, a) -> None:
        if a.name in ("back", "confirm"):
            self._close()
        elif a.name == "primary" and self.close_btn.click(a.pos):
            self.game.sfx.play("ui_click")

    def update(self, dt: float) -> None:
        self.age += dt
        self.mouse = self.ui_pointer()

    def draw(self, canvas) -> None:
        ui.backdrop(canvas, self.fishing, int(170 * min(1.0, self.age / 0.15)), "pause")
        canvas = self.ui_canvas(canvas)
        box = pygame.Rect(12, 6, 456, 262)
        canvas.fill(ui.SHADOW, box.move(2, 2))
        canvas.fill(su.WIN_BG, box)
        pygame.draw.rect(canvas, su.BORDER, box, 1)
        text(canvas, "비늘석", (box.x + 8, box.y + 10), ui.ACCENT, 16, "midleft")
        text(canvas, "변경은 마을 상점에서만 할 수 있어요", (box.right - 8, box.y + 10), su.SUB, 11, "midright")
        eq = ss.equipped_stones(self.game.save)
        cw = (box.w - 16 - 9) // 4
        for i, slot in enumerate(ss.SLOTS):
            r = pygame.Rect(box.x + 8 + i * (cw + 3), box.y + 24, cw, 118)
            canvas.fill(su.CELL_BG, r)
            pygame.draw.rect(canvas, su.BORDER, r, 1)
            gear_icon.draw(canvas, slot, self.game.save.equipped(slot), (r.x + 4, r.y + 4, 14, 14))
            text(canvas, SLOT_KO[slot], (r.x + 21, r.y + 11), su.GRAY, 11, "midleft")
            st = eq[slot]
            canvas.blit(sui.icon(st["grade"] if st else None), (r.right - 36, r.y + 4))
            if st is None:
                text(canvas, "비어 있음", (r.x + 4, r.y + 48), su.SUB, 11, "midleft")
                continue
            g = ss.grade_info(st["grade"])
            text(canvas, f"{g['name']} +{st['level']}", (r.x + 4, r.y + 28), tuple(g["color"]), 11, "midleft")
            for j, o in enumerate(st["opts"]):
                y = r.y + 46 + j * 14
                v = ss.value_text(o["id"], o["v"])
                vr = text(canvas, v, (r.right - 4, y), tuple(g["color"]), 11, "midright")
                text(canvas, su.fit(ss.option_text(o, False), vr.x - r.x - 8), (r.x + 4, y), su.WHITE, 11, "midleft")
        # 합계 효과 (두 줄로)
        tot = ss.totals(self.game.save)
        ids = [oid for oid in ss.options()["order"] if oid in tot]
        y0 = box.y + 152
        su.btext(canvas, "합계 효과", (box.x + 8, y0), su.YELLOW, 11, "midleft")
        if not ids:
            text(canvas, "장착한 비늘석이 없어요", (box.centerx, y0 + 24), su.GRAY, 11, "center")
        half = (len(ids) + 1) // 2
        colw = (box.w - 16) // 2
        for k, oid in enumerate(ids):
            t = tot[oid]
            x = box.x + 8 + (k // half) * colw if half else box.x + 8
            y = y0 + 16 + (k % half) * 13 if half else y0
            text(canvas, ss.options()["options"][oid]["name"], (x, y), su.WHITE, 11, "midleft")
            text(canvas, ss.value_text(oid, t["eff"]), (x + 140, y), su.GREEN, 11, "midright")
            note = f"({unit(oid, t['over'])} 초과)" if t["over"] > 0 else f"상한 {unit(oid, t['cap'])}"
            text(canvas, note, (x + 146, y), su.GRAY if t["over"] > 0 else su.SUB, 11, "midleft")
        self.close_btn.draw(canvas, self.mouse)
        draw_cursor(canvas, self.mouse)
