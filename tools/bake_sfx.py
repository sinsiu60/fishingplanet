"""효과음 미리 굽기 (DESIGN.md 32장, Phase S2).

data/sfx_recipes.json 의 레시피를 합성해서 assets/sfx_generated/<이름>.ogg 로 저장한다.
게임은 실행할 때 합성하지 않고 이 파일을 읽는다 (모바일 로딩 빠름). 구운 파일은 저장소에 함께 올린다.

  python tools/bake_sfx.py            바뀐 레시피만 다시 굽기 (assets/sfx_generated/manifest.json 의 해시로 판단)
  python tools/bake_sfx.py --all      전부 다시
  python tools/bake_sfx.py 이름 ...   그 소리만
  python tools/bake_sfx.py --check    굽지 않고 확인만 (최신이 아니면 종료 코드 1 — CI)
공간별 버전(N5, synth.space_recipes — '<이름>~<공간>')은 assets/sfx_space/ 로 함께 굽는다 (OGG 품질 2 — 잔향·먹먹한 소리라 낮아도 티가 덜 남, APK 크기).

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
SPACE_OUT = os.path.join(ROOT, "assets", "sfx_space")


def recipe_hash(name: str, recipe: dict) -> str:
    src = open(os.path.join(ROOT, "src", "audio", "synth.py"), "rb").read()  # 엔진이 바뀌어도 다시 굽는다
    src = src.replace(b"\r\n", b"\n")  # 윈도 체크아웃(CRLF)에서도 같은 해시 — CI --check
    return hashlib.sha1(src + json.dumps(recipe, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:16]


def bake(name: str, recipe: dict, ffmpeg: str | None, out: str = OUT, quality: str = "6", render=None) -> str:
    wav = (render or synth.render)(recipe, seed=int(hashlib.sha1(name.encode()).hexdigest()[:6], 16))
    fname = name.replace("#", "__")  # 단계 소리 이름의 #은 파일 이름에선 __
    for ext in (".ogg", ".wav"):
        old = os.path.join(out, fname + ext)
        if os.path.exists(old):
            os.remove(old)
    if ffmpeg:
        with tempfile.TemporaryDirectory() as tmp:
            src = os.path.join(tmp, "x.wav")
            synth.write_wav(src, wav)
            dst = os.path.join(out, fname + ".ogg")
            subprocess.run([ffmpeg, "-loglevel", "error", "-y", "-i", src, "-c:a", "libvorbis", "-q:a", quality,
                            "-fflags", "+bitexact", "-flags:a", "+bitexact", dst],  # 같은 소리 = 같은 파일 (git 변경 최소)
                           check=True)
            return dst
    dst = os.path.join(out, fname + ".wav")
    synth.write_wav(dst, wav)
    return dst


def main(argv: list[str], rec: dict | None = None, out_dir: str = OUT, quality: str = "6", hash_fn=recipe_hash,
         render=None) -> int:
    """rec/out_dir/quality/hash_fn/render 는 tools/bake_music.py 가 음악 층을 구울 때 바꿔 넣는다."""
    os.makedirs(out_dir, exist_ok=True)
    man_path = os.path.join(out_dir, "manifest.json")
    manifest = json.load(open(man_path, encoding="utf-8")) if os.path.exists(man_path) else {}
    rec = synth.recipes() if rec is None else rec
    if "--check" in argv:
        # 빌드 전 확인 (CI, ffmpeg 필요 없음): 레시피가 바뀌었는데 안 구웠거나 파일이 빠졌으면 실패
        stale = [n for n in rec if manifest.get(n) != hash_fn(n, rec[n]) or not any(
            os.path.exists(os.path.join(out_dir, n.replace("#", "__") + e)) for e in (".ogg", ".wav"))]
        print(f"{os.path.relpath(out_dir, ROOT)}: {len(rec) - len(stale)}/{len(rec)} 최신" + (f" — 다시 구울 것: {stale}" if stale else ""))
        return 1 if stale else 0
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
        h = hash_fn(name, rec[name])
        if not force and manifest.get(name) == h and any(
                os.path.exists(os.path.join(out_dir, name.replace("#", "__") + e)) for e in (".ogg", ".wav")):
            continue
        path = bake(name, rec[name], ffmpeg, out_dir, quality, render)
        manifest[name] = h
        done += 1
        print(f"굽기: {os.path.relpath(path, ROOT)} ({os.path.getsize(path) // 1024}KB)")
    for gone in [k for k in manifest if k not in rec]:  # 레시피에서 지운 소리 정리
        for e in (".ogg", ".wav"):
            p = os.path.join(out_dir, gone.replace("#", "__") + e)
            if os.path.exists(p):
                os.remove(p)
        manifest.pop(gone)
    with open(man_path, "w", encoding="utf-8") as fp:
        json.dump(manifest, fp, ensure_ascii=False, indent=1, sort_keys=True)
    print(f"완료: {done}개 새로 구움, 전체 {len(rec)}개")
    return 0


def main_all(argv: list[str]) -> int:
    """기본 소리 + 공간별 버전 (이름을 주면 '~' 있는 이름은 공간 쪽으로)."""
    flags = [a for a in argv if a.startswith("--")]
    names = [a for a in argv if not a.startswith("--")]
    base = [n for n in names if "~" not in n]
    space = [n for n in names if "~" in n]
    rc = 0
    if not names or base:
        rc |= main(flags + base)
    if not names or space:
        rc |= main(flags + space, rec=synth.space_recipes(), out_dir=SPACE_OUT, quality="2")
    return rc


if __name__ == "__main__":
    sys.exit(main_all(sys.argv[1:]))
