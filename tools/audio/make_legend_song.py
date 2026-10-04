"""
전설의 노래 (DESIGN.md 34장, LEGEND_CATCH_SHOW.md 2장): 전설 포획 연출 전용 곡을 미리 합성한다.

- 장조 + 믹솔리디안 색채(♭7 화음 → 으뜸화음 마침), 96 BPM, 박자감 있게 (환상의 노래는 흐름, 전설은 행진)
- 보스 테마와 같은 으뜸음으로 시작: 샤르미온 D (보스 테마 D 단조 → D 장조로 승리), 엘드라시온 E (보스 테마 E 장조)
- 악기: 금관(겹친 톱니 + 시작할 때 밝아지는 필터 + 늦게 드는 떨림) / 팀파니(음높이 살짝 하강 + 타격 소음 + 몸통)
        심벌즈(스웰·크래시) / 현악 스타카토 / 합창 '오—'(모음 '오' 공명) / 저음 '쿵'
        샤르미온 = 따뜻한 호른 + 현악 중심, 엘드라시온 = 밝은 금관 + 신비 합창 + 수정 벨 반짝임
- 공간: 큰 홀 잔향 2.2초 (환상 3.6초보다 짧고 단단하게), 중음 보강, 리미터, 최대 −1dBFS
- 구조·마커는 data/legend_catch_timeline.json 을 읽는다 (연출과 같은 숫자 = 싱크)
  끝맺음 타격(hit) → 팀파니 롤 + 금관 상승(rise) → 현악 스타카토 고조(scales) → 절정 화음(climax, ♭VII→I)
  → 3음 동기(card) → 인장 '쿵'(record) → 웅장한 마침(afterglow)
- 3음 동기 = 5-1-3 (A4-D5-F#5, 짧게-짧게-길게) — 환상의 4음 동기(리디안)와 다른 전설의 서명

출력: assets/music_generated/legend_catch_{full,short,loop}_{sharmion,eldrasion}.ogg + legend_catch_markers.json
      + tools/audio/reference/legend_catch/ 같은 이름 .wav + 길이·최대·평균 음량·마커 표
      (final 버전은 full 곡을 그대로 쓴다 — 닫을 때 엔딩 음악으로 넘어감)
사용: python tools/audio/make_legend_song.py   (numpy, scipy, ffmpeg 필요 — 빌드 때는 안 돌린다)
"""
import json
import os
import sys

import numpy as np
from scipy import signal

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import make_phantom_song as ps  # noqa: E402  (악기·잔향·마무리 재사용)

SR = ps.SR
RNG = np.random.default_rng(96)
ROOT = ps.ROOT
TL = json.load(open(os.path.join(ROOT, "data", "legend_catch_timeline.json"), encoding="utf-8"))
REF = os.path.join(ROOT, "tools", "audio", "reference", "legend_catch")
BPM = 96
BEAT = 60.0 / BPM
hz = ps.hz

# D 기준 음 (엘드라시온은 +2 = E)
MOTIF = [69, 74, 78]                          # A4 D5 F#5 (5-1-3)
I_CHORD = [38, 50, 57, 62, 66, 69, 74]        # D2 D3 A3 D4 F#4 A4 D5
BVII = [36, 48, 55, 60, 64, 67, 72]           # C 장3화음 (믹솔리디안 ♭VII)
IV = [43, 55, 59, 62, 67, 71]                 # G
RISE = [50, 54, 57, 60, 62, 64, 66, 69]       # D3 F#3 A3 C4 D4 E4 F#4 A4 (♭7 C 를 지나 상승)


# ───────────────────────── 악기 ─────────────────────────

