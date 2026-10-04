"""전설의 노래 (DESIGN.md 34장): 전설 포획 연출 전용 곡 불러오기.

찾는 순서: assets/music/legend_catch_<버전>_<대륙>.ogg → assets/music/legend_catch_<버전>.ogg (직접 고른 곡으로 덮어쓰기)
         → assets/music_generated/legend_catch_<버전>_<대륙>.ogg (tools/audio/make_legend_song.py 합성본)
버전: full / short / loop (final 은 full 곡). 보상 버스 'legend_song_*' — 속도·피치·필터 변경 없이 그대로 (AS_IS).
"""
import pygame

from src.core.paths import asset_path


def path_of(variant: str, cont: str):
    variant = "full" if variant == "final" else variant
    for p in (asset_path("music", f"legend_catch_{variant}_{cont}.ogg"),
              asset_path("music", f"legend_catch_{variant}.ogg"),
              asset_path("music_generated", f"legend_catch_{variant}_{cont}.ogg"),
              asset_path("music_generated", f"legend_catch_{variant}_{cont}.wav")):
        if p.exists():
            return p
    return None


def name_of(variant: str, cont: str) -> str:
    return f"legend_song_{'full' if variant == 'final' else variant}_{cont}"


def preload(sfx, variant: str, cont: str) -> str | None:
    if not getattr(sfx, "enabled", False):
        return None
    name = name_of(variant, cont)
    if name in sfx.sounds:
        return name
    p = path_of(variant, cont)
    if p is None:
        return None
    try:
        sfx.sounds[name] = pygame.mixer.Sound(str(p))
    except Exception:
        return None
    return name
