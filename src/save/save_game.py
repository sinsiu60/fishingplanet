"""게임 진행 저장 (슬롯 3개, 내 문서/FishingPlanet/slot1~3.json).

돈·장비·살림망·도감·통계·현재 시간/낚시터를 담는다. 자동 저장은 FishingScene이 호출한다.

버전 기록:
  1  출시 버전
  2  확장 (대륙·강화·소재·상자·부적·특수 찌 필드). v1 세이브는 불러올 때 원본을 slotN.v1.bak.json으로
     백업한 뒤 새 필드만 기본값으로 채운다 (DESIGN.md 22장). 지우는 필드 없음, unlocked_spots는 그대로.
"""
import copy
import json
import os
import shutil
import time

from src.core.config import load_json
from src.core.paths import save_dir

SLOTS = 3
VERSION = 2
RANK_ORDER = {"C": 0, "B": 1, "A": 2, "S": 3}
GEAR_KINDS = ("rod", "reel", "line", "net")
TOP_TIER = {"sharmion": 5, "eldrasion": 8}  # 대륙별 상점 최고 티어


def _slot_path(slot: int):
    return save_dir() / f"slot{slot}.json"


def rules() -> dict:
    return load_json("equipment.json")["_rules"]


def _deep_merge(base: dict, data: dict) -> dict:
    """data 값을 우선하되, base에만 있는 키(새 버전에서 생긴 필드)는 중첩 dict 안까지 채운다."""
    out = dict(base)
    for k, v in data.items():
        if isinstance(v, dict) and isinstance(base.get(k), dict) and k not in ("dex", "enhance", "treasure_dex"):
            out[k] = _deep_merge(base[k], v)
        else:
            out[k] = v
    return out


def migrate(data: dict, slot: int | None = None) -> dict:
    """옛 세이브를 현재 버전으로. 지우지 않고 추가만 한다."""
    ver = data.get("version", 1)
    if ver < 2:
        if slot is not None:
            src, bak = _slot_path(slot), save_dir() / f"slot{slot}.v1.bak.json"
            if src.exists() and not bak.exists():
                try:
                    shutil.copyfile(src, bak)
                except OSError:
                    pass
        conts = ["sharmion"]
        if "dragon_carp" in data.get("dex", {}):
            conts.append("eldrasion")  # 이미 '등용'을 잡았으면 확장을 바로 시작
            spots = data.setdefault("unlocked_spots", ["reservoir"])
            if "marsh" not in spots:
                spots.append("marsh")
            data.setdefault("flags", {})["voyage_pending"] = True
        data.setdefault("unlocked_continents", conts)
        data["version"] = 2
    return data


def equipment() -> dict:
    return load_json("equipment.json")


def baits() -> dict:
    return {b["id"]: b for b in load_json("baits.json")["baits"]}


def find_gear(kind: str, gear_id: str) -> dict:
    for g in equipment()[kind]:
        if g["id"] == gear_id:
            return g
    return equipment()[kind][0]


def all_fish() -> list[dict]:
    return load_json("fish.json")["fish"]


def fish_by_id(fid: str) -> dict:
    return next(f for f in all_fish() if f["id"] == fid)


def spot_continent(spot_id: str) -> str:
    for s in load_json("spots.json")["spots"]:
        if s["id"] == spot_id:
            return s.get("continent", "sharmion")
    return "sharmion"


def _stat(kind: str, g: dict) -> dict:
    """강화 대상 능력치 (모두 '클수록 좋음'으로 맞춤: 실패 거리는 역수)."""
    if kind == "rod":
        return {"green": g["green"][1] - g["green"][0]}
    if kind == "reel":
        return {"speed": g["speed"]}
    if kind == "line":
        return {"durability": g["durability"]}
    return {"window": g["window"], "fail_distance": 1.0 / g["fail_distance"]}


def enhance_gain(kind: str, item: dict, level: int) -> dict:
    """능력치별 배율. 단계당 '다음 티어와의 차이 × gap_frac' → +3이어도 다음 티어 기본 성능보다 조금 낮다.
    최고 티어는 바로 아래 티어와의 차이를 쓴다. 티어를 모르는 장비는 단계당 per_level 고정."""
    r = rules()
    shop = {g["tier"]: g for g in equipment().get(kind, [])}
    tier = item.get("tier")
    if tier in shop and (tier + 1 in shop or tier - 1 in shop):
        lo, hi = (shop[tier], shop[tier + 1]) if tier + 1 in shop else (shop[tier - 1], shop[tier])
        a, b = _stat(kind, lo), _stat(kind, hi)
        return {k: 1.0 + (b[k] / a[k] - 1.0) * r["gap_frac"] * level for k in a}
    return {k: 1.0 + r["per_level"] * level for k in _stat(kind, item)}


