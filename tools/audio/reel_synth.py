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


TIER_CFG = {
    "wood":    dict(teeth=14, res=950,  decay=2.2, jitter=0.35, tick=1.0, hum=0.35, rustle=0.5, creak=0.5, shimmer=0.0),
    "mid":     dict(teeth=22, res=2600, decay=1.2, jitter=0.18, tick=0.7, hum=0.45, rustle=0.45, creak=0.0, shimmer=0.0),
    "crystal": dict(teeth=30, res=3400, decay=0.8, jitter=0.08, tick=0.35, hum=0.55, rustle=0.35, creak=0.0, shimmer=0.25),
}


def reel_core(v, rps, load, tier):
    """핸들 회전수 곡선 v(회/초) → 감기 소리 (finish 전). reel()과 게임용 반복 루프가 같이 쓴다."""
    cfg = TIER_CFG[tier]
    n = len(v)
    t = np.arange(n) / SR
    handle_phase = np.cumsum(v) / SR  # 핸들 누적 회전수
    tooth_phase = handle_phase * cfg["teeth"]
    idx = np.where(np.diff(np.floor(tooth_phase)) > 0)[0]
    imp = np.zeros(n)
    amp = 1 + cfg["jitter"] * RNG.standard_normal(len(idx))
    if tier == "wood":
        amp *= 1 + 0.6 * (RNG.random(len(idx)) < 0.08)  # 가끔 덜컥
    imp[idx] = np.clip(amp, 0.2, 2.0)
    ticks = fftconvolve(imp, tick_kernel(cfg["res"] * (1 - 0.12 * load), cfg["decay"], tier == "wood"))[:n]
    ticks *= cfg["tick"]
    f_hum = v * cfg["teeth"] * (1 - 0.15 * load)
    ph = 2 * np.pi * np.cumsum(f_hum) / SR
    hum = (np.sin(ph) + 0.5 * np.sin(2 * ph) + 0.25 * np.sin(3 * ph) + 0.12 * np.sin(5 * ph))
    hum = lp(hum, 1800 - 600 * load) * cfg["hum"] * 1.6
    hum += bp(RNG.standard_normal(n), 300, 1200) * 0.15 * (v / max(rps, 1e-6)) * (1 + 1.5 * load)
    rustle = bp(RNG.standard_normal(n), 1200, 4200) * cfg["rustle"] * 0.45 * (v / max(rps, 1e-6)) * (0.4 + 0.5 * load)
    rustle *= 1 + 0.4 * lp(np.abs(RNG.standard_normal(n)), 30)
    creak = 0
    if cfg["creak"]:
        cf = 180 + 40 * np.sin(2 * np.pi * 0.9 * t)
        creak = bp(np.sign(np.sin(2 * np.pi * np.cumsum(cf) / SR)) * RNG.random(n), 200, 1400) * cfg["creak"] * 0.3
    shimmer = 0
    if cfg["shimmer"]:
        shimmer = np.sin(2 * np.pi * np.cumsum(f_hum * 6.03) / SR) * cfg["shimmer"] * 0.15
    sig = ticks + hum + rustle + creak + shimmer
    sig *= 1 + 0.18 * np.sin(2 * np.pi * handle_phase)
    sig *= np.clip(v / max(rps, 1e-6), 0, 1.2) ** 0.6
    return sig


def stop_click_sound(tier):
    """멈춤 '딸깍' (역회전 방지)."""
    cfg = TIER_CFG[tier]
    click = np.zeros(int(0.15 * SR))
    k = tick_kernel(cfg["res"] * 0.8, cfg["decay"] * 1.8, tier == "wood")
    click[: len(k)] += k * 1.6
    k2 = tick_kernel(cfg["res"] * 1.1, cfg["decay"], tier == "wood")
    o = int(0.018 * SR)
    click[o:o + len(k2)] += k2 * 0.7
    return click


# ───────── 게임용 미리 굽기 (DESIGN.md 32-16 Z2): 정규화 없이 같은 기준 배율로 → 속도·부하별 크기 차이가 남는다 ─────────
LOOP_SPEEDS = (1.0, 1.5, 2.0, 2.5, 3.0, 3.5)
LOOP_LOADS = (0.0, 0.5, 0.9)
TIERS = ("wood", "mid", "crystal")
DRAG_RATES = (90, 160, 240, 330)   # 드랙 풀림 클릭/초: 느림 / 보통 / 빠름 / 질주
XF = int(0.05 * SR)                # 루프 끝 크로스페이드
PRE = int(0.25 * SR)               # 필터 시작 과도음 버림


