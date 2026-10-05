"""크리스탈 트랜스 곡 (BOSS_BGM.md 엘드라시온 L08, DESIGN.md 43-23) — 결정어왕 프리시아 전용 L08-TRANCE. 스펙에 "trance": true.

boss_synth.Song 을 물려받아 층 구조·반복 이음새·마스터링은 그대로, 악기와 연주만 트랜스로 (boss_synth.py 는 그대로).
A단조 · 158 · 4/4, 잔향 1.2초.
  악기  수정 벨 주선율(boss_synth 수정 공명 + 유리 벨 겹침) · 슈퍼소(톱니 7개를 조금씩 어긋나게 — 패드 · 리드) ·
        게이트 화음(슈퍼소를 16분으로 끊어 침) · 플럭 아르페지오(톱니가 뜯자마자 필터가 닫힘) · 서브 베이스(엇박 굴림) ·
        4박 킥 · 박수 · 하이햇 · 크래시 (boss_synth) · 합창 '아—' · 오케스트라 타격(금관 + 현악 화음)
  사이드체인  킥마다 바탕·합창을 눌렀다 놓기 (Song.pump — 트랜스의 '숨 쉬는' 느낌)
  1페이즈  플럭 아르페지오 16분 + 4박 킥 + 서브 베이스, 플럭 리드가 주인의 동기
  2페이즈(어둠)  수정 벨 주선율 + 게이트 화음, 중음역 −5dB 더 (태고 방식 — 반사광만 믿는 어둠에서 신호가 잘 들리게)
  3페이즈  16마디 끝 2마디 빌드업(스네어 몰아치기 + 잡음 상승, 마지막 마디는 킥 빠짐) → 첫 박에 전체 + 합창 + 오케스트라 타격,
           슈퍼소 리드 + 수정 벨이 주인의 동기
  위기  킥 사이 16분 북 + 박수 촘촘히 / 지침: 합창이 주선율을 한 옥타브 위에서
  전환  1마디 빌드업 (스네어 16분 점점 세게 + 잡음 상승, 마지막 16분은 비움 — 다음 페이즈 첫 박이 '쾅')
  실패  전원이 꺼지듯 패드 음이 한 옥타브 아래로 미끄러지며 필터가 닫힘 + 수정이 부서지는 소리
  인트로 1마디: 잡음 상승 + 수정 벨 하강 + 스네어 몰아치기 → 1페이즈 첫 킥
"""
import numpy as np

from src.audio.boss_muhyeop import _env, _harm, _norm, _ph
from src.audio.boss_synth import (RATE, Song, _bw_filter, _t, chord_midis, d_crash, d_hat, d_kick, d_ohat, d_snap, d_snare2,
                                  degree_to_midi, hz, i_brass, i_choir_a, i_crystal, i_glass, i_strings, noise)


# ───────────────────────── 악기 ─────────────────────────

def _saw(f_t, top=9000.0):
    return _harm(f_t, [1 / k for k in range(1, 60)], top=top)


def supersaw(f, n, rng, voices=7, spread=0.012):
    """톱니 7개를 조금씩 어긋나게 (가운데 가장 크게) — 넓고 반짝이는 트랜스 소리."""
    x = np.zeros(n)
    for v in range(voices):
        d = (v - (voices - 1) / 2) / ((voices - 1) / 2) * spread / 2
        a = 1.0 if v == voices // 2 else 0.6
        ph0 = rng.uniform(0, 1)
        f_t = np.full(n, f * (1 + d))
        x += a * np.roll(_saw(f_t, top=9000), int(ph0 * RATE / f))
    return _norm(x)


def i_pad(f, n, rng, **k):
    """패드: 슈퍼소를 부드럽게 (느리게 열림)."""
    x = _bw_filter(supersaw(f, n, rng), "lp", 2800)
    return _norm(x) * _env(n, 0.25, 0.0, 0.3)


def i_gate(f, n, rng, **k):
    """게이트 화음 한 칸: 밝은 슈퍼소를 짧게."""
    x = _bw_filter(supersaw(f, n, rng, voices=5), "lp", 5200)
    return _norm(x) * _env(n, 0.003, 0.0, 0.02)


