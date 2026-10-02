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
    """릴 감기 루프 (2초, 끊김 없음). clicks = 0.5초당 딸깍 수.

    같은 딸깍이 기계처럼 반복되면 귀가 아프므로 간격·세기·음색을 매번 조금씩 흔들고,
    빨리 감을수록 딸깍은 작아지고 기어 웅웅거림(부드러운 소리)이 커진다.
    """
    sec = 2.0
    n = int(RATE * sec)
    out = np.zeros(n)
    count = clicks * 4
    fast = min(1.0, clicks / 24)
    base = np.linspace(0, n, count, endpoint=False)
    starts = (base + rng.uniform(-0.18, 0.18, count) * n / count).astype(int)
    for s in starts:
        csec = 0.007 / pitch * rng.uniform(0.85, 1.2)
        m = int(RATE * csec)
        body = _lowpass(rng.uniform(-1, 1, m), 4) * _env(m, 0.0005, 0.0018 / pitch)
        f = 950 * pitch * rng.uniform(0.9, 1.1)
        tone = np.sin(2 * np.pi * f * np.arange(m) / RATE) * _env(m, 0.0005, 0.0015)
        click = (body + tone * 0.25) * rng.uniform(0.55, 1.0)
        idx = (s + np.arange(m)) % n  # 루프 끝에서 앞으로 감김 → 이음매 없음
        out[idx] += click * (1.0 - 0.45 * fast)
    # 기어 웅웅: 2초에 정수 주기라 이음매가 없다
    tt = np.arange(n) / RATE
    hum_f = round((70 + 90 * fast) * pitch * sec) / sec
    hum = np.sin(2 * np.pi * hum_f * tt) + 0.35 * np.sin(2 * np.pi * 2 * hum_f * tt)
    whir = _loop_noise(rng, 300, 1400, 0.5, sec)
    out += hum * 0.05 * (0.3 + fast) + whir * 0.05 * fast
    return (out + np.roll(out, 1)) * 0.25  # 원형 저역통과 (루프 이음매 보존)


def make_line_out(rng) -> np.ndarray:
    """캐스팅: 스풀에서 줄이 풀리는 '지이이잉'. 날아가는 동안 재생, 착수 때 끊는다.

    스풀 회전(진폭 떨림)과 윙 하는 음이 점점 느려지고 낮아진다.
    """
    sec = 1.6
    n = int(RATE * sec)
    t = _t(sec)
    slow = np.exp(-t / 0.9)                       # 회전이 서서히 느려짐
    whine_f = 420 + 520 * slow                    # 940Hz → 약 520Hz
    phase = np.cumsum(whine_f) / RATE
    whine = np.sin(2 * np.pi * phase) + 0.45 * np.sin(4 * np.pi * phase) + 0.2 * np.sin(6 * np.pi * phase)
    spin_f = 18 + 42 * slow                       # 스풀 회전 떨림 60Hz → 18Hz
    spin = 0.62 + 0.38 * np.sin(2 * np.pi * np.cumsum(spin_f) / RATE)
    hiss = _lowpass(_noise(sec, rng), 3) * (0.25 + 0.35 * slow)  # 줄이 가이드를 스치는 쉬익
    env = np.clip(t / 0.03, 0, 1) * np.clip((sec - t) / 0.25, 0, 1)
    return (whine * spin * 0.3 + hiss * 0.35) * env * 0.55


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


def make_amb_cave(rng) -> np.ndarray:
    """수정 동굴: 낮은 울림 + 똑똑 떨어지는 물방울 (메아리)."""
    t = _loop_t()
    drone = _loop_noise(rng, 40, 220, 1.5) * 0.18
    drops = np.zeros_like(t)
    for start in rng.uniform(0.1, LOOP_SEC - 0.6, 9):
        for k, g in enumerate((1.0, 0.35, 0.15)):  # 메아리
            s0 = int((start + k * 0.18) * RATE)
            f = rng.uniform(1100, 1700)
            d = _sweep(f, f * 1.6, 0.05) * _env(int(RATE * 0.05), 0.001, 0.02)
            drops[s0:s0 + len(d)] += d[: len(drops) - s0] * 0.12 * g
    return drone + drops


