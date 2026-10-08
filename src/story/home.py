"""주인공의 집 (STORY.md '새 장소: 주인공의 집'): 사람 없는 방 + 메뉴 낚시 일지 · 추억 · 수첩 · 나가기.

낚시 일지: 기록된 항목을 시간 순서로, 한 쪽에 4개 (게임 날짜 + 계절 아이콘). 추억: 본 장면을 막별로 묶어 다시 재생.
수첩: 기존 수첩 보관함 (보물상자 화면 '수첩' 탭).
"""
import re

import pygame

from src.core import season as seasons
from src.core.config import load_json
from src.scene.base import Scene
from src.scene.interior import InteriorScene
from src.story import story
from src.ui import widgets as ui
from src.ui.hud import draw_cursor, text, wrap_text

def _title(sc: dict) -> str:
    """장면 제목에서 설명용 괄호 '(내부 대화 + 이름 입력)' 은 빼고 보여 준다 ((A)·(B) 는 그대로)."""
    return re.sub(r"\s*\([^)]*\s[^)]*\)", "", sc.get("title", ""))


PAGE_BG, PAGE_INK = (0xF2, 0xEB, 0xD8), (0x3A, 0x2E, 0x22)


class HomeScene(InteriorScene):
    def __init__(self, game, fishing, village=None):
        super().__init__(game, fishing, "home", village=village, greet=False)
        self.wait_menu = True
        if not self.script:
            game.guide.event("home_ready")   # TG-14 주인공의 집 (대사 장면이 있으면 그 뒤 interior_ready 로)

    def _portrait_img(self):
        return pygame.Surface((1, 1), pygame.SRCALPHA)   # 사람 없는 방

    def draw_room(self, canvas, px: int | None = None) -> dict:
        """사람 없는 방 + 친밀도 5면 마루에서 자는 고양이 나비 (DT9). 조명(밤 어둡기)은 고양이까지 덮는다."""
        from src.render import interior as ir
        from src.render import village_life as vl
        if vl.affection(self.save) < vl.cfg()["cat"]["sleep_home_at"]:
            g = super().draw_room(canvas, px)
            self._draw_cups(canvas, g)
            return g
        g = self._geom(canvas)
        env = self.env(g["w"], g["top_h"])
        canvas.fill((0, 0, 0))
        ir.draw_back(canvas, self.nc["bg"], env)
        ir.draw_counter(canvas, self.nc["bg"], env)
        cx, by = g["cx"], g["top_h"] - 175
        pygame.draw.ellipse(canvas, (150, 70, 60), (cx + 84, by + 156, 44, 12))   # 작은 방석
        pygame.draw.ellipse(canvas, (180, 96, 80), (cx + 86, by + 157, 40, 9))
        vl.draw_cat(canvas, cx + 106, by + 164, "sleep", -1, self.t)
        z = (self.t * 0.6) % 1.0   # z z
        text(canvas, "z", (cx + 96 - int(z * 6), by + 150 - int(z * 14)), tuple(int(v * (1 - z)) for v in (240, 236, 220)), 11, "center")
        ir.draw_light(canvas, self.nc["bg"], env)
        self._draw_cups(canvas, g)
        return g

    def _draw_cups(self, canvas, g: dict) -> None:
        """주간 대회 트로피 (CU12): 벽 선반에 금 · 은 · 동 컵 (최근 6개)."""
        from src.save import events_cal
        tro = events_cal.st(self.save).get("trophies", [])[-6:]
        if not tro:
            return
        x0, y0 = g["cx"] - 150, g["top_h"] - 178
        canvas.fill((110, 80, 50), (x0 - 4, y0 + 14, 14 * len(tro) + 6, 3))   # 선반
        for i, t in enumerate(tro):
            col = ((255, 214, 90), (210, 214, 224), (205, 140, 90))[t["rank"] - 1]
            x = x0 + i * 14
            pygame.draw.polygon(canvas, col, [(x, y0), (x + 8, y0), (x + 6, y0 + 7), (x + 2, y0 + 7)])
            canvas.fill(col, (x + 3, y0 + 7, 2, 4))
            canvas.fill(col, (x + 1, y0 + 11, 6, 2))

    def _choose(self, item: str) -> None:
        self.game.sfx.play("ui_click")
        if item == "journal":
            self.game.scenes.push(JournalScene(self.game, self))
        elif item == "memories":
            self.game.scenes.push(MemoriesScene(self.game, self))
        elif item == "notebook":
            from src.scene.chest_scene import ChestScene, TABS
            cs = ChestScene(self.game, self.fishing)
            cs.tabs.index = next(i for i, t in enumerate(TABS) if t[0] == "diary")
            self.game.scenes.push(cs)
        elif item == "leave":
            self._begin_leave(farewell=False)
            self.leaving = self.c["fade_sec"]

    def _draw_talk(self, canvas, r) -> None:
        self._box(canvas, r)


