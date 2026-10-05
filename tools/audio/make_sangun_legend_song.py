"""전설의 노래 '산의 노래' (SHARMION_THEMES.md 2장, DESIGN.md 43-17): 산신 쏘가리 '산군' 포획 연출 전용.

기존 전설의 노래와 같은 길이 · 같은 싱크 마커(data/legend_catch_timeline.json) — 포획 연출 VFX(범의 발톱)는 그대로 맞는다.
악기는 전투 곡 L02-SANGUN 과 같은 합성(src/audio/boss_sangun.py). E단조 5음 → 마무리는 목 노래가 E장조 5음으로 풀림.

  hit 0초       모든 북 강타 + 낮은 '어흥'
  rise 0.3초    손북 몰아치기 (점점 빠르고 세게)
  scales 0.8초  마두금이 위로 치솟음
  climax 1.4초  전체 + 목 노래 화음(낮은 E + 휘파람 배음) + 큰북·낮은 북 + 외침 '하!'
  card 1.9초    뿔나팔이 주인의 동기 E → B → A
  record 2.6초  발톱 할퀴는 '촥' + 인장 (큰북)
  afterglow     목 노래 지속음이 E장조 5음(E·F#·G#·B·C#)으로 풀리며 끝 (마지막 큰북 = afterglow)
  짧은 버전은 같은 순서를 짧은 마커로, 대기(loop)는 낮은 목 노래 + 바람 + 드문 손북.

출력: assets/music_generated/legend_catch_{full,short,loop}_L02-SANGUN.ogg (+ legend_catch_markers.json 에 추가)
      tools/audio/reference/legend_catch/L02-SANGUN_full.wav · L02-SANGUN_short.wav
사용: python tools/audio/make_sangun_legend_song.py
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
from src.audio import boss_sangun as S  # noqa: E402
from src.audio.boss_muhyeop import s_wind  # noqa: E402
from src.audio.boss_synth import hz  # noqa: E402

SR = ps.SR
ROOT = ps.ROOT
TL = json.load(open(os.path.join(ROOT, "data", "legend_catch_timeline.json"), encoding="utf-8"))
REF = os.path.join(ROOT, "tools", "audio", "reference", "legend_catch")
SID = "L02-SANGUN"
E4 = 64
RNG = np.random.default_rng(156)


def n_of(sec: float) -> int:
    return max(1, int(sec * SR))


def inst(name: str, m: float, dur: float) -> np.ndarray:
    return S.INST[name](hz(m), n_of(dur + 0.12), RNG, dur=dur, q=0.38)


def drum(name: str) -> np.ndarray:
    fn, ln = S.DRUM[name]
    return fn(n_of(ln), 1.0, RNG)


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
    f0 = hz(E4 - 24)
    # 1) hit: 모든 북 강타 + 낮은 '어흥'
    tr.add(drum("big"), hit, 1.0)
    tr.add(drum("low"), hit, 0.8, -0.15)
    tr.add(drum("hand"), hit, 0.5, 0.3)
    tr.add(S.s_roar(n_of(1.0), RNG), hit + 0.02, 0.55, 0.1)
    # 2) rise: 손북 몰아치기 (절정 0.1초 전에 숨)
    k, i = rise, 0
    while k < cl - 0.1:
        u = (k - rise) / max(1e-3, cl - rise)
        tr.add(drum("hand"), k, 0.3 + 0.4 * u, 0.3 * (-1) ** i)
        if i % 4 == 0:
            tr.add(drum("low"), k, 0.3 + 0.4 * u, -0.15)
        k += 0.09 - 0.04 * u
        i += 1
    # 3) scales: 마두금이 위로 치솟음 (5음)
    up = [64, 67, 69, 71, 74, 76, 79, 81, 83, 86]
    span = cl - sc - 0.1
    for j, nn in enumerate(up[:: 2 if short else 1]):
        n_ = len(up[:: 2 if short else 1])
        tr.add(inst("morin", nn, span / n_ * 1.1), sc + span * j / n_, 0.4 + 0.02 * j, 0.15)
    # 4) climax: 전체 + 목 노래 화음 + 북 + 외침
    hold = card - cl + 0.2
    tr.add(drum("big"), cl, 1.05)
    tr.add(drum("low"), cl, 0.85, -0.15)
    tr.add(S.throat(f0, n_of(hold + 0.6), RNG, whistle=[(0.0, 12), (hold * 0.5, 16)], sharp=1.4), cl, 0.55)
    tr.add(inst("morin", 76, hold), cl, 0.35, -0.25)
    tr.add(inst("horn", 71, hold), cl, 0.35, 0.2)
    tr.add(S.s_shout(n_of(0.32), RNG), cl, 0.5, 0.2)
    # 5) card: 뿔나팔 주인의 동기 E → B → A
    q = (rec - card) / 2
    st = card
    for j, (nn, d) in enumerate(zip((76, 83, 81), (q, q, 2 * q - 0.06))):
        tr.add(inst("horn", nn, d), st, 0.6, 0.1)
        tr.add(drum("hand"), st, 0.35, 0.3)
        st += d
    # 6) record: 발톱 '촥' + 인장 (큰북)
    tr.add(S.s_claw(n_of(0.45), RNG), rec, 0.95, 0.15)
    tr.add(drum("big"), rec, 0.7)
    # 7) 목 노래 지속음이 E장조 5음으로 풀리며 끝 (휘파람 배음: 8 E · 10 G# · 12 B · 9 F# · 8 E)
    wh = [(0.0, 8), (0.3, 10), (0.6, 12), (0.9, 9), (1.3, 8)] if not short else [(0.0, 10), (0.4, 12), (0.7, 8)]
    tr.add(S.throat(f0, n_of(aft + tail - rec), RNG, whistle=wh, sharp=1.2), rec + 0.05, 0.5)
    tr.add(drum("big"), aft, 0.9)
    tr.add(drum("low"), aft, 0.6, -0.15)
    tr.add(inst("horn", 68, tail * 0.7), aft + 0.02, 0.3, 0.2)        # G#4 — 장조로 풀림
    y = ps.reverb(tr.buf, rt60=1.1, wet=0.16)
    n_end = int((aft + tail) * SR)
    y = y[:, :n_end]
    fade = int(0.4 * SR)
    y[:, -fade:] *= np.linspace(1, 0, fade)
    return master(y, -2.0, 1.35 if short else 1.5), dict(m)   # 평균 음량을 L02 전설의 노래와 같게


def compose_loop() -> np.ndarray:
    """카드 대기: 낮은 목 노래 + 바람 + 드문 손북, 이음매 없이 반복."""
    L = TL["loop_len"]
    tr = ps.Track(L)
    tr.add(s_wind(n_of(L + 2.0), RNG), 0.0, 0.25, -0.2)
    tr.add(S.throat(hz(E4 - 24), n_of(L + 2.0), RNG, whistle=[(0.0, 8), (L / 2, 12)], sharp=0.6), 0.0, 0.3)
    for i in range(4):
        tr.add(drum("hand"), 0.3 + i * L / 4, 0.15, 0.3)
    y = ps.reverb(tr.buf, rt60=1.1, wet=0.22)
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
