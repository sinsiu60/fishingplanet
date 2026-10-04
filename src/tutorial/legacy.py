"""기존 세이브 (TUTORIAL.md 데이터·저장): 이미 그 시스템을 쓴 기록이 있으면 튜토리얼 완료 처리.

패턴 튜토리얼은 숙련도가 '처음'(첫 단계)이 아닌 패턴만. 모두 '튜토리얼 다시 보기'에서 다시 실행할 수 있다.
"""
from src.core.config import load_json


def _first_tier() -> int:
    tiers = [n for n, _ in load_json("signals.json")["mastery"]["tiers"] if n > 0]
    return min(tiers) if tiers else 1


def done_from(data: dict) -> list[str]:
    tuts = load_json("tutorials.json")["tutorials"]
    st = data.get("stats", {})
    catches = st.get("catches", 0)
    story = data.get("story", {})
    seen_story = story.get("seen_scenes", []) if isinstance(story, dict) else []
    owned = data.get("owned", {})
    used = {
        "TG-01": catches > 0, "TG-02": catches > 0, "TG-03": catches > 0,
        "TG-04": catches >= 3 or bool(data.get("dex_book", {}).get("seen")),
        "TG-05": bool(data.get("patterns_seen")),
        "TG-06": st.get("earned", 0) > 0,
        "TG-07": any(len(v) > 1 for v in owned.values() if isinstance(v, list)),
        "TG-08": catches >= 2,
        "TG-09": catches >= 5,
        "TG-10": st.get("chests_opened", 0) > 0,
        "TG-11": data.get("quests", {}).get("done", 0) > 0 or bool(data.get("quests", {}).get("boards")),
        "TG-12": bool(data.get("enhance")),
        "TG-13": catches >= 2,
        "TG-14": bool(seen_story),
        "TG-15": data.get("season_seen") is not None,
        "TG-16": bool(data.get("events", {}).get("seen")),
        "TG-17": st.get("mutations_caught", 0) > 0,
        "TG-18": bool(data.get("float", {}).get("owned")),
        "TG-PH": bool(data.get("phantom", {}).get("caught")),
    }
    eldra = "eldrasion" in data.get("unlocked_continents", []) and data.get("flags", {}).get("eldra_escape_tutorial")
    mastery = data.get("pattern_mastery", {})
    first = _first_tier()
    out = []
    for tid, tut in tuts.items():
        if tid.startswith("TG-P") and tid != "TG-PH":
            pid = tut.get("start", "").split(":")[-1]
            if mastery.get(pid, 0) >= first:
                out.append(tid)
        elif tid.startswith("TG-19"):
            if eldra:
                out.append(tid)
        elif used.get(tid):
            out.append(tid)
    return out


def migrate(data: dict) -> None:
    if "tutorial" in data:
        return
    data["tutorial"] = {"done": done_from(data), "active": None, "enabled": True, "replay": []}
