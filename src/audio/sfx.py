"""효과음을 numpy로 생성 (외부 파일 없음).

오디오 장치가 없으면 조용히 무음으로 동작한다.
"""
import numpy as np
import pygame

RATE = 44100


def _t(sec: float) -> np.ndarray:
    return np.arange(int(RATE * sec)) / RATE


def _lowpass(x: np.ndarray, width: int) -> np.ndarray:
    if width <= 1:
        return x
    k = np.ones(width) / width
    return np.convolve(x, k, mode="same")


def _env(n: int, attack: float, decay: float) -> np.ndarray:
    t = np.arange(n) / RATE
    a = np.clip(t / max(attack, 1e-4), 0, 1)
    return a * np.exp(-np.maximum(t - attack, 0) / decay)


def _sweep(f0: float, f1: float, sec: float) -> np.ndarray:
    t = _t(sec)
    freq = f0 * (f1 / f0) ** (t / sec)
    return np.sin(2 * np.pi * np.cumsum(freq) / RATE)


def _noise(sec: float, rng) -> np.ndarray:
    return rng.uniform(-1, 1, int(RATE * sec))


def make_splash(rng, big: float = 1.0) -> np.ndarray:
    """풍덩: 낮은 플롭 + 물보라 노이즈."""
    sec = 0.45 + 0.2 * big
    plop = _sweep(320, 110, sec) * _env(int(RATE * sec), 0.004, 0.07) * 0.8
    spray = _lowpass(_noise(sec, rng), 6) * _env(int(RATE * sec), 0.01, 0.12 + 0.08 * big) * 0.6
    return (plop + spray) * (0.6 + 0.4 * big)


def make_nibble(rng) -> np.ndarray:
    """톡: 짧고 가벼운."""
    sec = 0.09
    tone = _sweep(1100, 700, sec) * _env(int(RATE * sec), 0.002, 0.02)
    click = _lowpass(_noise(sec, rng), 3) * _env(int(RATE * sec), 0.001, 0.008)
    return (tone * 0.45 + click * 0.3)


