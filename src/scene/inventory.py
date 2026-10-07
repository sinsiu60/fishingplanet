"""인벤토리 (I · 오른쪽 메뉴 '가방' 아이콘): 장착 중인 것 한눈에 + 가진 것 전부 관리.

왼쪽   장비칸 — 낚싯대·릴·줄·뜰채·미끼·특수 찌·부적(1~2칸)·외형. 칸을 누르면 그 종류 목록으로.
오른쪽 탭 — 장비(가진 낚싯대·릴·줄·뜰채, 보물 장비 포함) · 미끼 · 찌 · 아이템(보물상자에서 얻은 소모품·부적·외형) · 재료(돈·비늘·조각·소재·상자·살림망)
       목록에서 고르면 설명 + 버튼 하나 (장착 / 해제 / 사용 / 보물상자 열기 / 상점에서 판매).
아이템 사용·장착 규칙은 보물상자 화면과 같다 (src/save/item_use.py). 구매·강화는 상점에서.
"""
import pygame

from src.core.config import load_json
from src.save import item_use
from src.save import treasure as tr
from src.save.save_game import baits, equipment
from src.scene.base import Scene
from src.ui import widgets as ui
from src.ui.hud import draw_cursor, text, wrap_text

TABS = [("gear", "장비"), ("bait", "미끼"), ("float", "찌"), ("items", "아이템"), ("mats", "재료")]
GEAR_KINDS = ("rod", "reel", "line", "net")
KIND_KO = {"rod": "낚싯대", "reel": "릴", "line": "줄", "net": "뜰채", "bait": "미끼", "float": "특수 찌",
           "consumable": "소모품", "charm": "부적", "cosmetic": "외형"}
EQ = pygame.Rect(16, 52, 162, 186)
LIST = pygame.Rect(184, 52, 150, 186)
DETAIL = pygame.Rect(338, 52, 126, 186)
ROW_H = 17
EQ_ROW = 19
MAT_KO = {"sharmion": "샤르미온 소재", "eldrasion": "엘드라시온 소재", "rare": "희귀 소재"}


