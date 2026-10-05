"""북과 목 노래 전투 곡 (SHARMION_THEMES.md 2장, DESIGN.md 43-17) — 산신 쏘가리 '산군' 전용 L02-SANGUN. 스펙에 "sangun": true.

boss_synth.Song 을 물려받아 층 구조·반복 이음새·마스터링은 그대로, 악기와 연주만 '산의 의식'으로 (boss_synth.py 는 그대로).
E단조 5음(E·G·A·B·D) · 156 · 4/4.
  악기  목 노래(한 사람이 낮은 소리 + 휘파람 같은 높은 배음을 동시에 — 낮은 E 의 배음 하나를 좁게 키워 가락으로) ·
        마두금(두 줄 활 악기, 거칠고 따뜻하게, 반복 음형은 활을 짧게) · 뿔나팔 · 큰 북 · 손북 · 낮은 북 · 낮은 남성 외침 '하!' ·
        호랑이 울음 '어흥'(작게) · 폭풍 바람
  바탕  목 노래 낮은 지속음 + 마두금 16분 반복 음형 (짧게)
  타악  큰북 x..x..x.x..x..x. · 손북 16분 전부 · 낮은 북 강타 5·13칸 (3페이즈: 모든 북 최대)
  주선율 마두금 (주인의 동기로 시작), 3페이즈 뿔나팔 / 3페이즈 목 노래 휘파람 배음이 날카롭게
  합창 자리 낮은 남성 외침 '하!' (마디 1·11칸, 2페이즈부터)
  위기  낮은 북 연타 + 외침 매 박 (위기 타악 층에) / 지침: 목 노래 휘파람음이 길게 (옥타브 주선율 층)
  전환  북 몰아치기 1마디 + 뿔나팔 한 음 + 끝에 낮은 '어흥' (= 페이즈 시작마다 작게)
  실패  큰 북 한 번 + 호랑이 울음이 멀어지며 사라짐
  인트로 폭풍 바람 → 낮은 '어흥' → 큰북 '둥!' (1마디)
"""
import numpy as np

from src.audio.boss_muhyeop import _env, _harm, _norm, _ph, _vib, s_wind
from src.audio.boss_synth import RATE, Song, _bw_filter, _t, chord_midis, degree_to_midi, hz, noise, peaking_eq


# ───────────────────────── 악기 ─────────────────────────

def throat(f0: float, n: int, rng, whistle=None, sharp: float = 1.0) -> np.ndarray:
    """목 노래: 낮은 f0 의 거친 소리(모음 '오') + whistle = [(시작초, 배음 번호)] 로 그 배음만 좁게 키운 휘파람 가락."""
    t = _t(n)
    f_t = f0 * (1 + 0.003 * np.sin(2 * np.pi * 4.3 * t))
    src = _harm(f_t, [1 / k ** 0.8 for k in range(1, 48)], top=7000)
    low = peaking_eq(peaking_eq(_bw_filter(src, "lp", 1800), 380.0, 8.0, 1.5), 760.0, 5.0, 1.8)
    out = np.tanh(1.3 * _norm(low))
    if whistle:
        w = np.zeros(n)
        ph = _ph(f_t)
        for j, (at, k) in enumerate(whistle):
            s = int(at * RATE)
            e = int(whistle[j + 1][0] * RATE) if j + 1 < len(whistle) else n
            if s >= n:
                break
            seg = np.arange(s, min(e, n))
            glide = np.clip((seg - s) / (0.03 * RATE), 0, 1)
            w[seg] = np.sin(k * ph[seg] + 0.3) * glide
        w *= 1 + 0.15 * np.sin(2 * np.pi * 5.5 * t)
        out = out + w * 0.55 * sharp
    return _norm(out) * _env(n, 0.15, 0.0, 0.2)


