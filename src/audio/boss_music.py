"""전설·환상 전용 파이팅 곡 재생 (DESIGN.md 43, BOSS_BGM.md).

곡 = 인트로 2마디 → 페이즈별 16마디 반복 (층: 바탕·타악·주선율·합창 + 위기 타악 + 옥타브 주선율). 층 파일은 tools/bake_boss.py 가 굽는다.
적응형 음악(adaptive_music)의 예약 채널을 빌려 쓴다 — 도는 동안 적응형 음악은 멈춰 있다(suspended).

맞물림 (샘플 단위): 같은 프레임에 모든 층 채널에서 '앞부분'(인트로·라이저 또는 같은 길이 무음)을 틀고 층을 queue 해 두면
앞부분이 끝나는 순간 모든 층이 정확히 같이 시작한다. 그 뒤엔 채널마다 큐가 비면 같은 층을 다시 queue (이음새 없는 반복).
  - 페이즈 전환: 다음 마디 경계에서 라이저(1마디) + 지금 층은 그 마디 동안 사라짐 → 라이저가 끝나는 순간 다음 페이즈 층
  - 위기: 다음 마디 경계에서 타악 ↔ 위기 타악 (둘 다 늘 돌고 음량만 바꿈)
  - 지침: 다음 마디 경계부터 2마디 동안 주선율 → 옥타브 주선율
  - 실패: 바로 정지 + 낮은 '쿵'(sfx_boss_fail, 1.5초 잔향 — 곡 전용 <곡ID>_fail 이 있으면 그것) / 성공: stop() — 전설·환상 포획 연결은 장면이 (B5)
음량: 층 × GAIN(0.35) × state_gain boss × 음악 버스(설정·덕킹) × 설정 '전설·환상 음악 음량' × 소리 구역.
파일: assets/music/boss/<곡ID>_<페이즈>_<층>.ogg|wav (직접 고른 곡) → assets/music_generated/boss/… (합성본). 없는 층은 조용히.
"""
import pygame

from src.core.paths import asset_path

LAYERS = ("base", "perc", "perc_crisis", "lead", "lead_oct", "choir")
ON = {"base": 1.0, "perc": 1.0, "perc_crisis": 0.0, "lead": 1.0, "lead_oct": 0.0, "choir": 1.0}
SLOTS = 2          # 층 채널 묶음 2개 (지금 페이즈 / 다음 페이즈) + 앞부분 채널 1
TIRED_BARS = 2
FADE_SEC = 0.12    # 마디 경계에서 층 음량 바꿀 때 (딸깍 방지)


def find(name: str):
    for d in (asset_path("music", "boss"), asset_path("music_generated", "boss")):
        for ext in (".ogg", ".wav"):
            p = d / (name + ext)
            if p.exists():
                return p
    return None


