"""플라멩코 메탈 곡 (BOSS_BGM.md 엘드라시온 L10, DESIGN.md 43-25) — 불꽃상어 이그니스 전용 L10-FLAMENCO. 스펙에 "flamenco": true.

boss_synth.Song 을 물려받아 층 구조·반복 이음새·마스터링은 그대로, 악기와 연주만 플라멩코 메탈로 (boss_synth.py 는 그대로).
E 프리지안 도미넌트 (A 화성단음계의 5음 선법: E F G# A B C D) · 176 · 4/4, 잔향 1.0초.
  음계  "phrygdom" 을 이 모듈을 불러올 때 boss_synth.SCALES 에 더함 (boss_synth.py 를 고치면 모든 곡을 다시 구워야 해서)
  화성  E – F – E (프리지안 '스페인' 반음) / 안달루시아 종지 Am – G – F – E ("4m" · "b3M" · "2M" · "1")
  악기  나일론 기타 (손톱으로 뜯는 따뜻한 현 — 라스게아도 = 손가락 넷이 차례로 긁기, 피카도 = 빠른 단음 주선율, 골페 = 몸통 두드림) ·
        손뼉 팔마스 (12박 콤파스: 3·6·8·10·12 강세를 8분 위에 — 3마디에 두 바퀴) · 카혼 (낮은 '둥' · 높은 '탁') ·
        메탈 드럼 (투베이스 갤럽 · 스네어 · 크래시 · 라이드) + 낮게 찌그러진 기타 리프 (boss_rock 뮤트 · 파워 코드 · 리드) ·
        합창 '아—' + 외침 '하!' (boss_sangun 외침 여러 목소리)
  1페이즈  나일론 기타 라스게아도 + 손뼉 + 카혼, 피카도가 주인의 동기
  2페이즈  메탈 드럼(투베이스) + 낮은 찌그러진 리프 합류
  3페이즈  전체 최대 + 합창 '아—' + 4마디마다 외침, 피카도 + 일렉 리드 기타가 함께 주선율
  위기  투베이스 16분 + 카혼 연타 / 지침: 합창이 주선율을 한 옥타브 위에서
  전환  라스게아도 굴림(끊이지 않게) + 투베이스 16분 점점 세게 (2→3 은 스네어 굴림까지)
  실패  골페 '탁' + 피카도가 프리지안으로 미끄러져 내려가며 사그라듦 + 카혼
  인트로 1마디: 라스게아도 굴림 → 외침 '하!' + 카혼 → 1페이즈 첫 박
"""
import numpy as np

from src.audio import boss_rock, boss_sangun
from src.audio import boss_synth as bs
from src.audio.boss_muhyeop import _env, _harm, _norm, _ph
from src.audio.boss_synth import RATE, Song, _bw_filter, _t, chord_midis, degree_to_midi, hz, noise, peaking_eq

bs.SCALES.setdefault("phrygdom", [0, 1, 4, 5, 7, 8, 10])


# ───────────────────────── 악기 ─────────────────────────

def i_nylon(f, n, rng, **k):
    """나일론 기타: 손톱으로 뜯은 따뜻한 현 (배음이 빨리 사라짐) + 몸통 울림 200Hz + 손톱 '틱'."""
    x = _harm(np.full(n, f * (1 + rng.uniform(-6e-4, 6e-4))), [1.0, 0.65, 0.45, 0.32, 0.24, 0.17, 0.12, 0.08, 0.05, 0.035], decay=1.5)
    x = peaking_eq(x, 200.0, 4.0, 1.2)
    m = min(n, int(0.004 * RATE))
    x[:m] += _bw_filter(noise(m, rng), "bp", (2500, 7000)) * 0.4
    return _norm(_bw_filter(x, "lp", 5000)) * _env(n, 0.0015, 2.0, 0.03)


def i_picado(f, n, rng, dur=0.0, q=0.34, **k):
    """피카도: 빠른 단음 (조금 더 밝고 단단하게), 긴 음엔 떨림."""
    t = _t(n)
    f_t = np.full(n, f)
    if dur >= 0.9 * q:
        f_t = f * 2 ** (0.18 * np.sin(2 * np.pi * 5.5 * np.maximum(0, t - 0.15)) * np.clip((t - 0.15) / 0.15, 0, 1) / 12)
    x = _harm(f_t, [1.0, 0.7, 0.55, 0.4, 0.3, 0.2, 0.14, 0.1, 0.07], decay=1.2)
    m = min(n, int(0.004 * RATE))
    x[:m] += _bw_filter(noise(m, rng), "bp", (3000, 8000)) * 0.6
    return _norm(_bw_filter(peaking_eq(x, 220.0, 3.0, 1.2), "lp", 5500)) * _env(n, 0.001, 1.4, 0.03)