def i_morin(f, n, rng, dur=0.0, q=0.38, **k):
    """마두금: 말총 활로 긋는 두 줄 — 거칠고 따뜻하게 (활 긁힘 + 낮은 울림통), 1박 이상 떨림."""
    t = _t(n)
    semi = -0.35 * np.exp(-t / 0.03)
    if dur >= 0.9 * q:
        semi += _vib(t, 0.18, 0.3, 5.0, 0.2)
    f_t = f * 2 ** (semi / 12) * (1 + 0.002 * rng.standard_normal(n).cumsum() / np.sqrt(n))
    x = _harm(f_t, [1 / k_ ** 0.95 for k_ in range(1, 30)], top=6000)
    x += _bw_filter(noise(n, rng), "bp", (1200, 4500)) * 0.18 * (0.5 + 0.5 * np.exp(-t / 0.06))   # 말총 긁힘
    x = peaking_eq(peaking_eq(_bw_filter(x, "hp", 120), 480.0, 5.0, 1.0), 1300.0, 3.0, 1.2)
    x = np.tanh(1.7 * _norm(_bw_filter(x, "lp", 5000)))
    return _norm(x) * _env(n, 0.025, 0.12, 0.04)


def i_horn(f, n, rng, dur=0.0, q=0.38, **k):
    """뿔나팔: 굵고 거친 원뿔 관 — 바탕음이 강하고 배음은 적게, 숨 섞임, 아래에서 밀어 올림."""
    t = _t(n)
    semi = -1.0 * np.exp(-t / 0.05)
    if dur >= 0.9 * q:
        semi += _vib(t, 0.3, 0.2, 4.6, 0.3)
    f_t = f * 2 ** (semi / 12)
    x = _harm(f_t, [1.0, 0.75, 0.5, 0.32, 0.2, 0.12, 0.07, 0.04], top=5000)
    x += _bw_filter(noise(n, rng), "bp", (f * 1.5, min(8000, f * 6))) * 0.1
    x = np.tanh(2.0 * _norm(x))
    return _norm(_bw_filter(x, "lp", 4000)) * _env(n, 0.05, 0.1, 0.06)


def i_whistle(f, n, rng, dur=0.0, **k):
    """목 노래 휘파람 배음만 길게 (지침)."""
    t = _t(n)
    f_t = f * (1 + 0.004 * np.sin(2 * np.pi * 5.5 * t))
    x = np.sin(_ph(f_t)) + 0.15 * np.sin(2 * _ph(f_t))
    return x * _env(n, 0.08, 0.1, 0.08)


def d_bigdrum(n, vel, rng):          # 큰 북
    t = _t(n)
    f = 52 + 30 * np.exp(-t * 16)
    x = np.sin(_ph(f)) * np.exp(-t * 3.5) + _bw_filter(noise(n, rng), "lp", 400) * np.exp(-t * 30) * 0.5
    return np.tanh(1.5 * x) * np.minimum(1, t / 0.003)


def d_handdrum(n, vel, rng):         # 손북 (손바닥으로 탁)
    t = _t(n)
    x = np.sin(_ph(np.full(n, 210.0) * (1 + 0.3 * np.exp(-t * 50)))) * np.exp(-t * 28) * 0.7
    x += _bw_filter(noise(n, rng), "bp", (900, 4500)) * np.exp(-t * 60) * 0.6
    return x


def d_lowdrum(n, vel, rng):          # 낮은 북 강타 (가죽 떨림)
    t = _t(n)
    f = 64 + 40 * np.exp(-t * 20)
    x = np.sin(_ph(f)) * np.exp(-t * 6) + _bw_filter(noise(n, rng), "bp", (150, 900)) * np.exp(-t * 14) * 0.5
    return np.tanh(1.8 * x)


def s_shout(n, rng, pitch=118.0):    # 낮은 남성 외침 '하!'
    t = _t(n)
    f_t = pitch * (1.08 - 0.12 * t / t[-1])
    src = _harm(f_t, [1 / k ** 0.7 for k in range(1, 40)], top=6000) + noise(n, rng) * 0.35
    x = sum(a * _bw_filter(src, "bp", (fc - bw, fc + bw)) for fc, a, bw in ((720, 1.0, 110), (1150, 0.7, 140), (2500, 0.3, 250)))
    x = np.tanh(2.2 * _norm(x))
    e = np.minimum(1, t / 0.012) * np.exp(-t * 7)
    return _norm(x) * e


