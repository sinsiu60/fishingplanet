"""환상의 물고기 (DESIGN.md 33장, PHANTOM_FISH.md): 데이터·등장 판정·천장·세이브 기록.

data/phantom.json 에 따로 두므로 fish.json 을 도는 도감 %·해금·의뢰·변이 집계에 들어가지 않는다.
등장 판정은 찌가 착수하는 순간 (낚시 씬 _splash) — 판정되면 그 캐스팅은 가짜 입질 없이 환상어 진짜 입질.
"""
import random

from src.core.config import load_json

COLOR = (190, 120, 255)        # 환상 보라 (테두리·카드·탭)
COLOR_LIGHT = (225, 180, 255)  # 연보라 (대사·강조)
LINE = "물결이 숨을 죽인다"
LOST_LINE = "보라빛 잔상이 깊은 곳으로 사라졌다"


def cfg() -> dict:
    return load_json("phantom.json")


def spawn_cfg() -> dict:
    return cfg()["spawn"]


def all_phantoms() -> list[dict]:
    return cfg()["fish"]


def by_id(fid: str) -> dict | None:
    return next((f for f in all_phantoms() if f["id"] == fid), None)


def for_spot(spot: str) -> dict | None:
    return next((f for f in all_phantoms() if f["spot"] == spot), None)


def is_phantom(fish: dict | None) -> bool:
    return bool(fish) and fish.get("rarity") == "phantom"


def state(save) -> dict:
    """세이브 data['phantom'] (옛 세이브는 _deep_merge 가 기본값으로 채움)."""
    ph = save.data.setdefault("phantom", {})
    for k, v in (("casts", {}), ("caught", {}), ("tutorial", False), ("notes", []), ("scales", 0), ("rewards", []),
                 ("title_frame", False)):
        ph.setdefault(k, v if not isinstance(v, (dict, list)) else type(v)())
    return ph


def legend_caught(save, spot: str) -> bool:
    return any(f["spot"] == spot and f["rarity"] == "legend" and save.caught(f["id"])
               for f in load_json("fish.json")["fish"])


def chance(save, spot: str) -> float:
    """이번 착수의 환상 확률: 기본 0.5% / 그 낚시터 전설을 잡았으면 2%, 천장 이후 착수마다 +0.05%p (최대 5%)."""
    c = spawn_cfg()
    leg = legend_caught(save, spot)
    p = c["legend_chance"] if leg else c["base_chance"]
    n = state(save)["casts"].get(spot, 0)
    after = c["pity_after_legend"] if leg else c["pity_after"]
    if n > after:
        p = min(c["pity_max"], p + c["pity_step"] * (n - after))
    return p


def pity_frac(save, spot: str) -> float:
    """천장 진행도 0~1 (환상의 눈 눈금·먼 수면 보라 물결 빈도). 천장 시작까지 0→0.5, 최대 확률까지 0.5→1."""
    c = spawn_cfg()
    leg = legend_caught(save, spot)
    after = c["pity_after_legend"] if leg else c["pity_after"]
    n = state(save)["casts"].get(spot, 0)
    if n <= after:
        return 0.5 * n / after
    base = c["legend_chance"] if leg else c["base_chance"]
    full = (c["pity_max"] - base) / c["pity_step"]
    return min(1.0, 0.5 + 0.5 * (n - after) / max(1.0, full))


def roll(save, spot: str, rnd=random, force: bool = False) -> dict | None:
    """착수 순간 판정. 나오면 그 환상어, 아니면 None (착수 수 +1)."""
    fish = for_spot(spot)
    if fish is None:
        return None
    if force or rnd.random() < chance(save, spot):
        return fish
    casts = state(save)["casts"]
    casts[spot] = casts.get(spot, 0) + 1
    return None


def reset_pity(save, spot: str) -> None:
    """환상어와 파이팅까지 갔다 (잡든 놓치든) → 그 낚시터 천장 카운트 0."""
    state(save)["casts"][spot] = 0


def caught_ids(save) -> list[str]:
    return [fid for fid, e in state(save)["caught"].items() if e.get("count", 0) > 0]


def caught(save, fid: str) -> bool:
    return state(save)["caught"].get(fid, {}).get("count", 0) > 0


def record(save, result: dict) -> dict:
    """포획 기록 (환상 도감). 돌려줌: {'new': 그 종 첫 포획, 'first_ever': 환상어 첫 포획}."""
    ph = state(save)
    fid = result["fish"]["id"]
    first_ever = not caught_ids(save)
    e = ph["caught"].setdefault(fid, {"count": 0, "max_size": 0.0, "best_rank": "C"})
    new = e["count"] == 0
    e["count"] += 1
    e["max_size"] = max(e["max_size"], result["size"])
    order = "CBAS"
    if order.index(result["rank"]) > order.index(e["best_rank"]) or new:
        e["best_rank"] = result["rank"] if new or order.index(result["rank"]) > order.index(e["best_rank"]) else e["best_rank"]
    return {"new": new, "first_ever": first_ever}


def continent_of(spot: str) -> str:
    sp = next((s for s in load_json("spots.json")["spots"] if s["id"] == spot), {})
    return sp.get("continent", "sharmion")