def d_palma(n, vel, rng):
    """손뼉 (팔마스): 손바닥이 겹쳐 맞는 날카로운 '짝' — 여러 사람이 살짝 어긋나게 (2kHz 위 위주, 신호 자리 덜 가리게)."""
    t = _t(n)
    x = np.zeros(n)
    for d in (0.0, 0.006, 0.013):
        s = int(d * RATE)
        x[s:] += _bw_filter(noise(n - s, rng), "bp", (2200, 7500)) * np.exp(-_t(n - s) * 55)
    return _norm(x) * np.minimum(1, t / 0.001)


def d_cajon_low(n, vel, rng):          # 카혼 가운데: 낮은 '둥'
    t = _t(n)
    x = np.sin(_ph(np.full(n, 78.0) * (1 + 0.6 * np.exp(-t * 40)))) * np.exp(-t * 14)
    x += _bw_filter(noise(n, rng), "lp", 600) * np.exp(-t * 40) * 0.3
    return np.tanh(1.5 * x)


def d_cajon_slap(n, vel, rng):         # 카혼 모서리: 높은 '탁' (나무 + 안쪽 줄 울림)
    t = _t(n)
    x = 0.6 * np.sin(_ph(np.full(n, 260.0))) * np.exp(-t * 35)
    x += _bw_filter(noise(n, rng), "bp", (2500, 8000)) * np.exp(-t * 45)
    return np.tanh(1.3 * x)


def d_golpe(n, vel, rng):              # 골페: 기타 몸통을 손가락으로 '탁'
    t = _t(n)
    return (0.7 * np.sin(_ph(np.full(n, 190.0))) * np.exp(-t * 50) + _bw_filter(noise(n, rng), "bp", (800, 4000)) * np.exp(-t * 80) * 0.5)


def s_shout(n, rng):
    """외침 '하!': 낮은 남성 셋이 조금씩 다른 높이로 (boss_sangun 외침)."""
    x = sum(boss_sangun.s_shout(n, rng, pitch=p) * a for p, a in ((110.0, 1.0), (131.0, 0.8), (98.0, 0.7)))
    return _norm(x)


def _orch(name):
    fn = bs.INST[name]
    return lambda f, n, rng, dur, q: fn(f, n, 1.0, rng)


INST = {"choir_a": _orch("choir_a"), "choir": _orch("choir"), "bass": _orch("bass")}
INST.update({
    "nylon": lambda f, n, rng, dur, q: i_nylon(f, n, rng),
    "picado": lambda f, n, rng, dur, q: i_picado(f, n, rng, dur=dur, q=q),
    "gtr_mute": lambda f, n, rng, dur, q: boss_rock.g_mute(f, n, rng),
    "gtr_power": lambda f, n, rng, dur, q: boss_rock.g_power(f, n, rng),
    "gtr_lead": lambda f, n, rng, dur, q: boss_rock.g_lead(f, n, rng, dur=dur, q=q),
    "bass_gtr": lambda f, n, rng, dur, q: boss_rock.g_bass(f, n, rng),
})
# 타악: 이름 → (함수, 길이 초, 크기, 자리)
KIT = {"palma": (d_palma, 0.15, 0.65, 0.25), "clow": (d_cajon_low, 0.4, 1.15, -0.05), "cslap": (d_cajon_slap, 0.2, 0.85, -0.1),
       "golpe": (d_golpe, 0.12, 0.35, 0.1), "kick": (bs.d_kick, 0.35, 0.55, 0.0), "snare": (bs.d_snare2, 0.35, 0.45, 0.05),
       "crash": (bs.d_crash, 2.2, 0.26, 0.25), "ride": (boss_rock.d_ride, 0.8, 0.2, -0.35)}


