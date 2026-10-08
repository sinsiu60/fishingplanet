"""보스전 무대가 판정을 해치지 않는지 (BOSS_ARENA.md BA4, DESIGN.md 51-4): 실제 낚시 화면 안에서 봇 '보통'으로 보스와 싸워
무대(히트스톱 · 흔들림 · 무대 효과 · 보스 예고음) 켬 / 끔 성공률 · 랭크 분포를 비교한다. 같은 씨앗이면 물고기 · 봇 난수가 같지만
장면의 실제 시간 연출(성공음에 맞춘 슬로모션 등)이 틱 배치를 바꿔 같은 모드끼리도 판마다 조금씩 달라진다 → 판별이 아니라 분포로 본다.
비교 기준으로 화면 없는 순수 봇(balance_sim.bot_fight) 성공률도 같이.

  python tools/boss_arena_bot.py [판 수=8]
봇 = tools/balance_sim.BotPlayer (balance_sim 의 bot_fight 와 같은 손). 화면은 10틱에 한 번 그림 (무대 시계 · 비네트 갱신).
깜빡임 로그: 무대 번쩍임 시각 → 3초 안에 두 번 이상이 있는지.
"""
import os
import random
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import boss_arena_check as bc  # noqa: E402  (모바일 미리보기 · 더미 화면)
import balance_sim as bs  # noqa: E402

BOSSES = [("golden_carp", "여우비"), ("silver_bass", "일렉트로"), ("dragon_carp", "등용"), ("phantom:moon_shadow_carp", "환상 달그림자")]
# 장비 = 그 낚시터 티어 (balance_sim.gear_for_tier — 화면 없는 봇과 같게). 켬/끔 둘 다 매번 줄이 끊겨 비교가 안 되는 보스는 +1:
# 등용 T5 (화면 없는 봇도 0/8) → T6, 일렉트로 T3 (화면 없는 봇 12/12 인데 낚시 화면 안에선 무대 켬 · 끔 모두 0/12 — 무대와 무관한
# 기존 차이, DESIGN 51-4) → T4.
GEAR_BONUS = {"dragon_carp": 1, "silver_bass": 1}


def _fish(fid: str) -> dict:
    from src.core.config import load_json
    if fid.startswith("phantom:"):
        return dict(next(f for f in load_json("phantom.json")["fish"] if f["id"] == fid.split(":", 1)[1]), rarity="phantom")
    return next(f for f in load_json("fish.json")["fish"] if f["id"] == fid)


def _tier(fid: str) -> int:
    from src.core.config import load_json
    spot = next(s for s in load_json("spots.json")["spots"] if s["id"] == _fish(fid)["spot"])
    return spot.get("gear_tier", 1) + GEAR_BONUS.get(fid.split(":")[-1], 0)
DT = 1 / 60