class BossMusic:
    def __init__(self, sfx, adaptive):
        self.sfx = sfx
        self.am = adaptive
        self.enabled = sfx.enabled and adaptive.enabled
        from src.core.config import load_json
        self.cfg = load_json("music_patterns.json")
        self.song = None
        self.snd: dict[str, pygame.mixer.Sound] = {}
        self.active = False
        self.loaded_for = None
        self._steps = None
        if self.enabled:
            chs = list(adaptive.ch.values()) + [adaptive.ch_sting]
            self.lay_ch = [dict(zip(LAYERS, chs[s * len(LAYERS):(s + 1) * len(LAYERS)])) for s in range(SLOTS)]
            self.head_ch = chs[SLOTS * len(LAYERS)]
        self._reset()

    def _reset(self) -> None:
        self.t = 0.0
        self.loop_t0 = None      # 지금 페이즈 반복이 시작한 시각 (마디 계산 기준)
        self.phase = 0           # 0부터
        self.slot = 0
        self.want_phase = 0
        self.next_at = None      # 페이즈 전환이 시작될 마디 경계
        self.switch_at = None    # 라이저가 끝나고 다음 페이즈가 시작되는 시각
        self.crisis = self.crisis_on = False
        self.tired_req = False
        self.tired_until = None
        self.tired_from = None
        self.level = {}          # (슬롯, 층) → 지금 음량
        self.goal = {}
        self.fade_rate = {}
        self._vol_q = {}

    # ── 곡 정보 ──
    def spec(self, sid: str) -> dict | None:
        return self.cfg.get("boss", {}).get("songs", {}).get(sid)

    def timing(self, sid: str) -> tuple[float, float]:
        sp = self.spec(sid)
        num, den = sp.get("meter", [4, 4])
        q = 60.0 / sp["bpm"]
        return q, q * num * 4 / den

    def song_for(self, fish_id: str | None) -> str | None:
        """물고기 id → 전용 곡 ID (music_patterns boss.songs 의 fish, 시험곡 제외).
        "replaces" 가 있는 곡(예: L03-ROCK → L03)은 구운 파일이 있으면 원래 곡 대신."""
        if not fish_id:
            return None
        found = [(sid, sp) for sid, sp in self.cfg.get("boss", {}).get("songs", {}).items()
                 if sp.get("fish") == fish_id and not sp.get("test")]
        for sid, sp in found:
            if sp.get("replaces") and find(f"{sid}_1_base") is not None:
                return sid
        return next((sid for sid, sp in found if not sp.get("replaces")), found[0][0] if found else None)

    def available(self, sid: str | None) -> bool:
        """그 곡의 층 파일이 있는가 (없으면 장면이 예전 보스 테마를 쓴다)."""
        return bool(sid) and self.enabled and self.spec(sid) is not None and find(f"{sid}_1_base") is not None

    # ── 불러오기 (한 번에 한 파일 — 입질 전·파장 동안 프레임마다 조금씩) ──
    def prepare(self, sid: str) -> None:
        if not self.available(sid) or self.loaded_for == sid:
            return
        self.snd = {}
        self.loaded_for = sid
        n = len(self.spec(sid)["phases"])
        names = [f"{sid}_intro", f"{sid}_fail"] + [f"{sid}_{i}_{l}" for i in range(1, n + 1) for l in LAYERS + ("riser",)]
        self._steps = iter(names)

    def load_step(self, k: int = 1) -> bool:
        """k 개 불러옴. 다 됐으면 True."""
        if self._steps is None:
            return True
        for _ in range(k):
            name = next(self._steps, None)
            if name is None:
                self._steps = None
                return True
            p = find(name)
            if p is not None:
                try:
                    self.snd[name] = pygame.mixer.Sound(str(p))
                except Exception as e:
                    print("boss music:", name, e)
        return False

    def _get(self, name: str):
        if name not in self.snd and self.loaded_for is not None:
            p = find(name)   # 미리 못 불렀으면 지금 (한 번 끊길 수 있음)
            if p is not None:
                try:
                    self.snd[name] = pygame.mixer.Sound(str(p))
                except Exception:
                    return None
        return self.snd.get(name)

    def _silence(self, sec: float) -> pygame.mixer.Sound:
        key = f"_silence_{round(sec, 4)}"
        if key not in self.snd:
            freq, size, ch = pygame.mixer.get_init()
            n = int(round(sec * freq)) * ch * abs(size) // 8
            self.snd[key] = pygame.mixer.Sound(buffer=bytes(n))
        return self.snd[key]

    # ── 시작·끝 ──
    def start(self, sid: str) -> bool:
        if not self.available(sid):
            return False
        self.prepare(sid)
        while not self.load_step(4):
            pass
        self.am.suspend(True)
        self.sfx.boss_mode = True   # 덕킹 −2dB · 릴 −2dB (환경음 −6dB 는 장면이 set_base_duck("boss_fight"))
        self.song = sid
        self._reset()
        self.q, self.bar = self.timing(sid)
        self.n_phases = len(self.spec(sid)["phases"])
        self.active = True
        intro = self._get(f"{sid}_intro")
        head = intro.get_length() if intro is not None else 0.0
        self._start_phase(0, 0, head, intro)
        self.loop_t0 = head
        return True

    def stop(self, fade_ms: int = 0) -> None:
        if not self.enabled:
            return
        for slot in self.lay_ch:
            for ch in slot.values():
                ch.fadeout(fade_ms) if fade_ms else ch.stop()
        self.head_ch.fadeout(fade_ms) if fade_ms else self.head_ch.stop()
        was = self.active
        self.active = False
        self.song = None
        self.sfx.boss_mode = False
        if was:
            self.am.suspend(False)

    def fail(self) -> None:
        """줄 끊김·도주: 바로 멈추고 낮은 '쿵' + 1.5초 잔향. 곡 전용 실패음(<곡ID>_fail — L03-ROCK: 코드 '콰앙' + 피드백)이 있으면 그것."""
        if not self.active:
            return
        own = self._get(f"{self.song}_fail")
        name, vol = "sfx_boss_fail", 1.0
        if own is not None:   # 효과음 쪽으로 (음악 채널은 적응형 음악이 곧 다시 씀), 크기는 방금까지 듣던 곡과 같게
            from src.audio.adaptive_music import GAIN
            name = f"sfx_boss_fail_{self.song}"
            self.sfx.sounds[name] = own
            vb = self.sfx.settings_boss_vol if hasattr(self.sfx, "settings_boss_vol") else 1.0
            vol = min(1.0, GAIN * self.cfg.get("state_gain", {}).get("boss", 1.0) * vb)
        self.stop()
        self.sfx.play(name, vol)

    def unload(self) -> None:
        self.stop()
        self.snd = {}
        self.loaded_for = None
        self._steps = None

    # ── 바깥 상태 ──
    def set_phase(self, phase: int) -> None:
        if self.active:
            self.want_phase = max(self.want_phase, min(phase, self.n_phases - 1))

    def set_crisis(self, on: bool) -> None:
        self.crisis = bool(on)

    def tired(self) -> None:
        """물고기가 지친 순간 (가장자리): 다음 마디 경계부터 2마디 동안 주선율 한 옥타브 위."""
        if self.active and self.tired_until is None:
            self.tired_req = True

    # ── 내부 ──
    def _start_phase(self, slot: int, phase: int, head_sec: float, head_snd) -> None:
        """같은 프레임에 head(앞부분)를 틀고 층을 queue → head 가 끝나는 순간 모든 층이 같이 시작."""
        sid = self.song
        chs = self.lay_ch[slot]
        sil = self._silence(head_sec) if head_sec > 0 else None
        if head_snd is not None:
            self.head_ch.set_volume(self._bus())
            self.head_ch.play(head_snd)
        for lay in LAYERS:
            ch = chs[lay]
            snd = self._get(f"{sid}_{phase + 1}_{lay}")
            ch.stop()
            self.level[(slot, lay)] = self.goal[(slot, lay)] = ON[lay]
            self._vol_q.pop((slot, lay), None)
            if snd is None:
                continue
            ch.set_volume(0.0)
            if sil is not None:
                ch.play(sil)
                ch.queue(snd)
            else:
                ch.play(snd)
        self.cur_snd = {lay: self._get(f"{sid}_{phase + 1}_{lay}") for lay in LAYERS}
        self.wait_start = (slot, head_sec > 0)   # 층이 실제로 시작되는 프레임에 마디 시계(loop_t0)를 다시 맞춤

    def _bus(self) -> float:
        from src.audio.adaptive_music import GAIN
        st = self.cfg.get("state_gain", {})
        vb = self.sfx.settings_boss_vol if hasattr(self.sfx, "settings_boss_vol") else 1.0
        return min(1.0, GAIN * st.get("boss", 1.0) * self.sfx.bus_gain("mus") * vb * self.am.zone_gain)

    def _next_bar(self) -> float:
        import math
        k = math.floor((self.t - self.loop_t0) / self.bar + 1e-6) + 1
        return self.loop_t0 + k * self.bar

    def update(self, dt: float) -> None:
        if not self.active:
            if self._steps is not None:
                self.load_step(1)
            return
        self.t += dt
        sid = self.song
        # 페이즈 전환 예약 → 다음 마디 경계에 라이저
        if self.want_phase > self.phase and self.next_at is None and self.t >= self.loop_t0:
            self.next_at = self._next_bar()
        if self.next_at is not None and self.switch_at is None and self.t >= self.next_at:
            riser = self._get(f"{sid}_{self.phase + 1}_riser")
            rl = riser.get_length() if riser is not None else self.bar
            new = 1 - self.slot
            for lay in LAYERS:   # 지금 층은 라이저 마디 동안 사라짐
                self.goal[(self.slot, lay)] = 0.0
                self.fade_rate[(self.slot, lay)] = 1.0 / max(0.1, rl)
            self.phase += 1
            self._start_phase(new, self.phase, rl, riser)
            self.old_slot, self.slot = self.slot, new
            self.switch_at = self.t + rl
        ws = getattr(self, "wait_start", None)
        if ws and ws[1]:   # 앞부분(인트로·라이저)이 끝나고 층이 실제로 나오기 시작한 순간 = 반복 0마디
            ch = next((c for lay, c in self.lay_ch[ws[0]].items() if self.cur_snd.get(lay) is not None), None)
            if ch is not None and ch.get_busy() and ch.get_sound() is self.cur_snd.get(next(
                    lay for lay, c in self.lay_ch[ws[0]].items() if c is ch)):
                self.wait_start = None
                if self.switch_at is not None:
                    self.switch_at = self.t
                else:
                    self.loop_t0 = self.t
        if self.switch_at is not None and self.t >= self.switch_at:
            for ch in self.lay_ch[self.old_slot].values():
                ch.stop()
            self.loop_t0 = self.switch_at
            self.switch_at = self.next_at = None
            self.tired_until = None   # 새 페이즈는 보통 주선율부터
            self._bar_i = None
        # 위기·지침: 마디 경계에서
        if self.loop_t0 is not None and self.t >= self.loop_t0 and self.switch_at is None:
            bar_i = int((self.t - self.loop_t0) / self.bar + 1e-6)
            if getattr(self, "_bar_i", None) != bar_i:
                self._bar_i = bar_i
                if self.crisis != self.crisis_on:
                    self.crisis_on = self.crisis
                if self.tired_req:
                    self.tired_req = False
                    self.tired_until = self.loop_t0 + (bar_i + TIRED_BARS) * self.bar
                elif self.tired_until is not None and self.t >= self.tired_until - 1e-3:
                    self.tired_until = None
                s = self.slot
                self.goal[(s, "perc")], self.goal[(s, "perc_crisis")] = (0.0, 1.0) if self.crisis_on else (1.0, 0.0)
                oct_ = self.tired_until is not None
                self.goal[(s, "lead")], self.goal[(s, "lead_oct")] = (0.0, 1.0) if oct_ else (1.0, 0.0)
                for lay in ("perc", "perc_crisis", "lead", "lead_oct"):
                    self.fade_rate[(s, lay)] = 1.0 / FADE_SEC
        # 반복: 큐가 비면 같은 층을 다시 (지금 슬롯만)
        for lay, ch in self.lay_ch[self.slot].items():
            snd = self.cur_snd.get(lay)
            if snd is not None and ch.get_busy() and ch.get_queue() is None:
                ch.queue(snd)
        # 음량
        bus = self._bus()
        for (s, lay), goal in self.goal.items():
            cur = self.level.get((s, lay), 0.0)
            r = self.fade_rate.get((s, lay), 1.0 / FADE_SEC) * dt
            cur = min(goal, cur + r) if goal > cur else max(goal, cur - r)
            self.level[(s, lay)] = cur
            q = round(min(1.0, cur * bus) * 128)
            if self._vol_q.get((s, lay)) != q:
                self._vol_q[(s, lay)] = q
                self.lay_ch[s][lay].set_volume(q / 128)
        hq = round(bus * 128)
        if self._vol_q.get("head") != hq:
            self._vol_q["head"] = hq
            self.head_ch.set_volume(hq / 128)

    def debug(self) -> dict:
        return {"song": self.song, "phase": self.phase + 1, "crisis": self.crisis_on, "tired": self.tired_until is not None,
                "t": round(self.t, 2), "bar": getattr(self, "_bar_i", None)}
