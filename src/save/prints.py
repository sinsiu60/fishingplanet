"""어탁 기록 (DESIGN.md 35-2): 종마다 최고 기록 1장. 그림은 src/render/fish_print.py 가 기록에서 만든다."""
import time

from src.render.fish_print import cost, print_kind


def all_prints(save) -> dict:
    return save.data.setdefault("prints", {})


def offer(save, fish: dict, size: float) -> dict | None:
    """크기 신기록(첫 포획 포함)이고 지금 어탁보다 크면 제안: {cost, replace(기존 크기 또는 None)}."""
    from src.save import dexbook
    e = dexbook.entry(save, fish)
    if e is None or size + 1e-6 < e.get("max_size", 0):
        return None
    old = all_prints(save).get(fish["id"])
    if old and old["size"] >= size:
        return None
    return {"cost": cost(fish), "replace": old["size"] if old else None}


def make(save, fish: dict, size: float, spot_name: str) -> bool:
    """골드를 내고 어탁을 남긴다 (모자라면 False)."""
    from src.save import dexbook
    c = cost(fish)
    if save.data["money"] < c:
        return False
    save.data["money"] -= c
    all_prints(save)[fish["id"]] = {"size": round(size, 1), "date": time.strftime("%Y.%m.%d"), "spot": spot_name,
                                    "season": fish.get("season"), "kind": print_kind(fish, dexbook.mastery(save, fish))}
    return True
