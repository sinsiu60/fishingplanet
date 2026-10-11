"""여정 — 진행 사슬 하나 (JOURNEY.md, DESIGN.md 54).

앞 낚시터 전설 포획 → 백 노인 시험 합격 → 다음 장비 → 다음 낚시터. 해금 조건은 data/spots.json unlock
(exam 시험 합격 티어 · legend 전설 · legends 샤르미온 전설 수 · need_rod 낚싯대 티어), 시험 자격은 data/exam.json
(도감 dex_ratio + 그 티어 전설 owner).

옛 세이브 (54-1 ⑥): 처음 불러올 때 한 번, 옛 해금 조건(비용 빼고)을 이미 다 채운 잠긴 낚시터와 옛 시험 자격을
이미 채운 다음 시험 티어를 기록해 두고, 새 사슬에서도 넘은 것으로 친다.
저장: save.data["journey"] = {"v": 1, "old_ok": [낚시터], "exam_ok": 티어 또는 0}.
"""
import math

from src.core.config import load_json

# 옛 해금 조건 (v1.8.0 spots.json unlock 그대로 — 옛 세이브 판정용)
LEGACY_UNLOCK = {
    "valley": {"dex": 4, "cost": 500},
    "breakwater": {"dex_pct": 25, "rod_tier": 2, "spot_s": "valley", "cost": 2500},
    "offshore": {"dex_pct": 45, "rare_total": 5, "legend": "silver_bass", "cost": 6000},
    "deep": {"dex_pct": 65, "all_gear_tier": 4, "legend": "marlin", "s_total": 5, "cost": 15000},
    "secret": {"dex_pct": 80, "legends": 5, "perfects": 100},
    "crystal_cave": {"dex_pct": 12, "gear_count_tier": [3, 5], "cost": 25000},
    "sky_falls": {"dex_pct": 25, "legend": "prisia", "s_eldra": 5, "cost": 60000},
    "volcano": {"dex_pct": 40, "all_gear_tier": 6, "legend": "aeris", "cost": 120000},
    "ice_sea": {"dex_pct": 55, "legends_list": ["silva", "prisia", "aeris", "ignis"], "perfects": 200, "cost": 200000},
    "world_tree": {"dex_pct": 70, "legends_list": ["silva", "prisia", "aeris", "ignis", "borealis"], "legend_s": 1,
                   "s_eldra": 10},
}
# 옛 시험 자격 (exam.json v1.8.0): 도감 80% (T8 75%) · 별 25% · 그 물의 주인(T3+, 전설 또는 희귀 75%) · T5 는 심해 제외
LEGACY_EXAM = {"dex": 0.8, "dex_tier": {8: 0.75}, "stars": 0.25, "owner_from": 3, "rare": 0.75, "exclude": {5: ["deep"]}}

ORDER = ["reservoir", "valley", "breakwater", "offshore", "deep", "secret",
         "marsh", "crystal_cave", "sky_falls", "volcano", "ice_sea", "world_tree"]


def state(save) -> dict:
    st = save.data.get("journey")
    if st is None:
        st = {"v": 1, "old_ok": _legacy_open(save), "exam_ok": _legacy_exam_ok(save)}
        save.data["journey"] = st
    st.setdefault("old_ok", [])
    st.setdefault("exam_ok", 0)
    return st


def old_ok(save, spot_id: str) -> bool:
    return spot_id in state(save)["old_ok"]


def exam_grandfathered(save, tier: int) -> bool:
    return int(state(save)["exam_ok"]) == tier


def _legacy_open(save) -> list[str]:
    """옛 조건을 비용 빼고 다 채운 잠긴 낚시터 (새 세이브는 빈 목록)."""
    from src.scene.map_scene import cond_rows
    out = []
    spots = {s["id"]: s for s in load_json("spots.json")["spots"]}
    for sid, cond in LEGACY_UNLOCK.items():
        if sid in save.data.get("unlocked_spots", []) or sid not in spots:
            continue
        if spots[sid].get("continent", "sharmion") not in save.data.get("unlocked_continents", ["sharmion"]):
            continue
        rows = cond_rows(save, spots[sid], {k: v for k, v in cond.items() if k != "cost"})
        if rows and all(ok for _, ok in rows):
            out.append(sid)
    return out


