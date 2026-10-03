"""
패턴 성공 사운드: "쒸익-팽!" (줄이 물을 가르며 팽팽해지는 순간)
주인공: 팽팽해진 낚싯줄의 울림 (연속 성공할수록 음이 한 단계씩 올라감)
보조: 줄이 물을 가르는 소리, 낚싯대에 힘이 실리는 저음, 물고기가 끌려오는 물소리, 원본 릴 꼬리
사용: python make_success_sfx.py [릴 샘플 폴더] [출력 폴더]
"""
import sys, os
import numpy as np
from scipy.io import wavfile
from scipy.signal import butter, sosfilt

SR = 44100
RNG = np.random.default_rng(5)


def bp(x, lo, hi, o=2):
    return sosfilt(butter(o, [lo, hi], "band", fs=SR, output="sos"), x)


def lp(x, f):
    return sosfilt(butter(2, f, "low", fs=SR, output="sos"), x)


def hp(x, f):
    return sosfilt(butter(2, f, "high", fs=SR, output="sos"), x)


def norm(x, p=1.0):
    return x / (np.max(np.abs(x)) + 1e-9) * p


def water_zip(dur, power):
    """줄이 물을 가르며 당겨지는 '쒸익': 점점 높아지는 물살 노이즈"""
    n = int(dur * SR)
    t = np.linspace(0, 1, n)
    noise = RNG.standard_normal(n)
    lo_band = bp(noise, 600, 1800)
    hi_band = bp(noise, 2200, 6500)
    y = lo_band * (1 - t) + hi_band * t
    e = np.minimum(1, t / 0.15) * np.exp(-np.maximum(0, t - 0.6) * 9)
    y *= e * (1 + 0.4 * lp(np.abs(RNG.standard_normal(n)), 40))
    return norm(y, power)


def line_twang(freq, dur, power):
    """팽팽해진 낚싯줄의 '팽!' (튕긴 줄 + 금속성 배음)"""
    n = int(dur * SR)
    p = int(SR / freq)
    buf = RNG.uniform(-1, 1, p) * np.hanning(p)
    y = np.zeros(n)
    for i in range(n):
        y[i] = buf[i % p]
        buf[i % p] = 0.5 * (buf[i % p] + buf[(i + 1) % p]) * 0.994
    tt = np.arange(n) / SR
    ping = np.sin(2 * np.pi * freq * 2.76 * tt) * np.exp(-tt / 0.03) * 0.35
    snap = hp(RNG.standard_normal(n), 3000) * np.exp(-tt / 0.004) * 0.8  # 순간 '딱'
    y = lp(y, 7000) * np.exp(-tt / (dur * 0.35)) + ping + snap
    return norm(y, power)


def rod_thump(power, low=70):
    """낚싯대에 힘이 확 실리는 묵직한 저음"""
    n = int(0.16 * SR)
    tt = np.arange(n) / SR
    f = low + (low * 1.8 - low) * np.exp(-tt / 0.02)
    y = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-tt / 0.045)
    y += 0.25 * np.sin(4 * np.pi * np.cumsum(f) / SR) * np.exp(-tt / 0.03)  # 폰 스피커용 중음
    return norm(y, power)


def bubbles(n, count):
    y = np.zeros(n)
    for _ in range(count):
        d = RNG.uniform(0.008, 0.028)
        m = int(d * SR)
        s = RNG.integers(0, max(1, n - m))
        tt = np.arange(m) / SR
        f0 = RNG.uniform(400, 1300)
        y[s:s + m] += np.sin(2 * np.pi * np.cumsum(f0 * (1 + 2.5 * tt / d)) / SR) * np.exp(-tt / (d / 3))
    return y


def water_pull(dur, power, splashy=False):
    """물고기가 끌려오는 물소리"""
    n = int(dur * SR)
    tt = np.arange(n) / SR
    y = bp(RNG.standard_normal(n), 300, 2500) * np.exp(-tt / (dur * 0.35))
    if splashy:
        y += 1.4 * lp(RNG.standard_normal(n), 3500) * np.exp(-tt / 0.07)
    y = norm(y) + 0.4 * norm(bubbles(n, 10 if not splashy else 20))
    return norm(y, power)


def load(path):
    sr, x = wavfile.read(path)
    x = x.astype(float) / 32768
    return x.mean(1) if x.ndim > 1 else x


