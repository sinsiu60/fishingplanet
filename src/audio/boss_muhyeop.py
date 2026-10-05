"""국악 무협 전투 곡 (ILSEOM.md, DESIGN.md 43-15) — 청새치 '일섬' 전용 L04-MUHYEOP. 스펙에 "muhyeop": true.

boss_synth.Song 을 물려받아 층 구조·반복 이음새·마스터링은 그대로, 악기와 연주만 국악 무협으로 (boss_synth.py 는 그대로).
페이즈마다 빠르기·박자가 다르다 (스펙 phases[i].bpm · meter — 1·2페이즈 12/8 점4분 = 100, 3페이즈 4/4 168).
  악기  대금(숨소리 + 아래에서 밀어 올리는 시작 + 깊고 느린 떨림) · 해금(콧소리 + 음 사이 미끄러짐) · 태평소(날카로운 겹리드)
        가야금(뜯는 현 + 농현) · 거문고(낮게 튕김 + 술대 딱) · 장구(쿵 · 덕) · 대고 · 징(여러 배음 4초 여운)
        칼 소리: 스릉(뽑기) · 챙(부딪침) · 슉(베기) · 착(칼집) · 쨍(부러짐)
  바탕  가야금 반복(으뜸·으뜸·5도 / 으뜸·4도·5도, 12/8 은 8분 · 3페이즈 16분) + 거문고(1·4·7·10칸 / 4분)
  타악  12/8: 대고 x.....x..... · 쿵 ...x.....x.. · 덕 ..x..x..x..x (2페이즈 마디 첫 칸 작은 '챙')
        4/4: 대고 x..x..x.x..x..x. · 덕 16칸 전부 · 쿵 x...x...x...x... · 징 4마디마다
  위기  대고 연타 + 해금 높은 음 떨림 (위기 타악 층에) / 지침: 옥타브 주선율 층 = 대금 한 옥타브 위 깊은 떨림
  전환  라이저 1마디 = 징 + 장구 몰아치기 (다음 페이즈 빠르기) / 실패: 칼 부러지는 '쨍' → 징 여운 1.5초
  인트로 바람 → 챔질 순간 칼 뽑는 '스릉—' (반 마디) → 1페이즈 첫 박 대고 '둥!' + 징
"""
import numpy as np

from src.audio.boss_synth import RATE, Song, _bw_filter, _t, chord_midis, degree_to_midi, hz, noise, peaking_eq


# ───────────────────────── 악기 ─────────────────────────

def _ph(f_t: np.ndarray) -> np.ndarray:
    return 2 * np.pi * np.cumsum(f_t) / RATE


def _harm(f_t: np.ndarray, amps, decay: float = 0.0, top: float = 8000.0) -> np.ndarray:
    n = len(f_t)
    t = _t(n)
    ph = _ph(f_t)
    out = np.zeros(n)
    fm = float(f_t.max())
    for k, a in enumerate(amps, start=1):
        if fm * k > top:
            break
        w = np.exp(-t * decay * k) if decay else 1.0
        out += a * np.sin(k * ph + 0.4 * k) * w
    return out


def _env(n: int, a: float, d: float = 0.0, rel: float = 0.05) -> np.ndarray:
    t = _t(n)
    e = np.minimum(1.0, t / max(a, 1e-4))
    if d:
        e = e * np.exp(-t * d)
    r = min(n, int(rel * RATE))
    if r > 0:
        e[-r:] *= np.linspace(1, 0, r)
    return e


def _vib(t, start, depth, rate, ramp=0.3):
    return depth * np.sin(2 * np.pi * rate * np.maximum(0, t - start)) * np.clip((t - start) / ramp, 0, 1)


def _norm(x):
    return x / (float(np.abs(x).max()) or 1.0)


