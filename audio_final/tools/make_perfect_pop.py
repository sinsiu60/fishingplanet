"""
퍼펙트 "팡!" 레이어: 노란 이펙트가 터지는 순간과 맞추는 소리
- 팡: 이펙트가 터지는 순간의 밝고 짧은 파열음
- 반짝임: 노란 빛이 퍼졌다 사라지는 동안의 금빛 잔향 (줄 '팽' 음과 화음이 맞게)
기존 make_success_sfx.py와 같은 폴더에서 실행
사용: python make_perfect_pop.py [릴 샘플 폴더] [출력 폴더]
"""
import sys, os
import numpy as np
from scipy.io import wavfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import make_success_sfx as S

SR, RNG = S.SR, np.random.default_rng(9)
FLASH_AT = 0.04      # 퍼펙트 '팽'과 같은 순간 (초)
GLOW_LEN = 0.30      # 노란 빛이 퍼졌다 사라지는 시간 (이펙트 길이와 맞출 것)


def pop(power=1.0):
    """팡: 순간 파열 + 짧은 공기 펀치"""
    n = int(0.09 * SR)
    t = np.arange(n) / SR
    burst = S.bp(RNG.standard_normal(n), 1200, 7000) * np.exp(-t / 0.006)
    f = 90 + 110 * np.exp(-t / 0.012)
    punch = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t / 0.025)
    click = np.sin(2 * np.pi * 3200 * t) * np.exp(-t / 0.005)
    return S.norm(S.norm(burst) + 0.5 * punch + 0.8 * click, power)


def glow(base_freq, dur=GLOW_LEN, power=1.0):
    """반짝임: '팽' 음 기준 장3화음 위쪽 배음 + 흩어지는 작은 반짝 소리"""
    n = int(dur * SR)
    t = np.arange(n) / SR
    y = np.zeros(n)
    for ratio, amp in [(2.0, 1.0), (2.5, 0.7), (3.0, 0.6), (4.0, 0.35)]:
        f = base_freq * ratio
        y += amp * np.sin(2 * np.pi * f * t + RNG.uniform(0, 6.28)) * np.exp(-t / (dur * 0.33))
    y *= np.minimum(1, t / 0.006)
    tinkles = np.zeros(n)
    notes = [base_freq * r for r in (6, 7.5, 8, 9, 10, 12)]
    for k in range(7):
        s = int(RNG.uniform(0.01, dur * 0.75) * SR)
        m = int(0.05 * SR)
        tt = np.arange(m) / SR
        f = RNG.choice(notes)
        seg = np.sin(2 * np.pi * f * tt) * np.exp(-tt / 0.012) * (1 - s / n)
        tinkles[s:s + m] += seg[: n - s]
    return S.norm(S.norm(y) + 0.45 * S.norm(tinkles), power)


def perfect_with_pop(streak, R):
    base = S.success("big", streak, R)
    f = S.BASE * S.STEPS[streak]
    n = len(base)
    layer = S.place(n, [(FLASH_AT, pop(), 1.4), (FLASH_AT + 0.005, glow(f), 0.5)])
    return S.finish(base / np.max(np.abs(base)) + layer)


def double_with_pop(R):
    a = perfect_with_pop(0, R)
    b = perfect_with_pop(2, R)
    o = int(0.42 * SR)
    out = np.zeros(o + len(b))
    out[: len(a)] += a
    out[o:] += b
    return S.finish(out)


if __name__ == "__main__":
    here = os.path.dirname(os.path.abspath(__file__))
    rdir = sys.argv[1] if len(sys.argv) > 1 else os.path.join(here, "pull_samples")
    out = sys.argv[2] if len(sys.argv) > 2 else here
    R = {"1": S.load(os.path.join(rdir, "pull_1_short_A.wav")), "2": S.load(os.path.join(rdir, "pull_2_mid_A.wav")),
         "3": S.load(os.path.join(rdir, "pull_3_long_A.wav")), "hook": S.load(os.path.join(rdir, "pull_4_hook.wav"))}
    os.makedirs(os.path.join(out, "all"), exist_ok=True)
    pp = [perfect_with_pop(k, R) for k in range(3)]
    for k, x in enumerate(pp):
        S.save(os.path.join(out, "all"), f"success_big_pop_k{k}.wav", x)
    d = double_with_pop(R)
    S.save(os.path.join(out, "all"), "success_double_pop.wav", d)
    S.save(out, "3_퍼펙트_팡.wav", pp[0])
    S.save(out, "4_더블퍼펙트_팡.wav", d)
    S.save(os.path.join(out, "stems"), "perfect_pop.wav", S.finish(pop()))
    S.save(os.path.join(out, "stems"), "perfect_glow.wav", S.finish(glow(S.BASE)))
    g = lambda s: np.zeros(int(s * SR))
    old = S.success("big", 0, R)
    seq = [old, g(0.8), pp[0], g(1.2), S.success("big", 2, R), g(0.8), pp[2], g(1.2), d]
    S.save(out, "0_미리듣기_퍼펙트_비교.wav", S.finish(np.concatenate(seq)))
