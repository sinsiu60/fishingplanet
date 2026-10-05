"""바로크 질주 곡 (BOSS_BGM.md 엘드라시온 L09, DESIGN.md 43-24) — 천공어 에어리스 전용 L09-BAROQUE. 스펙에 "baroque": true.

boss_synth.Song 을 물려받아 층 구조·반복 이음새·마스터링은 그대로, 악기와 연주만 '하늘 성당 토카타'로 (boss_synth.py 는 그대로).
E단조 · 172 · 4/4, 잔향 1.2초. 화성은 바로크 5도권 진행(i–iv–VII–III–VI–ii°–V–i).
  악기  하프시코드(깃촉으로 뜯는 현 — 8' + 4' 두 벌, 높은 배음일수록 빨리 사라짐, 뜯는 '틱') ·
        파이프 오르간 · 페달 (boss_organ) · 바로크 트럼펫 (boss_jazz 약음기 없는 트럼펫) · 현악 합주 · 콘트라베이스 · 합창 · 팀파니 (boss_synth)
  바탕  하프시코드 16분 쉼 없는 분산화음 (토카타) + 콘트라베이스 8분 (통주저음)
  1페이즈  하프시코드 질주 — 하프시코드 높은 성부가 주인의 동기
  2페이즈  현악 합주(16분 스피카토 + 긴 화음) + 트럼펫 주선율 (현악이 한 옥타브 아래서 같이)
  3페이즈  파이프 오르간 전체 화음 + 페달 + 합창 '아—' + 트럼펫 · 오르간이 주선율, 크래시 4마디마다
  위기  팀파니 16분 연타 + 큰북 / 지침: 합창이 주선율을 한 옥타브 위에서
  전환  하프시코드 32분 상승 질주 + 팀파니 굴림 (2→3 은 오르간 하강 음형 + 페달)
  실패  하프시코드가 줄을 긁어 내리는 소리 + 오르간 화음이 무너지듯 낮아지며 사라짐 + 팀파니
  인트로 1마디: 팀파니 굴림 + 하프시코드 하강 질주 → 1페이즈 첫 박
"""
import numpy as np

from src.audio import boss_jazz, boss_organ
from src.audio import boss_synth as bs
from src.audio.boss_muhyeop import _env, _harm, _norm
from src.audio.boss_synth import RATE, Song, _bw_filter, _t, chord_midis, degree_to_midi, hz, noise


# ───────────────────────── 악기 ─────────────────────────

def i_harpsichord(f, n, rng, **k):
    """하프시코드: 깃촉으로 뜯은 현 — 8' (기본) + 4' (옥타브 위) 두 벌, 배음이 많고 높은 배음일수록 빨리 사라짐 + 뜯는 '틱'."""
    t = _t(n)
    amps = [1 / kk ** 0.55 for kk in range(1, 34)]
    x = _harm(np.full(n, f * (1 + rng.uniform(-4e-4, 4e-4))), amps, decay=0.45, top=10000)
    x += 0.45 * _harm(np.full(n, 2 * f * 1.0015), amps[:16], decay=0.6, top=10000)
    m = min(n, int(0.005 * RATE))
    x[:m] += _bw_filter(noise(m, rng), "bp", (2500, 8000)) * 0.6
    x = _bw_filter(x, "hp", 90)
    return _norm(x) * _env(n, 0.001, 1.6 + f / 900, 0.03) * np.minimum(1, t / 0.0015)


def _orch(name):
    fn = bs.INST[name]
    return lambda f, n, rng, dur, q: fn(f, n, 1.0, rng)


INST = {k: _orch(k) for k in ("strings", "spiccato", "bass", "choir", "choir_a")}
INST.update({
    "harpsichord": lambda f, n, rng, dur, q: i_harpsichord(f, n, rng),
    "trumpet": lambda f, n, rng, dur, q: boss_jazz.i_trumpet_open(f, n, rng, dur=dur, q=q),
    "organ": lambda f, n, rng, dur, q: boss_organ.pipe(f, n, rng),
    "organ_full": lambda f, n, rng, dur, q: boss_organ.pipe(f, n, rng, full=True),
    "pedal": lambda f, n, rng, dur, q: boss_organ.i_pedal(f, n, rng),
})
# 타악: 이름 → (함수(n, vel, rng), 길이 초, 크기, 자리)
KIT = {"timp": (None, 1.4, 0.75, 0.0), "big": (bs.d_bigdrum, 1.2, 0.6, 0.0), "snare": (bs.d_snare2, 0.35, 0.32, 0.1),
       "crash": (bs.d_crash, 2.2, 0.26, 0.25)}


# ───────────────────────── 곡 ─────────────────────────

