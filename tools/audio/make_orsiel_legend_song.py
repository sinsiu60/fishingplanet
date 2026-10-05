"""전설의 노래 '천해' (ORSIEL_BGM.md, DESIGN.md 43-27): 천해왕 오르시엘 포획 연출 전용 — C장조.

전투 곡 L12-ORSIEL(음표 데이터) 4페이즈는 C장조로 바뀌어 딸림화음(G)에서 반복되므로, 뜰채 성공 순간 이 노래의 첫 타격(C장조)이
그 딸림화음을 풀어 줌. 같은 길이 · 같은 싱크 마커(data/legend_catch_timeline.json) — 포획 연출(바다 가르기) · 첫 포획 뒤 최종 엔딩 그대로.
음색은 전투 곡과 같은 게임 음색 (src/audio/boss_notes.py — 천해의 종 · 금관 · 호른 · 트럼펫 · 현악 · 합창 · 팀파니 · taiko).
다른 곡의 선율을 가져오지 않음 — 주인의 동기(C → G → F)만 (모든 전설의 노래 공통 규칙).

  hit 0초       C장조 전체 강타: 낮은 금관 · 호른 · 현악 트레몰로 · 합창 + 천해의 종 + taiko + 크래시
  rise 0.3초    taiko · 팀파니 몰아치기 (점점 촘촘히, 절정 0.08초 전에 멈춤)
  scales 0.8초  현악 C장조 두 옥타브 상승 + 합창
  climax 1.4초  C장조 최대 + 천해의 종 + 합창 + 크래시 + taiko
  card 1.9초    호른 · 트럼펫이 주인의 동기 C → G → F
  record 2.6초  천해의 종 + taiko 인장
  afterglow     G장조(V)로 숨 → C장조 (금관 · 합창 · 현악 · 종)
  짧은 버전은 같은 순서를 짧은 마커로, 대기(loop)는 조용한 C장조 현악 · 합창 + 멀리서 종.

출력: assets/music_generated/legend_catch_{full,short,loop}_L12-ORSIEL.ogg (+ legend_catch_markers.json 에 추가)
      tools/audio/reference/legend_catch/L12-ORSIEL_full.wav · L12-ORSIEL_short.wav
사용: python tools/audio/make_orsiel_legend_song.py
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
from src.audio import boss_notes as O  # noqa: E402
from src.audio import boss_synth as bs  # noqa: E402
from src.audio.boss_synth import hz  # noqa: E402

SR = ps.SR
ROOT = ps.ROOT
TL = json.load(open(os.path.join(ROOT, "data", "legend_catch_timeline.json"), encoding="utf-8"))
REF = os.path.join(ROOT, "tools", "audio", "reference", "legend_catch")
SID = "L12-ORSIEL"
C_MAJ = [48, 55, 60, 64, 67]
G_MAJ = [43, 55, 59, 62, 67]
C_SCALE = [60, 62, 64, 65, 67, 69, 71, 72]
RNG = np.random.default_rng(138)


def n_of(sec: float) -> int:
    return max(1, int(sec * SR))


def inst(track: str, m: float, dur: float) -> np.ndarray:
    return O.VOICE[track](hz(m), n_of(dur + 0.1), RNG)


def taiko(vel=1.0) -> np.ndarray:
    return (bs.d_taiko(n_of(0.6), 1.0, RNG) * 0.8 + np.pad(bs.d_bigdrum(n_of(1.2), 1.0, RNG) * 0.45, (0, 0))[:n_of(0.6)]) * vel


def timp(vel=1.0, f=hz(36)) -> np.ndarray:
    return bs.d_timp(n_of(1.4), 1.0, RNG, f=f) * vel


def bell(tr, m, at, g=1.0, ring=6.0) -> None:
    tr.add(inst("bell", m, ring), at, 0.4 * g)


def chord(tr, notes, at, dur, g=1.0, choir=True) -> None:
    for j, m in enumerate(notes):
        pan = (j / max(1, len(notes) - 1) - 0.5) * 0.9
        tr.add(inst("lowbrass", m - 12 if m >= 55 else m, dur), at, 0.16 * g, pan)
        tr.add(inst("horn", m, dur), at, 0.12 * g, -pan)
        tr.add(inst("strings_trem", m + 12, dur), at, 0.08 * g, pan)
        if choir:
            tr.add(inst("choir_a", m + 12 if m < 55 else m, dur), at, 0.14 * g, -pan)


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
    # 1) hit: C장조 전체 강타 + 천해의 종 + taiko + 크래시
    chord(tr, C_MAJ, hit, rise + 0.15, 1.2)
    bell(tr, 36, hit, 1.0)
    tr.add(taiko(), hit, 1.0)
    tr.add(bs.d_crash(n_of(2.2), 1.0, RNG) * 0.3, hit, 1.0, 0.25)
    # 2) rise: taiko · 팀파니 몰아치기 (점점 촘촘히 · 절정 0.08초 전에 멈춤)
    t = rise
    k = 0
    while t < cl - 0.08:
        u = (t - rise) / (cl - rise)
        tr.add(timp(0.5 + 0.5 * u, hz(36) * (1.5 if k % 4 == 2 else 1.0)), t, 0.8, 0.1 * (-1) ** k)
        if k % 2 == 0:
            tr.add(taiko(0.6 + 0.4 * u), t, 1.0)
        t += max(0.045, (0.11 if not short else 0.065) * (1 - 0.5 * u))
        k += 1
    # 3) scales: 현악 C장조 두 옥타브 상승 + 합창
    up = C_SCALE + [d + 12 for d in C_SCALE[1:]]
    stepn = up[:: 2 if short else 1]
    span = cl - sc - 0.08
    for j, nn in enumerate(stepn):
        at = sc + span * j / len(stepn)
        tr.add(inst("strings", nn - 12, span / len(stepn) * 1.4), at, 0.32, 0.3 * (-1) ** j)
    for j, nn in enumerate((60, 64, 67)):
        tr.add(inst("choir_a", nn, span), sc + span * j / 3, 0.2, -0.2)
    # 4) climax: C장조 최대 + 천해의 종 + 합창 + 크래시 + taiko
    hold = card - cl + 0.2
    chord(tr, C_MAJ + [72], cl, hold, 1.4)
    bell(tr, 36, cl, 1.1)
    tr.add(taiko(), cl, 1.0)
    tr.add(timp(), cl, 0.9)
    tr.add(bs.d_crash(n_of(2.2), 1.0, RNG) * 0.32, cl, 1.0, 0.25)
    # 5) card: 호른 · 트럼펫 주인의 동기 C → G → F
    q = (rec - card) / 2
    t = card
    for nn, d in zip((72, 79, 77), (q, q, 2 * q - 0.06)):
        tr.add(inst("horn", nn - 12, d), t, 0.36, -0.15)
        tr.add(inst("trumpet", nn, d), t, 0.24, 0.2)
        tr.add(timp(0.7), t, 0.8)
        t += d
    for j, nn in enumerate((48, 60, 64)):
        tr.add(inst("strings_trem", nn, rec - card), card, 0.1, (j - 1) * 0.4)
    # 6) record: 천해의 종 + taiko
    bell(tr, 36, rec, 1.2, ring=4.0)
    tr.add(taiko(), rec, 1.0)
    # 7) G장조(V)로 숨 → C장조로 끝
    if not short:
        chord(tr, G_MAJ, rec + 0.15, aft - rec - 0.22, 0.6)
    chord(tr, C_MAJ + [72, 76], aft, tail, 1.3)
    bell(tr, 48, aft, 0.7, ring=tail + 1.0)
    tr.add(taiko(), aft, 1.0)
    tr.add(timp(), aft, 0.9)
    y = ps.reverb(tr.buf, rt60=1.6, wet=0.2)
    n_end = int((aft + tail) * SR)
    y = y[:, :n_end]
    fade = int(0.4 * SR)
    y[:, -fade:] *= np.linspace(1, 0, fade)
    for at in (cl, aft):   # 강타 직전 '숨' (43-20)
        y = ps.breath(y, at)
    return master(y, -2.0, 2.8 if short else 1.9), dict(m)   # 평균 음량을 L12 전설의 노래와 같게


def compose_loop() -> np.ndarray:
    """카드 대기: 조용한 C장조 현악 · 합창 + 멀리서 천해의 종, 이음매 없이 반복."""
    L = TL["loop_len"]
    tr = ps.Track(L)
    for j, nn in enumerate((48, 60, 64, 67)):
        tr.add(inst("strings_trem", nn, L + 2.0), 0.0, 0.07, (j - 1.5) * 0.4)
        tr.add(inst("choir_a", nn + 12 if nn < 55 else nn, L + 2.0), 0.0, 0.06, -(j - 1.5) * 0.4)
    tr.add(inst("bell", 36, 3.0), 0.5, 0.12)
    y = ps.reverb(tr.buf, rt60=1.8, wet=0.3)
    n = int(L * SR)
    out = y[:, :n].copy()
    tl_ = y[:, n:n * 2]
    out[:, : tl_.shape[1]] += tl_
    out = 0.5 * (out + np.roll(out, n // 2, axis=1))
    return master(out, -12.0, 1.3)


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
