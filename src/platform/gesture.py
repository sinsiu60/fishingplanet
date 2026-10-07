"""파이팅·대기 중 추가 조작 상태 (DESIGN.md 27-7, Phase U2).

입력 계층(PcInput/TouchInput)이 주는 원재료를 낚시 씬이 매 틱(로직 60틱) 여기에 넣는다.
틱 시간(씬의 self.t)만 쓰므로 리플레이에서도 결과가 같다.

상태
  pitch        낚싯대 상하 -1(내림)~1(올림), 부드럽게 따라감
  taps         최근 tap_window_sec 동안 연타 수
  circle       원 그리기 진행 (-1~1 바퀴, 부호 = 방향), turns = 지금까지 완성한 바퀴 수
  drag_min     드랙 순간 최저 (누르는 동안)
이벤트 (events, 틱마다 비움)
  rod_up / rod_down / reel_tap / circle:+1 / circle:-1
"""
import math


class TapCounter:
    def __init__(self, window: float):
        self.window = window
        self.times: list[float] = []

    def tap(self, t: float) -> None:
        self.times.append(t)

    def count(self, t: float) -> int:
        self.times = [x for x in self.times if t - x <= self.window]
        return len(self.times)


def fit_center(hist) -> tuple[float, float]:
    """최근 궤적에 원을 맞춘 중심 (Kasa 최소제곱). 점이 적거나 거의 직선이면 경계 상자 가운데."""
    xs, ys = [h[1] for h in hist], [h[2] for h in hist]
    box = ((min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2)
    n = len(hist)
    if n < 6:
        return box
    mx, my = sum(xs) / n, sum(ys) / n
    u = [x - mx for x in xs]
    v = [y - my for y in ys]
    suu = sum(a * a for a in u)
    svv = sum(b * b for b in v)
    suv = sum(a * b for a, b in zip(u, v))
    r_u = sum(a * (a * a + b * b) for a, b in zip(u, v)) / 2
    r_v = sum(b * (a * a + b * b) for a, b in zip(u, v)) / 2
    det = suu * svv - suv * suv
    if det < 1e-6 * max(1.0, suu * svv):
        return box
    cu = (r_u * svv - r_v * suv) / det
    cv = (r_v * suu - r_u * suv) / det
    if math.hypot(cu, cv) > 200:  # 거의 직선 = 엄청 큰 원
        return box
    return mx + cu, my + cv


class CircleTracker:
    """방향 무관 원 그리기. 중심(주어지지 않으면 최근 궤적에 맞춘 원의 중심, fit_center) 둘레 회전 각도를 부호 있게 누적해
    360°마다 한 바퀴 이벤트. 반경이 너무 작은 점·순간 이동은 무시, 잠깐 멈추면 누적 초기화."""

    def __init__(self, center_sec: float, idle_reset: float):
        self.center_sec = center_sec
        self.idle_reset = idle_reset
        self.hist: list[tuple[float, float, float]] = []
        self.prev_ang: float | None = None
        self.acc = 0.0
        self.idle = 0.0
        self.turns = 0

    def reset(self) -> None:
        self.hist.clear()
        self.prev_ang = None
        self.acc = 0.0
        self.idle = 0.0

    @property
    def progress(self) -> float:
        return self.acc / (2 * math.pi)

    def feed(self, t: float, dt: float, pos, center, min_r: float) -> int:
        """한 틱 입력. 완성한 바퀴의 방향(+1 시계 / -1 반시계, 화면 좌표 기준)을, 없으면 0을 돌려준다."""
        if pos is None:
            self.reset()
            return 0
        if center is None:
            if not self.hist or self.hist[-1][1:] != (pos[0], pos[1]):  # 멈춰 있던 자리는 한 점만
                self.hist.append((t, pos[0], pos[1]))
            self.hist = [h for h in self.hist if t - h[0] <= self.center_sec] or [(t, pos[0], pos[1])]
            center = fit_center(self.hist)
        dx, dy = pos[0] - center[0], pos[1] - center[1]
        if math.hypot(dx, dy) < min_r:
            self.prev_ang = None
            return self._idle(dt)
        ang = math.atan2(dy, dx)
        if self.prev_ang is None:
            self.prev_ang = ang
            return self._idle(dt)
        d = (ang - self.prev_ang + math.pi) % (2 * math.pi) - math.pi
        self.prev_ang = ang
        if abs(d) < 0.01 or abs(d) > math.pi / 2:  # 멈춤 또는 순간 이동
            return self._idle(dt)
        self.idle = 0.0
        self.acc += d
        if abs(self.acc) >= 2 * math.pi:
            sign = 1 if self.acc > 0 else -1
            self.acc -= sign * 2 * math.pi
            self.turns += 1
            return sign
        return 0

    def _idle(self, dt: float) -> int:
        self.idle += dt
        if self.idle >= self.idle_reset:
            self.acc = 0.0
        return 0


class Controls:
    def __init__(self, cfg: dict):
        self.cfg = cfg
        self.pitch = 0.0
        self.rod_state = 0  # 1 = 올린 상태, -1 = 내린 상태 (이벤트 히스테리시스)
        self.tap_counter = TapCounter(cfg["tap_window_sec"])
        self.taps = 0
        self.circle = CircleTracker(cfg["circle_center_sec"], cfg["circle_idle_reset_sec"])
        self.drag_min = False
        self.events: list[str] = []
        self._queued: list[str] = []  # 틱 밖(입력 이벤트)에서 생긴 것 → 다음 틱 events 로
        self.last_event = ""
        self.last_event_t = -9.0

    def tap(self, t: float) -> None:
        self.tap_counter.tap(t)
        self._queued.append("reel_tap")
        self.last_event, self.last_event_t = "reel_tap", t

    def begin_tick(self) -> None:
        """틱 시작: 지난 틱 이벤트를 버리고 입력 이벤트로 생긴 것을 넘겨받는다."""
        self.events = self._queued
        self._queued = []

    def _emit(self, ev: str, t: float) -> None:
        self.events.append(ev)
        self.last_event, self.last_event_t = ev, t

    def reset(self) -> None:
        """파이팅 시작·끝, 루어 대기 시작에 지난 상태를 버린다."""
        self.circle.reset()
        self.pitch = 0.0
        self.rod_state = 0
        self.drag_min = False

    def update_fight(self, dt: float, t: float, inp) -> None:
        c = self.cfg
        target = inp.rod_pitch()
        target = 0.0 if target is None else max(-1.0, min(1.0, target))
        self.pitch += (target - self.pitch) * min(1.0, c["pitch_smooth"] * dt)
        on, off = c["rod_event_on"], c["rod_event_off"]
        if self.rod_state != 1 and self.pitch >= on:
            self.rod_state = 1
            self._emit("rod_up", t)
        elif self.rod_state != -1 and self.pitch <= -on:
            self.rod_state = -1
            self._emit("rod_down", t)
        elif abs(self.pitch) <= off:
            self.rod_state = 0
        self.taps = self.tap_counter.count(t)
        s = inp.circle_sample(c["circle_min_px"])
        turn = self.circle.feed(t, dt, *s) if s else self.circle.feed(t, dt, None, None, 0)
        if turn:
            self._emit(f"circle:{turn:+d}", t)
        self.drag_min = inp.held("drag_min")

    def debug_lines(self, t: float) -> list[str]:
        p = self.circle.progress
        ev = self.last_event if t - self.last_event_t < 1.5 else "-"
        return [
            f"상하 {self.pitch:+.2f} 연타 {self.taps}/s",
            f"원 {p:+.2f}바퀴 (완성 {self.circle.turns})",
            f"최저드랙 {'켬' if self.drag_min else '끔'}",
            f"입력 {ev}",
        ]