def make_amb_wind(rng) -> np.ndarray:
    """부유섬: 높은 곳의 바람 (휘이잉)."""
    t = _loop_t()
    gust = 0.55 + 0.45 * np.sin(2 * np.pi * 2 * t / LOOP_SEC) ** 2
    return _loop_noise(rng, 200, 1800, 0.8) * gust * 0.28


def make_amb_vent(rng) -> np.ndarray:
    """화산 열수: 부글부글 끓는 소리 + 낮은 울림."""
    t = _loop_t()
    rumble = _loop_noise(rng, 30, 160, 1.5) * 0.25
    boil = np.zeros_like(t)
    for _ in range(70):
        s0 = rng.integers(0, len(t) - int(RATE * 0.05))
        b = _sweep(rng.uniform(180, 320), rng.uniform(350, 600), 0.05) * _env(int(RATE * 0.05), 0.004, 0.015)
        boil[s0:s0 + len(b)] += b * 0.06
    return rumble + boil


def make_amb_ice(rng) -> np.ndarray:
    """빙해: 차가운 바람 + 가끔 얼음 갈라지는 소리."""
    t = _loop_t()
    wind = _loop_noise(rng, 300, 3000, 0.6) * (0.6 + 0.4 * np.sin(2 * np.pi * t / LOOP_SEC)) * 0.16
    crack = np.zeros_like(t)
    for start in (1.3, 4.1):
        s0 = int(start * RATE)
        c = _lowpass(_noise(0.12, rng), 2) * _env(int(RATE * 0.12), 0.001, 0.03)
        crack[s0:s0 + len(c)] += c * 0.25
    return wind + crack


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


def make_creak(rng, base: float = 900, wobble: float = 7) -> np.ndarray:
    """끼익: 줄이 버티는 소리 (톱니파 + 피치 흔들림). 변형 여러 개를 번갈아 쓴다."""
    sec = 0.45
    n = int(RATE * sec)
    t = _t(sec)
    freq = base + 0.13 * base * np.sin(2 * np.pi * wobble * t) + rng.uniform(-30, 30, n)
    phase = np.cumsum(freq) / RATE
    saw = 2 * (phase % 1.0) - 1
    env = np.sin(np.pi * np.linspace(0, 1, n)) ** 0.7
    return _lowpass(saw, 6) * env * 0.18


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


def make_cue_leap(rng) -> np.ndarray:
    """몸털기 예고 (소리 전용 물고기): 물을 차는 두 번의 '촵촵' + 올라가는 짧은 음."""
    out = np.zeros(int(RATE * 0.4))
    for i, start in enumerate((0.0, 0.12)):
        s = int(RATE * start)
        n = _lowpass(_noise(0.07, rng), 3) * _env(int(RATE * 0.07), 0.002, 0.025)
        out[s:s + len(n)] += n * 0.5
    chirp = _sweep(600, 1400, 0.16) * _env(int(RATE * 0.16), 0.01, 0.08)
    s = int(RATE * 0.2)
    out[s:s + len(chirp)] += chirp[: len(out) - s] * 0.25
    return out


def make_cue_charge(rng) -> np.ndarray:
    """힘 모으기 (소리 전용 물고기): 낮고 묵직한 '쿵'."""
    sec = 0.5
    body = _sweep(90, 45, sec) * _env(int(RATE * sec), 0.004, 0.18)
    thud = _lowpass(_noise(sec, rng), 12) * _env(int(RATE * sec), 0.002, 0.04)
    return body * 0.7 + thud * 0.4


def make_cue_lure(rng) -> np.ndarray:
    """가짜 예고 (초롱아귀 등불): 유리 같은 '팅' — 기포 소리와 확실히 다르다."""
    sec = 0.6
    t = _t(sec)
    tone = np.sin(2 * np.pi * 1760 * t) + 0.4 * np.sin(2 * np.pi * 2640 * t)
    return tone * _env(int(RATE * sec), 0.002, 0.18) * 0.18


def make_chest_open(rng) -> np.ndarray:
    """상자 열림: 걸쇠 '딸깍' + 나무 뚜껑 '끼익'."""
    out = np.zeros(int(RATE * 0.55))
    latch = np.sin(2 * np.pi * 2200 * _t(0.03)) * _env(int(RATE * 0.03), 0.001, 0.006)
    out[: len(latch)] += latch * 0.5
    sec = 0.35
    n = int(RATE * sec)
    freq = 380 + 160 * np.linspace(0, 1, n) + rng.uniform(-20, 20, n)
    saw = 2 * ((np.cumsum(freq) / RATE) % 1.0) - 1
    creak = _lowpass(saw, 8) * np.sin(np.pi * np.linspace(0, 1, n)) * 0.18
    s = int(RATE * 0.08)
    out[s:s + n] += creak
    return out


