"""
원본 릴 녹음에서 성공음 꼬리용 짧은 릴 클립 자르기 (자르기 + 페이드만)
사용: python make_pull_samples.py [원본.wav] [출력 폴더]
"""
import sys, os
import numpy as np
from scipy.io import wavfile

here = os.path.dirname(os.path.abspath(__file__))
src = sys.argv[1] if len(sys.argv) > 1 else os.path.join(here, "source", "reel_recording.wav")
out = sys.argv[2] if len(sys.argv) > 2 else os.path.join(here, "pull_samples")
os.makedirs(out, exist_ok=True)

sr, x = wavfile.read(src)
x = x.astype(float) / 32768
if x.ndim == 1:
    x = x[:, None]


def onset(t0, look=0.25):
    a = int(t0 * sr)
    seg = np.abs(x[a:a + int(look * sr)]).mean(1)
    w = int(0.003 * sr)
    env = np.convolve(seg, np.ones(w) / w, "same")
    i = np.argmax(env > env.max() * 0.35)
    return t0 + max(0, i - int(0.004 * sr)) / sr


def clip(t0, dur, fout):
    a = int(t0 * sr)
    y = x[a:a + int(dur * sr)].copy()
    i, o = int(0.004 * sr), int(fout * sr)
    y[:i] *= np.linspace(0, 1, i)[:, None]
    y[-o:] *= (np.linspace(1, 0, o) ** 1.5)[:, None]
    return y


SOURCES = {"A": 22.46, "B": 7.77, "C": 37.27}
LENGTHS = {"pull_1_short": (0.18, 0.06), "pull_2_mid": (0.36, 0.09), "pull_3_long": (0.65, 0.12)}
clips = {}
for name, (d, fo) in LENGTHS.items():
    for v, t in SOURCES.items():
        clips[f"{name}_{v}"] = clip(onset(t), d, fo)
clips["pull_4_hook"] = clip(onset(32.29), 0.32, 0.1)
g = 0.89 / max(np.abs(c).max() for c in clips.values())
for name, c in clips.items():
    wavfile.write(os.path.join(out, name + ".wav"), sr, (c * g * 32767).astype(np.int16))
print(f"{len(clips)}개 → {out}")
