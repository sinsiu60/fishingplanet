"""물고기 패턴 상태머신 = 보스 AI. 종마다 fish.json 값으로 성격이 달라진다.

격렬 사이클:  idle ⇄ (telegraph → 행동) 반복, 행동마다 burst 소모
burst가 바닥나면: tired(지침, 빈틈) → recover(회복) → 다시 격렬
stamina가 0이면: exhausted (끝까지 저항 거의 없음)

모든 행동 앞에는 예고(telegraph)가 있다. (DESIGN.md 0장 공정함 규칙 1)
  rush  ← 꼬리 물보라
  jump  ← 그림자 커짐 + 기포
  turn  ← 줄 쏠림
  charge(힘 모으기)는 "멈춤" 자체가 신호이며, 끝나면 예고 후 돌진한다.

종별 특성 (fish.json):
  jump_chain [min,max]  연속 점프 (다음 점프 예고는 짧게, 최소 0.35초)
  turn_chain [min,max]  연속 방향 전환 (좌우 번갈아)
  combo {행동: [다음 행동, 확률]}  행동 직후 짧은 예고로 이어지는 콤보
  cover_bias 0~1        방향 전환·돌진을 수초/바위 쪽으로 할 확률
  charge_rush_mult      힘 모으기 뒤 돌진의 힘 배율
  fake_tired 0~1        지칠 때 '가짜 지침'일 확률 (단서: 기포가 계속 올라옴)
  ink 0~1               돌진 후 먹물을 뿜을 확률 (그림자 신호를 가림)
"""
import random

from src.core.config import load_json

ACTIVE_STATES = ("idle", "telegraph", "rush", "jump", "turn", "fake_tired")
CALM_STATES = ("charge", "tired", "exhausted")
STATE_NAMES = {
    "idle": "격렬", "telegraph": "격렬", "rush": "돌진!", "jump": "점프!", "turn": "방향 전환",
    "charge": "멈춤", "tired": "지침", "fake_tired": "지침", "recover": "회복 중", "exhausted": "완전 지침",
}


