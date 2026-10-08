"""릴·돌진·챔질·패턴 성공 소리 — 오디오 최종 팩 (tools/audio/INTEGRATE.md, assets/sfx/audio_manifest.json).

모든 클립은 원본 릴 녹음을 자르기만 했거나 미리 만든 파일 → 재생 속도·피치·필터를 바꾸지 않고 그대로 재생 (음량만 조절).
manifest 경로 "sfx/..." 는 assets/sfx/... 기준.

  릴 감기  감기 속도 0~1 (게임 감기 0~3 → /3) 을 speed_bands 로 slow / normal / fast. 구간이 바뀌면 0.2초 크로스페이드.
           normal 은 loop_normal_A·B 를 번갈아 (30ms 겹쳐 이어 붙임 — 끝·처음 샘플이 달라 바로 붙이면 '틱').
           장력(부하) 높으면 한 단계 느린 구간 + 2dB. 감기 시작 reel_start, 0.25초 넘게 감다 떼면 reel_stop.
           릴 루프는 크로스페이드 중에도 동시 최대 2개.
  돌진     rush_begin() = zing_rise_C·A·B 중 무작위(같은 것 연속 금지) → 줄이 계속 풀리는 동안 loop_fast →
           돌진 정점(줄 풀림이 최고에서 꺾이는 순간)에 drag_fast 한 번 → rush_end() = reel_stop. 돌진 중엔 감기 루프 정지.
           돌진 예고(줄 펄스) 동안은 tease 0→1 만큼 loop_slow 가 커짐 (드랙이 슬금슬금 — 자연음 신호).
  챔질     hook(size_cm) = reel_burst_heavy, 큰 물고기일수록 크게.
  성공음   register_success(sfx) = 믹서 소리표에 'succ_<등급>_<연속 0~2>' (small·mid·big·big_pop), 'succ_double', 'succ_double_pop'.
           타격 시점 impact_ms 등은 success_info().
루프·원샷은 믹서의 빈 채널을 직접 쓰고(동시 재생 한도 밖 — 연속음 주인공), 음량은 버스(sfx) 배율·덕킹·리미터를 따른다.
"""
import json
import random

import pygame

MAN = ("sfx", "audio_manifest.json")
BANDS = ("slow", "normal", "fast")
BAND_XF = 0.2         # manifest band_crossfade_sec 이 우선
AB_OVERLAP = 0.03     # normal A↔B 이어 붙일 때 겹침
START_FADE = 0.25
LOAD_HEAVY = (0.75, 0.65)   # 부하 '높음' 들어감 / 풀림 (떨림 방지)
HEAVY_GAIN = 10 ** (2 / 20)
RUN_PAYOUT = 0.3      # 돌진이 아니어도 줄이 이만큼 빨리 풀리면 loop_fast (줄이 계속 풀리는 소리)
MAX_LOOPS = 2
RELEASE_HOLD = 0.15   # 손을 이만큼 떼고 있어야 '멈춤' (짧게 끊었다 감는 것은 계속 감는 것으로 — 루프·'시작' 반복 방지)
LOW_SEMIS = -3          # 무게 단서: 큰 물고기 감기 루프 피치 (core.json arm.reel_semitones 와 같은 값)
RESTART_GAP = 0.25    # 이만큼 쉬었다 다시 감을 때만 reel_start

_man: dict | None = None


def manifest() -> dict:
    global _man
    if _man is None:
        from src.core.paths import asset_path
        try:
            _man = json.loads(asset_path(*MAN).read_text(encoding="utf-8"))
        except Exception:
            _man = {}
    return _man


def _path(rel: str):
    from src.core.paths import asset_path
    return asset_path("sfx", *rel.split("/")[1:]) if rel.startswith("sfx/") else asset_path(*rel.split("/"))


def _sound(rel: str | None) -> pygame.mixer.Sound | None:
    if not rel:
        return None
    p = _path(rel)
    if p.exists():
        try:
            return pygame.mixer.Sound(str(p))
        except Exception:
            return None
    return None


SUCCESS_GRADES = ("small", "mid", "big", "big_pop")


def success_name(grade: str, streak: int) -> str:
    return f"succ_{grade}" if grade in ("double", "double_pop", "phantom") else f"succ_{grade}_{max(0, min(2, streak))}"


