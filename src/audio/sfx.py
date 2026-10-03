"""효과음 믹서 (DESIGN.md 32장).

소리는 모두 레시피(data/sfx_recipes.json)를 미리 구운 assets/sfx_generated/ 에서 읽는다 (assets/sfx/ 외부 음원이 우선).
예전 실행 중 합성 내장음(약 80종)은 S8에서 모두 새 이름 레시피로 옮기고 지웠다 → 시작이 빠르고 모바일 캐시도 필요 없다.
오디오 장치가 없으면 조용히 무음으로 동작한다.
"""
import numpy as np
import pygame

RATE = 44100
LAZY_SEC = 2.5   # 이보다 긴 소리(환경음 바탕 9초 등)는 처음 쓸 때 읽는다 → 시작 메모리·시간 절반 (폰, v0.8.3)


class _Sounds(dict):
    """이름 → Sound. 긴 소리는 이름만 먼저 등록하고 처음 꺼낼 때 파일을 읽는다."""

    def __init__(self):
        super().__init__()
        self.paths: dict[str, str] = {}

    def add_lazy(self, name: str, path) -> None:
        self.paths[name] = str(path)
        dict.__setitem__(self, name, None)

    def __getitem__(self, name):
        snd = dict.__getitem__(self, name)
        if snd is None:
            try:
                snd = pygame.mixer.Sound(self.paths[name])
            except Exception:
                snd = pygame.mixer.Sound(buffer=bytes(64))  # 못 읽으면 무음
            dict.__setitem__(self, name, snd)
        return snd

    def get(self, name, default=None):
        return self[name] if name in self else default


