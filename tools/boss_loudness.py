"""전설·환상 전용 BGM 음량 측정 (DESIGN.md 43-5, 개발용 — scipy · pyloudnorm · ffmpeg 필요).

구운 층(assets/music_generated/boss/, assets/music/boss/ 가 있으면 그것)을 게임처럼 섞어
  - 곡 전체(인트로 + 페이즈 보통 믹스) 통합 음량 LUFS, 모든 조합(보통·위기·지침)의 최대치 dBTP
  - 일반 파이팅 음악(mus_fight_<대륙>)과 실제로 들리는 크기 차이 (재생 배율 state_gain 반영, 목표 +6dB)
를 표로 보여 준다.

  python tools/boss_loudness.py            모든 곡
  python tools/boss_loudness.py L01 P03    그 곡만
  python tools/boss_loudness.py --dir 폴더  다른 폴더 (시험 굽기)
"""
import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

import numpy as np  # noqa: E402


def load(path: str) -> np.ndarray:
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-f", "f32le", "-ac", "2", "-ar", "44100", "-"],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.float32).reshape(-1, 2).astype(np.float64)


def find(d: str, name: str) -> str | None:
    for base in (os.path.join(ROOT, "assets", "music", "boss"), d):
        for ext in (".ogg", ".wav"):
            p = os.path.join(base, name + ext)
            if os.path.exists(p):
                return p
    return None


def fight_lufs() -> float:
    """일반 파이팅 기본 층(두 대륙) 평균 LUFS — 3바퀴 이어서 잼 (짧은 반복 층)."""
    from src.audio.boss_synth import lufs
    vals = []
    for c in ("sharmion", "eldrasion"):
        p = os.path.join(ROOT, "assets", "music_generated", f"mus_fight_{c}.ogg")
        if os.path.exists(p):
            vals.append(lufs(np.tile(load(p), (3, 1))))
    return float(np.mean(vals)) if vals else -20.0


def main(argv: list[str]) -> int:
    from src.audio import boss_synth
    from src.core.config import load_json
    d = os.path.join(ROOT, "assets", "music_generated", "boss")
    if "--dir" in argv:
        d = argv[argv.index("--dir") + 1]
        argv = [a for a in argv if a not in ("--dir", d)]
    songs, _ = boss_synth.song_specs()
    names = [a for a in argv if not a.startswith("--")] or [k for k, v in songs.items() if not v.get("test")]
    sg = load_json("music_patterns.json")["state_gain"]
    g_boss, g_fight = sg.get("boss", 1.0), sg.get("fight", 1.0)
    fl = fight_lufs()
    print(f"일반 파이팅 음악: {fl:.1f} LUFS (재생 배율 {g_fight}) — 전용 곡 목표 +6dB, 재생 배율 {g_boss}")
    print(f"{'곡':5} {'LUFS':>7} {'최대dBTP':>9} {'일반 대비':>9}   페이즈별 LUFS")
    bad = 0
    for sid in names:
        spec = songs.get(sid)
        if spec is None:
            print(sid, "스펙 없음")
            bad += 1
            continue
        n = len(spec["phases"])
        stems = {}
        for k in ["intro_mix"] + [f"{i}_{l}" for i in range(1, n + 1) for l in ("base", "perc", "perc_crisis", "lead", "lead_oct", "choir")]:
            p = find(d, f"{sid}_intro" if k == "intro_mix" else f"{sid}_{k}")
            if p is not None:
                stems[k] = load(p)
        if "intro_mix" not in stems or any(f"{i}_base" not in stems for i in range(1, n + 1)):
            print(f"{sid:5} 구운 파일 없음 (python tools/bake_boss.py {sid})")
            bad += 1
            continue
        for i in range(1, n + 1):   # 이 페이즈에 없는 층(무음이라 파일을 안 만든 것) = 0
            for l in ("perc", "perc_crisis", "lead", "lead_oct", "choir"):
                stems.setdefault(f"{i}_{l}", np.zeros_like(stems[f"{i}_base"]))
        mx = boss_synth.mixes(stems, n)
        whole = np.concatenate([mx["intro"]] + [mx[str(i)] for i in range(1, n + 1)])
        lu = boss_synth.lufs(whole)
        tp = max(boss_synth.true_peak_db(v) for v in mx.values())
        diff = (lu + 20 * np.log10(g_boss)) - (fl + 20 * np.log10(g_fight))
        ph = " ".join(f"{k}:{boss_synth.lufs(v):.1f}" for k, v in mx.items() if "_" not in k)
        ok = abs(lu + 14) <= 1.0 and tp <= -1.0 + 0.05 and abs(diff - 6) <= 1.0
        bad += not ok
        print(f"{sid:5} {lu:7.1f} {tp:9.2f} {diff:+8.1f}dB   {ph}{'' if ok else '   ← 확인'}")
    print("결과:", "ok" if not bad else f"확인 필요 {bad}곡")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
