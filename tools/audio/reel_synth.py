"""
릴 효과음 합성기 (외부 음원 없이 numpy + scipy로 생성)
구성: 기어 이빨 틱 + 기어 웅웅거림 + 핸들 회전 주기 + 줄 감김 마찰 + 멈춤 딸깍 + 짧은 공간 잔향
사용: python reel_synth.py  → 같은 폴더에 wav 생성
"""
import numpy as np
from scipy.signal import butter, sosfilt, fftconvolve
from scipy.io import wavfile
import os

SR = 44100
RNG = np.random.default_rng(7)
OUT = os.path.dirname(os.path.abspath(__file__))


def bp(x, lo, hi, order=2):
    return sosfilt(butter(order, [lo, hi], btype="band", fs=SR, output="sos"), x)


def lp(x, f, order=2):
    return sosfilt(butter(order, f, btype="low", fs=SR, output="sos"), x)


def hp(x, f, order=2):
    return sosfilt(butter(order, f, btype="high", fs=SR, output="sos"), x)


def speed_profile(dur, rps, accel=0.15, decel=0.12):
    """핸들 회전수(회/초) 곡선: 가속 → 유지 → 감속"""
    t = np.arange(int(dur * SR)) / SR
    v = np.full_like(t, rps)
    a = t < accel
    v[a] = rps * (t[a] / accel) ** 0.7
    d = t > dur - decel
    v[d] = rps * np.clip((dur - t[d]) / decel, 0, 1) ** 1.5
    v *= 1 + 0.03 * np.sin(2 * np.pi * 0.7 * t) + 0.015 * RNG.standard_normal(len(t)).cumsum() / np.sqrt(len(t))
    return np.clip(v, 0, None)


def tick_kernel(res_freq, decay_ms, wood=False):
    n = int(0.012 * SR)
    t = np.arange(n) / SR
    env = np.exp(-t / (decay_ms / 1000))
    noise = RNG.standard_normal(n) * env
    ping = np.sin(2 * np.pi * res_freq * t) * env * 0.8
    ping2 = np.sin(2 * np.pi * res_freq * 1.62 * t) * np.exp(-t / (decay_ms / 2000)) * 0.35
    k = bp(noise, 1200 if not wood else 400, 5000 if not wood else 2500) * 0.7 + ping + ping2
    return k / np.max(np.abs(k))


def reel(dur=3.0, rps=2.0, load=0.0, tier="mid", stop_click=True):
    """
    rps: 핸들 회전/초 (느림 1.2, 보통 2.0, 빠름 3.2)
    load: 0(빈 릴) ~ 1(대물 부하)
    tier: "wood" (T1), "mid" (T2~T5), "crystal" (T6~T8)
    """
    cfg = {
        "wood":    dict(teeth=14, res=950,  decay=2.2, jitter=0.35, tick=1.0, hum=0.35, rustle=0.5, creak=0.5, shimmer=0.0),
        "mid":     dict(teeth=22, res=2600, decay=1.2, jitter=0.18, tick=0.7, hum=0.45, rustle=0.45, creak=0.0, shimmer=0.0),
        "crystal": dict(teeth=30, res=3400, decay=0.8, jitter=0.08, tick=0.35, hum=0.55, rustle=0.35, creak=0.0, shimmer=0.25),
    }[tier]

    v = speed_profile(dur, rps * (1 - 0.35 * load))
    n = len(v)
    t = np.arange(n) / SR
    handle_phase = np.cumsum(v) / SR  # 핸들 누적 회전수

    # 1) 기어 이빨 틱: 이빨이 지나갈 때마다 임펄스
    tooth_phase = handle_phase * cfg["teeth"]
    idx = np.where(np.diff(np.floor(tooth_phase)) > 0)[0]
    imp = np.zeros(n)
    amp = 1 + cfg["jitter"] * RNG.standard_normal(len(idx))
    if tier == "wood":
        amp *= 1 + 0.6 * (RNG.random(len(idx)) < 0.08)  # 가끔 덜컥
    imp[idx] = np.clip(amp, 0.2, 2.0)
    ticks = fftconvolve(imp, tick_kernel(cfg["res"] * (1 - 0.12 * load), cfg["decay"], tier == "wood"))[:n]
    ticks *= cfg["tick"]

    # 2) 기어 웅웅거림: 이빨 주파수를 따라가는 톤 (음색 유지, 높이만 변화)
    f_hum = v * cfg["teeth"] * (1 - 0.15 * load)
    ph = 2 * np.pi * np.cumsum(f_hum) / SR
    hum = (np.sin(ph) + 0.5 * np.sin(2 * ph) + 0.25 * np.sin(3 * ph) + 0.12 * np.sin(5 * ph))
    hum = lp(hum, 1800 - 600 * load) * cfg["hum"] * 1.6
    hum += bp(RNG.standard_normal(n), 300, 1200) * 0.15 * (v / max(rps, 1e-6)) * (1 + 1.5 * load)  # 부하 시 거칠게

    # 3) 줄 감김 마찰
    rustle = bp(RNG.standard_normal(n), 1200, 4200) * cfg["rustle"] * 0.45 * (v / max(rps, 1e-6)) * (0.4 + 0.5 * load)
    rustle *= 1 + 0.4 * lp(np.abs(RNG.standard_normal(n)), 30)

    # 4) 나무 릴 삐걱임
    creak = 0
    if cfg["creak"]:
        cf = 180 + 40 * np.sin(2 * np.pi * 0.9 * t)
        creak = bp(np.sign(np.sin(2 * np.pi * np.cumsum(cf) / SR)) * RNG.random(n), 200, 1400) * cfg["creak"] * 0.3

    # 5) 고티어 맑은 공명
    shimmer = 0
    if cfg["shimmer"]:
        shimmer = np.sin(2 * np.pi * np.cumsum(f_hum * 6.03) / SR) * cfg["shimmer"] * 0.15

    sig = ticks + hum + rustle + creak + shimmer

    # 핸들 한 바퀴 주기 변조
    sig *= 1 + 0.18 * np.sin(2 * np.pi * handle_phase)
    # 속도에 따른 전체 음량 (멈추면 잦아듦)
    sig *= np.clip(v / max(rps, 1e-6), 0, 1.2) ** 0.6

    # 6) 멈춤 딸깍 (역회전 방지)
    if stop_click:
        click = np.zeros(int(0.15 * SR))
        k = tick_kernel(cfg["res"] * 0.8, cfg["decay"] * 1.8, tier == "wood")
        click[: len(k)] += k * 1.6
        k2 = tick_kernel(cfg["res"] * 1.1, cfg["decay"], tier == "wood")
        o = int(0.018 * SR)
        click[o:o + len(k2)] += k2 * 0.7
        sig = np.concatenate([sig, click])

    return finish(sig)


