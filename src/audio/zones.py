"""소리 구역 (AUDIO_ZONES.md, DESIGN.md 39): 바깥(마을·낚시터) ↔ 실내(건물 안 5곳).

구역은 장면 스택에서 정한다 — 건물 안 대화 화면(InteriorScene, 집 HomeScene 포함)이 있으면 그 건물의 실내 구역, 없으면 바깥.
그 위에 뜨는 상점 패널·이름 입력·종이 같은 창은 구역을 바꾸지 않는다 (같은 실내). 마을에서 여는 의뢰 게시판·도감·상점 창은 바깥 그대로.
작별 페이드(나가기)가 시작되는 순간부터 바깥으로 돌아가기 시작한다 (화면 페이드 0.4초와 소리 전환을 같은 때에).

하는 일 (매 프레임 Game 이 update):
  - sfx.indoor (0 바깥 ~ 1 실내)를 0.4초에 걸쳐 바꿈 → 믹서가 바깥·실내 버전 반복음 음량 비율을 바꾸고, 환경음 조각·천둥은 실내 버전으로
  - 바깥 음악(adaptive)은 멈추지 않고 zone_gain 으로 0.8초 페이드 → 나오면 그 자리부터 (마디가 이어짐)
  - 장소 음악: 라디오(-8dB) · 집 잔잔한 곡(한 곡 뒤 1~2분 정적) · 공방 패드 · 서재 오르골(3분마다) · 오두막 없음
  - 실내 전용 소리: 방 공기 · 지붕 빗소리(비/폭풍) · 창문 틈 바람(폭풍) + 장소별 (시계·삐걱·릴·화로·그물·수정·책장·촛불)
  - 실내에 있는 동안 바깥 환경음(마을 바탕·조각·날씨)을 계속 돌림 (마을 화면은 멈춰 있으므로)
  - 폭풍 천둥: 마을·실내 모두. 실내 창문 있는 곳(집·낚시점)은 창밖이 0.1초 약하게 번쩍 → 0.5~1.5초 뒤 먹먹한 천둥 + 창문 덜컹
    (번쩍임은 최소 간격, '화면 효과 줄이기'면 없음)
  - 문 소리: 들어갈 때 0초 문 열기(바깥 버전) · 0.5초 문 닫기(실내 '툭'), 나올 때 0초 문 열기(실내 버전)
"""
import random

from src.core.config import load_json


