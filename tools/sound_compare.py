"""두 소리 번갈아 비교 (DESIGN.md 32장 S2 — 예전 내장음은 S8에서 지움, 지금은 아무 두 소리나).

  python tools/sound_compare.py [첫째=sfx_hook_success] [둘째=sfx_hook_heavy] [--wav 폴더]
스피커로 첫째 → 1초 쉼 → 둘째를 3번 번갈아 재생하고, --wav 를 주면 두 소리를 wav로 저장한다.
"""
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

import numpy as np  # noqa: E402
import pygame  # noqa: E402


def main(argv):
    out = None
    if "--wav" in argv:
        i = argv.index("--wav")
        out = argv[i + 1]
        argv = argv[:i] + argv[i + 2:]
    old = argv[0] if argv else "sfx_hook_success"
    new = argv[1] if len(argv) > 1 else "sfx_hook_heavy"
    pygame.mixer.pre_init(44100, -16, 2, 512)
    pygame.init()
    from src.audio.sfx import Sfx
    sfx = Sfx()
    if not sfx.enabled:
        print("오디오 장치 없음")
        return 1
    for name in (old, new):
        if name not in sfx.sounds:
            print(f"소리 없음: {name}")
            return 1
    if out:
        from src.audio.synth import write_wav
        os.makedirs(out, exist_ok=True)
        for tag, name in (("old", old), ("new", new)):
            arr = pygame.sndarray.array(sfx.sounds[name]).astype(np.float32) / 32767
            if arr.ndim == 1:
                arr = np.stack([arr, arr], axis=1)
            write_wav(os.path.join(out, f"{tag}_{name}.wav"), arr)
        print(f"저장: {out}")
    if os.environ.get("SDL_AUDIODRIVER") == "dummy":
        return 0
    for _ in range(3):
        for name in (old, new):
            print("재생:", name)
            sfx.sounds[name].play()
            time.sleep(sfx.sounds[name].get_length() + 1.0)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
