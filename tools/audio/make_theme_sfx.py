"""테마 전설 연출 효과음 굽기 (ILSEOM.md 5장 · DESIGN.md 43-15) — 전투 곡과 같은 합성(src/audio/boss_muhyeop.py)을 그대로.

출력: assets/sfx_generated/<테마>/<이름>.ogg (최대 −3dBFS)
      ilseom (청새치 '일섬', boss_muhyeop): seureung · chaeng · jing · wind
      yeoubi (황금잉어 '여우비', boss_jazz): piano (가짜 지침 예고 '띵—') · coin (퍼펙트 금화 '띵')
      게임은 src/audio/theme_sfx.py 가 'sfx_<테마>_<이름>' 으로 불러옴 (assets/sfx/<테마>/<이름>.ogg 가 있으면 그것 우선)
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
from src.audio import boss_jazz as J  # noqa: E402
from src.audio import boss_muhyeop as M  # noqa: E402
from src.audio.boss_synth import RATE  # noqa: E402

OUT = os.path.join(ROOT, "assets", "sfx_generated")


def sounds() -> dict:
    rng = np.random.default_rng(2024)
    n = lambda s: int(s * RATE)  # noqa: E731
    wind = M.s_wind(n(3.0), rng)
    wind[-n(0.6):] *= np.linspace(1, 0, n(0.6))
    from src.audio.boss_synth import hz
    piano = J.i_piano(hz(86), n(1.6), rng)            # D6 능청스러운 한 음
    return {"ilseom/seureung": M.s_seureung(n(0.85), rng),
            "ilseom/chaeng": M.s_chaeng(n(0.55), rng),
            "ilseom/jing": M.d_jing(n(3.0), 1.0, rng) * np.linspace(1, 0, n(3.0)) ** 0.7,
            "ilseom/wind": wind,
            "yeoubi/piano": piano,
            "yeoubi/coin": J.s_coin(n(0.6), rng)}


def main() -> int:
    ff = shutil.which("ffmpeg")
    for name, x in sounds().items():
        os.makedirs(os.path.dirname(os.path.join(OUT, name)), exist_ok=True)
        x = x / (np.abs(x).max() or 1.0) * 10 ** (-3 / 20)
        st = np.stack([x, x], axis=1)
        pcm = (np.clip(st, -1, 1) * 32767).astype(np.int16)
        with tempfile.TemporaryDirectory() as tmp:
            wav = os.path.join(tmp, os.path.basename(name) + ".wav")
            wavfile.write(wav, RATE, pcm)
            if ff:
                subprocess.run([ff, "-loglevel", "error", "-y", "-i", wav, "-c:a", "libvorbis", "-q:a", "5",
                                os.path.join(OUT, name + ".ogg")], check=True)
            else:
                shutil.copy(wav, os.path.join(OUT, name + ".wav"))
        print(f"{name}: {len(x) / RATE:.2f}초")
    return 0


if __name__ == "__main__":
    sys.exit(main())
