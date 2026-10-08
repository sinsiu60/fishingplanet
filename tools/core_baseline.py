"""코어 업데이트 기준 측정 (CORE_UPDATE.md CU2, DESIGN.md 52-1) — 게임 코드 · 데이터는 그대로, 지금 상태를 잰다.

봇 3종 (tools/balance_sim.SKILLS_ALL): '보통'(average) · '숙련'(skilled) · '드랙만'(drag_only = 보통 + 패턴 입력 None).
낚시터마다 (전설 제외) N판: 시간대(아침 4 · 낮 7 · 저녁 3 · 밤 10시간 비율) · 날씨(낚시터 확률)로 조건을 뽑고, 그 낚시터 티어의 가장 좋은 상점 미끼로
pick_fish (거리 28m) → 그 낚시터 티어 장비로 파이팅. 1판 시간 = balance_sim.Sim.OVERHEAD(16초: 던지기 · 대기 · 챔질 · 포획 컷) + 파이팅.
  성공률(등급별) · 파이팅 시간 · 랭크 · 실패 이유 · 시간당 포획 · 시간당 판매 골드(랭크 배율 포함, 상자 · 의뢰 제외) · 등급 비율.
전설 12종: 봇마다 L판 (장비 = 낚시터 티어 +1, 권장 장비).
전설 만남 시간 (조건 칸 안): 입질마다 legend.chance 로 전설 — 그 전까지 일반 입질은 그 조건의 '보통' 봇 평균 시간.
진행 시뮬: balance_sim.Sim (봇 '보통' · '숙련') 시험 합격 시각 → 티어 간격.

  python tools/core_baseline.py [N=300] [L=40] [진행 횟수=3]   → tools/core_baseline.json
"""
import json
import multiprocessing as mp
import os
import random
import statistics
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))
os.chdir(ROOT)
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import balance_sim as bs  # noqa: E402
from src.core.config import load_json  # noqa: E402
from src.fishing.bite import pick_fish  # noqa: E402
from src.fishing.rank import sell_price  # noqa: E402

PERIOD_H = {"morning": 4, "day": 7, "evening": 3, "night": 10}
BOTS = ("average", "skilled", "drag_only")
OUT = os.path.join(ROOT, "tools", "core_baseline.json")


def spots() -> dict:
    return {s["id"]: s for s in load_json("spots.json")["spots"]}


def best_bait(spot: dict) -> dict:
    cont = spot.get("continent", "sharmion")
    tier = spot.get("gear_tier", 1)
    cands = [b for b in load_json("baits.json")["baits"] if b.get("tier") and not b.get("legend_for")
             and b["tier"] <= tier and b.get("continent", "sharmion") in ("sharmion", cont)]
    return max(cands, key=lambda b: b["tier"])


def conditions(spot: dict, rnd: random.Random) -> tuple[str, str]:
    p = rnd.choices(list(PERIOD_H), list(PERIOD_H.values()))[0]
    w = spot["weather"]
    return p, rnd.choices(list(w), list(w.values()))[0]


def rarity_table(spot: dict, n: int = 20000) -> dict:
    """등급 비율 2가지: 시간 · 날씨 가중 평균(티어 미끼) / '낮 · 맑음 · 기본 미끼(지렁이)' (CU7-1 문서 기준)."""
    rnd = random.Random(7)
    bait = best_bait(spot)
    worm = next(b for b in load_json("baits.json")["baits"] if b["id"] == "worm")
    out = {}
    for key, cond, bt in (("avg", None, bait), ("day_clear_worm", ("day", "clear"), worm)):
        cnt = {}
        tot = 0
        for _ in range(n):
            p, w = cond or conditions(spot, rnd)
            f = pick_fish(p, w, 28.0, rnd, spot["id"], bt)
            if f is None:
                continue
            tot += 1
            cnt[f["rarity"]] = cnt.get(f["rarity"], 0) + 1
        out[key] = {k: round(v / max(1, tot) * 100, 1) for k, v in sorted(cnt.items())}
    out["bait"] = bait["id"]
    return out