def brass(notes, dur: float, warm: bool, attack: float = 0.04, stab: bool = False) -> np.ndarray:
    """금관: 겹친 톱니 + 시작할 때 확 밝아졌다 가라앉는 필터 + 0.3초 뒤 드는 떨림. warm = 호른(어둡고 둥글게)."""
    n = int(dur * SR)
    t = np.arange(n) / SR
    raw = np.zeros(n)
    for m in notes:
        f = hz(m)
        vib = 1 + 0.0035 * np.sin(2 * np.pi * 5.3 * t + RNG.uniform(0, 6)) * np.clip((t - 0.3) / 0.4, 0, 1)
        for k in range(5):
            d = 2 ** ((7 * (k / 4 * 2 - 1)) / 1200)
            ph = np.cumsum(f * d * vib) / SR + RNG.uniform(0, 1)
            raw += 2 * (ph % 1.0) - 1
    lo_c, hi_c = (700, 2200) if warm else (1100, 4200)
    dark = signal.sosfilt(signal.butter(2, lo_c, "lowpass", fs=SR, output="sos"), raw)
    bright = signal.sosfilt(signal.butter(2, hi_c, "lowpass", fs=SR, output="sos"), raw)
    # 밝기: 어택 순간 1 → 0.15초에 0.55 (금관 '빠-' 의 입김)
    b = np.clip(t / 0.03, 0, 1) * (0.55 + 0.45 * np.exp(-t / 0.15))
    y = dark * (1 - b) + bright * b
    rel = 0.08 if stab else min(0.5, dur * 0.35)
    y *= ps.env_adsr(n, attack, rel, 1.2)
    return y / (np.max(np.abs(y)) + 1e-9)


def timpani(m: float, dur: float = 1.4, hard: float = 1.0) -> np.ndarray:
    n = int(dur * SR)
    t = np.arange(n) / SR
    f0 = hz(m)
    f = f0 * (1 + 0.06 * np.exp(-t / 0.05))           # 맞는 순간 살짝 높았다가 내려앉음
    ph = np.cumsum(f) / SR
    y = np.sin(2 * np.pi * ph) * np.exp(-t / 0.75)
    for r, a, dec in ((1.5, 0.45, 0.35), (1.99, 0.3, 0.3), (2.44, 0.18, 0.2), (2.9, 0.1, 0.15)):
        y += a * np.sin(2 * np.pi * ph * r + RNG.uniform(0, 6)) * np.exp(-t / dec)
    hit = signal.sosfilt(signal.butter(2, [90, 900], "bandpass", fs=SR, output="sos"), RNG.normal(0, 1, n))
    y += 1.2 * hard * hit / (np.max(np.abs(hit)) + 1e-9) * np.exp(-t / 0.035)
    y *= np.minimum(1, t / 0.0015)
    return y / (np.max(np.abs(y)) + 1e-9)


def timp_roll(m: float, dur: float, g0: float = 0.15, g1: float = 1.0) -> np.ndarray:
    """팀파니 롤: 0.055초 간격 타격, 점점 세게."""
    n = int((dur + 1.0) * SR)
    y = np.zeros(n)
    k, i = 0.0, 0
    while k < dur:
        g = g0 + (g1 - g0) * (k / dur) ** 1.6
        x = timpani(m, 0.9, hard=0.4) * g * RNG.uniform(0.85, 1.0)
        j = int(k * SR)
        y[j:j + len(x)] += x[: n - j]
        k += 0.055 + RNG.uniform(-0.006, 0.006)
        i += 1
    return y / (np.max(np.abs(y)) + 1e-9)


def cymbal(dur: float, swell: bool) -> np.ndarray:
    """swell = 점점 커지는 심벌즈 (절정까지), 아니면 크래시."""
    n = int(dur * SR)
    t = np.arange(n) / SR
    x = signal.sosfilt(signal.butter(2, [3500, 15000], "bandpass", fs=SR, output="sos"), RNG.normal(0, 1, n))
    metal = sum(np.sin(2 * np.pi * f * t + RNG.uniform(0, 6)) for f in (3110, 4270, 5830, 7390)) * 0.06
    x = x / (np.max(np.abs(x)) + 1e-9) + metal
    if swell:
        e = (t / dur) ** 2.6
    else:
        e = np.minimum(1, t / 0.004) * np.exp(-t / 0.9)
    return x * e


