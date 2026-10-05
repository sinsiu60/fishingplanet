"""주선율 유사도 검사 (ORSIEL_BGM.md '다른 곡도 리믹스처럼 들리지 않게', DESIGN.md 43-27).

게임에서 실제로 나오는 전설 · 환상 전투 곡(테마 곡이 원곡을 대신하면 테마 곡)의 주선율을 뽑아
음 간격(반음 수) 4개씩 묶은 조각들을 서로 비교한다. 겹침 = 두 곡에 같이 있는 조각 수 / 조각이 적은 곡의 조각 수.
리듬 · 조성 · 빠르기와 상관없이 '선율의 모양'이 같은지를 본다 (조옮김해도 같은 간격이면 같은 조각).

  주선율   스펙 곡 = 페이즈마다 lead 첫 파트(주선율)의 음 (도수 → MIDI), 음표 데이터 곡 = horn · trumpet 중 같은 박에서 가장 높은 음
  공통 동기 제외   주인의 동기(으뜸음 → 5도 위 → 4도 위, 1:1:2) · 이름 없는 것의 동기(으뜸음 → #4 → 5도 → 3도, 1:1:2:4) 자리의 음은 빼고,
                   그 자리에서 선율을 끊어 앞뒤를 따로 셈
  기준     겹침 20% 이상 = 경고

사용: python tools/audio/melody_similarity.py [--all] [--min 0.2]
      --all  원곡(테마 곡으로 대체된 L01~L12)까지 포함
      --try 이름:곡ID   게임에 넣기 전 새 음표 데이터(data/music/<이름>_notes.json)로 그 곡을 바꿔 넣고 비교 (여러 번 가능)
"""
import json
import os
import sys
from itertools import combinations

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from src.audio import boss_flamenco  # noqa: E402,F401  (프리지안 도미넌트 음계 등록)
from src.audio.boss_synth import degree_to_midi  # noqa: E402


def phrases_from_spec(sp: dict) -> list:
    """[(시작 초, 길이 박, MIDI)] 목록들 (페이즈마다 하나)."""
    out = []
    for ph in sp["phases"]:
        lead = ph.get("lead") or []
        if not lead:
            continue
        root = sp["root"] + ph.get("transpose", 0)
        scale = ph.get("scale", sp.get("scale", "minor"))
        o = 12 * lead[0].get("oct", 0)
        num, den = ph.get("meter", sp.get("meter", [4, 4]))
        bar = num * 4 / den
        notes = sorted(((b * bar + at, ln, degree_to_midi(d, root, scale) + o) for b, at, d, ln in lead[0]["notes"]), key=lambda x: x[0])
        out.append(notes)
    return out


def phrases_from_notes(name: str) -> list:
    d = json.load(open(os.path.join(ROOT, "data", "music", f"{name}_notes.json"), encoding="utf-8"))
    lead = {t for t, lay in d.get("layers", {}).items() if lay == "lead"} or {"horn", "trumpet"}
    top = {}
    for n in d["notes"]:
        if n["track"] in lead:
            k = round(n["start"], 3)
            if k not in top or n["pitch"] > top[k][2]:
                top[k] = (n["start"], n["dur"], n["pitch"])
    out = []
    for a, b in sorted(d["loops"].values()):
        out.append(sorted(v for v in top.values() if a <= v[0] < b))
    return out


def strip_motifs(notes: list) -> list:
    """공통 동기 자리를 빼고 남은 연속 구간들."""
    drop = set()
    for i in range(len(notes)):
        if i + 2 < len(notes):   # 주인의 동기
            a, b, c = notes[i:i + 3]
            if b[2] - a[2] == 7 and c[2] - a[2] == 5 and abs(b[1] - a[1]) < 1e-6 and abs(c[1] - 2 * a[1]) < 1e-6:
                drop |= {i, i + 1, i + 2}
        if i + 3 < len(notes):   # 이름 없는 것의 동기
            a, b, c, e = notes[i:i + 4]
            if (b[2] - a[2], c[2] - a[2], e[2] - a[2]) == (6, 7, 4) and abs(b[1] - a[1]) < 1e-6 and abs(c[1] - 2 * a[1]) < 1e-6:
                drop |= {i, i + 1, i + 2, i + 3}
    segs, cur = [], []
    for i, nt in enumerate(notes):
        if i in drop:
            if cur:
                segs.append(cur)
            cur = []
        else:
            cur.append(nt)
    if cur:
        segs.append(cur)
    return segs


def grams(phrases: list, k: int = 4) -> set:
    out = set()
    for ph in phrases:
        for seg in strip_motifs(ph):
            iv = [b[2] - a[2] for a, b in zip(seg, seg[1:])]
            for i in range(len(iv) - k + 1):
                out.add(tuple(iv[i:i + k]))
    return out


def main(argv) -> int:
    lim = float(argv[argv.index("--min") + 1]) if "--min" in argv else 0.2
    pat = json.load(open(os.path.join(ROOT, "data", "music_patterns.json"), encoding="utf-8"))["boss"]["songs"]
    songs = {k: v for k, v in pat.items() if not k.startswith("_") and not v.get("test") and v.get("kind") in ("legend", "phantom")}
    replaced = {v["replaces"] for v in songs.values() if v.get("replaces")}
    if "--all" not in argv:
        songs = {k: v for k, v in songs.items() if k not in replaced}
    trial = {}
    for i, a in enumerate(argv):
        if a == "--try":
            nm, sid = argv[i + 1].split(":")
            trial[sid] = nm
    g = {}
    for sid, sp in sorted(songs.items()):
        if sid in trial:
            sp = dict(sp, notes=trial[sid])
        ph = phrases_from_notes(sp["notes"]) if sp.get("notes") else phrases_from_spec(sp)
        g[sid] = grams(ph)
    print(f"곡 {len(g)}개 · 음 간격 4개 묶음 · 공통 동기 제외 · 기준 {lim:.0%}")
    rows = []
    for a, b in combinations(sorted(g), 2):
        if not g[a] or not g[b]:
            continue
        ov = len(g[a] & g[b]) / min(len(g[a]), len(g[b]))
        rows.append((ov, a, b, len(g[a] & g[b]), min(len(g[a]), len(g[b]))))
    rows.sort(reverse=True)
    bad = [r for r in rows if r[0] >= lim]
    for ov, a, b, n, m in bad:
        print(f"  {a:13} ↔ {b:13} {ov:5.0%}  ({n}/{m} 조각)")
    print(f"경고 {len(bad)}쌍 / 전체 {len(rows)}쌍" + ("" if bad else " — 없음"))
    for sid in sorted(g):
        best = max((r for r in rows if sid in (r[1], r[2])), default=None)
        print(f"  {sid:13} 조각 {len(g[sid]):3}개 · 가장 비슷한 곡 {(best[2] if best[1] == sid else best[1]) if best else '-':13} {best[0] if best else 0:5.0%}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
