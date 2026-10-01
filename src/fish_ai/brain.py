"""물고기 패턴 상태머신 = 보스 AI.

격렬 사이클:  idle ⇄ (telegraph → 행동) 반복, 행동마다 burst 소모
burst가 바닥나면: tired(지침, 빈틈) → recover(회복) → 다시 격렬
stamina가 0이면: exhausted (끝까지 저항 거의 없음)

모든 행동 앞에는 예고(telegraph)가 있다. (DESIGN.md 0장 공정함 규칙 1)
  rush  ← 꼬리 물보라
  jump  ← 그림자 커짐 + 기포
  turn  ← 줄 쏠림
  charge(힘 모으기)는 "멈춤" 자체가 신호이며, 끝나면 짧은 예고 후 돌진한다.
"""
import random

from src.core.config import load_json

ACTIVE_STATES = ("idle", "telegraph", "rush", "jump", "turn")
CALM_STATES = ("charge", "tired", "exhausted")
STATE_NAMES = {
    "idle": "격렬", "telegraph": "격렬", "rush": "돌진!", "jump": "점프!", "turn": "방향 전환",
    "charge": "멈춤", "tired": "지침", "recover": "회복 중", "exhausted": "완전 지침",
}


class FishBrain:
    def __init__(self, fish: dict, rnd: random.Random | None = None):
        self.fish = fish
        self.cfg = load_json("fishing_config.json")["fish_ai"]
        self.rnd = rnd or random.Random()
        self.telegraph_sec = fish.get("telegraph_sec", 1.0)
        self.actions = fish.get("actions", {"rush": 1})
        self.tired_range = fish.get("tired_sec", self.cfg["tired_sec"])
        self.state = "idle"
        self.pending: str | None = None   # telegraph 중일 때 다음 행동
        self.timer = self._rand(self.cfg["idle_sec"])
        self.state_t = 0.0
        self.burst = 1.0
        self.turn_dir = 1
        self.after_charge = False
        self.jump_judged = False
        self.events: list[str] = []

    def _rand(self, pair) -> float:
        return self.rnd.uniform(pair[0], pair[1])

    # ── 조회 ──
    @property
    def pull(self) -> float:
        return self.cfg["pull"][self.state]

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
        return min(1.0, self.state_t / self.telegraph_sec)

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
            return (self.telegraph_sec - self.state_t) + self.jump_air / 2
        return 999.0

    def display_name(self) -> str:
        return STATE_NAMES[self.state]

    # ── 외부 개입 ──
    def lose_burst(self, amount: float) -> None:
        self.burst -= amount

    def force_exhausted(self) -> None:
        if self.state not in ("jump",):
            self._enter("exhausted", 999.0)

    def recover_from_net_fail(self) -> None:
        self.burst = max(self.burst, 0.6)
        self._begin_telegraph("rush")

    # ── 상태 전환 ──
    def _enter(self, state: str, duration: float) -> None:
        self.state = state
        self.timer = duration
        self.state_t = 0.0

    def _begin_telegraph(self, action: str) -> None:
        self.pending = action
        if action == "turn":
            self.turn_dir = self.rnd.choice((-1, 1))
        self._enter("telegraph", self.telegraph_sec)
        self.events.append(f"telegraph:{action}")

    def _choose_action(self) -> str:
        names = list(self.actions)
        return self.rnd.choices(names, [self.actions[n] for n in names])[0]

    def _start_action(self, action: str) -> None:
        cfg = self.cfg
        self.burst -= cfg["burst_cost"].get(action, 0.2)
        self.pending = None
        if action == "rush":
            self._enter("rush", cfg["rush_sec"])
        elif action == "jump":
            self.jump_judged = False
            self._enter("jump", cfg["jump_air_sec"])
        elif action == "turn":
            self._enter("turn", cfg["turn_sec"])
        elif action == "charge":
            self._enter("charge", self._rand(cfg["charge_sec"]))
        self.events.append(f"action:{action}")

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
            self._after_action()
        elif s == "charge":
            # 힘을 모았다가 돌진 (짧은 예고 후)
            self._begin_telegraph("rush")
        elif s in ("rush", "turn"):
            self._after_action()
        elif s == "idle":
            if self.burst <= 0:
                self._enter("tired", self._rand(self.tired_range))
                self.events.append("tired")
            else:
                action = self._choose_action()
                if action == "charge":
                    self._start_action("charge")  # 멈춤 자체가 신호
                else:
                    self._begin_telegraph(action)
        elif s == "tired":
            self._enter("recover", cfg["recover_sec"])
            self.events.append("recover")
        elif s == "recover":
            self.burst = 1.0
            self._enter("idle", self._rand(cfg["idle_sec"]))

    def _after_action(self) -> None:
        self._enter("idle", self._rand(self.cfg["idle_sec"]))
