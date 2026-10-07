"""비늘석 전체 검증 (SCALESTONE.md Phase S6, DESIGN.md 46-7).

  python tools/scalestone_check.py            전부 (1~7)
  python tools/scalestone_check.py fight      3. 파이팅만 (n 판 기본 40 — 'fight 80' 처럼)
  python tools/scalestone_check.py econ       2 · 4. 강화 비용 · 경제만

1. 획득: 낚시터(샤르미온 초반 · 중반 · 후반, 엘드라시온)별 시간당 비늘석 개수 · 등급 분포 (tools/scalestone_sim.py 와 같은 가정)
2. 강화 비용 ÷ 시간당 수입: 희귀 +4 하나 (9,200원 · 소재 75) 만드는 데 몇 시간
3. 파이팅: 비늘석 없음 / 평균 세팅 (희귀 +4 ×4, 부옵션 무작위) / 최고 세팅 (파이팅 옵션 8종 모두 상한 — 실제로는 못 만드는 위쪽 끝)
   티어별 포획 성공률 · 평균 파이팅 시간 (balance_sim 봇 '보통'). 최고 세팅 T(n) 이 맨몸 T(n+1) 보다 강하면 표시
4. 경제: 시간당 판매 골드 증가 (판매가 · 희귀 확률 · 대물 확률) — 기존 대비 +10% 이내인지
5. 로그: 합계 상한 · 한 돌 안 중복 금지 · 희귀 확률이 전설 · 환상에 영향 없는지
6. 옛 세이브 3종: 환급 금액 · 환영 선물 · 안내
7. 장비 강화 코드 · 데이터가 남아 있지 않은지 검색
"""
import copy
import os
import random
import re
import statistics
import sys
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))
os.chdir(ROOT)
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

from src.core.config import load_json  # noqa: E402
from src.fishing import rank as rank_mod  # noqa: E402
from src.fishing.bite import pick_fish, roll_size  # noqa: E402
from src.save import scalestone as ss  # noqa: E402

SPOTS = {s["id"]: s for s in load_json("spots.json")["spots"]}
STAGE = {"reservoir": "샤르미온 초반", "valley": "샤르미온 초반", "breakwater": "샤르미온 중반", "offshore": "샤르미온 후반",
         "deep": "샤르미온 후반", "secret": "샤르미온 후반"}
FISH_PER_H = 50
RANKS = {"S": 0.35, "A": 0.40, "B": 0.20, "C": 0.05}   # balance_sim HUMAN 숙련
FIGHT_OPTS = ["tension_limit", "line_durability", "line_wear", "reel_speed", "perfect_window", "hook_hold", "twist_resist",
              "warning_lead"]


class _Save:
    def __init__(self):
        self.data = {"money": 0, "materials": {"sharmion": 0, "eldrasion": 0, "rare": 0}}


def stage(spot_id: str) -> str:
    return STAGE.get(spot_id, "엘드라시온")


# ───────────────────────── 세팅 ─────────────────────────

def avg_setup(n: int = 3000, grade: str = "rare") -> dict:
    """희귀 +4 비늘석 4개 (부옵션 5개 무작위) 를 장착했을 때 옵션별 합계(상한 적용)의 평균."""
    rnd = random.Random(11)
    acc = Counter()
    for _ in range(n):
        sv = _Save()
        for slot in ss.SLOTS:
            st = ss.grant(sv, grade, "sim", "sharmion", rnd)["stone"]
            for _ in range(4):
                st["opts"].append(ss.roll_option(grade, exclude=[o["id"] for o in st["opts"]], rnd=rnd))
            st["level"] = 4
            ss.equip(sv, st["uid"], slot)
        for oid, v in ss.effects(sv).items():
            acc[oid] += v
    return {oid: round(v / n, 3) for oid, v in acc.items()}


def best_fight() -> dict:
    o = ss.options()["options"]
    return {oid: o[oid]["cap"] for oid in FIGHT_OPTS}


def best_econ() -> dict:
    o = ss.options()["options"]
    return {oid: o[oid]["cap"] for oid in ("sell_price", "rare_chance", "trophy_chance")}


# ───────────────────────── 1. 획득 ─────────────────────────

def acquisition() -> None:
    print("## 1. 획득 (시간당 50마리 · 상자 4개 · 하루 1시간 = 일일 의뢰 1 + 주간 1/7, 200시간)")
    import scalestone_sim
    from io import StringIO
    buf, old = StringIO(), sys.stdout
    sys.stdout = buf
    try:
        scalestone_sim.run(200)
    finally:
        sys.stdout = old
    rows = [ln for ln in buf.getvalue().splitlines() if ln.split(" ")[0] in SPOTS]
    for ln in rows:
        sid = ln.split(" ")[0]
        print(f"  {stage(sid):8s} {ln}")
    print()


