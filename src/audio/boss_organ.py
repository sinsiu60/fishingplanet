"""심해 대성당 전투 곡 (SHARMION_THEMES.md 5장, DESIGN.md 43-18) — 실러캔스 '태고' 전용 L05-ORGAN. 스펙에 "organ": true.

boss_synth.Song 을 물려받아 층 구조·반복 이음새·마스터링은 그대로, 악기와 연주만 심해 대성당으로 (boss_synth.py 는 그대로).
B♭단조 · 136 · 4/4, 잔향 2.0초 이하 (16분 음형이 뭉개지지 않는 선).
  악기  파이프 오르간(페달 16' 저음 지속 + 손건반 8'·4'·2⅔'·2' + 혼합 관, '전체 음전'이면 리드 관까지 · 관이 울리기 시작할 때 '츄' 소리) ·
        낮은 남성 성가('오—' · '아—' · '에—' 뜻 없는 음절, 여러 사람, 속삭임 판) · 큰 종 · 작은 종 · 심장 같은 낮은 북 · 깊은 물 울림
  바탕  오르간 페달 저음 지속 + 손건반 16분 쉼 없는 음형 (화음음 위아래로)
  타악  낮은 북 x...x...x..x.... (심장 박동) · 큰 종 4마디마다
  주선율 1페이즈 오르간 높은 음 / 2페이즈 오르간 낮게 + 성가 속삭임 / 3페이즈 남성 성가가 주인의 동기, 오르간 전체 음전
  합창 자리 남성 성가 (2페이즈는 속삭임)
  2페이즈(어둠) 음악 중음역(1~3kHz)을 이 페이즈만 −5dB 더 — 줄과 소리로 읽어야 하는 어둠 속에서 신호 소리가 잘 들리게
  위기  심장 북 2배 + 오르간 낮은 음 강세 (위기 타악 층에) / 지침: 성가가 한 옥타브 위 (옥타브 주선율 층)
  전환  오르간 빠른 하강 음형 1마디 + 종 / 실패: 오르간 화음이 길게 무너지듯 낮아지며 사라짐
  인트로 깊은 물 울림 → 큰 종 '댕' → 오르간 화음 '웅—' (1마디)
"""
import numpy as np

from src.audio.boss_muhyeop import _env, _harm, _norm, _ph, _vib
from src.audio.boss_synth import RATE, Song, _bw_filter, _t, chord_midis, degree_to_midi, hz, noise, peaking_eq

VOWEL = {"o": ((450, 1.0, 90), (800, 0.55, 110), (2830, 0.1, 200)),
         "a": ((720, 1.0, 110), (1150, 0.6, 140), (2600, 0.12, 220)),
         "e": ((480, 1.0, 90), (1750, 0.5, 160), (2600, 0.15, 220))}


# ───────────────────────── 악기 ─────────────────────────

def pipe(f, n, rng, full=False, chiff=True):
    """오르간 관 한 묶음: 8' + 4' + 2⅔' + 2' + 혼합(1⅓') (full = 리드 관 8' 더). 시작에 '츄', 소리는 평평하게 지속."""
    t = _t(n)
    x = np.zeros(n)
    for mult, a in ((1, 1.0), (2, 0.55), (3, 0.32), (4, 0.3), (6, 0.15), (8, 0.1)):
        if f * mult > 9000:
            continue
        ph = 2 * np.pi * f * mult * t + rng.uniform(0, 6)
        x += a * (np.sin(ph) + 0.12 * np.sin(2 * ph))   # 관 소리: 맑은 사인 + 약한 2배음
    if full:   # 리드 관 (트럼펫 음전): 톱니 배음
        x += 0.45 * _harm(np.full(n, f), [1 / k for k in range(1, 25)], top=6000)
    if chiff:
        m = min(n, int(0.04 * RATE))
        x[:m] += _bw_filter(noise(m, rng), "bp", (min(8000, f * 3), min(10000, f * 8))) * np.exp(-np.arange(m) / (m / 4)) * 0.5
    return _norm(x) * _env(n, 0.025, 0.0, 0.07)


def i_organ(f, n, rng, dur=0.0, **k):
    return pipe(f, n, rng)


def i_organ_full(f, n, rng, dur=0.0, **k):
    return pipe(f, n, rng, full=True)


def i_pedal(f, n, rng, dur=0.0, **k):
    """페달 16' + 8': 아주 낮고 둥근 바닥."""
    t = _t(n)
    x = np.sin(_ph(np.full(n, f))) + 0.5 * np.sin(_ph(np.full(n, 2 * f))) + 0.15 * np.sin(_ph(np.full(n, 3 * f)))
    return _norm(x) * _env(n, 0.08, 0.0, 0.15) * (1 + 0.02 * np.sin(2 * np.pi * 0.7 * t))


