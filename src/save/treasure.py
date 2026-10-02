"""보물상자: 드랍 판정, 천장(불운 방지), 개봉 보상, 중복 → 조각, 조각 교환소.

수치는 전부 data/treasure.json. 세이브 필드: chests{등급: 개수}, pity{special, legend}, shards,
items{owned: [고유 아이템 id], consumables: {id: 개수}}, stats.chests_opened.
상자 등급은 '얻는 순간' 정해진다 (포획 컷에서 등급 색으로 보여주기 위해). 천장도 그때 적용.
"""
import random

from src.core.config import load_json
from src.save.save_game import all_fish, spot_continent

GRADES = ("common", "rare", "special", "legend")


def cfg() -> dict:
    return load_json("treasure.json")


def grade_info(grade: str) -> dict:
    return next(g for g in cfg()["grades"] if g["id"] == grade)


def item_info(item_id: str) -> dict:
    return next(i for i in cfg()["items"] if i["id"] == item_id)


def items_of(grade: str) -> list[dict]:
    return [i for i in cfg()["items"] if i["grade"] == grade]


def drop_chance(fish: dict, rank: str, bonus: float = 0.0) -> float:
    c = cfg()
    p = c["drop"].get(fish["rarity"], 0.0) + bonus
    if fish["rarity"] == "legend":
        return p
    if rank == "S":
        p += c["s_rank_bonus"]
    p += c["fish_bonus"].get(fish["id"], 0.0)
    return min(1.0, p)


def _roll_grade(save, rnd, legend_fish: bool) -> str:
    c = cfg()
    pity = save.data["pity"]
    if pity["legend"] >= c["pity"]["legend"]:
        grade = "legend"
    elif pity["special"] >= c["pity"]["special"] and not legend_fish:
        grade = "special"
    elif legend_fish:
        w = c["legend_fish_grades"]
        grade = rnd.choices(list(w), list(w.values()))[0]
    else:
        gs = c["grades"]
        grade = rnd.choices([g["id"] for g in gs], [g["weight"] for g in gs])[0]
    # 천장 카운트: 특별 이상이 나오면 특별 카운트 초기화, 전설이 나오면 둘 다 초기화
    pity["special"] = 0 if grade in ("special", "legend") else pity["special"] + 1
    pity["legend"] = 0 if grade == "legend" else pity["legend"] + 1
    return grade


def roll_drop(save, fish: dict, rank: str, rnd=random, bonus: float = 0.0) -> str | None:
    """포획 1회의 상자 드랍. 얻으면 등급을 돌려주고 인벤토리에 넣는다. bonus = 광폭 변이 +2%p."""
    if rnd.random() >= drop_chance(fish, rank, bonus):
        return None
    grade = _roll_grade(save, rnd, fish["rarity"] == "legend")
    give_chest(save, grade)
    return grade


def give_chest(save, grade: str, n: int = 1) -> None:
    save.data["chests"][grade] = save.data["chests"].get(grade, 0) + n


def _spot_avg_price(spot: str) -> float:
    prices = [f["base_price"] for f in all_fish() if f["spot"] == spot and f["rarity"] != "legend"]
    return sum(prices) / len(prices) if prices else 50


def give_item(save, item_id: str) -> dict:
    """아이템 지급. 고유 아이템을 이미 가졌으면 조각으로 바꾼다. 돌려주는 값: 보상 설명."""
    it = item_info(item_id)
    items = save.data["items"]
    tdex = save.data["treasure_dex"]
    tdex[item_id] = tdex.get(item_id, 0) + 1
    if it["kind"] == "consumable":
        items["consumables"][item_id] = items["consumables"].get(item_id, 0) + 1
        return {"type": "item", "item": it, "dup": False}
    if item_id in items["owned"]:
        n = cfg()["shards"][it["grade"]]
        save.data["shards"] += n
        return {"type": "item", "item": it, "dup": True, "shards": n}
    items["owned"].append(item_id)
    items.setdefault("origin", {})[item_id] = save.data.get("continent", "sharmion")  # 특별 장비 기준 대륙
    return {"type": "item", "item": it, "dup": False}


def open_chest(save, grade: str, spot: str, rnd=random) -> dict | None:
    """상자 1개 개봉 → 보상 dict (type: gold / materials / item)."""
    chests = save.data["chests"]
    if chests.get(grade, 0) <= 0:
        return None
    chests[grade] -= 1
    save.data["stats"]["chests_opened"] = save.data["stats"].get("chests_opened", 0) + 1
    table = cfg()["contents"][grade]
    pick = rnd.choices(table, [e["w"] for e in table])[0]
    if pick["type"] == "gold":
        amount = int(round(_spot_avg_price(spot) * pick["mult"] * rnd.uniform(0.8, 1.2)))
        amount = max(10, amount)
        save.data["money"] += amount
        return {"type": "gold", "amount": amount, "grade": grade}
    if pick["type"] == "materials":
        cont = spot_continent(spot)
        n = rnd.randint(*pick["n"])
        mats = save.data["materials"]
        mats[cont] = mats.get(cont, 0) + n
        rare = pick.get("rare", 0)
        mats["rare"] = mats.get("rare", 0) + rare
        return {"type": "materials", "continent": cont, "n": n, "rare": rare, "grade": grade}
    it = rnd.choice(items_of(pick["grade"]))
    return give_item(save, it["id"]) | {"grade": grade}


def exchange_cost(item_id: str) -> int:
    return cfg()["exchange"][item_info(item_id)["grade"]]


def can_exchange(save, item_id: str) -> str | None:
    """교환할 수 없으면 이유."""
    it = item_info(item_id)
    if it["kind"] != "consumable" and item_id in save.data["items"]["owned"]:
        return "이미 가지고 있어요"
    if save.data["shards"] < exchange_cost(item_id):
        return "조각이 부족해요"
    return None


def exchange(save, item_id: str) -> bool:
    if can_exchange(save, item_id):
        return False
    save.data["shards"] -= exchange_cost(item_id)
    give_item(save, item_id)
    return True