class AudioZones:
    def __init__(self, game):
        self.game = game
        self.cfg = load_json("audio/zones.json")
        self.tr = self.cfg["transition"]
        self.by_npc = {z["npc"]: zid for zid, z in self.cfg["zones"].items() if z.get("npc")}
        self.zone: str | None = None        # 지금 실내 구역 (None = 바깥)
        self.k = 0.0                        # 실내 섞임 (sfx.indoor)
        self.t_in = 0.0                     # 들어온 뒤 시간
        self.room_k = 0.0                   # 실내 전용 소리 페이드
        self.music_k = 0.0                  # 장소 음악 페이드
        self.loops: dict[str, float] = {}   # 지금 켜 둔 실내 반복음 → 음량
        self.timers: dict[str, float] = {}
        self.pending: list[list] = []       # [남은 초, 소리, 음량] (문 닫기 등)
        self.song: dict = {}                # 집 음악: {"left": 남은 재생, "rest": 남은 정적}
        self.thunder_t = random.uniform(*self.cfg["thunder"]["every"])
        self.flash_t = 0.0                  # 창밖 번쩍임 남은 시간
        self.last_flash = -99.0
        self.clock = 0.0
        self.rnd = random.Random()
        self.last_zone = None               # 나가는 동안 실내 소리 페이드 아웃에 씀
        self.music_on: str | None = None    # 지금 켜 둔 장소 음악
        self.test: dict | None = None       # 사운드 테스트 룸: {"zone": 구역 id, "weather": 날씨} — 장면 대신 이걸로
        self.prefetch: list[str] = []       # 마을에 있는 동안 그 대륙 건물들의 실내 음악·소리를 한 프레임에 하나씩 미리 읽음
        self.prefetched: set[str] = set()
        self.prefetch_t = 0.0

    # ── 장면 → 구역 ──
    def _interior(self):
        from src.scene.interior import InteriorScene
        for sc in reversed(self.game.scenes.stack):
            if isinstance(sc, InteriorScene):
                return sc
        return None

    def _zone_now(self, sc) -> str | None:
        if sc is None:
            return None
        if sc.leaving is not None and sc.leaving >= 0:
            return None   # 작별 페이드 시작 = 바깥으로 전환 시작
        return self.by_npc.get(sc.npc)

    def zcfg(self, zid: str | None = None) -> dict:
        return self.cfg["zones"].get(zid or self.zone or "", {})

    @property
    def window_flash(self) -> float:
        """창밖 번쩍임 세기 0~1 (창문 있는 실내 배경이 그림)."""
        if not self.zone or not self.zcfg().get("has_window"):
            return 0.0
        return max(0.0, self.flash_t / self.cfg["thunder"]["flash_sec"])

    # ── 전환 ──
    def _enter(self, zid: str) -> None:
        sfx = self.game.sfx
        door = self.cfg["doors"][self.zcfg(zid).get("door_sound", "wood")]
        sfx.play(door["open_out"], 0.7)                                   # 0.0초 문 열기 (바깥, 또렷)
        self.pending.append([self.tr["door_close_at"], door["close_in"], 0.6])   # 0.5초 문 닫기 (실내 '툭')
        self.zone = self.last_zone = zid
        self.t_in = 0.0
        self.timers = {}
        self.song = {"left": 0.0, "rest": 0.0}
        z = self.zcfg(zid)
        m = z.get("music")
        if isinstance(m, dict) and m.get("oneshot_every"):
            self.timers["__music"] = m.get("first", 20)

    def _leave(self) -> None:
        from src.scene.village import VillageScene
        sfx = self.game.sfx
        door = self.cfg["doors"][self.zcfg().get("door_sound", "wood")]
        if any(isinstance(s, VillageScene) for s in self.game.scenes.stack) or self._interior() is not None:
            sfx.play(door["open_in"], 0.65)                               # 0.0초 문 열기 (실내 버전) — 타이틀로 나갈 땐 없음
        self.zone = None
        self.pending = [p for p in self.pending if not p[1].startswith("door_")]

    # ── 매 프레임 ──
    def update(self, dt: float) -> None:
        game = self.game
        sfx = game.sfx
        if not sfx.enabled:
            return   # 타이틀로 나가도(세이브 없음) 바깥으로 되돌린다 — 아래 장면 검사가 구역 없음으로 처리
        self.clock += dt
        self._prefetch(dt)
        sc = self._interior()
        want = self._zone_now(sc)
        if self.test is not None:
            tz = self.test["zone"]
            want = tz if self.cfg["zones"].get(tz, {}).get("type") == "indoor" else None
        if want != self.zone:
            if self.zone is not None:
                self._leave()
            if want is not None:
                self._enter(want)
        indoor = self.zone is not None
        # 실내 섞임 0.4초, 음악 0.8초
        self.k = self._toward(self.k, 1.0 if indoor else 0.0, dt / self.tr["amb_sec"])
        sfx.indoor = self.k
        game.adaptive.zone_gain = self._toward(game.adaptive.zone_gain, 0.0 if indoor else 1.0, dt / self.tr["music_sec"])
        if indoor:
            self.t_in += dt
        # 실내 전용 소리: 들어온 지 0.4초부터 0.4초 페이드 인 / 나가면 0.3초 페이드 아웃
        if indoor and self.t_in >= self.tr["room_in_at"]:
            self.room_k = self._toward(self.room_k, 1.0, dt / self.tr["room_in_sec"])
        elif not indoor:
            self.room_k = self._toward(self.room_k, 0.0, dt / self.tr["room_out_sec"])
        self.music_k = self._toward(self.music_k, 1.0 if indoor and not self._story_music() else 0.0,
                                    dt / self.tr["music_sec"])
        for p in self.pending:
            p[0] -= dt
        for p in [p for p in self.pending if p[0] <= 0]:
            sfx.play(p[1], p[2])
        self.pending = [p for p in self.pending if p[0] > 0]
        f = getattr(sc, "fishing", None) or self._fishing()
        weather = getattr(f, "weather", "clear") if f is not None else "clear"
        if self.test is not None:
            weather = self.test["weather"]
        zc = self.zcfg(self.zone or self.last_zone)
        self._room(dt, zc, weather)
        self._music(dt, zc)
        if self.test is not None and f is not None:
            self._outside(dt, sc, f, self.cfg["zones"][self.test["zone"]], weather)
        elif sc is not None and f is not None:
            self._outside(dt, sc, f, zc, weather)
        self._thunder(dt, weather, sc)
        self.flash_t = max(0.0, self.flash_t - dt)
        if not indoor and self.room_k <= 0 and self.music_k <= 0 and self.k <= 0:
            self.last_zone = None

    def _prefetch(self, dt: float) -> None:
        """마을 화면에 있는 동안: 그 마을 건물들의 장소 음악·실내 소리를 0.25초에 하나씩 미리 읽어 둔다
        (문을 열 때 긴 파일을 처음 읽느라 화면이 멈칫하지 않게 — 폰)."""
        from src.scene.village import VillageScene
        top = self.game.scenes.current
        if not isinstance(top, VillageScene):
            return
        key = top.cfg.get("ambience")
        if key != getattr(self, "prefetch_key", None):
            self.prefetch_key, self.prefetch = key, []
        if not self.prefetch:
            names = []
            for z in self.cfg["zones"].values():
                if z.get("outside") != key or z.get("type") != "indoor":
                    continue
                m = z.get("music")
                if isinstance(m, dict):
                    names.append(m["name"])
                names += [r[0] for r in z.get("room_sounds", []) if not r[0].endswith("#")]
            rc = self.cfg["room_common"]
            names += [rc["air"][0], rc["storm_wind"][0], rc["thunder_rattle"][0]] + [v[0] for v in rc["rain"].values()]
            self.prefetch = [n for n in dict.fromkeys(names) if n not in self.prefetched]
            if not self.prefetch:
                self.prefetch = [""]   # 다 읽음 표시
        self.prefetch_t -= dt
        if self.prefetch_t > 0 or self.prefetch == [""]:
            return
        self.prefetch_t = 0.25
        name = self.prefetch.pop(0)
        self.prefetched.add(name)
        if name in self.game.sfx.sounds:
            self.game.sfx.sounds[name]   # _Sounds: 처음 꺼낼 때 파일을 읽는다
        if not self.prefetch:
            self.prefetch = [""]

    @staticmethod
    def _toward(v: float, goal: float, step: float) -> float:
        return min(goal, v + step) if goal > v else max(goal, v - step)

    def _fishing(self):
        from src.scene.fishing_scene import FishingScene
        return next((s for s in self.game.scenes.stack if isinstance(s, FishingScene)), None)

    def _story_music(self) -> bool:
        """스토리 장면이 음악을 정해 두면(장면의 story_music) 장소 음악은 비켜 준다."""
        return any(getattr(s, "story_music", None) for s in self.game.scenes.stack)

    # ── 실내 전용 소리 ──
    def _room(self, dt: float, zc: dict, weather: str) -> None:
        sfx = self.game.sfx
        want: dict[str, float] = {}
        k = self.room_k
        if k > 0 and zc:
            rc = self.cfg["room_common"]
            want[rc["air"][0]] = rc["air"][1]
            if weather in rc["rain"]:
                want[rc["rain"][weather][0]] = rc["rain"][weather][1]
            if weather == "storm":
                want[rc["storm_wind"][0]] = rc["storm_wind"][1]
            for name, when, vol in zc.get("room_sounds", []):
                if when == "loop":
                    want[name] = vol
                elif self.zone is not None:   # 가끔 (간격 랜덤)
                    t = self.timers.get(name)
                    if t is None:
                        t = self.rnd.uniform(when[0] * 0.3, when[1])
                    t -= dt
                    if t <= 0:
                        t = self.rnd.uniform(*when)
                        snd = name
                        if name.endswith("#"):
                            n = sum(1 for s in sfx.sounds if s.startswith(name[:-1]) and s[len(name) - 1:].isdigit())
                            snd = f"{name[:-1]}{self.rnd.randrange(max(1, n))}"
                        sfx.play(snd, vol * self.rnd.uniform(0.6, 1.0) * k, pan=self.rnd.uniform(-0.5, 0.5))
                    self.timers[name] = t
        for name in set(self.loops) | set(want):
            v = want.get(name, 0.0) * k
            if v <= 0.001:
                if name in self.loops:
                    sfx.loop(name, False)
                    self.loops.pop(name)
                continue
            sfx.loop(name, True, v)
            self.loops[name] = v

    # ── 장소 음악 ──
    def _stop_music(self) -> None:
        if self.music_on:
            self.game.sfx.loop(self.music_on, False)
            self.music_on = None

    def _music(self, dt: float, zc: dict) -> None:
        sfx = self.game.sfx
        m = zc.get("music") if zc else None
        name = m.get("name") if isinstance(m, dict) else None
        if not name or self.music_k <= 0:
            self._stop_music()
            return
        vol = m.get("vol", 0.5) * 10 ** (m.get("db", 0) / 20) * self.music_k
        if m.get("oneshot_every"):   # 서재: 아주 작은 오르골 (3분마다 한 번)
            t = self.timers.get("__music", m.get("first", 20)) - dt
            if t <= 0 and self.zone is not None:
                sfx.play(name, vol)
                t = m["oneshot_every"]
            self.timers["__music"] = t
            return
        if m.get("rest"):            # 집: 한 곡 울리고 1~2분 정적
            s = self.song
            if s.get("rest", 0) > 0:
                s["rest"] -= dt
                self._stop_music()
                return
            if not self.music_on:
                snd = sfx.sounds.get(name)
                s["left"] = snd.get_length() if snd is not None else 60.0
            s["left"] -= dt
            if s["left"] <= 0:
                self._stop_music()
                s["rest"] = self.rnd.uniform(*m["rest"])
                return
        if self.music_on and self.music_on != name:
            self._stop_music()
        sfx.loop(name, True, vol)
        self.music_on = name

    # ── 실내에서 바깥 환경음 계속 ──
    def _outside(self, dt: float, sc, f, zc: dict, weather: str) -> None:
        from src.scene.village import VillageScene
        if self.test is None and (isinstance(self.game.scenes.current, VillageScene) or self.game.scenes.current is f):
            return   # 바깥 화면이 직접 돌림
        key = zc.get("outside") or (self.cfg["zones"].get(self.by_npc.get(getattr(sc, "npc", ""), ""), {}).get("outside"))
        if not key:
            return
        village = getattr(sc, "village", None)
        season = getattr(village, "season", None)
        if season is None:
            from src.core import season as seasons
            season = seasons.current(self.game.settings)
        f.ambience.xfade = self.tr["weather_xfade"]
        f.ambience.update(dt, key, f.clock.period()[0], weather, season=season)

    def force_thunder(self) -> None:
        """사운드 테스트 룸: 지금 천둥 (폭풍일 때)."""
        self.thunder_t = 0.0

    # ── 폭풍 천둥 (마을 · 실내) ──
    def _thunder(self, dt: float, weather: str, sc) -> None:
        from src.scene.village import VillageScene
        th = self.cfg["thunder"]
        f = self._fishing()
        if weather != "storm" or f is None:
            return
        top = self.game.scenes.current
        if self.test is not None:
            weather = self.test["weather"]
        if weather != "storm":
            return
        if not (self.zone is not None or isinstance(top, VillageScene) or self.test is not None):
            return   # 낚시터는 낚시 화면의 번개가 따로
        self.thunder_t -= dt
        if self.thunder_t > 0:
            return
        self.thunder_t = self.rnd.uniform(*th["every"])
        if self.zone is not None:
            if (self.zcfg().get("has_window") and not self.game.settings.get("reduce_fx")
                    and self.clock - self.last_flash >= th["min_gap"]):
                self.flash_t = th["flash_sec"]   # 창밖이 0.1초 약하게 번쩍 (연속 번쩍임 없음)
                self.last_flash = self.clock
            f.ambience.strike(self.rnd.uniform(*th["indoor_delay"]))   # 0.5~1.5초 뒤 먹먹한 천둥 + 창문 덜컹
        else:
            f.ambience.strike()
