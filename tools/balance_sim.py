"""밸런스 시뮬레이션 (확장 Phase G). 실제 플레이 없이 숫자를 뽑는다.

1단계 (measure): 화면 없이 Fight를 직접 돌리는 봇으로 물고기마다 성공률·파이팅 시간·랭크 분포를 잰다.
   봇 실력 2종 — skilled(판정 오차 σ 0.05초, 반응 0.25초) / average(σ 0.10초, 반응 0.4초, 점프 10% 놓침)
   장비는 '그 낚시터에 처음 갈 때 쯤의 티어'로 맞춘다.
2단계 (progress): 1단계 결과로 처음부터 끝까지 '가상 플레이어'를 돌린다.
   낚시 → 판매 → 장비·미끼·찌 구매 → 낚시터 해금 → 전설 → 대륙 이동 → 오르시엘.
   게임 규칙(해금 조건, 상자, 판매가, 출현 테이블)은 실제 코드를 그대로 쓴다.

사용: python tools/balance_sim.py measure [N]      (결과: build/balance_measure.json, 수 분 걸림)
      python tools/balance_sim.py progress [runs]  (결과를 표로 출력, build/balance_progress.json)
"""
import json
import math
import os
import random
import statistics
import sys

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src.core.config import load_json  # noqa: E402
from src.fishing.bite import bait_tier_mult, pick_fish  # noqa: E402
from src.fishing.fight import Fight  # noqa: E402
from src.fishing.rank import sell_price  # noqa: E402
from src.save.save_game import SaveGame, all_fish, enhanced, equipment  # noqa: E402

OUT = os.path.join(ROOT, "build")
DT = 1 / 60
SKILLS = {
    "skilled": dict(sigma=0.05, react=0.25, miss_jump=0.0, turn_sigma=0.06),
    "average": dict(sigma=0.10, react=0.40, miss_jump=0.10, turn_sigma=0.11),
}
# 그 낚시터에 처음 도착할 무렵의 장비 티어 (진행 경로 가정)
SPOT_TIER = {"reservoir": 1, "valley": 2, "breakwater": 3, "offshore": 4, "deep": 4, "secret": 5,
             "marsh": 5, "crystal_cave": 6, "sky_falls": 6, "volcano": 6, "ice_sea": 7, "world_tree": 8}
PERIODS = [(6.0, "morning"), (10.0, "day"), (17.0, "evening"), (20.0, "night")]
# 봇은 장력 수치를 정확히 보고 반응하므로 사람보다 잘한다 → 진행 시뮬에선 사람 기준으로 보정
HUMAN = {"skilled": {"success": 0.92, "ranks": {"S": 0.35, "A": 0.40, "B": 0.20, "C": 0.05}},
         "average": {"success": 0.80, "ranks": {"S": 0.15, "A": 0.40, "B": 0.35, "C": 0.10}}}


def gear_for_tier(tier: int) -> dict:
    eq = equipment()
    pick = {k: max((g for g in eq[k] if g["tier"] <= tier), key=lambda g: g["tier"]) for k in ("rod", "reel", "line", "net")}
    rod, reel, line, net = pick["rod"], pick["reel"], pick["line"], pick["net"]
    return {"rod_green": list(rod["green"]), "reel_speed": reel["speed"], "drag_steps": reel["drag_steps"],
            "line_max": line["durability"], "net_window_sec": net["window"], "net_fail_distance": net["fail_distance"]}


# ───────────────────────── 1단계: 헤드리스 봇 ─────────────────────────

