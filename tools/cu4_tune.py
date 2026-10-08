"""CU4 목표 맞추기 (CORE_UPDATE.md CU4-2 목표 표, DESIGN.md 52-3): 봇 3종 × 낚시터 · 전설을 빠르게 재고 CU2 기준과 비교.

  목표: '보통' 성공률 = CU2 와 같게 (±3%p, 등급별) · '숙련' 판 시간 CU2 대비 −15% 이상 · '드랙만' 일반 ~60% · 희귀 ~25% · 전설 0~10%
  python tools/cu4_tune.py [낚시터당 판 N=120] [전설당 판 L=16]   → 표 출력 (+ CU4_TUNE_OUT 이 있으면 JSON)
"""
import json
import multiprocessing as mp
import os
import statistics
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
sys.path.insert(0, ROOT)


def _overrides():
    """CU4_OVR='{"core.json": {"attack": {"perfect_frac": 0.08}}, "fishing_config.json": {"fight": {...}}}' — 파일은 그대로, 측정만 바꿔 봄."""
    import src.core.config as config
    ovr = json.loads(os.environ.get("CU4_OVR") or "{}")
    raw, cache = config.load_json, {}

    def merge(a, b):
        for k, v in b.items():
            if isinstance(v, dict) and isinstance(a.get(k), dict):
                merge(a[k], v)
            else:
                a[k] = v

    def load(name):
        if name not in cache:
            d = raw(name)
            if name in ovr:
                merge(d, ovr[name])
            cache[name] = d
        return json.loads(json.dumps(cache[name]))
    config.load_json = load


_overrides()
import core_baseline as cb  # noqa: E402

BASE = os.path.join(ROOT, "tools", "core_baseline.json")
RARS = ("common", "uncommon", "rare")


def pooled(rows: list) -> dict:
    out = {}
    for rar in RARS + ("legend",):
        rr = [r for r in rows if r.get("rarity") == rar]
        if rr:
            out[rar] = {"n": len(rr), "success": round(sum(r["ok"] for r in rr) / len(rr) * 100, 1),
                        "t": round(statistics.mean(r["t"] for r in rr), 1),
                        "fails": {k: sum(1 for r in rr if not r["ok"] and r["reason"] == k)
                                  for k in {r["reason"] for r in rr if not r["ok"]}}}
    return out


def base_pooled() -> dict:
    """CU2 기준 (core_baseline.json): 낚시터 등급별 · 전설, 판 수 가중."""
    b = json.load(open(BASE, encoding="utf-8"))
    out = {}
    for bot in cb.BOTS:
        acc = {}
        for sid, s in b["spots"].items():
            for rar, v in s[bot].get("by_rarity", {}).items():
                a = acc.setdefault(rar, [0, 0.0, 0.0])
                a[0] += v["n"]
                a[1] += v["success"] * v["n"]
                a[2] += v["t"] * v["n"]
        res = {rar: {"success": round(a[1] / a[0], 1), "t": round(a[2] / a[0], 1)} for rar, a in acc.items()}
        lg = [v[bot] for v in b["legends"].values()]
        res["legend"] = {"success": round(statistics.mean(x["success"] for x in lg), 1),
                         "t": round(statistics.mean(x["t_mean"] for x in lg), 1)}
        out[bot] = res
    return out


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 120
    nl = int(sys.argv[2]) if len(sys.argv) > 2 else 16
    sp = cb.spots()
    jobs = [(sid, bot, n, 1000 + i * 7 + j) for i, sid in enumerate(sp) for j, bot in enumerate(cb.BOTS)]
    leg = [f["id"] for f in cb.bs.all_fish() if f["rarity"] == "legend"]
    ljobs = [(fid, bot, nl, 5000 + i * 7 + j) for i, fid in enumerate(leg) for j, bot in enumerate(cb.BOTS)]
    with mp.Pool(os.cpu_count() or 1) as pool:
        sres = pool.map(cb.run_spot, jobs)
        lres = pool.map(cb.run_legend, ljobs)
    rows = {bot: [] for bot in cb.BOTS}
    for r in sres:
        rows[r["bot"]] += r["rows"]
    per_leg = {}
    for r in lres:
        for x in r["rows"]:
            x["rarity"] = "legend"
        rows[r["bot"]] += r["rows"]
        per_leg.setdefault(r["fish"], {})[r["bot"]] = round(sum(x["ok"] for x in r["rows"]) / len(r["rows"]) * 100)
    base = base_pooled()
    now = {bot: pooled(rows[bot]) for bot in cb.BOTS}
    print(f"{'봇':10} | " + " | ".join(f"{r:>24}" for r in RARS + ('legend',)))
    for bot in cb.BOTS:
        cells = []
        for rar in RARS + ("legend",):
            a, b = base[bot].get(rar, {}), now[bot].get(rar, {})
            cells.append(f"{a.get('success', 0):5.1f}→{b.get('success', 0):5.1f}% {a.get('t', 0):5.1f}→{b.get('t', 0):5.1f}s")
        print(f"{bot:10} | " + " | ".join(cells))
    for bot in cb.BOTS:
        print(bot, "실패", {rar: v["fails"] for rar, v in now[bot].items()})
    # 이중 벌 확인 (CU5-2): '보통' 대물(크기 상위 10%) 성공률 vs 평균 크기(가운데 40~60%)
    for bot in cb.BOTS:
        rr = [r for r in rows[bot] if r.get("rarity") in RARS and "size_u" in r]
        big = [r for r in rr if r["size_u"] >= 0.9]
        mid = [r for r in rr if 0.4 <= r["size_u"] <= 0.6]
        heavy = [r for r in rr if r.get("weight", 1) > 1.8]
        def pct(x):
            return round(sum(r["ok"] for r in x) / max(1, len(x)) * 100, 1)
        print(f"{bot:10} 대물 {pct(big)}% ({len(big)}판) · 평균 크기 {pct(mid)}% ({len(mid)}판) · 무게>1.8 {pct(heavy)}% ({len(heavy)}판)")
    print("전설별 (보통/숙련/드랙만):", {k: tuple(v.get(b) for b in cb.BOTS) for k, v in per_leg.items()})
    if os.environ.get("CU4_TUNE_OUT"):
        json.dump({"base": base, "now": now, "legends": per_leg, "n": n, "nl": nl},
                  open(os.environ["CU4_TUNE_OUT"], "w", encoding="utf-8"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
