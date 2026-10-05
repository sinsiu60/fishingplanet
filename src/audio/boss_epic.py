"""에픽 집대성 전투 곡 (SHARMION_THEMES.md 6장, DESIGN.md 43-19) — 용문잉어 '등용' 전용 L06-EPIC. 스펙에 "epic": true.

boss_synth.Song 을 물려받아 층 구조·반복 이음새·마스터링은 그대로. 다섯 테마의 소리는 새로 만들지 않고 그 모듈에서 그대로 가져옴:
  여우비 boss_jazz (트럼펫·색소폰·트롬본·브러시) · 산군 boss_sangun (큰 북·목 노래) · 일렉트로 boss_rock (일렉 기타·라이드) ·
  일섬 boss_muhyeop (태평소·장구·징) · 태고 boss_organ (파이프 오르간·종)  + 오케스트라·합창은 boss_synth.
D 화성단음계 · 160 · 4/4.
  1페이즈  용의 포효 같은 낮은 금관 + 오케스트라(현악 16분·금관) + 큰북·팀파니
  2페이즈  다섯 테마 메들리 20마디 (4마디씩 여우비 → 산군 → 일렉트로 → 일섬 → 태고), 바닥에 현악 16분이 쉬지 않고 이어짐
           (파트의 "span": [시작 마디, 끝 마디] = 그 구간에서만 연주, 타악 "이름@시작-끝" 도 같음)
  변신     2→3 라이저는 마디를 기다리지 않고 바로 (스펙 phases[2].sync — src/render/dragon.py 의 2.4초 변신을 실제 시간으로 옮긴 것):
           낮은 지속음 하나 → 붉은 번개 두 번에 큰북 두 번 → 섬광에 전체 강타 → 1마디 여운 뒤 3페이즈
  3페이즈  다섯 테마 악기를 한꺼번에 + 오케스트라 + 합창, 주파수 자리 나누기 (파트의 "band": [낮은 Hz, 높은 Hz]):
           오르간·목 노래 = 낮은 쪽, 일렉 기타 = 중간 (오르간과 같은 화음), 태평소·트럼펫 = 중고음에서 주인의 동기 함께, 합창 = 넓게
  위기  큰북·팀파니 연타 / 지침: 합창이 주선율을 한 옥타브 위에서 / 실패: 전체가 무너지듯 강타 후 징 여운
"""
import numpy as np

from src.audio import boss_jazz, boss_muhyeop, boss_organ, boss_rock, boss_sangun
from src.audio import boss_synth as bs
from src.audio.boss_muhyeop import _harm, _norm
from src.audio.boss_synth import RATE, Song, _bw_filter, _t, chord_midis, degree_to_midi, hz


# ───────────────────────── 악기: 이름 → (f, n, rng, dur, q) ─────────────────────────

def _orch(name):
    fn = bs.INST[name]
    return lambda f, n, rng, dur, q: fn(f, n, 1.0, rng)


def _throat(f, n, rng, dur, q):
    """목 노래: 낮은 소리 + 2박마다 배음 휘파람 (8·12·9·8배음 = 으뜸음·5도·2도·으뜸음 — 어느 화음 위에서도 어울림)."""
    wh = [(k * 2 * q, (8, 12, 9, 8)[k % 4]) for k in range(int(n / RATE / (2 * q)) + 1)]
    return boss_sangun.throat(f, n, rng, whistle=wh, sharp=0.8)


INST = {k: _orch(k) for k in ("brass", "horn", "trumpet", "roar", "strings", "spiccato", "tremolo", "bass", "drone", "choir", "choir_a")}
INST.update({
    "trumpet_open": lambda f, n, rng, dur, q: boss_jazz.i_trumpet_open(f, n, rng, dur=dur, q=q),
    "sax": lambda f, n, rng, dur, q: boss_jazz.i_sax(f, n, rng, dur=dur, q=q),
    "trombone": lambda f, n, rng, dur, q: boss_jazz.i_trombone(f, n, rng, dur=dur),
    "throat": _throat,
    "gtr_mute": lambda f, n, rng, dur, q: boss_rock.g_mute(f, n, rng),
    "gtr_power": lambda f, n, rng, dur, q: boss_rock.g_power(f, n, rng),
    "gtr_lead": lambda f, n, rng, dur, q: boss_rock.g_lead(f, n, rng, dur=dur, q=q),
    "taepyeongso": lambda f, n, rng, dur, q: boss_muhyeop.i_taepyeongso(f, n, rng, dur=dur, q=q),
    "organ": lambda f, n, rng, dur, q: boss_organ.pipe(f, n, rng),
    "organ_full": lambda f, n, rng, dur, q: boss_organ.pipe(f, n, rng, full=True),
    "pedal": lambda f, n, rng, dur, q: boss_organ.i_pedal(f, n, rng),
})

