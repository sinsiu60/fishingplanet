"""재즈 빅밴드 전투 곡 (SHARMION_THEMES.md 1장, DESIGN.md 43-16) — 황금잉어 '여우비' 전용 L01-JAZZ. 스펙에 "jazz": true.

boss_synth.Song 을 물려받아 층 구조·반복 이음새·마스터링은 그대로, 악기와 연주만 재즈 빅밴드로 (boss_synth.py 는 그대로).
D단조 · 176 · 4/4 스윙 (8분음표를 길게-짧게 = 박을 셋으로 나눈 2:1). 리듬 칸 = 한 박 3칸 (마디 12칸).
  악기  약음기 트럼펫(하몬 뮤트: 코맹맹이 중고음) · 색소폰 섹션 · 트롬본 · 피아노(짧은 화음 엇박) · 콘트라베이스(워킹) ·
        재즈 드럼(라이드 스윙 · 하이햇 2·4박 · 브러시/스틱 스네어 끼워 넣기 · 킥 강세 · 크래시)
  바탕  워킹 베이스 (1페이즈 4분 · 2·3페이즈 스윙 8분) + 피아노 짧은 화음 엇박
  주선율 1페이즈 약음기 트럼펫(주인의 동기로 시작) / 2페이즈 트럼펫 ↔ 색소폰 2박씩 주고받기 /
        3페이즈 약음기 뺀 트럼펫 + 색소폰 3도 아래
  합창 자리 금관 섹션 찌르기 (2페이즈 엇박 / 3페이즈 매 마디 + 크게)
  3페이즈 '속임수': 8마디마다 끝 2박 동안 밴드 전체가 뚝 멈췄다가(끝난 척) 다음 마디 첫 박 심벌 '촤앙'과 함께 다시 터짐
         — 음악 층 안에서만 (게임 진행·신호·예고와는 무관)
  위기  금관 찌르기 매 마디 + 킥 강세 늘어남 (위기 타악 층에) / 지침: 트럼펫 한 옥타브 위
  전환  드럼 필인 + 트럼펫 높은 음 '삐이-' / 실패: 트롬본 '와와와와—' 축 처지는 소리 뒤 정지
  인트로 빗소리 → 브러시 스네어 '쓰윽' → 금관 '빠밤!' (1마디)
"""
import numpy as np

from src.audio.boss_muhyeop import _env, _harm, _norm, _vib
from src.audio.boss_rock import d_ride
from src.audio.boss_synth import (RATE, Song, _bw_filter, _t, chord_midis, d_crash, d_hat, d_kick, d_snare2, degree_to_midi, hz,
                                  noise, peaking_eq)


# ───────────────────────── 악기 ─────────────────────────

def _saw(f_t, top=8000.0, p=1.0):
    return _harm(f_t, [1 / k ** p for k in range(1, 40)], top=top)


def i_trumpet(f, n, rng, dur=0.0, q=0.34, mute=True, **k):
    """트럼펫: 아래에서 살짝 밀어 올리는 시작, 긴 음엔 늦게 드는 떨림. mute = 하몬 약음기(코맹맹이)."""
    t = _t(n)
    semi = -0.5 * np.exp(-t / 0.03)
    if dur >= 0.9 * q:
        semi += _vib(t, 0.25, 0.22, 5.8, 0.25)
    f_t = f * 2 ** (semi / 12)
    x = _saw(f_t, top=9000)
    if mute:
        x = peaking_eq(_bw_filter(_bw_filter(x, "hp", 650), "lp", 4800), 1750.0, 12.0, 2.0)
        x = np.tanh(1.6 * _norm(x))
    else:
        bright = np.clip(t / 0.05, 0, 1)
        x = np.tanh(2.0 * _norm(peaking_eq(_bw_filter(x, "lp", 6500), 1300.0, 3.0, 0.9))) * (0.7 + 0.3 * bright)
    return _norm(x) * _env(n, 0.02, 0.15, 0.05)


def i_trumpet_open(f, n, rng, **k):
    return i_trumpet(f, n, rng, **dict(k, mute=False))


