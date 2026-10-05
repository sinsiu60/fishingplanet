"""전설·환상 전용 파이팅 곡 합성 (DESIGN.md 43, BOSS_BGM.md). tools/bake_boss.py 가 굽기 때만 쓴다 (게임 실행 중엔 안 씀).

곡 = data/music_patterns.json "boss" → "songs" → <곡ID> 스펙. 층(스템)을 따로 만들어 같은 배율로 마스터링한다:
  intro_mix       인트로 2마디 (반복 없음, 1페이즈로 이어짐)
  <페이즈>_base   바탕 (화음·베이스)         <페이즈>_perc / _perc_crisis   타악 / 위기 타악 (더 세게)
  <페이즈>_lead   주선율 / _lead_oct 한 옥타브 위 (지침 2마디 동안)        <페이즈>_choir 합창
  <페이즈>_riser  다음 페이즈로 넘어가는 1마디 상승음 (반복 없음, 마지막 페이즈엔 없음)
반복 층은 정확히 16마디 길이 — 넘친 울림을 앞머리에 겹쳐(wrap) 이음새 없이 돈다.

스펙 (음 = 음계 도수: 1~7, 8 = 한 옥타브 위 1, 0·-1… = 아래, "#4"·"b7" 처럼 반음 올림/내림):
  root  으뜸음 MIDI (예 62 = D4)     scale  minor / harmonic / dorian / major / lydian / whole(전음)
  bpm   4분음표 빠르기 (6/8·3/4도 4분음표 기준 — 6/8 한 마디 = 4분 3개)     meter [4, 4] / [6, 8] / [3, 4]
  intro {"chords": [도수 2개], "parts": {...}} (없으면 1페이즈 바탕·타악을 2마디로 + 크레셴도)
  phases [{ "chords": [마디당 도수 16개], "transpose": 반음, "scale": 바꿀 음계,
            "base": [파트...], "perc": {"kit": ..., "pattern": {악기: "x..."}, "crisis": {악기: "x..."}},
            "lead": [파트...], "choir": [파트...] }]
  파트 {"inst": 악기, "style": 연주법, "gain": 1.0, "oct": 0, "pan": 0, ...연주법 옵션}
악기·연주법·타악은 아래 INST / STYLES / DRUMS 참고.
"""
import numpy as np

RATE = 44100

SCALES = {
    "minor": [0, 2, 3, 5, 7, 8, 10],
    "harmonic": [0, 2, 3, 5, 7, 8, 11],
    "dorian": [0, 2, 3, 5, 7, 9, 10],
    "major": [0, 2, 4, 5, 7, 9, 11],
    "lydian": [0, 2, 4, 6, 7, 9, 11],
    "whole": [0, 2, 4, 6, 8, 10, 12],
}
VOWELS = {   # 합창 모음 공명 (Hz, 세기, 폭)
    "o": [(450, 1.0, 80), (800, 0.5, 90), (2830, 0.08, 120)],
    "a": [(800, 1.0, 90), (1150, 0.6, 100), (2900, 0.12, 130)],
}


def hz(m: float) -> float:
    return 440.0 * 2 ** ((m - 69) / 12)


# ───────────────────────── 음계 ─────────────────────────

def degree_to_midi(deg, root: int, scale: str) -> float:
    """도수 → MIDI. 정수(1=으뜸음, 8=옥타브 위) 또는 '#4'·'b7'·'5+12' 같은 문자열."""
    acc = 0
    off = 0
    if isinstance(deg, str):
        s = deg
        if "+" in s[1:]:
            s, o = s.rsplit("+", 1)
            off += int(o)
        while s and s[0] in "#b":
            acc += 1 if s[0] == "#" else -1
            s = s[1:]
        deg = int(s)
    sc = SCALES[scale]
    d = deg - 1
    octv, idx = divmod(d, 7)
    return root + 12 * octv + sc[idx] + acc + off


def chord_midis(deg, root: int, scale: str, n: int = 3) -> list[float]:
    """도수 화음 (3화음, n=4 면 7화음). '5:7' = 5도 7화음. 'M'/'m' 꼬리 = 장·단3화음으로 고정
    ('5M' = 화성단음계 V, 'b7M' = ♭VII, 'b6M' = ♭VI, '4m' = iv, 'b2M' = 나폴리)."""
    if isinstance(deg, str) and deg[-1:] in ("M", "m") and ":" not in deg:
        base = degree_to_midi(deg[:-1], root, scale)
        third = 4 if deg[-1] == "M" else 3
        out = [base, base + third, base + 7]
        return out + [base + 10] if n == 4 else out
    if isinstance(deg, str) and ":" in deg:
        d, k = deg.split(":")
        deg, n = int(d), 4 if k == "7" else n
    d0 = int(deg) if not isinstance(deg, str) else deg
    if isinstance(d0, str):
        base = degree_to_midi(d0, root, scale)
        return [base, base + (3 if scale in ("minor", "harmonic", "dorian") else 4), base + 7][:n]
    return [degree_to_midi(d0 + 2 * k, root, scale) for k in range(n)]


# ───────────────────────── 재료 ─────────────────────────

def _t(n: int) -> np.ndarray:
    return np.arange(n) / RATE


def env_adsr(n: int, a: float, d: float, s: float, r: float) -> np.ndarray:
    t = _t(n)
    total = n / RATE
    e = np.minimum(1.0, t / max(a, 1e-4))
    e = np.minimum(e, np.where(t > a, s + (1 - s) * np.exp(-(t - a) / max(d, 1e-4) * 3), 1.0))
    if r > 0:
        e = e * np.clip((total - t) / r, 0, 1)
    return e


def additive(f0: float, n: int, amps, brightness=None, vib=(0.0, 0.0), detune: float = 0.0, decay=None,
             partials=None, rng=None) -> np.ndarray:
    """배음 합성. amps(k) = k번째 배음 세기, brightness(t) 배열이면 높은 배음이 시간에 따라 열림(필터가 열리는 금관).
    partials: 배음 배수 목록(종처럼 정수배가 아닌 소리). decay: 배음별 감쇠 속도(초당, k에 비례)."""
    t = _t(n)
    ph0 = rng.uniform(0, 1) if rng is not None else 0.0
    fm = 1.0 + vib[1] * np.sin(2 * np.pi * vib[0] * t + ph0 * 6.28) if vib[1] else 1.0
    phase = np.cumsum(np.full(n, f0 * (1 + detune)) * fm) / RATE
    ks = partials if partials is not None else range(1, 64)
    out = np.zeros(n)
    for i, k in enumerate(ks):
        if f0 * k > RATE * 0.45 or (not callable(amps) and i >= len(amps)):
            break
        a = amps(i + 1) if callable(amps) else amps[i]
        if a <= 2e-3:
            continue
        w = a
        if brightness is not None:
            if np.isscalar(brightness):
                w = a * np.exp(-i / max(0.3, brightness))
            else:
                w = a * np.exp(-i / np.maximum(0.3, brightness))
            if np.max(w) < 2e-3:
                break   # 더 높은 배음은 거의 안 들림
        if decay is not None:
            w = w * np.exp(-t * decay * (1 + 0.6 * i))
        out += w * np.sin(2 * np.pi * k * phase + i * 0.7)
    return out


