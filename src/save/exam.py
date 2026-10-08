"""백 노인의 등급 시험 (BAEK_EXAM.md 🅱, DESIGN.md 49-3).

시험 하나 = 장비 티어 하나 (T2 ~ T8). 합격한 티어보다 높은 장비(낚싯대 · 릴 · 줄 · 뜰채)는 살 수도, 장착할 수도 없다.
세이브 save.data["exam"] = {"passed": 합격 티어, "fails": {티어: 불합격 수}, "retry_day": {티어: 다시 볼 수 있는 게임 날},
"active": 시험 찌를 받은 시험 {"tier", "fish"} 또는 None, "notice_seen": 옛 세이브 안내를 봤는지, "missed": 마지막 시험 판 놓친 패턴 수}.
"""
import copy
import math

from src.core.config import load_json

RANKS = {"C": 0, "B": 1, "A": 2, "S": 3}
ROMAN = {1: "Ⅰ", 2: "Ⅱ", 3: "Ⅲ", 4: "Ⅳ", 5: "Ⅴ", 6: "Ⅵ", 7: "Ⅶ", 8: "Ⅷ"}
MAX_TIER = 8


def cfg() -> dict:
    return load_json("exam.json")


def default_state() -> dict:
    return {"passed": 1, "fails": {}, "retry_day": {}, "active": None, "notice_seen": False, "missed": {}, "ready_seen": [],
            "legacy": False, "goal_toast": []}


def state(save) -> dict:
    st = save.data.setdefault("exam", default_state())
    for k, v in default_state().items():
        st.setdefault(k, copy.deepcopy(v))
    return st


def passed(save) -> int:
    return int(state(save)["passed"])


def next_tier(save) -> int | None:
    """다음 시험 티어 (다 합격했으면 None)."""
    t = passed(save) + 1
    return t if t <= MAX_TIER else None


# ── 옛 세이브 ──
def legacy_passed(data: dict) -> int:
    """가진 장비(상점 장비 4종 + 장착 중인 장비) 중 가장 높은 티어 — 그 티어까지 자동 합격 (🅱-5)."""
    from src.save.save_game import GEAR_KINDS, equipment
    eq = equipment()
    tiers = {g["id"]: g.get("tier", 1) for k in GEAR_KINDS for g in eq[k]}
    best = 1
    for k in GEAR_KINDS:
        for gid in data.get("owned", {}).get(k, []):
            best = max(best, tiers.get(gid, 1))
    # 장착 중인 상자 장비: 장착 칸이 잠기지 않게 그 티어(얻은 대륙 상점 최고 티어)도 합격으로
    # (🅱-5 '장착 중인 장비가 합격 티어보다 높은 경우는 없음')
    from src.save.save_game import TOP_TIER
    items = data.get("items", {})
    origin = items.get("origin", {})
    for k in GEAR_KINDS:
        gid = data.get("gear", {}).get(k)
        if gid and gid in items.get("owned", []) and gid not in tiers:
            best = max(best, TOP_TIER.get(origin.get(gid, "sharmion"), 5))
    return min(MAX_TIER, best)


def migrate(data: dict) -> None:
    """exam 필드가 없는 세이브 (시험 이전): 가진 장비 최고 티어까지 합격, T2 이상이면 안내 한 번."""
    if "exam" in data:
        return
    st = default_state()
    st["passed"] = legacy_passed(data)
    st["notice_seen"] = st["passed"] <= 1
    st["legacy"] = st["passed"] >= 2   # 이미 진행한 세이브 (🅲-1): 변경 공지 · TG-21 잠긴 장비 건너뜀
    data["exam"] = st
    if st["legacy"]:
        done = data.setdefault("tutorial", {}).setdefault("done", [])
        skip = ["TG-21"] + (["TG-22", "TG-23", "TG-24"] if st["passed"] >= MAX_TIER else [])   # T8: 볼 시험이 없음
        done += [t for t in skip if t not in done]
    titles = data.setdefault("cosmetics", {}).setdefault("titles", [])
    for t, tid in cfg()["titles"].items():   # 자동 합격한 티어의 칭호도 (T4 · T8)
        if int(t) <= st["passed"] and tid not in titles:
            titles.append(tid)