def drag_scream(dur=2.6, peak_rate=260):
    """드랙 풀림: 물고기가 질주하며 줄을 빼 가는 '지이이잉' (클리커 + 스풀 회전음 + 줄 마찰)"""
    n = int(dur * SR)
    t = np.arange(n) / SR
    rate = peak_rate * np.clip(np.sin(np.pi * t / dur) ** 0.6, 0, 1) * (1 + 0.08 * np.sin(2 * np.pi * 3.1 * t))
    phase = np.cumsum(rate) / SR
    idx = np.where(np.diff(np.floor(phase)) > 0)[0]
    imp = np.zeros(n)
    imp[idx] = 1 + 0.15 * RNG.standard_normal(len(idx))
    clicks = fftconvolve(imp, tick_kernel(4200, 0.7))[:n] * 0.55
    spool = np.sin(2 * np.pi * np.cumsum(rate * 0.5) / SR)
    spool = lp(spool + 0.3 * np.sign(spool), 2500) * 0.35 * (rate / peak_rate)
    hiss = bp(RNG.standard_normal(n), 2500, 7000) * 0.2 * (rate / peak_rate)
    return finish(clicks + spool + hiss)


def room(x, amount=0.12, length=0.09):
    """아주 짧은 공간 잔향 (손 근처에서 들리는 느낌)"""
    m = int(length * SR)
    ir = RNG.standard_normal(m) * np.exp(-np.arange(m) / (m / 5))
    ir = lp(ir, 5000)
    ir /= np.sum(np.abs(ir))
    return x + amount * fftconvolve(x, ir)[: len(x)] * 8


def finish(x, fade_ms=8):
    x = hp(x, 60)
    x = lp(x, 8500)
    x = room(x)
    f = int(fade_ms / 1000 * SR)
    x[:f] *= np.linspace(0, 1, f)
    x[-f:] *= np.linspace(1, 0, f)
    x = np.tanh(x / (np.max(np.abs(x)) + 1e-9) * 1.3)  # 부드러운 포화로 힘 있게
    return x / np.max(np.abs(x)) * 0.89  # 약 -1 dBFS


def save(name, x):
    wavfile.write(os.path.join(OUT, name), SR, (x * 32767).astype(np.int16))
    print(f"{name}: {len(x) / SR:.2f}s")


if __name__ == "__main__":
    save("reel_slow.wav", reel(3.0, 1.2))
    save("reel_normal.wav", reel(3.0, 2.0))
    save("reel_fast.wav", reel(3.0, 3.2))
    save("reel_under_load.wav", reel(3.5, 2.4, load=0.85))
    save("reel_T1_wood.wav", reel(3.0, 2.0, tier="wood"))
    save("reel_T8_crystal.wav", reel(3.0, 2.0, tier="crystal"))
    save("drag_scream.wav", drag_scream())

    # 데모: 감기 → 멈춤 → 물고기 질주(드랙) → 부하 감기 → 빠르게 마무리
    gap = np.zeros(int(0.35 * SR))
    demo = np.concatenate([
        reel(2.2, 2.0), gap, drag_scream(2.2), gap[:5000],
        reel(2.8, 2.4, load=0.85), gap, reel(1.8, 3.2),
    ])
    save("demo_sequence.wav", demo / np.max(np.abs(demo)) * 0.89)
