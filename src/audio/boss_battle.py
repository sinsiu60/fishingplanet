"""전투감 곡 (BOSS_BGM_FIX.md, DESIGN.md 43-13) — 스펙에 "battle": true 인 곡만 이 연주법으로 굽는다.

boss_synth.Song 을 그대로 물려받고, 바뀌는 곳만 덮어쓴다 (boss_synth.py 를 고치면 모든 곡이 다시 구워져야 하므로 따로 둠).
  - 리듬 뼈대: 전설 = 엇박 큰북 · 2·4박 강타 · 하이햇(8분 → 16분) · 16분 현악 엔진(으뜸·으뜸·5도·으뜸 / 으뜸·으뜸·♭6·5도)
               · 8분 옥타브 베이스 · 1·11칸 금관 강세
               환상 = 둥근 킥 · 작은 스냅 · 16분 셰이커 · 16분 하프 아르페지오 · 8분 신스 베이스 맥박 · 1·9칸 합창 "아-" 짧은 화음
  - 소리 정리: 잔향 전설 1.2초 / 환상 1.8초, 길게 까는 패드·합창 −6dB, 타악 층 비중 맞춤(전설 30% / 환상 25%),
               1마디 인트로, 화음은 마디마다 바뀜, 반복 음형·아르페지오는 칸 길이의 60%만 울림
  - 주선율: 전설은 2박 이상 긴 음이 마디에 하나만, 환상은 긴 음을 마지막 페이즈 절정(뒤 8마디)에만
"""
import numpy as np

from src.audio.boss_synth import (DRUM_LEN, DRUM_PAN, DRUMS, PUMP, PUMP_LV, RATE, Song, chord_midis, d_bigdrum,
                                  d_crash, d_shaker, d_snap, d_snare2, d_softkick, d_tom)

ART = 0.6                                       # 짧게 끊기: 칸 길이의 60%
REVERB = {"legend": 1.2, "phantom": 1.8}        # 잔향 길이 (초)
PERC_SHARE = {"legend": 0.30, "phantom": 0.25}  # 타악 층 에너지 비중 목표
SOFT = 0.5                                      # 패드·길게 까는 합창 −6dB
FORM = [0.92, 1.0, 1.0, 1.0]                    # 4마디 묶음마다 세기 (처음부터 거의 가득)

# 박 단계 0~2 (첫 페이즈 → 마지막 페이즈). 칸 16 = 4/4, 12 = 6/8·3/4
SKELETON = {
    "legend": {
        16: [dict(kick="x..x..x.x..x..x.", snare2="....X.......X...", hat="x.x.x.x.x.x.x.x."),
             dict(kick="x..x..x.x..x..x.", snare2="....X.......X...", hat="xxxxxxxxxxxxxxxx", ohat="..x...x...x...x."),
             dict(kick="x..x..x.x..x..x.", snare2="....X.....xxX...", hat="xxxxxxxxxxxxxxxx", ohat="..x...x...x...x.")],
        12: [dict(kick="x...x.x...x.", snare2="......X.....", hat="x.x.x.x.x.x."),
             dict(kick="x...x.x...x.", snare2="......X.....", hat="xxxxxxxxxxxx", ohat="..x.....x..."),
             dict(kick="x...x.x...x.", snare2="....xxX.....", hat="xxxxxxxxxxxx", ohat="..x.....x...")],
        "crisis": {16: dict(kick="x.xx..x.x.xx..x.", snare2="....X..x....X.xx", tom="............xxxx"),
                   12: dict(kick="x.x.x.x.x.x.", snare2="...x..X..xxx", tom="........xxxx")},
    },
    "phantom": {
        16: [dict(softkick="x.......x..x....", snap="....x.......x...", shaker="xxxxxxxxxxxxxxxx"),
             dict(softkick="x.......x..x....", snap="....x.......x...", shaker="xxxxxxxxxxxxxxxx", ohat="..x...x...x...x."),
             dict(softkick="x.......x..x....", snap="....x.......x..x", shaker="xxxxxxxxxxxxxxxx", ohat="..x...x...x...x.")],
        12: [dict(softkick="x...x.x...x.", snap="......x.....", shaker="xxxxxxxxxxxx"),
             dict(softkick="x...x.x...x.", snap="......x.....", shaker="xxxxxxxxxxxx", ohat="...x.....x.."),
             dict(softkick="x...x.x...x.", snap="......x....x", shaker="xxxxxxxxxxxx", ohat="...x.....x..")],
        "crisis": {16: dict(softkick="x...x...x..xx...", snap="....x..x....x..x"),
                   12: dict(softkick="x..xx.x..xx.", snap="...x..x..x.x")},
    },
}
DRUM_GAIN = {"hat": 0.55, "ohat": 0.5, "shaker": 0.45, "snap": 0.6, "tom": 0.8}   # 잔 타악은 작게 (반짝이게)

