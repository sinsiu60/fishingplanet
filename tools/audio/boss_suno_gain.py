"""SUNO 전설 보스 곡 음량 측정 → data/music/boss_bgm_gain.json (BOSS_BGM_SUNO.md 음량 규칙, 개발용 — ffmpeg · pyloudnorm · scipy).

곡 하나의 모든 파일(인트로 · 반복 구간 · 브리지 · 포획 타격)을 이어 붙여 통합 음량(LUFS)과 최대 트루피크(dBTP, 4배 오버샘플)를 재고,
평균 -14 LUFS 근처 · 최대 -1 dBTP 가 되는 **한 배율**을 곡마다 정한다 (층 사이 균형 유지). 게임은 그 배율을 채널 음량에 곱한다
(배율 × 보스 버스(0.35 × state_gain …, 1 미만) 를 채널 음량으로 — 곱이 1.0 을 넘으면 거기서 자름).

  python tools/audio/boss_suno_gain.py           12곡 전부
  python tools/audio/boss_suno_gain.py yeoubi    그 곡만
"""
import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(ROOT)
import numpy as np  # noqa: E402

TARGET_LUFS, TARGET_TP = -14.0, -1.0
RATE = 44100


def load(path: str) -> np.ndarray:
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-f", "f32le", "-ac", "2", "-ar", str(RATE), "-"],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.float32).reshape(-1, 2).astype(np.float64)


def true_peak_db(x: np.ndarray) -> float:
    from scipy.signal import resample_poly
    up = resample_poly(x, 4, 1, axis=0)
    return 20 * np.log10(max(1e-9, float(np.abs(up).max())))


def main(argv) -> int:
    import pyloudnorm as pyln
    idx = json.load(open("data/music/boss_bgm_index.json", encoding="utf-8"))
    only = set(argv)
    out_path = "data/music/boss_bgm_gain.json"
    out = json.load(open(out_path, encoding="utf-8")) if os.path.exists(out_path) else {}
    meter = pyln.Meter(RATE)
    for e in idx["legends"]:
        sid = e["id"]
        if only and sid not in only:
            continue
        folder = os.path.join(ROOT, e["folder"])
        m = json.load(open(os.path.join(folder, "markers.json"), encoding="utf-8"))
        parts = [load(os.path.join(folder, f["file"])) for f in m["files"].values()]
        crisis = [load(os.path.join(folder, fn)) for fn in m.get("crisis_layers", {}).values()]
        whole = np.concatenate(parts)
        lufs = meter.integrated_loudness(whole)
        tp = max(true_peak_db(p) for p in parts + crisis)
        gain_db = min(TARGET_LUFS - lufs, TARGET_TP - tp)
        gain = 10 ** (gain_db / 20)   # 1.0 을 넘어도 그대로 적는다 — 게임의 보스 버스(< 1) 와 곱한 뒤 채널에서 1.0 으로 자름
        out[sid] = {"lufs": round(lufs, 2), "true_peak_db": round(tp, 2), "gain_db": round(gain_db, 2), "gain": round(gain, 4)}
        print(f"{sid:9} LUFS {lufs:6.2f}  TP {tp:6.2f} dBTP  → 배율 {gain:.3f} ({gain_db:+.1f} dB)")
    json.dump(out, open(out_path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