class Sfx:
    def __init__(self, audio: bool = True):
        self.enabled = False
        self.volume = 0.8
        self.sounds = _Sounds()
        self.loops: dict[str, pygame.mixer.Channel] = {}
        if not audio:
            return  # 안전 모드: 소리 없이 (지난번 시작이 소리 준비 중에 꺼졌을 때)
        try:
            init = pygame.mixer.get_init()
            if init is None:
                pygame.mixer.init(RATE, -16, 2, 512)
                init = pygame.mixer.get_init()
            self.channels = init[2]
            self.rate = init[0]
            self.enabled = True
        except pygame.error:
            return
        self._mixer_setup()
        self._load_assets()

    def _load_assets(self) -> None:
        """새 방식 소리 (DESIGN.md 32장 S2). 우선순위:
        assets/sfx/<이름>.ogg|wav (외부 음원, 기존 이름도 덮어씀) → assets/sfx_generated/<이름> (미리 구운 레시피)
        → 레시피를 지금 합성 (경고). 레시피에 없는 assets/sfx 파일도 그 이름으로 쓴다."""
        from src.audio import synth
        from src.core.paths import asset_path
        self.missing_baked: list[str] = []
        try:
            rec = synth.recipes()
        except (OSError, ValueError):
            rec = {}
        override = {}
        d = asset_path("sfx")
        if d.is_dir():
            for p in d.iterdir():
                if p.suffix.lower() in (".ogg", ".wav"):
                    override[p.stem.replace("__", "#")] = p
        from src.core import bootlog
        self.load_errors: list[str] = []
        for n_done, name in enumerate(sorted(set(rec) | set(override))):
            if n_done % 30 == 0:
                bootlog.mark(f"  효과음 {n_done} ({name})")
            path = override.get(name)
            if path is None:
                for ext in (".ogg", ".wav"):
                    q = asset_path("sfx_generated", name.replace("#", "__") + ext)
                    if q.exists():
                        path = q
                        break
            try:
                if path is not None:
                    if rec.get(name, {}).get("len", 0) >= LAZY_SEC:
                        self.sounds.add_lazy(name, path)
                    else:
                        self.sounds[name] = pygame.mixer.Sound(str(path))
                    continue
            except Exception as e:  # 파일을 못 읽어도 게임은 계속 (그 소리만 대신 합성 또는 무음)
                if not self.load_errors:
                    bootlog.mark(f"  {name} 읽기 실패: {e!r}")
                self.load_errors.append(name)
            if name not in rec:
                continue
            # 구운 파일이 없다: 지금 합성 (tools/bake_sfx.py 를 돌리면 사라지는 경고)
            self.missing_baked.append(name)
            print(f"[sfx] 구운 파일 없음, 실행 중 합성: {name} (python tools/bake_sfx.py)")
            try:
                st = synth.render(rec[name])
                self.sounds[name] = pygame.sndarray.make_sound(self._to_pcm_stereo(st))
            except Exception as e:
                if len(self.missing_baked) == 1:
                    bootlog.mark(f"  {name} 합성 실패: {e!r}")
        from src.audio.reel_audio import load_zings
        load_zings(self, "mid")  # 패턴 성공 지잉 (Z3) — 낚시 화면이 장착 릴 티어로 바꿈

    def _to_pcm_stereo(self, st: np.ndarray) -> np.ndarray:
        """합성 엔진의 스테레오 float → 믹서 형식 (샘플레이트 맞춤, 모노 믹서면 섞음)."""
        if self.rate != RATE:
            idx = np.linspace(0, len(st) - 1, int(len(st) * self.rate / RATE))
            st = np.stack([np.interp(idx, np.arange(len(st)), st[:, c]) for c in range(2)], axis=1)
        pcm = (np.clip(st, -1, 1) * 32767).astype(np.int16)
        if self.channels == 1:
            return pcm.mean(axis=1).astype(np.int16)
        if self.channels > 2:
            return np.repeat(pcm[:, :1], self.channels, axis=1)
        return np.ascontiguousarray(pcm)

    # ───────────────────────── 믹서 (DESIGN.md 32-6, S3) ─────────────────────────
    def _mixer_setup(self) -> None:
        from src.core.config import load_json
        self.cfg = load_json("audio_config.json")
        c = self.cfg
        pygame.mixer.set_num_channels(c["channels"])
        self.n_sig = c["reserved_sig"]
        self.n_mus = c.get("reserved_mus", 0)
        pygame.mixer.set_reserved(self.n_sig + self.n_mus)  # 0~3번 신호 전용, 그 뒤 음악 층 전용 (adaptive_music)
        self.bus_vol = {"master": self.volume, "mus": 1.0, "sfx": 1.0, "amb": 1.0}
        self.sig_boost = False
        self.duck_db = {b: 0.0 for b in c["priority"]}  # 지금 낮춘 양 (dB, 음수)
        self.duck_hold: dict[str, float] = {}
        self.base_duck = {b: 0.0 for b in c["priority"]}  # 계속 낮춤 (파이팅 중 환경음 등)
        self.limiter = 1.0
        self.slow = False
        self.active: list[dict] = []
        self.last_play: dict[str, float] = {}
        self.variants: dict[str, list] = {}
        self.slowed: dict[str, pygame.mixer.Sound] = {}
        self.muffle = False      # 안개: 효과음·환경음 고음을 깎은 '먹먹한' 변형으로 (32장 S7)
        self.muffled: dict[str, pygame.mixer.Sound] = {}
        self._bus_cache: dict[str, str] = {}
        self.clock = 0.0
        from src.platform.detect import IS_ANDROID
        self.latency = c["buffer_mobile" if IS_ANDROID else "buffer_pc"] / max(1, self.rate)  # 출력 버퍼 지연 (초)
        self.offset_s = 0.0      # 설정 '오디오 지연 보정' (game.apply_audio_settings)
        self.haptics = None      # game이 넣어 줌
        self.attack_t: dict[str, float] = {}
        self.budget: int | None = None   # 동시 재생 한도 (N3: 파이팅 3 / 전설 4, None = 없음)
        # N5 공간감: 지금 낚시터의 공간(out/cave/deep, open = 원래 소리)과 그 공간 버전 소리, 물고기 쪽 소리의 먼 버전
        self.space_name = "open"
        self.space_mask: dict[str, float] = {}
        self.space_snd: dict[str, pygame.mixer.Sound] = {}
        self.far_snd: dict[str, pygame.mixer.Sound] = {}
        self.fish_dist = 0.3             # 물고기(또는 찌)까지 거리 0 가까움 ~ 1 멂 (낚시 화면이 넣어 줌)
        self._fish_cache: dict[str, bool] = {}
        self._grade_cache: dict[str, int] = {}
        self.dropped = 0                 # 한도 때문에 안 낸·끊은 소리 수 (검증용)
        self.dropped_names: dict[str, int] = {}

    GRADES = ("small", "normal", "signal", "big")
    SIGNAL = 2
    BUDGET_BUSES = ("sig", "sfx", "reward")

    def grade_of(self, name: str) -> int:
        """강조 등급 (N3): 0 작게 / 1 보통 / 2 신호 / 3 크게 — audio_config.json grade (이름 앞부분 규칙)."""
        g = self._grade_cache.get(name)
        if g is None:
            g = 0
            gc = self.cfg.get("grade", {})
            for i, key in enumerate(self.GRADES):
                if i and any(name.startswith(pre) for pre in gc.get(key, [])):
                    g = i
            self._grade_cache[name] = g
        return g

    def set_budget(self, kind: str | None) -> None:
        """동시 재생 한도 (SOUND_CLEANUP 3-1): 'fight' 일반 파이팅 / 'legend' 전설 / None 없음.
        켜는 순간 이미 한도를 넘게 울리는 소리(파이팅 직전 입질·챔질)는 등급 낮은 것부터 정리한다."""
        if not self.enabled:
            return
        self.budget = self.cfg.get("budget", {}).get(kind) if kind else None
        if self.budget is not None:
            heads = self._heads()
            for e in sorted((e for e in heads if not e["loop"] and self.grade_of(e["name"]) != self.SIGNAL),
                            key=lambda e: (self.grade_of(e["name"]), e["t0"])):
                if len(heads) <= self.budget:
                    break
                self._cut(e)
                heads.remove(e)

    def _heads(self) -> list[dict]:
        """한도에 세는 소리: 반복음 + 한 번 소리의 '마른 부분'(원래 소리 길이 안). 공간 잔향 꼬리는 세지 않는다 (N5)."""
        return [e for e in self.active if e["bus"] in self.BUDGET_BUSES and e["ch"].get_busy()
                and not e["name"].startswith("legacy_") and (e["loop"] or self.clock < e.get("dry", 1e9))]

    def _cut(self, e: dict) -> None:
        e["ch"].fadeout(int(self.cfg["budget"].get("fade_ms", 30)))
        self.active = [a for a in self.active if a is not e]
        self.dropped += 1
        self.dropped_names[e["name"]] = self.dropped_names.get(e["name"], 0) + 1

    def _make_room(self, name: str, bus: str, grade: int | None = None) -> bool:
        """한도가 차 있으면 등급 낮고 오래된 한 번 소리를 끊는다. 새 소리가 더 낮은 등급이면 False (안 냄).
        반복음(드랙 바람)은 '보통' 등급으로 자리를 얻고, 못 얻으면 다음 프레임에 다시 시도된다."""
        if self.budget is None or bus not in self.BUDGET_BUSES or name.startswith("legacy_"):
            return True  # 롤백 소리(legacy_)는 사운드 개편 전처럼 한도 밖 (N1 결정 A)
        live = self._heads()
        if len(live) < self.budget:
            return True
        # 신호는 끊지 않는다 (N6: 크게가 몰리는 순간에도 예고를 놓치지 않게 — 그때만 한도를 잠깐 넘을 수 있음)
        cands = [e for e in live if not e["loop"] and self.grade_of(e["name"]) != self.SIGNAL]
        if not cands:
            return True  # 반복음·신호만 가득 — 끊지 않는다
        g = self.grade_of(name) if grade is None else grade
        victim = min(cands, key=lambda e: (self.grade_of(e["name"]), e["t0"]))
        if self.grade_of(victim["name"]) > g and g != self.SIGNAL:  # 새 소리가 신호면 자리가 없어도 낸다
            self.dropped += 1
            self.dropped_names[name] = self.dropped_names.get(name, 0) + 1
            return False
        self._cut(victim)
        return True

    def set_space(self, spot_id: str | None) -> None:
        """N5: 낚시터 공간 (data/audio_config.json space). 그 공간의 미리 구운 버전만 읽어 둔다 (assets/sfx_space)."""
        if not self.enabled:
            return
        sc = self.cfg.get("space")
        if not sc:
            return
        self.space_spot = spot_id
        sp = sc["spots"].get(spot_id, "open") if spot_id else "open"
        pre = sc["presets"].get(sp, {})
        self.space_mask = dict(pre.get("mask", {}))  # 폭포: 효과음을 살짝 덮는다 (버스 dB)
        use = pre.get("use", sp)
        if use == self.space_name and (self.far_snd or use == "open" and not spot_id):
            return
        self.space_name = use
        self.space_snd, self.far_snd = {}, {}
        if not spot_id:
            return
        from src.core.paths import asset_path
        from src.core import bootlog
        d = asset_path("sfx_space")
        if not d.is_dir():
            return
        import time
        t0 = time.perf_counter()
        for p in d.iterdir():
            if p.suffix.lower() not in (".ogg", ".wav"):
                continue
            name, _, var = p.stem.partition("~")
            name = name.replace("__", "#")
            if name not in self.sounds or var not in (use, use + "_far"):
                continue
            try:
                (self.space_snd if var == use else self.far_snd)[name] = pygame.mixer.Sound(str(p))
            except Exception as e:  # 못 읽으면 원래 소리로
                bootlog.mark(f"  공간 소리 {p.name} 읽기 실패: {e!r}")
        bootlog.mark(f"  공간 {use}: 소리 {len(self.space_snd)} + 먼 소리 {len(self.far_snd)} ({(time.perf_counter() - t0) * 1000:.0f}ms)")

    def is_fish(self, name: str) -> bool:
        f = self._fish_cache.get(name)
        if f is None:
            sc = self.cfg.get("space", {})
            b = name.split("#")[0]
            f = self._fish_cache[name] = any(b == k or (k.endswith("_") and b.startswith(k)) for k in sc.get("fish", []))
        return f

    def _far(self) -> bool:
        return self.fish_dist >= self.cfg.get("space", {}).get("far", {}).get("far_from", 2.0)

    def _base(self, name: str) -> tuple[pygame.mixer.Sound, tuple]:
        """공간·거리에 맞는 원본 소리와 변형 캐시 키 (N5)."""
        if self._far() and name in self.far_snd:
            return self.far_snd[name], (name, self.space_name, "far")
        snd = self.space_snd.get(name)
        if snd is not None:
            return snd, (name, self.space_name)
        return self.sounds[name], (name,)

    def bus_of(self, name: str) -> str:
        b = self._bus_cache.get(name)
        if b is None:
            b = next((bus for pre, bus in self.cfg["bus_rules"] if name.startswith(pre)), "sfx")
            self._bus_cache[name] = b
        return b

    def set_volumes(self, master: float, music: float = 1.0, sfx: float = 1.0, amb: float = 1.0,
                    sig_boost: bool = False) -> None:
        self.volume = master
        if self.enabled:
            self.bus_vol.update(master=master, mus=music, sfx=sfx, amb=amb)
            self.sig_boost = sig_boost

    def bus_gain(self, bus: str, limit: bool = True) -> float:
        """버스 최종 배율: 전체 × 버스 볼륨 × 덕킹 × 리미터 (신호 강조면 신호 ×1.3)."""
        bv = self.bus_vol
        g = bv["master"] * bv.get({"mus": "mus", "amb": "amb"}.get(bus, "sfx"), 1.0)
        if bus == "sig" and self.sig_boost:
            g *= self.cfg["sig_boost_gain"]
        db = self.duck_db.get(bus, 0.0) + self.base_duck.get(bus, 0.0) + self.space_mask.get(bus, 0.0)
        g *= 10 ** (db / 20)
        if limit and bus not in ("sig", "mus"):
            g *= self.limiter
        return g

    def duck(self, kind: str) -> None:
        """순간 덕킹: 신호·챔질·퍼펙트 때 음악·환경음을 잠깐 낮춘다 (sec 동안 유지 후 복귀)."""
        if not self.enabled:
            return
        if kind == "sig" and self.sig_boost:
            kind = "sig_boost"
        d = self.cfg["duck"].get(kind)
        if not d:
            return
        for bus, db in d.items():
            if bus == "sec":
                continue
            self.duck_db[bus] = min(self.duck_db.get(bus, 0.0), db)
            self.duck_hold[bus] = max(self.duck_hold.get(bus, 0.0), d.get("sec", 0.3))

    def set_base_duck(self, kind: str | None) -> None:
        """계속 낮춤 (예: 파이팅 중 환경음 −4dB). None이면 해제."""
        if not self.enabled:
            return
        self.base_duck = {b: 0.0 for b in self.cfg["priority"]}
        if kind:
            for bus, db in self.cfg["duck"].get(kind, {}).items():
                if bus != "sec":
                    self.base_duck[bus] = db

    def _variant(self, name: str) -> pygame.mixer.Sound:
        """반복 소리 변주: 피치 ±2·4% 변형 중 하나 (처음 쓸 때 만들어 둠), 슬로우모션이면 낮고 먹먹한 변형."""
        snd, key = self._base(name)
        if self.slow and self.bus_of(name) in ("sfx", "reward", "amb"):
            if key not in self.slowed:
                self.slowed[key] = self._resampled(snd, self.cfg["slowmo"]["pitch"], self.cfg["slowmo"]["lowpass"])
            return self.slowed[key]
        if self.muffle and self.bus_of(name) in ("sfx", "reward", "amb"):
            return self._muffled(name)
        if name not in self.cfg["variation"]["names"]:
            return snd
        if key not in self.variants:
            self.variants[key] = [snd] + [self._resampled(snd, 1 + p / 100) for p in self.cfg["variation"]["pitch_pct"]]
        import random
        return random.choice(self.variants[key])

    def _muffled(self, name: str) -> pygame.mixer.Sound:
        snd, key = self._base(name)
        if key not in self.muffled:
            self.muffled[key] = self._resampled(snd, 1.0, self.cfg["fog_lowpass"])
        return self.muffled[key]

    def _resampled(self, snd: pygame.mixer.Sound, ratio: float, lowpass: int = 0) -> pygame.mixer.Sound:
        a = pygame.sndarray.array(snd).astype(np.float32)
        n = max(2, int(len(a) / ratio))
        idx = np.linspace(0, len(a) - 1, n)
        if a.ndim == 1:
            out = np.interp(idx, np.arange(len(a)), a)
            if lowpass > 1:
                out = np.convolve(out, np.ones(lowpass) / lowpass, mode="same")
        else:
            out = np.stack([np.interp(idx, np.arange(len(a)), a[:, c]) for c in range(a.shape[1])], axis=1)
            if lowpass > 1:
                k = np.ones(lowpass) / lowpass
                out = np.stack([np.convolve(out[:, c], k, mode="same") for c in range(out.shape[1])], axis=1)
        return pygame.sndarray.make_sound(np.ascontiguousarray(np.clip(out, -32768, 32767).astype(np.int16)))

    def _free(self) -> tuple[int, pygame.mixer.Channel] | None:
        """예약(신호·음악 층) 뒤의 빈 채널. pygame(안드로이드 2.6)·pygame-ce 둘 다 되게 번호로 직접 찾는다."""
        for i in range(self.n_sig + self.n_mus, pygame.mixer.get_num_channels()):
            ch = pygame.mixer.Channel(i)
            if not ch.get_busy():
                return i, ch
        return None

    def _channel(self, bus: str) -> tuple[int, pygame.mixer.Channel] | None:
        """(채널 번호, 채널). 신호는 예약 채널(0~3). 없으면 우선순위가 같거나 낮은 것 중 가장 덜 중요하고 오래된 소리를 끊는다.
        Channel 객체는 부를 때마다 새로 만들어지고 pygame 2.6 에는 Channel.id 가 없다 → 번호(idx)를 같이 들고 다닌다."""
        prio = self.cfg["priority"][bus]
        if bus == "sig":
            for i in range(self.n_sig):
                ch = pygame.mixer.Channel(i)
                if not ch.get_busy():
                    return i, ch
            olds = [e for e in self.active if e["bus"] == "sig" and not e["loop"]]
            if olds:
                e = min(olds, key=lambda e: e["t0"])
                e["ch"].stop()
                return e["idx"], e["ch"]
            return 0, pygame.mixer.Channel(0)
        got = self._free()
        if got is not None:
            return got
        cands = [e for e in self.active if not e["loop"] and e["bus"] != "sig" and e["prio"] >= prio
                 and e["ch"].get_busy()]
        if not cands:
            return None
        e = max(cands, key=lambda e: (e["prio"], -e["t0"]))
        e["ch"].stop()
        return e["idx"], e["ch"]

    def play(self, name: str, volume: float = 1.0, pan: float | None = None, haptic: str | None = None,
             strength: float = 1.0) -> pygame.mixer.Channel | None:
        """효과음 한 번. pan: -1(왼쪽)~1(오른쪽). 같은 소리 동시 3개·최소 간격·우선순위 채널·변주 적용.
        haptic: 진동 종류 — 소리의 어택(처음 큰 소리) 순간에 맞춰 울린다 (출력 지연 + 보정 + 어택 시각, 32장 S5)."""
        ch = self._play(name, volume, pan)
        if haptic and self.haptics is not None:
            delay = self.latency + self.offset_s + self.attack_of(name) if ch is not None else 0.0
            self.haptics.vibrate(haptic, strength, delay=max(0.0, delay))
        return ch

    def attack_of(self, name: str) -> float:
        """소리가 처음 최대 음량의 절반에 닿는 시각 (초, 최대 1.5초). 처음 쓸 때 계산해 둔다."""
        t = self.attack_t.get(name)
        if t is None:
            t = 0.0
            snd = self.sounds.get(name)
            if snd is not None:
                a = np.abs(pygame.sndarray.array(snd)[: int(self.rate * 1.5)].astype(np.int32))
                if a.ndim > 1:
                    a = a.max(axis=1)
                if len(a) and a.max() > 0:
                    t = float(np.argmax(a >= a.max() * 0.5)) / self.rate
            self.attack_t[name] = t
        return t

    def _play(self, name: str, volume: float, pan: float | None) -> pygame.mixer.Channel | None:
        if not self.enabled or name not in self.sounds:
            return None
        c = self.cfg
        mi = c["min_interval"]
        gap = mi.get(name, mi.get(name.split("#")[0], mi["default"]))  # 단계 소리(#)는 바탕 이름 규칙
        if self.clock - self.last_play.get(name, -9.0) < gap:
            return None
        same = [e for e in self.active if e["name"] == name and e["ch"].get_busy()]
        if len(same) >= c["max_same"]:
            oldest = min(same, key=lambda e: e["t0"])
            oldest["ch"].stop()
        bus = self.bus_of(name)
        if not self._make_room(name, bus):
            return None
        got = self._channel(bus)
        if got is None:
            return None
        idx, ch = got
        snd = self._variant(name)
        snd.set_volume(1.0)
        if name in c["variation"]["names"]:
            import random
            volume *= 10 ** (random.uniform(-1, 1) * c["variation"]["vol_db"] / 20)
        if getattr(self, "boost", 1) >= 2 and bus == "sig":
            volume *= 2.0  # 투명 변이: 예고 소리 +6dB
        if self.is_fish(name):  # N5 거리감: 물고기 쪽 소리는 멀수록 작게 (먼 버전은 _base 가 둔하게)
            volume *= 1 - self.cfg["space"]["far"]["far_vol"] * max(0.0, min(1.0, self.fish_dist))
        ch.play(snd)
        e = {"ch": ch, "idx": idx, "name": name, "bus": bus, "prio": c["priority"][bus], "t0": self.clock,
             "vol": volume, "pan": pan, "loop": False, "dry": self.clock + self.sounds[name].get_length()}
        self.active = [a for a in self.active if a["idx"] != idx]  # 같은 채널의 예전 기록은 버림
        self.active.append(e)
        self.last_play[name] = self.clock
        self._apply(e)
        if bus == "sig":
            self.duck("sig")
        return ch

    def _apply(self, e: dict) -> None:
        """채널 음량 반영. 값이 실제로 바뀔 때만 set_volume (믹서 단위 1/128로 비교).
        폰에선 set_volume 마다 오디오 장치를 잠가서(패닝 효과 등록) 매 프레임 수십 번 부르면 파이팅이 끊겼다 (v0.8.8)."""
        v = min(1.0, e["vol"] * self.bus_gain(e["bus"]))
        if e["pan"] is None:
            lr = (v, None)
        else:
            a = (max(-1.0, min(1.0, e["pan"])) + 1) * np.pi / 4
            lr = (min(1.0, v * np.cos(a) * 1.41), min(1.0, v * np.sin(a) * 1.41))
        q = (round(lr[0] * 128), None if lr[1] is None else round(lr[1] * 128))
        if e.get("_q") == q:
            return
        e["_q"] = q
        if lr[1] is None:
            e["ch"].set_volume(lr[0])
        else:
            e["ch"].set_volume(lr[0], lr[1])

    def update(self, dt: float, slow: bool = False) -> None:
        """매 프레임: 덕킹 복귀, 끝난 소리 정리, 리미터, 루프·재생 중 소리 볼륨 갱신."""
        if not self.enabled:
            return
        self.clock += dt
        self.slow = slow
        for bus in list(self.duck_db):
            if self.duck_hold.get(bus, 0) > 0:
                self.duck_hold[bus] -= dt
            elif self.duck_db[bus] < 0:
                self.duck_db[bus] = min(0.0, self.duck_db[bus] + dt * 30)  # 초당 30dB로 복귀
        self.active = [e for e in self.active if e["ch"].get_busy() and e["ch"].get_sound() is not None]
        self.bus_vol["master"] = self.volume
        total = sum(min(1.0, e["vol"] * self.bus_gain(e["bus"], limit=False))
                    for e in self.active if e["bus"] not in ("sig", "mus"))
        lim = self.cfg["limiter"]
        want = min(1.0, (lim["max_sum"] / total) ** 0.5) if total > 0 else 1.0  # 부드럽게 (제곱근)
        if want < self.limiter:
            self.limiter = want
        else:
            self.limiter = min(want, self.limiter + dt / lim["release_sec"])
        for e in self.active:
            self._apply(e)
        mv = round(min(1.0, self.bus_gain("mus") * getattr(self, "music_gain", 0.6)) * 128)
        if mv != getattr(self, "_music_q", None):  # 스트리밍 음악 음량도 바뀔 때만
            self._music_q = mv
            pygame.mixer.music.set_volume(mv / 128)

    def stop_all(self) -> None:
        """효과음·환경음 전부 멈춤 (음악 층 예약 채널은 그대로 — adaptive_music이 따로 관리)."""
        if self.enabled:
            for i in range(pygame.mixer.get_num_channels()):
                if not (self.n_sig <= i < self.n_sig + self.n_mus):
                    pygame.mixer.Channel(i).stop()
            self.active.clear()
        self.loops.clear()

    def loop(self, name: str, on: bool, volume: float = 1.0) -> None:
        """반복 재생 켜기/끄기. 켜진 채로 다시 부르면 볼륨만 바뀐다."""
        if not self.enabled or name not in self.sounds:
            return
        e = self.loops.get(name)
        if on:
            bus = self.bus_of(name)
            snd = self._muffled(name) if self.muffle and bus == "amb" else self._base(name)[0]  # 안개면 먹먹한 바탕, 공간 버전 (N5)
            if e is not None and e["ch"].get_busy() and e["ch"].get_sound() is snd:
                e["vol"] = volume
                self._apply(e)
                return
            if e is not None:
                e["ch"].stop()
                self.loops.pop(name, None)
                self.active = [a for a in self.active if a is not e]
            if not self._make_room(name, bus, grade=1):
                return
            got = self._channel(bus) if bus == "sig" else self._free() or self._channel(bus)
            if got is None:
                return
            idx, ch = got
            snd.set_volume(1.0)
            ch.play(snd, loops=-1)
            e = {"ch": ch, "idx": idx, "name": name, "bus": bus, "prio": self.cfg["priority"][bus], "t0": self.clock,
                 "vol": volume, "pan": None, "loop": True}
            self.active = [a for a in self.active if a["idx"] != idx]
            self.active.append(e)
            self.loops[name] = e
            self._apply(e)
        elif e is not None:
            e["ch"].stop()
            self.loops.pop(name, None)

    def stats(self) -> dict:
        """사운드 테스트 룸·검증용: 버스별 재생 중 수, 리미터, 덕킹."""
        out = {b: 0 for b in self.cfg["priority"]}
        for e in self.active:
            out[e["bus"]] += 1
        return {"busy": out, "limiter": round(self.limiter, 2), "duck": {k: round(v, 1) for k, v in self.duck_db.items() if v}}