# ───────────────────────── 2 · 4. 경제 ─────────────────────────

def spot_income(spot_id: str, eff: dict, n: int = 20000, seed: int = 5) -> dict:
    """한 마리 평균 판매가 · 시간당 골드 · 분해하면 시간당 소재 (eff = 비늘석 합계 효과)."""
    rnd = random.Random(seed)
    fish_here = [f for f in load_json("fish.json")["fish"] if f["spot"] == spot_id]
    combos = sorted({(t, w) for f in fish_here if f["rarity"] != "legend" for t in f["times"] for w in f["weathers"]})
    trophy = eff.get("trophy_chance", 0.0) / 100
    sell = eff.get("sell_price", 0.0) / 100
    rare_pp = eff.get("rare_chance", 0.0)
    dis = load_json("equipment.json")["_rules"]["disassemble"]
    tot = mats = 0.0
    k = 0
    rarity = Counter()
    while k < n:
        per, we = rnd.choice(combos)
        f = pick_fish(per, we, 20, rnd, spot_id, rare_pp=rare_pp)
        if f is None:
            continue
        k += 1
        rarity[f["rarity"]] += 1
        rk = rnd.choices(list(RANKS), list(RANKS.values()))[0]
        size = rank_mod.final_size(roll_size(f, 20, rnd, trophy=trophy), rk)
        tot += rank_mod.sell_price(f, size, rk) * (1 + sell)
        mats += dis.get(f["rarity"], 0) * (1 + eff.get("material_gain", 0.0) / 100)
    return {"price": tot / n, "gold_h": tot / n * FISH_PER_H, "mat_h": mats / n * FISH_PER_H,
            "rare": rarity["rare"] / n}


def economy(avg: dict) -> None:
    print("## 2. 강화 비용 ÷ 시간당 수입 (희귀 +4 = 9,200원 · 소재 75)")
    cost_g = sum(ss.enhance_cost({"grade": "rare", "level": i})["gold"] for i in range(4))
    cost_m = sum(ss.enhance_cost({"grade": "rare", "level": i})["mat"] for i in range(4))
    print(f"  희귀 +4 합계: {cost_g:,}원 · 소재 {cost_m}")
    print("  낚시터          단계          시간당 판매(원)   골드 시간   소재(전부 분해) 시간당   소재 시간   분해로 잃는 판매")
    base = {}
    for sid in SPOTS:
        inc = spot_income(sid, {})
        base[sid] = inc
        h_g = cost_g / inc["gold_h"]
        h_m = cost_m / inc["mat_h"] if inc["mat_h"] else float("inf")
        lost = cost_m / max(1e-9, inc["mat_h"] / FISH_PER_H) * inc["price"]   # 소재 75개를 모으려고 분해한 물고기 값
        print(f"  {sid:14s} {stage(sid):10s} {inc['gold_h']:>14,.0f}   {h_g:8.2f}h   {inc['mat_h']:>18.1f}   {h_m:8.2f}h   {lost:>12,.0f}원")
    print()
    print("## 4. 경제: 시간당 판매 골드 (비늘석 없음 대비)")
    print("  낚시터          평균 세팅 (판매가 · 희귀 · 대물)        최고 세팅 (판매가 10% · 희귀 2.5%p · 대물 12%)")
    best = best_econ()
    av = {k: avg.get(k, 0.0) for k in ("sell_price", "rare_chance", "trophy_chance", "material_gain")}
    worst = 0.0
    for sid in SPOTS:
        b = base[sid]["gold_h"]
        a = spot_income(sid, av)["gold_h"]
        x = spot_income(sid, best)["gold_h"]
        worst = max(worst, x / b - 1)
        print(f"  {sid:14s} {a / b * 100 - 100:+6.1f}%  ({a:>10,.0f})            {x / b * 100 - 100:+6.1f}%  ({x:>10,.0f})")
    print(f"  평균 세팅 효과: 판매가 +{av['sell_price']:.2f}% · 희귀 +{av['rare_chance']:.2f}%p · 대물 +{av['trophy_chance']:.2f}%")
    print(f"  → 최고 세팅 최대 증가 {worst * 100:+.1f}% ({'+10% 이내' if worst <= 0.10 + 1e-9 else '⚠ +10% 넘음'})")
    print()


# ───────────────────────── 3. 파이팅 ─────────────────────────