def _bw_filter(x: np.ndarray, kind: str, f, order: int = 2) -> np.ndarray:
    from scipy.signal import butter, sosfilt
    if kind == "bp":
        sos = butter(order, [max(20, f[0]), min(RATE * 0.45, f[1])], "bandpass", fs=RATE, output="sos")
    else:
        sos = butter(order, min(RATE * 0.45, max(20, f)), "lowpass" if kind == "lp" else "highpass", fs=RATE, output="sos")
    return sosfilt(sos, x, axis=0)


def noise(n: int, rng) -> np.ndarray:
    return rng.uniform(-1, 1, n)


# ───────────────────────── 악기 (한 음 → 모노) ─────────────────────────

def _brass(f, n, vel, rng, bright=6.0, dark=False):
    """금관: 여러 겹 톱니 + 밝아지는 배음. 어택에서 한 번 더 밝게 치솟았다(빰) 자리 잡음 — 힘 있게."""
    att = 0.03 if not dark else 0.05
    t = _t(n)
    rise = np.clip(t / att, 0, 1) ** 0.6
    blat = 1.0 + 0.45 * np.exp(-np.maximum(0, t - att) / 0.09)          # 어택 직후 과하게 밝음 → 가라앉음
    br = 1.5 + (bright - 1.5) * rise * blat * (0.75 + 0.25 * vel)
    x = sum(additive(f, n, lambda k: 1.0 / k, br, vib=(5.2, 0.003), detune=d, rng=rng) for d in (-0.004, 0.0, 0.005)) / 3
    return np.tanh(x * 1.6) * env_adsr(n, att, 0.35, 0.72, 0.1)


def i_brass(f, n, vel, rng):            # 낮은 금관 (트롬본·튜바풍)
    return _brass(f, n, vel, rng, bright=5.0, dark=True)


def i_horn(f, n, vel, rng):             # 호른 (둥글게)
    return _brass(f, n, vel, rng, bright=3.5, dark=True) * 0.9


def i_trumpet(f, n, vel, rng):          # 트럼펫 (밝게)
    return _brass(f, n, vel, rng, bright=9.0)


def i_roar(f, n, vel, rng):             # 용의 포효 같은 낮은 금관 (찌그러짐 + 낮은 소음)
    x = _brass(f, n, vel, rng, bright=7.0, dark=True)
    nz = _bw_filter(noise(n, rng), "lp", 400) * env_adsr(n, 0.15, 0.6, 0.4, 0.2) * 0.25
    return np.tanh((x + nz) * 2.2) * 0.8


def i_strings(f, n, vel, rng):          # 현악 (길게, 합주)
    x = sum(additive(f, n, lambda k: 1.0 / k ** 1.1, 4.5, vib=(5.5, 0.004), detune=d, rng=rng) for d in (-0.006, 0.0, 0.006)) / 3
    return x * env_adsr(n, 0.12, 0.3, 0.85, 0.25)


def i_spiccato(f, n, vel, rng):         # 현악 오스티나토 (짧게 튀김 — 활이 튕기는 소리까지)
    t = _t(n)
    x = sum(additive(f, n, lambda k: 1.0 / k, 6.5, detune=d, rng=rng) for d in (-0.005, 0.005)) / 2
    bow = _bw_filter(noise(n, rng), "bp", (f * 2, min(9000, f * 9))) * np.exp(-t * 90) * 0.35
    return (x + bow) * env_adsr(n, 0.004, 0.06, 0.12, 0.03)


def i_tremolo(f, n, vel, rng):          # 현악 트레몰로 (바람 같은 떨림)
    x = i_strings(f, n, vel, rng)
    t = _t(n)
    return x * (0.6 + 0.4 * np.abs(np.sin(2 * np.pi * 7.5 * t + rng.uniform(0, 3))))


def i_pizz(f, n, vel, rng):             # 피치카토
    return additive(f, n, lambda k: 1.0 / k ** 1.4, None, decay=6.0, rng=rng) * env_adsr(n, 0.002, 0.15, 0.0, 0.05)


def i_pad(f, n, vel, rng):              # 부드러운 신스 패드
    x = sum(additive(f, n, lambda k: 1.0 / k ** 1.6, 3.0, vib=(0.3, 0.002), detune=d, rng=rng) for d in (-0.008, 0.0, 0.008)) / 3
    return x * env_adsr(n, 0.5, 0.5, 0.9, 0.6)


def i_drone(f, n, vel, rng):            # 아주 낮은 지속음
    x = additive(f, n, lambda k: 1.0 / k ** 1.2, 3.0, vib=(0.15, 0.002), rng=rng)
    return np.tanh(x * 1.3) * env_adsr(n, 1.0, 1.0, 1.0, 1.0)


def i_bass(f, n, vel, rng):             # 현악 베이스 (첼로·콘트라베이스)
    return additive(f, n, lambda k: 1.0 / k ** 1.2, 3.5, rng=rng) * env_adsr(n, 0.02, 0.25, 0.7, 0.08)


def i_synbass(f, n, vel, rng):          # 부드러운 신스 베이스 맥박
    return additive(f, n, lambda k: 1.0 / k ** 1.5, 2.2, rng=rng) * env_adsr(n, 0.01, 0.18, 0.35, 0.08)


def i_grit(f, n, vel, rng):             # 거칠게 찌그러진 낮은 신스 (전설 전용)
    x = additive(f, n, lambda k: 1.0 / k, 8.0, detune=0.003, rng=rng) + additive(f, n, lambda k: 1.0 / k, 8.0, detune=-0.004, rng=rng)
    return np.tanh(x * 3.0) * 0.6 * env_adsr(n, 0.01, 0.2, 0.6, 0.08)


def i_flute(f, n, vel, rng):            # 플루트·맑은 피리
    t = _t(n)
    x = additive(f, n, [1.0, 0.25, 0.08, 0.03], None, vib=(5.0, 0.006), rng=rng)
    br = _bw_filter(noise(n, rng), "bp", (f * 1.5, f * 3.5)) * 0.12 * np.exp(-t * 6)
    return (x + br) * env_adsr(n, 0.05, 0.3, 0.8, 0.1)


def i_reed(f, n, vel, rng):             # 숨소리 섞인 갈대 피리
    t = _t(n)
    x = additive(f, n, [1.0, 0.05, 0.35, 0.04, 0.15], None, vib=(4.5, 0.008), rng=rng)
    br = _bw_filter(noise(n, rng), "bp", (f * 0.8, f * 4)) * (0.25 + 0.1 * np.exp(-t * 4))
    return (x + br) * env_adsr(n, 0.08, 0.3, 0.75, 0.12)


def i_harp(f, n, vel, rng):             # 하프
    return additive(f, n, lambda k: 1.0 / k ** 1.8, None, decay=1.6, rng=rng) * env_adsr(n, 0.002, 0.6, 0.0, 0.2)


