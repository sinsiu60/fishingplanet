"""캐치 랭크와 판매가 (DESIGN.md 2-5)."""
from src.core.config import load_json


def par_time(cast_distance: float, stamina: float) -> float:
    f = load_json("fishing_config.json")["fight"]
    return f["par_base_sec"] + f["par_per_meter"] * cast_distance + f["par_per_stamina"] * stamina


def compute_score(perfects: int, misses: int, line_damage: float, elapsed: float, par: float) -> dict:
    r = load_json("fishing_config.json")["rank"]
    perfect_pts = min(r["perfect_max"], perfects * r["per_perfect"])
    line_pts = (1.0 - max(0.0, min(1.0, line_damage))) * r["line_weight"]
    if elapsed <= par:
        time_pts = r["time_weight"]
    else:
        time_pts = max(0.0, r["time_weight"] * (1.0 - (elapsed - par) / par))
    miss_pts = -misses * r["per_miss"]
    score = r["base"] + perfect_pts + line_pts + time_pts + miss_pts
    if score >= r["S"]:
        rank = "S"
    elif score >= r["A"]:
        rank = "A"
    elif score >= r["B"]:
        rank = "B"
    else:
        rank = "C"
    return {"score": score, "rank": rank, "perfect_pts": perfect_pts, "line_pts": line_pts,
            "time_pts": time_pts, "miss_pts": miss_pts}


def final_size(size_cm: float, rank: str) -> float:
    r = load_json("fishing_config.json")["rank"]
    return round(size_cm * (1 + r["s_size_bonus"]), 1) if rank == "S" else size_cm


def sell_price(fish: dict, size_cm: float, rank: str) -> int:
    r = load_json("fishing_config.json")["rank"]
    lo, hi = fish["size_cm"]
    avg = (lo + hi) / 2
    return max(1, round(fish["base_price"] * (size_cm / avg) * r["price_mult"][rank]))