class BaroqueSong(Song):
    def note(self, buf, inst: str, midi: float, start: float, dur: float, gain=1.0, p=0.0, rng=None, rel=0.3) -> None:
        n = int((dur + rel) * RATE)
        if n <= 0:
            return
        key = (inst, round(midi, 2), n // 64)
        mono = self._cache.get(key)
        if mono is None:
            mono = INST[inst](hz(midi), n, rng, dur, self.q).astype(np.float32)
            if len(self._cache) < 4000:
                self._cache[key] = mono
        self._place(buf, mono, start, gain, p)

    def drum(self, buf, kind: str, start: float, vel: float, rng, root: int, i: int = 0) -> None:
        fn, ln, g, pan = KIT[kind]
        n = int(ln * RATE)
        if kind == "timp":   # 으뜸음 (낮은 옥타브), 박 사이엔 5도
            tm = root
            while tm > 45:
                tm -= 12
            mono = bs.d_timp(n, vel, rng, f=hz(tm) * (1.5 if i % 8 == 4 else 1.0))
        else:
            mono = fn(n, vel, rng)
        self._place(buf, mono, start, vel * g, pan + rng.uniform(-0.04, 0.04))

    # ── 연주법 ──
    def render_part(self, buf, part: dict, chords: list, root: int, scale: str, bars: int, rng, crescendo=False) -> None:
        st = part.get("style")
        g, o, p = part.get("gain", 1.0), 12 * part.get("oct", 0), part.get("pan", 0.0)
        bar, step, S = self.bar, self.step, self.steps
        if st == "toccata":     # 16분 분산화음: 화음음 위아래 + 마디 끝은 다음 화음으로 이어지는 경과음
            inst = part["inst"]
            for b in range(bars):
                cm = chord_midis(chords[b], root, scale)
                tones = [m + o for m in cm] + [cm[0] + 12 + o]
                seq = tones + [cm[1] + 12 + o] + tones[::-1][:-1]   # 바로크식 오르내림 (아래-위-더 위-아래)
                for i in range(S):
                    self.note(buf, inst, seq[i % len(seq)], b * bar + i * step, step * 1.2, g * (1.0 if i % 4 == 0 else 0.72),
                              p + (0.25 if i % 2 else -0.25), rng, rel=0.08)
            return
        if st == "continuo":    # 통주저음: 근음 8분 (박 사이엔 옥타브 위)
            for b in range(bars):
                r = chord_midis(chords[b], root, scale)[0] - 24 + o
                for i in range(0, S, 2):
                    self.note(buf, part.get("inst", "bass"), r + (12 if i % 4 == 2 else 0), b * bar + i * step, step * 1.7,
                              g * (1.0 if i % 8 == 0 else 0.8), p, rng, rel=0.06)
            return
        if st == "organ_chords":   # 오르간 전체 화음: 마디마다 (아래 · 위 두 손)
            for b in range(bars):
                cm = chord_midis(chords[b], root, scale)
                for j, m in enumerate(cm + [cm[0] + 12]):
                    self.note(buf, part["inst"], m + o, b * bar, bar * 0.92, g * (1.0 if j == 0 else 0.75), p + (j - 1.5) * 0.3, rng, rel=0.08)
            return
        if st == "pedal":       # 오르간 페달: 화음이 바뀔 때까지
            b = 0
            while b < bars:
                e = b + 1
                while e < bars and chords[e] == chords[b]:
                    e += 1
                r = chord_midis(chords[b], root, scale)[0] - 24 + o
                self.note(buf, "pedal", r, b * bar, (e - b) * bar * 0.98, g, p, rng, rel=0.15)
                b = e
            return
        super().render_part(buf, part, chords, root, scale, bars, rng, crescendo)

    def render_perc(self, buf, pattern: dict, bars: int, rng, crescendo=False, root=None) -> None:
        """pattern = {타악 이름: 16칸 (또는 마디마다 돌아가는 목록)}."""
        root = root if root is not None else self.root
        for kind, pat in pattern.items():
            pats = pat if isinstance(pat, list) else [pat]
            for b in range(bars):
                for i, ch in enumerate(pats[b % len(pats)][: self.steps]):
                    if ch in "xX":
                        self.drum(buf, kind, b * self.bar + i * self.step, 1.0 if ch == "X" else 0.7, rng, root, i)

    # ── 층 만들기 ──
    def stems(self) -> dict:
        sp = self.spec
        rv = sp.get("reverb", [0.2, 1.2])
        prv = [rv[0] * 0.6, rv[1] * 0.7]
        out = {}
        n16 = self.loop_len(self.bars)
        phases = sp["phases"]
        for i, ph in enumerate(phases):
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
            mel = sorted({(b, at): [b, at, d, ln] for pt in lead for b, at, d, ln in pt["notes"]}.values(), key=lambda x: (x[0], x[1]))
            up = [dict(pt, gain=pt.get("gain", 1.0) * 0.7) for pt in lead] + \
                 [dict(inst="choir_a", style="melody", gain=ph.get("tired_choir", 1.2), oct=1, notes=mel)]
            out[pre + "lead_oct"] = lay(up, g=np.random.default_rng(self.seed + i * 13 + 1))   # 지침: 합창이 한 옥타브 위
            out[pre + "choir"] = lay(ph.get("choir"))
            if i + 1 < len(phases):
                out[pre + "riser"] = self.riser(i, rng, rv)
        out["intro_mix"] = self.intro(rv)
        out["fail"] = self.fail_sound(rv)
        return out

    def intro(self, rv) -> np.ndarray:
        """1마디: 팀파니 굴림(점점 세게) + 하프시코드 하강 질주 (화성단음계 두 옥타브) → 1페이즈 첫 박."""
        root, scale = self.phase_info(0)
        rng = np.random.default_rng(self.seed + 999)
        buf = self._buf(self.bar)
        S = self.steps
        for s in range(S):
            self.drum(buf, "timp", s * self.step, 0.35 + 0.65 * s / S, rng, root)
            m = degree_to_midi(15 - s, root, "harmonic")
            self.note(buf, "harpsichord", m, s * self.step, self.step * 1.2, 0.45, 0.25 * ((-1) ** s), rng, rel=0.05)
        buf = self.hall(buf, rv[0], rv[1], rng)
        n = self.loop_len(1)
        out = buf[: n + int(RATE * 0.02)].copy()
        out[n:] *= np.linspace(1, 0, len(out) - n)[:, None]
        return out[:n]

    def riser(self, i: int, rng, rv) -> np.ndarray:
        """전환 1마디: 1→2 하프시코드 32분 상승 질주 + 팀파니 굴림 / 2→3 첫 박 페달 + 오르간 16분 하강 음형 (두 옥타브)."""
        root, scale = self.phase_info(i + 1)
        n = self.loop_len(1)
        buf = self._buf(self.bar)
        S = self.steps
        if i == 0:
            for s in range(S * 2):
                m = degree_to_midi(1 + s * 15 // (S * 2), root - 12, "harmonic")
                self.note(buf, "harpsichord", m, s * self.step / 2, self.step * 0.7, 0.35 + 0.25 * s / (2 * S), 0.25 * ((-1) ** s), rng, rel=0.04)
        else:
            self.note(buf, "pedal", root - 24, 0.0, self.bar, 0.5, 0.0, rng, rel=0.1)
            for s in range(S):
                m = degree_to_midi(15 - s, root, "harmonic")
                self.note(buf, "organ_full", m, s * self.step, self.step * 0.85, 0.3 + 0.2 * s / S, 0.3 * ((-1) ** s), rng, rel=0.05)
        for s in range(S):
            self.drum(buf, "timp", s * self.step, 0.4 + 0.6 * s / S, rng, root)
        out = self.hall(buf, rv[0], rv[1], rng)[:n]
        out[-int(RATE * 0.02):] *= np.linspace(1, 0, int(RATE * 0.02))[:, None]
        return out

    def fail_sound(self, rv) -> np.ndarray:
        """실패: 하프시코드가 줄을 긁어 내림 + 오르간 화음이 반음 넷 아래로 무너지듯 사라짐 + 팀파니."""
        root, scale = self.phase_info(0)
        rng = np.random.default_rng(self.seed + 777)
        L = 2.4
        n = int(L * RATE)
        t = _t(n)
        drop = 2 ** (-4 * (t / t[-1]) ** 1.5 / 12)
        x = np.zeros(n)
        for m in chord_midis(1, root, scale) + [root - 12]:
            x += _harm(hz(m) * drop, [1.0, 0.55, 0.3, 0.3, 0.15], top=6000)
        x = _norm(x) * (1 - t / t[-1]) ** 1.3 * np.minimum(1, t / 0.03)
        buf = self._buf(L)
        self._place(buf, x, 0.08, 0.6, 0.0)
        for s in range(14):   # 하프시코드 줄 긁어 내리기
            m = degree_to_midi(16 - s, root, scale)
            self.note(buf, "harpsichord", m, s * 0.012, 0.6, 0.35, 0.3 * ((-1) ** s), rng, rel=0.05)
        self.drum(buf, "timp", 0.0, 1.0, rng, root)
        buf = self.hall(buf, rv[0], rv[1], rng)
        out = buf[:n].copy()
        out[-int(RATE * 0.05):] *= np.linspace(1, 0, int(RATE * 0.05))[:, None]
        return out
