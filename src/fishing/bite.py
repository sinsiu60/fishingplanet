"""입질 + 챔질 상태머신 (로직만).

WAIT ─(대기)→ APPROACH(그림자 접근) → NIBBLE(톡톡, 가짜 입질 N회) → BITE(쑥! 챔질 창)
  - BITE 중 좌클릭 → HOOKED
  - BITE 창 지나면 → MISSED (미끼만 먹고 도망, 다시 던져야 함)
  - APPROACH/NIBBLE 중 좌클릭 → SCARED (놀라 도망, 일정 시간 입질 없음)
"""
import math
import random
from enum import Enum, auto

from src.core.config import load_json
from src.core.mathutil import clamp, lerp, smoothstep


class BiteState(Enum):
    WAIT = auto()
    APPROACH = auto()
    NIBBLE = auto()
    BITE = auto()
    HOOKED = auto()
    MISSED = auto()
    SCARED = auto()


def bait_tier_mult(bait: dict | None, key: str) -> float:
    """미끼 티어 공통 보너스 배율 (티어 1 = 1.0). 티어 없는 전설 미끼는 1.0."""
    if not bait or not bait.get("tier"):
        return 1.0
    return 1.0 + load_json("equipment.json")["_rules"][key] * (bait["tier"] - 1)


def pick_fish(period: str, weather: str, cast_distance: float, rnd=random, spot: str = "reservoir",
              bait: dict | None = None, rare_bonus: float = 0.0) -> dict | None:
    cfg = load_json("fishing_config.json")["bite"]
    candidates, weights = [], []
    for f in load_json("fish.json")["fish"]:
        if f["spot"] != spot or period not in f["times"] or weather not in f["weathers"]:
            continue
        w = cfg["rarity_weight"].get(f["rarity"], 0)
        if weather == "storm" and f["rarity"] in ("rare", "legend"):
            w *= cfg["storm_rare_mult"]  # 폭풍: 희귀어 증가
        if bait:
            # 미끼: 물고기별·낚시터별 배율 + 티어 공통 보너스(희귀 이상)
            w *= bait.get("boost", {}).get(f["id"], 1.0) * bait.get("spot_boost", {}).get(spot, 1.0)
            if f["rarity"] in ("rare", "legend"):
                w *= bait_tier_mult(bait, "bait_tier_rare_bonus")
        if f["rarity"] != "common":
            if cast_distance >= cfg["far_cast_distance"]:
                w *= cfg["far_rare_mult"]
            elif cast_distance <= cfg["near_cast_distance"]:
                w *= cfg["near_rare_mult"]
        if w > 0:
            candidates.append(f)
            weights.append(w)
    if not candidates:
        return None
    if rare_bonus > 0:
        # 행운의 떡밥: 희귀 이상이 나올 확률을 +rare_bonus (%p)
        total = sum(weights)
        rare = sum(w for f, w in zip(candidates, weights) if f["rarity"] in ("rare", "legend"))
        share = rare / total
        target = min(0.95, share + rare_bonus)
        if 0 < rare and share < target:
            k = target * (total - rare) / ((1 - target) * rare)
            weights = [w * k if f["rarity"] in ("rare", "legend") else w for f, w in zip(candidates, weights)]
    return rnd.choices(candidates, weights)[0]


def legend_candidate(spot: str, period: str, weather: str, cast_distance: float, bait: dict | None) -> dict | None:
    """전설 등장 조건: 낚시터·시간대·날씨·전용 미끼·거리를 모두 만족해야 한다."""
    if not bait or not bait.get("legend_for"):
        return None
    if cast_distance < load_json("fishing_config.json")["legend"]["min_distance"]:
        return None
    for f in load_json("fish.json")["fish"]:
        if (f["id"] == bait["legend_for"] and f["spot"] == spot and period in f["times"]
                and weather in f["weathers"]):
            return f
    return None


def roll_size(fish: dict, cast_distance: float, rnd=random) -> float:
    lo, hi = fish["size_cm"]
    u = rnd.betavariate(2.0, 2.4)
    # 멀리 던지면 큰 개체 확률 ↑ (DESIGN.md 1장)
    if cast_distance >= load_json("fishing_config.json")["bite"]["far_cast_distance"] and rnd.random() < 0.5:
        u = max(u, rnd.random())
    return round(lo + (hi - lo) * u, 1)