def place(n, parts):
    out = np.zeros(n)
    for start, sig, gain in parts:
        i = int(start * SR)
        out[i:i + len(sig)] += sig[: n - i] * gain
    return out


def finish(x):
    x[: int(0.002 * SR)] *= np.linspace(0, 1, int(0.002 * SR))
    r = int(0.03 * SR)
    x[-r:] *= np.linspace(1, 0, r)
    x = np.tanh(norm(x) * 1.3)
    return norm(x, 0.89)


# 연속 성공 음 단계: 도 → 레 → 미 (장력이 올라가는 느낌 + 보상감)
STEPS = [1.0, 9 / 8, 5 / 4]
BASE = 520


def success(grade, streak, R):
    f = BASE * STEPS[streak]
    if grade == "small":
        n = int(0.42 * SR)
        parts = [(0.00, water_zip(0.09, 1), 0.35),
                 (0.025, line_twang(f, 0.3, 1), 0.85),
                 (0.025, rod_thump(1, 85), 0.22),
                 (0.09, R["1"], 0.18)]
    elif grade == "mid":
        n = int(0.62 * SR)
        parts = [(0.00, water_zip(0.12, 1), 0.45),
                 (0.03, line_twang(f, 0.4, 1), 0.9),
                 (0.03, rod_thump(1, 75), 0.38),
                 (0.07, water_pull(0.3, 1), 0.3),
                 (0.15, R["2"], 0.22)]
    else:  # big (퍼펙트·콤보 완료)
        n = int(0.95 * SR)
        parts = [(0.00, water_zip(0.16, 1), 0.55),
                 (0.04, line_twang(f * 0.75, 0.6, 1), 0.85),   # 한 옥타브 아래 느낌의 굵은 줄
                 (0.04, line_twang(f * 1.5, 0.35, 1), 0.35),   # 위로 5도, 반짝임
                 (0.04, rod_thump(1, 60), 0.6),
                 (0.08, water_pull(0.45, 1, splashy=True), 0.45),
                 (0.04, R["hook"], 0.3),
                 (0.22, R["3"], 0.2)]
    return finish(place(n, parts))


def double(R):
    a = success("big", 0, R)
    b = success("big", 2, R)
    o = int(0.42 * SR)
    out = np.zeros(o + len(b))
    out[: len(a)] += a
    out[o:] += b
    return finish(out)


def save(d, name, x):
    wavfile.write(os.path.join(d, name), SR, (x * 32767).astype(np.int16))
    print(name)


if __name__ == "__main__":
    here = os.path.dirname(os.path.abspath(__file__))
    rdir = sys.argv[1] if len(sys.argv) > 1 else os.path.join(here, "pull_samples")
    out = sys.argv[2] if len(sys.argv) > 2 else here
    R = {"1": load(os.path.join(rdir, "pull_1_short_A.wav")), "2": load(os.path.join(rdir, "pull_2_mid_A.wav")),
         "3": load(os.path.join(rdir, "pull_3_long_A.wav")), "hook": load(os.path.join(rdir, "pull_4_hook.wav"))}
    os.makedirs(os.path.join(out, "all"), exist_ok=True)
    clips = {}
    for g in ["small", "mid", "big"]:
        for k in range(3):
            clips[(g, k)] = success(g, k, R)
            save(os.path.join(out, "all"), f"success_{g}_k{k}.wav", clips[(g, k)])
    dbl = double(R)
    save(os.path.join(out, "all"), "success_double.wav", dbl)
    save(out, "1_작은성공.wav", clips[("small", 0)])
    save(out, "2_성공.wav", clips[("mid", 0)])
    save(out, "3_퍼펙트.wav", clips[("big", 0)])
    save(out, "4_더블퍼펙트.wav", dbl)
    g = lambda s: np.zeros(int(s * SR))
    seq = [clips[("small", 0)], g(0.5), clips[("small", 1)], g(0.5), clips[("small", 2)], g(1.0),
           clips[("mid", 0)], g(0.5), clips[("mid", 1)], g(0.5), clips[("mid", 2)], g(1.0),
           clips[("big", 0)], g(0.8), dbl, g(1.2),
           clips[("small", 0)], g(0.7), clips[("mid", 1)], g(0.9), clips[("big", 2)]]
    save(out, "0_미리듣기.wav", finish(np.concatenate(seq)))