def stacc(notes, dur: float = 0.11) -> np.ndarray:
    """현악 스타카토: 짧게 끊는 겹친 톱니."""
    n = int(dur * SR)
    raw = sum(ps.saw_stack(hz(m), n, 5, 10, 5.5, 0.002) for m in notes)
    y = signal.sosfilt(signal.butter(2, 3000, "lowpass", fs=SR, output="sos"), raw)
    y *= ps.env_adsr(n, 0.006, 0.05, 1.0)
    return y / (np.max(np.abs(y)) + 1e-9)


def choir_oh(notes, dur: float, attack: float = 0.12, mystic: bool = False) -> np.ndarray:
    """합창 '오—': 어긋난 톱니 + 모음 '오' 공명(450·800·2830Hz). mystic = 엘드라시온 신비 합창(넓고 밝은 위 배음)."""
    n = int(dur * SR)
    raw = sum(ps.saw_stack(hz(m), n, 7, 12 if not mystic else 18, 5.0, 0.004) for m in notes)
    forms = [(450, 1.0, 80), (800, 0.6, 100), (2830, 0.18, 200)]
    if mystic:
        forms += [(3600, 0.16, 400), (5200, 0.08, 600)]
    y = np.zeros(n)
    for fc, k, bw in forms:
        y += k * signal.sosfilt(signal.butter(2, [fc - bw, fc + bw], "bandpass", fs=SR, output="sos"), raw)
    y += 0.15 * signal.sosfilt(signal.butter(2, 350, "lowpass", fs=SR, output="sos"), raw)
    y *= ps.env_adsr(n, attack, min(1.4, dur * 0.4), 1.4)
    return y / (np.max(np.abs(y)) + 1e-9)


def boom(dur: float = 1.2) -> np.ndarray:
    """저음 '쿵': 55→32Hz 사인."""
    n = int(dur * SR)
    t = np.arange(n) / SR
    f = 32 + 23 * np.exp(-t / 0.12)
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t / 0.45) * np.minimum(1, t / 0.002)


def ching() -> np.ndarray:
    """금속성 '챙': 밝은 금속 배음 + 짧은 고음 소음."""
    n = int(1.6 * SR)
    t = np.arange(n) / SR
    y = sum(a * np.sin(2 * np.pi * f * t) * np.exp(-t / d) for f, a, d in
            ((1480, 1.0, 0.6), (2217, 0.6, 0.45), (3520, 0.4, 0.3), (5274, 0.25, 0.2)))
    y += cymbal(1.6, False) * 0.5
    return y / (np.max(np.abs(y)) + 1e-9)


# ───────────────────────── 곡 ─────────────────────────

