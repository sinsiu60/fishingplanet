"""달력 (CORE_UPDATE.md CU1-2, DESIGN.md 52-0): 오늘부터 14일 예보 · 3시간 칸을 골라 그 시각까지 쉬기.

여는 곳: 수집 서랍 '달력' · 지도 [달력] · PC 단축키 K · 모바일 가방 → 수집 → 달력.
왼쪽 = 날짜 칸 7 × 2줄 (날짜 · 대표 날씨 · 아침/낮/저녁/밤 4색 막대 · 오늘 · 금색 점 = 전용 미끼를 가진 전설의 조건이 맞는 칸이 있는 날),
오른쪽 = ◀ 낚시터 ▶ + 고른 날 시간대 4줄 (그 안의 3시간 칸) + 전설 조건 문구 + 특별 날씨 줄 + 쉬기 버튼.
칸(또는 시간대 이름)을 누르면 버튼이 '내일 21:00까지 쉬기' → 모닥불 → 그 칸 시작 시각. 지난 · 지금 칸은 못 고름 (최대 14일 = rest_max_hours).
쉬는 곳은 늘 지금 자리 — 다른 낚시터 예보는 보기만 (쉰 뒤 이동은 지도에서, 1시간).
"""
import pygame

from src.core import forecast as fc
from src.core.config import game_config, load_json
from src.core.weather import CHANGE_EVERY, WEATHER_KO
from src.save.save_game import all_fish
from src.scene.base import Scene
from src.ui import weather_icons
from src.ui import widgets as ui
from src.ui.hud import draw_cursor, text

GOLD = (255, 214, 90)
GRID = pygame.Rect(12, 40, 7 * 32 + 6 * 2, 2 * 46 + 4)   # 날짜 칸 7 × 2 (칸 32×46 — 손가락 기준 32px 이상)
RIGHT = pygame.Rect(254, 26, 214, 226)
CELL = (34, 26)                                          # 3시간 칸


def _obj(word: str) -> str:
    """목적격 조사 (받침 있으면 '을')."""
    c = ord(word[-1]) - 0xAC00 if word else -1
    return "을" if 0 <= c < 11172 and c % 28 else "를"


