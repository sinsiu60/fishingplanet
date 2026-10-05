"""켈틱 포크 배틀 곡 (BOSS_BGM.md 엘드라시온 L07, DESIGN.md 43-22) — 갈대왕 실바 전용 L07-CELTIC. 스펙에 "celtic": true.

boss_synth.Song 을 물려받아 층 구조·반복 이음새·마스터링은 그대로, 악기와 연주만 켈틱으로 (boss_synth.py 는 그대로).
D 도리안. 1·2페이즈 6/8 (점4분 = 100, 엔진 빠르기 150 · 한 마디 12칸), 3페이즈 4/4 · 150 (페이즈별 빠르기 — L04-MUHYEOP 방식).
  악기  틴 휘슬(높은 피리 — 숨 섞인 맑은 소리, 강박 음에 '컷' 꾸밈음) · 피들(활 긁힘 + 나무 몸통 울림, 반복 음형) ·
        백파이프(드론 D2·D3·A3 쉬지 않고 + 챈터 — 콧소리 리드) · 보드란(프레임 드럼 — 막대 양끝으로 치는 낮은 '둥'과 테두리 '탁',
        손으로 눌러 음높이 바꿈) · 부주키(두 줄씩 뜯는 현, 6/8 내림·올림 긁기) · 남성 합창 '오—' (boss_organ.chant)
  1페이즈  휘슬 주선율 + 보드란 질주 + 부주키 + 콘트라베이스
  2페이즈  피들 주선율(휘슬이 3도 위에서 받침) + 피들 반복 음형 + 백파이프 드론 합류
  3페이즈  4/4 로 바뀌며 큰북 + 남성 합창 '오—' + 백파이프 챈터·휘슬이 주인의 동기, 피들 16분
  위기  보드란 굴림(촘촘히) + 큰북 / 지침: 피들이 주선율을 한 옥타브 위에서
  전환  보드란 굴림 + 피들 상승 (2→3 은 4/4 빠르기로 큰북까지) / 실패: 백파이프 주머니에서 바람이 빠지며 드론이 처져 사라짐
  인트로 1마디: 보드란 굴림 → 휘슬이 아래에서 휙 올라옴 + 드론이 켜짐
"""
import numpy as np

from src.audio import boss_organ
from src.audio.boss_muhyeop import _env, _harm, _norm, _ph, _vib
from src.audio.boss_synth import (RATE, Song, _bw_filter, _t, chord_midis, d_bigdrum, degree_to_midi, hz, i_bass, noise,
                                  peaking_eq)


# ───────────────────────── 악기 ─────────────────────────

def i_whistle(f, n, rng, dur=0.0, q=0.4, cut=False, **k):
    """틴 휘슬: 거의 사인(맑게) + 약한 2·3배음 + 숨소리, 시작 '츄'. cut = 시작 25ms 동안 위 음을 스치는 꾸밈음 (켈틱 '컷')."""
    t = _t(n)
    semi = np.zeros(n)
    if cut:
        semi += 3.0 * (t < 0.025)
    if dur >= 0.9 * q:
        semi += _vib(t, 0.18, 0.18, 5.6, 0.2)
    f_t = f * 2 ** (semi / 12)
    x = _harm(f_t, [1.0, 0.16, 0.07, 0.03], top=9000)
    br = _bw_filter(noise(n, rng), "bp", (min(9000, f * 1.5), min(12000, f * 4))) * 0.07
    m = min(n, int(0.03 * RATE))
    x[:m] += _bw_filter(noise(m, rng), "bp", (2000, 7000))[:m] * np.exp(-np.arange(m) / (m / 4)) * 0.3
    return _norm(x + br) * _env(n, 0.012, 0.0, 0.03)


def i_whistle_cut(f, n, rng, **k):
    return i_whistle(f, n, rng, **dict(k, cut=True))


