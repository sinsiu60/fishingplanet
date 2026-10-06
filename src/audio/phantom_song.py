"""환상의 노래 (DESIGN.md 33-11): 환상어 포획 연출 전용 곡 불러오기·재생.

찾는 순서: assets/music/phantom_catch_<버전>_<대륙>.ogg → assets/music/phantom_catch_<버전>.ogg (직접 고른 곡으로 덮어쓰기)
         → assets/music_generated/phantom_catch_<버전>_<대륙>.ogg (tools/audio/make_phantom_song.py 합성본)
버전: full / short / extended / loop. 보상 버스 'phantom_song_*' — 속도·피치·필터 변경 없이 그대로 (AS_IS).
"""
from src.audio import loader
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


def prefetch(sfx, cont: str) -> None:
    """파이팅이 시작될 때 버전들을 일꾼 스레드에 맡겨 둔다 (src/audio/loader.py, DESIGN.md 44)."""
    if not getattr(sfx, "enabled", False):
        return
    for v in ('full', 'short', 'extended', 'loop'):
        p = path_of(v, cont)
        if p is not None:
            loader.request(p)


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
    snd = loader.take(p, wait=True)   # prefetch 로 미리 맡겼으면 이미 다 읽혀 있음 (포획 순간 끊김 없게)
    if snd is None:
        return None
    sfx.sounds[name] = snd
    return name
