"""전설의 노래 '대성당' (SHARMION_THEMES.md 5장, DESIGN.md 43-18): 실러캔스 '태고' 포획 연출 전용.

기존 전설의 노래와 같은 길이 · 같은 싱크 마커(data/legend_catch_timeline.json) — 포획 연출 VFX(금빛 룬 고리)는 그대로 맞는다.
악기는 전투 곡 L05-ORGAN 과 같은 합성(src/audio/boss_organ.py). B♭단조 → 마지막 화음만 장화음(어둠 속 빛).

  hit 0초       오르간 최대 화음(리드 관까지) + 페달 + 낮은 북
  rise 0.3초    오르간 페달이 위로 걸어 올라감
  scales 0.8초  성가 합창 상승
  climax 1.4초  오르간 전체 + 성가 + 종 여러 개
  card 1.9초    성가가 주인의 동기 B♭ → F → E♭
  record 2.6초  큰 종 '댕—' + 인장 (낮은 북)
  afterglow     단조에서 마지막 화음만 B♭장화음으로 풀리며 끝 (오르간 + 성가 + 페달)
  짧은 버전은 같은 순서를 짧은 마커로, 대기(loop)는 조용한 오르간 장화음 + 깊은 물 울림 + 드문 작은 종.

출력: assets/music_generated/legend_catch_{full,short,loop}_L05-ORGAN.ogg (+ legend_catch_markers.json 에 추가)
      tools/audio/reference/legend_catch/L05-ORGAN_full.wav · L05-ORGAN_short.wav
사용: python tools/audio/make_organ_legend_song.py
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
from src.audio import boss_organ as O  # noqa: E402
from src.audio.boss_synth import hz  # noqa: E402

SR = ps.SR
ROOT = ps.ROOT
TL = json.load(open(os.path.join(ROOT, "data", "legend_catch_timeline.json"), encoding="utf-8"))
REF = os.path.join(ROOT, "tools", "audio", "reference", "legend_catch")
SID = "L05-ORGAN"
BB3 = 58
MINOR = [46, 53, 58, 61, 65, 70]       # B♭단조 (B♭ F B♭ D♭ F B♭)
MAJOR = [46, 53, 58, 62, 65, 70, 74]   # B♭장조 — 마지막 화음만 (D♮)
RNG = np.random.default_rng(136)


def n_of(sec: float) -> int:
    return max(1, int(sec * SR))


def organ(chord, dur: float, full=True) -> np.ndarray:
    x = sum(O.pipe(hz(m), n_of(dur + 0.1), RNG, full=full) for m in chord)
    return x / (np.abs(x).max() or 1.0)


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
    # 1) hit: 오르간 최대 화음 + 페달 + 낮은 북
    tr.add(organ(MINOR, rise + 0.2), hit, 0.75)
    tr.add(O.i_pedal(hz(BB3 - 24), n_of(rise + 0.3), RNG), hit, 0.6)
    tr.add(O.d_heart(n_of(0.6), 1.0, RNG), hit, 0.9)
    # 2) rise: 페달이 위로 걸어 올라감 (B♭ C D♭ E♭ F G♭ A — 화성단음계)
    walk = [34, 36, 37, 39, 41, 42, 45]
    span = cl - rise - 0.08
    for j, nn in enumerate(walk[:: 2 if short else 1]):
        k_ = len(walk[:: 2 if short else 1])
        tr.add(O.i_pedal(hz(nn), n_of(span / k_ * 1.05), RNG), rise + span * j / k_, 0.55 + 0.03 * j)
    # 3) scales: 성가 합창 상승 (모음 바꿔 가며)
    up = [58, 60, 61, 63, 65, 66, 69, 70]
    span = cl - sc - 0.08
    for j, nn in enumerate(up[:: 2 if short else 1]):
        k_ = len(up[:: 2 if short else 1])
        tr.add(O.chant(hz(nn), n_of(span / k_ * 1.3), RNG, vowel="oae"[j % 3]), sc + span * j / k_, 0.4 + 0.03 * j)
    # 4) climax: 오르간 전체 + 성가 + 종 여러 개
    hold = card - cl + 0.25
    tr.add(organ(MINOR + [77], hold), cl, 0.8)
    tr.add(O.i_pedal(hz(BB3 - 24), n_of(hold), RNG), cl, 0.6)
    for j, nn in enumerate((58, 65, 70)):
        tr.add(O.chant(hz(nn), n_of(hold), RNG, vowel="a"), cl, 0.3, (j - 1) * 0.4)
    for j, f in enumerate((hz(BB3 - 12), hz(BB3), hz(BB3 + 7), hz(BB3 + 12))):
        tr.add(O.d_bell(n_of(3.0), 1.0, RNG, f=f), cl + 0.03 * j, 0.32 - 0.04 * j, (-0.5, 0.5, -0.2, 0.2)[j])
    tr.add(O.d_heart(n_of(0.6), 1.0, RNG), cl, 0.9)
    # 5) card: 성가가 주인의 동기 B♭ → F → E♭
    q = (rec - card) / 2
    st = card
    for j, (nn, d) in enumerate(zip((58, 65, 63), (q, q, 2 * q - 0.06))):
        tr.add(O.chant(hz(nn), n_of(d + 0.15), RNG, vowel="oao"[j]), st, 0.75)
        tr.add(O.chant(hz(nn - 12), n_of(d + 0.15), RNG, vowel="oao"[j]), st, 0.4, -0.3)
        st += d
    # 6) record: 큰 종 '댕—' + 인장 (낮은 북)
    tr.add(O.d_bell(n_of(3.5), 1.0, RNG, f=hz(BB3 - 12)), rec, 0.85, 0.1)
    tr.add(O.d_heart(n_of(0.6), 1.0, RNG), rec, 0.8)
    # 7) 마지막 화음만 장화음 (어둠 속 빛)
    if not short:
        tr.add(organ(MINOR, aft - rec - 0.22, full=False), rec + 0.15, 0.4)   # 마지막 화음 직전에 숨
    tr.add(organ(MAJOR, tail), aft, 0.85)
    tr.add(O.i_pedal(hz(BB3 - 24), n_of(tail), RNG), aft, 0.6)
    for j, nn in enumerate((58, 62, 65)):
        tr.add(O.chant(hz(nn), n_of(tail * 0.9), RNG, vowel="o"), aft + 0.02, 0.3, (j - 1) * 0.4)
    tr.add(O.d_heart(n_of(0.6), 1.0, RNG), aft, 1.0)
    tr.add(O.d_bell(n_of(3.0), 1.0, RNG, f=hz(BB3)), aft, 0.45, -0.2)   # 장화음과 함께 종 (또렷한 시작)
    y = ps.reverb(tr.buf, rt60=2.0, wet=0.24)
    n_end = int((aft + tail) * SR)
    y = y[:, :n_end]
    fade = int(0.4 * SR)
    y[:, -fade:] *= np.linspace(1, 0, fade)
    return master(y, -2.0, 1.0 if short else 0.95), dict(m)   # 평균 음량을 L05 전설의 노래와 같게


def compose_loop() -> np.ndarray:
    """카드 대기: 조용한 오르간 장화음 + 깊은 물 울림 + 드문 작은 종, 이음매 없이 반복."""
    L = TL["loop_len"]
    tr = ps.Track(L)
    tr.add(O.s_deep(n_of(L + 2.0), RNG), 0.0, 0.25)
    tr.add(organ([58, 62, 65, 70], L + 2.0, full=False), 0.0, 0.3)
    for i in range(2):
        tr.add(O.d_smallbell(n_of(2.0), 1.0, RNG), 0.6 + i * L / 2, 0.08, 0.4 * (-1) ** i)
    y = ps.reverb(tr.buf, rt60=2.0, wet=0.3)
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
