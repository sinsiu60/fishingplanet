"""한글 폰트 로더. Windows 맑은 고딕 우선, 없으면 시스템 한글 폰트로 대체."""
import os

import pygame

_WINDOWS_FONTS = [
    r"C:\Windows\Fonts\malgun.ttf",
    r"C:\Windows\Fonts\malgunbd.ttf",
    r"C:\Windows\Fonts\gulim.ttc",
]
_FALLBACK_NAMES = [
    "malgungothic", "applesdgothicneo", "applegothic", "nanumgothic",
    "notosanscjkkr", "notosanskr", "notosanscjk", "wenquanyizenhei", "unifont",
]

_font_file: str | None = None
_resolved = False
_cache: dict[int, pygame.font.Font] = {}


def _resolve_font_file() -> str | None:
    from src.platform.detect import IS_MOBILE, IS_WEB
    if IS_MOBILE or IS_WEB:
        # 안드로이드엔 맑은 고딕이 없다 → 앱에 넣은 Noto Sans KR (tools/make_mobile_font.py). 미리보기도 같은 폰트.
        from src.core.paths import data_path
        bundled = data_path("fonts", "NotoSansKR-Subset.ttf")
        if bundled.exists():
            return str(bundled)
    for path in _WINDOWS_FONTS:
        if os.path.exists(path):
            return path
    for name in _FALLBACK_NAMES:
        path = pygame.font.match_font(name)
        if path:
            return path
    # 한글 시스템 폰트가 없는 리눅스(CI의 안드로이드 스플래시 그림 등) → 게임에 넣은 Noto Sans KR
    from src.core.paths import data_path
    bundled = data_path("fonts", "NotoSansKR-Subset.ttf")
    return str(bundled) if bundled.exists() else None


def get_font(size: int) -> pygame.font.Font:
    global _font_file, _resolved
    if not _resolved:
        _font_file = _resolve_font_file()
        _resolved = True
    if size not in _cache:
        _cache[size] = pygame.font.Font(_font_file, size)
    return _cache[size]
