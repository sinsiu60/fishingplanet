"""적응형 음악 층 합성 (DESIGN.md 32-12, Phase S6): data/music_patterns.json → 합성 레시피 (src/audio/synth.py).

층 (대륙 C = sharmion / eldrasion, 낚시터 S):
  mus_theme_C      메뉴·지도 대륙 테마 (패드 + 멜로디 + 가벼운 타악)
  mus_pad_S        대기 패드 — 낚시터마다 음색·연주법 (대륙 화성)
  mus_shimmer_C    높은 종 반짝임 — 낮에만 크게 (밤에는 고음을 줄인 효과)
  mus_tension_C    진짜 입질: 낮은 현 8분 펄스 + 높은 떨림
  mus_perc_lo_C    파이팅 기본 타악 / mus_perc_hi_C 장력만큼 더해지는 타악 (스네어·하이햇·마지막 마디 탐)
  mus_rise_C       물고기 지침: 상승 멜로디
  mus_boss1~3_C    전설 파이팅: 페이즈마다 한 층씩 (오스티나토 + 북 / 금관 화음 / 빠른 현 + 스네어)
  mus_sting_win    포획 승리 스팅 (반복 없음)
  mus_ending       엔딩 (공기 패드 + 하프 + 유리 멜로디)
모든 반복 층은 같은 길이(bars마디)로 잘라 넘친 울림을 앞에 더한다 (synth "wrap").
"""
import random
import zlib

from src.core.config import load_json

C = None


def cfg() -> dict:
    global C
    if C is None:
        C = load_json("music_patterns.json")
    return C


def hz(m: float) -> float:
    return 440.0 * 2 ** ((m - 69) / 12)


def timing() -> tuple[float, float, float]:
    """(박 길이, 마디 길이, 전체 길이) 초."""
    c = cfg()
    beat = 60.0 / c["bpm"]
    bar = beat * c["beats"]
    return beat, bar, bar * c["bars"]


def _note(inst: str, m: float, start: float, dur: float, gain: float = 1.0, pan: float = 0.0) -> dict:
    t = dict(cfg()["instruments"][inst])
    rel = t.pop("rel", 0.2)
    ly = {k: v for k, v in t.items() if not k.startswith("_")}
    ly.update(freq=hz(m), start=max(0.0, start), len=dur + rel, gain=t.get("gain", 0.3) * gain, pan=pan)
    return ly


def _drum(kind: str, start: float, gain: float, kit: str) -> list[dict]:
    """타악 한 번 (레이어 1~2개). kit: wood(샤르미온) / frame(엘드라시온 — 스네어 대신 프레임 드럼)."""
    E = lambda a, d, s, r: {"a": a, "d": d, "s": s, "r": r}  # noqa: E731
    if kind == "kick":
        return [{"wave": "sine", "freq": [150, 45], "start": start, "len": 0.3, "env": E(0.002, 0.12, 0, 0.08), "dist": 0.2, "gain": 0.75 * gain},
                {"wave": "triangle", "freq": [240, 110], "start": start, "len": 0.08, "env": E(0.001, 0.03, 0, 0.03), "gain": 0.2 * gain}]
    if kind == "snare":
        if kit == "frame":
            return [{"wave": "sine", "freq": [260, 150], "start": start, "len": 0.22, "env": E(0.002, 0.08, 0, 0.08), "gain": 0.45 * gain},
                    {"wave": "noise", "start": start, "len": 0.12, "filter": {"type": "bp", "f": 1200, "q": 1.2}, "env": E(0.001, 0.04, 0, 0.04), "gain": 0.25 * gain}]
        return [{"wave": "noise", "start": start, "len": 0.18, "filter": {"type": "bp", "f": 2400, "q": 0.8}, "env": E(0.001, 0.06, 0, 0.06), "gain": 0.4 * gain},
                {"wave": "triangle", "freq": [210, 160], "start": start, "len": 0.1, "env": E(0.001, 0.04, 0, 0.03), "gain": 0.3 * gain}]
    if kind == "hat":
        return [{"wave": "noise", "start": start, "len": 0.05, "filter": {"type": "hp", "f": 7000}, "env": E(0.001, 0.015, 0, 0.02), "gain": 0.16 * gain}]
    if kind == "shaker":
        return [{"wave": "noise", "start": start, "len": 0.07, "filter": {"type": "bp", "f": 5000, "q": 1.5}, "env": E(0.015, 0.02, 0, 0.03), "gain": 0.1 * gain}]
    if kind in ("tom", "tom_last"):
        return [{"wave": "sine", "freq": [180, 85], "start": start, "len": 0.3, "env": E(0.002, 0.12, 0, 0.1), "dist": 0.15, "gain": 0.5 * gain}]
    if kind == "crash_first":
        return [{"wave": "noise", "start": start, "len": 1.6, "filter": {"type": "hp", "f": 4000}, "env": E(0.002, 0.6, 0, 0.8), "gain": 0.2 * gain}]
    return []


