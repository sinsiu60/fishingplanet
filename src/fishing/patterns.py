"""신규 패턴 판정 (DESIGN.md 27-2, Phase U3). 수치는 data/patterns.json.

Fight가 패턴 하나를 들고 있다 (Judge). 흐름:
  물고기 예고(telegraph:<id>) → Judge 생성 (예고 중 입력도 받음: 낚싯대 미리 세우기·미리 연타)
  행동 시작(action:<id>)       → begin(): 판정 시작
  행동 끝(end:<id>)            → finish(): 성공/실패 효과, 이벤트 pattern_ok:<id> / pattern_fail:<id>
꼬임 게이지(줄 비틀기)는 행동이 끝나도 남으므로 Fight의 TwistGauge가 따로 들고 있다.

입력은 PatternInput 하나로 받는다 (낚시 씬은 gesture.Controls에서, 밸런스 봇은 직접 채움).
"""
from dataclasses import dataclass

from src.core.config import load_json
from src.core.mathutil import clamp

PATTERN_IDS = ("shake", "dive", "surface", "reverse", "twist")


def cfg() -> dict:
    return load_json("patterns.json")


@dataclass
class PatternInput:
    pitch: float = 0.0      # 낚싯대 상하 -1~1
    taps: int = 0           # 이번 틱 연타 수
    turns: int = 0          # 이번 틱 완성한 원 바퀴 수 (방향 무관)
    drag_min: bool = False  # 드랙 순간 최저 누름

    @classmethod
    def from_controls(cls, ctl) -> "PatternInput":
        ev = ctl.events
        return cls(ctl.pitch, ev.count("reel_tap"), sum(1 for e in ev if e.startswith("circle:")), ctl.drag_min)


TIP_SHORT = {"shake": "손 멈춤", "dive": "낚싯대 위로", "surface": "낚싯대 아래로", "reverse": "연타",
             "twist": "원 그리기", "chain": "순서대로 대응"}


def fish_patterns(fish: dict) -> list[str]:
    """이 물고기가 쓰는 신규 패턴 (기본 + 페이즈 + 콤보 순서 안), 정해진 순서로."""
    used = set(fish.get("actions", {}))
    for ph in fish.get("phases", []):
        used |= set(ph.get("actions", {}))
        used |= set(ph.get("chain_seq", []))
    used |= set(fish.get("chain_seq", []))
    return [p for p in PATTERN_IDS + ("chain",) if p in used]


class Judge:
    """패턴 하나의 판정. 하위 클래스가 _tick / _success / _fail 을 채운다."""
    need = 0.0  # 표시용: 필요한 유지율

    def __init__(self, pid: str, fight):
        self.id = pid
        self.c = cfg()[pid]
        self.active = False   # 예고 중엔 False
        self.t = 0.0          # 행동 경과
        self.dur = 1.0
        self.ok_t = 0.0       # 판정 구간 중 잘한 시간
        self.judged_t = 0.0   # 판정 구간 길이 (grace 이후)
        self.result: str | None = None  # "ok" / "fail" / "neutral"
        self.last_ok = False
        self.fight = fight

    def begin(self, dur: float) -> None:
        self.active = True
        self.dur = max(0.1, dur)

    @property
    def ratio(self) -> float:
        """지금까지 유지율 (판정 구간이 아직 없으면 1)."""
        return self.ok_t / self.judged_t if self.judged_t > 0 else 1.0

    def doing_ok(self, inp: PatternInput, reeling: bool, aim_rate: float) -> bool:
        return True

    def update(self, dt: float, inp: PatternInput, reeling: bool, aim_rate: float) -> None:
        self.pre(dt, inp)
        if not self.active:
            return
        self.t += dt
        ok = self.doing_ok(inp, reeling, aim_rate)
        self.last_ok = ok
        if self.t >= self.c.get("grace_sec", 0.0):
            self.judged_t += dt
            if ok:
                self.ok_t += dt
        self.during(dt, inp, ok)

    def pre(self, dt: float, inp: PatternInput) -> None:
        """예고 중에도 도는 부분 (역주행 게이지)."""

    def during(self, dt: float, inp: PatternInput, ok: bool) -> None:
        """행동 중 지속 효과."""

    def passed(self) -> bool:
        return self.ratio >= self.need

    def finish(self) -> str:
        f = self.fight
        if self.passed():
            self.result = "ok"
            self._success(f)
        else:
            self.result = "fail"
            self._fail(f)
        f.pattern_result(self.id, self.result)
        return self.result

    def _success(self, f) -> None:
        pass

    def _fail(self, f) -> None:
        pass

    # Fight가 묻는 것
    def tension_override(self, f) -> float | None:
        return None

    @property
    def hold_payout(self) -> bool:
        return False


class Shake(Judge):
    """① 머리 흔들기: 감기·방향 조작 멈춤."""

    def __init__(self, fight):
        super().__init__("shake", fight)
        self.need = 1 - self.c["fail_frac"]

    def doing_ok(self, inp, reeling, aim_rate):
        return not reeling and aim_rate <= self.c["aim_rate_max"]

    def _success(self, f):
        f.stamina -= self.c["ok_stamina"]
        f.brain.lose_burst(self.c["ok_burst"])

    def _fail(self, f):
        bad = self.judged_t - self.ok_t
        f.hook = min(100.0, f.hook + self.c["hook_per_sec"] * bad)


