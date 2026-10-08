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

PATTERN_IDS = ("shake", "dive", "surface", "reverse", "twist", "hide", "pump", "bite")  # 판정 객체가 있는 상태형 패턴


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
             "hide": "풀어 주다 고개 내밀 때 감기", "pump": "박자 사이에 감기", "thrash": "정점·착수 직전 숙이기",
             "bite": "번쩍일 때 드랙 최저", "fake": "가짜면 감지 않기", "dual": "두 손으로 따로",
             "twist": "원 그리기", "chain": "순서대로 대응"}


def fish_patterns(fish: dict) -> list[str]:
    """이 물고기가 쓰는 신규 패턴 (기본 + 페이즈 + 콤보 순서 안), 정해진 순서로."""
    used = set(fish.get("actions", {}))
    for ph in fish.get("phases", []):
        used |= set(ph.get("actions", {}))
        used |= set(ph.get("chain_seq", []))
    used |= set(fish.get("chain_seq", []))
    if fish.get("fake_tired") or any(ph.get("fake_tired") for ph in fish.get("phases", [])):
        used.add("fake")
    for pair in fish.get("dual_pairs", []):
        used |= set(pair)
    order = ("shake", "dive", "surface", "reverse", "twist", "chain", "hide", "pump", "thrash", "bite", "fake", "dual")
    return [p for p in order if p in used]


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

    PERFECT_RATIO = 0.95

    def perfect(self) -> bool:
        """성공 중에서도 깔끔했나 (연출 등급 PERFECT / GREAT — 판정·보상엔 영향 없음)."""
        return self.ratio >= self.PERFECT_RATIO

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

    def tension_add(self, f) -> float:
        return 0.0

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
        f.brain.lose_burst(self.c["ok_burst"])   # 체력은 fight.pattern_result 가 비율로 (CU4)

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
        tg.value += self.c["rise"] * self.fight.gear.get("twist_mult", 1.0) * dt   # 비늘석 꼬임 저항
        if tg.check_snap():
            self.snapped = True

    def passed(self) -> bool:
        return not self.snapped and self.fight.twist.value < self.c["ok_below"]

    def perfect(self) -> bool:
        return self.fight.twist.value <= 5

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


class Hide(Judge):
    """⑦ 숨기: 감지 말고 풀어 줘서(장력 초록 아래 끝) 버티면 고개를 내민다 → 그때 감기."""

    def __init__(self, fight):
        super().__init__("hide", fight)
        self.hold_t = 0.0
        self.peek_t = 0.0
        self.peeks = 0
        self.success = False
        self.reeling = False

    @property
    def ratio(self) -> float:
        return 1.0 if self.peek_t > 0 else self.hold_t / self.c["hold_sec"]

    @property
    def peeking(self) -> bool:
        return self.peek_t > 0

    def perfect(self) -> bool:
        return getattr(self, "react_left", 0.0) >= 0.5

    def update(self, dt, inp, reeling, aim_rate):
        self.reeling = reeling
        super().update(dt, inp, reeling, aim_rate)

    def during(self, dt, inp, ok):
        f, c = self.fight, self.c
        if self.success:
            return
        if self.peek_t > 0:
            self.peek_t -= dt
            if self.reeling:
                self.success = True
                self.react_left = self.peek_t / c["peek_sec"]  # 고개 내밀자마자 감았나 (연출 등급)
                f.brain.end_pattern("hide")
            elif self.peek_t <= 0:
                self.hold_t = 0.0  # 놓쳤다 → 다시 숨는다
            return
        lo, hi = f.green_low + c["low_min"], f.green_low + c["low_max"]
        if lo <= f.tension <= hi and not self.reeling:
            self.hold_t += dt
            if self.hold_t >= c["hold_sec"]:
                self.peek_t = c["peek_sec"]
                self.peeks += 1
                f.events.append("hide_peek")
        else:
            self.hold_t = 0.0
        if f.tension > (f.green_low + f.green_high) / 2:
            dmg = f.line_max * c["pull_line_frac"] * dt  # 바위 틈에서 억지로 당기면 줄이 쓸린다
            f.line -= dmg
            f.line_damage += dmg

    def tension_override(self, f):
        if not self.active or self.success:
            return None
        # 숨은 물고기는 버티기만 한다: 감지 않으면 초록 아래 끝 근처, 감으면 감는 만큼 올라감
        if not self.reeling:
            return f.green_low - 2
        cfg = f.cfg
        return f.green_low + cfg["reel_tension_min"] + cfg["reel_tension_per_drag"] * f.drag_frac

    def finish(self) -> str:
        f = self.fight
        if self.success:
            self.result = "ok"
            f.distance = max(0.0, f.distance - self.c["ok_distance"])
        else:
            self.result = "neutral"  # 시간이 지나 그냥 나왔다 (보너스 없음)
        f.pattern_result(self.id, self.result)
        return self.result


