"""전설·환상 전용 파이팅 곡 굽기 (DESIGN.md 43, BOSS_BGM.md).

data/music_patterns.json "boss" → src/audio/boss_synth.py 로 층 합성 + 마스터링(−14 LUFS · −1dBTP · 중음역 −2dB)
→ assets/music_generated/boss/<곡ID>_intro.ogg · <곡ID>_<페이즈>_<층>.ogg (OGG, 층마다 같은 배율).
바뀐 곡만 다시 굽는다 (manifest.json 해시 = 곡 스펙 + 마스터 설정 + boss_synth.py, "battle" 곡은 + boss_battle.py). 구운 파일은 저장소에 함께 올린다.
시험곡("test": true)은 게임 파일로는 굽지 않는다 (--out 으로만).

  python tools/bake_boss.py              바뀐 곡만
  python tools/bake_boss.py --all        전부 다시
  python tools/bake_boss.py L01 P03      그 곡만
  python tools/bake_boss.py --check      확인만 (CI — 최신이 아니면 종료 코드 1, 합성 안 함)
  python tools/bake_boss.py --preview    미리듣기도: tools/audio/reference/boss_bgm/<legend|phantom>/<곡ID>.ogg
                                         (인트로 → 1페이즈 → 라이저 → 2페이즈 … 를 이어 붙인 것, --wav 면 wav)
  python tools/bake_boss.py --out 폴더 T00   다른 폴더로 (시험)
필요: scipy · pyloudnorm (requirements-dev.txt), ffmpeg
"""
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

OUT = os.path.join(ROOT, "assets", "music_generated", "boss")
PREVIEW = os.path.join(ROOT, "tools", "audio", "reference", "boss_bgm")