def i_daegeum(f, n, rng, dur=0.0, q=0.4, tired=False, **k):
    """대금: 맑은 음 + 숨소리, 아래에서 밀어 올리는 시작, 1박 이상은 깊고 느린 떨림 (지침 = 더 깊게)."""
    t = _t(n)
    semi = -1.2 * np.exp(-t / 0.045)
    if dur >= 0.9 * q:
        semi += _vib(t, 0.22, 0.55 if tired else 0.38, 4.6 + 0.8 * np.clip(t / 2, 0, 1), 0.35)
    f_t = f * 2 ** (semi / 12)
    tone = _harm(f_t, [1.0, 0.42, 0.2, 0.1, 0.06, 0.03])
    br = _bw_filter(noise(n, rng), "bp", (f * 1.2, min(10000, f * 10))) * (0.28 + 0.5 * np.exp(-t / 0.05))
    x = np.tanh(1.4 * (tone + br * 2.2))   # 청(갈대막) 떨림 같은 거친 기운
    return _norm(x) * _env(n, 0.035, 0.25, 0.06)


def i_daegeum_t(f, n, rng, **k):
    return i_daegeum(f, n, rng, **dict(k, tired=True))


def i_haegeum(f, n, rng, dur=0.0, q=0.4, frm=None, trem=False, **k):
    """해금: 활로 긋는 콧소리 (중음 강조), 앞 음에서 미끄러져 옴, 떨림."""
    t = _t(n)
    semi = np.zeros(n)
    if frm is not None:
        d = 12 * np.log2(hz(frm) / f)
        semi += d * np.clip(1 - t / 0.09, 0, 1) ** 1.5
    if trem:
        semi += 0.55 * np.sin(2 * np.pi * 8.5 * t)
    elif dur >= 0.6 * q:
        semi += _vib(t, 0.14, 0.32, 6.0, 0.2)
    f_t = f * 2 ** (semi / 12)
    x = _harm(f_t, [1 / k_ for k_ in range(1, 30)], top=6500)
    x += _bw_filter(noise(n, rng), "bp", (1500, 5000)) * 0.06   # 활 긁힘
    x = peaking_eq(peaking_eq(_bw_filter(x, "hp", 220), 1150.0, 9.0, 1.3), 2600.0, 4.0, 1.0)
    if trem:
        x *= 1 + 0.25 * np.sin(2 * np.pi * 8.5 * t)
    return _norm(x) * _env(n, 0.03, 0.15, 0.05)


def i_haegeum_trem(f, n, rng, **k):
    return i_haegeum(f, n, rng, trem=True)


def i_taepyeongso(f, n, rng, dur=0.0, q=0.4, **k):
    """태평소: 날카롭고 거친 겹리드 나팔 (중고음), 크게."""
    t = _t(n)
    semi = -0.7 * np.exp(-t / 0.035)
    if dur >= 0.9 * q:
        semi += _vib(t, 0.18, 0.28, 6.2, 0.2)
    f_t = f * 2 ** (semi / 12) * (1 + 0.003 * np.sin(2 * np.pi * 1.3 * t))
    x = _harm(f_t, [1 / k_ ** 0.65 for k_ in range(1, 26)], top=7000)
    x = np.tanh(2.2 * _norm(x))
    x = _bw_filter(peaking_eq(_bw_filter(x, "hp", 300), 1800.0, 5.0, 0.9), "lp", 5200)
    return _norm(x) * _env(n, 0.02, 0.1, 0.04)


def i_gayageum(f, n, rng, nong=False, **k):
    """가야금: 뜯는 명주 현 (둥글게) + 농현(뜯은 뒤 음을 살짝 흔들기)."""
    t = _t(n)
    semi = np.zeros(n)
    if nong:
        semi += 0.45 * np.sin(2 * np.pi * 5.0 * np.maximum(0, t - 0.1)) * (t > 0.1)
    f_t = f * 2 ** (semi / 12)
    x = _harm(f_t, [1.0, 0.6, 0.38, 0.3, 0.2, 0.14, 0.1, 0.07, 0.05, 0.035, 0.025], decay=1.1)
    m = min(n, int(0.004 * RATE))
    x[:m] += _bw_filter(noise(m, rng), "bp", (1500, 5000)) * 0.6
    x = _bw_filter(x, "lp", 5200)
    return _norm(x) * _env(n, 0.002, 3.2, 0.03)