def i_celesta(f, n, vel, rng):          # 첼레스타·오르골
    return additive(f, n, [1.0, 0.0, 0.0, 0.35, 0.0, 0.0, 0.0, 0.1], None, decay=1.2, rng=rng) * env_adsr(n, 0.002, 0.8, 0.0, 0.2)


def i_glass(f, n, vel, rng):            # 유리 벨 (정수배가 아닌 배음)
    return additive(f, n, [1.0, 0.5, 0.25, 0.12], None, decay=0.9, partials=[1.0, 2.76, 5.4, 8.93], rng=rng) * env_adsr(n, 0.002, 1.0, 0.0, 0.3)


def i_crystal(f, n, vel, rng):          # 수정 공명 (길게 우는 금속)
    return additive(f, n, [1.0, 0.6, 0.3, 0.2], None, decay=0.5, partials=[1.0, 2.0, 3.01, 4.17], vib=(3.0, 0.002), rng=rng) \
        * env_adsr(n, 0.01, 1.5, 0.3, 0.5)


def i_harmonics(f, n, vel, rng):        # 기타 하모닉스풍
    return additive(f * 2, n, [1.0, 0.15], None, decay=1.0, rng=rng) * env_adsr(n, 0.003, 0.9, 0.0, 0.3)


def i_choir(f, n, vel, rng, vowel="o"):  # 합창 (모음 공명, 여러 사람)
    forms = VOWELS[vowel]

    def amps(k):
        fk = f * k
        return sum(a * np.exp(-((fk - F) / bw) ** 2) for F, a, bw in forms) + 0.02 / k
    x = sum(additive(f, n, amps, None, vib=(5.3 + d * 40, 0.006), detune=d, rng=rng) for d in (-0.007, -0.002, 0.003, 0.008)) / 4
    return x * env_adsr(n, 0.35, 0.5, 0.9, 0.4)


def i_choir_a(f, n, vel, rng):
    return i_choir(f, n, vel, rng, "a")


INST = {k[2:]: v for k, v in dict(globals()).items() if k.startswith("i_") and callable(v)}


# ───────────────────────── 타악 (한 번 → 모노) ─────────────────────────

def d_timp(n, vel, rng, f=73.4):         # 팀파니
    t = _t(n)
    fp = f * (1 + 0.04 * np.exp(-t * 25))
    ph = np.cumsum(fp) / RATE
    x = sum(a * np.sin(2 * np.pi * r * ph) * np.exp(-t * dcy) for r, a, dcy in ((1, 1.0, 2.2), (1.5, 0.45, 3.5), (1.99, 0.3, 4.5), (2.44, 0.15, 6)))
    th = _bw_filter(noise(n, rng), "lp", 900) * np.exp(-t * 40) * 0.6
    return np.tanh((x + th) * 1.2) * env_adsr(n, 0.002, 1.5, 0.0, 0.05)


def d_bigdrum(n, vel, rng):              # 큰북 (그란 카사·태고)
    t = _t(n)
    f = 48 + 40 * np.exp(-t * 18)
    x = np.sin(2 * np.pi * np.cumsum(f) / RATE) * np.exp(-t * 3.2)
    th = _bw_filter(noise(n, rng), "lp", 300) * np.exp(-t * 12) * 0.7
    return np.tanh((x + th) * 1.8)


def d_taiko(n, vel, rng):                # 공격적인 북 (짧고 단단하게)
    t = _t(n)
    f = 70 + 90 * np.exp(-t * 30)
    x = np.sin(2 * np.pi * np.cumsum(f) / RATE) * np.exp(-t * 7)
    sk = _bw_filter(noise(n, rng), "bp", (300, 2500)) * np.exp(-t * 45) * 0.5
    return np.tanh((x + sk) * 2.0)


def d_snare(n, vel, rng):                # 행진 스네어
    t = _t(n)
    x = _bw_filter(noise(n, rng), "bp", (1500, 7000)) * np.exp(-t * 18) + np.sin(2 * np.pi * 190 * t) * np.exp(-t * 30) * 0.5
    return x


def d_janggu(n, vel, rng):               # 장구 같은 엇박 북 (덩·쿵)
    t = _t(n)
    f = 140 + 60 * np.exp(-t * 35)
    x = np.sin(2 * np.pi * np.cumsum(f) / RATE) * np.exp(-t * 9)
    sl = _bw_filter(noise(n, rng), "bp", (1800, 5000)) * np.exp(-t * 60) * 0.6
    return x + sl


def d_cymbal(n, vel, rng):               # 심벌즈 (부서지듯)
    t = _t(n)
    return _bw_filter(noise(n, rng), "hp", 3500) * np.exp(-t * 1.6) * 0.8


def d_hat(n, vel, rng):
    t = _t(n)
    return _bw_filter(noise(n, rng), "hp", 7000) * np.exp(-t * 60) * 0.6


def d_metal(n, vel, rng):                # 수정이 부딪치는 금속 타악
    t = _t(n)
    f = rng.choice([2400, 2900, 3300, 3700])
    x = sum(a * np.sin(2 * np.pi * f * r * t) for r, a in ((1, 1), (1.47, 0.6), (2.09, 0.4), (2.56, 0.3)))
    return x * np.exp(-t * 9) * 0.5


def d_crackle(n, vel, rng):              # 타닥이는 불씨
    t = _t(n)
    x = np.zeros(n)
    for _ in range(rng.integers(3, 7)):
        p = int(rng.uniform(0, min(n - 200, RATE * 0.12)))
        x[p:p + 120] += rng.uniform(-1, 1, 120) * np.exp(-np.arange(120) / 25)
    return _bw_filter(x, "bp", (1200, 8000)) * 1.5


def d_pulse(n, vel, rng):                # 낮은 맥박 (환상: 부드러운 낮은 박)
    t = _t(n)
    f = 55 + 25 * np.exp(-t * 14)
    return np.sin(2 * np.pi * np.cumsum(f) / RATE) * np.exp(-t * 5) * env_adsr(n, 0.008, 0.5, 0, 0.05)


def d_shaker(n, vel, rng):
    t = _t(n)
    return _bw_filter(noise(n, rng), "bp", (4000, 9000)) * np.minimum(1, t / 0.012) * np.exp(-t * 35) * 0.5


def d_kick(n, vel, rng):                 # 힘 있는 킥 (가슴을 치는 저음 + 딱 소리) — 박을 미는 쾌감
    t = _t(n)
    f = 46 + 110 * np.exp(-t * 32)
    body = np.sin(2 * np.pi * np.cumsum(f) / RATE) * np.exp(-t * 7.5)
    click = _bw_filter(noise(n, rng), "bp", (2500, 7000)) * np.exp(-t * 300) * 0.5
    return np.tanh((body + click) * 2.2)


def d_snare2(n, vel, rng):               # 두꺼운 스네어 (몸통 + 줄 소리 — 1~3kHz 는 비워 신호 자리)
    t = _t(n)
    body = np.sin(2 * np.pi * np.cumsum(180 + 60 * np.exp(-t * 40)) / RATE) * np.exp(-t * 22)
    wires = _bw_filter(noise(n, rng), "bp", (3200, 9500)) * np.exp(-t * 14)
    return np.tanh((body * 0.9 + wires * 0.9) * 1.5)


