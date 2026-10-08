"""전설 12종 SUNO 보스 곡 재생기 (BOSS_BGM_SUNO.md) + 예전 합성 곡과의 갈림길 (BossRouter).

곡 = assets/music/boss/<곡ID>/ 의 ogg 조각 + markers.json (파일별 마디 시작 시각 bar_starts_sec — 고정 BPM 계산 금지).
  챔질 → intro → phase1_loop 반복 / 다음 페이즈 → 지금 파일의 다음 4마디 경계에서 bridge → 다음 반복 구간
  위기 → 같은 위치로 도는 crisis_perc 층(늘 같이 돌고 음량만) 0.5초 페이드 인(-3dB) · 끝나면 1초 페이드 아웃
  실패 → 즉시 정지 + 낮은 '쿵'(sfx_boss_fail, 1.5초 잔향) / 포획 → 다음 박(일섬은 즉시)에서 ending_hit
  파일 사이 0.15초 크로스페이드 (반복 자체는 같은 채널 queue 라 이음새 없음).
채널: 적응형 음악 예약 채널 4개를 빌린다 — 주 A/B (크로스페이드 짝) + 위기 A/B. 도는 동안 적응형 음악은 멈춤(suspend).
시각: 우리 시계 t(프레임 dt 누적)로 파일 안 위치를 계산 → 전환은 프레임 한 번 안(±8ms) 에서 시작, 크로스페이드가 덮는다.
불러오기: src/audio/loader.py 일꾼 스레드, 쓰는 순서대로 한 파일씩 (OPTIMIZATION.md O5 — 메인은 기다리지 않음). 최근 2곡만 메모리에.
음량: data/music/boss_bgm_gain.json 의 곡별 배율(평균 -14 LUFS · 최대 -1dBTP, 곡 안 모든 파일 같은 배율) × 보스 버스.
환상 공통 곡 (PHANTOM_BGM.md): 색인 "phantom" 하나를 환상 12종이 함께 씀 — intro → loop 를 같은 채널에 queue 로 이어 붙여 틈 없이,
곡 전체(loop)를 반복하고 페이즈 · 위기 변화 없음. 포획은 장면이 즉시 정지 → 정적 → 환상의 노래.
"""
import json
import math

from src.audio import loader
from src.core.paths import asset_path, data_path

CROSS_MS = 150
CRISIS_DB = -3.0
CRISIS_IN, CRISIS_OUT = 0.5, 1.0
PHRASE = 4
KEEP_SONGS = 2
DRIP_BEFORE, DRIP_AFTER = 0.5, 0.8


