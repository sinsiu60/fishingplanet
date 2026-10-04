"""스토리 상태·조건 (DESIGN.md 36, STORY.md): 막 · 본 장면 · 대기 장면 · 일지 · 휴대폰 · 목표 · 스토리 아이템.

조건은 전부 기존 세이브 기록(해금·포획·방문·환상·엔딩)을 보고 판단한다 (poll) — 스토리 때문에 새로 막히는 곳 없음.
장소에 묶인 장면(interior:<npc>)은 대기열(pending)에 넣고, 그 건물에 들어갈 때 하나씩 재생한다.
컷신(첫 방문 뒤·엔딩 앞뒤)은 그 순간의 신호로 바로 (src/story/runner.py).
저장: save.data["story"] = {player_name, chapter, seen_scenes, pending_scenes, journal, phone_shown, phone_pending,
true_end_choice, items, flags, journal_toasts}.
"""
from src.core.config import load_json

SH_LEGENDS = ("golden_carp", "tiger_mandarin", "silver_bass", "marlin", "coelacanth", "dragon_carp")
# 장소 장면을 재생할 순서 (같은 건물에 여러 개가 대기 중이면 앞의 것부터 — 한 번 들어갈 때 하나)
ORDER = ("NAME", "C1-04", "C1-06", "C2-02", "C2-03", "C2-05", "C3-03", "PH-01", "PH-02",
         "C4-02B", "C4-02A", "C4-03", "C4-04", "C4-05", "C5-03")
PHONES = ("M1", "M2", "M3", "M4", "M5")
DEFAULT_NAME = "하늘"


_GAME = {"g": None}


def bind(game) -> None:
    """게임 시작 때 한 번 (일지 날짜의 계절 = 설정의 계절 고정 반영)."""
    _GAME["g"] = game


def scenes() -> dict:
    return load_json("story/scenes.json")


def scene(sid: str) -> dict:
    return scenes()[sid]


def state(save) -> dict:
    st = save.data.setdefault("story", {})
    st.setdefault("player_name", None)
    st.setdefault("chapter", 0)
    st.setdefault("seen_scenes", [])
    st.setdefault("pending_scenes", [])
    st.setdefault("journal", [])
    st.setdefault("phone_shown", [])
    st.setdefault("phone_pending", [])
    st.setdefault("true_end_choice", None)
    st.setdefault("items", {})
    st.setdefault("flags", {})
    st.setdefault("journal_toasts", [])
    return st


def active(save) -> bool:
    return save is not None and "story" in save.data


def player_name(save) -> str:
    st = save.data.get("story") or {}
    return st.get("player_name") or DEFAULT_NAME


def seen(save, sid: str) -> bool:
    return sid in state(save)["seen_scenes"]


def flag(save, key: str, default=None):
    return state(save)["flags"].get(key, default)


# ───────────────────────── 진행 기록 읽기 ─────────────────────────
def _unlocked(save, spot: str) -> bool:
    return spot in save.data.get("unlocked_spots", [])


def _visited(save, spot: str) -> bool:
    return spot in save.data.get("visited", [])


def _sh_legend(save) -> bool:
    return any(save.caught(f) for f in SH_LEGENDS)


def _phantom(save) -> tuple[bool, int]:
    from src.fishing import phantom
    ps = phantom.state(save)
    return bool(ps["tutorial"]), len(ps.get("caught", {}))


def _catches(save) -> int:
    return int(save.data.get("stats", {}).get("catches", 0))


def _eldra(save) -> bool:
    return "eldrasion" in save.data.get("unlocked_continents", [])


def scene_due(save, sid: str) -> bool:
    """장소 장면의 발생 조건 (STORY.md 각 장면 '조건' 칸 → 게임 신호, DESIGN.md 36-0)."""
    tut, n_ph = _phantom(save)
    fl = state(save)["flags"]
    return {
        "C1-04": _catches(save) >= 1,
        "C1-06": _unlocked(save, "breakwater"),
        "C2-02": save.caught("silver_bass") and not _unlocked(save, "offshore"),
        "C2-03": _unlocked(save, "offshore"),
        "C2-05": _unlocked(save, "deep"),
        "C3-03": seen(save, "C3-02"),
        "C4-02A": bool(fl.get("eldra_escape")),
        "C4-02B": _eldra(save) and not fl.get("eldra_escape"),
        "C4-03": _eldra(save),
        "C4-04": save.caught("prisia"),
        "C4-05": _unlocked(save, "volcano"),
        "C5-03": _unlocked(save, "world_tree"),
        "PH-01": tut,
        "PH-02": tut and n_ph >= 12,
    }.get(sid, False)