def i_lead(f, n, rng, dur=0.0, q=0.38, **k):
    """슈퍼소 리드: 밝게, 긴 음엔 늦게 드는 떨림."""
    t = _t(n)
    x = _bw_filter(supersaw(f, n, rng, spread=0.008), "lp", 6500)
    if dur >= 0.9 * q:
        x = x * (1 + 0.06 * np.sin(2 * np.pi * 5.5 * np.maximum(0, t - 0.2)))
    return _norm(x) * _env(n, 0.006, 0.0, 0.05)


def i_pluck(f, n, rng, **k):
    """플럭: 톱니를 뜯자마자 필터가 닫힘 (5kHz → 600Hz) — 반짝이는 16분 아르페지오."""
    t = _t(n)
    x = _saw(np.full(n, f), top=9000) + 0.6 * _saw(np.full(n, f * 1.005), top=9000)
    cut = 600 + 4400 * np.exp(-t * 18)
    y = np.zeros(n)
    seg = max(1, int(0.01 * RATE))
    for s in range(0, n, seg):   # 10ms 마다 필터를 다시 (닫혀 가는 필터)
        y[s:s + seg] = _bw_filter(x[max(0, s - 512):s + seg], "lp", float(cut[s]))[-len(x[s:s + seg]):]
    return _norm(y) * _env(n, 0.002, 6.0, 0.02)


def i_bell(f, n, rng, **k):
    """수정 벨: 수정 공명 + 유리 벨 겹침 (+ 맑은 사인 바닥)."""
    t = _t(n)
    x = 0.7 * i_crystal(f, n, 1.0, rng) + 0.5 * i_glass(f, n, 1.0, rng) + 0.3 * np.sin(_ph(np.full(n, f))) * np.exp(-t * 2.0)
    return _norm(x) * _env(n, 0.002, 0.0, 0.05)


def i_sub(f, n, rng, **k):
    """서브 베이스: 사인 + 약한 2배음, 짧게 (엇박 굴림)."""
    x = np.sin(_ph(np.full(n, f))) + 0.25 * np.sin(_ph(np.full(n, 2 * f)))
    return _norm(np.tanh(1.5 * x)) * _env(n, 0.003, 0.0, 0.03)


def i_choir(f, n, rng, **k):
    return i_choir_a(f, n, 1.0, rng)


def i_hit_brass(f, n, rng, **k):
    return i_brass(f, n, 1.0, rng)


def i_hit_str(f, n, rng, **k):
    return i_strings(f, n, 1.0, rng)


def s_riser(n, rng):
    """잡음 상승: 하얀 잡음이 점점 커지며 밝아짐 (빌드업)."""
    t = _t(n)
    x = noise(n, rng)
    y = np.zeros(n)
    seg = max(1, int(0.02 * RATE))
    for s in range(0, n, seg):
        fc = 400 * (12000 / 400) ** (s / n)
        y[s:s + seg] = _bw_filter(x[max(0, s - 1024):s + seg], "bp", (fc * 0.7, min(16000, fc * 1.6)))[-len(x[s:s + seg]):]
    return _norm(y) * (t / t[-1]) ** 2


def s_shatter(n, rng):
    """수정이 부서짐: 높은 유리 벨 조각이 흩어짐."""
    x = np.zeros(n)
    for _ in range(14):
        s = int(rng.uniform(0, 0.35) * RATE)
        f = rng.uniform(2200, 6500)
        m = n - s
        x[s:] += i_glass(f, m, 1.0, rng) * rng.uniform(0.3, 1.0)
    return _norm(x + _bw_filter(noise(n, rng), "hp", 5000) * np.exp(-_t(n) * 8) * 0.4)


INST = {"pad": i_pad, "gate": i_gate, "lead": i_lead, "pluck": i_pluck, "bell": i_bell, "sub": i_sub, "choir": i_choir,
        "hit_brass": i_hit_brass, "hit_str": i_hit_str}
