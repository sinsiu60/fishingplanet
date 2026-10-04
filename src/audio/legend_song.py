"""전설의 노래 (DESIGN.md 34장): 전설 포획 연출 전용 곡 불러오기.

찾는 순서: assets/music/legend_catch_<버전>_<곡ID>.ogg → …_<대륙>.ogg → legend_catch_<버전>.ogg (직접 고른 곡으로 덮어쓰기)
         → assets/music_generated/legend_catch_<버전>_<곡ID>.ogg (전설마다 그 파이팅 곡 조성, DESIGN.md 43)
         → assets/music_generated/legend_catch_<버전>_<대륙>.ogg (tools/audio/make_legend_song.py 합성본)
버전: full / short / loop (final 은 full 곡). 보상 버스 'legend_song_*' — 속도·피치·필터 변경 없이 그대로 (AS_IS).
곡ID = 전설 전용 파이팅 곡 ID (L01~L12). 없으면 대륙판.
"""
import pygame

from src.core.paths import asset_path


def path_of(variant: str, cont: str, sid: str | None = None):
    variant = "full" if variant == "final" else variant
    tags = ([sid] if sid else []) + [cont]
    cands = [asset_path("music", f"legend_catch_{variant}_{t}.ogg") for t in tags] + [asset_path("music", f"legend_catch_{variant}.ogg")]
    for t in tags:
        cands += [asset_path("music_generated", f"legend_catch_{variant}_{t}.ogg"), asset_path("music_generated", f"legend_catch_{variant}_{t}.wav")]
    for p in cands:
        if p.exists():
            return p
    return None


def name_of(variant: str, cont: str, sid: str | None = None) -> str:
    return f"legend_song_{'full' if variant == 'final' else variant}_{sid or cont}"


def preload(sfx, variant: str, cont: str, sid: str | None = None) -> str | None:
    if not getattr(sfx, "enabled", False):
        return None
    name = name_of(variant, cont, sid)
    if name in sfx.sounds:
        return name
    p = path_of(variant, cont, sid)
    if p is None:
        return None
    try:
        sfx.sounds[name] = pygame.mixer.Sound(str(p))
    except Exception:
        return None
    return name