def run_spot(args) -> dict:
    sid, bot, n, seed = args
    sp = spots()[sid]
    rnd = random.Random(seed)
    bait = best_bait(sp)
    gear = bs.gear_for_tier(sp.get("gear_tier", 1))
    skill = bs.SKILLS_ALL[bot]
    rows = []
    tries = 0
    while len(rows) < n and tries < n * 50:
        tries += 1
        p, w = conditions(sp, rnd)
        fish = pick_fish(p, w, 28.0, rnd, sid, bait)
        if fish is None:
            continue
        r = bs.bot_fight(fish, sp, gear, skill, rnd)
        r["rarity"] = fish["rarity"]
        r["fish"] = fish["id"]
        r["price"] = sell_price(fish, r["size"], r["rank"]) if r["ok"] else 0
        rows.append(r)
    return {"spot": sid, "bot": bot, "rows": rows}


def run_legend(args) -> dict:
    fid, bot, n, seed = args
    fish = next(f for f in bs.all_fish() if f["id"] == fid)
    sp = spots()[fish["spot"]]
    gear = bs.gear_for_tier(min(8, sp.get("gear_tier", 1) + 1))
    rnd = random.Random(seed)
    rows = [bs.bot_fight(fish, sp, gear, bs.SKILLS_ALL[bot], rnd) for _ in range(n)]
    return {"fish": fid, "bot": bot, "rows": rows}


def summarize(rows: list, overhead: float) -> dict:
    n = len(rows)
    ok = [r for r in rows if r["ok"]]
    sec = sum(overhead + r["t"] for r in rows)
    by = {}
    for rar in ("common", "uncommon", "rare"):
        rr = [r for r in rows if r.get("rarity") == rar]
        if rr:
            by[rar] = {"n": len(rr), "success": round(sum(r["ok"] for r in rr) / len(rr) * 100, 1),
                       "t": round(statistics.mean(r["t"] for r in rr), 1)}
    fails = {}
    for r in rows:
        if not r["ok"]:
            fails[r["reason"]] = fails.get(r["reason"], 0) + 1
    return {"n": n, "success": round(len(ok) / max(1, n) * 100, 1),
            "t_mean": round(statistics.mean(r["t"] for r in rows), 1) if rows else None,
            "ranks": {k: round(sum(1 for r in ok if r["rank"] == k) / max(1, len(ok)) * 100) for k in "SABC"},
            "fails": fails, "by_rarity": by,
            "catch_per_h": round(len(ok) / max(1e-9, sec / 3600), 1),
            "gold_per_h": round(sum(r.get("price", 0) for r in rows) / max(1e-9, sec / 3600)),
            "share": {k: round(sum(1 for r in rows if r.get("rarity") == k) / max(1, n) * 100, 1)
                      for k in ("common", "uncommon", "rare")}}


def legend_meet(spot_sum: dict) -> dict:
    """조건 칸 안 전설 만남 평균 실제 분: (1/chance − 1) × (16 + 그 낚시터 '보통' 평균 판 시간) + 16 (전설 입질까지)."""
    lg = load_json("fishing_config.json")["legend"]
    p = lg["chance"]
    out = {}
    for f in bs.all_fish():
        if f["rarity"] != "legend":
            continue
        s = spot_sum.get(f["spot"], {}).get("average")
        if not s:
            continue
        per = bs.Sim.OVERHEAD + (s["t_mean"] or 30)
        mins = ((1 / p - 1) * per + bs.Sim.OVERHEAD) / 60
        span = sum(PERIOD_H[t] for t in f["times"]) * bs.Sim.DAY_SEC / 24 / 60   # 그 시간대 실제 길이(분)
        out[f["id"]] = {"meet_min": round(mins, 1), "window_real_min": round(span, 1)}
    return out