def i_sax(f, n, rng, dur=0.0, q=0.34, **k):
    """색소폰: 리드 떨림(홀수 배음 강조) + 두 모음 울림 + 숨, 긴 음엔 떨림."""
    t = _t(n)
    semi = -0.4 * np.exp(-t / 0.04)
    if dur >= 0.9 * q:
        semi += _vib(t, 0.2, 0.28, 5.4, 0.25)
    f_t = f * 2 ** (semi / 12)
    x = _harm(f_t, [(1.0 if k_ % 2 else 0.7) / k_ ** 0.9 for k_ in range(1, 30)], top=7000)
    x = peaking_eq(peaking_eq(x, 560.0, 6.0, 1.0), 1600.0, 5.0, 1.2)
    x += _bw_filter(noise(n, rng), "bp", (1500, 6000)) * 0.08
    x = np.tanh(1.5 * _norm(_bw_filter(x, "lp", 5500)))
    return _norm(x) * _env(n, 0.03, 0.12, 0.05)


def i_trombone(f, n, rng, dur=0.0, wah=False, **k):
    """트롬본: 둥근 낮은 금관. wah = 플런저 뮤트로 '와—와—' (실패음)."""
    t = _t(n)
    x = _saw(np.full(n, f), top=5000)
    if wah:
        cut = 400 + 1600 * (0.5 + 0.5 * np.sin(2 * np.pi * 2.4 * t - 1.5))   # 막았다 열었다
        out = np.zeros(n)
        seg = 512
        for s in range(0, n, seg):
            e = min(n, s + seg + 256)
            out[s:min(n, s + seg)] = _bw_filter(x[s:e], "lp", float(cut[s]))[: min(seg, n - s)]
        x = out
    else:
        x = _bw_filter(x, "lp", 2400)
    return _norm(np.tanh(1.3 * _norm(x))) * _env(n, 0.04, 0.1, 0.06)


def i_piano(f, n, rng, **k):
    """피아노: 살짝 늘어난 배음 + 두 줄 맥놀이 + 해머 소리, 높은 배음부터 빨리 사라짐."""
    t = _t(n)
    x = np.zeros(n)
    for kk in range(1, 14):
        fk = f * kk * (1 + 0.0004 * kk * kk)
        if fk > 9000:
            break
        a = 1.0 / kk ** 1.1
        for det in (1.0, 1.0012):
            x += a * np.sin(2 * np.pi * fk * det * t + kk) * np.exp(-t * (1.2 + 0.45 * kk))
    m = min(n, int(0.006 * RATE))
    x[:m] += _bw_filter(noise(m, rng), "bp", (800, 4000)) * 0.4
    return _norm(x) * _env(n, 0.002, 0.4, 0.04)


def i_upright(f, n, rng, **k):
    """콘트라베이스: 손가락으로 튕긴 둥근 저음 + 줄 소리."""
    x = _harm(np.full(n, f), [1.0, 0.55, 0.3, 0.15, 0.08], decay=1.8)
    m = min(n, int(0.01 * RATE))
    x[:m] += _bw_filter(noise(m, rng), "bp", (300, 1500)) * np.exp(-np.arange(m) / (m / 4)) * 0.6
    return _norm(_bw_filter(x, "lp", 1600)) * _env(n, 0.004, 2.6, 0.04)


def d_brush(n, vel, rng, swish=True):
    """브러시 스네어 '쓰윽' (swish) / 짧은 톡."""
    t = _t(n)
    x = _bw_filter(noise(n, rng), "bp", (2000, 9000))
    if swish:
        e = np.sin(np.pi * np.clip(t / t[-1], 0, 1)) ** 1.5
    else:
        e = np.exp(-t * 45)
    return x * e * 0.8


