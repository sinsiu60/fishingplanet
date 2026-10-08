"""비늘석 (SCALESTONE.md, DESIGN.md 46장): 장비 칸(낚싯대 · 릴 · 줄 · 뜰채)에 하나씩 끼우는 강화 돌.

데이터: data/scalestone/options.json · grades.json · enhance.json · drops.json
세이브: data["scalestone"] = {"items": [...], "equipped": {rod, reel, line, net: uid | None}, "first_quest_bonus": bool, "next_id": n}
아이템: {"uid", "grade", "level", "opts": [{"id", "v"}], "locked", "spent": {"gold", "mat"}, "got": 획득 순번, "src": 출처}

S2: 데이터 · 아이템 구조 · 첫 부옵션 뽑기 · 획득(포획 · 의뢰 · 상자 · 첫 포획 · 첫 의뢰) · 보관 150개(가득 차면 자동 분해) · 디버그.
S3: 강화 +1~+4 (단계마다 새 부옵션, 실패 없음) · 비용 · 잠금 · 분해 · 일괄 분해.
S4: 장착(칸 4개, 하나는 한 칸에만, 칸에 붙어서 장비를 바꿔도 유지) · 장착 4개 합계 + 상한 → effect(save, id).
소재 = 대륙 소재 2종(sharmion · eldrasion)을 하나처럼 — 많은 쪽부터 쓰고, 분해로 받는 소재는 지금 있는 대륙 쪽 (46-2 답 1).
"""
import math
import random

from src.core.config import load_json

SLOTS = ("rod", "reel", "line", "net")
CONTS = ("sharmion", "eldrasion")


def options() -> dict:
    return load_json("scalestone/options.json")


def grades() -> dict:
    return load_json("scalestone/grades.json")


def enhance_cfg() -> dict:
    return load_json("scalestone/enhance.json")


def drops() -> dict:
    return load_json("scalestone/drops.json")


def grade_info(grade: str) -> dict:
    return grades()["grades"][grade]


def state(save) -> dict:
    st = save.data.setdefault("scalestone", {})
    st.setdefault("items", [])
    eq = st.setdefault("equipped", {})
    for s in SLOTS:
        eq.setdefault(s, None)
    st.setdefault("first_quest_bonus", False)
    st.setdefault("next_id", 1)
    return st


# ───────────────────────── 옵션 ─────────────────────────

def _round(unit: str, v: float) -> float:
    """% = 소수 첫째 · 초 = 소수 둘째 · %p = 소수 둘째."""
    return round(v, 1 if unit == "pct" else 2)


def roll_option(grade: str, exclude=(), rnd=random) -> dict | None:
    """부옵션 하나: 이미 붙은 옵션 빼고 비중대로 → 희귀 기준 범위에서 균등 무작위 × 등급 배율 → 반올림."""
    o = options()
    pool = [oid for oid in o["order"] if oid not in exclude]
    if not pool:
        return None
    oid = rnd.choices(pool, [o["options"][x]["weight"] for x in pool])[0]
    spec = o["options"][oid]
    lo, hi = spec["range"]
    v = rnd.uniform(lo, hi) * grade_info(grade)["mult"]
    return {"id": oid, "v": _round(spec["unit"], v)}


def option_text(opt: dict, with_value: bool = True) -> str:
    spec = options()["options"][opt["id"]]
    if not with_value:
        return spec["name"]
    return f"{spec['name']} {value_text(opt['id'], opt['v'])}"


def value_text(oid: str, v: float) -> str:
    spec = options()["options"][oid]
    sign = "-" if spec.get("sign", 1) < 0 else "+"
    if spec["unit"] == "pct":
        return f"{sign}{v:.1f}%"
    if spec["unit"] == "sec":
        return f"{sign}{v:.2f}초"
    return f"{sign}{v:.2f}%p"


# ───────────────────────── 아이템 ─────────────────────────

def make(save, grade: str, rnd=random, opts: list | None = None, src: str = "") -> dict:
    """새 비늘석 (+0, 부옵션 1개). opts 를 주면 그 옵션으로 (디버그)."""
    st = state(save)
    uid = st["next_id"]
    st["next_id"] += 1
    if opts is None:
        opts = [roll_option(grade, rnd=rnd)]
    return {"uid": uid, "grade": grade, "level": 0, "opts": opts, "locked": grade == "legend",   # 전설은 얻을 때 자동 잠금
            "spent": {"gold": 0, "mat": 0}, "got": uid, "src": src}


def by_uid(save, uid) -> dict | None:
    return next((s for s in state(save)["items"] if s["uid"] == uid), None)


def equipped_slot(save, uid) -> str | None:
    eq = state(save)["equipped"]
    return next((s for s in SLOTS if eq.get(s) == uid), None)


