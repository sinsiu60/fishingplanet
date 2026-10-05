"""
환상의 노래 (DESIGN.md 33-11, PHANTOM_CATCH_SHOW.md 2장): 환상어 포획 연출 전용 곡을 미리 합성한다.

- F 리디안 (F G A B C D E — #4 = B), 느리고 자유로운 흐름, 승리 팡파레 느낌 금지 (금관·북 없음)
- 악기: 하프(튕긴 줄 Karplus-Strong + 몸통 공명) / 유리 벨·첼레스타(비정수 배음) / 합창 '아—'(어긋난 톱니 여러 겹 + 모음 공명 필터)
        현악 패드(겹친 톱니 + 부드러운 필터 + 느린 떨림) / 낮은 스웰 / 샤르미온 = 플루트풍 선율, 엘드라시온 = 수정 벨·신스 합창·고음 반짝임
- 공간: 3.5초 잔향(좌우 다른 IR = 넓은 스테레오), 마무리: 중음 보강(폰 스피커), 리미터, 정규화
- 구조와 마커는 data/phantom_catch_timeline.json 을 읽는다 (연출 이펙트와 같은 숫자 = 싱크)
  정적 → 하프 상승(rise) → 벨(scales) → 합창 스웰(rays) → 절정 화음(climax) → 벨 4음 동기(card) → 맑은 '띵'(record) → 해결 화음 + 잔향
- 4음 동기 = '이름 없는 것의 동기' 으뜸음 → #4 → 5도 → 3도 (F5-B5-C6-A5, 8분·8분·4분·2분) = 환상만의 음악 서명.
  환상 전용 파이팅 곡(BOSS_BGM.md, DESIGN.md 43)의 주선율 동기와 같은 음

출력: assets/music_generated/phantom_catch_{full,short,extended,loop}_{sharmion,eldrasion}.ogg
      + tools/audio/reference/phantom_catch/ 같은 이름 .wav (들어보기용) + 길이·최대·평균 음량·마커 표
사용: python tools/audio/make_phantom_song.py   (numpy, scipy, ffmpeg 필요 — 빌드 때는 안 돌린다)
"""
import json
import os
import shutil
import subprocess
import sys

import numpy as np
from scipy import signal
from scipy.io import wavfile

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SR = 44100
RNG = np.random.default_rng(33)
TL = json.load(open(os.path.join(ROOT, "data", "phantom_catch_timeline.json"), encoding="utf-8"))
OUT = os.path.join(ROOT, "assets", "music_generated")
REF = os.path.join(ROOT, "tools", "audio", "reference", "phantom_catch")

MOTIF = [77, 83, 84, 81]          # F5 B5 C6 A5 (1 → #4 → 5 → 3)
MOTIF_AT = [0, 1, 2, 4]           # 8분 · 8분 · 4분 · 2분 (step = 8분음표)
CHORD_LO = [41, 53, 60, 64, 67, 69, 71]   # F2 F3 C4 E4 G4 A4 B4 — Fmaj9(#11)
RESOLVE = [53, 57, 60, 62, 67, 72]         # F3 A3 C4 D4 G4 C5 — F6/9 (해결)


def hz(m: float) -> float:
    return 440.0 * 2 ** ((m - 69) / 12)


def env_adsr(n: int, a: float, r: float, curve: float = 1.0) -> np.ndarray:
    t = np.arange(n) / SR
    e = np.minimum(1.0, t / max(1e-4, a)) ** curve
    rel = int(r * SR)
    if rel > 0 and rel < n:
        e[-rel:] *= np.linspace(1, 0, rel) ** 1.5
    return e


class Track:
    def __init__(self, length: float):
        self.n = int(length * SR)
        self.buf = np.zeros((2, self.n + SR * 6))

    def add(self, x: np.ndarray, start: float, gain: float = 1.0, pan: float = 0.0) -> None:
        i = int(start * SR)
        if i >= self.buf.shape[1]:
            return
        x = x[: self.buf.shape[1] - i]
        lg, rg = np.cos((pan + 1) * np.pi / 4), np.sin((pan + 1) * np.pi / 4)
        self.buf[0, i:i + len(x)] += x * gain * lg * 1.414
        self.buf[1, i:i + len(x)] += x * gain * rg * 1.414


