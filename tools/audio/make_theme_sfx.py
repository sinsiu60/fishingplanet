"""테마 전설 연출 효과음 굽기 (ILSEOM.md 5장 · DESIGN.md 43-15) — 전투 곡과 같은 합성(src/audio/boss_muhyeop.py)을 그대로.

출력: assets/sfx_generated/ilseom/{seureung,chaeng,jing,wind}.ogg (최대 −3dBFS)
      게임은 src/audio/theme_sfx.py 가 'sfx_ilseom_<이름>' 으로 불러옴 (assets/sfx/ilseom/<이름>.ogg 가 있으면 그것 우선)
사용: python tools/audio/make_theme_sfx.py
"""
import os
import shutil
import subprocess
import sys
import tempfile

import numpy as np
from scipy.io import wavfile

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
from src.audio import boss_muhyeop as M  # noqa: E402
from src.audio.boss_synth import RATE  # noqa: E402

OUT = os.path.join(ROOT, "assets", "sfx_generated", "ilseom")


def sounds() -> dict:
    rng = np.random.default_rng(2024)
    n = lambda s: int(s * RATE)  # noqa: E731
    wind = M.s_wind(n(3.0), rng)
    wind[-n(0.6):] *= np.linspace(1, 0, n(0.6))
    return {"seureung": M.s_seureung(n(0.85), rng),
            "chaeng": M.s_chaeng(n(0.55), rng),
            "jing": M.d_jing(n(3.0), 1.0, rng) * np.linspace(1, 0, n(3.0)) ** 0.7,
            "wind": wind}


def main() -> int:
    os.makedirs(OUT, exist_ok=True)
    ff = shutil.which("ffmpeg")
    for name, x in sounds().items():
        x = x / (np.abs(x).max() or 1.0) * 10 ** (-3 / 20)
        st = np.stack([x, x], axis=1)
        pcm = (np.clip(st, -1, 1) * 32767).astype(np.int16)
        with tempfile.TemporaryDirectory() as tmp:
            wav = os.path.join(tmp, name + ".wav")
            wavfile.write(wav, RATE, pcm)
            if ff:
                subprocess.run([ff, "-loglevel", "error", "-y", "-i", wav, "-c:a", "libvorbis", "-q:a", "5",
                                os.path.join(OUT, name + ".ogg")], check=True)
            else:
                shutil.copy(wav, os.path.join(OUT, name + ".wav"))
        print(f"ilseom/{name}: {len(x) / RATE:.2f}초")
    return 0


if __name__ == "__main__":
    sys.exit(main())