def _drums(pattern: dict, kit: str) -> list[dict]:
    beat, bar, total = timing()
    step = bar / 16
    out = []
    bars = cfg()["bars"]
    for kind, pat in pattern.items():
        for b in range(bars):
            if kind.endswith("_last") and b != bars - 1:
                continue
            if kind.endswith("_first") and b != 0:
                continue
            for i, ch in enumerate(pat):
                if ch in "xX":
                    out += _drum(kind, b * bar + i * step, 1.0 if ch == "X" else 0.7, kit)
    return out


def _chord_style(cont: dict, inst: str, style: str, oct_: int, seed: int) -> list[dict]:
    beat, bar, total = timing()
    rnd = random.Random(seed)
    out = []
    for b, chord in enumerate(cont["chords"]):
        notes = [m + 12 * oct_ for m in chord]
        t0 = b * bar
        if style == "hold":
            for i, m in enumerate(notes):
                out.append(_note(inst, m, t0, bar * 0.98, 1.0, pan=(i / max(1, len(notes) - 1) - 0.5) * 0.6))
        elif style == "arp":
            seq = notes + notes[-2:0:-1]
            for k in range(8):
                m = seq[k % len(seq)]
                out.append(_note(inst, m, t0 + k * beat / 2, beat / 2, 0.8 + 0.2 * (k % 4 == 0),
                                 pan=((k % 4) / 3 - 0.5) * 0.5))
        elif style == "strum":
            for half in range(2):
                for i, m in enumerate(notes):
                    out.append(_note(inst, m, t0 + half * bar / 2 + i * 0.025, bar / 2 * 0.95, 0.85 if half else 1.0,
                                     pan=(i / max(1, len(notes) - 1) - 0.5) * 0.6))
        elif style == "sparse":
            for k in range(4):
                if rnd.random() < 0.8:
                    m = rnd.choice(notes[1:])
                    out.append(_note(inst, m, t0 + k * beat + rnd.uniform(0, 0.12), beat, 0.9, pan=rnd.uniform(-0.5, 0.5)))
    return out


def _bass(cont: dict, inst: str = "bass", rhythm=((0, 2), (2, 1.5), (3.5, 0.5)), gain: float = 1.0) -> list[dict]:
    beat, bar, total = timing()
    out = []
    for b, m in enumerate(cont["bass"]):
        for at, ln in rhythm:
            out.append(_note(inst, m, b * bar + at * beat, ln * beat * 0.95, gain))
    return out


def _melody(notes: list, inst: str, gain: float = 1.0) -> list[dict]:
    beat, bar, total = timing()
    return [_note(inst, m, b * bar + at * beat, ln * beat, gain) for b, at, m, ln in notes]


def render(recipe: dict, seed: int = 1):
    """synth.render + 층마다 같은 크기로 (rms_db: 평균 음량 목표, 최대 −1dBFS를 넘지 않게)."""
    import numpy as np
    from src.audio import synth
    out = synth.render(recipe, seed)
    if "rms_db" in recipe:
        rms = float(np.sqrt(np.mean(out.astype(np.float64) ** 2))) or 1.0
        out = out * (10 ** (recipe["rms_db"] / 20) / rms)
        peak = float(np.abs(out).max())
        if peak > 0.89:
            out = out * (0.89 / peak)
    return out.astype(np.float32)


def _loop(layers: list[dict], rms_db: float, reverb=None, echo=None) -> dict:
    beat, bar, total = timing()
    r = {"len": total, "wrap": total, "rms_db": rms_db, "layers": layers}
    if reverb:
        r["reverb"] = reverb
    if echo:
        r["echo"] = echo
    return r