def _load_json(p):
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def _declick(snd, ms: float = 2.0) -> None:
    """반복 파일 양끝을 아주 짧게(2ms) 페이드 — 끝 → 처음이 이어질 때 파형 단차로 나는 '틱' 을 없앤다 (경계 2ms 만 만지므로 비용 ~0)."""
    try:
        import numpy as np
        import pygame.sndarray
        a = pygame.sndarray.samples(snd)
        n = min(len(a) // 4, int(pygame.mixer.get_init()[0] * ms / 1000))
        if n < 2:
            return
        ramp = np.linspace(0.0, 1.0, n, dtype=np.float32)
        if a.ndim == 1:
            a[:n] = (a[:n] * ramp).astype(a.dtype)
            a[-n:] = (a[-n:] * ramp[::-1]).astype(a.dtype)
        else:
            a[:n] = (a[:n] * ramp[:, None]).astype(a.dtype)
            a[-n:] = (a[-n:] * ramp[::-1][:, None]).astype(a.dtype)
        del a
    except Exception as e:   # 못 만지면 그대로 (웹 등)
        print("declick:", e)


class _Seg:
    """지금 나오는 파일 하나 (주 채널 + 위기 채널)."""

    def __init__(self, name, snd, ch, grid, length, loop, cr_snd=None, cr_ch=None, start=0.0):
        self.name, self.snd, self.ch = name, snd, ch
        self.grid, self.length, self.loop = grid, length, loop
        self.cr_snd, self.cr_ch = cr_snd, cr_ch
        self.start = start      # 시작한 시각 (재생기 시계)

    def pos(self, t: float) -> float:
        p = t - self.start
        if p < 0:   # 아직 앞 파일(환상 공통 곡 intro)이 나오는 중 — 반복 구간 시작 전 (음수 그대로)
            return p
        return p % self.length if self.loop and self.length > 0 else p


class SunoBoss:
    def __init__(self, sfx, adaptive):
        self.sfx = sfx
        self.am = adaptive
        self.enabled = sfx.enabled and adaptive.enabled
        idx = data_path("music", "boss_bgm_index.json")
        self.index = _load_json(idx) if idx.exists() else {"legends": []}
        self.by_fish = {e.get("fish"): e for e in self.index["legends"] if e.get("fish")}
        self.by_sid = {e["id"]: e for e in self.index["legends"]}
        ph = self.index.get("phantom")
        if ph:   # 환상 공통 곡: 12종 모두 같은 곡
            ph = dict(ph, kind="phantom")
            self.by_sid[ph["id"]] = ph
            pj = data_path("phantom.json")
            if pj.exists():
                for f in _load_json(pj).get("fish", []):
                    self.by_fish[f["id"]] = ph
        gp = data_path("music", "boss_bgm_gain.json")
        self.gains = _load_json(gp) if gp.exists() else {}
        self.markers: dict = {}
        self.songs: dict = {}        # sid → {이름: Sound}  (최근 KEEP_SONGS 곡)
        self._order: list = []
        self._steps: dict = {}       # sid → {이름: 경로} 아직 안 읽힌 것
        self._drip_wait = 0.0
        self.loaded_for = None
        if self.enabled:
            chs = list(adaptive.ch.values()) + [adaptive.ch_sting]
            self.ch_main = (chs[0], chs[1])
            self.ch_cr = (chs[2], chs[3])
        self._reset()

    def _reset(self) -> None:
        self.beat_events: list = []   # 화면 박자 펄스 (BOSS_ARENA 🅰-3, 51-2): 'bar' · 'beat' — 장면이 비움
        self._ub = self._ubt = None
        self.t = 0.0
        self.song = None
        self.active = False
        self.phase = 0               # 0부터
        self.want_phase = 0
        self.seg = None              # 지금 파일
        self.sched = None            # (시각, 함수) 예약된 전환 하나
        self.crisis = False
        self.cr_level = 0.0
        self.ending = False
        self._vol_q = {}
        self._late = False
        self._slot = 0
        self.muffle = 0.0            # 환상 2페이즈 컷신 (PHANTOM_PHASE2.md): 물속 버전 비율 0~1
        self.muffle_goal = 0.0
        self.muffle_rate = 1.0

    # ── 곡 정보 ──
    def folder(self, sid: str):
        e = self.by_sid.get(sid)
        return asset_path(*e["folder"].strip("/").split("/")[1:]) if e else None

    def is_sid(self, sid) -> bool:
        return bool(sid) and sid in self.by_sid

    def song_for(self, fish_id: str | None) -> str | None:
        e = self.by_fish.get(fish_id)
        return e["id"] if e and self.available(e["id"]) else None

    def _loop_name(self, sid: str, phase: int = 0) -> str:
        return self.by_sid[sid].get("loop") or f"phase{phase + 1}_loop"

    def _muffled_names(self, sid: str) -> list:
        d = self.folder(sid)
        return [n for n in ("intro_muffled", f"{self._loop_name(sid)}_muffled") if d is not None and (d / f"{n}.ogg").exists()]

    def is_phantom(self, sid) -> bool:
        return bool(sid) and self.by_sid.get(sid, {}).get("kind") == "phantom"

    def available(self, sid: str | None) -> bool:
        if not self.enabled or not self.is_sid(sid):
            return False
        d = self.folder(sid)
        return d is not None and (d / "intro.ogg").exists() and (d / f"{self._loop_name(sid)}.ogg").exists() and (d / "markers.json").exists()

    def spec(self, sid: str) -> dict | None:
        e = self.by_sid.get(sid)
        if not e:
            return None
        return {"kind": e.get("kind", "legend"), "fish": e.get("fish"), "bpm": e.get("bpm"), "phases": [{} for _ in range(int(e.get("phases", 3)))],
                "catch": e.get("catch", {}), "genre": e.get("genre"), "suno": True}

    def n_phases(self, sid: str) -> int:
        return int(self.by_sid[sid].get("phases", 3))

    def _markers(self, sid: str) -> dict:
        m = self.markers.get(sid)
        if m is None:
            m = self.markers[sid] = _load_json(self.folder(sid) / "markers.json")
        return m

    def _grid(self, sid: str, name: str, length: float) -> list:
        """마디 시작 시각 목록 (0초부터). 분석 목록이 첫 마디(0초)를 빼먹은 반복 구간은 앞에 0을 넣고, 파일 길이를 넘는 값은 뺀다."""
        f = self._markers(sid)["files"][name]
        g = [float(x) for x in f.get("bar_starts_sec", [])]
        if f.get("type") == "loop" and (not g or g[0] > 0.3):
            g = [0.0] + g
        g = [x for x in g if x < length - 0.05]
        return g or [0.0]

    def _names(self, sid: str) -> list:
        """읽을 순서: 인트로 · 1페이즈 · 포획 타격 · 그다음 페이즈들."""
        n = self.n_phases(sid)
        m = self._markers(sid)
        if self.is_phantom(sid):   # + 물속 버전 (같은 길이 · 위치 — 2페이즈 컷신)
            return ["intro", self._loop_name(sid)] + self._muffled_names(sid)
        out = ["intro", "phase1_loop", m["crisis_layers"].get("phase1_loop"), "ending_hit"]
        for i in range(2, n + 1):
            out += [f"bridge_{i - 1}to{i}", f"phase{i}_loop", m["crisis_layers"].get(f"phase{i}_loop")]
        return [x if not (x or "").endswith(".ogg") else x[:-4] for x in out if x]

    # ── 불러오기 ──
    def prepare(self, sid: str) -> None:
        if not self.available(sid) or self.loaded_for == sid:
            return
        for p in self._steps.get(self.loaded_for, {}).values():   # 다른 곡을 읽던 중이면 그만
            loader.drop(p)
        self.loaded_for = sid
        if sid in self.songs:
            self._order.remove(sid)
            self._order.append(sid)
            self._steps[sid] = {}
            return
        d = self.folder(sid)
        self.songs[sid] = {}
        self._order.append(sid)
        while len(self._order) > KEEP_SONGS:   # 최근 2곡만
            old = self._order.pop(0)
            if old != self.song:
                for p in self._steps.pop(old, {}).values():
                    loader.drop(p)
                self.songs.pop(old, None)
            else:
                self._order.insert(0, old)
                break
        self._steps[sid] = {n: str(d / f"{n}.ogg") for n in self._names(sid) if (d / f"{n}.ogg").exists()}
        self._drip_wait = 0.0
        self._drip_next(sid)

    def _drip_next(self, sid: str) -> None:
        steps = self._steps.get(sid) or {}
        if any(loader.pending(p) for p in steps.values()):
            return
        for p in steps.values():
            if not loader.ready(p):
                loader.request(p)
                self._drip_wait = DRIP_AFTER if self.active else DRIP_BEFORE
                return

    def load_step(self, dt: float = 0.0, k: int = 1) -> bool:
        sid = self.loaded_for
        if sid is None:
            return True
        steps = self._steps.get(sid) or {}
        for name, p in list(steps.items()):
            if loader.ready(p):
                snd = loader.take(p)
                if snd is not None:
                    if "_loop" in name:   # (환상 공통 곡 loop 는 끝과 처음이 이미 0.5초 섞여 있어 손대지 않음)
                        _declick(snd)   # 반복 경계 '틱' 방지 (양끝 2ms 페이드 — 분석에서 경계 파형 단차 최대 0.76×RMS)
                    self.songs[sid][name] = snd
                del steps[name]
        if not steps:
            return True
        self._drip_wait -= dt
        if self._drip_wait <= 0 or k > 1:
            self._drip_next(sid)
        return False

    def _ready(self, sid: str, names) -> bool:
        snd = self.songs.get(sid, {})
        steps = self._steps.get(sid) or {}
        for n in names:
            if n in snd:
                continue
            p = steps.get(n)
            if p is None:
                if (self.folder(sid) / f"{n}.ogg").exists():
                    return False   # 있는데 아직 맡기지도 않음 (prepare 전)
                continue           # 파일이 없으면 '없는 층'
            if not loader.ready(p):
                return False
        return True

    def _rush(self, sid: str, names) -> None:
        steps = self._steps.get(sid) or {}
        for n in names:
            p = steps.get(n)
            if p is not None and not loader.ready(p):
                loader.request(p)

    def _snd(self, name: str):
        return self.songs.get(self.song, {}).get(name)

    def _phase_names(self, sid: str, phase: int) -> list:
        """phase 0 = 인트로 + 1페이즈 (+위기층), phase ≥ 1 = 브리지 + 그 페이즈 반복 (+위기층)."""
        m = self._markers(sid)
        if self.is_phantom(sid):
            return ["intro", self._loop_name(sid)] + self._muffled_names(sid)
        loop = f"phase{phase + 1}_loop"
        cr = (m["crisis_layers"].get(loop) or "")[:-4]
        head = "intro" if phase == 0 else f"bridge_{phase}to{phase + 1}"
        return [head, loop] + ([cr] if cr else [])

    # ── 시작 · 끝 ──
    def start(self, sid: str) -> bool:
        if not self.available(sid):
            return False
        self.prepare(sid)
        self.load_step()
        need = self._phase_names(sid, 0)
        if not self._ready(sid, need):
            self._rush(sid, need)
            self._late = True
            return False
        if self._late:   # 늦게 준비됨: 일반 파이팅 음악의 다음 마디 경계에서 넘어온다 (O5)
            am = self.am
            if am.enabled and not am.suspended and am.ctx is not None and am.clock + 1 / 30 < am._next_boundary("bar"):
                return False
        self._reset()
        self.song = sid
        self.active = True
        self.am.suspend(True)
        self.sfx.boss_mode = True
        snd = self.songs[sid]
        intro = snd.get("intro")
        loop = snd.get(self._loop_name(sid))
        if self.by_sid[sid].get("gapless_intro") and intro is not None and loop is not None:
            self._start_gapless(intro, loop, snd.get("intro_muffled"), snd.get(f"{self._loop_name(sid)}_muffled"))
        elif intro is not None:
            self._play_seg("intro", intro, loop=False, cross=False)
            self.sched = (self.seg.length, lambda: self._enter_loop(0))
        else:
            self._enter_loop(0)
        return True

    def stop(self, fade_ms: int = 0) -> None:
        if not self.enabled:
            return
        for ch in self.ch_main + self.ch_cr:
            ch.fadeout(fade_ms) if fade_ms else ch.stop()
        was = self.active
        self.active = False
        self.song = None
        self.seg = None
        self.sched = None
        self.sfx.boss_mode = False
        if was:
            self.am.suspend(False)

    def fail(self) -> None:
        if not self.active:
            return
        self.stop()
        self.sfx.play("sfx_boss_fail", 1.0)

    def unload(self) -> None:
        self.stop()
        for steps in self._steps.values():
            for p in steps.values():
                loader.drop(p)
        self._steps = {}
        self.songs = {}
        self._order = []
        self.loaded_for = None

    # ── 바깥 상태 ──
    def set_phase(self, phase: int) -> None:
        self.want_phase = max(self.want_phase, min(phase, self.n_phases(self.song) - 1 if self.song else 0))

    def set_crisis(self, on: bool) -> None:
        self.crisis = bool(on)

    def tired(self) -> None:
        pass   # SUNO 곡엔 옥타브 주선율 층이 없다

    def set_muffle(self, on: bool, sec: float) -> None:
        """환상 2페이즈 컷신: 물속 버전으로 (on) / 원래 버전으로 — sec 초 동안 음량 비율만 바꿈 (멈추거나 처음으로 가지 않음)."""
        self.muffle_goal = 1.0 if on else 0.0
        self.muffle_rate = 1.0 / max(0.01, sec)

    def has_muffled(self) -> bool:
        return self.active and self.seg is not None and self.seg.cr_ch is not None and self.is_phantom(self.song)

    def until_next_bar(self) -> float | None:
        """다음 마디 첫 박까지 초 (intro 재생 중이면 intro 끝 = loop 시작). 곡이 안 돌면 None."""
        if not self.active or self.seg is None:
            return None
        seg = self.seg
        pos = seg.pos(self.t)
        if pos < 0:
            return -pos
        b = next((x for x in seg.grid + [seg.length] if x > pos + 0.02), seg.length)
        return b - pos

    def until_next_beat(self) -> float | None:
        if not self.active or self.seg is None:
            return None
        return max(0.0, self._next_beat() - self.t)

    def _bounds_after(self, lead: float, beats: bool) -> float | None:
        """지금부터 lead 초 뒤 이후 첫 마디(beats = 박) 첫 박까지 초. intro 중이면 intro 끝(= loop 시작)이 첫 마디."""
        if not self.active or self.seg is None:
            return None
        seg = self.seg
        pos = seg.pos(self.t)
        p = pos + max(0.0, lead)
        g = list(seg.grid) or [0.0]
        bpb = max(1, int(self._markers(self.song).get("beats_per_bar", 4)))
        if p <= 0.0:   # intro: 반복 구간 첫 마디 길이로 거꾸로 센 마디(박) — intro 끝 = 마디 첫 박
            step = (g[1] - g[0]) if len(g) > 1 else 2.0
            step = step / bpb if beats else step
            return max(0.0, -step * math.floor(-p / step + 1e-6) - pos)
        if seg.length <= 0:
            return max(0.0, lead)
        if beats:
            ext = g + [seg.length]
            g = [a + (b - a) * j / bpb for a, b in zip(ext, ext[1:]) for j in range(bpb)]
        k = math.floor(p / seg.length) if seg.loop else 0
        r = p - k * seg.length
        b = next((x for x in g if x >= r - 1e-4), None)
        if b is None:
            k, b = k + 1, g[0]
        return max(0.0, k * seg.length + b - pos)

    def until_bar_after(self, lead: float = 0.0) -> float | None:
        return self._bounds_after(lead, False)

    def until_beat_after(self, lead: float = 0.0) -> float | None:
        return self._bounds_after(lead, True)

    def catch(self) -> float:
        """포획 성공: 다음 박(일섬은 즉시)에서 ending_hit. 돌려주는 값 = 타격이 시작되기까지 초.
        환상 공통 곡은 즉시 정지 (정적 → 환상의 노래는 장면이)."""
        if not self.active or self.ending:
            return 0.0
        if self.is_phantom(self.song):
            self.stop()
            return 0.0
        self.ending = True
        self.want_phase = self.phase
        e = self.by_sid[self.song]
        wait = 0.0
        if e.get("catch", {}).get("start", "next_beat") != "immediate" and self.seg is not None:
            wait = max(0.0, self._next_beat() - self.t)
        self.sched = (self.t + wait, self._play_ending)
        return wait

    def catch_info(self, sid: str) -> dict:
        return dict(self.by_sid.get(sid, {}).get("catch", {}))

    # ── 매 프레임 ──
    def update(self, dt: float) -> None:
        if self.loaded_for is not None and self._steps.get(self.loaded_for):
            self.load_step(dt=dt)
        if not self.active:
            return
        self.t += dt
        seg = self.seg
        # 페이즈 전환 예약: 지금 반복 구간의 다음 4마디 경계
        if self.want_phase > self.phase and self.sched is None and seg is not None and seg.loop and not self.ending:
            need = self._phase_names(self.song, self.phase + 1)
            if self._ready(self.song, need):
                nxt = self.phase + 1
                self.sched = (self._next_phrase(), lambda n=nxt: self._enter_bridge(n))
            else:
                self._rush(self.song, need)   # 아직이면 바로 맡기고 다음 프레임에 다시
        # 예약된 전환
        if self.sched is not None and self.t + dt * 0.5 >= self.sched[0]:
            fn = self.sched[1]
            self.sched = None
            fn()
        seg = self.seg
        self._track_beats()
        # 반복: 큐가 비면 같은 파일을 다시 (주 · 위기 같이)
        if seg is not None and seg.loop:
            for ch, snd in ((seg.ch, seg.snd), (seg.cr_ch, seg.cr_snd)):
                if snd is not None and ch.get_busy() and ch.get_queue() is None:
                    ch.queue(snd)
        # 물속 버전 비율 (환상 2페이즈 컷신)
        if self.muffle != self.muffle_goal:
            step = dt * self.muffle_rate
            self.muffle = min(self.muffle_goal, self.muffle + step) if self.muffle_goal > self.muffle else max(self.muffle_goal, self.muffle - step)
        # 위기 층 음량 (0.5초 인 · 1초 아웃) — 환상 공통 곡은 위기 변화 없음 (그 채널은 물속 버전)
        goal = 1.0 if (self.crisis and seg is not None and seg.loop and seg.cr_snd is not None
                       and not self.is_phantom(self.song)) else 0.0
        rate = dt / (CRISIS_IN if goal > self.cr_level else CRISIS_OUT)
        self.cr_level = min(goal, self.cr_level + rate) if goal > self.cr_level else max(goal, self.cr_level - rate)
        if loader.busy():   # 일꾼이 OGG 를 푸는 동안은 믹서가 잠김 → 음량은 다음 프레임에 (O5)
            return
        self._apply_volumes()

    def _track_beats(self) -> None:
        """다음 마디 · 박까지 남은 시간이 갑자기 늘면 = 방금 지남 → beat_events 에 쌓음 (markers.json bar_starts_sec 기준)."""
        if self.seg is None or self.ending:
            self._ub = self._ubt = None
            return
        ub, ubt = self.until_next_bar(), self.until_next_beat()
        if ub is not None and self._ub is not None and ub > self._ub + 0.05:
            self.beat_events.append("bar")
        if ubt is not None and self._ubt is not None and ubt > self._ubt + 0.03:
            self.beat_events.append("beat")
        self._ub, self._ubt = ub, ubt
        if len(self.beat_events) > 16:
            del self.beat_events[:-4]

    # ── 안쪽 ──
    SUNO_GAIN = 0.95   # 채널 기준 음량 (× 곡별 배율 × 음악 설정 × 전설 음량 설정 × 소리 구역). 합성 보스 곡(0.35 × 1.04 ≈ 0.36)보다 +8.4dB —
                       # SUNO 파일은 이미 -14 LUFS 로 마스터링돼 있고 파이팅 동안은 음악이 주인공이라 거의 그대로 내보낸다

    def _bus(self) -> float:
        g = self.gains.get(self.song or "", {}).get("gain", 1.0)
        vb = self.sfx.settings_boss_vol if hasattr(self.sfx, "settings_boss_vol") else 1.0
        return min(1.0, self.SUNO_GAIN * g * self.sfx.bus_gain("mus") * vb * self.am.zone_gain
                   * (self.sfx.boss_duck_gain() if hasattr(self.sfx, "boss_duck_gain") else 1.0))   # 보스 예고음 덕킹 (51-3)

    def _apply_volumes(self) -> None:
        bus = self._bus()
        seg = self.seg
        if seg is None:
            return
        want = {seg.ch: bus}
        if seg.cr_ch is not None and self.is_phantom(self.song):   # 원래 ↔ 물속: 같은 위치, 음량 비율만 (두 버전 같은 배율)
            want = {seg.ch: bus * (1.0 - self.muffle), seg.cr_ch: bus * self.muffle}
        elif seg.cr_ch is not None:
            want[seg.cr_ch] = bus * self.cr_level * (10 ** (CRISIS_DB / 20))
        for ch, v in want.items():
            q = round(v * 128)
            key = id(ch)
            if self._vol_q.get(key) != q:
                self._vol_q[key] = q
                ch.set_volume(q / 128)

    def _other(self, pair, ch):
        return pair[1] if ch is pair[0] else pair[0]

    def _play_seg(self, name: str, snd, loop: bool, cross: bool, cr_name: str | None = None) -> None:
        """다른 주 채널에 새 파일을 틀고(크로스페이드) 이전 파일은 사라짐. 반복 구간이면 위기 층도 같은 프레임에."""
        prev = self.seg
        ch = self._other(self.ch_main, prev.ch) if prev is not None else self.ch_main[0]
        cr_ch = self._other(self.ch_cr, prev.cr_ch) if prev is not None and prev.cr_ch is not None else self.ch_cr[0]
        length = snd.get_length()
        grid = self._grid(self.song, name, length)
        bus = self._bus()
        fade = CROSS_MS if cross else 0
        if prev is not None:
            prev.ch.fadeout(CROSS_MS) if cross else prev.ch.stop()
            if prev.cr_ch is not None:
                prev.cr_ch.fadeout(CROSS_MS) if cross else prev.cr_ch.stop()
        ch.set_volume(bus)
        self._vol_q[id(ch)] = round(bus * 128)
        ch.play(snd, fade_ms=fade)
        cr_snd = self._snd(cr_name) if cr_name else None
        if cr_snd is not None:
            cr_ch.set_volume(0.0)
            self._vol_q[id(cr_ch)] = 0
            cr_ch.play(cr_snd)
        else:
            cr_ch = None
        self.seg = _Seg(name, snd, ch, grid, length, loop, cr_snd, cr_ch, start=self.t)

    def _start_gapless(self, intro, loop, intro_m=None, loop_m=None) -> None:
        """환상 공통 곡: 같은 채널에 intro 를 틀고 loop 를 queue — 끝나는 순간 틈 없이 이어짐 (원곡과 똑같이).
        그 뒤 반복은 update 가 큐가 빌 때마다 같은 loop 를 다시 queue.
        물속 버전(있으면)은 위기 채널에서 같은 프레임에 같은 방식으로 늘 같이 돌고(음량 0) 2페이즈 컷신이 음량 비율만 바꿈."""
        ch = self.ch_main[0]
        bus = self._bus()
        ch.set_volume(bus)
        self._vol_q[id(ch)] = round(bus * 128)
        mch = self.ch_cr[0] if (intro_m is not None and loop_m is not None) else None
        if mch is not None:
            mch.set_volume(0.0)
            self._vol_q[id(mch)] = 0
        ch.play(intro)
        if mch is not None:
            mch.play(intro_m)
        ch.queue(self._fade_in_copy(loop))   # 첫 반복만: 머리 3ms 페이드인 (intro 끝이 3ms 페이드아웃이라 바로 이으면 '틱')
        if mch is not None:
            mch.queue(self._fade_in_copy(loop_m))
        name = self._loop_name(self.song)
        length = loop.get_length()
        self.phase = 0
        self.muffle = self.muffle_goal = 0.0
        self.seg = _Seg(name, loop, ch, self._grid(self.song, name, length), length, True,
                        loop_m if mch is not None else None, mch, start=self.t + intro.get_length())

    _FADE_COPY: dict = {}

    def _fade_in_copy(self, snd, ms: float = 3.0):
        """같은 소리의 복사본 — 머리 ms 만 0 → 1 로 (intro → loop 첫 이음새용, 그 뒤 반복은 원본: 끝 → 처음이 이미 매끈)."""
        key = id(snd)
        c = self._FADE_COPY.get(key)
        if c is None:
            try:
                import numpy as np
                import pygame
                a = pygame.sndarray.array(snd).copy()
                n = min(len(a), int(pygame.mixer.get_init()[0] * ms / 1000))
                if n > 1:
                    ramp = np.linspace(0.0, 1.0, n)
                    a[:n] = (a[:n] * (ramp[:, None] if a.ndim > 1 else ramp)).astype(a.dtype)
                c = pygame.sndarray.make_sound(a)
            except Exception:
                c = snd
            if len(self._FADE_COPY) > 4:
                self._FADE_COPY.clear()
            self._FADE_COPY[key] = c
        return c

    def _enter_loop(self, phase: int) -> None:
        name = self._loop_name(self.song, phase)
        snd = self._snd(name)
        if snd is None:
            return
        cr = (self._markers(self.song)["crisis_layers"].get(name) or "")[:-4] or None
        self.phase = phase
        self._play_seg(name, snd, loop=True, cross=self.seg is not None, cr_name=cr)   # 인트로 · 브리지 → 반복: 0.15초 크로스페이드

    def _enter_bridge(self, phase: int) -> None:
        name = f"bridge_{phase}to{phase + 1}"
        snd = self._snd(name)
        if snd is None:   # 브리지 파일이 없으면 바로 다음 반복 구간
            self._enter_loop(phase)
            return
        self._play_seg(name, snd, loop=False, cross=True)
        self.phase = phase   # 브리지부터 다음 페이즈로 친다 (HUD · 디버그)
        self.sched = (self.t + self.seg.length, lambda p=phase: self._enter_loop(p))

    def _play_ending(self) -> None:
        snd = self._snd("ending_hit")
        if snd is None:
            self.stop(300)
            return
        self._play_seg("ending_hit", snd, loop=False, cross=True)
        self.sched = (self.t + self.seg.length + 0.05, lambda: self.stop(0))

    def _next_phrase(self) -> float:
        """지금 반복 파일의 다음 4마디 경계 (재생기 시계)."""
        seg = self.seg
        pos = seg.pos(self.t)
        bounds = [g for i, g in enumerate(seg.grid) if i % PHRASE == 0] + [seg.length]
        b = next((x for x in bounds if x > pos + 0.02), seg.length)
        k = max(0, math.floor((self.t - seg.start) / seg.length)) if seg.loop and seg.length > 0 else 0
        return seg.start + k * seg.length + b

    def _next_beat(self) -> float:
        seg = self.seg
        pos = seg.pos(self.t)
        g = seg.grid
        bpb = int(self._markers(self.song).get("beats_per_bar", 4))
        # 지금 마디와 그 길이 (마지막 마디는 앞 마디 길이로, 첫 마디 앞(브리지 · 인트로의 들어가는 박)은 첫 마디 길이로 거꾸로)
        i = max(0, max((j for j, x in enumerate(g) if x <= pos), default=0))
        bar_len = (g[i + 1] - g[i]) if i + 1 < len(g) else ((g[i] - g[i - 1]) if i > 0 else seg.length)
        beat = bar_len / max(1, bpb)
        nb = g[i] + math.ceil((pos - g[i]) / beat + 1e-6) * beat
        if nb <= pos + 0.02:
            nb += beat
        k = max(0, math.floor((self.t - seg.start) / seg.length)) if seg.loop and seg.length > 0 else 0
        return seg.start + k * seg.length + nb

    def debug(self) -> dict:
        seg = self.seg
        bar = None
        if seg is not None:
            pos = seg.pos(self.t)
            bar = sum(1 for x in seg.grid if x <= pos) if pos >= 0 else 0
        return {"song": self.song, "phase": self.phase + 1, "crisis": self.cr_level > 0.01, "tired": False,
                "t": round(self.t, 2), "bar": bar, "file": (seg.name if seg.pos(self.t) >= 0 else "intro") if seg else None, "suno": True}


class BossRouter:
    """물고기마다 SUNO 곡(있으면) 또는 예전 합성 곡(BossMusic). 장면은 이것 하나만 본다."""

    def __init__(self, sfx, adaptive):
        from src.audio.boss_music import BossMusic
        self.old = BossMusic(sfx, adaptive)
        self.suno = SunoBoss(sfx, adaptive)
        self.enabled = self.old.enabled or self.suno.enabled
        self.cur = None

    def _impl(self, sid):
        return self.suno if self.suno.is_sid(sid) else self.old

    def is_suno(self, sid) -> bool:
        return self.suno.is_sid(sid) and self.suno.available(sid)

    def prepare_for_spot(self, spot_id: str, fish_list) -> None:
        """낚시터 진입: 그 낚시터 전설의 SUNO 곡을 백그라운드로 읽기 시작 (BOSS_BGM_SUNO.md 미리 불러오기)."""
        for f in fish_list:
            if f.get("rarity") == "legend" and f.get("spot") == spot_id:
                sid = self.suno.song_for(f["id"])
                if sid and not self.suno.active:
                    self.suno.prepare(sid)
                return

    def catch(self) -> float:
        return self.suno.catch() if self.suno.active else 0.0

    def catch_info(self, sid) -> dict:
        return self.suno.catch_info(sid) if self.suno.is_sid(sid) else {}

    def song_for(self, fish_id):
        return self.suno.song_for(fish_id) or self.old.song_for(fish_id)

    def available(self, sid) -> bool:
        return self._impl(sid).available(sid)

    def spec(self, sid):
        return self._impl(sid).spec(sid)

    def timing(self, sid, phase: int = 0):
        return self.old.timing(sid, phase) if not self.suno.is_sid(sid) else (0.5, 2.0)

    def prepare(self, sid) -> None:
        self._impl(sid).prepare(sid)

    def start(self, sid) -> bool:
        impl = self._impl(sid)
        other = self.old if impl is self.suno else self.suno
        if other.active:
            other.stop()
        ok = impl.start(sid)
        if ok:
            self.cur = impl
        return ok

    @property
    def active(self) -> bool:
        return self.old.active or self.suno.active

    @property
    def song(self):
        return self.suno.song if self.suno.active else self.old.song

    @property
    def loaded_for(self):
        return self.cur.loaded_for if self.cur is not None else (self.suno.loaded_for or self.old.loaded_for)

    @property
    def cfg(self):
        return self.old.cfg

    def _live(self):
        return self.suno if self.suno.active else self.old

    def stop(self, fade_ms: int = 0) -> None:
        for impl in (self.old, self.suno):
            if impl.active:
                impl.stop(fade_ms)

    def fail(self) -> None:
        self._live().fail()

    def unload(self) -> None:
        self.old.unload()
        self.suno.unload()

    def set_phase(self, phase: int) -> None:
        self._live().set_phase(phase)

    def set_crisis(self, on: bool) -> None:
        self._live().set_crisis(on)

    def tired(self) -> None:
        self._live().tired()

    def load_step(self, *a, **k):
        return self._impl(self.loaded_for).load_step(*a, **k) if self.loaded_for else True

    def update(self, dt: float) -> None:
        self.old.update(dt)
        self.suno.update(dt)

    def debug(self) -> dict:
        return self._live().debug()

    def __getattr__(self, name):   # 그 밖의 것은 예전 재생기 (테스트 도구 등)
        return getattr(self.old, name)
