"""환경음 (DESIGN.md 32-13, Phase S7): 낚시터 바탕(반복) + 조각 소리를 무작위 간격·무작위 좌우로 섞는다 (data/ambience.json).

  - 조각은 때(낮/밤)를 가린다: 새는 낮(아침~저녁), 풀벌레·부엉이는 밤(20~6시).
  - 날씨: 비·폭풍 = 바탕 하나 더 + 빗방울 조각 (+ 폭풍 바람), 안개 = 믹서 '먹먹' (환경음·효과음 고음 깎음) + 조각 드물게·바탕 작게.
  - 천둥: 번개(섬광) 뒤 거리만큼 늦게 — 가까우면 빨리·크게 '쩍', 멀면 늦게·작게 '우르릉' (thunder_delay).
  - 파이팅 중: 조각 간격 ×2.5 (바탕은 믹서가 계속 −4dB), 전설이면 전체 ×0.4.
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

    def _frags(self, spot: str, weather: str, season: str | None = None) -> list:
        out = list(self.cfg["spots"].get(spot, {}).get("frags", []))
        out += self.cfg["weather"].get(weather, {}).get("frags", [])
        if season and not spot.startswith(("deep", "crystal_cave")):   # 계절 환경음 (35-4) — 심해·동굴은 없음
            out += load_json("seasons.json")["ambience"].get(season, [])
        return out

    def stop(self) -> None:
        for name in self.beds:
            self.sfx.loop(name, False)
        self.beds = {}
        self.key = None
        self.thunder = []
        self.sfx.muffle = False

    def strike(self) -> float:
        """번개가 쳤다 → 천둥 예약. 돌려주는 값 = 시간차(초)."""
        lo, hi = self.cfg["thunder"]["delay"]
        d = self.rnd.uniform(lo, hi)
        near = d < self.cfg["thunder"]["near_below"]
        k = 1 - (d - lo) / (hi - lo)
        self.thunder.append([d, "amb_thunder_near" if near else "amb_thunder_far", 0.55 + 0.45 * k])
        return d

    def update(self, dt: float, spot: str, period: str, weather: str, fighting: bool = False,
               legend: bool = False, season: str | None = None) -> None:
        c = self.cfg
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
        for name in list(self.beds):
            if name not in want:
                self.sfx.loop(name, False)
        for name, vol in want.items():
            self.sfx.loop(name, True, vol)
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
                        n = sum(1 for k in self.sfx.sounds if k.startswith(name))
                        snd = f"{name}{self.rnd.randrange(max(1, n))}"
                    self.sfx.play(snd, vol * self.rnd.uniform(0.7, 1.0) * mult,
                                  pan=self.rnd.uniform(-c["pan"], c["pan"]))
            self.timers[name] = t
        for th in self.thunder:
            th[0] -= dt
        for th in [x for x in self.thunder if x[0] <= 0]:
            self.sfx.play(th[1], th[2])
        self.thunder = [x for x in self.thunder if x[0] > 0]
