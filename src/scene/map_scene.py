"""낚시터 지도: 이동(1시간 — 도착 시각 미리보기), 해금 조건·해금, 오늘 날씨 한 줄 + [달력] (CORE_UPDATE CU1: 예보표 · 쉬기 버튼은 달력으로, DESIGN 52-0)."""
import math

import pygame

from src.core.config import load_json
from src.core.game_clock import PERIODS
from src.core.weather import WEATHER_KO
from src.save.save_game import all_fish
from src.scene.base import Scene
from src.ui import weather_icons
from src.ui import widgets as ui
from src.ui.hud import draw_cursor, text, wrap_text

SHARMION_SPOTS = ("reservoir", "valley", "breakwater", "offshore", "deep")
LAND = (88, 128, 82)
LAND_DARK = (66, 100, 64)
SEA = (44, 84, 140)
SEA_LIGHT = (70, 116, 170)
PATH = (240, 226, 180)
FC = pygame.Rect(298, 28, 168, 50)   # 오늘 날씨 한 줄 + [달력] 상자 (그 아래 낚시터 정보)


def unlock_status(save, spot: dict) -> tuple[bool, list[tuple[str, bool]]]:
    """(조건을 모두 채웠는지, [(조건 설명, 충족 여부)]) — 지도 체크리스트."""
    cond = spot.get("unlock", {})
    rows = []
    cont = spot.get("continent", "sharmion")
    if cont not in save.data["unlocked_continents"]:
        rows.append(("대륙이 아직 열리지 않았다", False))
    if "dex" in cond:
        rows.append((f"도감 {cond['dex']}종 ({save.dex_count()}/{cond['dex']})", save.dex_count() >= cond["dex"]))
    if "dex_pct" in cond:
        got, total = save.continent_dex(spot.get("continent", "sharmion"))
        need = math.ceil(total * cond["dex_pct"] / 100)
        rows.append((f"도감 {cond['dex_pct']}% ({min(got, need)}/{need}종)", got >= need))
    if "rod_tier" in cond:
        tier = save.gear_tier("rod")
        rows.append((f"낚싯대 T{cond['rod_tier']} 이상 (지금 T{tier})", tier >= cond["rod_tier"]))
    if "gear_count_tier" in cond:
        n, tier = cond["gear_count_tier"]
        got = sum(1 for k in ("rod", "reel", "line", "net", "bait") if save.gear_tier(k) >= tier)
        rows.append((f"장비 {n}종 T{tier} 이상 ({min(got, n)}/{n})", got >= n))
    if "line_tier" in cond:
        tier = save.gear_tier("line")
        rows.append((f"낚싯줄 T{cond['line_tier']} 이상 (지금 T{tier})", tier >= cond["line_tier"]))
    if "all_gear_tier" in cond:
        need = cond["all_gear_tier"]
        low = min(save.gear_tier(k) for k in ("rod", "reel", "line", "net", "bait"))
        rows.append((f"장비 전부 T{need} 이상 (최저 T{low})", low >= need))
    if "spot_s" in cond:
        name = next(s["name"] for s in load_json("spots.json")["spots"] if s["id"] == cond["spot_s"])
        rows.append((f"{name} 물고기 S랭크 1회", save.spot_has_s(cond["spot_s"])))
    if "rare_total" in cond:
        n = save.rare_total()
        rows.append((f"희귀 이상 {min(n, cond['rare_total'])}/{cond['rare_total']}마리",
                     n >= cond["rare_total"]))
    if "legend" in cond:
        fish = next(f for f in all_fish() if f["id"] == cond["legend"])
        rows.append((f"전설 {fish['name']}", save.caught(cond["legend"])))
    if "legends" in cond:
        legends = [f["id"] for f in all_fish() if f["rarity"] == "legend" and f["spot"] in SHARMION_SPOTS]
        got = sum(1 for fid in legends if save.caught(fid))
        rows.append((f"전설 {got}/{cond['legends']}마리 포획", got >= cond["legends"]))
    if "legends_list" in cond:
        ids = cond["legends_list"]
        got = sum(1 for fid in ids if save.caught(fid))
        rows.append((f"전설 {got}/{len(ids)}마리 포획", got >= len(ids)))
    if "legend_s" in cond:
        legends = [f["id"] for f in all_fish() if f["rarity"] == "legend"]
        n = sum(1 for fid in legends if save.caught(fid) and save.data["dex"][fid].get("best_rank") == "S")
        rows.append((f"전설 S랭크 {min(n, cond['legend_s'])}/{cond['legend_s']}회", n >= cond["legend_s"]))
    if "s_eldra" in cond:
        n = save.data["stats"].get("s_ranks_eldra", 0)
        rows.append((f"엘드라시온 S {min(n, cond['s_eldra'])}/{cond['s_eldra']}회", n >= cond["s_eldra"]))
    if "s_total" in cond:
        n = save.data["stats"]["s_ranks"]
        rows.append((f"S랭크 {min(n, cond['s_total'])}/{cond['s_total']}회", n >= cond["s_total"]))
    if "perfects" in cond:
        n = save.data["stats"]["perfects"]
        rows.append((f"퍼펙트 {min(n, cond['perfects'])}/{cond['perfects']}회",
                     n >= cond["perfects"]))
    if cond.get("cost"):
        rows.append((f"비용 {ui.money_text(cond['cost'])}", save.money >= cond["cost"]))
    if preview_ok(save, spot):   # 다음 티어 미리 맛보기 (CU8-⑤): 장비 조건은 '권장' — 막지 않음
        rows = [(f"{label} — 권장", True) if _is_gear_row(label) and not ok else (label, ok) for label, ok in rows]
    return all(ok for _, ok in rows), rows


