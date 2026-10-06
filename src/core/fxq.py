"""화질 단계 (OPTIMIZATION.md O4 · O6): 2 = 높음(지금 그대로, 픽셀 동일) · 1 = 중간 · 0 = 낮음.

설정 `fx_level` 을 게임 루프가 프레임마다 여기에 옮겨 두고, 이펙트 코드는 이 모듈만 본다 (설정 객체를 끌고 다니지 않게).
"높음" 에선 아무것도 줄이지 않는다 — 줄이는 건 중간 · 낮음에서만 (반투명 겹 합치기 · 파티클 상한 · 화면 흔들림 단순화).
"""
_level = 2


def level() -> int:
    return _level


def set_level(v) -> None:
    global _level
    _level = 2 if v is None else max(0, min(2, int(v)))


def particles() -> float:
    """파티클 상한 · 생성률 배율: 높음 1.0 / 중간 0.6 / 낮음 0.3."""
    return (0.3, 0.6, 1.0)[_level]
