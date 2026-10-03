"""사운드 개편(S1~S8) 전 내장 효과음을 그대로 꺼내 assets/sfx/legacy_*.wav 로 저장 (v0.8.14 롤백용).

예전 src/audio/sfx.py(커밋 c2cb9e8)를 git 에서 읽어 그 때의 합성 순서(같은 난수 흐름) 그대로 만들고,
필요한 소리만 'legacy_<예전 이름>' 으로 저장한다. assets/sfx/ 의 파일은 게임이 그 이름으로 바로 쓴다.
  python tools/legacy_sfx_extract.py
"""
import os
import subprocess
import sys
import types
import wave

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
COMMIT = "c2cb9e8"
NAMES = ["sig_reel", "creak", "creak2", "creak3", "bubbles", "rush_go", "splash_small"] + [f"rush_hum{i}" for i in range(8)]


def main() -> int:
    import pygame
    pygame.mixer.init(44100, -16, 2, 512)
    src = subprocess.check_output(["git", "show", f"{COMMIT}:src/audio/sfx.py"]).decode("utf-8")
    # 예전 코드가 읽는 data/*.json 도 그 커밋 것으로
    import json
    import src.core.config as config
    real = config.load_json
    config.load_json = lambda name: json.loads(subprocess.check_output(["git", "show", f"{COMMIT}:data/{name}"]).decode("utf-8"))
    mod = types.ModuleType("old_sfx")
    exec(compile(src, "old_sfx.py", "exec"), mod.__dict__)
    import src.platform.detect as det
    mobile, det.IS_MOBILE = det.IS_MOBILE, False   # 캐시 없이 직접 합성
    old = mod.Sfx()
    det.IS_MOBILE = mobile
    config.load_json = real
    out_dir = os.path.join(ROOT, "assets", "sfx")
    for n in NAMES:
        arr = pygame.sndarray.array(old.sounds[n])
        p = os.path.join(out_dir, f"legacy_{n}.wav")
        with wave.open(p, "wb") as w:
            w.setnchannels(arr.shape[1] if arr.ndim == 2 else 1)
            w.setsampwidth(2)
            w.setframerate(44100)
            w.writeframes(arr.astype("<i2").tobytes())
        print(f"{p}  {len(arr) / 44100:.2f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