def _legacy_exam_ok(save) -> int:
    """옛 자격으로 다음 시험을 이미 볼 수 있었으면 그 티어 (아니면 0)."""
    from src.save import dexbook, exam
    t = exam.next_tier(save)
    if t is None:
        return 0
    L = LEGACY_EXAM
    skip = set(L["exclude"].get(t, []))
    sp = {s for s in exam.spots_of_tier(exam.passed(save)) if s not in skip}
    allf = [f for f in load_json("fish.json")["fish"] if f["spot"] in sp]
    fs = [f for f in allf if f["rarity"] != "legend"]
    if not fs:
        return 0
    dex = save.data.get("dex", {})
    have = sum(1 for f in fs if dex.get(f["id"], {}).get("count", 0) > 0)
    if have < math.ceil(L["dex_tier"].get(t, L["dex"]) * len(fs) - 1e-9):
        return 0
    if sum(dexbook.star_count(save, f) for f in fs) < math.ceil(L["stars"] * 5 * len(fs) - 1e-9):
        return 0
    if t >= L["owner_from"]:
        leg = any(dex.get(f["id"], {}).get("count", 0) > 0 for f in allf if f["rarity"] == "legend")
        rares = [f for f in fs if f["rarity"] == "rare"]
        got = sum(1 for f in rares if dex.get(f["id"], {}).get("count", 0) > 0)
        if not leg and got < math.ceil(L["rare"] * len(rares) - 1e-9):
            return 0
    return t


# ── 이름 ──
def fish(fid: str) -> dict:
    from src.save.save_game import fish_by_id
    return fish_by_id(fid)


def nick(fid: str) -> str:
    """전설 짧은 이름: '산신 쏘가리 '산군'' → 산군, '갈대왕 실바' → 실바."""
    name = fish(fid)["name"]
    if "'" in name:
        return name.split("'")[1]
    return name.split()[-1]


def josa(word: str, pair: str = "을를") -> str:
    """받침이 있으면 앞 글자 (을 · 이 · 은), 없으면 뒤 글자."""
    c = word[-1]
    if "가" <= c <= "힣":
        return word + (pair[0] if (ord(c) - 0xAC00) % 28 else pair[1])
    return word + pair[1]


def spot_short(sid: str) -> str:
    sp = next(s for s in load_json("spots.json")["spots"] if s["id"] == sid)
    return sp["short"] if sp["short"] != "???" else sp["name"]


# ── 다음 목적지 ──
def next_spot(save) -> str | None:
    """사슬에서 아직 안 열린 첫 낚시터 (다 열렸으면 None)."""
    opened = set(save.data.get("unlocked_spots", []))
    return next((s for s in ORDER if s not in opened), None)


def next_goal(save) -> dict | None:
    """지도 '다음 목적지' · 진행 막대: {"spot": 열릴 낚시터, "where": 지금 가야 할 낚시터 또는 "baek", "text": 한 줄}.
    다 열고 오르시엘까지 잡았으면 None."""
    from src.save import exam
    nxt = next_spot(save)
    if nxt is None:
        if save.caught("orsiel"):
            return None
        return {"spot": "world_tree", "where": "world_tree", "text": f"세계수에서 {josa(nick('orsiel'))} 만나자"}
    sp = next(s for s in load_json("spots.json")["spots"] if s["id"] == nxt)
    cond = sp.get("unlock", {})
    if old_ok(save, nxt):
        return {"spot": nxt, "where": nxt, "text": f"{josa(spot_short(nxt), '이가')} 열렸어요 — 지도에서 해금"}
    t = cond.get("exam")
    if t and exam.passed(save) < t:
        return _exam_goal(save, nxt, exam.next_tier(save))
    if cond.get("legends"):
        from src.scene.map_scene import SHARMION_SPOTS
        legs = [f["id"] for f in load_json("fish.json")["fish"] if f["rarity"] == "legend" and f["spot"] in SHARMION_SPOTS]
        left = [f for f in legs if not save.caught(f)]
        if left:
            f = left[0]
            return {"spot": nxt, "where": fish(f)["spot"],
                    "text": f"{josa(nick(f))} 잡자 — 다섯 전설 {len(legs) - len(left)}/{len(legs)}"}
    if cond.get("legend") and not save.caught(cond["legend"]):
        f = cond["legend"]
        return {"spot": nxt, "where": fish(f)["spot"], "text": f"{josa(nick(f))} 잡으면 {josa(spot_short(nxt), '이가')} 열려요"}
    rod = cond.get("need_rod")
    if rod and save.gear_tier("rod") < rod:
        if exam.passed(save) < rod:
            return _exam_goal(save, nxt, exam.next_tier(save))
        return {"spot": nxt, "where": "shop", "text": f"T{rod} 낚싯대를 사면 {josa(spot_short(nxt), '이가')} 열려요"}
    if sp.get("continent", "sharmion") not in save.data.get("unlocked_continents", []):
        return {"spot": nxt, "where": fish("dragon_carp")["spot"], "text": f"{josa(nick('dragon_carp'))} 잡고 바다 건너로"}
    return {"spot": nxt, "where": nxt, "text": f"{spot_short(nxt)} 해금 — 지도에서"}


