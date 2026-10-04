"""소리 구역 측정 (DESIGN.md 39, AUDIO_ZONES.md Z5-1): 바깥 버전과 실내 버전의 음량(RMS) 차이와 고음 성분 차이.

  python tools/audio_zone_check.py

음량 설정 = zones.json 표(AUDIO_ZONES.md 2번)대로 건 음량. 전체 = 실제 RMS 차이 (고음 깎기 손실 포함 — 고음 많은 소리는 더 작아짐).
고음 = 깎기 주파수 위 에너지의 차이 (전체보다 더 많이 줄어야 '먹먹함').
"""
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
os.chdir(ROOT)
import bake_indoor as B  # noqa: E402


def hf_energy(st: np.ndarray, hz: float) -> float:
    m = st.mean(axis=1)
    sp = np.abs(np.fft.rfft(m)) ** 2
    f = np.fft.rfftfreq(len(m), 1 / B.RATE)
    return float(sp[f >= hz].sum() / len(m) + 1e-15)


def peak_level(name: str, vol: float) -> float:
    """50ms 창 RMS 의 최대 (dBFS × 재생 음량)."""
    a = B.load(B.source_of(name, ("sfx", "sfx_generated", "sfx_indoor", "music_generated")))
    m = a.mean(axis=1)
    w = 2205
    fr = [np.sqrt(np.mean(m[i:i + w] ** 2)) for i in range(0, max(1, len(m) - w), w)]
    return 20 * np.log10(max(fr) * vol + 1e-12)


def balance() -> int:
    """실내 소리 < 대화 말소리 - 3dB, 장소 음악은 바깥 테마 기준 (zones.json '_음량')."""
    z = B.zones()
    import json as _j
    npcs = _j.load(open(os.path.join(ROOT, "data", "interiors.json"), encoding="utf-8"))["npcs"]
    voice = min(peak_level(f"{v['voice']['sound']}{i}", v["voice"]["vol"]) for v in npcs.values() if v["voice"]["vol"] > 0
                for i in range(3))
    rc = z["room_common"]
    items = [rc["air"], rc["storm_wind"], rc["thunder_rattle"], rc["rain"]["rain"], rc["rain"]["storm"]]
    for zz in z["zones"].values():
        items += [[r[0].rstrip("#") + ("0" if r[0].endswith("#") else ""), r[2]] for r in zz.get("room_sounds", [])]
    print(f"\n실내 소리 음량 (말소리 가장 작은 것 {voice:.1f}dB, 기준 {voice - 3:.1f}dB 아래)")
    bad = 0
    for n, v in items:
        L = peak_level(n, v)
        ok = L <= voice - 3 + 0.3
        bad += not ok
        print(f"  {n:<24}{L:7.1f}  {'ok' if ok else '말소리보다 큼'}")
    return bad


def main() -> int:
    z = B.zones()
    rows = []
    bad = 0
    for name, (fn, src, ex) in B.jobs().items():
        if not name.endswith("~indoor"):
            continue
        base = name[:-7]
        cat = B.category(base, z["names"])
        db, hz = z["occlusion"][cat]
        p = os.path.join(B.OUT, name.replace("#", "__") + ".ogg")
        if not os.path.exists(p):
            print("없음:", p)
            bad += 1
            continue
        a, b = B.load(src), B.load(p)
        d = 20 * np.log10(B.rms(b) / B.rms(a))
        e0, e1 = hf_energy(a, hz), hf_energy(b, hz)
        hd = 10 * np.log10(e1 / e0)
        has_hf = e0 > 1e-6 * (B.rms(a) ** 2 + 1e-12) * 1e3
        ok = d <= db + 0.6 and (not has_hf or hd <= d + 0.5)
        bad += not ok
        rows.append((base, cat, db, d, hz, hd if has_hf else None, "ok" if ok else "확인"))
    print(f"{'소리':<20}{'종류':<12}{'음량설정':>8}{'전체dB':>8}{'깎기Hz':>8}{'고음dB':>8}")
    for r in rows:
        hs = f"{r[5]:>8.1f}" if r[5] is not None else f"{'-':>8}"
        print(f"{r[0]:<20}{r[1]:<12}{r[2]:>8}{r[3]:>8.1f}{r[4]:>8}{hs}  {r[6]}")
    bad += balance()
    print("결과:", "ok" if not bad else f"{bad}개 확인 필요")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