class JournalScene(Scene):
    """낚시 일지: 펼친 책 (왼쪽·오른쪽 쪽, 한 쪽에 4개)."""
    OPEN_SOUND = "ui_paper"   # 메뉴 소리 (DT10)

    def __init__(self, game, room):
        super().__init__(game)
        self.room = room
        self.page = 0
        self.t = 0.0
        self.mouse = (0, 0)
        self.texts = load_json("story/journal.json")["entries"]

    def _entries(self) -> list:
        return story.state(self.game.save)["journal"]

    def _pages(self) -> int:
        return max(1, (len(self._entries()) + 3) // 4)

    def handle_action(self, a) -> None:
        if a.name in ("back", "confirm"):
            self._close()
        elif a.name == "primary":
            w, h = self.game.screen.canvas.get_size()
            book = self._book(w, h)
            if a.pos[0] < book.x + 30 and self.page > 0:
                self.page = max(0, self.page - 2)
                self.game.sfx.play("st_paper", 0.4)
            elif a.pos[0] > book.right - 30 and self.page + 2 < self._pages():
                self.page += 2
                self.game.sfx.play("st_paper", 0.4)
            elif not book.collidepoint(a.pos) or (book.centerx - 30 < a.pos[0] < book.centerx + 30 and a.pos[1] > book.bottom - 22):
                self._close()

    def _close(self) -> None:
        if self in self.game.scenes.stack:
            self.game.scenes.stack.remove(self)

    def update(self, dt: float) -> None:
        self.t += dt
        self.mouse = self.game.input.pointer
        self.room.update(dt)

    def _book(self, w, h) -> pygame.Rect:
        return pygame.Rect(w // 2 - 220, h // 2 - 118, 440, 236)

    _PHOTOS: dict = {}

    def _draw_photo(self, canvas, e: dict, x: int, y: int) -> None:
        """사진 칸 (DT11 사진 모드): 흰 테두리 사진 + 찍은 날짜. 파일이 없으면 빈 칸."""
        img = self._PHOTOS.get(e["photo"])
        if img is None:
            try:
                img = pygame.image.load(e["photo"])
            except (OSError, pygame.error, FileNotFoundError):
                img = False
            self._PHOTOS[e["photo"]] = img
        r = pygame.Rect(x, y - 2, 66, 38)
        canvas.fill((252, 250, 244), r.inflate(4, 4))
        pygame.draw.rect(canvas, (190, 176, 150), r.inflate(4, 4), 1)
        if img:
            canvas.blit(pygame.transform.smoothscale(img, r.size), r)
        else:
            canvas.fill((200, 192, 176), r)
            text(canvas, "사진 없음", r.center, (120, 110, 96), 11, "center")
        if e.get("date"):
            text(canvas, e["date"].replace("-", ". "), (r.right + 8, r.centery), (130, 100, 70), 11, "midleft")

    def draw(self, canvas) -> None:
        self.room.draw_room(canvas)
        w, h = canvas.get_size()
        dim = pygame.Surface((w, h), pygame.SRCALPHA)
        dim.fill((0, 0, 0, 150))
        canvas.blit(dim, (0, 0))
        book = self._book(w, h)
        canvas.fill((70, 44, 30), book.inflate(10, 10))
        canvas.fill(PAGE_BG, book)
        canvas.fill((200, 186, 160), (book.centerx - 1, book.y, 2, book.h))
        text(canvas, "낚시 일지", (book.x + 14, book.y + 12), (120, 80, 50), 11, "midleft")
        ent = self._entries()
        for side in (0, 1):
            pg = self.page + side
            items = ent[pg * 4:pg * 4 + 4]
            x0 = book.x + 14 + side * (book.w // 2)
            for i, e in enumerate(items):
                y = book.y + 30 + i * 48
                icon = seasons.ICON.get(e.get("season"), "")
                text(canvas, f"{e.get('day', 1)}일째 {icon}", (x0, y), (130, 100, 70), 11, "midleft")
                body = e.get("text") or self.texts.get(e["id"], {}).get("text", "")   # 흔적 · 사진(DT11)은 문장을 직접 가짐
                if e.get("photo"):
                    self._draw_photo(canvas, e, x0, y + 9)
                    continue
                for j, ln in enumerate(wrap_text(body, book.w // 2 - 30)[:2]):
                    text(canvas, ln, (x0, y + 15 + j * 13), PAGE_INK, 11, "midleft")
            text(canvas, str(pg + 1), (x0 + book.w // 4 - 14, book.bottom - 10), (150, 130, 100), 11, "center")
        if not ent:
            text(canvas, "아직 적은 것이 없다.", (book.centerx // 1 - book.w // 4, book.centery), (150, 130, 100), 11, "center")
        if self.page > 0:
            text(canvas, "◀", (book.x + 12, book.centery), (120, 80, 50), 16, "center")
        if self.page + 2 < self._pages():
            text(canvas, "▶", (book.right - 12, book.centery), (120, 80, 50), 16, "center")
        text(canvas, "닫기", (book.centerx, book.bottom - 10), (120, 80, 50), 11, "center")
        draw_cursor(canvas, self.mouse)


class MemoriesScene(Scene):
    """추억: 본 컷신·대화 장면 목록 (막별로 묶음). 고르면 다시 재생 (기록은 그대로)."""
    ROW = 15

    def __init__(self, game, room):
        super().__init__(game)
        self.room = room
        self.t = 0.0
        self.mouse = (0, 0)
        self.scroll = 0
        self.close_btn = ui.Button((0, 0, 60, 16), "닫기", self._close)

    def _rows(self) -> list:
        """[(막 제목 또는 None, sid 또는 None)] — 막 머리줄 + 그 막에서 본 장면."""
        sc = story.scenes()
        seen = set(story.state(self.game.save)["seen_scenes"])
        acts = {a["act"]: a["name"] for a in load_json("story/chapters.json")["acts"]}
        order = ["P-01", "P-02", "P-03", "P-04", "P-05", "C1-04", "C1-06", "C2-02", "C2-03", "C2-05", "C3-02", "C3-03",
                 "C3-04", "C4-01", "C4-02B", "C4-02A", "C4-03", "C4-04", "C4-05", "C5-03", "C5-04", "C5-05", "E-01",
                 "PH-01", "PH-02"]
        out, cur = [], "x"
        for sid in order:
            if sid not in seen:
                continue
            act = sc[sid].get("act")
            if act != cur:
                cur = act
                out.append((acts.get(act, "환상") if act is not None else "환상", None))
            out.append((None, sid))
        return out

    def _list_rect(self, w, h) -> pygame.Rect:
        return pygame.Rect(w // 2 - 200, h // 2 - 110, 400, 200)

    def handle_action(self, a) -> None:
        w, h = self.game.screen.canvas.get_size()
        lr = self._list_rect(w, h)
        if a.name == "back":
            self._close()
        elif a.name == "scroll":
            n = len(self._rows())
            self.scroll = max(0, min(max(0, n - lr.h // self.ROW), self.scroll - a.value))
        elif a.name == "primary":
            if self.close_btn.click(a.pos):
                return
            if lr.collidepoint(a.pos):
                i = (a.pos[1] - lr.y) // self.ROW + self.scroll
                rows = self._rows()
                if 0 <= i < len(rows) and rows[i][1]:
                    self.game.sfx.play("ui_click")
                    from src.story import runner
                    runner.replay(self.game, self.room.fishing, rows[i][1])

    def _close(self) -> None:
        if self in self.game.scenes.stack:
            self.game.scenes.stack.remove(self)

    def update(self, dt: float) -> None:
        self.t += dt
        self.mouse = self.game.input.pointer
        self.room.update(dt)

    def draw(self, canvas) -> None:
        self.room.draw_room(canvas)
        w, h = canvas.get_size()
        dim = pygame.Surface((w, h), pygame.SRCALPHA)
        dim.fill((0, 0, 0, 170))
        canvas.blit(dim, (0, 0))
        lr = self._list_rect(w, h)
        ui.panel(canvas, lr.inflate(16, 52).move(0, 2))
        text(canvas, "추억", (lr.x, lr.y - 10), ui.ACCENT, 16, "midleft")
        rows = self._rows()
        sc = story.scenes()
        per = lr.h // self.ROW
        for i, (head, sid) in enumerate(rows[self.scroll:self.scroll + per]):
            y = lr.y + i * self.ROW + 7
            if head:
                text(canvas, head, (lr.x, y), (255, 214, 120), 11, "midleft")
                continue
            r = pygame.Rect(lr.x + 10, y - 7, lr.w - 10, self.ROW - 1)
            if r.collidepoint(self.mouse):
                canvas.fill(ui.PANEL_LIGHT, r)
            text(canvas, f"{sid}  {_title(sc[sid])}", (lr.x + 14, y), ui.TEXT, 11, "midleft")
        if not rows:
            text(canvas, "아직 추억이 없다.", lr.center, ui.DIM, 11, "center")
        self.close_btn.rect.topleft = (lr.right - 60, lr.bottom + 6)
        self.close_btn.draw(canvas, self.mouse)
        draw_cursor(canvas, self.mouse)
