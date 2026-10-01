"""캐스팅 상태머신 (로직만, 그리기 없음).

READY → CHARGING(좌클릭 유지) → SWING(뒤로 젖혔다 앞으로) → FLIGHT(포물선) → LANDED
LANDED → RETRIEVE(우클릭) → READY
"""
import math
from enum import Enum, auto

from src.core.config import load_json
from src.core.mathutil import clamp, lerp, smoothstep


class CastState(Enum):
    READY = auto()
    CHARGING = auto()
    SWING = auto()
    FLIGHT = auto()
    LANDED = auto()
    RETRIEVE = auto()


BACK_SWING_DEG = 62
FORWARD_OVERSHOOT_DEG = -22


class CastController:
    def __init__(self):
        self.cfg = load_json("fishing_config.json")["cast"]
        self.state = CastState.READY
        self.power = 0.0          # 0~1
        self.charge_t = 0.0
        self.state_t = 0.0        # 현재 상태 경과 시간
        self.aim = 0.0            # -1~1
        self.cast_angle = 0.0     # 라디안 (월드 기준)
        self.cast_distance = 0.0
        self.flight_dur = 1.0
        self.apex = 3.0
        # 찌 월드 위치
        self.bx = self.bz = self.bh = 0.0
        self.flight_s = 0.0       # 비행 진행도 0~1
        # 연출용
        self.swing_deg = 0.0
        self.bend = 4.0
        self.reel_angle = 0.0
        self.reel_speed = 0.0
        self.events: list[str] = []

    # ── 입력 ──
    def press(self) -> None:
        if self.state == CastState.READY:
            self._enter(CastState.CHARGING)
            self.charge_t = 0.0
            self.power = 0.0

    def release(self, yaw: float) -> None:
        if self.state == CastState.CHARGING:
            self.cast_angle = yaw + self.aim * math.radians(self.cfg["max_aim_deg"])
            self.cast_distance = self.distance_for_power(self.power)
            self._enter(CastState.SWING)

    def cancel_or_retrieve(self) -> None:
        if self.state == CastState.CHARGING:
            self._enter(CastState.READY)
            self.power = 0.0
        elif self.state == CastState.LANDED:
            self._enter(CastState.RETRIEVE)

    # ── 계산 ──
    def distance_for_power(self, power: float) -> float:
        return lerp(self.cfg["min_distance"], self.cfg["max_distance"], power)

    def current_distance(self) -> float:
        return math.hypot(self.bx, self.bz)

    def aim_angle(self, yaw: float) -> float:
        return yaw + self.aim * math.radians(self.cfg["max_aim_deg"])

    def rod_hand_offset(self) -> tuple[float, float]:
        k = max(0.0, self.swing_deg) / BACK_SWING_DEG
        return 7 * k, -9 * k

    def _enter(self, state: CastState) -> None:
        self.state = state
        self.state_t = 0.0

    # ── 틱 ──
    def update(self, dt: float, aim: float) -> None:
        self.state_t += dt
        cfg = self.cfg
        if self.state not in (CastState.SWING, CastState.FLIGHT):
            self.aim = aim
        reel_target = 0.0

        if self.state == CastState.READY:
            self.swing_deg = lerp(self.swing_deg, 0.0, 0.15)
            self.bend = lerp(self.bend, 3.0, 0.1)

        elif self.state == CastState.CHARGING:
            # 파워 0→1→0 왕복 (DESIGN.md 1장)
            self.charge_t += dt
            phase = (self.charge_t / cfg["charge_period_sec"]) % 1.0
            self.power = 1.0 - abs(1.0 - 2.0 * phase)
            self.swing_deg = lerp(self.swing_deg, 8 + 10 * self.power, 0.2)
            self.bend = lerp(self.bend, 3.0, 0.1)

        elif self.state == CastState.SWING:
            back, fwd = cfg["back_swing_sec"], cfg["forward_swing_sec"]
            if self.state_t < back:
                self.swing_deg = lerp(18, BACK_SWING_DEG, smoothstep(self.state_t / back))
                self.bend = lerp(3, -6, self.state_t / back)  # 뒤로 젖힐 때 반대로 휨
            else:
                s = smoothstep((self.state_t - back) / fwd)
                self.swing_deg = lerp(BACK_SWING_DEG, FORWARD_OVERSHOOT_DEG, s)
                self.bend = lerp(-6, 14, s)  # 앞으로 채찍처럼
            if self.state_t >= back + fwd:
                self._launch()

        elif self.state == CastState.FLIGHT:
            self.flight_s = clamp(self.state_t / self.flight_dur, 0.0, 1.0)
            d = lerp(1.5, self.cast_distance, self.flight_s)
            self.bx = math.sin(self.cast_angle) * d
            self.bz = math.cos(self.cast_angle) * d
            self.bh = 0.8 + 4 * self.apex * self.flight_s * (1 - self.flight_s) - 0.8 * self.flight_s
            self.swing_deg = lerp(self.swing_deg, 0.0, 0.08)
            self.bend = lerp(self.bend, 2.0, 0.08)
            reel_target = 30.0  # 줄 풀리며 릴 회전
            if self.flight_s >= 1.0:
                self.bh = 0.0
                self._enter(CastState.LANDED)
                self.events.append("splash")

        elif self.state == CastState.LANDED:
            self.swing_deg = lerp(self.swing_deg, -4.0, 0.05)
            self.bend = lerp(self.bend, 6.0, 0.05)

        elif self.state == CastState.RETRIEVE:
            d = self.current_distance() - cfg["retrieve_speed"] * dt
            self.bx = math.sin(self.cast_angle) * d
            self.bz = math.cos(self.cast_angle) * d
            self.bend = lerp(self.bend, 10.0, 0.1)
            reel_target = -22.0
            if d <= cfg["retrieve_done_distance"]:
                self._enter(CastState.READY)
                self.events.append("retrieved")

        self.reel_speed = lerp(self.reel_speed, reel_target, 0.2)
        self.reel_angle = (self.reel_angle + self.reel_speed * dt) % math.tau

    def _launch(self) -> None:
        cfg = self.cfg
        self.flight_dur = cfg["flight_sec_min"] + cfg["flight_sec_per_power"] * self.power
        self.apex = cfg["apex_min"] + cfg["apex_per_power"] * self.power
        self.flight_s = 0.0
        self._enter(CastState.FLIGHT)
        self.events.append("launch")