def i_fiddle(f, n, rng, dur=0.0, q=0.4, **k):
    """피들: 활로 긁는 톱니(배음 많이) + 나무 몸통 울림(280·450·1000·2800Hz) + 활 잡음, 긴 음엔 늦게 드는 떨림."""
    t = _t(n)
    semi = -0.25 * np.exp(-t / 0.02)
    if dur >= 0.9 * q:
        semi += _vib(t, 0.15, 0.2, 6.0, 0.15)
    f_t = f * 2 ** (semi / 12) * (1 + 0.0015 * np.sin(2 * np.pi * 1.7 * t))
    x = _harm(f_t, [1 / kk for kk in range(1, 40)], top=8000)
    for fc, g, qq in ((280.0, 6.0, 1.5), (450.0, 4.0, 1.4), (1000.0, 2.0, 1.2), (2800.0, 3.0, 1.5)):
        x = peaking_eq(x, fc, g, qq)
    bow = _bw_filter(noise(n, rng), "bp", (2500, 8000)) * (0.05 + 0.25 * np.exp(-t / 0.03))
    x = np.tanh(1.3 * _norm(_bw_filter(x, "lp", 6500))) + bow
    return _norm(x) * _env(n, 0.018, 0.0, 0.04)


def i_chanter(f, n, rng, dur=0.0, q=0.4, **k):
    """백파이프 챈터: 겹리드 콧소리 (홀수 배음 강조 + 1.2kHz 콧소리 울림), 음 사이 끊김 없이 크게."""
    t = _t(n)
    semi = np.zeros(n)
    if dur >= 0.9 * q:
        semi += 0.06 * np.sin(2 * np.pi * 6.5 * t)
    f_t = f * 2 ** (semi / 12)
    x = _harm(f_t, [(1.0 if kk % 2 else 0.55) / kk ** 0.7 for kk in range(1, 30)], top=7000)
    x = peaking_eq(_bw_filter(np.tanh(1.8 * _norm(x)), "hp", 250), 1200.0, 5.0, 1.0)
    return _norm(_bw_filter(x, "lp", 5000)) * _env(n, 0.008, 0.0, 0.03)


def i_drone(f, n, rng, **k):
    """백파이프 드론 한 줄: 리드가 떠는 톱니(낮게) — 쉬지 않는 '웅'."""
    t = _t(n)
    f_t = f * (1 + 0.0008 * np.sin(2 * np.pi * 0.4 * t + rng.uniform(0, 6)))
    x = _harm(f_t, [1 / kk ** 0.9 for kk in range(1, 30)], top=4000)
    x = _bw_filter(np.tanh(1.4 * _norm(x)), "lp", 2200)
    return _norm(x) * _env(n, 0.15, 0.0, 0.2)


def i_bouzouki(f, n, rng, **k):
    """부주키: 두 줄 한 쌍(같은 음 + 옥타브, 살짝 어긋남)을 뜯음 — 밝게 튀고 빨리 사라짐."""
    x = _harm(np.full(n, f), [1.0, 0.7, 0.5, 0.35, 0.25, 0.18, 0.12, 0.08, 0.05], decay=2.2)
    x += 0.5 * _harm(np.full(n, f * 2.004), [1.0, 0.5, 0.25, 0.12], decay=3.0)
    m = min(n, int(0.004 * RATE))
    x[:m] += _bw_filter(noise(m, rng), "bp", (2000, 6000)) * 0.5
    return _norm(_bw_filter(x, "lp", 5500)) * _env(n, 0.002, 2.5, 0.03)


def i_bassv(f, n, rng, **k):
    return i_bass(f, n, 1.0, rng)


def i_chant(f, n, rng, **k):
    return boss_organ.chant(f, n, rng, vowel="o", voices=6)


def d_bodhran(n, vel, rng, press=0.0):
    """보드란: 막대로 치는 낮은 '둥' (손으로 누르면 press 만큼 높아짐) + 가죽 '툭'."""
    t = _t(n)
    f = (68 + 40 * press) * (1 + 0.5 * np.exp(-t * 40))
    x = np.sin(_ph(f)) * np.exp(-t * 11) + 0.35 * np.sin(_ph(f * 1.6)) * np.exp(-t * 20)
    x += _bw_filter(noise(n, rng), "bp", (300, 2500)) * np.exp(-t * 60) * 0.45
    return np.tanh(1.4 * x) * np.minimum(1, t / 0.002)


def d_rim(n, vel, rng):                 # 보드란 테두리 '탁' (막대 끝)
    t = _t(n)
    x = _bw_filter(noise(n, rng), "bp", (1800, 6000)) * np.exp(-t * 90) + 0.4 * np.sin(_ph(np.full(n, 620.0))) * np.exp(-t * 70)
    return x