class Pump(Judge):
    """⑧ 펌핑 리듬: 박마다 당김(장력 +), 빈 박 가운데에만 감기. 박자는 예고 때 두 박 미리 들려준다."""

    def __init__(self, fight):
        super().__init__("pump", fight)
        self.interval = self.c["interval"]
        self.beat = -1          # 지금 박 번호 (행동 기준)
        self.hits: list[bool] = []
        self.bad: list[bool] = []
        self.streak = 0
        self.best = 0
        self.preview_sent = 1   # 예고 시작 박은 예고 이벤트가 대신 낸다
        self.reeling = False

    def update(self, dt, inp, reeling, aim_rate):
        self.reeling = reeling
        super().update(dt, inp, reeling, aim_rate)

    def pre(self, dt, inp):
        b = self.fight.brain
        if not self.active and b.state == "telegraph":
            k = int(b.state_t / self.interval + 1e-6)
            if k >= self.preview_sent and k < self.c["preview_beats"]:
                self.preview_sent = k + 1
                self.fight.events.append("pump_beat:preview")

    def _phase(self) -> tuple[int, float]:
        k = int(self.t / self.interval + 1e-6)
        return k, self.t - k * self.interval

    def during(self, dt, inp, ok):
        f, c = self.fight, self.c
        k, ph = self._phase()
        if k >= f.brain.pump_beats:
            return
        while self.beat < k:
            self._close_beat()
            self.beat += 1
            self.hits.append(False)
            self.bad.append(False)
            f.events.append(f"pump_beat:{self.beat}")
        lat = f.input_latency
        if ph < c["pull_sec"] + lat and self.reeling:
            self.bad[k] = True   # 당길 때 감았다
        center = self.interval / 2 + lat
        if abs(ph - center) <= c["window"] and self.reeling:
            self.hits[k] = True

    def _close_beat(self) -> None:
        if self.beat < 0:
            return
        good = self.hits[self.beat] and not self.bad[self.beat]
        self.streak = self.streak + 1 if good else 0
        self.best = max(self.best, self.streak)
        self.fight.events.append("pump_hit" if good else "pump_miss")

    def tension_add(self, f) -> float:
        if not self.active:
            return 0.0
        k, ph = self._phase()
        if k >= f.brain.pump_beats or ph >= self.c["pull_sec"]:
            return 0.0
        return self.c["pull_tension"] + (self.c["reel_in_pull"] if self.reeling else 0.0)

    @property
    def ratio(self) -> float:
        n = max(1, self.beat + 1)
        return sum(1 for h, b in zip(self.hits, self.bad) if h and not b) / n

    def finish(self) -> str:
        f, c = self.fight, self.c
        self._close_beat()
        self.beat = len(self.hits)  # 다시 닫지 않게
        n = max(1, len(self.hits))
        good = sum(1 for h, b in zip(self.hits, self.bad) if h and not b)
        if self.best > 0:
            f.reel_bonus = min(c["reel_bonus_max"], c["reel_bonus_per"] * self.best)
            f.reel_bonus_t = c["bonus_sec"]
        self.result = "ok" if good >= n * c["ok_frac"] else "fail"
        self.all_hit = good >= n
        f.pattern_result(self.id, self.result)
        return self.result

    def perfect(self) -> bool:
        return getattr(self, "all_hit", False)


class Bite(Judge):
    """⑩ 줄 물어뜯기: 예고가 끝나는 순간 ±window 안에 드랙 순간 최저를 '새로' 누르기."""

    def __init__(self, fight):
        super().__init__("bite", fight)
        self.prev = False
        self.edges: list[float] = []
        self.t0 = None

    def pre(self, dt, inp):
        f = self.fight
        if inp.drag_min and not self.prev:
            self.edges.append(f.elapsed)
        self.prev = inp.drag_min

    def begin(self, dur):
        super().begin(dur)
        self.t0 = self.fight.elapsed

    def passed(self) -> bool:
        w = self.c["window"]
        return self.t0 is not None and any(abs(e - self.t0) <= w for e in self.edges)

    @property
    def ratio(self) -> float:
        return 1.0 if self.passed() else 0.0

    def perfect(self) -> bool:
        w = self.c["window"] * 0.5
        return self.t0 is not None and any(abs(e - self.t0) <= w for e in self.edges)

    def _success(self, f):
        b = f.brain
        if b.state == "dual":
            f.stiff_after_dual = self.c["stiff_sec"]
        else:
            b.enter_stiff(self.c["stiff_sec"])

    def _fail(self, f):
        dmg = f.line_max * self.c["fail_line_frac"]
        f.line -= dmg
        f.line_damage += dmg


JUDGES = {"shake": Shake, "dive": Dive, "surface": Surface, "reverse": Reverse, "twist": Twist,
          "hide": Hide, "pump": Pump, "bite": Bite}


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