def bot_fight(fish: dict, spot: dict, gear: dict, skill: dict, rnd: random.Random) -> dict:
    cast = rnd.uniform(24, 34)
    size = round(fish["size_cm"][0] + (fish["size_cm"][1] - fish["size_cm"][0]) * rnd.betavariate(2, 2.4), 1)
    g = spot.get("gimmick")
    if g == "cycle":
        g = rnd.choice(["tangle", "dark", "current", "heat"])
    f = Fight(fish, size, cast, rnd.uniform(-0.15, 0.15), 0.0, gear=gear, rnd=random.Random(rnd.random()),
              hazards=spot.get("hazards", []), gimmick=g, float_need=0, float_tier=0)
    aim = 0.0
    plan_jump = plan_leap = plan_turn = None
    react_t = 0.0
    seen_turn = -1
    steps = 0
    while f.phase in ("fight", "net") and steps < 60 * 400:
        b = f.brain
        steps += 1
        if f.phase == "net":
            pose, still = f.net_pose()
            if still and rnd.random() < 0.08:  # 반응 지연
                f.net_click()
            f.update(DT, False, 0.0)
            continue
        # 드랙: 돌진 예고를 반응 시간 뒤에 알아챔
        if b.signal == "rush" or b.state == "rush":
            react_t += DT
            if react_t >= skill["react"] or b.state == "rush":
                f.drag = 1 if f.drag_steps <= 6 else 2
        else:
            react_t = 0.0
            f.drag = f.drag_steps if b.is_calm else max(1, f.drag_steps // 2)
        reeling = f.tension < f.green_high - 3 - (2 if skill is SKILLS["average"] else 0)
        # 낚싯대: 물고기 반대쪽 (위협 구역·기믹 쪽이면 더 세게)
        target = -f.fish_side() * 0.9
        aim += (target - aim) * 0.08
        # 점프(우클릭)
        if b.state == "jump" and b.jump_kind == "dip" and not b.jump_judged:
            if plan_jump is None:
                plan_jump = None if rnd.random() < skill["miss_jump"] else rnd.gauss(0, skill["sigma"])
            if plan_jump is not None and b.time_to_apex() <= plan_jump:
                f.dip()
        else:
            plan_jump = None
        # 몸털기(슬라이드)
        if b.state == "jump" and b.jump_kind == "swipe" and not b.jump_judged:
            if plan_leap is None:
                plan_leap = None if rnd.random() < skill["miss_jump"] else rnd.gauss(0, skill["sigma"])
            if plan_leap is not None and b.time_to_apex() <= plan_leap:
                f.flick(-b.leap_dir)
        else:
            plan_leap = None
        # 방향 전환 꺾기
        off = b.turn_offset()
        if off is not None and b.turn_count != seen_turn:
            if plan_turn is None:
                plan_turn = rnd.gauss(0, skill["turn_sigma"])
            if off >= plan_turn:
                f.flick(-b.turn_dir)
                seen_turn = b.turn_count
                plan_turn = None
        f.update(DT, reeling, aim)
    res = {"ok": f.phase == "caught", "t": round(f.elapsed, 1), "reason": f.lose_reason}
    if f.result:
        res.update(rank=f.result["rank"], size=f.result["size"], perfects=f.result["perfects"])
    return res


def measure(n: int = 6) -> dict:
    spots = {s["id"]: s for s in load_json("spots.json")["spots"]}
    rnd = random.Random(42)
    out = {}
    fishes = all_fish()
    for i, fish in enumerate(fishes):
        spot = spots[fish["spot"]]
        gear = gear_for_tier(SPOT_TIER[fish["spot"]] + (1 if fish["rarity"] == "legend" else 0))
        rec = {}
        for name, sk in SKILLS.items():
            rows = [bot_fight(fish, spot, gear, sk, rnd) for _ in range(n)]
            ok = [r for r in rows if r["ok"]]
            rec[name] = {
                "success": round(len(ok) / n, 2),
                "t_ok": round(statistics.mean(r["t"] for r in ok), 1) if ok else None,
                "t_all": round(statistics.mean(r["t"] for r in rows), 1),
                "ranks": {k: sum(1 for r in ok if r["rank"] == k) / max(1, len(ok)) for k in "SABC"},
                "fails": {r["reason"]: sum(1 for x in rows if x["reason"] == r["reason"]) for r in rows if not r["ok"]},
            }
        out[fish["id"]] = rec
        print(f"[{i + 1}/{len(fishes)}] {fish['name']:<14} 숙련 {rec['skilled']['success']:.0%} "
              f"{rec['skilled']['t_all']:>5}s · 보통 {rec['average']['success']:.0%} {rec['average']['t_all']:>5}s",
              flush=True)
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, "balance_measure.json"), "w", encoding="utf-8") as fp:
        json.dump(out, fp, ensure_ascii=False, indent=1)
    return out


# ───────────────────────── 2단계: 진행 시뮬레이션 ─────────────────────────

