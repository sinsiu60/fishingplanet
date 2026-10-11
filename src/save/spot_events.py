"""낚시터 사건 — 낚시터마다 한 번 (JOURNEY.md 🅰, DESIGN 54-4). 데이터는 data/spot_events.json.

그 낚시터에서 물고기를 at[0]~at[1] 마리째(낚시터마다 고정) 잡은 뒤 결과 카드를 닫으면 사건 연출(src/render/spot_events.py) →
보상 · 일지 한 줄. 옛 세이브는 이 칸이 생긴 뒤부터 세므로 다음 방문 때 한 번.
저장: save.data["spot_events"] = {"seen": [낚시터], "count": {낚시터: 마리}, "next_min": 등급 또는 None,
"rare_until": 플레이 초, "rare_mult": 배수, "hints": [전설 id], "keep": [기념품 id], "shots": {낚시터: 그림 파일}}.
"""
import zlib

from src.core.config import load_json

RANK = {"common": 0, "uncommon": 1, "rare": 2}


def cfg() -> dict:
    return load_json("spot_events.json")


def event(spot_id: str) -> dict | None:
    return cfg()["events"].get(spot_id)


def state(save) -> dict:
    st = save.data.setdefault("spot_events", {})
    st.setdefault("seen", [])
    st.setdefault("count", {})
    st.setdefault("next_min", None)
    st.setdefault("rare_until", 0.0)
    st.setdefault("rare_mult", 1.0)
    st.setdefault("hints", [])
    st.setdefault("keep", [])
    st.setdefault("shots", {})
    return st


def seen(save, spot_id: str) -> bool:
    return spot_id in state(save)["seen"]


def trigger_at(spot_id: str) -> int:
    """그 낚시터의 사건 마리 수 (at 범위 안에서 낚시터마다 고정)."""
    lo, hi = cfg()["at"]
    return lo + zlib.crc32(spot_id.encode()) % (hi - lo + 1)


def on_catch(save, spot_id: str) -> None:
    """그 낚시터에서 한 마리 잡음 (시험 · 훈련 · 대본 판은 부르지 않음)."""
    if event(spot_id) is None or seen(save, spot_id):
        return
    c = state(save)["count"]
    c[spot_id] = int(c.get(spot_id, 0)) + 1


def _after_ok(save, ev: dict) -> bool:
    need = ev.get("after")
    if not need:
        return True
    from src.story import story
    if not story.active(save):
        return True
    need = [need] if isinstance(need, str) else need
    return any(story.seen(save, sid) for sid in need)


def due(save, spot_id: str) -> dict | None:
    """지금 시작할 사건 (없으면 None)."""
    ev = event(spot_id)
    if ev is None or seen(save, spot_id):
        return None
    if int(state(save)["count"].get(spot_id, 0)) < trigger_at(spot_id):
        return None
    return ev if _after_ok(save, ev) else None


def finish(save, spot_id: str, playtime: float, day: int, season: str) -> list[str]:
    """사건 끝 (건너뛰어도): 본 것으로 + 보상 + 일지 한 줄. 돌려줌: 알림 문장들."""
    ev = event(spot_id)
    st = state(save)
    if ev is None or spot_id in st["seen"]:
        return []
    st["seen"].append(spot_id)
    rw = ev.get("reward", {})
    out = [ev.get("toast", ev["name"])]
    if rw.get("next"):
        cur = st["next_min"]
        if cur is None or RANK[rw["next"]] > RANK[cur]:
            st["next_min"] = rw["next"]
    if rw.get("rare_mult"):
        st["rare_mult"] = float(rw["rare_mult"])
        st["rare_until"] = playtime + 60.0 * float(rw.get("rare_min", 10))
    if rw.get("hint") and rw["hint"] not in st["hints"]:
        st["hints"].append(rw["hint"])
    if rw.get("keep") and rw["keep"] not in st["keep"]:
        st["keep"].append(rw["keep"])
    if rw.get("float_skin"):
        from src.save import quests
        cos = quests.cosmetics(save)["float_skins"]
        if rw["float_skin"] not in cos:
            cos.append(rw["float_skin"])
    if rw.get("mark"):
        from src.render import grandpa_marks
        res = grandpa_marks.find(save, spot_id, day, season)
        if res is not None:
            out.append(f"해강의 흔적 {res['n']}/{res['total']}")
    from src.story import story
    if story.active(save):
        sst = story.state(save)
        if not any(e.get("id") == ev["id"] for e in sst["journal"]):
            sst["journal"].append({"id": ev["id"], "text": ev["journal"], "day": int(day), "season": season})
    return out


# ── 보상 효과 (입질 고르기) ──
def take_next_min(save) -> str | None:
    """다음 한 마리 최소 등급 — 고른 뒤 한 번 쓰면 사라짐 (bite 가 실제로 쓸 때 consume_next_min)."""
    return state(save)["next_min"]


def consume_next_min(save) -> None:
    state(save)["next_min"] = None


def rare_mult(save, playtime: float) -> float:
    st = state(save)
    return float(st["rare_mult"]) if playtime < float(st["rare_until"]) else 1.0


def rare_left(save, playtime: float) -> float:
    return max(0.0, float(state(save)["rare_until"]) - playtime)


def hinted(save, fish_id: str) -> bool:
    return fish_id in state(save)["hints"]


def keepsakes(save) -> list[str]:
    names = cfg()["keepsakes"]
    return [names[k] for k in state(save)["keep"] if k in names]
