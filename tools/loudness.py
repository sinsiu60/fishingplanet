"""효과음 음량 점검 (DESIGN.md 32-14, Phase S8).

구운 소리(assets/sfx_generated)마다 최대 음량(peak dBFS)과 '울리는 동안' 평균 음량(active RMS: −40dB 아래 조용한 부분은 빼고)을 재서
같은 버스 안에서 너무 튀거나(+4dB 넘게) 너무 작은(−8dB 넘게) 소리를 찾는다.

  python tools/loudness.py           표 + 튀는 소리 목록
  python tools/loudness.py --apply   너무 큰 소리는 레시피 gain_db 로 줄이고(버스 중앙값 +2dB 까지),
                                     너무 작은데 최대 음량 여유가 있으면 키운 뒤 → tools/bake_sfx.py 로 다시 굽기

버스 기준: sig(신호)는 다른 소리보다 커야 하므로 sfx 중앙값 +2dB 이상인지도 본다. 반복 바탕(amb_bed_*, loop)은 따로.
"""
import json
import os
import statistics
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import numpy as np  # noqa: E402

LOUD, QUIET, KEEP = 4.0, -8.0, 2.0


def db(x: float) -> float:
    return 20 * np.log10(max(x, 1e-9))


def measure(snd) -> tuple[float, float]:
    import pygame
    a = pygame.sndarray.array(snd).astype(np.float64) / 32768
    mono = np.abs(a).max(axis=1) if a.ndim > 1 else np.abs(a)
    peak = float(mono.max())
    # 10ms 창 RMS, −40dB 넘는 창만
    w = 441
    n = len(mono) // w
    if n == 0:
        return db(peak), db(peak)
    win = np.sqrt((a[: n * w].reshape(n, w, -1) ** 2).mean(axis=(1, 2)))
    act = win[win > peak * 10 ** (-40 / 20)]
    return db(peak), db(float(np.sqrt((act ** 2).mean())) if len(act) else 0.0)


def main(argv) -> int:
    import pygame
    pygame.mixer.init(44100, -16, 2, 512)
    from src.audio.sfx import Sfx
    from src.audio import synth
    sfx = Sfx()
    rec = synth.recipes()
    rows = []
    for name in sorted(sfx.sounds):
        pk, rms = measure(sfx.sounds[name])
        bus = sfx.bus_of(name)
        group = "bed" if rec.get(name, {}).get("loop") and name.startswith("amb_") else bus
        rows.append((name, group, pk, rms))
    med = {g: float(statistics.median(r[3] for r in rows if r[1] == g)) for g in {r[1] for r in rows}}
    print(f"{'소리':28s} {'묶음':7s} {'최대':>6s} {'평균':>6s} {'차이':>6s}")
    flagged = []
    for name, g, pk, rms in rows:
        d = rms - med[g]
        mark = " ▲ 큼" if d > LOUD else " ▼ 작음" if d < QUIET else ""
        if mark:
            flagged.append((name, g, pk, rms, d))
        print(f"{name:28s} {g:7s} {pk:6.1f} {rms:6.1f} {d:+6.1f}{mark}")
    print("\n묶음 중앙값(평균 음량 dBFS):", {g: round(v, 1) for g, v in sorted(med.items())})
    sig_ok = med.get("sig", -99) >= med.get("sfx", 0) - 1
    print(f"신호가 효과음보다 작지 않은가: {'예' if sig_ok else '아니오'} (sig {med.get('sig', 0):.1f} / sfx {med.get('sfx', 0):.1f})")
    print(f"\n튀는 소리 {len(flagged)}개")
    for f in flagged:
        print("  ", f[0], f[1], f"{f[4]:+.1f}dB")
    if "--apply" in argv and flagged:
        path = os.path.join("data", "sfx_recipes.json")
        data = json.load(open(path, encoding="utf-8"))
        changed = []
        for name, g, pk, rms, d in flagged:
            base = name.split("#")[0]
            r = data.get(base)
            if r is None:
                continue
            if d > LOUD:
                adj = -(d - KEEP)
            else:
                adj = min(-(d + KEEP), -1.0 - pk)  # 최대 음량 −1dBFS 를 넘지 않게
                if adj <= 0.2:
                    continue
            r["gain_db"] = float(round(r.get("gain_db", 0.0) + adj, 1))
            changed.append((base, r["gain_db"]))
        json.dump(data, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        subprocess.run([sys.executable, os.path.join("tools", "fmt_recipes.py")], check=True)
        print("\n고친 레시피:", changed, "\n→ python tools/bake_sfx.py 로 다시 굽기")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