def compas(strong=(3, 6, 8, 10, 12)) -> list:
    """12박 콤파스 (8분 하나 = 한 박) → 3마디 × 16칸 손뼉 문자열 (강세 X · 나머지 박 x)."""
    cells = ["."] * 48
    for c in range(1, 25):
        cc = (c - 1) % 12 + 1
        cells[(c - 1) * 2] = "X" if cc in strong else "x"
    return ["".join(cells[i * 16:(i + 1) * 16]) for i in range(3)]


# ───────────────────────── 곡 ─────────────────────────

class FlamencoSong(Song):
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

    def drum(self, buf, kind: str, start: float, vel: float, rng) -> None:
        fn, ln, g, pan = KIT[kind]
        self._place(buf, fn(int(ln * RATE), vel, rng), start, vel * g, pan + rng.uniform(-0.04, 0.04))

    def voicing(self, c, root: int, scale: str) -> list:
        """기타 여섯 줄 화음: 근음을 E2~A2 근처로 내려 낮은 줄부터 (근음 · 5도 · 근음 · 3도 · 5도 · 근음)."""
        cm = chord_midis(c, root, scale)
        r = cm[0] - 24
        while r > 45:
            r -= 12
        while r < 40:
            r += 12
        third = cm[1] - cm[0]
        return [r, r + 7, r + 12, r + 12 + third, r + 19, r + 24]

    def strum(self, buf, notes, at: float, g: float, p: float, rng, up=False, gap=0.006, ln=0.5) -> None:
        seq = notes[::-1] if up else notes
        for j, m in enumerate(seq):
            self.note(buf, "nylon", m, at + j * gap, ln, g * (0.7 if up else 1.0), p + (j - 2.5) * 0.1, rng, rel=0.05)

    # ── 연주법 ──
    def render_part(self, buf, part: dict, chords: list, root: int, scale: str, bars: int, rng, crescendo=False) -> None:
        st = part.get("style")
        g, o, p = part.get("gain", 1.0), 12 * part.get("oct", 0), part.get("pan", 0.0)
        bar, step, S = self.bar, self.step, self.steps
        if st == "rasg":        # 라스게아도: R = 손가락 넷이 차례로 긁기(16분 안에), D = 내림, u = 올림, G = 골페
            pat = part.get("pattern", "R..D..u.D.uR..D.")[:S]
            for b in range(bars):
                v = [m + o for m in self.voicing(chords[b], root, scale)]
                for i, ch in enumerate(pat):
                    t0 = b * bar + i * step
                    if ch == "R":
                        for f in range(4):
                            self.strum(buf, v, t0 + f * step / 4, g * (0.75 + 0.1 * f), p, rng, gap=0.004, ln=step * 2)
                    elif ch == "D":
                        self.strum(buf, v, t0, g, p, rng, ln=step * 3)
                    elif ch == "u":
                        self.strum(buf, v[2:], t0, g, p, rng, up=True, ln=step * 2)
                    elif ch == "G":
                        self.drum(buf, "golpe", t0, 1.0, rng)
            return
        if st == "riff":        # 낮게 찌그러진 리프 (m 뮤트 · M 파워 코드 · - 늘임 · . 쉼), 화음 근음
            pat = part.get("pattern", "m.mm.mm.M--.m.mm")[:S]
            for b in range(bars):
                r = self.voicing(chords[b], root, scale)[0] + o
                i = 0
                while i < S:
                    ch = pat[i]
                    j = i + 1
                    while j < S and pat[j] == "-":
                        j += 1
                    if ch in "mM":
                        self.note(buf, "gtr_power" if ch == "M" else "gtr_mute", r, b * bar + i * step, step * (j - i) * 0.95,
                                  g * (1.0 if ch == "M" else 0.8), p + (0.3 if i % 2 else -0.3), rng, rel=0.05)
                    i = j
            return
        if st == "shouts":      # 외침 '하!' (몇 마디마다 첫 박)
            ev = part.get("every", 4)
            for b in range(0, bars, ev):
                self._place(buf, s_shout(int(0.4 * RATE), rng), b * bar + part.get("at", 0) * self.q, g, p)
            return
        if st == "choir_hold":  # 합창 '아—' (2마디마다)
            b = 0
            while b < bars:
                e = min(bars, b + 2)
                for j, m in enumerate(chord_midis(chords[b], root, scale)):
                    self.note(buf, "choir_a", m + o, b * bar, (e - b) * bar * 0.96, g * (1.0 if j == 0 else 0.8), p + (j - 1) * 0.5, rng, rel=0.3)
                b = e
            return
        super().render_part(buf, part, chords, root, scale, bars, rng, crescendo)

    def render_perc(self, buf, pattern: dict, bars: int, rng, crescendo=False, root=None) -> None:
        """pattern = {타악 이름: 16칸 (또는 마디마다 돌아가는 목록 — 손뼉 콤파스 3마디)}."""
        for kind, pat in pattern.items():
            pats = pat if isinstance(pat, list) else [pat]
            for b in range(bars):
                for i, ch in enumerate(pats[b % len(pats)][: self.steps]):
                    if ch in "xX":
                        self.drum(buf, kind, b * self.bar + i * self.step, 1.0 if ch == "X" else 0.6, rng)

    # ── 층 만들기 ──
    def stems(self) -> dict:
        sp = self.spec
        rv = sp.get("reverb", [0.15, 1.0])
        prv = [rv[0] * 0.5, rv[1] * 0.6]
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
        """1마디: 라스게아도 굴림(점점 세게) → 마지막 박 외침 '하!' + 카혼 → 1페이즈 첫 박."""
        root, scale = self.phase_info(0)
        rng = np.random.default_rng(self.seed + 999)
        buf = self._buf(self.bar)
        v = self.voicing(1, root, scale)
        for s in range(12):
            self.strum(buf, v, s * self.step, 0.1 + 0.015 * s, 0.0, rng, up=s % 2 == 1, gap=0.004, ln=self.step * 1.5)
        self._place(buf, s_shout(int(0.4 * RATE), rng), 12 * self.step, 0.6, 0.1)
        for s in (12, 14):
            self.drum(buf, "clow", s * self.step, 1.0, rng)
        buf = self.hall(buf, rv[0], rv[1], rng)
        n = self.loop_len(1)
        out = buf[: n + int(RATE * 0.02)].copy()
        out[n:] *= np.linspace(1, 0, len(out) - n)[:, None]
        return out[:n]

    def riser(self, i: int, rng, rv) -> np.ndarray:
        """전환 1마디: 라스게아도 굴림(끊이지 않게) + 투베이스 16분 점점 세게 (2→3 은 스네어 굴림까지)."""
        root, scale = self.phase_info(i + 1)
        n = self.loop_len(1)
        buf = self._buf(self.bar)
        S = self.steps
        v = self.voicing(1, root, scale)
        for s in range(S):
            u = s / max(1, S - 1)
            self.strum(buf, v, s * self.step, 0.08 + 0.1 * u, 0.0, rng, up=s % 2 == 1, gap=0.004, ln=self.step * 1.5)
            self.drum(buf, "kick", s * self.step, 0.5 + 0.5 * u, rng)
            if i == 1:
                self.drum(buf, "snare", s * self.step, 0.3 + 0.7 * u, rng)
        self.note(buf, "gtr_power", v[0], 0.0, self.bar * 0.9, 0.35, 0.0, rng, rel=0.05)
        out = self.hall(buf, rv[0], rv[1], rng)[:n]
        out[-int(RATE * 0.02):] *= np.linspace(1, 0, int(RATE * 0.02))[:, None]
        return out

    def fail_sound(self, rv) -> np.ndarray:
        """실패: 골페 '탁' + 피카도가 프리지안으로 미끄러져 내려가며 (E D C B A G# F E) 사그라듦 + 카혼."""
        root, scale = self.phase_info(0)
        rng = np.random.default_rng(self.seed + 777)
        L = 2.0
        buf = self._buf(L)
        self.drum(buf, "golpe", 0.0, 1.0, rng)
        self.drum(buf, "clow", 0.0, 1.0, rng)
        for j in range(8):
            m = degree_to_midi(8 - j, root, scale)
            self.note(buf, "picado", m, 0.08 + j * 0.11, 0.25, 0.5 * (1 - j / 9), 0.1, rng, rel=0.1)
        self.strum(buf, [m - 1 for m in self.voicing(1, root, scale)], 1.0, 0.3, 0.0, rng, gap=0.03, ln=0.9)   # 반음 아래로 늘어진 화음
        buf = self.hall(buf, rv[0], rv[1], rng)
        n = int(L * RATE)
        out = buf[:n].copy()
        out[-int(RATE * 0.05):] *= np.linspace(1, 0, int(RATE * 0.05))[:, None]
        return out
