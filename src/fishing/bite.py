"""입질 + 챔질 상태머신 (로직만).

WAIT ─(대기)→ APPROACH(그림자 접근) → NIBBLE(톡톡, 가짜 입질 N회) → BITE(쑥! 챔질 창)
  - BITE 중 좌클릭 → HOOKED
  - BITE 창 지나면 → MISSED (미끼만 먹고 도망, 다시 던져야 함)
  - APPROACH/NIBBLE 중 좌클릭 → SCARED (놀라 도망, 일정 시간 입질 없음)
루어 (U7, fishing/lure.py): WAIT 중 저킹·리트리브·멈춤 → 후보 물고기 관심도 → 대기 시계가 빨라지고(최대 ×1/0.6) 그 물고기가 온다.
  관심도는 그림자 연출로만 (방향 틀기 → 다가옴 → 맴돎). 아무것도 안 하면 지금과 같고, 대기는 원래 최대를 넘지 않는다.
수면 징후 보정(sign_mods): 대기 ×, 멈춤형 ×, 고급 이상 ×, 변이 × (확률만).
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
              bait: dict | None = None, rare_bonus: float = 0.0, pref: str | None = None,
              mods: dict | None = None) -> dict | None:
    """pref = 지금 루어 리듬(그 리듬을 좋아하는 물고기 ×1.5), mods = 수면 징후 보정."""
    cfg = load_json("fishing_config.json")["bite"]
    if pref or mods:
        from src.fishing.lure import cfg as lure_cfg, profile_of
        pref_mult = lure_cfg()["pref_weight_mult"]
    candidates, weights = [], []
    for f in load_json("fish.json")["fish"]:
        if f["spot"] != spot or period not in f["times"] or weather not in f["weathers"]:
            continue
        w = f.get("spawn_weight", cfg["rarity_weight"].get(f["rarity"], 0))  # 종별 덮어쓰기 (조건 까다로운 희귀)
        if weather == "storm" and f["rarity"] in ("rare", "legend"):
            w *= cfg["storm_rare_mult"]  # 폭풍: 희귀어 증가
        if bait:
            # 미끼: 물고기별·낚시터별 배율 + 티어 공통 보너스(희귀 이상)
            w *= bait.get("boost", {}).get(f["id"], 1.0) * bait.get("spot_boost", {}).get(spot, 1.0)
            if f["rarity"] in ("rare", "legend"):
                w *= bait_tier_mult(bait, "bait_tier_rare_bonus")
        if pref and profile_of(f) == pref:
            w *= pref_mult  # 루어 리듬에 맞는 물고기
        if mods:
            if profile_of(f) == "pause":
                w *= mods.get("pause_mult", 1.0)  # 물거품: 바닥형
            if f["rarity"] != "common":
                w *= mods.get("rare_mult", 1.0)  # 물고기 점프: 고급 이상
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
        # 루어 (U7)
        from src.fishing.lure import LureRhythm, cfg as lure_cfg
        self.lcfg = lure_cfg()
        self.lure = LureRhythm()
        self.lure_in = (False, False)        # (이번 틱 저킹, 리트리브 중) — 낚시 씬이 넣어 줌
        self.lure_t = 0.0
        self.candidate: dict | None = None   # 관심을 보이는 근처 물고기
        self.cand_cooldown = 0.0
        self.cand_count = 0
        self.wait_elapsed = 0.0
        self.wait_cap = 0.0
        self.lure_bite = False               # 이번 입질이 루어로 꾄 것인지 (의뢰 '저킹만으로')
        self.lure_used: set = set()
        self.sign_mods: dict = {}            # 수면 징후 보정 (낚시 씬이 매 틱)
        self.lurk_phase = 0.0

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
        wmult = self.cfg["weather_bite_mult"].get(self.weather, 1.0)
        wait = self._rand(self.cfg["wait_sec"]) / wmult
        self.timer = wait + self.cooldown
        self.wait_cap = self.cfg["wait_sec"][1] / wmult + self.cooldown  # 루어를 잘못 써도 이 이상 안 기다린다
        self.wait_elapsed = 0.0
        self.cooldown = 0.0
        self.fish = None
        self.shadow = None
        from src.fishing.lure import LureRhythm
        self.lure = LureRhythm()
        self.lure_t = 0.0
        self.candidate = None
        self.cand_cooldown = 0.0
        self.cand_count = 0
        self.lure_bite = False
        self.lure_used = set()

    def interest(self) -> float:
        """후보 물고기의 관심도 -1~1 (루어를 안 썼으면 0)."""
        if self.candidate is None or not self.lure.engaged:
            return 0.0
        from src.fishing.lure import profile_of
        return self.lure.score[profile_of(self.candidate)]

    def _pick(self, pref: str | None = None) -> dict | None:
        return pick_fish(self.period, self.weather, self.cast_distance, self.rnd, self.spot, self.bait,
                         rare_bonus=self.rare_bonus, pref=pref, mods=self.sign_mods or None)

    def _update_lure(self, dt: float) -> None:
        """WAIT 중 루어: 리듬 점수 → 후보 물고기 관심도 → 대기 시계·그림자."""
        lc = self.lcfg
        jerk, retrieving = self.lure_in
        self.lure_in = (False, False)
        self.lure_t += dt
        self.lure.update(dt, self.lure_t, jerk, retrieving)
        self.lure.events.clear()
        self.wait_elapsed += dt
        bx, bz = self.bobber
        if self.lure.engaged and self.candidate is None and self.force_fish is None:
            self.cand_cooldown -= dt
            if self.cand_cooldown <= 0 and self.cand_count <= lc["max_swaps"]:
                self.cand_count += 1
                self.candidate = self._pick(self.lure.current())
                if self.candidate is not None:
                    ang = self.rnd.uniform(0, math.tau)
                    d = lc["lurk_distance"]
                    self.shadow = {"x": bx + math.sin(ang) * d, "z": bz + math.cos(ang) * d, "x0": 0.0, "z0": 0.0,
                                   "heading": ang + math.pi / 2, "alpha": 0.0, "len": self.candidate["shadow_len_m"],
                                   "vx": 0.0, "vz": 0.0, "scale": 1.0, "ang": ang, "lurk": True}
        k = self.interest()
        # 대기 시계: 관심도만큼 빨리 (최대 ×1/0.6), 싫어하면 조금 느리게 — 단 원래 최대 대기는 넘지 않음
        if k >= 0:
            rate = 1 + (1 / lc["wait_mult_best"] - 1) * k
        else:
            rate = max(lc["wait_rate_min"], 1 + k * 0.25)
        rate /= self.sign_mods.get("wait_mult", 1.0) if self.sign_mods else 1.0  # 새 떼
        self.timer -= dt * (rate - 1)
        if k >= lc["bite_at"]:
            self.timer = min(self.timer, lc["bite_soon_sec"])  # 맴돌다가 곧 문다
        if self.wait_elapsed >= self.wait_cap:
            self.timer = min(self.timer, 0.0)
        sh = self.shadow
        if sh is not None and sh.get("lurk"):
            self._move_lurker(sh, k, dt)
        from src.fishing.lure import profile_of
        cur = self.lure.current()
        mismatch = cur is not None and k <= 0 and self.candidate is not None and profile_of(self.candidate) != cur
        if self.candidate is not None and (k <= lc["leave_at"] or mismatch):
            # 싫어서 떠난다: 그림자가 돌아서 멀어지고, 잠시 뒤 다른 물고기
            if sh is not None:
                away = math.atan2(sh["x"] - bx, sh["z"] - bz)
                sh.update(vx=math.sin(away) * 3, vz=math.cos(away) * 3, lurk=False, leaving=True)
            self.candidate = None
            self.cand_cooldown = lc["swap_cooldown_sec"]
            for p in self.lure.score:
                self.lure.score[p] = max(self.lure.score[p], -0.2)  # 새 물고기는 처음부터 다시
            self.events.append("lure_leave")
        if sh is not None and sh.get("leaving"):
            sh["x"] += sh["vx"] * dt
            sh["z"] += sh["vz"] * dt
            sh["alpha"] = max(0.0, sh["alpha"] - dt * 1.2)
            if sh["alpha"] <= 0:
                self.shadow = None

    def _move_lurker(self, sh: dict, k: float, dt: float) -> None:
        """관심도 연출: 멀리서 어슬렁 → 찌 쪽으로 돌기 → 다가오기 → 찌 주변 맴돌기 / 싫으면 돌아섬."""
        lc = self.lcfg
        bx, bz = self.bobber
        self.lurk_phase += dt
        near = lc["near_distance"] + (lc["lurk_distance"] - lc["near_distance"]) * (1 - max(0.0, min(1.0,
                                                                                                     (k - lc["turn_at"]) / (lc["circle_at"] - lc["turn_at"]))))
        if k >= lc["circle_at"]:
            sh["ang"] += dt * 0.9  # 맴돌기
        else:
            sh["ang"] += dt * 0.15 * math.sin(self.lurk_phase * 0.7)
        tx, tz = bx + math.sin(sh["ang"]) * near, bz + math.cos(sh["ang"]) * near
        sh["x"] += (tx - sh["x"]) * min(1.0, dt * 1.2)
        sh["z"] += (tz - sh["z"]) * min(1.0, dt * 1.2)
        to_bob = math.atan2(bx - sh["x"], bz - sh["z"])
        if k >= lc["circle_at"]:
            want = sh["ang"] + math.pi / 2  # 둘레를 따라 돈다
        elif k >= lc["turn_at"]:
            want = to_bob  # 찌 쪽을 본다
        elif k < 0:
            want = to_bob + math.pi  # 돌아선다
        else:
            want = to_bob + math.pi / 2  # 관심 없음: 옆으로 지나감
        d = (want - sh["heading"] + math.pi) % math.tau - math.pi
        sh["heading"] += d * min(1.0, dt * 3)
        sh["alpha"] = min(1.0 if k >= 0 else 0.6, sh["alpha"] + dt * 1.5)

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
            self._update_lure(dt)
            if self.timer <= 0:
                self.legend = False
                legend = legend_candidate(self.spot, self.period, self.weather, self.cast_distance, self.bait)
                lurker = self.shadow if self.shadow and self.shadow.get("lurk") else None
                if self.force_fish is not None:
                    self.fish = self.force_fish
                elif legend and self.rnd.random() < load_json("fishing_config.json")["legend"]["chance"]:
                    self.fish = legend
                elif self.candidate is not None and self.interest() >= self.lcfg["commit_interest"]:
                    self.fish = self.candidate  # 루어로 꾄 물고기
                    self.lure_bite = True
                    self.lure_used = set(self.lure.used)
                    from src.fishing.lure import profile_of
                    self.lure_profile = profile_of(self.candidate)
                else:
                    self.fish = self._pick()
                if self.fish is not self.candidate:
                    lurker = None  # 다른 물고기가 왔다: 어슬렁대던 그림자는 그대로 사라짐
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
                if lurker is not None:
                    # 맴돌던 그 자리에서 마지막 접근 (보이던 그림자 그대로)
                    self.shadow.update(x0=lurker["x"], z0=lurker["z"], x=lurker["x"], z=lurker["z"],
                                       alpha=lurker["alpha"], heading=lurker["heading"])
                self.candidate = None

        elif self.state == BiteState.APPROACH:
            s = smoothstep(1.0 - self.timer / self.approach_dur)
            sh = self.shadow
            # 찌 앞 0.45m 지점까지 접근
            tx = bx + (sh["x0"] - bx) * 0.13
            tz = bz + (sh["z0"] - bz) * 0.13
            sh["x"] = lerp(sh["x0"], tx, s)
            sh["z"] = lerp(sh["z0"], tz, s)
            sh["alpha"] = max(sh["alpha"], clamp(s * 2.0, 0, 1))
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
