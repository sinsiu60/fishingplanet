"""변이 물고기 (DESIGN.md 27-4, Phase U5). 수치는 data/mutations.json.

챔질 순간 roll()로 변이를 정하고, apply()가 물고기 데이터 사본에 효과를 입힌다 (원본은 그대로).
  거대  크기·힘·체력·그림자 ↑, 판매가 ×3        광폭  예고 ×0.7(최소 0.4초)·지침 ×0.6, 상자 +2%p
  교활  가짜 예고 +0.25, 분해 소재 ×2             투명  그림자 15%, 예고 소리 크게 + 자막
  황금  바늘 빠짐 ×1.5, 판매가 ×4.5              쌍둥이 두 마리가 번갈아 당김, 2마리 획득 (Fight)
  각성  다음 낚시터의 새 패턴 하나, 소재 +3
표시: 이름 앞에 변이 이름 ("거대 · 교활 붕어"), 몸·지느러미 색, 그림자 크기·투명도·빛.
"""
import random
import time

from src.core.config import load_json

ORDER = ("giant", "frenzy", "cunning", "clear", "golden", "twin", "awake")
# 변이 전용 난수: 다른 난수 흐름(입질·물고기 행동)을 건드리지 않게 따로, 씨앗은 시계에서 (리플레이는 시계가 고정이라 결정적)
_RNG = random.Random(int(time.time() * 1000))


def cfg() -> dict:
    return load_json("mutations.json")


def unlocked(save) -> bool:
    return cfg()["unlock_spot"] in save.data.get("unlocked_spots", [])


def roll(save, fish: dict, weather: str, rnd=_RNG, force: list | None = None, chance_mult: float = 1.0) -> list[str]:
    """이번 물고기의 변이 (없으면 빈 목록). force = 테스트용 강제 지정, chance_mult = 반짝이는 물결(수면 징후)."""
    if force is not None:
        return [m for m in force if m in ORDER]
    c = cfg()
    if fish.get("rarity") in ("legend", "phantom") or not unlocked(save):
        return []
    k = (c["storm_mult"] if weather == "storm" else 1.0) * chance_mult
    r = rnd.random()
    n = 2 if r < c["chance_two"] * k else 1 if r < (c["chance_two"] + c["chance_one"]) * k else 0
    names = list(c["kinds"])
    weights = [c["kinds"][m]["weight"] for m in names]
    out: list[str] = []
    while len(out) < n:
        m = rnd.choices(names, weights)[0]
        if m not in out:
            out.append(m)
    return sorted(out, key=ORDER.index)


def label(muts: list[str]) -> str:
    """"거대 · 교활" (없으면 "")."""
    kinds = cfg()["kinds"]
    return " · ".join(kinds[m]["name"] for m in muts)


def awake_pattern(fish: dict, rnd=_RNG) -> str:
    """각성: 다음 낚시터의 새 패턴 (마지막 낚시터면 같은 대륙 패턴 중 무작위).
    이중 패턴은 세계수·전설 마지막 페이즈 전용이라(31장 C4) 각성으로는 주지 않는다 — 대신 같은 대륙 다른 패턴."""
    c = cfg()
    spot = fish.get("spot")
    for order in c["spot_order"].values():
        if spot in order:
            pool = [p for s in order for p in c["spot_patterns"].get(s, []) if p != "dual"]
            i = order.index(spot)
            if i + 1 < len(order):
                nxt = [p for p in c["spot_patterns"][order[i + 1]] if p != "dual"]
                return rnd.choice(nxt or pool)
            return rnd.choice(pool)
    return "shake"


def _scale_pair(pair, k: float) -> list[float]:
    return [round(v * k, 3) for v in pair]


