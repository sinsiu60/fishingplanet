"""전설의 노래 '극광' (BOSS_BGM.md 엘드라시온 L11, DESIGN.md 43-26): 극광어 보레알리스 포획 연출 전용.

기존 전설의 노래와 같은 길이 · 같은 싱크 마커(data/legend_catch_timeline.json) — 포획 연출 VFX(얼음 조각)는 그대로 맞는다.
악기는 전투 곡 L11-NORDIC 과 같은 합성(src/audio/boss_nordic.py). B단조 → 마지막 화음만 B장조.

  hit 0초       전체 강타: 큰북 + 프레임 드럼 + 낮은 지속음 + 남성 합창 '오—' + 하르당에르 화음
  rise 0.3초    프레임 드럼 굴림 (점점 촘촘히, 절정 0.08초 전에 멈춤)
  scales 0.8초  니켈하르파 빠른 상승 + 첼레스타 반짝
  climax 1.4초  읊조리는 남성 합창 크게 + 큰북 + 하르당에르 · 니켈하르파 화음 + 첼레스타 — 가장 크게
  card 1.9초    하르당에르 · 니켈하르파가 함께 주인의 동기 B → F# → E
  record 2.6초  큰북 + 프레임 드럼 + 얼음 갈라지는 소리 인장
  afterglow     F#장조(V) → B장조(D#) 합창 · 하르당에르(공명 줄) · 첼레스타
  짧은 버전은 같은 순서를 짧은 마커로, 대기(loop)는 조용한 공명 줄 울림 + 첼레스타 드문 음.

출력: assets/music_generated/legend_catch_{full,short,loop}_L11-NORDIC.ogg (+ legend_catch_markers.json 에 추가)
      tools/audio/reference/legend_catch/L11-NORDIC_full.wav · L11-NORDIC_short.wav
사용: python tools/audio/make_nordic_legend_song.py
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
from src.audio import boss_nordic as N  # noqa: E402
from src.audio.boss_synth import hz  # noqa: E402

SR = ps.SR
ROOT = ps.ROOT
TL = json.load(open(os.path.join(ROOT, "data", "legend_catch_timeline.json"), encoding="utf-8"))
REF = os.path.join(ROOT, "tools", "audio", "reference", "legend_catch")
SID = "L11-NORDIC"
MINOR = [47, 54, 59, 62, 66]       # B단조 화음
MAJOR = [47, 54, 59, 63, 66, 71]   # B장조 — 마지막 화음 (D#)
NAT = [59, 61, 62, 64, 66, 67, 69, 71]   # B 자연단음계
Q = 60.0 / 144
RNG = np.random.default_rng(144)


def n_of(sec: float) -> int:
    return max(1, int(sec * SR))


def inst(name: str, m: float, dur: float, vowel="o") -> np.ndarray:
    return N.INST[name](hz(m), n_of(dur + 0.1), RNG, dur=dur, q=Q, vowel=vowel)


def drum(kind: str, vel: float = 1.0) -> np.ndarray:
    fn, ln, g, _ = N.KIT[kind]
    return fn(n_of(ln), vel, RNG) * g * vel


def chant(tr, notes, at: float, dur: float, g: float = 1.0, vowel="o") -> None:
    for j, m in enumerate(notes):
        tr.add(inst("chant", m, dur, vowel), at, 0.22 * g, (j - 1) * 0.4)


def strings(tr, notes, at: float, dur: float, g: float = 1.0, kind="hardanger") -> None:
    for j, m in enumerate(notes):
        tr.add(inst(kind, m, dur), at, 0.13 * g, (j / max(1, len(notes) - 1) - 0.5) * 0.7)


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
    # 1) hit: 큰북 + 프레임 드럼 + 낮은 지속음 + 합창 + 하르당에르 화음
    tr.add(drum("big"), hit, 1.0)
    tr.add(drum("frame"), hit, 1.0)
    tr.add(inst("drone", 35, rise + 0.3), hit, 0.5)
    chant(tr, [47, 54], hit, rise + 0.1, 1.1)
    strings(tr, MINOR[2:], hit, rise + 0.1, 1.2)
    # 2) rise: 프레임 드럼 굴림 (점점 촘촘히 · 절정 0.08초 전에 멈춤)
    t = rise
    k = 0
    while t < cl - 0.08:
        u = (t - rise) / (cl - rise)
        tr.add(drum("frame", 0.55 + 0.45 * u), t, 1.0, 0.1 * (-1) ** k)
        t += max(0.05, (0.12 if not short else 0.07) * (1 - 0.5 * u))
        k += 1
    # 3) scales: 니켈하르파 상승 + 첼레스타
    up = NAT + [d + 12 for d in NAT[1:]]
    stepn = up[:: 2 if short else 1]
    span = cl - sc - 0.08
    for j, nn in enumerate(stepn):
        at = sc + span * j / len(stepn)
        tr.add(inst("nyckel", nn - 12, span / len(stepn) * 1.1), at, 0.3, 0.2)
        if j % 3 == 0:
            tr.add(inst("celesta", nn + 12, 0.6), at, 0.18, -0.3)
    # 4) climax: 읊조리는 합창 크게 + 큰북 + 하르당에르 · 니켈하르파 화음 + 첼레스타
    hold = card - cl + 0.2
    chant(tr, [47, 54, 59], cl, hold, 1.5, "a")
    strings(tr, MINOR[1:], cl, hold, 1.3)
    strings(tr, MINOR[2:], cl, hold, 1.0, kind="nyckel")
    tr.add(inst("drone", 35, hold), cl, 0.55)
    tr.add(drum("big"), cl, 1.0)
    tr.add(drum("frame"), cl, 1.0)
    for j, nn in enumerate((83, 86, 90)):
        tr.add(inst("celesta", nn, 0.8), cl + j * 0.07, 0.18, 0.3 * (j - 1))
    # 5) card: 하르당에르 · 니켈하르파가 함께 주인의 동기 B → F# → E
    q = (rec - card) / 2
    t = card
    for nn, d in zip((71, 78, 76), (q, q, 2 * q - 0.06)):
        tr.add(inst("hardanger", nn, d), t, 0.38, -0.2)
        tr.add(inst("nyckel", nn - 12, d), t, 0.3, 0.2)
        tr.add(drum("frame", 0.8), t, 1.0)
        t += d
    chant(tr, [47, 54], card, rec - card, 0.7)
    # 6) record: 큰북 + 프레임 드럼 + 얼음 갈라지는 소리
    tr.add(drum("big"), rec, 1.0)
    tr.add(drum("frame"), rec, 1.0)
    tr.add(N.d_ice(n_of(1.0), RNG), rec, 0.35, 0.15)
    # 7) F#장조(V) → B장조로 끝
    if not short:
        strings(tr, [54, 58, 61, 66], rec + 0.12, aft - rec - 0.2, 0.7)
        chant(tr, [42, 49], rec + 0.12, aft - rec - 0.2, 0.6)
    chant(tr, [47, 54, 59], aft, tail * 0.9, 1.3)
    strings(tr, MAJOR[1:], aft, tail, 1.3)
    tr.add(inst("drone", 35, tail), aft, 0.5)
    for j, nn in enumerate((83, 87, 90, 95)):
        tr.add(inst("celesta", nn, 1.2), aft + j * 0.08, 0.16, 0.3 * (j - 1.5))
    tr.add(drum("big"), aft, 1.0)
    y = ps.reverb(tr.buf, rt60=1.4, wet=0.2)
    n_end = int((aft + tail) * SR)
    y = y[:, :n_end]
    fade = int(0.4 * SR)
    y[:, -fade:] *= np.linspace(1, 0, fade)
    for at in (cl, aft):   # 강타 직전 '숨' (43-20)
        y = ps.breath(y, at)
    return master(y, -2.0, 1.75 if short else 1.45), dict(m)   # 평균 음량을 L11 전설의 노래와 같게


def compose_loop() -> np.ndarray:
    """카드 대기: 조용한 B장조 공명 줄 울림 + 첼레스타 드문 음, 이음매 없이 반복."""
    L = TL["loop_len"]
    tr = ps.Track(L)
    strings(tr, [59, 63, 66, 71], 0.0, L + 2.0, 0.6)
    for i in range(3):
        tr.add(inst("celesta", (83, 87, 90)[i], 1.2), 0.4 + i * L / 3, 0.08, 0.4 * (-1) ** i)
    y = ps.reverb(tr.buf, rt60=1.6, wet=0.3)
    n = int(L * SR)
    out = y[:, :n].copy()
    tl_ = y[:, n:n * 2]
    out[:, : tl_.shape[1]] += tl_
    out = 0.5 * (out + np.roll(out, n // 2, axis=1))
    return master(out, -12.0, 1.15)


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