# 타악: 이름 → (함수(n, vel, rng), 길이 초, 크기, 소리 자리)
KIT = {
    "timp": (None, 1.6, 0.8, 0.0),
    "obig": (bs.d_bigdrum, 1.4, 0.8, 0.0),                    # 오케스트라 큰북
    "big": (boss_sangun.d_bigdrum, 1.2, 0.85, 0.0),           # 산군의 큰 북
    "taiko": (bs.d_taiko, 0.6, 0.55, -0.1),
    "snare": (bs.d_snare2, 0.35, 0.42, 0.05),
    "kick": (bs.d_kick, 0.5, 0.5, 0.0),
    "crash": (bs.d_crash, 2.0, 0.32, 0.25),
    "cymbal": (bs.d_cymbal, 2.2, 0.3, -0.25),
    "tom": (None, 0.6, 0.45, 0.0),
    "ride": (boss_rock.d_ride, 0.8, 0.3, -0.35),              # 일렉트로 라이드
    "brush": (boss_jazz.d_brush, 0.35, 0.4, 0.15),           # 여우비 브러시
    "kung": (boss_muhyeop.d_kung, 0.5, 0.55, -0.15),         # 일섬 장구 (궁편)
    "deok": (boss_muhyeop.d_deok, 0.25, 0.42, 0.15),         # (채편)
    "jing": (boss_muhyeop.d_jing, 4.0, 0.45, 0.0),
    "bell": (None, 4.0, 0.36, 0.15),                         # 태고 큰 종
}


# ───────────────────────── 곡 ─────────────────────────