def d_tom(n, vel, rng, f=110.0):         # 탐 (필인)
    t = _t(n)
    fr = f * (1 + 0.35 * np.exp(-t * 20))
    x = np.sin(2 * np.pi * np.cumsum(fr) / RATE) * np.exp(-t * 8)
    sk = _bw_filter(noise(n, rng), "bp", (400, 3000)) * np.exp(-t * 60) * 0.3
    return np.tanh((x + sk) * 1.8)


def d_crash(n, vel, rng):                # 크래시 (구간이 바뀌는 첫 박 — 확 열리는 순간)
    t = _t(n)
    x = _bw_filter(noise(n, rng), "hp", 3000) * np.exp(-t * 1.1)
    shim = _bw_filter(noise(n, rng), "bp", (6000, 12000)) * np.exp(-t * 0.7) * 0.4
    return (x + shim) * 0.9


def d_ohat(n, vel, rng):                 # 열린 하이햇 (엇박)
    t = _t(n)
    return _bw_filter(noise(n, rng), "hp", 6500) * np.exp(-t * 14) * 0.55


def d_softkick(n, vel, rng):             # 환상: 부드럽고 둥근 킥 (맥박)
    t = _t(n)
    f = 44 + 60 * np.exp(-t * 22)
    return np.sin(2 * np.pi * np.cumsum(f) / RATE) * np.exp(-t * 6) * env_adsr(n, 0.004, 0.4, 0, 0.05) * 1.1


def d_snap(n, vel, rng):                 # 환상: 손가락 튕김·가벼운 박수 (2·4박)
    t = _t(n)
    x = np.zeros(n)
    for k, d in enumerate((0.0, 0.009, 0.018)):
        s = int(d * RATE)
        seg = _bw_filter(noise(n - s, rng), "bp", (3500, 9000)) * np.exp(-_t(n - s) * (90 if k < 2 else 30))
        x[s:] += seg * (0.6 if k < 2 else 1.0)
    return x * 0.7


DRUMS = {k[2:]: v for k, v in dict(globals()).items() if k.startswith("d_") and callable(v)}
DRUM_LEN = {"timp": 1.6, "bigdrum": 1.4, "taiko": 0.6, "snare": 0.35, "janggu": 0.4, "cymbal": 2.2, "hat": 0.12,
            "metal": 0.5, "crackle": 0.15, "pulse": 0.6, "shaker": 0.15, "kick": 0.45, "snare2": 0.4, "tom": 0.6,
            "crash": 2.6, "ohat": 0.3, "softkick": 0.5, "snap": 0.25}
DRUM_PAN = {"hat": 0.3, "shaker": -0.3, "metal": 0.25, "crackle": -0.2, "janggu": -0.15, "ohat": 0.35, "snap": -0.1}

# ── 쾌감 (DESIGN.md 43-12): 모든 곡에 자동으로 더하는 '미는 박' — 킥·스네어·하이햇, 페이즈가 오를수록 촘촘하게 ──
# 단계 0~2 (1페이즈 → 마지막 페이즈), 박자 칸 16(4/4) / 12(3/4·6/8). crisis = 위기 타악에 더하는 것.
DRIVE = {
    "legend": {
        16: [dict(kick="x.......x.....x.", snare2="....x.......x...", hat="x.x.x.x.x.x.x.x."),
             dict(kick="x.....x.x.....x.", snare2="....x.......x..x", hat="x.xxx.xxx.xxx.xx", ohat="..x...x...x...x."),
             dict(kick="x..x..x.x.x..x..", snare2="....x..x....x.x.", hat="xxxxxxxxxxxxxxxx", ohat="..x...x...x...x.")],
        12: [dict(kick="x.....x.....", snare2="......x.....", hat="x.x.x.x.x.x."),
             dict(kick="x.....x..x..", snare2="...x.....x..", hat="x.xxx.xxx.xx", ohat="..x.....x..."),
             dict(kick="x..x..x..x..", snare2="...x..x..x.x", hat="xxxxxxxxxxxx", ohat="..x..x..x..x")],
        "crisis": {16: dict(kick="x.x.x.x.x.x.x.x.", snare2="....x..x....x.xx", tom="............xxxx"),
                   12: dict(kick="x.x.x.x.x.x.", snare2="...x..x..xxx", tom="........xxxx")},
    },
    "phantom": {
        16: [dict(softkick="x.......x.......", shaker="..x...x...x...x.", hat="........x......."),
             dict(softkick="x...x...x...x...", shaker="xxxxxxxxxxxxxxxx", snap="....x.......x...", ohat="..x...x...x...x."),
             dict(softkick="x...x...x...x...", shaker="xxxxxxxxxxxxxxxx", snap="....x.......x...", ohat="..x...x...x...x.")],
        12: [dict(softkick="x.....x.....", shaker="..x..x..x..x"),
             dict(softkick="x.....x.....", shaker="xxxxxxxxxxxx", snap="......x.....", ohat="...x.....x.."),
             dict(softkick="x.....x.....", shaker="xxxxxxxxxxxx", snap="......x.....", ohat="...x.....x..")],
        "crisis": {16: dict(softkick="x.x.x.x.x.x.x.x.", snap="....x..x....x..x"), 12: dict(softkick="x..x..x..x..", snap="...x..x..x.x")},
    },
}
FORM = [0.72, 0.86, 1.0, 1.0]   # 16마디 = 4마디 × 4 (가볍게 → 더함 → 가득 → 가득 + 필인) — 반복 안에서 쌓아 올리는 맛
PUMP = {"legend": 0.28, "phantom": 0.45}   # 킥마다 바탕·합창을 잠깐 눌렀다 놓기 (숨 쉬는 느낌, 사이드체인)
PUMP_LV = (1.0, 1.15, 1.35)                  # 박 단계가 오를수록 더 깊게 — 빽빽한 마지막 페이즈에서도 박이 튀어나오게


# ───────────────────────── 곡 → 층 ─────────────────────────