def enhanced(kind: str, item: dict, level: int) -> dict:
    """강화 단계만큼 능력치를 좋은 방향으로 올린 사본."""
    if level <= 0:
        return item
    k = enhance_gain(kind, item, level)
    g = copy.deepcopy(item)
    if kind == "rod":
        lo, hi = g["green"]
        c, w = (lo + hi) / 2, (hi - lo) * k["green"]
        g["green"] = [round(c - w / 2, 1), round(c + w / 2, 1)]
    elif kind == "reel":
        g["speed"] = round(g["speed"] * k["speed"], 3)
    elif kind == "line":
        g["durability"] = round(g["durability"] * k["durability"])
    elif kind == "net":
        g["window"] = round(g["window"] * k["window"], 3)
        g["fail_distance"] = round(g["fail_distance"] / k["fail_distance"], 2)
    return g


def new_data() -> dict:
    eq = equipment()
    now = time.time()
    return {
        "version": VERSION, "created": now, "updated": now, "playtime": 0.0,
        "money": 0, "hour": 7.0, "day": 1, "spot": "reservoir", "weather": "clear",
        "unlocked_spots": ["reservoir"],
        "gear": {k: eq[k][0]["id"] for k in GEAR_KINDS} | {"bait": "worm"},
        "owned": {k: [eq[k][0]["id"]] for k in GEAR_KINDS} | {"bait": ["worm"]},
        "keepnet": [],
        "dex": {},
        "stats": {"catches": 0, "s_ranks": 0, "perfects": 0, "lost": 0, "earned": 0,
                  "chests_opened": 0, "s_ranks_eldra": 0},
        # ── 확장 (v2) ──
        "continent": "sharmion",
        "unlocked_continents": ["sharmion"],
        "enhance": {},                                   # 장비 id → 강화 단계
        "materials": {"sharmion": 0, "eldrasion": 0, "rare": 0},
        "scales": 0,                                     # 전설 비늘
        "chests": {"common": 0, "rare": 0, "special": 0, "legend": 0},
        "pity": {"special": 0, "legend": 0},
        "shards": 0,
        "items": {"owned": [], "consumables": {}, "charms": [None]},
        "float": {"owned": [], "equipped": None},
        "treasure_dex": {},
        "flags": {"eldra_escape_tutorial": False},
        "buffs": {"lucky_casts": 0, "lunch_until": 0.0},  # 소모품 효과 (행운의 떡밥 남은 캐스팅, 도시락 끝나는 플레이 시간)
    }


