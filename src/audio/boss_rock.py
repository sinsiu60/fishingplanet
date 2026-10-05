"""락 밴드 전투 곡 (ELECTRO.md, DESIGN.md 43-14) — 은빛 농어 '일렉트로' 전용 L03-ROCK. 스펙에 "rock": true.

boss_synth.Song 을 물려받아 층 구조(바탕·타악·주선율·합창 자리 + 위기 타악 + 옥타브 주선율)·반복 이음새·마스터링은 그대로 쓰고,
악기와 연주만 락 밴드로 바꾼다 (boss_synth.py 는 건드리지 않음 — 고치면 모든 곡이 다시 구워짐).
  악기  일렉트릭 기타 2대(리듬: 손바닥 뮤트 16분 '둥둥둥둥' 좌우 2겹 / 리드: 찌그러짐 + 떨림 + 벤딩), 베이스 기타, 드럼 세트
        기타 = 튕긴 줄(배음이 빨리 사라지는 톱니) → 찌그러짐(눌러 깎기) → 스피커 통(80Hz 아래·5kHz 위 깎고 중음 살짝 강조)
        파워 코드 = 으뜸음 + 5도 + 옥타브. 효과: 피드백 '끼이잉', 줄 긁어 내리기
  바탕  리듬 기타 리프(스펙 riff: m 뮤트 · M 뮤트 강세 · p 파워 코드 · 숫자 = 그 도수 파워 코드 · - 이어 울림 · . 쉼) + 베이스 8분
  타악  1·2페이즈 킥 x..x..x.x..x..x. · 스네어 2·4박 · 하이햇 8분 · 크래시 4마디(2페이즈 2마디)
        3페이즈 투베이스 16분 · 스네어 + 마디 끝 4칸 연타 · 라이드 8분 · 크래시 2마디
  위기  킥 16분 + 리듬 기타 한 옥타브 아래 (위기 타악 층에 함께) / 지침: 옥타브 주선율 층은 1박 이상 음마다 길게 벤딩
  전환  라이저 1마디 = 줄 긁어 내리기 + 탐 연타 / 실패: <곡ID>_fail = 파워 코드 '콰앙' 뒤 바로 끊김 + 피드백 1.5초 사라짐
  인트로 피드백 0.5박 → 첫 박 E 파워 코드 + 크래시 + 킥 → 1마디 (끝에 탐 필인)
"""
import numpy as np

from src.audio.boss_synth import (DRUM_LEN, RATE, Song, _bw_filter, _t, d_crash, d_hat, d_kick, d_ohat, d_snare2, d_tom,
                                  degree_to_midi, hz, noise, peaking_eq)

DRUM_PAN = {"hat": 0.3, "ohat": 0.3, "ride": -0.35, "crash": 0.25}
KIT_GAIN = {"kick": 0.46, "snare": 0.46, "hat": 0.15, "ohat": 0.14, "ride": 0.17, "crash": 0.28, "tom": 0.42}   # 드럼은 기타 뒤 (주인공 = 일렉 기타)
# 박 단계 0~2 (1 → 3페이즈). crash = 몇 마디마다 첫 칸 크래시
KIT = [
    dict(kick="x..x..x.x..x..x.", snare="....x.......x...", hat="x.x.x.x.x.x.x.x.", crash=4),
    dict(kick="x..x..x.x..x..x.", snare="....x.......x...", hat="x.x.x.x.x.x.x.x.", ohat="......x.......x.", crash=2),
    dict(kick="xxxxxxxxxxxxxxxx", snare="....x.......xxxx", ride="x.x.x.x.x.x.x.x.", crash=2),
]
KIT_CRISIS = [dict(kick="xxxxxxxxxxxxxxxx"), dict(kick="xxxxxxxxxxxxxxxx"),
              dict(kick="xxxxxxxxxxxxxxxx", snare="....x..x....xxxx", crash=1)]
ACCENT = "x..x..x.x..x..x."   # 투베이스 16분 중 세게 밟는 칸


# ───────────────────────── 악기 ─────────────────────────

def _osc(f_t: np.ndarray, decay: float, top: float = 9000.0) -> np.ndarray:
    """튕긴 줄: 톱니 배음 (높은 배음일수록 빨리 사라짐). f_t = 순간 주파수 배열 (벤딩·떨림)."""
    n = len(f_t)
    t = _t(n)
    ph = np.cumsum(f_t) / RATE
    k_max = int(max(1, min(60, top / max(30.0, float(f_t.max())))))
    out = np.zeros(n)
    for k in range(1, k_max + 1):
        out += np.sin(2 * np.pi * k * ph + 0.3 * k) / k * np.exp(-t * decay * (0.25 + 0.06 * k))
    return out