def make_bite(rng) -> np.ndarray:
    """쑥!: 낮게 빨려 들어가는 소리 + 기포."""
    sec = 0.4
    n = int(RATE * sec)
    gulp = _sweep(520, 140, sec) * _env(n, 0.005, 0.12)
    bubbles = np.zeros(n)
    for _ in range(6):
        start = rng.integers(0, n // 2)
        b = _sweep(rng.uniform(600, 1200), rng.uniform(1300, 2000), 0.04) * _env(int(RATE * 0.04), 0.002, 0.012)
        bubbles[start:start + len(b)] += b[: n - start]
    return gulp * 0.8 + bubbles * 0.25


def make_whoosh(rng, sec: float = 0.28, bright: float = 1.0) -> np.ndarray:
    """휙: 대역 노이즈, 커졌다 작아짐."""
    n = int(RATE * sec)
    noise = _noise(sec, rng)
    band = _lowpass(noise, int(8 / bright)) - _lowpass(noise, int(40 / bright))
    t = np.linspace(0, 1, n)
    env = np.sin(np.pi * t) ** 2
    return band * env * 2.2


def make_hookset(rng) -> np.ndarray:
    """챔질: 휙 + 줄 팽팽해지는 탁."""
    w = make_whoosh(rng, 0.22, 1.4)
    snap_sec = 0.12
    snap = _sweep(240, 180, snap_sec) * _env(int(RATE * snap_sec), 0.001, 0.03)
    out = np.zeros(len(w) + int(RATE * 0.02))
    out[: len(w)] += w
    start = int(RATE * 0.1)
    out[start:start + len(snap)] += snap[: len(out) - start] * 0.9
    return out


def make_reel(rng, clicks: int = 12, pitch: float = 1.0) -> np.ndarray:
    """릴 딸깍 (루프용 0.5초). clicks가 많을수록 빨리 감는 소리."""
    sec = 0.5
    n = int(RATE * sec)
    out = np.zeros(n)
    click_sec = 0.006 / pitch
    click = _lowpass(_noise(click_sec, rng), 2) * _env(int(RATE * click_sec), 0.0005, 0.0015 / pitch)
    tone = np.sin(2 * np.pi * 1800 * pitch * _t(click_sec))[: len(click)] * _env(len(click), 0.0005, 0.002)
    click = click + tone * 0.4
    for i in range(clicks):
        s = int(i * n / clicks)
        out[s:s + len(click)] += click[: n - s]
    return out * 0.6


def make_perfect(rng) -> np.ndarray:
    """퍼펙트: 맑은 차임 두 음 + 반짝임."""
    sec = 0.7
    n = int(RATE * sec)
    t = _t(sec)
    out = np.zeros(n)
    for f, start, amp in ((1568, 0.0, 0.5), (2093, 0.06, 0.45), (3136, 0.12, 0.2)):
        s = int(start * RATE)
        tt = t[: n - s]
        out[s:] += np.sin(2 * np.pi * f * tt) * _env(n - s, 0.002, 0.18) * amp
    shimmer = _lowpass(_noise(sec, rng), 1) * _env(n, 0.01, 0.12) * 0.06
    return out + shimmer


def make_good(rng) -> np.ndarray:
    sec = 0.18
    return np.sin(2 * np.pi * 1046 * _t(sec)) * _env(int(RATE * sec), 0.002, 0.05) * 0.4


def make_great(rng) -> np.ndarray:
    """그레잇: 밝은 두 음 + 짧은 반짝."""
    sec = 0.4
    n = int(RATE * sec)
    t = _t(sec)
    out = np.sin(2 * np.pi * 1318.5 * t) * _env(n, 0.002, 0.08) * 0.4
    s = int(0.05 * RATE)
    out[s:] += np.sin(2 * np.pi * 1760 * t[: n - s]) * _env(n - s, 0.002, 0.12) * 0.4
    out += _lowpass(_noise(sec, rng), 1) * _env(n, 0.005, 0.05) * 0.05
    return out


def make_impact(rng) -> np.ndarray:
    """퍼펙트 타격감: 묵직한 쿵 + 고음 반짝 꼬리."""
    sec = 0.6
    n = int(RATE * sec)
    boom = _sweep(140, 45, sec) * _env(n, 0.001, 0.12) * 1.0
    crack = _lowpass(_noise(sec, rng), 2) * _env(n, 0.0005, 0.02) * 0.5
    return boom + crack


def make_rise(rng) -> np.ndarray:
    """끌어올림: 위로 올라가는 휘익 + 물 떨어지는 소리."""
    sec = 0.7
    n = int(RATE * sec)
    noise = _noise(sec, rng)
    band = _lowpass(noise, 3) - _lowpass(noise, 14)
    env = np.linspace(0.2, 1.0, n) * np.exp(-np.linspace(0, 2.5, n))
    tone = _sweep(300, 900, sec) * _env(n, 0.05, 0.3) * 0.15
    return band * env * 1.6 + tone


def make_launch(rng) -> np.ndarray:
    """튀어 오름: 반짝이며 올라가는 아르페지오."""
    notes = [659.25, 783.99, 987.77, 1318.5]
    out = np.zeros(int(RATE * 0.55))
    for i, f in enumerate(notes):
        s = int(i * 0.06 * RATE)
        t = _t(0.3)
        tone = np.sin(2 * np.pi * f * t) * _env(len(t), 0.002, 0.08) * 0.3
        out[s:s + len(tone)] += tone[: len(out) - s]
    return out


def make_chord(rng, notes, sec: float, swell: float, shimmer: float) -> np.ndarray:
    """희귀·전설 연출용 화음: 천천히 부풀었다 사라짐 + 반짝임."""
    n = int(RATE * sec)
    t = _t(sec)
    out = np.zeros(n)
    for i, f in enumerate(notes):
        vib = 1 + 0.003 * np.sin(2 * np.pi * 5 * t + i)
        out += np.sin(2 * np.pi * f * vib * t) * (0.5 / len(notes) ** 0.5)
        out += np.sin(4 * np.pi * f * t) * (0.12 / len(notes) ** 0.5)
    env = np.clip(t / swell, 0, 1) * np.exp(-np.maximum(t - swell, 0) / (sec * 0.45))
    out *= env
    if shimmer:
        sp = np.zeros(n)
        for _ in range(int(14 * shimmer)):
            st = rng.integers(0, n - int(RATE * 0.05))
            b = np.sin(2 * np.pi * rng.uniform(2500, 4200) * _t(0.05)) * _env(int(RATE * 0.05), 0.001, 0.015)
            sp[st:st + len(b)] += b * 0.12
        out += sp
    return out * 0.8


def make_click(rng) -> np.ndarray:
    sec = 0.05
    return np.sin(2 * np.pi * 1500 * _t(sec)) * _env(int(RATE * sec), 0.001, 0.012) * 0.35


def make_coin(rng) -> np.ndarray:
    """판매·구매: 짤랑."""
    out = np.zeros(int(RATE * 0.35))
    for i, f in enumerate((1975.5, 2637.0)):
        s = int(i * 0.06 * RATE)
        t = _t(0.25)
        tone = np.sin(2 * np.pi * f * t) * _env(len(t), 0.001, 0.06) * 0.3
        out[s:s + len(tone)] += tone[: len(out) - s]
    return out


# ───────────────────────── 환경음 (끊김 없는 루프) ─────────────────────────
LOOP_SEC = 6.0


def _loop_noise(rng, lo: float, hi: float, tilt: float = 0.0, sec: float = LOOP_SEC) -> np.ndarray:
    """주파수 영역에서 만든 노이즈 → 역변환하면 자연스럽게 반복되는(끊김 없는) 루프가 된다."""
    n = int(RATE * sec)
    freqs = np.fft.rfftfreq(n, 1 / RATE)
    mag = ((freqs >= lo) & (freqs <= hi)).astype(float)
    with np.errstate(divide="ignore"):
        mag *= np.where(freqs > 0, (freqs / max(lo, 1)) ** -tilt, 0)
    spec = mag * np.exp(1j * rng.uniform(0, 2 * np.pi, len(freqs)))
    out = np.fft.irfft(spec, n)
    return out / (np.max(np.abs(out)) + 1e-9)


def _loop_t(sec: float = LOOP_SEC) -> np.ndarray:
    return np.arange(int(RATE * sec)) / RATE


def make_amb_lake(rng) -> np.ndarray:
    """저수지: 잔잔한 바람 + 풀벌레."""
    t = _loop_t()
    wind = _loop_noise(rng, 80, 700, 1.0) * (0.6 + 0.4 * np.sin(2 * np.pi * t / LOOP_SEC)) * 0.25
    bugs = np.zeros_like(t)
    for start in np.arange(0.2, LOOP_SEC - 0.3, 0.75):
        for k in range(3):
            s0 = int((start + k * 0.06) * RATE)
            seg = np.sin(2 * np.pi * 4300 * _t(0.035)) * _env(int(RATE * 0.035), 0.004, 0.012)
            bugs[s0:s0 + len(seg)] += seg * 0.08
    return wind + bugs


def make_amb_stream(rng) -> np.ndarray:
    """계곡: 졸졸 흐르는 물."""
    t = _loop_t()
    water = _loop_noise(rng, 300, 3500, 0.5) * 0.22
    mod = 0.7 + 0.3 * np.sin(2 * np.pi * 3 * t / LOOP_SEC)
    bubbles = np.zeros_like(t)
    for _ in range(40):
        s0 = rng.integers(0, len(t) - int(RATE * 0.04))
        b = _sweep(rng.uniform(500, 900), rng.uniform(1000, 1600), 0.04) * _env(int(RATE * 0.04), 0.003, 0.012)
        bubbles[s0:s0 + len(b)] += b * 0.05
    return water * mod + bubbles


def make_amb_waves(rng) -> np.ndarray:
    """바다: 철썩이는 파도 (루프 길이에 맞춘 두 번의 너울)."""
    t = _loop_t()
    surf = _loop_noise(rng, 60, 2500, 1.2)
    swell = (0.5 + 0.5 * np.sin(2 * np.pi * 2 * t / LOOP_SEC - 1.2)) ** 2
    return surf * (0.08 + 0.32 * swell)


def make_amb_boat(rng) -> np.ndarray:
    """먼바다: 낮은 엔진음 + 파도."""
    t = _loop_t()
    base = 42.0  # 루프 길이(6초)에 정수 주기로 맞아떨어지는 주파수
    hum = sum(np.sin(2 * np.pi * base * h * t) / h for h in (1, 2, 3, 5)) * 0.12
    hum *= 0.85 + 0.15 * np.sin(2 * np.pi * 6 * t / LOOP_SEC)
    return hum + make_amb_waves(rng) * 0.6


def make_amb_deep(rng) -> np.ndarray:
    """심해: 깊게 울리는 저음 + 먼 파도."""
    t = _loop_t()
    drone = (np.sin(2 * np.pi * 55 * t) + 0.7 * np.sin(2 * np.pi * (82.5 + 1 / LOOP_SEC) * t)) * 0.12
    drone *= 0.7 + 0.3 * np.sin(2 * np.pi * t / LOOP_SEC)
    return drone + _loop_noise(rng, 40, 400, 1.0) * 0.12


def make_amb_rain(rng) -> np.ndarray:
    """빗소리: 사락사락."""
    hiss = _loop_noise(rng, 900, 9000, 0.3) * 0.18
    t = _loop_t()
    patter = np.zeros_like(t)
    for _ in range(260):
        s0 = rng.integers(0, len(t) - 200)
        patter[s0:s0 + 120] += _lowpass(rng.uniform(-1, 1, 120), 2) * np.exp(-np.arange(120) / 25) * 0.15
    return hiss + patter


def make_thunder(rng) -> np.ndarray:
    """천둥: 우르릉."""
    sec = 2.6
    n = int(RATE * sec)
    crack = _lowpass(_noise(sec, rng), 3) * _env(n, 0.002, 0.08) * 0.6
    rumble = _lowpass(_noise(sec, rng), 60) * 6
    rumble *= _env(n, 0.05, 0.9) * (0.7 + 0.3 * np.sin(np.linspace(0, 20, n)))
    return crack + rumble


# ───────────────────────── 음악 (코드 생성) ─────────────────────────

def _note_freq(name: str) -> float:
    names = {"C": -9, "C#": -8, "D": -7, "D#": -6, "E": -5, "F": -4, "F#": -3, "G": -2, "G#": -1, "A": 0,
             "A#": 1, "B": 2}
    pitch, octave = name[:-1], int(name[-1])
    return 440.0 * 2 ** ((names[pitch] + (octave - 4) * 12) / 12)


def _place(buf: np.ndarray, wave: np.ndarray, start: int) -> None:
    """루프 버퍼에 소리를 얹는다. 끝을 넘으면 앞으로 감아서 끊김 없는 루프가 되게."""
    n = len(buf)
    idx = (np.arange(len(wave)) + start) % n
    np.add.at(buf, idx, wave)


def _tone(freq: float, sec: float, kind: str = "sine", attack: float = 0.005, decay: float = 0.2) -> np.ndarray:
    t = _t(sec)
    if kind == "square":
        w = np.sign(np.sin(2 * np.pi * freq * t)) * 0.35 + np.sin(2 * np.pi * freq * t) * 0.4
    elif kind == "saw":
        w = 2 * ((freq * t) % 1.0) - 1
        w = _lowpass(w, 4) * 0.6
    else:
        w = np.sin(2 * np.pi * freq * t) + 0.3 * np.sin(4 * np.pi * freq * t)
    return w * _env(len(t), attack, decay)


def make_bgm_legend(rng) -> np.ndarray:
    """전설 BGM: D단조, 120BPM 4마디 루프 (8초). 북 + 베이스 오스티나토 + 긴장감 있는 아르페지오."""
    beat = 0.5
    sec = beat * 16
    buf = np.zeros(int(RATE * sec))
    bass_line = ["D2", "D2", "A1", "A1", "A#1", "A#1", "C2", "A1"]
    for i, note in enumerate(bass_line):
        _place(buf, _tone(_note_freq(note), beat * 2, "saw", 0.01, 0.5) * 0.5, int(i * beat * 2 * RATE))
    # 북: 정박 쿵, 엇박 딱
    for b in range(16):
        kick = _sweep(110, 45, 0.25) * _env(int(RATE * 0.25), 0.001, 0.08) * (0.9 if b % 4 == 0 else 0.55)
        _place(buf, kick, int(b * beat * RATE))
        if b % 2 == 1:
            tom = _sweep(220, 140, 0.15) * _env(int(RATE * 0.15), 0.001, 0.05) * 0.3
            _place(buf, tom, int((b * beat + beat * 0.5) * RATE))
    # 아르페지오 (8분음표)
    chords = [["D4", "F4", "A4", "D5"], ["A3", "C#4", "E4", "A4"], ["A#3", "D4", "F4", "A#4"], ["C4", "E4", "G4", "C5"]]
    for bar, chord in enumerate(chords):
        for k in range(8):
            n = chord[[0, 1, 2, 3, 2, 1, 2, 3][k]]
            _place(buf, _tone(_note_freq(n), beat * 0.5, "square", 0.003, 0.12) * 0.16,
                   int((bar * 4 + k * 0.5) * beat * RATE))
    # 긴 현악 패드
    for bar, chord in enumerate(chords):
        for n in chord[:3]:
            pad = _tone(_note_freq(n) / 2, beat * 4, "sine", 0.4, 1.4) * 0.07
            _place(buf, pad, int(bar * 4 * beat * RATE))
    return buf / (np.max(np.abs(buf)) + 1e-9) * 0.8


def make_bgm_ending(rng) -> np.ndarray:
    """엔딩: C장조, 느리고 따뜻한 아르페지오 + 패드 (16초 루프)."""
    beat = 0.75
    sec = beat * 16
    buf = np.zeros(int(RATE * sec))
    chords = [["C3", "E4", "G4", "C5"], ["A2", "C4", "E4", "A4"], ["F2", "A3", "C4", "F4"], ["G2", "B3", "D4", "G4"]]
    for bar, chord in enumerate(chords):
        _place(buf, _tone(_note_freq(chord[0]), beat * 4, "sine", 0.05, 1.6) * 0.35, int(bar * 4 * beat * RATE))
        for k in range(8):
            n = chord[1 + [0, 1, 2, 1, 0, 1, 2, 1][k]]
            _place(buf, _tone(_note_freq(n), beat, "sine", 0.01, 0.5) * 0.2, int((bar * 4 + k * 0.5) * beat * RATE))
        for n in chord[1:]:
            _place(buf, _tone(_note_freq(n), beat * 4, "sine", 0.8, 2.0) * 0.06, int(bar * 4 * beat * RATE))
    return buf / (np.max(np.abs(buf)) + 1e-9) * 0.7


def make_roar(rng) -> np.ndarray:
    """전설 페이즈 전환: 깊은 포효 + 물기둥."""
    sec = 1.2
    n = int(RATE * sec)
    growl = _sweep(90, 55, sec) * (0.6 + 0.4 * np.sin(np.linspace(0, 60, n))) * _env(n, 0.05, 0.4)
    noise = _lowpass(_noise(sec, rng), 12) * _env(n, 0.02, 0.35) * 3
    splash = np.zeros(n)
    sp = make_splash(rng, 1.0)[:n]
    splash[: len(sp)] = sp
    return growl * 0.8 + noise * 0.5 + splash * 0.4


def make_whip(rng) -> np.ndarray:
    """꺾기: 날카로운 휘익 + 탁 (채찍)."""
    sec = 0.32
    n = int(RATE * sec)
    noise = _noise(sec, rng)
    band = _lowpass(noise, 2) - _lowpass(noise, 7)
    t = np.linspace(0, 1, n)
    swoosh = band * np.exp(-((t - 0.35) / 0.18) ** 2) * 2.4
    crack = np.zeros(n)
    s0 = int(0.11 * RATE)
    c = _lowpass(_noise(0.03, rng), 1) * _env(int(RATE * 0.03), 0.0005, 0.006)
    crack[s0:s0 + len(c)] = c
    tone = _sweep(900, 1800, sec) * _env(n, 0.05, 0.06) * 0.12
    return swoosh + crack * 0.9 + tone


def make_miss(rng) -> np.ndarray:
    """실수: 낮은 쿵 + 줄 튕김."""
    sec = 0.35
    n = int(RATE * sec)
    thud = _sweep(180, 60, sec) * _env(n, 0.002, 0.08) * 0.9
    twang = _sweep(420, 300, sec) * _env(n, 0.002, 0.1) * 0.25
    return thud + twang


def make_creak(rng) -> np.ndarray:
    """끼익: 줄이 버티는 소리 (거친 톱니파 + 피치 흔들림)."""
    sec = 0.45
    n = int(RATE * sec)
    t = _t(sec)
    freq = 900 + 120 * np.sin(2 * np.pi * 7 * t) + rng.uniform(-30, 30, n)
    phase = np.cumsum(freq) / RATE
    saw = 2 * (phase % 1.0) - 1
    env = np.sin(np.pi * np.linspace(0, 1, n)) ** 0.7
    return _lowpass(saw, 3) * env * 0.22


def make_scrape(rng) -> np.ndarray:
    """줄 쏠림: 쉬익 긁히는 소리."""
    sec = 0.4
    n = int(RATE * sec)
    noise = _noise(sec, rng)
    band = _lowpass(noise, 2) - _lowpass(noise, 6)
    env = np.linspace(0.2, 1, n) * _env(n, 0.05, 0.25)
    return band * env * 1.2


def make_bubbles(rng) -> np.ndarray:
    sec = 0.6
    n = int(RATE * sec)
    out = np.zeros(n)
    for _ in range(10):
        start = rng.integers(0, n - int(RATE * 0.05))
        b = _sweep(rng.uniform(400, 900), rng.uniform(1000, 1800), 0.05) * _env(int(RATE * 0.05), 0.002, 0.015)
        out[start:start + len(b)] += b * rng.uniform(0.2, 0.4)
    return out


def make_snap(rng) -> np.ndarray:
    """줄 끊김: 날카로운 딱 + 휘익."""
    sec = 0.5
    n = int(RATE * sec)
    crack = _noise(sec, rng) * _env(n, 0.0005, 0.015) * 1.0
    whip = make_whoosh(rng, 0.35, 1.6)
    out = crack
    out[: len(whip)] += whip * 0.6
    return out


def make_lose(rng) -> np.ndarray:
    notes = [392.0, 349.2, 311.1]
    out = []
    for f in notes:
        sec = 0.16
        t = _t(sec)
        out.append(np.sin(2 * np.pi * f * t) * _env(len(t), 0.004, 0.08) * 0.35)
    return np.concatenate(out)


def make_catch(rng) -> np.ndarray:
    """획득 팡파르: 짧은 아르페지오."""
    notes = [523.25, 659.25, 783.99, 1046.5]
    step = 0.09
    total = int(RATE * (step * len(notes) + 0.35))
    out = np.zeros(total)
    for i, f in enumerate(notes):
        sec = 0.35 if i == len(notes) - 1 else step * 1.6
        t = _t(sec)
        tone = (np.sign(np.sin(2 * np.pi * f * t)) * 0.3 + np.sin(2 * np.pi * f * t) * 0.7)
        tone *= _env(len(t), 0.004, sec * 0.45)
        s = int(i * step * RATE)
        out[s:s + len(tone)] += tone[: total - s] * 0.35
    return out


def make_flee(rng) -> np.ndarray:
    """놀라 도망: 작은 철썩 두 번."""
    a = make_splash(rng, 0.2) * 0.5
    out = np.zeros(len(a) + int(RATE * 0.08))
    out[: len(a)] += a
    out[int(RATE * 0.08):] += a * 0.6
    return out


class Sfx:
    def __init__(self, seed: int = 1):
        self.enabled = False
        self.volume = 0.8
        self.sounds: dict[str, pygame.mixer.Sound] = {}
        self.loops: dict[str, pygame.mixer.Channel] = {}
        try:
            init = pygame.mixer.get_init()
            if init is None:
                pygame.mixer.init(RATE, -16, 2, 512)
                init = pygame.mixer.get_init()
            self.channels = init[2]
            self.rate = init[0]
            self.enabled = True
        except pygame.error:
            return
        rng = np.random.default_rng(seed)
        bank = {
            "splash": make_splash(rng, 1.0),
            "splash_small": make_splash(rng, 0.3),
            "nibble": make_nibble(rng),
            "bite": make_bite(rng),
            "cast": make_whoosh(rng, 0.3, 1.0),
            "hookset": make_hookset(rng),
            "reel": make_reel(rng),
            "reel0": make_reel(rng, 6, 0.9),
            "reel1": make_reel(rng, 10, 1.0),
            "reel2": make_reel(rng, 16, 1.15),
            "reel3": make_reel(rng, 24, 1.3),
            "perfect": make_perfect(rng),
            "good": make_good(rng),
            "great": make_great(rng),
            "impact": make_impact(rng),
            "whip": make_whip(rng),
            "rise": make_rise(rng),
            "click": make_click(rng),
            "amb_lake": make_amb_lake(rng),
            "amb_stream": make_amb_stream(rng),
            "amb_waves": make_amb_waves(rng),
            "amb_boat": make_amb_boat(rng),
            "amb_deep": make_amb_deep(rng),
            "amb_rain": make_amb_rain(rng),
            "thunder": make_thunder(rng),
            "bgm_legend": make_bgm_legend(rng),
            "bgm_ending": make_bgm_ending(rng),
            "roar": make_roar(rng),
            "coin": make_coin(rng),
            "chord_rare": make_chord(rng, [659.25, 830.61, 987.77, 1318.5], 1.4, 0.15, 1.0),
            "chord_legend": make_chord(rng, [261.63, 392.0, 523.25, 659.25, 783.99, 1046.5], 2.4, 0.5, 2.0),
            "launch": make_launch(rng),
            "miss": make_miss(rng),
            "creak": make_creak(rng),
            "scrape": make_scrape(rng),
            "bubbles": make_bubbles(rng),
            "snap": make_snap(rng),
            "lose": make_lose(rng),
            "catch": make_catch(rng),
            "flee": make_flee(rng),
        }
        for name, wave in bank.items():
            self.sounds[name] = self._to_sound(wave)

    def _to_sound(self, wave: np.ndarray) -> pygame.mixer.Sound:
        if self.rate != RATE:
            idx = np.linspace(0, len(wave) - 1, int(len(wave) * self.rate / RATE))
            wave = np.interp(idx, np.arange(len(wave)), wave)
        data = (np.clip(wave, -1, 1) * 32000).astype(np.int16)
        if self.channels == 2:
            data = np.column_stack((data, data))
        return pygame.sndarray.make_sound(np.ascontiguousarray(data))

    def play(self, name: str, volume: float = 1.0) -> None:
        if not self.enabled or name not in self.sounds:
            return
        snd = self.sounds[name]
        snd.set_volume(self.volume * volume)
        snd.play()

    def stop_all(self) -> None:
        if self.enabled:
            pygame.mixer.stop()
        self.loops.clear()

    def loop(self, name: str, on: bool, volume: float = 1.0) -> None:
        if not self.enabled or name not in self.sounds:
            return
        ch = self.loops.get(name)
        if on:
            snd = self.sounds[name]
            snd.set_volume(self.volume * volume)
            if ch is None or not ch.get_busy():
                self.loops[name] = snd.play(loops=-1)
        elif ch is not None:
            ch.stop()
            self.loops.pop(name, None)
