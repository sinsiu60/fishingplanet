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
    for path in _WINDOWS_FONTS:
        if os.path.exists(path):
            return path
    for name in _FALLBACK_NAMES:
        path = pygame.font.match_font(name)
        if path:
            return path
    return None


def get_font(size: int) -> pygame.font.Font:
    global _font_file, _resolved
    if not _resolved:
        _font_file = _resolve_font_file()
        _resolved = True
    if size not in _cache:
        _cache[size] = pygame.font.Font(_font_file, size)
    return _cache[size]
