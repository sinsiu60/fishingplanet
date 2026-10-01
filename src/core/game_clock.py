"""게임 내 시간. 하루 = 실제 day_length_sec 초. T키로 가속(테스트용)."""
from src.core.config import game_config

# DESIGN.md 7장: 아침 06–10 / 낮 10–17 / 저녁 17–20 / 밤 20–06
PERIODS = [(6.0, "morning", "아침"), (10.0, "day", "낮"), (17.0, "evening", "저녁"), (20.0, "night", "밤")]


class GameClock:
    def __init__(self):
        cfg = game_config()["time"]
        self.hour = cfg["start_hour"]
        self.day_length = cfg["day_length_sec"]
        self.fast_mult = cfg["fast_mult"]
        self.fast = False
        self.day = 1

    def update(self, dt: float) -> None:
        mult = self.fast_mult if self.fast else 1.0
        self.hour += dt * 24.0 / self.day_length * mult
        if self.hour >= 24.0:
            self.hour -= 24.0
            self.day += 1

    def period(self) -> tuple[str, str]:
        """(id, 한글 이름)."""
        result = PERIODS[-1]
        for start, pid, name in PERIODS:
            if self.hour >= start:
                result = (start, pid, name)
        return result[1], result[2]

    def label(self) -> str:
        h = int(self.hour)
        m = int((self.hour - h) * 60)
        return f"{h:02d}:{m:02d} {self.period()[1]}"
