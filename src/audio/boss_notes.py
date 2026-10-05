"""음표 데이터 곡 (ORSIEL_BGM.md, DESIGN.md 43-27): data/music/<이름>_notes.json 의 음표를 '그대로' 연주. 스펙에 "notes": "<이름>".

다른 곡처럼 공통 연주법(화음 → 분산화음 · 오스티나토 …)으로 만들지 않고, 작곡 데이터의 음 하나하나(트랙 · 시작 박 · 길이 · 음높이 · 세기)를
게임 음색으로 소리 낸다. 패턴 섞기 · 자동 변형 · 조옮김 없음 (유일한 예외: 규칙인 '지침 = 주선율 한 옥타브 위', '위기 = taiko 8분 2배').
  json   bpm · time_signatures [{beat, sig}] (박자 변화 — 4/4 → 7/8 → 4/4) · markers · loops {phaseN: [시작 박, 끝 박]} ·
         notes [{track, start, dur, pitch, vel}] (박 = 4분음표)
  층     ORSIEL_BGM.md 규칙 표:
           바탕  bass · strings · strings_trem · lowbrass  (+ 특수 bell · whale · riser — 바탕 층과 함께 재생)
           타악  taiko · timpani · kick · snare · tick · crash
           주선율 horn · trumpet          합창 choir
  인트로 = loops 첫 페이즈 앞 구간 (예: 0~8박) 전체 / 반복 = 각 loops 구간, 반복 끝을 넘는 울림은 앞으로 감음 (Song.wrap)
  위기  타악 층 + taiko 를 그 페이즈 박자의 8분음표마다 (이미 있는 자리는 그대로)
  지침  주선율 층을 한 옥타브 위 (BOSS_BGM 규칙)
  전환  데이터에 없는 음을 지어내지 않도록 라이저는 0.02초 무음 → 다음 마디 경계에서 바로 다음 페이즈 (박자는 BossMusic.timing 이 페이즈마다)
  실패  천해의 종 아주 낮게 '둥' + taiko + 1.5초 울림 (BOSS_BGM 규칙: 즉시 정지 + 낮은 '쿵')
  음색  boss_synth 오케스트라 (현악 스피카토 · 트레몰로 · 금관 · 호른 · 트럼펫 · 합창 · 팀파니 · 북) + 새 음색 2개
         천해의 종 (아주 낮은 큰 종 — 비정수 배음 · 맥놀이 · 8초 넘게 울림) · 고래 울음 (낮게 미끄러지며 우는 소리)
"""
import json

import numpy as np

from src.audio import boss_celtic, boss_synth as bs, boss_trance
from src.audio.boss_muhyeop import _env, _norm, _ph
from src.audio.boss_synth import RATE, Song, _bw_filter, _t, hz, noise

LAYER = {"bass": "base", "strings": "base", "strings_trem": "base", "lowbrass": "base", "bell": "base", "whale": "base", "riser": "base",
         "taiko": "perc", "timpani": "perc", "kick": "perc", "snare": "perc", "tick": "perc", "crash": "perc",
         "horn": "lead", "trumpet": "lead", "choir": "choir"}
PERC = {k for k, v in LAYER.items() if v == "perc"}


def load_notes(name: str) -> dict:
    from src.core.paths import data_path
    p = data_path("music", f"{name}_notes.json")
    return json.load(open(p, encoding="utf-8"))


# ───────────────────────── 새 음색 ─────────────────────────

BELL_PARTIALS = ((0.5, 0.9, 0.18), (1.0, 1.0, 0.22), (1.183, 0.7, 0.3), (1.506, 0.55, 0.36), (2.0, 0.5, 0.42), (2.514, 0.35, 0.55),
                 (3.011, 0.3, 0.7), (4.166, 0.2, 0.95), (5.43, 0.14, 1.3), (6.79, 0.09, 1.7))


