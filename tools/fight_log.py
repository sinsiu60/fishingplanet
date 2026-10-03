"""파이팅 로그 분석 (DESIGN.md 31장 C2).

  python tools/fight_log.py sim [N] [낚시터,...]   봇이 물고기마다 N번(기본 5) 파이팅 → 낚시터별 부하·휴식·패턴 성공률
  (봇 실력: 환경 변수 FIGHTLOG_SKILL=skilled|average, 기본 skilled / FIGHTLOG_FISH=normal|phantom|all — 환상어 포함, 기본 normal)
  python tools/fight_log.py read [폴더]            디버그 빌드가 남긴 fight_logs/*.jsonl 분석 (기본: 세이브 폴더/fight_logs)

출력: 3초 부하 예산 초과(파이팅 수·0.1초 창 수·최대 부하), 휴식 < 1.5초, 부하 3 이상 뒤 < 2.5초, 같은 고부하 연속, 휴식 중앙값,
      패턴별 횟수·성공·실패.
"""
import glob
import json
import os
import random
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.fishing.fight_log import analyze  # noqa: E402


def run_sim(n: int, only: list | None) -> list[dict]:
    from tools.balance_sim import bot_fight, gear_for_tier, SKILLS, SPOT_TIER
    from src.core.config import load_json
    from src.save.save_game import all_fish
    from src.fishing import fight as F
    logs = []
    orig = F.Fight.__init__

    def init(self, *a, **kw):
        orig(self, *a, **kw)
        logs.append(self.log)
    F.Fight.__init__ = init
    spots = {s["id"]: s for s in load_json("spots.json")["spots"]}
    rnd = random.Random(7)
    which = os.environ.get("FIGHTLOG_FISH", "normal")
    from src.fishing.phantom import all_phantoms
    pool = (all_fish() if which != "phantom" else []) + (all_phantoms() if which in ("phantom", "all") else [])
    for fish in pool:
        if only and fish["spot"] not in only:
            continue
        gear = gear_for_tier(SPOT_TIER[fish["spot"]] + (1 if fish["rarity"] in ("legend", "phantom") else 0))
        for _ in range(n):
            bot_fight(fish, spots[fish["spot"]], gear, SKILLS[os.environ.get("FIGHTLOG_SKILL", "skilled")], rnd)
    F.Fight.__init__ = orig
    return [lg.to_dict() for lg in logs]


def read_logs(folder: str) -> list[dict]:
    out = []
    for path in sorted(glob.glob(os.path.join(folder, "*.jsonl"))):
        with open(path, encoding="utf-8") as fp:
            out += [json.loads(ln) for ln in fp if ln.strip()]
    return out


def report(res: dict) -> None:
    print(f"{'낚시터':<13}{'파이팅':>5}{'초과파이팅':>8}{'초과창':>7}{'최대3초':>7}{'휴식<1.5':>9}{'고부하뒤<2.5':>11}{'고부하연속':>9}{'휴식중앙':>8}{'최소':>6}")
    tot = {"over_fights": 0, "rest_short": 0, "rest_short_heavy": 0, "same_heavy": 0}
    for sp, s in res["spots"].items():
        for k in tot:
            tot[k] += s[k]
        print(f"{sp:<15}{s['fights']:>5}{s['over_fights']:>9}{s['over_windows']:>8}{s['max3']:>8}{s['rest_short']:>10}"
              f"{s['rest_short_heavy']:>12}{s['same_heavy']:>10}{s['rest_median'] if s['rest_median'] is not None else '-':>9}{s['rest_min'] if s['rest_min'] is not None else '-':>8}")
    print("합계", tot)
    print("\n패턴별 (횟수 / 성공 / 실패 — 돌진·멈춤처럼 판정 없는 행동은 0/0)")
    for a, p in sorted(res["patterns"].items(), key=lambda x: -x[1]["n"]):
        print(f"  {a:<12}{p['n']:>6}{p['ok']:>6}{p['fail']:>6}")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "sim"
    if cmd == "sim":
        n = int(sys.argv[2]) if len(sys.argv) > 2 else 5
        only = sys.argv[3].split(",") if len(sys.argv) > 3 else None
        logs = run_sim(n, only)
    else:
        from src.core.paths import save_dir
        folder = sys.argv[2] if len(sys.argv) > 2 else str(save_dir() / "fight_logs")
        logs = read_logs(folder)
    report(analyze(logs))