def make_chest_legend(rng) -> np.ndarray:
    """전설 상자: 낮은 울림 → 상승하는 금빛 아르페지오 → 큰 화음."""
    sec = 2.2
    out = np.zeros(int(RATE * sec))
    boom = _sweep(70, 40, 0.8) * _env(int(RATE * 0.8), 0.01, 0.4) * 0.6
    out[: len(boom)] += boom
    notes = [523.25, 659.25, 783.99, 1046.5, 1318.5, 1568.0]
    for i, f in enumerate(notes):
        s = int(RATE * (0.35 + i * 0.09))
        tone = np.sin(2 * np.pi * f * _t(0.5)) * _env(int(RATE * 0.5), 0.004, 0.25) * 0.18
        out[s:s + len(tone)] += tone[: len(out) - s]
    s = int(RATE * 0.95)
    chord = make_chord(rng, [523.25, 659.25, 783.99, 1046.5, 1318.5], 1.2, 0.05, 1.5)
    out[s:s + len(chord)] += chord[: len(out) - s] * 0.8
    return out


def make_bell(rng) -> np.ndarray:
    """소리귀 방울: 작고 맑은 '딸랑'."""
    sec = 0.35
    tt = _t(sec)
    tone = np.sin(2 * np.pi * 2350 * tt) + 0.5 * np.sin(2 * np.pi * 3520 * tt) * np.sin(2 * np.pi * 18 * tt)
    return tone * _env(int(RATE * sec), 0.002, 0.09) * 0.16


def make_flee(rng) -> np.ndarray:
    """놀라 도망: 작은 철썩 두 번."""
    a = make_splash(rng, 0.2) * 0.5
    out = np.zeros(len(a) + int(RATE * 0.08))
    out[: len(a)] += a
    out[int(RATE * 0.08):] += a * 0.6
    return out


# ── 신규 패턴 예고 (U3) ──
def make_cue_shake(rng) -> np.ndarray:
    """① 머리 흔들기: 줄이 떨리는 '타타탁' — 짧고 빠른 딸깍 6번."""
    out = np.zeros(int(RATE * 0.42))
    for i in range(6):
        s = int(RATE * i * 0.055)
        n = int(RATE * 0.03)
        click = (_noise(0.03, rng) * 0.6 + np.sin(2 * np.pi * 2200 * _t(0.03)) * 0.4) * _env(n, 0.0005, 0.008)
        out[s:s + n] += click * (0.55 if i % 2 else 0.4)
    return out


def make_cue_dive(rng) -> np.ndarray:
    """② 잠수: 낮게 내려가는 '꾸르륵' — 아래로 미끄러지는 저음 + 큰 기포 몇 개."""
    sec = 0.7
    n = int(RATE * sec)
    body = _sweep(220, 70, sec) * _env(n, 0.02, 0.35) * 0.45
    for _ in range(5):
        st = rng.integers(0, n - int(RATE * 0.09))
        b = _sweep(rng.uniform(260, 380), rng.uniform(120, 180), 0.09) * _env(int(RATE * 0.09), 0.004, 0.03)
        body[st:st + len(b)] += b * 0.35
    return body


def make_cue_surface(rng) -> np.ndarray:
    """③ 수면 질주: 물을 가르는 '쉬이익' — 밝아지는 노이즈."""
    sec = 0.6
    n = int(RATE * sec)
    noise = _noise(sec, rng)
    bright = noise - _lowpass(noise, 4)
    env = np.linspace(0.15, 1.0, n) ** 1.5 * _env(n, 0.01, 0.4)
    return bright * env * 1.2


def make_cue_reverse(rng) -> np.ndarray:
    """④ 역주행: 줄이 풀려 늘어지는 '스르르' — 부드럽게 내려가는 미끄럼 소리."""
    sec = 0.6
    n = int(RATE * sec)
    noise = _lowpass(_noise(sec, rng), 5)
    slide = _sweep(900, 380, sec) * 0.25
    return (noise * 0.45 + slide) * _env(n, 0.05, 0.3) * 0.8