def s_roar(n, rng, far=False):       # 호랑이 울음 '어흥' (far = 멀어지며 사라짐)
    t = _t(n)
    u = t / t[-1]
    f0 = 92 * (1 + 0.25 * np.sin(np.pi * u)) * (1 + 0.02 * rng.standard_normal(n))
    f0 = _bw_filter(f0, "lp", 30)
    src = _harm(f0, [1 / k ** 0.6 for k in range(1, 40)], top=4000) + _bw_filter(noise(n, rng), "lp", 1500) * 0.8
    x = sum(a * _bw_filter(src, "bp", (fc - bw, fc + bw)) for fc, a, bw in ((420, 1.0, 160), (900, 0.6, 220), (1900, 0.2, 300)))
    x = np.tanh(2.6 * _norm(x)) * (1 + 0.3 * np.sin(2 * np.pi * 28 * t))   # 목 떨림
    e = np.sin(np.pi * np.clip(u * 1.2, 0, 1)) ** 0.7
    if far:
        e = e * (1 - u) ** 2
        x = _bw_filter(x, "lp", 900)
    return _norm(x) * e


def s_claw(n, rng):                 # 발톱 할퀴는 '촥': 세 줄이 빠르게 긁고 지나감 + 묵직한 바닥
    t = _t(n)
    x = np.zeros(n)
    for j in range(3):
        s0 = int((0.012 * j) * RATE)
        m = min(n - s0, int(0.07 * RATE))
        if m <= 0:
            continue
        seg = noise(m, rng)
        out = np.zeros(m)
        k = 6
        for i in range(k):   # 높은 데서 낮은 데로 쓸림
            fc = 6500 * (0.75 ** i)
            a, e = i * m // k, min(m, (i + 2) * m // k)
            out[a:e] += _bw_filter(seg[a:e], "bp", (fc * 0.6, fc * 1.4)) * np.hanning(e - a)
        x[s0:s0 + m] += out * (1 - 0.2 * j)
    x += np.sin(_ph(60 + 40 * np.exp(-t * 30))) * np.exp(-t * 14) * 0.6
    return np.tanh(1.8 * _norm(x))


INST = {"morin": i_morin, "horn": i_horn, "whistle": i_whistle}
DRUM = {"big": (d_bigdrum, 1.2), "hand": (d_handdrum, 0.25), "low": (d_lowdrum, 0.8)}
KIT_GAIN = {"big": 0.9, "hand": 0.32, "low": 0.75, "shout": 0.6}
KIT_PAN = {"hand": 0.3, "low": -0.15}


# ───────────────────────── 곡 ─────────────────────────