class Sim:
    """가상 플레이어. 실제 SaveGame·해금·상자 규칙을 그대로 쓴다."""

    OVERHEAD = 16.0      # 던지기·입질 대기·챔질·포획 컷·판매 등 1마리당 파이팅 외 시간(초)
    DAY_SEC = 1200.0     # 게임 하루 = 실제 20분

    def __init__(self, data: dict, skill: str, rnd: random.Random, use_chests: bool = True):
        os.environ["FISHING_SAVE_DIR"] = os.path.join(OUT, "sim_save")
        self.d = data
        self.skill = skill
        self.rnd = rnd
        self.use_chests = use_chests
        self.s = SaveGame(1)
        self.t = 0.0          # 실제 시간(초)
        self.hour = 7.0
        self.weather = "clear"
        self.next_weather = 3.0
        self.spots = {s["id"]: s for s in load_json("spots.json")["spots"]}
        self.spot = "reservoir"
        self.log: list[tuple] = []          # (시간, 사건)
        self.chests_by_cont = {"sharmion": [0, 0.0], "eldrasion": [0, 0.0]}  # 상자 수, 머문 시간
        self.money_curve: list[tuple] = []
        self.spot_stats: dict[str, list] = {}   # 낚시터별 [번 돈, 머문 초, 잡은 수]
        self.unlock_money: dict[str, int] = {}
        self.eldra_entry_t = None

    # 시간·날씨
    def advance(self, sec: float) -> None:
        self.t += sec
        self.spot_stats.setdefault(self.spot, [0, 0.0, 0])[1] += sec
        cont = self.spots[self.spot].get("continent", "sharmion")
        self.chests_by_cont[cont][1] += sec
        self.hour += sec * 24 / self.DAY_SEC
        while self.hour >= self.next_weather + 0.0001 or self.hour >= 24:
            if self.hour >= 24:
                self.hour -= 24
                self.next_weather -= 24
            if self.hour >= self.next_weather:
                w = self.spots[self.spot]["weather"]
                keys = list(w)
                self.weather = self.rnd.choices(keys, [w[k] for k in keys])[0]
                self.next_weather += 3.0

    def period(self) -> str:
        p = PERIODS[-1][1]
        for start, pid in PERIODS:
            if self.hour >= start:
                p = pid
        return p if self.hour >= 6.0 else "night"

    def rest_to(self, period: str) -> None:
        """텐트에서 쉬기 (게임 시간만 흐르고 실제 시간은 5초)."""
        target = {"morning": 6.0, "day": 10.0, "evening": 17.0, "night": 20.0}[period]
        while self.period() != period:
            self.hour += 0.5
            if self.hour >= 24:
                self.hour -= 24
            if self.hour >= self.next_weather or self.next_weather - self.hour > 3:
                w = self.spots[self.spot]["weather"]
                keys = list(w)
                self.weather = self.rnd.choices(keys, [w[k] for k in keys])[0]
                self.next_weather = (int(self.hour) // 3 + 1) * 3.0
        self.t += 5.0
        _ = target

    def note(self, what: str) -> None:
        self.log.append((round(self.t / 60, 1), what))

    # 장비
    def pending_legend_bait(self) -> bool:
        """살 수 있게 됐는데 돈이 모자란 전설 미끼가 있으면 장비보다 먼저 모은다."""
        s = self.s
        return any(b.get("legend_for") and b["price"] >= 0 and not s.owns("bait", b["id"])
                   and not s.bait_locked_reason(b) and not s.gear_locked_reason(b)
                   for b in load_json("baits.json")["baits"])

    def buy_upgrades(self) -> None:
        s = self.s
        cont_open = set(s.data["unlocked_continents"])
        # 특수 찌가 먼저: 지금 필요한 티어 (전설 노리면 +1). 못 사면 장비는 미루고 돈을 모은다
        if "eldrasion" in cont_open:
            need = self.float_need_now()
            for fl in load_json("floats.json")["floats"]:
                if fl["tier"] <= need and fl["id"] not in s.data["float"]["owned"] and s.float_tier() < fl["tier"]:
                    if s.buy_float(fl) == "ok":
                        self.note(f"{fl['name']} 구매")
        saving = self.pending_legend_bait() or self.float_tier_short()
        cont_open = set(s.data["unlocked_continents"])
        eq = equipment()
        # 낚싯대·릴·줄·뜰채: 다음 티어를 살 수 있고 돈이 1.3배 이상 있으면
        for kind in ("rod", "line", "reel", "net") if not saving else ():
            cur = s.gear_tier(kind)
            for g in sorted(eq[kind], key=lambda g: g["tier"]):
                if g["tier"] <= cur or (g.get("continent") and g["continent"] not in cont_open):
                    continue
                if s.data["money"] >= g["price"] * 1.3 and s.data["scales"] >= g.get("scales", 0) + self.scale_reserve():
                    if s.buy(kind, g) == "ok":
                        self.note(f"{g['name']} 구매 (T{g['tier']})")
                break
        # 미끼 (티어 미끼)
        baits = load_json("baits.json")["baits"]
        cur = s.gear_tier("bait")
        for b in sorted((b for b in baits if b.get("tier") and not saving), key=lambda b: b["tier"]):
            if b["tier"] <= cur or (b.get("continent") and b["continent"] not in cont_open):
                continue
            if s.data["money"] >= b["price"] * 2 and s.data["scales"] >= b.get("scales", 0) + self.scale_reserve():
                if s.buy("bait", b) == "ok":
                    self.note(f"{b['name']} 구매")
            break

    def float_tier_short(self) -> bool:
        return "eldrasion" in self.s.data["unlocked_continents"] and self.s.float_tier() < self.float_need_now()

    def scale_reserve(self) -> int:
        """봉인 찌용 비늘은 남겨둔다."""
        tier = self.s.float_tier()
        return 8 if tier >= 4 else 3 if tier >= 3 else 0

    def float_need_now(self) -> int:
        """열린 엘드라시온 낚시터 중 가장 높은 요구 티어 (그곳 전설 미끼가 있으면 +1)."""
        need = 0
        for sid in self.s.data["unlocked_spots"]:
            sp = self.spots[sid]
            if sp.get("continent") != "eldrasion":
                continue
            n = sp.get("float_req", 0)
            leg = next((f for f in all_fish() if f["spot"] == sid and f["rarity"] == "legend"), None)
            if leg and not self.s.caught(leg["id"]) and self.legend_bait_owned(leg):
                n += 1
            need = max(need, min(5, n))
        return need

    def legend_bait_owned(self, leg: dict) -> bool:
        return self.s.owns("bait", leg.get("bait", ""))

    def buy_legend_baits(self) -> None:
        s = self.s
        for b in load_json("baits.json")["baits"]:
            if b.get("legend_for") and not s.owns("bait", b["id"]) and b["price"] >= 0:
                if (not s.bait_locked_reason(b) and not s.gear_locked_reason(b)
                        and s.data["money"] >= b["price"] * 1.1):
                    cur = s.data["gear"]["bait"]
                    if s.buy("bait", b) == "ok":
                        s.data["gear"]["bait"] = cur
                        self.note(f"{b['name']} 구매")

    # 해금
    def try_unlocks(self) -> None:
        from src.scene.map_scene import unlock_status
        s = self.s
        for sp in self.spots.values():
            if sp["id"] in s.data["unlocked_spots"]:
                continue
            ok, _ = unlock_status(s, sp)
            if ok:
                s.data["money"] -= sp["unlock"].get("cost", 0)
                s.data["unlocked_spots"].append(sp["id"])
                reward = {"secret": "dragon_pearl", "world_tree": "world_fruit"}.get(sp["id"])
                if reward:
                    s.data["owned"]["bait"].append(reward)
                self.note(f"해금: {sp['name']}")
                self.unlock_money[sp["id"]] = s.data["money"]

    # 어디서 낚을까
    def scales_short(self) -> bool:
        """다음 특수 찌를 사는데 비늘만 모자란가."""
        need = self.float_need_now()
        for fl in load_json("floats.json")["floats"]:
            if fl["tier"] <= need and fl["id"] not in self.s.data["float"]["owned"]:
                if self.s.data["scales"] < fl.get("scales", 0):
                    return True
        return False

    def need_legend_s(self) -> bool:
        """세계수 해금에서 '전설 S랭크'만 모자라면 잡은 전설을 다시 노린다."""
        from src.scene.map_scene import unlock_status
        if "world_tree" in self.s.data["unlocked_spots"]:
            return False
        _, rows = unlock_status(self.s, self.spots["world_tree"])
        return all(ok for label, ok in rows if "전설 S" not in label) and \
            any(not ok for label, ok in rows if "전설 S" in label)

    def choose_spot(self) -> None:
        s = self.s
        self.rehunt = None
        if self.scales_short() or self.need_legend_s():
            # 비늘이 모자라면 이미 잡은 엘드라시온 전설을 다시 사냥 (+2)
            for f in all_fish():
                if (f["rarity"] == "legend" and s.caught(f["id"]) and f["spot"] in s.data["unlocked_spots"]
                        and self.spots[f["spot"]].get("continent") == "eldrasion" and self.legend_bait_owned(f)
                        and self.can_hold(f["spot"], True)):
                    self.rehunt = f["id"]
                    self.go(f["spot"])
                    return
        order = ["reservoir", "valley", "breakwater", "offshore", "deep", "secret",
                 "marsh", "crystal_cave", "sky_falls", "volcano", "ice_sea", "world_tree"]
        opened = [o for o in order if o in s.data["unlocked_spots"]]
        # 1) 아직 안 잡은 전설이 있고 미끼가 있는 곳
        for o in reversed(opened):
            leg = next((f for f in all_fish() if f["spot"] == o and f["rarity"] == "legend"), None)
            if leg and not s.caught(leg["id"]) and self.legend_bait_owned(leg) and self.can_hold(o, True):
                self.go(o)
                return
        # 2) 가장 높은 낚시터 중 아직 못 잡은 종이 있는 곳 (도감 조건), 없으면 가장 높은 곳.
        #    낮은 낚시터의 빈 칸은 지금 날씨에 나오는 종이 있을 때만 들른다 (실제 플레이어처럼 도감 조건을 보고)
        for i, o in enumerate(reversed(opened)):
            missing = [f for f in all_fish() if f["spot"] == o and f["rarity"] != "legend" and not s.caught(f["id"])]
            if i > 0:
                missing = [f for f in missing if self.weather in f["weathers"]]
            if missing and self.can_hold(o, False):
                self.go(o)
                return
        for o in reversed(opened):
            if self.can_hold(o, False):
                self.go(o)
                return

    def can_hold(self, spot: str, legend: bool) -> bool:
        sp = self.spots[spot]
        if sp.get("continent") != "eldrasion":
            return True
        need = sp.get("float_req", 0) + (1 if legend else 0)
        return self.s.float_tier() >= min(5, need)

    def go(self, spot: str) -> None:
        if spot != self.spot:
            old = self.spots[self.spot].get("continent")
            self.spot = spot
            self.s.data["continent"] = self.spots[spot].get("continent", "sharmion")
            self.advance(8.0)
            if old != self.s.data["continent"] and self.s.data["continent"] == "eldrasion" and self.eldra_entry_t is None:
                self.eldra_entry_t = self.t

    # 한 번 낚기
    def fish_once(self) -> None:
        s = self.s
        sp = self.spots[self.spot]
        leg = next((f for f in all_fish() if f["spot"] == self.spot and f["rarity"] == "legend"), None)
        hunting = leg is not None and (not s.caught(leg["id"]) or getattr(self, "rehunt", None) == leg["id"]) \
            and self.legend_bait_owned(leg)
        bait = None
        fish = None
        if hunting:
            # 전설 시간대로 쉬고, 날씨가 맞을 때만 전설 미끼
            if self.period() not in leg["times"]:
                self.rest_to(leg["times"][0])
            if self.weather in leg["weathers"]:
                bait = next(b for b in load_json("baits.json")["baits"] if b["id"] == leg["bait"])
                if self.rnd.random() < load_json("fishing_config.json")["legend"]["chance"]:
                    fish = leg
        if fish is None and not hunting:
            # 아직 못 잡은 종이 지금 시간대에 안 나오면 텐트에서 쉬어 그 시간대로 (실제 플레이어처럼)
            missing = [f for f in all_fish() if f["spot"] == self.spot and f["rarity"] != "legend"
                       and not s.caught(f["id"]) and self.weather in f["weathers"]]
            if missing and not any(self.period() in f["times"] for f in missing):
                self.rest_to(missing[0]["times"][0])
        if fish is None:
            bait = s.equipped("bait") if not bait else bait
            fish = pick_fish(self.period(), self.weather, 28.0, self.rnd, self.spot, bait)
        if fish is None:
            self.advance(self.OVERHEAD)
            return
        rec = self.d[fish["id"]][self.skill]
        need = s.float_need(fish, sp)
        escape = need > s.float_tier()
        hum = HUMAN[self.skill]
        ok = self.rnd.random() < rec["success"] * hum["success"] and not escape
        t_fight = rec["t_ok"] if ok and rec["t_ok"] else rec["t_all"]
        self.advance(self.OVERHEAD + (t_fight or 40))
        if not ok:
            s.data["stats"]["lost"] += 1
            return
        ranks = hum["ranks"]
        rank = self.rnd.choices("SABC", [ranks[k] for k in "SABC"])[0]
        lo, hi = fish["size_cm"]
        size = lo + (hi - lo) * self.rnd.betavariate(2, 2.4)
        price = sell_price(fish, size, rank)
        first = not s.caught(fish["id"])
        s.record_catch({"fish": fish, "size": size, "rank": rank, "price": price,
                        "perfects": self.rnd.randint(0, 6 if fish["rarity"] == "legend" else 3)})
        s.data["keepnet"].pop()
        s.data["money"] += price
        s.data["stats"]["earned"] += price
        st = self.spot_stats.setdefault(self.spot, [0, 0.0, 0])
        st[0] += price
        st[2] += 1
        if fish["rarity"] == "legend":
            self.note(f"전설 포획: {fish['name']}")
            if sp.get("continent") == "eldrasion":
                s.data["scales"] += 5 if first else 2
            if fish["id"] == "dragon_carp" and s.unlock_continent("eldrasion"):
                self.note("엘드라시온 해금")
        if self.use_chests:
            from src.save import treasure
            g = treasure.roll_drop(s, fish, rank, self.rnd)
            if g:
                self.chests_by_cont[sp.get("continent", "sharmion")][0] += 1
                treasure.open_chest(s, g, self.spot, self.rnd)  # 바로 연다 (골드·소재만 반영, 아이템 효과는 없음)

    def run(self, max_hours: float = 40.0) -> dict:
        while self.t < max_hours * 3600:
            self.try_unlocks()
            self.buy_legend_baits()
            self.buy_upgrades()
            self.choose_spot()
            self.fish_once()
            if int(self.t) // 300 != int(self.t - 1) // 300:
                self.money_curve.append((round(self.t / 60), self.s.data["money"]))
            if self.s.caught("orsiel"):
                self.note("오르시엘 포획 — 끝")
                break
        return self.summary()

    def summary(self) -> dict:
        s = self.s
        first = {}
        for t, what in self.log:
            first.setdefault(what, t)
        t6 = next((t for t, w in self.log if "T6" in w), None)
        return {
            "minutes": round(self.t / 60), "log": self.log, "first": first,
            "chests": {k: (v[0], round(v[0] / max(1e-9, v[1] / 3600), 2)) for k, v in self.chests_by_cont.items()},
            "eldra_entry_min": round(self.eldra_entry_t / 60) if self.eldra_entry_t else None,
            "first_t6_min": t6, "money": s.data["money"], "pity": dict(s.data["pity"]),
            "finished": s.caught("orsiel"),
            "spot_stats": {k: (round(v[0] / max(1, v[1] / 60)), round(v[1] / 60), v[2]) for k, v in self.spot_stats.items()},
            "unlock_money": self.unlock_money,
        }


def progress(runs: int = 4) -> None:
    with open(os.path.join(OUT, "balance_measure.json"), encoding="utf-8") as fp:
        data = json.load(fp)
    results = []
    for skill in ("skilled", "average"):
        for chests in (True, False):
            for r in range(runs):
                sim = Sim(data, skill, random.Random(100 + r), use_chests=chests)
                res = sim.run()
                res.update(skill=skill, use_chests=chests)
                results.append(res)
                print(f"{skill:8} 상자{'O' if chests else 'X'} #{r}: {res['minutes']}분, 완주 {res['finished']}, "
                      f"엘드라 진입 {res['eldra_entry_min']}분, 첫 T6 {res['first_t6_min']}분, 상자/시간 {res['chests']}",
                      flush=True)
    with open(os.path.join(OUT, "balance_progress.json"), "w", encoding="utf-8") as fp:
        json.dump(results, fp, ensure_ascii=False, indent=1)


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "measure"
    if cmd == "measure":
        measure(int(sys.argv[2]) if len(sys.argv) > 2 else 6)
    else:
        progress(int(sys.argv[2]) if len(sys.argv) > 2 else 4)
