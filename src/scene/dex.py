"""도감: 낚시터별 카드, 못 잡은 물고기는 실루엣 + ???, S랭크 금테, 3회·10회 힌트."""
import math

import pygame

from src.core.config import load_json
from src.core.weather import WEATHER_KO
from src.render.fish_draw import RANK_COLORS, draw_fish_side, fish_colors
from src.save.save_game import baits
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


class DexScene(Scene):
    def __init__(self, game, fishing):
        super().__init__(game)
        self.fishing = fishing
        self.save = game.save
        self.mouse = (0, 0)
        self.age = 0.0  # 열림 애니메이션
        self.fish = load_json("fish.json")["fish"]
        self.cont = "eldrasion" if fishing.spot_id in dict(ELDRA_TABS) else "sharmion"
        self._make_tabs()
        self.cont_btn = ui.Button((310, 30, 92, 16), "", self._switch)
        self.sel = 0
        self.t = 0.0
        self.close_btn = ui.Button((406, 250, 60, 15), "닫기 (Tab)", self._close)

    def _make_tabs(self) -> None:
        tabs = CONT_TABS[self.cont]
        self.tabs = ui.Tabs(14, 30, [t[1] for t in tabs], width=46)
        self.tabs.index = next((i for i, t in enumerate(tabs) if t[0] == self.fishing.spot_id), 0)

    def _switch(self) -> None:
        self.cont = "eldrasion" if self.cont == "sharmion" else "sharmion"
        self._make_tabs()
        self.sel = 0

    def spot_fish(self) -> list[dict]:
        return [f for f in self.fish if f["spot"] == CONT_TABS[self.cont][self.tabs.index][0]]

    def card_rect(self, i: int) -> pygame.Rect:
        return pygame.Rect(GRID_X + (i % 3) * (CARD_W + 4), GRID_Y + (i // 3) * (CARD_H + 4), CARD_W, CARD_H)

    def _close(self) -> None:
        self.game.scenes.pop()

    def handle_event(self, event) -> None:
        if event.type == pygame.KEYDOWN and event.key in (pygame.K_ESCAPE, pygame.K_TAB):
            self._close()
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            m = self.game.to_canvas(event.pos)
            if self.tabs.click(m):
                self.sel = 0
                self.game.sfx.play("click")
                return
            if self.close_btn.click(m):
                return
            if "eldrasion" in self.save.data["unlocked_continents"] and self.cont_btn.click(m):
                self.game.sfx.play("click")
                return
            for i in range(len(self.spot_fish())):
                if self.card_rect(i).collidepoint(m):
                    self.sel = i
                    self.game.sfx.play("click")

    def update(self, dt: float) -> None:
        self.age += dt
        self.t += dt
        self.mouse = self.game.to_canvas(pygame.mouse.get_pos())

    def draw(self, canvas) -> None:
        self.fishing.draw(canvas)
        ui.dim(canvas, int(180 * min(1.0, self.age / 0.15)))
        ui.panel(canvas, (6, 6, 468, 260))
        total = len(self.fish)
        got = self.save.dex_count()
        golds = sum(1 for e in self.save.data["dex"].values() if e.get("best_rank") == "S")
        text(canvas, "도감", (14, 16), ui.ACCENT, 16, "midleft")
        text(canvas, f"{got}/{total}종 ({got * 100 // total}%)   금테 {golds}", (466, 16), ui.ACCENT, 11, "midright")
        self.tabs.draw(canvas, self.mouse)
        if "eldrasion" in self.save.data["unlocked_continents"]:
            self.cont_btn.label = "엘드라시온 >" if self.cont == "sharmion" else "< 샤르미온"
            self.cont_btn.draw(canvas, self.mouse)
        fishes = self.spot_fish()
        self.sel = min(self.sel, len(fishes) - 1)
        for i, f in enumerate(fishes):
            self._draw_card(canvas, i, f)
        self._draw_detail(canvas, fishes[self.sel])
        self.close_btn.draw(canvas, self.mouse)
        draw_cursor(canvas, self.mouse)

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
            draw_fish_side(canvas, cx, cy, length, 0.0, fish_colors(f), -1, shape=f.get("shape"))
            text(canvas, f["name"][:7], (cx, r.bottom - 9), RARITY_COL[f["rarity"]], 11, "center")
            badge = pygame.Rect(r.right - 14, r.y + 3, 11, 11)
            canvas.fill((16, 20, 36), badge)
            text(canvas, entry["best_rank"], badge.center, RANK_COLORS[entry["best_rank"]], 11, "center")
        else:
            seen = self.save.data["dex"].get(f["id"], {}).get("seen")
            draw_fish_side(canvas, cx, cy, length, 0.0, fish_colors(f), -1, silhouette=(8, 8, 14),
                           shape=f.get("shape"))
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
            hinted = f["rarity"] in ("rare", "legend")
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
                    prev = {"rare": "uncommon", "legend": "rare"}[f["rarity"]]
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
        if entry["best_rank"] == "S":
            pulse = 0.5 + 0.5 * math.sin(self.t * 4)
            pygame.draw.rect(canvas, GOLD if pulse > 0.3 else (180, 140, 40), d, 1)