JOURNAL_RULES = (   # 상태로 바로 알 수 있는 일지 (나머지는 장면이 끝날 때)
    ("J02", lambda s: _catches(s) >= 1),
    ("J03", _sh_legend),
    ("J05", lambda s: _visited(s, "breakwater")),
    ("J06", lambda s: _unlocked(s, "offshore")),
    ("J07", lambda s: _visited(s, "deep")),
)
PHONE_RULES = (
    ("M1", lambda s: _catches(s) >= 1),
    ("M2", _sh_legend),
    ("M3", lambda s: _visited(s, "breakwater")),
    ("M4", lambda s: _unlocked(s, "offshore")),
    ("M5", lambda s: _visited(s, "deep")),
)


def poll(save) -> None:
    """지금 기록을 보고 대기 장면·일지·휴대폰 대기열을 채운다 (자주 불러도 됨)."""
    if not active(save):
        return
    st = state(save)
    for sid in ORDER:
        if sid == "NAME":
            continue
        if sid in st["seen_scenes"] or sid in st["pending_scenes"]:
            continue
        if scene_due(save, sid):
            st["pending_scenes"].append(sid)
    for jid, rule in JOURNAL_RULES:
        if rule(save):
            add_journal(save, jid)
    if "M6" not in st["phone_shown"]:   # 아스테라 도착(M6) 뒤로는 에필로그 전까지 알림 없음
        for mid, rule in PHONE_RULES:
            if mid not in st["phone_shown"] and mid not in st["phone_pending"] and rule(save):
                st["phone_pending"].append(mid)
    st["chapter"] = chapter(save)


_ACC = {"t": 0.0}


def tick(save, dt: float) -> None:
    """2초마다 poll (낚시터·마을 갱신에서) — 첫 포획 일지(J02) 같은 것이 바로 기록되게."""
    _ACC["t"] += dt
    if _ACC["t"] >= 2.0:
        _ACC["t"] = 0.0
        poll(save)


def take_interior(save, npc: str) -> str | None:
    """그 건물에 들어갈 때 재생할 장면 (대기 중인 것 중 순서가 가장 앞). 조건이 사라진 장면은 버린다."""
    if not active(save):
        return None
    poll(save)
    st = state(save)
    for sid in ORDER:
        if sid not in st["pending_scenes"]:
            continue
        sc = scene(sid)
        if sc["place"] != f"interior:{npc}":
            continue
        if sid == "C2-02" and _unlocked(save, "offshore"):     # 배를 이미 고쳤으면 없음
            st["pending_scenes"].remove(sid)
            st["seen_scenes"].append(sid)
            continue
        if sid == "C4-02B" and flag(save, "eldra_escape"):     # 도주 뒤면 첫 인사 대신 조건 A
            st["pending_scenes"].remove(sid)
            st["seen_scenes"].append(sid)
            continue
        if sid == "NAME" or scene_due(save, sid):
            return sid
    return None


def complete(game, sid: str, replay: bool = False) -> None:
    """장면이 끝남: 본 장면 기록 + 결과(일지·플래그·아이템·휴대폰). 다시 보기(replay)면 아무것도 안 바꿈."""
    if replay:
        return
    save = game.save
    st = state(save)
    if sid in st["pending_scenes"]:
        st["pending_scenes"].remove(sid)
    if sid not in st["seen_scenes"]:
        st["seen_scenes"].append(sid)
    res = scene(sid).get("results", {})
    if res.get("journal"):
        add_journal(save, res["journal"])
    st["flags"].update(res.get("flags", {}))
    for k, v in res.get("items", {}).items():
        st["items"][k] = v
        if k == "haegang_bobber_skin":
            give_skin(save)
    if res.get("phone") and res["phone"] not in st["phone_shown"]:
        st["phone_shown"].append(res["phone"])
    st["chapter"] = chapter(save)
    game.save_now()


def give_skin(save) -> None:
    """찌 외형 '해강의 찌' (외형만, 성능 없음)."""
    cos = save.data.setdefault("cosmetics", {})
    lst = cos.setdefault("float_skins", [])
    if "haegang_bobber" not in lst:
        lst.append("haegang_bobber")


def add_journal(save, jid: str) -> bool:
    st = state(save)
    if any(e["id"] == jid for e in st["journal"]):
        return False
    from src.core import season as seasons
    season = seasons.current(_GAME["g"].settings) if _GAME["g"] is not None else seasons.real_season()
    st["journal"].append({"id": jid, "day": int(save.data.get("day", 1)), "season": season})
    if not st.pop("_silent_journal", False):
        st["journal_toasts"].append(jid)
    return True


def chapter(save) -> int:
    st = state(save)
    if "force_chapter" in st["flags"]:   # 디버그: 막 강제 변경
        return st["flags"]["force_chapter"]
    s = st["seen_scenes"]
    if "E-01" in s:
        return 6
    if _unlocked(save, "volcano") and _eldra(save):
        return 5
    if _eldra(save):
        return 4
    if _unlocked(save, "deep"):
        return 3
    if _unlocked(save, "breakwater"):
        return 2
    if "P-05" in s:
        return 1
    return 0


