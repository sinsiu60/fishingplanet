"""
드랙 기반 "지이이잉" 합성 (실제 녹음 그레인 사용)
원리: 줄이 풀리는 속도 = 드랙 클릭 속도 = 들리는 음 높이
사용: python drag_zing.py 녹음파일.wav [출력폴더]
reel_from_recording.py와 같은 폴더(tools/audio/)에 있어야 함
"""
import sys, os
import numpy as np
from scipy.io import wavfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from reel_from_recording import load, extract_grains, place, events, finish, f, SR, RNG


def line_speed_drag(G, bed, rate, catch_click=True, grain_pitch=1.12):
    """rate: 시간별 드랙 클릭 속도(회/초) 배열 = 줄 풀리는 속도"""
    n = len(rate)
    tm = events(rate)
    amps = np.clip(1 + 0.12 * RNG.standard_normal(len(tm)), 0.5, 1.5)
    ratios = grain_pitch * (1 + 0.015 * RNG.standard_normal(len(tm)))
    clicks = place(n, tm, G, amps, ratios)
    speed = rate / rate.max()
    # 스풀 회전음: 클릭 속도가 빨라지면 음이 생김 (실제 드랙의 '잉' 성분)
    ph = 2 * np.pi * np.cumsum(rate) / SR
    whine = f(np.sin(ph) + 0.45 * np.sin(2 * ph) + 0.2 * np.sin(3 * ph), "low", 7000) * 0.35 * speed ** 1.5
    # 줄이 가이드를 스치는 소리
    hiss = f(RNG.standard_normal(n), "band", [2500, 8000]) * 0.12 * speed
    sig = f(clicks, "low", 11000) + whine + hiss + np.resize(bed, n) * 0.08 * speed
    if catch_click:  # 드랙이 다시 잡히는 순간 "틱"
        tail = np.zeros(int(0.08 * SR))
        g = G[RNG.integers(len(G))] * 1.3
        tail[:len(g)] += g
        sig = np.concatenate([sig, tail])
    return sig


def curve(dur, pts):
    """(시간비율, 속도) 점들을 부드럽게 잇는 속도 곡선"""
    t = np.linspace(0, 1, int(dur * SR))
    xs, ys = zip(*pts)
    return np.interp(t, xs, ys)


def run(G, bed):
    """돌진: 물고기가 가속하며 줄을 빼 감 → 피치 상승, 지치며 하강"""
    r = curve(2.6, [(0, 40), (0.08, 250), (0.25, 820), (0.55, 760), (0.8, 380), (1, 30)])
    r *= 1 + 0.05 * np.sin(2 * np.pi * np.linspace(0, 2.6, len(r)) * 3.3)  # 물고기 몸부림 흔들림
    return finish(line_speed_drag(G, bed, r))


def success(G, bed, grade="big", streak=0, grain_pitch=1.12):
    """패턴 성공: 드랙이 순간 확 풀렸다 잡힘 (피치가 끝에서 급하게 치솟고 '틱')"""
    spec = {"small": (0.3, 420), "mid": (0.45, 650), "big": (0.6, 950)}
    dur, peak = spec[grade]
    peak *= 1 + 0.07 * streak
    t = np.linspace(0, 1, int(dur * SR))
    r = 60 + (peak - 60) * t ** 2.4  # 끝에서 급하게
    r[t > 0.9] = peak * np.exp(-(t[t > 0.9] - 0.9) * 40)  # 드랙이 잡히며 급정지
    gain = {"small": 0.6, "mid": 0.78, "big": 0.89}[grade]
    return finish(line_speed_drag(G, bed, np.maximum(r, 20), grain_pitch=grain_pitch), gain)


def double(G, bed):
    a = success(G, bed, "big")
    b = success(G, bed, "big", streak=4)
    o = len(a) - int(0.05 * SR)
    out = np.zeros(o + len(b))
    out[:len(a)] += a
    out[o:] += b
    return finish(out)


def save(d, name, x):
    wavfile.write(os.path.join(d, name), SR, (x * 32767).astype(np.int16))
    print(f"{name}: {len(x) / SR:.2f}s")


if __name__ == "__main__":
    src = sys.argv[1]
    out = sys.argv[2] if len(sys.argv) > 2 else os.path.dirname(os.path.abspath(__file__))
    G, BED = extract_grains(load(src))
    save(out, "drag_run.wav", run(G, BED))
    for g in ["small", "mid", "big"]:
        save(out, f"zing_{g}.wav", success(G, BED, g))
    save(out, "zing_double.wav", double(G, BED))
    gap = np.zeros(int(0.5 * SR))
    demo = np.concatenate([run(G, BED), gap, success(G, BED, "small"), gap,
                           success(G, BED, "mid"), gap, success(G, BED, "big"), gap, double(G, BED)])
    save(out, "demo_drag_zing.wav", demo / np.max(np.abs(demo)) * 0.89)
