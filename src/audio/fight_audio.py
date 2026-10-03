"""상태 연동 연속 사운드 (DESIGN.md 32장 S4): 숫자처럼 상태를 알려 주는 소리.

  릴 감기     오디오 최종 팩 릴 루프(src/audio/reel_audio.py) — 속도 구간 slow/normal/fast, 장력 높으면 한 단계 느리게 +2dB
  줄 풀림     줄이 빨리 풀리는 동안 loop_fast (돌진이면 zing_rise → loop_fast → 정점 drag_fast → reel_stop, 장면이 rush_begin)
  장력 삐걱임 v0.8.14 롤백으로 없앰 — 예전처럼 빨강·줄 50% 아래에서 가끔 '끼익'(fight 'creak' 이벤트, fishing_scene)
  줄 실금     v0.8.14 롤백으로 없앰 (예전엔 그 구간에 '끼익'만)
  드랙 단계   단계가 바뀔 때마다 묵직한 '딸깍' (단계 = 피치)
  몸부림     물고기가 움직일 때 가끔 첨벙 — 멀수록 작고 둔하게 (믹서 거리감, N5)

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
    {"key": "drag", "label": "드랙 단계", "min": 0.0, "max": 4.0, "default": 2.0},
    {"key": "near", "label": "물고기 가까움", "min": 0.0, "max": 1.0, "default": 0.5},
    {"key": "space", "label": "공간", "min": 0.0, "max": 3.0, "default": 0.0},
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
        self.crack_t = 1.0
        self.thrash_t = 1.5
        from src.audio.reel_audio import ReelPlayer
        self.reel = ReelPlayer(sfx)  # 릴·돌진·챔질 소리 (오디오 최종 팩)
        self.last_drag = None

    def stop(self) -> None:
        self.reel.stop()
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
        self.sfx.fish_dist = 1.0 - near  # N5: 물고기 쪽 소리는 믹서가 거리만큼 작고 둔하게
        self._update_focus(dt, v, red_at)
        # 릴 감기·줄 풀림 (오디오 최종 팩, reel_audio) — 부하 = 장력 / 빨강 기준
        load = max(0.0, min(1.0, v.get("tension", 0.0) / max(1.0, red_at)))
        self.reel.update(dt, reel if (reel > 0.05 and payout < 0.6) else 0.0, load, payout,
                         self.gain["reel"], self.gain["drag"])
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
                self.sfx.play("sfx_thrash", 0.75 * self.gain["thrash"])  # 거리 감쇠는 믹서가 (N5)
                self.since_thrash = 0.0
