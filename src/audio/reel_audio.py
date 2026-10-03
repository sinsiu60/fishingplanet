"""릴 소리 재생 — 실제 릴 녹음의 클릭 그레인을 재배치해 미리 구운 소리 (REEL_AUDIO_INTEGRATE.md).
tools/audio/bake_reel_audio.py → assets/sfx_generated/reel/ (+ manifest.json). 파일은 manifest 로 찾는다.

  감기   속도 6단계(핸들 1.0~3.5회/초) × 부하 3단계(0/0.5/0.9) 루프 중 지금 값에 가까운 것을 음량 비율로 섞는다.
         소리 재생 속도는 바꾸지 않는다 (음색 유지). 티어 음색: manifest tier_of_equipment (T1 나무 / T2~T5 보통 / T6~T8 수정).
         감기 시작 = start 원샷 + 루프 페이드 인, 손 떼면 = stop 원샷.
  드랙   줄이 풀려나갈 때: 풀리는 속도 → 초당 드랙 클릭 150~850 → 가까운 두 루프 섞기 (빨라지면 음이 올라가고 지치면 내려감).
         돌진 예고(자연음 신호)도 드랙: 줄 펄스 동안 tease 0→1 → 클릭 150→550회/초로 점점 빠르고 크게, 돌진 직전 무음.
  공간   낚시터 공간(N5: out/cave/deep)이면 미리 구운 '~공간' 버전 (space/ 폴더).
  한도   동시에 섞는 루프 최대 4개 (모바일) — 넘으면 가장 작은 것부터 뺀다.

루프는 믹서의 동시 재생 한도(N3) 밖 — 연속음 자체가 '주인공'이고 배율은 fight_audio 의 focus 가 정한다.
채널은 믹서의 빈 채널을 직접 쓰고, 음량은 버스(sfx) 배율·덕킹·리미터를 따르며 1/128 단위로 바뀔 때만 set_volume (폰 v0.8.8).
"""
import json

import pygame

SPEEDS = (1.0, 1.5, 2.0, 2.5, 3.0, 3.5)   # manifest reel_loops 의 rps
LOADS = (0.0, 0.5, 0.9)
DRAG_RATE = (150.0, 850.0)                # 초당 드랙 클릭 (manifest drag_loops clicks_per_sec 범위)
MAX_LOOPS = 4
FADE = 0.12        # 루프 섞기 비율이 따라가는 시간 (초)
START_FADE = 0.25  # 감기 시작 때 루프가 올라오는 시간
DIR = ("sfx_generated", "reel")

_man: dict | None = None


def manifest() -> dict:
    global _man
    if _man is None:
        from src.core.paths import asset_path
        p = asset_path(*DIR, "manifest.json")
        try:
            _man = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            _man = {"tier_of_equipment": {}, "reel_loops": [], "drag_loops": [], "oneshots": [], "zing": []}
    return _man


def _sound(file: str) -> pygame.mixer.Sound | None:
    from src.core.paths import asset_path
    p = asset_path(*DIR, *file.split("/"))
    if p.exists():
        try:
            return pygame.mixer.Sound(str(p))
        except Exception:
            return None
    return None


ZING_GRADES = ("small", "mid", "big", "double")


def load_zings(sfx, tier: str) -> None:
    """패턴 성공 지잉을 믹서 소리표에 'zing_<등급>_<연속 0~2>' 이름으로 넣는다 (장착 릴 티어 음색).
    더블은 연속 단계 없이 한 파일 → 세 이름 모두 같은 소리."""
    if not sfx.enabled:
        return
    for e in manifest()["zing"]:
        if e["tier"] != tier:
            continue
        snd = _sound(e["file"])
        if snd is None:
            continue
        for st in (range(3) if e["grade"] == "double" else (e["streak"],)):
            sfx.sounds[f"zing_{e['grade']}_{st}"] = snd
    for cache in (sfx.slowed, sfx.muffled):  # 예전 티어로 만든 변형은 버림
        for k in [k for k in cache if str(k[0] if isinstance(k, tuple) else k).startswith("zing_")]:
            del cache[k]


def tier_of(gear_tier: int) -> str:
    return manifest()["tier_of_equipment"].get(f"T{int(gear_tier)}") or \
        ("wood" if gear_tier <= 1 else "mid" if gear_tier <= 5 else "crystal")