def legacy_notice(save) -> int | None:
    """옛 세이브 안내를 아직 안 봤으면 자동 합격 티어 (보면 mark_notice)."""
    st = state(save)
    if st["notice_seen"] or not st.get("legacy") or st["passed"] < 2:   # 새 세이브 · T1 세이브는 공지 없음 (🅲-1)
        return None
    return st["passed"]


def mark_notice(save) -> None:
    state(save)["notice_seen"] = True


# ── 장비 잠금 ──
def gear_lock_tier(save, item: dict) -> int | None:
    """이 장비가 시험 때문에 잠겼으면 필요한 티어 (상점 장비 · 상자 장비 모두 tier 로)."""
    t = item.get("tier")
    if not t or t <= passed(save):
        return None
    return int(t)


def lock_label(tier: int) -> str:
    """상점 잠김 이유 (자물쇠는 그림으로 — 글꼴에 🔒 가 없음)."""
    return f"백 노인의 시험 (T{tier})"


# ── 자격 ──
def spots_of_tier(tier: int) -> list[str]:
    return [s["id"] for s in load_json("spots.json")["spots"] if s.get("gear_tier") == tier]


def spot_names(tier: int) -> list[str]:
    """그 티어 낚시터 짧은 이름 (비밀 낚시터는 '???' 대신 이름 — 시험 기준이 될 무렵이면 이미 가 본 곳)."""
    ids = spots_of_tier(tier)
    return [s["short"] if s["short"] != "???" else s["name"] for s in load_json("spots.json")["spots"] if s["id"] in ids]


def base_spots(save) -> list[str]:
    """지금 합격 티어 낚시터 = 시험 자격 기준 · 시험을 볼 수 있는 곳 (CU8-③: T5 는 먼바다만 — base_exclude)."""
    skip = set(cfg().get("base_exclude", {}).get(str(next_tier(save) or 0), []))
    return [s for s in spots_of_tier(passed(save)) if s not in skip]


def on_exam_spot(save, spot_id: str) -> bool:
    return spot_id in base_spots(save)


def _base_fish(save) -> list[dict]:
    sp = set(base_spots(save))
    return [f for f in load_json("fish.json")["fish"] if f["spot"] in sp]


def quals(save) -> list[dict]:
    """자격 ①②③ — [{key, label, have, need, ok, alt}] (③ 은 T3 시험부터)."""
    from src.save import dexbook
    c = cfg()
    tier = next_tier(save)
    if tier is None:
        return []
    allf = _base_fish(save)
    fs = [f for f in allf if f["rarity"] != "legend"]
    dex = save.data.get("dex", {})
    caught = [f for f in fs if dex.get(f["id"], {}).get("count", 0) > 0]
    need1 = math.ceil(c.get("dex_ratio_tier", {}).get(str(tier), c["dex_ratio"]) * len(fs) - 1e-9)   # 티어별 덮어쓰기 (CU8-③)
    stars = sum(dexbook.star_count(save, f) for f in fs)
    need2 = math.ceil(c["star_ratio"] * 5 * len(fs) - 1e-9)
    out = [{"key": "dex", "label": "도감", "have": len(caught), "need": need1, "ok": len(caught) >= need1},
           {"key": "stars", "label": "도감 별", "have": stars, "need": need2, "ok": stars >= need2}]
    if tier >= c["owner_from"]:
        legends = [f for f in allf if f["rarity"] == "legend"]
        leg_ok = any(dex.get(f["id"], {}).get("count", 0) > 0 for f in legends)
        rares = [f for f in fs if f["rarity"] == "rare"]
        have = sum(1 for f in rares if dex.get(f["id"], {}).get("count", 0) > 0)
        need3 = math.ceil(c["rare_ratio"] * len(rares) - 1e-9)
        out.append({"key": "owner", "label": "그 물의 주인", "have": need3 if leg_ok else have, "need": need3,
                    "ok": leg_ok or have >= need3, "legend": leg_ok,
                    "alt": "전설 1마리 또는 희귀 " + str(need3) + "종"})
    return out


