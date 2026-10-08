"""달력 효과 계산 (CORE_UPDATE.md CU1-1 · CU1-6, DESIGN.md 52-0): 원하는 전설 조건 칸(시간대 + 날씨)까지 필요한 행동 수 · 날짜.

세이브 N개(씨앗 0..N-1), 1일째 07:00 에서 시작. 낚시터 예보표 = weather_at (게임과 같은 식).
  예전 (시작 시각만 보기): 그 시간대 시작 시각(밤 = 20:00)까지 쉬기 → 도착 칸 날씨가 맞으면 끝, 아니면 다음 날로 또 쉬기.
     행동 수 = 쉬기 횟수 (= 걸린 날 수).
  달력: 달력을 열어 14일 안에 맞는 3시간 칸이 있으면 그 칸까지 쉬기 (행동 2 = 보기 1 + 쉬기 1),
     없으면 14일 끝까지 쉬고 다시 보기 (+2). 걸린 날 수 = 그 칸까지의 날짜.

  python tools/calendar_calc.py [N=400]
"""
import json
import os
import statistics
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

from src.core.forecast import block_periods  # noqa: E402
from src.core.weather import weather_at  # noqa: E402

PERIOD_START = {"morning": 6, "day": 10, "evening": 17, "night": 20}
CASES = [("tiger_mandarin", "계곡 '산군'"), ("silver_bass", "방파제 '일렉트로'"), ("ignis", "화산 '이그니스'"),
         ("dragon_carp", "비밀 '등용' 저녁")]
DAYS = 14


def load():
    fish = {f["id"]: f for f in json.load(open("data/fish.json", encoding="utf-8"))["fish"]}
    spots = {s["id"]: s for s in json.load(open("data/spots.json", encoding="utf-8"))["spots"]}
    return fish, spots


def old_way(seed, spot, fi) -> int:
    """시간대 시작 시각 칸만 보고 넘기기: 맞을 때까지 쉰 횟수."""
    per = fi["times"][0]
    h = PERIOD_START[per]
    day = 1 if 7 < h else 2
    n = 1
    while n < 400:
        b = int((day * 24 + h) // 3)
        if weather_at(seed, spot["id"], spot["weather"], b) in fi["weathers"]:
            return n
        day += 1
        n += 1
    return n


def calendar_way(seed, spot, fi) -> tuple[int, float]:
    """(행동 수, 걸린 날 수)."""
    now = 1 * 24 + 7.0
    acts = 0
    while acts < 200:
        acts += 1   # 달력 보기
        b0 = int(now // 3) + 1
        for b in range(b0, int((now + DAYS * 24) // 3)):
            if set(fi["times"]) & block_periods(b) and weather_at(seed, spot["id"], spot["weather"], b) in fi["weathers"]:
                return acts + 1, (b * 3 - (24 + 7.0)) / 24
        acts += 1   # 14일 끝까지 쉬기
        now += DAYS * 24
    return acts, 99.0


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 400
    fish, spots = load()
    rows = []
    print(f"세이브 {n}개 · 1일째 07:00 시작")
    print(f"{'낚시터 (폭풍 확률)':28} | 예전: 쉬기 횟수 평균 · 최악 | 달력: 행동 수 평균 · 최악 | 달력: 걸린 날 평균 · 최악")
    for fid, name in CASES:
        fi = fish[fid]
        sp = spots[fi["spot"]]
        w = sp["weather"]
        p = w.get("storm", 0) / max(1e-9, sum(w.values()))
        old = [old_way(s, sp, fi) for s in range(n)]
        cal = [calendar_way(s, sp, fi) for s in range(n)]
        acts = [a for a, _ in cal]
        days = [d for _, d in cal]
        row = {"fish": fid, "name": name, "storm_pct": round(p * 100), "old_mean": round(statistics.mean(old), 1),
               "old_max": max(old), "cal_actions_mean": round(statistics.mean(acts), 2), "cal_actions_max": max(acts),
               "cal_days_mean": round(statistics.mean(days), 1), "cal_days_max": round(max(days), 1)}
        rows.append(row)
        label = f"{name} ({row['storm_pct']}%)"
        print(f"{label:28} | "
              f"{row['old_mean']:5} · {row['old_max']:3} | {row['cal_actions_mean']:5} · {row['cal_actions_max']:2} | "
              f"{row['cal_days_mean']:5} · {row['cal_days_max']}")
    return rows


if __name__ == "__main__":
    main()