def chant(f, n, rng, vowel="o", whisper=False, voices=5):
    """낮은 남성 성가: 여러 사람(조금씩 어긋난 음·떨림) + 모음 울림. whisper = 숨소리만 (속삭임)."""
    t = _t(n)
    src = np.zeros(n)
    if whisper:
        src = noise(n, rng)
    else:
        for v in range(voices):
            det = 1 + rng.uniform(-0.006, 0.006)
            f_t = f * det * 2 ** (_vib(t, 0.3 + 0.1 * v, 0.18, 4.8 + 0.4 * v, 0.4) / 12)
            src += _harm(f_t, [1 / k ** 0.8 for k in range(1, 30)], top=5000)
        src += noise(n, rng) * 0.15
    x = sum(a * _bw_filter(src, "bp", (fc - bw, fc + bw)) for fc, a, bw in VOWEL[vowel])
    x += 0.2 * _bw_filter(src, "lp", 300)
    return _norm(x) * _env(n, 0.12 if not whisper else 0.2, 0.0, 0.18)


def i_chant(f, n, rng, dur=0.0, vowel="o", **k):
    return chant(f, n, rng, vowel=vowel)


def i_whisper(f, n, rng, dur=0.0, vowel="o", **k):
    return chant(f, n, rng, vowel=vowel, whisper=True)


def d_bell(n, vel, rng, f=98.0):     # 큰 종 '댕': 종의 배음(험·기본·단3도·5도·옥타브·…) 길게
    t = _t(n)
    x = sum(a * np.sin(2 * np.pi * f * r * t + rng.uniform(0, 6)) * np.exp(-t * d) for r, a, d in
            ((0.5, 0.8, 0.5), (1.0, 1.0, 0.7), (1.19, 0.6, 0.9), (1.5, 0.45, 1.1), (2.0, 0.5, 1.2), (2.52, 0.25, 1.6),
             (3.01, 0.2, 2.0), (4.02, 0.12, 2.6)))
    m = min(n, int(0.01 * RATE))
    x[:m] += _bw_filter(noise(m, rng), "bp", (500, 3000))[:m] * 0.6
    return _norm(x) * np.minimum(1, t / 0.003)


def d_smallbell(n, vel, rng):         # 작은 종 '딩' (맑게)
    return d_bell(n, vel, rng, f=880.0)


def d_heart(n, vel, rng):             # 심장 같은 낮은 북 (둥 — 부드럽고 깊게)
    t = _t(n)
    f = 44 + 26 * np.exp(-t * 18)
    x = np.sin(_ph(f)) * np.exp(-t * 7) + _bw_filter(noise(n, rng), "lp", 200) * np.exp(-t * 35) * 0.4
    return np.tanh(1.4 * x) * np.minimum(1, t / 0.004)


def s_deep(n, rng):                   # 깊은 물 울림
    t = _t(n)
    x = _bw_filter(noise(n, rng), "lp", 160) * 2.0 + 0.3 * np.sin(_ph(30 + 6 * np.sin(2 * np.pi * 0.3 * t)))
    return _norm(x) * np.minimum(1, t / 0.4)


INST = {"organ": i_organ, "organ_full": i_organ_full, "pedal": i_pedal, "chant": i_chant, "whisper": i_whisper}
KIT_GAIN = {"heart": 0.95, "bell": 0.38, "smallbell": 0.3}


# ───────────────────────── 곡 ─────────────────────────

