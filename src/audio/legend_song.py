"""전설의 노래 (DESIGN.md 34장): 전설 포획 연출 전용 곡 불러오기.

찾는 순서: assets/music/legend_catch_<버전>_<곡ID>.ogg → …_<대륙>.ogg → legend_catch_<버전>.ogg (직접 고른 곡으로 덮어쓰기)
         → assets/music_generated/legend_catch_<버전>_<곡ID>.ogg (전설마다 그 파이팅 곡 조성, DESIGN.md 43)
         → assets/music_generated/legend_catch_<버전>_<대륙>.ogg (tools/audio/make_legend_song.py 합성본)
버전: full / short / loop (final 은 full 곡). 보상 버스 'legend_song_*' — 속도·피치·필터 변경 없이 그대로 (AS_IS).
곡ID = 전설 전용 파이팅 곡 ID (L01~L12, L03-ROCK — 락 버전이 없으면 L03). 없으면 대륙판.
"""
from src.audio import loader
from src.core.paths import asset_path


def path_of(variant: str, cont: str, sid: str | None = None):
    variant = "full" if variant == "final" else variant
    tags = ([sid] if sid else []) + ([sid.split("-")[0]] if sid and "-" in sid else []) + [cont]   # L03-ROCK → 없으면 L03
    cands = [asset_path("music", f"legend_catch_{variant}_{t}.ogg") for t in tags] + [asset_path("music", f"legend_catch_{variant}.ogg")]
    for t in tags:
        cands += [asset_path("music_generated", f"legend_catch_{variant}_{t}.ogg"), asset_path("music_generated", f"legend_catch_{variant}_{t}.wav")]
    for p in cands:
        if p.exists():
            return p
    return None


def name_of(variant: str, cont: str, sid: str | None = None) -> str:
    return f"legend_song_{'full' if variant == 'final' else variant}_{sid or cont}"


def prefetch(sfx, cont: str, sid: str | None = None) -> None:
    """파이팅이 시작될 때 버전들을 일꾼 스레드에 맡겨 둔다 (src/audio/loader.py, DESIGN.md 44)."""
    if not getattr(sfx, "enabled", False):
        return
    for v in ('full', 'short', 'loop'):
        p = path_of(v, cont, sid)
        if p is not None:
            loader.request(p)


def preload(sfx, variant: str, cont: str, sid: str | None = None) -> str | None:
    if not getattr(sfx, "enabled", False):
        return None
    name = name_of(variant, cont, sid)
    if name in sfx.sounds:
        return name
    p = path_of(variant, cont, sid)
    if p is None:
        return None
    snd = loader.take(p, wait=True)   # prefetch 로 미리 맡겼으면 이미 다 읽혀 있음 (포획 순간 끊김 없게)
    if snd is None:
        return None
    sfx.sounds[name] = snd
    return name
