"""상점: 살림망 물고기 판매, 장비 구매·교체."""
import pygame

from src.core.config import load_json
from src.render.fish_draw import RANK_COLORS, draw_fish_side, fish_colors
from src.save.save_game import baits, equipment
from src.scene.base import Scene
from src.ui import widgets as ui
from src.ui.hud import draw_cursor, text, wrap_text

TABS = [("sell", "판매"), ("rod", "낚싯대"), ("reel", "릴"), ("line", "줄"), ("net", "뜰채"), ("bait", "미끼")]
ROW_H = 17
LIST = pygame.Rect(16, 52, 236, 186)
DETAIL = pygame.Rect(260, 52, 204, 186)
RARITY_COL = {"common": (230, 230, 230), "uncommon": (130, 230, 150), "rare": (130, 190, 255),
              "legend": (255, 214, 90)}


def stat_lines(kind: str, item: dict) -> list[str]:
    if kind == "rod":
        lo, hi = item["green"]
        return [f"초록 구간 {lo}~{hi} (폭 {hi - lo})"]
    if kind == "reel":
        return [f"감기 속도 ×{item['speed']:.2f}", f"드랙 {item['drag_steps']}단계"]
    if kind == "line":
        return [f"줄 내구도 {item['durability']}"]
    if kind == "net":
        return [f"뜰채 판정 ±{item['window']:.2f}초", f"실패 시 {item['fail_distance']:.1f}m 도망"]
    if kind == "bait":
        lines = [f"챔질 창 ×{item.get('window_mult', 1.0):.1f}"]
        names = {f["id"]: f["name"] for f in load_json("fish.json")["fish"]}
        if item.get("legend_for"):
            lines.append(f"전설 {names[item['legend_for']]} 조건")
        boost = item.get("boost", {})
        if boost:
            best = [names[k] for k, v in boost.items() if v > 1.0][:3]
            if best:
                lines.append("잘 무는 물고기: " + ", ".join(best))
        for sp, v in item.get("spot_boost", {}).items():
            spot = next(s["name"] for s in load_json("spots.json")["spots"] if s["id"] == sp)
            lines.append(f"{spot} 입질 ×{v}")
        if item.get("nibble_delta", 0) < 0:
            lines.append("가짜 입질 감소")
        return lines
    return []


def score(kind: str, item: dict) -> float:
    """비교용 단일 수치 (높을수록 좋음)."""
    return {"rod": lambda i: i["green"][1] - i["green"][0], "reel": lambda i: i["speed"],
            "line": lambda i: i["durability"], "net": lambda i: i["window"]}.get(kind, lambda i: 0)(item)


