"""랭크 개편 · 백 노인 시험 분석 (BAEK_EXAM.md EX1, DESIGN.md 49-1). 게임 코드는 바꾸지 않고 측정만.

  python tools/rank_exam_sim.py record [n]    낚시터마다 봇 '보통'(average) · '잘함'(skilled) n판 (기본 300) — 판마다 응답 기록
                                              → build/rank_exam_records.json
  python tools/rank_exam_sim.py report        지금 식 / 새 식(BAEK_EXAM 🅰-2) 분포 · 평균 판매 배율 · 항목 평균 + 목표에 맞는 숫자 찾기

판마다 기록: 지금 랭크 · 점수 항목, 응답 기회(점프 · 몸털기 · 몸부림 · 꺾기 · 패턴)의 퍼펙트 / 좋음 / 놓침 수,
줄 손상 · 경과 · par · 크기 비율. 패턴 성공은 지금 퍼펙트 수에 안 들어가므로(연출 등급만) Fight 를 감싸서 등급까지 셈.
물고기는 그 낚시터 일반 · 고급 · 희귀 중 출현 가중치(시간 · 날씨 무시)로, 장비는 그 낚시터 티어 기본 (balance_sim 과 같음).
"""
import json
import os
import random
import math
import statistics
import zlib
import sys
from multiprocessing import Pool

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))

import balance_sim as bs  # noqa: E402
from src.core.config import load_json  # noqa: E402
from src.fishing import fight as fight_mod  # noqa: E402
from src.save.save_game import all_fish  # noqa: E402

OUT = os.path.join(ROOT, "build", "rank_exam_records.json")
TARGET = {"average": {"S": (0.10, 0.15), "A": (0.35, 0.45), "B": (0.30, 0.40), "C": (0.05, 0.15)},
          "skilled": {"S": (0.30, 0.40), "A": (0.40, 0.50), "B": (0.0, 1.0), "C": (0.0, 0.03)}}
NEW = {"line_max": 30, "time_max": 20, "signal_max": 50, "signal_none": 35, "good_credit": 0.6, "per_miss": 6,
       "S": 90, "S_min_perfects": 2, "A": 75, "B": 55}


def _instrument():
    """Fight 를 감싸 응답 판정을 등급까지 센다 (게임 코드는 그대로)."""
    F = fight_mod.Fight
    if getattr(F, "_ex_wrapped", False):
        return
    F._ex_wrapped = True

    def wrap(name, fn_before):
        orig = getattr(F, name)

        def w(self, *a, **k):
            ex = self.__dict__.setdefault("_ex", {"P": 0, "G": 0, "M": 0})
            fn_before(self, ex, *a, **k)
            return orig(self, *a, **k)
        setattr(F, name, w)

    wrap("_perfect", lambda s, ex: ex.__setitem__("P", ex["P"] + 1))
    wrap("_good", lambda s, ex: ex.__setitem__("G", ex["G"] + 1))
    wrap("_miss", lambda s, ex, kind: ex.__setitem__("M", ex["M"] + 1))
    wrap("_thrash_miss", lambda s, ex, idx, kind="miss_none": ex.__setitem__("M", ex["M"] + (1 if idx == 1 else 0)))
    orig_pr = F.pattern_result

    def pr(self, pid, result):
        ex = self.__dict__.setdefault("_ex", {"P": 0, "G": 0, "M": 0})
        orig_pr(self, pid, result)
        if result == "fail":
            ex["M"] += 1
        elif self.last_grade == "perfect":
            ex["P"] += 1
        else:
            ex["G"] += 1
    F.pattern_result = pr


def _spot_pool(spot_id: str) -> list:
    cfg = load_json("fishing_config.json")["bite"]
    out = []
    for f in all_fish():
        if f["spot"] != spot_id or f["rarity"] not in ("common", "uncommon", "rare"):
            continue
        out.append((f, f.get("spawn_weight", cfg["rarity_weight"].get(f["rarity"], 0))))
    return out


