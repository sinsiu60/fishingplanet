"""루어 액션 + 수면 징후 (DESIGN.md 27-6, Phase U7). 수치는 data/lure.json.

LureRhythm  플레이어의 대기 중 조작(저킹 / 리트리브 / 멈춤)을 선호 프로필 5종 각각의 점수(-1~1)로 매긴다.
            입질 후보 물고기의 관심도 = 그 물고기 프로필의 점수. (숫자는 안 보이고 그림자 움직임으로만 보인다)
            아무것도 안 했으면(engaged = False) 점수는 그대로 0 → 지금과 같은 대기.
SurfaceSigns 대기 중 가끔 나타나는 수면 징후 4종. 찌와 가까울수록(정확도) 확률을 조금 보정한다.
"""
import math
import random

from src.core.config import load_json

PROFILES = ("jerk_fast", "jerk_slow", "retrieve", "pause", "mixed")


def cfg() -> dict:
    return load_json("lure.json")


def profile_of(fish: dict) -> str:
    """물고기 선호 리듬: 개별 지정 > 이름 > 행동 습성."""
    c = cfg()
    if fish.get("lure"):
        return fish["lure"]
    if fish["id"] in c["overrides"]:
        return c["overrides"][fish["id"]]
    name = fish.get("name", "")
    for key, prof in (("메기", "pause"), ("장어", "pause"), ("아귀", "pause"), ("가오리", "pause"), ("대구", "pause"),
                      ("잉어", "jerk_slow"), ("붕어", "jerk_slow"), ("송어", "retrieve"), ("연어", "retrieve"),
                      ("날치", "retrieve"), ("도미", "mixed"), ("돔", "mixed"), ("농어", "jerk_fast")):
        if key in name:
            return prof
    a = fish.get("actions", {})
    total = sum(a.values()) or 1
    jumpy = (a.get("jump", 0) + a.get("leap", 0) + a.get("thrash", 0)) / total
    if jumpy >= 0.35:
        return "jerk_fast"
    if a.get("charge", 0) / total >= 0.35:
        return "pause"
    if a.get("rush", 0) / total >= 0.45:
        return "retrieve"
    return "jerk_slow" if a.get("turn", 0) / total >= 0.4 else "mixed"


class LureRhythm:
    """대기 한 번(착수~입질) 동안의 리듬 점수."""

    def __init__(self):
        self.c = cfg()["profiles"]
        self.score = {p: 0.0 for p in PROFILES}
        self.engaged = False     # 한 번이라도 움직였나 (안 움직였으면 지금과 똑같다)
        self.used: set = set()   # 쓴 액션 ("jerk", "retrieve", "pause") — 의뢰 '저킹만으로'
        self.jerks: list[float] = []
        self.last_action = -99.0
        self.retrieve_acc = 0.0
        self.idle_beats = 0
        self.pair_t: float | None = None
        self.events: list[str] = []  # "good" / "bad" (그림자 반응)

    def _add(self, prof: str, d: float) -> None:
        self.score[prof] = max(-1.0, min(1.0, self.score[prof] + d))

    def update(self, dt: float, t: float, jerk: bool, retrieving: bool) -> None:
        c = self.c
        before = dict(self.score)
        if jerk:
            self._on_jerk(t)
        if retrieving:
            self.engaged = True
            self.used.add("retrieve")
            self.last_action = t
            self.idle_beats = 0
            self.retrieve_acc += dt
            if self.retrieve_acc >= c["retrieve"]["beat_sec"]:
                self.retrieve_acc -= c["retrieve"]["beat_sec"]
                self._add("retrieve", c["retrieve"]["gain"])
                for p in ("jerk_fast", "jerk_slow"):
                    self._add(p, -c[p]["loss"] * 0.5)
                self._add("pause", -c["pause"]["loss"])
                self._add("mixed", -c["mixed"]["loss"])
                self.pair_t = None
        else:
            self.retrieve_acc = 0.0
        if self.engaged and not jerk and not retrieving:
            idle = t - self.last_action
            pc = c["pause"]
            need = pc["first_sec"] + self.idle_beats * pc["beat_sec"]
            if idle >= need:
                self._add("pause", pc["gain"] if self.idle_beats == 0 else pc["gain_more"])
                self.idle_beats += 1
                self.used.add("pause")
            mc = c["mixed"]
            if self.pair_t is not None and idle >= mc["rest_sec"]:
                self._add("mixed", mc["gain"])
                self.pair_t = None
        for p in PROFILES:
            if self.score[p] > before[p] + 1e-9:
                self.events.append(f"good:{p}")
            elif self.score[p] < before[p] - 1e-9:
                self.events.append(f"bad:{p}")

    def _on_jerk(self, t: float) -> None:
        c = self.c
        self.engaged = True
        self.used.add("jerk")
        self.idle_beats = 0
        prev = self.jerks[-1] if self.jerks else None
        self.jerks = (self.jerks + [t])[-6:]
        self.last_action = t
        if prev is not None:
            gap = t - prev
            for p in ("jerk_fast", "jerk_slow"):
                lo, hi = c[p]["interval"]
                if lo <= gap <= hi:
                    self._add(p, c[p]["gain"])
                elif gap < 4.0:
                    self._add(p, -c[p]["loss"])
            mc = c["mixed"]
            if self.pair_t is not None:
                self._add("mixed", -mc["loss"] * 0.5)  # 세 번째 저킹: 짝이 깨짐
                self.pair_t = None
            elif gap <= mc["pair_sec"]:
                self.pair_t = t
        self._add("retrieve", -c["retrieve"]["loss"])
        if prev is not None and t - prev < self.c["pause"]["first_sec"]:
            self._add("pause", -self.c["pause"]["loss"])

    def current(self) -> str | None:
        """지금 플레이어 리듬에 가장 맞는 프로필 (뚜렷하지 않으면 None)."""
        best = max(PROFILES, key=lambda p: self.score[p])
        return best if self.score[best] >= 0.2 else None