# ───────────────────────── 장착 · 합계 효과 (S4) ─────────────────────────

def equip(save, uid, slot: str, fighting: bool = False) -> bool:
    """칸에 장착. 원래 그 칸에 있던 비늘석은 보관함으로(장착만 풀림), 다른 칸에 있던 이 비늘석은 새 칸으로 이동 (원래 칸은 빔).
    파이팅 중에는 바꿀 수 없음."""
    if fighting or slot not in SLOTS or by_uid(save, uid) is None:
        return False
    eq = state(save)["equipped"]
    for s in SLOTS:
        if eq.get(s) == uid:
            eq[s] = None
    eq[slot] = uid
    return True


def unequip(save, slot: str, fighting: bool = False) -> bool:
    if fighting or slot not in SLOTS:
        return False
    state(save)["equipped"][slot] = None
    return True


def equipped_stones(save) -> dict:
    """{칸: 비늘석 | None} (없어진 uid 는 None 으로 정리)."""
    eq = state(save)["equipped"]
    out = {}
    for s in SLOTS:
        st = by_uid(save, eq.get(s)) if eq.get(s) is not None else None
        if st is None:
            eq[s] = None
        out[s] = st
    return out


def totals(save) -> dict:
    """장착한 4개의 같은 옵션 합산 → {옵션 id: {"sum", "cap", "eff" (상한 적용), "over" (초과분)}} (붙은 옵션만)."""
    o = options()["options"]
    raw: dict = {}
    for st in equipped_stones(save).values():
        if st is None:
            continue
        for opt in st["opts"]:
            raw[opt["id"]] = raw.get(opt["id"], 0.0) + opt["v"]
    out = {}
    for oid, v in raw.items():
        cap = o[oid]["cap"]
        v = _round(o[oid]["unit"], v)
        eff = min(v, cap)
        out[oid] = {"sum": v, "cap": cap, "eff": eff, "over": _round(o[oid]["unit"], max(0.0, v - cap))}
    return out


def effect(save, oid: str) -> float:
    """옵션 합계(상한 적용) — pct/pp 는 % 숫자 그대로(3.2 = 3.2%), sec 는 초. 장착 없으면 0."""
    if save is None or not isinstance(getattr(save, "data", None), dict) or "scalestone" not in save.data:
        return 0.0
    t = totals(save).get(oid)
    return t["eff"] if t else 0.0


def frac(save, oid: str) -> float:
    """% 옵션을 비율로 (3.2% → 0.032)."""
    return effect(save, oid) / 100.0


def apply_fight(gear: dict, eff: dict) -> dict:
    """장비 수치(Fight 에 넘길 dict) + 비늘석 합계 효과 {옵션 id: 상한 적용 값} → 새 dict (SaveGame.fight_gear · 시뮬이 같이 씀).
    보스 장력 완화 = 전설 · 환상이 당기는 힘 × (1−%) · 장력 한계 = 초록 위쪽 끝 + 초록 폭 × % (S6 승인: '위쪽 끝 × %'는 티어 한 단계를 넘어서 폭 기준으로) · 줄 내구도 × (1+%) · 줄 마모 = 빨강 손상 × (1−%) · 감기 × (1+%) · 퍼펙트 창 × (1+%) ·
    바늘 빠짐 / 꼬임 = 차는 속도 × (1−%) · 예고 여유 = +초."""
    def f(oid):
        return eff.get(oid, 0.0) / 100.0
    g = dict(gear)
    green = list(g["rod_green"])
    green[1] = round(green[1] + (green[1] - green[0]) * f("tension_limit"), 2)
    g["rod_green"] = green
    g["pull_mult"] = g.get("pull_mult", 1.0) * (1 - f("pull_relief"))   # 보스 장력 완화: 전설 · 환상이 당기는 힘 × (1−%) (Fight 목표 장력, 일반 물고기엔 안 씀)
    g["reel_speed"] = g["reel_speed"] * (1 + f("reel_speed"))
    g["line_base"] = g.get("line_base", g["line_max"])   # 열 손상 기준 (줄 내구도 보너스 전, DESIGN 46-10)
    g["line_max"] = round(g["line_max"] * (1 + f("line_durability")))
    g["line_red_mult"] = g.get("line_red_mult", 1.0) * (1 - f("line_wear"))
    g["perfect_mult"] = 1 + f("perfect_window")
    g["hook_fill_mult"] = 1 - f("hook_hold")
    g["twist_mult"] = 1 - f("twist_resist")
    g["warn_add"] = eff.get("warning_lead", 0.0)
    return g


def effects(save) -> dict:
    """{옵션 id: 상한 적용 합계} (장착 4개)."""
    return {oid: t["eff"] for oid, t in totals(save).items()}


