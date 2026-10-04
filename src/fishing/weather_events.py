"""특별한 날씨 이벤트 (DESIGN.md 35-4·35-14, CONTENT_EXPANSION.md C-2): 유성우 밤 · 쌍무지개 · 붉은 달 · 은빛 안개.

게임 하루가 시작될 때 하루 1개 이하를 계획(plan)하고, 그 시작 시각에 조건(날씨·비 그친 낮)을 확인해 열린다(active).
저장: save.data["events"] = {day, plan:{id,start}, active:{id,day,start,end}, seen:{id: 횟수}, rained:day}.
환상 확률·천장과 무관 (환상 팔레트가 이벤트 색감보다 우선 — 그리기 순서).
"""
import random

from src.core.config import load_json

_RNG = random.Random()


def cfg() -> dict:
    return load_json("weather_events.json")


def by_id(eid: str) -> dict | None:
    return next((e for e in cfg()["events"] if e["id"] == eid), None)


def state(save) -> dict:
    st = save.data.setdefault("events", {})
    st.setdefault("day", -1)
    st.setdefault("plan", None)
    st.setdefault("active", None)
    st.setdefault("seen", {})
    st.setdefault("rained", -1)
    return st


def _abs_hour(day: int, hour: float) -> float:
    return day * 24.0 + hour


def active(save) -> dict | None:
    """진행 중인 이벤트 (data 항목 + 남은 시간). 없으면 None."""
    if save is None:
        return None
    a = state(save).get("active")
    if not a:
        return None
    ev = by_id(a["id"])
    return dict(ev, **{"_end": a["end"]}) if ev else None


def tick(save, day: int, hour: float, weather: str, rnd=_RNG) -> str | None:
    """시간이 흐를 때마다 (낚시터·마을). 새로 시작한 이벤트 id 를 돌려준다 (배너용)."""
    st = state(save)
    now = _abs_hour(day, hour)
    if weather in ("rain", "storm") and 6 <= hour <= 18:
        st["rained"] = day
    a = st.get("active")
    if a and (now >= a["end"] or now < a["start"] - 1):
        st["active"] = None
    if st["day"] != day:   # 새 하루: 오늘 계획 (하루 1개 이하)
        st["day"] = day
        st["plan"] = None
        r = rnd.random()
        acc = 0.0
        for e in cfg()["events"]:
            acc += e["day_chance"]
            if r < acc:
                st["plan"] = {"id": e["id"], "start": e["start"]}
                break
    p = st.get("plan")
    if p and not st.get("active") and hour >= p["start"]:
        st["plan"] = None
        ev = by_id(p["id"])
        need = ev.get("need", {})
        ok = weather in need.get("weather", [weather])
        if need.get("rained_today") and st.get("rained") != day:
            ok = False
        if ok:
            return start(save, ev["id"], day, hour)
    return None


def start(save, eid: str, day: int, hour: float) -> str:
    ev = by_id(eid)
    st = state(save)
    st["active"] = {"id": eid, "day": day, "start": _abs_hour(day, hour), "end": _abs_hour(day, hour) + ev["hours"]}
    st["seen"][eid] = st["seen"].get(eid, 0) + 1
    return eid


def stop(save) -> None:
    state(save)["active"] = None


def remaining_hours(save, day: int, hour: float) -> float:
    a = state(save).get("active")
    return max(0.0, a["end"] - _abs_hour(day, hour)) if a else 0.0


def benefit(save, key: str, default=0.0):
    ev = active(save)
    return ev["benefit"].get(key, default) if ev else default


def extra_fish(save, cont: str) -> list:
    """이벤트 물고기 [(물고기, 가중치)] — 이벤트 중에만, 두 대륙 공통 (엘드라시온은 그 대륙 가격)."""
    ev = active(save)
    if not ev or not ev.get("fish"):
        return []
    f = dict(ev["fish"])
    if cont == "eldrasion" and f.get("price_eld"):
        f["base_price"] = f["price_eld"]
    f["continent"] = cont
    return [(f, cfg()["fish_weight"][f["rarity"]])]


def board_line(save, fishing) -> str | None:
    """마을 계절 알림판 한 줄."""
    ev = active(save)
    if ev:
        left = remaining_hours(save, fishing.clock.day, fishing.clock.hour)
        return f"지금: {ev['name']} — {ev['benefit_text']} · {ev['fish']['name']} 출현 (약 {left:.0f}시간 남음)"
    return "오늘은 특별한 날씨 소식이 없어요."
