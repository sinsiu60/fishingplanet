"""신호 6계열 소리 (DESIGN.md 32장 S5): 화면을 안 봐도 소리만으로 계열을 알 수 있게, 예고 시간에 맞춰 낸다.

  풀기   빌드업 '웅—'이 단계마다 높아짐 → 행동 silence_sec 전 무음 → 행동 순간 '쉬익!' (돌진·물어뜯기·숨기)
         돌진은 웅크림(crouch_frac) 뒤 줄 펄스 동안만 울린다 (31-14). 가짜 돌진은 울림 없음.
  감기   짧게 올라가는 '딸깍딸깍딸깍'
  타이밍 링이 줄어드는 동안 간격이 좁아지며 높아지는 틱 → 링이 닫히는 순간(점프 정점 = 판정) '띵'
  방향   '휙' — 물고기가 꺾는 쪽 스피커로 (pan)
  참기   '타타타탁'
  제스처 '끼리릭'

신호음 모드 (SOUND_CLEANUP N2, 설정 '신호음'): 자연음(기본) / 보조음 / 강조.
  자연음  세계에 있는 소리로 — 풀기 '꿀렁' + 줄 떨림 → '촤악' + 드랙 / 감기 줄 '툭' + 다가오는 물살 /
          타이밍 수면 아래 보글(물고기가 물 밖으로 나가면 멈춤) → 정점에 물방울 / 방향 물살 '쏴—'(패닝) /
          참기 팽팽한 줄 '드르르' / 제스처 줄 꼬이는 마찰. 행동 직전 무음은 대형(150cm+)·전설만.
  보조음  자연음 + 계열마다 아주 작고 짧은 보조음 (sig_aux_*). 패턴 숙련도 '처음'(성공 3회 미만)이면 자연음 모드여도 자동.
  강조    예전처럼 또렷한 인공 신호음 (sig_release_hum·sig_timing 등, 행동 직전 무음은 항상).
시각·진동은 세 모드 모두 같다.
보스 (BOSS_ARENA 🅱, DESIGN 51-3): 전설 · 환상 파이팅이면 설정 모드와 상관없이 보스 세트 sig_boss_* (무겁고 날카롭게, 음악을 뚫고).
  시각 · 길이는 그대로 — 소리만 교체. 행동 직전 무음은 항상. 숙련도 '처음'이면 보조음(sig_aux_*) 한 겹.
  예고 시작 = 보스 곡만 −4dB 0.25초, 행동 순간('쾅') · 정점('챙') = −5dB 0.2초 (Sfx.boss_duck — 효과음 · 환경음 · 신호 그대로).
  '쾅'은 행동 이벤트(action:*)에서만 → 화면 임팩트(🅰-4)와 같은 틱, '챙'은 on_hit('apex') 로 장면에 알림 (같은 틱 임팩트).

돌진(rush)은 여기서 소리를 내지 않는다 — fishing_scene._rush_audio 가 줄 펄스 동안 loop_slow(reel_audio tease:
드랙이 슬금슬금)와 'pump' 진동을, 돌진 순간 zing_rise → loop_fast → 정점 drag_fast → reel_stop 을 낸다 (오디오 최종 팩).
'강조' 모드만 예전 legacy_rush_hum0~7 · legacy_rush_go 도 같이.

시각 보정: 정해진 시각에 내는 소리(빌드업·틱·쉬익·띵)는 설정 '오디오 지연 보정'만큼 일찍 낸다 → 들리는 순간 = 화면 순간.
진동은 Sfx.play(haptic=)가 소리 어택에 맞춘다. 펌핑(박자 북)은 판정 박자와 같은 틱에 따로 낸다 (fishing_scene).
"""
from src.core.config import load_json

TICKS = 6          # sig_timing_tick · sig_nat_timing_boil 단계 수
HUMS = 8           # sig_release_hum · sig_nat_release_quiver 단계 수
MODES = ("natural", "assist", "strong")
AUX_VOL = 0.4      # 보조음 음량 (자연음보다 작게)