# 화음 바꾸기: 같은 화음이 두 마디 이어지면 둘째 마디를 가까운 화음으로 (앞·뒤와 겹치지 않는 첫 후보)
SUB = {
    "minor": {1: [6, 4, 3], 6: [4, 7, 1], 7: [3, 6, 5], 4: [1, 6, 7], 3: [7, 6, 4], 2: [7, 4],
              "5M": ["5:7"], 5: ["5M", 4]},
    "lydian": {1: [2, 5, 6], 2: [1, 5, 6], 6: [5, 2, 3], 5: [6, 2, 1], 3: [2, 6, 5]},
}


def quicken(chords: list, scale: str) -> list:
    sub = SUB.get(scale, SUB["minor"] if "minor" in scale or scale in ("dorian", "harmonic") else SUB["lydian"])
    out = list(chords)
    for i in range(1, len(out)):
        if out[i] != out[i - 1]:
            continue
        nxt = chords[i + 1] if i + 1 < len(chords) else chords[0]
        for c in sub.get(out[i], []):
            if c != out[i - 1] and c != nxt:
                out[i] = c
                break
    return out


def _step(deg, k):
    return deg + k if isinstance(deg, int) else deg


def tighten(notes: list, long_ok) -> list:
    """주선율 다듬기: long_ok(마디)가 참이면 그 마디의 첫 긴 음(2박 이상)만 남기고, 나머지 긴 음은
    2박마다 '점8분 · 16분 · 8분(한 음 위) · 8분' 으로 쪼갬 (같은 음 → 위 → 제자리: 동기 음은 그대로)."""
    out, kept = [], set()
    for b, at, deg, ln in notes:
        if ln < 2 - 1e-6:
            out.append([b, at, deg, ln])
            continue
        start, rest = at, ln
        if long_ok(b) and b not in kept:
            kept.add(b)
            keep = 2.0 if ln > 2 else ln
            out.append([b, at, deg, keep])
            start, rest = at + keep, ln - keep
        while rest >= 2 - 1e-6:
            out += [[b, start, deg, 0.75], [b, start + 0.75, deg, 0.25], [b, start + 1.0, _step(deg, 1), 0.5], [b, start + 1.5, deg, 0.5]]
            start, rest = start + 2.0, rest - 2.0
        if rest > 1e-6:
            out.append([b, start, deg, rest])
    return out


