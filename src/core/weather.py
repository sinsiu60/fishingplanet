"""날씨: (낚시터, 3시간 칸)마다 미리 정해진 예보표 (TIME_REST.md 🅰, DESIGN.md 48장).

DESIGN.md 7장: 맑음 60% / 비 30% / 폭풍 10% (낚시터별 보정)
  비: 입질 대기 ÷1.3 / 폭풍: 희귀 이상 ×1.5, 어두움, 번개
  안개 (용문 폭포 전용): 화면이 뿌옇고 입질 그림자가 안 보임

칸 번호 block = floor((day × 24 + hour) / 3).
weather_at(seed, spot, weights, block) = roll_weather(weights, Random(f"{seed}:{spot}:{block}")) — 저장 없이 과거 · 미래 어느 칸이든 같은 값.
쉬기 · 이동 · 다시 불러오기를 섞어도 같은 칸은 같은 날씨 (예전 '쉬기 연타 = 날씨 뽑기' 없앰). 세이브엔 weather_seed 하나만.
덮어쓰기 (weather_override = {"weather", "from", "until"} 절대 시각): 날씨 소모품(게임 12시간) · F5 디버그 · 측정 도구 — 그 동안만 모든 낚시터에서 그 날씨.
"""
import random

WEATHER_KO = {"clear": "맑음", "rain": "비", "storm": "폭풍", "fog": "안개"}  # 안개: 용문 폭포 전용 (확장)
CHANGE_EVERY = 3.0  # 게임 시간(시) = 예보표 칸 하나 (game_config time.weather_block_hours)


def roll_weather(weights: dict, rnd=random) -> str:
    keys = list(weights)
    return rnd.choices(keys, [weights[k] for k in keys])[0]


def block_of(t: float) -> int:
    """절대 시각(day*24 + hour) → 3시간 칸 번호."""
    return int(t // CHANGE_EVERY)


def weather_at(seed: int, spot: str, weights: dict, block: int) -> str:
    return roll_weather(weights, random.Random(f"{seed}:{spot}:{block}"))


def ensure_seed(data: dict) -> int:
    """세이브마다 한 번 만드는 날씨 씨앗 (없으면 지금 만들어 저장 — 옛 세이브는 처음 불러올 때 한 번 날씨가 바뀔 수 있음)."""
    if not isinstance(data.get("weather_seed"), int):
        data["weather_seed"] = random.randrange(1, 2 ** 31)
    return data["weather_seed"]


class Weather:
    """겉은 예전과 같음 (current · upcoming · next_change · hours_left · events 'change:<날씨>'), 속은 예보표."""

    def __init__(self, data: dict, spot: str, weights: dict):
        self.data = data            # 세이브 dict (weather_seed · weather_override)
        self.seed = ensure_seed(data)
        self.spot = spot
        self.weights = weights
        self.current: str | None = None
        self.upcoming = "clear"
        self.next_change = 0.0      # 절대 시간 (day*24 + hour)
        self.events: list[str] = []

    @staticmethod
    def abs_time(day: int, hour: float) -> float:
        return day * 24 + hour

    # ── 예보표 ──
    def override(self) -> dict | None:
        o = self.data.get("weather_override")
        return o if isinstance(o, dict) and o.get("weather") else None

    def at_block(self, block: int, spot: str | None = None, weights: dict | None = None) -> str:
        """그 칸의 날씨 (덮어쓰기가 칸 시작을 덮으면 그 날씨)."""
        o = self.override()
        t = block * CHANGE_EVERY
        if o and o["from"] <= t < o["until"]:
            return o["weather"]
        return weather_at(self.seed, spot or self.spot, weights or self.weights, block)

    def at_time(self, t: float, spot: str | None = None, weights: dict | None = None) -> str:
        o = self.override()
        if o and o["from"] <= t < o["until"]:
            return o["weather"]
        return weather_at(self.seed, spot or self.spot, weights or self.weights, block_of(t))

    def forecast(self, day: int, hour: float, hours: float = 48, spot: str | None = None,
                 weights: dict | None = None) -> list[tuple[int, str]]:
        """지금 칸부터 hours 시간 = [(칸 번호, 날씨)…] (지금 칸은 지금 날씨 — 덮어쓰기 포함)."""
        now = self.abs_time(day, hour)
        b0 = block_of(now)
        n = int(round(hours / CHANGE_EVERY))
        out = [(b0, self.at_time(now, spot, weights))]
        out += [(b, self.at_block(b, spot, weights)) for b in range(b0 + 1, b0 + n)]
        return out

    def set_override(self, weather: str, t_from: float, t_until: float) -> None:
        self.data["weather_override"] = {"weather": weather, "from": t_from, "until": t_until}

    # ── 예전 겉모양 ──
    def hours_left(self, day: int, hour: float) -> float:
        return max(0.0, self.next_change - self.abs_time(day, hour))

    def set_spot(self, spot: str, weights: dict) -> None:
        """이동: 그 낚시터의 예보표로 (다시 뽑지 않음). 날씨가 다르면 change 이벤트는 update 가 냄."""
        self.spot, self.weights = spot, weights

    def update(self, day: int, hour: float, weights: dict | None = None) -> None:
        if weights is not None:
            self.weights = weights
        now = self.abs_time(day, hour)
        o = self.override()
        if o and now >= o["until"]:
            self.data.pop("weather_override", None)
            o = None
        cur = self.at_time(now)
        nxt = (block_of(now) + 1) * CHANGE_EVERY
        if o and o["from"] <= now < o["until"]:
            nxt = min(nxt, o["until"]) if o["until"] > now else nxt
        if self.current is not None and cur != self.current:
            self.events.append(f"change:{cur}")
        self.current = cur
        self.next_change = nxt
        self.upcoming = self.at_time(nxt)

    def to_save(self) -> dict:
        """세이브엔 씨앗만 (weather_seed 는 data 에 이미 있음) — 옛 weather · weather_next · weather_change 는 지움."""
        for k in ("weather", "weather_next", "weather_change"):
            self.data.pop(k, None)
        return {}