class Song:
    def __init__(self, sid: str, spec: dict, master: dict):
        self.id, self.spec, self.master = sid, spec, master
        self.root = spec["root"]
        self.scale = spec.get("scale", "minor")
        self.bpm = spec["bpm"]
        num, den = spec.get("meter", [4, 4])
        self.q = 60.0 / self.bpm                         # 4분음표 (초)
        self.bar = self.q * num * 4 / den                # 마디 (초)
        self.steps = int(round(num * 16 / den))          # 마디당 16분음표 칸 (4/4 = 16, 3/4·6/8 = 12)
        self.step = self.bar / self.steps
        self.bars = spec.get("bars", 16)
        self._cache: dict = {}
        self.seed = sum(map(ord, sid)) * 97   # 곡마다 고정 (굽기 결과가 매번 같게)

    # ── 공통 ──
    def loop_len(self, bars: int) -> int:
        return int(round(bars * self.bar * RATE))

    def _buf(self, sec: float) -> np.ndarray:
        return np.zeros((int(sec * RATE) + RATE * 6, 2))

    @staticmethod
    def _place(buf, mono, start: float, gain: float, p: float) -> None:
        s = int(start * RATE)
        if s >= len(buf):
            return
        m = mono[: len(buf) - s] * gain
        a = (np.clip(p, -1, 1) + 1) * np.pi / 4
        buf[s:s + len(m), 0] += m * np.cos(a)
        buf[s:s + len(m), 1] += m * np.sin(a)

    def note(self, buf, inst: str, midi: float, start: float, dur: float, gain=1.0, p=0.0, rng=None, rel=0.3) -> None:
        n = int((dur + rel) * RATE)
        if n <= 0:
            return
        key = (inst, round(midi, 2), n // 64)
        mono = self._cache.get(key)
        if mono is None:   # 같은 악기·음·길이는 한 번만 합성 (오스티나토·반복 화음 — 굽기 시간)
            mono = INST[inst](hz(midi), n, 1.0, rng).astype(np.float32)
            if len(self._cache) < 4000:
                self._cache[key] = mono
        self._place(buf, mono, start, gain, p)

    # ── 파트 연주법 ──
    def render_part(self, buf, part: dict, chords: list, root: int, scale: str, bars: int, rng, crescendo=False) -> None:
        st = part.get("style", "hold")
        inst = part["inst"]
        g = part.get("gain", 1.0)
        o = 12 * part.get("oct", 0)
        p = part.get("pan", 0.0)
        bar, step = self.bar, self.step
        cm = [chord_midis(c, root, scale, 4 if part.get("seventh") else 3) for c in chords]

        def cg(b):   # 인트로 크레셴도
            return (0.45 + 0.55 * b / max(1, bars - 1)) if crescendo else 1.0
        if st == "hold":            # 화음이 바뀔 때까지 길게
            b = 0
            while b < bars:
                e = b + 1
                while e < bars and chords[e] == chords[b]:
                    e += 1
                for i, m in enumerate(cm[b]):
                    self.note(buf, inst, m + o, b * bar, (e - b) * bar * 0.98, g * cg(b), p + (i - 1) * 0.35, rng, rel=0.6)
                b = e
        elif st in ("ostinato", "arp", "pizz", "pulse"):
            pat = part.get("pattern", {"ostinato": "x" * self.steps, "arp": "x.x." * (self.steps // 4),
                                       "pizz": "x...x...x...x..."[: self.steps], "pulse": "x.x." * (self.steps // 4)}[st])
            seq_kind = part.get("seq", "updown")
            for b in range(bars):
                notes = cm[b] + [cm[b][0] + 12]
                seq = notes + notes[-2:0:-1] if seq_kind == "updown" else notes[::-1] if seq_kind == "down" else \
                    [notes[0]] if seq_kind == "root" else [notes[0], notes[0], notes[0] + 7, notes[0] + 12] if seq_kind == "rootfifth" else notes
                k = 0
                for i, ch in enumerate(pat):
                    if ch not in "xX":
                        continue
                    m = seq[k % len(seq)] + o
                    k += 1
                    acc = 1.0 if ch == "X" or i % (self.steps // 4 or 4) == 0 else 0.75
                    ln = step * part.get("len", 1.6 if st != "pizz" else 3)
                    self.note(buf, inst, m, b * bar + i * step, ln, g * acc * cg(b), p + ((k % 4) / 3 - 0.5) * part.get("spread", 0.4), rng,
                              rel=0.15)
        elif st == "bass":          # 근음 리듬 (pattern 칸)
            pat = part.get("pattern", "x.......x.......")[: self.steps]
            for b in range(bars):
                r = cm[b][0] - 12 + o
                for i, ch in enumerate(pat):
                    if ch in "xX":
                        five = part.get("fifths") and ch == "x" and i % 8 == 4
                        self.note(buf, inst, r + (7 if five else 0), b * bar + i * step, step * part.get("len", 3.5),
                                  g * (1.0 if ch == "X" else 0.85) * cg(b), p, rng, rel=0.1)
        elif st == "drone":         # 으뜸음 지속 (페이즈 내내)
            self.note(buf, inst, root - 24 + o, 0.0, bars * bar, g, p, rng, rel=1.0)
            self.note(buf, inst, root - 17 + o, 0.0, bars * bar, g * 0.5, p, rng, rel=1.0)
        elif st == "hits":          # 화음 타격 (pattern 칸)
            pat = part.get("pattern", "X.......x.......")[: self.steps]
            for b in range(bars):
                for i, ch in enumerate(pat):
                    if ch in "xX":
                        for j, m in enumerate(cm[b]):
                            self.note(buf, inst, m + o, b * bar + i * step, step * part.get("len", 4), g * (1.0 if ch == "X" else 0.8) * cg(b),
                                      p + (j - 1) * 0.3, rng, rel=0.25)
        elif st == "sparkle":       # 높은 화음음 무작위 (반짝임)
            per = part.get("per_bar", 4)
            for b in range(bars):
                for k in range(per):
                    m = rng.choice(cm[b]) + o + 12 * rng.integers(0, 2)
                    t0 = b * bar + (k + rng.uniform(0, 0.6)) * bar / per
                    self.note(buf, inst, m, t0, bar / per, g * rng.uniform(0.6, 1.0), rng.uniform(-0.7, 0.7), rng, rel=0.8)
        elif st == "fall":          # 쏟아지는 하강 아르페지오 (별)
            n_per = part.get("per_bar", 8)
            for b in range(bars):
                notes = sorted(cm[b] + [m + 12 for m in cm[b]] + [m + 24 for m in cm[b]], reverse=True)
                for k in range(n_per):
                    m = notes[k % len(notes)] + o
                    self.note(buf, inst, m, b * bar + k * bar / n_per, bar / n_per * 1.5, g * (1 - 0.4 * k / n_per), p + (k % 2 - 0.5) * 0.6, rng,
                              rel=0.6)
        elif st == "melody":        # 주선율 [마디, 박(4분 단위), 도수, 길이(4분)] — canon: 메아리 겹 [박 지연, 세기]...
            notes = part["notes"]
            echoes = [(0.0, 1.0)] + [tuple(e) for e in part.get("canon", [])]
            for d_beats, eg in echoes:
                for b, at, deg, ln in notes:
                    if b >= bars:
                        continue
                    m = degree_to_midi(deg, root, scale) + o
                    t0 = b * bar + (at + d_beats) * self.q
                    self.note(buf, inst, m, t0, ln * self.q * 0.95, g * eg * cg(b), p + (0.5 if d_beats else 0) * (1 if int(d_beats) % 2 else -1),
                              rng, rel=0.35)
        else:
            raise ValueError(f"모르는 연주법: {st}")

    def render_perc(self, buf, pattern: dict, bars: int, rng, crescendo=False, root=None) -> None:
        for kind, pat in pattern.items():
            last_only = kind.endswith("_last")
            k = kind.replace("_last", "")
            pats = pat if isinstance(pat, list) else [pat]
            fn = DRUMS[k]
            for b in range(bars):
                if last_only and b % 4 != 3:
                    continue
                pp = pats[b % len(pats)][: self.steps]
                for i, ch in enumerate(pp):
                    if ch not in "xX":
                        continue
                    vel = 1.0 if ch == "X" else 0.7
                    if crescendo:
                        vel *= 0.45 + 0.55 * b / max(1, bars - 1)
                    n = int(DRUM_LEN[k] * RATE)
                    if k == "timp":   # 으뜸음 (낮은 옥타브), 박 사이엔 5도
                        tm = root or 38
                        while tm > 45:
                            tm -= 12
                        mono = d_timp(n, vel, rng, f=hz(tm) * (1.5 if i % 8 == 4 else 1.0))
                    elif k == "tom":
                        mono = d_tom(n, vel, rng, f=max(75.0, 190.0 - 12.0 * (i % 8)))
                    else:
                        mono = fn(n, vel, rng)
                    self._place(buf, mono, b * self.bar + i * self.step, vel, DRUM_PAN.get(k, 0.0) + rng.uniform(-0.05, 0.05))

    # ── 마무리 ──
    def wrap(self, buf, n_loop: int) -> np.ndarray:
        out = buf[:n_loop].copy()
        tail = buf[n_loop:]
        while len(tail) and np.abs(tail).max() > 1e-6:
            k = min(len(tail), n_loop)
            out[:k] += tail[:k]
            tail = tail[k:]
        return out

    def hall(self, x: np.ndarray, mix: float, time: float, rng) -> np.ndarray:
        """큰 홀 잔향: 미리 지연 + 초기 반사 + 저역 통과된 꼬리 (좌우 다르게)."""
        if mix <= 0:
            return x
        n_ir = int(RATE * time)
        t = _t(n_ir)
        out = np.zeros((len(x) + n_ir, 2))
        L = 1 << int(np.ceil(np.log2(len(x) + n_ir)))
        for ch in range(2):
            ir = rng.uniform(-1, 1, n_ir) * np.exp(-t / (time / 6.5))
            ir = _bw_filter(ir, "lp", 5500)
            ir[: int(RATE * 0.025)] = 0
            for d, a in ((0.011, 0.5), (0.019, 0.35), (0.027, 0.28)):
                ir[int(RATE * (d + 0.004 * ch))] += a
            ir /= np.sqrt(np.sum(ir ** 2)) + 1e-9
            out[:, ch] = np.fft.irfft(np.fft.rfft(x[:, ch], L) * np.fft.rfft(ir, L), L)[: len(out)] * mix
        out[: len(x)] += x * (1 - mix * 0.4)
        return out

    # ── 쾌감 (DESIGN.md 43-12) ──
    def energy(self) -> bool:
        return self.spec.get("energy", True)

    def level(self, i: int) -> int:
        """페이즈 → 박 단계 0~2 (첫 페이즈 0, 마지막 페이즈 2)."""
        n = len(self.spec["phases"])
        return 2 if n == 1 else int(round(i * 2 / (n - 1)))

    def kind(self) -> str:
        return "phantom" if self.spec.get("kind") == "phantom" else "legend"

    def drive_pattern(self, lv: int, crisis: bool = False) -> dict:
        d = DRIVE[self.kind()]
        steps = 16 if self.steps == 16 else 12
        pat = dict(d[steps][lv])
        if crisis:
            pat.update(d["crisis"][steps])
        return pat

    def render_drive(self, buf, pat: dict, bars: int, rng, crescendo=False) -> None:
        """미는 박: 4마디마다 쌓아 올림(FORM), 0·8마디 첫 박 크래시, 7마디 끝 짧은 필인, 마지막 마디 끝 큰 필인(→ 다음 바퀴 크래시)."""
        st, S = self.step, self.steps
        fill_n = 4 if S == 16 else 3
        legend = self.kind() == "legend"
        for b in range(bars):
            gf = FORM[min(3, b * 4 // max(4, bars))] if not crescendo else 0.45 + 0.55 * b / max(1, bars - 1)
            big_fill = (b == bars - 1) and bars >= 4
            for k, pp in pat.items():
                pp = pp[:S]
                for i, ch in enumerate(pp):
                    if ch not in "xX":
                        continue
                    if big_fill and i >= S - fill_n and k not in ("hat", "shaker"):
                        continue   # 필인 자리는 비워 둠
                    vel = (1.0 if ch == "X" or i % (S // 4) == 0 else 0.78) * gf
                    n = int(DRUM_LEN[k] * RATE)
                    mono = d_tom(n, vel, rng, f=150.0) if k == "tom" else DRUMS[k](n, vel, rng)
                    self._place(buf, mono, b * self.bar + i * st, vel, DRUM_PAN.get(k, 0.0) + rng.uniform(-0.04, 0.04))
            if bars >= 8 and b in (0, 8):
                self._place(buf, d_crash(int(DRUM_LEN["crash"] * RATE), 1.0, rng), b * self.bar, 0.8, rng.uniform(-0.3, 0.3))
            if big_fill:   # 탐(전설)·스냅(환상) 내림 필인 + 마지막 칸 스네어
                for j in range(fill_n):
                    t0 = b * self.bar + (S - fill_n + j) * st
                    if legend:
                        self._place(buf, d_tom(int(0.6 * RATE), 1.0, rng, f=190.0 - 35.0 * j), t0, 0.85 + 0.05 * j, 0.4 - 0.27 * j)
                        if j == fill_n - 1:
                            self._place(buf, d_snare2(int(0.4 * RATE), 1.0, rng), t0, 1.0, 0.0)
                    else:
                        self._place(buf, d_snap(int(0.25 * RATE), 1.0, rng), t0, 0.6 + 0.12 * j, 0.0)
                        self._place(buf, d_softkick(int(0.5 * RATE), 1.0, rng), t0, 0.55, 0.0)
            elif bars >= 8 and b % 8 == 7:   # 작은 필인: 마지막 칸 두 개
                for j in range(2):
                    t0 = b * self.bar + (S - 2 + j) * st
                    self._place(buf, (d_snare2 if legend else d_snap)(int(0.35 * RATE), 1.0, rng), t0, 0.55 + 0.2 * j, 0.0)

    def drive_parts(self, lv: int, ph: dict) -> list:
        """바탕에 더하는 빠른 낮은 오스티나토(전설: 질주하는 현 / 환상: 8분 신스 맥박) + 리듬 강조(전설 엇박 금관 / 환상 16분 벨)."""
        S = self.steps
        if self.kind() == "legend":
            gallop = ("x.xxx.xxx.xxx.xx" if S == 16 else "x.xx.xx.xx.x") if lv >= 1 else ("x.x.x.x.x.x.x.x." if S == 16 else "x.x.x.x.x.x.")
            out = [dict(inst="spiccato", style="ostinato", gain=0.3 if lv else 0.24, oct=-1, pattern=gallop, seq="rootfifth", len=1.2)]
            if lv >= 1 and not any(p.get("style") == "hits" for p in ph.get("base", [])):
                out.append(dict(inst="brass", style="hits", gain=0.3, oct=-1, len=1.4,
                                pattern="X..X..X...X.X..." if S == 16 else "X..X..X.x..."))
            return out
        out = [dict(inst="synbass", style="pulse", gain=0.34, oct=-1, seq="root",
                    pattern="x.x.x.x.x.x.x.x." if S == 16 else "x.x.x.x.x.x.")]
        if lv >= 2:
            out.append(dict(inst="celesta", style="arp", gain=0.15, oct=1, seq="up", pattern="x" * S, len=1.0, spread=0.7))
        return out

    def pump(self, x: np.ndarray, kicks: list, depth: float) -> np.ndarray:
        """사이드체인: 킥마다 depth 만큼 눌렀다 0.15초에 걸쳐 놓기 (반복 길이 안에서 이어지게)."""
        n = len(x)
        env = np.ones(n)
        rel = int(0.15 * RATE)
        att = int(0.005 * RATE)
        shape = np.concatenate([1 - depth * np.linspace(0, 1, att), 1 - depth * np.exp(-np.arange(rel) / (rel / 4))])
        for t0 in kicks:
            s = int(t0 * RATE) % n
            seg = shape[: n - s]
            env[s:s + len(seg)] = np.minimum(env[s:s + len(seg)], seg)
            if len(seg) < len(shape):
                rest = shape[len(seg):]
                env[:len(rest)] = np.minimum(env[:len(rest)], rest)
        return x * env[:, None]

    def kick_times(self, pat: dict, bars: int) -> list:
        out = []
        for k in ("kick", "softkick"):
            for i, ch in enumerate(pat.get(k, "")[: self.steps]):
                if ch in "xX":
                    out += [b * self.bar + i * self.step for b in range(bars)]
        return sorted(out)

    # ── 층 만들기 ──
    def phase_info(self, i: int) -> tuple[int, str]:
        ph = self.spec["phases"][i]
        return self.root + ph.get("transpose", 0), ph.get("scale", self.scale)

    def render_layer(self, parts: list, chords, root, scale, bars, rng, reverb, crescendo=False, perc=None) -> np.ndarray:
        buf = self._buf(bars * self.bar)
        if perc is not None:
            self.render_perc(buf, perc, bars, rng, crescendo, root=root)
        for part in parts or []:
            self.render_part(buf, part, chords, root, scale, bars, rng, crescendo)
        return self.hall(buf, reverb[0], reverb[1], rng) if reverb else buf

    def stems(self) -> dict[str, np.ndarray]:
        """모든 층 (마스터링 전, 반복 층은 wrap 까지)."""
        sp = self.spec
        rv = sp.get("reverb", [0.25, 2.6])
        en = self.energy()
        if en:   # 잔향을 줄여 또렷하게 (넓게 번지면 밋밋해짐)
            rv = [rv[0] * 0.62, rv[1] * 0.8]
        prv = [rv[0] * (0.45 if en else 0.6), rv[1] * (0.6 if en else 0.7)]
        out = {}
        n16 = self.loop_len(self.bars)
        phases = sp["phases"]
        for i, ph in enumerate(phases):
            root, scale = self.phase_info(i)
            rng = np.random.default_rng(self.seed + i * 13)
            chords = ph["chords"]
            if len(chords) < self.bars:
                chords = (chords * (self.bars // len(chords) + 1))[: self.bars]
            pre = f"{i + 1}_"
            lv = self.level(i)
            on = en and ph.get("drive", True)
            base_parts = list(ph.get("base") or []) + (self.drive_parts(lv, ph) if on else [])
            base = self.wrap(self.render_layer(base_parts, chords, root, scale, self.bars, rng, rv), n16)
            perc = ph.get("perc", {})
            dpat = self.drive_pattern(lv) if on else {}

            def perc_layer(pattern, crisis):
                buf = self._buf(self.bars * self.bar)
                self.render_perc(buf, pattern, self.bars, rng, root=root)
                if on:
                    self.render_drive(buf, self.drive_pattern(lv, crisis), self.bars, rng)
                return self.wrap(self.hall(buf, prv[0], prv[1], rng), n16)
            out[pre + "perc"] = perc_layer(perc.get("pattern", {}), False)
            crisis = dict(perc.get("pattern", {}))
            for k, v in perc.get("crisis", {}).items():
                crisis[k] = v
            out[pre + "perc_crisis"] = perc_layer(crisis, True)
            lead = ph.get("lead") or []
            out[pre + "lead"] = self.wrap(self.render_layer(lead, chords, root, scale, self.bars, np.random.default_rng(self.seed + i * 13 + 1), rv), n16)
            up = [dict(p, oct=p.get("oct", 0) + 1) for p in lead]
            out[pre + "lead_oct"] = self.wrap(self.render_layer(up, chords, root, scale, self.bars, np.random.default_rng(self.seed + i * 13 + 1), rv), n16)
            choir = self.wrap(self.render_layer(ph.get("choir"), chords, root, scale, self.bars, rng, rv), n16)
            if on:   # 킥마다 바탕·합창이 숨 쉬듯 (사이드체인)
                kt = self.kick_times(dpat, self.bars)
                depth = min(0.6, PUMP[self.kind()] * PUMP_LV[lv])
                base = self.pump(base, kt, depth)
                choir = self.pump(choir, kt, depth * 0.7)
            out[pre + "base"] = base
            out[pre + "choir"] = choir
            if i + 1 < len(phases):
                out[pre + "riser"] = self.riser(i, rng, rv)
        out["intro_mix"] = self.intro(rv)
        return out

    def intro(self, rv) -> np.ndarray:
        sp = self.spec
        ph = sp["phases"][0]
        root, scale = self.phase_info(0)
        it = sp.get("intro", {})
        chords = it.get("chords", [1, 5])
        rng = np.random.default_rng(self.seed + 999)
        parts = it.get("parts", ph.get("base"))
        perc = it.get("perc", ph.get("perc", {}).get("pattern", {}))
        buf = self.render_layer(parts, chords, root, scale, 2, rng, rv, crescendo=True, perc=perc)
        if self.energy():   # 인트로: 박이 점점 커지고 둘째 마디 뒷반은 스네어(환상 = 스냅) 롤 → 1페이즈 첫 박
            self.render_drive(buf, self.drive_pattern(0), 2, rng, crescendo=True)
            half = self.steps // 2
            for j in range(half):
                t0 = self.bar + (half + j) * self.step
                fn = d_snare2 if self.kind() == "legend" else d_snap
                self._place(buf, fn(int(0.35 * RATE), 1.0, rng), t0, 0.35 + 0.6 * j / max(1, half - 1), 0.0)
        if it.get("hit", True):   # 정적을 깨는 첫 타격
            hit = self._buf(1.5)
            self._place(hit, d_bigdrum(int(1.4 * RATE), 1.0, rng), 0.0, 1.0, 0.0)
            for m in chord_midis(1, root, scale):
                self.note(hit, it.get("hit_inst", "brass"), m - 12, 0.0, self.q * 1.5, 0.8, 0.0, rng)
            buf[: len(hit)] += self.hall(hit, rv[0], rv[1], rng)[: len(hit)]
        n = self.loop_len(2)
        out = buf[: n + int(RATE * 0.02)].copy()   # 인트로 꼬리는 1페이즈 첫머리에 묻힘 — 끝 20ms 페이드
        out[n:] *= np.linspace(1, 0, len(out) - n)[:, None]
        return out[:n]

    def riser(self, i: int, rng, rv) -> np.ndarray:
        """다음 페이즈로: 1마디 동안 부풀어 오르는 소리(역재생 심벌) + 스네어·팀파니 롤 + 상승 음계."""
        root, scale = self.phase_info(i)
        nroot, nscale = self.phase_info(i + 1)
        bar = self.bar
        n = self.loop_len(1)
        buf = self._buf(bar)
        t = _t(n)
        sw = _bw_filter(noise(n, rng), "hp", 2500) * (t / (n / RATE)) ** 3 * 0.9
        self._place(buf, sw, 0.0, 1.0, 0.0)
        roll = "timp" if self.spec.get("kind", "legend") == "legend" else "pulse"
        k = self.steps
        for s in range(k):
            vel = 0.3 + 0.7 * s / (k - 1)
            m = d_timp(int(0.5 * RATE), vel, rng, f=hz(root - 24)) if roll == "timp" else d_pulse(int(0.4 * RATE), vel, rng)
            self._place(buf, m, s * self.step, vel * 0.8, 0.0)
        if self.energy():   # 스네어(환상: 셰이커) 16분 롤 크레셴도 → 다음 페이즈 첫 박 크래시
            for s in range(k):
                vel = 0.25 + 0.75 * (s / (k - 1)) ** 1.5
                fn = d_snare2 if roll == "timp" else d_shaker
                self._place(buf, fn(int(0.3 * RATE), vel, rng), s * self.step, vel, 0.0)
                if s >= k // 2:   # 뒷반은 32분
                    self._place(buf, fn(int(0.3 * RATE), vel, rng), (s + 0.5) * self.step, vel * 0.8, 0.0)
        inst = "strings" if roll == "timp" else "harp"
        for s in range(8):
            m = degree_to_midi(s + 1, nroot, nscale)
            self.note(buf, inst, m, s * bar / 8, bar / 8, 0.5 + 0.5 * s / 7, (s / 7 - 0.5) * 0.6, rng, rel=0.2)
        out = self.hall(buf, rv[0], rv[1] * 0.6, rng)[:n]
        out[-int(RATE * 0.02):] *= np.linspace(1, 0, int(RATE * 0.02))[:, None]
        return out


# ───────────────────────── 마스터링 ─────────────────────────

def peaking_eq(x: np.ndarray, f0: float, gain_db: float, q: float) -> np.ndarray:
    """RBJ 피킹 필터 (중음역 살짝 비우기)."""
    from scipy.signal import lfilter
    A = 10 ** (gain_db / 40)
    w0 = 2 * np.pi * f0 / RATE
    al = np.sin(w0) / (2 * q)
    b = np.array([1 + al * A, -2 * np.cos(w0), 1 - al * A])
    a = np.array([1 + al / A, -2 * np.cos(w0), 1 - al / A])
    return lfilter(b / a[0], a / a[0], x, axis=0)


def lufs(x: np.ndarray) -> float:
    import pyloudnorm
    return float(pyloudnorm.Meter(RATE).integrated_loudness(x))


def true_peak_db(x: np.ndarray) -> float:
    from scipy.signal import resample_poly
    up = resample_poly(x, 4, 1, axis=0)
    return 20 * np.log10(max(1e-9, float(np.abs(up).max())))


def mixes(stems: dict, n_phases: int) -> dict[str, np.ndarray]:
    """마스터링·측정용 조합: 인트로, 페이즈별 보통 / 위기 / 지침(옥타브)."""
    out = {"intro": stems["intro_mix"]}
    for i in range(1, n_phases + 1):
        p = f"{i}_"
        base = stems[p + "base"] + stems[p + "choir"]
        out[f"{i}"] = base + stems[p + "perc"] + stems[p + "lead"]
        out[f"{i}_crisis"] = base + stems[p + "perc_crisis"] + stems[p + "lead"]
        out[f"{i}_oct"] = base + stems[p + "perc_crisis"] + stems[p + "lead_oct"]
    return out


def master(stems: dict, n_phases: int, cfg: dict) -> tuple[dict, dict]:
    """중음역 −2dB → 곡 전체(인트로 + 페이즈 보통 믹스) −14 LUFS, 모든 조합의 최대치 −1dBTP 이하.
    층마다 같은 배율 (층끼리 비율 유지). 타악 층은 피크가 크면 부드럽게 눌러(소프트 리미트) 크기를 확보."""
    band = cfg.get("mid_band", [1000, 3000])
    f0 = float(np.sqrt(band[0] * band[1]))
    q = f0 / (band[1] - band[0]) * 1.0
    st = {k: peaking_eq(v, f0, cfg.get("mid_cut_db", -2.0), q) for k, v in stems.items()}
    target, ceil = cfg.get("lufs", -14.0), cfg.get("tp", -1.0)
    report = {}
    for it in range(10):
        mx = mixes(st, n_phases)
        whole = np.concatenate([mx["intro"]] + [mx[str(i)] for i in range(1, n_phases + 1)])
        lu = lufs(whole)
        g = 10 ** ((target - lu) / 20)
        tp = max(true_peak_db(v * g) for v in mx.values())
        if tp <= ceil + 0.05 or it == 9:
            break
        # 넘치면: 모든 층의 피크를 부드럽게 눌러(소프트 리미트) 크레스트를 줄이고 다시 — 타악은 더 세게
        over = 10 ** ((tp - ceil) / 20)
        for k in list(st):
            pk = np.abs(st[k]).max() or 1.0
            hard = k.endswith("perc") or k.endswith("perc_crisis") or k == "intro_mix"
            th = pk / over ** (0.8 if hard else 0.5)
            st[k] = np.tanh(st[k] / th) * th
    g_tp = 10 ** ((ceil - tp) / 20) if tp > ceil else 1.0
    g *= g_tp
    out = {k: (v * g).astype(np.float32) for k, v in st.items()}
    mx = mixes(out, n_phases)
    whole = np.concatenate([mx["intro"]] + [mx[str(i)] for i in range(1, n_phases + 1)])
    report["lufs"] = round(lufs(whole), 2)
    report["tp"] = round(max(true_peak_db(v) for v in mx.values()), 2)
    report["phases"] = {k: round(lufs(v), 2) for k, v in mx.items() if "_" not in k}
    return out, report


def song_specs() -> tuple[dict, dict]:
    from src.core.config import load_json
    b = load_json("music_patterns.json").get("boss", {})
    return {k: v for k, v in b.get("songs", {}).items() if not k.startswith("_")}, b.get("master", {})


def render_song(sid: str) -> tuple[dict, dict]:
    songs, mcfg = song_specs()
    song = Song(sid, songs[sid], mcfg)
    return master(song.stems(), len(songs[sid]["phases"]), mcfg)