def _job(args):
    spot_id, skill, n, seed = args
    _instrument()
    rnd = random.Random(seed)
    spot = next(s for s in load_json("spots.json")["spots"] if s["id"] == spot_id)
    pool = _spot_pool(spot_id)
    gear = bs.gear_for_tier(spot.get("gear_tier", 1))
    rows = []
    orig_init = fight_mod.Fight.__init__
    holder = {}

    def init(self, *a, **k):
        orig_init(self, *a, **k)
        holder["f"] = self
    fight_mod.Fight.__init__ = init
    try:
        for _ in range(n):
            fish = rnd.choices([p[0] for p in pool], [p[1] for p in pool])[0]
            r = bs.bot_fight(fish, spot, gear, bs.SKILLS[skill], rnd)
            f = holder["f"]
            ex = f.__dict__.get("_ex", {"P": 0, "G": 0, "M": 0})
            flick_p = sum(1 for e in f.events if e == "flick_perfect")
            flick_g = sum(1 for e in f.events if e == "flick_good")
            flick_m = sum(1 for e in f.events if e == "flick_miss")
            P = ex["P"] - getattr(f, "double_perfects", 0) + flick_p   # 더블 퍼펙트 보너스는 기회가 아님
            G, M = ex["G"] + flick_g, ex["M"] + flick_m
            lo, hi = fish["size_cm"]
            row = {"fish": fish["id"], "rarity": fish["rarity"], "ok": r["ok"], "P": P, "G": G, "M": M,
                   "misses": f.misses, "elapsed": round(f.elapsed, 2), "par": round(f.par, 2),
                   "u": round(max(0.0, min(1.0, (f.size_cm - lo) / max(1e-6, hi - lo))), 3)}
            if f.result:
                sc = f.result["score"]
                row.update(rank=f.result["rank"], dmg=round(f.result["line_damage"], 4), old_perfects=f.perfects,
                           old=dict(perfect=sc["perfect_pts"], line=sc["line_pts"], time=sc["time_pts"], miss=sc["miss_pts"],
                                    score=sc["score"]))
            rows.append(row)
    finally:
        fight_mod.Fight.__init__ = orig_init
    return spot_id, skill, rows