def fights(n: int = 40) -> None:
    import balance_sim as bs
    print(f"## 3. 파이팅 (봇 '보통', 낚시터 희귀 중 가장 힘센 종, {n}판씩)")
    avg = avg_setup()
    best = best_fight()
    print("  평균 세팅 (희귀 +4 ×4, 파이팅 옵션): " + ", ".join(f"{ss.options()['options'][k]['name']} {avg.get(k, 0):g}"
                                                         for k in FIGHT_OPTS))
    print("  최고 세팅 (파이팅 옵션 모두 상한): " + ", ".join(f"{ss.options()['options'][k]['name']} {best[k]:g}" for k in FIGHT_OPTS))
    by_tier: dict = {}
    for f in bs.all_fish():
        if f["rarity"] != "rare":
            continue
        t = SPOTS[f["spot"]].get("gear_tier", 1)
        if t not in by_tier or f.get("stamina", 100) * f.get("power", 1) > by_tier[t].get("stamina", 100) * by_tier[t].get("power", 1):
            by_tier[t] = f

    def run(fish, tier, eff, seed):
        rnd = random.Random(seed)
        gear = ss.apply_fight(bs.gear_for_tier(tier), eff)
        rows = [bs.bot_fight(fish, SPOTS[fish["spot"]], gear, bs.SKILLS["average"], rnd) for _ in range(n)]
        ok = [r for r in rows if r["ok"]]
        return {"s": len(ok) / n, "t": statistics.mean(r["t"] for r in ok) if ok else None,
                "lose": Counter(r["reason"] for r in rows if not r["ok"])}

    def fmt(r):
        t = f"{r['t']:5.1f}s" if r["t"] is not None else "   - "
        return f"{r['s'] * 100:5.1f}% {t}"
    print("  티어  물고기            맨몸 T(n)          평균 T(n)          최고 T(n)       |  다음 티어 물고기: 최고 T(n)  vs  맨몸 T(n+1)")
    flags = []
    tiers = sorted(by_tier)
    for t in tiers:
        f = by_tier[t]
        r0, r1, r2 = run(f, t, {}, 1), run(f, t, avg, 1), run(f, t, best, 1)
        line = f"  T{t}   {f['name']:<14} {fmt(r0)}   {fmt(r1)}   {fmt(r2)}"
        nxt = next((x for x in tiers if x > t), None)
        if nxt is not None:
            g = by_tier[nxt]
            a, b = run(g, t, best, 2), run(g, nxt, {}, 2)
            stronger = a["s"] > b["s"] + 0.05 or (abs(a["s"] - b["s"]) <= 0.05 and a["t"] and b["t"] and a["t"] < b["t"] * 0.95)
            line += f"   |  {g['name']:<12} {fmt(a)}  vs  {fmt(b)}" + ("   ⚠ 최고 T(n) 이 더 강함" if stronger else "")
            if stronger:
                flags.append((t, nxt))
        print(line)
    print("  → " + ("최고 세팅이어도 다음 티어 맨몸보다 약함 (장비 티어가 여전히 중요)" if not flags else
                    f"⚠ 최고 세팅 T(n) 이 맨몸 T(n+1) 보다 강한 곳: {flags}"))
    print()


# ───────────────────────── 5. 로그 ─────────────────────────

def logs() -> None:
    print("## 5. 로그")
    rnd = random.Random(3)
    sv = _Save()
    sv.data["money"] = 10 ** 9
    sv.data["materials"]["sharmion"] = 10 ** 6
    dup = 0
    for i in range(3000):
        st = ss.grant(sv, rnd.choice(ss.grades()["order"]), "t", "sharmion", rnd)["stone"]
        for _ in range(4):
            ss.enhance(sv, st["uid"], rnd)
        dup += len(st["opts"]) - len({o["id"] for o in st["opts"]})
        if len(ss.state(sv)["items"]) > 140:
            ss.state(sv)["items"].clear()
    print(f"  한 돌 안 중복: 3,000개 +4 → 중복 {dup}개")
    sv = _Save()
    o = ss.options()["order"]
    for slot in ss.SLOTS:
        st = ss.debug_make(sv, "legend", o[:5], rnd)
        ss.equip(sv, st["uid"], slot)
    over = {k: v for k, v in ss.totals(sv).items() if v["over"] > 0}
    print("  합계 상한 (전설 +4 ×4 같은 옵션 5종): " + ", ".join(f"{ss.options()['options'][k]['name']} 합 {v['sum']} → {v['eff']} (초과 {v['over']})"
                                                       for k, v in over.items()))
    ok = all(v["eff"] <= v["cap"] for v in ss.totals(sv).values())
    print(f"  모든 옵션 적용값 ≤ 상한: {ok}")
    # 희귀 확률: 희귀 등급만
    for sid, per, we in (("valley", "night", "rain"), ("breakwater", "night", "rain")):
        def share(rpp):
            r = random.Random(1)
            c = Counter(pick_fish(per, we, 20, r, sid, rare_pp=rpp)["rarity"] for _ in range(30000))
            return {k: round(v / 300, 2) for k, v in sorted(c.items())}
        print(f"  희귀 확률 {sid} {per}/{we}: 없음 {share(0)} → +2.5%p {share(2.5)}")
    legends = [f for f in load_json("fish.json")["fish"] if f["rarity"] == "legend"]
    w = load_json("fishing_config.json")["bite"]["rarity_weight"].get("legend", 0)
    print(f"  전설 {len(legends)}종: pick_fish 기본 가중치 {w} (전설은 전용 미끼 · legend_candidate 로만) · 희귀 확률은 rarity == 'rare' 만 바꿈")
    print("  환상: src/fishing/phantom.py 별도 판정 (bite.rare_pp 를 읽지 않음) · 변이: mutation.roll 별도 → 영향 없음")
    print()