def i_geomungo(f, n, rng, **k):
    """거문고: 낮고 무겁게 튕김 + 술대로 치는 '딱'."""
    x = _harm(np.full(n, f), [1.0, 0.7, 0.45, 0.25, 0.15, 0.08], decay=1.4)
    x = np.tanh(1.6 * _norm(x))
    m = min(n, int(0.012 * RATE))
    x[:m] += _bw_filter(noise(m, rng), "bp", (1500, 4000)) * np.exp(-np.arange(m) / (m / 5)) * 1.1
    return _norm(x) * _env(n, 0.002, 2.2, 0.03)


def d_kung(n, vel, rng):          # 장구 궁편 (손바닥): 낮고 둥근 '쿵'
    t = _t(n)
    f = 85 + 40 * np.exp(-t * 25)
    x = np.sin(_ph(f)) * np.exp(-t * 9) + _bw_filter(noise(n, rng), "lp", 400) * np.exp(-t * 40) * 0.3
    return x * np.minimum(1, t / 0.004)


def d_deok(n, vel, rng):          # 장구 채편 (열채): 높고 단단한 '덕'
    t = _t(n)
    x = np.sin(_ph(np.full(n, 340.0) * (1 + 0.2 * np.exp(-t * 60)))) * np.exp(-t * 30) * 0.7
    x += _bw_filter(noise(n, rng), "bp", (2200, 7000)) * np.exp(-t * 70)
    return np.tanh(1.5 * x)


def d_daego(n, vel, rng):         # 대고: 아주 낮고 큰 북
    t = _t(n)
    f = 46 + 22 * np.exp(-t * 14)
    x = np.sin(_ph(f)) * np.exp(-t * 3.2) + _bw_filter(noise(n, rng), "lp", 300) * np.exp(-t * 25) * 0.5
    return np.tanh(1.4 * x) * np.minimum(1, t / 0.003)


def d_jing(n, vel, rng):          # 징: 여러 배음이 맥놀이하며 길게 (4초), 바탕음이 살짝 올라가는 '웅—'
    t = _t(n)
    f0 = 92.0 * (1 + 0.025 * (1 - np.exp(-t / 0.8)))
    x = np.zeros(n)
    for r, a, dec in ((1.0, 1.0, 0.55), (1.52, 0.55, 0.7), (2.03, 0.45, 0.9), (2.41, 0.3, 1.1), (2.96, 0.25, 1.4),
                      (3.62, 0.15, 1.8), (4.41, 0.1, 2.2), (5.52, 0.08, 2.6), (6.81, 0.06, 3.0), (8.13, 0.05, 3.4),
                      (10.4, 0.04, 4.0), (13.7, 0.03, 4.6)):
        x += a * np.sin(_ph(f0 * r)) * np.exp(-t * dec)
        x += a * 0.5 * np.sin(_ph(f0 * r * 1.004)) * np.exp(-t * dec)   # 맥놀이
    x *= np.minimum(1, t / 0.012)
    x += _bw_filter(noise(n, rng), "bp", (300, 1200)) * np.exp(-t * 30) * 0.2
    return _norm(x)


