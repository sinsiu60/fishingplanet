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


class _Font(pygame.font.Font):
    """size() 캐시 (OPTIMIZATION.md O2): 글자 폭 재기는 글리프 배치라 그리기만큼 비싼데 같은 문구를 매 프레임 잰다
    (벤치에서 Font.size 9~21회/프레임). 같은 문구는 한 번만."""

    def __init__(self, *a):
        super().__init__(*a)
        self._sz: dict = {}

    def size(self, text):
        r = self._sz.get(text)
        if r is None:
            if len(self._sz) > 3000:
                self._sz.clear()
            r = self._sz[text] = super().size(text)
        return r


def get_font(size: int) -> pygame.font.Font:
    global _font_file, _resolved
    if not _resolved:
        _font_file = _resolve_font_file()
        _resolved = True
    if size not in _cache:
        _cache[size] = _Font(_font_file, size)
    return _cache[size]
