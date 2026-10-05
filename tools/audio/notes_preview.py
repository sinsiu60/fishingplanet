"""음표 데이터 곡 미리듣기 (DESIGN.md 43-28): 게임에 넣기 전에 게임 음색으로 렌더링해 들어 보기.

data/music/<이름>_notes.json 을 boss_notes.NotesSong 으로 굽고 (게임 파일 · music_patterns.json 은 건드리지 않음)
마스터링(−14 LUFS · −1dBTP)까지 한 뒤 인트로 + 페이즈들(+ 전환 마디)을 이어 붙여 wav 로 저장.

사용: python tools/audio/notes_preview.py yeoubi L01 golden_carp 62
      → tools/audio/reference/boss_bgm/new/yeoubi_preview.wav
"""
import os
import sys

import numpy as np
from scipy.io import wavfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)


def main(argv) -> int:
    name, replaces, fish, root = argv[0], argv[1], argv[2], int(argv[3])
    import boss_songs
    from src.audio import boss_synth
    from src.audio.boss_notes import NotesSong
    spec = boss_songs.notes_spec(name, fish, replaces, root)
    _, mcfg = boss_synth.song_specs()
    song = NotesSong(f"{replaces}-NEW", spec, mcfg)
    stems, rep = boss_synth.master(song.stems(), len(spec["phases"]), dict(mcfg, **spec.get("master", {})))
    mx = boss_synth.mixes(stems, len(spec["phases"]))
    parts = [stems["intro_mix"]]
    for i in range(1, len(spec["phases"]) + 1):
        parts.append(mx[str(i)])
        r = stems.get(f"{i}_riser")
        if r is not None and len(r) > int(0.05 * boss_synth.RATE):
            parts.append(r)
    y = np.clip(np.concatenate(parts), -1, 1)
    out = os.path.join(ROOT, "tools", "audio", "reference", "boss_bgm", "new")
    os.makedirs(out, exist_ok=True)
    p = os.path.join(out, f"{name}_preview.wav")
    wavfile.write(p, boss_synth.RATE, (y * 32767).astype(np.int16))
    print(f"{name}: {rep['lufs']} LUFS · 최대 {rep['tp']} dBTP · 페이즈 {rep['phases']} → {os.path.relpath(p, ROOT)} ({len(y) / boss_synth.RATE:.0f}초)")
    for i in range(1, len(spec["phases"]) + 1):   # 층별 크기 (섞기 확인용)
        import pyloudnorm
        mt = pyloudnorm.Meter(boss_synth.RATE)
        row = {}
        for lay in ("base", "perc", "perc_crisis", "lead", "lead_oct", "choir"):
            x = stems.get(f"{i}_{lay}")
            if x is not None and np.abs(x).max() > 1e-4:
                row[lay] = round(mt.integrated_loudness(x), 1)
        print(f"  {i}페이즈", row)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
