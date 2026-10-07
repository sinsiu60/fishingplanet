"""수면 징후 (DESIGN.md 27-6, Phase U7). 수치는 data/lure.json.

루어 액션(저킹 · 리트리브 · 멈춤 리듬)은 사용자 요청으로 삭제 (DESIGN 47장). 남은 것:
profile_of   물고기 습성 분류 — 물거품 징후가 '멈춤(바닥)형' 물고기 가중치를 올릴 때만 씀.
SurfaceSigns 대기 중 가끔 나타나는 수면 징후 4종. 찌와 가까울수록(정확도) 확률을 조금 보정한다.
"""
import math
import random

from src.core.config import load_json

PROFILES = ("jerk_fast", "jerk_slow", "retrieve", "pause", "mixed")


def cfg() -> dict:
    return load_json("lure.json")


def profile_of(fish: dict) -> str:
    """물고기 습성 분류 (jerk_fast · jerk_slow · retrieve · pause · mixed): 개별 지정 > 이름 > 행동 습성. 물거품 징후(pause_mult)만 씀."""
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
