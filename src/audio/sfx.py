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


def make_reel(rng) -> np.ndarray:
    """릴 딸깍 (루프용 0.5초)."""
    sec = 0.5
    n = int(RATE * sec)
    out = np.zeros(n)
    click = _lowpass(_noise(0.006, rng), 2) * _env(int(RATE * 0.006), 0.0005, 0.0015)
    for i in range(12):
        s = int(i * n / 12)
        out[s:s + len(click)] += click
    return out * 0.6


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