class SangunSong(Song):
    def note(self, buf, inst: str, midi: float, start: float, dur: float, gain=1.0, p=0.0, rng=None, rel=0.3) -> None:
        n = int((dur + rel) * RATE)
        if n <= 0:
            return
        key = (inst, round(midi, 2), n // 64)
        mono = self._cache.get(key)
        if mono is None:
            mono = INST[inst](hz(midi), n, rng, dur=dur, q=self.q).astype(np.float32)
            if len(self._cache) < 3000:
                self._cache[key] = mono
        self._place(buf, mono, start, gain, p)

    def render_part(self, buf, part: dict, chords: list, root: int, scale: str, bars: int, rng, crescendo=False) -> None:
        st = part.get("style")
        g, o, p = part.get("gain", 1.0), 12 * part.get("oct", 0), part.get("pan", 0.0)
        bar, step = self.bar, self.step
        if st == "throat":      # 목 노래: 16마디 내내 낮은 E + 휘파람 배음 가락 (2마디마다 배음을 바꿈)
            f0 = hz(root - 24 + o)
            seq = part.get("whistle", [8, 12, 11, 14, 12, 11, 8, 6])   # 낮은 E 의 배음 번호 (6=B · 8=E · 11≈A · 12=B · 14≈D — 5음에 가까운 것만)
            wh = [(b * bar, seq[(b // 2) % len(seq)]) for b in range(0, bars, 2)]
            x = throat(f0, int((bars * bar + 1.0) * RATE), rng, whistle=wh, sharp=part.get("sharp", 1.0))
            self._place(buf, x, 0.0, g, p)
            return
        if st == "morin_ost":   # 마두금 16분 반복 (활을 짧게): 으뜸·으뜸·5도·으뜸 / 으뜸·♭7·5도·으뜸
            seq = (0, 0, 7, 0, 0, 10, 7, 0) if part.get("busy") else (0, 0, 7, 0)
            pat = part.get("pattern", "x" * self.steps)
            for b in range(bars):
                r = chord_midis(chords[b], root, scale)[0] + o
                k = 0
                for i, ch in enumerate(pat[: self.steps]):
                    if ch not in "xX":
                        continue
                    acc = 1.0 if i % 4 == 0 else 0.7
                    self.note(buf, "morin", r + seq[k % len(seq)], b * bar + i * step, step * 0.6, g * acc, p + (0.15 if k % 2 else -0.15), rng, rel=0.06)
                    k += 1
            return
        if st == "shouts":      # 낮은 남성 외침 '하!' (칸 목록)
            cells = part.get("cells", [0, 10])
            for b in range(bars):
                for j, i in enumerate(cells):
                    x = s_shout(int(0.32 * RATE), rng, pitch=rng.uniform(108, 128))
                    self._place(buf, x, b * bar + i * step, g * KIT_GAIN["shout"], 0.2 * (-1) ** j)
            return
        if st == "melody":
            inst = part["inst"]
            for b, at, deg, ln in part["notes"]:
                if b >= bars:
                    continue
                m = degree_to_midi(deg, root, scale) + o
                d = ln * self.q * (1.1 if inst == "whistle" else 0.95)
                self.note(buf, inst, m, b * bar + at * self.q, d, g, p, rng, rel=0.12)
            return
        super().render_part(buf, part, chords, root, scale, bars, rng, crescendo)

    def render_perc(self, buf, pattern: dict, bars: int, rng, crescendo=False, root=None) -> None:
        """pattern = {big, hand, low: 16칸, gain: 북 배율, shout: 외침 칸 문자열(위기)}. 16마디 끝 북 몰아치기."""
        S, st = self.steps, self.step
        gm = pattern.get("gain", 1.0)
        for b in range(bars):
            last = b == bars - 1
            for k in ("big", "hand", "low"):
                pp = pattern.get(k, "")[:S]
                for i, ch in enumerate(pp):
                    if ch not in "xX" or (last and i >= S - 4 and k != "hand"):
                        continue
                    vel = 1.0 if (ch == "X" or i % 4 == 0) else 0.72
                    fn, ln = DRUM[k]
                    self._place(buf, fn(int(ln * RATE), vel, rng), b * self.bar + i * st, vel * KIT_GAIN[k] * gm,
                                KIT_PAN.get(k, 0.0) + rng.uniform(-0.04, 0.04))
            for i, ch in enumerate(pattern.get("shout", "")[:S]):
                if ch in "xX":
                    self._place(buf, s_shout(int(0.3 * RATE), rng, pitch=rng.uniform(105, 125)), b * self.bar + i * st,
                                KIT_GAIN["shout"] * 0.9, 0.25 * (-1) ** i)
            if last:   # 북 몰아치기 (마지막 4칸 큰북·낮은 북 번갈아)
                for j in range(4):
                    fn = d_bigdrum if j % 2 == 0 else d_lowdrum
                    self._place(buf, fn(int(0.8 * RATE), 1.0, rng), b * self.bar + (S - 4 + j) * st, (0.6 + 0.12 * j) * gm, 0.2 * (-1) ** j)

    # ── 층 만들기 ──
    def stems(self) -> dict:
        sp = self.spec
        rv = sp.get("reverb", [0.15, 1.1])
        prv = [rv[0] * 0.7, rv[1] * 0.7]
        out = {}
        n16 = self.loop_len(self.bars)
        phases = sp["phases"]
        for i, ph in enumerate(phases):
            root, scale = self.phase_info(i)
            rng = np.random.default_rng(self.seed + i * 13)
            chords = ph["chords"]
            pre = f"{i + 1}_"
            out[pre + "base"] = self.wrap(self.render_layer(ph.get("base"), chords, root, scale, self.bars, rng, rv), n16)
            perc = ph["perc"]
            out[pre + "perc"] = self.wrap(self.render_layer(None, chords, root, scale, self.bars, rng, prv, perc=perc["pattern"]), n16)
            crisis = dict(perc["pattern"], **perc.get("crisis", {}))
            out[pre + "perc_crisis"] = self.wrap(self.render_layer(None, chords, root, scale, self.bars, rng, prv, perc=crisis), n16)
            lead = ph.get("lead") or []
            lrng = np.random.default_rng(self.seed + i * 13 + 1)
            out[pre + "lead"] = self.wrap(self.render_layer(lead, chords, root, scale, self.bars, lrng, rv), n16)
            # 지침: 목 노래 휘파람음이 길게 — 주선율 음 중 박 첫머리 음만 골라 2배 길게 (한 옥타브 위)
            main = lead[:1]
            up = [dict(p, oct=p.get("oct", 0) + 1, inst="whistle", gain=p.get("gain", 1.0) * 0.6,
                       notes=[[b, at, d, max(ln, 1.0) * 2] for b, at, d, ln in p["notes"] if at in (0, 2)]) for p in main]
            out[pre + "lead_oct"] = self.wrap(self.render_layer(up, chords, root, scale, self.bars, np.random.default_rng(self.seed + i * 13 + 1), rv), n16)
            out[pre + "choir"] = self.wrap(self.render_layer(ph.get("choir"), chords, root, scale, self.bars, rng, rv), n16)
            if i + 1 < len(phases):
                out[pre + "riser"] = self.riser(i, rng, rv)
        out["intro_mix"] = self.intro(rv)
        out["fail"] = self.fail_sound(rv)
        return out

    def intro(self, rv) -> np.ndarray:
        """1마디: 폭풍 바람 → 낮은 '어흥' → 마디 끝 큰북 '둥!' (1페이즈 첫 박 바로 앞)."""
        rng = np.random.default_rng(self.seed + 999)
        buf = self._buf(self.bar)
        self._place(buf, s_wind(int((self.bar + 0.5) * RATE), rng), 0.0, 0.9, -0.2)
        self._place(buf, s_roar(int(1.0 * RATE), rng), 0.1, 1.0, 0.1)
        t_hit = self.bar - 2 * self.step
        self._place(buf, d_bigdrum(int(1.2 * RATE), 1.0, rng), t_hit, KIT_GAIN["big"] * 1.3, 0.0)
        self._place(buf, d_lowdrum(int(0.8 * RATE), 1.0, rng), t_hit, KIT_GAIN["low"], 0.0)
        buf = self.hall(buf, rv[0], rv[1], rng)
        n = self.loop_len(1)
        out = buf[: n + int(RATE * 0.02)].copy()
        out[n:] *= np.linspace(1, 0, len(out) - n)[:, None]
        return out[:n]

    def riser(self, i: int, rng, rv) -> np.ndarray:
        """페이즈 전환 1마디: 북 몰아치기(손북 16분 + 큰북 점점 세게) + 뿔나팔 한 음 + 끝에 작은 '어흥' (다음 페이즈 시작)."""
        root, scale = self.phase_info(i + 1)
        n = self.loop_len(1)
        buf = self._buf(self.bar)
        S, st = self.steps, self.step
        for s in range(S):
            u = s / (S - 1)
            self._place(buf, d_handdrum(int(0.25 * RATE), 1.0, rng), s * st, KIT_GAIN["hand"] * (0.6 + 0.8 * u), 0.3)
            if s % 2 == 0:
                self._place(buf, (d_bigdrum if s % 4 == 0 else d_lowdrum)(int(0.8 * RATE), 1.0, rng), s * st, (0.4 + 0.5 * u), 0.0)
        self.note(buf, "horn", degree_to_midi(1, root, scale), 0.0, self.bar * 0.7, 0.55, 0.1, rng, rel=0.1)
        self._place(buf, s_roar(int(0.8 * RATE), rng), self.bar - 0.55, 0.3, -0.2)
        out = self.hall(buf, rv[0], rv[1], rng)[:n]
        out[-int(RATE * 0.02):] *= np.linspace(1, 0, int(RATE * 0.02))[:, None]
        return out

    def fail_sound(self, rv) -> np.ndarray:
        """실패: 큰 북 한 번 + 호랑이 울음이 멀어지며 사라짐."""
        rng = np.random.default_rng(self.seed + 777)
        buf = self._buf(2.4)
        self._place(buf, d_bigdrum(int(1.2 * RATE), 1.0, rng), 0.0, 1.2, 0.0)
        self._place(buf, s_roar(int(1.9 * RATE), rng, far=True), 0.25, 0.6, 0.3)
        buf = self.hall(buf, rv[0], rv[1] * 1.3, rng)
        n = int(2.4 * RATE)
        out = buf[:n].copy()
        out[-int(RATE * 0.05):] *= np.linspace(1, 0, int(RATE * 0.05))[:, None]
        return out