def record(n: int = 300) -> None:
    spots = [s["id"] for s in load_json("spots.json")["spots"] if _spot_pool(s["id"])]
    jobs = []
    for sp in spots:
        for sk in ("average", "skilled"):
            for c in range(4):   # 4 조각으로 나눠 병렬
                jobs.append((sp, sk, n // 4, zlib.crc32(f"{sp}:{sk}:{c}".encode())))
    out = {}
    with Pool(4) as p:
        for i, (sp, sk, rows) in enumerate(p.imap_unordered(_job, jobs)):
            out.setdefault(sp, {}).setdefault(sk, []).extend(rows)
            print(f"[{i + 1}/{len(jobs)}] {sp} {sk} +{len(rows)}", flush=True)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as fp:
        json.dump(out, fp, ensure_ascii=False)


# ───────────────────────── 새 식 ─────────────────────────

def new_score(row: dict, c: dict) -> tuple[float, str, dict]:
    line = c["line_max"] * (1 - max(0.0, min(1.0, row["dmg"])))
    if row["elapsed"] <= row["par"]:
        tm = c["time_max"]
    else:
        tm = max(0.0, c["time_max"] * (1 - (row["elapsed"] - row["par"]) / row["par"]))
    n = row["P"] + row["G"] + row["M"]
    sig = c["signal_none"] if n == 0 else c["signal_max"] * (row["P"] + c["good_credit"] * row["G"]) / n
    miss = -c["per_miss"] * row["misses"]
    s = line + tm + sig + miss
    if s >= c["S"] and row["P"] >= c["S_min_perfects"]:
        rk = "S"
    elif s >= c["A"]:
        rk = "A"
    elif s >= c["B"]:
        rk = "B"
    else:
        rk = "C"
    return s, rk, {"line": line, "time": tm, "signal": sig, "miss": miss, "opps": n}


def dist(rows, key=None, c=None) -> dict:
    ok = [r for r in rows if r["ok"]]
    out = {k: 0 for k in "SABC"}
    for r in ok:
        rk = r["rank"] if c is None else new_score(r, c)[1]
        out[rk] += 1
    return {k: v / max(1, len(ok)) for k, v in out.items()}


def avg_mult(d: dict, pm: dict) -> float:
    return sum(d[k] * pm[k] for k in "SABC")


def fit_err(d: dict, skill: str) -> float:
    e = 0.0
    for k, (lo, hi) in TARGET[skill].items():
        if d[k] < lo:
            e += (lo - d[k]) ** 2
        elif d[k] > hi:
            e += (d[k] - hi) ** 2
    return e


def report() -> None:
    data = json.load(open(OUT, encoding="utf-8"))
    pm = load_json("fishing_config.json")["rank"]["price_mult"]
    all_rows = {"average": [], "skilled": []}
    print("## 지금 식 · 새 식(문서 기본값) — 낚시터별 (포획한 판만)\n")
    print("| 낚시터 | 봇 | 성공 | 지금 S/A/B/C | 지금 평균 배율 | 새 S/A/B/C | 응답 기회 평균 | 퍼펙트 평균 |")
    print("|---|---|---|---|---|---|---|---|")
    for sp, by in data.items():
        for sk in ("average", "skilled"):
            rows = by[sk]
            all_rows[sk] += rows
            ok = [r for r in rows if r["ok"]]
            d0, d1 = dist(rows), dist(rows, c=NEW)
            opps = statistics.mean(r["P"] + r["G"] + r["M"] for r in ok) if ok else 0
            pf = statistics.mean(r["P"] for r in ok) if ok else 0
            f = lambda d: "/".join(f"{d[k] * 100:.0f}" for k in "SABC")  # noqa: E731
            print(f"| {sp} | {'보통' if sk == 'average' else '잘함'} | {len(ok) / len(rows) * 100:.0f}% | {f(d0)} | "
                  f"{avg_mult(d0, pm):.3f} | {f(d1)} | {opps:.1f} | {pf:.1f} |")
    print("\n## 전체 (낚시터 합)\n")
    for sk, rows in all_rows.items():
        ok = [r for r in rows if r["ok"]]
        d0, d1 = dist(rows), dist(rows, c=NEW)
        old = {k: statistics.mean(r["old"][k] for r in ok) for k in ("perfect", "line", "time", "miss", "score")}
        comp = [new_score(r, NEW)[2] for r in ok]
        new = {k: statistics.mean(c[k] for c in comp) for k in ("line", "time", "signal", "miss", "opps")}
        zero = sum(1 for c in comp if c["opps"] == 0) / len(comp)
        print(f"- {sk}: 지금 {d0} 평균 배율 {avg_mult(d0, pm):.3f} · 지금 항목 평균 {old}")
        print(f"  새(기본값) {d1} · 새 항목 평균 {new} · 응답 기회 0번 {zero * 100:.0f}%")
    # 목표에 맞는 숫자 찾기
    print("\n## 목표 분포(🅰-3)에 맞는 숫자 (격자 탐색)\n")
    best = []
    for S in (88, 90, 92, 94, 96):
        for A in (75, 78, 81, 84, 87):
            for B in (55, 60, 65, 70):
                for gc in (0.4, 0.5, 0.6):
                    for none in (35, 40):
                        for pmiss in (6, 8):
                            for smp in (2, 3):
                                if not S > A > B:
                                    continue
                                c = dict(NEW, S=S, A=A, B=B, good_credit=gc, signal_none=none, per_miss=pmiss, S_min_perfects=smp)
                                e = sum(fit_err(dist(all_rows[sk], c=c), sk) for sk in all_rows)
                                best.append((e, c))
    best.sort(key=lambda x: x[0])
    for e, c in best[:5]:
        da, ds = dist(all_rows["average"], c=c), dist(all_rows["skilled"], c=c)
        print(f"- 오차 {e:.4f}: S {c['S']} · A {c['A']} · B {c['B']} · 좋음 {c['good_credit']} · 기회0 {c['signal_none']} · "
              f"실수 {c['per_miss']} · S퍼펙트 {c['S_min_perfects']} → 보통 {fmt(da)} / 잘함 {fmt(ds)}")
    c = best[0][1]
    # 판매 배율: 문서 예시 모양(S 2.8 · A 2.1 · B 1.6 · C 1.1)을 비율 그대로 늘리고 줄여 '보통' 평균 배율을 지금과 같게
    old_avg = avg_mult(dist(all_rows["average"]), pm)
    shape = {"S": 2.8, "A": 2.1, "B": 1.6, "C": 1.1}
    dn = dist(all_rows["average"], c=c)
    k = old_avg / avg_mult(dn, shape)
    newpm = {r: round(v * k, 2) for r, v in shape.items()}
    print(f"\n## 판매 배율: 지금 '보통' 평균 {old_avg:.3f} → 새 분포 {fmt(dn)} 에서 같은 평균이 되는 값 = {newpm} "
          f"(평균 {avg_mult(dn, newpm):.3f}, S/C = {newpm['S'] / newpm['C']:.2f}) · '잘함' 평균 {avg_mult(dist(all_rows['skilled'], c=c), newpm):.3f} "
          f"(지금 {avg_mult(dist(all_rows['skilled']), pm):.3f})")
    json.dump({"best": c, "price_mult": newpm}, open(os.path.join(ROOT, "build", "rank_exam_best.json"), "w"))


def fmt(d):
    return " ".join(f"{k}{d[k] * 100:.0f}" for k in "SABC")


# ───────────────────────── 자격 달성 시간 (🅱-2) ─────────────────────────

def qualify(runs: int = 200, dex_r: float = 0.8, star_r: float = 0.3, s_rate: float = 0.125, success: float = 0.8,
            per_hour: int = 50, quiet: bool = False) -> dict:
    """티어마다: 그 티어 낚시터만 · 시간당 50마리 시도 · 시간대 · 날씨 순환 · 미끼 없음 (전설 없음 → ③ 은 '희귀 전부' 경로).
    별: ★1 첫 포획 · ★2 S (포획마다 s_rate) · ★3 대물 (bite.roll_size, 던지기 30m) · ★4 변이 3종 (방파제 해금 뒤 = T3 부터) · ★5 숙련."""
    from src.fishing.bite import pick_fish, roll_size
    from src.fishing import mutation
    from src.save import dexbook
    spots = load_json("spots.json")["spots"]
    mcfg = mutation.cfg()
    kinds = list(mcfg["kinds"])
    kw = [mcfg["kinds"][k]["weight"] for k in kinds]
    res = {}
    for T in range(2, 9):
        base = [s for s in spots if s["gear_tier"] == T - 1]
        fl = [f for f in all_fish() if f["spot"] in [s["id"] for s in base] and f["rarity"] != "legend"]
        need_dex = math.ceil(len(fl) * dex_r)
        need_star = math.ceil(5 * len(fl) * star_r)
        rares = [f["id"] for f in fl if f["rarity"] == "rare"]
        mut_on = T >= 3
        hrs = {"dex": [], "star": [], "rare": [], "all": []}
        for run in range(runs):
            rnd = random.Random(run * 7 + T)
            t_game = rnd.uniform(0, 24)
            cnt, big, muts, s_got = {}, set(), {}, set()
            got = {}
            weather = {}
            n = 0
            while n < per_hour * 40:
                n += 1
                h = t_game % 24
                period = "night" if h >= 20 or h < 6 else "morning" if h < 10 else "day" if h < 17 else "evening"
                # 낚시터: 아직 못 잡은 종이 가장 많은 곳 (다 잡았으면 차례로)
                def missing(sp):
                    return sum(1 for f in fl if f["spot"] == sp["id"] and f["id"] not in cnt)
                sp = max(base, key=lambda s: (missing(s), rnd.random()))
                blk = int(t_game // 3)
                if (sp["id"], blk) not in weather:
                    w = sp["weather"]
                    weather[(sp["id"], blk)] = rnd.choices(list(w), list(w.values()))[0]
                wt = weather[(sp["id"], blk)]
                t_game += 24 * (3600 / per_hour) / 1200   # 게임 하루 = 실제 20분 → 한 번 시도(72초) = 게임 1.44시간
                fish = pick_fish(period, wt, 30.0, rnd, spot=sp["id"])
                if fish is None or fish["rarity"] == "legend" or rnd.random() > success:
                    continue
                fid = fish["id"]
                cnt[fid] = cnt.get(fid, 0) + 1
                if rnd.random() < s_rate:
                    s_got.add(fid)
                lo, hi = fish["size_cm"]
                if roll_size(fish, 30.0, rnd) >= lo + 0.9 * (hi - lo):
                    big.add(fid)
                if mut_on:
                    k = mcfg["storm_mult"] if wt == "storm" else 1.0
                    r = rnd.random()
                    m = 2 if r < mcfg["chance_two"] * k else 1 if r < (mcfg["chance_two"] + mcfg["chance_one"]) * k else 0
                    for _ in range(m):
                        muts.setdefault(fid, set()).add(rnd.choices(kinds, kw)[0])
                hours = n / per_hour
                reg = len(cnt)
                stars = 0
                for f in fl:
                    c = cnt.get(f["id"], 0)
                    if not c:
                        continue
                    stars += 1 + (f["id"] in s_got) + (f["id"] in big) + (len(muts.get(f["id"], ())) >= 3) \
                        + (c >= dexbook.thresholds(f)[4])
                if "dex" not in got and reg >= need_dex:
                    got["dex"] = hours
                if "star" not in got and stars >= need_star:
                    got["star"] = hours
                if "rare" not in got and all(r in cnt for r in rares):
                    got["rare"] = hours
                done = "dex" in got and "star" in got and (T == 2 or "rare" in got)
                if done:
                    got["all"] = hours
                    break
            for k in hrs:
                hrs[k].append(got.get(k, 40.0))
        q = {k: (statistics.median(v), sorted(v)[int(len(v) * 0.9) - 1]) for k, v in hrs.items()}
        res[T] = dict(q, need_dex=need_dex, n=len(fl), need_star=need_star, stars=5 * len(fl), rares=len(rares))
        if not quiet:
            f = lambda k: f"{q[k][0]:.1f} / {q[k][1]:.1f}"  # noqa: E731
            flag = " ⚠ 4시간 넘음" if q["all"][0] > 4 else ""
            print(f"| T{T} | ① {need_dex}/{len(fl)}: {f('dex')} | ② {need_star}/{5 * len(fl)}: {f('star')} | "
                  f"③ 희귀 {len(rares)}종: {'—' if T == 2 else f('rare')} | 전부: {f('all')}{flag} |", flush=True)
    return res


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "report"
    if cmd == "record":
        record(int(sys.argv[2]) if len(sys.argv) > 2 else 300)
    elif cmd == "qualify":
        kw = dict(a.split("=") for a in sys.argv[2:])
        qualify(int(kw.get("runs", 200)), float(kw.get("dex", 0.8)), float(kw.get("star", 0.3)), float(kw.get("s", 0.125)))
    else:
        report()