def song_hash(spec: dict, master: dict) -> str:
    src = open(os.path.join(ROOT, "src", "audio", "boss_synth.py"), "rb").read().replace(b"\r\n", b"\n")
    if spec.get("battle"):   # 전투감 곡은 boss_battle.py 도 (DESIGN.md 43-13)
        src += open(os.path.join(ROOT, "src", "audio", "boss_battle.py"), "rb").read().replace(b"\r\n", b"\n")
    if spec.get("muhyeop"):  # 국악 무협 곡은 boss_muhyeop.py 도 (DESIGN.md 43-15)
        src += open(os.path.join(ROOT, "src", "audio", "boss_muhyeop.py"), "rb").read().replace(b"\r\n", b"\n")
    if spec.get("organ"):    # 대성당 오르간 곡은 boss_organ.py 도 (DESIGN.md 43-18) — 일부를 boss_muhyeop 에서 가져옴
        for f in ("boss_organ.py", "boss_muhyeop.py"):
            src += open(os.path.join(ROOT, "src", "audio", f), "rb").read().replace(b"\r\n", b"\n")
    if spec.get("sangun"):   # 북과 목 노래 곡은 boss_sangun.py 도 (DESIGN.md 43-17) — 일부를 boss_muhyeop 에서 가져옴
        for f in ("boss_sangun.py", "boss_muhyeop.py"):
            src += open(os.path.join(ROOT, "src", "audio", f), "rb").read().replace(b"\r\n", b"\n")
    if spec.get("jazz"):     # 재즈 곡은 boss_jazz.py 도 (DESIGN.md 43-16) — 악기 일부를 boss_muhyeop·boss_rock 에서 가져옴
        for f in ("boss_jazz.py", "boss_muhyeop.py", "boss_rock.py"):
            src += open(os.path.join(ROOT, "src", "audio", f), "rb").read().replace(b"\r\n", b"\n")
    if spec.get("epic"):     # 에픽 집대성 곡은 boss_epic.py 와 다섯 테마 모듈 모두 (DESIGN.md 43-19)
        for f in ("boss_epic.py", "boss_jazz.py", "boss_sangun.py", "boss_rock.py", "boss_muhyeop.py", "boss_organ.py"):
            src += open(os.path.join(ROOT, "src", "audio", f), "rb").read().replace(b"\r\n", b"\n")
    if spec.get("celtic"):   # 켈틱 곡은 boss_celtic.py 도 (DESIGN.md 43-22) — 성가는 boss_organ, 도우미는 boss_muhyeop 에서
        for f in ("boss_celtic.py", "boss_organ.py", "boss_muhyeop.py"):
            src += open(os.path.join(ROOT, "src", "audio", f), "rb").read().replace(b"\r\n", b"\n")
    if spec.get("trance"):   # 트랜스 곡은 boss_trance.py 도 (DESIGN.md 43-23) — 도우미는 boss_muhyeop 에서
        for f in ("boss_trance.py", "boss_muhyeop.py"):
            src += open(os.path.join(ROOT, "src", "audio", f), "rb").read().replace(b"\r\n", b"\n")
    if spec.get("rock"):     # 락 곡은 boss_rock.py 도 (DESIGN.md 43-14)
        src += open(os.path.join(ROOT, "src", "audio", "boss_rock.py"), "rb").read().replace(b"\r\n", b"\n")
    return hashlib.sha1(src + json.dumps([spec, master], sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:16]


def write_audio(path: str, x, quality: str, ffmpeg: str | None) -> str:
    import numpy as np
    from src.audio import synth
    x = np.clip(x, -1, 1)
    if ffmpeg and path.endswith(".ogg"):
        with tempfile.TemporaryDirectory() as tmp:
            src = os.path.join(tmp, "x.wav")
            synth.write_wav(src, x)
            subprocess.run([ffmpeg, "-loglevel", "error", "-y", "-i", src, "-c:a", "libvorbis", "-q:a", quality,
                            "-fflags", "+bitexact", "-flags:a", "+bitexact", path], check=True)
        return path
    path = path.rsplit(".", 1)[0] + ".wav"
    synth.write_wav(path, x)
    return path


def preview(sid: str, spec: dict, stems: dict, ffmpeg, wav: bool) -> str:
    import numpy as np
    from src.audio import boss_synth
    n = len(spec["phases"])
    mx = boss_synth.mixes(stems, n)
    parts = [stems["intro_mix"]]
    for i in range(1, n + 1):
        parts.append(mx[str(i)])
        if i < n:
            parts.append(stems[f"{i}_riser"] + mx[str(i)][: len(stems[f"{i}_riser"])] * 0.5)   # 라이저 마디: 앞 페이즈가 줄어들며
    d = os.path.join(PREVIEW, "phantom" if spec.get("kind") == "phantom" else "legend")
    os.makedirs(d, exist_ok=True)
    return write_audio(os.path.join(d, f"{sid}.{'wav' if wav else 'ogg'}"), np.concatenate(parts), "5", ffmpeg)


def main(argv: list[str]) -> int:
    from src.audio import boss_synth
    songs, mcfg = boss_synth.song_specs()
    out = OUT
    if "--out" in argv:
        out = argv[argv.index("--out") + 1]
        argv = [a for a in argv if a not in ("--out", out)]
    os.makedirs(out, exist_ok=True)
    man_path = os.path.join(out, "manifest.json")
    man = json.load(open(man_path, encoding="utf-8")) if os.path.exists(man_path) else {}
    names = [a for a in argv if not a.startswith("--")]
    game = out == OUT
    todo = {k: v for k, v in songs.items() if (not names or k in names) and (not game or not v.get("test"))}
    if "--check" in argv:
        stale = [k for k, v in todo.items() if man.get(k, {}).get("hash") != song_hash(v, mcfg)]
        extra = [k for k in man if k not in songs or songs[k].get("test")]
        print(f"boss: {len(todo) - len(stale)}/{len(todo)} 최신" + (f" — 다시 구울 것: {' '.join(stale)}" if stale else "")
              + (f" — 남은 옛 곡: {' '.join(extra)}" if extra else ""))
        return 1 if stale or extra else 0
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        print("경고: ffmpeg 없음 → wav 로 저장")
    rows = []
    for sid, spec in todo.items():
        h = song_hash(spec, mcfg)
        if man.get(sid, {}).get("hash") == h and "--all" not in argv and "--preview" not in argv and not names:
            continue
        t0 = time.time()
        cls = boss_synth.Song
        if spec.get("battle"):
            from src.audio.boss_battle import BattleSong as cls
        if spec.get("rock"):
            from src.audio.boss_rock import RockSong as cls
        if spec.get("muhyeop"):
            from src.audio.boss_muhyeop import MuhyeopSong as cls
        if spec.get("jazz"):
            from src.audio.boss_jazz import JazzSong as cls
        if spec.get("sangun"):
            from src.audio.boss_sangun import SangunSong as cls
        if spec.get("organ"):
            from src.audio.boss_organ import OrganSong as cls
        if spec.get("epic"):
            from src.audio.boss_epic import EpicSong as cls
        if spec.get("celtic"):
            from src.audio.boss_celtic import CelticSong as cls
        if spec.get("trance"):
            from src.audio.boss_trance import TranceSong as cls
        stems, rep = boss_synth.master(cls(sid, spec, mcfg).stems(), len(spec["phases"]), dict(mcfg, **spec.get("master", {})))
        for old in os.listdir(out):
            if old.startswith(sid + "_"):
                os.remove(os.path.join(out, old))
        files = []
        for k, x in stems.items():
            if k != "intro_mix" and float(abs(x).max()) < 1e-4:
                continue   # 이 페이즈엔 없는 층 (예: 합창 없음) — 파일 없음 = 조용히
            name = f"{sid}_intro" if k == "intro_mix" else f"{sid}_{k}"
            files.append(os.path.basename(write_audio(os.path.join(out, name + ".ogg"), x, mcfg.get("quality", "4"), ffmpeg)))
        man[sid] = {"hash": h, "lufs": rep["lufs"], "tp": float(rep["tp"]), "phases": rep["phases"], "files": sorted(files)}
        if "--preview" in argv:
            print("  미리듣기:", os.path.relpath(preview(sid, spec, stems, ffmpeg, "--wav" in argv), ROOT))
        rows.append((sid, rep, time.time() - t0))
        print(f"{sid}: {rep['lufs']} LUFS · 최대 {float(rep['tp'])} dBTP · 페이즈 {rep['phases']} ({time.time() - t0:.0f}초)")
        json.dump(man, open(man_path, "w", encoding="utf-8"), ensure_ascii=False, indent=1, sort_keys=True)
    if game:   # 스펙에서 빠진 곡의 파일 정리
        for k in [k for k in man if k not in songs or songs[k].get("test")]:
            for f in man[k].get("files", []):
                p = os.path.join(out, f)
                if os.path.exists(p):
                    os.remove(p)
            del man[k]
    json.dump(man, open(man_path, "w", encoding="utf-8"), ensure_ascii=False, indent=1, sort_keys=True)
    print(f"완료: {len(rows)}곡 구움, 전체 {len([k for k in man])}곡")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
