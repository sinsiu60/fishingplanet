"""전설의 노래 재즈 버전 (SHARMION_THEMES.md 1장, DESIGN.md 43-16): 황금잉어 '여우비' 포획 연출 전용.

기존 전설의 노래와 같은 길이 · 같은 싱크 마커(data/legend_catch_timeline.json) — 포획 연출 VFX(금빛 소나기)는 그대로 맞는다.
악기는 전투 곡 L01-JAZZ 와 같은 합성(src/audio/boss_jazz.py). D단조 → 마무리 D장조 '빰—빠밤'.

  hit 0초       빅밴드 강타 + 심벌 (전투 곡과 같은 D)
  rise 0.3초    드럼 필인 상승 (스네어 셋잇단 점점 세게 + 탐)
  scales 0.8초  색소폰 빠른 상승 선율
  climax 1.4초  금관 전체 화려한 긴 화음 + 크래시
  card 1.9초    트럼펫이 약음기를 빼고 주인의 동기 D → A → G 를 크게
  record 2.6초  금화 '짤랑' + 인장 (킥·스네어)
  afterglow     피아노 짧은 마무리 → D장조 '빰—빠밤' (마지막 '밤' = afterglow)
  짧은 버전은 같은 순서를 짧은 마커로, 대기(loop)는 피아노 D장조 화음 + 브러시 + 빗소리.

출력: assets/music_generated/legend_catch_{full,short,loop}_L01-JAZZ.ogg (+ legend_catch_markers.json 에 추가)
      tools/audio/reference/legend_catch/L01-JAZZ_full.wav · L01-JAZZ_short.wav
사용: python tools/audio/make_jazz_legend_song.py
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
from src.audio import boss_jazz as J  # noqa: E402
from src.audio.boss_rock import d_ride  # noqa: E402
from src.audio.boss_synth import d_crash, d_kick, d_snare2, d_tom, hz  # noqa: E402

SR = ps.SR
ROOT = ps.ROOT
TL = json.load(open(os.path.join(ROOT, "data", "legend_catch_timeline.json"), encoding="utf-8"))
REF = os.path.join(ROOT, "tools", "audio", "reference", "legend_catch")
SID = "L01-JAZZ"
D4 = 62
DM9 = [50, 57, 60, 64, 65, 69]          # D단조 9화음 (D A C E F A)
DMAJ = [50, 57, 62, 66, 69, 71, 76]     # D장조 6/9 (D A D F# A B E)
RNG = np.random.default_rng(176)


def n_of(sec: float) -> int:
    return max(1, int(sec * SR))


def inst(name: str, m: float, dur: float) -> np.ndarray:
    return J.INST[name](hz(m), n_of(dur + 0.12), RNG, dur=dur, q=0.34)


def master(buf: np.ndarray, peak_db: float, drive: float) -> np.ndarray:
    """make_phantom_song.master 와 같음 (중음 보강 + 부드러운 리미터), drive 만 조절."""
    from scipy import signal
    mid = signal.sosfilt(signal.butter(2, [1500, 3200], "bandpass", fs=SR, output="sos"), buf, axis=1)
    y = buf + 0.42 * mid
    y = np.tanh(y / (np.max(np.abs(y)) + 1e-9) * drive)
    return y / (np.max(np.abs(y)) + 1e-9) * 10 ** (peak_db / 20)


def band(tr, at: float, chord, dur: float, g: float = 1.0, crash: bool = True) -> None:
    """빅밴드 강타: 트럼펫·색소폰·트롬본 화음 + 콘트라베이스 + 킥 (+ 크래시)."""
    for j, m in enumerate(chord):
        nm = "trumpet_open" if m >= 64 else "sax" if m >= 55 else "trombone"
        tr.add(inst(nm, m, dur), at + 0.004 * j, 0.26 * g, -0.5 + 0.17 * j)
    tr.add(inst("upright", chord[0] - 12, dur + 0.2), at, 0.5 * g)
    tr.add(d_kick(n_of(0.45), 1.0, RNG), at, 0.55 * g)
    if crash:
        tr.add(d_crash(n_of(2.6), 1.0, RNG), at, 0.4 * g, 0.25)


def compose(variant: str) -> tuple[np.ndarray, dict]:
    if variant == "loop":
        return compose_loop(), {}
    m = TL["variants"][variant]["markers"]
    short = variant == "short"
    hit, rise, sc, cl, card, rec, aft = (m[k] for k in ("hit", "rise", "scales", "climax", "card", "record", "afterglow"))
    tail = 2.0 if not short else 1.1
    tr = ps.Track(aft + tail)
    # 1) hit: 빅밴드 강타 + 심벌
    band(tr, hit, DM9, 0.35, 1.1)
    # 2) rise: 드럼 필인 상승 (스네어 셋잇단 점점 세게 + 탐, 절정 0.08초 전에 숨)
    k, i = rise, 0
    while k < cl - 0.08:
        u = (k - rise) / max(1e-3, cl - rise)
        tr.add(d_snare2(n_of(0.3), 1.0, RNG), k, 0.18 + 0.32 * u, 0.1 * (-1) ** i)
        if i % 3 == 2:
            tr.add(d_tom(n_of(0.5), 1.0, RNG, f=110 + 90 * u), k, 0.3 + 0.2 * u, -0.3)
        k += 0.085 - 0.03 * u
        i += 1
    # 3) scales: 색소폰 빠른 상승 선율 (D 도리안 + 꾸밈 반음)
    run = [62, 64, 65, 67, 68, 69, 71, 72, 74, 76, 77, 79]
    span = cl - sc - 0.08
    for j, nn in enumerate(run[:: 2 if short else 1]):
        n_ = len(run[:: 2 if short else 1])
        tr.add(inst("sax", nn, span / n_ * 1.05), sc + span * j / n_, 0.4 + 0.02 * j, 0.2)
    # 4) climax: 금관 전체 화려한 긴 화음 + 크래시
    hold = card - cl + 0.15
    band(tr, cl, [50, 57, 60, 64, 65, 69, 72, 76], hold, 1.15)
    tr.add(inst("trumpet_open", 81, hold), cl, 0.3, 0.1)              # 맨 위 A5 길게 (화려하게)
    tr.add(d_ride(n_of(1.2), 1.0, RNG), cl, 0.3, -0.3)
    # 5) card: 트럼펫이 약음기를 빼고 주인의 동기 D → A → G 를 크게 (+ 피아노 받침)
    q = (rec - card) / 2
    st = card
    for j, (nn, d) in enumerate(zip((74, 81, 79), (q, q, 2 * q - 0.06))):
        tr.add(inst("trumpet_open", nn, d), st, 0.6, 0.1)
        tr.add(inst("piano", nn - 24, 0.5), st, 0.25, -0.3)
        st += d
    # 6) record: 금화 '짤랑' + 인장 (킥·스네어 '착')
    tr.add(J.s_coin(n_of(0.9), RNG, big=True), rec, 1.0, 0.2)
    tr.add(d_kick(n_of(0.45), 1.0, RNG), rec, 0.45)
    tr.add(d_snare2(n_of(0.3), 1.0, RNG), rec, 0.35)
    # 7) 피아노 짧은 마무리 → D장조 '빰—빠밤' (마지막 '밤' = afterglow)
    if not short:
        for j, nn in enumerate((62, 66, 69, 74, 78)):       # 피아노 D장조 훑어 오르기
            tr.add(inst("piano", nn, 0.4), rec + 0.12 + 0.07 * j, 0.32, -0.3 + 0.15 * j)
        band(tr, rec + 0.5, DMAJ[:6], 0.32, 0.8, crash=False)   # 빰—
    band(tr, aft - 0.17, DMAJ[:6], 0.1, 0.75, crash=False)      # 빠
    band(tr, aft, DMAJ, tail * 0.85, 1.15)                       # 밤!
    tr.add(inst("piano", 86, tail * 0.7), aft + 0.02, 0.2, 0.3)
    y = ps.reverb(tr.buf, rt60=0.9, wet=0.16)
    n_end = int((aft + tail) * SR)
    y = y[:, :n_end]
    fade = int(0.4 * SR)
    y[:, -fade:] *= np.linspace(1, 0, fade)
    return master(y, -2.4 if short else -4.0, 0.9 if short else 0.8), dict(m)   # 평균 음량을 오케스트라 L01 전설의 노래와 같게


def compose_loop() -> np.ndarray:
    """카드 대기: 피아노 D장조 화음 + 브러시 '쓰윽' + 작은 빗소리, 이음매 없이 반복."""
    L = TL["loop_len"]
    tr = ps.Track(L)
    tr.add(J.s_rain(n_of(L + 2.0), RNG), 0.0, 0.12, -0.2)
    for i in range(4):
        for j, nn in enumerate((62, 66, 69, 73)):
            tr.add(inst("piano", nn, 1.0), 0.2 + i * L / 4 + 0.01 * j, 0.14, -0.2 + 0.13 * j)
        tr.add(J.d_brush(n_of(0.4), 1.0, RNG), 0.5 + i * L / 4, 0.12, 0.2)
    y = ps.reverb(tr.buf, rt60=0.9, wet=0.22)
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
