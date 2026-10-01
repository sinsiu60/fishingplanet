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
            "rise": make_rise(rng),
            "click": make_click(rng),
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
            if ch is None or not ch.get_busy():
                snd = self.sounds[name]
                snd.set_volume(self.volume * volume)
                self.loops[name] = snd.play(loops=-1)
        elif ch is not None:
            ch.stop()
            self.loops.pop(name, None)
