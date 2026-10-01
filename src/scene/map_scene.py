"""낚시터 지도: 이동, 해금 조건·해금, 날씨 예보, 텐트에서 쉬기."""
import math

import pygame

from src.core.config import load_json
from src.core.weather import WEATHER_KO
from src.save.save_game import all_fish
from src.scene.base import Scene
from src.ui import widgets as ui
from src.ui.hud import draw_cursor, text, wrap_text

SHARMION_SPOTS = ("reservoir", "valley", "breakwater", "offshore", "deep")
LAND = (88, 128, 82)
LAND_DARK = (66, 100, 64)
SEA = (44, 84, 140)
SEA_LIGHT = (70, 116, 170)
PATH = (240, 226, 180)


def unlock_status(save, spot: dict) -> tuple[bool, list[tuple[str, bool]]]:
    """(조건을 모두 채웠는지, [(조건 설명, 충족 여부)]) — 지도 체크리스트."""
    cond = spot.get("unlock", {})
    rows = []
    if "dex" in cond:
        rows.append((f"도감 {cond['dex']}종 ({save.dex_count()}/{cond['dex']})", save.dex_count() >= cond["dex"]))
    if "dex_pct" in cond:
        got, total = save.continent_dex(spot.get("continent", "sharmion"))
        need = math.ceil(total * cond["dex_pct"] / 100)
        rows.append((f"도감 {cond['dex_pct']}% ({got}/{need}종)", got >= need))
    if "rod_tier" in cond:
        tier = save.gear_tier("rod")
        rows.append((f"낚싯대 T{cond['rod_tier']} 이상 (지금 T{tier})", tier >= cond["rod_tier"]))
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
        legends = [f["id"] for f in all_fish() if f["rarity"] == "legend" and f["spot"] != "secret"
                   and f.get("spot") in SHARMION_SPOTS]
        got = sum(1 for fid in legends if save.caught(fid))
        rows.append((f"전설 {got}/{cond['legends']}마리 포획", got >= cond["legends"]))
    if "s_total" in cond:
        n = save.data["stats"]["s_ranks"]
        rows.append((f"S랭크 {min(n, cond['s_total'])}/{cond['s_total']}회", n >= cond["s_total"]))
    if "perfects" in cond:
        n = save.data["stats"]["perfects"]
        rows.append((f"퍼펙트 {min(n, cond['perfects'])}/{cond['perfects']}회",
                     n >= cond["perfects"]))
    if cond.get("cost"):
        rows.append((f"비용 {ui.money_text(cond['cost'])}", save.money >= cond["cost"]))
    return all(ok for _, ok in rows), rows


def can_unlock_soon(save, spot: dict) -> bool:
    """비용 빼고 조건이 다 찼는지 (새 낚시터 알림용)."""
    ok, rows = unlock_status(save, spot)
    return all(ok for label, ok in rows if not label.startswith("비용"))