def s_rain(n, rng):
    """빗소리 (작게 쏴—, 드문 물방울)."""
    t = _t(n)
    x = _bw_filter(noise(n, rng), "bp", (1500, 7000)) * 0.35
    for _ in range(int(n / RATE * 25)):
        p = int(rng.uniform(0, n - 400))
        x[p:p + 300] += np.sin(2 * np.pi * rng.uniform(1500, 4000) * _t(300)) * np.exp(-_t(300) * 60) * 0.3
    return x * np.minimum(1, t / 0.2)


def s_coin(n, rng, big=False):
    """금화: '띵' (big = 여러 개 '짤랑')."""
    t = _t(n)
    out = np.zeros(n)
    hits = [(0.0, 1.0)] if not big else [(0.0, 1.0), (0.05, 0.7), (0.09, 0.8), (0.16, 0.6), (0.22, 0.5), (0.3, 0.4)]
    for at, a in hits:
        s = int(at * RATE)
        if s >= n:
            continue
        tt = _t(n - s)
        base = rng.uniform(2600, 3400)
        ring = sum(b * np.sin(2 * np.pi * base * r * tt) * np.exp(-tt * d) for r, b, d in ((1.0, 1.0, 6), (2.76, 0.5, 9), (5.4, 0.25, 14)))
        out[s:] += ring * a
    return _norm(out) * np.minimum(1, t / 0.002)


INST = {"trumpet": i_trumpet, "trumpet_open": i_trumpet_open, "sax": i_sax, "trombone": i_trombone, "piano": i_piano,
        "upright": i_upright}
KIT_GAIN = {"kick": 0.48, "ride": 0.44, "hat": 0.32, "snare": 0.38, "brush": 0.45, "crash": 0.5}


def swing(beat: float) -> float:
    """스윙: 박 안의 8분 뒷박(0.5)을 2/3 자리로 (길게-짧게)."""
    b = int(beat)
    f = beat - b
    if abs(f - 0.5) < 1e-6:
        return b + 2 / 3
    if abs(f - 0.25) < 1e-6:
        return b + 1 / 3
    if abs(f - 0.75) < 1e-6:
        return b + 5 / 6
    return beat


# ───────────────────────── 곡 ─────────────────────────