# ───────────────────────── 악기 ─────────────────────────

def harp(f: float, dur: float = 2.5, bright: float = 0.6) -> np.ndarray:
    """튕긴 줄 (Karplus-Strong) + 몸통 공명."""
    n = int(dur * SR)
    N = max(2, int(round(SR / f)))
    x = np.zeros(n)
    burst = RNG.uniform(-1, 1, N)
    b, a = signal.butter(1, min(0.99, 1500 * (1 + 3 * bright) / (SR / 2)))
    x[:N] = signal.lfilter(b, a, burst)
    g = 0.9985 - 0.0006 * (f / 1000)
    den = np.zeros(N + 2)
    den[0] = 1.0
    den[N] = -0.5 * g
    den[N + 1] = -0.5 * g
    y = signal.lfilter([1.0], den, x)
    body = sum(signal.sosfilt(signal.butter(2, [fc * 0.8, fc * 1.25], "bandpass", fs=SR, output="sos"), y) * k
               for fc, k in ((210, 0.5), (720, 0.3)))
    y = y + body
    y *= env_adsr(n, 0.002, 0.3)
    return y / (np.max(np.abs(y)) + 1e-9)


def bell(f: float, dur: float = 3.0, kind: str = "glass") -> np.ndarray:
    """비정수 배음 종소리. glass = 유리 벨, celesta = 짧은 금속 울림, crystal = 수정 벨(배음 많고 김)."""
    n = int(dur * SR)
    t = np.arange(n) / SR
    parts = {"glass": [(1.0, 1.0, 1.6), (2.0, 0.45, 0.9), (2.76, 0.35, 0.6), (5.40, 0.18, 0.3), (8.93, 0.08, 0.15)],
             "celesta": [(1.0, 1.0, 0.7), (3.0, 0.3, 0.25), (4.2, 0.15, 0.12), (0.5, 0.15, 0.5)],
             "crystal": [(1.0, 1.0, 2.2), (2.01, 0.5, 1.4), (3.02, 0.3, 0.9), (4.16, 0.25, 0.7), (5.43, 0.15, 0.5),
                         (6.79, 0.1, 0.35), (0.5, 0.2, 2.0)]}[kind]
    y = np.zeros(n)
    for r, amp, dec in parts:
        det = 1 + RNG.uniform(-0.0015, 0.0015)
        y += amp * np.sin(2 * np.pi * f * r * det * t + RNG.uniform(0, 6.28)) * np.exp(-t / dec)
    y *= np.minimum(1, t / 0.003)
    return y / (np.max(np.abs(y)) + 1e-9)


def saw_stack(f: float, n: int, voices: int, cents: float, vib_hz: float, vib_amt: float) -> np.ndarray:
    t = np.arange(n) / SR
    y = np.zeros(n)
    for k in range(voices):
        d = 2 ** ((cents * (k / max(1, voices - 1) * 2 - 1)) / 1200)
        vib = 1 + vib_amt * np.sin(2 * np.pi * (vib_hz + RNG.uniform(-0.4, 0.4)) * t + RNG.uniform(0, 6.28))
        ph = np.cumsum(f * d * vib) / SR + RNG.uniform(0, 1)
        y += 2 * (ph % 1.0) - 1
    return y / voices


