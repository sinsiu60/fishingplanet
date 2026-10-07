"""비늘석 획득 확률 시뮬레이션 (SCALESTONE.md, DESIGN.md 46장 S2).

  python tools/scalestone_sim.py            낚시터별 시간당 비늘석 개수 · 등급 분포 (포획 · 상자 · 의뢰), 첫 부옵션 분포 확인
  python tools/scalestone_sim.py 200        시뮬레이션 시간 (기본 200시간)

가정 (DESIGN 20 · 33 · 46): 시간당 50마리(40~70 가운데), 일반/고급/희귀 비율 = 낚시터 물고기 가중치, 상자 시간당 4개(3~5 가운데)를
treasure.json 드랍 등급 비율로, 하루 1시간 플레이 = 일일 의뢰 3개(그중 1개 비늘석) + 주간 1/7.
"""
import os
import random
import sys
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

from src.core.config import load_json  # noqa: E402
from src.save import scalestone  # noqa: E402


class _Save:
    def __init__(self):
        self.data = {"materials": {"sharmion": 0, "eldrasion": 0, "rare": 0}}


def _rarity_share(spot: str) -> dict:
    fish = [f for f in load_json("fish.json")["fish"] if f.get("spot") == spot and f["rarity"] in ("common", "uncommon", "rare")]
    w = Counter()
    for f in fish:
        w[f["rarity"]] += f.get("weight", 1.0)
    tot = sum(w.values()) or 1
    return {k: v / tot for k, v in w.items()}


def _chest_grades() -> dict:
    """상자 등급 비율 (대략): 일반 60 · 희귀 28 · 특별 10 · 전설 2 (treasure.json drop_grades 가 있으면 그것)."""
    t = load_json("treasure.json")
    g = t.get("drop_grades")
    if isinstance(g, dict):
        return g
    return {"common": 60, "rare": 28, "special": 10, "legend": 2}


def run(hours: int = 200) -> None:
    rnd = random.Random(7)
    chest_g = _chest_grades()
    print(f"가정: 시간당 50마리 · 상자 4개 · 하루 1시간 (일일 의뢰 3개 중 1개 + 주간 1/7). {hours}시간\n")
    spots = [s for s in load_json("spots.json")["spots"]]
    for s in spots:
        share = _rarity_share(s["id"])
        if not share:
            continue
        save = _Save()
        got = Counter()
        src = Counter()
        for _h in range(hours):
            for _ in range(50):
                r = rnd.choices(list(share), list(share.values()))[0]
                st = scalestone.roll_catch(save, {"rarity": r}, s.get("continent", "sharmion"), rnd)
                if st:
                    got[st["grade"]] += 1
                    src["포획"] += 1
            for _ in range(4):
                g = rnd.choices(list(chest_g), list(chest_g.values()))[0]
                st = scalestone.roll_chest(save, g, "sharmion", rnd)
                if st:
                    got[st["grade"]] += 1
                    src["상자"] += 1
            st = scalestone.grant_table(save, "daily_quest", "sharmion", rnd)
            got[st["grade"]] += 1
            src["일일 의뢰"] += 1
            if rnd.random() < 1 / 7:
                st = scalestone.grant_table(save, "weekly_quest", "sharmion", rnd)
                got[st["grade"]] += 1
                src["주간 의뢰"] += 1
        tot = sum(got.values())
        dist = " ".join(f"{scalestone.grade_info(g)['name']} {got[g] / max(1, tot) * 100:4.1f}%" for g in scalestone.grades()["order"])
        print(f"{s['id']:14s} 시간당 {tot / hours:4.2f}개  ({dist})  출처 " +
              ", ".join(f"{k} {v / hours:.2f}" for k, v in src.items()))
    # 첫 부옵션 분포 (비중 10/8/6) · 수치 범위 (등급 배율)
    print("\n첫 부옵션 분포 (희귀 2만 개):")
    save = _Save()
    cnt = Counter()
    vals: dict = {}
    for _ in range(20000):
        o = scalestone.roll_option("rare", rnd=rnd)
        cnt[o["id"]] += 1
        lo, hi = vals.get(o["id"], (9e9, -9e9))
        vals[o["id"]] = (min(lo, o["v"]), max(hi, o["v"]))
    opts = scalestone.options()
    for oid in opts["order"]:
        sp = opts["options"][oid]
        print(f"  {sp['name']:10s} {cnt[oid] / 200:5.2f}% (비중 {sp['weight']:2d})  값 {vals[oid][0]}~{vals[oid][1]} (표 {sp['range'][0]}~{sp['range'][1]})")


if __name__ == "__main__":
    run(int(sys.argv[1]) if len(sys.argv) > 1 else 200)
