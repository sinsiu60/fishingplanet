"""음표 데이터 작곡 도우미 (DESIGN.md 43-28): 작곡 스크립트(compose_*.py)가 음을 하나하나 적어 data/music/<이름>_notes.json 을 만든다.

게임(src/audio/boss_notes.py)은 이 json 을 그대로 연주만 한다. 이 파일은 '적는 도구'일 뿐 곡을 지어내지 않음:
음높이 이름('D5', 'Bb3') → MIDI, 음 잇기(seq), 스윙(뒷박 8분을 2:1 로 — 적힌 위치를 바꿔 기록), json 저장.
"""
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
NOTE = {"C": 0, "C#": 1, "Db": 1, "D": 2, "D#": 3, "Eb": 3, "E": 4, "F": 5, "F#": 6, "Gb": 6, "G": 7, "G#": 8, "Ab": 8, "A": 9,
        "A#": 10, "Bb": 10, "B": 11, "Cb": 11}


def m(name):
    """'Ab4' → MIDI (정수는 그대로, None·'r' = 쉼)."""
    if name is None or isinstance(name, (int, float)):
        return name
    if name == "r":
        return None
    p, o = (name[:2], name[2:]) if len(name) > 2 and name[1] in "b#" else (name[:1], name[1:])
    return 12 * (int(o) + 1) + NOTE[p]


def swing(t: float, unit: float = 1.0, ratio: float = 2 / 3) -> float:
    """곧은 박 위치 → 스윙 위치 (unit 박마다 반 박 자리를 ratio 로)."""
    k, r = divmod(t, unit)
    if abs(r - unit / 2) < 1e-6:
        r = unit * ratio
    elif r > unit / 2:
        r = unit * ratio + (r - unit / 2) * (1 - ratio) / 0.5
    else:
        r = r * ratio / 0.5
    return k * unit + r


class Score:
    def __init__(self, title: str, bpm: float):
        self.title, self.bpm = title, bpm
        self.notes, self.markers, self.sigs, self.tempos = [], [], [], []
        self.loops, self.layers, self.voices, self.gains, self.pans = {}, {}, {}, {}, {}
        self.crisis, self.transitions, self.fail = {}, {}, None
        self.swing_on = False

    # ── 적기 ──
    def add(self, track, start, dur, pitch, vel=96, into=None):
        p = m(pitch)
        if p is None:
            return
        s, e = float(start), float(start) + float(dur)
        if self.swing_on:
            s, e = swing(s), swing(e)
        (self.notes if into is None else into).append(dict(track=track, start=round(s, 4), dur=round(max(0.05, e - s), 4), pitch=int(p), vel=int(vel)))

    def seq(self, track, start, items, vel=96, into=None):
        """items = [(음 · 화음 목록 · None 쉼, 길이)] 를 이어 적고 끝 박을 돌려줌."""
        t = start
        for p, d in items:
            if isinstance(p, (list, tuple)):
                for q in p:
                    self.add(track, t, d, q, vel, into)
            else:
                self.add(track, t, d, p, vel, into)
            t += d
        return t

    def bar_check(self, items, beats, what=""):
        tot = sum(d for _, d in items)
        assert abs(tot - beats) < 1e-6, f"{what}: {tot} 박 (마디 {beats} 박이어야)"

    def ornament(self, tracks, pcs, a: float, b: float, side: int = 1, min_dur: float = 1.0, grace: float = 0.17, every: int = 1):
        """[a, b) 박 안 tracks 의 긴 음(min_dur 박 이상) 앞에 꾸밈음을 붙인다 (side=1 위 이웃음 · -1 아래 이웃음, pcs = 음계 음 이름 집합).
        꾸밈음이 본음 머리를 grace 박만큼 가져간다 — 시김새(꺾는 소리) · 마두금 밑꾸밈처럼 장르마다 선율 모양을 다르게 하려고."""
        pcs = {m(f"{x}4") % 12 for x in pcs}
        keep = set()   # 주인의 동기(으뜸음 → 5도 위 → 4도 위, 1:1:2)는 꾸미지 않음 — 모든 전설 곡 공통 동기 그대로
        for tr in tracks:
            ns = sorted((n for n in self.notes if n["track"] == tr), key=lambda n: n["start"])
            for x, y, z in zip(ns, ns[1:], ns[2:]):
                if y["pitch"] - x["pitch"] == 7 and z["pitch"] - x["pitch"] == 5 and abs(y["dur"] - x["dur"]) < 1e-6 and abs(z["dur"] - 2 * x["dur"]) < 1e-6:
                    keep |= {id(x), id(y), id(z)}
        cand = sorted((n for n in self.notes if n["track"] in tracks and a <= n["start"] < b and n["dur"] >= min_dur and id(n) not in keep),
                      key=lambda n: n["start"])
        for i, n in enumerate(cand):
            if i % every:
                continue
            q = n["pitch"] + side
            while q % 12 not in pcs:
                q += side
            self.notes.append(dict(n, pitch=q, dur=round(grace, 4), vel=max(1, n["vel"] - 12)))
            n["start"], n["dur"] = round(n["start"] + grace, 4), round(n["dur"] - grace, 4)

    # ── 저장 ──
    def save(self, name: str):
        d = dict(title=self.title, bpm=self.bpm, time_signatures=[dict(beat=b, sig=s) for b, s in self.sigs],
                 markers=[dict(beat=b, name=n) for b, n in self.markers], loops=self.loops,
                 layers=self.layers, voices=self.voices, gains=self.gains, pans=self.pans,
                 notes=sorted(self.notes, key=lambda n: (n["start"], n["track"], n["pitch"])))
        if self.tempos:
            d["tempos"] = [dict(beat=b, bpm=v) for b, v in self.tempos]
        if self.crisis:
            d["crisis"] = {k: sorted(v, key=lambda n: n["start"]) for k, v in self.crisis.items()}
        if self.transitions:
            d["transitions"] = self.transitions
        if self.fail:
            d["fail"] = self.fail
        p = os.path.join(ROOT, "data", "music", f"{name}_notes.json")
        json.dump(d, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        n_tr = len({n["track"] for n in self.notes})
        print(f"썼음: {os.path.relpath(p, ROOT)} — 음 {len(self.notes)}개 · 트랙 {n_tr}개")
        return p
