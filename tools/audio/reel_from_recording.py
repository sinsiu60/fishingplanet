"""
실제 릴 녹음 기반 효과음 재합성기
- 녹음에서 개별 클릭(그레인)을 수천 개 잘라내고, 원하는 속도·부하에 맞춰 다시 배치
- 녹음의 금속 질감은 그대로, 속도·부하·지잉은 자유롭게
사용: python reel_from_recording.py 녹음파일.wav [출력폴더]
(mp3는 먼저 wav로 변환: ffmpeg -i reel.mp3 -ac 1 -ar 44100 reel.wav)
"""
import sys, os
import numpy as np
from scipy.io import wavfile
from scipy.signal import butter, sosfilt, find_peaks, resample

SR = 44100
RNG = np.random.default_rng(11)


def f(x, kind, freq, order=2):
    return sosfilt(butter(order, freq, btype=kind, fs=SR, output="sos"), x)


def load(path):
    sr, x = wavfile.read(path)
    x = x.astype(float)
    if x.ndim > 1:
        x = x.mean(1)
    x /= np.max(np.abs(x)) + 1e-9
    if sr != SR:
        x = resample(x, int(len(x) * SR / sr))
    return x


def extract_grains(x):
    """녹음에서 클릭 그레인 추출 (각 약 5ms)"""
    hp = f(x, "high", 2500, 4)
    env = f(np.abs(hp), "low", 800)
    pk, _ = find_peaks(env, distance=int(0.003 * SR), prominence=env.max() * 0.04)
    pre, post = int(0.0006 * SR), int(0.0045 * SR)
    win = np.concatenate([np.linspace(0, 1, pre), np.exp(-np.linspace(0, 4, post))])
    grains = []
    for p in pk:
        if pre < p < len(x) - post:
            g = x[p - pre:p + post] * win
            grains.append(g)
    grains = np.array(grains)
    peaks = np.max(np.abs(grains), 1)
    keep = peaks > np.percentile(peaks, 35)  # 너무 약한 클릭 제외
    grains = grains[keep] / peaks[keep][:, None]
    # 배경 질감: 클릭 사이의 잔잔한 소리를 잘라 반복용으로
    quiet = hp.copy()
    quiet[np.abs(env) > np.percentile(env, 60)] = 0
    bed = quiet[np.abs(quiet) > 0][: SR * 4]
    bed = bed / (np.max(np.abs(bed)) + 1e-9)
    return grains, bed


def pitch(g, ratio):
    if abs(ratio - 1) < 1e-3:
        return g
    return resample(g, max(8, int(len(g) / ratio)))


def place(n, times, grains, amps, ratios):
    out = np.zeros(n + 2000)
    for t, a, r in zip(times, amps, ratios):
        g = pitch(grains[RNG.integers(len(grains))], r) * a
        i = int(t * SR)
        if i + len(g) < len(out):
            out[i:i + len(g)] += g
    return out[:n]


def body_hum(rate_curve, amount):
    """녹음에 거의 없는 저중음 무게감을 아주 살짝 보강"""
    ph = 2 * np.pi * np.cumsum(rate_curve) / SR
    h = np.sin(ph) + 0.4 * np.sin(2 * ph) + 0.2 * np.sin(3 * ph)
    return f(h, "low", 1500) * amount


def finish(x, peak=0.89):
    x = f(x, "high", 120)
    fl = int(0.006 * SR)
    x[:fl] *= np.linspace(0, 1, fl)
    x[-fl:] *= np.linspace(1, 0, fl)
    x = np.tanh(x / (np.max(np.abs(x)) + 1e-9) * 1.2)
    return x / np.max(np.abs(x)) * peak


def rate_profile(dur, rate, accel=0.15, decel=0.12):
    t = np.arange(int(dur * SR)) / SR
    r = np.full_like(t, rate)
    a = t < accel
    r[a] = rate * (t[a] / accel) ** 0.7 + 1
    d = t > dur - decel
    r[d] = rate * np.clip((dur - t[d]) / decel, 0, 1) ** 1.5 + 1
    r *= 1 + 0.04 * np.sin(2 * np.pi * 0.8 * t)
    return r


def events(rate_curve):
    ph = np.cumsum(rate_curve) / SR
    idx = np.where(np.diff(np.floor(ph)) > 0)[0]
    return idx / SR


def reel(G, bed, dur=3.0, rate=110, load=0.0, stop_click=True):
    """rate: 초당 클릭 수 (느림 70, 보통 110, 빠름 170) / load: 0~1"""
    rc = rate_profile(dur, rate * (1 - 0.35 * load))
    n = len(rc)
    tm = events(rc)
    tm = tm + RNG.normal(0, 0.00025, len(tm))  # 미세한 불규칙
    amps = np.clip(1 + 0.22 * RNG.standard_normal(len(tm)), 0.3, 1.8)
    handle = np.sin(2 * np.pi * tm * (rate / 22))  # 핸들 한 바퀴 주기
    amps *= 1 + 0.15 * handle
    ratios = np.full(len(tm), 1 - 0.12 * load) * (1 + 0.02 * RNG.standard_normal(len(tm)))
    clicks = place(n, tm, G, amps, ratios)
    level = np.clip(rc / rate, 0, 1)
    b = np.resize(bed, n) * 0.12 * level * (1 + 1.5 * load)
    sig = clicks + b + body_hum(rc * 0.5, 0.06 + 0.08 * load) * level
    if load > 0:
        sig = f(sig, "low", 9000 - 3500 * load) * (1 + 0.15 * load)
    if stop_click:
        tail = np.zeros(int(0.12 * SR))
        g = pitch(G[RNG.integers(len(G))], 0.8) * 1.6
        tail[:len(g)] += g
        g2 = pitch(G[RNG.integers(len(G))], 1.05) * 0.7
        o = int(0.016 * SR)
        tail[o:o + len(g2)] += g2
        sig = np.concatenate([sig, tail])
    return finish(sig)


