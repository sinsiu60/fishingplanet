"""상태 연동 연속 사운드 (DESIGN.md 32장 S4): 숫자처럼 상태를 알려 주는 소리.

  릴 감기     감기 속도 → 클릭 간격(빠를수록 촘촘)·피치(#0~4)
  드랙 풀림   줄이 풀리는 속도 → 바람 '휘이잉' 반복음 높이(#0~3)·음량 (v0.8.13: 예전 '지이잉'은 거슬려서)
  장력 삐걱임 v0.8.14 롤백으로 없앰 — 예전처럼 빨강·줄 50% 아래에서 가끔 '끼익'(fight 'creak' 이벤트, fishing_scene)
  줄 실금     v0.8.14 롤백으로 없앰 (예전엔 그 구간에 '끼익'만)
  드랙 단계   단계가 바뀔 때마다 묵직한 '딸깍' (단계 = 피치)
  몸부림     물고기가 움직일 때 가끔 첨벙 — 가까울수록 크게

낚시 화면은 매 틱 update(dt, values)를 부르고(values = 아래 SLIDERS 키), 사운드 테스트 룸은 슬라이더 값으로 부른다.

주인공 하나 (SOUND_CLEANUP 3-2, N3 — audio_config.json focus): 상태마다 연속음 하나만 또렷하게, 나머지는 배율로 낮춘다.
  red(장력 빨강) > payout(줄 풀리는 중) > thrash(방금 첨벙) > yellow(초록 위쪽 끝) > reel(평소 감기)
  배율은 fade_sec(0.2초) 동안 크로스페이드, 주인공이 바뀌면 음악·환경음을 아주 살짝 덕킹(focus).
  장력 소리 자체는 v0.8.14 롤백 그대로(빨강 + 줄 50% 아래 '끼익') — 노란 구간 삐걱임은 새로 넣지 않는다 (N1 결정 A).
"""
import random

from src.core.config import load_json

SLIDERS = [
    {"key": "reel", "label": "감기 속도", "min": 0.0, "max": 3.0, "default": 1.2},
    {"key": "payout", "label": "줄 풀림", "min": 0.0, "max": 1.0, "default": 0.0},
    {"key": "tension", "label": "장력", "min": 0.0, "max": 110.0, "default": 50.0},
    {"key": "line", "label": "줄 내구도", "min": 0.0, "max": 1.0, "default": 1.0},
    {"key": "drag", "label": "드랙 단계", "min": 0.0, "max": 4.0, "default": 2.0},
    {"key": "near", "label": "물고기 가까움", "min": 0.0, "max": 1.0, "default": 0.5},
]
RED = 75.0  # 테스트 룸에선 이 위가 빨강 (게임에선 물고기별 green_high)


class FightAudio:
    def __init__(self, sfx):
        self.sfx = sfx
        self.fc = load_json("audio_config.json")["focus"]
        self.focus = "reel"
        self.gain = {"reel": 1.0, "drag": 1.0, "thrash": 1.0}   # 지금 배율 (크로스페이드 중)
        self.since_thrash = 9.0
        self.focus_duck_t = 0.0
        self.click_t = 0.0
        self.crack_t = 1.0
        self.thrash_t = 1.5
        self.loops: dict[str, str | None] = {"drag": None}
        self.last_drag = None

    def _loop(self, slot: str, name: str | None, vol: float = 1.0) -> None:
        cur = self.loops[slot]
        if cur != name and cur is not None:
            self.sfx.loop(cur, False)
        if name is not None:
            self.sfx.loop(name, True, vol)
        self.loops[slot] = name

    def stop(self) -> None:
        for slot in self.loops:
            self._loop(slot, None)
        self.last_drag = None

    def zone_of(self, v: dict, red_at: float) -> str:
        """장력 구간 (소리용): red / yellow(초록 위쪽 끝 yellow_frac) / green. 게임은 v["zone"]을 넣어 준다."""
        z = v.get("zone")
        if z is not None:
            return z
        t, lo = v.get("tension", 0.0), v.get("green_low", 30.0)
        if t >= red_at:
            return "red"
        return "yellow" if t >= red_at - self.fc["yellow_frac"] * max(1.0, red_at - lo) else "green"

    def _update_focus(self, dt: float, v: dict, red_at: float) -> None:
        zone = self.zone_of(v, red_at)
        self.since_thrash += dt
        if zone == "red":
            f = "red"
        elif v.get("payout", 0.0) > 0.12:
            f = "payout"
        elif self.since_thrash < self.fc["thrash_sec"]:
            f = "thrash"
        elif zone == "yellow":
            f = "yellow"
        else:
            f = "reel"
        self.focus_duck_t = max(0.0, self.focus_duck_t - dt)
        if f != self.focus:
            self.focus = f
            if self.focus_duck_t <= 0:
                self.sfx.duck("focus")  # 주인공이 바뀔 때만 아주 살짝
                self.focus_duck_t = 0.6
        step = dt / max(1e-3, self.fc["fade_sec"])
        for k in self.gain:
            goal = self.fc[k][f]
            g = self.gain[k]
            self.gain[k] = min(goal, g + step) if goal > g else max(goal, g - step)

    def update(self, dt: float, v: dict, red_at: float = RED, active: bool = True) -> None:
        reel, payout = v.get("reel", 0.0), v.get("payout", 0.0)
        drag, near = v.get("drag"), v.get("near", 0.5)
        self._update_focus(dt, v, red_at)
        # 드랙 풀림: 바람 휘이잉 (풀리는 속도 → 높이 단계·음량). 살짝 풀릴 땐 안 내서 파이팅 내내 깔리지 않게
        if payout > 0.12:
            step = min(3, int(payout * 4))
            self._loop("drag", f"sfx_drag_run#{step}", (0.12 + 0.45 * payout) * self.gain["drag"])
        else:
            self._loop("drag", None)
        # 릴 감기: 클릭 간격·피치 (드랙이 크게 풀리면 클릭은 묻히니 줄인다)
        if reel > 0.05 and payout < 0.6:
            self.click_t -= dt
            if self.click_t <= 0:
                self.click_t = max(0.022, 0.16 / (0.4 + reel))
                step = min(4, int(reel / 3.0 * 5))
                self.sfx.play(f"sfx_reel_click#{step}", (0.35 + 0.1 * min(1.0, reel / 2)) * self.gain["reel"])
        # 드랙 단계 딸깍
        if drag is not None:
            d = int(round(drag))
            if self.last_drag is not None and d != self.last_drag:
                self.sfx.play(f"sfx_drag_step#{max(0, min(4, d))}", 0.7)
            self.last_drag = d
        # 몸부림 첨벙 (가까울수록 크게)
        if active:
            self.thrash_t -= dt
            if self.thrash_t <= 0:
                self.thrash_t = random.uniform(0.9, 2.2)
                self.sfx.play("sfx_thrash", (0.15 + 0.6 * near) * self.gain["thrash"])
                self.since_thrash = 0.0
