"""챌린지 의뢰 게시판 (DESIGN.md 27-5, Phase U6). 지금 있는 대륙의 게시판.

탭 [의뢰]   일일 3개 + 주간 1개: 별, 내용, 진행, 보상. 새로고침(하루 1번).
탭 [상점]   의뢰 포인트로 칭호·찌 외형·낚싯대 외형 (성능 없음), 가진 것은 장착/해제.
PC: 클릭·휠 / 터치: 탭·끌어서 스크롤. 진입: 가방(터치)·일시정지·J 키.
"""
import pygame

from src.save import quests
from src.scene.base import Scene
from src.ui import widgets as ui
from src.ui.hud import draw_cursor, text, wrap_text

STAR = (255, 214, 90)
KIND_KO = {"title": "칭호", "float_skin": "찌", "rod_skin": "낚싯대", "net_skin": "뜰채"}
CONT_KO = {"sharmion": "샤르미온", "eldrasion": "엘드라시온"}
ROW_H = 46
SHOP_ROW = 17


class QuestBoardScene(Scene):
    UI_FRAME = True

    def __init__(self, game, fishing):
        super().__init__(game)
        self.fishing = fishing
        self.save = game.save
        self.cont = quests.spot_cont(fishing.spot_id)
        self.mouse = (-100, -100)
        self.age = 0.0
        self.tabs = ui.Tabs(14, 30, ["의뢰", "포인트 상점"], width=80)
        self.refresh_btn = ui.Button((340, 30, 126, 16), "", self._refresh)
        self.close_btn = ui.Button((406, 250, 60, 15), "닫기", self._close)
        self.buy_btn = ui.Button((330, 226, 136, 18), "", self._buy)
        self.scroll = 0
        self.sel = 0
        self.msg, self.msg_t = "", 0.0
        # 게시판 구석 낡은 쪽지 (33장 P6): 해금된 낚시터마다 한 장, 읽기 전용
        self.note_btn = ui.Button((262, 30, 70, 16), "낡은 쪽지", self._toggle_notes)
        self.notes_open = False

    # ── 동작 ──
    def _toggle_notes(self) -> None:
        self.notes_open = not self.notes_open

    def _notes(self) -> list[tuple[str, str]]:
        from src.core.config import load_json
        notes = load_json("phantom_hints.json")["notes"]
        spots = [sp for sp in load_json("spots.json")["spots"] if sp.get("continent", "sharmion") == self.cont]
        unlocked = self.save.data.get("unlocked_spots", [])
        return [(sp["name"], notes[sp["id"]]) for sp in spots if sp["id"] in unlocked and sp["id"] in notes]

    def _close(self) -> None:
        self.game.scenes.pop()

    def _refresh(self) -> None:
        if quests.refresh(self.save, self.cont):
            self._say("새 의뢰를 받았어요 (오늘 새로고침 끝)")
        else:
            self._say("오늘은 더 새로고침할 수 없어요")

    def _items(self) -> list[dict]:
        """상점 목록: 파는 것 + 다른 곳에서 얻어 가진 것(변이 도감·주간 칭호)."""
        c = quests.cfg()
        out = list(c["shop"])
        cos = quests.cosmetics(self.save)
        for tid in cos["titles"]:
            if tid in c["titles_extra"]:
                out.append(quests.shop_item(tid))
        for key in ("float_skins", "rod_skins", "net_skins"):
            for sid in cos[key]:
                if sid in c["skins_extra"]:
                    out.append(quests.shop_item(sid))
        return out

    def _buy(self) -> None:
        items = self._items()
        if not items:
            return
        it = items[self.sel]
        if quests.owns(self.save, it):
            quests.toggle_equip(self.save, it["id"])
            on = quests.equipped(self.save)[quests.KIND_SLOT[it["kind"]][1]] == it["id"]
            self._say(f"{it['name']} {'장착' if on else '해제'}")
            return
        res = quests.buy(self.save, it["id"])
        if res == "ok":
            quests.toggle_equip(self.save, it["id"])
            self.game.sfx.play("ui_buy")
            self._say(f"{it['name']} 구매 · 장착!")
        elif res == "points":
            self._say("의뢰 포인트가 모자라요")

    def _say(self, s: str) -> None:
        self.msg, self.msg_t = s, 2.0

    def handle_action(self, a) -> None:
        if a.name == "back" or a.is_("menu", "quests"):
            self._close()
        elif a.name == "scroll" and self.tabs.index == 1:
            self.scroll = max(0, min(self._max_scroll(), self.scroll - a.value))
        elif a.name == "primary":
            m = a.pos
            if self.notes_open:
                self.notes_open = False  # 쪽지는 아무 데나 누르면 닫힘
                return
            if self.tabs.index == 0 and self.note_btn.click(m):
                self.game.sfx.play("ui_click")
                return
            if self.tabs.click(m):
                self.game.sfx.play("ui_tab")
                return
            if self.close_btn.click(m):
                return
            if self.tabs.index == 0:
                if self.refresh_btn.click(m):
                    self.game.sfx.play("ui_click")
                return
            if self.buy_btn.click(m):
                self.game.sfx.play("ui_click")
                return
            for i in range(self.scroll, min(len(self._items()), self.scroll + self._visible())):
                if self._shop_rect(i).collidepoint(m):
                    self.sel = i
                    self.game.sfx.play("ui_click")

    def update(self, dt: float) -> None:
        self.age += dt
        self.msg_t = max(0.0, self.msg_t - dt)
        self.mouse = self.ui_pointer()

    # ── 그리기 ──
    def draw(self, canvas) -> None:
        self.fishing.draw(canvas)
        ui.dim(canvas, int(180 * min(1.0, self.age / 0.15)))
        canvas = self.ui_canvas(canvas)
        ui.panel(canvas, (6, 6, 468, 260))
        text(canvas, f"의뢰 게시판 · {CONT_KO.get(self.cont, '')}", (14, 16), ui.ACCENT, 16, "midleft")
        r = quests.root(self.save)
        text(canvas, f"의뢰 포인트 {r['points']}   완료 {r['done']}", (466, 16), STAR, 11, "midright")
        self.tabs.draw(canvas, self.mouse)
        if self.tabs.index == 0:
            self._draw_quests(canvas)
        else:
            self._draw_shop(canvas)
        if self.msg_t > 0:
            text(canvas, self.msg, (240, 257), ui.GOOD, 11, "center")
        self.close_btn.draw(canvas, self.mouse)
        if self.tabs.index == 0:
            self.note_btn.draw(canvas, self.mouse)
        if self.notes_open:
            self._draw_notes(canvas)
        draw_cursor(canvas, self.mouse)

    def _draw_notes(self, canvas) -> None:
        """누렇게 바랜 쪽지들 (분위기 문장만 — 도감·공략 정보 없음)."""
        from src.ui.hud import wrap_text
        box = pygame.Rect(40, 44, 400, 200)
        canvas.fill((58, 50, 36), box)
        pygame.draw.rect(canvas, (150, 130, 90), box, 1)
        text(canvas, "게시판 구석에 붙은 낡은 쪽지들", (box.centerx, box.y + 12), (230, 214, 170), 11, "center")
        y = box.y + 30
        for name, line in self._notes():
            for i, ln in enumerate(wrap_text(f"[{name}] {line}", box.w - 20)[:2]):
                text(canvas, ln, (box.x + 10, y), (225, 212, 180) if i == 0 else (200, 188, 160), 11, "midleft")
                y += 13
            y += 3
            if y > box.bottom - 16:
                break
        text(canvas, "(아무 데나 누르면 닫기)", (box.centerx, box.bottom - 8), (160, 146, 112), 11, "center")

    def _draw_quests(self, canvas) -> None:
        b = quests.board(self.save, self.cont)
        left = quests.cfg()["refresh_per_day"] - b["refresh_used"]
        self.refresh_btn.label = f"새로고침 (오늘 {left}번)"
        self.refresh_btn.enabled = left > 0
        self.refresh_btn.draw(canvas, self.mouse)
        rows = list(b["daily"]) + ([b["weekly"]] if b["weekly"] else [])
        y = 52
        for q in rows:
            self._draw_quest(canvas, q, pygame.Rect(14, y, 452, ROW_H - 4))
            y += ROW_H
        if not rows:
            text(canvas, "아직 받을 수 있는 의뢰가 없어요", (240, 120), ui.DIM, 11, "center")
        text(canvas, "일일 의뢰는 자정, 주간 의뢰는 월요일에 바뀌어요", (14, 257), ui.DIM, 11, "midleft")

    def _draw_quest(self, canvas, q: dict, r: pygame.Rect) -> None:
        done = q["done"]
        border = STAR if q["weekly"] else (ui.GOOD if done else ui.BORDER)
        ui.panel(canvas, r, border, (14, 18, 32) if done else (20, 26, 44))
        tag = "주간" if q["weekly"] else "일일"
        text(canvas, tag, (r.x + 6, r.y + 8), STAR if q["weekly"] else ui.DIM, 11, "midleft")
        text(canvas, "★" * q["stars"] + "☆" * (5 - q["stars"]), (r.x + 32, r.y + 8), STAR, 11, "midleft")
        lines = wrap_text(quests.title(q), r.w - 120)
        for i, ln in enumerate(lines[:2]):
            text(canvas, ln, (r.x + 6, r.y + 21 + i * 12), ui.DIM if done else ui.TEXT, 11, "midleft")
        prog = quests.progress_text(q)
        text(canvas, prog, (r.right - 6, r.y + 8), ui.GOOD if done else ui.ACCENT, 11, "midright")
        text(canvas, quests.reward_text(q["reward"]), (r.right - 6, r.y + 33), ui.DIM if done else STAR, 11, "midright")

    def _visible(self) -> int:
        return (218 - 52) // SHOP_ROW

    def _max_scroll(self) -> int:
        return max(0, len(self._items()) - self._visible())

    def _shop_rect(self, i: int) -> pygame.Rect:
        return pygame.Rect(14, 52 + (i - self.scroll) * SHOP_ROW, 306, SHOP_ROW - 1)

    def _draw_shop(self, canvas) -> None:
        items = self._items()
        self.sel = min(self.sel, len(items) - 1)
        eq = quests.equipped(self.save)
        for i in range(self.scroll, min(len(items), self.scroll + self._visible())):
            it = items[i]
            r = self._shop_rect(i)
            if i == self.sel or r.collidepoint(self.mouse):
                canvas.fill(ui.PANEL_LIGHT, r)
            owned = quests.owns(self.save, it)
            on = eq[quests.KIND_SLOT[it["kind"]][1]] == it["id"]
            text(canvas, KIND_KO[it["kind"]], (r.x + 4, r.centery), ui.DIM, 11, "midleft")
            text(canvas, it["name"], (r.x + 46, r.centery), STAR if on else ui.TEXT, 11, "midleft")
            right = "장착 중" if on else "보유" if owned else f"{it.get('price', 0)}점"
            text(canvas, right, (r.right - 4, r.centery), ui.GOOD if owned else ui.ACCENT, 11, "midright")
        if self._max_scroll():
            text(canvas, f"{self.scroll + 1}~{min(len(items), self.scroll + self._visible())}/{len(items)} (휠·끌기)",
                 (167, 226), ui.DIM, 11, "center")
        # 오른쪽: 고른 것 미리보기
        it = items[self.sel]
        d = pygame.Rect(330, 52, 136, 168)
        ui.panel(canvas, d, fill=(16, 20, 36))
        text(canvas, it["name"], (d.centerx, d.y + 12), STAR, 11, "center")
        text(canvas, f"{KIND_KO[it['kind']]} · 성능 없음", (d.centerx, d.y + 26), ui.DIM, 11, "center")
        cx, cy = d.centerx, d.y + 80
        if it["kind"] == "title":
            text(canvas, f"「{it['name']}」", (cx, cy), STAR, 11, "center")
            text(canvas, "타이틀·포획 컷에 표시", (cx, cy + 20), ui.DIM, 11, "center")
        elif it["kind"] == "float_skin":
            top, base = [tuple(c) for c in it["colors"]]
            pygame.draw.rect(canvas, base, (cx - 5, cy - 2, 10, 18), border_radius=4)
            pygame.draw.rect(canvas, top, (cx - 5, cy - 16, 10, 16), border_radius=4)
            canvas.fill((240, 240, 240), (cx - 1, cy - 26, 2, 10))
        elif it["kind"] == "net_skin":
            rim, mesh = [tuple(c) for c in it["colors"]]
            pygame.draw.ellipse(canvas, rim, (cx - 26, cy - 10, 52, 20), 2)
            for k in range(-2, 3):
                pygame.draw.line(canvas, mesh, (cx + k * 9, cy + 6), (cx + k * 5, cy + 26), 1)
            pygame.draw.line(canvas, mesh, (cx - 18, cy + 14), (cx + 18, cy + 14), 1)
        else:
            rod, hi, reel = [tuple(c) for c in it["colors"]]
            pygame.draw.line(canvas, rod, (cx - 50, cy + 30), (cx + 40, cy - 30), 3)
            pygame.draw.line(canvas, hi, (cx - 50, cy + 29), (cx + 40, cy - 31), 1)
            pygame.draw.circle(canvas, reel, (cx - 34, cy + 26), 6)
        owned = quests.owns(self.save, it)
        on = quests.equipped(self.save)[quests.KIND_SLOT[it["kind"]][1]] == it["id"]
        if owned:
            self.buy_btn.label = "해제" if on else "장착"
            self.buy_btn.enabled = True
        else:
            pts = quests.root(self.save)["points"]
            self.buy_btn.label = f"구매 ({it.get('price', 0)}점)"
            self.buy_btn.enabled = pts >= it.get("price", 0)
        self.buy_btn.draw(canvas, self.mouse)
