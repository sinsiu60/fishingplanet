"""캐치 랭크와 판매가 (DESIGN.md 2-5)."""
from src.core.config import load_json


def par_time(cast_distance: float, stamina: float, power: float = 1.0) -> float:
    """기준 시간. 힘센 물고기는 질주로 거리가 벌어지니 더 넉넉하게."""
    f = load_json("fishing_config.json")["fight"]
    power_k = 1 + f["par_power_weight"] * max(0.0, power - 1.0) * 2
    return f["par_base_sec"] + (f["par_per_meter"] * cast_distance + f["par_per_stamina"] * stamina) * power_k


def line_allow(fish: dict) -> float:
    """대형 물고기 예외 (49-4): 드랙을 다 풀어도 남는 무게(drag_floor)가 있는 물고기는 그만큼 줄이 닳는 게 당연 → 봐주는 줄 손상 비율."""
    floor = fish.get("drag_floor", 0.0)
    if floor <= 0:
        return 0.0
    r = load_json("fishing_config.json")["rank"]
    return min(r["heavy_line_allow_max"], floor * r["heavy_line_allow_per_floor"])


def compute_score(opp: dict, misses: int, line_damage: float, elapsed: float, par: float, legend: bool = False,
                  allow: float = 0.0) -> dict:
    """새 랭크 (BAEK_EXAM 🅰-2, DESIGN.md 49-2): 줄 관리 + 시간 + 신호 대응 − 실수, 기본 점수 없음.
    opp = 응답 기회의 {"P": 퍼펙트, "G": 좋음, "M": 놓침}. 신호 대응 = (퍼펙트 + 좋음 × good_credit) / 기회 × signal_max,
    기회가 0번이면 signal_none. S 는 점수 + 퍼펙트 S_min_perfects 번 이상. 전설 · 환상은 좋음을 legend_good_credit 으로 (길게 싸우는 만큼)."""
    r = load_json("fishing_config.json")["rank"]
    dmg = max(0.0, min(1.0, line_damage))
    if allow > 0:   # 대형 물고기: 봐주는 몫을 넘은 손상만 남은 폭에 비례해 (끊기지만 않으면 거의 만점)
        dmg = max(0.0, dmg - allow) / (1.0 - allow)
    line_pts = (1.0 - dmg) * r["line_max"]
    if elapsed <= par:
        time_pts = r["time_max"]
    else:
        time_pts = max(0.0, r["time_max"] * (1.0 - (elapsed - par) / par))
    P, G, M = opp.get("P", 0), opp.get("G", 0), opp.get("M", 0)
    n = P + G + M
    gc = r["legend_good_credit"] if legend else r["good_credit"]
    signal_pts = r["signal_none"] if n == 0 else r["signal_max"] * min(1.0, (P + gc * G) / n)
    # 전설 · 환상: 판이 길어 틈 공략(좋음) · 실수가 많이 쌓임 → 전용 기준 (CU8, 없으면 일반 기준)
    cut = {k: r.get("legend_" + k, r[k]) if legend else r[k] for k in ("S", "A", "B", "per_miss")}
    miss_pts = -misses * cut["per_miss"]
    score = line_pts + time_pts + signal_pts + miss_pts
    if score >= cut["S"] and P >= r["S_min_perfects"]:
        rank = "S"
    elif score >= cut["A"]:
        rank = "A"
    elif score >= cut["B"]:
        rank = "B"
    else:
        rank = "C"
    return {"score": score, "rank": rank, "line_pts": line_pts, "time_pts": time_pts, "signal_pts": signal_pts,
            "miss_pts": miss_pts, "opps": n, "perfects": P, "line_allow": allow,
            "s_blocked": score >= cut["S"] and P < r["S_min_perfects"]}   # 점수는 S 인데 퍼펙트가 모자라 A


def final_size(size_cm: float, rank: str) -> float:
    r = load_json("fishing_config.json")["rank"]
    return round(size_cm * (1 + r["s_size_bonus"]), 1) if rank == "S" else size_cm


def sell_price(fish: dict, size_cm: float, rank: str) -> int:
    cfg = load_json("fishing_config.json")
    r = cfg["rank"]
    lo, hi = fish["size_cm"]
    avg = (lo + hi) / 2
    eco = cfg.get("economy", {})   # 경제 맞춤 (CORE_UPDATE CU7-3): 등급 배율 × 낚시터 배율
    k = eco.get("rarity_price_mult", {}).get(fish.get("rarity"), 1.0)
    if fish.get("rarity") not in ("legend", "phantom"):
        k *= eco.get("spot_price_mult", {}).get(fish.get("spot"), 1.0)
    return max(1, round(fish["base_price"] * k * (size_cm / avg) * r["price_mult"][rank]))