def _bracket(x: float, grid: tuple) -> list[tuple[int, float]]:
    """x 양옆 두 칸과 비율. 가운데(25~75%)에서만 섞고 그 밖은 가까운 하나만 — 클릭이 두 겹으로 들리는 구간을 줄인다."""
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
        self.snd: dict[str, pygame.mixer.Sound] = {}   # 'loop_<속도>_<부하>' / 'drag_<k>' / 'start' / 'stop'
        self.drag_rates: tuple = ()
        self.voices: dict[str, dict] = {}   # 이름 → {ch, vol, q}
        self.reeling_t = 0.0       # 감기 시작 뒤 시간 (0 = 멈춤)
        self.tier = "mid"
        self.tease = 0.0           # 돌진 예고 0~1 (장면이 줄 펄스 동안 넣음) — 드랙이 슬금슬금 풀리는 소리
        self.surge_t = 0.0         # 돌진 순간 드랙이 확 풀리는 남은 시간
        self.max_voices = 0        # 검증용: 동시에 쓴 루프 채널 최대

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
        if self.key is None or self.key[0] != self.tier:
            load_zings(self.sfx, self.tier)
        self.key = key
        self.snd = {}
        man = manifest()

        def pick(e):
            alt = e.get("space", {}).get(space)
            return (alt and _sound("space/" + alt)) or _sound(e["file"])

        for e in man["reel_loops"]:
            if e["tier"] == self.tier and e["rps"] in SPEEDS and e["load"] in LOADS:
                s = pick(e)
                if s:
                    self.snd[f"loop_{SPEEDS.index(e['rps'])}_{LOADS.index(e['load'])}"] = s
        drags = sorted((e for e in man["drag_loops"] if e["tier"] == self.tier), key=lambda e: e["clicks_per_sec"])
        self.drag_rates = tuple(float(e["clicks_per_sec"]) for e in drags)
        for k, e in enumerate(drags):
            s = pick(e)
            if s:
                self.snd[f"drag_{k}"] = s
        for e in man["oneshots"]:
            if e["tier"] == self.tier:
                s = pick(e)
                if s:
                    self.snd[e["kind"]] = s

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
        goals = {n: g for n, g in goals.items() if g > 0.005 and n in self.snd}
        if len(goals) > MAX_LOOPS:   # 가장 큰 것 4개만
            goals = dict(sorted(goals.items(), key=lambda kv: -kv[1])[:MAX_LOOPS])
        for name in list(self.voices) + [n for n in goals if n not in self.voices]:
            v = self.voices.get(name)
            goal = goals.get(name, 0.0)
            if v is None:
                if len(self.voices) >= MAX_LOOPS:   # 빠지는 중인 가장 작은 루프를 바로 내리고 자리를 낸다
                    out = [n for n in self.voices if n not in goals]
                    if not out:
                        continue
                    q = min(out, key=lambda n: self.voices[n]["vol"])
                    self.voices[q]["ch"].fadeout(30)
                    del self.voices[q]
                got = self.sfx._free()
                if not got:
                    continue
                v = self.voices[name] = {"ch": got[1], "vol": 0.0, "q": None}
                got[1].set_volume(0.0)
                got[1].play(self.snd[name], loops=-1)
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

    SURGE = 0.5

    def surge(self) -> None:
        """돌진 순간: 드랙이 최고 속도로 확 풀렸다가 0.5초에 걸쳐 실제 줄 풀림 속도로 넘어감."""
        self.surge_t = self.SURGE

    @staticmethod
    def drag_rate(payout: float) -> float:
        """줄 풀리는 속도 0~1 (0.12 넘을 때만 소리) → 초당 드랙 클릭 150~850."""
        k = max(0.0, min(1.0, (payout - 0.12) / 0.88))
        return DRAG_RATE[0] + (DRAG_RATE[1] - DRAG_RATE[0]) * k

    def update(self, dt: float, reel: float, load: float, payout: float, reel_gain: float = 1.0,
               drag_gain: float = 1.0) -> None:
        """reel: 게임 감기 속도 (0 = 안 감음, 최대 약 3 → 핸들 1.0~3.5회/초), load: 0~1 장력 부하, payout: 0~1 줄 풀리는 속도."""
        if not self.sfx.enabled or not self.snd:
            return
        goals: dict[str, float] = {}
        if self.surge_t > 0:
            self.surge_t = max(0.0, self.surge_t - dt)
            payout = max(payout, 0.4 + 0.6 * self.surge_t / self.SURGE)
            drag_gain = max(drag_gain, 1.0)   # 신호 — 연속음 주인공 배율과 상관없이
        if reel > 0.05:
            if self.reeling_t == 0.0:
                self._one("start", 0.6 * reel_gain)
            self.reeling_t += dt
            rps = 1.0 + 2.5 * min(1.0, reel / 3.0)
            ramp = min(1.0, self.reeling_t / START_FADE)
            level = 0.6 * reel_gain * ramp
            for i, wi in _bracket(rps, SPEEDS):
                for j, wj in _bracket(load * 0.9, LOADS):
                    goals[f"loop_{i}_{j}"] = level * wi * wj
        else:
            if self.reeling_t > 0.25:
                self._one("stop", 0.7 * reel_gain)  # 손 떼면 '딸깍'
            self.reeling_t = 0.0
        if payout > 0.12 and self.drag_rates:
            level = (0.15 + 0.5 * payout) * drag_gain
            for k, w in _bracket(self.drag_rate(payout), self.drag_rates):
                goals[f"drag_{k}"] = level * w
        elif self.tease > 0 and self.drag_rates:
            # 돌진 예고(신호): 연속음 주인공 배율과 상관없이 들리게, 클릭 150 → 550회/초로 점점 빠르고 크게
            level = 0.2 + 0.4 * self.tease
            for k, w in _bracket(DRAG_RATE[0] + 400.0 * self.tease, self.drag_rates):
                goals[f"drag_{k}"] = level * w
        self._set(goals, dt)

    def stop(self) -> None:
        for v in self.voices.values():
            v["ch"].fadeout(60)
        self.voices = {}
        self.reeling_t = 0.0