def apply(fish: dict, muts: list[str], rnd=_RNG) -> dict:
    """변이 효과를 입힌 물고기 사본. muts가 비면 원본 그대로 돌려준다."""
    if not muts:
        return fish
    c = cfg()["kinds"]
    f = dict(fish)
    f["mutations"] = list(muts)
    f["base_name"] = fish["name"]
    f["name"] = f"{label(muts)} {fish['name']}"
    f["colors"] = dict(fish.get("colors") or {})
    f["actions"] = dict(fish.get("actions", {}))
    if fish.get("phases"):
        f["phases"] = [dict(p) for p in fish["phases"]]
    if "giant" in muts:
        g = c["giant"]
        f["power"] = fish.get("power", 1.0) * g["power_mult"]
        f["stamina"] = fish.get("stamina", 100) * g["stamina_mult"]
        f["shadow_len_m"] = fish["shadow_len_m"] * g["shadow_mult"]
    if "frenzy" in muts:
        g = c["frenzy"]
        f["telegraph_sec"] = max(g["min_telegraph"], fish.get("telegraph_sec", 1.0) * g["telegraph_mult"])
        base_tired = fish.get("tired_sec") or load_json("fishing_config.json")["fish_ai"]["tired_sec"]
        f["tired_sec"] = _scale_pair(base_tired, g["tired_mult"])
        f["colors"]["eye"] = g["color"]
    if "cunning" in muts:
        f["fake_cue"] = fish.get("fake_cue", 0.0) + c["cunning"]["fake_cue_add"]
        f["fake_rush"] = fish.get("fake_rush", 0.0) + load_json("signals.json")["rush_pulse"]["cunning_fake_rush"]
        f["colors"]["fin"] = c["cunning"]["color"]
    if "golden" in muts:
        f["hook_mult"] = c["golden"]["hook_mult"]
        f["colors"]["body"] = [235, 185, 60]
        f["colors"]["belly"] = [255, 235, 150]
        f["colors"]["fin"] = [200, 150, 40]
    if "clear" in muts:
        f["shadow_alpha"] = c["clear"]["shadow_alpha"]
    if "twin" in muts:
        f["twin"] = True
        f["stamina"] = f.get("stamina", 100) * c["twin"]["stamina_mult"]
    if "awake" in muts:
        p = awake_pattern(fish, rnd)
        f["awake_pattern"] = p
        w = c["awake"]["pattern_weight"]
        if p == "fake":
            f["fake_tired"] = max(fish.get("fake_tired", 0.0), 0.5)
        else:
            f["actions"][p] = w
            for ph in f.get("phases", []):
                if "actions" in ph:
                    ph["actions"] = dict(ph["actions"], **{p: w})
    return f


def price(base_price: int, muts: list[str]) -> int:
    """판매가 배율 (거대는 '크기 효과 포함 총 ×3'이라 Fight가 원래 크기로 계산한 값을 받는다)."""
    c = cfg()["kinds"]
    k = 1.0
    if "giant" in muts:
        k *= c["giant"]["price_total_mult"]
    if "golden" in muts:
        k *= c["golden"]["price_mult"]
    return int(round(base_price * k))


def dex_count(save) -> int:
    return sum(len(v) for v in save.data.get("mutation_dex", {}).values())


def record(save, fish_id: str, muts: list[str]) -> list[dict]:
    """변이 도감 기록. 새로 넘은 수집 보상 목록을 돌려주고 지급한다."""
    md = save.data.setdefault("mutation_dex", {})
    before = dex_count(save)
    got = md.setdefault(fish_id, [])
    for m in muts:
        if m not in got:
            got.append(m)
    after = dex_count(save)
    out = []
    for rw in cfg()["dex_rewards"]:
        if before < rw["count"] <= after:
            _grant(save, rw)
            out.append(rw)
    return out


def _grant(save, rw: dict) -> None:
    cos = save.data.setdefault("cosmetics", {"titles": [], "float_skins": [], "rod_skins": []})
    if rw["kind"] == "title":
        cos.setdefault("titles", []).append(rw["id"])
    elif rw["kind"] == "float_skin":
        cos.setdefault("float_skins", []).append(rw["id"])
    elif rw["kind"] == "chest":
        from src.save import treasure
        treasure.give_chest(save, rw["id"])
