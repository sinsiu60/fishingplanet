"""계절 (DESIGN.md 35-4): 실제 날짜의 ISO 주 번호 % 4 → 봄·여름·가을·겨울 (1주 = 계절 1개, 4주에 한 바퀴).

설정 '계절 고정'(season_lock)을 켜면 그 계절로 고정 — 고정 중에는 계절 한정 물고기가 나오지 않는다.
테스트: force(season) 로 강제 (디버그 키).
"""
import datetime

SEASONS = ("spring", "summer", "autumn", "winter")
NAMES = {"sharmion": {"spring": "봄", "summer": "여름", "autumn": "가을", "winter": "겨울"},
         "eldrasion": {"spring": "개화기", "summer": "성하기", "autumn": "수확기", "winter": "극야기"}}
ICON = {"spring": "꽃", "summer": "해", "autumn": "잎", "winter": "눈"}
_forced: str | None = None


def force(season: str | None) -> None:
    global _forced
    _forced = season if season in SEASONS else None


def cycle_forced() -> str:
    """디버그(F12): 봄 → 여름 → 가을 → 겨울 → 실제 날짜 → 봄 …  돌려주는 값 = 이름."""
    order = list(SEASONS) + [None]
    nxt = order[(order.index(_forced) + 1) % len(order)]
    force(nxt)
    return NAMES["sharmion"][nxt] if nxt else "실제 날짜"


def real_season(today: datetime.date | None = None) -> str:
    d = today or datetime.date.today()
    return SEASONS[d.isocalendar()[1] % 4]


def current(settings=None) -> str:
    if _forced:
        return _forced
    lock = settings.get("season_lock") if settings is not None else None
    if lock in SEASONS:
        return lock
    return real_season()


def locked(settings=None) -> bool:
    return _forced is None and settings is not None and settings.get("season_lock") in SEASONS


def name(season: str, cont: str = "sharmion") -> str:
    return NAMES.get(cont, NAMES["sharmion"])[season]


def days_left(today: datetime.date | None = None) -> int:
    """이번 계절(주)이 끝날 때까지 남은 날 (일요일 끝)."""
    d = today or datetime.date.today()
    return 7 - d.isoweekday() + 1