def choir(notes, dur: float, attack: float = 0.7, synth: bool = False) -> np.ndarray:
    """합창 '아—': 어긋난 톱니 여러 겹 + 모음 공명(포먼트) 필터. synth = 엘드라시온 신스 합창(밝고 넓게)."""
    n = int(dur * SR)
    raw = sum(saw_stack(hz(m), n, 6 if not synth else 8, 9 if not synth else 16, 5.2, 0.004) for m in notes)
    forms = [(730, 1.0, 90), (1090, 0.55, 110), (2440, 0.3, 160)] if not synth else \
            [(800, 0.9, 120), (1250, 0.6, 160), (2900, 0.45, 260), (4200, 0.2, 400)]
    y = np.zeros(n)
    for fc, k, bw in forms:
        sos = signal.butter(2, [fc - bw, fc + bw], "bandpass", fs=SR, output="sos")
        y += k * signal.sosfilt(sos, raw)
    y += 0.12 * signal.sosfilt(signal.butter(2, 400, "lowpass", fs=SR, output="sos"), raw)
    y *= env_adsr(n, attack, min(1.5, dur * 0.4), 1.6)
    return y / (np.max(np.abs(y)) + 1e-9)


def strings(notes, dur: float, attack: float = 0.5, cutoff: float = 2400) -> np.ndarray:
    n = int(dur * SR)
    raw = sum(saw_stack(hz(m), n, 7, 12, 5.5, 0.003) for m in notes)
    y = signal.sosfilt(signal.butter(2, cutoff, "lowpass", fs=SR, output="sos"), raw)
    y *= env_adsr(n, attack, min(1.6, dur * 0.4), 1.4)
    return y / (np.max(np.abs(y)) + 1e-9)


def swell(f: float, dur: float, attack: float) -> np.ndarray:
    n = int(dur * SR)
    t = np.arange(n) / SR
    y = np.sin(2 * np.pi * f * t) + 0.3 * np.sin(2 * np.pi * f * 2 * t)
    return y * env_adsr(n, attack, dur * 0.5, 2.0)


def flute(f: float, dur: float) -> np.ndarray:
    n = int(dur * SR)
    t = np.arange(n) / SR
    vib = 1 + 0.006 * np.sin(2 * np.pi * 5.0 * t) * np.minimum(1, t / 0.35)
    ph = np.cumsum(f * vib) / SR
    y = np.sin(2 * np.pi * ph) + 0.18 * np.sin(4 * np.pi * ph) + 0.06 * np.sin(6 * np.pi * ph)
    breath = signal.sosfilt(signal.butter(2, [f * 1.5, f * 4], "bandpass", fs=SR, output="sos"), RNG.normal(0, 1, n))
    y = y + 0.08 * breath / (np.max(np.abs(breath)) + 1e-9)
    return y * env_adsr(n, 0.09, 0.25)


def crystal_lead(f: float, dur: float) -> np.ndarray:
    """엘드라시온 선율: 부드러운 FM 수정 음."""
    n = int(dur * SR)
    t = np.arange(n) / SR
    mod = 1.2 * np.exp(-t / 0.6) * np.sin(2 * np.pi * f * 3.5 * t)
    y = np.sin(2 * np.pi * f * t + mod) * env_adsr(n, 0.04, 0.4)
    return y


def shimmer(dur: float) -> np.ndarray:
    """절정의 부드러운 반짝임 소음 (심벌 대신 — 거칠지 않게)."""
    n = int(dur * SR)
    x = signal.sosfilt(signal.butter(2, [6000, 12000], "bandpass", fs=SR, output="sos"), RNG.normal(0, 1, n))
    return x / (np.max(np.abs(x)) + 1e-9) * env_adsr(n, 0.25, dur * 0.7, 1.5)


def heartbeat() -> np.ndarray:
    n = int(0.45 * SR)
    t = np.arange(n) / SR
    f = 55 * np.exp(-t / 0.2)
    y = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t / 0.09)
    y2 = np.zeros(n)
    k = int(0.2 * SR)
    y2[k:] = y[: n - k] * 0.6
    return y + y2


# ───────────────────────── 공간·마무리 ─────────────────────────

