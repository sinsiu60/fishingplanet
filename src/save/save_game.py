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


def enhanced(kind: str, item: dict, level: int) -> dict:
    """강화 단계만큼 능력치를 좋은 방향으로 올린 사본."""
    if level <= 0:
        return item
    k = 1.0 + rules()["per_level"] * level
    g = copy.deepcopy(item)
    if kind == "rod":
        lo, hi = g["green"]
        c, w = (lo + hi) / 2, (hi - lo) * k
        g["green"] = [round(c - w / 2, 1), round(c + w / 2, 1)]
    elif kind == "reel":
        g["speed"] = round(g["speed"] * k, 3)
    elif kind == "line":
        g["durability"] = round(g["durability"] * k)
    elif kind == "net":
        g["window"] = round(g["window"] * k, 3)
        g["fail_distance"] = round(g["fail_distance"] / k, 2)
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
        return find_gear(kind, self.data["gear"][kind])

    def owns(self, kind: str, item_id: str) -> bool:
        return item_id in self.data["owned"][kind]

    def enhance_level(self, item_id: str) -> int:
        return self.data["enhance"].get(item_id, 0)

    def effective(self, kind: str, item: dict) -> dict:
        """강화가 반영된 장비 수치 (원본은 건드리지 않음)."""
        lvl = self.enhance_level(item["id"]) if self.owns(kind, item["id"]) else 0
        return enhanced(kind, item, lvl)

    def fight_gear(self) -> dict:
        """Fight에 넘길 장비 수치 (강화 반영)."""
        rod, reel, line, net = (self.effective(k, self.equipped(k)) for k in GEAR_KINDS)
        return {"rod_green": list(rod["green"]), "reel_speed": reel["speed"], "drag_steps": reel["drag_steps"],
                "line_max": line["durability"], "net_window_sec": net["window"],
                "net_fail_distance": net["fail_distance"]}

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
            need = [f for f in all_fish() if f["spot"] == spot and f["rarity"] != "legend"]
            missing = [f for f in need if f["id"] not in self.data["dex"]]
            if missing:
                return f"이 낚시터 물고기 {len(need) - len(missing)}/{len(need)}종 포획 필요"
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
        return news

    def record_loss(self) -> None:
        self.data["stats"]["lost"] += 1

    def sell(self, index: int) -> int:
        if not 0 <= index < len(self.data["keepnet"]):
            return 0
        item = self.data["keepnet"].pop(index)
        self.data["money"] += item["price"]
        self.data["stats"]["earned"] += item["price"]
        return item["price"]

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
        total = sum(it["price"] for it in self.data["keepnet"])
        self.data["money"] += total
        self.data["stats"]["earned"] += total
        self.data["keepnet"].clear()
        return total

    # ── 도감 ──
    def dex_count(self) -> int:
        return len(self.data["dex"])

    def dex_entry(self, fish_id: str) -> dict | None:
        return self.data["dex"].get(fish_id)
