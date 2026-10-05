"""노르딕 포크 서사 곡 (BOSS_BGM.md 엘드라시온 L11, DESIGN.md 43-26) — 극광어 보레알리스 전용 L11-NORDIC. 스펙에 "nordic": true.

boss_celtic.CelticSong 을 물려받아 6/8 연주법(드론 · 반복 음형 · 성가 · 프레임 드럼)은 그대로, 악기만 북유럽으로.
B단조 · 6/8 점4분 = 96 (엔진 144, 마디 1.25초 · 12칸), 잔향 1.2초.
  악기  하르당에르 피들 (활 줄 넷 아래 공명 줄 다섯 — B·D·F#·B·D 가 연주하는 음의 배음에 맞으면 같이 울림, 맑고 넓게) ·
        니켈하르파 (건반으로 누르는 활 현 — 콧소리 + 건반 '톡' + 공명 줄 열둘이 반짝임) · 첼레스타 (얼음 같은 분산화음) ·
        낮게 읊조리는 남성 합창 (boss_organ.chant — 점4분마다 모음을 바꾸며 리듬으로) · 프레임 드럼 (boss_celtic 보드란을 더 낮게) ·
        큰북 · 낮은 현 지속음
  1페이즈  하르당에르 피들 주선율 + 첼레스타 8분 분산화음 + 낮은 지속음 + 프레임 드럼
  2페이즈(얼음 아래 — 어둠 · 가짜 지침)  니켈하르파 주선율 + 프레임 드럼 강하게 + 피들 반복 음형, 중음역 −5dB 더
  3페이즈  읊조리는 남성 합창 크게 + 큰북 + 하르당에르 · 니켈하르파가 같이 주선율 + 첼레스타
  위기  프레임 드럼 연타 + 큰북 / 지침: 합창이 주선율을 한 옥타브 위에서
  전환  프레임 드럼 굴림 + 니켈하르파 상승 (2→3 은 큰북까지)
  실패  하르당에르 활이 줄을 긁어 내리며 공명 줄만 길게 남아 사라짐 + 얼음 갈라지는 소리 + 프레임 드럼
  인트로 1마디: 프레임 드럼 굴림 + 하르당에르 개방현 지속음이 부풀고 + 첼레스타 반짝
"""
import numpy as np

from src.audio import boss_celtic, boss_organ
from src.audio import boss_synth as bs
from src.audio.boss_celtic import CelticSong
from src.audio.boss_muhyeop import _env, _harm, _norm, _ph
from src.audio.boss_synth import RATE, _bw_filter, _t, chord_midis, degree_to_midi, hz, noise, peaking_eq

SYMP_HARD = [hz(m) for m in (59, 62, 66, 71, 74)]                       # 하르당에르 공명 줄 B3 D4 F#4 B4 D5
SYMP_NYCK = [hz(m) for m in (59, 61, 62, 64, 66, 67, 69, 71, 73, 74, 76, 78)]   # 니켈하르파 공명 줄 열둘 (B단조 음계)


# ───────────────────────── 악기 ─────────────────────────

def _sympathetic(f, n, strings, amp=0.12):
    """공명 줄: 연주하는 음(f)의 배음과 맞는 줄일수록 크게, 천천히 부풀었다가 길게 울림."""
    t = _t(n)
    x = np.zeros(n)
    for fs in strings:
        w = 0.12
        for k in range(1, 7):
            if abs(f * k / fs - 1) < 0.012 or abs(fs * k / f - 1) < 0.012:
                w = 1.0
                break
        x += w * np.sin(2 * np.pi * fs * t) * (1 - np.exp(-t / 0.08)) * np.exp(-t / 1.4)
    return x * amp


def i_hardanger(f, n, rng, dur=0.0, q=0.42, **k):
    """하르당에르 피들: 켈틱 피들 소리(boss_celtic) + 공명 줄 다섯이 같이 울림."""
    x = boss_celtic.i_fiddle(f, n, rng, dur=dur, q=q)
    x = x + _sympathetic(f, n, SYMP_HARD, 0.18)
    return _norm(x) * _env(n, 0.015, 0.0, 0.05)