class Dive(Judge):
    """② 잠수: 낚싯대 위로 유지. 올리고 있는 동안 줄이 안 풀린다."""

    def __init__(self, fight):
        super().__init__("dive", fight)
        self.need = self.c["hold_need"]
        self.last_ok = False

    def doing_ok(self, inp, reeling, aim_rate):
        return inp.pitch >= self.c["pitch_need"]

    @property
    def hold_payout(self) -> bool:
        return self.active and self.last_ok

    def _success(self, f):
        f.stamina -= self.c["ok_stamina"]

    def _fail(self, f):
        f.line -= f.line_max * self.c["fail_line_frac"]
        f.line_damage += f.line_max * self.c["fail_line_frac"]
        f.distance += self.c["fail_distance"]


class Surface(Judge):
    """③ 수면 질주: 낚싯대 아래로 유지. 실패하면 곧바로 점프."""

    def __init__(self, fight):
        super().__init__("surface", fight)
        self.need = self.c["hold_need"]

    def doing_ok(self, inp, reeling, aim_rate):
        return inp.pitch <= -self.c["pitch_need"]

    def _success(self, f):
        f.distance = max(0.0, f.distance - self.c["ok_distance"])

    def _fail(self, f):
        f.brain.insert_jump(self.c["fail_jump_telegraph"])


class Reverse(Judge):
    """④ 역주행: 연타로 회수 게이지를 기준 이상 유지 (예고 중 연타도 쌓인다)."""

    def __init__(self, fight):
        super().__init__("reverse", fight)
        self.need = self.c["hold_need"]
        self.gauge = 0.0

    def pre(self, dt, inp):
        self.gauge = clamp(self.gauge + inp.taps * self.c["tap_gain"] - self.c["decay"] * dt, 0, 100)

    def doing_ok(self, inp, reeling, aim_rate):
        return self.gauge >= self.c["keep_level"]

    def tension_override(self, f):
        if not self.active:
            return None
        return f.green_low + self.c["slack_offset"] + self.gauge * self.c["gauge_tension"]

    def _success(self, f):
        f.distance = max(0.0, f.distance - self.c["ok_distance"])

    def _fail(self, f):
        f.tension = 0.0
        f.hook = min(100.0, f.hook + self.c["fail_hook"])


class Twist(Judge):
    """⑤ 줄 비틀기: 꼬임 게이지(TwistGauge)를 원 그리기로 풀기. 끝날 때 거의 풀려 있으면 성공."""

    def __init__(self, fight):
        super().__init__("twist", fight)
        self.snapped = False

    def during(self, dt, inp, ok):
        tg = self.fight.twist
        tg.value += self.c["rise"] * dt
        if tg.check_snap():
            self.snapped = True

    def passed(self) -> bool:
        return not self.snapped and self.fight.twist.value < self.c["ok_below"]

    @property
    def ratio(self) -> float:
        return clamp(1 - self.fight.twist.value / 100, 0, 1)

    def finish(self) -> str:
        if self.passed():
            self.result = "ok"
            self.fight.calm_heave_t = self.c["ok_calm_sec"]
        else:
            # 끊어질 뻔했으면 실패, 그냥 남아 있으면 무승부 (게이지는 천천히 풀림)
            self.result = "fail" if self.snapped or self.fight.twist.value >= self.c["fail_at"] else "neutral"
        self.fight.pattern_result(self.id, self.result)
        return self.result


class TwistGauge:
    """꼬임 게이지 0~100: 원 1바퀴 −per_turn, 행동이 끝난 뒤엔 초당 −decay. 100 → 줄 손상, snap_to로."""

    def __init__(self, fight):
        self.c = cfg()["twist"]
        self.fight = fight
        self.value = 0.0
        self.step = 0  # 진동 단계 (25/50/75 넘을 때마다)

    def update(self, dt: float, inp: PatternInput, twisting: bool) -> None:
        if inp.turns:
            self.value = max(0.0, self.value - self.c["per_turn"] * inp.turns)
            self.fight.events.append("twist_turn")
        if not twisting:
            self.value = max(0.0, self.value - self.c["decay"] * dt)
        self.check_snap()
        steps = self.c["haptic_steps"]
        n = sum(1 for s in steps if self.value >= s)
        if n > self.step:
            self.fight.events.append(f"twist_step:{n}")
        self.step = n

    def check_snap(self) -> bool:
        if self.value < 100:
            return False
        f = self.fight
        dmg = f.line_max * self.c["snap_line_frac"]
        f.line -= dmg
        f.line_damage += dmg
        f.last_pattern_fail = ("twist", f.elapsed)
        self.value = self.c["snap_to"]
        f.events.append("twist_snap")
        return True


JUDGES = {"shake": Shake, "dive": Dive, "surface": Surface, "reverse": Reverse, "twist": Twist}


class Combo:
    """⑥ 연쇄 콤보 진행: 중간에 하나라도 실패하면 남은 행동 힘 ×1.3, 3연속 성공이면 스태미나 −15%."""

    def __init__(self, fight, seq: list[str]):
        self.c = cfg()["chain"]
        self.fight = fight
        self.seq = list(seq)
        self.index = -1        # 지금 몇 번째 행동 (화면 표시)
        self.failed = False
        self.rush_red = 0.0

    def fail(self) -> None:
        if not self.failed:
            self.failed = True
            self.fight.brain.combo_mult = self.c["fail_power_mult"]
            self.fight.events.append("combo_break")

    def update(self, dt: float) -> None:
        f = self.fight
        if f.brain.state == "rush" and f.tension > f.green_high:
            self.rush_red += dt
            if self.rush_red > self.c["rush_red_fail_sec"]:
                self.fail()

    def on_event(self, ev: str) -> None:
        if ev.startswith("action:") and ev != "action:chain":
            self.index += 1
            self.rush_red = 0.0

    def finish(self) -> str:
        f = self.fight
        if self.failed:
            res = "fail"
        else:
            res = "ok"
            f.stamina -= f.stamina_max * self.c["ok_stamina_frac"]
        f.events.append(f"combo_{res}")
        return res
