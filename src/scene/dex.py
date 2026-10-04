"""도감: 낚시터별 카드, 못 잡은 물고기는 실루엣 + ???, S랭크 금테, 3회·10회 힌트."""
import math

import pygame

from src.core.config import load_json
from src.core.mathutil import lerp_color
from src.core.weather import WEATHER_KO
from src.render.fish_draw import RANK_COLORS, draw_fish_fit
from src.save.save_game import baits
from src.fishing.patterns import TIP_SHORT, fish_patterns
from src.fishing import mutation
from src.fishing.lure import profile_of
from src.scene.base import Scene
from src.ui import widgets as ui
from src.ui.hud import draw_cursor, text, wrap_text
from src.scene.inventory import fit

SPOT_TABS = [("reservoir", "저수지"), ("valley", "계곡"), ("breakwater", "방파제"), ("offshore", "먼바다"),
             ("deep", "심해"), ("secret", "비밀")]
ELDRA_TABS = [("marsh", "습지"), ("crystal_cave", "동굴"), ("sky_falls", "부유섬"), ("volcano", "화산"),
              ("ice_sea", "빙해"), ("world_tree", "세계수")]
CONT_TABS = {"sharmion": SPOT_TABS, "eldrasion": ELDRA_TABS}
TIME_KO = {"morning": "아침", "day": "낮", "evening": "저녁", "night": "밤"}
RARITY_KO = {"common": "일반", "uncommon": "고급", "rare": "희귀", "phantom": "환상", "legend": "전설"}
RARITY_COL = {"common": (230, 230, 230), "uncommon": (130, 230, 150), "rare": (130, 190, 255),
              "phantom": (190, 120, 255), "legend": (255, 214, 90)}
GOLD = (255, 214, 90)
CARD_W, CARD_H = 69, 46          # 일반·고급·희귀 (4열 × 2줄)
COLS = 4
GRID_X, GRID_Y = 14, 50
BOSS = pygame.Rect(GRID_X, GRID_Y + 2 * (CARD_H + 4) + 2, 4 * CARD_W + 3 * 4, 94)  # 전설 = 이 낚시터의 보스 칸
DETAIL = pygame.Rect(306, 50, 160, 196)


def _join(values, table, all_count) -> str:
    return "전체" if len(values) >= all_count else "·".join(table[v] for v in values)


MUT_COL = (255, 190, 120)
STAR_ON, STAR_OFF = (255, 220, 110), (70, 72, 90)


def draw_stars(canvas, x: int, y: int, flags: list[bool], gap: int = 6) -> None:
    """도감 별 5개 (작은 십자 별, 채움 = 금색)."""
    for i, on in enumerate(flags):
        cx = x + i * gap
        col = STAR_ON if on else STAR_OFF
        canvas.fill(col, (cx - 1, y, 3, 1))
        canvas.fill(col, (cx, y - 1, 1, 3))