def i_nyckel(f, n, rng, dur=0.0, q=0.42, **k):
    """니켈하르파: 건반으로 누르는 활 현 — 콧소리(홀수 배음 · 700Hz 울림) + 건반 '톡' + 공명 줄 열둘의 반짝임."""
    t = _t(n)
    semi = np.zeros(n)
    if dur >= 0.9 * q:
        semi += 0.12 * np.sin(2 * np.pi * 5.0 * np.maximum(0, t - 0.2)) * np.clip((t - 0.2) / 0.2, 0, 1)
    f_t = f * 2 ** (semi / 12)
    x = _harm(f_t, [(1.0 if kk % 2 else 0.6) / kk ** 0.85 for kk in range(1, 34)], top=7000)
    x = peaking_eq(peaking_eq(x, 700.0, 6.0, 1.2), 2400.0, -4.0, 1.0)
    x = np.tanh(1.4 * _norm(_bw_filter(x, "lp", 5500)))
    m = min(n, int(0.012 * RATE))
    x[:m] += _bw_filter(noise(m, rng), "bp", (1200, 5000))[:m] * np.exp(-np.arange(m) / (m / 5)) * 0.5   # 건반 '톡'
    x = x + _bw_filter(noise(n, rng), "bp", (3000, 8000)) * 0.03 + _sympathetic(f, n, SYMP_NYCK, 0.22)
    return _norm(x) * _env(n, 0.02, 0.0, 0.05)


def i_celesta(f, n, rng, **k):
    return bs.i_celesta(f, n, 1.0, rng)


def i_ndrone(f, n, rng, **k):
    """낮은 현 지속음 (활로 길게): 현악 합주 소리를 어둡게."""
    x = _bw_filter(bs.i_strings(f, n, 1.0, rng), "lp", 900)
    return _norm(x) * _env(n, 0.4, 0.0, 0.3)


def i_chant(f, n, rng, vowel="o", **k):
    return boss_organ.chant(f, n, rng, vowel=vowel, voices=6)


def d_frame(n, vel, rng):              # 프레임 드럼: 보드란을 더 낮고 길게 (북유럽 손북)
    return boss_celtic.d_bodhran(n, vel, rng, press=-0.35)


def d_ice(n, rng):                     # 얼음 갈라지는 소리: 높은 잡음 딱딱 + 낮은 '쩍'
    t = _t(n)
    x = np.zeros(n)
    for _ in range(9):
        s = int(rng.uniform(0, 0.25) * RATE)
        x[s:] += _bw_filter(noise(n - s, rng), "bp", (2500, 9000)) * np.exp(-_t(n - s) * 70) * rng.uniform(0.4, 1.0)
    x += np.sin(_ph(np.full(n, 70.0) * (1 + np.exp(-t * 30)))) * np.exp(-t * 6) * 0.6
    return _norm(x)


INST = {"fiddle": i_hardanger, "hardanger": i_hardanger, "nyckel": i_nyckel, "celesta": i_celesta, "drone": i_ndrone,
        "chant": i_chant, "bass": boss_celtic.i_bassv}
KIT = {"frame": (d_frame, 0.6, 0.8, 0.05), "rim": (boss_celtic.d_rim, 0.15, 0.25, 0.2), "big": (bs.d_bigdrum, 1.4, 0.8, 0.0)}


# ───────────────────────── 곡 ─────────────────────────

