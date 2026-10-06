"""환경음 (DESIGN.md 32-13, Phase S7): 낚시터 바탕(반복) + 조각 소리를 무작위 간격·무작위 좌우로 섞는다 (data/ambience.json).

  - 조각은 때(낮/밤)를 가린다: 새는 낮(아침~저녁), 풀벌레·부엉이는 밤(20~6시).
  - 날씨: 비·폭풍 = 바탕 하나 더 + 빗방울 조각 (+ 폭풍 바람), 안개 = 믹서 '먹먹' (환경음·효과음 고음 깎음) + 조각 드물게·바탕 작게.
  - 천둥: 번개(섬광) 뒤 거리만큼 늦게 — 가까우면 빨리·크게 '쩍', 멀면 늦게·작게 '우르릉' (thunder_delay).
  - 파이팅 중: 조각 간격 ×2.5 (바탕은 믹서가 계속 −4dB), 전설이면 전체 ×0.4.
  - 소리 구역 (DESIGN.md 39): 실내(sfx.indoor ≥ 0.5)면 조각·천둥은 미리 구운 실내 버전('~indoor')으로, 실내 버전이 없는 바깥 소리는 내지 않는다.
    실내 천둥엔 창문 덜컹(room_window_rattle)이 같이. 바탕은 믹서가 바깥·실내 버전을 같이 돌린다 (sfx.loop).
  - 날씨·장소가 바뀌면 바탕은 1초 동안 서로 섞이며 바뀐다.
"""
import random

from src.core.config import load_json


