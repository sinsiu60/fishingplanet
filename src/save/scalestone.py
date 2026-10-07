"""비늘석 (SCALESTONE.md, DESIGN.md 46장): 장비 칸(낚싯대 · 릴 · 줄 · 뜰채)에 하나씩 끼우는 강화 돌.

데이터: data/scalestone/options.json · grades.json · enhance.json · drops.json
세이브: data["scalestone"] = {"items": [...], "equipped": {rod, reel, line, net: uid | None}, "first_quest_bonus": bool, "next_id": n}
아이템: {"uid", "grade", "level", "opts": [{"id", "v"}], "locked", "spent": {"gold", "mat"}, "got": 획득 순번, "src": 출처}

S2: 데이터 · 아이템 구조 · 첫 부옵션 뽑기 · 획득(포획 · 의뢰 · 상자 · 첫 포획 · 첫 의뢰) · 보관 150개(가득 차면 자동 분해) · 디버그.
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
