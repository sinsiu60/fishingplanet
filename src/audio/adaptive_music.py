"""적응형 음악 재생 (DESIGN.md 32-12, Phase S6).

같은 길이의 음악 층(src/audio/music_synth.py)을 예약 채널에서 한꺼번에 반복 재생하고, 상황에 따라 층 음량만 바꾼다.
  - 상황(set)  menu / idle / bite / fight / tired / legend / legend_tired / win / fail → data/music_patterns.json "levels"
  - 전환 시점  다음 마디 경계(대기·메뉴) 또는 다음 박(파이팅·지침 같은 긴급) — "quantize". 바뀐 뒤 fade_sec 동안 페이드.
  - 연속 값    장력(intensity) → 추가 타악 perc_hi 세기 / 낮 밝기(daylight) → 높은 반짝임 shimmer / 전설 페이즈 → 보스 층 수
  - 포획 win   층을 내리고 승리 스팅 → 스팅이 끝나면 대기로 / 실패 fail → 페이드 아웃 2.5초 뒤 대기로
  - 맥락(set_context) 대륙·낚시터·전설이 바뀌면 0.5초 페이드 아웃 → 새 층으로 처음부터 다시
N4 음악 절제 (SOUND_CLEANUP 5번): 낚시터 대기 음악은 간헐적으로 (idle_cycle: 몇 바퀴 울리고 1~3분 정적),
  입질·일반 파이팅은 그때 상태 그대로 낮추기만, 대형(fight_big)은 낮은 긴장 층 하나, 장력 타악은 전설만, 포획 스팅은 희귀 이상만.
층 파일: assets/music/<이름>.ogg|wav (직접 만든 음악, 우선) → assets/music_generated/<이름>.ogg (미리 구운 합성) → 실행 중 합성 (경고).
data/music/ 의 예전 스트리밍 곡(spot_/fight_/legend_/title)이 재생 중이면 층 음악은 조용히 비켜 준다.
"""
import math

import pygame

from src.audio import music_synth

LAYERS = ("theme", "pad", "shimmer", "tension", "perc_lo", "perc_hi", "rise", "boss1", "boss2", "boss3")
GAIN = 0.35          # 음악 전체 — N4: 낚시터에서 환경음 바탕보다 약 1.5dB 작게 (예전 0.75). 메뉴·전설·스팅은 state_gain 으로 키움
CTX_FADE = 0.5
FAIL_HOLD = 2.5