def i_abyss_bell(f, n, rng):
    """천해의 종: 아주 낮은 큰 종 — 비정수 배음(험 0.5 · 기본 · 단3도쯤 1.183 · 1.506 · 2.514 · 4.166 …), 배음마다 짝이 살짝 어긋나 맥놀이,
    낮은 배음일수록 오래 (8초 넘게) 울림 + 치는 순간 쇠 '쾅'."""
    t = _t(n)
    x = np.zeros(n)
    for r, a, d in BELL_PARTIALS:
        fr = f * r
        if fr > 9000:
            continue
        x += a * (np.sin(2 * np.pi * fr * t + rng.uniform(0, 6)) + 0.6 * np.sin(2 * np.pi * fr * 1.0025 * t)) * np.exp(-t * d)
    m = min(n, int(0.03 * RATE))
    x[:m] += _bw_filter(noise(m, rng), "bp", (300, 2500))[:m] * np.exp(-np.arange(m) / (m / 4)) * 1.2
    return _norm(x) * np.minimum(1, t / 0.004)


def i_whale(f, n, rng):
    """고래 울음: 낮은 음이 위에서 미끄러져 내려왔다 다시 살짝 오르며 떨림 + 몸통 울림(두 모음) + 숨, 천천히 부풀었다 사라짐."""
    t = _t(n)
    u = t / max(t[-1], 1e-6)
    semi = 5.0 * np.exp(-u * 4) - 3.0 * np.sin(np.pi * u) ** 2 + 0.35 * np.sin(2 * np.pi * 3.1 * t) * np.clip(u * 3, 0, 1)
    f_t = f * 2 ** (semi / 12)
    src = sum(np.sin(k * _ph(f_t)) / k ** 1.1 for k in range(1, 18))
    x = 0.8 * _bw_filter(src, "bp", (f * 1.5, f * 4.5)) + 0.5 * _bw_filter(src, "lp", f * 1.6)
    x = x + _bw_filter(noise(n, rng), "bp", (200, 900)) * 0.08
    env = np.sin(np.pi * np.clip(u, 0, 1)) ** 0.8
    return _norm(x) * env


def i_riser(f, n, rng):
    """상승: 잡음이 밝아지며 커지고 + 한 옥타브 아래에서 그 음까지 미끄러져 오르는 소리."""
    t = _t(n)
    u = t / max(t[-1], 1e-6)
    tone = np.sin(_ph(f * 2 ** ((u - 1) * 12 / 12))) * u ** 2
    return _norm(0.6 * boss_trance.s_riser(n, rng) + 0.5 * tone)


# ───────────────────────── 트랙 → 게임 음색 ─────────────────────────

def _orch(name, lp=None):
    fn = bs.INST[name]

    def play(f, n, rng):
        x = fn(f, n, 1.0, rng)
        return _bw_filter(x, "lp", lp) if lp else x
    return play


VOICE = {"bass": _orch("bass"), "strings": _orch("spiccato"), "strings_trem": _orch("tremolo"), "lowbrass": _orch("brass"),
         "horn": _orch("horn"), "trumpet": _orch("trumpet"), "choir": _orch("choir"), "choir_a": _orch("choir_a"),
         "bell": i_abyss_bell, "whale": i_whale, "riser": i_riser}
TRACK_GAIN = {"bass": 0.3, "strings": 0.22, "strings_trem": 0.16, "lowbrass": 0.55, "horn": 0.8, "trumpet": 0.4, "choir": 0.9,
              "bell": 0.5, "whale": 0.5, "riser": 0.35,
              "taiko": 1.3, "timpani": 0.9, "kick": 0.75, "snare": 0.55, "tick": 0.38, "crash": 0.3}
RING = {"bell": 9.0, "whale": 1.0, "riser": 0.2}   # 음 길이 뒤로 더 울리는 초 (종은 길게)


def vel_gain(v: int) -> float:
    return (max(1, v) / 127.0) ** 1.4


# ───────────────────────── 곡 ─────────────────────────