class SignalAudio:
    def __init__(self, sfx, sound_on=lambda: True, mode=lambda: 0, mastery=lambda: None, boss=lambda fight: False,
                 on_hit=None):
        self.sfx = sfx
        self.boss = boss           # 이 파이팅이 보스전(전설 · 환상 무대)인가
        self.on_hit = on_hit       # 보스 '챙'(정점) 순간 장면에 알림 → 같은 틱 임팩트
        self.log: list = []        # (게임 시각, 이름) — 보스 소리 · 임팩트 같은 틱 확인용 (tools/boss_signal_set.py)
        self.clock = 0.0
        self.sound_on = sound_on   # 접근성 '소리 신호' 끄면 소리 없이 진동만
        self.mode = mode           # 설정 signal_mode: 0 자연음 / 1 보조음 / 2 강조
        self.mastery = mastery     # 세이브 pattern_mastery (훈련 수조에서도 — 두뇌의 mastery 는 훈련 땐 None)
        sig = load_json("signals.json")
        self.rc = sig["rush_pulse"]
        self.first_need = sig["mastery"]["tiers"][1][0]  # 이 횟수만큼 성공하기 전 = 숙련도 '처음'
        self.curs: list[dict] = []  # 진행 중인 시간 맞춤 소리 (이중 패턴이면 둘)

    def stop(self) -> None:
        self.curs = []

    def _vib(self, kind: str, strength: float = 1.0) -> None:
        if self.sfx.haptics is not None:
            self.sfx.haptics.vibrate(kind, strength)

    def _play(self, name: str, vol: float = 0.8, pan: float | None = None, haptic: str | None = None,
              strength: float = 1.0) -> None:
        if self.sound_on():
            self.sfx.play(name, vol, pan, haptic=haptic, strength=strength)
        elif haptic:
            self._vib(haptic, strength)

    def _first(self, action: str) -> bool:
        mastery = self.mastery()
        return mastery is not None and action not in ("lure", "fake_rush") and mastery.get(action, 0) < self.first_need

    def _boss_cfg(self) -> dict:
        from src.render.boss_arena import cfg
        return cfg()["sound"]

    def boss_duck(self, kind: str) -> None:
        d = self._boss_cfg()["duck"][kind]
        if hasattr(self.sfx, "boss_duck"):
            self.sfx.boss_duck(d[0], d[1])

    def mode_for(self, action: str, fight) -> str:
        """이 행동의 신호음 모드. 자연음 모드라도 그 패턴 숙련도가 '처음'이면 보조음. 보스전이면 'boss'(처음이면 'boss+aux')."""
        if fight is not None and action not in ("lure", "fake_rush") and self.boss(fight):
            return "boss+aux" if self._first(action) else "boss"
        m = MODES[max(0, min(len(MODES) - 1, int(self.mode() or 0)))]
        if m == "natural":
            mastery = self.mastery()
            if mastery is not None and action not in ("lure", "fake_rush") and mastery.get(action, 0) < self.first_need:
                m = "assist"
        return m

    def pick(self, action: str, fight, strong: str, natural: str, aux: str | None = None) -> list[tuple[str, float]]:
        """낚시 화면이 직접 내는 신호(펌핑 박자·소리 전용 몸털기·등불 미끼)용: [(이름, 음량 배율)]."""
        m = self.mode_for(action, fight)
        if m.startswith("boss"):
            bv = self._boss_cfg()["vol"] / 0.8
            out = [({"pump": "sig_boss_drum", "leap": "sig_boss_timing_apex"}.get(action, natural), bv)]
            if m == "boss+aux" and aux:
                out.append((aux, AUX_VOL / 0.8))
            return out
        if m == "strong":
            return [(strong, 1.0)]
        out = [(natural, 1.0)]
        if m == "assist" and aux:
            out.append((aux, AUX_VOL / 0.8))
        return out

    def _aux(self, c_or_mode, fam: str, pan: float | None = None) -> None:
        mode = c_or_mode if isinstance(c_or_mode, str) else c_or_mode["mode"]
        if mode in ("assist", "boss+aux"):
            self._play(f"sig_aux_{fam}", AUX_VOL, pan=pan)

    def _big(self, fight) -> bool:
        """행동 직전 0.1초 무음은 대형·전설 물고기만 (자연음·보조음 모드)."""
        return fight.size_cm >= self.rc["big_fish_cm"] or fight.fish.get("rarity") == "legend"

    def _bplay(self, name: str, vol_k: float = 1.0, pan=None, haptic=None, strength: float = 1.0) -> None:
        """보스 세트 소리 (기준 음량 0.9)."""
        self.log.append((round(self.clock, 4), name))
        self._play(name, self._boss_cfg()["vol"] * vol_k, pan=pan, haptic=haptic, strength=strength)

    def start(self, action: str, fam: str, fight) -> None:
        """예고 시작 (telegraph:<action>). 계열마다 바로 내는 소리 + 시간 맞춰 낼 소리 준비."""
        b = fight.brain
        hap = f"sig_{fam}"
        self.curs = [c for c in self.curs if c["a"] != action]
        mode = self.mode_for(action, fight)
        boss = mode.startswith("boss")
        if boss:
            self.boss_duck("telegraph")   # 예고 시작: 보스 곡 −4dB 0.25초
            self.log.append((round(self.clock, 4), f"telegraph:{action}"))
        if action == "rush":
            return  # v0.8.14 롤백: 예전 방식 (fishing_scene._rush_audio — 보스전은 그쪽에서 보스 빌드업)
        strong = mode == "strong"
        if boss:
            self._start_boss(action, fam, fight, mode, hap)
            return
        if fam == "release":
            crouch = self.rc["crouch_frac"] * (self.rc["frenzy_crouch_mult"] if "frenzy" in fight.mutations else 1.0)
            c = {"a": action, "fam": fam, "hum": -1, "go": False, "mode": mode,
                 "silence": strong or self._big(fight), "start": crouch if action == "rush" else 0.0}
            self.curs.append(c)
            self._vib(hap)
            if not strong:
                self._play("sig_nat_release_gulp", 0.7)  # 물이 빨려드는 '꿀렁'
                self._aux(c, fam)
            return
        if fam == "timing" and action != "pump":
            total = b.time_to_apex()
            if total > 50:   # 정점이 없는 타이밍 행동
                self._play("sig_timing" if strong else "sig_nat_timing_boil#5", 0.8, haptic=hap)
                self._aux(mode, fam)
                return
            n = max(3, min(7, int(total / 0.16)))
            # 링이 닫힐수록 촘촘해지는 틱 시각 (0 = 지금, 1 = 정점)
            times = [total * (k / n) ** 0.7 for k in range(n)]
            c = {"a": action, "fam": fam, "times": times, "total": total, "k": 0, "t": 0.0, "ding": False, "mode": mode}
            self.curs.append(c)
            self._aux(c, fam)
            return
        if fam == "direction":
            pan = 0.85 * (b.turn_dir or 0) if action == "turn" else None
            self._play("sig_direction" if strong else "sig_nat_direction", 0.85, pan=pan, haptic=hap)
            self._aux(mode, fam, pan)
        elif fam in ("reel", "endure", "gesture"):
            self._play(f"sig_{fam}" if strong else f"sig_nat_{fam}", 0.8, haptic=hap)
            self._aux(mode, fam)
        elif fam == "timing":   # 펌핑: 박자 소리가 따로 (fishing_scene, pick) — 계열 진동만
            self._vib(hap)

    def _start_boss(self, action: str, fam: str, fight, mode: str, hap: str) -> None:
        b = fight.brain
        if fam == "release":
            self.curs.append({"a": action, "fam": fam, "hum": -1, "go": False, "mode": mode, "silence": True, "start": 0.0})
            self._vib(hap)
            self._aux(mode, fam)
            return
        if fam == "timing" and action != "pump":
            total = b.time_to_apex()
            if total > 50:
                self._bplay("sig_boss_timing_apex", haptic=hap)
                self._aux(mode, fam)
                return
            n = max(3, min(7, int(total / 0.16)))
            times = [total * (k / n) ** 0.7 for k in range(n)]
            self.curs.append({"a": action, "fam": fam, "times": times, "total": total, "k": 0, "t": 0.0, "ding": False,
                              "mode": mode})
            self._aux(mode, fam)
            return
        if fam == "direction":
            pan = 0.85 * (b.turn_dir or 0) if action == "turn" else None
            self._bplay("sig_boss_direction", pan=pan, haptic=hap)
            self._aux(mode, fam, pan)
        elif fam in ("reel", "endure", "gesture"):
            self._bplay(f"sig_boss_{fam}", haptic=hap)
            self._aux(mode, fam)
        elif fam == "timing":
            self._vib(hap)

    def boss_go(self) -> None:
        """보스 '쾅!' (돌진은 장면 _rush_audio 가 행동 순간에 부름). 보스 곡 −5dB 0.2초."""
        self._bplay("sig_boss_release_go", haptic="bite")
        self.boss_duck("action")

    def on_event(self, ev: str) -> None:
        """행동 시작(action:<a>) — 아직 '쉬익'을 안 냈으면 지금."""
        for c in list(self.curs):
            if c["fam"] == "release" and ev == f"action:{c['a']}":
                if not c["go"]:
                    self._release_go(c)
                self.curs.remove(c)

    def _release_go(self, c: dict) -> None:
        c["go"] = True
        if c["mode"].startswith("boss"):
            self.boss_go()
            return
        name = "sig_release_go" if c["mode"] == "strong" else "sig_nat_release_go"  # '쉬익!' / 물살 '촤악' + 드랙
        self._play(name, 1.0, haptic="bite", strength=1.0)

    def update(self, dt: float, fight) -> None:
        self.clock += dt
        if not self.curs or fight is None:
            return
        off = max(0.0, self.sfx.offset_s)
        for c in list(self.curs):
            if c["fam"] == "release":
                self._update_release(c, fight.brain, off)
            elif self._update_timing(c, dt, off, fight.brain):
                self.curs.remove(c)

    def _update_release(self, c: dict, b, off: float) -> None:
        if b.state != "telegraph" or b.pending != c["a"] or c["go"]:
            return  # 행동 시작 이벤트가 정리 (취소되면 다음 예고가 덮어씀)
        dur = max(1e-3, b.cur_telegraph)
        t = b.state_t + off
        left = dur - t
        if left <= 0 and not c["mode"].startswith("boss"):   # 보스 '쾅'은 행동 이벤트에서만 (화면 임팩트와 같은 틱)
            self._release_go(c)
            return
        p = t / dur
        if left <= 0 or ((c["silence"] and left <= self.rc["silence_sec"]) or p < c["start"]):
            return  # 웅크림 동안 조용, 행동 직전 무음 (자연음·보조음은 대형·전설만)
        q = (p - c["start"]) / max(1e-6, 1 - c["start"])
        i = min(HUMS - 1, int(q * HUMS))
        if i > c["hum"]:
            c["hum"] = i
            rc = self.rc
            if c["mode"].startswith("boss"):
                self._bplay(f"sig_boss_release_hum#{i}", 0.8 + 0.2 * q, haptic="pump",
                            strength=rc["haptic_min"] + (rc["haptic_max"] - rc["haptic_min"]) * q)
                return
            if c["mode"] == "strong":
                name, vol = f"sig_release_hum#{i}", 0.55 + 0.35 * q
            else:
                name, vol = f"sig_nat_release_quiver#{i}", 0.45 + 0.4 * q  # 팽팽해지는 줄의 미세한 떨림
            self._play(name, vol, haptic="pump", strength=rc["haptic_min"] + (rc["haptic_max"] - rc["haptic_min"]) * q)

    def _update_timing(self, c: dict, dt: float, off: float, b=None) -> bool:
        c["t"] += dt
        t = c["t"] + off
        strong = c["mode"] == "strong"
        boss = c["mode"].startswith("boss")
        while c["k"] < len(c["times"]) and t >= c["times"][c["k"]]:
            k = c["k"]
            step = round(k / max(1, len(c["times"]) - 1) * (TICKS - 1))
            hap = "sig_timing" if k == 0 else None
            vol = 0.55 + 0.3 * k / len(c["times"])
            if boss:
                self._bplay(f"sig_boss_timing_tick#{step}", 0.75 + 0.25 * k / len(c["times"]), haptic=hap)
            elif strong:
                self._play(f"sig_timing_tick#{step}", vol, haptic=hap)
            elif b is None or b.state == "telegraph":
                self._play(f"sig_nat_timing_boil#{step}", vol, haptic=hap)  # 수면 아래 보글 — 물 밖으로 나가면 멈춤
            elif hap:
                self._vib(hap)
            c["k"] += 1
        if t >= c["total"]:
            if boss:   # '챙!' + 보스 곡 −5dB + 같은 틱 화면 임팩트
                self._bplay("sig_boss_timing_apex")
                self.boss_duck("action")
                self._aux(c, "timing")
                if self.on_hit:
                    self.on_hit("apex")
                return True
            self._play("sig_timing" if strong else "sig_nat_timing_apex", 0.85)  # '띵' / 흩뿌려지는 물방울
            self._aux(c, "timing")
            return True
        return False
