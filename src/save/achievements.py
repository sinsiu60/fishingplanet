"""업적 (트로피): data/achievements.json. 성능 보상 없음 — 기록과 작은 알림만.

저장: save.data["achievements"] = {"got": {id: 게임 날짜}, "toasts": [아직 안 보여 준 id]}.
기존 세이브(이 칸이 없음)는 처음 확인할 때 이미 이룬 업적을 알림 없이 기록한다 (소급).
환상 업적은 환상 튜토리얼 전엔 목록에도 보이지 않는다 (환상 비밀).
"""
from src.core.config import load_json


def cfg() -> dict:
    return load_json("achievements.json")


def state(save) -> dict:
    first = "achievements" not in save.data
    st = save.data.setdefault("achievements", {})
    st.setdefault("got", {})
    st.setdefault("toasts", [])
    if first:
        st["_silent"] = True
    return st


def _phantom_open(save) -> bool:
    from src.fishing import phantom
    return bool(phantom.state(save)["tutorial"])


def visible(save) -> list[dict]:
    show_ph = _phantom_open(save)
    return [a for a in cfg()["list"] if show_ph or not a.get("hidden_until_phantom")]


def value(save, a: dict) -> int:
    """그 업적의 지금 값 (진행 막대용)."""
    d = save.data
    t, arg = a["type"], a.get("arg")
    st = d.get("stats", {})
    if t in ("catches", "s_ranks", "perfects", "earned"):
        return int(st.get(t, 0))
    if t == "mutation_dex":
        from src.fishing import mutation
        return mutation.dex_count(save)
    if t == "dex_pct":
        got, total = save.continent_dex(arg)
        return got * 100 // total if total else 0
    if t == "dex_points":
        from src.save import dexbook
        return dexbook.points(save)
    if t == "mastery_max":
        from src.save import dexbook
        return max((dexbook.mastery(save, f) for f in dexbook.all_species() if dexbook.entry(save, f)), default=0)
    if t == "seasonal_caught":
        return sum(1 for f in load_json("seasonal_fish.json")["fish"] if save.caught(f["id"]))
    if t in ("legends", "legends_cont"):
        from src.save.save_game import spot_continent
        return sum(1 for f in load_json("fish.json")["fish"] if f["rarity"] == "legend" and save.caught(f["id"])
                   and (t == "legends" or spot_continent(f["spot"]) == arg))
    if t == "caught":
        return 1 if save.caught(arg) else 0
    if t == "spots_cont":
        ids = {s["id"] for s in load_json("spots.json")["spots"] if s.get("continent", "sharmion") == arg}
        return len(ids & set(d.get("unlocked_spots", [])))
    if t == "spots_all":
        return len(set(d.get("unlocked_spots", [])))
    if t == "continent":
        return 1 if arg in d.get("unlocked_continents", []) else 0
    if t == "events_seen":
        return sum(1 for v in d.get("events", {}).get("seen", {}).values() if v)
    if t == "rod_tier":
        from src.save.save_game import equipment
        return max((g["tier"] for g in equipment()["rod"] if save.owns("rod", g["id"])), default=0)
    if t == "quests_done":
        return int(d.get("quests", {}).get("done", 0))
    if t == "prints":
        return len(d.get("prints", {}))
    if t == "phantoms":
        from src.fishing import phantom
        return len(phantom.state(save).get("caught", {}))
    return 0


def check(save) -> list[str]:
    """새로 이룬 업적 id (알림 대기열에도 넣음). 처음(소급)엔 알림 없이 기록만."""
    st = state(save)
    silent = st.pop("_silent", False)
    day = save.data.get("day", 0)
    new = []
    for a in visible(save):
        if a["id"] in st["got"]:
            continue
        try:
            ok = value(save, a) >= a["goal"]
        except (KeyError, TypeError, ValueError, StopIteration):
            ok = False
        if ok:
            st["got"][a["id"]] = day
            new.append(a["id"])
    if not silent:
        st["toasts"] += new
    return new


_ACC = {"t": 0.0}


def tick(save, dt: float) -> None:
    """2초마다 확인 (낚시터·마을 화면 갱신에서)."""
    _ACC["t"] += dt
    if _ACC["t"] >= 2.0 and save is not None:
        _ACC["t"] = 0.0
        check(save)


def pop_toast(save) -> dict | None:
    st = state(save)
    while st["toasts"]:
        aid = st["toasts"].pop(0)
        a = next((x for x in cfg()["list"] if x["id"] == aid), None)
        if a:
            return a
    return None


def by_id(aid: str) -> dict | None:
    return next((a for a in cfg()["list"] if a["id"] == aid), None)