class InventoryScene(Scene):
    UI_FRAME = True

    def __init__(self, game, fishing):
        super().__init__(game)
        self.fishing = fishing
        self.save = game.save
        self.mouse = (0, 0)
        self.age = 0.0
        self.tabs = ui.Tabs(LIST.x, 30, [t[1] for t in TABS], width=54)
        self.sel = 0
        self.scroll = 0
        self.msg, self.msg_col, self.msg_t = "", ui.TEXT, 0.0
        self.close_btn = ui.Button((404, 244, 60, 16), "닫기 (I)", self._close)
        self.action_btn = ui.Button((DETAIL.x + 6, DETAIL.bottom - 22, DETAIL.w - 12, 17), "", self._action)
        self.chooser: str | None = None
        self.choice_btns: list[ui.Button] = []

    @property
    def kind(self) -> str:
        return TABS[self.tabs.index][0]

    def _say(self, msg: str, col=ui.TEXT) -> None:
        self.msg, self.msg_col, self.msg_t = msg, col, 2.2
        if col == ui.BAD:
            self.game.sfx.play("ui_error")

    def _close(self) -> None:
        self.game.save_now()
        self.game.scenes.pop()

    # ── 목록 ──
    def _gear_entry(self, kind: str, gid: str) -> dict:
        s = self.save
        g = s.treasure_gear(kind, gid) if s.owns_treasure(kind, gid) else next(x for x in equipment()[kind] if x["id"] == gid)
        return {"type": "gear", "kind": kind, "item": g}

    def _list(self) -> list[dict]:
        s, d = self.save, self.save.data
        if self.kind == "gear":
            out = []
            for k in GEAR_KINDS:
                for g in sorted(equipment()[k], key=lambda g: g["tier"]):
                    if s.owns(k, g["id"]):
                        out.append({"type": "gear", "kind": k, "item": g})
                for iid in d["items"]["owned"]:
                    if tr.item_info(iid)["kind"] == k:
                        out.append(self._gear_entry(k, iid))
            return out
        if self.kind == "bait":
            lst = [b for b in baits().values() if s.owns("bait", b["id"])]
            lst.sort(key=lambda b: (b.get("tier") is None, b.get("tier") or 0, b["price"]))
            return [{"type": "gear", "kind": "bait", "item": b} for b in lst]
        if self.kind == "float":
            fl = {f["id"]: f for f in load_json("floats.json")["floats"]}
            return [{"type": "float", "item": fl[i]} for i in d["float"]["owned"] if i in fl]
        if self.kind == "items":
            items = d["items"]
            out = [tr.item_info(i) for i in items["owned"] if tr.item_info(i)["kind"] not in GEAR_KINDS]
            out += [tr.item_info(i) for i, n in items["consumables"].items() if n > 0]
            order = {g: i for i, g in enumerate(tr.GRADES)}
            out.sort(key=lambda it: (order[it["grade"]], it["name"]))
            return [{"type": "treasure", "item": it} for it in out]
        # 재료
        rows = [{"type": "mat", "key": "money", "name": "돈", "n": ui.money_text(d["money"])},
                {"type": "mat", "key": "scales", "name": "전설 비늘", "n": d["scales"]},
                {"type": "mat", "key": "shards", "name": "상자 조각", "n": d["shards"]}]
        rows += [{"type": "mat", "key": "mat", "name": MAT_KO[k], "n": v} for k, v in d["materials"].items() if k in MAT_KO]
        for g in tr.GRADES:
            n = d["chests"].get(g, 0)
            if n:
                rows.append({"type": "mat", "key": "chest", "name": f"{tr.grade_info(g)['name']} 상자", "n": n,
                             "col": tuple(tr.grade_info(g)["color"])})
        rows.append({"type": "mat", "key": "keepnet", "name": "살림망 물고기", "n": len(d["keepnet"])})
        return rows

    def _name(self, e: dict) -> str:
        it = e.get("item")
        if e["type"] == "mat":
            return e["name"]
        return it["name"]

    def _equipped(self, e: dict) -> bool:
        d = self.save.data
        if e["type"] == "gear":
            return d["gear"][e["kind"]] == e["item"]["id"]
        if e["type"] == "float":
            return d["float"]["equipped"] == e["item"]["id"]
        if e["type"] == "treasure":
            it = e["item"]
            return self.save.charm_on(it["id"]) if it["kind"] == "charm" else \
                self.save.cosmetic_on(it["id"]) if it["kind"] == "cosmetic" else False
        return False

    # ── 버튼 ──
    def _state(self, e: dict) -> tuple[str, bool]:
        if e["type"] == "gear":
            return ("장착 중", False) if self._equipped(e) else ("장착하기", True)
        if e["type"] == "float":
            return ("해제", True) if self._equipped(e) else ("장착하기", True)
        if e["type"] == "treasure":
            return item_use.item_state(self.save, e["item"])
        if e["key"] == "chest":
            return "보물상자 열기", True
        if e["key"] == "keepnet":
            return ("살림망 보기", True) if e["n"] else ("비어 있음", False)
        return "", False

    def _action(self) -> None:
        items = self._list()
        if not items:
            return
        e = items[min(self.sel, len(items) - 1)]
        label, ok = self._state(e)
        if not ok:
            return
        s, sfx = self.save, self.game.sfx
        if e["type"] == "gear":
            s.equip(e["kind"], e["item"]["id"])
            sfx.play("ui_equip")
            self._say(f"{e['item']['name']} 장착", ui.GOOD)
        elif e["type"] == "float":
            fl = s.data["float"]
            fl["equipped"] = None if fl["equipped"] == e["item"]["id"] else e["item"]["id"]
            sfx.play("ui_equip")
            self._say(f"{e['item']['name']} {'장착' if fl['equipped'] else '해제'}", ui.GOOD)
        elif e["type"] == "treasure":
            msg, col, options = item_use.use(self.game, e["item"])
            if options:
                self.chooser = e["item"]["id"]
                w = (DETAIL.w - 12 - 3 * (len(options) - 1)) // len(options)
                self.choice_btns = [ui.Button((DETAIL.x + 6 + i * (w + 3), DETAIL.bottom - 42, w, 17), lab,
                                              lambda v=val: self._choose(v), size=11) for i, (lab, val) in enumerate(options)]
                return
            if msg:
                self._say(msg, col)
            sfx.play("ui_enhance", 0.8)
        elif e["key"] == "chest":
            self._close()
            self.fishing.open_menu("chest")
            return
        elif e["key"] == "keepnet":
            self._close()
            self.fishing.open_menu("shop", tab="sell")
            return
        self.game.save_now()

    def _choose(self, value) -> None:
        msg, col = item_use.choose(self.game, self.fishing, self.chooser, value)
        self._say(msg, col)
        self.chooser, self.choice_btns = None, []
        self.game.sfx.play("ui_enhance", 0.8)
        self.game.save_now()

    # ── 장비칸 ──
    def _slots(self) -> list[tuple[str, str, str | None]]:
        """(종류 탭, 칸 이름, 장착된 것 이름)."""
        s, d = self.save, self.save.data
        out = []
        for k in GEAR_KINDS:
            out.append(("gear", KIND_KO[k], s.equipped(k)["name"]))
        out.append(("bait", "미끼", s.equipped("bait")["name"]))
        fid = d["float"]["equipped"]
        fname = next((f["name"] for f in load_json("floats.json")["floats"] if f["id"] == fid), None)
        out.append(("float", "특수 찌", fname))
        for i, c in enumerate(s.charms()):
            out.append(("items", f"부적 {i + 1}", tr.item_info(c)["name"] if c else None))
        cos = d["items"].get("cosmetic")
        out.append(("items", "외형", tr.item_info(cos)["name"] if cos else None))
        return out

    def _slot_click(self, i: int) -> None:
        slots = self._slots()
        if not 0 <= i < len(slots):
            return
        tab, label, _ = slots[i]
        self.tabs.index = next(j for j, t in enumerate(TABS) if t[0] == tab)
        self.sel, self.scroll = 0, 0
        self.chooser, self.choice_btns = None, []
        items = self._list()
        for j, e in enumerate(items):   # 장착된 것을 골라 둠
            if (tab != "gear" or e["kind"] == {v: k for k, v in KIND_KO.items()}.get(label)) and self._equipped(e):
                self.sel = j
                self.scroll = max(0, j - LIST.h // ROW_H + 1)
                break
        self.game.sfx.play("ui_tab")

    # ── 입력 ──
    def handle_action(self, act) -> None:
        if act.name == "back" or act.is_("menu", "inventory"):
            self._close()
        elif act.name == "scroll":
            n = len(self._list())
            self.scroll = max(0, min(max(0, n - LIST.h // ROW_H), self.scroll - act.value))
        elif act.name == "primary":
            m = act.pos
            if self.tabs.click(m):
                self.sel, self.scroll = 0, 0
                self.chooser, self.choice_btns = None, []
                self.game.sfx.play("ui_tab")
                return
            if self.close_btn.click(m):
                return
            if self.chooser:
                for b in self.choice_btns:
                    if b.click(m):
                        return
                self.chooser, self.choice_btns = None, []
            if self.action_btn.click(m):
                return
            if EQ.collidepoint(m):
                self._slot_click((m[1] - EQ.y - 18) // EQ_ROW)
                return
            if LIST.collidepoint(m):
                i = (m[1] - LIST.y) // ROW_H + self.scroll
                if 0 <= i < len(self._list()):
                    self.sel = i
                    self.chooser, self.choice_btns = None, []
                    self.game.sfx.play("ui_click")

    def update(self, dt: float) -> None:
        self.age += dt
        self.mouse = self.ui_pointer()
        self.msg_t = max(0.0, self.msg_t - dt)

    # ── 그리기 ──
    def draw(self, canvas) -> None:
        ui.backdrop(canvas, self.fishing, int(170 * min(1.0, self.age / 0.15)), "inventory")
        canvas = self.ui_canvas(canvas)
        ui.panel(canvas, (8, 6, 464, 258))
        text(canvas, "인벤토리", (16, 16), ui.ACCENT, 16, "midleft")
        d = self.save.data
        text(canvas, f"{ui.money_text(ui.money_anim(d['money']))} · 비늘 {d['scales']} · 조각 {d['shards']}", (464, 16), ui.TEXT, 11,
             "midright")
        self.tabs.draw(canvas, self.mouse)
        self._draw_slots(canvas)
        self._draw_list(canvas)
        if self.msg_t > 0:
            text(canvas, self.msg, (EQ.x, 252), self.msg_col, 11, "midleft")
        else:
            text(canvas, "구매·강화는 상점(B) · 상자 열기는 보물상자(C)", (EQ.x, 252), ui.DIM, 11, "midleft")
        self.close_btn.draw(canvas, self.mouse)
        draw_cursor(canvas, self.mouse)

    def _draw_slots(self, canvas) -> None:
        ui.panel(canvas, EQ, fill=(16, 20, 36))
        text(canvas, "장착 중", (EQ.x + 6, EQ.y + 9), ui.ACCENT, 11, "midleft")
        for i, (tab, label, name) in enumerate(self._slots()):
            y = EQ.y + 18 + i * EQ_ROW
            r = pygame.Rect(EQ.x + 3, y, EQ.w - 6, EQ_ROW - 2)
            if r.collidepoint(self.mouse):
                canvas.fill(ui.PANEL_LIGHT, r)
            text(canvas, label, (r.x + 3, r.y + 5), ui.DIM, 11, "midleft")
            text(canvas, fit(name or "비어 있음", EQ.w - 58), (r.right - 3, r.y + 5), ui.TEXT if name else ui.DIM,
                 11, "midright")

    def _row_rect(self, i: int) -> pygame.Rect:
        return pygame.Rect(LIST.x + 2, LIST.y + 2 + (i - self.scroll) * ROW_H, LIST.w - 4, ROW_H - 1)

    def _draw_list(self, canvas) -> None:
        ui.panel(canvas, LIST, fill=(16, 20, 36))
        ui.panel(canvas, DETAIL, fill=(16, 20, 36))
        items = self._list()
        self.sel = max(0, min(self.sel, len(items) - 1)) if items else 0
        if not items:
            text(canvas, "아직 없어요", LIST.center, ui.DIM, 11, "center")
            return
        visible = LIST.h // ROW_H
        for i in range(self.scroll, min(len(items), self.scroll + visible)):
            e = items[i]
            r = self._row_rect(i)
            if i == self.sel or r.collidepoint(self.mouse):
                canvas.fill(ui.PANEL_LIGHT, r)
            col = self._color(e)
            text(canvas, fit(self._name(e), LIST.w - 40), (r.x + 4, r.centery), col, 11, "midleft")
            if e["type"] == "mat":
                status, scol = str(e["n"]), ui.TEXT
            elif self._equipped(e):
                status, scol = "장착", ui.GOOD
            elif e["type"] == "treasure" and e["item"]["kind"] == "consumable":
                status, scol = f"×{self.save.consumable_count(e['item']['id'])}", ui.TEXT
            else:
                status, scol = "", ui.DIM
            text(canvas, status, (r.right - 4, r.centery), scol, 11, "midright")
        if len(items) > visible:
            k = self.scroll / max(1, len(items) - visible)
            canvas.fill(ui.BORDER, (LIST.right - 3, LIST.y + 3 + int(k * (LIST.h - 26)), 2, 20))
        self._draw_detail(canvas, items[self.sel])

    def _color(self, e: dict):
        if e["type"] == "treasure":
            return tuple(tr.grade_info(e["item"]["grade"])["color"])
        if e["type"] == "mat":
            return e.get("col", ui.TEXT)
        if e["type"] == "gear" and e["item"].get("treasure"):
            return (255, 214, 90)
        return ui.TEXT

    def _draw_detail(self, canvas, e: dict) -> None:
        x, y, w = DETAIL.x + 6, DETAIL.y + 8, DETAIL.w - 12
        for ln in wrap_text(self._name(e), w)[:2]:
            text(canvas, ln, (x, y + 4), self._color(e), 11, "midleft")
            y += 13
        lines = []
        if e["type"] == "gear":
            from src.scene.shop import stat_lines
            text(canvas, KIND_KO[e["kind"]], (x, y + 4), ui.DIM, 11, "midleft")
            y += 15
            try:
                lines = [w2 for ln in stat_lines(e["kind"], e["item"]) for w2 in wrap_text(ln, w)]
            except (KeyError, TypeError):
                lines = []
            lines += wrap_text(e["item"].get("desc", ""), w)
        elif e["type"] == "float":
            text(canvas, f"특수 찌 · {e['item']['tier']}단계", (x, y + 4), ui.DIM, 11, "midleft")
            y += 15
            lines = wrap_text(e["item"].get("desc", ""), w)
        elif e["type"] == "treasure":
            it = e["item"]
            text(canvas, f"{tr.grade_info(it['grade'])['name']} · {KIND_KO.get(it['kind'], it['kind'])}", (x, y + 4), ui.DIM, 11,
                 "midleft")
            y += 15
            lines = wrap_text(it["desc"], w)
            for key, label in (("cost", "대가"), ("limit", "제한")):
                if it.get(key):
                    lines += wrap_text(f"{label}: {it[key]}", w)
        else:
            lines = wrap_text({"money": "물고기를 팔아 번다. 장비·미끼는 상점에서.",
                               "scales": "전설을 잡으면 얻는다. 특수 찌·전설 장비에 쓴다.",
                               "shards": "겹친 보물에서 나온다. 보물상자 → 조각 교환소.",
                               "mat": "물고기를 분해해 얻는다. 상점 → 강화에 쓴다.",
                               "chest": "물고기를 잡다 보면 나온다. 보물상자(C)에서 연다.",
                               "keepnet": "잡은 물고기. 상점 → 판매에서 팔거나 분해한다."}.get(e["key"], ""), w)
        bottom = DETAIL.bottom - (46 if self.choice_btns else 26)
        for ln in lines:
            if y + 4 > bottom:
                break
            text(canvas, ln, (x, y + 4), ui.TEXT, 11, "midleft")
            y += 13
        label, ok = self._state(e)
        if label:
            self.action_btn.label, self.action_btn.enabled = label, ok
            self.action_btn.draw(canvas, self.mouse)
        for b in self.choice_btns:
            b.draw(canvas, self.mouse)


def fit(s: str, width: int) -> str:
    """글자가 width 보다 길면 뒤를 줄이고 '…'."""
    from src.core.fonts import get_font
    f = get_font(11)
    if f.size(s)[0] <= width:
        return s
    while len(s) > 1 and f.size(s + "…")[0] > width:
        s = s[:-1]
    return s + "…"