# ───────────────────────── 소재 (대륙 소재 2종을 하나처럼) ─────────────────────────

def materials_total(save) -> int:
    m = save.data.get("materials", {})
    return sum(int(m.get(c, 0)) for c in CONTS)


def spend_materials(save, n: int) -> bool:
    """많은 쪽부터 n개. 모자라면 아무것도 쓰지 않고 False."""
    if materials_total(save) < n:
        return False
    m = save.data["materials"]
    left = n
    for c in sorted(CONTS, key=lambda k: -m.get(k, 0)):
        take = min(left, m.get(c, 0))
        m[c] = m.get(c, 0) - take
        left -= take
        if left <= 0:
            break
    return True


def add_materials(save, n: int, cont: str) -> None:
    m = save.data.setdefault("materials", {})
    cont = cont if cont in CONTS else "sharmion"
    m[cont] = m.get(cont, 0) + int(n)


def salvage_yield(stone: dict) -> int:
    """분해 소재 = 등급 기본 + 강화에 쓴 소재의 50%."""
    base = grade_info(stone["grade"])["salvage"]
    return base + int(math.floor(stone.get("spent", {}).get("mat", 0) * enhance_cfg()["salvage_spent_frac"]))


# ───────────────────────── 강화 (S3) ─────────────────────────

def enhance_cost(stone: dict) -> dict | None:
    """다음 단계 비용 {gold, mat} = 단계 비용(희귀 기준) × 등급 배율 — 골드 10원 단위 반올림, 소재 올림. 최대(+4)면 None."""
    cfg = enhance_cfg()
    lvl = stone["level"]
    if lvl >= cfg["max_level"]:
        return None
    k = grade_info(stone["grade"])["cost"]
    return {"gold": int(round(cfg["gold"][lvl] * k / 10.0)) * 10, "mat": int(math.ceil(cfg["materials"][lvl] * k - 1e-9))}


def enhance_block(save, stone: dict) -> str | None:
    """강화할 수 없으면 이유 글자, 되면 None."""
    cost = enhance_cost(stone)
    if cost is None:
        return "최대 강화예요"
    if save.data.get("money", 0) < cost["gold"]:
        return "골드가 부족해요"
    if materials_total(save) < cost["mat"]:
        return "소재가 부족해요"
    return None


def enhance(save, uid, rnd=random) -> dict | None:
    """+1 강화: 비용을 내고 새 부옵션 1개 (이미 붙은 옵션 제외, 비중대로). 실패 없음.
    돌려주는 값: {"stone", "opt", "index" (새 옵션 칸 0~4), "level", "done" (+4 완성), "cost"} — 못 하면 None."""
    stone = by_uid(save, uid)
    if stone is None or enhance_block(save, stone):
        return None
    cost = enhance_cost(stone)
    opt = roll_option(stone["grade"], exclude=[o["id"] for o in stone["opts"]], rnd=rnd)
    if opt is None:
        return None
    save.data["money"] -= cost["gold"]
    spend_materials(save, cost["mat"])
    sp = stone.setdefault("spent", {"gold": 0, "mat": 0})
    sp["gold"] = sp.get("gold", 0) + cost["gold"]
    sp["mat"] = sp.get("mat", 0) + cost["mat"]
    stone["opts"].append(opt)
    stone["level"] += 1
    return {"stone": stone, "opt": opt, "index": len(stone["opts"]) - 1, "level": stone["level"],
            "done": stone["level"] >= enhance_cfg()["max_level"], "cost": cost}


# ───────────────────────── 잠금 · 분해 (S3) ─────────────────────────

def set_locked(save, uid, locked: bool) -> bool:
    stone = by_uid(save, uid)
    if stone is None:
        return False
    stone["locked"] = bool(locked)
    return True


def salvage_block(save, stone: dict) -> str | None:
    """분해할 수 없으면 이유 (잠김 · 장착 중), 되면 None."""
    if stone.get("locked"):
        return "잠긴 비늘석이에요"
    if equipped_slot(save, stone["uid"]):
        return "장착 중인 비늘석이에요"
    return None


def salvage(save, uid, cont: str) -> int | None:
    """분해 → 소재 (기본 + 강화에 쓴 소재 50%, 지금 있는 대륙 소재로). 못 하면 None."""
    st = state(save)
    stone = by_uid(save, uid)
    if stone is None or salvage_block(save, stone):
        return None
    n = salvage_yield(stone)
    st["items"].remove(stone)
    add_materials(save, n, cont)
    return n