def breath(y: np.ndarray, at: float, pre: float = 0.07, depth: float = 0.25) -> np.ndarray:
    """강타 직전 '숨' (전설의 노래, DESIGN.md 43-20): at 직전 pre 초 동안 전체를 depth 배로 눌러 at 의 강타가 마커에서 또렷하게 튀어나오게."""
    a, r, e = int((at - pre) * SR), int(0.02 * SR), int((at - 0.003) * SR)
    g = np.ones(y.shape[1])
    g[a:a + r] = np.linspace(1, depth, r)
    g[a + r:e] = depth
    g[e:int(at * SR)] = np.linspace(depth, 1, int(at * SR) - e)
    return y * g


def reverb(buf: np.ndarray, rt60: float = 3.6, wet: float = 0.38) -> np.ndarray:
    n = int(rt60 * 1.1 * SR)
    t = np.arange(n) / SR
    tau = rt60 / 6.91
    out = np.zeros_like(buf)
    for ch in range(2):
        ir = RNG.normal(0, 1, n) * np.exp(-t / tau)
        ir = signal.sosfilt(signal.butter(1, 5200, "lowpass", fs=SR, output="sos"), ir)
        for d, g in ((0.011 + 0.004 * ch, 0.6), (0.023 + 0.006 * ch, 0.45), (0.037 - 0.003 * ch, 0.35)):
            ir[int(d * SR)] += g * 8
        ir /= np.sqrt(np.sum(ir ** 2)) + 1e-9
        out[ch] = signal.fftconvolve(buf[ch], ir)[: buf.shape[1]]
    return buf * (1 - wet) + out * wet * 2.2


def master(buf: np.ndarray, peak_db: float = -1.0) -> np.ndarray:
    # 폰 스피커용 중음 보강 (1.5~3kHz 약 +3dB) — 대역 통과분을 더한다
    mid = signal.sosfilt(signal.butter(2, [1500, 3200], "bandpass", fs=SR, output="sos"), buf, axis=1)
    y = buf + 0.42 * mid
    # 부드러운 리미터 + 정규화
    y = y / (np.max(np.abs(y)) + 1e-9) * 1.25
    y = np.tanh(y)
    return y / (np.max(np.abs(y)) + 1e-9) * 10 ** (peak_db / 20)


# ───────────────────────── 곡 ─────────────────────────