class CalendarScene(Scene):
    UI_FRAME = True

    def __init__(self, game, fishing):
        super().__init__(game)
        self.fishing = fishing
        self.save = game.save
        self.mouse = (-100, -100)
        self.age = 0.0
        self.days = int(fc.cfg().get("days", 14))
        self.max_h = float(game_config()["time"].get("rest_max_hours", 336))
        spots = [s for s in load_json("spots.json")["spots"] if s["id"] in self.save.data.get("unlocked_spots", [])]
        self.spots = spots or [fishing.spot]
        self.si = next((i for i, s in enumerate(self.spots) if s["id"] == fishing.spot_id), 0)
        self.sel_day = fishing.clock.day
        self.sel_t: float | None = None          # 고른 쉬기 목표 (절대 시각)
        self.sel_key = None                      # 강조할 칸 (칸 번호) 또는 ("row", 시간대 id)
        self.spot_btns = [ui.Button((RIGHT.x, RIGHT.y, 18, 16), "<", lambda: self._spot(-1), size=11),
                          ui.Button((RIGHT.right - 18, RIGHT.y, 18, 16), ">", lambda: self._spot(1), size=11)]
        self.rest_btn = ui.Button((RIGHT.x, RIGHT.bottom - 22, RIGHT.w, 22), "", self._rest, size=11)
        self.close_btn = ui.Button((12, 246, 72, 15), "닫기 (K)", self._close)
        self.day_rects: list = []      # [(Rect, day)]
        self.cell_rects: list = []     # [(Rect, block, t0)]
        self.row_rects: list = []      # [(Rect, row)]
        self._cache: dict = {}

    # ── 데이터 ──
    @property
    def spot(self) -> dict:
        return self.spots[self.si]

    def _now(self) -> float:
        c = self.fishing.clock
        return c.day * 24.0 + c.hour

    def _summary(self, day: int) -> dict:
        key = (self.spot["id"], day, repr(self.save.data.get("weather_override")))
        s = self._cache.get(key)
        if s is None:
            ws = self.fishing.weather_sys
            s = fc.day_summary(ws, self.spot, day)
            legends = fc.legends_with_bait(self.save, self.spot, all_fish())
            s["legend"] = {}
            for r in s["rows"]:
                for b, w in zip(r["blocks"], r["weathers"]):
                    hits = fc.legend_hits(legends, b, w)
                    if hits:
                        s["legend"][b] = hits
            s["event"] = fc.event_plan(self.save, ws, self.spot, day)
            self._cache[key] = s
        return s

    def _selectable(self, t0: float) -> bool:
        now = self._now()
        return now < t0 <= now + self.max_h and int(t0 // CHANGE_EVERY) != int(now // CHANGE_EVERY)

    # ── 조작 ──
    def _spot(self, d: int) -> None:
        self.si = (self.si + d) % len(self.spots)
        self.game.sfx.play("ui_click")

    def _close(self) -> None:
        if self in self.game.scenes.stack:
            self.game.scenes.stack.remove(self)

    def _rest(self) -> None:
        f = self.fishing
        if self.sel_t is None:
            return
        if not f.can_rest():
            self.game.sfx.play("ui_error")
            return
        from src.save import item_use
        if item_use.tide_left(self.save) > 0:   # 물때 멈춤 소라 효과 중: 확인 창
            from src.scene.confirm import ConfirmScene
            self.game.scenes.push(ConfirmScene(self.game, "물때 멈춤이 끝나요. 쉴까요?", self._rest_now, "쉬기", "그만두기"))
            return
        self._rest_now()

    def _rest_now(self) -> None:
        from src.save import item_use
        from src.scene.campfire import CampfireScene
        from src.scene.map_scene import MapScene
        f = self.fishing
        hours = self.sel_t - self._now()
        if hours <= 0:
            return
        item_use.tide_end(self.game, f)
        self.game.sfx.play("ui_click")
        st = self.game.scenes.stack
        self._close()
        while st and isinstance(st[-1], MapScene):   # 지도에서 열었으면 지도도 닫음
            st.pop()
        f.rest_begin()
        self.game.scenes.push(CampfireScene(self.game, f, hours))

    def handle_action(self, a) -> None:
        if a.name == "back" or a.is_("menu", "calendar"):
            self._close()
            return
        if a.name != "primary" or a.pos is None:
            return
        m = self.ui_pointer()
        for b in (*self.spot_btns, self.rest_btn, self.close_btn):
            if b.click(m):
                return
        for r, day in self.day_rects:
            if r.collidepoint(m):
                if day != self.sel_day:
                    self.sel_day, self.sel_t, self.sel_key = day, None, None
                self.game.sfx.play("ui_click")
                return
        for r, blk, t0 in self.cell_rects:
            if r.collidepoint(m):
                self._pick(t0, blk)
                return
        for r, row in self.row_rects:
            if r.collidepoint(m):
                self._pick(row["t0"], ("row", row["id"]))
                return
        if not pygame.Rect(6, 6, 468, 260).collidepoint(m):   # 바깥 탭 = 닫기
            self._close()

    def _pick(self, t0: float, key) -> None:
        if not self._selectable(t0):
            self.game.sfx.play("ui_error")
            return
        self.sel_t, self.sel_key = t0, key
        self.game.sfx.play("ui_click")

    def update(self, dt: float) -> None:
        self.age += dt
        self.mouse = self.ui_pointer()

    # ── 그리기 ──
    def draw(self, canvas) -> None:
        ui.backdrop(canvas, self.fishing, int(170 * min(1.0, self.age / 0.15)), "calendar")
        canvas = self.ui_canvas(canvas)
        ui.panel(canvas, (6, 6, 468, 260))
        f = self.fishing
        text(canvas, "달력", (14, 16), ui.ACCENT, 16, "midleft")
        text(canvas, f"지금 {f.clock.label()} · {f.clock.day}일째", (GRID.right, 16), ui.DIM, 11, "midright")
        self._draw_days(canvas)
        self._draw_fest_band(canvas)
        self._draw_key(canvas)
        self._draw_detail(canvas)
        self.close_btn.draw(canvas, self.mouse)
        draw_cursor(canvas, self.mouse)

    def _draw_days(self, canvas) -> None:
        today = self.fishing.clock.day
        bars = fc.cfg()["bar_colors"]
        self.day_rects = []
        for k in range(self.days):
            day = today + k
            row, col = divmod(k, 7)
            r = pygame.Rect(GRID.x + col * 34, GRID.y + row * 50, 32, 46)
            self.day_rects.append((r, day))
            s = self._summary(day)
            sel = day == self.sel_day
            hov = r.collidepoint(self.mouse)
            canvas.fill((40, 48, 74) if sel else ((30, 36, 58) if hov else (22, 26, 44)), r)
            if k == 0:
                text(canvas, "오늘", (r.centerx, r.y + 7), ui.ACCENT, 11, "center")
            else:
                n = str(day)
                weather_icons.digits(canvas, n, r.x + 3, r.y + 3, (200, 206, 226))
            icon = pygame.transform.scale(weather_icons.icon(s["rep"]), (18, 18))
            canvas.blit(icon, (r.centerx - 9, r.y + 14))
            for i, rw in enumerate(s["rows"]):   # 아침 · 낮 · 저녁 · 밤 4색 막대
                canvas.fill(tuple(bars.get(rw["rep"], (200, 200, 200))), (r.x + 2 + i * 7, r.bottom - 7, 6, 4))
            if s["legend"]:
                canvas.fill(GOLD, (r.right - 6, r.y + 3, 3, 3))
            if s["event"]:
                canvas.fill((200, 170, 255), (r.right - 6, r.y + 8, 3, 2))
            from src.save import events_cal
            if events_cal.merchant_here(day):   # 떠돌이 상인이 오는 날 (CU12): 등롱 색 작은 점 2개
                canvas.fill((220, 70, 60), (r.x + 3, r.y + 34, 3, 3))
                canvas.fill((255, 214, 90), (r.x + 4, r.y + 32, 1, 2))
            pygame.draw.rect(canvas, ui.ACCENT if sel else ((255, 255, 255) if k == 0 else (60, 68, 96)), r, 1)

    def _draw_fest_band(self, canvas) -> None:
        """계절 축제 띠 (CU12): 실제 날짜로 14일 안에 열리는 축제 — 날짜 칸 아래 한 줄 + 상인 표시 설명."""
        from src.save import events_cal
        nf = events_cal.next_festival(14)
        y = GRID.bottom + 2
        if nf:
            k, f, d0 = nf
            on = events_cal.festival() is not None
            band = pygame.Rect(GRID.x, y, GRID.w, 12)
            canvas.fill(tuple(int(c * (0.55 if on else 0.3)) for c in f["color"]), band)
            label = f"{f['name']} {'진행 중' if on else f'{d0.month}/{d0.day}부터'} (실제 날짜 {f['from'].replace('-', '/')}~{f['to'].replace('-', '/')})"
            text(canvas, label, band.center, (255, 250, 240), 11, "center")

    def _draw_key(self, canvas) -> None:
        bars = fc.cfg()["bar_colors"]
        from src.save import events_cal
        x, y = GRID.x, GRID.bottom + (21 if events_cal.next_festival(14) else 12)   # 축제 띠가 있으면 한 줄 아래 (CU12)
        text(canvas, "막대 = 아침 · 낮 · 저녁 · 밤", (x, y), ui.DIM, 11, "midleft")
        y += 14
        for w in ("clear", "rain", "storm", "fog"):
            canvas.fill(tuple(bars[w]), (x, y - 2, 6, 4))
            r = text(canvas, WEATHER_KO[w], (x + 9, y), ui.DIM, 11, "midleft")
            x = r.right + 8
        x, y = GRID.x, y + 14
        canvas.fill(GOLD, (x + 1, y - 1, 3, 3))
        text(canvas, "전설을 만날 수 있는 칸 (전용 미끼)", (x + 9, y), ui.DIM, 11, "midleft")
        y += 14
        canvas.fill((200, 170, 255), (x + 1, y - 1, 3, 2))
        text(canvas, "특별한 날씨가 올지도", (x + 9, y), ui.DIM, 11, "midleft")
        y += 14
        canvas.fill((220, 70, 60), (x + 1, y - 1, 3, 3))
        text(canvas, "떠돌이 상인이 오는 날 (윤슬 마을)", (x + 9, y), ui.DIM, 11, "midleft")
        y += 16
        text(canvas, "칸을 눌러 그 시각까지 쉬어 가요", (GRID.x, y), (170, 200, 240), 11, "midleft")

    def _draw_detail(self, canvas) -> None:
        f = self.fishing
        today = f.clock.day
        ui.panel(canvas, RIGHT, fill=(16, 20, 36))
        for b in self.spot_btns:
            b.enabled = len(self.spots) > 1
            b.draw(canvas, self.mouse)
        here = self.spot["id"] == f.spot_id
        text(canvas, self.spot["name"] + (" (여기)" if here else ""), (RIGHT.centerx, RIGHT.y + 8),
             ui.ACCENT if here else ui.TEXT, 11, "center")
        s = self._summary(self.sel_day)
        text(canvas, f"{fc.day_word(self.sel_day, today)} · {self.sel_day}일째", (RIGHT.x + 6, RIGHT.y + 26), ui.TEXT, 11, "midleft")
        self.cell_rects, self.row_rects = [], []
        y = RIGHT.y + 36
        now = self._now()
        for rw in s["rows"]:
            rr = pygame.Rect(RIGHT.x + 4, y, 64, CELL[1])
            self.row_rects.append((rr, rw))
            ok = self._selectable(rw["t0"])
            rsel = self.sel_key == ("row", rw["id"])
            if rsel:
                canvas.fill((44, 52, 82), rr)
            h0 = int(rw["t0"] % 24)
            h1 = {"morning": 10, "day": 17, "evening": 20, "night": 6}[rw["id"]]
            col = (ui.ACCENT if rsel or (ok and rr.collidepoint(self.mouse)) else ui.TEXT) if ok else ui.DIM
            text(canvas, rw["name"], (rr.x + 3, rr.y + 7), col, 11, "midleft")
            text(canvas, f"{h0:02d}–{h1:02d}", (rr.x + 3, rr.y + 19), ui.DIM, 11, "midleft")
            for i, (blk, w) in enumerate(zip(rw["blocks"], rw["weathers"])):
                cr = pygame.Rect(RIGHT.x + 72 + i * (CELL[0] + 3), y, *CELL)
                t0 = blk * CHANGE_EVERY
                self.cell_rects.append((cr, blk, t0))
                past = t0 + CHANGE_EVERY <= now
                cur = int(now // CHANGE_EVERY) == blk
                canvas.fill((14, 16, 26) if past else ((36, 42, 66) if cr.collidepoint(self.mouse) else (26, 30, 50)), cr)
                hh = int(t0 % 24)
                if cur:   # 지금 칸: 시각 자리에 '지금'
                    text(canvas, "지금", (cr.centerx, cr.y + 6), (255, 255, 255), 11, "center")
                else:
                    weather_icons.digits(canvas, f"{hh:02d}", cr.x + 3, cr.y + 3, ui.DIM if past else (210, 216, 236))
                img = weather_icons.icon(w)
                if past:
                    img = img.copy()
                    img.set_alpha(90)
                canvas.blit(img, (cr.centerx - 4, cr.y + 13))
                if blk in s["legend"]:
                    pygame.draw.rect(canvas, GOLD, cr, 1)
                    canvas.fill(GOLD, (cr.right - 5, cr.y + 2, 3, 3))
                if cur:
                    pygame.draw.rect(canvas, (255, 255, 255), cr, 1)
                if self.sel_key == blk:
                    pygame.draw.rect(canvas, ui.ACCENT, cr.inflate(2, 2), 1)
            y += CELL[1] + 4
        y += 4
        lines = []
        seen = set()
        for rw in s["rows"]:
            for blk, w in zip(rw["blocks"], rw["weathers"]):
                for fi in s["legend"].get(blk, []):
                    key = (rw["id"], w, fi["id"])
                    if key not in seen:
                        seen.add(key)
                        nm = fi["name"].split()[-1]
                        lines.append((f"★ {rw['name']} · {WEATHER_KO[w]}: '{nm}'{_obj(nm)} 만날 수 있어요", GOLD))
        if s["event"]:
            e = s["event"]
            lines.append((f"✦ {int(e['start']):02d}:00 무렵 '{e['name']}'가 올지도", (200, 170, 255)))
        for ln, col in lines[:3]:
            text(canvas, ln, (RIGHT.x + 6, y), col, 11, "midleft")
            y += 13
        self.rest_btn.enabled = self.sel_t is not None and f.can_rest()
        if self.sel_t is None:
            self.rest_btn.label = "칸을 골라 쉬어 가요"
        elif not f.can_rest():
            self.rest_btn.label = "지금은 쉴 수 없어요"
        else:
            self.rest_btn.label = f"{fc.until_label(self.sel_t, today)}까지 쉬기"
        self.rest_btn.draw(canvas, self.mouse)
