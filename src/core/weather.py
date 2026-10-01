"""날씨: 게임 시간 3시간마다 바뀐다. 다음 날씨(예보)를 미리 정해 둬서 지도에서 계획할 수 있다.

DESIGN.md 7장: 맑음 60% / 비 30% / 폭풍 10% (낚시터별 보정)
  비: 입질 대기 ÷1.3 / 폭풍: 희귀 이상 ×1.5, 어두움, 번개
  안개 (용문 폭포 전용): 화면이 뿌옇고 입질 그림자가 안 보임
"""
import random

WEATHER_KO = {"clear": "맑음", "rain": "비", "storm": "폭풍", "fog": "안개"}  # 안개: 용문 폭포 전용 (확장)
CHANGE_EVERY = 3.0  # 게임 시간(시)


def roll_weather(weights: dict, rnd=random) -> str:
    keys = list(weights)
    return rnd.choices(keys, [weights[k] for k in keys])[0]


class Weather:
    def __init__(self, current: str, upcoming: str, next_change: float, rnd: random.Random | None = None):
        self.current = current
        self.upcoming = upcoming
        self.next_change = next_change  # 절대 시간 (day*24 + hour)
        self.rnd = rnd or random.Random()
        self.events: list[str] = []

    @staticmethod
    def abs_time(day: int, hour: float) -> float:
        return day * 24 + hour

    def hours_left(self, day: int, hour: float) -> float:
        return max(0.0, self.next_change - self.abs_time(day, hour))

    def update(self, day: int, hour: float, weights: dict) -> None:
        now = self.abs_time(day, hour)
        if self.next_change <= 0:
            self.next_change = (now // CHANGE_EVERY + 1) * CHANGE_EVERY
        while now >= self.next_change:
            old = self.current
            self.current = self.upcoming
            self.upcoming = roll_weather(weights, self.rnd)
            self.next_change += CHANGE_EVERY
            if old != self.current:
                self.events.append(f"change:{self.current}")

    def reroll_upcoming(self, weights: dict) -> None:
        """낚시터를 옮기면 그 지역 기후로 예보를 다시 잡는다 (현재 날씨는 유지)."""
        self.upcoming = roll_weather(weights, self.rnd)

    def to_save(self) -> dict:
        return {"weather": self.current, "weather_next": self.upcoming, "weather_change": self.next_change}
