"""신호 6계열 소리 (DESIGN.md 32장 S5): 화면을 안 봐도 소리만으로 계열을 알 수 있게, 예고 시간에 맞춰 낸다.

  풀기   빌드업 '웅—'이 단계마다 높아짐 → 행동 silence_sec 전 무음 → 행동 순간 '쉬익!' (돌진·물어뜯기·숨기)
         돌진은 웅크림(crouch_frac) 뒤 줄 펄스 동안만 울린다 (31-14). 가짜 돌진은 울림 없음.
  감기   짧게 올라가는 '딸깍딸깍딸깍'
  타이밍 링이 줄어드는 동안 간격이 좁아지며 높아지는 틱 → 링이 닫히는 순간(점프 정점 = 판정) '띵'
  방향   '휙' — 물고기가 꺾는 쪽 스피커로 (pan)
  참기   '타타타탁'
  제스처 '끼리릭'

시각 보정: 정해진 시각에 내는 소리(빌드업·틱·쉬익·띵)는 설정 '오디오 지연 보정'만큼 일찍 낸다 → 들리는 순간 = 화면 순간.
진동은 Sfx.play(haptic=)가 소리 어택에 맞춘다. 펌핑(박자 북)은 판정 박자와 같은 틱에 따로 낸다 (fishing_scene).
"""
from src.core.config import load_json

TICKS = 6          # sig_timing_tick 단계 수
HUMS = 8           # sig_release_hum 단계 수


class SignalAudio:
    def __init__(self, sfx, sound_on=lambda: True):
        self.sfx = sfx
        self.sound_on = sound_on   # 접근성 '소리 신호' 끄면 소리 없이 진동만
        self.rc = load_json("signals.json")["rush_pulse"]
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

    def start(self, action: str, fam: str, fight) -> None:
        """예고 시작 (telegraph:<action>). 계열마다 바로 내는 소리 + 시간 맞춰 낼 소리 준비."""
        b = fight.brain
        hap = f"sig_{fam}"
        self.curs = [c for c in self.curs if c["a"] != action]
        if fam == "release":
            crouch = self.rc["crouch_frac"] * (self.rc["frenzy_crouch_mult"] if "frenzy" in fight.mutations else 1.0)
            self.curs.append({"a": action, "fam": fam, "hum": -1, "go": False,
                              "start": crouch if action == "rush" else 0.0})
            if action != "rush":
                self._vib(hap)
            return
        if fam == "timing" and action != "pump":
            total = b.time_to_apex()
            if total > 50:   # 정점이 없는 타이밍 행동
                self._play("sig_timing", 0.8, haptic=hap)
                return
            n = max(3, min(7, int(total / 0.16)))
            # 링이 닫힐수록 촘촘해지는 틱 시각 (0 = 지금, 1 = 정점)
            times = [total * (k / n) ** 0.7 for k in range(n)]
            self.curs.append({"a": action, "fam": fam, "times": times, "total": total, "k": 0, "t": 0.0, "ding": False})
            return
        if fam == "direction":
            pan = 0.85 * (b.turn_dir or 0) if action == "turn" else None
            self._play("sig_direction", 0.85, pan=pan, haptic=hap)
        elif fam in ("reel", "endure", "gesture"):
            self._play(f"sig_{fam}", 0.8, haptic=hap)
        elif fam == "timing":   # 펌핑: 박자 북이 따로 — 계열 진동만
            self._vib(hap)

    def on_event(self, ev: str) -> None:
        """행동 시작(action:<a>) — 아직 '쉬익'을 안 냈으면 지금."""
        for c in list(self.curs):
            if c["fam"] == "release" and ev == f"action:{c['a']}":
                if not c["go"]:
                    self._release_go(c)
                self.curs.remove(c)

    def _release_go(self, c: dict) -> None:
        c["go"] = True
        self._play("sig_release_go", 1.0, haptic="bite", strength=1.0)

    def update(self, dt: float, fight) -> None:
        if not self.curs or fight is None:
            return
        off = max(0.0, self.sfx.offset_s)
        for c in list(self.curs):
            if c["fam"] == "release":
                self._update_release(c, fight.brain, off)
            elif self._update_timing(c, dt, off):
                self.curs.remove(c)

    def _update_release(self, c: dict, b, off: float) -> None:
        if b.state != "telegraph" or b.pending != c["a"] or c["go"]:
            return  # 행동 시작 이벤트가 정리 (취소되면 다음 예고가 덮어씀)
        dur = max(1e-3, b.cur_telegraph)
        t = b.state_t + off
        left = dur - t
        if left <= 0:
            self._release_go(c)
            return
        p = t / dur
        if left <= self.rc["silence_sec"] or p < c["start"]:
            return  # 웅크림 동안 조용, 행동 직전 무음
        q = (p - c["start"]) / max(1e-6, 1 - c["start"])
        i = min(HUMS - 1, int(q * HUMS))
        if i > c["hum"]:
            c["hum"] = i
            rc = self.rc
            self._play(f"sig_release_hum#{i}", 0.55 + 0.35 * q, haptic="pump",
                       strength=rc["haptic_min"] + (rc["haptic_max"] - rc["haptic_min"]) * q)

    def _update_timing(self, c: dict, dt: float, off: float) -> bool:
        c["t"] += dt
        t = c["t"] + off
        while c["k"] < len(c["times"]) and t >= c["times"][c["k"]]:
            k = c["k"]
            step = round(k / max(1, len(c["times"]) - 1) * (TICKS - 1))
            self._play(f"sig_timing_tick#{step}", 0.55 + 0.3 * k / len(c["times"]),
                       haptic="sig_timing" if k == 0 else None)
            c["k"] += 1
        if t >= c["total"]:
            self._play("sig_timing", 0.85)
            return True
        return False
