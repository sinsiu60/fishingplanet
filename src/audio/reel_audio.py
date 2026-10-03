"""합성 릴 소리 재생 (DESIGN.md 32-16 Z2) — tools/audio/reel_synth.py 로 미리 구운 루프를 섞어 낸다.

  감기   속도 6단계(핸들 1.0~3.5회/초) × 부하 3단계(0/0.5/0.9) 루프 중 지금 값에 가까운 2~4개를 음량 비율로 섞는다.
         소리 재생 속도는 바꾸지 않는다 (음색 유지). 티어 음색: T1 나무 / T2~T5 보통 / T6~T8 수정.
         감기 시작 = 가속음 + 루프 페이드 인, 멈춤 = '딸깍'.
  드랙   풀리는 속도 4단계 루프(느림/보통/빠름/질주)를 같은 방식으로 섞는다 ('지이이잉', Z1 결정 B).
  공간   낚시터 공간(N5: out/cave/deep)에 맞춰 구운 '~공간' 버전을 쓴다.

루프는 믹서의 동시 재생 한도(N3) 밖 — 연속음 자체가 '주인공'이고 배율은 fight_audio 의 focus 가 정한다.
채널은 믹서의 빈 채널을 직접 쓰고, 음량은 버스(sfx) 배율·덕킹·리미터를 따르며 1/128 단위로 바뀔 때만 set_volume (폰 v0.8.8).
"""
import pygame

SPEEDS = (1.0, 1.5, 2.0, 2.5, 3.0, 3.5)   # tools/bake_reel.py 와 같게
LOADS = (0.0, 0.5, 0.9)
TIERS = ("wood", "mid", "crystal")
DRAGS = 4
FADE = 0.12        # 루프 섞기 비율이 따라가는 시간 (초)
START_FADE = 0.25  # 감기 시작 때 루프가 올라오는 시간


def tier_of(gear_tier: int) -> str:
    return "wood" if gear_tier <= 1 else "mid" if gear_tier <= 5 else "crystal"


def _bracket(x: float, grid: tuple) -> list[tuple[int, float]]:
    """x 양옆 두 칸과 비율. 가운데(25~75%)에서만 섞고 그 밖은 가까운 하나만 — 틱이 두 겹으로 들리는 구간을 줄인다."""
    if x <= grid[0]:
        return [(0, 1.0)]
    if x >= grid[-1]:
        return [(len(grid) - 1, 1.0)]
    for i in range(len(grid) - 1):
        if grid[i] <= x <= grid[i + 1]:
            w = (x - grid[i]) / (grid[i + 1] - grid[i])
            w = min(1.0, max(0.0, (w - 0.25) / 0.5))
            w = w * w * (3 - 2 * w)
            return [(i, 1 - w), (i + 1, w)]
    return [(0, 1.0)]


class ReelPlayer:
    def __init__(self, sfx):
        self.sfx = sfx
        self.key = None            # 읽어 둔 (티어, 공간)
        self.snd: dict[str, pygame.mixer.Sound] = {}
        self.voices: dict[str, dict] = {}   # 이름 → {ch, vol, goal, q}
        self.reeling_t = 0.0       # 감기 시작 뒤 시간 (0 = 멈춤)
        self.tier = "mid"
        self.max_voices = 0        # 검증용: 동시에 쓴 채널 최대

    # ── 파일 ──
    def prepare(self, tier: str | None = None) -> None:
        """지금 티어·공간 소리를 읽어 둔다 (낚시터 들어올 때·파이팅 시작 때 — 바뀌었을 때만)."""
        if tier:
            self.tier = tier
        if not self.sfx.enabled:
            return
        space = getattr(self.sfx, "space_name", "open")
        key = (self.tier, space)
        if key == self.key:
            return
        self.stop()
        self.key = key
        self.snd = {}
        from src.core.paths import asset_path
        names = [f"reel_{self.tier}_s{i}_l{j}" for i in range(len(SPEEDS)) for j in range(len(LOADS))]
        names += [f"reel_{self.tier}_start", f"reel_{self.tier}_stop"] + [f"drag_{k}" for k in range(DRAGS)]
        for n in names:
            for fn in ((n + f"~{space}") if space != "open" else None, n):
                if not fn:
                    continue
                p = asset_path("sfx_generated", "reel", fn + ".ogg")
                if p.exists():
                    try:
                        self.snd[n] = pygame.mixer.Sound(str(p))
                        break
                    except Exception:
                        pass

    # ── 재생 ──
    def _gain(self) -> float:
        return self.sfx.bus_gain("sfx")

    def _one(self, name: str, vol: float) -> None:
        snd = self.snd.get(name)
        got = self.sfx._free() if snd else None
        if got:
            got[1].set_volume(min(1.0, vol * self._gain()))
            got[1].play(snd)

    def _set(self, goals: dict[str, float], dt: float) -> None:
        for name in set(self.voices) | {n for n, g in goals.items() if g > 0.005}:
            v = self.voices.get(name)
            goal = goals.get(name, 0.0)
            if v is None:
                snd = self.snd.get(name)
                got = self.sfx._free() if snd else None
                if not got:
                    continue
                v = self.voices[name] = {"ch": got[1], "vol": 0.0, "q": None}
                got[1].set_volume(0.0)
                got[1].play(snd, loops=-1)
            step = dt / FADE
            v["vol"] = min(goal, v["vol"] + step) if goal > v["vol"] else max(goal, v["vol"] - step)
            if v["vol"] <= 0.003 and goal <= 0.003:
                v["ch"].fadeout(30)
                del self.voices[name]
                continue
            q = round(min(1.0, v["vol"] * self._gain()) * 128)
            if q != v["q"]:
                v["q"] = q
                v["ch"].set_volume(q / 128)
            if not v["ch"].get_busy():   # stop_all 등으로 멈췄으면 다시
                v["ch"].play(self.snd[name], loops=-1)
        self.max_voices = max(self.max_voices, len(self.voices))

    def update(self, dt: float, reel: float, load: float, payout: float, reel_gain: float = 1.0,
               drag_gain: float = 1.0) -> None:
        """reel: 게임 감기 속도 (0 = 안 감음, 최대 약 3), load: 0~1 장력 부하, payout: 0~1 줄 풀리는 속도."""
        if not self.sfx.enabled or not self.snd:
            return
        goals: dict[str, float] = {}
        if reel > 0.05:
            if self.reeling_t == 0.0:
                self._one(f"reel_{self.tier}_start", 0.5 * reel_gain)
            self.reeling_t += dt
            rps = 1.0 + 2.5 * min(1.0, reel / 3.0)
            ramp = min(1.0, self.reeling_t / START_FADE)
            level = 0.6 * reel_gain * ramp
            for i, wi in _bracket(rps, SPEEDS):
                for j, wj in _bracket(load * 0.9, LOADS):
                    goals[f"reel_{self.tier}_s{i}_l{j}"] = level * wi * wj
        else:
            if self.reeling_t > 0.25:
                self._one(f"reel_{self.tier}_stop", 0.7 * reel_gain)  # 멈춤 '딸깍'
            self.reeling_t = 0.0
        if payout > 0.12:
            level = (0.15 + 0.5 * payout) * drag_gain
            for k, w in _bracket(payout * (DRAGS - 1), tuple(range(DRAGS))):
                goals[f"drag_{k}"] = level * w
        self._set(goals, dt)

    def stop(self) -> None:
        for v in self.voices.values():
            v["ch"].fadeout(60)
        self.voices = {}
        self.reeling_t = 0.0