class Ambience:
    def __init__(self, sfx, rnd=None):
        self.sfx = sfx
        self.cfg = load_json("ambience.json")
        self.rnd = rnd or random.Random()
        self.beds: dict[str, float] = {}       # 지금 도는 바탕 → 음량
        self.timers: dict[str, float] = {}     # 조각 → 남은 초
        self.key = None
        self.thunder: list[list] = []          # [남은 초, 이름, 음량]
        self.cur: dict[str, float] = {}        # 바탕 지금 음량 (1초 크로스페이드)
        self.span: dict[str, float] = {}       # 바탕마다 마지막 목표 음량 (페이드를 일정한 속도로)
        self.xfade = 1.0

    def _frags(self, spot: str, weather: str, season: str | None = None) -> list:
        out = list(self.cfg["spots"].get(spot, {}).get("frags", []))
        out += self.cfg["weather"].get(weather, {}).get("frags", [])
        if season and not spot.startswith(("deep", "crystal_cave")):   # 계절 환경음 (35-4) — 심해·동굴은 없음
            out += load_json("seasons.json")["ambience"].get(season, [])
        return out

    def stop(self) -> None:
        for name in set(self.beds) | set(self.cur):
            self.sfx.loop(name, False)
        self.beds = {}
        self.cur = {}
        self.key = None
        self.thunder = []
        self.sfx.muffle = False

    def strike(self, delay: float | None = None) -> float:
        """번개가 쳤다 → 천둥 예약. 돌려주는 값 = 시간차(초). delay: 실내처럼 시간차를 정해 줄 때."""
        lo, hi = self.cfg["thunder"]["delay"]
        d = self.rnd.uniform(lo, hi) if delay is None else max(lo, min(hi, delay))
        near = d < self.cfg["thunder"]["near_below"]
        k = 1 - (d - lo) / (hi - lo)
        self.thunder.append([d, "amb_thunder_near" if near else "amb_thunder_far", 0.55 + 0.45 * k])
        return d

    def update(self, dt: float, spot: str, period: str, weather: str, fighting: bool = False,
               legend: bool = False, season: str | None = None) -> None:
        c = self.cfg
        if getattr(self, "_pf_spot", None) != spot:   # 이 낚시터 바탕 + 모든 날씨 바탕 · 천둥을 미리 (날씨가 바뀌는 순간 끊김 없게)
            self._pf_spot = spot
            names = [b[0] for b in [c["spots"].get(spot, {}).get("bed")] + [w.get("bed") for w in c["weather"].values()] if b]
            self.sfx.prefetch(names + ["amb_thunder_near", "amb_thunder_far"])
        fog = weather == "fog"
        self.sfx.muffle = fog
        mult = c["legend_mult"] if legend else 1.0
        want: dict[str, float] = {}
        sp = c["spots"].get(spot)
        if sp and sp.get("bed"):
            want[sp["bed"][0]] = sp["bed"][1] * (c["fog_bed_mult"] if fog else 1.0) * mult
        wb = c["weather"].get(weather, {}).get("bed")
        if wb:
            want[wb[0]] = wb[1] * mult
        # 바탕: 지금 음량 → 목표로 1초 크로스페이드 (새 바탕은 0에서, 빠지는 바탕은 0까지 내려간 뒤 끔)
        for name in set(self.cur) | set(want):
            goal = want.get(name, 0.0)
            cur = self.cur.get(name, 0.0 if self.cur or self.key is not None else goal)
            if goal > 0:
                self.span[name] = goal
            step = dt * max(self.span.get(name, cur), 0.05) / self.xfade
            cur = min(goal, cur + step) if goal > cur else max(goal, cur - step)
            if goal <= 0 and cur <= 0:
                self.sfx.loop(name, False)
                self.cur.pop(name, None)
                self.span.pop(name, None)
                continue
            self.cur[name] = cur
            self.sfx.loop(name, True, cur)
        self.beds = want
        # 조각: 낚시터·날씨가 바뀌면 처음 간격을 새로 뽑는다 (모두 한꺼번에 울리지 않게)
        key = (spot, weather, season)
        frags = self._frags(spot, weather, season)
        if key != self.key:
            self.key = key
            self.timers = {f[0]: self.rnd.uniform(f[1] * 0.3, f[2]) for f in frags}
        night = period == "night"
        slow = (c["fight_interval_mult"] if fighting else 1.0) * (c["fog_interval_mult"] if fog else 1.0)
        for name, lo, hi, vol, when in frags:
            t = self.timers.get(name, hi) - dt
            if t <= 0:
                t = self.rnd.uniform(lo, hi) * slow
                if when == "any" or (when == "night") == night:
                    snd = name
                    if name.endswith("#"):
                        # 'amb_bird#' → amb_bird#0.. / 'amb_chatter#' → amb_chatter0.. (이름에 # 없는 묶음도)
                        pre = name if any(k.startswith(name) for k in self.sfx.sounds) else name[:-1]
                        n = sum(1 for k in self.sfx.sounds if k.startswith(pre) and k[len(pre):].isdigit())
                        snd = f"{pre}{self.rnd.randrange(max(1, n))}"
                    snd = self._zoned(snd)
                    if snd:
                        self.sfx.play(snd, vol * self.rnd.uniform(0.7, 1.0) * mult,
                                      pan=self.rnd.uniform(-c["pan"], c["pan"]))
            self.timers[name] = t
        for th in self.thunder:
            th[0] -= dt
        for th in [x for x in self.thunder if x[0] <= 0]:
            snd = self._zoned(th[1])
            if snd:
                self.sfx.play(snd, th[2])
            if self.indoor():   # 실내: 천둥 저음과 같은 순간 창문 '덜컥' (작게, data/audio/zones.json)
                name, vol = load_json("audio/zones.json")["room_common"]["thunder_rattle"]
                self.sfx.play(name, vol * th[2])
        self.thunder = [x for x in self.thunder if x[0] > 0]

    def indoor(self) -> bool:
        return getattr(self.sfx, "indoor", 0.0) >= 0.5

    def _zoned(self, name: str) -> str | None:
        """실내면 실내 버전 (없으면 None = 내지 않음), 바깥이면 그대로."""
        if not self.indoor():
            return name
        alt = f"{name}~indoor"
        return alt if alt in self.sfx.sounds else None
