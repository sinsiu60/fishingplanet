"""효과음 미리 굽기 (DESIGN.md 32장, Phase S2).

data/sfx_recipes.json 의 레시피를 합성해서 assets/sfx_generated/<이름>.ogg 로 저장한다.
게임은 실행할 때 합성하지 않고 이 파일을 읽는다 (모바일 로딩 빠름). 구운 파일은 저장소에 함께 올린다.

  python tools/bake_sfx.py            바뀐 레시피만 다시 굽기 (assets/sfx_generated/manifest.json 의 해시로 판단)
  python tools/bake_sfx.py --all      전부 다시
  python tools/bake_sfx.py 이름 ...   그 소리만

OGG 인코딩은 ffmpeg(libvorbis)를 쓴다. ffmpeg이 없으면 .wav 로 저장 (게임은 둘 다 읽음).
"""
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

from src.audio import synth  # noqa: E402

OUT = os.path.join(ROOT, "assets", "sfx_generated")


def recipe_hash(name: str, recipe: dict) -> str:
    src = open(os.path.join(ROOT, "src", "audio", "synth.py"), "rb").read()  # 엔진이 바뀌어도 다시 굽는다
    return hashlib.sha1(src + json.dumps(recipe, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:16]


def bake(name: str, recipe: dict, ffmpeg: str | None) -> str:
    wav = synth.render(recipe, seed=int(hashlib.sha1(name.encode()).hexdigest()[:6], 16))
    for ext in (".ogg", ".wav"):
        old = os.path.join(OUT, name + ext)
        if os.path.exists(old):
            os.remove(old)
    if ffmpeg:
        with tempfile.TemporaryDirectory() as tmp:
            src = os.path.join(tmp, name + ".wav")
            synth.write_wav(src, wav)
            dst = os.path.join(OUT, name + ".ogg")
            subprocess.run([ffmpeg, "-loglevel", "error", "-y", "-i", src, "-c:a", "libvorbis", "-q:a", "6", dst],
                           check=True)
            return dst
    dst = os.path.join(OUT, name + ".wav")
    synth.write_wav(dst, wav)
    return dst


def main(argv: list[str]) -> int:
    os.makedirs(OUT, exist_ok=True)
    man_path = os.path.join(OUT, "manifest.json")
    manifest = json.load(open(man_path, encoding="utf-8")) if os.path.exists(man_path) else {}
    rec = synth.recipes()
    names = [a for a in argv if not a.startswith("--")] or list(rec)
    force = "--all" in argv or any(not a.startswith("--") for a in argv)
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        print("ffmpeg 없음 → .wav 로 저장합니다")
    done = 0
    for name in names:
        if name not in rec:
            print(f"레시피 없음: {name}")
            continue
        h = recipe_hash(name, rec[name])
        if not force and manifest.get(name) == h and any(
                os.path.exists(os.path.join(OUT, name + e)) for e in (".ogg", ".wav")):
            continue
        path = bake(name, rec[name], ffmpeg)
        manifest[name] = h
        done += 1
        print(f"굽기: {os.path.relpath(path, ROOT)} ({os.path.getsize(path) // 1024}KB)")
    for gone in [k for k in manifest if k not in rec]:  # 레시피에서 지운 소리 정리
        for e in (".ogg", ".wav"):
            p = os.path.join(OUT, gone + e)
            if os.path.exists(p):
                os.remove(p)
        manifest.pop(gone)
    with open(man_path, "w", encoding="utf-8") as fp:
        json.dump(manifest, fp, ensure_ascii=False, indent=1, sort_keys=True)
    print(f"완료: {done}개 새로 구움, 전체 {len(rec)}개")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
