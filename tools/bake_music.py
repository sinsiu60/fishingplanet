"""음악 층 미리 굽기 (DESIGN.md 32-12, Phase S6).

data/music_patterns.json → src/audio/music_synth.py 로 합성 → assets/music_generated/<이름>.ogg (OGG q4, 반복 층은 길이가 모두 같다).
바뀐 것만 다시 굽는다 (manifest.json 해시 = 레시피 + synth.py + music_synth.py). 구운 파일은 저장소에 함께 올린다.

  python tools/bake_music.py            바뀐 층만
  python tools/bake_music.py --all      전부 다시
  python tools/bake_music.py 이름 ...   그 층만
  python tools/bake_music.py --check    확인만 (CI)
"""
import hashlib
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))
os.chdir(ROOT)

import bake_sfx  # noqa: E402
from src.audio import music_synth  # noqa: E402

OUT = os.path.join(ROOT, "assets", "music_generated")


def music_hash(name: str, recipe: dict) -> str:
    src = b"".join(open(os.path.join(ROOT, "src", "audio", f), "rb").read() for f in ("synth.py", "music_synth.py"))
    src = src.replace(b"\r\n", b"\n")  # 줄바꿈 무관
    return hashlib.sha1(src + json.dumps(recipe, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:16]


if __name__ == "__main__":
    sys.exit(bake_sfx.main(sys.argv[1:], rec=music_synth.recipes(), out_dir=OUT, quality="4", hash_fn=music_hash,
                                render=music_synth.render))