def batch_candidates(save, grades_in=None, max_level: int | None = None) -> list[dict]:
    """일괄 분해 대상: 고른 등급 · 강화 단계 이하, 잠김 · 장착 중 제외."""
    out = []
    for s in state(save)["items"]:
        if grades_in is not None and s["grade"] not in grades_in:
            continue
        if max_level is not None and s["level"] > max_level:
            continue
        if salvage_block(save, s):
            continue
        out.append(s)
    return out


def batch_salvage(save, uids, cont: str) -> dict:
    """확인 창에서 [분해] → {"count", "mat"} (그 사이 잠기거나 장착된 것은 건너뜀)."""
    count = mat = 0
    for uid in list(uids):
        n = salvage(save, uid, cont)
        if n is not None:
            count += 1
            mat += n
    return {"count": count, "mat": mat}


# ───────────────────────── 획득 ─────────────────────────

def _pick_grade(table: dict, rnd) -> str:
    gs = list(table)
    return rnd.choices(gs, [table[g] for g in gs])[0]


def grant(save, grade: str, src: str, cont: str = "sharmion", rnd=random) -> dict:
    """비늘석 1개 지급. 보관함(150)이 가득 차면 자동 분해 → 소재.
    돌려주는 값: {"grade", "stone" (보관했으면), "auto_salvage" (분해한 소재 수, 아니면 0), "src"}."""
    st = state(save)
    stone = make(save, grade, rnd, src=src)
    if len(st["items"]) >= enhance_cfg()["storage_max"]:
        n = salvage_yield(stone)
        add_materials(save, n, cont)
        return {"grade": grade, "stone": None, "first_opt": stone["opts"][0], "auto_salvage": n, "src": src}
    st["items"].append(stone)
    return {"grade": grade, "stone": stone, "first_opt": stone["opts"][0], "auto_salvage": 0, "src": src}


def roll_catch(save, fish: dict, cont: str, rnd=random) -> dict | None:
    """포획: 일반 · 고급 0.8%, 희귀 3% → 일반 70 / 고급 25 / 희귀 5."""
    d = drops()["catch"]
    p = d["chance"].get(fish.get("rarity"))
    if not p or rnd.random() >= p:
        return None
    return grant(save, _pick_grade(d["grade"], rnd), "catch", cont, rnd)


def roll_chest(save, chest_grade: str, cont: str, rnd=random) -> dict | None:
    """보물상자: 기존 내용물과 별도 확률 (내용물 · 천장 영향 없음)."""
    d = drops()["chest"].get(chest_grade)
    if not d or rnd.random() >= d["chance"]:
        return None
    return grant(save, _pick_grade(d["grade"], rnd), "chest", cont, rnd)


def grant_table(save, key: str, cont: str, rnd=random) -> dict:
    """legend_first · phantom_first · first_quest · weekly_quest · daily_quest — 등급표대로 1개."""
    return grant(save, _pick_grade(drops()[key]["grade"], rnd), key, cont, rnd)


def on_quest_complete(save, q: dict, cont: str, rnd=random) -> list[dict]:
    """의뢰 완료 보상: 일일 3개 중 표시된 1개 · 주간 = 희귀, 게임 전체 첫 의뢰 = 고급 1번."""
    got = []
    rw = q.get("reward", {})
    if rw.get("stone"):
        got.append(grant_table(save, "weekly_quest" if q.get("weekly") else "daily_quest", cont, rnd))
    st = state(save)
    if not st["first_quest_bonus"]:
        st["first_quest_bonus"] = True
        got.append(grant_table(save, "first_quest", cont, rnd))
    return got


def news_line(info: dict) -> tuple[str, tuple]:
    """포획 카드 · 결과 화면 한 줄: '비늘석 희귀 · 감기 속도 +3.1%' (가득 차서 분해했으면 그 안내)."""
    g = grade_info(info["grade"])
    if info.get("auto_salvage"):
        return "보관함이 가득 차서 소재로 바꿨어요", tuple(g["color"])
    return f"비늘석 {g['name']} · {option_text(info['first_opt'])}", tuple(g["color"])


# ───────────────────────── 디버그 ─────────────────────────

def debug_make(save, grade: str, opt_ids: list | None = None, rnd=random) -> dict:
    """등급 · 옵션을 지정해서 비늘석 생성 (옵션 수치는 범위에서 뽑음, opt_ids 길이 = 부옵션 수 → 강화 단계 len-1)."""
    if opt_ids:
        o = options()["options"]
        opts = []
        for oid in opt_ids[:5]:
            lo, hi = o[oid]["range"]
            opts.append({"id": oid, "v": _round(o[oid]["unit"], rnd.uniform(lo, hi) * grade_info(grade)["mult"])})
    else:
        opts = None
    stone = make(save, grade, rnd, opts=opts, src="debug")
    stone["level"] = max(0, len(stone["opts"]) - 1)
    state(save)["items"].append(stone)
    return stone