class BattleSong(Song):
    def __init__(self, sid: str, spec: dict, master: dict):
        sp = dict(spec)
        phantom = sp.get("kind") == "phantom"
        n = len(sp["phases"])
        bars = sp.get("bars", 16)
        phases = []
        for i, ph in enumerate(sp["phases"]):
            ph = dict(ph)
            scale = ph.get("scale", sp.get("scale", "minor"))
            ch = ph["chords"]
            if len(ch) < bars:
                ch = (ch * (bars // len(ch) + 1))[:bars]
            ph["chords"] = quicken(ch, scale)
            last = i == n - 1
            long_ok = (lambda b: b >= bars // 2) if (phantom and last) else (lambda b: False) if phantom else (lambda b: True)
            ph["lead"] = [dict(p, notes=tighten(p["notes"], long_ok)) if p.get("style") == "melody" else p for p in ph.get("lead") or []]
            phases.append(ph)
        sp["phases"] = phases
        super().__init__(sid, sp, master)

    # ── 연주법: 전설 현악 엔진 · 옥타브 베이스 · 짧은 쏟아짐 ──
    def render_part(self, buf, part: dict, chords: list, root: int, scale: str, bars: int, rng, crescendo=False) -> None:
        st = part.get("style")
        g, o, p = part.get("gain", 1.0), 12 * part.get("oct", 0), part.get("pan", 0.0)
        step, bar, S = self.step, self.bar, self.steps
        if st == "engine":        # 16분 전부: 으뜸 · 으뜸 · 5도 · 으뜸 / 으뜸 · 으뜸 · ♭6 · 5도
            seq = (0, 0, 7, 0, 0, 0, 8, 7)
            for b in range(bars):
                r = chord_midis(chords[b], root, scale)[0] + o
                for i in range(S):
                    acc = 1.0 if i % 4 == 0 else 0.72
                    self.note(buf, part["inst"], r + seq[i % 8], b * bar + i * step, step * ART, g * acc, p + (0.15 if i % 2 else -0.15),
                              rng, rel=0.08)
            return
        if st == "octbass":       # 8분 전부: 으뜸음 옥타브 아래 · 위 교대
            for b in range(bars):
                r = chord_midis(chords[b], root, scale)[0] - 12 + o
                for k, i in enumerate(range(0, S, 2)):
                    self.note(buf, part["inst"], r + (12 if k % 2 else 0), b * bar + i * step, 2 * step * ART,
                              g * (1.0 if i % 4 == 0 else 0.8), p, rng, rel=0.08)
            return
        if st == "fall":          # 쏟아지는 하강 아르페지오 — 간격의 60%만 울림
            n_per = part.get("per_bar", 8)
            for b in range(bars):
                cm = chord_midis(chords[b], root, scale)
                notes = sorted(cm + [m + 12 for m in cm] + [m + 24 for m in cm], reverse=True)
                for k in range(n_per):
                    self.note(buf, part["inst"], notes[k % len(notes)] + o, b * bar + k * bar / n_per, bar / n_per * ART,
                              g * (1 - 0.4 * k / n_per), p + (k % 2 - 0.5) * 0.6, rng, rel=0.35)
            return
        super().render_part(buf, part, chords, root, scale, bars, rng, crescendo)

    # ── 뼈대 ──
    def skeleton(self, lv: int, crisis: bool = False) -> dict:
        d = SKELETON[self.kind()]
        S = 16 if self.steps == 16 else 12
        pat = dict(d[S][lv])
        if crisis:
            pat.update(d["crisis"][S])
        return pat

    def skeleton_parts(self, lv: int) -> list:
        S = self.steps
        if self.kind() == "legend":
            return [dict(inst="spiccato", style="engine", gain=0.46, oct=-1),
                    dict(inst="bass", style="octbass", gain=0.5),
                    dict(inst="brass", style="hits", gain=0.36 + 0.04 * lv, oct=-1, len=1.5,
                         pattern="X.........x....." if S == 16 else "X.....x.....")]
        return [dict(inst="harp", style="arp", gain=0.3, oct=1, seq="updown", pattern="x" * S, len=ART, spread=0.6),
                dict(inst="synbass", style="pulse", gain=0.36, oct=-1, seq="root", pattern="x." * (S // 2), len=2 * ART)]

    def choir_stabs(self, lv: int) -> list:
        if self.kind() != "phantom":
            return []
        S = self.steps
        return [dict(inst="choir_a", style="hits", gain=0.24 + 0.04 * lv, len=3, pattern="X.......x......." if S == 16 else "X.....x.....")]

    def base_parts(self, ph: dict, lv: int) -> list:
        out = []
        for part in ph.get("base") or []:
            st = part.get("style", "hold")
            if st in ("ostinato", "pulse", "bass", "pizz", "arp"):
                continue   # 뼈대(현악 엔진·아르페지오·베이스)가 대신함
            if st in ("hold", "drone"):
                part = dict(part, gain=part.get("gain", 1.0) * SOFT)
            elif st == "hits":
                part = dict(part, len=min(part.get("len", 4), 2))
            out.append(part)
        return out + self.skeleton_parts(lv)

    def render_drive(self, buf, pat: dict, bars: int, rng, crescendo=False) -> None:
        """뼈대 타악: 4마디 묶음 세기(FORM), 0·8마디 첫 박 크래시, 8마디마다 작은 필인, 마지막 마디 큰 필인."""
        st, S = self.step, self.steps
        fill_n = 4 if S == 16 else 3
        legend = self.kind() == "legend"
        for b in range(bars):
            gf = FORM[min(3, b * 4 // max(4, bars))] if not crescendo else 0.55 + 0.45 * b / max(1, bars - 1)
            big_fill = (b == bars - 1) and bars >= 4
            for k, pp in pat.items():
                for i, ch in enumerate(pp[:S]):
                    if ch not in "xX":
                        continue
                    if big_fill and i >= S - fill_n and k not in ("hat", "shaker"):
                        continue
                    vel = (1.0 if ch == "X" or i % (S // 4) == 0 else 0.8) * gf
                    n = int(DRUM_LEN[k] * RATE)
                    mono = d_tom(n, vel, rng, f=150.0) if k == "tom" else DRUMS[k](n, vel, rng)
                    self._place(buf, mono, b * self.bar + i * st, vel * DRUM_GAIN.get(k, 1.0), DRUM_PAN.get(k, 0.0) + rng.uniform(-0.04, 0.04))
            if bars >= 8 and b in (0, 8):
                self._place(buf, d_crash(int(DRUM_LEN["crash"] * RATE), 1.0, rng), b * self.bar, 0.75, rng.uniform(-0.3, 0.3))
            if big_fill:
                for j in range(fill_n):
                    t0 = b * self.bar + (S - fill_n + j) * st
                    if legend:
                        self._place(buf, d_tom(int(0.6 * RATE), 1.0, rng, f=190.0 - 35.0 * j), t0, 0.85 + 0.05 * j, 0.4 - 0.27 * j)
                        if j == fill_n - 1:
                            self._place(buf, d_snare2(int(0.4 * RATE), 1.0, rng), t0, 1.0, 0.0)
                    else:
                        self._place(buf, d_snap(int(0.25 * RATE), 1.0, rng), t0, 0.5 + 0.1 * j, 0.0)
                        self._place(buf, d_softkick(int(0.5 * RATE), 1.0, rng), t0, 0.5, 0.0)
            elif bars >= 8 and b % 8 == 7:
                for j in range(2):
                    t0 = b * self.bar + (S - 2 + j) * st
                    self._place(buf, (d_snare2 if legend else d_snap)(int(0.35 * RATE), 1.0, rng), t0, (0.55 + 0.2 * j) * (1 if legend else 0.7), 0.0)

    @staticmethod
    def spec_perc(pattern: dict) -> dict:
        """곡 고유 타악(팀파니·큰북·장구 …)은 살리고, 뼈대와 겹치는 하이햇·셰이커·스네어는 뺌."""
        return {k: v for k, v in pattern.items() if k.replace("_last", "") not in ("hat", "shaker", "snare", "ohat", "snap")}

    def rv(self) -> list:
        mix = self.spec.get("reverb", [0.25, 2.6])[0] * 0.62
        return [mix, REVERB[self.kind()]]

    # ── 층 만들기 ──
    def stems(self) -> dict:
        sp = self.spec
        rv = self.rv()
        prv = [rv[0] * 0.45, rv[1] * 0.6]
        out = {}
        n16 = self.loop_len(self.bars)
        phases = sp["phases"]
        for i, ph in enumerate(phases):
            root, scale = self.phase_info(i)
            rng = np.random.default_rng(self.seed + i * 13)
            chords = ph["chords"]
            pre = f"{i + 1}_"
            lv = self.level(i)
            base = self.wrap(self.render_layer(self.base_parts(ph, lv), chords, root, scale, self.bars, rng, rv), n16)
            perc = ph.get("perc", {})

            def perc_layer(pattern, crisis):
                buf = self._buf(self.bars * self.bar)
                self.render_perc(buf, self.spec_perc(pattern), self.bars, rng, root=root)
                self.render_drive(buf, self.skeleton(lv, crisis), self.bars, rng)
                return self.wrap(self.hall(buf, prv[0], prv[1], rng), n16)
            p_norm = perc_layer(perc.get("pattern", {}), False)
            crisis = dict(perc.get("pattern", {}))
            crisis.update(perc.get("crisis", {}))
            p_crisis = perc_layer(crisis, True)
            lead = ph.get("lead") or []
            lrng = np.random.default_rng(self.seed + i * 13 + 1)
            out[pre + "lead"] = self.wrap(self.render_layer(lead, chords, root, scale, self.bars, lrng, rv), n16)
            up = [dict(p, oct=p.get("oct", 0) + 1) for p in lead]
            out[pre + "lead_oct"] = self.wrap(self.render_layer(up, chords, root, scale, self.bars, np.random.default_rng(self.seed + i * 13 + 1), rv), n16)
            choir_parts = [dict(p, gain=p.get("gain", 1.0) * SOFT) if p.get("style", "hold") == "hold" else p for p in ph.get("choir") or []]
            choir = self.wrap(self.render_layer(choir_parts + self.choir_stabs(lv), chords, root, scale, self.bars, rng, rv), n16)
            kt = self.kick_times(self.skeleton(lv), self.bars)
            depth = min(0.6, PUMP[self.kind()] * PUMP_LV[lv])
            base = self.pump(base, kt, depth)
            choir = self.pump(choir, kt, depth * 0.7)
            # 타악 층 비중 맞춤 (보통 믹스 기준 — 위기 타악도 같은 배율)
            e_rest = sum(float((x ** 2).sum()) for x in (base, choir, out[pre + "lead"]))
            e_perc = float((p_norm ** 2).sum())
            share = PERC_SHARE[self.kind()]
            k = np.sqrt(share / (1 - share) * e_rest / max(1e-12, e_perc)) if e_perc > 0 else 1.0
            k = float(np.clip(k, 0.3, 3.0))
            out[pre + "perc"] = p_norm * k
            out[pre + "perc_crisis"] = p_crisis * k
            out[pre + "base"] = base
            out[pre + "choir"] = choir
            if i + 1 < len(phases):
                out[pre + "riser"] = self.riser(i, rng, rv)
        out["intro_mix"] = self.intro(rv)
        return out

    def intro(self, rv) -> np.ndarray:
        """1마디. 전설: 첫 박에 금관 + 큰북 동시 강타 → 뼈대 → 끝 4칸 필인 / 환상: 반짝이며 오르는 아르페지오 + 셰이커 크레셴도."""
        root, scale = self.phase_info(0)
        rng = np.random.default_rng(self.seed + 999)
        it = self.spec.get("intro", {})
        ch = it.get("chords", [1])[:1]
        S, st = self.steps, self.step
        buf = self._buf(self.bar)
        if self.kind() == "legend":
            buf += self.render_layer([dict(inst="spiccato", style="engine", gain=0.46, oct=-1), dict(inst="bass", style="octbass", gain=0.5)],
                                     ch, root, scale, 1, rng, rv)[: len(buf)]
            pat = {k: v for k, v in self.skeleton(0).items()}
            self.render_drive(buf, pat, 1, rng)
            for j in range(4):   # 끝 4칸: 탐 내림 + 스네어 → 1페이즈 첫 박 크래시
                t0 = (S - 4 + j) * st
                self._place(buf, d_tom(int(0.6 * RATE), 1.0, rng, f=190.0 - 35.0 * j), t0, 0.8, 0.4 - 0.27 * j)
            self._place(buf, d_snare2(int(0.4 * RATE), 1.0, rng), (S - 1) * st, 1.0, 0.0)
        else:
            cm = chord_midis(ch[0], root, scale)
            notes = [m + 12 * o for o in (0, 1, 2) for m in cm] + [cm[0] + 36]
            for k in range(S):   # 반짝이며 오르는 16분
                self.note(buf, "harp", notes[k % len(notes)] + 12, k * st, st * ART, 0.25 + 0.35 * k / (S - 1), (k % 2 - 0.5) * 0.6, rng, rel=0.4)
                self.note(buf, "celesta", notes[k % len(notes)] + 24, k * st, st * ART, 0.12 + 0.18 * k / (S - 1), 0.0, rng, rel=0.4)
                self._place(buf, d_shaker(int(DRUM_LEN["shaker"] * RATE), 1.0, rng), k * st, 0.15 + 0.35 * k / (S - 1), -0.3)
            buf = self.hall(buf, rv[0], rv[1], rng)
        hit = self._buf(1.0)   # 첫 박 강타
        self._place(hit, d_bigdrum(int(1.4 * RATE), 1.0, rng), 0.0, 1.0 if self.kind() == "legend" else 0.5, 0.0)
        for m in chord_midis(1, root, scale):
            self.note(hit, it.get("hit_inst", "brass"), m - 12, 0.0, self.q * 1.0, 0.8, 0.0, rng)
        buf[: len(hit)] += self.hall(hit, rv[0], rv[1], rng)[: len(hit)]
        n = self.loop_len(1)
        out = buf[: n + int(RATE * 0.02)].copy()
        out[n:] *= np.linspace(1, 0, len(out) - n)[:, None]
        return out[:n]