def _pick(n: int, rng, f=2500.0, k=0.25) -> np.ndarray:
    x = np.zeros(n)
    m = min(n, int(0.006 * RATE))
    x[:m] = _bw_filter(noise(m, rng), "lp", f) * np.exp(-np.arange(m) / (m / 4))
    return x * k


def amp(x: np.ndarray, drive: float, tight: float = 110.0) -> np.ndarray:
    """찌그러짐 (중음을 미리 올려 비대칭으로 눌러 깎기 — 2단) → 스피커 통 울림
    (80Hz 아래 · 5.5kHz 위 깎고, 400Hz 살짝 파내고 750Hz·3.2kHz 살짝 강조)."""
    x = _bw_filter(x, "hp", tight)
    x = peaking_eq(x, 900.0, 12.0, 0.6)          # 오버드라이브 앞단: 중음을 밀어 넣어 '깎이는' 소리
    x = x / (float(np.abs(x).max()) or 1.0)
    y = np.tanh(drive * x + 0.2) - np.tanh(0.2)
    y = _bw_filter(y, "hp", 160)
    y = np.tanh(2.5 * y / (float(np.abs(y).max()) or 1.0))
    y = _bw_filter(y, "hp", 80)
    y = _bw_filter(_bw_filter(y, "lp", 5500, 4), "lp", 7000)
    y = peaking_eq(peaking_eq(peaking_eq(y, 400.0, -2.5, 1.0), 750.0, 2.0, 0.8), 3500.0, 7.0, 0.9)
    return y / (float(np.abs(y).max()) or 1.0)


def _env(n: int, a: float, decay: float, rel: float) -> np.ndarray:
    t = _t(n)
    e = np.minimum(1.0, t / a) * np.exp(-t * decay)
    r = int(rel * RATE)
    if 0 < r < n:
        e[-r:] *= np.linspace(1, 0, r)
    return e


def g_mute(f, n, rng, take=0):
    """손바닥 뮤트 파워 코드 (으뜸음 + 5도): 짧고 둔탁한 '둥'."""
    det = (1.0, 0.997)[take % 2]
    x = sum(_osc(np.full(n, f * r * det * (1 + rng.uniform(-6e-4, 6e-4))), 9.0) * a for r, a in ((1, 1.0), (1.5, 0.8)))
    x = _bw_filter(x, "lp", 1700 if take % 2 == 0 else 1900) + _pick(n, rng, 2500, 0.5)
    y = amp(x, 10.0 + take, tight=140)
    return y * _env(n, 0.002, 16.0, 0.02)


def g_power(f, n, rng, take=0):
    """파워 코드 (으뜸음 + 5도 + 옥타브), 크게 울림 — 줄마다 6ms 늦게 긁음."""
    det = (1.0, 0.996)[take % 2]
    x = np.zeros(n)
    for j, (r, a) in enumerate(((1, 1.0), (1.5, 0.85), (2, 0.6))):
        s = int(j * 0.006 * RATE)
        x[s:] += _osc(np.full(n - s, f * r * det * (1 + rng.uniform(-8e-4, 8e-4))), 1.2) * a
    x += _pick(n, rng, 3000, 0.4)
    y = amp(x, 8.0 + take, tight=130)
    return y * _env(n, 0.003, 0.9, 0.08)


def g_low(f, n, rng, take=0):          # 위기: 한 옥타브 아래 뮤트
    return g_mute(f, n, rng, 0) * 0.9


def contour(f, n, dur, q, bend: bool, tired: bool = False) -> np.ndarray:
    """리드 음높이: 1박 이상 = 떨림(비브라토), 벤딩 = 온음 아래에서 끌어올림 (지침 = 더 길고 깊게)."""
    t = _t(n)
    semi = np.zeros(n)
    if bend:
        up = 0.16 if not tired else 0.3
        semi -= 2.0 * np.clip(1 - t / up, 0, 1) ** 2
    if dur >= q * 0.9:
        start = 0.14 if not bend else 0.26
        depth = (0.32 if dur >= 1.9 * q else 0.22) * (1.4 if tired else 1.0)
        semi += depth * np.sin(2 * np.pi * 5.6 * np.maximum(0, t - start)) * np.clip((t - start) / 0.15, 0, 1)
    return f * 2 ** (semi / 12)


