"""전설을 낚시터 티어 장비(전설 기준 장비보다 1티어 낮음)로 상대할 때 봇 성공률 (CORE_UPDATE CU8).

전설의 맞는 장비 = 낚시터 티어 +1 (`fight.fish_gear_tier`) 이라 시험 · 해금 순서상 대부분 1티어 낮은 장비로 처음 만남.
진행 시뮬(`balance_sim.Sim`)이 그 경우의 성공률로 씀 → tools/legend_spot_tier.json.
  bare = 비늘석 없음, avg = 평균 세팅 (희귀 +4 ×4, scalestone_check.avg_setup)
사용: python tools/legend_spot_tier.py [판 수 = 12]
"""
import json
import os
import random
import sys

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.chdir(os.path.join(os.path.dirname(__file__), ".."))

from multiprocessing import Pool  # noqa: E402

import balance_sim as bs  # noqa: E402
import scalestone_check as sc  # noqa: E402
from src.save import scalestone as ss  # noqa: E402

N = int(sys.argv[1]) if len(sys.argv) > 1 else 12
SPOTS = {s["id"]: s for s in bs.load_json("spots.json")["spots"]}
AVG = sc.avg_setup()


def one(job):
    fid, skill, setup = job
    f = next(x for x in bs.all_fish() if x["id"] == fid)
    eff = {"bare": {}, "avg": AVG}[setup]
    gear = ss.apply_fight(bs.gear_for_tier(SPOTS[f["spot"]]["gear_tier"]), eff)
    rnd = random.Random(31)
    rows = [bs.bot_fight(f, SPOTS[f["spot"]], gear, bs.SKILLS[skill], rnd) for _ in range(N)]
    return fid, skill, setup, round(sum(r["ok"] for r in rows) / N, 3)


def main() -> None:
    legs = [f["id"] for f in bs.all_fish() if f["rarity"] == "legend"]
    jobs = [(fid, sk, st) for fid in legs for sk in ("average", "skilled") for st in ("bare", "avg")]
    with Pool(4) as p:
        res = p.map(one, jobs)
    out = {"_설명": "전설을 낚시터 티어 장비(전설 기준 −1 티어)로 상대할 때 봇 성공률 (12판, 비늘석 없음 'bare' / "
                   "평균 비늘석 'avg') — 진행 시뮬이 장비 1티어 부족 전설에 씀 (CU8)"}
    for fid, sk, st, s in res:
        out.setdefault(fid, {}).setdefault(sk, {})[st] = s
    for fid in legs:
        a, k = out[fid]["average"], out[fid]["skilled"]
        print(f"{fid:16s} 보통 맨몸 {a['bare'] * 100:5.1f} 평균 비늘석 {a['avg'] * 100:5.1f} | 숙련 {k['bare'] * 100:5.1f} {k['avg'] * 100:5.1f}")
    with open("tools/legend_spot_tier.json", "w", encoding="utf-8") as fp:
        json.dump(out, fp, ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