def finish_fixed(x, ref):
    """finish()와 같은 색(60Hz~8.5kHz, 짧은 잔향, 부드러운 포화)이되 파일마다 정규화하지 않고 ref 기준."""
    x = hp(x, 60)
    x = lp(x, 8500)
    x = room(x)
    return np.tanh(x / ref * 1.3) * 0.89 / np.tanh(1.3)


def _loop_cut(x, n):
    """x = [PRE 과도음][n 본체][XF 이어짐] → 이음매 없는 n 길이 루프."""
    seg = x[PRE:PRE + n + XF]
    out = seg[:n].copy()
    a = np.linspace(0, 1, XF)
    out[:XF] = out[:XF] * a + seg[n:n + XF] * (1 - a)
    return out


def reel_loop_raw(rps, load, tier, post=None):
    """일정한 속도로 감는 구간만, 핸들 정수 바퀴 길이 (약 1~1.4초) — 이빨·웅웅·한 바퀴 변조가 모두 이음매에서 맞물린다."""
    v_eff = rps * (1 - 0.35 * load)
    revs = max(1, round(v_eff * 1.2))
    n = int(round(revs / v_eff * SR))
    v = np.full(PRE + n + XF, v_eff)
    x = reel_core(v, v_eff, load, tier)
    return _loop_cut(post(x) if post else x, n)  # 필터·잔향(post)은 자르기 전에 → 이음매에 시작 과도음이 안 남음


def reel_start_raw(tier, rps=2.0):
    """감기 시작 (가속 0.3초) — 루프가 페이드 인 하는 동안 겹쳐 낸다."""
    n = int(0.3 * SR)
    t = np.arange(PRE + n) / SR
    v = rps * np.clip((t - PRE / SR) / 0.3, 0, 1) ** 0.7
    x = reel_core(v, rps, 0.0, tier)[PRE:]
    x[-int(0.06 * SR):] *= np.linspace(1, 0, int(0.06 * SR))
    return x


def drag_loop_raw(peak_rate, post=None):
    """드랙 풀림 '지이이잉' 일정 구간: 흔들림 4주기(3.1Hz) 길이, 클릭·스풀 회전이 이음매에서 맞물리게 속도를 맞춤."""
    L = 4 / 3.1
    rate0 = round(peak_rate * L / 2) * 2 / L
    n = int(round(L * SR))
    N = PRE + n + XF
    t = np.arange(N) / SR
    rate = rate0 * (1 + 0.08 * np.sin(2 * np.pi * 3.1 * t))
    phase = np.cumsum(rate) / SR
    idx = np.where(np.diff(np.floor(phase)) > 0)[0]
    imp = np.zeros(N)
    imp[idx] = 1 + 0.15 * RNG.standard_normal(len(idx))
    clicks = fftconvolve(imp, tick_kernel(4200, 0.7))[:N] * 0.55
    spool = np.sin(2 * np.pi * np.cumsum(rate * 0.5) / SR)
    k = rate0 / max(DRAG_RATES)
    spool = lp(spool + 0.3 * np.sign(spool), 2500) * 0.35 * (0.6 + 0.4 * k)
    hiss = bp(RNG.standard_normal(N), 2500, 7000) * 0.2 * (0.6 + 0.4 * k)
    x = clicks + spool + hiss
    return _loop_cut(post(x) if post else x, n)


def reel(dur=3.0, rps=2.0, load=0.0, tier="mid", stop_click=True):
    """
    rps: 핸들 회전/초 (느림 1.2, 보통 2.0, 빠름 3.2)
    load: 0(빈 릴) ~ 1(대물 부하)
    tier: "wood" (T1), "mid" (T2~T5), "crystal" (T6~T8)
    """
    v = speed_profile(dur, rps * (1 - 0.35 * load))
    sig = reel_core(v, rps, load, tier)
    if stop_click:
        sig = np.concatenate([sig, stop_click_sound(tier)])
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