class MapScene(Scene):
    def __init__(self, game, fishing):
        super().__init__(game)
        self.fishing = fishing
        self.save = game.save
        self.mouse = (0, 0)
        self.age = 0.0  # 열림 애니메이션
        self.spots = load_json("spots.json")["spots"]
        self.sel = next(i for i, s in enumerate(self.spots) if s["id"] == fishing.spot_id)
        self.t = 0.0
        self.msg, self.msg_t, self.msg_col = "", 0.0, ui.TEXT
        self.close_btn = ui.Button((404, 250, 64, 15), "닫기 (M)", self._close)
        self.go_btn = ui.Button((300, 214, 164, 17), "", self._go)
        self.rest_btn = ui.Button((300, 56, 164, 16), "텐트에서 쉬기", self._rest)

    @property
    def spot(self) -> dict:
        return self.spots[self.sel]

    def unlocked(self, spot) -> bool:
        return spot["id"] in self.save.data["unlocked_spots"]

    def _say(self, s: str, col=ui.TEXT) -> None:
        self.msg, self.msg_t, self.msg_col = s, 2.2, col

    def _close(self) -> None:
        self.game.scenes.pop()

    def _go(self) -> None:
        sp = self.spot
        if sp["id"] == self.fishing.spot_id:
            return
        if self.unlocked(sp):
            self.fishing.travel(sp["id"])
            self.game.sfx.play("splash_small", 0.6)
            self.game.scenes.pop()
            self.game.fade_in(0.8)
            return
        ok, _ = unlock_status(self.save, sp)
        if ok:
            self.save.data["money"] -= sp["unlock"].get("cost", 0)
            self.save.data["unlocked_spots"].append(sp["id"])
            self.game.sfx.play("coin")
            self.game.sfx.play("catch", 0.7)
            self._say(f"{sp['name']} 해금!", ui.GOOD)
            if sp["id"] == "secret" and not self.save.owns("bait", "dragon_pearl"):
                # 최종 전설을 부르는 미끼
                self.save.data["owned"]["bait"].append("dragon_pearl")
                self.game.sfx.play("chord_legend", 0.7)
                self._say("용문 폭포 해금! 여의주를 얻었다", (255, 214, 90))
            self.game.save_now()

    def _rest(self) -> None:
        label = self.fishing.rest()
        self.game.sfx.play("click")
        self._say(f"텐트에서 쉬었다 → {label}", ui.GOOD)

    def handle_event(self, event) -> None:
        if event.type == pygame.KEYDOWN and event.key in (pygame.K_ESCAPE, pygame.K_m):
            self._close()
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            m = self.game.to_canvas(event.pos)
            for b in (self.close_btn, self.go_btn, self.rest_btn):
                if b.click(m):
                    return
            for i, sp in enumerate(self.spots):
                x, y = self._node(sp)
                if math.hypot(m[0] - x, m[1] - y) < 13:
                    self.sel = i
                    self.game.sfx.play("click")

    def update(self, dt: float) -> None:
        self.age += dt
        self.t += dt
        self.msg_t = max(0.0, self.msg_t - dt)
        self.mouse = self.game.to_canvas(pygame.mouse.get_pos())

    def _node(self, sp) -> tuple[int, int]:
        x, y = sp["map_pos"]
        return int(12 + x * 0.6), int(30 + y * 0.92)

    # ───────────────────────── 그리기 ─────────────────────────
    def draw(self, canvas) -> None:
        self.fishing.draw(canvas)
        ui.dim(canvas, int(170 * min(1.0, self.age / 0.15)))
        ui.panel(canvas, (6, 6, 468, 260))
        text(canvas, "지도", (14, 16), ui.ACCENT, 16, "midleft")
        text(canvas, f"소지금 {ui.money_text(self.save.money)} · 도감 {self.save.dex_count()}/{len(all_fish())}",
             (290, 16), ui.ACCENT, 11, "midright")
        self._draw_map(canvas)
        self._draw_weather(canvas)
        self._draw_info(canvas)
        if self.msg_t > 0:
            text(canvas, self.msg, (14, 256), self.msg_col, 11, "midleft")
        self.close_btn.draw(canvas, self.mouse)
        draw_cursor(canvas, self.mouse)

    def _draw_map(self, canvas) -> None:
        area = pygame.Rect(12, 28, 280, 222)
        canvas.fill(SEA, area)
        for i in range(0, area.h, 6):
            off = int(self.t * 6 + i * 3) % 24
            canvas.fill(SEA_LIGHT, (area.x + off + (i * 37) % 200, area.y + i, 10, 1))
        land = [(12, 28), (200, 28), (190, 70), (165, 110), (150, 150), (120, 180), (130, 215), (95, 250), (12, 250)]
        pygame.draw.polygon(canvas, LAND, land)
        pygame.draw.lines(canvas, LAND_DARK, False, land[1:-1], 2)
        # 산 기호
        for mx, my in ((60, 70), (90, 60), (115, 82), (45, 110)):
            pygame.draw.polygon(canvas, LAND_DARK, [(mx - 9, my + 7), (mx, my - 7), (mx + 9, my + 7)])
        # 경로
        nodes = [self._node(sp) for sp in self.spots]
        for a, b in zip(nodes[:-2], nodes[1:-1]):
            steps = int(math.hypot(b[0] - a[0], b[1] - a[1]) / 6)
            for k in range(steps):
                if k % 2 == 0:
                    x = a[0] + (b[0] - a[0]) * k / steps
                    y = a[1] + (b[1] - a[1]) * k / steps
                    canvas.fill(PATH, (int(x), int(y), 2, 2))
        for i, sp in enumerate(self.spots):
            x, y = nodes[i]
            secret = sp["id"] == "secret"
            unlocked = self.unlocked(sp)
            if secret and not unlocked:
                if not can_unlock_soon(self.save, sp):
                    # 비밀 장소는 조건을 채우기 전까지 희미한 물음표
                    text(canvas, "?", (x, y), (120, 130, 160), 16, "center")
                    if i == self.sel:
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
            if i == self.sel:
                rr = r + 4 + int(2 * math.sin(self.t * 5))
                pygame.draw.circle(canvas, ui.ACCENT, (x, y), rr, 1)
            if current:
                text(canvas, "현재", (x, y - 13), ui.ACCENT, 11, "center")
            text(canvas, sp["short"], (x, y + 13), col, 11, "center")

    def _draw_weather(self, canvas) -> None:
        f = self.fishing
        w = f.weather_sys
        box = pygame.Rect(298, 28, 168, 46)
        ui.panel(canvas, box, fill=(16, 20, 36))
        left = w.hours_left(f.clock.day, f.clock.hour)
        text(canvas, f"{f.clock.label()} · {WEATHER_KO[w.current]}", (box.x + 6, box.y + 9), ui.TEXT, 11, "midleft")
        text(canvas, f"예보: {left:.0f}시간 뒤 {WEATHER_KO[w.upcoming]}", (box.x + 6, box.y + 21), (150, 210, 255), 11,
             "midleft")
        self.rest_btn.rect.topleft = (box.x + 2, box.y + 30)
        self.rest_btn.rect.size = (box.w - 4, 14)
        self.rest_btn.label = f"텐트에서 쉬기 → {f.next_period_name()}"
        self.rest_btn.enabled = f.fight is None
        self.rest_btn.draw(canvas, self.mouse)

    def _draw_info(self, canvas) -> None:
        sp = self.spot
        box = pygame.Rect(298, 80, 168, 156)
        ui.panel(canvas, box, fill=(16, 20, 36))
        x, y = box.x + 6, box.y + 8
        secret_hidden = sp["id"] == "secret" and not self.unlocked(sp) and not can_unlock_soon(self.save, sp)
        text(canvas, "???" if secret_hidden else sp["name"], (x, y + 2), ui.ACCENT, 11, "midleft")
        yy = y + 18
        desc = "어딘가에 숨겨진 장소가 있다고 한다." if secret_hidden else sp["desc"]
        for ln in wrap_text(desc, box.w - 12)[:3]:
            text(canvas, ln, (x, yy), ui.DIM, 11, "midleft")
            yy += 12
        yy += 4
        fishes = [f for f in all_fish() if f["spot"] == sp["id"]]
        got = sum(1 for f in fishes if self.save.dex_entry(f["id"]))
        if not secret_hidden:
            text(canvas, f"도감 {got}/{len(fishes)}종", (x, yy), ui.TEXT, 11, "midleft")
            yy += 14
        self.go_btn.rect.topleft = (box.x + 2, box.bottom - 20)
        self.go_btn.rect.size = (box.w - 4, 17)
        if sp["id"] == self.fishing.spot_id:
            self.go_btn.label, self.go_btn.enabled = "지금 여기 있어요", False
        elif self.unlocked(sp):
            self.go_btn.label, self.go_btn.enabled = "이동 (1시간)", self.fishing.fight is None
        else:
            ok, rows = unlock_status(self.save, sp)
            text(canvas, "해금 조건", (x, yy), ui.TEXT, 11, "midleft")
            yy += 13
            for label, met in rows:
                col = ui.GOOD if met else ui.BAD
                canvas.fill(col, (x + 2, yy - 2, 5, 5))
                if not met:
                    canvas.fill((16, 20, 36), (x + 3, yy - 1, 3, 3))
                text(canvas, label, (x + 11, yy), col, 11, "midleft")
                yy += 12
            cost = sp["unlock"].get("cost", 0)
            self.go_btn.label = f"해금하기 ({cost:,}원)" if cost else "해금하기"
            self.go_btn.enabled = ok
        self.go_btn.draw(canvas, self.mouse)