# ───────────────────────── 수면 징후 ─────────────────────────

class SurfaceSigns:
    """대기 중 가끔 하나씩: 새 떼 / 물거품 / 물고기 점프 / 반짝이는 물결."""

    def __init__(self, rnd: random.Random | None = None):
        self.c = cfg()["signs"]
        self.rnd = rnd or random.Random()
        self.sign: dict | None = None
        self.next_t = self.rnd.uniform(*self.c["first_sec"])

    @property
    def radius(self) -> float:
        return self.c["diameter_m"] / 2

    def update(self, dt: float, waiting: bool, yaw: float) -> str | None:
        """새 징후가 생기면 그 종류를 돌려준다."""
        s = self.sign
        if s is not None:
            s["t"] += dt
            if s["t"] >= s["life"]:
                self.sign = None
            return None
        if not waiting:
            return None
        self.next_t -= dt
        if self.next_t > 0:
            return None
        self.next_t = self.rnd.uniform(*self.c["interval_sec"])
        kinds = list(self.c["kinds"])
        kind = self.rnd.choices(kinds, [self.c["kinds"][k]["weight"] for k in kinds])[0]
        ang = yaw + self.rnd.uniform(-0.38, 0.38)
        d = self.rnd.uniform(*self.c["distance_m"])
        self.sign = {"kind": kind, "x": math.sin(ang) * d, "z": math.cos(ang) * d, "t": 0.0,
                     "life": self.rnd.uniform(*self.c["life_sec"])}
        return kind

    def accuracy(self, bx: float, bz: float) -> float:
        s = self.sign
        if s is None:
            return 0.0
        return max(0.0, 1 - math.hypot(bx - s["x"], bz - s["z"]) / self.radius)

    def mods(self, bx: float, bz: float) -> dict:
        """찌 위치에서의 확률 보정 (징후 없거나 멀면 전부 1)."""
        out = {"wait_mult": 1.0, "pause_mult": 1.0, "rare_mult": 1.0, "mutation_mult": 1.0}
        acc = self.accuracy(bx, bz)
        if acc <= 0:
            return out
        k = self.c["kinds"][self.sign["kind"]]
        if "wait_mult" in k:
            out["wait_mult"] = 1 - (1 - k["wait_mult"]) * acc
        if "pause_mult" in k:
            out["pause_mult"] = 1 + (k["pause_mult"] - 1) * acc
        if "rare_mult" in k:
            out["rare_mult"] = 1 + (k["rare_mult"] - 1) * acc
        if "mutation_mult" in k:
            out["mutation_mult"] = 1 + (k["mutation_mult"] - 1) * acc
        return out