def make_cue_twist(rng) -> np.ndarray:
    """⑤ 줄 비틀기: '끼릭끼릭' — 높은 삐걱 두 번."""
    out = np.zeros(int(RATE * 0.5))
    for k, start in enumerate((0.0, 0.22)):
        sec = 0.16
        t = _t(sec)
        base = 1500 + k * 180
        freq = base * (1 + 0.12 * np.sin(2 * np.pi * 22 * t)) + rng.uniform(-40, 40, len(t))
        saw = 2 * ((np.cumsum(freq) / RATE) % 1.0) - 1
        w = _lowpass(saw, 4) * _env(len(t), 0.006, 0.07) * 0.4
        s = int(RATE * start)
        out[s:s + len(w)] += w
    return out


def make_cue_combo(rng) -> np.ndarray:
    """⑥ 연쇄 콤보: 북 세 번 '둥 둥 둥'."""
    out = np.zeros(int(RATE * 0.75))
    for i in range(3):
        sec = 0.22
        drum = _sweep(130 - i * 10, 55, sec) * _env(int(RATE * sec), 0.002, 0.09)
        hit = _lowpass(_noise(sec, rng), 6) * _env(int(RATE * sec), 0.001, 0.02)
        s = int(RATE * i * 0.2)
        out[s:s + int(RATE * sec)] += drum * 0.8 + hit * 0.3
    return out


def make_twist_click(rng) -> np.ndarray:
    """원 한 바퀴로 꼬임이 풀릴 때 '틱'."""
    n = int(RATE * 0.05)
    return np.sin(2 * np.pi * 1300 * _t(0.05)) * _env(n, 0.001, 0.015) * 0.35


# ── 신규 패턴 예고 (U4) ──
def make_cue_hide(rng) -> np.ndarray:
    """⑦ 숨기: 바위에 부딪히는 묵직한 '쿵' + 자갈 긁힘."""
    sec = 0.6
    n = int(RATE * sec)
    body = _sweep(70, 35, sec) * _env(n, 0.003, 0.2) * 0.65
    grit = (_noise(sec, rng) - _lowpass(_noise(sec, rng), 3)) * _env(n, 0.02, 0.12) * 0.25
    return body + grit


def make_cue_drum(rng) -> np.ndarray:
    """⑧ 펌핑 박자 북 한 번 '둥' (박마다 울림 — 짧고 어택이 또렷해야 박자가 맞게 들린다)."""
    sec = 0.25
    n = int(RATE * sec)
    drum = _sweep(150, 60, sec) * _env(n, 0.001, 0.08)
    hit = _lowpass(_noise(sec, rng), 4) * _env(n, 0.0005, 0.012)
    return drum * 0.85 + hit * 0.35


def make_cue_bite(rng) -> np.ndarray:
    """⑩ 줄 물어뜯기: 이빨이 맞부딪히는 날카로운 '딱'."""
    sec = 0.2
    n = int(RATE * sec)
    crack = _noise(sec, rng) * _env(n, 0.0003, 0.01)
    ping = np.sin(2 * np.pi * 3100 * _t(sec)) * _env(n, 0.0005, 0.03) * 0.4
    return (crack + ping) * 0.8


def make_double_perfect(rng) -> np.ndarray:
    """⑨ 더블 퍼펙트: 위로 쭉 올라가는 반짝임 + 화음."""
    sec = 0.9
    n = int(RATE * sec)
    out = np.zeros(n)
    for i, f in enumerate((784.0, 1046.5, 1318.5, 1568.0, 2093.0)):
        s = int(RATE * i * 0.06)
        tone = np.sin(2 * np.pi * f * _t(0.5)) * _env(int(RATE * 0.5), 0.004, 0.2)
        out[s:s + len(tone)] += tone[: n - s] * 0.22
    return out


# ── 신호 사전 6계열 (31장 C3): 같은 대응 = 같은 소리 ──
def make_rush_hum(rng, hz: float) -> np.ndarray:
    """돌진 예고 줄 울림 한 박: 팽팽한 줄이 웅— 하고 우는 짧은 음 (배음 + 살짝 떨림)."""
    sec = 0.13
    t = _t(sec)
    vib = 1 + 0.01 * np.sin(2 * np.pi * 28 * t)
    tone = (np.sin(2 * np.pi * hz * t * vib) + 0.45 * np.sin(2 * np.pi * hz * 2 * t * vib)
            + 0.2 * np.sin(2 * np.pi * hz * 3.01 * t))
    return tone * _env(len(t), 0.008, 0.07) * 0.45


