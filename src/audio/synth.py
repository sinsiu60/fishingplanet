"""효과음 합성 엔진 (DESIGN.md 32장 사운드, Phase S2).

레시피(data/sfx_recipes.json) 하나 = 레이어 여러 개를 겹친 소리. 레이어마다:
  wave     sine / square / saw / triangle / noise (white) / pink / click
  freq     Hz 숫자 또는 [시작, 끝] (+ "curve": "exp"(기본) / "lin") — 피치 엔벨로프(위아래로 휘는 소리)
  start    시작 시각(초), len 길이(초)
  env      {"a","d","s","r"} 어택·디케이·서스테인(0~1)·릴리즈(초) — 길이 끝에서 r초 동안 사라짐
  filter   {"type": "lp"/"hp"/"bp", "f": Hz 또는 [시작, 끝], "q": 0.5~10} — 시간에 따라 변하는 필터
  dist     0~1 왜곡 (tanh 포화 — 찌그러뜨려 힘 있게)
  vib      [Hz, 깊이] 피치 떨림, trem [Hz, 깊이] 음량 떨림
  gain     레이어 음량 (선형), pan -1(왼쪽)~1(오른쪽)
레시피 전체: len(전체 길이), reverb {"mix", "time"} 간단한 잔향, echo {"delay", "fb", "mix"} 메아리,
            pan, peak_db (정규화 목표, 기본 -1dBFS), gain_db (정규화 뒤 더할 음량)
결과는 float32 스테레오 [-1, 1] 배열 (RATE 44100).
"""
import numpy as np

RATE = 44100


# ───────────────────────── 기본 재료 ─────────────────────────

def _curve(v, n: int, curve: str = "exp") -> np.ndarray:
    """숫자 → 일정, [a, b] → a에서 b로 (exp = 음높이처럼 지수, lin = 직선)."""
    if not isinstance(v, (list, tuple)):
        return np.full(n, float(v))
    a, b = float(v[0]), float(v[-1])
    if len(v) > 2:  # 여러 점: 고르게 나눠 직선 연결
        xs = np.linspace(0, 1, len(v))
        return np.interp(np.linspace(0, 1, n), xs, np.array(v, dtype=float))
    k = np.linspace(0, 1, n)
    if curve == "exp" and a > 0 and b > 0:
        return a * (b / a) ** k
    return a + (b - a) * k