def one(g, fid: str, seed: int, arena: bool) -> dict:
    from src.fishing import fight as fight_mod
    random.seed(seed)   # 크기 굴림 등 장면이 쓰는 전역 난수
    real_random = fight_mod.random

    class _Seeded:   # Fight 가 rnd 없이 만들 때 쓰는 random.Random() 을 씨앗 고정으로
        def __getattr__(self, k):
            return getattr(real_random, k)

        @staticmethod
        def Random(x=None):
            return real_random.Random(seed * 7919 + 1 if x is None else x)
    fight_mod.random = _Seeded()
    gear = bs.gear_for_tier(_tier(fid))
    real_gear = g.save.fight_gear
    g.save.fight_gear = lambda period="day": dict(gear)
    try:
        sc = bc.start(g, fid)
    finally:
        fight_mod.random = real_random
        g.save.fight_gear = real_gear
    f = sc.fight
    f.line = float(f.line_max)
    del f._lose   # bc.start 의 '놓치지 않게' 를 되돌림 — 진짜 승부
    if not arena:
        sc.arena.stop()
    bot = bs.BotPlayer(bs.SKILLS["average"], random.Random(seed + 1000))
    real_update = f.update

    def upd(dt, reeling, aim, inp=None):
        if f.phase == "net":
            bot.act(f)
            return real_update(dt, False, 0.0)
        r, a, i = bot.act(f)
        return real_update(dt, r, a, i)
    f.update = upd
    n = 0
    stops = 0
    while sc.fight is f and f.phase in ("fight", "net") and n < 60 * 600:
        sc.card = None
        sc.help = False
        sc.game.guide.run = None
        if g.hit_timer > 0:
            g.hit_timer -= DT
            stops += 1
        else:
            if g.slow_timer > 0:
                g.slow_timer -= DT
                if g.slow_timer <= 0:
                    g.time_scale = 1.0
            g._acc += DT * g.time_scale
        while g._acc >= g.tick_dt:
            g.scenes.current.update(g.tick_dt)
            g._acc -= g.tick_dt
        g.boss.update(DT)
        g.sfx.update(DT)
        n += 1
        if n % 10 == 0:
            sc._arena_rt = time.perf_counter() - DT * 10
            g.scenes.current.draw(g.screen.canvas)
    ft = list(sc.arena.flash_times)
    res = {"ok": f.phase == "caught", "t": round(f.elapsed, 1), "reason": f.lose_reason,
           "rank": (f.result or {}).get("rank"), "hitstop_frames": stops, "flash_t": ft,
           "min_gap": min((b - a for a, b in zip(ft, ft[1:])), default=None)}
    sc._end_fight()
    return res


def pure(fid: str, runs: int) -> tuple[int, str]:
    from src.core.config import load_json
    fish = _fish(fid)
    spot = next(s for s in load_json("spots.json")["spots"] if s["id"] == fish["spot"])
    gear = bs.gear_for_tier(_tier(fid))
    rows = [bs.bot_fight(fish, spot, gear, bs.SKILLS["average"], random.Random(s)) for s in range(runs)]
    return sum(r["ok"] for r in rows), "".join(sorted(r.get("rank") or "-" for r in rows))


def main():
    runs = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isdigit() else 12
    g = bc.pb.make_game()
    print(f"봇 '보통' · 판 {runs} · 무대 켬 / 끔 (같은 씨앗들) · 장비 = 낚시터 티어 (등용 · 일렉트로 +1)")
    print(f"{'보스':12} | 성공 켬 | 성공 끔 | 화면 없는 봇 | 랭크 켬 / 끔 / 화면 없음 | 히트스톱 프레임 | 깜빡임")
    flash_bad = 0
    worse = 0
    for fid, name in BOSSES:
        rows = {True: [], False: []}
        for seed in range(runs):
            for on in (True, False):
                rows[on].append(one(g, fid, seed, on))
        ok_on = sum(r["ok"] for r in rows[True])
        ok_off = sum(r["ok"] for r in rows[False])
        p_ok, p_rank = pure(fid, runs)
        ranks = lambda rs: "".join(sorted(r["rank"] or "-" for r in rs))  # noqa: E731
        hs = sum(r["hitstop_frames"] for r in rows[True])
        fl = sum(len(r["flash_t"]) for r in rows[True])
        gaps = [r["min_gap"] for r in rows[True] if r["min_gap"] is not None]
        flash_bad += sum(1 for x in gaps if x < 3.0 - 1e-6)
        worse += ok_on < ok_off - max(1, runs // 6)
        print(f"{name:12} | {ok_on:2}/{runs} | {ok_off:2}/{runs} | {p_ok:2}/{runs} | {ranks(rows[True])} / {ranks(rows[False])} / {p_rank}"
              f" | {hs} | 번쩍임 {fl}번, 최소 간격 {round(min(gaps), 1) if gaps else '-'}초", flush=True)
    print(f"\n무대 켬이 눈에 띄게 낮은 보스: {worse} · 3초 안에 번쩍임 두 번: {flash_bad}")
    sys.exit(1 if worse or flash_bad else 0)


if __name__ == "__main__":
    main()