class BiteController:
    def __init__(self, rnd: random.Random | None = None):
        self.cfg = load_json("fishing_config.json")["bite"]
        self.rnd = rnd or random.Random()
        self.state = BiteState.WAIT
        self.active = False
        self.timer = 0.0
        self.cooldown = 0.0
        self.fish: dict | None = None
        self.nibbles_left = 0
        self.dip = 0.0          # 찌 잠김 0~1
        self.tip_pull = 0.0     # 낚싯대 끝 까딱 (px)
        self.nibble_t = -1.0
        self.shadow: dict | None = None
        self.events: list[str] = []
        self.bobber = (0.0, 0.0)
        self.cast_distance = 0.0
        self.period, self.weather = "day", "clear"
        self.spot = "reservoir"
        self.force_fish: dict | None = None  # 테스트용 강제 물고기
        self.bait: dict | None = None        # 장착한 미끼
        self.rare_bonus = 0.0                # 행운의 떡밥 (+%p)
        self.window_extra = 1.0              # 바람개비 찌: 0.95
        self.legend = False                  # 이번 입질이 전설인지

    def _rand(self, pair) -> float:
        return self.rnd.uniform(pair[0], pair[1])

    # ── 외부 호출 ──
    def start(self, bobber_xz, cast_distance: float) -> None:
        """찌가 착수했을 때."""
        self.active = True
        self.bobber = bobber_xz
        self.cast_distance = cast_distance
        self._to_wait()

    def stop(self) -> None:
        """줄 회수 등으로 대기 종료."""
        self.active = False
        self.legend = False
        self.state = BiteState.WAIT
        self.shadow = None
        self.dip = 0.0
        self.fish = None

    def set_conditions(self, period: str, weather: str, spot: str = "reservoir") -> None:
        self.period, self.weather, self.spot = period, weather, spot

    def hookset(self) -> str:
        """좌클릭(챔질). 결과: 'hooked' / 'scared' / 'empty'."""
        if not self.active:
            return "empty"
        if self.state == BiteState.BITE:
            self.state = BiteState.HOOKED
            self.events.append("hooked")
            return "hooked"
        if self.state in (BiteState.APPROACH, BiteState.NIBBLE):
            self._scare()
            return "scared"
        return "empty"

    # ── 내부 ──
    def _to_wait(self) -> None:
        self.state = BiteState.WAIT
        wait = self._rand(self.cfg["wait_sec"]) / self.cfg["weather_bite_mult"].get(self.weather, 1.0)
        self.timer = wait + self.cooldown
        self.cooldown = 0.0
        self.fish = None
        self.shadow = None

    def _scare(self) -> None:
        self.state = BiteState.SCARED
        self.timer = 0.6
        self.cooldown = self.cfg["scare_cooldown_sec"]
        self.events.append("scared")
        if self.shadow:
            sx, sz = self.shadow["x"], self.shadow["z"]
            away = math.atan2(sx - self.bobber[0], sz - self.bobber[1])
            self.shadow["vx"] = math.sin(away) * 6
            self.shadow["vz"] = math.cos(away) * 6

    def update(self, dt: float) -> None:
        if not self.active:
            return
        cfg = self.cfg
        self.timer -= dt
        bx, bz = self.bobber
        self.tip_pull = lerp(self.tip_pull, 0.0, 0.12)

        if self.state == BiteState.WAIT:
            self.dip = lerp(self.dip, 0.0, 0.2)
            if self.timer <= 0:
                self.legend = False
                legend = legend_candidate(self.spot, self.period, self.weather, self.cast_distance, self.bait)
                if self.force_fish is not None:
                    self.fish = self.force_fish
                elif legend and self.rnd.random() < load_json("fishing_config.json")["legend"]["chance"]:
                    self.fish = legend
                else:
                    self.fish = pick_fish(self.period, self.weather, self.cast_distance, self.rnd, self.spot,
                                          self.bait, rare_bonus=self.rare_bonus)
                self.legend = self.fish is not None and self.fish["rarity"] == "legend"
                if self.fish is None:
                    self.timer = 3.0
                    return
                self.state = BiteState.APPROACH
                self.approach_dur = self._rand(cfg["approach_sec"])
                if self.legend:
                    # 전설: 거대한 그림자가 천천히 다가온다
                    self.approach_dur *= load_json("fishing_config.json")["legend"]["approach_mult"]
                    self.events.append("legend_approach")
                self.timer = self.approach_dur
                ang = self.rnd.uniform(0, math.tau)
                d0 = cfg["approach_start_distance_m"]
                self.shadow = {
                    "x0": bx + math.sin(ang) * d0, "z0": bz + math.cos(ang) * d0,
                    "x": bx + math.sin(ang) * d0, "z": bz + math.cos(ang) * d0,
                    "heading": ang + math.pi, "alpha": 0.0,
                    "len": self.fish["shadow_len_m"], "vx": 0.0, "vz": 0.0,
                    "scale": load_json("fishing_config.json")["legend"]["shadow_scale"] if self.legend else 1.0,
                }

        elif self.state == BiteState.APPROACH:
            s = smoothstep(1.0 - self.timer / self.approach_dur)
            sh = self.shadow
            # 찌 앞 0.45m 지점까지 접근
            tx = bx + (sh["x0"] - bx) * 0.13
            tz = bz + (sh["z0"] - bz) * 0.13
            sh["x"] = lerp(sh["x0"], tx, s)
            sh["z"] = lerp(sh["z0"], tz, s)
            sh["alpha"] = clamp(s * 2.0, 0, 1)
            sh["heading"] = math.atan2(bx - sh["x"], bz - sh["z"])
            if self.timer <= 0:
                self.state = BiteState.NIBBLE
                lo, hi = self.fish["nibbles"]
                delta = self.bait.get("nibble_delta", 0) if self.bait else 0
                self.nibbles_left = max(0, self.rnd.randint(lo, hi) + delta)
                self.timer = self._rand(cfg["nibble_interval_sec"])

        elif self.state == BiteState.NIBBLE:
            sh = self.shadow
            sh["x"] += math.sin(self.timer * 5) * 0.004
            # 톡톡: 짧고 얕게 잠김
            if self.nibble_t >= 0:
                self.nibble_t += dt
                k = self.nibble_t / cfg["nibble_dip_sec"]
                self.dip = cfg["nibble_dip_depth"] * math.sin(math.pi * clamp(k, 0, 1))
                if k >= 1:
                    self.nibble_t = -1.0
                    self.dip = 0.0
            if self.timer <= 0 and self.nibble_t < 0:
                if self.nibbles_left > 0:
                    self.nibbles_left -= 1
                    self.nibble_t = 0.0
                    self.tip_pull = 3.0
                    self.events.append("nibble")
                    self.timer = self._rand(cfg["nibble_interval_sec"])
                else:
                    self.state = BiteState.BITE
                    # 예민한 물고기(감성돔 등)는 챔질 창이 짧다
                    bait_mult = (self.bait.get("window_mult", 1.0) if self.bait else 1.0) \
                        * bait_tier_mult(self.bait, "bait_tier_window_bonus")
                    self.timer = cfg["bite_window_sec"] * self.fish.get("bite_window_mult", 1.0) * bait_mult \
                        * self.window_extra
                    self.bite_t = 0.0
                    self.tip_pull = 12.0
                    self.events.append("bite")

        elif self.state == BiteState.BITE:
            # 쑥: 찌가 완전히 잠기고 낚싯대 끝이 크게 당겨짐
            self.bite_t += dt
            self.dip = clamp(self.bite_t / cfg["bite_sink_sec"], 0, 1)
            self.tip_pull = max(self.tip_pull, 10.0)
            sh = self.shadow
            sh["x"] = lerp(sh["x"], bx, 0.2)
            sh["z"] = lerp(sh["z"], bz, 0.2)
            if self.timer <= 0:
                self.state = BiteState.MISSED
                self.events.append("missed")
                self.shadow["vx"] = math.sin(sh["heading"]) * 4
                self.shadow["vz"] = math.cos(sh["heading"]) * 4

        elif self.state in (BiteState.SCARED, BiteState.MISSED):
            self.dip = lerp(self.dip, 0.0, 0.15)
            sh = self.shadow
            if sh:
                sh["x"] += sh["vx"] * dt
                sh["z"] += sh["vz"] * dt
                sh["alpha"] = max(0.0, sh["alpha"] - dt * 1.6)
                if sh["alpha"] <= 0:
                    self.shadow = None
            if self.state == BiteState.SCARED and self.timer <= 0:
                self._to_wait()
            # MISSED: 미끼가 없으니 다시 던질 때까지 입질 없음

        elif self.state == BiteState.HOOKED:
            self.dip = 1.0
            self.tip_pull = 14.0