def g_lead(f, n, rng, take=0, dur=0.0, q=0.36, tired=False):
    bend = dur >= 1.9 * q or (tired and dur >= 0.9 * q)
    x = _osc(contour(f, n, dur, q, bend, tired), 0.55, top=7000) + _pick(n, rng, 3500, 0.15)
    y = amp(x, 12.0, tight=220)
    return y * _env(n, 0.004, 0.35, 0.06)


def g_bass(f, n, rng, take=0):
    """베이스 기타: 둥근 몸통 + 줄 소리, 살짝 눌러 앞으로."""
    t = _t(n)
    x = _osc(np.full(n, f), 3.0, top=1800) + 0.8 * np.sin(2 * np.pi * f * t)
    x = np.tanh(1.8 * x / (np.abs(x).max() or 1.0))
    x = _bw_filter(x, "lp", 1400)
    return x * _env(n, 0.003, 2.2, 0.03)


def g_feedback(f, n, rng, take=0, swell=True):
    """피드백 '끼이잉': 높은 음이 천천히 커짐 (swell=False 면 바로 시작해 사라짐)."""
    t = _t(n)
    fm = f * (1 + 0.004 * np.sin(2 * np.pi * 5.2 * t))
    x = np.sin(2 * np.pi * np.cumsum(fm) / RATE) + 0.35 * np.sin(4 * np.pi * np.cumsum(fm) / RATE)
    y = np.tanh(2.5 * x)
    y = _bw_filter(y, "lp", 6000)
    e = (t / t[-1]) ** 2 if swell else np.exp(-t * 2.4)
    return y * e * 0.6


