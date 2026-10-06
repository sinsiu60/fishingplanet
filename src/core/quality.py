"""화질 설정 (OPTIMIZATION.md O6): 높음 · 중간 · 낮음 한 단계가 여러 설정값을 한꺼번에 정한다.

| 항목                 | 높음 | 중간 | 낮음 |
| 화면 fps (폰)        | 60   | 60   | 30   |
| 배경 애니메이션 갱신 | 15   | 12   | 8    |   → settings bg_fps  (O3 띠 캐시)
| 이펙트 단계          | 2    | 1    | 0    |   → settings fx_level (O4: 비네트 한 장 · 흔들림 · 파티클 ×0.6/×0.3)

설정 `quality` = "high" | "medium" | "low" | None(아직 자동 감지 전). apply() 가 개별 값으로 풀어 쓴다 — 나머지 코드는
bg_fps · fx_level · fps 만 본다. 자동 감지(Game._quality_watch): 처음 10초 평균 fps 로 고르고(안드로이드는 '중간'에서 시작),
그 뒤 낚시 장면에서 30초 동안 목표 fps 에 못 미치면 한 단계 낮추자고 한 번 묻는다.
"""
LEVELS = ("low", "medium", "high")
NAMES = {"high": "높음", "medium": "중간", "low": "낮음"}
PRESET = {"high": {"bg_fps": 15, "fx_level": 2, "fps": 60},
          "medium": {"bg_fps": 12, "fx_level": 1, "fps": 60},
          "low": {"bg_fps": 8, "fx_level": 0, "fps": 30}}


def apply(settings, level: str) -> None:
    if level not in PRESET:
        return
    settings.data["quality"] = level
    for k, v in PRESET[level].items():
        settings.data[k] = v
    settings.save()


def current(settings) -> str | None:
    return settings.get("quality")


def lower(level: str) -> str | None:
    i = LEVELS.index(level) if level in LEVELS else 0
    return LEVELS[i - 1] if i > 0 else None


def pick_by_fps(avg_fps: float, mobile: bool) -> str:
    """처음 10초 평균 fps 로 단계 고르기 (폰은 60fps 상한, PC 는 144 상한이라 기준이 다름)."""
    if mobile:
        return "high" if avg_fps >= 52 else "medium" if avg_fps >= 28 else "low"
    return "high" if avg_fps >= 55 else "medium" if avg_fps >= 35 else "low"
