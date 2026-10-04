"""환상의 노래 (DESIGN.md 33-11): 환상어 포획 연출 전용 곡 불러오기·재생.

찾는 순서: assets/music/phantom_catch_<버전>_<대륙>.ogg → assets/music/phantom_catch_<버전>.ogg (직접 고른 곡으로 덮어쓰기)
         → assets/music_generated/phantom_catch_<버전>_<대륙>.ogg (tools/audio/make_phantom_song.py 합성본)
버전: full / short / extended / loop. 보상 버스 'phantom_song_*' — 속도·피치·필터 변경 없이 그대로 (AS_IS).
"""
import pygame

from src.core.paths import asset_path


def path_of(variant: str, cont: str):
    for p in (asset_path("music", f"phantom_catch_{variant}_{cont}.ogg"),
              asset_path("music", f"phantom_catch_{variant}.ogg"),
              asset_path("music_generated", f"phantom_catch_{variant}_{cont}.ogg"),
              asset_path("music_generated", f"phantom_catch_{variant}_{cont}.wav")):
        if p.exists():
            return p
    return None


def name_of(variant: str, cont: str) -> str:
    return f"phantom_song_{variant}_{cont}"


def preload(sfx, variant: str, cont: str) -> str | None:
    """믹서 소리표에 올려 둔다 (환상어 파이팅 시작 때 — 포획 순간 끊김 없게). 이름을 돌려줌."""
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
