"""도감: 낚시터별 카드, 못 잡은 물고기는 실루엣 + ???, S랭크 금테, 3회·10회 힌트."""
import math

import pygame

from src.core.config import load_json
from src.core.weather import WEATHER_KO
from src.render.fish_draw import RANK_COLORS, draw_fish_side, fish_colors, fish_shape
from src.save.save_game import baits
from src.fishing.patterns import TIP_SHORT, fish_patterns
from src.fishing import mutation
from src.fishing.lure import profile_of
from src.scene.base import Scene
from src.ui import widgets as ui
from src.ui.hud import draw_cursor, text, wrap_text

SPOT_TABS = [("reservoir", "저수지"), ("valley", "계곡"), ("breakwater", "방파제"), ("offshore", "먼바다"),
             ("deep", "심해"), ("secret", "비밀")]
ELDRA_TABS = [("marsh", "습지"), ("crystal_cave", "동굴"), ("sky_falls", "부유섬"), ("volcano", "화산"),
              ("ice_sea", "빙해"), ("world_tree", "세계수")]
CONT_TABS = {"sharmion": SPOT_TABS, "eldrasion": ELDRA_TABS}
TIME_KO = {"morning": "아침", "day": "낮", "evening": "저녁", "night": "밤"}
RARITY_KO = {"common": "일반", "uncommon": "고급", "rare": "희귀", "legend": "전설"}
RARITY_COL = {"common": (230, 230, 230), "uncommon": (130, 230, 150), "rare": (130, 190, 255),
              "legend": (255, 214, 90)}
GOLD = (255, 214, 90)
CARD_W, CARD_H = 92, 60
GRID_X, GRID_Y = 14, 50
DETAIL = pygame.Rect(306, 50, 160, 196)


def _join(values, table, all_count) -> str:
    return "전체" if len(values) >= all_count else "·".join(table[v] for v in values)


MUT_COL = (255, 190, 120)


class DexScene(Scene):
    UI_FRAME = True

    def __init__(self, game, fishing):
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

    def _toggle_mut(self) -> None:
        self.mut_mode = not self.mut_mode
        self.pat_mode = False

    def _toggle_pat(self) -> None:
        self.pat_mode = not self.pat_mode
        self.mut_mode = False

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
        return pygame.Rect(GRID_X + (i % 3) * (CARD_W + 4), GRID_Y + (i // 3) * (CARD_H + 4), CARD_W, CARD_H)

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
            text(canvas, f"{got}/{total}종 ({got * 100 // total}%)   금테 {golds}", (466, 16), ui.ACCENT, 11, "midright")
        if mutation.unlocked(self.save):
            self.mut_btn.label = "기본 도감" if self.mut_mode else "변이 도감"
            self.mut_btn.draw(canvas, self.mouse)
        self.pat_btn.label = "기본 도감" if self.pat_mode else "패턴 사전"
        self.pat_btn.draw(canvas, self.mouse)
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

    def _draw_card(self, canvas, i: int, f: dict) -> None:
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
        cx, cy = r.centerx, r.y + 24
        length = 62 if f["rarity"] != "legend" else 70
        if entry:
            draw_fish_side(canvas, cx, cy, length, 0.0, fish_colors(f), -1, shape=fish_shape(f))
            text(canvas, f["name"][:7], (cx, r.bottom - 9), RARITY_COL[f["rarity"]], 11, "center")
            badge = pygame.Rect(r.right - 14, r.y + 3, 11, 11)
            canvas.fill((16, 20, 36), badge)
            text(canvas, entry["best_rank"], badge.center, RANK_COLORS[entry["best_rank"]], 11, "center")
        else:
            seen = self.save.data["dex"].get(f["id"], {}).get("seen")
            draw_fish_side(canvas, cx, cy, length, 0.0, fish_colors(f), -1, silhouette=(8, 8, 14),
                           shape=fish_shape(f))
            if seen:
                # 목격 (엘드라시온에서 도망친 물고기): 실루엣 + 이름
                text(canvas, f["name"][:7], (cx, r.bottom - 9), ui.DIM, 11, "center")
                text(canvas, "목격", (r.right - 16, r.y + 8), (200, 180, 255), 11, "center")
            else:
                text(canvas, "???", (cx, r.bottom - 9), ui.DIM, 11, "center")

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
        ]
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
        if entry["count"] >= lc["dex_hint_catches"]:
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