class NotesSong(Song):
    def __init__(self, sid, spec, master):
        super().__init__(sid, spec, master)
        self.data = load_notes(spec["notes"])
        self.bpm = self.data.get("bpm", self.bpm)
        self.q = 60.0 / self.bpm
        self.sigs = sorted(((float(s["beat"]), s["sig"]) for s in self.data["time_signatures"]))
        self.loops = [tuple(self.data["loops"][k]) for k in sorted(self.data["loops"], key=lambda k: self.data["loops"][k][0])]
        self.set_phase(0)

    # ── 박자 ──
    def sig_at(self, beat: float) -> tuple[int, int]:
        cur = "4/4"
        for b, s in self.sigs:
            if beat + 1e-6 >= b:
                cur = s
        num, den = (int(v) for v in cur.split("/"))
        return num, den

    def set_phase(self, i: int) -> None:
        a, b = self.loops[i]
        num, den = self.sig_at(a)
        self.bar = self.q * num * 4 / den
        self.steps = int(round(num * 16 / den))
        self.step = self.bar / self.steps
        self.bars = int(round((b - a) * self.q / self.bar))
        self.span = (a, b)

    # ── 소리 ──
    def note(self, buf, inst: str, midi: float, start: float, dur: float, gain=1.0, p=0.0, rng=None, rel=0.3) -> None:
        n = int((dur + rel) * RATE)
        if n <= 0:
            return
        key = (inst, round(midi, 2), n // 64)
        mono = self._cache.get(key)
        if mono is None:
            mono = VOICE[inst](hz(midi), n, rng).astype(np.float32)
            if inst not in ("bell", "whale", "riser"):
                mono = mono * _env(n, 0.002, 0.0, min(rel, 0.25)).astype(np.float32)
            if len(self._cache) < 5000:
                self._cache[key] = mono
        self._place(buf, mono, start, gain, p)

    def hit(self, buf, track: str, midi: int, start: float, vel: float, rng) -> None:
        """타악 한 번 (트랙 → 게임 북)."""
        g = TRACK_GAIN[track] * vel
        if track == "taiko":   # 일본 북처럼 단단한 '둥' + 큰북의 무게
            self._place(buf, bs.d_taiko(int(0.6 * RATE), 1.0, rng), start, g * 0.8, -0.05)
            self._place(buf, bs.d_bigdrum(int(1.2 * RATE), 1.0, rng), start, g * 0.45, 0.05)
        elif track == "timpani":
            self._place(buf, bs.d_timp(int(1.4 * RATE), 1.0, rng, f=hz(midi)), start, g, 0.0)
        elif track == "kick":
            self._place(buf, bs.d_kick(int(0.4 * RATE), 1.0, rng), start, g, 0.0)
        elif track == "snare":
            self._place(buf, bs.d_snare2(int(0.35 * RATE), 1.0, rng), start, g, 0.08)
        elif track == "tick":  # 8분 똑딱: 나무 막대 '딱'
            self._place(buf, boss_celtic.d_rim(int(0.15 * RATE), 1.0, rng), start, g, 0.3)
        elif track == "crash":
            self._place(buf, bs.d_crash(int(2.4 * RATE), 1.0, rng), start, g, 0.25)

    def render_part(self, buf, part: dict, chords, root, scale, bars, rng, crescendo=False) -> None:
        if not part.get("raw"):
            return super().render_part(buf, part, chords, root, scale, bars, rng, crescendo)
        o = 12 * part.get("oct", 0)
        for nt in part["notes"]:
            tr = nt["track"]
            t0 = nt["at"] * self.q
            dur = nt["dur"] * self.q
            inst = "choir_a" if tr == "choir" and part.get("bright") else tr
            pan = {"strings": -0.3, "strings_trem": 0.3, "horn": -0.15, "trumpet": 0.2, "lowbrass": 0.1}.get(tr, 0.0)
            self.note(buf, inst, nt["pitch"] + o, t0, dur * 0.97, TRACK_GAIN[tr] * vel_gain(nt["vel"]) * part.get("gain", 1.0), pan, rng,
                      rel=RING.get(tr, 0.25))

    def render_perc(self, buf, pattern: dict, bars, rng, crescendo=False, root=None) -> None:
        for nt in pattern["notes"]:
            self.hit(buf, nt["track"], nt["pitch"], nt["at"] * self.q, vel_gain(nt["vel"]), rng)

    # ── 층 만들기 ──
    def pick(self, a: float, b: float, layer: str) -> list:
        """구간 [a, b) 에서 시작하는 그 층의 음 (시작 박을 구간 처음 기준으로)."""
        return [dict(n, at=n["start"] - a) for n in self.data["notes"] if a - 1e-6 <= n["start"] < b - 1e-6 and LAYER.get(n["track"]) == layer]

    def crisis_taiko(self, a: float, b: float, notes: list) -> list:
        """위기: taiko 를 이 페이즈 박자의 8분음표마다 (이미 있는 자리는 그대로)."""
        tk = [n for n in notes if n["track"] == "taiko"]
        pitch = max(set(n["pitch"] for n in tk), key=[n["pitch"] for n in tk].count) if tk else 36
        have = {round(n["at"], 3) for n in tk}
        out = list(notes)
        t = 0.0
        while t < (b - a) - 1e-6:
            if round(t, 3) not in have:
                out.append(dict(track="taiko", at=t, dur=0.5, pitch=pitch, vel=76))
            t += 0.5
        return out

    def stems(self) -> dict:
        sp = self.spec
        rv = sp.get("reverb", [0.2, 1.2])
        prv = [rv[0] * 0.6, rv[1] * 0.7]
        out = {}
        for i, (a, b) in enumerate(self.loops[: len(sp["phases"])]):
            self.set_phase(i)
            n_loop = int(round((b - a) * self.q * RATE))
            rng = np.random.default_rng(self.seed + i * 13)
            pre = f"{i + 1}_"
            ph = sp["phases"][i] if i < len(sp["phases"]) else {}
            bright = ph.get("bright_choir", False)

            def lay(layer, notes=None, r=rv, oct=0, perc=False, g=None):
                notes = self.pick(a, b, layer) if notes is None else notes
                if hasattr(self, "ev"):   # 측정 도구(boss_rhythm_check)의 '소리 없는' 곡: 층 이름 기록
                    self.layer, self.skip = layer, False
                buf = self._buf((b - a) * self.q)
                if perc:
                    self.render_perc(buf, {"notes": notes}, self.bars, g or rng)
                else:
                    self.render_part(buf, {"raw": True, "notes": notes, "oct": oct, "bright": bright, "style": "melody" if layer == "lead" else "raw"},
                                     None, None, None, self.bars, g or rng)
                buf = self.hall(buf, r[0], r[1], rng) if r else buf
                return self.wrap(buf, n_loop)
            out[pre + "base"] = lay("base")
            perc = self.pick(a, b, "perc")
            out[pre + "perc"] = lay("perc", perc, prv, perc=True)
            out[pre + "perc_crisis"] = lay("perc", self.crisis_taiko(a, b, perc), prv, perc=True)
            out[pre + "lead"] = lay("lead", g=np.random.default_rng(self.seed + i * 13 + 1))
            out[pre + "lead_oct"] = lay("lead", oct=1, g=np.random.default_rng(self.seed + i * 13 + 1))   # 지침: 주선율 한 옥타브 위
            out[pre + "choir"] = lay("choir")
            if i + 1 < len(sp["phases"]):
                out[pre + "riser"] = np.zeros((int(0.02 * RATE), 2))   # 지어낸 음 없이 마디 경계에서 바로 다음 페이즈
        self.set_phase(0)
        out["intro_mix"] = self.intro(rv)
        out["fail"] = self.fail_sound(rv)
        return out

    def intro(self, rv) -> np.ndarray:
        """인트로 = 첫 반복 구간 앞 (데이터 그대로, 모든 층)."""
        a0 = self.loops[0][0]
        rng = np.random.default_rng(self.seed + 999)
        L = a0 * self.q
        buf = self._buf(L)
        for layer in ("base", "lead", "choir"):
            self.render_part(buf, {"raw": True, "notes": self.pick(0.0, a0, layer)}, None, None, None, 1, rng)
        self.render_perc(buf, {"notes": self.pick(0.0, a0, "perc")}, 1, rng)
        buf = self.hall(buf, rv[0], rv[1], rng)
        n = int(round(L * RATE))
        out = buf[:n].copy()   # 인트로 끝을 넘는 울림(종 · 고래)은 끊지 않고 짧게 줄여 1페이즈 첫 박으로
        f = int(0.05 * RATE)
        out[-f:] *= np.linspace(1, 0.4, f)[:, None]
        return out

    def fail_sound(self, rv) -> np.ndarray:
        """실패: 천해의 종 아주 낮게 '둥' + taiko + 1.5초 울림."""
        rng = np.random.default_rng(self.seed + 777)
        L = 2.2
        buf = self._buf(L)
        self.note(buf, "bell", 24, 0.0, 0.5, 0.7, 0.0, rng, rel=1.7)
        self.hit(buf, "taiko", 36, 0.0, 1.0, rng)
        buf = self.hall(buf, rv[0], rv[1], rng)   # 1.5초 울림은 종 자체의 울림으로
        n = int(L * RATE)
        out = buf[:n].copy()
        out[-int(RATE * 0.3):] *= np.linspace(1, 0, int(RATE * 0.3))[:, None]
        return out
