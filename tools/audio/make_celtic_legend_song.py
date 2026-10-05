"""전설의 노래 '갈대왕' (BOSS_BGM.md 엘드라시온 L07, DESIGN.md 43-22): 갈대왕 실바 포획 연출 전용.

기존 전설의 노래와 같은 길이 · 같은 싱크 마커(data/legend_catch_timeline.json) — 포획 연출 VFX(갈대 활)는 그대로 맞는다.
악기는 전투 곡 L07-CELTIC 과 같은 합성(src/audio/boss_celtic.py). D 도리안 → 마지막 화음만 D장조.

  hit 0초       전체 강타: 보드란 + 큰북 + 부주키 화음 + 드론이 켜짐 + 휘슬 높은 음
  rise 0.3초    보드란 굴림 (점점 촘촘히, 절정 0.08초 전에 멈춤)
  scales 0.8초  피들 빠른 상승 (도리안)
  climax 1.4초  백파이프(챈터 + 드론) + 남성 합창 '오—' + 큰북 + 부주키 — 가장 크게
  card 1.9초    휘슬 · 피들 · 챈터가 함께 주인의 동기 D → A → G
  record 2.6초  큰북 + 보드란 '둥' 인장
  afterglow     D장조 화음 (드론 + 챈터 + 합창 + 부주키 긁기)
  짧은 버전은 같은 순서를 짧은 마커로, 대기(loop)는 조용한 드론 + 휘슬 숨소리 + 드문 보드란.

출력: assets/music_generated/legend_catch_{full,short,loop}_L07-CELTIC.ogg (+ legend_catch_markers.json 에 추가)
      tools/audio/reference/legend_catch/L07-CELTIC_full.wav · L07-CELTIC_short.wav
사용: python tools/audio/make_celtic_legend_song.py
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
from src.audio import boss_celtic as C  # noqa: E402
from src.audio.boss_synth import hz  # noqa: E402

SR = ps.SR
ROOT = ps.ROOT
TL = json.load(open(os.path.join(ROOT, "data", "legend_catch_timeline.json"), encoding="utf-8"))
REF = os.path.join(ROOT, "tools", "audio", "reference", "legend_catch")
SID = "L07-CELTIC"
D4 = 62
DORIAN = [62, 64, 65, 67, 69, 71, 72, 74]
MINOR = [50, 57, 62, 65, 69]       # D단조 화음
MAJOR = [50, 57, 62, 66, 69, 74]   # D장조 — 마지막 화음 (F♯)
Q = 0.4
RNG = np.random.default_rng(150)


def n_of(sec: float) -> int:
    return max(1, int(sec * SR))


def inst(name: str, m: float, dur: float) -> np.ndarray:
    return C.INST[name](hz(m), n_of(dur + 0.1), RNG, dur=dur, q=Q)


def drum(kind: str, vel: float = 1.0) -> np.ndarray:
    fn, ln, g, _ = C.KIT[kind]
    return fn(n_of(ln), vel, RNG) * g * vel


def drones(tr, at: float, dur: float, g: float = 1.0) -> None:
    for j, m in enumerate((38, 50, 57)):
        tr.add(inst("drone", m, dur), at, (0.3, 0.22, 0.16)[j] * g, (j - 1) * 0.3)


def strum(tr, notes, at: float, g: float = 1.0, up=False) -> None:
    seq = notes[::-1] if up else notes
    for j, m in enumerate(seq):
        tr.add(inst("bouzouki", m, 0.8), at + j * 0.009, 0.16 * g, (j / max(1, len(seq) - 1) - 0.5) * 0.6)


def chant(tr, notes, at: float, dur: float, g: float = 1.0) -> None:
    for j, m in enumerate(notes):
        tr.add(C.INST["chant"](hz(m), n_of(dur + 0.1), RNG), at, 0.2 * g, (j - 1) * 0.4)


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
    # 1) hit: 보드란 + 큰북 + 부주키 화음 + 드론 + 휘슬 높은 음
    tr.add(drum("big"), hit, 1.0)
    tr.add(drum("bod"), hit, 1.0)
    strum(tr, [50, 57, 62, 65], hit, 1.2)
    drones(tr, hit, rise + 0.2, 0.9)
    tr.add(inst("whistle_cut", 86, rise), hit, 0.3, 0.2)
    # 2) rise: 보드란 굴림 (점점 촘촘히 · 절정 0.08초 전에 멈춤)
    t = rise
    k = 0
    while t < cl - 0.08:
        u = (t - rise) / (cl - rise)
        tr.add(drum("bod" if k % 3 == 0 else "bodp", 0.55 + 0.45 * u), t, 1.0, 0.1)
        if k % 3 == 1:
            tr.add(drum("rim", 0.6 + 0.4 * u), t, 1.0, 0.2)
        t += max(0.05, (0.11 if not short else 0.07) * (1 - 0.5 * u))
        k += 1
    # 3) scales: 피들 빠른 상승 (도리안 두 옥타브)
    up = DORIAN + [d + 12 for d in DORIAN[1:]]
    step = up[:: 2 if short else 1]
    span = cl - sc - 0.08
    for j, nn in enumerate(step):
        tr.add(inst("fiddle", nn, span / len(step) * 1.1), sc + span * j / len(step), 0.3 + 0.015 * j, 0.25)
    # 4) climax: 백파이프(챈터 + 드론) + 남성 합창 + 큰북 + 부주키
    hold = card - cl + 0.2
    drones(tr, cl, hold + 0.1, 1.2)
    tr.add(inst("chanter", 74, hold), cl, 0.32, -0.15)
    chant(tr, [50, 57, 62], cl, hold, 1.2)
    tr.add(drum("big"), cl, 1.0)
    tr.add(drum("bod"), cl, 1.0)
    strum(tr, MINOR, cl, 1.3)
    strum(tr, MINOR, cl + Q * 0.75, 0.9, up=True)
    # 5) card: 휘슬 · 피들 · 챈터가 함께 주인의 동기 D → A → G
    q = (rec - card) / 2
    st = card
    for nn, d in zip((74, 81, 79), (q, q, 2 * q - 0.06)):
        tr.add(inst("whistle_cut", nn + 12, d), st, 0.26, 0.25)
        tr.add(inst("fiddle", nn, d), st, 0.34, -0.25)
        tr.add(inst("chanter", nn, d), st, 0.26, 0.0)
        tr.add(drum("bod", 0.8), st, 1.0)
        st += d
    drones(tr, card, rec - card, 0.8)
    # 6) record: 큰북 + 보드란 인장
    tr.add(drum("big"), rec, 1.0)
    tr.add(drum("bod"), rec, 1.0)
    tr.add(drum("rim"), rec, 0.8)
    # 7) D장조로 끝
    if not short:
        strum(tr, [57, 61, 64, 69], rec + 0.12, 0.7)                     # V (A장조) → 숨 → I
        tr.add(inst("fiddle", 73, aft - rec - 0.25), rec + 0.12, 0.2, -0.2)
    drones(tr, aft, tail, 1.1)
    tr.add(inst("chanter", 78, tail * 0.8), aft, 0.26, -0.15)          # F#5 (장3도)
    tr.add(inst("whistle", 86, tail * 0.7), aft + 0.02, 0.2, 0.25)
    chant(tr, [50, 57, 62, 66], aft, tail * 0.9, 1.1)
    strum(tr, MAJOR, aft, 1.3)
    tr.add(drum("big"), aft, 1.0)
    tr.add(drum("bod"), aft, 0.9)
    y = ps.reverb(tr.buf, rt60=1.2, wet=0.18)
    n_end = int((aft + tail) * SR)
    y = y[:, :n_end]
    fade = int(0.4 * SR)
    y[:, -fade:] *= np.linspace(1, 0, fade)
    for at in (cl,):   # 강타 직전 '숨' (43-20)
        y = ps.breath(y, at)
    return master(y, -2.0, 1.0 if short else 1.75), dict(m)   # 평균 음량을 L07 전설의 노래와 같게


def compose_loop() -> np.ndarray:
    """카드 대기: 조용한 드론(D장조 5도) + 휘슬 긴 음 + 드문 보드란, 이음매 없이 반복."""
    L = TL["loop_len"]
    tr = ps.Track(L)
    drones(tr, 0.0, L + 2.0, 0.5)
    tr.add(inst("whistle", 78, L * 0.4), 0.8, 0.06, 0.2)
    tr.add(inst("whistle", 81, L * 0.4), 0.8 + L / 2, 0.06, -0.2)
    for i in range(2):
        tr.add(drum("bod", 0.5), 0.3 + i * L / 2, 0.5)
    y = ps.reverb(tr.buf, rt60=1.2, wet=0.3)
    n = int(L * SR)
    out = y[:, :n].copy()
    tl_ = y[:, n:n * 2]
    out[:, : tl_.shape[1]] += tl_
    out = 0.5 * (out + np.roll(out, n // 2, axis=1))
    return master(out, -12.0, 1.35)


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
