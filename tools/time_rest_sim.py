"""시간 · 날씨 개편 시뮬레이션 (TIME_REST.md, DESIGN.md 48장).

  python tools/time_rest_sim.py [n]   날씨 조건이 있는 전설마다 (n = 1만 기본)
    예전: 쉬기(다음 시간대)만 눌러 조건(시간대 + 날씨)을 만나기까지 쉬기 클릭 수 평균
    새: 예보표(3시간 칸, 정해진 날씨) 보고 골라 쉬기 — 조건이 처음 맞는 순간까지 쉬기 횟수(한 번 ≤ 24시간) · 게임 일수 평균,
        지금부터 48시간 예보표 안에 조건 칸이 있을 확률
"""
import math
import os
import random
import statistics
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

from src.core.config import load_json  # noqa: E402
from src.core.game_clock import PERIODS  # noqa: E402
from src.core.weather import roll_weather  # noqa: E402

STARTS = [(p[0], p[1]) for p in PERIODS]   # (시작 시, 이름)


def period_of(h: float) -> str:
    h %= 24
    cur = STARTS[-1][1]
    for start, name in STARTS:
        if h >= start:
            cur = name
    return cur


def old_clicks(spot_w: dict, times, weathers, rnd) -> int:
    """예전: 3시간마다 upcoming → current, 새 upcoming 은 그 순간 무작위. 쉬기 = 다음 시간대 시작으로."""
    t = rnd.uniform(0, 24 * 5)
    cur, up = roll_weather(spot_w, rnd), roll_weather(spot_w, rnd)
    nxt = (t // 3 + 1) * 3
    clicks = 0
    while True:
        if period_of(t) in times and cur in weathers:
            return clicks
        h = t % 24
        start = next((s for s, _ in STARTS if s > h + 0.01), STARTS[0][0] + 24)
        t = t - h + start
        clicks += 1
        while t >= nxt:
            cur, up = up, roll_weather(spot_w, rnd)
            nxt += 3
        if clicks > 10000:
            return clicks


def new_run(spot_w: dict, times, weathers, rnd) -> tuple[int, float, bool]:
    """새: 칸 날씨가 미리 정해짐 (칸마다 독립 = 같은 확률). 조건이 처음 맞는 순간(칸 시작 · 시간대 시작 중 이른 쪽)까지 골라 쉬기."""
    t0 = rnd.uniform(0, 24 * 5)
    cache: dict = {}

    def w_at(block: int) -> str:
        if block not in cache:
            cache[block] = roll_weather(spot_w, rnd)
        return cache[block]
    # 조건이 처음 맞는 시각 (3시간 칸 경계 · 시간대 경계에서만 바뀌므로 그 점들을 훑음)
    t = t0
    hit = None
    while t < t0 + 24 * 400:
        if period_of(t) in times and w_at(int(t // 3)) in weathers:
            hit = t
            break
        h = t % 24
        nb = (t // 3 + 1) * 3
        np_ = next((s for s, _ in STARTS if s > h + 1e-6), STARTS[0][0] + 24) + (t - h)
        t = min(nb, np_)
    wait = hit - t0
    rests = 0 if wait <= 0 else math.ceil(wait / 24)   # 한 번에 ≤ 24시간 (시간대 시작 · 칸 경계에 맞춰 쉰다고 봄)
    return rests, wait / 24, wait <= 48


def main(n: int = 10000) -> None:
    spots = {s["id"]: s for s in load_json("spots.json")["spots"]}
    print(f"전설(날씨 조건 있는 것) {n}번씩")
    print("  전설                 조건               | 예전 쉬기 클릭 | 새 쉬기 횟수 · 게임 일수 | 48시간 예보 안에 있을 확률")
    for f in load_json("fish.json")["fish"]:
        if f["rarity"] != "legend" or set(f["weathers"]) >= {"clear", "rain", "storm"}:
            continue
        w = spots[f["spot"]]["weather"]
        rnd = random.Random(7)
        o = [old_clicks(w, f["times"], f["weathers"], rnd) for _ in range(n)]
        r = [new_run(w, f["times"], f["weathers"], rnd) for _ in range(n)]
        cond = "·".join(f["times"]) + " " + "·".join(f["weathers"])
        print(f"  {f['name']:<18} {cond:<16} | {statistics.mean(o):10.1f}    | {statistics.mean(x[0] for x in r):6.2f}회 · "
              f"{statistics.mean(x[1] for x in r):5.2f}일     | {sum(x[2] for x in r) / n * 100:5.1f}%")


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 10000)
