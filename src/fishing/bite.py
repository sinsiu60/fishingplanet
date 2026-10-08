"""입질 + 챔질 상태머신 (로직만).

WAIT ─(대기)→ APPROACH(그림자 접근) → NIBBLE(톡톡, 가짜 입질 N회) → BITE(쑥! 챔질 창)
  - BITE 중 좌클릭 → HOOKED
  - BITE 창 지나면 → MISSED (미끼만 먹고 도망, 다시 던져야 함)
  - APPROACH/NIBBLE 중 좌클릭 → SCARED (놀라 도망, 일정 시간 입질 없음)
루어 액션(저킹 · 리트리브)은 삭제됨 (사용자 요청, DESIGN 47장) — 대기는 기다리기만.
수면 징후 보정(sign_mods): 대기 ×, 바닥형(물거품) ×, 고급 이상 ×, 변이 × (확률만).
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


def spot_price_level(spot: str) -> float:
    """그 낚시터 물고기(전설 제외) 기본가의 출현 가중 평균 = 평소 입질 한 번의 기대 기본가."""
    rw = load_json("fishing_config.json")["bite"]["rarity_weight"]
    fs = [(f["base_price"], f.get("spawn_weight", rw.get(f["rarity"], 0))) for f in load_json("fish.json")["fish"]
          if f["spot"] == spot and f["rarity"] != "legend"]
    tot = sum(w for _, w in fs)
    return sum(p * w for p, w in fs) / tot if tot else 50


def limited_here(f: dict, spot: str, level: float | None = None) -> dict:
    """계절·이벤트 한정 물고기를 지금 낚시터에 맞춘 복사본: spot = 지금 낚시터, 판매가 = 지금 입질 기대 기본가(level) × 희귀도 배율
    (어느 낚시터·시간대에서든 '조금 비싼 손님' — 시간당 골드 +10% 이내, DESIGN.md 35-15). level 없으면 낚시터 하루 평균."""
    mult = load_json("fishing_config.json")["bite"]["limited_price_mult"][f["rarity"]]
    lv = spot_price_level(spot) if level is None else level
    return dict(f, spot=spot, base_price=max(10, int(round(lv * mult, -1 if lv * mult >= 100 else 0))))


def pick_fish(period: str, weather: str, cast_distance: float, rnd=random, spot: str = "reservoir",
              bait: dict | None = None, rare_bonus: float = 0.0,
              mods: dict | None = None, season: str | None = None, extra: list | None = None,
              rare_pp: float = 0.0) -> dict | None:
    """mods = 수면 징후 보정.
    season = 지금 계절 (종별 잘 나옴 ×1.5 / 안 나옴 ×0.5, data/seasons.json), extra = [(물고기, 가중치)] 계절·날씨 이벤트 한정 물고기
    (그 낚시터 기준 시간·날씨 조건 없이 추가, 낚이면 spot = 지금 낚시터)."""
    cfg = load_json("fishing_config.json")["bite"]
    sw = load_json("seasons.json") if season else None
    if mods:
        from src.fishing.lure import profile_of
    candidates, weights, bases = [], [], []
    srm = cfg.get("spot_rarity_mult", {}).get(spot, {})   # 확률 개편 (CU7-1): 낚시터별 고급 · 희귀 배율
    from src.fishing import live_bait
    pool = [(f, None) for f in load_json("fish.json")["fish"]] + [(dict(f, spot=spot, _limited=True), w0) for f, w0 in (extra or [])]
    for f, w0 in pool:
        if f["spot"] != spot or period not in f["times"] or weather not in f["weathers"]:
            continue
        w = w0 if w0 is not None else f.get("spawn_weight", cfg["rarity_weight"].get(f["rarity"], 0))  # 종별 덮어쓰기 (조건 까다로운 희귀)
        if sw is not None and f["id"] in sw["fish"]:
            sf = sw["fish"][f["id"]]
            w *= sw["mult"]["good"] if season in sf["good"] else sw["mult"]["bad"] if season in sf["bad"] else 1.0
        if w0 is None:
            w *= srm.get(f["rarity"], 1.0)
        w *= live_bait.weight_mult(bait, f)   # 생미끼 (CU7-2): 노리는 희귀 ×3 · 희귀 생미끼 ×1.5
        base = w   # 희귀 보정 상한의 기준 (아래 보정 전)
        if weather == "storm" and f["rarity"] in ("rare", "legend"):
            w *= cfg["storm_rare_mult"]  # 폭풍: 희귀어 증가
        if bait:
            # 미끼: 물고기별·낚시터별 배율 + 티어 공통 보너스(희귀 이상)
            w *= bait.get("boost", {}).get(f["id"], 1.0) * bait.get("spot_boost", {}).get(spot, 1.0)
            if f["rarity"] in ("rare", "legend"):
                w *= bait_tier_mult(bait, "bait_tier_rare_bonus")
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
            bases.append(base)
    if not candidates:
        return None
    if extra:
        # 한정 물고기: 판매가 = 지금 후보(전설·한정 제외)의 출현 가중 기대 기본가 × 희귀도 배율,
        # 가중치 = 데이터 값 × (지금 후보 합 / 표준 풀 limited_ref_pool) — 작은 풀(비밀 낚시터 등)에서도 같은 비율로 드물게.
        base = [(c["base_price"], w) for c, w in zip(candidates, weights) if not c.get("_limited") and c["rarity"] != "legend"]
        tot = sum(w for _, w in base)
        if not tot:
            return None   # 평소 물고기가 안 나오는 시간·날씨엔 한정 물고기도 없음 (비밀 낚시터 낮 등)
        level = sum(p * w for p, w in base) / tot
        scale = tot / cfg["limited_ref_pool"]
        weights = [w * scale if c.get("_limited") else w for c, w in zip(candidates, weights)]
        candidates = [limited_here({k: v for k, v in c.items() if k != "_limited"}, spot, level) if c.get("_limited") else c
                      for c in candidates]
    if rare_bonus > 0:
        # 행운의 떡밥: 희귀 이상이 나올 확률을 +rare_bonus (%p)
        total = sum(weights)
        rare = sum(w for f, w in zip(candidates, weights) if f["rarity"] in ("rare", "legend"))
        share = rare / total
        target = min(0.95, share + rare_bonus)
        if 0 < rare and share < target:
            k = target * (total - rare) / ((1 - target) * rare)
            weights = [w * k if f["rarity"] in ("rare", "legend") else w for f, w in zip(candidates, weights)]
    if rare_pp > 0:
        # 비늘석 희귀 확률: '희귀' 등급만의 몫을 +rare_pp %p (전설 · 한정 · 다른 등급 비율은 그대로 줄어든 만큼 나눔)
        total = sum(weights)
        rare = sum(w for f, w in zip(candidates, weights) if f["rarity"] == "rare")
        if 0 < rare < total:
            share = rare / total
            target = min(0.95, share + rare_pp / 100.0)
            k = target * (total - rare) / ((1 - target) * rare)
            weights = [w * k if f["rarity"] == "rare" else w for f, w in zip(candidates, weights)]
    weights = _rare_cap(candidates, weights, bases, cfg.get("rare_boost_cap", 0.0))
    return rnd.choices(candidates, weights)[0]


def _rare_cap(cands: list, weights: list, bases: list, cap: float) -> list:
    """희귀 보정 상한 (CU7-1): 폭풍 · 원투 · 미끼 티어 · 징후 · 행운의 떡밥 · 축복 · 비늘석을 다 합쳐도
    희귀 몫이 보정 전의 cap 배를 넘지 않게 (%p 보정도 몫으로 환산돼 같이 묶임)."""
    if cap <= 0 or len(bases) != len(weights):
        return weights
    def share(ws):
        tot = sum(ws)
        return sum(w for f, w in zip(cands, ws) if f["rarity"] == "rare") / tot if tot else 0.0
    s0, s1 = share(bases), share(weights)
    limit = min(0.95, s0 * cap)
    if s0 <= 0 or s1 <= limit:
        return weights
    rare = sum(w for f, w in zip(cands, weights) if f["rarity"] == "rare")
    if rare >= sum(weights) - 1e-9:
        return weights   # 후보가 희귀뿐 (비밀 낚시터 등): 몫을 바꿀 수 없음
    k = limit * (sum(weights) - rare) / ((1 - limit) * rare)
    return [w * k if f["rarity"] == "rare" else w for f, w in zip(cands, weights)]


def stray_pick(spot: str, rnd) -> dict | None:
    """길을 잃은 손님 (CU9): 같은 대륙 다른 낚시터(이 낚시터 티어 이하 — 이웃 물에서 흘러옴)의 일반 · 고급 하나 (시간 · 날씨 조건 없이)."""
    spots = {s["id"]: s for s in load_json("spots.json")["spots"]}
    here = spots.get(spot, {})
    cont, tier = here.get("continent", "sharmion"), here.get("gear_tier", 1)
    pool = [f for f in load_json("fish.json")["fish"] if f["spot"] != spot and f["rarity"] in ("common", "uncommon")
            and spots.get(f["spot"], {}).get("continent", "sharmion") == cont
            and spots.get(f["spot"], {}).get("gear_tier", 1) <= tier]
    return rnd.choice(pool) if pool else None


def excited_action(fish: dict, rnd) -> str | None:
    """들뜬 물고기 (CU9): 그 물고기 행동 중 하나 (가중치대로) — 예고가 1.3배 빨라짐 (brain.excited_action)."""
    acts = {k: w for k, w in fish.get("actions", {}).items() if w > 0 and k not in ("idle", "pump")}
    if not acts:
        return None
    keys = list(acts)
    return rnd.choices(keys, [acts[k] for k in keys])[0]


def legend_chance(bait: dict | None) -> float:
    """입질당 전설 확률 (CU7-1): 기본 chance, 전설 미끼 위에 희귀 생미끼를 덧붙였으면 chance_live_rare."""
    lg = load_json("fishing_config.json")["legend"]
    live = (bait or {}).get("live")
    return lg.get("chance_live_rare", lg["chance"]) if live and live["kind"] == "rare" else lg["chance"]


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


_TOP10: dict = {}


def _top10_chance(far: bool) -> float:
    """크기 상위 10% (u ≥ 0.9) 가 나올 원래 확률 — 베타(2, 2.4) (+ 원투면 절반 확률로 max(u, 균등))."""
    if far not in _TOP10:
        n = 4000   # 베타(2, 2.4) 꼬리를 수치 적분 (한 번만)
        from math import gamma
        c = gamma(4.4) / (gamma(2.0) * gamma(2.4))
        p = sum(c * x * (1 - x) ** 1.4 for x in (0.9 + (i + 0.5) * 0.1 / n for i in range(n))) * 0.1 / n
        _TOP10[False] = p
        _TOP10[True] = 0.5 * p + 0.5 * (1 - (1 - p) * 0.9)
    return _TOP10[far]


def roll_size(fish: dict, cast_distance: float, rnd=random, trophy: float = 0.0) -> float:
    """trophy = 비늘석 대물 확률 (0.12 = +12%): 상위 10%가 나올 확률에 (1 + trophy)를 곱함 (46장 S4)."""
    lo, hi = fish["size_cm"]
    u = rnd.betavariate(2.0, 2.4)
    # 멀리 던지면 큰 개체 확률 ↑ (DESIGN.md 1장)
    far = cast_distance >= load_json("fishing_config.json")["bite"]["far_cast_distance"]
    if far and rnd.random() < 0.5:
        u = max(u, rnd.random())
    if trophy > 0 and u < 0.9:
        p0 = _top10_chance(far)
        if rnd.random() < p0 * trophy / (1 - p0):
            u = rnd.uniform(0.9, 1.0)
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
        # 튜토리얼 대본 (TG-01): {"fish", "wait", "approach", "first_nibble", "nibbles", "gap"} — 착수 몇 초 뒤 가짜 입질·진짜 입질이
        # 정확히 오게. 대본 중엔 이른 챔질도 놀래지 않는다 (가이드가 '아직이에요'로 알려 줌)
        self.script: dict | None = None
        self.bait: dict | None = None        # 장착한 미끼
        self.rare_bonus = 0.0                # 행운의 떡밥 (+%p)
        self.window_extra = 1.0              # 바람개비 찌: 0.95
        self.window_add = 0.0                # 비늘석 챔질 여유 +초 (46장 S4)
        self.rare_pp = 0.0                   # 비늘석 희귀 확률 +%p — 희귀 등급만 (전설 · 환상 · 변이 영향 없음)
        self.legend = False                  # 이번 입질이 전설인지
        self.phantom: dict | None = None     # 환상어 (33장): 착수 순간 판정 → 연출 동안 대기 → 가짜 입질 없이 진짜 입질
        self.wait_elapsed = 0.0
        self.sign_mods: dict = {}            # 수면 징후 보정 (낚시 씬이 매 틱)
        self.school_mult = 1.0               # 물고기 떼 지나감 (CU9): 대기 ×0.5 (낚시 씬이 매 틱)
        self.school_fish: dict | None = None  # 떼가 지나가는 동안 처음 문 종 → 같은 종이 연달아
        self.bottle_ok = True                # 유리병 편지가 남았는지 (12장 다 모으면 False)

    def _rand(self, pair) -> float:
        return self.rnd.uniform(pair[0], pair[1])

    # ── 외부 호출 ──
    def start(self, bobber_xz, cast_distance: float) -> None:
        """찌가 착수했을 때."""
        self.active = True
        self.phantom = None
        self.bobber = bobber_xz
        self.cast_distance = cast_distance
        self._to_wait()

    def start_phantom(self, bobber_xz, cast_distance: float, fish: dict, delay: float, approach: float) -> None:
        """환상어 착수: delay(파장·대사) 동안 아무것도 오지 않다가 approach 초 그림자 접근 → 가짜 입질 없이 BITE."""
        self.start(bobber_xz, cast_distance)
        self.phantom = fish
        self.phantom_approach = approach
        self.timer = delay

    def stop(self) -> None:
        """줄 회수 등으로 대기 종료."""
        self.script = None
        self.active = False
        self.legend = False
        self.phantom = None
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
        if (self.phantom is not None or self.script) and self.state in (BiteState.WAIT, BiteState.APPROACH, BiteState.NIBBLE):
            return "empty"  # 환상어·튜토리얼 대본: 진짜 입질 전 클릭은 놀래지 않는다
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
        if self.script:
            self.timer = self.script["wait"]
        self.wait_elapsed = 0.0
        self.cooldown = 0.0
        self.fish = None
        self.shadow = None

    def _pick(self) -> dict | None:
        return pick_fish(self.period, self.weather, self.cast_distance, self.rnd, self.spot, self.bait,
                         rare_bonus=self.rare_bonus, mods=self.sign_mods or None,
                         season=getattr(self, "season", None), extra=getattr(self, "extra_pool", None),
                         rare_pp=getattr(self, "rare_pp", 0.0))

    def _variety(self, fish: dict | None) -> dict | None:
        """던질 때마다 변수 (CU9, data/core.json variety): 떼 지나감(같은 종 연달아) · 유리병 편지 · 길을 잃은 손님 · 들뜬 물고기.
        전설 · 환상 · 시험 · 대본(튜토리얼) · 강제 물고기는 손대지 않음 (호출하는 쪽에서 이미 빠짐)."""
        if fish is None or fish["rarity"] in ("legend", "phantom") or fish.get("exam"):
            return fish
        v = load_json("core.json")["variety"]
        if self.school_fish is not None and self.school_fish["spot"] == fish["spot"] and self.rnd.random() < v["school_same"]:
            sf = self.school_fish   # 떼 지나감: 같은 종이 연달아 (조건이 맞을 때만 — 처음 문 종)
            if self.period in sf["times"] and self.weather in sf["weathers"]:
                fish = sf
        if fish["rarity"] == "common" and self.bottle_ok and self.rnd.random() < v["bottle_chance"]:
            return dict(fish, bottle=True, shadow_len_m=0.3)   # 물고기 대신 유리병 (그림자는 아주 작게)
        if fish["rarity"] in ("common", "uncommon") and self.rnd.random() < v["stray_chance"]:
            st = stray_pick(self.spot, self.rnd)
            if st is not None:
                fish = dict(st, stray=True)   # 길을 잃은 손님: 도감은 원래 낚시터(spot)로
        if self.rnd.random() < v["excited_chance"]:
            fish = dict(fish, excited=excited_action(fish, self.rnd))
        return fish

    def _update_wait(self, dt: float) -> None:
        """WAIT 중 대기 시계: 새 떼 징후(wait_mult) · 물고기 떼(school_mult, CU9) 만큼 빨리 간다 (루어 액션은 삭제됨)."""
        self.wait_elapsed += dt
        mult = self.sign_mods.get("wait_mult", 1.0) if self.sign_mods else 1.0
        mult *= self.school_mult
        if mult < 1.0:
            self.timer -= dt * (1 / mult - 1)

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

        if self.state == BiteState.WAIT and self.phantom is not None:
            self.dip = lerp(self.dip, 0.0, 0.2)  # 물결이 숨을 죽인다: 루어·다른 물고기 없음
            if self.timer <= 0:
                self.fish = self.phantom
                self.state = BiteState.APPROACH
                self.approach_dur = self.timer = self.phantom_approach
                ang = self.rnd.uniform(0, math.tau)
                d0 = cfg["approach_start_distance_m"]
                self.shadow = {"x0": bx + math.sin(ang) * d0, "z0": bz + math.cos(ang) * d0,
                               "x": bx + math.sin(ang) * d0, "z": bz + math.cos(ang) * d0,
                               "heading": ang + math.pi, "alpha": 0.0, "len": self.fish["shadow_len_m"], "spray": bool(self.fish.get("excited")),
                               "vx": 0.0, "vz": 0.0, "scale": 1.3}
                self.events.append("phantom_approach")
        elif self.state == BiteState.WAIT:
            self.dip = lerp(self.dip, 0.0, 0.2)
            self._update_wait(dt)
            if self.timer <= 0:
                self.legend = False
                legend = legend_candidate(self.spot, self.period, self.weather, self.cast_distance, self.bait)
                if getattr(self, "legend_block", False):
                    legend = None   # 미리 맛보기 낚시터 (CU8-⑤): 장비 조건을 채워야 전설
                if self.script:
                    from src.save.save_game import fish_by_id
                    self.fish = fish_by_id(self.script["fish"])
                    legend = None
                elif self.force_fish is not None:
                    self.fish = self.force_fish
                elif legend and self.rnd.random() < legend_chance(self.bait):
                    self.fish = legend
                else:
                    self.fish = self._variety(self._pick())
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
                if self.script:
                    self.approach_dur = self.script["approach"]
                self.timer = self.approach_dur
                ang = self.rnd.uniform(0, math.tau)
                d0 = cfg["approach_start_distance_m"]
                self.shadow = {
                    "x0": bx + math.sin(ang) * d0, "z0": bz + math.cos(ang) * d0,
                    "x": bx + math.sin(ang) * d0, "z": bz + math.cos(ang) * d0,
                    "heading": ang + math.pi, "alpha": 0.0,
                    "len": self.fish["shadow_len_m"], "spray": bool(self.fish.get("excited")), "vx": 0.0, "vz": 0.0,
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
            sh["alpha"] = max(sh["alpha"], clamp(s * 2.0, 0, 1))
            sh["heading"] = math.atan2(bx - sh["x"], bz - sh["z"])
            if self.timer <= 0:
                self.state = BiteState.NIBBLE
                lo, hi = self.fish["nibbles"]
                delta = self.bait.get("nibble_delta", 0) if self.bait else 0
                self.nibbles_left = max(0, self.rnd.randint(lo, hi) + delta)
                self.timer = self._rand(cfg["nibble_interval_sec"])
                if self.phantom is not None:
                    self.nibbles_left, self.timer = 0, 0.15  # 가짜 입질 없이 바로 진짜 입질
                elif self.script:
                    self.nibbles_left, self.timer = self.script["nibbles"], self.script["first_nibble"]

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
                    self.timer = self.script["gap"] if self.script else self._rand(cfg["nibble_interval_sec"])
                else:
                    self.state = BiteState.BITE
                    # 예민한 물고기(감성돔 등)는 챔질 창이 짧다
                    bait_mult = (self.bait.get("window_mult", 1.0) if self.bait else 1.0) \
                        * bait_tier_mult(self.bait, "bait_tier_window_bonus")
                    self.timer = cfg["bite_window_sec"] * self.fish.get("bite_window_mult", 1.0) * bait_mult \
                        * self.window_extra + self.window_add
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