class AdaptiveMusic:
    def __init__(self, sfx):
        self.sfx = sfx
        self.enabled = sfx.enabled
        self.cfg = music_synth.cfg()
        self.beat, self.bar, self.total = music_synth.timing()
        self.ctx: tuple | None = None        # 지금 도는 (대륙, 낚시터, 전설)
        self.ctx_next: tuple | None = None   # 바꿀 맥락 (페이드 아웃 뒤)
        self.ctx_fade = 0.0
        self.sounds: dict[str, pygame.mixer.Sound] = {}   # 층 → 소리
        self.cache: dict[str, pygame.mixer.Sound] = {}    # 파일 이름 → 소리 (지금 맥락 + 스팅만 들고 있음)
        self.level = {k: 0.0 for k in LAYERS}
        self.goal = {k: 0.0 for k in LAYERS}
        self.state = "idle"
        self.applied = None                  # 지금 반영된 (상황, 페이즈)
        self.pending: tuple | None = None    # (적용 시각, 상황, 페이즈)
        self.intensity = 0.0
        self.daylight = 1.0
        self.phase = 0
        self.clock = 0.0
        self.t0 = 0.0
        self.state_t = 0.0
        self.sting_left = 0.0
        self.quiet = False                   # 예전 스트리밍 곡이 나오는 중
        self._vol_q: dict = {}             # 채널에 마지막으로 넣은 음량 (1/128 단위)
        self.missing: list[str] = []
        # N4 대기 음악 간헐 재생: play(울림) / rest(정적)
        self.cyc = self.cfg.get("idle_cycle")
        self.idle_phase = "play"
        self.idle_t = 0.0          # play: 울린 시간 / rest: 남은 정적
        self.cur_fade = self.cfg["fade_sec"]
        self.sgain = 1.0           # 상황별 음악 배율 (state_gain, 부드럽게 바뀜)
        if self.enabled:
            base = sfx.n_sig
            self.ch = {k: pygame.mixer.Channel(base + i) for i, k in enumerate(LAYERS)}
            self.ch_sting = pygame.mixer.Channel(base + len(LAYERS))

    # ── 파일 ──
    def _load(self, name: str) -> pygame.mixer.Sound | None:
        from src.core import bootlog
        from src.core.paths import asset_path
        bootlog.mark(f"  음악 {name}")
        for d in ("music", "music_generated"):
            for ext in (".ogg", ".wav"):
                p = asset_path(d, name + ext)
                if p.exists():
                    try:
                        return pygame.mixer.Sound(str(p))
                    except Exception as e:
                        bootlog.mark(f"  {name} 읽기 실패: {e!r}")
        self.missing.append(name)
        from src.platform.detect import IS_MOBILE
        if IS_MOBILE:
            return None  # 폰에서 음악을 실행 중 합성하면 너무 오래 걸린다 → 그 층은 조용히
        rec = music_synth.recipes().get(name)
        if rec is None:
            return None
        print(f"[music] 구운 파일 없음, 실행 중 합성: {name} (python tools/bake_music.py)")
        try:
            st = music_synth.render(rec)
            return pygame.sndarray.make_sound(self.sfx._to_pcm_stereo(st))
        except Exception:
            return None

    def _names(self, ctx: tuple) -> dict[str, str]:
        cont, spot, legend = ctx
        if cont == "ending":
            return {"theme": "mus_ending"}
        if spot is None:
            return {"theme": f"mus_theme_{cont}"}  # 메뉴·지도: 대륙 테마만
        out = dict(pad=f"mus_pad_{spot}", shimmer=f"mus_shimmer_{cont}", tension=f"mus_tension_{cont}",
                   perc_lo=f"mus_perc_lo_{cont}", perc_hi=f"mus_perc_hi_{cont}", rise=f"mus_rise_{cont}")
        if legend:
            out.update({f"boss{i}": f"mus_boss{i}_{cont}" for i in (1, 2, 3)})
        return out

    # ── 바깥에서 부르는 것 ──
    def set_context(self, continent: str, spot: str | None, legend: bool = False) -> None:
        if continent != "ending" and continent not in self.cfg["continents"]:
            continent = "sharmion"
        ctx = (continent, spot, bool(legend))
        if ctx == self.ctx or ctx == self.ctx_next:
            return
        self.ctx_next = ctx
        self.ctx_fade = CTX_FADE if self.ctx is not None else 0.0

    def set(self, state: str, intensity: float = 0.0, phase: int = 0, daylight: float = 1.0,
            rarity: str | None = None) -> None:
        """rarity: 포획(win) 때 물고기 희귀도 — sting_rarity 에 있을 때만 승리 스팅 (N4)."""
        if state != self.state:
            self.state = state
            self.state_t = 0.0
            if state == "win" and (rarity is None or rarity in self.cfg.get("sting_rarity", [rarity])):
                self._sting()
        self.intensity = max(0.0, min(1.0, intensity))
        self.phase = phase
        self.daylight = daylight

    def stop(self) -> None:
        if self.enabled:
            for ch in self.ch.values():
                ch.stop()
            self.ch_sting.stop()
        self.ctx = self.ctx_next = None
        self.sounds = {}
        self.cache = {}
        self.level = {k: 0.0 for k in LAYERS}

    @staticmethod
    def daylight_of(hour: float, night=(20, 5)) -> float:
        """낮 1 → 밤 0 (해 질 녘·새벽 1시간 동안 서서히)."""
        dusk, dawn = night
        if dawn + 1 <= hour < dusk - 1:
            return 1.0
        if dusk - 1 <= hour < dusk:
            return dusk - hour
        if dawn <= hour < dawn + 1:
            return hour - dawn
        return 0.0

    # ── 매 프레임 ──
    def _restart(self) -> None:
        for ch in self.ch.values():
            ch.stop()
        self.ctx = self.ctx_next
        self.ctx_next = None
        names = self._names(self.ctx)
        cache = {n: self.cache.get(n) or self._load(n) for n in names.values()}
        if "mus_sting_win" in self.cache:
            cache["mus_sting_win"] = self.cache["mus_sting_win"]
        self.cache = {n: snd for n, snd in cache.items() if snd is not None}  # 안 쓰는 대륙·낚시터 층은 놓아 준다
        self.sounds = {k: self.cache[n] for k, n in names.items() if n in self.cache}
        self.level = {k: 0.0 for k in LAYERS}
        self._vol_q = {}
        for k, snd in self.sounds.items():   # 같은 프레임에 한꺼번에 → 끝까지 맞물려 돈다
            self.ch[k].set_volume(0.0)
            self._vol_q[k] = 0
            self.ch[k].play(snd, loops=-1)
        self.t0 = self.clock
        self.applied = None
        self.pending = None
        self.idle_phase, self.idle_t = "play", 0.0  # 새 낚시터에 오면 음악부터

    def _next_boundary(self, unit: str) -> float:
        step = self.bar if unit == "bar" else self.beat
        k = math.ceil((self.clock - self.t0) / step - 1e-6)
        return self.t0 + k * step

    def _idle_tick(self, dt: float) -> None:
        """대기 중에만 도는 울림/정적 주기. 입질·파이팅 중엔 멈춘 채 그 상태 유지."""
        c = self.cyc
        if self.idle_phase == "play":
            self.idle_t += dt
            if self.idle_t >= c["play_loops"] * self.total - c["fade_out_sec"]:
                import random
                self.idle_phase, self.idle_t = "rest", random.uniform(*c["rest_sec"])
        else:
            self.idle_t -= dt
            if self.idle_t <= 0:
                self.idle_phase, self.idle_t = "play", 0.0

    def resting(self) -> bool:
        """지금 대기 음악 정적 구간인가 (낚시터에서만)."""
        return bool(self.cyc) and self.ctx is not None and self.ctx[1] is not None and self.idle_phase == "rest"

    def _sg(self, key: str) -> float:
        return float(self.cfg.get("state_gain", {}).get(key, 1.0))

    def _effective(self) -> str:
        if self.state == "win" and self.sting_left <= 0:
            return "idle"
        if self.state == "fail" and self.state_t >= FAIL_HOLD:
            return "idle"
        return self.state

    def _sting(self) -> None:
        if not self.enabled:
            return
        snd = self.cache.get("mus_sting_win") or self._load("mus_sting_win")
        if snd is None:
            return
        self.cache["mus_sting_win"] = snd
        self._vol_q.pop("_sting", None)
        self.ch_sting.set_volume(min(1.0, GAIN * self._sg("sting") * self.sfx.bus_gain("mus")))
        self.ch_sting.play(snd)
        self.sting_left = snd.get_length()

    def update(self, dt: float, quiet: bool = False) -> None:
        if not self.enabled:
            return
        self.clock += dt
        self.state_t += dt
        self.sting_left = max(0.0, self.sting_left - dt)
        self.quiet = quiet
        if self.ctx_next is not None:
            self.ctx_fade -= dt
            if self.ctx_fade <= 0:
                self._restart()
        if self.ctx is None:
            return
        st = self._effective()
        if self.cyc and self.ctx[1] is not None and st == "idle":
            self._idle_tick(dt)
        rest = self.resting() and st in ("idle", "bite", "fight", "tired")  # 정적이면 입질·일반 파이팅도 조용히
        key = (st, self.phase, rest)
        if key != self.applied and (self.pending is None or self.pending[1:] != key):
            unit = self.cfg["quantize"].get(st, "bar")
            at = self.clock if self.applied is None else self._next_boundary(unit)
            self.pending = (at, st, self.phase, rest)
        if self.pending is not None and self.clock >= self.pending[0]:
            _, st2, ph, rest2 = self.pending
            was_rest = self.applied[2] if self.applied else False
            self.applied = (st2, ph, rest2)
            self.pending = None
            lv = {} if rest2 else self.cfg["levels"].get(st2, {})
            self.goal = {k: lv.get(k, 0.0) for k in LAYERS}
            # 대기 음악이 끝날 땐 천천히 사라지고, 정적 뒤엔 천천히 들어온다
            self.cur_fade = (self.cyc["fade_out_sec"] if rest2 and not was_rest else
                             self.cyc["fade_in_sec"] if was_rest and not rest2 else self.cfg["fade_sec"]) \
                if self.cyc else self.cfg["fade_sec"]
            if st2.startswith("legend"):
                for i in (2, 3):  # 페이즈마다 보스 층 하나씩
                    if ph < i - 1:
                        self.goal[f"boss{i}"] = 0.0
        # 연속 값: 장력 → 추가 타악, 낮 밝기 → 반짝임
        night = self.cfg["night_shimmer"]
        mult = {"perc_hi": self.intensity, "shimmer": night + (1 - night) * self.daylight}
        rate = dt / max(0.05, self.cur_fade)
        fade_ctx = max(0.0, self.ctx_fade / CTX_FADE) if self.ctx_next is not None else 1.0
        want = self._sg(self.applied[0]) if self.applied else 1.0
        self.sgain += max(-dt, min(dt, want - self.sgain))  # 초당 1.0 만큼 (메뉴 → 낚시터 등)
        bus = self.sfx.bus_gain("mus") * GAIN * self.sgain * (0.0 if quiet else 1.0) * fade_ctx
        for k in LAYERS:
            goal = self.goal[k] * mult.get(k, 1.0)
            cur = self.level[k]
            step = rate if k not in mult else rate * 0.6
            self.level[k] = min(goal, cur + step) if goal > cur else max(goal, cur - step)
            if k in self.sounds:
                q = round(min(1.0, self.level[k] * bus) * 128)
                if self._vol_q.get(k) != q:  # 바뀔 때만 (폰 오디오 잠금, v0.8.8)
                    self._vol_q[k] = q
                    self.ch[k].set_volume(q / 128)
        if self.sting_left > 0:
            q = round(min(1.0, GAIN * self._sg("sting") * self.sfx.bus_gain("mus") * (0.0 if quiet else 1.0)) * 128)
            if self._vol_q.get("_sting") != q:
                self._vol_q["_sting"] = q
                self.ch_sting.set_volume(q / 128)