def drag(G, bed, dur=2.6, peak_rate=320):
    n = int(dur * SR)
    t = np.arange(n) / SR
    rc = peak_rate * np.clip(np.sin(np.pi * t / dur), 0, 1) ** 0.6 * (1 + 0.07 * np.sin(2 * np.pi * 3 * t)) + 5
    tm = events(rc)
    amps = np.clip(1 + 0.15 * RNG.standard_normal(len(tm)), 0.4, 1.6)
    ratios = 1.15 + 0.02 * RNG.standard_normal(len(tm))
    clicks = place(n, tm, G, amps, ratios)
    hiss = f(RNG.standard_normal(n), "band", [3000, 9000]) * 0.08 * rc / peak_rate
    return finish(clicks + hiss + np.resize(bed, n) * 0.1)


def zing(G, grade="big", streak=0):
    """패턴 성공 지이잉: 클릭이 촘촘해지며 한 음으로 뭉치고 피치가 끝에서 급하게 치솟음"""
    spec = {"small": (0.35, 1.5, 0.55), "mid": (0.5, 2.0, 0.75), "big": (0.7, 3.0, 1.0)}
    dur, up, gain = spec[grade]
    start = 90 * (1 + 0.08 * streak)
    n = int(dur * SR)
    t = np.arange(n) / SR
    k = (t / dur) ** 2.6  # 끝에서 급하게
    rc = start * (1 + (up * 5 - 1) * k)  # 클릭 속도 상승 → 높은 음으로 뭉침
    tm = events(rc)
    pr = 1 + (up - 1) * (tm / dur) ** 2.6
    amps = 0.6 + 0.6 * (tm / dur)
    clicks = place(n, tm, G, amps, pr)
    tone_ph = 2 * np.pi * np.cumsum(rc) / SR
    tone = f(np.sin(tone_ph) + 0.35 * np.sin(2 * tone_ph), "low", 6000) * 0.45 * k
    env = np.minimum(1, t / 0.02) * np.where(t > dur * 0.88, np.exp(-(t - dur * 0.88) / 0.025), 1)
    sig = (f(clicks, "low", 11000) + tone) * env
    # 정점 금속 울림
    rl = int(0.18 * SR)
    rt = np.arange(rl) / SR
    fpk = rc[int(n * 0.88)] * 3.2
    ring = (np.sin(2 * np.pi * fpk * rt) + 0.5 * np.sin(2 * np.pi * fpk * 1.51 * rt)) * np.exp(-rt / 0.035) * 0.35
    out = np.zeros(n + rl)
    out[:n] += sig
    o = int(n * 0.88)
    out[o:o + rl] += ring
    return finish(out, 0.89 * gain)


def double_zing(G):
    a = zing(G, "big")
    b = zing(G, "big", streak=3)
    b = pitch(b, 1.33)
    gap = int(0.08 * SR)
    out = np.zeros(len(a) + gap + len(b))
    out[:len(a)] += a
    out[len(a) - int(0.1 * SR) + gap:][:len(b)] += b[: len(out) - (len(a) - int(0.1 * SR) + gap)]
    return finish(out)


def save(d, name, x):
    wavfile.write(os.path.join(d, name), SR, (x * 32767).astype(np.int16))
    print(f"{name}: {len(x) / SR:.2f}s")


if __name__ == "__main__":
    src = sys.argv[1]
    out = sys.argv[2] if len(sys.argv) > 2 else os.path.dirname(os.path.abspath(__file__))
    os.makedirs(out, exist_ok=True)
    G, BED = extract_grains(load(src))
    print("grains:", len(G))
    save(out, "reel_slow.wav", reel(G, BED, 3.0, 70))
    save(out, "reel_normal.wav", reel(G, BED, 3.0, 110))
    save(out, "reel_fast.wav", reel(G, BED, 3.0, 170))
    save(out, "reel_under_load.wav", reel(G, BED, 3.5, 130, load=0.85))
    save(out, "drag_scream.wav", drag(G, BED))
    save(out, "zing_small.wav", zing(G, "small"))
    save(out, "zing_mid.wav", zing(G, "mid"))
    save(out, "zing_big.wav", zing(G, "big"))
    save(out, "zing_double.wav", double_zing(G))
    gap = np.zeros(int(0.3 * SR))
    demo = np.concatenate([reel(G, BED, 2.0, 110), gap, drag(G, BED, 2.0), gap[:4000],
                           reel(G, BED, 2.4, 130, load=0.85), gap[:6000], zing(G, "big"),
                           gap, reel(G, BED, 1.6, 170), gap[:6000], double_zing(G)])
    save(out, "demo_sequence.wav", demo / np.max(np.abs(demo)) * 0.89)