def success_info(grade: str, streak: int = 0) -> dict:
    """{'impact_ms', 'second_impact_ms'(더블만), 'duration_sec'} — manifest success."""
    s = manifest().get("success", {})
    e = s.get(grade, {})
    if grade not in ("double", "double_pop"):
        e = e.get(f"streak{max(0, min(2, streak))}", {})
    return {"impact_ms": e.get("impact_ms", 40), "second_impact_ms": e.get("second_impact_ms"),
            "duration_sec": e.get("duration_sec", 0.6)}


def register_success(sfx) -> None:
    """패턴 성공음 14개를 믹서 소리표에 넣는다 (보상 버스, 그대로 재생 — 변주·슬로우·먹먹 없음)."""
    if not sfx.enabled:
        return
    s = manifest().get("success", {})
    for g in SUCCESS_GRADES:
        for k in range(3):
            snd = _sound(s.get(g, {}).get(f"streak{k}", {}).get("file"))
            if snd is not None:
                sfx.sounds[success_name(g, k)] = snd
    for g in ("double", "double_pop", "phantom"):
        snd = _sound(s.get(g, {}).get("file"))
        if snd is not None:
            sfx.sounds[success_name(g, 0)] = snd


class ReelPlayer:
    def __init__(self, sfx):
        self.sfx = sfx
        self.key = None
        self.snd: dict[str, pygame.mixer.Sound] = {}
        self.loops: list[dict] = []     # 릴 루프 채널 (최대 2): {ch, key, vol, goal, rate, t, dur, kind}
        self.band: str | None = None    # 지금 감기 구간 (또는 'run' = 줄 풀림 loop_fast, 'tease')
        self.ab = 0                     # normal 번갈이 (0 = A, 1 = B)
        self.heavy = False
        self.low = False                # 무게 단서 (CORE_UPDATE CU5-2): 큰 물고기 = 감기 루프를 낮게 (피치 −3반음)
        self.reeling_t = 0.0
        self.idle_t = 9.0               # 손 뗀 뒤 시간
        self.last_reel = 0.0
        self.tease = 0.0                # 돌진 예고 0~1 (장면이 줄 펄스 동안 넣음)
        self.rushing = False
        self.rush_t = 0.0
        self.rush_peak = 0.0
        self.rush_peaked = False
        self.last_rise = None
        self.tier = "pack"              # (예전 티어 음색 — 이 팩은 녹음 하나라 티어 없음)
        self.max_voices = 0             # 검증용: 동시에 쓴 릴 루프 채널 최대
        self.voices = {}                # 검증용 (sound_stress): 이름 → {ch, q}

    # ── 파일 ──
    def prepare(self, tier: str | None = None) -> None:
        """팩 소리를 읽어 둔다 (한 번만). tier 는 예전 호출 호환용 (무시)."""
        if not self.sfx.enabled or self.key:
            return
        m = manifest()
        r = m.get("reel", {})
        for b in BANDS:
            files = r.get("loops", {}).get(b, {}).get("files", [])
            for i, rel in enumerate(files):
                s = _sound(rel)
                if s is not None:
                    self.snd[f"{b}_{i}"] = s
        fr = m.get("fish_run", {})
        for i, rel in enumerate(fr.get("start_options", [])):
            s = _sound(rel)
            if s is not None:
                self.snd[f"rise_{i}"] = s
        for k, rel in (("start", r.get("start")), ("stop", r.get("stop")), ("run", fr.get("sustain_loop")),
                       ("peak", fr.get("peak_accent")), ("run_end", fr.get("end")), ("burst", m.get("hookset_or_heavy"))):
            s = _sound(rel)
            if s is not None:
                self.snd[k] = s
        self.bands = {b: tuple(r.get("speed_bands", {}).get(b, (0, 1))) for b in BANDS}
        self.xf = float(r.get("band_crossfade_sec", BAND_XF))
        self.key = "pack"

    # ── 원샷 ──
    def _gain(self) -> float:
        g = self.sfx.bus_gain("sfx")
        if getattr(self.sfx, "boss_mode", False):   # 전용 곡이 커진 만큼 릴은 −2dB (DESIGN.md 43)
            g *= 10 ** (self.sfx.cfg.get("boss", {}).get("reel_db", -2) / 20)
        return g

    def _one(self, key: str, vol: float):
        snd = self.snd.get(key)
        got = self.sfx._free() if snd else None
        if got:
            got[1].set_volume(min(1.0, vol * self._gain()))
            got[1].play(snd)
            return got[1]
        return None

    def hook(self, size_cm: float) -> None:
        """챔질 성공 임팩트: reel_burst_heavy (30cm 0.45 → 150cm 이상 1.0)."""
        self.prepare()
        k = max(0.0, min(1.0, (size_cm - 30) / 120))
        self._one("burst", 0.45 + 0.55 * k)

    def rush_begin(self) -> None:
        """돌진 시작: zing_rise 셋 중 무작위 (같은 것 연속 금지). 감기 루프는 바로 내린다."""
        rises = [k for k in self.snd if k.startswith("rise_")]
        if not rises:
            return
        pick = random.choice([k for k in rises if k != self.last_rise] or rises)
        self.last_rise = pick
        self._one(pick, 1.0)
        for v in self.loops:   # 돌진 중엔 감기 루프 정지 (겹치지 않게 바로)
            v["ch"].fadeout(40)
        self.loops = []
        self.reeling_t = 0.0
        self.rushing, self.rush_t, self.rush_peak, self.rush_peaked = True, 0.0, 0.0, False
        self.pay_s = 0.0
        self.rush_rise_len = self.snd[pick].get_length()

    def rush_end(self) -> None:
        if self.rushing:
            self.rushing = False
            self._one("run_end", 0.8)

    # ── 루프 ──
    def _loop_key(self, band: str) -> str:
        key = self._loop_key_base(band)
        if self.low and band in BANDS:
            return self._pitched(key)
        return key

    def _loop_key_base(self, band: str) -> str:
        if band == "normal":
            return f"normal_{self.ab}" if f"normal_{self.ab}" in self.snd else "normal_0"
        if band == "run":
            return "run"
        if band == "tease":
            return "slow_0"
        return f"{band}_0"

    def _pitched(self, key: str, semis: float = LOW_SEMIS) -> str:
        """감기 루프를 semis 반음 낮춘 사본 (처음 한 번 리샘플해서 둠 — 느리고 낮아짐). 실패하면 원래 소리."""
        lk = key + "_low"
        if lk not in self.snd and key in self.snd:
            try:
                import numpy as np
                arr = pygame.sndarray.array(self.snd[key])
                step = 2 ** (semis / 12)
                pos = np.arange(0, len(arr) - 1, step)
                i0 = pos.astype(np.int64)
                fr = (pos - i0)[:, None] if arr.ndim == 2 else pos - i0
                out = arr[i0] * (1 - fr) + arr[i0 + 1] * fr
                self.snd[lk] = pygame.sndarray.make_sound(np.ascontiguousarray(out.astype(arr.dtype)))
            except Exception:   # 믹서 · numpy 가 없는 환경
                self.snd[lk] = self.snd[key]
        return lk if lk in self.snd else key

    def _start_voice(self, band: str, goal: float, fade_in: float):
        key = self._loop_key(band)
        snd = self.snd.get(key)
        if snd is None:
            return None
        while len(self.loops) >= MAX_LOOPS:   # 동시 2개: 가장 조용한(빠지는 중인) 것부터 바로 내림
            old = min(self.loops, key=lambda v: (v["goal"] > 0, v["vol"]))
            old["ch"].fadeout(20)
            self.loops.remove(old)
        got = self.sfx._free()
        if not got:
            return None
        ab = band == "normal"   # normal 은 한 번씩 재생하고 A↔B 로 이어 감
        v = {"ch": got[1], "key": key, "band": band, "vol": 0.0 if fade_in > 0 else goal, "goal": goal,
             "rate": 1.0 / max(0.02, fade_in), "t": 0.0, "dur": snd.get_length(), "ab": ab, "q": None}
        got[1].set_volume(0.0)
        got[1].play(snd, loops=0 if ab else -1, fade_ms=int(AB_OVERLAP * 1000) if fade_in == 0 else 0)
        self.loops.append(v)
        return v

    def _set_volume(self, v) -> None:
        q = round(min(1.0, v["vol"] * self._gain()) * 128)
        if q != v["q"]:
            v["q"] = q
            v["ch"].set_volume(q / 128)

    def _band_of(self, s: float) -> str:
        for b in BANDS:
            lo, hi = self.bands[b]
            if lo <= s < hi or (b == "fast" and s >= hi):
                return b
        return "slow"

    def update(self, dt: float, reel: float, load: float, payout: float, reel_gain: float = 1.0,
               drag_gain: float = 1.0) -> None:
        """reel: 게임 감기 속도 (0 = 안 감음, 최대 약 3), load: 0~1 장력 부하, payout: 0~1 줄 풀리는 속도."""
        if not self.sfx.enabled:
            return
        self.prepare()
        if not self.snd:
            return
        # 돌진: 정점(줄 풀림 최고에서 꺾임) drag_fast 한 번
        if self.rushing:
            self.rush_t += dt
            self.pay_s += (payout - self.pay_s) * min(1.0, dt / 0.15)   # 줄 풀림 흔들림을 고른 값으로
            if self.pay_s > self.rush_peak:
                self.rush_peak = self.pay_s
            elif (not self.rush_peaked and self.rush_t >= 0.4 and self.rush_peak >= 0.1
                  and self.pay_s < self.rush_peak * 0.85):
                self.rush_peaked = True
                self._one("peak", 0.9 * max(drag_gain, 0.7))
        # 무엇을 틀까
        want, goal = None, 0.0
        if self.rushing or payout >= RUN_PAYOUT:
            # 돌진은 zing_rise 가 끝나 갈 때부터 loop_fast (줄이 계속 풀리는 동안), 감기 루프는 정지
            if not self.rushing or self.rush_t >= getattr(self, "rush_rise_len", 0.0) - 0.15:
                if payout >= 0.12:
                    want, goal = "run", (0.35 + 0.5 * min(1.0, payout)) * max(drag_gain, 0.7 if self.rushing else 0.0)
            if self.reeling_t > 0:
                self.reeling_t = 0.0   # 감기 멈춤 (돌진·질주 중엔 '딸깍' 없이)
        elif reel > 0.05 or (self.reeling_t > 0 and self.idle_t < RELEASE_HOLD):
            if reel > 0.05:
                if self.reeling_t == 0.0 and self.idle_t >= RESTART_GAP:
                    self._one("start", 0.7 * reel_gain)
                self.idle_t = 0.0
                self.last_reel = reel
            else:
                self.idle_t += dt
                reel = self.last_reel   # 잠깐 끊김: 같은 구간 유지
            self.reeling_t += dt
            s = min(1.0, reel / 3.0)
            self.heavy = load >= LOAD_HEAVY[0] or (self.heavy and load >= LOAD_HEAVY[1])
            b = self._band_of(s)
            if self.heavy:   # 장력 높으면 한 단계 느린 구간 + 2dB
                b = BANDS[max(0, BANDS.index(b) - 1)]
            want = b
            goal = 0.6 * reel_gain * min(1.0, self.reeling_t / START_FADE) * (HEAVY_GAIN if self.heavy else 1.0)
        else:
            if self.reeling_t > 0.25 + RELEASE_HOLD:
                self._one("stop", 0.7 * reel_gain)
            self.reeling_t = 0.0
            self.idle_t += dt
            if self.tease > 0:
                want, goal = "tease", 0.15 + 0.45 * self.tease
        # 루프 채널 관리
        cur = next((v for v in self.loops if v["goal"] > 0 and v["band"] == want), None) if want else None
        for v in self.loops:
            if v is not cur:
                v["goal"] = 0.0
        if want and cur is None:
            cur = self._start_voice(want, goal, self.xf if self.band not in (None,) else 0.12)
        if cur is not None:
            cur["goal"] = goal
        self.band = want
        for v in list(self.loops):
            v["t"] += dt
            # normal A↔B: 끝나기 30ms 전 다음 것을 30ms 페이드 인으로 이어 붙임 (그동안만 2개)
            if v["ab"] and v["goal"] > 0 and v["t"] >= v["dur"] - AB_OVERLAP - dt and not v.get("next"):
                v["next"] = True
                self.ab ^= 1
                nv = self._start_voice("normal", v["goal"], 0.0)
                if nv is not None:
                    nv["vol"] = v["vol"]
                    v["goal"] = 0.0
                    v["rate"] = 1.0 / AB_OVERLAP
                    v["ch"].fadeout(int(AB_OVERLAP * 1000))
            step = v["rate"] * dt
            v["vol"] = min(v["goal"], v["vol"] + step) if v["goal"] > v["vol"] else max(v["goal"], v["vol"] - step)
            done = (v["vol"] <= 0.003 and v["goal"] <= 0.003) or (v["ab"] and v["t"] >= v["dur"] + 0.05)
            if done:
                v["ch"].fadeout(20)
                self.loops.remove(v)
                continue
            self._set_volume(v)
        self.max_voices = max(self.max_voices, len(self.loops))
        self.voices = {v["key"]: v for v in self.loops}

    def stop(self) -> None:
        for v in self.loops:
            v["ch"].fadeout(60)
        self.loops = []
        self.voices = {}
        self.reeling_t = 0.0
        self.rushing = False
        self.band = None