# 타악: 이름 → (함수, 길이 초, 크기, 자리)
KIT = {"kick": (d_kick, 0.45, 0.8, 0.0), "clap": (d_snap, 0.25, 0.55, -0.05), "snare": (d_snare2, 0.35, 0.45, 0.05),
       "hat": (d_hat, 0.1, 0.22, 0.3), "ohat": (d_ohat, 0.3, 0.3, -0.3), "crash": (d_crash, 2.4, 0.3, 0.2)}


# ───────────────────────── 곡 ─────────────────────────

class TranceSong(Song):
    def note(self, buf, inst: str, midi: float, start: float, dur: float, gain=1.0, p=0.0, rng=None, rel=0.3) -> None:
        n = int((dur + rel) * RATE)
        if n <= 0:
            return
        key = (inst, round(midi, 2), n // 64)
        mono = self._cache.get(key)
        if mono is None:
            mono = INST[inst](hz(midi), n, rng, dur=dur, q=self.q).astype(np.float32)
            if len(self._cache) < 4000:
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
        mute = set(part.get("mute", []))   # 이 마디들은 쉼 (빌드업)
        if st == "arp":         # 플럭 16분 아르페지오: 화음음 위로 두 옥타브 → 아래로
            for b in range(bars):
                if b in mute:
                    continue
                cm = chord_midis(chords[b], root, scale)
                tones = [m + o for m in cm] + [m + 12 + o for m in cm]
                seq = tones + tones[-2:0:-1]
                for i in range(S):
                    self.note(buf, "pluck", seq[i % len(seq)], b * bar + i * step, step * 1.5, g * (1.0 if i % 4 == 0 else 0.7),
                              p + (0.3 if i % 2 else -0.3), rng, rel=0.05)
            return
        if st == "gate":        # 게이트 화음: 슈퍼소 화음을 칸마다 끊어 침 (pattern)
            pat = part.get("pattern", "x.xxx.xxx.xxx.xx")[:S]
            for b in range(bars):
                if b in mute:
                    continue
                cm = chord_midis(chords[b], root, scale) + [chord_midis(chords[b], root, scale)[0] + 12]
                for i, ch in enumerate(pat):
                    if ch in "xX":
                        for j, m in enumerate(cm):
                            self.note(buf, "gate", m + o, b * bar + i * step, step * 0.55, g * (1.0 if i % 4 == 0 else 0.75),
                                      p + (j - 1.5) * 0.3, rng, rel=0.02)
            return
        if st == "sub":         # 서브 베이스 엇박 굴림: 박마다 '.xxx'
            pat = part.get("pattern", ".xxx" * (S // 4))[:S]
            for b in range(bars):
                if b in mute:
                    continue
                r = chord_midis(chords[b], root, scale)[0] - 24 + o
                for i, ch in enumerate(pat):
                    if ch in "xX":
                        self.note(buf, "sub", r, b * bar + i * step, step * 0.85, g, 0.0, rng, rel=0.02)
            return
        if st == "pad":         # 패드 화음 (화음이 바뀔 때마다)
            for b in range(bars):
                if b in mute:
                    continue
                for j, m in enumerate(chord_midis(chords[b], root, scale)):
                    self.note(buf, "pad", m + o, b * bar, bar * 0.98, g * (1.0 if j == 0 else 0.8), p + (j - 1) * 0.5, rng, rel=0.25)
            return
        if st == "orch_hits":   # 오케스트라 타격: 마디 첫 박 금관 + 현악 화음 (every 마디마다)
            ev = part.get("every", 4)
            for b in range(0, bars, ev):
                if b in mute:
                    continue
                for j, m in enumerate(chord_midis(chords[b], root, scale)):
                    self.note(buf, "hit_brass", m - 12 + o, b * bar, step * 3, g, (j - 1) * 0.35, rng, rel=0.25)
                    self.note(buf, "hit_str", m + o, b * bar, step * 3, g * 0.7, -(j - 1) * 0.35, rng, rel=0.25)
            return
        if st == "riser":       # 빌드업 잡음 상승 (bars 목록의 마디 동안)
            for b0, b1 in part.get("spans", []):
                if b0 >= bars:
                    continue
                L = (b1 - b0) * bar
                self._place(buf, s_riser(int(L * RATE), rng), b0 * bar, g, 0.0)
            return
        if st == "choir_hold":  # 합창 '아—' 화음 (2마디마다)
            b = 0
            while b < bars:
                e = min(bars, b + 2)
                if b not in mute:
                    for j, m in enumerate(chord_midis(chords[b], root, scale)):
                        self.note(buf, "choir", m + o, b * bar, (e - b) * bar * 0.96, g * (1.0 if j == 0 else 0.8), p + (j - 1) * 0.5, rng, rel=0.3)
                b = e
            return
        super().render_part(buf, part, chords, root, scale, bars, rng, crescendo)

    def render_perc(self, buf, pattern: dict, bars: int, rng, crescendo=False, root=None) -> None:
        """pattern = {타악 이름: 16칸 (또는 마디마다 돌아가는 목록)}."""
        for kind, pat in pattern.items():
            pats = pat if isinstance(pat, list) else [pat]
            for b in range(bars):
                for i, ch in enumerate(pats[b % len(pats)][: self.steps]):
                    if ch in "xX":
                        self.drum(buf, kind, b * self.bar + i * self.step, 1.0 if ch == "X" else 0.7, rng)

    def kicks(self, pattern: dict, bars: int) -> list:
        pats = pattern.get("kick", "")
        pats = pats if isinstance(pats, list) else [pats]
        return [b * self.bar + i * self.step for b in range(bars) for i, ch in enumerate(pats[b % len(pats)][: self.steps]) if ch in "xX"]

    # ── 층 만들기 ──
    def stems(self) -> dict:
        sp = self.spec
        rv = sp.get("reverb", [0.18, 1.2])
        prv = [rv[0] * 0.5, rv[1] * 0.6]
        out = {}
        n16 = self.loop_len(self.bars)
        phases = sp["phases"]
        for i, ph in enumerate(phases):
            root, scale = self.phase_info(i)
            rng = np.random.default_rng(self.seed + i * 13)
            chords = ph["chords"]
            pre = f"{i + 1}_"
            dark = ph.get("mid_cut_extra", 0.0)
            pat = ph["perc"]["pattern"]
            kicks = self.kicks(pat, self.bars)
            depth = ph.get("pump", 0.45)

            def lay(parts, perc=None, r=rv, g=None, pump=False):
                x = self.wrap(self.render_layer(parts, chords, root, scale, self.bars, g if g is not None else rng, r, perc=perc), n16)
                if pump and kicks:
                    x = self.pump(x, kicks, depth)   # 킥마다 눌렀다 놓기
                if dark:
                    from src.audio.boss_synth import peaking_eq
                    x = peaking_eq(x, 1732.0, dark, 0.9)
                return x
            out[pre + "base"] = lay(ph.get("base"), pump=True)
            out[pre + "perc"] = lay(None, pat, prv)
            out[pre + "perc_crisis"] = lay(None, dict(pat, **ph["perc"].get("crisis", {})), prv)
            lead = ph.get("lead") or []
            out[pre + "lead"] = lay(lead, g=np.random.default_rng(self.seed + i * 13 + 1))
            mel = sorted({(b, at): [b, at, d, ln] for pt in lead for b, at, d, ln in pt["notes"]}.values())
            up = [dict(pt, gain=pt.get("gain", 1.0) * 0.7) for pt in lead] + \
                 [dict(inst="choir", style="melody", gain=ph.get("tired_choir", 1.3), oct=1, notes=mel)]
            out[pre + "lead_oct"] = lay(up, g=np.random.default_rng(self.seed + i * 13 + 1))   # 지침: 합창이 한 옥타브 위
            out[pre + "choir"] = lay(ph.get("choir"), pump=True)
            if i + 1 < len(phases):
                out[pre + "riser"] = self.riser(i, rng, rv)
        out["intro_mix"] = self.intro(rv)
        out["fail"] = self.fail_sound(rv)
        return out

    def build(self, buf, at: float, L: float, rng, root: int) -> None:
        """빌드업 L초: 스네어 16분 점점 세게 + 잡음 상승 + 플럭이 한 음씩 올라감, 마지막 16분은 비움."""
        S = int(round(L / self.step))
        for s in range(S - 1):
            u = s / max(1, S - 2)
            self.drum(buf, "snare", at + s * self.step, 0.35 + 0.65 * u, rng)
            if s % 2 == 0:
                self.note(buf, "pluck", root + 12 + s // 2, at + s * self.step, self.step * 1.5, 0.25 + 0.3 * u, 0.3 * ((-1) ** s), rng, rel=0.03)
        self._place(buf, s_riser(int((L - self.step) * RATE), rng), at, 0.5, 0.0)

    def intro(self, rv) -> np.ndarray:
        """1마디: 잡음 상승 + 수정 벨 하강(A단조 두 옥타브) + 스네어 몰아치기 → 1페이즈 첫 킥."""
        root, scale = self.phase_info(0)
        rng = np.random.default_rng(self.seed + 999)
        buf = self._buf(self.bar)
        self.build(buf, 0.0, self.bar, rng, root)
        for j in range(8):
            m = degree_to_midi(15 - j * 2, root, scale)
            self.note(buf, "bell", m, j * self.bar / 8, self.bar / 8, 0.25, 0.4 * ((-1) ** j), rng, rel=0.2)
        buf = self.hall(buf, rv[0], rv[1], rng)
        n = self.loop_len(1)
        out = buf[: n + int(RATE * 0.02)].copy()
        out[n:] *= np.linspace(1, 0, len(out) - n)[:, None]
        return out[:n]

    def riser(self, i: int, rng, rv) -> np.ndarray:
        """페이즈 전환 1마디 빌드업 (다음 페이즈 첫 박이 '쾅')."""
        root, scale = self.phase_info(i + 1)
        n = self.loop_len(1)
        buf = self._buf(self.bar)
        self.build(buf, 0.0, self.bar, rng, root)
        self.note(buf, "pad", root, 0.0, self.bar * 0.9, 0.25, 0.0, rng, rel=0.05)
        out = self.hall(buf, rv[0], rv[1], rng)[:n]
        out[-int(RATE * 0.02):] *= np.linspace(1, 0, int(RATE * 0.02))[:, None]
        return out

    def fail_sound(self, rv) -> np.ndarray:
        """실패: 전원이 꺼지듯 — 패드 화음이 한 옥타브 아래로 미끄러지며 필터가 닫힘 + 수정이 부서짐 + 킥."""
        root, scale = self.phase_info(0)
        rng = np.random.default_rng(self.seed + 777)
        L = 2.2
        n = int(L * RATE)
        t = _t(n)
        drop = 2 ** (-12 * np.clip(t / 1.2, 0, 1) ** 2 / 12)
        x = np.zeros(n)
        for m in chord_midis(1, root, scale):
            x += _saw(hz(m) * drop, top=6000)
        y = np.zeros(n)
        seg = int(0.02 * RATE)
        for s in range(0, n, seg):
            fc = max(150.0, 4000 * (1 - s / n) ** 2)
            y[s:s + seg] = _bw_filter(x[max(0, s - 1024):s + seg], "lp", fc)[-len(x[s:s + seg]):]
        y = _norm(y) * np.clip(1 - t / 1.6, 0, 1) ** 1.2
        buf = self._buf(L)
        self._place(buf, y, 0.0, 0.6, 0.0)
        self._place(buf, s_shatter(int(1.2 * RATE), rng), 0.0, 0.35, 0.2)
        self.drum(buf, "kick", 0.0, 1.0, rng)
        buf = self.hall(buf, rv[0], rv[1], rng)
        out = buf[:n].copy()
        out[-int(RATE * 0.05):] *= np.linspace(1, 0, int(RATE * 0.05))[:, None]
        return out
