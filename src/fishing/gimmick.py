"""엘드라시온 환경 기믹 (DESIGN.md 23-2). Fight가 매 틱 부른다.

  tangle  갈대 엉킴 : 물고기가 옆(0.3rad 밖)에 1.2초 넘게 머물면 엉킴 게이지 상승 → 가득 차면 1.5초 감기 불가 + 줄 -15%
  dark    어둠      : 그림자 신호 숨김 (예고는 천장 수정 반사광으로 보여줌, 렌더 쪽)
  current 물살      : 장력에 사인파 ±12 (4초 주기) — 다음 마루까지 남은 시간을 HUD로 보여줌
  heat    열 손상   : 파이팅 45초 뒤부터 줄이 초당 0.6%씩, 15초마다 +0.2%p 더 상함 (최대 1.4%)
  ice     얼음 구멍 : 정면 기준 ±0.25rad 밖으로 물고기가 나가면 줄이 초당 2%씩 얼음에 쓸림
세계수(cycle)는 낚시터 쪽에서 시간대로 하나를 골라 넘긴다. 전설 페이즈의 gimmick / gimmick_mult 가 덮어쓴다.
수치는 fishing_config.json "gimmick".
"""
import math

from src.core.config import load_json
from src.core.mathutil import clamp

KO = {"tangle": "갈대 엉킴", "dark": "어둠", "current": "물살", "heat": "열 손상", "ice": "얼음 구멍"}


def cycle_gimmick(period: str, weather: str) -> str:
    """세계수 뿌리 샘: 시간대마다 기믹이 바뀐다 (밤 폭풍이면 얼음)."""
    if period == "night" and weather == "storm":
        return "ice"
    return {"morning": "tangle", "day": "dark", "evening": "current", "night": "heat"}[period]


class Gimmicks:
    def __init__(self, base: str | None):
        self.cfg = load_json("fishing_config.json")["gimmick"]
        self.base = base           # 낚시터 기믹 (세계수는 이미 골라진 것)
        self.tangle = 0.0          # 0~100
        self.side_t = 0.0
        self.reel_lock_t = 0.0
        self.heat_dmg = 0.0        # 지금 초당 줄 손상 (%)
        self.ice_out = False
        self.scrape_t = 0.0
        self.events: list[str] = []

    def kinds(self, brain) -> set[str]:
        g = getattr(brain, "gimmick", None) or self.base
        return set(g.split("+")) if g else set()

    def mult(self, brain) -> float:
        return getattr(brain, "gimmick_mult", 1.0)

    def tension_offset(self, fight) -> float:
        if "current" not in self.kinds(fight.brain):
            return 0.0
        c = self.cfg
        return c["current_amp"] * self.mult(fight.brain) * math.sin(math.tau * fight.elapsed / c["current_period"])

    def next_crest(self, fight) -> float:
        """다음 물살 마루까지 남은 초."""
        p = self.cfg["current_period"]
        phase = (fight.elapsed / p) % 1.0
        return ((0.25 - phase) % 1.0) * p

    def heat_start(self, fight) -> float:
        """열 손상 시작 시각: 기본 45초, 체력이 많은 물고기(전설)는 그만큼 늦게."""
        c = self.cfg
        return max(c["heat_start"], fight.stamina_max * c["heat_start_per_stamina"])

    def update(self, fight, dt: float) -> None:
        c = self.cfg
        b = fight.brain
        kinds = self.kinds(b)
        m = self.mult(b)
        self.reel_lock_t = max(0.0, self.reel_lock_t - dt)
        rel = fight.angle - fight.yaw
        # 갈대 엉킴
        if "tangle" in kinds:
            if abs(rel) > c["tangle_angle"]:
                self.side_t += dt
                if self.side_t > c["tangle_delay"]:
                    self.tangle += c["tangle_rate"] * m * dt
            else:
                self.side_t = 0.0
                self.tangle -= c["tangle_recover"] * dt
            self.tangle = clamp(self.tangle, 0, 100)
            if self.tangle >= 100:
                self.tangle = c["tangle_after"]
                self.reel_lock_t = c["tangle_lock_sec"]
                fight.line -= fight.line_max * c["tangle_line_loss"]
                self.events.append("gimmick:tangle_full")
        else:
            self.tangle = max(0.0, self.tangle - c["tangle_recover"] * dt)
        # 열 손상
        self.heat_dmg = 0.0
        start = self.heat_start(fight)
        if "heat" in kinds and fight.elapsed > start:
            steps = int((fight.elapsed - start) // c["heat_step_sec"])
            self.heat_dmg = min(c["heat_rate_max"], c["heat_rate"] + c["heat_rate_step"] * steps) * m
            fight.line -= fight.line_max * self.heat_dmg / 100 * dt
        # 얼음 구멍
        self.ice_out = "ice" in kinds and abs(rel) > c["ice_hole"]
        if self.ice_out:
            fight.line -= fight.line_max * c["ice_scrape"] / 100 * dt
            self.scrape_t -= dt
            if self.scrape_t <= 0:
                self.scrape_t = 0.6
                self.events.append("gimmick:ice_scrape")
        fight.events.extend(self.events)
        self.events.clear()