class OrganSong(Song):
    def note(self, buf, inst: str, midi: float, start: float, dur: float, gain=1.0, p=0.0, rng=None, rel=0.3) -> None:
        n = int((dur + rel) * RATE)
        if n <= 0:
            return
        vowel = getattr(self, "_vowel", "o")
        key = (inst, round(midi, 2), n // 64, vowel)
        mono = self._cache.get(key)
        if mono is None:
            mono = INST[inst](hz(midi), n, rng, dur=dur, vowel=vowel).astype(np.float32)
            if len(self._cache) < 3000:
                self._cache[key] = mono
        self._place(buf, mono, start, gain, p)

    def render_part(self, buf, part: dict, chords: list, root: int, scale: str, bars: int, rng, crescendo=False) -> None:
        st = part.get("style")
        g, o, p = part.get("gain", 1.0), 12 * part.get("oct", 0), part.get("pan", 0.0)
        bar, step = self.bar, self.step
        if st == "pedal":       # 페달 저음: 화음이 바뀔 때까지 길게
            b = 0
            while b < bars:
                e = b + 1
                while e < bars and chords[e] == chords[b]:
                    e += 1
                r = chord_midis(chords[b], root, scale)[0] - 24 + o
                self.note(buf, "pedal", r, b * bar, (e - b) * bar * 0.98, g, p, rng, rel=0.2)
                b = e
            return
        if st == "toccata":     # 손건반 16분 쉼 없는 음형: 화음음을 위아래로 (짧게 끊어 또렷하게)
            inst = part["inst"]
            for b in range(bars):
                cm = chord_midis(chords[b], root, scale)
                tones = [m + o for m in cm] + [cm[0] + 12 + o]
                seq = tones + tones[-2:0:-1]
                for i in range(self.steps):
                    m = seq[i % len(seq)]
                    acc = 1.0 if i % 4 == 0 else 0.75
                    self.note(buf, inst, m, b * bar + i * step, step * 0.7, g * acc, p + (0.2 if i % 2 else -0.2), rng, rel=0.05)
            return
        if st == "chant_hold":  # 성가 화음 길게 (모음 바꿔 가며 — 뜻 없는 음절)
            vowels = ("o", "a", "e", "o")
            inst = part["inst"]
            b = 0
            while b < bars:
                e = min(bars, b + 2)
                self._vowel = vowels[(b // 2) % len(vowels)]
                for j, m in enumerate(chord_midis(chords[b], root, scale)):
                    self.note(buf, inst, m - 12 + o, b * bar, (e - b) * bar * 0.96, g * (1.0 if j == 0 else 0.8), p + (j - 1) * 0.35, rng, rel=0.3)
                b = e
            self._vowel = "o"
            return
        if st == "melody":
            inst = part["inst"]
            vowels = ("o", "a", "e")
            for j, (b, at, deg, ln) in enumerate(part["notes"]):
                if b >= bars:
                    continue
                self._vowel = vowels[j % 3] if inst in ("chant", "whisper") else "o"
                m = degree_to_midi(deg, root, scale) + o
                self.note(buf, inst, m, b * bar + at * self.q, ln * self.q * 0.95, g, p, rng, rel=0.15)
            self._vowel = "o"
            return
        super().render_part(buf, part, chords, root, scale, bars, rng, crescendo)

    def render_perc(self, buf, pattern: dict, bars: int, rng, crescendo=False, root=None) -> None:
        """pattern = {heart: 16칸, bell: 몇 마디마다, accent: 위기 오르간 낮은 음 강세 칸}."""
        S, st = self.steps, self.step
        for b in range(bars):
            for i, ch in enumerate(pattern.get("heart", "")[:S]):
                if ch in "xX":
                    vel = 1.0 if i % 8 == 0 else 0.8
                    self._place(buf, d_heart(int(0.6 * RATE), vel, rng), b * self.bar + i * st, vel * KIT_GAIN["heart"], 0.0)
            be = pattern.get("bell", 0)
            if be and b % be == 0:
                self._place(buf, d_bell(int(4.0 * RATE), 1.0, rng, f=hz((root or 58) - 12)), b * self.bar, KIT_GAIN["bell"], 0.15)
            acc = pattern.get("accent", "")
            if acc and root is not None:
                for i, ch in enumerate(acc[:S]):
                    if ch in "xX":
                        self.note(buf, "organ_full", root - 24, b * self.bar + i * st, st * 1.6, 0.35, -0.1, rng, rel=0.05)

    # ── 층 만들기 ──
    def stems(self) -> dict:
        sp = self.spec
        rv = sp.get("reverb", [0.22, 1.9])
        rv = [rv[0], min(2.0, rv[1])]
        prv = [rv[0] * 0.7, rv[1] * 0.7]
        out = {}
        n16 = self.loop_len(self.bars)
        phases = sp["phases"]
        for i, ph in enumerate(phases):
            root, scale = self.phase_info(i)
            rng = np.random.default_rng(self.seed + i * 13)
            chords = ph["chords"]
            pre = f"{i + 1}_"
            dark = ph.get("mid_cut_extra", 0.0)

            def lay(parts, perc=None, r=rv, g=None):
                x = self.wrap(self.render_layer(parts, chords, root, scale, self.bars, g if g is not None else rng, r, perc=perc), n16)
                return peaking_eq(x, 1732.0, dark, 0.9) if dark else x   # 어둠: 이 페이즈만 중음역 더 비우기
            out[pre + "base"] = lay(ph.get("base"))
            perc = ph["perc"]
            out[pre + "perc"] = lay(None, perc["pattern"], prv)
            crisis = dict(perc["pattern"], **perc.get("crisis", {}))
            out[pre + "perc_crisis"] = lay(None, crisis, prv)
            lead = ph.get("lead") or []
            out[pre + "lead"] = lay(lead, g=np.random.default_rng(self.seed + i * 13 + 1))
            main = [p for p in lead if p.get("inst") in ("chant", "whisper")][:1] or lead[:1]
            up = [dict(p, oct=p.get("oct", 0) + 1, inst="chant") for p in main]   # 지침: 성가가 한 옥타브 위
            out[pre + "lead_oct"] = lay(up, g=np.random.default_rng(self.seed + i * 13 + 1))
            out[pre + "choir"] = lay(ph.get("choir"))
            if i + 1 < len(phases):
                out[pre + "riser"] = self.riser(i, rng, rv)
        out["intro_mix"] = self.intro(rv)
        out["fail"] = self.fail_sound(rv)
        return out

    def intro(self, rv) -> np.ndarray:
        """1마디: 깊은 물 울림 → 큰 종 '댕' → 오르간 화음 '웅—' (1페이즈 첫 박으로 이어짐)."""
        root, scale = self.phase_info(0)
        rng = np.random.default_rng(self.seed + 999)
        buf = self._buf(self.bar)
        self._place(buf, s_deep(int((self.bar + 0.5) * RATE), rng), 0.0, 0.7, 0.0)
        self._place(buf, d_bell(int(4.0 * RATE), 1.0, rng, f=hz(root - 12)), 0.05, 0.6, 0.15)
        at = self.bar * 0.4
        for j, m in enumerate(chord_midis(1, root, scale)):
            self.note(buf, "organ_full", m, at, self.bar - at, 0.32, (j - 1) * 0.3, rng, rel=0.1)
        self.note(buf, "pedal", root - 24, at, self.bar - at, 0.5, 0.0, rng, rel=0.1)
        buf = self.hall(buf, rv[0], rv[1], rng)
        n = self.loop_len(1)
        out = buf[: n + int(RATE * 0.02)].copy()
        out[n:] *= np.linspace(1, 0, len(out) - n)[:, None]
        return out[:n]

    def riser(self, i: int, rng, rv) -> np.ndarray:
        """페이즈 전환 1마디: 오르간 빠른 하강 음형(16분, 화성단음계로 두 옥타브) + 첫 박 종."""
        root, scale = self.phase_info(i + 1)
        n = self.loop_len(1)
        buf = self._buf(self.bar)
        self._place(buf, d_bell(int(4.0 * RATE), 1.0, rng, f=hz(root - 12)), 0.0, KIT_GAIN["bell"] * 1.3, 0.15)
        S = self.steps
        for s in range(S):
            deg = 15 - s
            m = degree_to_midi(deg, root, "harmonic")
            self.note(buf, "organ_full", m, s * self.step, self.step * 0.8, 0.3 + 0.2 * s / S, 0.3 * ((-1) ** s), rng, rel=0.05)
        self.note(buf, "pedal", root - 24, 0.0, self.bar, 0.5, 0.0, rng, rel=0.1)
        out = self.hall(buf, rv[0], rv[1], rng)[:n]
        out[-int(RATE * 0.02):] *= np.linspace(1, 0, int(RATE * 0.02))[:, None]
        return out

    def fail_sound(self, rv) -> np.ndarray:
        """실패: 오르간 화음이 길게 무너지듯 낮아지며 (반음 넷 아래로 미끄러지며) 사라짐."""
        root, scale = self.phase_info(0)
        rng = np.random.default_rng(self.seed + 777)
        L = 2.4
        n = int(L * RATE)
        t = _t(n)
        drop = 2 ** (-4 * (t / t[-1]) ** 1.5 / 12)
        x = np.zeros(n)
        for m in chord_midis(1, root, scale) + [root - 12]:
            f_t = hz(m) * drop
            x += _harm(f_t, [1.0, 0.55, 0.3, 0.3, 0.15], top=6000)
        x = _norm(x) * (1 - t / t[-1]) ** 1.3 * np.minimum(1, t / 0.03)
        buf = self._buf(L)
        self._place(buf, x, 0.0, 0.8, 0.0)
        self._place(buf, d_heart(int(0.6 * RATE), 1.0, rng), 0.0, 0.9, 0.0)
        buf = self.hall(buf, rv[0], rv[1], rng)
        out = buf[:n].copy()
        out[-int(RATE * 0.05):] *= np.linspace(1, 0, int(RATE * 0.05))[:, None]
        return out