def goal(save) -> str | None:
    """다음 목표 한 줄 (마을 왼쪽 위). goals.json 표 순서 그대로, 지금 구간의 문구."""
    if not active(save):
        return None
    g = [x["text"] for x in load_json("story/goals.json")["goals"]]
    st = state(save)
    s = st["seen_scenes"]
    if "E-01" in s:
        return g[17]
    if _eldra(save):
        if "C5-04" in s or _visited(save, "world_tree"):
            return g[16]
        if "C5-03" in s:
            return g[15]
        if _unlocked(save, "world_tree"):
            return g[14]
        if "C4-05" in s:
            return g[13]
        if _unlocked(save, "volcano"):
            return g[12]
        return g[11]
    if "C3-03" in s:
        return g[10]
    if _visited(save, "secret") or "C3-02" in s:
        return g[9]
    if "C2-05" in s:
        return g[8]
    if _unlocked(save, "deep"):
        return g[7]
    if _unlocked(save, "offshore"):
        return g[6]
    if save.caught("silver_bass"):
        return g[5]
    if "C1-06" in s:
        return g[4]
    if _unlocked(save, "breakwater"):
        return g[3]
    if "C1-04" in s:
        return g[2]
    if _catches(save) >= 1:
        return g[1]
    return g[0]


def next_phone(save) -> str | None:
    """마을에 들어올 때 보여 줄 휴대폰 알림 1개 (나머지는 다음 입장 때)."""
    if not active(save):
        return None
    poll(save)
    st = state(save)
    for mid in PHONES:
        if mid in st["phone_pending"]:
            st["phone_pending"].remove(mid)
            st["phone_shown"].append(mid)
            return mid
    return None


def pop_journal_toast(save) -> str | None:
    if not active(save):
        return None
    lst = state(save)["journal_toasts"]
    return lst.pop(0) if lst else None


# ───────────────────────── 새 게임 · 기존 세이브 ─────────────────────────
def is_fresh(save) -> bool:
    d = save.data
    return _catches(save) == 0 and set(d.get("unlocked_spots", [])) <= {"reservoir"} and not d.get("dex")


def begin_new(save) -> None:
    st = state(save)
    st["chapter"] = 0


def migrate(save) -> None:
    """기존 세이브 (STORY.md '기존 세이브 처리'): 이름 장면 1회 · 막 계산 · 지난 장면은 추억으로 · 지난 일지·보상 · 표시 이름."""
    st = state(save)
    st["_silent_journal"] = True
    s = st["seen_scenes"]
    for sid in ("P-01", "P-02", "P-03", "P-04", "P-05"):
        s.append(sid)
    for sid in ORDER:
        if sid != "NAME" and scene_due(save, sid) and sid not in s:
            s.append(sid)
    if _visited(save, "secret"):
        s += [x for x in ("C3-02", "C3-03") if x not in s]
    if save.data.get("ending_seen") or save.caught("dragon_carp"):
        s += [x for x in ("C3-04",) if x not in s]
    if _eldra(save):
        s += [x for x in ("C4-01",) if x not in s]
        st["phone_shown"].append("M6")
    if _visited(save, "world_tree"):
        s += [x for x in ("C5-04",) if x not in s]
    if save.caught("orsiel"):
        s += [x for x in ("C5-05", "E-01") if x not in s]   # 선택 장면 없이 (true_end_choice 비움), 에필로그는 추억에서
    if "C1-06" in s:
        st["flags"]["grandpa_named"] = True
    # 지난 일지 (날짜는 불러온 날)
    jid_of = {"P-05": "J01", "C1-06": "J04", "C3-02": "J08", "C3-04": "J09", "C4-01": "J10", "C4-05": "J11",
              "C5-04": "J12", "E-01": "J14", "PH-01": "J15", "PH-02": "J16"}
    for sid, jid in jid_of.items():
        if sid in s:
            st["_silent_journal"] = True
            add_journal(save, jid)
    for jid, rule in JOURNAL_RULES:
        if rule(save):
            st["_silent_journal"] = True
            add_journal(save, jid)
    st.pop("_silent_journal", None)
    # 지난 보상
    if "C4-05" in s:
        st["items"]["haegang_bobber_skin"] = True
        give_skin(save)
    if "C5-04" in s:
        st["items"]["grandpa_last_page"] = True
    # 지난 휴대폰 알림은 보여 준 것으로
    for mid, rule in PHONE_RULES:
        if rule(save) and mid not in st["phone_shown"]:
            st["phone_shown"].append(mid)
    st["pending_scenes"] = ["NAME"]   # 하루네 낚시점에서 짧은 이름 장면
    st["chapter"] = chapter(save)