def _exam_goal(save, nxt: str, t: int | None) -> dict:
    from src.save import exam
    if t is None:
        return {"spot": nxt, "where": nxt, "text": f"{spot_short(nxt)} 해금 — 지도에서"}
    q = exam.quals(save)
    owner = next((x for x in q if x["key"] == "owner"), None)
    dex = next((x for x in q if x["key"] == "dex"), None)
    if owner and not owner["ok"]:
        f = owner["fish"]
        return {"spot": nxt, "where": fish(f)["spot"], "text": f"{josa(nick(f))} 잡고 백 노인에게"}
    if dex and not dex["ok"]:
        base = exam.base_spots(save)
        names = " · ".join(spot_short(s) for s in base)
        return {"spot": nxt, "where": base[0] if base else nxt,
                "text": f"{names} 도감 {dex['have']}/{dex['need']} 채우고 백 노인에게"}
    return {"spot": nxt, "where": "baek", "text": f"백 노인의 T{t} 시험을 보자"}


# ── 엔딩 뒤 (JOURNEY 🏁, DESIGN 54-5) ──
def ended(save) -> bool:
    """오르시엘을 잡았거나 에필로그를 봤으면 엔딩 뒤."""
    from src.story import story
    return save.caught("orsiel") or (story.active(save) and story.seen(save, "E-01"))


def remaining_goals(save) -> list[dict]:
    """집 '남은 이야기' 쪽: [{title, line, have, need}] — 원하는 사람만 하는 목표 (숫자 채우기는 여기로)."""
    from src.save import achievements, bottles, dexbook, events_cal
    from src.save.save_game import equipment
    out = []
    got, tot = 0, 0
    for cont in ("sharmion", "eldrasion"):
        g, t = save.continent_dex(cont)
        got, tot = got + g, tot + t
    out.append({"title": "도감 완성", "line": f"도감 {got}/{tot}종 · 별 {dexbook.points(save)}/{dexbook.max_points(save)}",
                "have": got, "need": tot})
    legs = [f for f in load_json("fish.json")["fish"] if f["rarity"] == "legend"]
    s = sum(1 for f in legs if save.data.get("dex", {}).get(f["id"], {}).get("best_rank") == "S")
    out.append({"title": "전설 다시 낚기", "line": f"전설 S랭크 {s}/{len(legs)}종 (조건 칸 · 생미끼로 노리기, 입질당 5 · 10%)",
                "have": s, "need": len(legs)})
    eq = equipment()
    t8 = sum(1 for k in ("rod", "reel", "line", "net") if any(g.get("tier") == 8 and save.owns(k, g["id"]) for g in eq[k]))
    out.append({"title": "장비 완성", "line": f"T8 장비 {t8}/4종 · 비늘석 맞추기", "have": t8, "need": 4})
    vis = [a for a in achievements.visible(save)]
    ag = sum(1 for a in vis if a["id"] in achievements.state(save)["got"])
    out.append({"title": "업적", "line": f"업적 {ag}/{len(vis)}개 · 퍼펙트 {save.data.get('stats', {}).get('perfects', 0)}번",
                "have": ag, "need": len(vis)})
    tro = len(events_cal.st(save).get("trophies", []))
    out.append({"title": "계절 축제 · 대회 · 상인", "line": f"주간 대회 트로피 {tro}개 · 축제는 계절마다", "have": min(tro, 1), "need": 1})
    b = len(bottles.collected(save))
    out.append({"title": "해강의 자리", "line": f"유리병 편지 {b}/{len(bottles.letters())}장", "have": b, "need": len(bottles.letters())})
    return out