def recipes() -> dict:
    """이름 → 합성 레시피 (모든 음악 층)."""
    c = cfg()
    beat, bar, total = timing()
    out = {}
    for cid, cont in c["continents"].items():
        kit = cont["kit"]
        # 메뉴·지도 테마: 패드 + 멜로디 + 가벼운 타악 + 베이스
        th = (_chord_style(cont, cont["theme_inst"], "arp", 0, 1) + _melody(cont["theme"], "lead" if cid == "sharmion" else "glass", 0.9)
              + _bass(cont, gain=0.7) + _drums({"kick": "x.......x.......", "shaker": "..x...x...x...x."}, kit))
        out[f"mus_theme_{cid}"] = _loop(th, -19.0, reverb={"mix": 0.18, "time": 1.2})
        # 반짝임: 두 옥타브 위 화음음을 2박마다
        rnd = random.Random(7)
        sh = []
        for b, chord in enumerate(cont["chords"]):
            for k in range(2):
                m = rnd.choice(chord[2:]) + 24
                sh.append(_note("bell", m, b * bar + k * bar / 2 + beat * rnd.choice((0, 0.5, 1)), beat, 0.7, pan=rnd.uniform(-0.6, 0.6)))
        out[f"mus_shimmer_{cid}"] = _loop(sh, -27.0, echo={"delay": beat * 0.75, "fb": 0.35, "mix": 0.3})
        # 긴장: 낮은 현 8분 펄스 (베이스 한 옥타브 위) + 높은 2도 떨림
        tn = []
        for b, m in enumerate(cont["bass"]):
            for k in range(8):
                tn.append(_note("strings", m + 12, b * bar + k * beat / 2, beat / 2 * 0.7, 1.0 if k % 2 == 0 else 0.7))
            top = cont["chords"][b][-1] + 12
            for mm in (top, top + 1):
                ly = _note("strings", mm, b * bar, bar * 0.98, 0.25)
                ly["trem"] = [11, 0.8]
                ly["env"] = {"a": 0.4, "d": 0.5, "s": 0.8, "r": 0.3}
                tn.append(ly)
        out[f"mus_tension_{cid}"] = _loop(tn, -21.0, reverb={"mix": 0.12, "time": 0.8})
        out[f"mus_perc_lo_{cid}"] = _loop(_drums(c["drums"]["perc_lo"], kit) + _bass(cont, gain=0.8), -21.0)
        out[f"mus_perc_hi_{cid}"] = _loop(_drums(c["drums"]["perc_hi"], kit), -26.0)
        out[f"mus_rise_{cid}"] = _loop(_melody(cont["rise"], "lead", 1.0) + _melody(cont["rise"], "bell", 0.35),
                                       -20.0, reverb={"mix": 0.2, "time": 1.0})
        # 전설 보스 층
        b1 = _bass(cont, "bass_drive", rhythm=tuple((k * 0.25, 0.22) for k in range(16)), gain=1.0) + _drums(c["drums"]["boss1"], kit)
        out[f"mus_boss1_{cid}"] = _loop(b1, -19.0)
        b2 = []
        for b, chord in enumerate(cont["chords"]):
            for i, m in enumerate(chord[:4]):
                b2.append(_note("brass", m, b * bar, beat * 1.5, 1.0, pan=(i / 3 - 0.5) * 0.6))
                b2.append(_note("brass", m, b * bar + beat * 2.5, beat * 1.5, 0.8, pan=(i / 3 - 0.5) * 0.6))
        out[f"mus_boss2_{cid}"] = _loop(b2, -22.0, reverb={"mix": 0.2, "time": 1.0})
        b3 = []
        for b, chord in enumerate(cont["chords"]):
            seq = [m + 12 for m in chord]
            for k in range(16):
                b3.append(_note("strings", seq[k % len(seq)], b * bar + k * beat / 4, beat / 4 * 0.8, 0.6, pan=((k % 4) / 3 - 0.5) * 0.7))
        out[f"mus_boss3_{cid}"] = _loop(b3 + _drums(c["drums"]["boss3"], kit), -23.0)
    for sid, p in c["pads"].items():
        if sid.startswith("_"):
            continue
        cid = spot_continent(sid)
        out[f"mus_pad_{sid}"] = _loop(_chord_style(c["continents"][cid], p["inst"], p["style"], p["oct"], zlib.crc32(sid.encode()) & 0xFFFF),
                                      -19.0, reverb={"mix": 0.22, "time": 1.4})
    # 엔딩: 샤르미온 화성 위에 공기 패드 + 하프 아르페지오 + 유리 멜로디 (넓은 잔향)
    sh = c["continents"]["sharmion"]
    en = (_chord_style(sh, "airy", "hold", 0, 3) + _chord_style(sh, "harp", "arp", 0, 4)
          + _melody(sh["theme"], "glass", 0.8) + _bass(sh, rhythm=((0, 4),), gain=0.6))
    out["mus_ending"] = _loop(en, -19.0, reverb={"mix": 0.3, "time": 1.8})
    sw = c["sting_win"]
    st = [_note("glass", m, t, d, 1.0) for t, m, d in sw["notes"]] + [_note("bass", m, t, d, 1.0) for t, m, d in sw["bass"]]
    st += _drum("kick", 0.6, 1.0, "wood") + _drum("crash_first", 0.6, 1.0, "wood")
    out["mus_sting_win"] = {"len": sw["len"], "peak_db": -2.0, "reverb": {"mix": 0.25, "time": 1.2}, "layers": st}
    return out


def spot_continent(spot_id: str) -> str:
    for sp in load_json("spots.json")["spots"]:
        if sp["id"] == spot_id:
            return sp.get("continent", "sharmion")
    return "sharmion"
