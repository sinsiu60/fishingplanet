"""녹음 느낌 그대로 쓰는 릴 소리 (비교용 시안): 녹음을 짧은 조각으로 잘라 이어 붙인다.

reel_from_recording.py 는 클릭 그레인(5ms)을 '일정한 간격'으로 다시 놓고 웅웅·이잉 합성음을 더해서
녹음의 불규칙한 '치르르륵 치르륵' 리듬과 클릭 사이 금속 울림이 사라진다. 여기서는
  감기  = 녹음에서 클릭 밀도(초당 클릭)가 목표 속도와 비슷한 0.12초 조각들을 골라 8ms 크로스페이드로 이어 붙임 (녹음 그대로)
  드랙  = 녹음 클릭 그레인 + '녹음의 실제 클릭 간격 패턴'을 목표 속도로 압축 (합성 톤 없음)
  지잉  = 드랙과 같은 방식으로 클릭 속도가 끝에서 급하게 치솟음 (합성 톤 없음)
"""
import os
import sys

import numpy as np
from scipy.io import wavfile
from scipy.signal import butter, find_peaks, resample, sosfilt

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
SR = 44100
W = int(0.12 * SR)          # 조각 길이
HOP = int(0.02 * SR)
XF = int(0.008 * SR)        # 조각 이음 크로스페이드


def f(x, kind, freq, order=2):
    return sosfilt(butter(order, freq, btype=kind, fs=SR, output="sos"), x)


class Source:
    def __init__(self, path):
        sr, x = wavfile.read(path)
        x = x.astype(float)
        if x.ndim > 1:
            x = x.mean(1)
        if sr != SR:
            x = resample(x, int(len(x) * SR / sr))
        self.x = x / (np.max(np.abs(x)) + 1e-9)
        h = f(self.x, "high", 2500, 4)
        env = f(np.abs(h), "low", 3000)
        pk, _ = find_peaks(env, distance=int(0.0015 * SR), prominence=env.max() * 0.05)
        self.clicks = pk
        # 조각 표: 시작 위치, 초당 클릭, 크기
        starts = np.arange(0, len(self.x) - W, HOP)
        cnt = np.searchsorted(pk, starts + W) - np.searchsorted(pk, starts)
        self.starts = starts
        self.rate = cnt / (W / SR)
        self.rms = np.array([np.sqrt(np.mean(self.x[s:s + W] ** 2)) for s in starts])
        # 클릭 간격 패턴 (뭉침 포함) — 드랙·지잉 타이밍용
        iv = np.diff(pk) / SR
        self.iv = iv[(iv > 0.0008) & (iv < 0.06)]
        # 그레인
        pre, post = int(0.0006 * SR), int(0.0045 * SR)
        win = np.concatenate([np.linspace(0, 1, pre), np.exp(-np.linspace(0, 4, post))])
        g = [self.x[p - pre:p + post] * win for p in pk if pre < p < len(self.x) - post]
        g = np.array(g)
        peaks = np.max(np.abs(g), 1)
        keep = peaks > np.percentile(peaks, 35)
        self.grains = g[keep] / peaks[keep][:, None]

    def chunks_like(self, rate, rng, n, tol=0.2):
        """초당 클릭이 rate 근처인 조각을 n샘플 넘게 이어 붙인다 (조각 크기는 그 속도 중앙값 ±3dB 안으로)."""
        ok = np.where(np.abs(self.rate - rate) <= tol * rate)[0]
        if len(ok) < 8:
            ok = np.argsort(np.abs(self.rate - rate))[:24]
        target = np.median(self.rms[ok])
        out = np.zeros(0)
        fade = np.sqrt(np.linspace(0, 1, XF))
        while len(out) < n:
            i = ok[rng.integers(len(ok))]
            seg = self.x[self.starts[i]:self.starts[i] + W].copy()
            seg *= np.clip(target / (self.rms[i] + 1e-9), 10 ** (-3 / 20), 10 ** (3 / 20))
            if len(out) == 0:
                out = seg
            else:
                out[-XF:] = out[-XF:] * fade[::-1] + seg[:XF] * fade
                out = np.concatenate([out, seg[XF:]])
        return out[:n]

    def click_times(self, rate_curve, rng):
        """녹음의 실제 클릭 간격 패턴(뭉침·빈틈)을 이어서, 평균 속도가 rate_curve 가 되게 시간축을 늘이고 줄인다."""
        mean_iv = float(np.mean(self.iv))
        n = len(rate_curve)
        times, t = [], 0.0
        k = rng.integers(len(self.iv))
        while True:
            i = min(n - 1, int(t * SR))
            t += self.iv[k % len(self.iv)] / mean_iv / max(1.0, rate_curve[i])
            k += 1
            if t * SR >= n:
                break
            times.append(t)
        return np.array(times)

    def place(self, n, times, amps, ratio=1.0, rng=None):
        out = np.zeros(n + 2000)
        for t, a in zip(times, amps):
            g = self.grains[rng.integers(len(self.grains))]
            if abs(ratio - 1) > 1e-3:
                g = resample(g, max(8, int(len(g) / ratio)))
            i = int(t * SR)
            out[i:i + len(g)] += g * a
        return out[:n]