def make_rush_go(rng) -> np.ndarray:
    """돌진 시작 '쉬익': 줄이 확 당겨지며 물을 가르는 소리."""
    w = make_whoosh(rng, 0.34, 1.8)
    sec = 0.34
    n = int(RATE * sec)
    snap = np.sin(2 * np.pi * np.cumsum(np.linspace(900, 300, n)) / RATE) * _env(n, 0.002, 0.04) * 0.5
    return w[:n] * 0.9 + snap


def make_sig_release(rng) -> np.ndarray:
    """풀기: 낮게 빠지는 '쉬익' (아래로 미끄러지는 노이즈)."""
    sec = 0.32
    n = int(RATE * sec)
    noise = _lowpass(_noise(sec, rng), 6)
    tone = np.sin(2 * np.pi * np.cumsum(np.linspace(420, 160, n)) / RATE) * 0.35
    return (noise * 0.5 + tone) * _env(n, 0.01, 0.16) * 0.8


def make_sig_reel(rng) -> np.ndarray:
    """감기: 높은 '딸깍' 두 번."""
    out = np.zeros(int(RATE * 0.16))
    for i in range(2):
        s = int(RATE * i * 0.07)
        k = int(RATE * 0.025)
        click = np.sin(2 * np.pi * 3200 * _t(0.025)) * _env(k, 0.0005, 0.008)
        out[s:s + k] += click * 0.6
    return out


def make_sig_timing(rng) -> np.ndarray:
    """타이밍: 맑은 '띵'."""
    sec = 0.45
    n = int(RATE * sec)
    t = _t(sec)
    return (np.sin(2 * np.pi * 1568 * t) + 0.35 * np.sin(2 * np.pi * 3136 * t)) * _env(n, 0.002, 0.16) * 0.45


def make_sig_direction(rng) -> np.ndarray:
    """방향: 짧고 밝은 '휙'."""
    w = make_whoosh(rng, 0.2, 1.6)
    return w / max(1e-6, float(np.abs(w).max())) * 0.6


def make_sig_endure(rng) -> np.ndarray:
    """참기: '타타탁' (줄 떨림)."""
    return make_cue_shake(rng)


def make_sig_gesture(rng) -> np.ndarray:
    """제스처: 올라가는 '끼릭' 톱니 소리."""
    out = np.zeros(int(RATE * 0.36))
    for i in range(5):
        s = int(RATE * i * 0.06)
        k = int(RATE * 0.03)
        f = 900 + i * 180
        saw = 2 * ((_t(0.03) * f) % 1.0) - 1
        out[s:s + k] += saw * _env(k, 0.001, 0.012) * 0.3
    return out


def _rush_hums(rng) -> dict:
    from src.core.config import load_json
    c = load_json("signals.json")["rush_pulse"]
    n = c["hum_steps"]
    return {f"rush_hum{i}": make_rush_hum(rng, c["hum_base_hz"] * (c["hum_top_hz"] / c["hum_base_hz"]) ** (i / max(1, n - 1)))
            for i in range(n)}


