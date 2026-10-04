"""업적 화면 (수집 서랍 · U 키): 분류 탭 + 목록 (트로피 = 금색 달성 / 회색 아직), 진행 막대."""
import pygame

from src.save import achievements
from src.scene.base import Scene
from src.ui import side_menu
from src.ui import widgets as ui
from src.ui.hud import draw_cursor, text
from src.scene.inventory import fit

LIST = pygame.Rect(16, 52, 448, 188)
ROW_H = 30


class AchievementsScene(Scene):
    UI_FRAME = True

    def __init__(self, game, fishing):
        super().__init__(game)
        self.fishing = fishing
        self.save = game.save
        self.mouse = (0, 0)
        self.age = 0.0
        self.scroll = 0
        achievements.check(self.save)
        self.cats = [("all", "전체")] + [tuple(c) for c in achievements.cfg()["categories"]]
        self.tabs = ui.Tabs(16, 30, [c[1] for c in self.cats], width=60)
        self.close_btn = ui.Button((404, 248, 60, 15), "닫기 (U)", self._close)

    def _items(self) -> list[dict]:
        cat = self.cats[self.tabs.index][0]
        got = achievements.state(self.save)["got"]
        lst = [a for a in achievements.visible(self.save) if cat == "all" or a["cat"] == cat]
        return sorted(lst, key=lambda a: (a["id"] not in got, 0))   # 달성한 것 먼저 (원래 순서 유지)

    def _close(self) -> None:
        self.game.scenes.pop()

    def handle_action(self, a) -> None:
        if a.name == "back" or a.is_("menu", "achievements"):
            self._close()
        elif a.name == "scroll":
            n = len(self._items())
            self.scroll = max(0, min(max(0, n - LIST.h // ROW_H), self.scroll - a.value))
        elif a.name == "primary":
            if self.tabs.click(a.pos):
                self.scroll = 0
                self.game.sfx.play("ui_tab")
                return
            self.close_btn.click(a.pos)

    def update(self, dt: float) -> None:
        self.age += dt
        self.mouse = self.ui_pointer()

    def draw(self, canvas) -> None:
        self.fishing.draw(canvas)
        ui.dim(canvas, int(170 * min(1.0, self.age / 0.15)))
        canvas = self.ui_canvas(canvas)
        ui.panel(canvas, (8, 6, 464, 260))
        side_menu.trophy(canvas, 22, 16, (255, 255, 255), self.age)
        text(canvas, "업적", (34, 16), ui.ACCENT, 16, "midleft")
        vis = achievements.visible(self.save)
        got = achievements.state(self.save)["got"]
        n_got = sum(1 for a in vis if a["id"] in got)
        text(canvas, f"{n_got} / {len(vis)}", (464, 16), ui.ACCENT, 11, "midright")
        self.tabs.draw(canvas, self.mouse)
        ui.panel(canvas, LIST, fill=(16, 20, 36))
        items = self._items()
        per = LIST.h // ROW_H
        old = canvas.get_clip()
        canvas.set_clip(LIST.inflate(-2, -2))
        for i, a in enumerate(items[self.scroll:self.scroll + per]):
            r = pygame.Rect(LIST.x + 4, LIST.y + 3 + i * ROW_H, LIST.w - 8, ROW_H - 3)
            done = a["id"] in got
            canvas.fill((34, 30, 20) if done else (22, 26, 40), r)
            pygame.draw.rect(canvas, (150, 120, 50) if done else (50, 56, 76), r, 1)
            if done:
                side_menu.trophy(canvas, r.x + 14, r.centery, (255, 255, 255), self.age)
            else:
                side_menu.trophy(canvas, r.x + 14, r.centery, (120, 124, 140), 0, gold=(92, 96, 112), dark=(70, 72, 86))
            name, desc = (a["name"], a["desc"]) if done or not _secret(self.save, a) else ("???", "비밀 내용")
            text(canvas, fit(name, 150), (r.x + 30, r.y + 8), (255, 220, 120) if done else ui.TEXT, 11, "midleft")
            text(canvas, fit(desc, 220), (r.x + 30, r.y + 20), ui.DIM, 11, "midleft")
            v = min(achievements.value(self.save, a), a["goal"])
            if done:
                text(canvas, "달성", (r.right - 8, r.centery), ui.GOOD, 11, "midright")
            else:
                bar = pygame.Rect(r.right - 150, r.centery - 3, 80, 6)
                ui.bar(canvas, bar, v / a["goal"], (110, 170, 255))
                goal = f"{a['goal']:,}" if a["goal"] >= 1000 else str(a["goal"])
                text(canvas, f"{v:,}/{goal}", (r.right - 6, r.centery), ui.DIM, 11, "midright")
        canvas.set_clip(old)
        if len(items) > per:
            text(canvas, f"{self.scroll + 1}-{min(len(items), self.scroll + per)} / {len(items)}  (휠·끌기)",
                 (LIST.x, 255), ui.DIM, 11, "midleft")
        self.close_btn.draw(canvas, self.mouse)
        draw_cursor(canvas, self.mouse)


def _secret(save, a: dict) -> bool:
    """아직 낚지 못한 전설 물고기가 이름으로 나오는 업적 (용문잉어 '등용' · 오르시엘 등) → '비밀 내용'."""
    if a.get("type") != "caught":
        return False
    from src.save.save_game import fish_by_id
    try:
        f = fish_by_id(a["arg"])
    except (KeyError, StopIteration):
        return False
    return f.get("rarity") == "legend" and not save.caught(a["arg"])
