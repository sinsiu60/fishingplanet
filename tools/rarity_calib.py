"""확률 개편 맞춤 (CORE_UPDATE.md CU7-1, DESIGN.md 52-6): 낚시터별 등급 비율을 재고 고급 · 희귀 배율을 찾는다.

기준 (52-1 질문 ② 기본안): 시간대(아침 4 · 낮 7 · 저녁 3 · 밤 10시간) · 날씨(낚시터 확률) 가중 평균 + 그 티어 상점 미끼 (core_baseline 과 같은 조건),
보정(폭풍 · 원투 · 미끼 티어 · 징후)은 게임 그대로. 목표: 고급 20~25% · 희귀 5~8% (가운데 22.5 / 6.5), 희귀 전용 낚시터(용문 폭포) 제외.

  python tools/rarity_calib.py            → 지금 비율 표
  python tools/rarity_calib.py solve      → bite.spot_rarity_mult 를 몇 번 고쳐 가며 맞춘 값 출력 (파일은 안 바꿈)
"""
import json
import os
import random
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

import src.core.config as config  # noqa: E402

_RAW = config.load_json
_OVR: dict = {}


def _load(name):
    d = _RAW(name)
    if name == "fishing_config.json" and _OVR:
        d["bite"]["spot_rarity_mult"] = json.loads(json.dumps(_OVR))
    return d


config.load_json = _load

import core_baseline as cb  # noqa: E402
from src.fishing.bite import pick_fish  # noqa: E402

TARGET = {"uncommon": 22.5, "rare": 6.5}
N = 6000


def shares(sid: str, n: int = N) -> dict:
    sp = cb.spots()[sid]
    rnd = random.Random(11)
    bait = cb.best_bait(sp)
    cnt, tot = {}, 0
    for _ in range(n):
        p, w = cb.conditions(sp, rnd)
        f = pick_fish(p, w, 28.0, rnd, sid, bait)
        if f is None:
            continue
        tot += 1
        cnt[f["rarity"]] = cnt.get(f["rarity"], 0) + 1
    return {k: round(cnt.get(k, 0) / max(1, tot) * 100, 1) for k in ("common", "uncommon", "rare")}


def has_common(sid: str) -> bool:
    return any(f["spot"] == sid and f["rarity"] == "common" for f in cb.bs.all_fish())


def table() -> dict:
    """비밀 낚시터라도 일반이 있으면 맞춤 (세계수), 희귀 전용(용문 폭포)만 제외."""
    return {sid: shares(sid) for sid in cb.spots() if has_common(sid)}


def solve(rounds: int = 6) -> dict:
    base = _RAW("fishing_config.json")["bite"].get("spot_rarity_mult", {})
    mult = {sid: dict(base.get(sid, {"uncommon": 1.0, "rare": 1.0})) for sid in cb.spots() if has_common(sid)}
    for _ in range(rounds):
        _OVR.clear()
        _OVR.update(mult)
        now = table()
        for sid, s in now.items():
            for r in ("uncommon", "rare"):
                if s[r] > 0:
                    # 등급 몫 x → 목표 t: 가중치 배율은 t(1−x) / (x(1−t)) 근사 (다른 등급도 같이 바뀌니 몇 번 반복)
                    x, t = s[r] / 100, TARGET[r] / 100
                    mult[sid][r] = round(mult[sid][r] * (t * (1 - x)) / (x * (1 - t)), 3)
    _OVR.clear()
    _OVR.update(mult)
    return {"mult": mult, "result": table()}


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "solve":
        out = solve()
        for sid, m in out["mult"].items():
            print(f"{sid:14} 고급 ×{m['uncommon']:<6} 희귀 ×{m['rare']:<6} → {out['result'][sid]}")
        print(json.dumps(out["mult"], ensure_ascii=False))
    else:
        for sid, s in table().items():
            print(f"{sid:14} 일반 {s['common']:5} · 고급 {s['uncommon']:5} · 희귀 {s['rare']:5}")


if __name__ == "__main__":
    main()