GEAR_ROWS = ("낚싯대 T", "장비 ", "낚싯줄 T")


def _is_gear_row(label: str) -> bool:
    return label.startswith(GEAR_ROWS)


def preview_ok(save, spot: dict) -> bool:
    """다음 티어 낚시터 1곳 (CU8-⑤): 열린 낚시터 중 가장 높은 장비 티어 + 1 까지는 장비가 모자라도 들어갈 수 있음."""
    top = max((s.get("gear_tier", 1) for s in load_json("spots.json")["spots"] if s["id"] in save.data["unlocked_spots"]),
              default=1)
    return spot.get("gear_tier", 1) <= top + 1


def gear_ok(save, spot: dict) -> bool:
    """그 낚시터의 장비 조건을 다 채웠나 — 전설은 이게 참일 때만 (CU8-⑤). 장비 조건이 없으면 권장 티어 낚싯대."""
    cond = spot.get("unlock", {})
    tiers = [save.gear_tier(k) for k in ("rod", "reel", "line", "net", "bait")]
    if "rod_tier" in cond and save.gear_tier("rod") < cond["rod_tier"]:
        return False
    if "all_gear_tier" in cond and min(tiers) < cond["all_gear_tier"]:
        return False
    if "gear_count_tier" in cond:
        n, t = cond["gear_count_tier"]
        if sum(1 for x in tiers if x >= t) < n:
            return False
    return save.gear_tier("rod") >= spot.get("gear_tier", 1)


def gear_warning(save, spot: dict) -> str | None:
    """지도 · 낚시터 도착: 장비가 권장보다 약하면 "장비가 약해요 (T4 권장)"."""
    if save.gear_tier("rod") >= spot.get("gear_tier", 1):
        return None
    return f"장비가 약해요 (T{spot.get('gear_tier', 1)} 권장)"


def can_unlock_soon(save, spot: dict) -> bool:
    """비용 빼고 조건이 다 찼는지 (새 낚시터 알림용)."""
    ok, rows = unlock_status(save, spot)
    return all(ok for label, ok in rows if not label.startswith("비용"))


