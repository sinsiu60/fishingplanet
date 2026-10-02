"""파이팅 모델 (로직만). DESIGN.md 2장.

phase: fight → net(뜰채) → caught
                 ↘ lost (줄 끊김 / 바늘 빠짐)
"""
import math
import random

from src.core.config import load_json
from src.core.mathutil import clamp, lerp
from src.fish_ai.brain import FishBrain
from src.fishing import rank as rank_mod

LOSE_REASONS = {
    "snap": ("줄이 끊어졌다", "빨간 구간에 너무 오래 있었다. 돌진할 땐 드랙(Q)을 낮추고 감기를 멈추세요."),
    "slack": ("바늘이 빠졌다", "줄이 너무 느슨했다. 장력을 초록 구간 아래로 떨어뜨리지 마세요."),
    "jump": ("바늘이 빠졌다", "점프 정점에 낚싯대를 숙이지 못했다. 그림자가 커지면 우클릭을 준비하세요."),
    "snag": ("줄이 걸려 끊어졌다", "물고기가 위협 구역(수초·바위)으로 들어갔다. 그쪽으로 가면 마우스를 반대로 당겨 빼내세요."),
    "worn": ("바늘이 빠졌다", "신호 대응(숙이기·꺾기·몸털기)을 세 번 놓쳐 바늘이 헐거워졌다. 바늘 게이지의 어두운 칸은 다시 줄어들지 않아요."),
    "escape": ("마지막 발악! 줄을 끊고 달아났다", "엘드라시온의 물고기는 특수 찌 없이는 끝까지 잡을 수 없다. 상점에서 필요한 찌를 장착하세요."),
}