def progress(runs: int) -> dict:
    with open(os.path.join(bs.OUT, "balance_measure.json"), encoding="utf-8") as fp:
        data = json.load(fp)
    out = {}
    for skill in ("average", "skilled"):
        res = []
        for r in range(runs):
            sim = bs.Sim(data, skill, random.Random(500 + r))
            s = sim.run(max_hours=40)
            ex = [(m, t) for m, t, ok, _ in s["exams"] if ok]
            res.append({"minutes": s["minutes"], "finished": s["finished"], "passes": ex, "fails": sum(1 for e in s["exams"] if not e[2])})
        tiers = sorted({t for r in res for _, t in r["passes"]})
        table = {}
        for t in tiers:
            ms = [next(m for m, tt in r["passes"] if tt == t) for r in res if any(tt == t for _, tt in r["passes"])]
            table[f"T{t}"] = round(statistics.mean(ms))
        out[skill] = {"runs": res, "pass_min_mean": table}
    return out


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 300
    nl = int(sys.argv[2]) if len(sys.argv) > 2 else 40
    pr = int(sys.argv[3]) if len(sys.argv) > 3 else 3
    sp = spots()
    jobs = [(sid, bot, n, 1000 + i * 7 + j) for i, sid in enumerate(sp) for j, bot in enumerate(BOTS)]
    leg = [f["id"] for f in bs.all_fish() if f["rarity"] == "legend"]
    ljobs = [(fid, bot, nl, 5000 + i * 7 + j) for i, fid in enumerate(leg) for j, bot in enumerate(BOTS)]
    with mp.Pool(min(4, os.cpu_count() or 1)) as pool:
        spot_res = pool.map(run_spot, jobs)
        print("낚시터 측정 끝", flush=True)
        leg_res = pool.map(run_legend, ljobs)
        print("전설 측정 끝", flush=True)
    out = {"n": n, "n_legend": nl, "overhead_sec": bs.Sim.OVERHEAD, "spots": {}, "legends": {}, "rarity": {}}
    for r in spot_res:
        out["spots"].setdefault(r["spot"], {})[r["bot"]] = summarize(r["rows"], bs.Sim.OVERHEAD)
    for r in leg_res:
        s = summarize(r["rows"], bs.Sim.OVERHEAD)
        out["legends"].setdefault(r["fish"], {})[r["bot"]] = {k: s[k] for k in ("success", "t_mean", "ranks", "fails")}
    for sid, s in sp.items():
        out["rarity"][sid] = rarity_table(s)
    out["legend_meet"] = legend_meet(out["spots"])
    out["progress"] = progress(pr)
    with open(OUT, "w", encoding="utf-8") as fp:
        json.dump(out, fp, ensure_ascii=False, indent=1)
    print_tables(out)


def print_tables(out: dict) -> None:
    sp = spots()
    print(f"\n낚시터 (봇 {out['n']}판) | 성공 보통/숙련/드랙만 | 일반·고급·희귀 성공(드랙만) | 시간 보통/숙련 | 포획/시 보통 | 골드/시 보통/숙련 | 비율 일반/고급/희귀")
    for sid, d in out["spots"].items():
        a, s, dg = d["average"], d["skilled"], d["drag_only"]
        br = " · ".join(f"{dg['by_rarity'][k]['success']:.0f}" if k in dg["by_rarity"] else "-" for k in ("common", "uncommon", "rare"))
        print(f"{sp[sid]['name'][:8]:9} | {a['success']:5.1f} / {s['success']:5.1f} / {dg['success']:5.1f} | {br:14} | "
              f"{a['t_mean']:5} / {s['t_mean']:5} | {a['catch_per_h']:5} | {a['gold_per_h']:7,} / {s['gold_per_h']:7,} | "
              f"{a['share']['common']}/{a['share']['uncommon']}/{a['share']['rare']}")
    print("\n전설 (봇 판) | 성공 보통/숙련/드랙만 | 시간 보통 | 만남(분) / 시간대 실제 길이(분)")
    for fid, d in out["legends"].items():
        m = out["legend_meet"].get(fid, {})
        print(f"{fid:15} | {d['average']['success']:5.1f} / {d['skilled']['success']:5.1f} / {d['drag_only']['success']:5.1f} | "
              f"{d['average']['t_mean']:6} | {m.get('meet_min')} / {m.get('window_real_min')}")
    print("\n진행 (시험 합격 평균 분):", {k: v["pass_min_mean"] for k, v in out["progress"].items()})


if __name__ == "__main__":
    main()
