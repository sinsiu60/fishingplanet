"""상점: 살림망 물고기 판매·분해, 장비 구매·교체(티어별), 강화."""
import pygame

from src.core.config import load_json
from src.render.fish_draw import RANK_COLORS, draw_fish_side, fish_colors
from src.fishing.bite import bait_tier_mult
from src.save.save_game import baits, enhanced, equipment, rules
from src.scene.base import Scene
from src.ui import widgets as ui
from src.ui.hud import draw_cursor, text, wrap_text

TABS = [("sell", "판매"), ("rod", "낚싯대"), ("reel", "릴"), ("line", "줄"), ("net", "뜰채"), ("bait", "미끼"),
        ("enhance", "강화")]
KIND_KO = {"rod": "낚싯대", "reel": "릴", "line": "줄", "net": "뜰채", "bait": "미끼"}
MAT_KO = {"sharmion": "샤르미온 소재", "eldrasion": "엘드라시온 소재", "rare": "희귀 소재"}
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
        if item.get("tier", 1) > 1:
            rare = (bait_tier_mult(item, "bait_tier_rare_bonus") - 1) * 100
            win = (bait_tier_mult(item, "bait_tier_window_bonus") - 1) * 100
            lines.append(f"티어 보너스: 희귀 +{rare:.0f}% · 챔질 +{win:.0f}%")
        return lines
    return []