def oscillator(wave: str, freq: np.ndarray, rng) -> np.ndarray:
    n = len(freq)
    if wave == "noise":
        return rng.uniform(-1, 1, n)
    if wave == "pink":
        # 핑크 노이즈 (Voss-McCartney 근사: 여러 옥타브 랜덤을 더함)
        out = np.zeros(n)
        for k in range(7):
            step = 2 ** k
            vals = rng.uniform(-1, 1, n // step + 2)
            out += np.repeat(vals, step)[:n]
        return out / 7 * 2.2
    if wave == "click":
        out = np.zeros(n)
        out[: min(n, 40)] = np.linspace(1, -0.5, min(n, 40))
        return out
    phase = np.cumsum(freq) / RATE  # 주기 단위 위상
    if wave == "sine":
        return np.sin(2 * np.pi * phase)
    if wave == "square":
        return np.sign(np.sin(2 * np.pi * phase)) * 0.7
    if wave == "saw":
        return 2 * (phase % 1.0) - 1
    if wave == "triangle":
        return 2 * np.abs(2 * (phase % 1.0) - 1) - 1
    raise ValueError(f"모르는 파형: {wave}")


def adsr(n: int, a: float = 0.005, d: float = 0.1, s: float = 0.0, r: float = 0.05) -> np.ndarray:
    """어택 → 디케이(서스테인 수준까지) → 서스테인 → 길이 끝 r초 릴리즈."""
    t = np.arange(n) / RATE
    total = n / RATE
    env = np.ones(n)
    if a > 0:
        env = np.minimum(env, t / a)
    dec = np.where(t > a, s + (1 - s) * np.exp(-(t - a) / max(d, 1e-4) * 3), 1.0)
    env = np.minimum(env, dec)
    if r > 0:
        env *= np.clip((total - t) / r, 0, 1)
    return env


def svf(x: np.ndarray, kind: str, cutoff: np.ndarray, q: float = 0.707) -> np.ndarray:
    """상태 변수 필터 (lp/hp/bp), 컷오프가 샘플마다 바뀔 수 있다."""
    f = 2 * np.sin(np.pi * np.clip(cutoff, 20, RATE * 0.45) / RATE)
    damp = 1.0 / max(0.3, q)
    low = band = 0.0
    out = np.empty_like(x)
    pick = {"lp": 0, "hp": 1, "bp": 2}[kind]
    for i in range(len(x)):
        fi = f[i]
        low += fi * band
        high = x[i] - low - damp * band
        band += fi * high
        out[i] = low if pick == 0 else high if pick == 1 else band
    return out


def distort(x: np.ndarray, amount: float) -> np.ndarray:
    if amount <= 0:
        return x
    drive = 1 + amount * 9
    return np.tanh(x * drive) / np.tanh(drive)


def reverb(stereo: np.ndarray, mix: float, time: float, rng) -> np.ndarray:
    """간단한 잔향: 지수로 사라지는 노이즈 임펄스와 FFT 합성곱 (좌우 다른 임펄스 → 넓게)."""
    if mix <= 0:
        return stereo
    n_ir = int(RATE * max(0.05, time))
    t = np.arange(n_ir) / RATE
    out = np.zeros((stereo.shape[0] + n_ir, 2))
    for ch in range(2):
        ir = rng.uniform(-1, 1, n_ir) * np.exp(-t / (time / 5))
        ir[: int(RATE * 0.008)] = 0  # 첫 반사 전 짧은 틈
        ir /= np.sqrt(np.sum(ir ** 2)) + 1e-9
        L = 1 << int(np.ceil(np.log2(stereo.shape[0] + n_ir)))
        wet = np.fft.irfft(np.fft.rfft(stereo[:, ch], L) * np.fft.rfft(ir, L), L)[: out.shape[0]]
        out[:, ch] = wet * mix
    out[: stereo.shape[0]] += stereo * (1 - mix * 0.5)
    return out


def echo(stereo: np.ndarray, delay: float, fb: float, mix: float) -> np.ndarray:
    d = int(RATE * delay)
    if d <= 0 or mix <= 0:
        return stereo
    taps = 5
    out = np.zeros((stereo.shape[0] + d * taps, 2))
    out[: stereo.shape[0]] += stereo
    g = mix
    for k in range(1, taps + 1):
        out[d * k: d * k + stereo.shape[0]] += stereo * g
        g *= fb
    return out


def pan(mono: np.ndarray, p: float) -> np.ndarray:
    """일정 파워 패닝: -1 왼쪽 ~ 1 오른쪽."""
    a = (np.clip(p, -1, 1) + 1) * np.pi / 4
    return np.stack([mono * np.cos(a), mono * np.sin(a)], axis=1)


def normalize(stereo: np.ndarray, peak_db: float = -1.0) -> np.ndarray:
    peak = np.max(np.abs(stereo)) or 1.0
    return stereo / peak * (10 ** (peak_db / 20))


# ───────────────────────── 레시피 ─────────────────────────

def render_layer(layer: dict, rng) -> tuple[int, np.ndarray]:
    n = max(1, int(RATE * layer.get("len", 0.3)))
    freq = _curve(layer.get("freq", 440), n, layer.get("curve", "exp"))
    if "vib" in layer:
        hz, depth = layer["vib"]
        freq = freq * (1 + depth * np.sin(2 * np.pi * hz * np.arange(n) / RATE))
    x = oscillator(layer.get("wave", "sine"), freq, rng)
    if "harm" in layer:  # 배음: [[배수, 세기], ...]
        for mult, amp in layer["harm"]:
            x = x + amp * oscillator(layer.get("wave", "sine"), freq * mult, rng)
    flt = layer.get("filter")
    if flt:
        x = svf(x, flt.get("type", "lp"), _curve(flt.get("f", 2000), n, flt.get("curve", "exp")), flt.get("q", 0.707))
    x = distort(x, layer.get("dist", 0.0))
    e = layer.get("env", {})
    x = x * adsr(n, e.get("a", 0.002), e.get("d", 0.15), e.get("s", 0.0), e.get("r", 0.03))
    if "trem" in layer:
        hz, depth = layer["trem"]
        x = x * (1 - depth * 0.5 * (1 + np.sin(2 * np.pi * hz * np.arange(n) / RATE)))
    st = pan(x * layer.get("gain", 1.0), layer.get("pan", 0.0))
    return int(RATE * layer.get("start", 0.0)), st


def render(recipe: dict, seed: int = 1) -> np.ndarray:
    """레시피 → float32 스테레오 (-1~1)."""
    rng = np.random.default_rng(seed)
    parts = [render_layer(ly, rng) for ly in recipe["layers"]]
    n = max(int(RATE * recipe.get("len", 0)), max(s + len(x) for s, x in parts))
    out = np.zeros((n, 2))
    for s, x in parts:
        out[s: s + len(x)] += x
    if recipe.get("pan"):
        mono = out.mean(axis=1)
        out = pan(mono, recipe["pan"])
    if "echo" in recipe:
        e = recipe["echo"]
        out = echo(out, e.get("delay", 0.12), e.get("fb", 0.4), e.get("mix", 0.3))
    if "reverb" in recipe:
        r = recipe["reverb"]
        out = reverb(out, r.get("mix", 0.2), r.get("time", 0.6), rng)
    # 끝 1ms 페이드 (딸깍 방지) → 정규화
    k = min(len(out), int(RATE * 0.001))
    if k:
        out[-k:] *= np.linspace(1, 0, k)[:, None]
    out = normalize(out, recipe.get("peak_db", -1.0))
    out *= 10 ** (recipe.get("gain_db", 0.0) / 20)
    return np.clip(out, -1, 1).astype(np.float32)


def to_pcm16(stereo: np.ndarray) -> np.ndarray:
    return (np.clip(stereo, -1, 1) * 32767).astype(np.int16)


def write_wav(path, stereo: np.ndarray) -> None:
    import wave
    pcm = to_pcm16(stereo)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(pcm.tobytes())


def recipes() -> dict:
    from src.core.config import load_json
    return {k: v for k, v in load_json("sfx_recipes.json").items() if not k.startswith("_")}