def compose(variant: str, cont: str) -> tuple[np.ndarray, dict]:
    eld = cont == "eldrasion"
    if variant == "loop":
        return compose_loop(eld), {}
    v = TL["variants"][variant]
    m = v["markers"]
    L = v["len"]
    tr = Track(L)
    short = variant == "short"
    bellk = "crystal" if eld else "glass"
    # 0) 숨 멎음: 심장 박동 한 번 (아주 작게)
    tr.add(heartbeat(), 0.05, 0.22)
    # 1) 하프 상승 (rise → rays), 엘드라시온은 수정 벨이 같이 (반짝이는 고음)
    arp = [53, 60, 65, 69, 71, 72, 76, 77, 81, 83, 84, 88] if not short else [60, 65, 71, 76, 81, 84]
    span = (m["rays"] - m["rise"]) * (1.0 if not short else 0.9)
    for i, note in enumerate(arp):
        t = m["rise"] + span * (i / len(arp)) ** 1.15
        pan = -0.5 + i / len(arp)
        tr.add(harp(hz(note), 3.0, 0.5 + 0.04 * i), t, 0.30 if not eld else 0.2, pan)
        if eld and i % 2 == 1:
            tr.add(bell(hz(note + 12), 2.0, "crystal"), t, 0.08, -pan)
    # 2) 비늘 빛: 유리 벨
    tr.add(bell(hz(88), 3.0, bellk), m["scales"], 0.16, 0.3)
    tr.add(bell(hz(95), 2.5, bellk), m["scales"] + 0.22, 0.10, -0.35)
    # 3) 빛줄기: 합창 패드가 부풀어 오름 + 현악 + 낮은 스웰 + 하프 글리산도
    build = m["climax"] - m["rays"]
    tr.add(choir([57, 60, 64, 71], build + 0.6, attack=build, synth=eld), m["rays"], 0.32)
    tr.add(strings([53, 60, 64, 69], build + 0.6, attack=build * 0.9), m["rays"], 0.22)
    tr.add(swell(hz(29), build + 1.2, attack=build), m["rays"], 0.35)
    gl = [72, 74, 76, 77, 79, 81, 83, 84, 86, 88, 89, 91] if not short else [76, 79, 83, 86, 88, 91]
    for i, note in enumerate(gl):
        t = m["climax"] - build * 0.55 + build * 0.55 * i / len(gl)
        tr.add(harp(hz(note), 2.0, 0.8), t, 0.12, -0.6 + 1.2 * i / len(gl))
    # 4) 절정 화음 (현악 + 합창 + 저음 스웰 + 벨) — 팡파레가 아니라 '빛'
    hold = (m["card"] - m["climax"]) + (2.6 if not short else 1.4)
    tr.add(strings(CHORD_LO, hold, attack=0.05, cutoff=3200), m["climax"], 0.36)
    tr.add(choir([60, 64, 67, 71, 76], hold, attack=0.06, synth=eld), m["climax"], 0.42)
    tr.add(swell(hz(29), hold, attack=0.04), m["climax"], 0.5)
    for k, note in enumerate((84, 88, 93)):
        tr.add(bell(hz(note), 4.0, bellk), m["climax"] + 0.01 * k, 0.16, (-0.4, 0.0, 0.4)[k])
    tr.add(shimmer(hold * 0.6), m["climax"], 0.05)
    # 4-1) 12종 완성: 절정 뒤 원을 그리는 12음 (ring → ring_end)
    if "ring" in m:
        ring = [77, 79, 81, 83, 84, 86, 88, 89, 91, 93, 95, 96]
        for i, note in enumerate(ring):
            t = m["ring"] + (m["ring_end"] - m["ring"]) * i / len(ring)
            tr.add(bell(hz(note), 2.5, bellk), t, 0.12, np.sin(i / 12 * 2 * np.pi) * 0.7)
            tr.add(harp(hz(note - 24), 2.0, 0.5), t, 0.10, -np.sin(i / 12 * 2 * np.pi) * 0.6)
        tr.add(choir([60, 64, 67, 71, 76, 79], m["return"] - m["ring"] + 1.5, attack=1.0, synth=eld), m["ring"], 0.30)
    # 5) 카드: 벨 4음 동기
    step = 0.18 if not short else 0.14
    for i, note in enumerate(MOTIF):
        tr.add(bell(hz(note), 3.0, bellk), m["card"] + MOTIF_AT[i] * step, 0.24, -0.3 + 0.2 * i)
        tr.add(harp(hz(note - 12), 2.0, 0.4), m["card"] + MOTIF_AT[i] * step, 0.12, 0.2 - 0.15 * i)
    # 6) 기록: 맑은 '띵'
    tr.add(bell(hz(96), 3.5, "glass" if not eld else "crystal"), m["record"], 0.22, 0.0)
    # 7) 해결 화음 + 선율 (보상 → 여운)
    res_t = m["rewards"] - (0.2 if not short else 0.1)
    res_len = L - res_t + 2.5
    tr.add(choir(RESOLVE[1:], res_len, attack=0.9, synth=eld), res_t, 0.26)
    tr.add(strings(RESOLVE, res_len, attack=0.8, cutoff=1800), res_t, 0.18)
    tr.add(swell(hz(41), res_len, attack=0.8), res_t, 0.22)
    lead = flute if not eld else crystal_lead
    if not short:
        for i, (note, d) in enumerate(((81, 0.4), (83, 0.4), (84, 0.6), (88, 0.9), (86, 1.4))):
            tr.add(lead(hz(note), d + 0.3), m["rewards"] + 0.15 + sum(x for _, x in ((81, 0.4), (83, 0.4), (84, 0.6), (88, 0.9))[:i]),
                   0.15 if not eld else 0.12, 0.15)
    else:
        tr.add(lead(hz(88), 1.2), m["rewards"] + 0.1, 0.12, 0.15)
    for i, note in enumerate((89, 93, 96, 100)):
        tr.add(bell(hz(note), 2.0, "celesta" if not eld else "crystal"), m["afterglow"] + 0.3 * i, 0.06, 0.5 - 0.3 * i)
    y = reverb(tr.buf)
    y = y[:, : int((L + 1.2) * SR)]
    fade = int(1.2 * SR)
    y[:, -fade:] *= np.linspace(1, 0, fade) ** 2
    return master(y, -1.0), m


