"""테마 전설 연출 효과음 (DESIGN.md 43-15): 'sfx_<테마>_<이름>' 을 처음 쓸 때 불러 둔다.

찾는 순서: assets/sfx/<테마>/<이름>.ogg|wav (직접 고른 음원) → assets/sfx_generated/<테마>/<이름>.ogg (tools/audio/make_theme_sfx.py)
테마: ilseom (청새치 '일섬' — 스릉 · 챙 · 징 · 바람) · yeoubi (황금잉어 '여우비' — 피아노 '띵—' · 금화 '띵') · sangun (산신 쏘가리 '산군' — 발톱 '촥') · taego (실러캔스 '태고' — 작은 종 '딩')
"""
from src.audio import loader
from src.core.paths import asset_path

NAMES = {"ilseom": ("seureung", "chaeng", "jing", "wind"), "yeoubi": ("piano", "coin"), "sangun": ("claw",), "taego": ("bell",)}


def _path(theme: str, short: str):
    for d in (asset_path("sfx", theme), asset_path("sfx_generated", theme)):
        p = next((d / (short + e) for e in (".ogg", ".wav") if (d / (short + e)).exists()), None)
        if p is not None:
            return p
    return None


def prefetch(sfx, theme: str | None) -> None:
    """전설이 다가올 때 일꾼 스레드에 맡겨 둔다 (src/audio/loader.py — 처음 울리는 순간 끊김 없게)."""
    if not theme or not getattr(sfx, "enabled", False) or theme not in NAMES:
        return
    for short in NAMES[theme]:
        if f"sfx_{theme}_{short}" not in sfx.sounds:
            p = _path(theme, short)
            if p is not None:
                loader.request(p)


def ensure(sfx, theme: str | None) -> None:
    if not theme or not getattr(sfx, "enabled", False) or theme not in NAMES:
        return
    for short in NAMES[theme]:
        name = f"sfx_{theme}_{short}"
        if name in sfx.sounds:
            continue
        p = _path(theme, short)
        if p is not None:
            snd = loader.take(p, wait=True)   # 못 읽어도 게임은 계속 (그 소리만 없음)
            if snd is not None:
                sfx.sounds[name] = snd


def play(sfx, theme: str | None, short: str, volume: float = 1.0, pan=None):
    if not theme:
        return None
    ensure(sfx, theme)
    name = f"sfx_{theme}_{short}"
    return sfx.play(name, volume, pan) if name in sfx.sounds else None
