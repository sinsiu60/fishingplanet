"""상점: 살림망 물고기 판매·분해, 장비 구매·교체(티어별), 강화.

화면 배치는 SHOP_UI.md (목업 tools/art/reference/shop/): 동전 소지금 · 탭 구분선 · 선택 줄(노란 테두리 + 찌 커서) ·
구매 목록(장착 중 상자 장비 맨 위, 작은 장비 그림, 상태 5종) · 상세(그림 받침, 티어 배지, 능력치 비교 막대, 상태별 버튼) ·
판매 목록(필터 칩, 정렬, 두 단 줄, 같은 종 묶기, 잠금) · 일괄 판매 확인 창. 가격·판매·구매·강화·분해 계산은 SaveGame 그대로.
"""
import pygame

from src.core.config import load_json
from src.render import gear_icon
from src.render.fish_draw import RANK_COLORS, draw_fish_fit
from src.fishing.bite import bait_tier_mult
from src.save.save_game import baits, enhanced, equipment, rules
from src.fishing.mutation import label as mut_label
from src.platform.detect import IS_MOBILE
from src.scene.base import Scene
from src.ui import shop_ui as su
from src.ui import widgets as ui
from src.ui.hud import draw_cursor, text, wrap_text

TABS = [("sell", "판매"), ("rod", "낚싯대"), ("reel", "릴"), ("line", "줄"), ("net", "뜰채"), ("bait", "미끼"),
        ("float", "특수 찌"), ("enhance", "강화")]
GROUP = {"sell": 0, "rod": 1, "reel": 1, "line": 1, "net": 1, "bait": 1, "float": 1, "enhance": 2}   # 탭 구분선
KIND_KO = {"rod": "낚싯대", "reel": "릴", "line": "줄", "net": "뜰채", "bait": "미끼"}
MAT_KO = {"sharmion": "샤르미온 소재", "eldrasion": "엘드라시온 소재", "rare": "희귀 소재"}
ROW_H = 19          # 구매·강화 목록 한 줄
SELL_H = 28         # 판매 목록 한 줄 (두 단)
RARITY_COL = su.RARITY
RARITY_ORDER = {"legend": 0, "phantom": 1, "rare": 2, "uncommon": 3, "common": 4}
SORTS = [("price", "가격 높은 순"), ("rarity", "희귀도 순"), ("size", "크기 순"), ("recent", "최근 획득 순")]
FILTERS = [("all", "전체", su.WHITE), ("phantom", "환상", su.RARITY["phantom"]), ("legend", "전설", su.RARITY["legend"]),
           ("rare", "희귀", su.RARITY["rare"]), ("mut", "변이", su.MUT), ("lock", "잠금", su.GRAY)]
BULK_DEFAULT = ("common", "uncommon", "rare")   # 일괄 판매 기본 체크