class Fight:
    def __init__(self, fish: dict, size_cm: float, cast_distance: float, angle: float, yaw: float,
                 gear: dict | None = None, rnd: random.Random | None = None, hazards: list | None = None,
                 gimmick: str | None = None, float_need: int = 0, float_tier: int = 0):
        root = load_json("fishing_config.json")
        self.cfg = root["fight"]
        self.fcfg = root["flick"]
        self.gear = gear or root["default_gear"]
        self.rnd = rnd or random.Random()
        self.fish = fish
        self.size_cm = size_cm
        self.brain = FishBrain(fish, self.rnd)
        self.phase = "fight"
        self.green_low, self.green_high = self.gear["rod_green"]
        self.tension = 45.0
        self.target = 45.0
        self.line_max = self.gear["line_max"]
        self.line = float(self.line_max)
        self.line_damage = 0.0
        self.hook = 0.0
        self.hook_floor = 0.0  # 신호 대응 실패로 쌓인, 줄어들지 않는 바늘 게이지 (한 번에 1/3)
        # 힘센 물고기의 울렁임 (장력이 천천히 크게 오르내림) — 좋은 낚싯대(넓은 초록)일수록 버티기 쉽다
        self.heave_amp = max(0.0, fish.get("power", 1.0) - self.cfg["heave_from_power"]) * self.cfg["heave_per_power"]
        self.heave_phase = self.rnd.uniform(0, math.tau)
        self.stamina_max = float(fish.get("stamina", 100))
        self.stamina = self.stamina_max
        self.cast_distance = cast_distance
        self.distance = cast_distance
        self.angle = angle
        self.yaw = yaw
        self.drag_steps = self.gear["drag_steps"]
        self.drag = (self.drag_steps + 1) // 2
        self.perfects = self.goods = self.misses = 0
        self.perfect_streak = 0
        self.elapsed = 0.0
        self.par = rank_mod.par_time(cast_distance, self.stamina_max, fish.get("power", 1.0))
        self.events: list[str] = []
        self.lose_reason: str | None = None
        self.result: dict | None = None
        self.last_jump_miss_t = -99.0
        self.pre_judged = False
        self.reeling = False
        self.rod_aim = 0.0
        self.align = 0.0
        self.reel_speed_now = 0.0
        self.payout_now = 0.0
        self.drag_limit = 0.0
        self.creak_t = 0.0
        self.dip_t = 0.0
        self.last_judge = ""
        self.last_judge_kind = ""   # "dip"(우클릭) / "swipe"(슬라이드)
        self.last_flick_dir = 0
        # 방향 전환 꺾기: {"need": 필요한 방향, "done": 판정 끝}
        self.turn_flick: dict | None = None
        # 상자 아이템 (Phase E)
        self.snag_mult = 1.0          # 잔잔한 물 부적: 0.5
        self.consumable_used = None   # 이번 파이팅에 쓴 소모품 (파이팅당 1개)
        self.auto_drag_prev: int | None = None  # 고대 어부의 릴: 돌진 전에 쓰던 드랙
        # 엘드라시온 환경 기믹
        from src.fishing.gimmick import Gimmicks
        self.gim = Gimmicks(gimmick)
        if "dark" in self.gim.kinds(self.brain):
            self.brain.dark = True  # 수정 동굴: 그림자 대신 천장 반사광
        # 특수 찌: 모자라면 뜰채 직전에 마지막 발악 (엘드라시온)
        self.float_need = float_need
        self.float_tier = float_tier
        self.escape_t: float | None = None
        fcfg = load_json("floats.json")
        self.escape_frac = fcfg["escape_distance_frac"]
        if float_need and float_tier > float_need:
            k = 1 + fcfg["bonus_tired_per_tier"] * (float_tier - float_need)  # 초과 티어당 지침 +5%
            self.brain.tired_range = [v * k for v in self.brain.tired_range]
        self.turn_mult = 1.0
        # 환경 위협 (수초·바위): 구역 안에 있으면 줄 걸림 게이지 증가
        self.hazards = hazards or []
        self.snag = 0.0
        self.in_hazard: dict | None = None
        self.hazard_mult = fish.get("hazard_mult", 1.0)
        # 뜰채
        self.net_t = 0.0
        self.net_period = 1.0

    # ── 조회 ──
    @property
    def drag_frac(self) -> float:
        return (self.drag - 1) / max(1, self.drag_steps - 1)

    @property
    def stamina_frac(self) -> float:
        return clamp(self.stamina / self.stamina_max, 0, 1)

    @property
    def line_frac(self) -> float:
        return clamp(self.line / self.line_max, 0, 1)

    def zone(self) -> str:
        if self.tension > self.green_high:
            return "red"
        if self.tension < self.green_low:
            return "slack"
        return "green"

    def fish_side(self) -> float:
        """물고기의 화면 좌우 위치 -1~1."""
        return clamp((self.angle - self.yaw) / 0.45, -1, 1)

    def _hazard_at(self) -> dict | None:
        for hz in self.hazards:
            if hz["angle"][0] <= self.angle <= hz["angle"][1] and hz["dist"][0] <= self.distance <= hz["dist"][1]:
                return hz
        return None

    def _cover_dir(self) -> int:
        """가장 가까운 위협 구역 쪽 (-1 왼쪽 / 1 오른쪽 / 0 없음)."""
        best, best_d = 0, 9.0
        for hz in self.hazards:
            center = (hz["angle"][0] + hz["angle"][1]) / 2
            d = abs(center - self.angle)
            if d < best_d and hz["dist"][0] - 3 <= self.distance <= hz["dist"][1] + 3:
                best, best_d = (1 if center > self.angle else -1), d
        return best

    def fish_xz(self) -> tuple[float, float]:
        return math.sin(self.angle) * self.distance, math.cos(self.angle) * self.distance

    # ── 입력 ──
    def change_drag(self, delta: int) -> None:
        self.drag = int(clamp(self.drag + delta, 1, self.drag_steps))
        if self.auto_drag_prev is not None:
            # 자동 하강 중에 직접 바꾸면, 끝난 뒤엔 바꾼 값에서 1단계 위로 돌아온다
            self.auto_drag_prev = int(clamp(self.drag + 1, 1, self.drag_steps))

    def dip(self) -> None:
        """우클릭: 낚싯대 숙이기. 점프 정점이면 퍼펙트."""
        self.dip_t = 0.35
        if self.phase != "fight":
            return
        b = self.brain
        cfg = self.cfg
        self.last_judge_kind = "dip"
        if b.state == "jump" and b.jump_kind == "dip" and not b.jump_judged:
            b.jump_judged = True
            off = b.time_to_apex()  # + 면 이름, - 면 늦음
            if abs(off) <= cfg["perfect_window_sec"]:
                self._perfect()
            elif abs(off) <= cfg["good_window_sec"]:
                self._good()
            else:
                self._miss("miss_early" if off > 0 else "miss_late")
        elif b.state == "telegraph" and b.pending == "jump" and not self.pre_judged:
            self.pre_judged = True
            self._miss("miss_early")

    @property
    def net_pause(self) -> float:
        """멈춤 길이 = 판정 창 전체 (보이는 '멈춘 순간'과 판정이 정확히 일치하도록)."""
        return self.gear["net_window_sec"] * 2 + self.cfg["net_pause_grace_sec"]

    def flick(self, direction: int) -> None:
        """마우스를 좌우로 확 슬라이드. 방향 전환 꺾기 / 몸털기 점프 받아치기."""
        if self.phase != "fight" or direction == 0:
            return
        b = self.brain
        fc = self.fcfg
        self.last_flick_dir = direction
        # 1) 몸털기 점프: 정점에서 물고기가 몸을 던지는 반대쪽으로
        if b.state == "jump" and b.jump_kind == "swipe" and not b.jump_judged:
            if direction != -b.leap_dir:
                return  # 엉뚱한 쪽은 무시 (흔들다 실수로 판정되지 않게)
            b.jump_judged = True
            self.last_judge_kind = "swipe"
            off = b.time_to_apex()
            if abs(off) <= self.cfg["perfect_window_sec"]:
                self._perfect()
            elif abs(off) <= self.cfg["good_window_sec"]:
                self._good()
            else:
                self._miss("miss_early" if off > 0 else "miss_late")
            return
        # 2) 방향 전환 꺾기: 전환하는 순간 반대쪽으로
        tf = self.turn_flick
        off = b.turn_offset()
        if tf and not tf["done"] and off is not None and off >= -fc["turn_before_sec"] and direction == tf["need"]:
            tf["done"] = True
            perfect = abs(off) <= fc["turn_perfect_sec"]
            self.turn_mult = fc["turn_ok_lateral"]
            self.tension = max(0.0, self.tension - fc["turn_ok_tension_relief"])
            self.stamina -= fc["turn_perfect_stamina"] if perfect else fc["turn_ok_stamina"]
            if perfect:
                self.brain.lose_burst(0.1)
                self.perfects += 1
                self.perfect_streak += 1
            self.events.append("flick_perfect" if perfect else "flick_good")

    def _update_turn_flick(self) -> None:
        """꺾기 창을 놓치면 물고기가 확 끌고 간다."""
        b = self.brain
        tf = self.turn_flick
        off = b.turn_offset()
        if off is None:
            if not (b.state == "telegraph" and b.pending == "turn"):
                self.turn_mult = 1.0
            return
        if tf is None or tf.get("turn_id") != b.turn_count:
            self.turn_flick = tf = {"need": -b.turn_dir, "done": False, "turn_id": b.turn_count}
            self.turn_mult = 1.0
        if not tf["done"] and off > self.fcfg["turn_after_sec"]:
            tf["done"] = True
            fc = self.fcfg
            self.turn_mult = fc["turn_fail_lateral"]
            self.tension += fc["turn_fail_tension"]
            self.hook += fc["turn_fail_hook"]
            self._fail_floor()
            self.misses += 1
            self.perfect_streak = 0
            self.last_judge = "flick_miss"
            self.events.append("flick_miss")

    def net_click(self) -> None:
        if self.phase != "net":
            return
        cycle = self.net_period + self.net_pause
        t_in = self.net_t % cycle
        if t_in >= self.net_period:
            self._caught()
        else:
            self._net_fail()

    # ── 판정 ──
    def use_consumable(self, item_id: str) -> bool:
        """파이팅 중 소모품 (파이팅당 1개). 수리용 실타래 / 잔잔한 물 부적."""
        if self.consumable_used or self.phase != "fight":
            return False
        if item_id == "repair_spool":
            self.line = min(float(self.line_max), self.line + self.line_max * 0.2)
        elif item_id == "calm_charm":
            self.snag_mult = 0.5
        else:
            return False
        self.consumable_used = item_id
        self.events.append(f"used:{item_id}")
        return True

    def _auto_drag(self) -> None:
        """고대 어부의 릴: 돌진 예고 때 드랙 1단계 자동 하강, 돌진이 끝나면 복귀."""
        b = self.brain
        rushing = b.state == "rush" or (b.state == "telegraph" and b.pending == "rush")
        if rushing and self.auto_drag_prev is None:
            self.auto_drag_prev = self.drag
            self.drag = max(1, self.drag - 1)
        elif not rushing and self.auto_drag_prev is not None:
            self.drag = self.auto_drag_prev
            self.auto_drag_prev = None

    def _perfect(self) -> None:
        heal = self.gear.get("perfect_heal", 0.0)
        if heal:
            self.line = min(float(self.line_max), self.line + self.line_max * heal)  # 용린 낚싯대
            self.events.append("scale_heal")
        self.perfects += 1
        self.perfect_streak += 1
        self.stamina -= self.cfg["perfect_stamina"]
        self.brain.lose_burst(self.cfg["perfect_burst"])
        self.last_judge = "perfect"
        self.events.append("perfect")

    def _good(self) -> None:
        self.goods += 1
        self.perfect_streak = 0
        self.stamina -= self.cfg["good_stamina"]
        self.last_judge = "good"
        self.events.append("good")

    def _fail_floor(self) -> None:
        """신호 대응 실패: 바늘 게이지 바닥이 1/3씩 올라가 다시 내려오지 않는다."""
        self.hook_floor = min(100.0, self.hook_floor + self.cfg["fail_hook_floor"])
        self.hook = max(self.hook, self.hook_floor)

    def _miss(self, kind: str) -> None:
        self.misses += 1
        self.perfect_streak = 0
        self.tension += self.cfg["miss_tension_spike"]
        self.hook += self.cfg["miss_hook"]
        self._fail_floor()
        self.last_jump_miss_t = self.elapsed
        self.last_judge = kind
        self.events.append(kind)

    # ── 틱 ──
    def update(self, dt: float, reeling: bool, rod_aim: float) -> None:
        self.dip_t = max(0.0, self.dip_t - dt)
        if self.escape_t is not None and self.phase == "fight":
            self._update_escape(dt)
            return
        if self.phase == "fight":
            if self.gear.get("auto_drag"):
                self._auto_drag()
            self._update_fight(dt, reeling, rod_aim)
        elif self.phase == "net":
            self._update_net(dt)

    def _update_fight(self, dt: float, reeling: bool, rod_aim: float) -> None:
        cfg = self.cfg
        b = self.brain
        self.elapsed += dt
        if self.gim.reel_lock_t > 0:
            reeling = False  # 갈대에 엉켜 감을 수 없다
        self.reeling = reeling
        self.rod_aim = rod_aim

        b.cover_dir = self._cover_dir()
        b.cover_from_gimmick = False
        if b.cover_dir == 0 and b.gimmick_bias > 0 and self.gim.kinds(b) & {"tangle", "ice", "current"}:
            b.cover_dir = 1 if self.angle - self.yaw >= 0 else -1  # 기믹 쪽(바깥)으로 끌고 간다
            b.cover_from_gimmick = True
        b.update(dt, self.stamina <= 0, self.stamina_frac)
        for ev in b.events:
            if ev == "action:jump" and self.pre_judged:
                b.jump_judged = True
                self.pre_judged = False
            if ev == "jump_land" and not b.jump_judged:
                self._miss("miss_none")
            self.events.append(ev)
        b.events.clear()

        self._update_turn_flick()

        # 낚싯대 방향: 물고기(또는 방향 전환 쪽) 반대로 버티면 이득
        if (b.state == "turn") or (b.state == "telegraph" and b.pending == "turn"):
            side = float(b.turn_dir)
        else:
            side = self.fish_side()
        self.align = rod_aim * side  # + 같은 쪽(나쁨), - 반대쪽(좋음)
        dir_mult = 1 + cfg["rod_align_tension"] * self.align

        # 목표 장력
        drag_frac = self.drag_frac
        pull = b.pull * self.fish.get("power", 1.0) * cfg["fish_pull_scale"] * dir_mult
        calm = not b.is_active
        reel_t = 0.0
        if reeling:
            reel_t = cfg["reel_tension_min"] + cfg["reel_tension_per_drag"] * drag_frac
            if calm:
                reel_t *= cfg["reel_tension_mult_when_calm"]
        target = cfg["base_line_tension"] + pull + reel_t
        self.drag_limit = lerp(cfg["drag_limit_min"], cfg["drag_limit_max"], drag_frac) + \
            max(0.0, self.fish.get("power", 1.0) - 1.0) * cfg["drag_floor_per_power"]  # 힘센 물고기는 드랙을 풀어도 무겁다
        payout = 0.0
        if target > self.drag_limit:
            over = target - self.drag_limit
            payout = min(cfg["payout_max_speed"], over * cfg["payout_speed_per_tension"])
            target = self.drag_limit + over * cfg["drag_overflow_keep"]
        if reeling and calm:
            # 지친 물고기를 감는 중엔 물고기 무게만큼 줄이 당겨짐 → 장력은 초록 구간 안에 유지
            # (드랙 풀림 계산 뒤에 적용: 저항이 없으니 줄은 풀리지 않는다)
            floor = self.green_low + cfg["calm_reel_floor"] + cfg["calm_reel_floor_per_drag"] * drag_frac
            target = max(target, floor)
        if b.is_active:
            target += math.sin(self.elapsed * 13.0) * 2.5 + math.sin(self.elapsed * 5.3) * 2.0
            if b.state not in ("rush", "jump"):  # 돌진·점프는 따로 대응(드랙·숙이기)이 있으니 겹치지 않게
                target += self.heave_amp * math.sin(self.elapsed * cfg["heave_speed"] + self.heave_phase)
        target += self.gim.tension_offset(self)  # 부유섬 물살
        self.target = target
        k = 1 - math.exp(-dt / cfg["tension_response_sec"])
        self.tension = clamp(self.tension + (target - self.tension) * k, 0, 110)

        # 거리
        if reeling:
            mult = cfg["reel_mult"]["exhausted"] if b.state == "exhausted" else \
                cfg["reel_mult"]["calm"] if b.is_calm else \
                1.0 if b.state == "recover" else cfg["reel_mult"]["active"]
            reel_in = self.gear["reel_speed"] * (cfg["reel_speed_drag_min"] + cfg["reel_speed_drag_add"] * drag_frac) * mult
        else:
            reel_in = 0.0
        self.reel_speed_now = reel_in
        self.payout_now = payout
        self.distance = max(0.0, self.distance + (payout - reel_in) * dt)

        # 좌우 이동
        if b.state == "turn":
            lateral = b.turn_dir * b.turn_speed * self.turn_mult
            if self.align < 0:
                lateral *= 1 - cfg["rod_align_lateral"] * (-self.align)
            self.angle += lateral * dt
        elif b.state == "rush" and b.cover_dir and b.cover_bias > 0:
            # 숨을 곳이 있는 물고기는 돌진도 그쪽으로 휜다
            lateral = b.cover_dir * b.turn_speed * b.cfg["cover_rush_lateral"] * b.cover_bias
            if self.align < 0:
                lateral *= 1 - cfg["rod_align_lateral"] * (-self.align)
            self.angle += lateral * dt
        else:
            self.angle += math.sin(self.elapsed * 0.7) * 0.02 * dt
        if self.align < 0:
            rel = self.angle - self.yaw
            self.angle -= math.copysign(1, rel) * cfg["center_pull_when_opposed"] * (-self.align) * dt * min(1, abs(rel) * 10)
        m = cfg["max_fish_angle"]
        self.angle = clamp(self.angle, self.yaw - m, self.yaw + m)

        # 줄 내구도 (빨간 구간에서 서서히)
        if self.tension > self.green_high:
            dmg = (self.tension - self.green_high) * cfg["line_damage_per_tension"] * dt
            if self.tension >= 100:
                dmg *= cfg["line_damage_over100_mult"]
            dmg *= self.gear.get("line_red_mult", 1.0)  # 온기 장갑
            self.line -= dmg
            self.line_damage += dmg
            if self.line_frac < 0.5:
                self.creak_t -= dt
                if self.creak_t <= 0:
                    self.creak_t = random.uniform(1.4, 2.2)  # 일정 간격 반복은 귀가 아프다
                    self.events.append("creak")

        self.gim.update(self, dt)  # 엉킴·열·얼음

        # 바늘 빠짐 (느슨 구간에서 증가)
        if self.tension < self.green_low:
            rate = cfg["hook_slack_rate"] + (self.green_low - self.tension) * cfg["hook_slack_extra_per_tension"]
            if calm:
                rate *= cfg["hook_slack_mult_calm"]  # 몸부림이 없으니 바늘이 덜 빠짐
            # 힘이 약한 물고기는 바늘을 덜 턴다
            rate *= clamp(self.fish.get("power", 1.0), cfg["hook_slack_power_min"], 1.0)
            self.hook += rate * dt
        else:
            self.hook -= cfg["hook_recover_rate"] * dt
        self.hook = clamp(self.hook, self.hook_floor, 100)

        # 줄 걸림 (환경 위협)
        hz = self._hazard_at()
        if hz is not None and self.in_hazard is None:
            self.events.append("hazard_enter")
        self.in_hazard = hz
        if hz is not None:
            self.snag += cfg["snag_rate"] * self.hazard_mult * self.snag_mult * dt
        else:
            self.snag -= cfg["snag_recover"] * dt
        self.snag = clamp(self.snag, 0, 100)

        # 스태미나
        drain = 0.0
        if b.is_active:
            drain += cfg["stamina_drain_active"] + self.tension / 100 * cfg["stamina_drain_per_tension"]
        elif reeling and b.is_calm:
            drain += cfg["stamina_drain_reel_calm"]
        self.stamina = max(0.0, self.stamina - drain * dt)

        # 종료 판정
        if self.line <= 0:
            self._lose("snap")
        elif self.snag >= 100:
            self._lose("snag")
        elif self.hook >= 100:
            if self.hook_floor >= 99.9:
                self._lose("worn")  # 실수 세 번
            else:
                self._lose("jump" if self.elapsed - self.last_jump_miss_t < 1.5 else "slack")
        elif self._escape_ready():
            self.escape_t = 0.0
            self.events.append("escape_start")  # 눈이 번쩍 + 물보라 폭발
        elif self.distance <= cfg["net_distance"] and b.state not in ("jump", "telegraph"):
            need = cfg["net_min_stamina_legend"] if self.fish["rarity"] == "legend" else cfg["net_min_stamina"]
            if self.stamina_frac > need and b.state not in ("rush",):
                # 아직 힘이 남았으면 뜰채 앞에서 다시 도망친다 (예고 후 돌진)
                b.chain_left = 0
                b._begin_telegraph("rush")
                self.events.append("bolt")
            elif self.stamina_frac <= need:
                self._start_net()

    # ── 특수 찌 부족: 마지막 발악 ──
    def _escape_ready(self) -> bool:
        if not self.float_need or self.float_tier >= self.float_need:
            return False
        cfg = self.cfg
        need = cfg["net_min_stamina_legend"] if self.fish["rarity"] == "legend" else cfg["net_min_stamina"]
        near = max(cfg["net_distance"] + 1.5, self.cast_distance * self.escape_frac)
        return self.distance <= near and self.stamina_frac <= need and self.brain.state not in ("jump",)

    def _update_escape(self, dt: float) -> None:
        """0.7초 몸부림 → '투둑' (줄 끊김) → 깊은 곳으로 사라짐 → 실패."""
        prev = self.escape_t
        self.escape_t += dt
        self.elapsed += dt
        if prev < 0.7 <= self.escape_t:
            self.events.append("escape_snap")
        if self.escape_t >= 0.7:
            self.distance += 9.0 * dt  # 깊은 곳으로
            self.tension = max(0.0, self.tension - 120 * dt)
        if self.escape_t >= 2.0:
            self._lose("escape")

    # ── 뜰채 ──
    def _start_net(self) -> None:
        cfg = self.cfg
        self.phase = "net"
        self.net_t = 0.0
        self.net_period = lerp(cfg["net_period_tired"], cfg["net_period_fresh"], self.stamina_frac)
        self.tension = 50.0
        self.events.append("net_start")

    def net_pose(self) -> tuple[float, bool]:
        """(-1~1 좌우 몸부림, 멈춤 여부)."""
        cycle = self.net_period + self.net_pause
        t_in = self.net_t % cycle
        if t_in >= self.net_period:
            return 0.0, True
        k = t_in / self.net_period
        return math.sin(k * math.tau * 2), False

    def _update_net(self, dt: float) -> None:
        self.elapsed += dt
        self.net_t += dt
        cycle = self.net_period + self.net_pause
        if self.net_t >= cycle * self.cfg["net_max_cycles"]:
            self._net_fail()

    def _net_fail(self) -> None:
        cfg = self.cfg
        self.phase = "fight"
        self.distance = cfg["net_distance"] + self.gear["net_fail_distance"]
        self.stamina = min(self.stamina_max, self.stamina + cfg["net_fail_stamina_recover"])
        if self.brain.state == "exhausted" and self.stamina > 0:
            self.brain.state = "idle"
        self.brain.recover_from_net_fail()
        self.events.append("net_fail")

    def _caught(self) -> None:
        self.phase = "caught"
        damage = clamp(self.line_damage / self.line_max, 0, 1)
        score = rank_mod.compute_score(self.perfects, self.misses, damage, self.elapsed, self.par)
        size = rank_mod.final_size(self.size_cm, score["rank"])
        self.result = {
            "fish": self.fish, "size": size, "rank": score["rank"], "score": score,
            "price": rank_mod.sell_price(self.fish, size, score["rank"]),
            "perfects": self.perfects, "misses": self.misses, "line_damage": damage,
            "elapsed": self.elapsed, "par": self.par,
        }
        self.events.append("caught")

    def _lose(self, reason: str) -> None:
        self.phase = "lost"
        self.lose_reason = reason
        self.events.append("lost:" + reason)
