"""전설의 노래 '등용' (SHARMION_THEMES.md 6장, DESIGN.md 43-19): 용문잉어 '등용' 포획 연출 전용.

기존 전설의 노래와 같은 길이 · 같은 싱크 마커(data/legend_catch_timeline.json) — 포획 연출 VFX(물보라 용의 승천)는 그대로 맞는다.
악기는 전투 곡 L06-EPIC 과 같은 합성(src/audio/boss_epic.py — 다섯 테마 악기 + 오케스트라 + 합창). D 화성단음계 → D장조로 풀리며 끝.
첫 포획(엔딩)은 'final' 버전 = 이 full 곡 그대로 (src/audio/legend_song.py) → 기존 엔딩으로 이어짐.

  hit 0초       전체 강타 + 용의 포효
  rise 0.3초    큰북·팀파니 몰아치기 (절정 0.08초 전에 멈춤 — 절정 강타가 또렷하게)
  scales 0.8초  현악·합창 상승
  climax 1.4초  다섯 테마 악기 + 오케스트라 + 합창 최대
  card 1.9초    태평소·트럼펫·일렉 기타가 함께 주인의 동기 D → A → G
  record 2.6초  징 + 인장 (큰북)
  afterglow     D장조로 풀리며 끝 (금관·현악·합창·오르간 + 팀파니)
  짧은 버전은 같은 순서를 짧은 마커로, 대기(loop)는 조용한 D장조 현악·합창 + 드문 팀파니.

출력: assets/music_generated/legend_catch_{full,short,loop}_L06-EPIC.ogg (+ legend_catch_markers.json 에 추가)
      tools/audio/reference/legend_catch/L06-EPIC_full.wav · L06-EPIC_short.wav
사용: python tools/audio/make_epic_legend_song.py
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

import numpy as np
from scipy.io import wavfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(os.path.dirname(HERE)))
import make_phantom_song as ps  # noqa: E402  (Track · 잔향 · 통계 재사용)
from src.audio import boss_epic as E  # noqa: E402
from src.audio import boss_synth as bs  # noqa: E402
from src.audio.boss_synth import hz  # noqa: E402

SR = ps.SR
ROOT = ps.ROOT
TL = json.load(open(os.path.join(ROOT, "data", "legend_catch_timeline.json"), encoding="utf-8"))
REF = os.path.join(ROOT, "tools", "audio", "reference", "legend_catch")
SID = "L06-EPIC"
D4 = 62
MINOR = [50, 57, 62, 65, 69]       # D단조 (D A D F A)
MAJOR = [50, 57, 62, 66, 69, 74]   # D장조 — 마지막 화음 (F♯)
Q = 60.0 / 160
RNG = np.random.default_rng(160)


def n_of(sec: float) -> int:
    return max(1, int(sec * SR))


def inst(name: str, m: float, dur: float) -> np.ndarray:
    return E.INST[name](hz(m), n_of(dur + 0.1), RNG, dur, Q)


def drum(kind: str, vel: float = 1.0) -> np.ndarray:
    fn, ln, g, _ = E.KIT[kind]
    if kind == "timp":
        return bs.d_timp(n_of(ln), vel, RNG, f=hz(38)) * g
    return fn(n_of(ln), vel, RNG) * g


def chord(tr, notes, at: float, dur: float, g: float = 1.0, full=True) -> None:
    """오케스트라 + 합창 (+ full = 오르간 전체 음전 · 페달 · 일렉 기타 파워 코드 · 포효 금관)."""
    for j, m in enumerate(notes):
        pan = (j / max(1, len(notes) - 1) - 0.5) * 0.9
        tr.add(inst("brass", m, dur), at, 0.22 * g, pan)
        tr.add(inst("strings", m + 12, dur), at, 0.16 * g, -pan)
        tr.add(inst("choir_a", m + 12 if m < 60 else m, dur), at, 0.2 * g, pan)
        if full:
            tr.add(inst("organ_full", m, dur), at, 0.1 * g, -pan)
    if full:
        tr.add(inst("pedal", notes[0] - 12, dur), at, 0.4 * g)
        tr.add(inst("roar", notes[0] - 12, dur), at, 0.35 * g)
        tr.add(inst("gtr_power", notes[0] - 12, dur), at, 0.28 * g, -0.3)


def roar(dur: float = 1.1) -> np.ndarray:
    """용의 포효: 낮은 금관이 아래로 미끄러지며 + 거친 숨 (목 울림 30Hz 떨림)."""
    n = n_of(dur)
    t = np.arange(n) / SR
    f_t = hz(38) * 2 ** (-3 * (t / dur) ** 1.2 / 12)
    from src.audio.boss_muhyeop import _harm, _norm
    x = _harm(f_t, [1 / k ** 0.7 for k in range(1, 40)], top=4000)
    nz = bs._bw_filter(bs.noise(n, RNG), "bp", (120, 900)) * (0.6 + 0.4 * np.sin(2 * np.pi * 30 * t))
    y = np.tanh(2.2 * _norm(x + 1.2 * _norm(nz)))
    return y * np.minimum(1, t / 0.02) * np.clip(1 - t / dur, 0, 1) ** 0.8


def master(buf: np.ndarray, peak_db: float, drive: float) -> np.ndarray:
    """make_phantom_song.master 와 같음 (중음 보강 + 부드러운 리미터), drive 만 조절."""
    from scipy import signal
    mid = signal.sosfilt(signal.butter(2, [1500, 3200], "bandpass", fs=SR, output="sos"), buf, axis=1)
    y = buf + 0.42 * mid
    y = np.tanh(y / (np.max(np.abs(y)) + 1e-9) * drive)
    return y / (np.max(np.abs(y)) + 1e-9) * 10 ** (peak_db / 20)


def compose(variant: str) -> tuple[np.ndarray, dict]:
    if variant == "loop":
        return compose_loop(), {}
    m = TL["variants"][variant]["markers"]
    short = variant == "short"
    hit, rise, sc, cl, card, rec, aft = (m[k] for k in ("hit", "rise", "scales", "climax", "card", "record", "afterglow"))
    tail = 2.0 if not short else 1.1
    tr = ps.Track(aft + tail)
    # 1) hit: 전체 강타 + 용의 포효
    chord(tr, MINOR, hit, rise + 0.15)
    tr.add(roar(1.1 if not short else 0.6), hit + 0.02, 0.55)
    for k in ("obig", "big", "crash", "timp"):
        tr.add(drum(k), hit, 1.0)
    # 2) rise: 큰북·팀파니 몰아치기 (점점 촘촘히 · 절정 0.08초 전에 멈춤)
    t = rise
    k = 0
    while t < cl - 0.08:
        tr.add(drum("timp", 0.55 + 0.45 * (t - rise) / (cl - rise)), t, 0.9, -0.2)
        if k % 2 == 0:
            tr.add(drum("obig", 0.7 + 0.3 * (t - rise) / (cl - rise)), t, 0.8, 0.2)
        if k % 4 == 0:
            tr.add(drum("big"), t, 0.7)
        t += max(0.045, (0.12 if not short else 0.07) * (1 - 0.6 * (t - rise) / (cl - rise)))
        k += 1
    # 3) scales: 현악·합창 상승 (D 화성단음계)
    up = [62, 64, 65, 67, 69, 70, 73, 74]
    span = cl - sc - 0.08
    step = up[:: 2 if short else 1]
    for j, nn in enumerate(step):
        at = sc + span * j / len(step)
        tr.add(inst("strings", nn + 12, span / len(step) * 1.3), at, 0.32 + 0.02 * j, 0.3)
        tr.add(inst("spiccato", nn, span / len(step)), at, 0.3, -0.3)
        tr.add(inst("choir", nn, span / len(step) * 1.4), at, 0.28 + 0.02 * j, -0.2)
    # 4) climax: 다섯 테마 악기 + 오케스트라 + 합창 최대
    hold = card - cl + 0.2
    chord(tr, MINOR + [74], cl, hold, 1.15)
    tr.add(inst("taepyeongso", 74, hold), cl, 0.22, 0.25)
    tr.add(inst("trumpet_open", 81, hold), cl, 0.18, -0.25)
    tr.add(inst("throat", 38, hold), cl, 0.3)
    for k in ("obig", "big", "crash", "cymbal", "timp", "jing"):
        tr.add(drum(k), cl, 1.0)
    # 5) card: 태평소·트럼펫·일렉 기타가 함께 주인의 동기 D → A → G
    q = (rec - card) / 2
    st = card
    for nn, d in zip((74, 81, 79), (q, q, 2 * q - 0.06)):
        tr.add(inst("taepyeongso", nn, d), st, 0.42, 0.25)
        tr.add(inst("trumpet_open", nn, d), st, 0.36, -0.25)
        tr.add(inst("gtr_lead", nn - 12, d), st, 0.34, 0.0)
        tr.add(drum("obig", 0.8), st, 0.6)
        st += d
    tr.add(inst("strings", 62, rec - card), card, 0.18, 0.4)
    tr.add(inst("pedal", 38, rec - card), card, 0.3)
    # 6) record: 징 + 인장 (큰북)
    tr.add(drum("jing"), rec, 1.1)
    tr.add(drum("obig"), rec, 1.0)
    tr.add(drum("big"), rec, 0.9)
    tr.add(drum("timp"), rec, 0.8)
    # 7) D장조로 풀리며 끝
    if not short:
        chord(tr, [57, 61, 64, 69], rec + 0.15, aft - rec - 0.2, 0.55, full=False)   # V (A장조) → 숨 → I (D장조)
    chord(tr, MAJOR, aft, tail, 1.0)
    tr.add(inst("trumpet_open", 78, tail * 0.8), aft + 0.02, 0.2, -0.2)
    for k in ("obig", "timp", "crash"):
        tr.add(drum(k), aft, 1.0)
    y = ps.reverb(tr.buf, rt60=1.8, wet=0.22)
    n_end = int((aft + tail) * SR)
    y = y[:, :n_end]
    fade = int(0.4 * SR)
    y[:, -fade:] *= np.linspace(1, 0, fade)
    return master(y, -2.0, 1.25 if short else 1.1), dict(m)   # 평균 음량을 L06 전설의 노래와 같게


def compose_loop() -> np.ndarray:
    """카드 대기: 조용한 D장조 현악·합창 + 드문 팀파니, 이음매 없이 반복."""
    L = TL["loop_len"]
    tr = ps.Track(L)
    for j, nn in enumerate((50, 57, 62, 66, 69)):
        tr.add(inst("strings", nn, L + 2.0), 0.0, 0.18, (j - 2) * 0.3)
        tr.add(inst("choir", nn + 12, L + 2.0), 0.0, 0.1, -(j - 2) * 0.3)
    for i in range(2):
        tr.add(drum("timp", 0.5), 0.4 + i * L / 2, 0.25)
    y = ps.reverb(tr.buf, rt60=1.8, wet=0.3)
    n = int(L * SR)
    out = y[:, :n].copy()
    tl_ = y[:, n:n * 2]
    out[:, : tl_.shape[1]] += tl_
    out = 0.5 * (out + np.roll(out, n // 2, axis=1))
    return master(out, -12.0, 1.0)


def save(y: np.ndarray, variant: str) -> None:
    name = f"legend_catch_{variant}_{SID}"
    pcm = (np.clip(y.T, -1, 1) * 32767).astype(np.int16)
    os.makedirs(REF, exist_ok=True)
    keep = variant in ("full", "short")
    wav = os.path.join(REF, f"{SID}_{variant}.wav") if keep else os.path.join(tempfile.mkdtemp(), name + ".wav")
    wavfile.write(wav, SR, pcm)
    ff = shutil.which("ffmpeg")
    if ff:
        subprocess.run([ff, "-loglevel", "error", "-y", "-i", wav, "-c:a", "libvorbis", "-q:a", "5",
                        os.path.join(ps.OUT, name + ".ogg")], check=True)
    else:
        shutil.copy(wav, os.path.join(ps.OUT, name + ".wav"))


if __name__ == "__main__":
    mpath = os.path.join(ps.OUT, "legend_catch_markers.json")
    markers = json.load(open(mpath, encoding="utf-8"))
    for variant in ("full", "short", "loop"):
        y, mk = compose(variant)
        save(y, variant)
        ln, pk, rms = ps.stats(y)
        name = f"legend_catch_{variant}_{SID}"
        markers["files"][name] = {"len": round(ln, 3), "peak_db": round(pk, 1), "rms_db": round(rms, 1), "markers": mk}
        print(f"{name:<38} {ln:5.2f}s  최대 {pk:6.1f}dBFS  평균 {rms:6.1f}dBFS", flush=True)
    with open(mpath, "w", encoding="utf-8") as fp:
        json.dump(markers, fp, ensure_ascii=False, indent=1)