def d_big(n, vel, rng):
    return d_bigdrum(n, vel, rng)


INST = {"whistle": i_whistle, "whistle_cut": i_whistle_cut, "fiddle": i_fiddle, "chanter": i_chanter, "drone": i_drone,
        "bouzouki": i_bouzouki, "bass": i_bassv, "chant": i_chant}
# 타악: 이름 → (함수, 길이 초, 크기, 자리)
KIT = {"bod": (d_bodhran, 0.5, 0.75, 0.05), "bodp": (lambda n, v, r: d_bodhran(n, v, r, 1.0), 0.4, 0.6, 0.05),
       "rim": (d_rim, 0.15, 0.32, 0.2), "big": (d_big, 1.4, 0.85, 0.0)}


# ───────────────────────── 곡 ─────────────────────────

class CelticSong(Song):
    def set_tempo(self, i: int) -> None:
        """페이즈 i 의 빠르기·박자 (6/8 → 4/4)."""
        ph = self.spec["phases"][i]
        bpm = ph.get("bpm", self.spec["bpm"])
        num, den = ph.get("meter", self.spec.get("meter", [4, 4]))
        self.bpm, self.q = bpm, 60.0 / bpm
        self.bar = self.q * num * 4 / den
        self.steps = int(round(num * 16 / den))
        self.step = self.bar / self.steps
        self.six = (num, den) == (6, 8)

    def note(self, buf, inst: str, midi: float, start: float, dur: float, gain=1.0, p=0.0, rng=None, rel=0.3) -> None:
        n = int((dur + rel) * RATE)
        if n <= 0:
            return
        key = (inst, round(midi, 2), n // 64, round(self.q, 4))
        mono = self._cache.get(key)
        if mono is None:
            mono = INST[inst](hz(midi), n, rng, dur=dur, q=self.q).astype(np.float32)
            if len(self._cache) < 3000:
                self._cache[key] = mono
        self._place(buf, mono, start, gain, p)

    def drum(self, buf, kind: str, start: float, vel: float, rng) -> None:
        fn, ln, g, pan = KIT[kind]
        self._place(buf, fn(int(ln * RATE), vel, rng), start, vel * g, pan + rng.uniform(-0.04, 0.04))

    # ── 연주법 ──
    def render_part(self, buf, part: dict, chords: list, root: int, scale: str, bars: int, rng, crescendo=False) -> None:
        st = part.get("style")
        g, o, p = part.get("gain", 1.0), 12 * part.get("oct", 0), part.get("pan", 0.0)
        bar, step, S = self.bar, self.step, self.steps
        if st == "drone":       # 백파이프 드론: 으뜸음 D2 · D3 · A3, 화음과 상관없이 페이즈 내내
            for j, iv in enumerate((-24, -12, -5)):
                self.note(buf, "drone", root + iv + o, 0.0, bars * bar, g * (1.0, 0.7, 0.5)[j], (j - 1) * 0.3, rng, rel=0.3)
            return
        if st == "strum":       # 부주키 긁기: 6/8 = 8분마다 내림(강) · 올림(약), 4/4 = 8분 + 16분 올림 몇 개
            pat = part.get("pattern") or ("D.uD.uD.uD.u" if self.six else "D.uD.uD.D.uD.uDu")
            for b in range(bars):
                cm = chord_midis(chords[b], root, scale) + [chord_midis(chords[b], root, scale)[0] + 12]
                for i, ch in enumerate(pat[:S]):
                    if ch not in "Du":
                        continue
                    seq = cm if ch == "D" else cm[::-1]
                    for j, m in enumerate(seq):
                        self.note(buf, "bouzouki", m - 12 + o, b * bar + i * step + j * 0.009, step * 2.2, g * (1.0 if ch == "D" else 0.6),
                                  p + (j - 1.5) * 0.15, rng, rel=0.05)
            return
        if st == "reel":        # 피들 반복 음형: 화음음 위아래 (6/8 = 8분, 4/4 = 16분), 박 첫 음에 활 강세
            every = 2 if self.six else 1
            for b in range(bars):
                cm = chord_midis(chords[b], root, scale)
                tones = [m + o for m in cm] + [cm[0] + 12 + o]
                seq = tones + tones[-2:0:-1]
                k = 0
                for i in range(0, S, every):
                    acc = 1.0 if i % (6 if self.six else 4) == 0 else 0.7
                    self.note(buf, "fiddle", seq[k % len(seq)], b * bar + i * step, step * every * 0.8, g * acc,
                              p + (0.2 if k % 2 else -0.2), rng, rel=0.04)
                    k += 1
            return
        if st == "chant_hold":  # 남성 합창 '오—' 화음 (2마디마다)
            b = 0
            while b < bars:
                e = min(bars, b + 2)
                for j, m in enumerate(chord_midis(chords[b], root, scale)):
                    self.note(buf, "chant", m - 12 + o, b * bar, (e - b) * bar * 0.96, g * (1.0 if j == 0 else 0.8), p + (j - 1) * 0.4, rng, rel=0.3)
                b = e
            return
        if st == "melody":      # 주선율 — 휘슬은 박 첫 음(점4분 · 4분 자리)에 '컷' 꾸밈음
            inst = part["inst"]
            beat = 1.5 if self.six else 1.0
            for b, at, deg, ln in part["notes"]:
                if b >= bars:
                    continue
                m = degree_to_midi(deg, root, scale) + o
                use = inst
                if inst == "whistle" and abs(at / beat - round(at / beat)) < 1e-6 and ln >= 0.5:
                    use = "whistle_cut"
                self.note(buf, use, m, b * bar + at * self.q, ln * self.q * 0.95, g, p, rng, rel=0.12)
            return
        super().render_part(buf, part, chords, root, scale, bars, rng, crescendo)

    def render_perc(self, buf, pattern: dict, bars: int, rng, crescendo=False, root=None) -> None:
        """pattern = {타악 이름: 마디 칸 문자열 (6/8 = 12칸, 4/4 = 16칸) 또는 마디마다 돌아가는 목록}. X = 강하게."""
        for kind, pat in pattern.items():
            pats = pat if isinstance(pat, list) else [pat]
            for b in range(bars):
                for i, ch in enumerate(pats[b % len(pats)][: self.steps]):
                    if ch in "xX":
                        self.drum(buf, kind, b * self.bar + i * self.step, 1.0 if ch == "X" else 0.68, rng)

    # ── 층 만들기 ──
    def stems(self) -> dict:
        sp = self.spec
        rv = sp.get("reverb", [0.15, 1.1])
        prv = [rv[0] * 0.6, rv[1] * 0.7]
        out = {}
        phases = sp["phases"]
        for i, ph in enumerate(phases):
            self.set_tempo(i)
            n16 = self.loop_len(self.bars)
            root, scale = self.phase_info(i)
            rng = np.random.default_rng(self.seed + i * 13)
            chords = ph["chords"]
            pre = f"{i + 1}_"

            def lay(parts, perc=None, r=rv, g=None):
                return self.wrap(self.render_layer(parts, chords, root, scale, self.bars, g if g is not None else rng, r, perc=perc), n16)
            out[pre + "base"] = lay(ph.get("base"))
            perc = ph["perc"]
            out[pre + "perc"] = lay(None, perc["pattern"], prv)
            out[pre + "perc_crisis"] = lay(None, dict(perc["pattern"], **perc.get("crisis", {})), prv)
            lead = ph.get("lead") or []
            out[pre + "lead"] = lay(lead, g=np.random.default_rng(self.seed + i * 13 + 1))
            main = lead[:1]   # 지침: 피들이 주선율을 한 옥타브 위에서 (휘슬은 이미 높아 신호 자리를 가리므로)
            up = [dict(pt, inst="fiddle", oct=(0 if pt.get("inst") == "whistle" else pt.get("oct", 0)) + 1, gain=ph.get("tired_gain", 0.6))
                  for pt in main] + [dict(pt, gain=pt.get("gain", 1.0) * 0.5) for pt in lead]
            out[pre + "lead_oct"] = lay(up, g=np.random.default_rng(self.seed + i * 13 + 1))
            out[pre + "choir"] = lay(ph.get("choir"))
            if i + 1 < len(phases):
                self.set_tempo(i + 1)   # 라이저 = 다음 페이즈 빠르기로
                out[pre + "riser"] = self.riser(i, rng, rv)
        self.set_tempo(0)
        out["intro_mix"] = self.intro(rv)
        out["fail"] = self.fail_sound(rv)
        return out

    def intro(self, rv) -> np.ndarray:
        """1마디: 보드란 굴림(점점 세게) → 휘슬이 아래에서 휙 올라와 1페이즈 첫 박으로 + 드론이 켜짐."""
        root, scale = self.phase_info(0)
        rng = np.random.default_rng(self.seed + 999)
        buf = self._buf(self.bar)
        S = self.steps
        for s in range(S):
            self.drum(buf, "bod" if s % 3 == 0 else "bodp", s * self.step, 0.45 + 0.55 * s / S, rng)
        for j, iv in enumerate((-24, -12, -5)):
            self.note(buf, "drone", root + iv, self.bar * 0.3, self.bar * 0.7, (0.5, 0.35, 0.25)[j], (j - 1) * 0.3, rng, rel=0.05)
        run = [degree_to_midi(d, root + 12, scale) for d in (1, 2, 3, 4, 5, 6, 7, 8)]
        at0 = self.bar * 0.5
        for j, m in enumerate(run):
            self.note(buf, "whistle", m, at0 + j * self.bar * 0.5 / len(run), self.bar * 0.5 / len(run) * 0.9, 0.35 + 0.05 * j, 0.15, rng, rel=0.03)
        buf = self.hall(buf, rv[0], rv[1], rng)
        n = self.loop_len(1)
        out = buf[: n + int(RATE * 0.02)].copy()
        out[n:] *= np.linspace(1, 0, len(out) - n)[:, None]
        return out[:n]

    def riser(self, i: int, rng, rv) -> np.ndarray:
        """페이즈 전환 1마디 (다음 페이즈 빠르기): 보드란 굴림 점점 세게 + 피들 상승 (도리안 두 옥타브) · 4/4 로 갈 땐 큰북 셋."""
        root, scale = self.phase_info(i + 1)
        n = self.loop_len(1)
        buf = self._buf(self.bar)
        S = self.steps
        for s in range(S):
            u = s / max(1, S - 1)
            self.drum(buf, "bod" if s % (3 if self.six else 4) == 0 else "bodp", s * self.step, 0.45 + 0.55 * u, rng)
            m = degree_to_midi(1 + s * 14 // S, root - 12, scale)
            self.note(buf, "fiddle", m, s * self.step, self.step * 0.9, 0.3 + 0.25 * u, 0.25 * ((-1) ** s), rng, rel=0.03)
        if not self.six:
            for s in (0, 8, 12):
                self.drum(buf, "big", s * self.step, 0.9, rng)
        out = self.hall(buf, rv[0], rv[1], rng)[:n]
        out[-int(RATE * 0.02):] *= np.linspace(1, 0, int(RATE * 0.02))[:, None]
        return out

    def fail_sound(self, rv) -> np.ndarray:
        """실패: 백파이프 주머니에서 바람이 빠짐 — 드론·챈터가 반음 셋 아래로 처지며 사그라듦 + 보드란 '둥'."""
        root, scale = self.phase_info(0)
        rng = np.random.default_rng(self.seed + 777)
        L = 2.2
        n = int(L * RATE)
        t = _t(n)
        sag = 2 ** (-3 * (t / t[-1]) ** 1.6 / 12)
        x = np.zeros(n)
        for m, a in ((root - 24, 1.0), (root - 12, 0.7), (root - 5, 0.5), (root + 12, 0.6)):
            x += a * _harm(hz(m) * sag, [1 / kk ** 0.8 for kk in range(1, 20)], top=4000)
        x = _bw_filter(np.tanh(1.4 * _norm(x)), "lp", 2500) * (1 - t / t[-1]) ** 1.2 * np.minimum(1, t / 0.02)
        buf = self._buf(L)
        self._place(buf, x, 0.0, 0.7, 0.0)
        self.drum(buf, "bod", 0.0, 1.0, rng)
        self.drum(buf, "big", 0.0, 0.8, rng)
        buf = self.hall(buf, rv[0], rv[1], rng)
        out = buf[:n].copy()
        out[-int(RATE * 0.05):] *= np.linspace(1, 0, int(RATE * 0.05))[:, None]
        return out