def eligible(save) -> bool:
    q = quals(save)
    return bool(q) and all(x["ok"] for x in q)


def retry_wait(save, day: int) -> bool:
    """불합격 뒤 아직 하루가 안 지났으면 True."""
    t = next_tier(save)
    if t is None:
        return False
    return day < int(state(save)["retry_day"].get(str(t), 0))


# ── 시험 물고기 · 합격 조건 ──
def exam_fish(tier: int) -> dict:
    """시험 물고기 (fish.json 사본 + exam 표시, T8 은 체력 × 1.3). 크기 → 난이도 배율은 적용하지 않음 (fight)."""
    from src.save.save_game import fish_by_id
    c = cfg()
    f = copy.deepcopy(fish_by_id(c["fish"][str(tier)]))
    k = c.get("stamina_mult", {}).get(str(tier))
    if k:
        f["stamina"] = round(f["stamina"] * k)
    k = c.get("power_mult", {}).get(str(tier))
    if k:
        f["power"] = round(f["power"] * k, 3)
    k = c.get("telegraph_mult", {}).get(str(tier))
    if k:   # 예고를 길게 = 신호를 받아내기 쉽게 (49-5)
        f["telegraph_sec"] = round(f.get("telegraph_sec", 1.0) * k, 3)
    f["exam"] = tier
    f["nibbles"] = [1, 1]   # 톡톡 한 번 뒤 바로 입질 (3초 대기 + 접근 → 실측 약 6초)
    return f


def fish_known(save, tier: int) -> bool:
    """그 종을 도감에 등록했으면 이름을 보여 줌 (아니면 '???')."""
    fid = cfg()["fish"][str(tier)]
    return save.data.get("dex", {}).get(fid, {}).get("count", 0) > 0


def pass_rule(tier: int) -> dict:
    return cfg()["pass"][str(tier)]


def pass_text(tier: int) -> str:
    r = pass_rule(tier)
    s = f"{r['rank']} 랭크 이상"
    if r.get("perfects"):
        s += f" + 퍼펙트 {r['perfects']}번"
    return s


def judge(tier: int, result: dict | None) -> bool:
    """잡은 판의 결과 (fight.result) 로 합격 판정. 놓쳤으면 (None) 불합격."""
    if not result or result.get("rank") is None:
        return False
    r = pass_rule(tier)
    if RANKS[result["rank"]] < RANKS[r["rank"]]:
        return False
    perf = (result.get("opp") or {}).get("P", 0)
    return perf >= r.get("perfects", 0)


# ── 시험 진행 ──
def active(save) -> dict | None:
    return state(save)["active"]


def give_float(save) -> dict:
    """시험 찌 지급 (가방 소모품 칸에 1개, 장착 중인 찌 대신 자동으로 끼워짐)."""
    t = next_tier(save)
    st = state(save)
    st["active"] = {"tier": t, "fish": cfg()["fish"][str(t)]}
    return st["active"]


def postpone(save) -> None:
    """시험 미루기: 시험 찌 반납 (불합격으로 치지 않음)."""
    state(save)["active"] = None


def finish(save, ok: bool, day: int, missed: dict | None = None) -> dict:
    """시험 판 끝. 돌려주는 값 {tier, pass, fails}."""
    st = state(save)
    act = st["active"] or {"tier": next_tier(save)}
    t = int(act["tier"])
    st["active"] = None
    st["missed"] = dict(missed or {})
    st["last_pass"] = bool(ok)   # TG-24 첫 시험 ③ (합격 / 불합격 안내)
    titles = []
    if ok:
        st["passed"] = max(st["passed"], t)
        titles = grant_titles(save, st["passed"])
    else:
        st["fails"][str(t)] = int(st["fails"].get(str(t), 0)) + 1
        st["retry_day"][str(t)] = day + int(cfg()["retry_days"])
    return {"tier": t, "pass": ok, "fails": int(st["fails"].get(str(t), 0)), "titles": titles}


