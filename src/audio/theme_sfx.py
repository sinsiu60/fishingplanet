"""테마 전설 연출 효과음 (DESIGN.md 43-15): 'sfx_<테마>_<이름>' 을 처음 쓸 때 불러 둔다.

찾는 순서: assets/sfx/<테마>/<이름>.ogg|wav (직접 고른 음원) → assets/sfx_generated/<테마>/<이름>.ogg (tools/audio/make_theme_sfx.py)
테마: ilseom (청새치 '일섬' — 스릉 · 챙 · 징 · 바람) · yeoubi (황금잉어 '여우비' — 피아노 '띵—' · 금화 '띵')
"""
import pygame

from src.core.paths import asset_path

NAMES = {"ilseom": ("seureung", "chaeng", "jing", "wind"), "yeoubi": ("piano", "coin")}


def ensure(sfx, theme: str | None) -> None:
    if not theme or not getattr(sfx, "enabled", False) or theme not in NAMES:
        return
    for short in NAMES[theme]:
        name = f"sfx_{theme}_{short}"
        if name in sfx.sounds:
            continue
        for d in (asset_path("sfx", theme), asset_path("sfx_generated", theme)):
            p = next((d / (short + e) for e in (".ogg", ".wav") if (d / (short + e)).exists()), None)
            if p is not None:
                try:
                    sfx.sounds[name] = pygame.mixer.Sound(str(p))
                except Exception as e:   # 못 읽어도 게임은 계속 (그 소리만 없음)
                    print("theme sfx:", name, e)
                break


def play(sfx, theme: str | None, short: str, volume: float = 1.0, pan=None):
    if not theme:
        return None
    ensure(sfx, theme)
    name = f"sfx_{theme}_{short}"
    return sfx.play(name, volume, pan) if name in sfx.sounds else None