def compose(variant: str, cont: str) -> tuple[np.ndarray, dict]:
    eld = cont == "eldrasion"
    if variant == "loop":
        return compose_loop(eld), {}
    tp = 2 if eld else 0
    T = lambda ns: [m + tp for m in ns]  # noqa: E731
    m = TL["variants"][variant]["markers"]
    short = variant == "short"
    warm = not eld
    tail = 2.0 if not short else 1.1
    tr = Track(m["afterglow"] + tail)
    hit, cl, card, rec, aft = m["hit"], m["climax"], m["card"], m["record"], m["afterglow"]

    # 1) 끝맺음 타격: 팀파니 + 금관 짧은 화음 + 크래시 + 저음 쿵 (보스 테마 으뜸음 그대로)
    tr.add(timpani(38 + tp, 1.6), hit, 0.9)
    tr.add(brass(T([38, 50, 57, 62]), 0.35, warm, 0.01, stab=True), hit, 0.55)
    tr.add(cymbal(1.4, False), hit, 0.22)
    tr.add(boom(), hit, 0.8)
    # 2) 팀파니 롤(딸림음) 점점 세게 → 절정
    tr.add(timp_roll(45 + tp, cl - hit - 0.12, 0.12, 0.85), hit + 0.12, 0.3)
    # 3) 금관 상승 (rise → 절정): 아래에서 위로
    notes = RISE if not short else RISE[::2]
    span = cl - m["rise"] - 0.05
    for i, n_ in enumerate(notes):
        st = m["rise"] + span * i / len(notes)
        tr.add(brass([n_ + tp, n_ + tp - 12], span / len(notes) + 0.12, warm, 0.03), st, 0.22 + 0.025 * i, -0.15)
    # 4) 현악 스타카토 고조 (scales → 절정, 16분음표 + 위로) + 심벌즈 스웰
    k, i = m["scales"], 0
    step = BEAT / 4
    while k < cl - 0.02:
        top = 57 + tp + (i // 2)
        tr.add(stacc([top, top + 12 - 5]), k, 0.17 + 0.01 * i, 0.25 * (-1) ** i)
        k += step
        i += 1
    tr.add(cymbal(cl - m["scales"] + 0.05, True), m["scales"] - 0.05, 0.22)
    # ♭VII (C 장화음) 금관 → 절정에서 I (믹솔리디안 마침)
    pre = max(m["scales"], cl - BEAT * 0.6)
    tr.add(brass(T(BVII[1:6]), cl - pre + 0.05, warm, 0.06), pre, 0.32)
    # 5) 절정 화음: 금관 + 합창 '오—' + 팀파니 + 크래시 + 현악
    hold = card - cl + (1.2 if not short else 0.6)
    tr.add(brass(T(I_CHORD), hold, warm, 0.02), cl, 0.62)
    tr.add(choir_oh(T([50, 57, 62, 66, 69]), hold + 0.6, 0.08, mystic=eld), cl, 0.42 if not eld else 0.5)
    tr.add(ps.strings(T([62, 66, 69, 74, 78]), hold + 0.4, 0.04, 3600), cl, 0.3 if warm else 0.22)
    tr.add(timpani(38 + tp, 1.6), cl, 0.95)
    tr.add(cymbal(2.0, False), cl, 0.3)
    tr.add(boom(), cl, 0.55)
    if eld:
        for j, nn in enumerate((86, 90, 93, 98)):
            tr.add(ps.bell(hz(nn + tp), 2.2, "crystal"), cl + 0.03 * j, 0.1, (-0.5, -0.2, 0.2, 0.5)[j])
    # 6) 3음 동기 (card): 트럼펫(엘드라시온)/호른+트럼펫(샤르미온) 5-1-3, 짧게-짧게-길게 + 금속성 '챙'
    tr.add(ching(), card, 0.28)
    durs = (BEAT / 2, BEAT / 2, (rec - card) + 0.6)
    st = card
    for j, (nn, d) in enumerate(zip(MOTIF, durs)):
        tr.add(brass([nn + tp], d + 0.05, False, 0.015, stab=j < 2), st, 0.5, 0.1)
        tr.add(brass([nn + tp - 12], d + 0.05, True, 0.02, stab=j < 2), st, 0.3, -0.1)
        st += d * (1 if j < 2 else 0)
    # 7) 인장 '쿵' (record)
    tr.add(timpani(38 + tp, 1.4, hard=1.2), rec, 0.75)
    tr.add(boom(0.9), rec, 0.45)
    # 8) 웅장한 마침: IV → I (afterglow 에서 최종 I 화음 tutti)
    if not short:
        tr.add(brass(T(IV), aft - rec, warm, 0.06), rec + 0.05, 0.38)
        tr.add(choir_oh(T([55, 59, 62, 67]), aft - rec + 0.3, 0.2, mystic=eld), rec + 0.05, 0.3)
        tr.add(timp_roll(45 + tp, aft - rec - 0.25, 0.1, 0.6), rec + 0.2, 0.3)
        tr.add(cymbal(aft - rec, True), rec, 0.22)
    tr.add(brass(T(I_CHORD), tail, warm, 0.03), aft, 0.6)
    tr.add(choir_oh(T([50, 57, 62, 66, 69, 74]), tail, 0.1, mystic=eld), aft, 0.45)
    tr.add(ps.strings(T([50, 57, 62, 66, 69]), tail, 0.05, 3000), aft, 0.3)
    tr.add(timpani(38 + tp, 2.0, hard=1.1), aft, 0.95)
    tr.add(cymbal(2.4, False), aft, 0.3)
    tr.add(boom(1.6), aft, 0.6)
    if eld:
        for j, nn in enumerate((90, 93, 97, 102)):
            tr.add(ps.bell(hz(nn + tp), 2.6, "crystal"), aft + 0.12 * j, 0.08, (-0.6, 0.6, -0.3, 0.3)[j])
    y = ps.reverb(tr.buf, rt60=2.2, wet=0.26)
    n_end = int((aft + tail) * SR)
    y = y[:, :n_end]
    fade = int(0.4 * SR)
    y[:, -fade:] *= np.linspace(1, 0, fade)
    return ps.master(y, -2.0), {k: v for k, v in m.items()}  # 평균 음량을 환상(−13dB)과 비슷하게


def compose_loop(eld: bool) -> np.ndarray:
    """카드 대기: 작은 여운 (금관 패드 + 합창, 드문 반짝임), 이음매 없이 반복."""
    tp = 2 if eld else 0
    L = TL["loop_len"]
    tr = Track(L)
    tr.add(brass([50 + tp, 57 + tp, 62 + tp, 66 + tp], L + 2.0, True, 1.0), 0.0, 0.3)
    tr.add(choir_oh([57 + tp, 62 + tp, 66 + tp], L + 2.0, 1.2, mystic=eld), 0.0, 0.3)
    for i, nn in enumerate((81, 86, 90, 93)):
        tr.add(ps.bell(hz(nn + tp), 2.0, "crystal" if eld else "celesta"), 0.3 + i * L / 4, 0.05, 0.5 * np.sin(i * 2.1))
    y = ps.reverb(tr.buf, rt60=2.2, wet=0.3)
    n = int(L * SR)
    out = y[:, :n].copy()
    tl_ = y[:, n:n * 2]
    out[:, : tl_.shape[1]] += tl_
    out = 0.5 * (out + np.roll(out, n // 2, axis=1))
    return ps.master(out, -12.0)


class Track(ps.Track):
    pass


if __name__ == "__main__":
    ps.REF = REF  # 저장 위치만 전설용으로
    markers = {"_설명": "make_legend_song.py 가 실제로 음을 놓은 시각 (초). 게임 연출은 data/legend_catch_timeline.json 의 같은 값을 쓴다.",
               "files": {}}
    for cont in ("sharmion", "eldrasion"):
        for variant in ("full", "short", "loop"):
            y, mk = compose(variant, cont)
            name = f"legend_catch_{variant}_{cont}"
            ps.save(y, name)
            ln, pk, rms = ps.stats(y)
            s = " ".join(f"{k}{v:g}" for k, v in mk.items() if k in ("rise", "climax", "card", "record", "afterglow"))
            markers["files"][name] = {"len": round(ln, 3), "peak_db": round(pk, 1), "rms_db": round(rms, 1), "markers": mk}
            print(f"{name:<32} {ln:5.2f}s  최대 {pk:6.1f}dBFS  평균 {rms:6.1f}dBFS  {s}", flush=True)
    with open(os.path.join(ps.OUT, "legend_catch_markers.json"), "w", encoding="utf-8") as fp:
        json.dump(markers, fp, ensure_ascii=False, indent=1)
