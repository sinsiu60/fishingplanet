"""어탁 갤러리 (DESIGN.md 35-2·35-3): 남긴 어탁을 벽에 전시. 마을 어탁 갤러리(갈매기 박사)와 도감에서 연다.

한 쪽에 6장 (3 × 2), 누르면 크게. 종마다 최고 기록 1장.
"""
import pygame

from src.render.fish_print import make
from src.save.dexbook import all_species
from src.scene.base import Scene
from src.ui import widgets as ui
from src.ui.hud import draw_cursor, text, wrap_text

WALL = (58, 44, 34)
WALL_DARK = (44, 32, 24)
PER = 6
TW, TH = 140, 76


class PrintGalleryScene(Scene):
    UI_FRAME = True

    def __init__(self, game, fishing, keeper_line=None):
        super().__init__(game)
        self.fishing = fishing
        self.save = game.save
        self.mouse = (0, 0)
        self.page = 0
        self.big = None
        self.keeper_line = keeper_line   # 마을: 갈매기 박사 한마디 (함수: fish → 문장)
        byid = {f["id"]: f for f in all_species()}
        self.items = [(byid[fid], rec) for fid, rec in self.save.data.get("prints", {}).items() if fid in byid]
        self.items.sort(key=lambda it: it[1].get("date", ""), reverse=True)
        self.close_btn = ui.Button((404, 250, 64, 15), "닫기", self._close)
        self.prev_btn = ui.Button((14, 250, 40, 15), "◀", lambda: self._page(-1))
        self.next_btn = ui.Button((58, 250, 40, 15), "▶", lambda: self._page(1))

    def _pages(self) -> int:
        return max(1, (len(self.items) + PER - 1) // PER)

    def _page(self, d: int) -> None:
        self.page = (self.page + d) % self._pages()

    def _close(self) -> None:
        self.game.scenes.pop()

    def _rect(self, i: int) -> pygame.Rect:
        return pygame.Rect(24 + (i % 3) * (TW + 12), 44 + (i // 3) * (TH + 36), TW, TH)

    def handle_action(self, a) -> None:
        if a.name == "back":
            if self.big is not None:
                self.big = None
            else:
                self._close()
        elif a.name == "primary":
            if self.big is not None:
                self.big = None
                return
            for b in (self.close_btn, self.prev_btn, self.next_btn):
                if b.click(a.pos):
                    self.game.sfx.play("ui_click")
                    return
            for i, it in enumerate(self.items[self.page * PER:(self.page + 1) * PER]):
                if self._rect(i).collidepoint(a.pos):
                    self.big = it
                    self.game.sfx.play("ui_click")

    def update(self, dt: float) -> None:
        self.mouse = self.ui_pointer()

    def draw(self, canvas) -> None:
        self.fishing.draw(canvas)
        canvas = self.ui_canvas(canvas)
        canvas.fill(WALL)
        for x in range(0, canvas.get_width(), 24):   # 나무 벽 판자
            canvas.fill(WALL_DARK, (x, 0, 1, canvas.get_height()))
        text(canvas, f"어탁 갤러리  {len(self.items)}장", (14, 16), (240, 226, 200), 16, "midleft")
        if not self.items:
            text(canvas, "아직 어탁이 없어요. 크기 신기록을 세우면 결과 화면에서 남길 수 있어요.",
                 (240, 130), (220, 205, 180), 11, "center")
        for i, (fish, rec) in enumerate(self.items[self.page * PER:(self.page + 1) * PER]):
            r = self._rect(i)
            canvas.fill((30, 22, 16), r.move(3, 3))
            canvas.blit(pygame.transform.smoothscale(make(fish, rec), (TW, TH)), r)
            if r.collidepoint(self.mouse):
                pygame.draw.rect(canvas, (255, 230, 170), r.inflate(4, 4), 1)
            pygame.draw.circle(canvas, (150, 150, 160), (r.centerx, r.y - 4), 2)   # 압정
            text(canvas, fish["name"].split(" '")[0], (r.centerx, r.bottom + 9), (230, 215, 190), 11, "center")
        if self._pages() > 1:
            self.prev_btn.draw(canvas, self.mouse)
            self.next_btn.draw(canvas, self.mouse)
            text(canvas, f"{self.page + 1}/{self._pages()}", (110, 257), (220, 205, 180), 11, "midleft")
        self.close_btn.draw(canvas, self.mouse)
        if self.big is not None:
            fish, rec = self.big
            ui.dim(canvas, 170)
            img = make(fish, rec, 330, 180)
            r = img.get_rect(center=(240, 118))
            canvas.blit(img, r)
            if self.keeper_line:
                for j, ln in enumerate(wrap_text(self.keeper_line(fish), 400)[:2]):
                    text(canvas, ln, (240, r.bottom + 14 + j * 13), (255, 236, 190), 11, "center")
        draw_cursor(canvas, self.mouse)