class MapScene(Scene):
    UI_FRAME = True

    def __init__(self, game, fishing, from_village=None):
        super().__init__(game)
        self.fishing = fishing
        self.village = from_village   # 마을 부두에서 열었으면 그 마을 (이동하면 마을도 닫힘)
        self.save = game.save
        self.mouse = (0, 0)
        self.age = 0.0  # 열림 애니메이션
        self.all_spots = load_json("spots.json")["spots"]
        self.conts = load_json("continents.json")["continents"]
        here = next(s for s in self.all_spots if s["id"] == fishing.spot_id)
        self.cont = here.get("continent", "sharmion")
        self.sel = next(i for i, s in enumerate(self.spots) if s["id"] == fishing.spot_id)
        self.town_sel = False   # 지도 위 마을 칸을 골랐는지 (처음엔 지금 낚시터)
        self.cont_btns = [ui.Button((112, 9, 16, 15), "<", lambda: self._switch(-1)),
                          ui.Button((262, 9, 16, 15), ">", lambda: self._switch(1))]
        self.t = 0.0
        self.msg, self.msg_t, self.msg_col = "", 0.0, ui.TEXT
        self.close_btn = ui.Button((404, 250, 64, 15), "닫기 (M)", self._close)
        self.go_btn = ui.Button((300, 214, 164, 17), "", self._go)
        self.cal_btn = ui.Button((FC.x + 4, FC.bottom - 20, FC.w - 8, 16), "달력 (K) · 14일 예보 · 골라 쉬기", self._calendar)
        self.train_btn = ui.Button((330, 250, 70, 15), "훈련 수조", self._train)

    @property
    def spots(self) -> list:
        return [s for s in self.all_spots if s.get("continent", "sharmion") == self.cont]

    @property
    def cont_info(self) -> dict:
        return next(c for c in self.conts if c["id"] == self.cont)

    def _switch(self, d: int) -> None:
        opened = [c["id"] for c in self.conts if c["id"] in self.save.data["unlocked_continents"]]
        if len(opened) < 2:
            return
        self.cont = opened[(opened.index(self.cont) + d) % len(opened)]
        here = [i for i, s in enumerate(self.spots) if s["id"] == self.fishing.spot_id]
        self.sel = here[0] if here else 0
        self.town_sel = False
        self.game.sfx.play("ui_click")

    @property
    def spot(self) -> dict:
        return self.spots[self.sel]

    def unlocked(self, spot) -> bool:
        return spot["id"] in self.save.data["unlocked_spots"]

    def _say(self, s: str, col=ui.TEXT) -> None:
        self.msg, self.msg_t, self.msg_col = s, 2.2, col
        if col == ui.BAD:
            self.game.sfx.play("ui_error")

    def _close(self) -> None:
        self.game.scenes.pop()

    def _calendar(self) -> None:
        from src.scene.calendar_scene import CalendarScene
        self.game.sfx.play("ui_click")
        self.game.scenes.push(CalendarScene(self.game, self.fishing))

    def _tide_confirm(self, then) -> bool:
        """물때 멈춤 소라 효과 중 이동하면 끝 (CU1-4): 확인 창을 띄웠으면 True."""
        from src.save import item_use
        if item_use.tide_left(self.save) <= 0:
            return False

        def yes():
            item_use.tide_end(self.game, self.fishing)
            then()
        from src.scene.confirm import ConfirmScene
        self.game.scenes.push(ConfirmScene(self.game, "물때 멈춤이 끝나요. 갈까요?", yes, "가기", "그만두기"))
        return True

    def _town(self) -> None:
        """마을로: 낚시터 → 마을 (보고 있는 대륙의 마을)."""
        if not (self.village is not None and self.village.cont == self.cont) and self._tide_confirm(self._town):
            return
        self.game.sfx.play("ui_click")
        if self.village is not None and self.village.cont == self.cont:
            self._close()   # 지금 그 마을 부두에서 열었으면 지도만 닫기
            return
        from src.scene.travel import start_return
        self.game.scenes.pop()
        if self.village is not None:
            self.village.leave()   # 다른 대륙 마을로: 지금 마을을 닫고 항해
        start_return(self.game, self.fishing, self.cont)   # 돌아오는 길 컷신 → 마을

    def _go(self) -> None:
        if self.town_sel:
            self._town()
            return
        sp = self.spot
        if sp["id"] == self.fishing.spot_id and self.village is None:
            return
        if self.unlocked(sp):
            if self._tide_confirm(self._go):
                return
            prev_cont = self.fishing.spot.get("continent", "sharmion") if self.village is None else self.village.cont
            if sp["id"] != self.fishing.spot_id:
                self.fishing.travel(sp["id"])
            self.game.scenes.pop()
            if self.village is not None:
                self.village.leave()   # 부두에서 출발: 마을도 닫고 낚시터로
            from src.scene.travel import start_trip
            start_trip(self.game, self.fishing, sp["id"], prev_cont)   # 이동 컷신 (35-3)
            return
        ok, _ = unlock_status(self.save, sp)
        if ok:
            self.save.data["money"] -= sp["unlock"].get("cost", 0)
            self.save.data["unlocked_spots"].append(sp["id"])
            self.game.sfx.play("ui_buy")
            self.game.sfx.play("sfx_catch", 0.7)
            self._say(f"{sp['name']} 해금!", ui.GOOD)
            reward = {"secret": ("dragon_pearl", "여의주"), "world_tree": ("world_fruit", "세계수 열매")}.get(sp["id"])
            if reward and not self.save.owns("bait", reward[0]):
                # 최종 전설을 부르는 미끼
                self.save.data["owned"]["bait"].append(reward[0])
                self.game.sfx.play("sfx_chord_legend", 0.7)
                self._say(f"{sp['name']} 해금! {reward[1]}을(를) 얻었다", (255, 214, 90))
            self.game.save_now()

    def _train(self) -> None:
        """훈련 수조 (31장 C5): 해금 패턴 무한 반복, 보상·패널티 없음."""
        if self.fishing.fight is not None:
            return
        self.game.sfx.play("ui_click")
        self.game.scenes.pop()
        if self.village is not None:
            self.village.leave()
        self.fishing.start_training()

    def handle_action(self, a) -> None:
        if a.name == "back" or a.is_("menu", "map"):
            self._close()
        elif a.is_("menu", "calendar"):
            self._calendar()
        elif a.name == "primary":
            m = a.pos
            for b in (self.close_btn, self.go_btn, self.train_btn, self.cal_btn) + tuple(self.cont_btns if self._multi() else ()):
                if b.click(m):
                    return
            tx, ty = self._town_node()
            if math.hypot(m[0] - tx, m[1] - ty) < 13:
                self.town_sel = True
                self.game.sfx.play("ui_click")
                return
            for i, sp in enumerate(self.spots):
                x, y = self._node(sp)
                if math.hypot(m[0] - x, m[1] - y) < 13:
                    self.sel = i
                    self.town_sel = False
                    self.game.sfx.play("ui_click")

    def _multi(self) -> bool:
        return len(self.save.data["unlocked_continents"]) > 1

    def update(self, dt: float) -> None:
        self.age += dt
        self.t += dt
        self.msg_t = max(0.0, self.msg_t - dt)
        self.mouse = self.ui_pointer()
        self.game.adaptive.set_context(self.cont, None)  # 지도: 보고 있는 대륙 테마 (32장 S6)
        self.game.adaptive.set("menu")

    def _village(self) -> dict:
        return load_json("villages.json")[self.cont]

    def _town_node(self) -> tuple[int, int]:
        x, y = self._village().get("map_node", (100, 228))
        return int(x), int(y)

    def _node(self, sp) -> tuple[int, int]:
        x, y = sp["map_pos"]
        return int(12 + x * 0.6), int(30 + y * 0.92)

    # ───────────────────────── 그리기 ─────────────────────────
    def draw(self, canvas) -> None:
        ui.backdrop(canvas, self.fishing, int(170 * min(1.0, self.age / 0.15)), "map_scene")
        canvas = self.ui_canvas(canvas)
        ui.panel(canvas, (6, 6, 468, 260))
        text(canvas, "지도", (14, 16), ui.ACCENT, 16, "midleft")
        text(canvas, self.cont_info["name"], (195, 16), (220, 210, 255), 11, "center")
        if self._multi():
            for b in self.cont_btns:
                b.draw(canvas, self.mouse)
        got, total = self.save.continent_dex(self.cont)
        text(canvas, f"{ui.money_text(ui.money_anim(self.save.money))} · 도감 {got}/{total}", (466, 16), ui.ACCENT, 11, "midright")
        self._draw_map(canvas)
        self._draw_today(canvas)
        self._draw_info(canvas)
        if self.msg_t > 0:
            text(canvas, self.msg, (14, 256), self.msg_col, 11, "midleft")
        self.close_btn.draw(canvas, self.mouse)
        self.train_btn.enabled = self.fishing.fight is None
        self.train_btn.draw(canvas, self.mouse)
        draw_cursor(canvas, self.mouse)

    def _draw_map(self, canvas) -> None:
        area = pygame.Rect(12, 28, 280, 222)
        ci = self.cont_info
        sea, sea_light, land_c, land_dark = (tuple(ci[k]) for k in ("sea", "sea_light", "land", "land_dark"))
        canvas.fill(sea, area)
        for i in range(0, area.h, 6):
            off = int(self.t * 6 + i * 3) % 24
            canvas.fill(sea_light, (area.x + off + (i * 37) % 200, area.y + i, 10, 1))
        if self.cont == "sharmion":
            land = [(12, 28), (200, 28), (190, 70), (165, 110), (150, 150), (120, 180), (130, 215), (95, 250), (12, 250)]
            pygame.draw.polygon(canvas, land_c, land)
            pygame.draw.lines(canvas, land_dark, False, land[1:-1], 2)
            # 산 기호
            for mx, my in ((60, 70), (90, 60), (115, 82), (45, 110)):
                pygame.draw.polygon(canvas, land_dark, [(mx - 9, my + 7), (mx, my - 7), (mx + 9, my + 7)])
        else:
            self._draw_eldra_land(canvas, land_c, land_dark)
        # 경로
        nodes = [self._node(sp) for sp in self.spots]
        for a, b in zip(nodes[:-2], nodes[1:-1]):
            steps = int(math.hypot(b[0] - a[0], b[1] - a[1]) / 6)
            for k in range(steps):
                if k % 2 == 0:
                    x = a[0] + (b[0] - a[0]) * k / steps
                    y = a[1] + (b[1] - a[1]) * k / steps
                    canvas.fill(PATH, (int(x), int(y), 2, 2))
        self._draw_town_node(canvas)
        for i, sp in enumerate(self.spots):
            x, y = nodes[i]
            secret = bool(sp.get("secret"))
            unlocked = self.unlocked(sp)
            if secret and not unlocked:
                if not can_unlock_soon(self.save, sp):
                    # 비밀 장소는 조건을 채우기 전까지 희미한 물음표
                    text(canvas, "?", (x, y), (120, 130, 160), 16, "center")
                    if i == self.sel and not self.town_sel:
                        pygame.draw.circle(canvas, ui.ACCENT, (x, y), 11, 1)
                    continue
            current = sp["id"] == self.fishing.spot_id
            col = ui.ACCENT if current else ((235, 240, 250) if unlocked else (110, 116, 136))
            r = 7 if current else 6
            pygame.draw.circle(canvas, (12, 14, 26), (x + 1, y + 1), r + 1)
            pygame.draw.circle(canvas, col, (x, y), r)
            if not unlocked:
                canvas.fill((40, 44, 60), (x - 2, y - 1, 5, 4))
                pygame.draw.arc(canvas, (40, 44, 60), (x - 2, y - 4, 5, 6), 0, math.pi, 1)
                if can_unlock_soon(self.save, sp) and int(self.t * 3) % 2 == 0:
                    pygame.draw.circle(canvas, ui.GOOD, (x, y), r + 3, 1)
            if i == self.sel and not self.town_sel:
                rr = r + 4 + int(2 * math.sin(self.t * 5))
                pygame.draw.circle(canvas, ui.ACCENT, (x, y), rr, 1)
            if current and self.village is None:   # 마을에 있으면 '현재'는 마을 칸에만
                text(canvas, "현재", (x, y - 13), ui.ACCENT, 11, "center")
            text(canvas, sp["short"], (x, y + 13), col, 11, "center")
            if unlocked and self.save.charm_on("phantom_eye"):
                self._draw_phantom_eye(canvas, sp["id"], x + 10, y - 6)

    def _draw_town_node(self, canvas) -> None:
        """마을: 지붕 달린 집 기호 + 이름 (금색). 낚시터와 점선 길로 이어짐."""
        x, y = self._town_node()
        first = next((sp for sp in self.spots if sp["id"] == self.cont_info.get("first_spot")), None)
        if first:
            a, b = (x, y), self._node(first)
            steps = int(math.hypot(b[0] - a[0], b[1] - a[1]) / 6)
            for k in range(1, steps):
                if k % 2 == 0:
                    canvas.fill(PATH, (int(a[0] + (b[0] - a[0]) * k / steps), int(a[1] + (b[1] - a[1]) * k / steps), 2, 2))
        here = self.village is not None and self.village.cont == self.cont
        wall = (250, 236, 200) if self.cont == "sharmion" else (210, 214, 240)
        roof = (190, 80, 60) if self.cont == "sharmion" else (90, 150, 190)
        pygame.draw.rect(canvas, (12, 14, 26), (x - 6, y - 2, 14, 10))
        canvas.fill(wall, (x - 7, y - 3, 14, 10))
        pygame.draw.polygon(canvas, roof, [(x - 9, y - 2), (x, y - 10), (x + 9, y - 2)])
        canvas.fill((70, 50, 40), (x - 2, y + 2, 4, 5))
        if self.town_sel:
            rr = 13 + int(2 * math.sin(self.t * 5))
            pygame.draw.circle(canvas, ui.ACCENT, (x, y - 2), rr, 1)
        if here:
            text(canvas, "현재", (x, y - 19), ui.ACCENT, 11, "center")
        text(canvas, self._village()["name"], (x, y + 15), (255, 226, 150), 11, "center")

    def _draw_phantom_eye(self, canvas, spot_id: str, x: int, y: int) -> None:
        """환상의 눈 (부적, 33장 P5): 그 낚시터 환상어를 잡았으면 채운 보라 점, 아니면 빈 점 +
        천장 진행도 보라 눈금 5칸 (확률 숫자는 보여 주지 않는다)."""
        from src.fishing import phantom
        ph = phantom.for_spot(spot_id)
        if ph is None:
            return
        col = (200, 140, 255)
        if phantom.caught(self.save, ph["id"]):
            pygame.draw.circle(canvas, col, (x, y), 3)
        else:
            pygame.draw.circle(canvas, col, (x, y), 3, 1)
        n = int(round(phantom.pity_frac(self.save, spot_id) * 5))
        for k in range(5):
            r = (x + 5 + k * 3, y - 1, 2, 3)
            canvas.fill(col if k < n else (60, 44, 90), r)

    def _draw_eldra_land(self, canvas, land_c, land_dark) -> None:
        """엘드라시온: 가운데 큰 섬 + 남쪽 얼음 + 하늘섬, 낚시터마다 기호."""
        main = [(30, 70), (90, 40), (170, 50), (230, 90), (250, 150), (210, 200), (140, 215), (70, 195), (25, 140)]
        pygame.draw.polygon(canvas, land_c, main)
        pygame.draw.lines(canvas, land_dark, True, main, 2)
        ice = (220, 232, 245)
        pygame.draw.polygon(canvas, ice, [(170, 228), (230, 214), (285, 226), (285, 250), (160, 250)])
        # 하늘섬 (북동)
        bob = math.sin(self.t * 1.5) * 1.5
        pygame.draw.ellipse(canvas, (200, 220, 245), (172, 40 + bob, 50, 12))
        # 화산 (동)
        pygame.draw.polygon(canvas, (70, 50, 60), [(240, 150), (260, 118), (280, 150)])
        canvas.fill((255, 120, 50), (257, 116, 6, 3))
        # 수정 (서)
        for cx, cy in ((100, 128), (110, 120), (118, 130)):
            pygame.draw.polygon(canvas, (170, 200, 255), [(cx - 3, cy + 6), (cx, cy - 6), (cx + 3, cy + 6)])
        # 세계수 (북)
        pygame.draw.circle(canvas, (90, 160, 110), (132, 46), 12)
        canvas.fill((96, 72, 50), (130, 50, 5, 10))

    # ── 오늘 한 줄 + [달력] (CU1-2 ②: 예보표 · 쉬기 4버튼은 달력으로) ──
    def _fc_spot(self) -> dict:
        """날씨를 보여 줄 낚시터 (마을 칸을 고르면 지금 낚시터)."""
        if self.town_sel:
            return next(s for s in self.all_spots if s["id"] == self.fishing.spot_id)
        return self.spot

    def _draw_today(self, canvas) -> None:
        f = self.fishing
        w = f.weather_sys
        box = FC
        ui.panel(canvas, box, fill=(16, 20, 36))
        sp = self._fc_spot()
        hidden = sp.get("secret") and not self.unlocked(sp) and not can_unlock_soon(self.save, sp)
        text(canvas, f"오늘 · {'???' if hidden else sp['short']}", (box.x + 6, box.y + 8), ui.ACCENT, 11, "midleft")
        text(canvas, f.clock.label(), (box.right - 5, box.y + 8), ui.DIM, 11, "midright")
        if hidden:
            text(canvas, "알 수 없는 곳의 하늘", (box.x + 6, box.y + 21), ui.DIM, 11, "midleft")
        else:
            now = w.abs_time(f.clock.day, f.clock.hour)
            h = f.clock.hour
            cur = next((n for st, _, n in reversed(PERIODS) if h >= st), PERIODS[-1][2])
            nxt_start, nxt_name = next(((st, n) for st, _, n in PERIODS if st > h + 0.01), (PERIODS[0][0] + 24, PERIODS[0][2]))
            w0 = w.at_time(now, sp["id"], sp["weather"])
            w1 = w.at_time(now + (nxt_start - h), sp["id"], sp["weather"])
            x = box.x + 6
            r = text(canvas, f"{cur} {WEATHER_KO[w0]}", (x, box.y + 21), ui.TEXT, 11, "midleft")
            weather_icons.draw(canvas, w0, r.right + 3, box.y + 17)
            r = text(canvas, "→", (r.right + 15, box.y + 21), ui.DIM, 11, "midleft")
            r = text(canvas, f"{nxt_name} {WEATHER_KO[w1]}", (r.right + 4, box.y + 21), ui.TEXT, 11, "midleft")
            weather_icons.draw(canvas, w1, r.right + 3, box.y + 17)
        self.cal_btn.draw(canvas, self.mouse)

    def _travel_preview(self, canvas, x: int, y: int) -> None:
        """이동 미리보기 (CU1-3): '이동하면 1시간이 지나요' + 도착 시각, 시간대가 끝나면 노란색."""
        f = self.fishing
        h0 = f.clock.hour
        h1 = (h0 + 1.0) % 24
        p0 = next((n for st, _, n in reversed(PERIODS) if h0 >= st), PERIODS[-1][2])
        p1 = next((n for st, _, n in reversed(PERIODS) if h1 >= st), PERIODS[-1][2])

        def hm(h):
            return f"{int(h):02d}:{int((h - int(h)) * 60):02d}"
        text(canvas, "이동하면 1시간이 지나요", (x, y), ui.DIM, 11, "midleft")
        line = f"{p0} {hm(h0)} → {hm(h1)}"
        if p1 != p0:
            text(canvas, f"{line} · {p0}이 끝나요", (x, y + 12), (255, 214, 90), 11, "midleft")   # 아침 · 낮 · 저녁 · 밤 모두 받침
        else:
            text(canvas, line, (x, y + 12), ui.TEXT, 11, "midleft")

    def _draw_info(self, canvas) -> None:
        sp = self.spot
        box = pygame.Rect(298, FC.bottom + 4, 168, 247 - FC.bottom - 4)
        ui.panel(canvas, box, fill=(16, 20, 36))
        if self.town_sel:
            self._draw_town_info(canvas, box)
            return
        x, y = box.x + 6, box.y + 8
        secret_hidden = sp.get("secret") and not self.unlocked(sp) and not can_unlock_soon(self.save, sp)
        text(canvas, "???" if secret_hidden else sp["name"], (x, y + 2), ui.ACCENT, 11, "midleft")
        yy = y + 18
        desc = "어딘가에 숨겨진 장소가 있다고 한다." if secret_hidden else sp["desc"]
        locked = not self.unlocked(sp)
        if not locked or secret_hidden:   # 잠긴 곳은 설명 대신 해금 조건 
            for ln in wrap_text(desc, box.w - 12)[:2]:
                text(canvas, ln, (x, yy), ui.DIM, 11, "midleft")
                yy += 12
            yy += 4
        fishes = [f for f in all_fish() if f["spot"] == sp["id"]]
        got = sum(1 for f in fishes if self.save.dex_entry(f["id"]))
        if not secret_hidden:
            if not locked:
                text(canvas, f"도감 {got}/{len(fishes)}종", (x, yy), ui.TEXT, 11, "midleft")
                yy += 13
            # 권장 낚싯대: 이보다 낮으면 희귀·전설이 크게 날뛰어 버티기 어렵다 (fight.heave_amp)
            need = sp.get("gear_tier", 1)
            have = self.save.gear_tier("rod")
            label = f"권장 낚싯대 T{need}+ · 전설 T{min(8, need + 1)}+" if have >= need else \
                f"장비가 약해요 (T{need} 권장) · 전설은 장비 조건 후"   # 미리 맛보기 (CU8-⑤)
            text(canvas, label, (x, yy), ui.TEXT if have >= need else ui.BAD, 11, "midleft")  # 지금 낚싯대보다 높으면 빨강
            yy += 14
        self.go_btn.rect.topleft = (box.x + 2, box.bottom - 20)
        self.go_btn.rect.size = (box.w - 4, 17)
        if sp["id"] == self.fishing.spot_id and self.village is not None:
            self.go_btn.label, self.go_btn.enabled = "다시 여기로 출발", self.fishing.fight is None
        elif sp["id"] == self.fishing.spot_id:
            self.go_btn.label, self.go_btn.enabled = "지금 여기 있어요", False
        elif self.unlocked(sp):
            self.go_btn.label, self.go_btn.enabled = "이동 (1시간)", self.fishing.fight is None
            self._travel_preview(canvas, x, self.go_btn.rect.y - 20)
        else:
            ok, rows = unlock_status(self.save, sp)
            room = max(1, (self.go_btn.rect.y - yy + 4) // 12)
            if len(rows) > room:   # 다 못 넣으면 못 채운 것부터
                rows = sorted(rows, key=lambda r: r[1])[:room]
            for label, met in rows:
                col = ui.GOOD if met else ui.BAD
                canvas.fill(col, (x + 2, yy - 2, 5, 5))
                if not met:
                    canvas.fill((16, 20, 36), (x + 3, yy - 1, 3, 3))
                text(canvas, label, (x + 11, yy), col, 11, "midleft")
                yy += 12
            cost = sp["unlock"].get("cost", 0)
            self.go_btn.label = f"해금하기 ({cost:,}원)" if cost else "해금하기"
            if sp["id"] == "offshore":   # 스토리: 먼바다용 배 = 해강의 배 수리 (가격·조건 그대로)
                self.go_btn.label = f"해강의 배 수리 ({cost:,}원)"
            self.go_btn.enabled = ok
        self.go_btn.draw(canvas, self.mouse)

    def _draw_town_info(self, canvas, box) -> None:
        v = self._village()
        x, y = box.x + 6, box.y + 8
        text(canvas, v["name"], (x, y + 2), (255, 226, 150), 11, "midleft")
        yy = y + 18
        for ln in wrap_text(v.get("subtitle", ""), box.w - 12)[:2]:
            text(canvas, ln, (x, yy), ui.DIM, 11, "midleft")
            yy += 12
        yy += 4
        for ln in ("낚시점 · 의뢰 게시판 · 어탁 갤러리", "계절 알림판 · 마을 사람들"):
            text(canvas, ln, (x, yy), ui.TEXT, 11, "midleft")
            yy += 13
        self.go_btn.rect.topleft = (box.x + 2, box.bottom - 20)
        self.go_btn.rect.size = (box.w - 4, 17)
        if self.village is not None and self.village.cont == self.cont:
            self.go_btn.label, self.go_btn.enabled = "마을로 돌아가기", True
        else:
            self.go_btn.label, self.go_btn.enabled = f"{v['name']}로 가기", self.fishing.fight is None
        self.go_btn.draw(canvas, self.mouse)