class ShopScene(Scene):
    def __init__(self, game, fishing):
        super().__init__(game)
        self.fishing = fishing
        self.save = game.save
        self.mouse = (0, 0)
        self.tabs = ui.Tabs(16, 30, [t[1] for t in TABS], width=58)
        self.sel = 0
        self.scroll = 0
        self.msg, self.msg_col, self.msg_t = "", ui.TEXT, 0.0
        self.close_btn = ui.Button((404, 244, 60, 16), "닫기 (B)", self._close)
        self.action_btn = ui.Button((DETAIL.x + 8, DETAIL.bottom - 40, DETAIL.w - 16, 17), "", self._action)
        self.sell_all_btn = ui.Button((DETAIL.x + 8, DETAIL.bottom - 20, DETAIL.w - 16, 17), "", self._sell_all)

    # ── 데이터 ──
    @property
    def kind(self) -> str:
        return TABS[self.tabs.index][0]

    def items(self) -> list:
        if self.kind == "sell":
            return self.save.data["keepnet"]
        if self.kind == "bait":
            return [b for b in baits().values() if b["price"] >= 0 or self.save.owns("bait", b["id"])]
        return equipment()[self.kind]

    def fish_by_id(self, fid: str) -> dict:
        return next(f for f in load_json("fish.json")["fish"] if f["id"] == fid)

    def _say(self, msg: str, col=ui.TEXT) -> None:
        self.msg, self.msg_col, self.msg_t = msg, col, 2.0

    # ── 동작 ──
    def _close(self) -> None:
        self.game.save_now()
        self.game.scenes.pop()

    def _action(self) -> None:
        items = self.items()
        if not items:
            return
        item = items[min(self.sel, len(items) - 1)]
        if self.kind == "sell":
            gained = self.save.sell(self.sel)
            self.game.sfx.play("coin")
            self._say(f"+{ui.money_text(gained)}", ui.GOOD)
            self.sel = max(0, min(self.sel, len(self.items()) - 1))
            return
        if self.save.owns(self.kind, item["id"]):
            self.save.equip(self.kind, item["id"])
            self.game.sfx.play("click")
            self._say(f"{item['name']} 장착", ui.GOOD)
            return
        result = self.save.buy(self.kind, item)
        if result == "ok":
            self.game.sfx.play("coin")
            self._say(f"{item['name']} 구매 · 장착!", ui.GOOD)
        elif result == "money":
            self._say("돈이 부족해요", ui.BAD)
        elif result == "locked":
            self._say(self.save.bait_locked_reason(item), ui.BAD)

    def _sell_all(self) -> None:
        if self.save.data["keepnet"]:
            total = self.save.sell_all()
            self.game.sfx.play("coin")
            self._say(f"모두 팔았어요 +{ui.money_text(total)}", ui.GOOD)
            self.sel = 0

    # ── 입력 ──
    def handle_event(self, event) -> None:
        if event.type == pygame.KEYDOWN and event.key in (pygame.K_ESCAPE, pygame.K_b):
            self._close()
        elif event.type == pygame.MOUSEWHEEL:
            n = len(self.items())
            visible = LIST.h // ROW_H
            self.scroll = max(0, min(max(0, n - visible), self.scroll - event.y))
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            m = self.game.to_canvas(event.pos)
            if self.tabs.click(m):
                self.sel, self.scroll = 0, 0
                self.game.sfx.play("click")
                return
            for b in (self.close_btn, self.action_btn, self.sell_all_btn):
                if b.click(m):
                    return
            if LIST.collidepoint(m):
                i = (m[1] - LIST.y) // ROW_H + self.scroll
                if 0 <= i < len(self.items()):
                    self.sel = i
                    self.game.sfx.play("click")

    def update(self, dt: float) -> None:
        self.mouse = self.game.to_canvas(pygame.mouse.get_pos())
        self.msg_t = max(0.0, self.msg_t - dt)

    # ── 그리기 ──
    def draw(self, canvas) -> None:
        self.fishing.draw(canvas)
        ui.dim(canvas, 170)
        ui.panel(canvas, (8, 6, 464, 258))
        text(canvas, "상점", (16, 16), ui.ACCENT, 16, "midleft")
        text(canvas, f"소지금 {ui.money_text(self.save.money)}", (464, 16), ui.ACCENT, 11, "midright")
        self.tabs.draw(canvas, self.mouse)
        ui.panel(canvas, LIST, fill=(16, 20, 36))
        ui.panel(canvas, DETAIL, fill=(16, 20, 36))
        items = self.items()
        self.sel = max(0, min(self.sel, len(items) - 1)) if items else 0
        visible = LIST.h // ROW_H
        if self.kind == "sell":
            self._draw_sell(canvas, items, visible)
        else:
            self._draw_gear(canvas, items, visible)
        if self.msg_t > 0:
            text(canvas, self.msg, (LIST.x, 252), self.msg_col, 11, "midleft")
        self.close_btn.draw(canvas, self.mouse)
        draw_cursor(canvas, self.mouse)

    def _row_rect(self, i: int) -> pygame.Rect:
        return pygame.Rect(LIST.x + 2, LIST.y + 2 + (i - self.scroll) * ROW_H, LIST.w - 4, ROW_H - 1)

    def _draw_sell(self, canvas, items, visible) -> None:
        if not items:
            text(canvas, "살림망이 비어 있어요", LIST.center, ui.DIM, 11, "center")
            text(canvas, "물고기를 잡으면 여기에 보관돼요", (DETAIL.centerx, DETAIL.centery), ui.DIM, 11, "center")
            self.sell_all_btn.enabled = self.action_btn.enabled = False
            return
        for i in range(self.scroll, min(len(items), self.scroll + visible)):
            it = items[i]
            fish = self.fish_by_id(it["id"])
            r = self._row_rect(i)
            sel = i == self.sel
            if sel or r.collidepoint(self.mouse):
                canvas.fill(ui.PANEL_LIGHT, r)
            text(canvas, fish["name"][:9], (r.x + 4, r.centery), RARITY_COL[fish["rarity"]], 11, "midleft")
            text(canvas, f"{it['size']:.1f}cm", (r.x + 120, r.centery), ui.TEXT, 11, "midleft")
            text(canvas, it["rank"], (r.x + 168, r.centery), RANK_COLORS[it["rank"]], 11, "midleft")
            text(canvas, f"{it['price']:,}", (r.right - 4, r.centery), ui.ACCENT, 11, "midright")
        it = items[self.sel]
        fish = self.fish_by_id(it["id"])
        draw_fish_side(canvas, DETAIL.centerx, DETAIL.y + 40, 110, 0.0, fish_colors(fish), -1, shape=fish.get("shape"))
        text(canvas, fish["name"], (DETAIL.centerx, DETAIL.y + 76), RARITY_COL[fish["rarity"]], 11, "center")
        text(canvas, f"{it['size']:.1f}cm · {it['rank']}랭크", (DETAIL.centerx, DETAIL.y + 92), ui.TEXT, 11, "center")
        text(canvas, f"판매가 {ui.money_text(it['price'])}", (DETAIL.centerx, DETAIL.y + 110), ui.ACCENT, 11, "center")
        if it["rank"] == "S":
            text(canvas, "S랭크 ×2 적용", (DETAIL.centerx, DETAIL.y + 124), RANK_COLORS["S"], 11, "center")
        total = sum(x["price"] for x in items)
        self.action_btn.label, self.action_btn.enabled = "팔기", True
        self.sell_all_btn.label, self.sell_all_btn.enabled = f"모두 팔기 ({len(items)}마리 · {total:,}원)", True
        self.action_btn.draw(canvas, self.mouse)
        self.sell_all_btn.draw(canvas, self.mouse)

    def _draw_gear(self, canvas, items, visible) -> None:
        kind = self.kind
        equipped = self.save.data["gear"][kind]
        for i in range(self.scroll, min(len(items), self.scroll + visible)):
            it = items[i]
            r = self._row_rect(i)
            if i == self.sel or r.collidepoint(self.mouse):
                canvas.fill(ui.PANEL_LIGHT, r)
            owned = self.save.owns(kind, it["id"])
            locked = kind == "bait" and not owned and self.save.bait_locked_reason(it)
            col = ui.DIM if locked else ui.TEXT
            text(canvas, it["name"], (r.x + 4, r.centery), col, 11, "midleft")
            if it["id"] == equipped:
                status, scol = "장착 중", ui.GOOD
            elif owned:
                status, scol = "보유", ui.TEXT
            elif locked:
                status, scol = "잠김", ui.DIM
            else:
                status, scol = f"{it['price']:,}원", ui.ACCENT if self.save.money >= it["price"] else ui.BAD
            text(canvas, status, (r.right - 4, r.centery), scol, 11, "midright")
        it = items[self.sel]
        cur = self.save.equipped(kind)
        x, y = DETAIL.x + 8, DETAIL.y + 8
        text(canvas, it["name"], (x, y + 4), ui.ACCENT, 11, "midleft")
        if "tier" in it:
            text(canvas, "★" * it["tier"] + "☆" * (5 - it["tier"]), (DETAIL.right - 8, y + 4), ui.ACCENT, 11, "midright")
        yy = y + 20
        for ln in wrap_text(it["desc"], DETAIL.w - 16)[:3]:
            text(canvas, ln, (x, yy), ui.DIM, 11, "midleft")
            yy += 13
        yy += 4
        better = score(kind, it) - score(kind, cur)
        for ln in stat_lines(kind, it):
            col = ui.GOOD if better > 0 and it["id"] != cur["id"] else ui.TEXT
            text(canvas, ln, (x, yy), col, 11, "midleft")
            yy += 13
        if it["id"] != cur["id"] and kind != "bait":
            yy += 2
            text(canvas, "지금: " + stat_lines(kind, cur)[0], (x, yy), ui.DIM, 11, "midleft")
        owned = self.save.owns(kind, it["id"])
        reason = kind == "bait" and not owned and self.save.bait_locked_reason(it)
        if it["id"] == self.save.data["gear"][kind]:
            self.action_btn.label, self.action_btn.enabled = "장착 중", False
        elif owned:
            self.action_btn.label, self.action_btn.enabled = "장착하기", True
        elif reason:
            self.action_btn.label, self.action_btn.enabled = "잠김", False
            for i, ln in enumerate(wrap_text(reason, DETAIL.w - 16)[:2]):
                text(canvas, ln, (x, DETAIL.bottom - 58 + i * 12), ui.BAD, 11, "midleft")
        else:
            self.action_btn.label = f"구매 ({it['price']:,}원)"
            self.action_btn.enabled = self.save.money >= it["price"]
        self.action_btn.draw(canvas, self.mouse)
        self.sell_all_btn.enabled = False