def s_seureung(n, rng):           # 칼 뽑기 '스릉—': 쇠 긁히는 소리가 점점 높아짐
    t = _t(n)
    u = t / t[-1]
    x = np.zeros(n)
    seg = max(1, n // 16)
    src = noise(n, rng)
    for i in range(16):
        fc = 1500 * (5.0 ** (i / 15))
        s, e = i * seg, min(n, (i + 2) * seg)
        x[s:e] += _bw_filter(src[s:e], "bp", (fc * 0.8, fc * 1.25)) * np.hanning(e - s)
    ring = sum(a * np.sin(_ph(fr * (1 + 0.15 * u))) for fr, a in ((2100, 0.5), (3300, 0.35), (5200, 0.25)))
    y = x * 1.2 + ring * 0.25 * u ** 2
    return _norm(y) * (0.3 + 0.7 * u) * np.minimum(1, (1 - u) / 0.08 + 0.2)


def s_chaeng(n, rng, k=1.0):      # 칼 부딪침 '챙': 짧은 쇠 울림
    t = _t(n)
    x = sum(a * np.sin(_ph(np.full(n, fr * k))) * np.exp(-t * d) for fr, a, d in
            ((2350, 1.0, 7), (3420, 0.7, 9), (4870, 0.5, 11), (6230, 0.35, 14), (7900, 0.2, 18)))
    m = min(n, int(0.005 * RATE))
    x[:m] += noise(m, rng) * 1.5
    return np.tanh(1.3 * _norm(x))


def s_syuk(n, rng):               # 베기 '슉': 바람 가르는 소리
    t = _t(n)
    u = t / t[-1]
    x = np.zeros(n)
    seg = max(1, n // 10)
    src = noise(n, rng)
    for i in range(10):
        fc = 800 * (5 ** (i / 9))
        s, e = i * seg, min(n, (i + 2) * seg)
        x[s:e] += _bw_filter(src[s:e], "bp", (fc * 0.7, fc * 1.4)) * np.hanning(e - s)
    return _norm(x) * np.sin(np.pi * u) ** 1.5


def s_chak(n, rng):               # 칼집에 넣기 '착': 짧고 단단한 나무 + 쇠
    t = _t(n)
    x = _bw_filter(noise(n, rng), "bp", (350, 1100)) * np.exp(-t * 90) * 1.4
    x += sum(np.sin(_ph(np.full(n, fr))) * np.exp(-t * 35) * a for fr, a in ((3900, 0.5), (5600, 0.3)))
    d = int(0.028 * RATE)
    if d < n:
        x[d:] += _bw_filter(noise(n - d, rng), "bp", (500, 2500)) * np.exp(-_t(n - d) * 120) * 0.6
    return np.tanh(1.5 * _norm(x))


def s_jjaeng(n, rng):             # 칼이 부러지는 '쨍': 깨지는 날카로운 쇠
    t = _t(n)
    x = sum(a * np.sin(_ph(fr * (1 - 0.04 * (1 - np.exp(-t * 6))))) * np.exp(-t * d) for fr, a, d in
            ((3100, 1.0, 5), (4730, 0.8, 6), (6650, 0.6, 8), (8800, 0.4, 10), (10400, 0.3, 12)))
    x = np.full(n, 0.0) + x
    m = min(n, int(0.03 * RATE))
    x[:m] += _bw_filter(noise(m, rng), "hp", 2500) * 2.0
    return np.tanh(1.6 * _norm(x))


def s_wind(n, rng):               # 넓은 바다 바람
    t = _t(n)
    x = _bw_filter(noise(n, rng), "bp", (180, 1300))
    return _norm(x) * (0.6 + 0.4 * np.sin(2 * np.pi * 0.35 * t + 1.0)) * np.minimum(1, t / 0.3)


INST = {"daegeum": i_daegeum, "daegeum_t": i_daegeum_t, "haegeum": i_haegeum, "haegeum_trem": i_haegeum_trem,
        "taepyeongso": i_taepyeongso, "gayageum": i_gayageum, "geomungo": i_geomungo}
DRUM = {"daego": (d_daego, 1.4), "kung": (d_kung, 0.5), "deok": (d_deok, 0.25), "jing": (d_jing, 4.0)}
KIT_GAIN = {"daego": 1.0, "kung": 0.55, "deok": 0.4, "jing": 0.42, "clash": 0.22}
KIT_PAN = {"kung": -0.2, "deok": 0.25, "jing": 0.1, "clash": 0.3}


# ───────────────────────── 곡 ─────────────────────────

class MuhyeopSong(Song):
    def __init__(self, sid, spec, master):
        super().__init__(sid, spec, master)
        self._frm = None
        self._nong = False

    def set_tempo(self, i: int) -> None:
        """페이즈 i 의 빠르기·박자 (없으면 곡 기본)."""
        ph = self.spec["phases"][i] if i is not None else {}
        bpm = ph.get("bpm", self.spec["bpm"])
        num, den = ph.get("meter", self.spec.get("meter", [4, 4]))
        self.bpm, self.q = bpm, 60.0 / bpm
        self.bar = self.q * num * 4 / den
        self.steps = int(round(num * 16 / den))
        self.step = self.bar / self.steps
        self.cells = 12 if (num, den) == (12, 8) else self.steps   # 리듬 뼈대 칸 (12/8 = 8분 12칸)

    # ── 한 음 ──
    def note(self, buf, inst: str, midi: float, start: float, dur: float, gain=1.0, p=0.0, rng=None, rel=0.3) -> None:
        n = int((dur + rel) * RATE)
        if n <= 0:
            return
        frm = self._frm if inst == "haegeum" else None
        nong = self._nong if inst == "gayageum" else False
        key = (inst, round(midi, 2), n // 64, frm, nong, round(self.q, 4))
        mono = self._cache.get(key)
        if mono is None:
            mono = INST[inst](hz(midi), n, rng, dur=dur, q=self.q, frm=frm, nong=nong).astype(np.float32)
            if len(self._cache) < 3000:
                self._cache[key] = mono
        self._place(buf, mono, start, gain, p)

    def sfx(self, buf, name: str, start: float, dur: float, gain: float, p: float, rng) -> None:
        fn = {"seureung": s_seureung, "chaeng": s_chaeng, "syuk": s_syuk, "chak": s_chak, "jjaeng": s_jjaeng, "wind": s_wind}[name]
        self._place(buf, fn(int(dur * RATE), rng), start, gain, p)

    # ── 연주법 ──
    def render_part(self, buf, part: dict, chords: list, root: int, scale: str, bars: int, rng, crescendo=False) -> None:
        st = part.get("style")
        g, o, p = part.get("gain", 1.0), 12 * part.get("oct", 0), part.get("pan", 0.0)
        bar = self.bar
        if st == "gaya":     # 가야금 반복: 으뜸·으뜸·5도 / 으뜸·4도·5도 (12/8 8분 · 4/4 16분)
            seq = (0, 0, 7, 0, 5, 7) if self.cells == 12 else (0, 0, 7, 0, 5, 7, 0, 12)
            cell = bar / self.cells
            for b in range(bars):
                r = chord_midis(chords[b], root, scale)[0] + o
                for i in range(self.cells):
                    self._nong = i == 0
                    acc = 1.0 if i % (3 if self.cells == 12 else 4) == 0 else 0.72
                    self.note(buf, "gayageum", r + seq[i % len(seq)], b * bar + i * cell, cell * 0.9, g * acc,
                              p + (0.2 if i % 2 else -0.2), rng, rel=0.25)
            self._nong = False
            return
        if st == "geomungo":   # 거문고: 12/8 1·4·7·10칸 / 4/4 4분
            hits = (0, 3, 6, 9) if self.cells == 12 else (0, 4, 8, 12)
            cell = bar / self.cells
            for b in range(bars):
                r = chord_midis(chords[b], root, scale)[0] - 24 + o
                for k, i in enumerate(hits):
                    self.note(buf, "geomungo", r + (7 if k == 2 else 0), b * bar + i * cell, cell * 2.5, g * (1.0 if k == 0 else 0.8),
                              p - 0.1, rng, rel=0.3)
            return
        if st == "hold_hae":   # 합창 자리: 해금 높은 음 지속 (2마디마다 화음의 5도)
            for b in range(0, bars, 2):
                m = chord_midis(chords[b], root, scale)[2] + o
                self._frm = None
                self.note(buf, "haegeum", m, b * bar, 2 * bar * 0.96, g, p, rng, rel=0.2)
            return
        if st == "trem_hae":   # 위기: 해금 높은 음 떨림
            for b in range(bars):
                m = chord_midis(chords[b], root, scale)[2] + o
                self.note(buf, "haegeum_trem", m, b * bar, bar * 0.98, g, p, rng, rel=0.05)
            return
        if st == "melody":
            inst = part["inst"]
            prev_end, prev_m = -9.0, None
            for b, at, deg, ln in sorted(part["notes"], key=lambda x: (x[0], x[1])):
                if b >= bars:
                    continue
                m = degree_to_midi(deg, root, scale) + o
                t0 = b * bar + at * self.q
                self._frm = prev_m if (prev_m is not None and t0 - prev_end < 0.06 and prev_m != m) else None
                d = ln * self.q * 0.95
                self.note(buf, inst, m, t0, d, g, p, rng, rel=0.12)
                prev_end, prev_m = t0 + ln * self.q, m
            self._frm = None
            return
        super().render_part(buf, part, chords, root, scale, bars, rng, crescendo)

    def render_perc(self, buf, pattern: dict, bars: int, rng, crescendo=False, root=None) -> None:
        """pattern = {daego, kung, deok: 칸 문자열 (12/8 = 8분 12칸, 4/4 = 16칸), jing: 몇 마디마다, clash: 마디 첫 칸 '챙'}.
        마지막 마디는 뒷반 장구 몰아치기."""
        for b in range(bars):
            last = b == bars - 1
            for k in ("daego", "kung", "deok"):
                pp = pattern.get(k, "")
                if not pp:
                    continue
                cell = self.bar / len(pp)
                for i, ch in enumerate(pp):
                    if ch not in "xX":
                        continue
                    vel = 1.0 if (ch == "X" or i == 0) else 0.8
                    if k == "deok" and len(pp) == 16 and pp.count("x") == 16:   # 휘모리 몰아치기: 박마다만 세게
                        vel *= 0.85 if i % 4 == 0 else 0.5
                    fn, ln = DRUM[k]
                    self._place(buf, fn(int(ln * RATE), vel, rng), b * self.bar + i * cell, vel * KIT_GAIN[k],
                                KIT_PAN.get(k, 0.0) + rng.uniform(-0.04, 0.04))
            je = pattern.get("jing", 0)
            if je and b % je == 0:
                self._place(buf, d_jing(int(4.0 * RATE), 1.0, rng), b * self.bar, KIT_GAIN["jing"], KIT_PAN["jing"])
            if pattern.get("clash"):
                self._place(buf, s_chaeng(int(0.5 * RATE), rng, k=rng.uniform(0.95, 1.05)), b * self.bar, KIT_GAIN["clash"], KIT_PAN["clash"])
            if last:   # 장구 몰아치기 (뒷반 덕 16분 + 끝 쿵)
                n16 = self.steps // 2
                for j in range(n16):
                    t0 = b * self.bar + (self.steps - n16 + j) * self.step
                    self._place(buf, d_deok(int(0.25 * RATE), 1.0, rng), t0, KIT_GAIN["deok"] * (0.6 + 0.6 * j / n16), 0.25)
                self._place(buf, d_kung(int(0.5 * RATE), 1.0, rng), b * self.bar + (self.steps - 1) * self.step, KIT_GAIN["kung"] * 1.2, -0.2)

    # ── 층 만들기 ──
    def stems(self) -> dict:
        sp = self.spec
        rv = sp.get("reverb", [0.15, 1.0])
        prv = [rv[0] * 0.7, rv[1] * 0.8]
        out = {}
        phases = sp["phases"]
        for i, ph in enumerate(phases):
            self.set_tempo(i)
            n16 = self.loop_len(self.bars)
            root, scale = self.phase_info(i)
            rng = np.random.default_rng(self.seed + i * 13)
            chords = ph["chords"]
            pre = f"{i + 1}_"
            out[pre + "base"] = self.wrap(self.render_layer(ph.get("base"), chords, root, scale, self.bars, rng, rv), n16)
            perc = ph["perc"]
            out[pre + "perc"] = self.wrap(self.render_layer(None, chords, root, scale, self.bars, rng, prv, perc=perc["pattern"]), n16)
            crisis = dict(perc["pattern"], **perc.get("crisis", {}))
            tr = [dict(inst="haegeum_trem", style="trem_hae", gain=0.3, oct=1, pan=0.35)]
            out[pre + "perc_crisis"] = self.wrap(self.render_layer(tr, chords, root, scale, self.bars, rng, prv, perc=crisis), n16)
            lead = ph.get("lead") or []
            lrng = np.random.default_rng(self.seed + i * 13 + 1)
            out[pre + "lead"] = self.wrap(self.render_layer(lead, chords, root, scale, self.bars, lrng, rv), n16)
            main = lead[:1]   # 지침: 대금이 한 옥타브 위에서 길게 (주선율 첫 파트의 음으로)
            up = [dict(p, oct=p.get("oct", 0) + 1, inst="daegeum_t") for p in main]
            out[pre + "lead_oct"] = self.wrap(self.render_layer(up, chords, root, scale, self.bars, np.random.default_rng(self.seed + i * 13 + 1), rv), n16)
            out[pre + "choir"] = self.wrap(self.render_layer(ph.get("choir"), chords, root, scale, self.bars, rng, rv), n16)
            if i + 1 < len(phases):
                self.set_tempo(i + 1)   # 라이저 = 다음 페이즈 빠르기로 몰아쳐 들어감
                out[pre + "riser"] = self.riser(i, rng, rv)
        self.set_tempo(0)
        out["intro_mix"] = self.intro(rv)
        out["fail"] = self.fail_sound(rv)
        return out

    def intro(self, rv) -> np.ndarray:
        """반 마디: 바람 → 챔질 순간 칼 뽑는 '스릉—' (1페이즈 첫 박의 대고 '둥!' + 징은 1페이즈 타악 층이 친다)."""
        rng = np.random.default_rng(self.seed + 999)
        L = self.bar * 0.5
        buf = self._buf(L)
        self.sfx(buf, "wind", 0.0, L + 0.3, 0.6, -0.2, rng)
        self.sfx(buf, "seureung", 0.0, min(0.85, L * 0.75), 1.8, 0.15, rng)
        buf = self.hall(buf, rv[0], rv[1], rng)
        n = int(round(L * RATE))
        out = buf[: n + int(RATE * 0.02)].copy()
        out[n:] *= np.linspace(1, 0, len(out) - n)[:, None]
        return out[:n]

    def riser(self, i: int, rng, rv) -> np.ndarray:
        """페이즈 전환 1마디 (다음 페이즈 빠르기): 징 한 번 + 장구 몰아치기(덕 16분 점점 세게, 박마다 쿵) + 끝 대고."""
        n = self.loop_len(1)
        buf = self._buf(self.bar)
        self._place(buf, d_jing(int(4.0 * RATE), 1.0, rng), 0.0, KIT_GAIN["jing"] * 1.2, KIT_PAN["jing"])
        for s in range(self.steps):
            u = s / max(1, self.steps - 1)
            self._place(buf, d_deok(int(0.25 * RATE), 1.0, rng), s * self.step, KIT_GAIN["deok"] * (0.5 + 0.8 * u), 0.25)
            if s % 4 == 0:
                self._place(buf, d_kung(int(0.5 * RATE), 1.0, rng), s * self.step, KIT_GAIN["kung"] * (0.7 + 0.5 * u), -0.2)
        self._place(buf, d_daego(int(1.4 * RATE), 1.0, rng), (self.steps - 1) * self.step, KIT_GAIN["daego"] * 0.8, 0.0)
        self.sfx(buf, "syuk", self.bar * 0.55, self.bar * 0.4, 0.3, -0.3, rng)
        out = self.hall(buf, rv[0], rv[1], rng)[:n]
        out[-int(RATE * 0.02):] *= np.linspace(1, 0, int(RATE * 0.02))[:, None]
        return out

    def fail_sound(self, rv) -> np.ndarray:
        """실패: 칼이 부러지는 '쨍' → 징 여운 1.5초."""
        rng = np.random.default_rng(self.seed + 777)
        buf = self._buf(2.0)
        self.sfx(buf, "jjaeng", 0.0, 0.9, 1.0, 0.1, rng)
        jing = d_jing(int(1.6 * RATE), 1.0, rng) * np.linspace(1, 0, int(1.6 * RATE)) ** 1.5
        self._place(buf, jing, 0.12, KIT_GAIN["jing"] * 1.4, 0.0)
        buf = self.hall(buf, rv[0], rv[1], rng)
        n = int(2.0 * RATE)
        out = buf[:n].copy()
        out[-int(RATE * 0.05):] *= np.linspace(1, 0, int(RATE * 0.05))[:, None]
        return out