class DexScene(Scene):
    UI_FRAME = True

    def __init__(self, game, fishing, phantom_tab: bool = False):
        super().__init__(game)
        self.fishing = fishing
        self.save = game.save
        from src.ui import signal_slots
        signal_slots.configure(game.settings)  # 색약 모드 신호색 (31장 C6)
        self.mouse = (0, 0)
        self.age = 0.0  # 열림 애니메이션
        self.fish = load_json("fish.json")["fish"]
        self.cont = "eldrasion" if fishing.spot_id in dict(ELDRA_TABS) else "sharmion"
        self._make_tabs()
        self.cont_btn = ui.Button((310, 30, 92, 16), "", self._switch)
        self.sel = 0
        self.t = 0.0
        self.close_btn = ui.Button((406, 250, 60, 15), "닫기 (Tab)", self._close)
        self.mut_mode = False  # 변이 도감 (U5): 물고기 × 변이 칸
        self.mut_btn = ui.Button((52, 9, 64, 15), "변이 도감", self._toggle_mut)
        # 패턴 사전 (31장 C5): 본 신호 카드를 다시 보기
        self.pat_mode = False
        self.pat_btn = ui.Button((120, 9, 64, 15), "패턴 사전", self._toggle_pat)
        self.pat_card = None  # 열어 둔 카드 {"key", "t"}
        # 환상 도감 (33장 P6): 첫 환상어 포획 튜토리얼 뒤에만 탭이 생긴다 — 잡은 환상어만 보인다
        from src.fishing import phantom
        self.ph_on = phantom.state(self.save)["tutorial"]
        self.ph_mode = phantom_tab and self.ph_on
        self.ph_btn = ui.Button((188, 9, 52, 15), "환상", self._toggle_ph)
        self.ph_sel = 0
        # 도감 별 보상 (35-2): 도감 포인트 · 보상 · 표지 · 칭호 장착
        self.star_mode = False
        self.star_btn = ui.Button((244, 9, 56, 15), "별 보상", self._toggle_star)
        self.print_btn = ui.Button((244, 232, 76, 15), "어탁 갤러리", self._open_prints)
        # 계절·날씨 이벤트 한정 (35-4): 도감 % 밖, 계절 표시
        self.lim_mode = False
        self.lim_btn = ui.Button((304, 9, 34, 15), "한정", self._toggle_lim)
        self.lim_sel = 0
        self.title_page = 0

    def _toggle_mut(self) -> None:
        self.mut_mode = not self.mut_mode
        self.pat_mode = False
        self.ph_mode = False
        self.star_mode = False
        self.lim_mode = False

    def _toggle_star(self) -> None:
        self.star_mode = not self.star_mode
        self.mut_mode = self.pat_mode = self.ph_mode = self.lim_mode = False

    def _toggle_lim(self) -> None:
        self.lim_mode = not self.lim_mode
        self.mut_mode = self.pat_mode = self.ph_mode = self.star_mode = False

    def _lim_list(self) -> list[dict]:
        from src.save.dexbook import limited_fish
        order = {"spring": 0, "summer": 1, "autumn": 2, "winter": 3}
        return sorted(limited_fish(), key=lambda f: (f.get("continent", "z"), order.get(f.get("season"), 9)))

    def _toggle_ph(self) -> None:
        self.ph_mode = not self.ph_mode
        self.star_mode = False
        self.pat_mode = self.mut_mode = False
        self.lim_mode = False

    def _ph_list(self) -> list[dict]:
        from src.fishing import phantom
        return [f for f in phantom.all_phantoms() if phantom.caught(self.save, f["id"])]

    def _toggle_pat(self) -> None:
        self.pat_mode = not self.pat_mode
        self.mut_mode = False
        self.ph_mode = False
        self.star_mode = False
        self.lim_mode = False

    PAT_KEYS = ("telegraph:rush", "telegraph:jump", "telegraph:turn", "telegraph:leap", "pattern:shake", "pattern:dive",
                "pattern:surface", "pattern:reverse", "pattern:twist", "pattern:chain", "pattern:hide", "pattern:pump",
                "pattern:thrash", "pattern:bite", "pattern:dual")

    def _pat_seen(self, key: str) -> bool:
        pid = key.split(":", 1)[1]
        return self.fishing.tutorial.is_seen(key) or pid in self.save.data.get("patterns_seen", [])

    def _pat_rect(self, i: int) -> pygame.Rect:
        return pygame.Rect(18 + (i % 5) * 90, 52 + (i // 5) * 62, 84, 56)

    def _make_tabs(self) -> None:
        tabs = CONT_TABS[self.cont]
        self.tabs = ui.Tabs(14, 30, [t[1] for t in tabs], width=46)
        self.tabs.index = next((i for i, t in enumerate(tabs) if t[0] == self.fishing.spot_id), 0)

    def _switch(self) -> None:
        self.cont = "eldrasion" if self.cont == "sharmion" else "sharmion"
        self._make_tabs()
        self.sel = 0

    RARITY_ORDER = {"common": 0, "uncommon": 1, "rare": 2, "legend": 3}

    def spot_fish(self) -> list[dict]:
        """그 낚시터 물고기: 일반 → 고급 → 희귀 → 전설 (왼쪽 위부터, 같은 등급은 fish.json 순서)."""
        lst = [f for f in self.fish if f["spot"] == CONT_TABS[self.cont][self.tabs.index][0]]
        return sorted(lst, key=lambda f: self.RARITY_ORDER.get(f["rarity"], 9))

    def card_rect(self, i: int) -> pygame.Rect:
        fishes = self.spot_fish()
        if 0 <= i < len(fishes) and fishes[i]["rarity"] == "legend":
            return BOSS
        return pygame.Rect(GRID_X + (i % COLS) * (CARD_W + 4), GRID_Y + (i // COLS) * (CARD_H + 4), CARD_W, CARD_H)

    def _close(self) -> None:
        self.game.scenes.pop()

    def handle_action(self, a) -> None:
        if a.name == "back" or a.is_("menu", "dex"):
            self._close()
        elif a.name == "primary":
            m = a.pos
            if self.pat_card is not None:
                if self.pat_card["t"] > 0.3:
                    self.pat_card = None
                return
            if self.pat_btn.click(m):
                self.game.sfx.play("ui_click")
                return
            if self.star_btn.click(m):
                self.game.sfx.play("ui_click")
                return
            if self.lim_btn.click(m):
                self.game.sfx.play("ui_click")
                return
            if self.lim_mode:
                for i in range(len(self._lim_list())):
                    if self.card_rect_lim(i).collidepoint(m):
                        self.lim_sel = i
                        self.game.sfx.play("ui_click")
                self.close_btn.click(m)
                return
            if self.star_mode:
                self._star_click(m)
                self.close_btn.click(m)
                return
            if self.ph_on and self.ph_btn.click(m):
                self.game.sfx.play("ui_click")
                return
            if self.ph_mode:
                for i in range(len(self._ph_list())):
                    if self.card_rect_ph(i).collidepoint(m):
                        self.ph_sel = i
                        self.game.sfx.play("ui_click")
                self.close_btn.click(m)
                return
            if self.pat_mode:
                for i, key in enumerate(self.PAT_KEYS):
                    if self._pat_rect(i).collidepoint(m) and self._pat_seen(key):
                        self.pat_card = {"key": key, "t": 0.0}
                        self.game.sfx.play("ui_click")
                if self.close_btn.click(m):
                    return
                return
            if self.tabs.click(m):
                self.sel = 0
                self.game.sfx.play("ui_tab")
                return
            if self.close_btn.click(m):
                return
            if mutation.unlocked(self.save) and self.mut_btn.click(m):
                self.game.sfx.play("ui_click")
                return
            if "eldrasion" in self.save.data["unlocked_continents"] and self.cont_btn.click(m):
                self.game.sfx.play("ui_click")
                return
            for i in range(len(self.spot_fish())):
                if self.card_rect(i).collidepoint(m):
                    self.sel = i
                    self.game.sfx.play("ui_click")

    def update(self, dt: float) -> None:
        self.age += dt
        self.t += dt
        if self.pat_card is not None:
            self.pat_card["t"] += dt
        self.mouse = self.ui_pointer()

    def draw(self, canvas) -> None:
        self.fishing.draw(canvas)
        ui.dim(canvas, int(180 * min(1.0, self.age / 0.15)))
        canvas = self.ui_canvas(canvas)
        ui.panel(canvas, (6, 6, 468, 260))
        self._draw_cover(canvas)
        total = len(self.fish)
        got = self.save.dex_count()
        golds = sum(1 for e in self.save.data["dex"].values() if e.get("best_rank") == "S")
        text(canvas, "도감", (14, 16), ui.ACCENT, 16, "midleft")
        if self.mut_mode:
            n, cap = mutation.dex_count(self.save), self._mut_total()
            nxt = next((r for r in mutation.cfg()["dex_rewards"] if r["count"] > n), None)
            tail = f" · 다음 보상 {nxt['count']}: {nxt['name']}" if nxt else " · 보상 모두 받음"
            text(canvas, f"변이 {n}/{cap}{tail}", (466, 16), MUT_COL, 11, "midright")
        else:
            text(canvas, f"{got}/{total}종 ({got * 100 // total}%) · 금테 {golds}", (466, 16), ui.ACCENT, 11, "midright")
        if mutation.unlocked(self.save):
            self.mut_btn.label = "기본 도감" if self.mut_mode else "변이 도감"
            self.mut_btn.draw(canvas, self.mouse)
        self.pat_btn.label = "기본 도감" if self.pat_mode else "패턴 사전"
        self.pat_btn.draw(canvas, self.mouse)
        self.star_btn.label = "기본 도감" if self.star_mode else "별 보상"
        self.star_btn.draw(canvas, self.mouse)
        self.lim_btn.label = "기본" if self.lim_mode else "한정"
        self.lim_btn.draw(canvas, self.mouse)
        if self.lim_mode:
            self._draw_limited(canvas)
            self.close_btn.draw(canvas, self.mouse)
            draw_cursor(canvas, self.mouse)
            return
        if self.star_mode:
            self._draw_star_page(canvas)
            self.close_btn.draw(canvas, self.mouse)
            draw_cursor(canvas, self.mouse)
            return
        if self.ph_on:
            self.ph_btn.label = "기본 도감" if self.ph_mode else "환상"
            self.ph_btn.draw(canvas, self.mouse)
        if self.ph_mode:
            self._draw_phantoms(canvas)
            self.close_btn.draw(canvas, self.mouse)
            draw_cursor(canvas, self.mouse)
            return
        if self.pat_mode:
            self._draw_patterns(canvas)
            self.close_btn.draw(canvas, self.mouse)
            if self.pat_card is not None:
                from src.ui import tutorial as tut
                tut.draw_card(canvas, self.pat_card["key"], None, self.pat_card["t"], self.fishing.touch)
            draw_cursor(canvas, self.mouse)
            return
        self.tabs.draw(canvas, self.mouse)
        if "eldrasion" in self.save.data["unlocked_continents"]:
            self.cont_btn.label = "엘드라시온 >" if self.cont == "sharmion" else "< 샤르미온"
            self.cont_btn.draw(canvas, self.mouse)
        fishes = self.spot_fish()
        from src.save import dexbook
        got_s, max_s = dexbook.spot_stars(self.save, CONT_TABS[self.cont][self.tabs.index][0])
        text(canvas, f"★ {got_s}/{max_s}", (466, 38), STAR_ON, 11, "midright")
        self.sel = min(self.sel, len(fishes) - 1)
        for i, f in enumerate(fishes):
            self._draw_card(canvas, i, f)
            if self.mut_mode:
                self._draw_mut_dots(canvas, i, f)
        if self.mut_mode:
            self._draw_mut_detail(canvas, fishes[self.sel])
        else:
            self._draw_detail(canvas, fishes[self.sel])
        self.close_btn.draw(canvas, self.mouse)
        draw_cursor(canvas, self.mouse)

    def _draw_patterns(self, canvas) -> None:
        """패턴 사전: 신호 아이콘 + 이름. 본 것만 눌러서 첫 만남 카드를 다시 본다 (모르는 것은 ???)."""
        from src.ui import signal_slots as ss
        from src.ui import tutorial as tut
        text(canvas, "본 신호를 누르면 그때 카드를 다시 볼 수 있어요", (466, 36), (170, 180, 200), 11, "midright")
        for i, key in enumerate(self.PAT_KEYS):
            r = self._pat_rect(i)
            seen = self._pat_seen(key)
            hover = r.collidepoint(self.mouse) and seen
            canvas.fill((30, 36, 58) if hover else (20, 24, 40), r)
            pid = key.split(":", 1)[1]
            fam = ss.family_of(pid)
            col = ss.color_of(fam) if seen and fam in ss.cfg()["families"] else (90, 96, 120)
            pygame.draw.rect(canvas, col, r, 1, border_radius=6)
            if seen:
                if fam in ss.cfg()["families"]:
                    dirv = (0, -1) if pid == "dive" else (0, 1) if pid == "surface" else (1, 0)
                    ss.family_icon(canvas, fam, r.centerx, r.y + 20, col, self.t, dir=dirv)
                else:
                    from src.ui import icons
                    icons.pips(canvas, r.centerx, r.y + 20, 3 if pid == "chain" else 2, (255, 214, 90), 7)
                text(canvas, tut.CARDS[key][0].rstrip("!"), (r.centerx, r.bottom - 11), (232, 236, 245), 11, "center")
            else:
                text(canvas, "???", (r.centerx, r.centery), (110, 116, 140), 16, "center")

    def _mut_total(self) -> int:
        return sum(len(mutation.ORDER) for f in self.fish if f["rarity"] != "legend")

    def _draw_mut_dots(self, canvas, i: int, f: dict) -> None:
        """카드 위쪽에 변이 7칸 (잡아 본 변이는 그 색으로)."""
        r = self.card_rect(i)
        if f["rarity"] == "legend":
            return
        got = self.save.data.get("mutation_dex", {}).get(f["id"], [])
        kinds = mutation.cfg()["kinds"]
        x0 = r.x + 4
        for k, m in enumerate(mutation.ORDER):
            box = pygame.Rect(x0 + k * 7, r.y + 3, 5, 5)
            if m in got:
                canvas.fill(tuple(kinds[m]["color"]), box)
            else:
                pygame.draw.rect(canvas, (60, 66, 90), box, 1)

    def _draw_mut_detail(self, canvas, f: dict) -> None:
        d = DETAIL
        ui.panel(canvas, d, fill=(16, 20, 36))
        x, y = d.x + 6, d.y + 10
        name = f["name"] if self.save.dex_entry(f["id"]) else "???"
        text(canvas, f"{name} · 변이", (d.centerx, y), MUT_COL, 11, "center")
        y += 16
        if f["rarity"] == "legend":
            text(canvas, "전설은 변이하지 않는다", (d.centerx, y + 10), ui.DIM, 11, "center")
        else:
            got = self.save.data.get("mutation_dex", {}).get(f["id"], [])
            kinds = mutation.cfg()["kinds"]
            for m in mutation.ORDER:
                have = m in got
                col = tuple(kinds[m]["color"]) if have else ui.DIM
                text(canvas, f"{'v' if have else '·'} {kinds[m]['name']}", (x, y), col, 11, "midleft")
                if have:
                    text(canvas, kinds[m]["desc"].split(" · ")[-1][:14], (x + 52, y), ui.DIM, 11, "midleft")
                y += 13
        y += 6
        n = mutation.dex_count(self.save)
        text(canvas, "수집 보상", (x, y), ui.ACCENT, 11, "midleft")
        y += 13
        for rw in mutation.cfg()["dex_rewards"]:
            done = n >= rw["count"]
            text(canvas, f"{'v' if done else '·'} {rw['count']}종: {rw['name']}", (x, y), ui.GOOD if done else ui.DIM, 11,
                 "midleft")
            y += 12

    def card_rect_ph(self, i: int) -> pygame.Rect:
        return pygame.Rect(GRID_X + (i % COLS) * (CARD_W + 4), GRID_Y + (i // COLS) * (CARD_H + 4) + 8, CARD_W, CARD_H)

    def _draw_phantoms(self, canvas) -> None:
        """환상 도감: 잡은 환상어만 (보라 칸) + 진행도 n / 12. 못 잡은 건 칸 자체가 없다."""
        from src.fishing import phantom
        col = phantom.COLOR
        fl = self._ph_list()
        text(canvas, f"환상  {len(fl)} / {len(phantom.all_phantoms())}", (GRID_X + 2, 40), col, 11, "midleft")
        for i, f in enumerate(fl):
            r = self.card_rect_ph(i)
            sel = i == self.ph_sel
            ui.panel(canvas, r, col if sel else (110, 70, 160), (40, 20, 60) if sel or r.collidepoint(self.mouse) else (24, 14, 40))
            draw_fish_fit(canvas, pygame.Rect(r.x + 3, r.y + 3, r.w - 6, r.h - 19), f, 52)
            text(canvas, fit(f["name"], r.w - 6), (r.centerx, r.bottom - 8), phantom.COLOR_LIGHT, 11, "center")
            from src.save import dexbook
            draw_stars(canvas, r.x + 5, r.y + 5, dexbook.stars(self.save, f), 5)
        d = DETAIL
        ui.panel(canvas, d, (110, 70, 160), (16, 12, 30))
        if not fl:
            return
        self.ph_sel = min(self.ph_sel, len(fl) - 1)
        f = fl[self.ph_sel]
        e = phantom.state(self.save)["caught"][f["id"]]
        y = d.y + 10
        text(canvas, f["name"], (d.centerx, y), phantom.COLOR_LIGHT, 11, "center")
        draw_fish_fit(canvas, pygame.Rect(d.x + 8, y + 8, d.w - 16, 48), f, 120)
        y += 64
        spot = next((s for s in load_json("spots.json")["spots"] if s["id"] == f["spot"]), {})
        for ln, c in ((f"환상 · {spot.get('name', '')}", col),
                      (f"최대 {e['max_size']:.1f}cm · 최고 {e['best_rank']} · {e['count']}회", ui.ACCENT),
                      (self._mastery_line(f), (170, 255, 200))):
            text(canvas, ln, (d.x + 6, y), c, 11, "midleft")
            y += 14
        for ln in wrap_text(f["desc"], d.w - 12)[:4]:
            text(canvas, ln, (d.x + 6, y), ui.DIM, 11, "midleft")
            y += 13

    def _season_rows(self, f: dict) -> list:
        """'잘 잡히는 계절' (35-4, data/seasons.json)."""
        from src.core import season as seasons
        sf = load_json("seasons.json")["fish"].get(f["id"])
        if not sf:
            return []
        cont = "eldrasion" if f["spot"] in dict(ELDRA_TABS) else "sharmion"
        good = "·".join(seasons.name(s, cont) for s in sf["good"])
        return [(f"잘 잡히는 계절: {good}", (255, 200, 220))]

    def card_rect_lim(self, i: int) -> pygame.Rect:
        return pygame.Rect(GRID_X + (i % COLS) * (CARD_W + 4), GRID_Y + (i // COLS) * (CARD_H + 4) + 8, CARD_W, CARD_H)

    def _lim_label(self, f: dict) -> str:
        from src.core import season as seasons
        cont = f.get("continent", "sharmion")
        if f.get("season"):
            return f"{seasons.name(f['season'], cont)} 한정 · {'샤르미온' if cont == 'sharmion' else '엘드라시온'} 어디서나"
        return f"날씨 이벤트 '{f.get('event_name', '')}' 중에만"

    def _draw_limited(self, canvas) -> None:
        """계절·이벤트 한정: 칸마다 계절 표시. 도감 %·해금 조건에는 들어가지 않는다."""
        from src.core import season as seasons
        from src.save import dexbook
        fl = self._lim_list()
        got = sum(1 for f in fl if dexbook.entry(self.save, f))
        text(canvas, f"계절·이벤트 한정  {got} / {len(fl)}  (도감 %에는 안 들어가요)", (GRID_X + 2, 40), (255, 200, 220), 11, "midleft")
        scol = {"spring": (255, 170, 200), "summer": (120, 210, 100), "autumn": (230, 140, 60), "winter": (190, 220, 255)}
        for i, f in enumerate(fl):
            r = self.card_rect_lim(i)
            e = dexbook.entry(self.save, f)
            sel = i == self.lim_sel
            col = scol.get(f.get("season"), (200, 220, 255))
            ui.panel(canvas, r, col if sel else ui.BORDER, ui.PANEL_LIGHT if sel or r.collidepoint(self.mouse) else (16, 20, 36))
            draw_fish_fit(canvas, pygame.Rect(r.x + 3, r.y + 3, r.w - 6, r.h - 19), f, 52, silhouette=None if e else (8, 8, 14))
            text(canvas, fit(f["name"], r.w - 6) if e else "???", (r.centerx, r.bottom - 8), RARITY_COL.get(f["rarity"], ui.TEXT), 11, "center")
            mark = seasons.ICON.get(f.get("season"), "★")
            pygame.draw.circle(canvas, col, (r.right - 8, r.y + 8), 6)
            text(canvas, mark, (r.right - 8, r.y + 8), (30, 30, 40), 11, "center")
            if e:
                draw_stars(canvas, r.x + 5, r.y + 5, dexbook.stars(self.save, f), 5)
        d = DETAIL
        ui.panel(canvas, d, ui.BORDER, (16, 20, 36))
        if not fl:
            return
        self.lim_sel = min(self.lim_sel, len(fl) - 1)
        f = fl[self.lim_sel]
        e = dexbook.entry(self.save, f)
        y = d.y + 10
        text(canvas, f["name"] if e else "???", (d.centerx, y), RARITY_COL.get(f["rarity"], ui.TEXT), 11, "center")
        y += 16
        rows = [(f"{RARITY_KO[f['rarity']]} · {self._lim_label(f)}", (255, 200, 220))]
        if e:
            rows += [(f"최대 {e['max_size']:.1f}cm · 최고 {e['best_rank']} · {e['count']}회", ui.ACCENT),
                     (self._mastery_line(f), (170, 255, 200))]
        for ln, c in rows:
            for w_ in wrap_text(ln, d.w - 12):
                text(canvas, w_, (d.x + 6, y), c, 11, "midleft")
                y += 13
        y += 3
        for ln in wrap_text(f["desc"] if e else "그때가 오면 어딘가에서 모습을 드러낸다고 한다.", d.w - 12)[:3]:
            text(canvas, ln, (d.x + 6, y), ui.DIM, 11, "midleft")
            y += 12
        if e and e["count"] >= 3:
            for ln in wrap_text("· " + f.get("hint3", ""), d.w - 12)[:2]:
                text(canvas, ln, (d.x + 6, y + 4), (150, 230, 255), 11, "midleft")
                y += 12

    def _mastery_line(self, f: dict) -> str:
        from src.save import dexbook
        m = dexbook.mastery(self.save, f)
        nxt = dexbook.next_mastery(self.save, f)
        tail = f" ({nxt[0]}/{nxt[1]})" if nxt else " 달인"
        return f"숙련 {m}단계{tail} · ★{dexbook.star_count(self.save, f)}/5"

    # ── 도감 별 보상 페이지 (35-2) ──
    REW_X, REW_Y = 14, 52
    TITLE_RECT = pygame.Rect(244, 52, 222, 176)

    def _titles(self) -> list[dict]:
        from src.save import quests
        out = []
        for tid in quests.cosmetics(self.save)["titles"]:
            it = quests.shop_item(tid)
            if it:
                out.append(it)
        return out

    def _cover_btns(self) -> list[tuple[pygame.Rect, str | None]]:
        from src.save import dexbook
        b = dexbook.book(self.save)
        owned = [c for c in dexbook.covers() if f"cover:{c['id']}" in b["claimed"]]
        out = [(pygame.Rect(14 + i * 56, 216, 52, 14), c["id"]) for i, c in enumerate(owned)]
        if owned:
            out.append((pygame.Rect(14 + len(owned) * 56, 216, 40, 14), None))
        return out

    def _open_prints(self) -> None:
        from src.scene.print_gallery import PrintGalleryScene
        self.game.scenes.push(PrintGalleryScene(self.game, self.fishing))

    def _star_click(self, m) -> None:
        from src.save import dexbook, quests
        if self.print_btn.click(m):
            self.game.sfx.play("ui_click")
            return
        for r, cid in self._cover_btns():
            if r.collidepoint(m):
                dexbook.book(self.save)["cover"] = cid
                self.game.sfx.play("ui_click")
                return
        titles = self._titles()
        per = 10
        for j, it in enumerate(titles[self.title_page * per:(self.title_page + 1) * per]):
            r = pygame.Rect(self.TITLE_RECT.x + 4, self.TITLE_RECT.y + 18 + j * 15, self.TITLE_RECT.w - 8, 14)
            if r.collidepoint(m):
                quests.toggle_equip(self.save, it["id"])
                self.game.sfx.play("ui_click")
                return
        pages = max(1, (len(titles) + per - 1) // per)
        nav = pygame.Rect(self.TITLE_RECT.right - 40, self.TITLE_RECT.bottom - 16, 36, 14)
        if nav.collidepoint(m) and pages > 1:
            self.title_page = (self.title_page + 1) % pages
            self.game.sfx.play("ui_click")

    def _draw_star_page(self, canvas) -> None:
        from src.save import dexbook, quests
        pts, cap = dexbook.points(self.save), dexbook.max_points(self.save)
        text(canvas, f"도감 포인트 ★ {pts} / {cap}", (14, 38), STAR_ON, 11, "midleft")
        rule = "(전설·환상 3회)" if self.ph_on else "(전설 3회)"   # 환상 튜토리얼 전엔 '환상' 단어 없음
        text(canvas, f"별: 첫 포획 · S랭크 · 대물 · 변이 3종{rule} · 숙련 5", (466, 38), ui.DIM, 11, "midright")
        claimed = dexbook.book(self.save)["claimed"]
        kind_ko = {"title": "칭호", "float_skin": "찌", "rod_skin": "낚싯대", "net_skin": "뜰채", "cover": "표지"}
        for i, rw in enumerate(dexbook.cfg()["rewards"]):
            y = self.REW_Y + i * 17
            got = f"{rw['kind']}:{rw['id']}" in claimed
            col = STAR_ON if got else (ui.TEXT if pts >= rw["points"] else ui.DIM)
            text(canvas, f"★{rw['points']:>3}", (self.REW_X, y + 6), col, 11, "midleft")
            text(canvas, f"{kind_ko[rw['kind']]} '{rw['name']}'", (self.REW_X + 40, y + 6), col, 11, "midleft")
            text(canvas, "받음" if got else f"{min(pts, rw['points'])}/{rw['points']}", (236, y + 6),
                 ui.GOOD if got else ui.DIM, 11, "midright")
        btns = self._cover_btns()
        if btns:
            text(canvas, "표지", (14, 208), ui.TEXT, 11, "midleft")
            cur = dexbook.book(self.save)["cover"]
            for r, cid in btns:
                name = next((c["name"] for c in dexbook.covers() if c["id"] == cid), "기본")
                on = cid == cur
                ui.panel(canvas, r, STAR_ON if on else ui.BORDER, ui.PANEL_LIGHT if r.collidepoint(self.mouse) else (16, 20, 36))
                text(canvas, fit(name, r.w - 4), r.center, STAR_ON if on else ui.TEXT, 11, "center")
        # 칭호 장착 (의뢰 상점·변이·환상·도감 보상·달인 칭호 전부)
        self.print_btn.label = f"어탁 {len(self.save.data.get('prints', {}))}장"
        self.print_btn.draw(canvas, self.mouse)
        tr = self.TITLE_RECT
        ui.panel(canvas, tr, ui.BORDER, (16, 20, 36))
        text(canvas, "칭호 (눌러서 장착/해제)", (tr.x + 6, tr.y + 8), ui.ACCENT, 11, "midleft")
        titles = self._titles()
        cur = quests.equipped(self.save)["title"]
        per = 10
        pages = max(1, (len(titles) + per - 1) // per)
        self.title_page = min(self.title_page, pages - 1)
        if not titles:
            text(canvas, "아직 칭호가 없어요", (tr.centerx, tr.y + 40), ui.DIM, 11, "center")
        for j, it in enumerate(titles[self.title_page * per:(self.title_page + 1) * per]):
            r = pygame.Rect(tr.x + 4, tr.y + 18 + j * 15, tr.w - 8, 14)
            on = it["id"] == cur
            if r.collidepoint(self.mouse):
                canvas.fill(ui.PANEL_LIGHT, r)
            text(canvas, ("▶ " if on else "  ") + fit(f"「{it['name']}」", r.w - 20), (r.x + 2, r.centery),
                 STAR_ON if on else ui.TEXT, 11, "midleft")
        if pages > 1:
            nav = pygame.Rect(tr.right - 40, tr.bottom - 16, 36, 14)
            ui.panel(canvas, nav, ui.BORDER, (16, 20, 36))
            text(canvas, f"{self.title_page + 1}/{pages}▶", nav.center, ui.TEXT, 11, "center")

    def _draw_cover(self, canvas) -> None:
        """도감 표지 꾸미기: 테두리 색 + 모서리 장식."""
        from src.save import dexbook
        c = dexbook.cover_of(self.save)
        if not c:
            return
        r = pygame.Rect(6, 6, 468, 260)
        pygame.draw.rect(canvas, tuple(c["frame"]), r, 2)
        pygame.draw.rect(canvas, lerp_color(tuple(c["frame"]), (0, 0, 0), 0.5), r.inflate(-6, -6), 1)
        for x, y in (r.topleft, r.topright, r.bottomleft, r.bottomright):
            pts = [(x, y - 5), (x + 5, y), (x, y + 5), (x - 5, y)]
            pygame.draw.polygon(canvas, tuple(c["corner"]), pts)

    def _draw_card(self, canvas, i: int, f: dict) -> None:
        if f["rarity"] == "legend":
            self._draw_boss(canvas, i, f)
            return
        r = self.card_rect(i)
        entry = self.save.dex_entry(f["id"])
        gold = entry is not None and entry["best_rank"] == "S"
        sel = i == self.sel
        hov = r.collidepoint(self.mouse)
        border = GOLD if gold else (ui.ACCENT if sel else (ui.TEXT if hov else ui.BORDER))
        ui.panel(canvas, r, border, ui.PANEL_LIGHT if sel or hov else (16, 20, 36))
        if gold:
            # 금테: 두 겹 + 반짝
            pygame.draw.rect(canvas, (180, 140, 40), r.inflate(-4, -4), 1)
            k = (self.t * 0.6 + i * 0.13) % 1.0
            px = r.x + int(k * r.w)
            canvas.fill((255, 255, 230), (px, r.y, 3, 1))
        cx = r.centerx
        area = pygame.Rect(r.x + 3, r.y + 3, r.w - 6, r.h - 19)  # 이름 줄 위 (칸 밖으로 안 나감)
        length = 52
        short = fit(f["name"].split(" '")[0], r.w - 6)
        if entry:
            draw_fish_fit(canvas, area, f, length)
            text(canvas, short, (cx, r.bottom - 8), RARITY_COL[f["rarity"]], 11, "center")
            from src.save import dexbook
            draw_stars(canvas, r.x + 5, r.y + 5, dexbook.stars(self.save, f), 5)
            badge = pygame.Rect(r.right - 14, r.y + 3, 11, 11)
            canvas.fill((16, 20, 36), badge)
            text(canvas, entry["best_rank"], badge.center, RANK_COLORS[entry["best_rank"]], 11, "center")
        else:
            seen = self.save.data["dex"].get(f["id"], {}).get("seen")
            draw_fish_fit(canvas, area, f, length, silhouette=(8, 8, 14))
            if seen:
                # 목격 (엘드라시온에서 도망친 물고기): 실루엣 + 이름
                text(canvas, short, (cx, r.bottom - 8), ui.DIM, 11, "center")
                text(canvas, "목격", (r.right - 16, r.y + 8), (200, 180, 255), 11, "center")
            else:
                text(canvas, "???", (cx, r.bottom - 8), ui.DIM, 11, "center")

    def _draw_boss(self, canvas, i: int, f: dict) -> None:
        """전설 = 이 낚시터의 보스: 넓은 칸, 붉은 바탕, 금테 두 겹, 큰 그림, 별명까지 큰 글씨."""
        r = self.card_rect(i)
        entry = self.save.dex_entry(f["id"])
        sel = i == self.sel
        hov = r.collidepoint(self.mouse)
        top, bot = ((70, 30, 34), (26, 14, 30)) if (sel or hov) else ((52, 22, 28), (18, 12, 26))
        for y in range(r.h):
            canvas.fill(lerp_color(top, bot, y / max(1, r.h - 1)), (r.x, r.y + y, r.w, 1))
        pulse = 0.5 + 0.5 * math.sin(self.t * 3.0)
        edge = lerp_color((150, 110, 40), GOLD, pulse if sel else 0.4)
        pygame.draw.rect(canvas, edge, r, 1)
        pygame.draw.rect(canvas, (120, 90, 36), r.inflate(-4, -4), 1)
        for cx_, cy_ in (r.topleft, r.topright, r.bottomleft, r.bottomright):  # 모서리 금장식
            pts = [(cx_, cy_ - 3), (cx_ + 3, cy_), (cx_, cy_ + 3), (cx_ - 3, cy_)]
            pygame.draw.polygon(canvas, GOLD, pts)
        k = (self.t * 0.35) % 1.4  # 금빛이 훑고 지나감
        if k < 1.0:
            px = r.x + int(k * r.w)
            canvas.fill((255, 240, 190), (px, r.y, 6, 1))
            canvas.fill((255, 240, 190), (px - 6, r.bottom - 1, 6, 1))
        area = pygame.Rect(r.x + 8, r.y + 10, r.w - 16, r.h - 28)  # 글자는 그림 위에 얹음 (그림을 크게)
        if entry:
            draw_fish_fit(canvas, area, f, 160)
            text(canvas, "★ 전설 · 이 낚시터의 주인", (r.x + 8, r.y + 9), GOLD, 11, "midleft")
            text(canvas, f["name"], (r.centerx, r.bottom - 11), GOLD, 16, "center")
            from src.save import dexbook
            draw_stars(canvas, r.right - 52, r.y + 9, dexbook.stars(self.save, f), 6)
            badge = pygame.Rect(r.right - 16, r.y + 4, 11, 11)
            canvas.fill((16, 20, 36), badge)
            text(canvas, entry["best_rank"], badge.center, RANK_COLORS[entry["best_rank"]], 11, "center")
        else:
            seen = self.save.data["dex"].get(f["id"], {}).get("seen")
            draw_fish_fit(canvas, area, f, 160, silhouette=(6, 4, 10))
            text(canvas, "★ 전설 · 이 낚시터의 주인", (r.x + 8, r.y + 9), GOLD, 11, "midleft")
            label = f["name"] if seen else "???"
            text(canvas, label, (r.centerx, r.bottom - 11), (170, 150, 120), 16, "center")
            if seen:
                text(canvas, "목격", (r.right - 18, r.y + 9), (200, 180, 255), 11, "center")

    def _draw_detail(self, canvas, f: dict) -> None:
        d = DETAIL
        ui.panel(canvas, d, fill=(16, 20, 36))
        entry = self.save.dex_entry(f["id"])
        x, y = d.x + 6, d.y + 8
        if entry is None:
            seen = self.save.data["dex"].get(f["id"], {}).get("seen")
            text(canvas, f["name"] if seen else "???", (d.centerx, y + 4), ui.DIM, 16 if not seen else 11, "center")
            hinted = f["rarity"] in ("uncommon", "rare", "legend")
            text(canvas, f"희귀도: {RARITY_KO[f['rarity']]}" if hinted else "아직 잡지 못했다",
                 (d.centerx, y + 26), ui.DIM, 11, "center")
            if hinted:
                revealed, rows = self.save.hint_status(f)
                lines = ["특별한 조건에서만 나타난다고 한다."] if f["rarity"] == "legend" else []
                if f["rarity"] == "legend":
                    bait = next((b for b in baits().values() if b.get("legend_for") == f["id"]), None)
                    if bait:
                        lines.append(f"필요한 미끼: {bait['name']}")
                if revealed:
                    # 아래 등급을 충분히 잡으면 등장 조건 공개
                    cond = f"조건: {_join(f['times'], TIME_KO, 4)} · {_join(f['weathers'], WEATHER_KO, 3)}"
                    if f["rarity"] == "legend":
                        cond += " · 25m 이상 던지기"
                    lines.append(cond)
                    if f["rarity"] == "legend":
                        lines.append("지도에서 날씨 예보를 확인하세요.")
                else:
                    # 바로 아래 등급은 1종 이상, 그보다 아래는 모두 (save.hint_status)
                    prev = {"uncommon": None, "rare": "uncommon", "legend": "rare"}[f["rarity"]]
                    lines.append("이 낚시터에서 이만큼 잡으면 단서가 보인다:")
                    for t, h, n in rows:
                        done = h >= n
                        lines.append((f"{'v' if done else '·'} {RARITY_KO[t]} {'1종 이상' if t == prev else '모두'}"
                                      f" {h}/{n}", ui.GOOD if done else ui.DIM))
                yy = y + 46
                for ln in lines:
                    ln, col = ln if isinstance(ln, tuple) else (ln, ui.TEXT)
                    for w in wrap_text(ln, d.w - 12):
                        text(canvas, w, (x, yy), col, 11, "midleft")
                        yy += 13
            return
        text(canvas, f["name"], (d.centerx, y + 4), RARITY_COL[f["rarity"]], 11, "center")
        yy = y + 18
        rows = [
            (f"{RARITY_KO[f['rarity']]} · 난이도 {'★' * min(5, (f['difficulty'] + 1) // 2)}", ui.TEXT),
            (f"시간 {_join(f['times'], TIME_KO, 4)} / {_join(f['weathers'], WEATHER_KO, 3)}", ui.TEXT),
            (f"크기 {f['size_cm'][0]}~{f['size_cm'][1]}cm", ui.TEXT),
            (f"최대 {entry['max_size']:.1f}cm · 최고 {entry['best_rank']} · {entry['count']}회", ui.ACCENT),
            (self._mastery_line(f), (170, 255, 200)),
        ] + self._season_rows(f)
        for s, col in rows:
            text(canvas, s, (x, yy), col, 11, "midleft")
            yy += 13
        yy += 2
        for ln in wrap_text(f["desc"], d.w - 12)[:3]:
            text(canvas, ln, (x, yy), ui.DIM, 11, "midleft")
            yy += 12
        yy += 4
        for need, key in ((3, "hint3"), (10, "hint10")):
            if entry["count"] >= need:
                lines = wrap_text("· " + f[key], d.w - 12)[:3]
                for ln in lines:
                    text(canvas, ln, (x, yy), (150, 230, 255), 11, "midleft")
                    yy += 12
            else:
                for ln in wrap_text(f"· 힌트 잠김: {need}회 포획 시 해금 ({entry['count']}/{need})", d.w - 12):
                    text(canvas, ln, (x, yy), ui.DIM, 11, "midleft")
                    yy += 12
        lc = load_json("lure.json")
        from src.save import dexbook
        if entry["count"] >= lc["dex_hint_catches"] or dexbook.mastery(self.save, f) >= 3:  # 숙련 3 보상 (전설은 3회)
            prof = lc["profiles"][profile_of(f)]
            for ln in wrap_text(f"· 선호 리듬: {prof['name']} — {prof['hint']}", d.w - 12)[:2]:
                text(canvas, ln, (x, yy), (170, 255, 200), 11, "midleft")
                yy += 12
        else:
            text(canvas, f"· 선호 리듬: {lc['dex_hint_catches']}회 포획 시 ({entry['count']}/{lc['dex_hint_catches']})",
                 (x, yy), ui.DIM, 11, "midleft")
            yy += 12
        pats = fish_patterns(f)
        if pats:
            # 신규 패턴 힌트: 만나 본 패턴만 이름과 대응, 아직이면 ???
            seen = self.save.data.get("patterns_seen", [])
            names = load_json("patterns.json")["names"]
            parts = [f"{names[p]}({TIP_SHORT[p]})" if p in seen else "???" for p in pats]
            for ln in wrap_text("· 패턴: " + ", ".join(parts), d.w - 12)[:2]:
                text(canvas, ln, (x, yy), (255, 200, 150), 11, "midleft")
                yy += 12
        if entry["best_rank"] == "S":
            pulse = 0.5 + 0.5 * math.sin(self.t * 4)
            pygame.draw.rect(canvas, GOLD if pulse > 0.3 else (180, 140, 40), d, 1)