class NordicSong(CelticSong):
    def note(self, buf, inst: str, midi: float, start: float, dur: float, gain=1.0, p=0.0, rng=None, rel=0.3) -> None:
        n = int((dur + rel) * RATE)
        if n <= 0:
            return
        vowel = getattr(self, "_vowel", "o")
        key = (inst, round(midi, 2), n // 64, vowel if inst == "chant" else "")
        mono = self._cache.get(key)
        if mono is None:
            mono = INST[inst](hz(midi), n, rng, dur=dur, q=self.q, vowel=vowel).astype(np.float32)
            if len(self._cache) < 3000:
                self._cache[key] = mono
        self._place(buf, mono, start, gain, p)

    def drum(self, buf, kind: str, start: float, vel: float, rng) -> None:
        fn, ln, g, pan = KIT[kind]
        self._place(buf, fn(int(ln * RATE), vel, rng), start, vel * g, pan + rng.uniform(-0.04, 0.04))

    def render_part(self, buf, part: dict, chords: list, root: int, scale: str, bars: int, rng, crescendo=False) -> None:
        st = part.get("style")
        g, o, p = part.get("gain", 1.0), 12 * part.get("oct", 0), part.get("pan", 0.0)
        bar, step, S = self.bar, self.step, self.steps
        if st == "ice_arp":     # 첼레스타 8분 분산화음 (위로 · 아래로 번갈아)
            for b in range(bars):
                cm = chord_midis(chords[b], root, scale)
                tones = [m + o for m in cm] + [cm[0] + 12 + o, cm[1] + 12 + o]
                seq = tones if b % 2 == 0 else tones[::-1]
                for k, i in enumerate(range(0, S, part.get("every", 2))):
                    self.note(buf, "celesta", seq[k % len(seq)], b * bar + i * step, step * 3, g * (1.0 if k % 3 == 0 else 0.75),
                              p + (0.35 if k % 2 else -0.35), rng, rel=0.4)
            return
        if st == "low_drone":   # 낮은 현 지속음: 화음 근음, 바뀔 때까지
            b = 0
            while b < bars:
                e = b + 1
                while e < bars and chords[e] == chords[b]:
                    e += 1
                r = chord_midis(chords[b], root, scale)[0] - 24 + o
                self.note(buf, "drone", r, b * bar, (e - b) * bar * 0.98, g, p, rng, rel=0.3)
                self.note(buf, "drone", r + 7, b * bar, (e - b) * bar * 0.98, g * 0.5, p, rng, rel=0.3)
                b = e
            return
        if st == "chant_rhythm":   # 낮게 읊조리는 남성 합창: 점4분마다 화음 근음 · 5도를 모음 바꿔 가며 (리듬으로)
            vowels = ("o", "a", "e", "o")
            for b in range(bars):
                cm = chord_midis(chords[b], root, scale)
                for k in range(2):
                    self._vowel = vowels[(b * 2 + k) % 4]
                    for j, m in enumerate((cm[0] - 12, cm[0] - 5)):
                        self.note(buf, "chant", m + o, b * bar + k * bar / 2, bar / 2 * 0.9, g * (1.0 if k == 0 else 0.8) * (1.0 if j == 0 else 0.7),
                                  p + (j - 0.5) * 0.5, rng, rel=0.15)
            self._vowel = "o"
            return
        super().render_part(buf, part, chords, root, scale, bars, rng, crescendo)

    def stems(self) -> dict:
        out = super().stems()
        # 지침은 '합창이 한 옥타브 위' 로 다시 (CelticSong 은 피들)
        sp = self.spec
        rv = sp.get("reverb", [0.18, 1.2])
        for i, ph in enumerate(sp["phases"]):
            self.set_tempo(i)
            n16 = self.loop_len(self.bars)
            root, scale = self.phase_info(i)
            lead = ph.get("lead") or []
            mel = sorted({(b, at): [b, at, d, ln] for pt in lead for b, at, d, ln in pt["notes"]}.values(), key=lambda x: (x[0], x[1]))
            up = [dict(pt, gain=pt.get("gain", 1.0) * 0.7) for pt in lead] + \
                 [dict(inst="chant", style="melody", gain=ph.get("tired_choir", 0.9), oct=1, notes=mel)]
            x = self.wrap(self.render_layer(up, ph["chords"], root, scale, self.bars, np.random.default_rng(self.seed + i * 13 + 1), rv), n16)
            dark = ph.get("mid_cut_extra", 0.0)
            out[f"{i + 1}_lead_oct"] = peaking_eq(x, 1732.0, dark, 0.9) if dark else x
            if dark:   # 어둠: 이 페이즈 모든 층 중음역 더 비우기 (태고 방식)
                for lay in ("base", "perc", "perc_crisis", "lead", "choir"):
                    out[f"{i + 1}_{lay}"] = peaking_eq(out[f"{i + 1}_{lay}"], 1732.0, dark, 0.9)
        self.set_tempo(0)
        return out

    def intro(self, rv) -> np.ndarray:
        """1마디: 프레임 드럼 굴림(점점 세게) + 하르당에르 개방현(B · F#) 지속음이 부풀고 + 첼레스타 반짝."""
        root, scale = self.phase_info(0)
        rng = np.random.default_rng(self.seed + 999)
        buf = self._buf(self.bar)
        S = self.steps
        for s in range(S):
            self.drum(buf, "frame", s * self.step, 0.35 + 0.65 * s / S, rng)
        for m in (root - 12, root - 5):
            self.note(buf, "hardanger", m, 0.0, self.bar, 0.3, 0.0, rng, rel=0.05)
        for j, m in enumerate(chord_midis(1, root + 24, scale)):
            self.note(buf, "celesta", m, self.bar * (0.5 + 0.12 * j), self.bar * 0.4, 0.3, 0.3 * (j - 1), rng, rel=0.3)
        buf = self.hall(buf, rv[0], rv[1], rng)
        n = self.loop_len(1)
        out = buf[: n + int(RATE * 0.02)].copy()
        out[n:] *= np.linspace(1, 0, len(out) - n)[:, None]
        return out[:n]

    def riser(self, i: int, rng, rv) -> np.ndarray:
        """전환 1마디: 프레임 드럼 굴림 + 니켈하르파 상승 (2→3 은 큰북까지)."""
        root, scale = self.phase_info(i + 1)
        n = self.loop_len(1)
        buf = self._buf(self.bar)
        S = self.steps
        for s in range(S):
            u = s / max(1, S - 1)
            self.drum(buf, "frame", s * self.step, 0.45 + 0.55 * u, rng)
            m = degree_to_midi(1 + s * 8 // S, root - 12, scale)
            self.note(buf, "nyckel", m, s * self.step, self.step * 0.95, 0.25 + 0.2 * u, 0.25 * ((-1) ** s), rng, rel=0.04)
        if i == 1:
            for s in (0, 6, 9):
                self.drum(buf, "big", s * self.step, 0.9, rng)
        out = self.hall(buf, rv[0], rv[1], rng)[:n]
        out[-int(RATE * 0.02):] *= np.linspace(1, 0, int(RATE * 0.02))[:, None]
        return out

    def fail_sound(self, rv) -> np.ndarray:
        """실패: 하르당에르 활이 줄을 긁어 내리고 공명 줄만 길게 남아 사라짐 + 얼음 갈라짐 + 프레임 드럼."""
        root, scale = self.phase_info(0)
        rng = np.random.default_rng(self.seed + 777)
        L = 2.4
        n = int(L * RATE)
        buf = self._buf(L)
        self._place(buf, d_ice(int(1.0 * RATE), rng), 0.0, 0.4, 0.15)
        self.drum(buf, "frame", 0.0, 1.0, rng)
        for j in range(6):
            m = degree_to_midi(8 - j, root, scale)
            self.note(buf, "hardanger", m, 0.05 + j * 0.09, 0.18, 0.35 * (1 - j / 7), -0.1, rng, rel=0.05)
        t = _t(n)
        res = _sympathetic(hz(root - 12), n, SYMP_HARD, 1.0) * np.exp(-t / 0.9)
        self._place(buf, _norm(res), 0.55, 0.25, 0.0)
        buf = self.hall(buf, rv[0], rv[1], rng)
        out = buf[:n].copy()
        out[-int(RATE * 0.05):] *= np.linspace(1, 0, int(RATE * 0.05))[:, None]
        return out