# ───────────────────────── 6. 옛 세이브 ─────────────────────────

def old_saves() -> None:
    from src.save.save_game import migrate, new_data
    print("## 6. 옛 세이브 3종")
    cases = []
    a = new_data()
    a.pop("scalestone")
    a["enhance"] = {}
    cases.append(("A 강화 안 한 초반 세이브", a))
    b = new_data()
    b.pop("scalestone")
    b["enhance"] = {"glass": 3, "carbon": 3, "hm_carbon": 2, "light_reel": 3, "bait_reel": 1, "nylon4": 2, "alu_net": 1}
    b["stats"]["quests_done"] = 12
    cases.append(("B 샤르미온 강화 많이 + 의뢰 12번", b))
    c = new_data()
    c.pop("scalestone")
    c["enhance"] = {"crystal_rod": 3, "nebula_rod": 2, "crystal_reel": 3, "crystal_line": 1, "crystal_net": 2, "master_rod": 3}
    c["stats"]["quests_done"] = 40
    c["unlocked_continents"] = ["sharmion", "eldrasion"]
    cases.append(("C 엘드라시온 장비 강화 + 의뢰 40번", c))
    for name, d in cases:
        m0, mats0 = d["money"], dict(d.get("materials", {}))
        m = migrate(copy.deepcopy(d))
        w = m["scalestone"]["welcome"]
        gift = ss.by_uid(type("S", (), {"data": m})(), w["gift"])
        dm = {k: m["materials"].get(k, 0) - mats0.get(k, 0) for k in ("sharmion", "eldrasion", "rare")}
        print(f"  {name}: 환급 {m['money'] - m0:,}원 · 소재 {dm} · 안내 {w['pending']} · 선물 {gift['grade']} ({ss.option_text(gift['opts'][0])})"
              f" · 첫 의뢰 보너스 지급 완료 {m['scalestone']['first_quest_bonus']} · enhance 남음 {'enhance' in m}")
        again = migrate(m)
        print(f"     다시 불러와도: 비늘석 {len(again['scalestone']['items'])}개 (한 번만)")
    print('  안내 문구: "장비 강화가 비늘석으로 바뀌었어요!" / "강화에 쓴 골드와 소재는 모두 돌려드렸어요." (scene/scalestone_notice.py)')
    print()


# ───────────────────────── 7. 남은 강화 코드 ─────────────────────────

def leftovers() -> None:
    print("## 7. 장비 강화 코드 · 데이터 검색")
    pats = [r"enhance_level", r"enhanced\(", r"enhance_gain", r"enhance_kinds", r"gap_frac", r"data\[\"enhance\"\]",
            r"\.effective\(", r"shop_enhance", r"shop\.enhance\.", r"interior\.menu\.enhance", r'"enhance"']
    hits = []
    for base in ("src", "data", "tools"):
        for d, _, files in os.walk(base):
            for fn in files:
                if not fn.endswith((".py", ".json")) or fn == "scalestone_check.py":
                    continue
                p = os.path.join(d, fn)
                for i, ln in enumerate(open(p, encoding="utf-8", errors="ignore"), 1):
                    for pat in pats:
                        if re.search(pat, ln):
                            hits.append(f"{p}:{i}: {ln.strip()[:110]}")
    allowed = ("src/save/save_game.py",)   # 옛 세이브 환급 (data.pop('enhance') · _OLD_ENHANCE)
    npc = [h for h in hits if "_react(" in h]   # NPC 반응 대사 종류 react_enhance (특급 배송 · 비늘석 강화 때 웃음) — 장비 강화 아님
    real = [h for h in hits if not h.startswith(allowed) and h not in npc]
    for h in hits:
        print(("  (환급용) " if h.startswith(allowed) else "  (NPC 반응) " if h in npc else "  ⚠ ") + h)
    print(f"  → 남은 강화 코드: {len(real)}곳" + (" (없음)" if not real else ""))
    print()


def main() -> None:
    args = sys.argv[1:]
    if args and args[0] == "fight":
        fights(int(args[1]) if len(args) > 1 else 40)
        return
    avg = avg_setup()
    if args and args[0] == "econ":
        economy(avg)
        return
    acquisition()
    economy(avg)
    fights(int(args[0]) if args else 40)
    logs()
    old_saves()
    leftovers()


if __name__ == "__main__":
    main()