def stat_rows(kind: str, item: dict) -> list[tuple[str, float, str, bool]]:
    """비교용 (이름, 값, 표시 형식, 클수록 좋은지)."""
    if kind == "rod":
        lo, hi = item["green"]
        return [("초록 구간 폭", hi - lo, "{:.0f}", True)]
    if kind == "reel":
        return [("감기 속도", item["speed"], "×{:.2f}", True), ("드랙 단계", item["drag_steps"], "{:.0f}", True)]
    if kind == "line":
        return [("줄 내구도", item["durability"], "{:.0f}", True)]
    if kind == "net":
        return [("판정 창", item["window"], "±{:.2f}초", True), ("실패 시 도망", item["fail_distance"], "{:.1f}m", False)]
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
        self.age = 0.0  # 열림 애니메이션
        self.tabs = ui.Tabs(16, 30, [t[1] for t in TABS], width=56)
        self.sel = 0
        self.scroll = 0
        self.msg, self.msg_col, self.msg_t = "", ui.TEXT, 0.0
        self.close_btn = ui.Button((404, 244, 60, 16), "닫기 (B)", self._close)
        self.action_btn = ui.Button((DETAIL.x + 8, DETAIL.bottom - 40, DETAIL.w - 16, 17), "", self._action)
        self.sell_all_btn = ui.Button((DETAIL.x + 8, DETAIL.bottom - 20, DETAIL.w - 16, 17), "", self._sell_all)
        half = (DETAIL.w - 20) // 2
        self.sell_btn = ui.Button((DETAIL.x + 8, DETAIL.bottom - 40, half, 17), "팔기", self._action)
        self.dis_btn = ui.Button((DETAIL.x + 12 + half, DETAIL.bottom - 40, half, 17), "분해", self._disassemble)

    # ── 데이터 ──
    @property
    def kind(self) -> str:
        return TABS[self.tabs.index][0]

    def items(self) -> list:
        if self.kind == "sell":
            return self.save.data["keepnet"]
        if self.kind == "bait":
            lst = [b for b in baits().values() if b["price"] >= 0 or self.save.owns("bait", b["id"])]
            return sorted(lst, key=lambda b: (b.get("tier") is None, b.get("tier") or 0, b["price"]))  # 전설 미끼는 맨 뒤
        if self.kind == "enhance":
            out = []
            for k in rules()["enhance_kinds"]:
                for g in sorted(equipment()[k], key=lambda g: g["tier"]):
                    if self.save.owns(k, g["id"]):
                        out.append((k, g))
            return out
        return sorted(equipment()[self.kind], key=lambda g: g["tier"])

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
        if self.kind == "enhance":
            kind, gear = item
            res = self.save.enhance(kind, gear)
            if res == "ok":
                self.game.sfx.play("great")
                self._say(f"{gear['name']} +{self.save.enhance_level(gear['id'])} 강화 성공!", ui.GOOD)
            elif res == "money":
                self._say("돈이 부족해요", ui.BAD)
            elif res == "materials":
                self._say("소재가 부족해요 (판매 탭에서 물고기 분해)", ui.BAD)
            return
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
        elif result == "scales":
            self._say("전설 비늘이 부족해요", ui.BAD)
        elif result == "locked":
            self._say(self.save.gear_locked_reason(item) or self.save.bait_locked_reason(item), ui.BAD)

    def _disassemble(self) -> None:
        got = self.save.disassemble(self.sel)
        if got is None:
            self._say("전설은 분해할 수 없어요", ui.BAD)
            return
        self.game.sfx.play("click")
        self._say("분해: " + ", ".join(f"{MAT_KO[k]} +{v}" for k, v in got.items()), ui.GOOD)
        self.sel = max(0, min(self.sel, len(self.items()) - 1))

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
            buttons = (self.close_btn, self.sell_btn, self.dis_btn, self.sell_all_btn) if self.kind == "sell" \
                else (self.close_btn, self.action_btn)
            for b in buttons:
                if b.click(m):
                    return
            if LIST.collidepoint(m):
                i = (m[1] - LIST.y) // ROW_H + self.scroll
                if 0 <= i < len(self.items()):
                    self.sel = i
                    self.game.sfx.play("click")

    def update(self, dt: float) -> None:
        self.age += dt
        self.mouse = self.game.to_canvas(pygame.mouse.get_pos())
        self.msg_t = max(0.0, self.msg_t - dt)

    # ── 그리기 ──
    def draw(self, canvas) -> None:
        self.fishing.draw(canvas)
        ui.dim(canvas, int(170 * min(1.0, self.age / 0.15)))
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
        elif self.kind == "enhance":
            self._draw_enhance(canvas, items, visible)
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
            self.sell_all_btn.enabled = self.sell_btn.enabled = self.dis_btn.enabled = False
            return
        self.sell_btn.enabled = True
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
        got = self.save.disassemble_yield(self.sel)
        dis = ", ".join(f"{MAT_KO[k]} {v}" for k, v in got.items()) if got else "전설은 분해 불가"
        text(canvas, f"분해: {dis}", (DETAIL.centerx, DETAIL.y + 138), ui.DIM, 11, "center")
        total = sum(x["price"] for x in items)
        self.dis_btn.enabled = got is not None
        self.sell_all_btn.label, self.sell_all_btn.enabled = f"모두 팔기 ({len(items)}마리 · {total:,}원)", True
        self.sell_btn.draw(canvas, self.mouse)
        self.dis_btn.draw(canvas, self.mouse)
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
            locked = not owned and (self.save.gear_locked_reason(it)
                                    or (kind == "bait" and self.save.bait_locked_reason(it)))
            col = ui.DIM if locked else ui.TEXT
            tier = f"T{it['tier']}" if it.get("tier") else "전설"
            lvl = self.save.enhance_level(it["id"]) if owned else 0
            text(canvas, tier, (r.x + 4, r.centery), ui.DIM if locked else ui.ACCENT, 11, "midleft")
            text(canvas, it["name"] + (f" +{lvl}" if lvl else ""), (r.x + 34, r.centery), col, 11, "midleft")
            if it["id"] == equipped:
                status, scol = "장착 중", ui.GOOD
            elif owned:
                status, scol = "보유", ui.TEXT
            elif locked:
                status, scol = ("엘드라시온" if self.save.gear_locked_reason(it) else "잠김"), ui.DIM
            else:
                status, scol = f"{it['price']:,}원", ui.ACCENT if self.save.money >= it["price"] else ui.BAD
            text(canvas, status, (r.right - 4, r.centery), scol, 11, "midright")
        it = items[self.sel]
        cur = self.save.equipped(kind)
        owned = self.save.owns(kind, it["id"])
        x, y = DETAIL.x + 8, DETAIL.y + 8
        lvl = self.save.enhance_level(it["id"]) if owned else 0
        text(canvas, it["name"] + (f" +{lvl}" if lvl else ""), (x, y + 4), ui.ACCENT, 11, "midleft")
        text(canvas, f"T{it['tier']}" if it.get("tier") else "전설 미끼", (DETAIL.right - 8, y + 4), ui.ACCENT, 11,
             "midright")
        yy = y + 20
        for ln in wrap_text(it["desc"], DETAIL.w - 16)[:2]:
            text(canvas, ln, (x, yy), ui.DIM, 11, "midleft")
            yy += 13
        yy += 4
        if kind == "bait":
            for ln in stat_lines(kind, it)[:5]:
                text(canvas, ln, (x, yy), ui.TEXT, 11, "midleft")
                yy += 13
        else:
            # 지금 장착한 장비(강화 포함)와 비교: +는 초록, -는 빨강
            mine = self.save.effective(kind, it)
            now = self.save.effective(kind, cur)
            same = it["id"] == cur["id"]
            for (label, v, fmt, up), (_, v0, _, _) in zip(stat_rows(kind, mine), stat_rows(kind, now)):
                text(canvas, f"{label} {fmt.format(v)}", (x, yy), ui.TEXT, 11, "midleft")
                d = v - v0
                if not same and abs(d) > 1e-6:
                    good = (d > 0) == up
                    dtxt = ("+" if d > 0 else "-") + fmt.format(abs(d)).lstrip("×±")
                    text(canvas, dtxt, (DETAIL.right - 8, yy), ui.GOOD if good else ui.BAD, 11, "midright")
                yy += 13
            if not same:
                text(canvas, f"(지금: {cur['name']})", (x, yy + 2), ui.DIM, 11, "midleft")
        if it.get("scales"):
            have = self.save.data["scales"]
            text(canvas, f"전설 비늘 {it['scales']}개 필요 (보유 {have})", (x, DETAIL.bottom - 72),
                 ui.TEXT if have >= it["scales"] else ui.BAD, 11, "midleft")
        reason = not owned and (self.save.gear_locked_reason(it)
                                or (kind == "bait" and self.save.bait_locked_reason(it)))
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
            self.action_btn.enabled = self.save.money >= it["price"] and self.save.data["scales"] >= it.get("scales", 0)
        self.action_btn.draw(canvas, self.mouse)

    def _draw_enhance(self, canvas, items, visible) -> None:
        mats = self.save.data["materials"]
        text(canvas, "  ".join(f"{MAT_KO[k]} {mats.get(k, 0)}" for k in ("sharmion", "eldrasion", "rare")),
             (240, 16), ui.DIM, 11, "center")
        if not items:
            text(canvas, "강화할 장비가 없어요", LIST.center, ui.DIM, 11, "center")
            self.action_btn.enabled = False
            return
        for i in range(self.scroll, min(len(items), self.scroll + visible)):
            kind, g = items[i]
            r = self._row_rect(i)
            if i == self.sel or r.collidepoint(self.mouse):
                canvas.fill(ui.PANEL_LIGHT, r)
            lvl = self.save.enhance_level(g["id"])
            text(canvas, KIND_KO[kind], (r.x + 4, r.centery), ui.DIM, 11, "midleft")
            text(canvas, f"T{g['tier']} {g['name']}", (r.x + 46, r.centery), ui.TEXT, 11, "midleft")
            text(canvas, f"+{lvl}" if lvl else "", (r.right - 4, r.centery), ui.ACCENT, 11, "midright")
        kind, g = items[self.sel]
        lvl = self.save.enhance_level(g["id"])
        x, y = DETAIL.x + 8, DETAIL.y + 8
        text(canvas, f"{g['name']} +{lvl}", (x, y + 4), ui.ACCENT, 11, "midleft")
        text(canvas, "★" * lvl + "☆" * (rules()["max_level"] - lvl), (DETAIL.right - 8, y + 4), ui.ACCENT, 11,
             "midright")
        cost = self.save.enhance_cost(kind, g)
        yy = y + 22
        now = enhanced(kind, g, lvl)
        nxt = enhanced(kind, g, lvl + 1) if cost else now
        for (label, v0, fmt, up), (_, v1, _, _) in zip(stat_rows(kind, now), stat_rows(kind, nxt)):
            line = f"{label} {fmt.format(v0)}" + (f" → {fmt.format(v1)}" if cost else "")
            text(canvas, line, (x, yy), ui.GOOD if cost and v1 != v0 else ui.TEXT, 11, "midleft")
            yy += 13
        yy += 6
        if cost is None:
            text(canvas, "최대 강화 (+3)", (x, yy), ui.GOOD, 11, "midleft")
            self.action_btn.label, self.action_btn.enabled = "최대 강화", False
        else:
            have_gold = self.save.money >= cost["gold"]
            have_mat = mats.get(cost["continent"], 0) >= cost["materials"]
            have_rare = mats.get("rare", 0) >= cost["rare"]
            text(canvas, f"골드 {cost['gold']:,}원", (x, yy), ui.TEXT if have_gold else ui.BAD, 11, "midleft")
            yy += 13
            text(canvas, f"{MAT_KO[cost['continent']]} {mats.get(cost['continent'], 0)}/{cost['materials']}",
                 (x, yy), ui.TEXT if have_mat else ui.BAD, 11, "midleft")
            yy += 13
            if cost["rare"]:
                text(canvas, f"희귀 소재 {mats.get('rare', 0)}/{cost['rare']}", (x, yy),
                     ui.TEXT if have_rare else ui.BAD, 11, "midleft")
            text(canvas, "강화는 실패하지 않아요", (x, DETAIL.bottom - 56), ui.DIM, 11, "midleft")
            self.action_btn.label = f"+{lvl + 1} 강화"
            self.action_btn.enabled = have_gold and have_mat and have_rare
        self.action_btn.draw(canvas, self.mouse)