class EpicSong(Song):
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
        elif kind == "tom":
            mono = bs.d_tom(n, vel, rng, f=max(75.0, 190.0 - 12.0 * (i % 8)))
        elif kind == "bell":
            mono = boss_organ.d_bell(n, vel, rng, f=hz(root - 24))
        else:
            mono = fn(n, vel, rng)
        self._place(buf, mono, start, vel * g, pan + rng.uniform(-0.04, 0.04))

    # ── 연주법 ──
    def render_part(self, buf, part: dict, chords: list, root: int, scale: str, bars: int, rng, crescendo=False) -> None:
        span, band = part.get("span"), part.get("band")
        if span or band:   # 구간만 · 주파수 자리만: 따로 그려서 잘라 더함
            b0, b1 = span or (0, bars)
            tmp = self._buf(bars * self.bar)
            self.render_part(tmp, {k: v for k, v in part.items() if k not in ("span", "band")}, chords, root, scale, min(bars, b1), rng, crescendo)
            if span:
                a, e = int(b0 * self.bar * RATE), int(b1 * self.bar * RATE)
                w = np.zeros(len(tmp))
                w[a:e] = 1.0
                if a > 0:
                    w[max(0, a - 220):a] = np.linspace(0, 1, a - max(0, a - 220))
                f = min(len(tmp) - e, int(0.25 * RATE))
                w[e:e + f] = np.linspace(1, 0, f) ** 2   # 구간 끝: 울림을 짧게 남기고 다음 테마로
                tmp *= w[:, None]
            if band:
                tmp = _bw_filter(_bw_filter(tmp, "hp", band[0]), "lp", band[1])
            buf += tmp[: len(buf)]
            return
        st = part.get("style")
        g, o, p = part.get("gain", 1.0), 12 * part.get("oct", 0), part.get("pan", 0.0)
        bar, step, S = self.bar, self.step, self.steps
        if st == "section":     # 여우비: 금관 섹션 찌르기 (트럼펫 위 · 색소폰 가운데 · 트롬본 아래)
            pat = part.get("pattern", "x..x......x..x..")[:S]
            for b in range(bars):
                cm = chord_midis(chords[b], root, scale, 4)
                for i, ch in enumerate(pat):
                    if ch not in "xX":
                        continue
                    t0, ln, v = b * bar + i * step, step * (3 if ch == "X" else 1.6), g * (1.0 if ch == "X" else 0.8)
                    self.note(buf, "trumpet_open", cm[2] + 12 + o, t0, ln, v * 0.8, 0.25, rng, rel=0.08)
                    self.note(buf, "trumpet_open", cm[0] + 12 + o, t0, ln, v * 0.6, 0.35, rng, rel=0.08)
                    self.note(buf, "sax", cm[1] + o, t0, ln, v * 0.7, -0.25, rng, rel=0.08)
                    self.note(buf, "sax", cm[3] + o, t0, ln, v * 0.5, -0.35, rng, rel=0.08)
                    self.note(buf, "trombone", cm[0] - 12 + o, t0, ln, v * 0.7, 0.0, rng, rel=0.08)
            return
        if st == "riff":        # 일렉트로: 기타 리프 (m = 뮤트, M = 파워 코드, - = 늘임, . = 쉼) — 화음 근음, 낮은 줄
            pat = part.get("pattern", "mm.mm.mmM--.mm.m")[:S]
            for b in range(bars):
                r = chord_midis(chords[b], root, scale)[0] - 12 + o
                while r > 47 + o:
                    r -= 12
                i = 0
                while i < S:
                    ch = pat[i]
                    j = i + 1
                    while j < S and pat[j] == "-":
                        j += 1
                    if ch in "mM":
                        inst = "gtr_power" if ch == "M" else "gtr_mute"
                        self.note(buf, inst, r, b * bar + i * step, step * (j - i) * 0.95, g * (1.0 if ch == "M" else 0.8),
                                  p + (0.3 if i % 2 else -0.3), rng, rel=0.05)
                    i = j
            return
        if st == "throat":      # 산군: 목 노래 (화음이 바뀔 때까지, 근음 두 옥타브 아래)
            b = 0
            while b < bars:
                e = b + 1
                while e < bars and chords[e] == chords[b]:
                    e += 1
                r = chord_midis(chords[b], root, scale)[0] - 24 + o
                self.note(buf, "throat", r, b * bar, (e - b) * bar * 0.97, g, p, rng, rel=0.2)
                b = e
            return
        if st == "pedal":       # 태고: 오르간 페달 (화음이 바뀔 때까지)
            b = 0
            while b < bars:
                e = b + 1
                while e < bars and chords[e] == chords[b]:
                    e += 1
                r = chord_midis(chords[b], root, scale)[0] - 24 + o
                self.note(buf, "pedal", r, b * bar, (e - b) * bar * 0.98, g, p, rng, rel=0.2)
                b = e
            return
        if st == "toccata":     # 태고: 손건반 16분 쉼 없는 음형 (화음음 위아래로, 짧게)
            inst = part["inst"]
            for b in range(bars):
                cm = chord_midis(chords[b], root, scale)
                tones = [m + o for m in cm] + [cm[0] + 12 + o]
                seq = tones + tones[-2:0:-1]
                for i in range(S):
                    self.note(buf, inst, seq[i % len(seq)], b * bar + i * step, step * 0.7, g * (1.0 if i % 4 == 0 else 0.75),
                              p + (0.2 if i % 2 else -0.2), rng, rel=0.05)
            return
        super().render_part(buf, part, chords, root, scale, bars, rng, crescendo)

    def render_perc(self, buf, pattern: dict, bars: int, rng, crescendo=False, root=None) -> None:
        """pattern = {타악 이름[@시작-끝]: 16칸 (또는 마디마다 돌아가는 목록)}."""
        root = root if root is not None else self.root
        for key, pat in pattern.items():
            kind, _, rg = key.partition("@")
            b0, b1 = (int(v) for v in rg.split("-")) if rg else (0, bars)
            pats = pat if isinstance(pat, list) else [pat]
            for b in range(b0, min(b1, bars)):
                for i, ch in enumerate(pats[b % len(pats)][: self.steps]):
                    if ch in "xX":
                        self.drum(buf, kind, b * self.bar + i * self.step, 1.0 if ch == "X" else 0.72, rng, root, i)

    # ── 층 만들기 ──
    def stems(self) -> dict:
        sp = self.spec
        rv = sp.get("reverb", [0.22, 1.8])
        prv = [rv[0] * 0.6, rv[1] * 0.7]
        out = {}
        phases = sp["phases"]
        bars0 = self.bars
        for i, ph in enumerate(phases):
            self.bars = ph.get("bars", bars0)   # 2페이즈 메들리 = 20마디 (4마디 × 5테마)
            n_loop = self.loop_len(self.bars)
            root, scale = self.phase_info(i)
            rng = np.random.default_rng(self.seed + i * 13)
            chords = ph["chords"]
            pre = f"{i + 1}_"

            def lay(parts, perc=None, r=rv, g=None):
                return self.wrap(self.render_layer(parts, chords, root, scale, self.bars, g if g is not None else rng, r, perc=perc), n_loop)
            out[pre + "base"] = lay(ph.get("base"))
            perc = ph["perc"]
            out[pre + "perc"] = lay(None, perc["pattern"], prv)
            out[pre + "perc_crisis"] = lay(None, dict(perc["pattern"], **perc.get("crisis", {})), prv)
            lead = ph.get("lead") or []
            out[pre + "lead"] = lay(lead, g=np.random.default_rng(self.seed + i * 13 + 1))
            mel = [n for p in lead for n in p["notes"]]
            mel = sorted({(b, at): [b, at, d, ln] for b, at, d, ln in mel}.values())   # 테마마다 주선율을 하나로 (합창이 따라 부름)
            up = [dict(p, gain=p.get("gain", 1.0) * 0.7) for p in lead] + [dict(inst="choir", style="melody", gain=ph.get("tired_choir", 1.4), oct=1, notes=mel)]
            out[pre + "lead_oct"] = lay(up, g=np.random.default_rng(self.seed + i * 13 + 1))   # 지침: 합창이 한 옥타브 위
            out[pre + "choir"] = lay(ph.get("choir"))
            if i + 1 < len(phases):
                out[pre + "riser"] = self.riser(i, rng, rv)
        self.bars = bars0
        out["intro_mix"] = self.intro(rv)
        out["fail"] = self.fail_sound(rv)
        return out

    def chord_hit(self, buf, at: float, ln: float, root: int, scale: str, rng, g=1.0, deg=1) -> None:
        """전체 강타: 금관(포효)·현악·합창·오르간 전체 음전·일렉 기타 파워 코드·태평소·큰북·심벌·징."""
        cm = chord_midis(deg, root, scale)
        for j, m in enumerate(cm):
            pan = (j - 1) * 0.35
            self.note(buf, "roar", m - 12, at, ln, 0.4 * g, pan, rng, rel=0.4)
            self.note(buf, "brass", m, at, ln, 0.32 * g, -pan, rng, rel=0.4)
            self.note(buf, "strings", m + 12, at, ln, 0.22 * g, pan, rng, rel=0.4)
            self.note(buf, "choir_a", m, at, ln, 0.3 * g, -pan, rng, rel=0.4)
            self.note(buf, "organ_full", m - 12, at, ln, 0.16 * g, pan, rng, rel=0.2)
        self.note(buf, "pedal", cm[0] - 24, at, ln, 0.4 * g, 0.0, rng, rel=0.2)
        self.note(buf, "gtr_power", cm[0] - 24, at, ln, 0.3 * g, -0.3, rng, rel=0.1)
        self.note(buf, "taepyeongso", cm[0] + 12, at, ln * 0.8, 0.22 * g, 0.2, rng, rel=0.1)
        for k in ("obig", "big", "crash", "cymbal", "jing"):
            self.drum(buf, k, at, 1.0 * g, rng, root)
        self.drum(buf, "timp", at, 1.0 * g, rng, root)

    def intro(self, rv) -> np.ndarray:
        """1마디: 큰북 '둥' → 팀파니 몰아치기 + 용의 포효 금관이 부풀어 오름 (1페이즈 첫 박으로 이어짐)."""
        root, scale = self.phase_info(0)
        rng = np.random.default_rng(self.seed + 999)
        buf = self._buf(self.bar)
        self.drum(buf, "obig", 0.0, 1.0, rng, root)
        self.drum(buf, "big", 0.0, 0.9, rng, root)
        for j, m in enumerate(chord_midis(1, root, scale)):
            self.note(buf, "roar", m - 12, 0.0, self.bar, 0.4, (j - 1) * 0.3, rng, rel=0.1)
        for s in range(4, self.steps):
            self.drum(buf, "timp", s * self.step, 0.35 + 0.65 * s / self.steps, rng, root)
        buf = self.hall(buf, rv[0], rv[1], rng)
        n = self.loop_len(1)
        out = buf[: n + int(RATE * 0.02)].copy()
        out[n:] *= np.linspace(1, 0, len(out) - n)[:, None]
        return out[:n]

    def riser(self, i: int, rng, rv) -> np.ndarray:
        sync = self.spec["phases"][i + 1].get("sync")
        root, scale = self.phase_info(i + 1)
        if sync:
            return self.transform(sync, root, scale, rng, rv)
        # 1→2: 현악 16분 상승(화성단음계 두 옥타브) + 작은북 몰아치기 + 팀파니
        n = self.loop_len(1)
        buf = self._buf(self.bar)
        S = self.steps
        for s in range(S):
            m = degree_to_midi(1 + s, root - 12, "harmonic")
            self.note(buf, "spiccato", m, s * self.step, self.step * 1.4, 0.4 + 0.3 * s / S, 0.3 * ((-1) ** s), rng, rel=0.05)
            self.drum(buf, "snare", s * self.step, 0.4 + 0.6 * s / S, rng, root)
            if s % 4 == 0:
                self.drum(buf, "timp", s * self.step, 0.8, rng, root, s)
        self.note(buf, "roar", root - 24, 0.0, self.bar, 0.35, 0.0, rng, rel=0.1)
        out = self.hall(buf, rv[0], rv[1], rng)[:n]
        out[-int(RATE * 0.02):] *= np.linspace(1, 0, int(RATE * 0.02))[:, None]
        return out

    def transform(self, sync: dict, root: int, scale: str, rng, rv) -> np.ndarray:
        """변신 (src/render/dragon.py, 실제 시간): 낮은 지속음 하나 → 번개마다 큰북 → 섬광에 전체 강타 → 1마디 여운 + 몰아치기."""
        fl = sync["flash"]
        L = fl + sync.get("tail_bars", 1) * self.bar
        n = int(round(L * RATE))
        buf = self._buf(L)
        self.note(buf, "drone", root - 24, 0.0, fl + 0.05, 0.75, 0.0, rng, rel=0.05)      # 음악이 낮은 지속음 하나로
        self.note(buf, "roar", root - 24, 0.4, fl - 0.35, 0.22, 0.0, rng, rel=0.05)
        for k, at in enumerate(sync["bolts"]):                                            # 붉은 번개 = 큰북
            for d in ("obig", "big", "timp"):
                self.drum(buf, d, at, 1.0, rng, root)
        self.chord_hit(buf, fl, self.bar * 0.9, root, scale, rng)                         # 섬광 = 전체 강타
        S = self.steps
        for s in range(S // 2, S):                                                         # 3페이즈로 몰아치기 (마지막 반 마디)
            t0 = fl + s * self.step
            self.drum(buf, "taiko", t0, 0.5 + 0.5 * s / S, rng, root)
            self.drum(buf, "snare", t0, 0.4 + 0.6 * s / S, rng, root)
        out = self.hall(buf, rv[0], rv[1], rng)[:n]
        out[-int(RATE * 0.02):] *= np.linspace(1, 0, int(RATE * 0.02))[:, None]
        return out

    def fail_sound(self, rv) -> np.ndarray:
        """실패: 전체가 한 번 무너지듯 강타 (화음이 반음 넷 아래로 미끄러짐) 후 징 여운."""
        root, scale = self.phase_info(0)
        rng = np.random.default_rng(self.seed + 777)
        L = 3.6
        n = int(L * RATE)
        t = _t(n)
        drop = 2 ** (-4 * np.clip(t / 1.4, 0, 1) ** 1.5 / 12)
        x = np.zeros(n)
        for m in chord_midis(1, root, scale) + [root - 12]:
            x += _harm(hz(m - 12) * drop, [1.0, 0.7, 0.5, 0.35, 0.25, 0.15], top=5000)
        x = np.tanh(1.8 * _norm(x)) * np.clip(1 - t / 1.6, 0, 1) ** 1.4 * np.minimum(1, t / 0.01)
        buf = self._buf(L)
        self._place(buf, x, 0.0, 0.7, 0.0)
        for k in ("obig", "big", "crash", "timp"):
            self.drum(buf, k, 0.0, 1.0, rng, root)
        self.drum(buf, "jing", 0.25, 1.0, rng, root)
        buf = self.hall(buf, rv[0], rv[1], rng)
        out = buf[:n].copy()
        out[-int(RATE * 0.3):] *= np.linspace(1, 0, int(RATE * 0.3))[:, None]
        return out
