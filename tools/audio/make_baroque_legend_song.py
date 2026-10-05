"""전설의 노래 '천공' (BOSS_BGM.md 엘드라시온 L09, DESIGN.md 43-24): 천공어 에어리스 포획 연출 전용.

기존 전설의 노래와 같은 길이 · 같은 싱크 마커(data/legend_catch_timeline.json) — 포획 연출 VFX(구름 가르기)는 그대로 맞는다.
악기는 전투 곡 L09-BAROQUE 와 같은 합성(src/audio/boss_baroque.py). E단조 → 마지막 화음만 E장조 (바로크의 '피카르디 3도').

  hit 0초       전체 강타: 오르간 전체 화음 + 페달 + 팀파니 + 하프시코드 화음 + 트럼펫
  rise 0.3초    팀파니 굴림 (점점 촘촘히, 절정 0.08초 전에 멈춤)
  scales 0.8초  하프시코드 32분 상승 질주 + 현악 상승
  climax 1.4초  파이프 오르간 전체 + 페달 + 합창 '아—' + 트럼펫 높은 음 + 팀파니 + 크래시 — 가장 크게
  card 1.9초    트럼펫 · 하프시코드 · 오르간이 함께 주인의 동기 E → B → A
  record 2.6초  팀파니 둘 + 오르간 페달 인장
  afterglow     B장조(V) → E장조(G♯) 오르간 · 합창 · 현악 · 트럼펫 + 팀파니
  짧은 버전은 같은 순서를 짧은 마커로, 대기(loop)는 조용한 오르간 E장조 + 드문 하프시코드.

출력: assets/music_generated/legend_catch_{full,short,loop}_L09-BAROQUE.ogg (+ legend_catch_markers.json 에 추가)
      tools/audio/reference/legend_catch/L09-BAROQUE_full.wav · L09-BAROQUE_short.wav
사용: python tools/audio/make_baroque_legend_song.py
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
from src.audio import boss_baroque as B  # noqa: E402
from src.audio import boss_synth as bs  # noqa: E402
from src.audio.boss_synth import hz  # noqa: E402

SR = ps.SR
ROOT = ps.ROOT
TL = json.load(open(os.path.join(ROOT, "data", "legend_catch_timeline.json"), encoding="utf-8"))
REF = os.path.join(ROOT, "tools", "audio", "reference", "legend_catch")
SID = "L09-BAROQUE"
E4 = 64
MINOR = [52, 59, 64, 67, 71]       # E단조 화음
MAJOR = [52, 59, 64, 68, 71, 76]   # E장조 — 마지막 화음 (G♯)
HARM = [64, 66, 67, 69, 71, 72, 75, 76]   # E 화성단음계
Q = 60.0 / 172
RNG = np.random.default_rng(172)


def n_of(sec: float) -> int:
    return max(1, int(sec * SR))


def inst(name: str, m: float, dur: float) -> np.ndarray:
    return B.INST[name](hz(m), n_of(dur + 0.1), RNG, dur, Q)


def timp(vel: float = 1.0, fifth=False) -> np.ndarray:
    return bs.d_timp(n_of(1.4), vel, RNG, f=hz(40) * (1.5 if fifth else 1.0)) * 0.75 * vel


def organ(tr, notes, at: float, dur: float, g: float = 1.0) -> None:
    for j, m in enumerate(notes):
        tr.add(inst("organ_full", m, dur), at, 0.13 * g, (j / max(1, len(notes) - 1) - 0.5) * 0.8)
    tr.add(inst("pedal", notes[0] - 12, dur), at, 0.4 * g)


def harp(tr, notes, at: float, g: float = 1.0) -> None:
    for j, m in enumerate(notes):
        tr.add(inst("harpsichord", m, 0.8), at + j * 0.012, 0.16 * g, (j / max(1, len(notes) - 1) - 0.5) * 0.6)


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
    # 1) hit: 오르간 전체 화음 + 페달 + 팀파니 + 하프시코드 화음 + 트럼펫
    organ(tr, MINOR, hit, rise + 0.15, 1.1)
    tr.add(timp(), hit, 1.0)
    harp(tr, MINOR, hit, 1.2)
    tr.add(inst("trumpet", 76, rise + 0.1), hit, 0.18, 0.2)
    # 2) rise: 팀파니 굴림 (점점 촘촘히 · 절정 0.08초 전에 멈춤)
    t = rise
    k = 0
    while t < cl - 0.08:
        u = (t - rise) / (cl - rise)
        tr.add(timp(0.5 + 0.5 * u, fifth=k % 4 == 2), t, 1.0, 0.1 * (-1) ** k)
        t += max(0.045, (0.1 if not short else 0.06) * (1 - 0.5 * u))
        k += 1
    # 3) scales: 하프시코드 32분 상승 질주 + 현악 상승 (E 화성단음계 두 옥타브)
    up = HARM + [d + 12 for d in HARM[1:]]
    stepn = up[:: 2 if short else 1]
    span = cl - sc - 0.08
    for j, nn in enumerate(stepn):
        at = sc + span * j / len(stepn)
        tr.add(inst("harpsichord", nn, 0.3), at, 0.3, 0.25 * (-1) ** j)
        tr.add(inst("strings", nn - 12, span / len(stepn) * 1.3), at, 0.2, -0.2)
    # 4) climax: 오르간 전체 + 페달 + 합창 + 트럼펫 + 팀파니 + 크래시
    hold = card - cl + 0.2
    organ(tr, MINOR + [76], cl, hold, 1.3)
    for j, nn in enumerate((64, 71, 76)):
        tr.add(inst("choir_a", nn, hold), cl, 0.24, (j - 1) * 0.5)
    tr.add(inst("trumpet", 83, hold), cl, 0.16, 0.2)
    harp(tr, MINOR + [76], cl, 1.2)
    tr.add(timp(), cl, 1.0)
    tr.add(bs.d_crash(n_of(2.2), 1.0, RNG) * 0.26, cl, 1.0, 0.25)
    # 5) card: 트럼펫 · 하프시코드 · 오르간이 함께 주인의 동기 E → B → A
    q = (rec - card) / 2
    t = card
    for nn, d in zip((76, 83, 81), (q, q, 2 * q - 0.06)):
        tr.add(inst("trumpet", nn, d), t, 0.2, 0.2)
        tr.add(inst("harpsichord", nn, d + 0.3), t, 0.3, -0.25)
        tr.add(inst("organ", nn - 12, d), t, 0.16, 0.0)
        tr.add(timp(0.7), t, 1.0)
        t += d
    # 6) record: 팀파니 둘 + 오르간 페달 인장
    tr.add(timp(), rec, 1.0)
    tr.add(timp(0.8, fifth=True), rec + 0.06, 1.0)
    tr.add(inst("pedal", 40, 0.6), rec, 0.45)
    # 7) B장조(V) → E장조로 끝
    if not short:
        organ(tr, [47, 59, 63, 66, 71], rec + 0.12, aft - rec - 0.2, 0.7)
    organ(tr, MAJOR, aft, tail, 1.3)
    for j, nn in enumerate((64, 68, 71, 76)):
        tr.add(inst("choir_a", nn, tail * 0.9), aft, 0.22, (j - 1.5) * 0.4)
        tr.add(inst("strings", nn, tail * 0.9), aft, 0.12, -(j - 1.5) * 0.4)
    tr.add(inst("trumpet", 80, tail * 0.7), aft + 0.02, 0.15, 0.2)
    harp(tr, MAJOR, aft, 1.0)
    tr.add(timp(), aft, 1.0)
    y = ps.reverb(tr.buf, rt60=1.3, wet=0.2)
    n_end = int((aft + tail) * SR)
    y = y[:, :n_end]
    fade = int(0.4 * SR)
    y[:, -fade:] *= np.linspace(1, 0, fade)
    for at in (cl, aft):   # 강타 직전 '숨' (43-20)
        y = ps.breath(y, at)
    return master(y, -2.0, 0.95 if short else 0.75), dict(m)   # 평균 음량을 L09 전설의 노래와 같게


def compose_loop() -> np.ndarray:
    """카드 대기: 조용한 오르간 E장조 + 드문 하프시코드, 이음매 없이 반복."""
    L = TL["loop_len"]
    tr = ps.Track(L)
    for j, m in enumerate((52, 64, 68, 71)):
        tr.add(inst("organ", m, L + 2.0), 0.0, 0.1, (j - 1.5) * 0.4)
    for i in range(3):
        tr.add(inst("harpsichord", (76, 80, 83)[i], 0.8), 0.4 + i * L / 3, 0.08, 0.4 * (-1) ** i)
    y = ps.reverb(tr.buf, rt60=1.4, wet=0.3)
    n = int(L * SR)
    out = y[:, :n].copy()
    tl_ = y[:, n:n * 2]
    out[:, : tl_.shape[1]] += tl_
    out = 0.5 * (out + np.roll(out, n // 2, axis=1))
    return master(out, -12.0, 0.35)


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
