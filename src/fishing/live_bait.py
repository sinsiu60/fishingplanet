"""먹이사슬 (CORE_UPDATE.md CU7-2, data/live_bait.json).

생미끼 = 살림망 물고기를 미끼로 끼운 것 (세이브 live_bait). 끼우면 영구 미끼 효과는 꺼지고, 다 쓰면 원래 미끼로 자동 복귀.
  일반 생미끼: 1마리 = 입질 3번 (물렸을 때만 1번 줄어듦), 사슬표의 노리는 희귀 가중치 ×3.
  희귀 생미끼: 1마리 = 입질 1번. 지금 끼운 영구 미끼 위에 '덧붙임' — 끼운 미끼가 그 전설의 전용 미끼일 때만
              전설 조건 칸 안에서 전설 확률 chance_live_rare (5% → 10%). 다른 미끼 위에선 전설 없음, 그 낚시터 희귀 가중치 ×1.5.
전설 전용 미끼 만들기: craft 의 희귀 1마리 + 지금 가격의 60% (영구).
낚시 화면은 bait_dict() 를 BiteSystem.bait 로 쓰고, 물리면 consume().
"""
from src.core.config import load_json

BLOCK = ("legend", "phantom")


def cfg() -> dict:
    return load_json("live_bait.json")


def state(save) -> dict | None:
    lb = save.data.get("live_bait")
    return lb if lb and lb.get("left", 0) > 0 else None


def usable(entry: dict, fish: dict) -> str | None:
    """살림망 한 칸을 생미끼로 쓸 수 없는 이유 (없으면 None)."""
    if fish.get("rarity") in BLOCK:
        return "전설 · 환상은 미끼로 못 써요"
    if fish.get("rarity") not in ("common", "rare"):
        return "일반 · 희귀만 생미끼가 돼요"
    if entry.get("lock") or entry.get("record"):
        return "잠금 · 신기록 물고기는 못 써요"
    return None


def targets(spot: str, fid: str) -> list[str]:
    """이 낚시터에서 그 일반 생미끼가 노리는 희귀."""
    return cfg()["chain"].get(spot, {}).get(fid, [])


def eaters(fid: str) -> list[str]:
    """도감 '먹는 물고기' 줄: 이 물고기를 노리는 희귀 (모든 낚시터)."""
    out = []
    for chain in cfg()["chain"].values():
        for t in chain.get(fid, []):
            if t not in out:
                out.append(t)
    return out


def prey(fid: str) -> list[str]:
    """도감 '노리는 물고기' 줄: 이 희귀가 좋아하는 일반."""
    out = []
    for chain in cfg()["chain"].values():
        for c, ts in chain.items():
            if fid in ts and c not in out:
                out.append(c)
    return out


def equip(save, index: int) -> str:
    """살림망 index 번 물고기를 생미끼로. 돌려줌: 'ok' 또는 못 쓰는 이유."""
    from src.save.save_game import fish_by_id
    keep = save.data["keepnet"]
    if not 0 <= index < len(keep):
        return "없는 물고기"
    entry = keep[index]
    fish = fish_by_id(entry["id"])
    why = usable(entry, fish)
    if why:
        return why
    c = cfg()
    keep.pop(index)   # 이미 끼워 둔 생미끼가 있으면 남은 입질은 버리고 새것으로
    kind = "common" if fish["rarity"] == "common" else "rare"
    save.data["live_bait"] = {"fish": fish["id"], "kind": kind, "left": c["common_bites"] if kind == "common" else 1}
    return "ok"


def consume(save) -> bool:
    """물렸을 때 한 번 줄어듦. 다 쓰면 원래 미끼로 (True = 방금 다 씀)."""
    lb = state(save)
    if not lb:
        return False
    lb["left"] -= 1
    if lb["left"] <= 0:
        save.data["live_bait"] = None
        return True
    return False


def label(save) -> str | None:
    """화면 미끼 아이콘 옆 "피라미 ×2"."""
    lb = state(save)
    if not lb:
        return None
    from src.save.save_game import fish_by_id
    return f"{fish_by_id(lb['fish'])['name']} ×{lb['left']}"


def bait_dict(save, spot: str) -> dict | None:
    """BiteSystem.bait 로 쓸 생미끼 (영구 미끼 효과 없음 — 티어 0). 생미끼가 없으면 None (= 영구 미끼 그대로)."""
    lb = state(save)
    if not lb:
        return None
    from src.save.save_game import fish_by_id
    fish = fish_by_id(lb["fish"])
    live = {"kind": lb["kind"], "fish": lb["fish"], "targets": targets(spot, lb["fish"]) if lb["kind"] == "common" else []}
    out = {"id": f"live:{lb['fish']}", "name": f"{fish['name']} 생미끼", "tier": 0, "live": live}
    base = save.equipped("bait")
    if lb["kind"] == "rare" and base.get("legend_for"):
        out["legend_for"] = base["legend_for"]   # 전설 미끼 위에 덧붙인 희귀 생미끼만 전설을 부름 (확률 ×2)
    return out


def weight_mult(bait: dict | None, fish: dict) -> float:
    """pick_fish 가중치 배율."""
    live = (bait or {}).get("live")
    if not live:
        return 1.0
    c = cfg()
    if live["kind"] == "common":
        return c["common_target_mult"] if fish["id"] in live["targets"] else 1.0
    return c["rare_spot_mult"] if fish.get("rarity") == "rare" else 1.0


def craft_need(bait: dict) -> str | None:
    """전설 전용 미끼 만들기 재료 희귀 id (만들기 없는 미끼는 None)."""
    return cfg()["craft"].get(bait["id"])


def craft_price(bait: dict) -> int:
    return int(round(bait["price"] * cfg()["craft_price_frac"]))


def craft_index(save, bait: dict) -> int | None:
    """살림망에서 재료로 쓸 수 있는 첫 칸 (잠금 · 신기록 제외)."""
    need = craft_need(bait)
    for i, e in enumerate(save.data["keepnet"]):
        if e["id"] == need and not e.get("lock") and not e.get("record"):
            return i
    return None


def craft(save, bait: dict) -> str:
    """전설 전용 미끼 만들기: 지정 희귀 1마리 + 가격 60%. 돌려줌: 'ok' · 'material' · 'money' · 'already' · 'none'."""
    if craft_need(bait) is None:
        return "none"
    if save.owns("bait", bait["id"]):
        return "already"
    idx = craft_index(save, bait)
    if idx is None:
        return "material"
    price = craft_price(bait)
    if save.data["money"] < price:
        return "money"
    save.data["money"] -= price
    save.data["keepnet"].pop(idx)
    save.data["owned"]["bait"].append(bait["id"])
    save.data["gear"]["bait"] = bait["id"]
    return "ok"
