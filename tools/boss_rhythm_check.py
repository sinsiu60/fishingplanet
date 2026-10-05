"""전설·환상 BGM 전투감 측정 (BOSS_BGM_FIX.md 4번 측정 목표, DESIGN.md 43-13 — 개발용).

곡마다 1페이즈를 '소리 없이' 다시 만들어 음 시작을 세고(합성은 건너뜀), 구운 파일로 타악 비중을 잰다.
  - 빠르기·박자, 마디 길이
  - 한 마디 안 음 시작 횟수 (모든 층 합 — 같은 악기가 같은 순간 친 화음은 1번, 타악은 같은 순간 1번)
  - 1박 이상 이어지는 음의 비율 (선율·화음 음 중)
  - 타악 층 에너지 비중 (구운 1페이즈 보통 믹스: 타악 / (바탕+타악+주선율+합창))
  - 잔향 길이 (실제로 쓰는 값)
목표: 전설 음 시작 ≥24 · 긴 음 ≤30% · 타악 25~35% / 환상 ≥20 · ≤35% · 20~30%

  python tools/boss_rhythm_check.py            모든 곡
  python tools/boss_rhythm_check.py L02 P04    그 곡만
  python tools/boss_rhythm_check.py --dir 폴더  구운 파일 폴더 (시험 굽기)
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))
os.chdir(ROOT)


GOAL = {"legend": (24, 0.30, (0.25, 0.35)), "phantom": (20, 0.35, (0.20, 0.30))}
REVERB = {"legend": 1.2, "phantom": 1.8}
# BOSS_BGM_FIX 1번 빠르기표 (엔진 bpm = 4분음표 기준 — 6/8 은 점4분 × 1.5)
TEMPO = {"L01": 152, "L02": 168, "L03": 156, "L04": 150, "L05": 136, "L06": 160, "L07": 150, "L08": 158, "L09": 172, "L10": 176,
         "L11": 144, "L12": 162, "P01": 138, "P02": 140, "P03": 144, "P04": 160, "P05": 136, "P06": 140, "P07": 142, "P08": 136,
         "P09": 138, "P10": 150, "P11": 135, "P12": 148}


def dry_class(base):
    """합성 없이 음 시작만 기록하는 곡 (base = Song 또는 BattleSong)."""
    class Dry(base):
        def __init__(self, *a, **k):
            super().__init__(*a, **k)
            self.ev = []          # (층, 악기, 시작, 길이)
            self.layer = ""
            self.skip = False     # 위기 타악 · 인트로는 세지 않음
            self.n_perc = 0

        def note(self, buf, inst, midi, start, dur, gain=1.0, p=0.0, rng=None, rel=0.3):
            if not self.skip:
                self.ev.append((self.layer, inst, round(start, 4), dur))

        def _place(self, buf, mono, start, gain, p):
            if self.layer and not self.skip:
                self.ev.append((self.layer, "drum", round(start, 4), 0.0))

        def render_perc(self, *a, **k):   # 페이즈마다 보통 → 위기 순서로 불림: 둘째(위기)는 세지 않음
            self.n_perc += 1
            if not getattr(self, "in_intro", False):
                self.skip = self.n_perc % 2 == 0
            return super().render_perc(*a, **k)

        def intro(self, *a, **k):
            self.in_intro, self.skip = True, True
            return super().intro(*a, **k)

        def hall(self, x, mix, time, rng):
            self.rv_time = max(getattr(self, "rv_time", 0.0), time if mix > 0 else 0.0)
            return x

        def pump(self, x, kicks, depth):
            return x
    return Dry


def measure(sid: str, spec: dict, mcfg: dict) -> dict:
    from src.audio import boss_synth
    cls = boss_synth.Song
    if spec.get("battle"):
        from src.audio import boss_battle
        cls = boss_battle.BattleSong
    D = dry_class(cls)
    s = D(sid, spec, mcfg)
    # 1페이즈만: 층 이름을 바꿔 가며 기록 (stems 를 그대로 돌리되 1페이즈 기록만 씀)
    orig = s.render_layer

    def tagged(parts, *a, **k):
        if k.get("perc") is not None or parts is None:
            s.layer = "perc"
        elif parts and all(p.get("style") == "melody" for p in parts):
            s.layer = "lead"
        else:
            s.layer = "base"
        if not getattr(s, "in_intro", False):
            s.skip = False
        return orig(parts, *a, **k)
    s.render_layer = tagged
    real_stems = s.stems

    def only_first():
        sp = dict(s.spec)
        s.spec = dict(sp, phases=sp["phases"][:1])
        try:
            return real_stems()
        finally:
            s.spec = sp
    st = only_first()
    intro_bars = len(st["intro_mix"]) / boss_synth.RATE / s.bar
    bars = s.bars
    t_end = bars * s.bar
    ev = [e for e in s.ev if 0 <= e[2] < t_end and e[0] in ("base", "perc", "lead")]
    onsets = len({(e[1] if e[1] != "drum" else "drum", e[2]) for e in ev})
    notes = [e for e in ev if e[1] != "drum"]
    uniq = {(e[1], e[2]): e[3] for e in notes}
    long_ratio = sum(1 for d in uniq.values() if d >= s.q * 0.999) / max(1, len(uniq))
    lead = {(e[1], e[2]): e[3] for e in ev if e[0] == "lead" and e[1] != "drum"}
    per_bar = {}
    for (inst, t), dur in lead.items():
        if dur >= 2 * s.q * 0.9:   # 2박으로 적은 음 (실제 울림은 95%)
            per_bar.setdefault((inst, int(t // s.bar)), 0)
            per_bar[(inst, int(t // s.bar))] += 1
    lead_long = max(per_bar.values()) if per_bar else 0
    chords = s.spec["phases"][0]["chords"]
    changes = sum(1 for a, b in zip(chords, chords[1:]) if a != b)
    return {"bpm": spec["bpm"], "meter": spec.get("meter", [4, 4]), "onsets": onsets / bars, "long": long_ratio,
            "lead_long": lead_long, "chord_bars": bars / max(1, changes + 1),
            "reverb": getattr(s, "rv_time", 0.0), "bar": s.bar, "intro": intro_bars}


def perc_share(sid: str, d: str) -> float | None:
    from boss_loudness import find, load
    parts = {}
    for l in ("base", "perc", "lead", "choir"):
        p = find(d, f"{sid}_1_{l}")
        if p is not None:
            parts[l] = load(p)
    if "perc" not in parts:
        return None
    n = min(len(v) for v in parts.values())
    e = {k: float((v[:n] ** 2).sum()) for k, v in parts.items()}
    return e["perc"] / max(1e-12, sum(e.values()))


def main(argv: list[str]) -> int:
    from src.audio import boss_synth
    d = os.path.join(ROOT, "assets", "music_generated", "boss")
    if "--dir" in argv:
        d = argv[argv.index("--dir") + 1]
        argv = [a for a in argv if a not in ("--dir", d)]
    songs, mcfg = boss_synth.song_specs()
    names = [a for a in argv if not a.startswith("--")] or [k for k, v in songs.items() if not v.get("test")]
    print(f"{'곡':4} {'빠르기':>6} {'박자':>5} {'음 시작/마디':>11} {'긴 음':>6} {'타악 비중':>8} {'잔향':>6} {'화음 간격':>8} {'선율 2박↑/마디':>12} {'인트로':>5}   목표와 다른 것")
    rows = []
    for sid in names:
        sp = songs[sid]
        kind = "phantom" if sp.get("kind") == "phantom" else "legend"
        m = measure(sid, sp, mcfg)
        ps = perc_share(sid, d)
        g_on, g_long, (g_lo, g_hi) = GOAL[kind]
        miss = []
        if m["onsets"] < g_on:
            miss.append(f"음 시작 {m['onsets']:.0f}<{g_on}")
        if m["long"] > g_long:
            miss.append(f"긴 음 {m['long']:.0%}>{g_long:.0%}")
        if ps is not None and not g_lo <= ps <= g_hi:
            miss.append(f"타악 {ps:.0%}≠{g_lo:.0%}~{g_hi:.0%}")
        num, den = m["meter"]
        rows.append((sid, m, ps, miss))
        if m["chord_bars"] > 1.01:
            miss.append(f"화음 {m['chord_bars']:.1f}마디마다")
        if m["lead_long"] > 1:
            miss.append(f"선율 긴 음 마디당 {m['lead_long']}개")
        if m["bpm"] != TEMPO.get(sid, m["bpm"]):
            miss.append(f"빠르기 {m['bpm']}→{TEMPO[sid]}")
        if m["reverb"] > REVERB[kind] + 0.05:
            miss.append(f"잔향 {m['reverb']:.1f}>{REVERB[kind]}초")
        if m["intro"] > 1.01:
            miss.append(f"인트로 {m['intro']:.0f}마디")
        print(f"{sid:4} {m['bpm']:6} {num}/{den:<3} {m['onsets']:11.1f} {m['long']:6.0%} {('-' if ps is None else f'{ps:.0%}'):>8} {m['reverb']:5.1f}초 "
              f"{m['chord_bars']:6.1f}마디 {m['lead_long']:10d} {m['intro']:5.0f}마디   "
              + (", ".join(miss) if miss else "ok"))
    print("목표 (BOSS_BGM_FIX 1·3·4번): 전설 음 시작 ≥24 · 긴 음 ≤30% · 타악 25~35% · 잔향 1.2초 / 환상 ≥20 · ≤35% · 20~30% · 1.8초"
          " / 화음 1마디 이하 · 선율 2박↑ 마디당 1개 · 인트로 1마디 · 빠르기표")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