def stat_lines(kind: str, item: dict) -> list[str]:
    if kind == "rod":
        lo, hi = item["green"]
        return [f"초록 구간 {lo}~{hi} (폭 {hi - lo})"]
    if kind == "reel":
        return [f"감기 속도 ×{item['speed']:.2f}", f"드랙 완충 −{item.get('drag_cushion', 0) * 100:.0f}% (돌진 때 장력)"]
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
        return [("감기 속도", item["speed"], "×{:.2f}", True), ("드랙 완충", item.get("drag_cushion", 0) * 100, "−{:.0f}%", True)]
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
    UI_FRAME = True

    def __init__(self, game, fishing, tab: str | None = None, frame=None, host=None, tabs: list[str] | None = None,
                 title: str = "상점"):
        """frame = 상점 패널 자리 (UI 상자 기준, 기본 = 화면 전체 상자). host = 건물 안 대화 화면 (35-3a):
        뒤 배경·초상화를 host 가 그리고, 사고·팔고·강화하면 host.react(종류) 로 NPC가 반응. tabs = 보일 탭 id 만 (사기/팔기/강화)."""
        super().__init__(game)
        self.fishing = fishing
        self.save = game.save
        self.host = host
        self.title = title
        self.mouse = (0, 0)
        self.age = 0.0  # 열림 애니메이션
        self.frame = pygame.Rect(frame or (8, 6, 464, 258))
        fr = self.frame
        self.wide = fr.w >= 440
        self.tab_ids = [t[0] for t in TABS if tabs is None or t[0] in tabs]
        # 판매·분해는 하루네 낚시점 안에서만. 야외(낚시터·마을)는 살림망 보기만 + 특급 배송 일괄 판매 (하루 n번)
        self.can_sell = host is not None and getattr(host, "npc", None) == "haru"
        names = dict(TABS)
        if not self.can_sell:
            names["sell"] = "살림망"
        # 탭: 같은 줄, 판매 │ 장비 6종 │ 강화 사이 세로 구분선 (목업: 위 25~42)
        seps = sum(1 for a, b in zip(self.tab_ids, self.tab_ids[1:]) if GROUP[a] != GROUP[b])
        n = len(self.tab_ids)
        tw = min(50, (fr.w - 16 - seps * 8 - (n - 1) * 2) // n)
        self.tabs = ui.Tabs(fr.x + 8, fr.y + 19, [names[t] for t in self.tab_ids], width=tw, height=17)
        x = fr.x + 8
        self.tab_seps = []
        for i, t in enumerate(self.tab_ids):
            if i and GROUP[self.tab_ids[i - 1]] != GROUP[t]:
                self.tab_seps.append(x + 2)
                x += 8
            self.tabs.rects[i] = pygame.Rect(x, fr.y + 19, tw, 17)
            x += tw + 2
        if tab and tab in self.tab_ids:
            self.tabs.index = self.tab_ids.index(tab)
        self.sel = 0
        self.scroll = 0
        self.confirm = None  # 비늘 경고를 본 장비 id (한 번 더 누르면 구매)
        self.msg, self.msg_col, self.msg_t = "", ui.TEXT, 0.0
        # 판매 탭 상태
        self.filter = "all"
        self.sort = 0
        self.expanded = None          # 펼친 묶음 (id, 변이, 잠금)
        self.chip_rects: list = []
        self.sort_rect = pygame.Rect(0, 0, 0, 0)
        self.bulk = None              # 일괄 판매 확인 창 {"rar": set}
        self.bulk_scroll = 0
        self.dscroll, self.dpages = 0, 1   # 상세 능력치·설명이 칸을 넘칠 때 넘김
        self.close_btn = ui.Button((fr.right - 66, fr.bottom - 21, 58, 16), "닫기" if host else "닫기 (B)", self._close)
        self._layout()

    def _layout(self) -> None:
        """탭마다 목록·상세 자리 (판매 탭은 칩 줄만큼 아래로)."""
        fr = self.frame
        top = fr.y + (56 if self.kind == "sell" else 42)
        bottom = fr.bottom - 26
        if self.wide:
            lw = 240
        else:
            lw = int((fr.w - 22) * 0.53)
        self.LIST = pygame.Rect(fr.x + 6, top, lw, bottom - top)
        self.DETAIL = pygame.Rect(self.LIST.right + 8, top, fr.right - 7 - (self.LIST.right + 8), bottom - top)
        D = self.DETAIL
        self.action_btn = ui.Button((D.x + 6, D.bottom - 20, D.w - 12, 16), "", self._action)
        sw = int((D.w - 12) * 0.62)
        o = self._sell_off()
        self.sell_btn = ui.Button((D.x + 6, D.y + 138 + o, sw, 16), "팔기", self._action)
        self.lock_btn = ui.Button((D.x + 10 + sw, D.y + 138 + o, D.w - 16 - sw, 16), "잠금", self._toggle_lock)
        self.dis_btn = ui.Button((D.x + 6, D.y + 158 + o, D.w - 12, 14 if self.wide else 26), "분해", self._disassemble)
        self.sell_all_btn = ui.Button((self.LIST.x, fr.bottom - 21, self.LIST.w, 16), "", self._open_bulk)

    def _sell_off(self) -> int:
        """판매 상세: 좁은 패널은 물고기 그림을 10px 줄여 분해 이유 두 줄 자리를 만든다."""
        return 0 if self.wide else -10

    # ── 데이터 ──
    @property
    def kind(self) -> str:
        return self.tab_ids[self.tabs.index]

    def items(self) -> list:
        if self.kind == "sell":
            return self.save.data["keepnet"]
        if self.kind == "bait":
            lst = [b for b in baits().values() if b["price"] >= 0 or self.save.owns("bait", b["id"])]
            return sorted(lst, key=lambda b: (b.get("tier") is None, b.get("tier") or 0, b["price"]))  # 전설 미끼는 맨 뒤
        if self.kind == "float":
            return load_json("floats.json")["floats"]
        if self.kind == "enhance":
            out = []
            for k in rules()["enhance_kinds"]:
                for g in sorted(equipment()[k], key=lambda g: g["tier"]):
                    if self.save.owns(k, g["id"]):
                        out.append((k, g))
            out.append(("delivery", {"id": "delivery", "name": "특급 배송 시스템", "tier": 0}))   # 야외 일괄 판매 (하루 n번)
            return out
        return sorted(equipment()[self.kind], key=lambda g: g["tier"])

    def _extra(self) -> dict | None:
        """지금 장착한 장비가 상점 티어 목록에 없으면(상자 장비) 그 장비 — 목록 맨 위 따로 한 줄."""
        if self.kind not in ("rod", "reel", "line", "net"):
            return None
        cur = self.save.equipped(self.kind)
        return cur if all(g["id"] != cur["id"] for g in equipment()[self.kind]) else None

    def _rows(self) -> list:
        """화면 줄 (선택 sel 의 기준). 구매: [상자 장비?] + 티어 목록. 판매: 묶음/한 마리 줄."""
        if self.kind == "sell":
            return self._sell_rows()
        ex = self._extra()
        return ([ex] if ex else []) + self.items()

    def fish_by_id(self, fid: str) -> dict:
        from src.save.save_game import fish_by_id
        return fish_by_id(fid)  # 환상어(data/phantom.json)도

    def _say(self, msg: str, col=ui.TEXT) -> None:
        self.msg, self.msg_col, self.msg_t = msg, col, 2.0
        if col == ui.BAD:
            self.game.sfx.play("ui_error")  # 안 됨 (돈·소재 부족 등)
            if self.host is not None and ("돈" in msg):
                self.host.react("short")

    def _react(self, kind: str) -> None:
        if self.host is not None:
            self.host.react(kind)   # 건물 안: NPC 웃음 표정 + 짧은 반응 대사

    # ── 판매 목록 (필터 · 정렬 · 묶기) ──
    def _pass(self, it: dict, key: str) -> bool:
        if key == "all":
            return True
        if key == "mut":
            return bool(it.get("mut"))
        if key == "lock":
            return bool(it.get("lock"))
        return self.fish_by_id(it["id"])["rarity"] == key

    def _sort_key(self, i: int, it: dict):
        mode = SORTS[self.sort][0]
        if mode == "price":
            return -self.save.sale_price(it)
        if mode == "rarity":
            return (RARITY_ORDER.get(self.fish_by_id(it["id"])["rarity"], 9), -self.save.sale_price(it))
        if mode == "size":
            return -it["size"]
        return -i   # 최근 획득 = 살림망 뒤쪽

    def _sell_rows(self) -> list:
        """[{"idxs": [살림망 번호…], "group": bool}] — 같은 종(변이·잠금 같음)은 한 줄 '이름 ×n', 펼친 묶음은 한 마리씩."""
        net = self.save.data["keepnet"]
        idxs = [i for i, it in enumerate(net) if self._pass(it, self.filter)]
        idxs.sort(key=lambda i: self._sort_key(i, net[i]))
        groups: dict = {}
        order = []
        for i in idxs:
            it = net[i]
            k = (it["id"], tuple(it.get("mut") or ()), bool(it.get("lock")))
            if k not in groups:
                groups[k] = []
                order.append(k)
            groups[k].append(i)
        rows = []
        for k in order:
            g = groups[k]
            if len(g) > 1 and k != self.expanded:
                rows.append({"idxs": g, "group": True, "key": k})
            else:
                rows += [{"idxs": [i], "group": False, "key": k, "member": len(g) > 1} for i in g]
        return rows

    def _sel_index(self) -> int | None:
        """판매 탭: 선택한 줄의 살림망 번호 (묶음이면 맨 앞 = 정렬상 첫째)."""
        rows = self._sell_rows()
        if not rows:
            return None
        return rows[max(0, min(self.sel, len(rows) - 1))]["idxs"][0]

    def _select(self, i: int) -> None:
        """줄 고르기 (판매 묶음 줄이면 펼쳐서 첫 마리)."""
        rows = self._rows()
        if not rows:
            self.sel = 0
            return
        self.sel = max(0, min(i, len(rows) - 1))
        if self.kind == "sell":
            r = rows[self.sel]
            if r["group"]:
                self.expanded = r["key"]
            elif not r.get("member"):
                self.expanded = None
            rows = self._rows()
            self.sel = next((j for j, x in enumerate(rows) if x["idxs"][0] == r["idxs"][0]), 0)
        vis = self._visible()
        if self.sel < self.scroll + self._pinned():
            self.scroll = max(0, self.sel - self._pinned())
        elif self.sel >= self.scroll + vis + self._pinned():
            self.scroll = self.sel - vis - self._pinned() + 1

    def _rh(self) -> int:
        """구매·강화 한 줄 높이: 넓으면 한 단(19), 좁은 패널(건물 안)은 이름이 잘리지 않게 두 단(27)."""
        return ROW_H if self.wide else 27

    def _pinned(self) -> int:
        return 1 if self.kind != "sell" and self._extra() else 0

    def _visible(self) -> int:
        """스크롤되는 줄 수 (고정 줄·아래 요약 줄 빼고)."""
        if self.kind == "sell":
            return (self.LIST.h - 4) // SELL_H
        h = self.LIST.h - 2 - 14 - self._rh() * self._pinned()
        return h // self._rh()

    # ── 동작 ──
    def _close(self) -> None:
        self.game.save_now()
        self.game.scenes.pop()
        if self.host is not None:
            self.host.shop_closed()

    def _action(self) -> None:
        if self.kind == "sell":
            idx = self._sel_index()
            if idx is None:
                return
            if not self.can_sell:
                self._say("판매는 하루네 낚시점에서 할 수 있어요", ui.BAD)
                return
            gained = self.save.sell(idx)
            self.game.sfx.play("sfx_coin")
            self._react("sell")
            self._say(f"+{ui.money_text(gained)}", ui.GOOD)
            self.sel = max(0, min(self.sel, len(self._rows()) - 1))
            return
        rows = self._rows()
        if not rows:
            return
        item = rows[min(self.sel, len(rows) - 1)]
        if self.kind == "float":
            fl = self.save.data["float"]
            if item["id"] in fl["owned"]:
                fl["equipped"] = item["id"]
                self.game.sfx.play("ui_equip")
                self._say(f"{item['name']} 장착", ui.GOOD)
                return
            res = self.save.buy_float(item)
            msg = {"ok": (f"{item['name']} 구매 · 장착!", ui.GOOD), "money": ("돈이 부족해요", ui.BAD),
                   "scales": ("전설 비늘이 부족해요", ui.BAD), "locked": ("엘드라시온 대륙에서 판매", ui.BAD)}.get(res)
            if res == "ok":
                self.game.sfx.play("ui_buy")
                self._react("buy")
            if msg:
                self._say(*msg)
            return
        if self.kind == "enhance":
            kind, gear = item
            if kind == "delivery":
                from src.save import delivery
                lv = delivery.level(self.save)
                res = delivery.upgrade(self.save)
                if res == "ok":
                    self.game.sfx.play("ui_buy" if lv == 0 else "ui_enhance")
                    self._react("buy" if lv == 0 else "enhance")
                    self._say(f"특급 배송 {'구매' if lv == 0 else '강화'}! 야외 판매 하루 {lv + 1}번", ui.GOOD)
                elif res == "money":
                    self._say("돈이 부족해요", ui.BAD)
                return
            res = self.save.enhance(kind, gear)
            if res == "ok":
                self.game.sfx.play("ui_enhance")
                self._react("enhance")
                self._say(f"{gear['name']} +{self.save.enhance_level(gear['id'])} 강화 성공!", ui.GOOD)
            elif res == "money":
                self._say("돈이 부족해요", ui.BAD)
            elif res == "materials":
                self._say("소재가 부족해요 (판매 탭에서 물고기 분해)", ui.BAD)
            return
        if self.save.owns(self.kind, item["id"]):
            if self.save.data["gear"][self.kind] == item["id"]:
                return
            self.save.equip(self.kind, item["id"])
            self.game.sfx.play("ui_equip")
            self._say(f"{item['name']} 장착", ui.GOOD)
            return
        need = self.save.scale_warning(item)
        if need and self.confirm != item["id"]:
            # 비늘을 써 버리면 다음 특수 찌를 못 살 수 있다 → 한 번 경고하고 다시 누르면 구매
            self.confirm = item["id"]
            self._say(f"특수 찌용 비늘이 모자라져요 (필요 {need}개) · 다시 누르면 구매", ui.BAD)
            self.msg_t = 4.0
            return
        self.confirm = None
        result = self.save.buy(self.kind, item)
        if result == "ok":
            self.game.sfx.play("ui_buy")
            self._react("buy")
            self._say(f"{item['name']} 구매 · 장착!", ui.GOOD)
        elif result == "money":
            self._say("돈이 부족해요", ui.BAD)
        elif result == "scales":
            self._say("전설 비늘이 부족해요", ui.BAD)
        elif result == "locked":
            self._say(self.save.gear_locked_reason(item) or self.save.bait_locked_reason(item), ui.BAD)

    def _disassemble(self) -> None:
        idx = self._sel_index()
        if idx is None:
            return
        if not self.can_sell:
            self._say("분해는 하루네 낚시점에서 할 수 있어요", ui.BAD)
            return
        got = self.save.disassemble(idx)
        if got is None:
            self._say(self._no_dis_reason(idx), ui.BAD)
            return
        self.game.sfx.play("ui_click")
        self._say("분해: " + ", ".join(f"{MAT_KO[k]} +{v}" for k, v in got.items()), ui.GOOD)
        self.sel = max(0, min(self.sel, len(self._rows()) - 1))

    def _no_dis_reason(self, idx: int) -> str:
        rar = self.fish_by_id(self.save.data["keepnet"][idx]["id"])["rarity"]
        return f"{su.RARITY_KO.get(rar, '이')} 물고기는 분해할 수 없어요"

    def _toggle_lock(self) -> None:
        idx = self._sel_index()
        if idx is None:
            return
        it = self.save.data["keepnet"][idx]
        it["lock"] = not it.get("lock")
        self.game.sfx.play("ui_click")
        key = (it["id"], tuple(it.get("mut") or ()), bool(it["lock"]))
        self.expanded = key
        rows = self._rows()
        self.sel = next((j for j, r in enumerate(rows) if idx in r["idxs"]), 0)
        self._say("잠금 · 일괄 판매에서 빠져요" if it["lock"] else "잠금 해제", ui.TEXT)

    def _sell_all(self) -> None:
        """(호환) 잠금 제외 전부 팔기."""
        self.bulk = {"rar": set(RARITY_ORDER)}
        self._bulk_confirm()

    # ── 일괄 판매 확인 창 ──
    def _open_bulk(self) -> None:
        from src.save import delivery
        if not self.can_sell:
            if delivery.level(self.save) == 0:
                self._say("특급 배송 시스템이 있으면 여기서도 팔 수 있어요 (하루네 낚시점 강화 탭)", ui.BAD)
                return
            if delivery.uses_left(self.save) <= 0:
                self._say("오늘 특급 배송을 다 썼어요 · 내일 다시", ui.BAD)
                return
        if not self._bulk_pool():
            self._say("잠금 제외 팔 물고기가 없어요", ui.BAD)
            return
        self.bulk = {"rar": set(BULK_DEFAULT)}
        self.bulk_scroll = 0
        self.game.sfx.play("ui_click")

    def _bulk_pool(self) -> list[dict]:
        return [it for it in self.save.data["keepnet"] if not it.get("lock")]

    def _bulk_items(self) -> list[dict]:
        rar = self.bulk["rar"] if self.bulk else set()
        return [it for it in self._bulk_pool() if self.fish_by_id(it["id"])["rarity"] in rar]

    def _bulk_confirm(self) -> None:
        todo = self._bulk_items()
        if not todo:
            self.bulk = None
            return
        net = self.save.data["keepnet"]
        total = 0
        if not self.can_sell:
            from src.save import delivery
            delivery.use(self.save)   # 특급 배송 1회
        for it in todo:   # 살림망 순서대로 한 마리씩 (판매가·전설 감가는 save.sell 그대로)
            idx = next(i for i, x in enumerate(net) if x is it)
            total += self.save.sell(idx)
        self.bulk = None
        self.sel = 0
        self.expanded = None
        self.game.sfx.play("sfx_coin")
        self._react("sell")
        self._say(f"{len(todo)}마리 팔았어요 +{ui.money_text(total)}", ui.GOOD)

    def _bulk_rects(self):
        fr = self.frame
        w, h = min(300, fr.w - 20), 196
        P = pygame.Rect(0, 0, w, h)
        P.center = fr.center
        checks = []
        x = P.x + 10
        for r in ("common", "uncommon", "rare", "phantom", "legend"):
            tw = su.width(su.RARITY_KO[r]) + 14
            checks.append((r, pygame.Rect(x, P.y + 24, tw, 13)))
            x += tw + 6
        lst = pygame.Rect(P.x + 8, P.y + 42, P.w - 16, P.h - 86)
        ok = pygame.Rect(P.right - 140, P.bottom - 22, 64, 16)
        cancel = pygame.Rect(P.right - 70, P.bottom - 22, 62, 16)
        return P, checks, lst, ok, cancel

    def _bulk_click(self, m) -> None:
        P, checks, lst, ok, cancel = self._bulk_rects()
        for r, rc in checks:
            if rc.collidepoint(m):
                self.bulk["rar"] ^= {r}
                self.bulk_scroll = 0
                self.game.sfx.play("ui_click")
                return
        if ok.collidepoint(m) and self._bulk_items():
            self._bulk_confirm()
        elif cancel.collidepoint(m) or not P.collidepoint(m):
            self.bulk = None
            self.game.sfx.play("ui_click")

    # ── 입력 ──
    def handle_event(self, event) -> None:
        if event.type == pygame.KEYDOWN and self.bulk is None:
            if event.key in (pygame.K_UP, pygame.K_DOWN, pygame.K_w, pygame.K_s):
                d = -1 if event.key in (pygame.K_UP, pygame.K_w) else 1
                self._select(self.sel + d)
                self.game.sfx.play("ui_click")
                return
            if event.key == pygame.K_l and self.kind == "sell":
                self._toggle_lock()
                return
        if event.type == pygame.KEYDOWN and self.bulk is not None and event.key == pygame.K_RETURN:
            self._bulk_confirm()
            return
        super().handle_event(event)

    def handle_action(self, a) -> None:
        if self.bulk is not None:
            if a.name == "back" or a.is_("menu", "shop"):
                self.bulk = None
            elif a.name == "scroll":
                n = len(self._bulk_lines())
                vis = (self._bulk_rects()[2].h - 4) // 13
                self.bulk_scroll = max(0, min(max(0, n - vis), self.bulk_scroll - a.value))
            elif a.name == "primary":
                self._bulk_click(a.pos)
            return
        if a.name == "back" or a.is_("menu", "shop"):
            self._close()
        elif a.name == "confirm":
            self._action()
        elif a.name == "scroll":
            if self.kind != "sell" and self.DETAIL.collidepoint(self.mouse):
                self.dscroll = max(0, min(self.dpages - 1, self.dscroll - a.value))
                return
            n = len(self._rows()) - self._pinned()
            self.scroll = max(0, min(max(0, n - self._visible()), self.scroll - a.value))
        elif a.name == "primary":
            m = a.pos
            if self.tabs.click(m):
                self.sel, self.scroll, self.expanded = 0, 0, None
                self._layout()
                self.game.sfx.play("ui_tab")
                return
            if self.kind == "sell":
                for key, r in self.chip_rects:
                    if r.collidepoint(m):
                        self.filter, self.sel, self.scroll, self.expanded = key, 0, 0, None
                        self.game.sfx.play("ui_tab")
                        return
                if self.sort_rect.collidepoint(m):
                    self.sort = (self.sort + 1) % len(SORTS)
                    self.sel, self.scroll = 0, 0
                    self.game.sfx.play("ui_click")
                    return
            buttons = (self.close_btn, self.sell_btn, self.lock_btn, self.dis_btn, self.sell_all_btn) \
                if self.kind == "sell" else (self.close_btn, self.action_btn)
            for b in buttons:
                if b.click(m):
                    return
            if self.kind != "sell" and self.dpages > 1 and self._info_area().collidepoint(m):
                self.dscroll = (self.dscroll + 1) % self.dpages   # 능력치 넘기기
                self.game.sfx.play("ui_click")
                return
            if self.LIST.collidepoint(m):
                i = self._row_at(m)
                if i is not None and i < len(self._rows()):
                    self._select(i)
                    self.game.sfx.play("ui_click")

    def _row_at(self, m) -> int | None:
        for i in range(len(self._rows())):
            r = self._row_rect(i)
            if r is not None and r.collidepoint(m):
                return i
        return None

    def update(self, dt: float) -> None:
        if self.host is not None:
            self.host.update(dt)   # 건물 안: 초상화 깜빡임·숨쉬기 계속
        self.age += dt
        self.mouse = self.ui_pointer()
        self.msg_t = max(0.0, self.msg_t - dt)

    # ── 그리기 ──
    def draw(self, canvas) -> None:
        if self.host is not None:
            self.host.draw_shop_backdrop(canvas)   # 건물 안: 배경 + 왼쪽 초상화 + 반응 대사
        else:
            self.fishing.draw(canvas)
            ui.dim(canvas, int(170 * min(1.0, self.age / 0.15)))
        canvas = self.ui_canvas(canvas)
        fr = self.frame
        canvas.fill(ui.SHADOW, fr.move(2, 2))
        canvas.fill(su.WIN_BG, fr)
        pygame.draw.rect(canvas, su.BORDER, fr, 1)
        text(canvas, su.fit(self.title, fr.w - 110, 16), (fr.x + 8, fr.y + 9), ui.ACCENT, 16, "midleft")
        su.price(canvas, self.save.money, (fr.right - 9, fr.y + 9), su.YELLOW, bold=True, big=True)
        self._draw_tabs(canvas)
        for r in (self.LIST, self.DETAIL):
            canvas.fill(su.CELL_BG, r)
            pygame.draw.rect(canvas, su.BORDER, r, 1)
        rows = self._rows()
        self.sel = max(0, min(self.sel, len(rows) - 1)) if rows else 0
        if self.kind == "sell":
            self._draw_sell(canvas, rows)
        elif self.kind == "enhance":
            self._draw_enhance(canvas, rows)
        else:
            self._draw_buy(canvas, rows)
        self._draw_bottom(canvas)
        self.close_btn.draw(canvas, self.mouse)
        if self.bulk is not None:
            self._draw_bulk(canvas)
        draw_cursor(canvas, self.mouse)

    def _draw_tabs(self, canvas) -> None:
        for i, (r, label) in enumerate(zip(self.tabs.rects, self.tabs.labels)):
            sel = i == self.tabs.index
            hov = r.collidepoint(self.mouse)
            canvas.fill(su.SEL_BG if sel or hov else su.CELL_BG, r)
            pygame.draw.rect(canvas, su.YELLOW if sel else su.BORDER, r, 1)
            if sel:
                su.btext(canvas, label, r.center, su.YELLOW, 11, "center")
            else:
                text(canvas, label, r.center, su.WHITE if hov else su.GRAY, 11, "center")
        for x in self.tab_seps:
            canvas.fill(su.BORDER, (x, self.tabs.rects[0].y + 3, 1, 11))

    def _draw_bottom(self, canvas) -> None:
        fr = self.frame
        y = fr.bottom - 13
        if self.kind == "sell":
            gap = pygame.Rect(self.LIST.right + 6, y - 6, self.close_btn.rect.x - self.LIST.right - 12, 12)
            if self.msg_t > 0 and gap.w > 30:
                text(canvas, su.fit(self.msg, gap.w), (gap.x, y), self.msg_col, 11, "midleft")
            return
        if self.msg_t > 0:
            text(canvas, su.fit(self.msg, self.close_btn.rect.x - fr.x - 16), (fr.x + 8, y), self.msg_col, 11, "midleft")
        elif not IS_MOBILE:
            verb = "강화" if self.kind == "enhance" else "구매"
            text(canvas, f"↑↓ 선택   Enter {verb}   {'Esc' if self.host else 'B'} 닫기", (fr.x + 8, y), su.SUB, 11,
                 "midleft")

    def _row_rect(self, i: int) -> pygame.Rect | None:
        """i 번째 줄 자리 (화면 밖이면 None). 구매: 고정 줄(상자 장비) + 스크롤 줄."""
        L = self.LIST
        if self.kind == "sell":
            j = i - self.scroll
            if not 0 <= j < self._visible():
                return None
            return pygame.Rect(L.x + 2, L.y + 2 + j * SELL_H, L.w - 8, SELL_H - 1)
        p = self._pinned()
        rh = self._rh()
        if i < p:
            return pygame.Rect(L.x + 2, L.y + 2, L.w - 4, rh - 1)
        j = i - p - self.scroll
        if not 0 <= j < self._visible():
            return None
        return pygame.Rect(L.x + 2, L.y + 2 + p * rh + j * rh, L.w - 4, rh - 1)

    # ── 구매 탭 ──
    def _gear_state(self, it: dict) -> str:
        """equipped · owned · buy · short · locked"""
        kind = self.kind
        if kind == "float":
            fl = self.save.data["float"]
            if fl.get("equipped") == it["id"]:
                return "equipped"
            if it["id"] in fl["owned"]:
                return "owned"
            if "eldrasion" not in self.save.data["unlocked_continents"]:
                return "locked"
        else:
            if self.save.data["gear"][kind] == it["id"]:
                return "equipped"
            if self.save.owns(kind, it["id"]):
                return "owned"
            if self.save.gear_locked_reason(it) or (kind == "bait" and self.save.bait_locked_reason(it)):
                return "locked"
        return "buy" if self.save.money >= it["price"] else "short"

    def _locked_label(self, it: dict) -> str:
        if self.kind == "float" or self.save.gear_locked_reason(it):
            return "엘드라시온"
        return "잠김"

    def _tier_label(self, it: dict) -> str:
        if self.kind == "float":
            return f"S{it['tier']}"
        return f"T{it['tier']}" if it.get("tier") else "전설"

    def _draw_buy(self, canvas, rows) -> None:
        L = self.LIST
        kind = self.kind
        ex = self._extra()
        hl = kind == "float" and self.save.data["flags"].get("float_highlight")
        counts = {"owned": 0, "buy": 0, "locked": 0}
        for i, it in enumerate(rows):
            st = "equipped" if (ex is not None and i == 0) else self._gear_state(it)
            counts["owned"] += st in ("owned", "equipped")
            counts["buy"] += st == "buy"
            counts["locked"] += st == "locked"
            r = self._row_rect(i)
            if r is None:
                continue
            su.row_bg(canvas, r, i == self.sel, r.collidepoint(self.mouse))
            if hl and it.get("tier") == 1 and int(self.age * 4) % 2 == 0:
                pygame.draw.rect(canvas, (255, 230, 120), r, 1)  # 튜토리얼: 마비 찌 반짝임
            locked = st == "locked"
            cy = r.centery
            # 두 단(좁은 패널): 위 = 이름, 아래 = 상태 / 한 단: 이름 · 상태 같은 줄
            ny, sy = (r.y + 8, r.y + 19) if not self.wide else (cy, cy)
            ty = cy if self.wide else ny
            if ex is not None and i == 0:   # 장착 중인 상자 장비: 티어 자리에 청록 ★
                pygame.draw.polygon(canvas, su.CYAN, _star(r.x + 15, ty, 5))
            else:
                su.btext(canvas, self._tier_label(it), (r.x + 9, ty), su.GRAY if locked else su.YELLOW, 11, "midleft")
            icy = cy if self.wide else sy
            gear_icon.draw(canvas, kind, it, (r.x + 30, icy - 7, 14, 14), dark=locked)
            right = r.right - 4
            if st == "equipped":
                sx = su.badge(canvas, "장착 중", (right, sy), su.GREEN).x
            elif st == "owned":
                sx = right - su.width("보유") - 9
                su.check(canvas, sx, sy)
                text(canvas, "보유", (right, sy), su.WHITE, 11, "midright")
            elif locked:
                lab = self._locked_label(it)
                sx = right - su.width(lab) - 9
                su.lock(canvas, sx, sy)
                text(canvas, lab, (right, sy), su.GRAY, 11, "midright")
            else:
                sx = su.price(canvas, it["price"], (right, sy), su.WHITE if st == "buy" else su.RED).x
            lvl = self.save.enhance_level(it["id"]) if st in ("owned", "equipped") and kind != "float" else 0
            nx = r.x + 46 if self.wide else r.x + 30
            nw = (sx - nx - 2) if self.wide else (r.right - 4 - nx)
            name = it["name"]
            if lvl and self.wide:   # 강화 단계: 넓으면 이름 뒤 (자리가 모자라면 붙여서)
                name = f"{name} +{lvl}" if su.width(f"{name} +{lvl}") <= nw else f"{name}+{lvl}"
            elif lvl:               # 좁은 패널: 아래 단 그림 옆
                su.btext(canvas, f"+{lvl}", (r.x + 47, sy), su.YELLOW, 11, "midleft")
            text(canvas, su.fit(name, nw), (nx, ny), su.GRAY if locked else su.WHITE, 11, "midleft")
            if ex is not None and i == 0:
                canvas.fill(su.BORDER, (L.x + 6, r.bottom, L.w - 12, 1))
        n = len(rows) - self._pinned()
        if n > self._visible():   # 스크롤 막대
            self._scrollbar(canvas, n, self._visible(), L.y + 2 + self._pinned() * self._rh(), L.bottom - 16)
        summary = f"보유 {counts['owned']} · 구매 가능 {counts['buy']} · 잠김 {counts['locked']}"
        text(canvas, su.fit(summary, L.w - 12), (L.x + 6, L.bottom - 8), su.SUB, 11, "midleft")
        if rows:
            self._draw_buy_detail(canvas, rows[self.sel], ex is not None and self.sel == 0)

    def _scrollbar(self, canvas, n: int, vis: int, y0: int, y1: int) -> None:
        x = self.LIST.right - 4
        canvas.fill((30, 36, 58), (x, y0, 2, y1 - y0))
        h = max(8, (y1 - y0) * vis // n)
        y = y0 + (y1 - y0 - h) * self.scroll // max(1, n - vis)
        canvas.fill(su.BORDER, (x, y, 2, h))

    # 상세 세로 자리 (목업 기준, 상세 칸 위 = 0): 그림 6~76 · 이름 88 · 설명 104 · 능력치 116~(아래-34) · 가격 아래-26 · 버튼 아래-20
    INFO_TOP = 116

    def _info_area(self) -> pygame.Rect:
        D = self.DETAIL
        return pygame.Rect(D.x + 6, D.y + self.INFO_TOP, D.w - 12, D.bottom - 34 - (D.y + self.INFO_TOP))

    def _draw_buy_detail(self, canvas, it: dict, is_extra: bool) -> None:
        D = self.DETAIL
        kind = self.kind
        st = "equipped" if is_extra else self._gear_state(it)
        x = D.x + 6
        if getattr(self, "_detail_of", None) != (kind, it["id"]):
            self._detail_of, self.dscroll = (kind, it["id"]), 0
        box = pygame.Rect(D.x + 6, D.y + 6, D.w - 12, 70)
        su.pic_box(canvas, box)
        gear_icon.draw(canvas, kind, it, (box.centerx - 32, box.centery - 32, 64, 64), dark=st == "locked")
        # 이름 + 티어 배지
        tier = "★" if is_extra else self._tier_label(it)
        br = su.badge(canvas, tier, (D.right - 6, D.y + 88), su.YELLOW, bold=True)
        lvl = self.save.enhance_level(it["id"]) if st in ("owned", "equipped") and kind != "float" else 0
        name = it["name"] + (f" +{lvl}" if lvl else "")
        ncol = tuple(it["color"]) if kind == "float" and st != "locked" else su.YELLOW
        su.btext(canvas, su.fit(name, br.x - x - 6), (x, D.y + 88), ncol, 11, "midleft")
        # 설명 한 줄 (주의할 것이 있으면 그 자리에: 잠김 이유 · 비늘)
        warn = None
        if st == "locked":
            reason = (self.save.gear_locked_reason(it) or (kind == "bait" and self.save.bait_locked_reason(it))
                      or "엘드라시온 대륙에서 판매")
            warn = (reason, su.RED)
        elif st in ("buy", "short"):
            need = self.save.scale_warning(it) if kind != "float" else 0
            if need:
                warn = (f"주의: 남은 특수 찌에 비늘 {need}개 필요", su.RED)
            elif it.get("scales"):
                have = self.save.data["scales"]
                warn = (f"전설 비늘 {it['scales']}개 필요 (보유 {have})", su.WHITE if have >= it["scales"] else su.RED)
        desc, dcol = warn if warn else (it["desc"], su.GRAY)
        text(canvas, su.fit(desc, D.w - 12), (x, D.y + 104), dcol, 11, "midleft")
        # 능력치 (장비) / 설명 줄 (미끼·특수 찌) — 칸을 넘치면 휠·클릭으로 넘김
        area = self._info_area()
        if kind in ("rod", "reel", "line", "net"):
            self._draw_compare(canvas, it, area)
        else:
            if kind == "bait":
                lines = [w for ln in stat_lines(kind, it) for w in wrap_text(ln, area.w - 14)]
            else:   # 특수 찌: 쓸 수 있는 곳
                spots = [s for s in load_json("spots.json")["spots"] if s.get("continent") == "eldrasion"]
                ok = [s["short"] for s in spots if s.get("float_req", 9) <= it["tier"]]
                lines = wrap_text("쓸 수 있는 곳: " + (", ".join(ok) if ok else "-"), area.w - 14)
                lines.append("전설은 한 단계 위 찌가 필요해요")
            per = area.h // 13
            self.dpages = max(1, len(lines) - per + 1)
            self.dscroll = min(self.dscroll, self.dpages - 1)
            for j, ln in enumerate(lines[self.dscroll:self.dscroll + per]):
                text(canvas, ln, (x, area.y + 6 + j * 13), su.SUB if ln.startswith("전설은") else su.WHITE, 11, "midleft")
            if len(lines) > per:
                self._more_arrows(canvas, area, self.dscroll > 0, self.dscroll < self.dpages - 1)
        # 가격 + 구매 후
        py = D.bottom - 26
        if st in ("buy", "short", "locked"):
            pr = su.price(canvas, it["price"], (x, py), su.WHITE if st == "buy" else (su.RED if st == "short" else su.GRAY),
                          anchor="midleft", bold=True, big=True)
            after = f"구매 후 {self.save.money - it['price']:,}원"
            if st == "buy" and pr.right + 6 + su.width(after) <= D.right - 6:
                text(canvas, after, (D.right - 6, py), su.SUB, 11, "midright")
        # 상태별 버튼
        b = self.action_btn
        scales_ok = self.save.data["scales"] >= it.get("scales", 0)
        if st == "equipped":
            b.label, b.enabled, style = "장착 중", False, "dim"
        elif st == "owned":
            b.label, b.enabled, style = "장착하기", True, "outline"
        elif st == "locked":
            b.label, b.enabled, style = ("엘드라시온에서 해금" if self._locked_label(it) == "엘드라시온" else "잠김"), False, "dim"
        elif st == "short":
            b.label, b.enabled, style = f"소지금이 {it['price'] - self.save.money:,}원 부족해요", False, "dim"
        elif not scales_ok:
            b.label, b.enabled, style = "전설 비늘이 부족해요", False, "dim"
        else:
            b.label, b.enabled, style = ("그래도 구매" if self.confirm == it["id"] else "구매하기"), True, "fill"
        if self.confirm and self.confirm != it["id"]:
            self.confirm = None
        label = b.label if su.width(b.label) <= b.rect.w - 6 else b.label.replace("소지금이 ", "")
        su.button(canvas, b.rect, su.fit(label, b.rect.w - 6), style, self.mouse)

    def _more_arrows(self, canvas, area: pygame.Rect, up: bool, down: bool) -> None:
        """칸을 넘칠 때 오른쪽 위·아래 작은 화살표 (휠·클릭으로 넘김)."""
        x = area.right - 5
        if up:
            pygame.draw.polygon(canvas, su.GRAY, [(x - 3, area.y + 4), (x + 3, area.y + 4), (x, area.y + 1)])
        if down:
            y = area.bottom - 3
            pygame.draw.polygon(canvas, su.YELLOW, [(x - 3, y - 3), (x + 3, y - 3), (x, y)])

    def _draw_compare(self, canvas, it: dict, area: pygame.Rect) -> None:
        """능력치 비교 (능력치마다): 이름 · 선택 장비 수치(굵게) · 차이(▲초록/▼빨강) ·
        막대 2개(선택 = 노랑 굵게, 지금 = 회색 얇게, 같은 기준) · '지금 n · 이름'. 칸에 하나씩, 넘치면 휠·클릭."""
        kind = self.kind
        x = area.x
        cur = self.save.equipped(kind)
        mine = self.save.effective(kind, it)
        now = self.save.effective(kind, cur)
        same = it["id"] == cur["id"]
        allv: dict = {}
        for g in equipment()[kind] + [cur, it]:
            for label, v, _, _ in stat_rows(kind, self.save.effective(kind, g)):
                allv[label] = max(allv.get(label, 0), abs(v))
        pairs = list(zip(stat_rows(kind, mine), stat_rows(kind, now)))[:3]
        per = max(1, area.h // 34)
        self.dpages = max(1, len(pairs) - per + 1)
        self.dscroll = min(self.dscroll, self.dpages - 1)
        for j, ((label, v, fmt, up), (_, v0, _, _)) in enumerate(pairs[self.dscroll:self.dscroll + per]):
            yy = area.y + 6 + j * 34
            text(canvas, label, (x, yy), su.WHITE, 11, "midleft")
            d = v - v0
            dx = area.right
            if not same and abs(d) > 1e-6:
                good = (d > 0) == up
                col = su.GREEN if good else su.RED
                dtxt = ("+" if d > 0 else "-") + fmt.format(abs(d)).lstrip("×±−")
                r = su.btext(canvas, dtxt, (dx, yy), col, 11, "midright")
                ax = r.x - 8
                if d > 0:
                    pygame.draw.polygon(canvas, col, [(ax, yy + 2), (ax + 6, yy + 2), (ax + 3, yy - 2)])
                else:
                    pygame.draw.polygon(canvas, col, [(ax, yy - 2), (ax + 6, yy - 2), (ax + 3, yy + 2)])
                dx = ax - 6
            su.btext(canvas, fmt.format(v), (dx, yy), su.WHITE, 11, "midright")
            full = max(1e-6, allv.get(label, 1.0))
            bw = area.w
            canvas.fill((30, 36, 58), (x, yy + 7, bw, 4))
            canvas.fill(su.YELLOW, (x, yy + 7, int(bw * min(1.0, abs(v) / full)), 4))
            canvas.fill((30, 36, 58), (x, yy + 12, bw, 2))
            canvas.fill(su.GRAY, (x, yy + 12, int(bw * min(1.0, abs(v0) / full)), 2))
            pages = f"{self.dscroll + 1}/{self.dpages}" if self.dpages > 1 else ""
            pw = su.width(pages) + 4 if pages else 0
            text(canvas, su.fit(f"지금 {fmt.format(v0)} · {cur['name']}", area.w - pw), (x, yy + 22), su.SUB, 11, "midleft")
            if pages:
                text(canvas, pages, (area.right, yy + 22), su.YELLOW, 11, "midright")

    # ── 판매 탭 ──
    def _draw_sell(self, canvas, rows) -> None:
        L, D = self.LIST, self.DETAIL
        net = self.save.data["keepnet"]
        # 필터 칩 + 정렬
        fr = self.frame
        cy = L.y - 7
        sort_s = f"정렬: {SORTS[self.sort][1]}"
        sw = su.width(sort_s) + 10
        self.sort_rect = pygame.Rect(fr.right - 8 - sw, cy - 6, sw, 12)
        text(canvas, sort_s, (self.sort_rect.x, cy), su.WHITE if self.sort_rect.collidepoint(self.mouse) else su.GRAY, 11,
             "midleft")
        ax = self.sort_rect.right - 6
        pygame.draw.polygon(canvas, su.GRAY, [(ax, cy - 2), (ax + 5, cy - 2), (ax + 2, cy + 2)])
        self.chip_rects = []
        x = L.x
        for key, lab, col in FILTERS:
            n = sum(1 for it in net if self._pass(it, key))
            if n == 0 and key != "all":
                continue
            s = f"{lab}{n}"
            if x + su.width(s) + 4 > self.sort_rect.x - 4:
                break
            r = su.chip(canvas, s, x, cy, col, self.filter == key)
            self.chip_rects.append((key, r))
            x = r.right + 3
        if self.filter != "all" and all(k != self.filter for k, _ in self.chip_rects):
            self.filter = "all"
        pool = self._bulk_pool()
        self.sell_all_btn.enabled = bool(pool)
        self._draw_bulk_button(canvas, pool)
        if not rows:
            msg = "살림망이 비어 있어요" if not net else "이 조건의 물고기가 없어요"
            text(canvas, msg, L.center, ui.DIM, 11, "center")
            if not net:
                text(canvas, "물고기를 잡으면 여기에 보관돼요", D.center, ui.DIM, 11, "center")
            self.sell_btn.enabled = self.dis_btn.enabled = self.lock_btn.enabled = False
            return
        self.sell_btn.enabled = self.lock_btn.enabled = True
        for i, row in enumerate(rows):
            r = self._row_rect(i)
            if r is None:
                continue
            su.row_bg(canvas, r, i == self.sel, r.collidepoint(self.mouse))
            self._draw_sell_row(canvas, r, row)
        if len(rows) > self._visible():
            self._scrollbar(canvas, len(rows), self._visible(), L.y + 2, L.bottom - 2)
        idx = rows[self.sel]["idxs"][0]
        self._draw_sell_detail(canvas, idx, net[idx])

    def _draw_sell_row(self, canvas, r: pygame.Rect, row: dict) -> None:
        net = self.save.data["keepnet"]
        its = [net[i] for i in row["idxs"]]
        it = its[0]
        fish = self.fish_by_id(it["id"])
        rar = fish["rarity"]
        col = su.RARITY.get(rar, su.WHITE)
        canvas.fill(col, (r.x + 9, r.y + 3, 2, r.h - 6))
        su.fish_icon(canvas, r.x + 13, r.centery, col)
        tx = r.x + 31
        y1, y2 = r.y + 8, r.y + 20
        # 위 단: 등급 → 변이 배지 → 자물쇠 | 크기 + 랭크 배지
        xx = text(canvas, su.RARITY_KO.get(rar, ""), (tx, y1), col, 11, "midleft").right + 3
        if it.get("mut"):
            ms = "◆" + mut_label(it["mut"]) if self.wide else "◆"
            xx = text(canvas, ms, (xx, y1), su.MUT, 11, "midleft").right + 3
        if it.get("lock"):
            su.lock(canvas, xx, y1, su.GRAY)
        rank = max((x["rank"] for x in its), key=lambda k: "CBAS".index(k))
        rr = pygame.Rect(r.right - 11, y1 - 5, 9, 11)
        canvas.fill(RANK_COLORS[rank], rr)
        text(canvas, rank, rr.center, su.DARK_TEXT, 11, "center", shadow=False)
        group = row["group"]
        size = max(x["size"] for x in its)
        if group:
            p = max(self.save.sale_price(x) for x in its)
            ps = f"~{p:,}원"
        else:
            ps = f"{self.save.sale_price(it):,}원"
        name = fish["name"] + (f" ×{len(its)}" if group else "")
        if self.wide:   # 위 단 오른쪽 = 크기, 아래 단 = 이름 | 가격
            text(canvas, f"{'~' if group else ''}{size:.1f}cm", (rr.x - 3, y1), su.SUB, 11, "midright")
            pr = su.btext(canvas, ps, (r.right - 3, y2), su.WHITE, 11, "midright")
            text(canvas, su.fit(name, pr.x - tx - 4), (tx, y2), su.WHITE, 11, "midleft")
        else:           # 좁은 패널: 가격을 위 단으로 (크기는 상세에) → 이름이 줄 폭을 다 쓴다
            su.btext(canvas, ps, (rr.x - 3, y1), su.WHITE, 11, "midright")
            text(canvas, su.fit(name, r.right - 3 - tx), (tx, y2), su.WHITE, 11, "midleft")

    def _draw_sell_detail(self, canvas, idx: int, it: dict) -> None:
        D = self.DETAIL
        fish = self.fish_by_id(it["id"])
        rar = fish["rarity"]
        col = su.RARITY.get(rar, su.WHITE)
        o = self._sell_off()
        box = pygame.Rect(D.x + 6, D.y + 6, D.w - 12, 56 + o)
        su.pic_box(canvas, box)
        draw_fish_fit(canvas, box.inflate(-8, -6), fish, 110)
        name = fish["name"]
        su.btext(canvas, su.fit(name, D.w - 12), (D.centerx, D.y + o + 70), col, 11, "center")
        # 배지 줄: 등급 · 변이 · 랭크 · 신기록
        badges = [(su.RARITY_KO.get(rar, ""), col)]
        if it.get("mut"):
            badges.append(("◆" + mut_label(it["mut"]), su.MUT))
        badges.append((f"{it['rank']}랭크", RANK_COLORS[it["rank"]]))
        if it.get("record"):
            badges.append(("신기록", su.YELLOW))
        tw = sum(su.width(s) + 9 for s, _ in badges) - 3
        while tw > D.w - 12 and len(badges) > 2:
            badges.pop()
            tw = sum(su.width(s) + 9 for s, _ in badges) - 3
        bx = D.centerx - tw // 2
        for s, c in badges:
            bx = su.badge(canvas, s, (bx, D.y + o + 85), c, anchor="midleft").right + 3
        text(canvas, f"{it['size']:.1f}cm", (D.centerx, D.y + o + 99), su.WHITE, 11, "center")
        # 가격 계산 상자
        calc = pygame.Rect(D.x + 6, D.y + o + 107, D.w - 12, 27)
        canvas.fill(su.WIN_BG, calc)
        pygame.draw.rect(canvas, (46, 54, 84), calc, 1)
        final = self.save.sale_price(it)
        parts, k = self._price_factors(it, fish)
        base = int(round(it["price"] / k)) if k else it["price"]
        line = f"기본가 {base:,}원" + "".join(f" × {p}" for p in parts)
        text(canvas, su.fit(line, calc.w - 8), (calc.x + 4, calc.y + 7), su.SUB, 11, "midleft")
        text(canvas, "= 판매가", (calc.x + 4, calc.y + 19), su.SUB, 11, "midleft")
        su.btext(canvas, f"{final:,}원", (calc.right - 4, calc.y + 19), su.YELLOW, 11, "midright")
        # 팔기 + 잠금
        if self.can_sell:
            su.button(canvas, self.sell_btn.rect, su.fit(f"팔기 {final:,}원", self.sell_btn.rect.w - 6), "fill", self.mouse)
        else:   # 야외: 살림망 보기만
            su.button(canvas, self.sell_btn.rect, su.fit("하루네에서 판매", self.sell_btn.rect.w - 6), "dim", self.mouse)
        lr = self.lock_btn.rect
        hov = lr.collidepoint(self.mouse)
        canvas.fill(ui.SHADOW, lr.move(1, 1))
        canvas.fill(su.SEL_BG if hov else su.WIN_BG, lr)
        pygame.draw.rect(canvas, su.YELLOW if hov else su.BORDER, lr, 1)
        lab = "잠금 해제" if it.get("lock") else "잠금"
        lab = lab if su.width(lab) + 12 <= lr.w else ("해제" if it.get("lock") else "잠금")
        lw = su.width(lab) + 9
        lx = lr.centerx - lw // 2
        su.lock(canvas, lx, lr.centery, su.WHITE)
        text(canvas, lab, (lx + 9, lr.centery), su.WHITE, 11, "midleft")
        # 분해
        got = self.save.disassemble_yield(idx)
        dr = self.dis_btn.rect
        self.dis_btn.enabled = got is not None
        if not self.can_sell:
            canvas.fill(su.CELL_BG, dr)
            pygame.draw.rect(canvas, (46, 54, 84), dr, 1)
            text(canvas, su.fit("분해는 하루네 낚시점에서", dr.w - 6), (dr.x + 4, dr.centery), su.SUB, 11, "midleft")
        elif got is None:
            canvas.fill(su.CELL_BG, dr)
            pygame.draw.rect(canvas, (46, 54, 84), dr, 1)
            s = f"분해  {self._no_dis_reason(idx)}"
            if su.width(s) <= dr.w - 8:
                text(canvas, s, (dr.x + 4, dr.centery), su.SUB, 11, "midleft")
            else:   # 좁은 패널: 두 줄
                ls = wrap_text(s, dr.w - 8)[:2]
                for j, ln in enumerate(ls):
                    text(canvas, ln, (dr.x + 4, dr.centery + (j - (len(ls) - 1) / 2) * 12), su.SUB, 11, "midleft")
        else:
            hov = dr.collidepoint(self.mouse)
            canvas.fill(su.SEL_BG if hov else su.WIN_BG, dr)
            pygame.draw.rect(canvas, su.YELLOW if hov else su.BORDER, dr, 1)
            s = "분해  " + ", ".join(f"{MAT_KO[k]} +{v}" for k, v in got.items())
            text(canvas, su.fit(s, dr.w - 6), (dr.x + 4, dr.centery), su.WHITE, 11, "midleft")

    def _price_factors(self, it: dict, fish: dict) -> tuple[list[str], float]:
        """가격 계산 상자 글자: 잡을 때 붙은 배율(랭크·변이)은 기본가로 되돌려 보이고, 팔 때 배율(도시락·전설)은 그대로."""
        parts, k = [], 1.0
        rm = load_json("fishing_config.json")["rank"]["price_mult"].get(it["rank"], 1.0)
        if rm != 1.0:
            parts.append(f"{it['rank']}랭크 {rm:g}배")
            k *= rm
        from src.fishing.mutation import cfg as mcfg
        mk = mcfg()["kinds"]
        for m in it.get("mut", []):
            v = {"giant": mk["giant"].get("price_total_mult"), "golden": mk["golden"].get("price_mult")}.get(m)
            if v:
                parts.append(f"{mut_label([m])} {v:g}배")
                k *= v
        if self.save.lunch_active():
            parts.append("도시락 1.1배")
        lm = self.save.legend_sale_mult(it)
        if abs(lm - 1.0) > 1e-6:
            parts.append(f"전설 {lm:g}배")
        return parts, k

    def _draw_bulk_button(self, canvas, pool: list) -> None:
        r = self.sell_all_btn.rect
        if not self.can_sell:
            self._draw_delivery_button(canvas, pool)
            return
        en = bool(pool)
        hov = en and r.collidepoint(self.mouse)
        canvas.fill(ui.SHADOW, r.move(1, 1))
        canvas.fill(su.SEL_BG if hov else su.WIN_BG, r)
        pygame.draw.rect(canvas, su.YELLOW if hov else su.BORDER, r, 1)
        lab = su.btext(canvas, "일괄 판매…", (r.x + 5, r.centery), su.WHITE if en else su.SUB, 11, "midleft")
        total = sum(self.save.sale_prices(pool))
        s = f"잠금 제외 {len(pool)}마리 · {total:,}원"
        if su.width(s) > r.right - lab.right - 12:
            s = f"{len(pool)}마리 · {total:,}원"
        text(canvas, su.fit(s, r.right - lab.right - 12), (r.right - 5, r.centery), su.SUB, 11, "midright")

    def _draw_delivery_button(self, canvas, pool: list) -> None:
        """야외: 특급 배송 일괄 판매 (오늘 남은 횟수) / 없으면 안내."""
        from src.save import delivery
        r = self.sell_all_btn.rect
        lv = delivery.level(self.save)
        left = delivery.uses_left(self.save)
        en = lv > 0 and left > 0 and bool(pool)
        self.sell_all_btn.enabled = True   # 눌렀을 때 이유 안내
        hov = en and r.collidepoint(self.mouse)
        canvas.fill(ui.SHADOW, r.move(1, 1))
        canvas.fill(su.SEL_BG if hov else (su.WIN_BG if en else su.CELL_BG), r)
        pygame.draw.rect(canvas, su.YELLOW if hov else (su.BORDER if en else (54, 62, 90)), r, 1)
        if lv == 0:
            text(canvas, su.fit("판매는 하루네 낚시점에서", r.w - 10), (r.x + 5, r.centery), su.SUB, 11, "midleft")
            return
        lab = su.btext(canvas, "특급 배송…", (r.x + 5, r.centery), su.WHITE if en else su.SUB, 11, "midleft")
        s = f"오늘 {left}/{lv}회"
        text(canvas, su.fit(s, r.right - lab.right - 12), (r.right - 5, r.centery), su.YELLOW if left else su.SUB, 11, "midright")

    def _bulk_lines(self) -> list[tuple[str, int, int, str]]:
        """확인 창 목록: (이름, 마리 수, 합계, 등급) — 같은 종은 한 줄."""
        todo = self._bulk_items()
        prices = self.save.sale_prices(todo)
        out: dict = {}
        for it, p in zip(todo, prices):
            f = self.fish_by_id(it["id"])
            nm = (mut_label(it["mut"]) + " " + f["name"]) if it.get("mut") else f["name"]
            e = out.setdefault(nm, [0, 0, f["rarity"]])
            e[0] += 1
            e[1] += p
        return [(k, v[0], v[1], v[2]) for k, v in out.items()]

    def _draw_bulk(self, canvas) -> None:
        P, checks, lst, ok, cancel = self._bulk_rects()
        dim = pygame.Surface(self.frame.size, pygame.SRCALPHA)
        dim.fill((6, 8, 20, 150))
        canvas.blit(dim, self.frame.topleft)
        canvas.fill(ui.SHADOW, P.move(2, 2))
        canvas.fill(su.WIN_BG, P)
        pygame.draw.rect(canvas, su.YELLOW, P, 1)
        if self.can_sell:
            su.btext(canvas, "일괄 판매", (P.x + 10, P.y + 11), su.YELLOW, 11, "midleft")
        else:
            from src.save import delivery
            su.btext(canvas, f"특급 배송 (오늘 {delivery.uses_left(self.save)}회 남음)", (P.x + 10, P.y + 11), su.YELLOW, 11,
                     "midleft")
        if P.w >= 280:
            text(canvas, "잠금한 물고기는 빠져요", (P.right - 10, P.y + 11), su.SUB, 11, "midright")
        for r, rc in checks:
            on = r in self.bulk["rar"]
            box = pygame.Rect(rc.x, rc.y + 2, 9, 9)
            canvas.fill(su.CELL_BG, box)
            pygame.draw.rect(canvas, su.RARITY[r], box, 1)
            if on:
                su.check(canvas, box.x + 1, box.centery, su.RARITY[r])
            text(canvas, su.RARITY_KO[r], (rc.x + 12, rc.centery), su.RARITY[r] if on else su.GRAY, 11, "midleft")
        canvas.fill(su.CELL_BG, lst)
        pygame.draw.rect(canvas, su.BORDER, lst, 1)
        lines = self._bulk_lines()
        vis = (lst.h - 4) // 13
        self.bulk_scroll = max(0, min(self.bulk_scroll, max(0, len(lines) - vis)))
        for j, (nm, n, total, rar) in enumerate(lines[self.bulk_scroll:self.bulk_scroll + vis]):
            y = lst.y + 8 + j * 13
            canvas.fill(su.RARITY.get(rar, su.WHITE), (lst.x + 4, y - 4, 2, 9))
            pr = text(canvas, f"{total:,}원", (lst.right - 6, y), su.WHITE, 11, "midright")
            text(canvas, su.fit(f"{nm} ×{n}", pr.x - lst.x - 16), (lst.x + 10, y), su.WHITE, 11, "midleft")
        if not lines:
            text(canvas, "고른 등급의 물고기가 없어요", lst.center, su.SUB, 11, "center")
        elif len(lines) > vis:
            text(canvas, f"… 외 {len(lines) - vis}종 (휠)", (lst.right - 6, lst.bottom + 6), su.SUB, 11, "midright")
        n = sum(x[1] for x in lines)
        total = sum(x[2] for x in lines)
        text(canvas, "합계", (P.x + 10, P.bottom - 30), su.GRAY, 11, "midleft")
        su.btext(canvas, f"{n}마리 · {total:,}원", (P.x + 36, P.bottom - 30), su.YELLOW, 11, "midleft")
        su.button(canvas, ok, "팔기", "fill" if lines else "dim", self.mouse)
        su.button(canvas, cancel, "취소", "outline", self.mouse)

    # ── 강화 탭 ──
    def _draw_enhance(self, canvas, rows) -> None:
        L = self.LIST
        mats = self.save.data["materials"]
        short = {"sharmion": "샤르미온", "eldrasion": "엘드라시온", "rare": "희귀"}
        mline = "소재 " + " · ".join(f"{short[k]} {mats.get(k, 0)}" for k in ("sharmion", "eldrasion", "rare"))
        if su.width(mline) > L.w - 12:
            mline = " · ".join(f"{s} {mats.get(k, 0)}" for k, s in (("sharmion", "샤르미온"), ("eldrasion", "엘드라"),
                                                                      ("rare", "희귀")))
        text(canvas, su.fit(mline, L.w - 12), (L.x + 6, L.bottom - 8), su.SUB, 11, "midleft")
        if not rows:
            text(canvas, "강화할 장비가 없어요", L.center, ui.DIM, 11, "center")
            self.action_btn.enabled = False
            return
        for i, (kind, g) in enumerate(rows):
            r = self._row_rect(i)
            if r is None:
                continue
            su.row_bg(canvas, r, i == self.sel, r.collidepoint(self.mouse))
            ny, sy = (r.centery, r.centery) if self.wide else (r.y + 8, r.y + 19)
            if kind == "delivery":
                from src.save import delivery
                dl = delivery.level(self.save)
                gear_icon.draw(canvas, kind, g, (r.x + 30, sy - 7, 14, 14))
                st = f"Lv{dl}" if dl else "미보유"
                sr = text(canvas, st, (r.right - 4, sy), su.YELLOW if dl else su.SUB, 11, "midright")
                nx = r.x + 48 if self.wide else r.x + 9
                text(canvas, su.fit(g["name"], (sr.x - nx - 4) if self.wide else (r.right - 4 - nx)), (nx, ny), su.WHITE,
                     11, "midleft")
                continue
            lvl = self.save.enhance_level(g["id"])
            su.btext(canvas, f"T{g['tier']}", (r.x + 9, ny), su.YELLOW, 11, "midleft")
            gear_icon.draw(canvas, kind, g, (r.x + 30, sy - 7, 14, 14))
            right = r.right - 4
            if lvl:
                right = su.btext(canvas, f"+{lvl}", (right, sy), su.YELLOW, 11, "midright").x - 4
            kr = text(canvas, KIND_KO[kind], (right, sy), su.SUB, 11, "midright")
            nx = r.x + 48 if self.wide else r.x + 30
            nw = (kr.x - nx - 4) if self.wide else (r.right - 4 - nx)
            text(canvas, su.fit(g["name"], nw), (nx, ny), su.WHITE, 11, "midleft")
        n = len(rows)
        if n > self._visible():
            self._scrollbar(canvas, n, self._visible(), L.y + 2, L.bottom - 16)
        D = self.DETAIL
        kind, g = rows[self.sel]
        if kind == "delivery":
            self._draw_delivery_detail(canvas, g)
            return
        lvl = self.save.enhance_level(g["id"])
        x = D.x + 6
        box = pygame.Rect(D.x + 6, D.y + 6, D.w - 12, 70)
        su.pic_box(canvas, box)
        gear_icon.draw(canvas, kind, g, (box.centerx - 32, box.centery - 32, 64, 64))
        stars = "★" * lvl + "☆" * (rules()["max_level"] - lvl)
        text(canvas, stars, (box.right - 4, box.y + 8), su.YELLOW, 11, "midright")
        su.btext(canvas, su.fit(f"{g['name']} +{lvl}", D.w - 12), (x, D.y + 88), su.YELLOW, 11, "midleft")
        cost = self.save.enhance_cost(kind, g)
        yy = D.y + 106
        now = enhanced(kind, g, lvl)
        nxt = enhanced(kind, g, lvl + 1) if cost else now
        for (label, v0, fmt, up), (_, v1, _, _) in zip(stat_rows(kind, now), stat_rows(kind, nxt)):
            text(canvas, label, (x, yy), su.WHITE, 11, "midleft")
            s = f"{fmt.format(v0)}" + (f" → {fmt.format(v1)}" if cost else "")
            (su.btext if cost and v1 != v0 else text)(canvas, s, (D.right - 6, yy), su.GREEN if cost and v1 != v0 else su.WHITE,
                                                     11, "midright")
            yy += 13
        yy += 4
        b = self.action_btn
        if cost is None:
            text(canvas, "최대 강화 (+3)", (x, yy), su.GREEN, 11, "midleft")
            b.label, b.enabled, style = "최대 강화", False, "dim"
        else:
            have_gold = self.save.money >= cost["gold"]
            have_mat = mats.get(cost["continent"], 0) >= cost["materials"]
            have_rare = mats.get("rare", 0) >= cost["rare"]
            su.price(canvas, cost["gold"], (x, yy), su.WHITE if have_gold else su.RED, anchor="midleft", bold=True)
            yy += 13
            text(canvas, f"{MAT_KO[cost['continent']]} {mats.get(cost['continent'], 0)}/{cost['materials']}",
                 (x, yy), su.WHITE if have_mat else su.RED, 11, "midleft")
            yy += 13
            if cost["rare"]:
                text(canvas, f"희귀 소재 {mats.get('rare', 0)}/{cost['rare']}", (x, yy),
                     su.WHITE if have_rare else su.RED, 11, "midleft")
            text(canvas, "강화는 실패하지 않아요", (x, D.bottom - 31), su.SUB, 11, "midleft")
            b.label = f"+{lvl + 1} 강화"
            b.enabled = have_gold and have_mat and have_rare
            style = "fill" if b.enabled else "dim"
        su.button(canvas, b.rect, b.label, style, self.mouse)

    def _draw_delivery_detail(self, canvas, g: dict) -> None:
        """특급 배송 시스템: 야외에서 일괄 판매 하루 n번 (단계 = 횟수, 최대 5)."""
        from src.save import delivery
        D = self.DETAIL
        x = D.x + 6
        lv = delivery.level(self.save)
        box = pygame.Rect(D.x + 6, D.y + 6, D.w - 12, 70)
        su.pic_box(canvas, box)
        gear_icon.draw(canvas, "delivery", g, (box.centerx - 32, box.centery - 32, 64, 64))
        text(canvas, "★" * lv + "☆" * (delivery.MAX_LEVEL - lv), (box.right - 4, box.y + 8), su.YELLOW, 11, "midright")
        su.btext(canvas, su.fit(f"{g['name']} Lv{lv}", D.w - 12), (x, D.y + 88), su.YELLOW, 11, "midleft")
        lines = wrap_text("낚시터·마을에서도 살림망 물고기를 일괄 판매할 수 있어요.", D.w - 12)[:2]
        for i, ln in enumerate(lines):
            text(canvas, ln, (x, D.y + 104 + i * 12), su.GRAY, 11, "midleft")
        yy = D.y + 132
        text(canvas, "하루 횟수", (x, yy), su.WHITE, 11, "midleft")
        cost = delivery.next_cost(self.save)
        s = f"{lv}회" + (f" → {lv + 1}회" if cost is not None else "")
        (su.btext if cost is not None else text)(canvas, s, (D.right - 6, yy), su.GREEN if cost is not None else su.WHITE, 11,
                                                 "midright")
        if lv:
            text(canvas, f"오늘 남은 횟수 {delivery.uses_left(self.save)}회", (x, yy + 13), su.SUB, 11, "midleft")
        b = self.action_btn
        if cost is None:
            b.label, b.enabled, style = "최대 단계", False, "dim"
        else:
            su.price(canvas, cost, (x, D.bottom - 31), su.WHITE if self.save.money >= cost else su.RED, anchor="midleft",
                     bold=True)
            b.label = "구매하기" if lv == 0 else f"Lv{lv + 1} 강화"
            b.enabled = self.save.money >= cost
            style = "fill" if b.enabled else "dim"
        su.button(canvas, b.rect, b.label, style, self.mouse)


def _star(cx: int, cy: int, r: int) -> list:
    import math
    pts = []
    for i in range(10):
        a = -math.pi / 2 + i * math.pi / 5
        rr = r if i % 2 == 0 else r * 0.45
        pts.append((cx + math.cos(a) * rr, cy + math.sin(a) * rr))
    return pts