def g_slide(f, n, rng, take=0):
    """줄 긁어 내리기 (피크 슬라이드): 높은 데서 낮은 데로 쓸리는 거친 소리."""
    t = _t(n)
    x = noise(n, rng) * (0.6 + 0.4 * np.sign(np.sin(2 * np.pi * 38 * t)))
    out = np.zeros(n)
    seg = max(1, n // 12)
    for i in range(12):   # 대역이 내려가며 쓸림
        lo = 4200 * (0.78 ** i)
        s, e = i * seg, min(n, (i + 2) * seg)
        out[s:e] += _bw_filter(x[s:e], "bp", (lo * 0.6, lo * 1.4)) * np.hanning(e - s)
    return amp(out, 4.0, tight=300) * (1 - t / t[-1]) * 0.7


def d_ride(n, vel, rng):
    t = _t(n)
    bell = sum(a * np.sin(2 * np.pi * fr * t) for fr, a in ((3100, 0.5), (4570, 0.35), (6210, 0.25))) * np.exp(-t * 6)
    wash = _bw_filter(noise(n, rng), "hp", 5500) * np.exp(-t * 4.5) * 0.6
    return (bell * 0.5 + wash) * 0.8


GTR = {"gtr_mute": g_mute, "gtr_power": g_power, "gtr_low": g_low, "gtr_lead": g_lead, "gtr_lead_t": g_lead, "gtr_harm": g_lead,
       "bass_gtr": g_bass, "feedback": g_feedback, "pickslide": g_slide}


# ───────────────────────── 곡 ─────────────────────────

class RockSong(Song):
    # ── 한 음 ──
    def note(self, buf, inst: str, midi: float, start: float, dur: float, gain=1.0, p=0.0, rng=None, rel=0.3) -> None:
        n = int((dur + rel) * RATE)
        if n <= 0:
            return
        take = 1 if p > 0.2 else 0
        key = (inst, round(midi, 2), n // 64, take)
        mono = self._cache.get(key)
        if mono is None:
            fn = GTR[inst]
            if fn is g_lead:
                mono = g_lead(hz(midi), n, rng, take, dur=dur, q=self.q, tired=inst == "gtr_lead_t")
            else:
                mono = fn(hz(midi), n, rng, take)
            mono = mono.astype(np.float32)
            if len(self._cache) < 3000:
                self._cache[key] = mono
        self._place(buf, mono, start + (0.004 if take else 0.0), gain, p)

    # ── 연주법 ──
    def riff_events(self, riff: dict, chords: list, root: int, scale: str, bars: int) -> list:
        """리프 → [(시작 칸, 길이 칸, 종류 'm'|'M'|'p', MIDI)] (마디마다)."""
        out = []
        S = self.steps
        for b in range(bars):
            c = chords[b]
            pat = riff.get(str(c), riff.get("*", "m" * S))[:S]
            r = degree_to_midi(c, root, scale) - 12
            while r > 47:
                r -= 12
            i = 0
            while i < S:
                ch = pat[i]
                if ch in ".-":
                    i += 1
                    continue
                j = i + 1
                while j < S and pat[j] == "-":
                    j += 1
                if ch.isdigit():
                    m = degree_to_midi(int(ch), root, scale) - 12
                    while m > 47:
                        m -= 12
                    out.append((b * S + i, j - i, "p", m))
                else:
                    out.append((b * S + i, j - i, ch, r))
                i = j
        return out

    def render_part(self, buf, part: dict, chords: list, root: int, scale: str, bars: int, rng, crescendo=False) -> None:
        st = part.get("style")
        g, o, p = part.get("gain", 1.0), 12 * part.get("oct", 0), part.get("pan", 0.0)
        step = self.step
        if st in ("riff", "riff_low"):
            low = st == "riff_low"
            for s0, ln, kind, m in self.riff_events(part["riff"], chords, root, scale, bars):
                t0 = s0 * step
                acc = 1.0 if kind in "Mp" else 0.78
                if kind == "p" and not low:
                    inst, dur, rel = "gtr_power", ln * step * 0.92, 0.06
                else:
                    inst, dur, rel = ("gtr_low" if low else "gtr_mute"), step * 0.8, 0.03
                mm = m + o - (12 if low else 0)
                if low:
                    self.note(buf, inst, mm, t0, dur, g * acc, 0.0, rng, rel)
                else:   # 좌우 2겹 (조금 다른 연주)
                    self.note(buf, inst, mm, t0, dur, g * acc, -0.75, rng, rel)
                    self.note(buf, inst, mm, t0, dur, g * acc * 0.95, 0.75, rng, rel)
            return
        if st == "bassriff":     # 리듬 기타와 같은 음, 8분
            ev = self.riff_events(part["riff"], chords, root, scale, bars)
            S = self.steps
            for b in range(bars):
                for i in range(0, S, 2):
                    s = b * S + i
                    cur = [e for e in ev if e[0] <= s < e[0] + max(e[1], 1)] or [e for e in ev if e[0] <= s][-1:]
                    if not cur:
                        continue
                    m = cur[-1][3] - 12 + o
                    acc = 1.0 if i % 4 == 0 else 0.85
                    self.note(buf, "bass_gtr", m, s * step, 2 * step * 0.85, g * acc, 0.0, rng, rel=0.03)
            return
        if st == "melody":
            inst = part["inst"]
            for b, at, deg, ln in part["notes"]:
                if b >= bars:
                    continue
                m = degree_to_midi(deg, root, scale) + o
                self.note(buf, inst, m, b * self.bar + at * self.q, ln * self.q * 0.95, g, p, rng, rel=0.12)
            return
        super().render_part(buf, part, chords, root, scale, bars, rng, crescendo)

    def render_perc(self, buf, pattern: dict, bars: int, rng, crescendo=False, root=None) -> None:
        """드럼 세트: pattern = {kick, snare, hat, ohat, ride: 16칸, crash: 몇 마디마다}. 8마디 끝 작은 필인 · 마지막 마디 탐 필인."""
        S, st = self.steps, self.step
        for b in range(bars):
            last = b == bars - 1
            for k in ("kick", "snare", "hat", "ohat", "ride"):
                pp = pattern.get(k, "")[:S]
                for i, ch in enumerate(pp):
                    if ch not in "xX" or (last and i >= S - 4 and k in ("snare", "kick")):
                        continue
                    if k == "kick":
                        vel = 1.0 if (pp == "x" * S and ACCENT[i] == "x") or pp != "x" * S else 0.62
                        mono = d_kick(int(DRUM_LEN["kick"] * RATE), vel, rng)
                    elif k == "snare":
                        vel = 1.0 if i % 4 == 0 else 0.7
                        mono = d_snare2(int(DRUM_LEN["snare2"] * RATE), vel, rng)
                    elif k == "ride":
                        vel = 1.0 if i % 4 == 0 else 0.75
                        mono = d_ride(int(1.2 * RATE), vel, rng)
                    else:
                        vel = 1.0 if i % 4 == 0 else 0.7
                        mono = (d_hat if k == "hat" else d_ohat)(int(DRUM_LEN[k] * RATE), vel, rng)
                    self._place(buf, mono, b * self.bar + i * st, vel * KIT_GAIN[k], DRUM_PAN.get(k, 0.0) + rng.uniform(-0.03, 0.03))
            ce = pattern.get("crash", 4)
            if ce and b % ce == 0:
                self._place(buf, d_crash(int(DRUM_LEN["crash"] * RATE), 1.0, rng), b * self.bar, KIT_GAIN["crash"], DRUM_PAN["crash"])
            if last:     # 탐 내림 필인 (높은 탐 → 낮은 탐) + 마지막 칸 스네어·킥
                for j in range(4):
                    t0 = b * self.bar + (S - 4 + j) * st
                    self._place(buf, d_tom(int(0.6 * RATE), 1.0, rng, f=(200.0, 160.0, 125.0, 95.0)[j]), t0, KIT_GAIN["tom"], 0.45 - 0.3 * j)
                self._place(buf, d_snare2(int(0.4 * RATE), 1.0, rng), b * self.bar + (S - 1) * st, 0.9, 0.0)
            elif b % 8 == 7:
                for j in (S - 2, S - 1):
                    self._place(buf, d_snare2(int(0.4 * RATE), 1.0, rng), b * self.bar + j * st, 0.6 + 0.2 * (j == S - 1), 0.0)

    # ── 층 만들기 ──
    def stems(self) -> dict:
        sp = self.spec
        rv = sp.get("reverb", [0.1, 0.7])
        prv = [rv[0] * 0.6, min(0.5, rv[1] * 0.7)]
        out = {}
        n16 = self.loop_len(self.bars)
        phases = sp["phases"]
        for i, ph in enumerate(phases):
            root, scale = self.phase_info(i)
            rng = np.random.default_rng(self.seed + i * 13)
            chords = ph["chords"]
            pre = f"{i + 1}_"
            lv = self.level(i)
            out[pre + "base"] = self.wrap(self.render_layer(ph.get("base"), chords, root, scale, self.bars, rng, rv), n16)
            kit = dict(KIT[lv])
            out[pre + "perc"] = self.wrap(self.render_layer(None, chords, root, scale, self.bars, rng, prv, perc=kit), n16)
            crisis = dict(kit, **KIT_CRISIS[lv])
            riff = next((p["riff"] for p in ph.get("base") or [] if p.get("style") == "riff"), None)
            low = [dict(inst="gtr_low", style="riff_low", gain=0.8, riff=riff)] if riff else []
            out[pre + "perc_crisis"] = self.wrap(self.render_layer(low, chords, root, scale, self.bars, rng, prv, perc=crisis), n16)
            lead = ph.get("lead") or []
            lrng = np.random.default_rng(self.seed + i * 13 + 1)
            out[pre + "lead"] = self.wrap(self.render_layer(lead, chords, root, scale, self.bars, lrng, rv), n16)
            up = [dict(p, oct=p.get("oct", 0) + 1, inst="gtr_lead_t") for p in lead]
            out[pre + "lead_oct"] = self.wrap(self.render_layer(up, chords, root, scale, self.bars, np.random.default_rng(self.seed + i * 13 + 1), rv), n16)
            out[pre + "choir"] = self.wrap(self.render_layer(ph.get("choir"), chords, root, scale, self.bars, rng, rv), n16)
            if i + 1 < len(phases):
                out[pre + "riser"] = self.riser(i, rng, rv)
        out["intro_mix"] = self.intro(rv)
        out["fail"] = self.fail_sound(rv)
        return out

    def intro(self, rv) -> np.ndarray:
        """피드백 0.5박 → 첫 박 E 파워 코드 + 크래시 + 킥 → 1마디 (끝 4칸 탐 필인 + 뮤트 리프 끌어오기)."""
        root, scale = self.phase_info(0)
        rng = np.random.default_rng(self.seed + 999)
        pick = 0.5 * self.q
        S, st = self.steps, self.step
        buf = self._buf(pick + self.bar)
        e2 = root - 12
        while e2 > 47:
            e2 -= 12
        self.note(buf, "feedback", e2 + 36, 0.0, pick, 0.5, 0.2, rng, rel=0.0)
        self.note(buf, "gtr_power", e2, pick, self.bar * 0.72, 1.0, -0.75, rng, rel=0.05)
        self.note(buf, "gtr_power", e2, pick, self.bar * 0.72, 0.95, 0.75, rng, rel=0.05)
        self.note(buf, "bass_gtr", e2 - 12, pick, self.bar * 0.7, 0.9, 0.0, rng, rel=0.05)
        self._place(buf, d_kick(int(DRUM_LEN["kick"] * RATE), 1.0, rng), pick, 1.1, 0.0)
        self._place(buf, d_crash(int(DRUM_LEN["crash"] * RATE), 1.0, rng), pick, 0.75, 0.2)
        for j in range(4):
            t0 = pick + (S - 4 + j) * st
            self._place(buf, d_tom(int(0.6 * RATE), 1.0, rng, f=(200.0, 160.0, 125.0, 95.0)[j]), t0, 0.8, 0.45 - 0.3 * j)
            self.note(buf, "gtr_mute", e2, t0, st * 0.8, 0.7 + 0.1 * j, -0.75, rng, rel=0.03)
            self.note(buf, "gtr_mute", e2, t0, st * 0.8, 0.7 + 0.1 * j, 0.75, rng, rel=0.03)
        buf = self.hall(buf, rv[0], rv[1], rng)
        n = int(round((pick + self.bar) * RATE))
        out = buf[: n + int(RATE * 0.02)].copy()
        out[n:] *= np.linspace(1, 0, len(out) - n)[:, None]
        return out[:n]

    def riser(self, i: int, rng, rv) -> np.ndarray:
        """페이즈 전환 1마디: 줄 긁어 내리기 + 탐 16분 연타(높은 → 낮은, 점점 세게) + 킥 4분 → 다음 페이즈 첫 박."""
        root, scale = self.phase_info(i)
        S, st = self.steps, self.step
        n = self.loop_len(1)
        buf = self._buf(self.bar)
        self.note(buf, "pickslide", root, 0.0, self.bar * 0.55, 0.9, -0.3, rng, rel=0.0)
        self.note(buf, "pickslide", root, 0.0, self.bar * 0.55, 0.85, 0.3, rng, rel=0.0)
        toms = (220.0, 180.0, 145.0, 110.0)
        for s in range(S):
            vel = 0.45 + 0.55 * s / (S - 1)
            self._place(buf, d_tom(int(0.5 * RATE), 1.0, rng, f=toms[s * 4 // S]), s * st, vel * KIT_GAIN["tom"], 0.45 - 0.3 * (s * 4 // S))
            if s % 4 == 0:
                self._place(buf, d_kick(int(DRUM_LEN["kick"] * RATE), 1.0, rng), s * st, 0.9, 0.0)
        self._place(buf, d_snare2(int(0.4 * RATE), 1.0, rng), (S - 1) * st, 1.0, 0.0)
        out = self.hall(buf, rv[0], rv[1], rng)[:n]
        out[-int(RATE * 0.02):] *= np.linspace(1, 0, int(RATE * 0.02))[:, None]
        return out

    def fail_sound(self, rv) -> np.ndarray:
        """실패: 파워 코드 '콰앙' 0.4초 뒤 툭 끊김 + 피드백이 1.5초에 걸쳐 사라짐."""
        root, scale = self.phase_info(0)
        rng = np.random.default_rng(self.seed + 777)
        e2 = root - 12
        while e2 > 47:
            e2 -= 12
        buf = self._buf(2.0)
        hit = self._buf(0.5)
        self.note(hit, "gtr_power", e2, 0.0, 0.42, 1.0, -0.6, rng, rel=0.0)
        self.note(hit, "gtr_power", e2, 0.0, 0.42, 1.0, 0.6, rng, rel=0.0)
        self.note(hit, "bass_gtr", e2 - 12, 0.0, 0.42, 0.9, 0.0, rng, rel=0.0)
        self._place(hit, d_kick(int(DRUM_LEN["kick"] * RATE), 1.0, rng), 0.0, 1.1, 0.0)
        self._place(hit, d_crash(int(DRUM_LEN["crash"] * RATE), 1.0, rng), 0.0, 0.7, 0.2)
        k = int(0.42 * RATE)
        hit[k:] = 0
        hit[k - int(0.008 * RATE):k] *= np.linspace(1, 0, int(0.008 * RATE))[:, None]
        buf[: len(hit)] += hit
        fb = self._buf(1.6)
        mono = g_feedback(hz(e2 + 36), int(1.5 * RATE), rng, swell=False)
        self._place(fb, mono, 0.0, 0.5, 0.15)
        buf[k:k + len(fb)] += fb[: len(buf) - k]
        n = int(2.0 * RATE)
        out = buf[:n].copy()
        out[-int(RATE * 0.05):] *= np.linspace(1, 0, int(RATE * 0.05))[:, None]
        return out