def compose_loop(eld: bool) -> np.ndarray:
    """카드 대기: 아주 작은 여운 (합창 패드 + 드문 반짝임), 이음매 없이 반복."""
    L = TL["loop_len"]
    tr = Track(L)
    tr.add(choir([57, 60, 64, 67, 71], L + 2.0, attack=1.5, synth=eld), 0.0, 0.35)
    tr.add(strings([53, 60, 64], L + 2.0, attack=1.5, cutoff=1400), 0.0, 0.2)
    for i, note in enumerate((88, 91, 93, 95, 96)):
        tr.add(bell(hz(note), 2.5, "crystal" if eld else "glass"), 0.4 + i * L / 5, 0.07, 0.6 * np.sin(i * 1.7))
    y = reverb(tr.buf)
    n = int(L * SR)
    out = y[:, :n].copy()
    tail = y[:, n:n * 2]
    out[:, : tail.shape[1]] += tail  # 넘친 울림을 앞에 더해 이음매 없애기
    # 앞 2초는 패드가 막 차오르는 구간 → 뒤쪽(차오른 상태)과 섞어 고르게
    out = 0.5 * (out + np.roll(out, n // 2, axis=1))
    return master(out, -12.0)


def stats(y: np.ndarray) -> tuple[float, float, float]:
    peak = 20 * np.log10(np.max(np.abs(y)) + 1e-9)
    rms = 20 * np.log10(np.sqrt(np.mean(y ** 2)) + 1e-9)
    return y.shape[1] / SR, peak, rms


def save(y: np.ndarray, name: str) -> None:
    os.makedirs(OUT, exist_ok=True)
    os.makedirs(REF, exist_ok=True)
    pcm = (np.clip(y.T, -1, 1) * 32767).astype(np.int16)
    wav = os.path.join(REF, name + ".wav")
    wavfile.write(wav, SR, pcm)
    ff = shutil.which("ffmpeg")
    if ff:
        subprocess.run([ff, "-loglevel", "error", "-y", "-i", wav, "-c:a", "libvorbis", "-q:a", "5",
                        os.path.join(OUT, name + ".ogg")], check=True)
    else:
        shutil.copy(wav, os.path.join(OUT, name + ".wav"))


if __name__ == "__main__":
    rows = []
    markers = {"_설명": "make_phantom_song.py 가 실제로 음을 놓은 시각 (초). 게임 연출은 data/phantom_catch_timeline.json 의 같은 값을 쓴다.",
               "files": {}}
    for cont in ("sharmion", "eldrasion"):
        for variant in ("full", "short", "extended", "loop"):
            y, m = compose(variant, cont)
            name = f"phantom_catch_{variant}_{cont}"
            save(y, name)
            ln, pk, rms = stats(y)
            mk = " ".join(f"{k}{v:g}" for k, v in m.items() if k in ("rise", "climax", "card", "record", "ring"))
            rows.append((name, ln, pk, rms, mk))
            markers["files"][name] = {"len": round(ln, 3), "peak_db": round(pk, 1), "rms_db": round(rms, 1), "markers": m}
            print(f"{name:<34} {ln:5.2f}s  최대 {pk:6.1f}dBFS  평균 {rms:6.1f}dBFS  {mk}", flush=True)
    with open(os.path.join(OUT, "phantom_catch_markers.json"), "w", encoding="utf-8") as fp:
        json.dump(markers, fp, ensure_ascii=False, indent=1)
