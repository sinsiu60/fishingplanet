"""특급 배송 시스템: 판매는 하루네 낚시점·엘라 공방에서만 — 이걸 사면 야외(낚시터·마을)에서도 '일괄 판매'를 하루 n번 할 수 있다.

단계 1 = 구매 (5,000원), 강화할 때마다 하루 횟수 +1 (최대 5단계 = 5번). 강화 비용 10,000 → 20,000 → 40,000 → 80,000원.
횟수는 게임 날짜(save.data["day"])가 바뀌면 다시 가득 찬다. 세이브: data["delivery"] = {"level", "day", "used"}.
"""
BUY_PRICE = 5000
UPGRADE = [10000, 20000, 40000, 80000]   # 1→2, 2→3, 3→4, 4→5
MAX_LEVEL = 5


def state(save) -> dict:
    d = save.data.setdefault("delivery", {})
    d.setdefault("level", 0)
    d.setdefault("day", -1)
    d.setdefault("used", 0)
    return d


def level(save) -> int:
    return int(state(save)["level"])


def _today(save) -> int:
    return int(save.data.get("day", 1))


def uses_left(save) -> int:
    d = state(save)
    if d["day"] != _today(save):
        return d["level"]
    return max(0, d["level"] - d["used"])


def use(save) -> None:
    d = state(save)
    if d["day"] != _today(save):
        d["day"], d["used"] = _today(save), 0
    d["used"] += 1


def next_cost(save) -> int | None:
    lv = level(save)
    if lv >= MAX_LEVEL:
        return None
    return BUY_PRICE if lv == 0 else UPGRADE[lv - 1]


def upgrade(save) -> str:
    """구매(0→1) 또는 강화. 'ok' · 'money' · 'max'."""
    cost = next_cost(save)
    if cost is None:
        return "max"
    if save.data["money"] < cost:
        return "money"
    save.data["money"] -= cost
    state(save)["level"] += 1
    return "ok"