def fails(save, tier: int | None = None) -> int:
    t = tier if tier is not None else next_tier(save)
    return int(state(save)["fails"].get(str(t), 0)) if t else 0


def most_missed(save) -> str | None:
    """마지막 시험 판에서 가장 많이 놓친 패턴 (3번 불합격 뒤 힌트)."""
    m = state(save).get("missed") or {}
    if not m:
        return None
    return max(m, key=lambda k: (m[k], k))


def show_hint(save) -> str | None:
    """3번 이상 떨어졌고 놓친 패턴 기록이 있으면 그 패턴."""
    if fails(save) < cfg()["hint_after_fails"]:
        return None
    return most_missed(save)


def pattern_name(pid: str) -> str:
    names = load_json("patterns.json").get("names", {})
    return names.get(pid) or {"rush": "돌진", "rush_big": "돌진 (대형)", "jump": "점프", "turn": "방향 전환",
                              "leap": "몸털기 점프"}.get(pid, pid)


def borrowed_gear(tier: int) -> dict:
    """빌린 다음 티어 기본 장비 4종의 Fight 수치 — 비늘석 · 부적 · 상자 장비 효과 없음 (순수 실력)."""
    from src.save.save_game import equipment
    eq = equipment()

    def pick(kind):
        return next(g for g in eq[kind] if g.get("tier") == tier)
    rod, reel, line, net = pick("rod"), pick("reel"), pick("line"), pick("net")
    return {"rod_green": list(rod["green"]), "rod_tier": rod["tier"], "reel_speed": reel["speed"],
            "drag_steps": reel["drag_steps"], "drag_cushion": reel.get("drag_cushion", 0.0),
            "line_max": line["durability"], "net_window_sec": net["window"], "net_fail_distance": net["fail_distance"],
            "line_red_mult": 1.0, "perfect_heal": 0.0, "auto_drag": False}


def borrowed_names(tier: int) -> list[str]:
    from src.save.save_game import GEAR_KINDS, equipment
    eq = equipment()
    return [next(g["name"] for g in eq[k] if g.get("tier") == tier) for k in GEAR_KINDS]


def letter_menu(save) -> bool:
    """엘라 공방 [백 노인의 편지]: 다음 시험이 T6 이상일 때부터 (🅱-4, 다 합격한 뒤에도 남음)."""
    return passed(save) + 1 >= cfg()["letter_from"]


def line(key: str, **kw) -> tuple:
    """(표정, 대사) — data/dialogue.json kind exam_<key> (🅱-7). 편지 본문은 표정 None."""
    ln = next(x for x in load_json("dialogue.json")["lines"] if x.get("kind") == f"exam_{key}")
    return ln.get("expr"), ln["text"].format(**kw)


def ready_first(save, tier: int) -> bool:
    """자격 충족을 처음 본 순간이면 True (그 뒤로는 'sharp' 대사 없이)."""
    seen = state(save).setdefault("ready_seen", [])
    if tier in seen:
        return False
    seen.append(tier)
    return True


def grant_titles(save, upto: int) -> list[str]:
    """합격 칭호 (T4 '물을 아는 자' · T8 '해강의 뒤를 이은 자', 🅱-6). 새로 받은 칭호 이름 목록."""
    from src.save import quests
    titles = quests.cosmetics(save)["titles"]
    got = []
    for t, tid in cfg()["titles"].items():
        if int(t) <= upto and tid not in titles:
            titles.append(tid)
            got.append(quests.shop_item(tid)["name"])
    return got