class FishBrain:
    def __init__(self, fish: dict, rnd: random.Random | None = None):
        self.fish = fish
        self.cfg = load_json("fishing_config.json")["fish_ai"]
        self.rnd = rnd or random.Random()
        cfg = self.cfg
        self.telegraph_sec = fish.get("telegraph_sec", 1.0)
        self.actions = fish.get("actions", {"rush": 1})
        self.tired_range = fish.get("tired_sec", cfg["tired_sec"])
        self.rush_sec = fish.get("rush_sec", cfg["rush_sec"])
        self.turn_sec = fish.get("turn_sec", cfg["turn_sec"])
        self.turn_speed = fish.get("turn_speed", cfg["turn_speed"])
        self.charge_range = fish.get("charge_sec", cfg["charge_sec"])
        self.jump_chain = fish.get("jump_chain", [1, 1])
        self.turn_chain = fish.get("turn_chain", [1, 1])
        self.combo = fish.get("combo", {})
        self.cover_bias = fish.get("cover_bias", 0.0)
        self.charge_rush_mult = fish.get("charge_rush_mult", 1.0)
        self.fake_tired_p = fish.get("fake_tired", 0.0)
        self.ink_p = fish.get("ink", 0.0)
        self.state = "idle"
        self.pending: str | None = None   # telegraph 중일 때 다음 행동
        self.cur_telegraph = self.telegraph_sec
        self.timer = self._rand(cfg["idle_sec"])
        self.state_t = 0.0
        self.burst = 1.0
        self.turn_dir = 1
        self.cover_dir = 0          # Fight가 매 틱 알려줌: 가장 가까운 위협 구역 방향 (-1/0/1)
        self.chain_left = 0
        self.chain_action: str | None = None
        self.rush_after_charge = False
        self.jump_judged = False
        self.events: list[str] = []

    def _rand(self, pair) -> float:
        return self.rnd.uniform(pair[0], pair[1])

    # ── 조회 ──
    @property
    def pull(self) -> float:
        p = self.cfg["pull"][self.state]
        if self.state == "rush" and self.rush_after_charge:
            p *= self.charge_rush_mult
        return p

    @property
    def is_calm(self) -> bool:
        """크게 감을 수 있는 빈틈 상태."""
        return self.state in CALM_STATES

    @property
    def is_active(self) -> bool:
        return self.state in ACTIVE_STATES

    @property
    def signal(self) -> str | None:
        """현재 보여줄 예고 신호 종류."""
        return self.pending if self.state == "telegraph" else None

    def signal_progress(self) -> float:
        if self.state != "telegraph":
            return 0.0
        return min(1.0, self.state_t / self.cur_telegraph)

    @property
    def jump_air(self) -> float:
        return self.cfg["jump_air_sec"]

    def jump_phase(self) -> float:
        """점프 진행도 0~1 (0.5 = 정점)."""
        if self.state != "jump":
            return 0.0
        return min(1.0, self.state_t / self.jump_air)

    def time_to_apex(self) -> float:
        """점프 정점까지 남은 시간 (음수면 지남). 점프 예고 중이면 예고 남은 시간 포함."""
        if self.state == "jump":
            return self.jump_air / 2 - self.state_t
        if self.state == "telegraph" and self.pending == "jump":
            return (self.cur_telegraph - self.state_t) + self.jump_air / 2
        return 999.0

    def display_name(self) -> str:
        return STATE_NAMES[self.state]

    # ── 외부 개입 ──
    def lose_burst(self, amount: float) -> None:
        self.burst -= amount

    def recover_from_net_fail(self) -> None:
        self.burst = max(self.burst, 0.6)
        self.chain_left = 0
        self._begin_telegraph("rush")

    # ── 상태 전환 ──
    def _enter(self, state: str, duration: float) -> None:
        self.state = state
        self.timer = duration
        self.state_t = 0.0

    def _short_telegraph(self) -> float:
        return max(self.cfg["min_telegraph_sec"], self.telegraph_sec * self.cfg["chain_telegraph_mult"])

    def _begin_telegraph(self, action: str, duration: float | None = None, turn_dir: int | None = None) -> None:
        self.pending = action
        if action == "turn":
            if turn_dir is not None:
                self.turn_dir = turn_dir
            elif self.cover_dir and self.rnd.random() < self.cover_bias:
                self.turn_dir = self.cover_dir
            else:
                self.turn_dir = self.rnd.choice((-1, 1))
        self.cur_telegraph = duration if duration is not None else self.telegraph_sec
        self._enter("telegraph", self.cur_telegraph)
        self.events.append(f"telegraph:{action}")

    def _choose_action(self) -> str:
        names = list(self.actions)
        return self.rnd.choices(names, [self.actions[n] for n in names])[0]

    def _start_action(self, action: str) -> None:
        cfg = self.cfg
        # 연속 동작(체인) 중엔 burst를 덜 쓴다
        cost = cfg["burst_cost"].get(action, 0.2)
        self.burst -= cost * (0.5 if self.chain_action == action else 1.0)
        self.pending = None
        if action == "rush":
            self._enter("rush", self.rush_sec)
        elif action == "jump":
            self.jump_judged = False
            self._enter("jump", cfg["jump_air_sec"])
        elif action == "turn":
            self._enter("turn", self.turn_sec)
        elif action == "charge":
            self._enter("charge", self._rand(self.charge_range))
        self.events.append(f"action:{action}")

    def _begin_action_sequence(self, action: str) -> None:
        """새 행동 시작: 체인 횟수 결정."""
        self.chain_action = None
        self.chain_left = 0
        if action == "jump":
            self.chain_left = self.rnd.randint(*self.jump_chain) - 1
        elif action == "turn":
            self.chain_left = self.rnd.randint(*self.turn_chain) - 1
        if self.chain_left > 0:
            self.chain_action = action
        if action == "charge":
            self._start_action("charge")  # 멈춤 자체가 신호
        else:
            self._begin_telegraph(action)

    def update(self, dt: float, stamina_empty: bool) -> None:
        self.state_t += dt
        self.timer -= dt
        if self.state == "exhausted":
            return
        if stamina_empty and self.state not in ("jump",):
            self._enter("exhausted", 999.0)
            self.events.append("exhausted")
            return
        if self.timer > 0:
            return

        cfg = self.cfg
        s = self.state
        if s == "telegraph":
            self._start_action(self.pending)
        elif s == "jump":
            self.events.append("jump_land")
            self._after_action("jump")
        elif s == "charge":
            # 힘을 모았다가 돌진 (예고 후)
            self._begin_telegraph("rush")
            self.rush_after_charge = True
            return
        elif s in ("rush", "turn"):
            if s == "rush" and self.ink_p and self.rnd.random() < self.ink_p:
                self.events.append("ink")
            self._after_action(s)
        elif s == "idle":
            if self.burst <= 0:
                if self.fake_tired_p and self.rnd.random() < self.fake_tired_p:
                    self._enter("fake_tired", self._rand(cfg["fake_tired_sec"]))
                    self.events.append("fake_tired")
                else:
                    self._enter("tired", self._rand(self.tired_range))
                    self.events.append("tired")
            else:
                self._begin_action_sequence(self._choose_action())
        elif s == "fake_tired":
            # 지친 척 끝 → 돌진 (예고는 정상 길이)
            self.burst = max(self.burst, 0.3)
            self._begin_telegraph("rush")
        elif s == "tired":
            self._enter("recover", cfg["recover_sec"])
            self.events.append("recover")
        elif s == "recover":
            self.burst = 1.0
            self._enter("idle", self._rand(cfg["idle_sec"]))
        if self.state != "rush":
            self.rush_after_charge = False

    def _after_action(self, action: str) -> None:
        # 연속 동작
        if self.chain_left > 0 and self.chain_action == action:
            self.chain_left -= 1
            if action == "turn":
                self._begin_telegraph("turn", self._short_telegraph(), turn_dir=-self.turn_dir)
            else:
                self._begin_telegraph(action, self._short_telegraph())
            return
        self.chain_action = None
        # 콤보
        nxt = self.combo.get(action)
        if nxt and self.burst > 0 and self.rnd.random() < nxt[1]:
            self._begin_telegraph(nxt[0], self._short_telegraph())
            return
        self._enter("idle", self._rand(self.cfg["idle_sec"]))