def _cache_path(rate: int, channels: int, seed: int):
    """소리 캐시 파일: 이 파일(합성 코드) 내용이 바뀌면 이름이 바뀌어 새로 만든다."""
    import hashlib
    from src.core.paths import save_dir
    try:
        with open(__file__, "rb") as f:
            from src.core.config import load_json
            hum = load_json("signals.json")["rush_pulse"]  # 줄 울림 음높이를 바꾸면 캐시도 새로
            extra = f"{hum['hum_steps']}/{hum['hum_base_hz']}/{hum['hum_top_hz']}"
            key = hashlib.sha1(f.read() + f"{rate}/{channels}/{seed}/{extra}".encode()).hexdigest()[:12]
    except OSError:
        return None
    return save_dir() / "cache" / f"sfx_{key}.npz"


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
        from src.platform.detect import IS_MOBILE
        cache = _cache_path(self.rate, self.channels, seed) if IS_MOBILE else None
        if cache is not None and self._load_cache(cache):
            return  # 모바일: 처음 한 번 만든 소리를 저장해 두고 다음부터 불러옴 (폰에서 합성은 몇 초 걸림)
        rng = np.random.default_rng(seed)
        bank = {
            "splash": make_splash(rng, 1.0),
            "splash_small": make_splash(rng, 0.3),
            "nibble": make_nibble(rng),
            "bite": make_bite(rng),
            "cast": make_whoosh(rng, 0.3, 1.0),
            "line_out": make_line_out(rng),
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
            "amb_cave": make_amb_cave(rng),
            "amb_wind": make_amb_wind(rng),
            "amb_vent": make_amb_vent(rng),
            "amb_ice": make_amb_ice(rng),
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
            "creak2": make_creak(rng, 760, 5),
            "creak3": make_creak(rng, 640, 9),
            "scrape": make_scrape(rng),
            "bubbles": make_bubbles(rng),
            "snap": make_snap(rng),
            "lose": make_lose(rng),
            "catch": make_catch(rng),
            "flee": make_flee(rng),
            "cue_leap": make_cue_leap(rng),
            "cue_charge": make_cue_charge(rng),
            "cue_lure": make_cue_lure(rng),
            "chest_open": make_chest_open(rng),
            "bell": make_bell(rng),
            "chest_legend": make_chest_legend(rng),
            # 신규 패턴 (U3) — 맨 뒤에 붙여 기존 소리의 난수가 바뀌지 않게
            "cue_shake": make_cue_shake(rng),
            "cue_dive": make_cue_dive(rng),
            "cue_surface": make_cue_surface(rng),
            "cue_reverse": make_cue_reverse(rng),
            "cue_twist": make_cue_twist(rng),
            "cue_combo": make_cue_combo(rng),
            "twist_click": make_twist_click(rng),
            # U4
            "cue_hide": make_cue_hide(rng),
            "cue_drum": make_cue_drum(rng),
            "cue_bite": make_cue_bite(rng),
            "double_perfect": make_double_perfect(rng),
            # 신호 사전 6계열 (31장 C3) — 맨 뒤
            "sig_release": make_sig_release(rng),
            "sig_reel": make_sig_reel(rng),
            "sig_timing": make_sig_timing(rng),
            "sig_direction": make_sig_direction(rng),
            "sig_endure": make_sig_endure(rng),
            "sig_gesture": make_sig_gesture(rng),
            # 돌진 줄 펄스 (31-14) — 맨 뒤. 울림 음높이는 signals.json rush_pulse
            "rush_go": make_rush_go(rng),
            **_rush_hums(rng),
        }
        pcms = {}
        for name, wave in bank.items():
            pcms[name] = self._to_pcm(wave)
            self.sounds[name] = self._pcm_sound(pcms[name])
        if cache is not None:
            try:
                cache.parent.mkdir(parents=True, exist_ok=True)
                np.savez(cache, **pcms)
            except OSError:
                pass

    def _to_pcm(self, wave: np.ndarray) -> np.ndarray:
        if self.rate != RATE:
            idx = np.linspace(0, len(wave) - 1, int(len(wave) * self.rate / RATE))
            wave = np.interp(idx, np.arange(len(wave)), wave)
        return (np.clip(wave, -1, 1) * 32000).astype(np.int16)

    def _pcm_sound(self, data: np.ndarray) -> pygame.mixer.Sound:
        if self.channels == 2:
            data = np.column_stack((data, data))
        return pygame.sndarray.make_sound(np.ascontiguousarray(data))

    def _to_sound(self, wave: np.ndarray) -> pygame.mixer.Sound:
        return self._pcm_sound(self._to_pcm(wave))

    def _load_cache(self, path) -> bool:
        try:
            with np.load(path) as z:
                for name in z.files:
                    self.sounds[name] = self._pcm_sound(z[name])
            return bool(self.sounds)
        except Exception:
            self.sounds.clear()
            return False

    def play(self, name: str, volume: float = 1.0) -> pygame.mixer.Channel | None:
        if not self.enabled or name not in self.sounds:
            return None
        snd = self.sounds[name]
        snd.set_volume(self.volume * volume)
        ch = snd.play()
        if getattr(self, "boost", 1) >= 2:
            snd.play()  # 같은 소리를 겹쳐 +6dB (투명 변이의 예고 소리)
        return ch

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
