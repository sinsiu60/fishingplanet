"""전설·환상 전용 BGM 위에서 신호 소리가 묻히지 않는지 (DESIGN.md 43, BOSS_BGM.md B6-2 — 개발용, scipy·ffmpeg 필요).

곡마다 페이즈별 보통·위기 믹스를 게임에서 들리는 크기로(음악 배율 0.35 × state_gain boss × 기본 음악 음량 × 신호 덕킹 −2dB) 놓고,
신호 6계열 소리(자연음 sig_nat_*, 신호 버스 — 전용 곡 동안 audio_config boss.sig_db 만큼 키움)의 가장 큰 100ms 와 음악의 큰 순간(100ms 창 90% 지점)을
  - 1~3kHz (신호가 사는 중음역 — 음악은 −2dB 비워 둠)
  - 전체 대역
에서 비교한다. 결과 = 신호 − 음악 (dB, 클수록 잘 들림). 계열마다 가장 나쁜 곡·페이즈와 전체 표.

  python tools/boss_signal_check.py            모든 곡
  python tools/boss_signal_check.py L01 P03    그 곡만
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))
os.chdir(ROOT)

import numpy as np  # noqa: E402

from boss_loudness import find, load  # noqa: E402

RATE = 44100
FAMILIES = {   # 신호 사전 6계열 (자연음 모드 = 기본)
    "풀기": ["sig_nat_release_go", "sig_nat_release_gulp"],
    "타이밍": ["sig_nat_timing_apex"],
    "방향": ["sig_nat_direction"],
    "버티기": ["sig_nat_endure"],
    "감기": ["sig_nat_reel"],
    "몸짓": ["sig_nat_gesture", "sig_nat_leap", "sig_nat_lure"],
}
WARN_DB = 3.0


def band(x: np.ndarray, lo=1000, hi=3000) -> np.ndarray:
    from scipy.signal import butter, sosfilt
    sos = butter(4, [lo, hi], "bandpass", fs=RATE, output="sos")
    return sosfilt(sos, x, axis=0)


def win_rms_db(x: np.ndarray, win: float = 0.1) -> np.ndarray:
    m = x.mean(axis=1) if x.ndim > 1 else x
    w = int(RATE * win)
    n = len(m) // w
    if n == 0:
        return np.array([20 * np.log10(np.sqrt(np.mean(m ** 2)) + 1e-9)])
    seg = m[: n * w].reshape(n, w)
    return 20 * np.log10(np.sqrt((seg ** 2).mean(axis=1)) + 1e-9)


def main(argv: list[str]) -> int:
    from src.audio import boss_synth
    from src.audio.adaptive_music import GAIN
    from src.core.config import load_json
    from src.save.settings import DEFAULTS
    songs, _ = boss_synth.song_specs()
    names = [a for a in argv if not a.startswith("--")] or [k for k, v in songs.items() if not v.get("test")]
    sg = load_json("music_patterns.json")["state_gain"].get("boss", 1.0)
    duck = load_json("audio_config.json").get("boss", {}).get("duck_mus", -2)
    g_mus = GAIN * sg * DEFAULTS["vol_music"] * 10 ** (duck / 20)
    g_sig = DEFAULTS["vol_sfx"] * 10 ** (load_json("audio_config.json").get("boss", {}).get("sig_db", 0) / 20)   # 전용 곡 동안 신호 +dB
    d = os.path.join(ROOT, "assets", "music_generated", "boss")
    sig = {}
    for fam, ns in FAMILIES.items():
        vals = []
        for n in ns:
            p = os.path.join(ROOT, "assets", "sfx_generated", n + ".ogg")
            if os.path.exists(p):
                x = load(p) * g_sig
                vals.append((float(win_rms_db(band(x)).max()), float(win_rms_db(x).max())))
        sig[fam] = (min(v[0] for v in vals), min(v[1] for v in vals))   # 계열 안에서 가장 작은 소리 기준
    print("신호(1~3kHz / 전체, 가장 큰 100ms):", "  ".join(f"{k} {a:.1f}/{b:.1f}" for k, (a, b) in sig.items()))
    print(f"{'곡·페이즈':10} {'음악 1~3k':>9} {'음악 전체':>9}   신호−음악 1~3kHz (계열별)")
    worst = {k: (99.0, "") for k in sig}
    bad = 0
    for sid in names:
        n = len(songs[sid]["phases"])
        for i in range(1, n + 1):
            for var in ("", "_crisis"):
                parts = [f"{sid}_{i}_base", f"{sid}_{i}_choir", f"{sid}_{i}_lead", f"{sid}_{i}_perc{var}"]
                mix = None
                for pn in parts:
                    p = find(d, pn)
                    if p is None:
                        continue
                    x = load(p)
                    mix = x if mix is None else mix[: len(x)] + x[: len(mix)]
                if mix is None:
                    continue
                mix = mix * g_mus
                mb = float(np.percentile(win_rms_db(band(mix)), 90))
                mf = float(np.percentile(win_rms_db(mix), 90))
                diffs = {k: v[0] - mb for k, v in sig.items()}
                for k, v in diffs.items():
                    if v < worst[k][0]:
                        worst[k] = (v, f"{sid} {i}{'위기' if var else ''}")
                low = min(diffs.values())
                bad += low < WARN_DB
                tag = f"{sid} {i}{'위기' if var else ''}"
                print(f"{tag:10} {mb:9.1f} {mf:9.1f}   " + " ".join(f"{k}{v:+.0f}" for k, v in diffs.items())
                      + ("   ← 확인" if low < WARN_DB else ""))
    print("계열별 가장 나쁜 곳:", "  ".join(f"{k} {v:+.1f}dB({w})" for k, (v, w) in worst.items()))
    print("결과:", "ok (모든 신호가 음악보다 +3dB 이상)" if not bad else f"확인 {bad}곳 (+3dB 미만)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