TIER = {"wood": dict(ratio=0.88, lp=9000, shelf=0.0), "mid": dict(ratio=1.0, lp=None, shelf=0.0),
        "crystal": dict(ratio=1.12, lp=None, shelf=0.35)}
CLICKS_PER_REV = 55


def tier_color(y, tier):
    c = TIER[tier]
    if c["ratio"] != 1.0:   # 나무 = 살짝 낮고 둔하게 / 수정 = 살짝 높고 맑게 (길이는 그대로)
        y = resample(resample(y, int(len(y) / c["ratio"])), len(y))
    if c["lp"]:
        y = f(y, "low", c["lp"])
    if c["shelf"]:
        y = y + f(y, "high", 7000) * c["shelf"]
    return y


def make_loop(gen, n, xf=int(0.03 * SR)):
    s = gen(n + xf)
    out = s[:n].copy()
    w = np.linspace(0, 1, xf)
    out[:xf] = s[:xf] * w + s[n:n + xf] * (1 - w)
    return out


def reel_loop(src, rps, load, tier, rng):
    revs = max(2, int(round(rps * 1.6)))
    n = int(revs / rps * SR)
    rate = rps * CLICKS_PER_REV * (1 - 0.35 * load)

    def gen(m):
        y = src.chunks_like(rate, rng, m)
        if load > 0:   # 부하: 조금 둔하고 묵직하게 (녹음에 없는 저음은 넣지 않음)
            y = f(y, "low", 12000 - 5000 * load) * (1 + 0.2 * load)
        return tier_color(y, tier)

    return make_loop(gen, n)


def drag_loop(src, rate, tier, rng, dur=1.2):
    n = int(dur * SR)

    def gen(m):
        t = np.arange(m) / SR
        rc = rate * (1 + 0.04 * np.sin(2 * np.pi * 2.5 * t))
        tm = src.click_times(rc, rng)
        amps = np.clip(1 + 0.3 * rng.standard_normal(len(tm)), 0.3, 1.8)
        y = src.place(m, tm, amps, TIER[tier]["ratio"] * 1.1, rng)
        y += f(rng.standard_normal(m), "band", [3000, 9000]) * 0.04 * min(1.0, rate / 850)   # 줄 스침 (아주 약하게)
        return y

    return make_loop(gen, n)


def zing(src, grade, streak, tier, rng):
    dur, peak = {"small": (0.3, 420), "mid": (0.45, 650), "big": (0.6, 950)}[grade]
    peak *= 1 + 0.07 * streak
    n = int(dur * SR)
    u = np.linspace(0, 1, n)
    rc = 50 + (peak - 50) * (1 - u) ** 1.6    # '지이이잉↘': 처음 최고 → 점점 내려감
    a = u < 0.04
    rc[a] *= 0.75 + 0.25 * u[a] / 0.04
    rc = np.maximum(rc, 20)
    tm = src.click_times(rc, rng)
    amps = 1.2 - 0.6 * (tm / dur)            # 터질 때 가장 크고 점점 작아짐
    y = src.place(n, tm, amps, TIER[tier]["ratio"] * 1.1, rng)
    tail = np.zeros(int(0.08 * SR))
    g = src.grains[rng.integers(len(src.grains))] * 1.3     # 드랙이 다시 잡히는 '틱'
    tail[:len(g)] += g
    y = np.concatenate([y, tail])
    fl = int(0.004 * SR)
    y[-fl:] *= np.linspace(1, 0, fl)
    return y * {"small": 0.6, "mid": 0.78, "big": 0.89}[grade]


def norm(y, peak=0.89):
    y = f(y, "high", 120)
    return y / (np.max(np.abs(y)) + 1e-9) * peak