class SaveGame:
    def __init__(self, slot: int, data: dict | None = None):
        self.slot = slot
        self.data = data or new_data()

    # ── 슬롯 ──
    @staticmethod
    def load(slot: int) -> "SaveGame | None":
        try:
            with open(_slot_path(slot), encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, ValueError):
            return None
        data = migrate(data, slot)
        return SaveGame(slot, _deep_merge(new_data(), data))  # 새 항목은 기본값으로 채움

    @staticmethod
    def summary(slot: int) -> dict | None:
        sg = SaveGame.load(slot)
        if sg is None:
            return None
        d = sg.data
        return {"money": d["money"], "dex": sg.dex_count(), "dex_total": len(all_fish()),
                "playtime": d["playtime"], "updated": d["updated"], "spot": d["spot"]}

    @staticmethod
    def latest_slot() -> int | None:
        best, best_t = None, -1.0
        for s in range(1, SLOTS + 1):
            info = SaveGame.summary(s)
            if info and info["updated"] > best_t:
                best, best_t = s, info["updated"]
        return best

    def save(self) -> bool:
        self.data["updated"] = time.time()
        path = _slot_path(self.slot)
        tmp = path.with_suffix(".tmp")
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self.data, f, ensure_ascii=False, indent=1)
            os.replace(tmp, path)  # 저장 중 꺼져도 기존 파일이 깨지지 않게
            return True
        except OSError:
            return False

    # ── 장비 ──
    @property
    def money(self) -> int:
        return self.data["money"]

    def equipped(self, kind: str) -> dict:
        if kind == "bait":
            return baits()[self.data["gear"]["bait"]]
        gid = self.data["gear"][kind]
        if self.owns_treasure(kind, gid):
            return self.treasure_gear(kind, gid)
        return find_gear(kind, gid)

    def owns(self, kind: str, item_id: str) -> bool:
        return item_id in self.data["owned"][kind] or self.owns_treasure(kind, item_id)

    # ── 상자 아이템 (Phase E) ──
    def owns_treasure(self, kind: str, item_id: str) -> bool:
        if item_id not in self.data["items"]["owned"]:
            return False
        from src.save.treasure import item_info
        return item_info(item_id)["kind"] == kind

    def top_continent(self) -> str:
        return "eldrasion" if "eldrasion" in self.data["unlocked_continents"] else "sharmion"

    def treasure_gear(self, kind: str, item_id: str) -> dict:
        """상자 장비의 실제 수치. 기본 = 대륙 상점 최고 티어 (전설은 지금 열린 가장 높은 대륙 기준으로 자동 상향,
        특별은 얻은 대륙 기준). 대가(-5%)는 그대로 유지. 상점 최고 티어를 넘지 않는다."""
        from src.save.treasure import item_info
        it = item_info(item_id)
        cont = self.top_continent() if it["grade"] == "legend" else \
            self.data["items"].get("origin", {}).get(item_id, "sharmion")
        top = TOP_TIER[cont]
        base = max((g for g in equipment()[kind] if g["tier"] <= top), key=lambda g: g["tier"])
        g = copy.deepcopy(base)
        g.pop("continent", None)
        g.pop("scales", None)
        g.update(id=item_id, name=it["name"], desc=it["desc"], price=0, treasure=True)
        if item_id == "dragon_scale_rod":
            lo, hi = g["green"]
            c, w = (lo + hi) / 2, (hi - lo) * 0.95
            g["green"] = [round(c - w / 2, 1), round(c + w / 2, 1)]
        elif item_id == "ancient_reel":
            g["speed"] = round(g["speed"] * 0.95, 3)
        return g

    def unlock_continent(self, cont: str) -> bool:
        """대륙 해금 (처음이면 True). 첫 낚시터도 함께 연다."""
        if cont in self.data["unlocked_continents"]:
            return False
        self.data["unlocked_continents"].append(cont)
        first = next(c["first_spot"] for c in load_json("continents.json")["continents"] if c["id"] == cont)
        if first not in self.data["unlocked_spots"]:
            self.data["unlocked_spots"].append(first)
        return True

    # ── 특수 찌 (엘드라시온) ──
    def float_tier(self) -> int:
        fid = self.data["float"].get("equipped")
        if not fid:
            return 0
        return next((f["tier"] for f in load_json("floats.json")["floats"] if f["id"] == fid), 0)

    def float_need(self, fish: dict, spot: dict) -> int:
        """이 물고기를 끝까지 잡는 데 필요한 찌 티어 (샤르미온 = 0)."""
        if spot.get("continent", "sharmion") != "eldrasion":
            return 0
        need = spot.get("float_req", 0) + (1 if fish["rarity"] == "legend" else 0)
        return min(5, need)

    def float_scales_needed(self) -> int:
        """아직 안 산 특수 찌들에 드는 전설 비늘 합계."""
        owned = self.data["float"]["owned"]
        return sum(f.get("scales", 0) for f in load_json("floats.json")["floats"] if f["id"] not in owned)

    def scale_warning(self, item: dict) -> int | None:
        """비늘이 드는 장비를 사면 남은 특수 찌를 살 비늘이 모자라지는지. 모자라지면 필요한 비늘 수."""
        cost = item.get("scales", 0)
        need = self.float_scales_needed()
        if cost and self.data["scales"] >= need and self.data["scales"] - cost < need:
            return need
        return None

    def buy_float(self, item: dict) -> str:
        fl = self.data["float"]
        if item["id"] in fl["owned"]:
            return "already"
        if "eldrasion" not in self.data["unlocked_continents"]:
            return "locked"
        if self.data["money"] < item["price"]:
            return "money"
        if self.data["scales"] < item.get("scales", 0):
            return "scales"
        self.data["money"] -= item["price"]
        self.data["scales"] -= item.get("scales", 0)
        fl["owned"].append(item["id"])
        fl["equipped"] = item["id"]
        self.data["flags"]["float_highlight"] = False
        return "ok"

    def record_seen(self, fish_id: str) -> None:
        """도감에 '목격'으로 등록 (잡은 것은 아님)."""
        self.data["dex"].setdefault(fish_id, {"count": 0, "max_size": 0.0, "best_rank": "C", "seen": True})

    def charm_slots(self) -> int:
        return 2 if "eldrasion" in self.data["unlocked_continents"] else 1

    def charms(self) -> list:
        ch = self.data["items"].setdefault("charms", [None])
        n = self.charm_slots()
        while len(ch) < n:
            ch.append(None)
        return ch[:n]

    def charm_on(self, item_id: str) -> bool:
        return item_id in self.charms()

    def toggle_charm(self, item_id: str) -> str:
        """장착/해제. 칸이 꽉 찼으면 첫 칸을 바꾼다."""
        ch = self.charms()
        full = self.data["items"]["charms"]
        if item_id in ch:
            full[full.index(item_id)] = None
            return "off"
        for i, v in enumerate(ch):
            if v is None:
                full[i] = item_id
                return "on"
        full[0] = item_id
        return "on"

    def cosmetic_on(self, item_id: str) -> bool:
        return self.data["items"].get("cosmetic") == item_id

    def toggle_cosmetic(self, item_id: str) -> None:
        items = self.data["items"]
        items["cosmetic"] = None if items.get("cosmetic") == item_id else item_id

    def consumable_count(self, item_id: str) -> int:
        return self.data["items"]["consumables"].get(item_id, 0)

    def use_consumable(self, item_id: str) -> bool:
        cons = self.data["items"]["consumables"]
        if cons.get(item_id, 0) <= 0:
            return False
        cons[item_id] -= 1
        return True

    def lunch_active(self) -> bool:
        return self.data["playtime"] < self.data["buffs"].get("lunch_until", 0.0)

    def sale_price(self, item: dict) -> int:
        return int(round(item["price"] * (1.1 if self.lunch_active() else 1.0)))

    def enhance_level(self, item_id: str) -> int:
        return self.data["enhance"].get(item_id, 0)

    def effective(self, kind: str, item: dict) -> dict:
        """강화가 반영된 장비 수치 (원본은 건드리지 않음)."""
        lvl = self.enhance_level(item["id"]) if self.owns(kind, item["id"]) else 0
        return enhanced(kind, item, lvl)

    def fight_gear(self, period: str = "day") -> dict:
        """Fight에 넘길 장비 수치 (강화 + 상자 아이템 효과 반영)."""
        rod, reel, line, net = (self.effective(k, self.equipped(k)) for k in GEAR_KINDS)
        green = list(rod["green"])
        if rod["id"] == "moon_rod" and period in ("night", "day"):
            # 달빛 낚싯대: 밤 +10%, 낮 -5%
            k = 1.10 if period == "night" else 0.95
            c, w = (green[0] + green[1]) / 2, (green[1] - green[0]) * k
            green = [c - w / 2, c + w / 2]
        return {"rod_green": green, "rod_tier": rod.get("tier", 1), "reel_speed": reel["speed"], "drag_steps": reel["drag_steps"],
                "line_max": line["durability"], "net_window_sec": net["window"],
                "net_fail_distance": net["fail_distance"],
                "line_red_mult": 0.9 if self.charm_on("warm_gloves") else 1.0,
                "perfect_heal": 0.10 if rod["id"] == "dragon_scale_rod" else 0.0,
                "auto_drag": reel["id"] == "ancient_reel"}

    def gear_tier(self, kind: str) -> int:
        """장착한 장비 티어 (전설 미끼처럼 티어 없는 미끼는 0)."""
        return self.equipped(kind).get("tier", 0)

    # ── 강화 ──
    def enhance_cost(self, kind: str, item: dict) -> dict | None:
        """다음 강화 비용 {gold, materials, rare, continent}. 최대 단계면 None."""
        r = rules()
        lvl = self.enhance_level(item["id"])
        if kind not in r["enhance_kinds"] or lvl >= r["max_level"]:
            return None
        gold = round(item["price"] * r["gold_frac"][lvl]) if item["price"] > 0 else r["gold_free"][lvl]
        return {"gold": gold, "materials": r["materials"][lvl], "rare": r["rare_materials"][lvl],
                "continent": item.get("continent", "sharmion")}

    def enhance(self, kind: str, item: dict) -> str:
        if not self.owns(kind, item["id"]):
            return "not_owned"
        cost = self.enhance_cost(kind, item)
        if cost is None:
            return "max"
        mats = self.data["materials"]
        if self.data["money"] < cost["gold"]:
            return "money"
        if mats.get(cost["continent"], 0) < cost["materials"] or mats.get("rare", 0) < cost["rare"]:
            return "materials"
        self.data["money"] -= cost["gold"]
        mats[cost["continent"]] -= cost["materials"]
        mats["rare"] -= cost["rare"]
        self.data["enhance"][item["id"]] = self.enhance_level(item["id"]) + 1
        return "ok"

    def bait_locked_reason(self, bait: dict) -> str | None:
        """판매 조건을 못 채웠으면 이유, 아니면 None."""
        if bait.get("price", 0) < 0:
            return "판매하지 않음"
        spot = bait.get("unlock_spot")
        if spot:
            # 일반~고급만 (희귀는 빠짐 — 전설 미끼가 너무 늦게 열리지 않게, DESIGN.md 25장)
            need = [f for f in all_fish() if f["spot"] == spot and f["rarity"] in ("common", "uncommon")]
            missing = [f for f in need if f["id"] not in self.data["dex"]]
            if missing:
                return f"이 낚시터 일반~고급 {len(need) - len(missing)}/{len(need)}종 포획 필요"
        return None

    def gear_locked_reason(self, item: dict) -> str | None:
        """대륙 잠금 (엘드라시온 장비)."""
        cont = item.get("continent")
        if cont and cont not in self.data["unlocked_continents"]:
            return "엘드라시온 대륙에서 판매"
        return None

    def buy(self, kind: str, item: dict) -> str:
        if self.owns(kind, item["id"]):
            return "already"
        if self.gear_locked_reason(item) or (kind == "bait" and self.bait_locked_reason(item)):
            return "locked"
        if self.data["money"] < item["price"]:
            return "money"
        if self.data["scales"] < item.get("scales", 0):
            return "scales"
        self.data["money"] -= item["price"]
        self.data["scales"] -= item.get("scales", 0)
        self.data["owned"][kind].append(item["id"])
        self.data["gear"][kind] = item["id"]
        return "ok"

    def equip(self, kind: str, item_id: str) -> None:
        if self.owns(kind, item_id):
            self.data["gear"][kind] = item_id

    # ── 포획 · 판매 ──
    def record_catch(self, result: dict) -> dict:
        """획득 기록. 돌려주는 값: 새로 등록 / 최대 크기 경신 / 힌트 해금 / S 금테 등."""
        fish = result["fish"]
        fid = fish["id"]
        dex = self.data["dex"]
        entry = dex.get(fid)
        news = {"new": entry is None, "record": False, "hint": 0, "gold": False}
        if entry is None:
            entry = {"count": 0, "max_size": 0.0, "best_rank": "C"}
            dex[fid] = entry
        entry["count"] += 1
        if result["size"] > entry["max_size"]:
            news["record"] = not news["new"]
            entry["max_size"] = result["size"]
        if RANK_ORDER[result["rank"]] > RANK_ORDER[entry["best_rank"]] or entry["count"] == 1:
            if result["rank"] == "S" and entry.get("best_rank") != "S":
                news["gold"] = True
            entry["best_rank"] = result["rank"] if RANK_ORDER[result["rank"]] >= RANK_ORDER[entry["best_rank"]] \
                else entry["best_rank"]
        if entry["count"] in (3, 10):
            news["hint"] = entry["count"]
        self.data["keepnet"].append({"id": fid, "size": result["size"], "rank": result["rank"],
                                     "price": result["price"]})
        st = self.data["stats"]
        st["catches"] += 1
        st["perfects"] += result.get("perfects", 0)
        if result["rank"] == "S":
            st["s_ranks"] += 1
            if spot_continent(fish["spot"]) == "eldrasion":
                st["s_ranks_eldra"] = st.get("s_ranks_eldra", 0) + 1
        return news

    def record_loss(self) -> None:
        self.data["stats"]["lost"] += 1

    def sell(self, index: int) -> int:
        if not 0 <= index < len(self.data["keepnet"]):
            return 0
        item = self.data["keepnet"].pop(index)
        price = self.sale_price(item)
        self.data["money"] += price
        self.data["stats"]["earned"] += price
        return price

    def disassemble_yield(self, index: int) -> dict | None:
        """분해하면 얻는 소재 {대륙: n, 'rare': n}. 전설은 분해 불가 (None)."""
        if not 0 <= index < len(self.data["keepnet"]):
            return None
        fish = fish_by_id(self.data["keepnet"][index]["id"])
        r = rules()
        n = r["disassemble"].get(fish["rarity"])
        if n is None:
            return None
        out = {spot_continent(fish["spot"]): n}
        if r["disassemble_rare_bonus"].get(fish["rarity"]):
            out["rare"] = r["disassemble_rare_bonus"][fish["rarity"]]
        return out

    def disassemble(self, index: int) -> dict | None:
        got = self.disassemble_yield(index)
        if got is None:
            return None
        self.data["keepnet"].pop(index)
        mats = self.data["materials"]
        for k, v in got.items():
            mats[k] = mats.get(k, 0) + v
        return got

    def sell_all(self) -> int:
        total = sum(self.sale_price(it) for it in self.data["keepnet"])
        self.data["money"] += total
        self.data["stats"]["earned"] += total
        self.data["keepnet"].clear()
        return total

    # ── 도감 ──
    def dex_count(self) -> int:
        return sum(1 for e in self.data["dex"].values() if e.get("count", 0) > 0)

    def dex_entry(self, fish_id: str) -> dict | None:
        e = self.data["dex"].get(fish_id)
        return e if e and e.get("count", 0) > 0 else None  # '목격'만 한 물고기는 잡은 것이 아님

    def hint_status(self, fish: dict) -> tuple[bool, list[tuple[str, int, int]]]:
        """고급·희귀·전설의 등장 조건(시간·날씨)이 도감에 보이는지 + 진행 [(등급, 잡은 수, 필요 수)].
        고급 = 그 낚시터 일반 전부, 희귀 = 일반 전부 + 고급 1종 이상, 전설 = 일반·고급 전부 + 희귀 1종 이상.
        (그 등급이 그 낚시터에 없으면 그 조건은 빠진다 — 용문 폭포의 희귀처럼)"""
        order = ["common", "uncommon", "rare", "legend"]
        k = order.index(fish["rarity"])
        if k == 0:
            return False, []
        same = [f for f in all_fish() if f["spot"] == fish["spot"]]
        if k == 1:
            group = [f for f in same if f["rarity"] == "common"]
            rows = [("common", sum(self.caught(f["id"]) for f in group), len(group))] if group else []
            return all(h >= n for _, h, n in rows), rows
        rows = []
        for tier in order[:k - 1]:
            group = [f for f in same if f["rarity"] == tier]
            if group:
                rows.append((tier, sum(self.caught(f["id"]) for f in group), len(group)))
        prev = [f for f in same if f["rarity"] == order[k - 1]]
        if prev:
            rows.append((order[k - 1], min(1, sum(self.caught(f["id"]) for f in prev)), 1))
        return all(have >= need for _, have, need in rows), rows

    def caught(self, fish_id: str) -> bool:
        return self.dex_entry(fish_id) is not None

    def continent_dex(self, continent: str = "sharmion") -> tuple[int, int]:
        """(잡은 종 수, 전체 종 수) — 그 대륙 기준."""
        fish = [f for f in all_fish() if spot_continent(f["spot"]) == continent]
        return sum(1 for f in fish if self.caught(f["id"])), len(fish)

    def rare_total(self) -> int:
        """희귀 이상 누적 포획 마리 수."""
        rar = {f["id"]: f["rarity"] for f in all_fish()}
        return sum(e.get("count", 0) for fid, e in self.data["dex"].items() if rar.get(fid) in ("rare", "legend"))

    def spot_has_s(self, spot: str) -> bool:
        return any(self.dex_entry(f["id"]) and self.data["dex"][f["id"]].get("best_rank") == "S"
                   for f in all_fish() if f["spot"] == spot)