class JazzSong(Song):
    CELLS = 12   # 한 박 3칸 (셋잇단 격자)

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

    def cell(self) -> float:
        return self.bar / self.CELLS

    def voicing(self, c, root, scale) -> list:
        """재즈 화음 (7화음, 가운데 음역)."""
        ms = chord_midis(c, root, scale, 4)
        out = []
        for m in ms:
            while m < root - 3:
                m += 12
            while m > root + 11:
                m -= 12
            out.append(m)
        return sorted(out)

    def render_part(self, buf, part: dict, chords: list, root: int, scale: str, bars: int, rng, crescendo=False) -> None:
        st = part.get("style")
        g, o, p = part.get("gain", 1.0), 12 * part.get("oct", 0), part.get("pan", 0.0)
        bar, c = self.bar, self.cell()
        if st == "walk":       # 워킹 베이스: eighth=False 4분 / True 스윙 8분
            eighth = part.get("eighth", False)
            for b in range(bars):
                r = chord_midis(chords[b], root, scale)[0] - 24 + o
                while r < 36:
                    r += 12
                tones = chord_midis(chords[b], root, scale, 4)
                tones = [t_ - 24 + o + (12 if t_ - 24 + o < r else 0) for t_ in tones]
                nxt = chord_midis(chords[(b + 1) % bars], root, scale)[0] - 24 + o
                while nxt < 36:
                    nxt += 12
                line = [r, tones[1], tones[2], nxt + (1 if rng.random() < 0.5 else -1)]   # 마지막은 다음 으뜸음 반음 옆
                for i, m in enumerate(line):
                    self.note(buf, "upright", m, b * bar + i * 3 * c, 3 * c * 0.92, g * (1.0 if i == 0 else 0.85), p, rng, rel=0.06)
                    if eighth and rng.random() < 0.55:   # 스윙 8분 사이 음 (뒷박)
                        mm = m + rng.choice((-2, -1, 2, 3, 7))
                        self.note(buf, "upright", mm, b * bar + (i * 3 + 2) * c, c * 0.9, g * 0.6, p, rng, rel=0.05)
            return
        if st == "comp":       # 피아노 짧은 화음 엇박 (찰스턴 · 뒷박)
            pats = part.get("pats", [[0, 5], [2, 8], [5, 11], [0, 8]])
            for b in range(bars):
                vo = self.voicing(chords[b], root, scale)
                for i in pats[(b + rng.integers(0, 2)) % len(pats)]:
                    for j, m in enumerate(vo):
                        self.note(buf, "piano", m + o, b * bar + i * c + 0.004 * j, c * 1.2, g * (0.8 if j else 1.0), p + (j - 1.5) * 0.12,
                                  rng, rel=0.12)
            return
        if st == "stabs":      # 금관 섹션 찌르기 (트럼펫·색소폰·트롬본 한꺼번에)
            pats = part.get("pats", [[5, 11]])
            every = part.get("every", 1)
            for b in range(bars):
                if b % every:
                    continue
                vo = self.voicing(chords[b], root, scale)
                for i in pats[b % len(pats)]:
                    ln = part.get("len", 1.4) * c
                    for j, m in enumerate(vo):
                        self.note(buf, ("trumpet_open", "sax", "sax", "trumpet_open")[j % 4], m + 12 + o, b * bar + i * c, ln, g * 0.5, -0.4 + 0.27 * j, rng, rel=0.08)
                    self.note(buf, "trombone", vo[0] - 12 + o, b * bar + i * c, ln, g * 0.6, 0.0, rng, rel=0.08)
            return
        if st == "melody":
            inst = part["inst"]
            for b, at, deg, ln in part["notes"]:
                if b >= bars:
                    continue
                m = degree_to_midi(deg, root, scale) + o
                s0 = swing(at)
                e0 = swing(at + ln) if ln < 1 else at + ln
                self.note(buf, inst, m, b * bar + s0 * self.q, max(0.05, (e0 - s0)) * self.q * 0.92, g, p, rng, rel=0.1)
            return
        super().render_part(buf, part, chords, root, scale, bars, rng, crescendo)

    def render_perc(self, buf, pattern: dict, bars: int, rng, crescendo=False, root=None) -> None:
        """재즈 드럼 (12칸 스윙 격자): 라이드 '딩 딩-가 딩' · 하이햇 2·4박 · 스네어 끼워 넣기(comp 개수) · 킥 깃털 + 강세.
        pattern: ride/hat/kick 칸 문자열(12), comp = 마디당 스네어 개수, brush = 브러시, crash = 몇 마디마다, fill = 8마디 끝 필인."""
        c = self.cell()
        for b in range(bars):
            t0 = b * self.bar
            for k in ("ride", "hat", "kick"):
                for i, ch in enumerate(pattern.get(k, "")[:12]):
                    if ch not in "xX":
                        continue
                    vel = 1.0 if ch == "X" else 0.7
                    if k == "ride":
                        mono = d_ride(int(1.2 * RATE), vel, rng)
                    elif k == "hat":
                        mono = d_hat(int(0.1 * RATE), vel, rng)
                    else:
                        mono = d_kick(int(0.45 * RATE), vel, rng)
                    self._place(buf, mono, t0 + i * c, vel * KIT_GAIN[k], {"ride": -0.3, "hat": 0.3}.get(k, 0.0))
            for _ in range(pattern.get("comp", 0)):   # 스네어 끼워 넣기 (스윙 뒷박)
                i = int(rng.choice([2, 5, 8, 11]))
                if pattern.get("brush"):
                    self._place(buf, d_brush(int(0.12 * RATE), 1.0, rng, swish=False), t0 + i * c, KIT_GAIN["brush"] * 0.7, 0.1)
                else:
                    self._place(buf, d_snare2(int(0.3 * RATE), 1.0, rng), t0 + i * c, KIT_GAIN["snare"] * rng.uniform(0.4, 0.8), 0.1)
            ce = pattern.get("crash", 0)
            if ce and b % ce == 0:
                self._place(buf, d_crash(int(2.6 * RATE), 1.0, rng), t0, KIT_GAIN["crash"], 0.25)
            if pattern.get("fill") and b % 8 == 7:   # 8마디 끝 필인: 스네어 셋잇단
                for j in range(6):
                    self._place(buf, d_snare2(int(0.3 * RATE), 1.0, rng), t0 + (6 + j) * c, KIT_GAIN["snare"] * (0.5 + 0.1 * j), 0.0)

    # ── 3페이즈 '속임수' 멈춤 ──
    def breaks(self, phase: int) -> list:
        """(시작, 끝) 초 — 3페이즈: 8마디마다 끝 2박 (7·15마디 3~4박)."""
        if not self.spec["phases"][phase].get("fake_stop"):
            return []
        return [((b + 0.5) * self.bar, (b + 1) * self.bar) for b in range(7, self.bars, 8)]

    def apply_breaks(self, x: np.ndarray, br: list) -> np.ndarray:
        if not br:
            return x
        m = np.ones(len(x))
        f = int(0.012 * RATE)
        for a, b in br:
            s, e = int(a * RATE), int(b * RATE)
            m[s:e] = 0.0
            m[max(0, s - f):s] = np.minimum(m[max(0, s - f):s], np.linspace(1, 0, s - max(0, s - f)))
        return x * m[:, None]

    # ── 층 만들기 ──
    def stems(self) -> dict:
        sp = self.spec
        rv = sp.get("reverb", [0.14, 0.8])
        prv = [rv[0] * 0.7, rv[1] * 0.7]
        out = {}
        n16 = self.loop_len(self.bars)
        phases = sp["phases"]
        for i, ph in enumerate(phases):
            root, scale = self.phase_info(i)
            rng = np.random.default_rng(self.seed + i * 13)
            chords = ph["chords"]
            pre = f"{i + 1}_"
            br = self.breaks(i)

            def lay(parts, perc=None, r=rv, seed=None):
                g = rng if seed is None else np.random.default_rng(seed)
                buf = self.render_layer(parts, chords, root, scale, self.bars, g, r, perc=perc)
                return self.wrap(self.apply_breaks(buf[: n16 + int(RATE * 6)], br), n16)
            out[pre + "base"] = lay(ph.get("base"))
            perc = ph["perc"]
            def crash_after(buf):   # 멈춤 뒤 다음 마디 첫 박 심벌 '촤앙' (멈춤 밖이라 지워지지 않음)
                for _a, e in br:
                    s0 = int(round(e * RATE)) % n16
                    hit = d_crash(int(2.6 * RATE), 1.0, rng) * KIT_GAIN["crash"] * 1.3
                    k = min(len(hit), n16 - s0)
                    buf[s0:s0 + k] += hit[:k, None] * 0.7
                    self._place(buf, d_kick(int(0.45 * RATE), 1.0, rng), s0 / RATE, KIT_GAIN["kick"] * 1.3, 0.0)
                return buf
            out[pre + "perc"] = crash_after(lay(None, perc["pattern"], prv))
            crisis = dict(perc["pattern"], **perc.get("crisis", {}))
            stabs = [dict(inst="trumpet_open", style="stabs", gain=0.35, pats=[[0, 5, 11]], len=1.2)]
            out[pre + "perc_crisis"] = crash_after(lay(stabs, crisis, prv))
            lead = ph.get("lead") or []
            out[pre + "lead"] = lay(lead, seed=self.seed + i * 13 + 1)
            up = [dict(p, oct=p.get("oct", 0) + 1) for p in lead]
            out[pre + "lead_oct"] = lay(up, seed=self.seed + i * 13 + 1)
            out[pre + "choir"] = lay(ph.get("choir"))
            if i + 1 < len(phases):
                out[pre + "riser"] = self.riser(i, rng, rv)
        out["intro_mix"] = self.intro(rv)
        out["fail"] = self.fail_sound(rv)
        return out

    def intro(self, rv) -> np.ndarray:
        """1마디: 빗소리 → 브러시 '쓰윽' → 마디 끝 금관 '빠밤!' (빠- 한 박 앞 뒷박 + 밤 마지막 박)."""
        root, scale = self.phase_info(0)
        rng = np.random.default_rng(self.seed + 999)
        c = self.cell()
        buf = self._buf(self.bar)
        self._place(buf, s_rain(int((self.bar + 0.5) * RATE), rng), 0.0, 0.35, -0.2)
        self._place(buf, d_brush(int(0.5 * RATE), 1.0, rng), 0.05, 0.8, 0.15)
        self._place(buf, d_brush(int(0.35 * RATE), 1.0, rng), 4 * c, 0.6, -0.1)
        vo = self.voicing(1, root, scale)
        for at, ln, g in ((8 * c, 1.0 * c, 0.75), (9 * c, 2.6 * c, 1.0)):   # 빠- 밤!
            for j, m in enumerate(vo):
                self.note(buf, ("trumpet_open", "sax", "sax", "trumpet_open")[j], m + 12, at, ln, g * 0.5, -0.4 + 0.27 * j, rng, rel=0.06)
            self.note(buf, "trombone", vo[0] - 12, at, ln, g * 0.6, 0.0, rng, rel=0.06)
            self._place(buf, d_kick(int(0.45 * RATE), 1.0, rng), at, KIT_GAIN["kick"] * 1.2 * g, 0.0)
        self._place(buf, d_snare2(int(0.3 * RATE), 1.0, rng), 9 * c, KIT_GAIN["snare"], 0.0)
        buf = self.hall(buf, rv[0], rv[1], rng)
        n = self.loop_len(1)
        out = buf[: n + int(RATE * 0.02)].copy()
        out[n:] *= np.linspace(1, 0, len(out) - n)[:, None]
        return out[:n]

    def riser(self, i: int, rng, rv) -> np.ndarray:
        """페이즈 전환 1마디: 드럼 필인(스네어·탐 셋잇단 몰아치기) + 트럼펫 높은 음 '삐이-'."""
        root, scale = self.phase_info(i + 1)
        n = self.loop_len(1)
        c = self.cell()
        buf = self._buf(self.bar)
        for j in range(12):
            self._place(buf, d_snare2(int(0.3 * RATE), 1.0, rng), j * c, KIT_GAIN["snare"] * (0.35 + 0.65 * j / 11), 0.1 * (-1) ** j)
            if j % 3 == 0:
                self._place(buf, d_kick(int(0.45 * RATE), 1.0, rng), j * c, KIT_GAIN["kick"], 0.0)
        hi = degree_to_midi(8, root, scale) + 12   # D6 '삐이-'
        self.note(buf, "trumpet_open", hi, 3 * c, 8 * c, 0.55, 0.1, rng, rel=0.1)
        out = self.hall(buf, rv[0], rv[1], rng)[:n]
        out[-int(RATE * 0.02):] *= np.linspace(1, 0, int(RATE * 0.02))[:, None]
        return out

    def fail_sound(self, rv) -> np.ndarray:
        """실패: 트롬본 '와와와와—' (반음씩 축 처지며 내려감) 뒤 정지."""
        root, scale = self.phase_info(0)
        rng = np.random.default_rng(self.seed + 777)
        buf = self._buf(2.2)
        m0 = root - 12 + 3
        for j, (at, ln) in enumerate(((0.0, 0.32), (0.36, 0.32), (0.72, 0.32), (1.08, 0.85))):
            x = i_trombone(hz(m0 - j), int((ln + 0.05) * RATE), rng, wah=True)
            if j == 3:   # 마지막 음은 처지며 더 내려감
                x = x * np.linspace(1, 0.2, len(x))
            self._place(buf, x, at, 0.8, 0.0)
        buf = self.hall(buf, rv[0], rv[1], rng)
        n = int(2.2 * RATE)
        out = buf[:n].copy()
        out[-int(RATE * 0.05):] *= np.linspace(1, 0, int(RATE * 0.05))[:, None]
        return out
