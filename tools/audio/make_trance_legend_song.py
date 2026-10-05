"""전설의 노래 '결정' (BOSS_BGM.md 엘드라시온 L08, DESIGN.md 43-23): 결정어왕 프리시아 포획 연출 전용.

기존 전설의 노래와 같은 길이 · 같은 싱크 마커(data/legend_catch_timeline.json) — 포획 연출 VFX(수정 기둥)는 그대로 맞는다.
악기는 전투 곡 L08-TRANCE 와 같은 합성(src/audio/boss_trance.py). A단조 → 마지막 화음만 A장조.

  hit 0초       전체 강타: 킥 + 크래시 + 슈퍼소 화음 + 오케스트라 타격 + 수정 벨
  rise 0.3초    빌드업: 스네어 몰아치기(점점 촘촘히) + 잡음 상승 — 절정 0.08초 전에 멈춤 (트랜스의 '드롭' 직전 정적)
  scales 0.8초  플럭 아르페지오가 두 옥타브 위로 + 합창 '아—' 상승
  climax 1.4초  드롭: 킥 + 슈퍼소 화음 + 게이트 + 합창 + 오케스트라 타격 + 크래시 — 가장 크게
  card 1.9초    수정 벨 + 슈퍼소 리드가 함께 주인의 동기 A → E → D
  record 2.6초  킥 + 박수 + 수정이 부서지는 소리 인장
  afterglow     A장조 슈퍼소 패드 + 합창 + 수정 벨 화음 (C♯)
  짧은 버전은 같은 순서를 짧은 마커로, 대기(loop)는 조용한 패드 + 드문 수정 벨.

출력: assets/music_generated/legend_catch_{full,short,loop}_L08-TRANCE.ogg (+ legend_catch_markers.json 에 추가)
      tools/audio/reference/legend_catch/L08-TRANCE_full.wav · L08-TRANCE_short.wav
사용: python tools/audio/make_trance_legend_song.py
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
from src.audio import boss_trance as T  # noqa: E402
from src.audio.boss_synth import hz  # noqa: E402

SR = ps.SR
ROOT = ps.ROOT
TL = json.load(open(os.path.join(ROOT, "data", "legend_catch_timeline.json"), encoding="utf-8"))
REF = os.path.join(ROOT, "tools", "audio", "reference", "legend_catch")
SID = "L08-TRANCE"
A3 = 57
MINOR = [45, 52, 57, 60, 64]       # A단조 화음
MAJOR = [45, 52, 57, 61, 64, 69]   # A장조 — 마지막 화음 (C♯)
Q = 60.0 / 158
RNG = np.random.default_rng(158)


def n_of(sec: float) -> int:
    return max(1, int(sec * SR))


def inst(name: str, m: float, dur: float) -> np.ndarray:
    return T.INST[name](hz(m), n_of(dur + 0.1), RNG, dur=dur, q=Q)


def drum(kind: str, vel: float = 1.0) -> np.ndarray:
    fn, ln, g, _ = T.KIT[kind]
    return fn(n_of(ln), vel, RNG) * g * vel


def chord(tr, notes, at: float, dur: float, g: float = 1.0, kind="pad") -> None:
    for j, m in enumerate(notes):
        tr.add(inst(kind, m, dur), at, (0.16 if kind == "pad" else 0.1) * g, (j / max(1, len(notes) - 1) - 0.5) * 0.9)


def orch(tr, notes, at: float, g: float = 1.0) -> None:
    for j, m in enumerate(notes[:4]):
        tr.add(inst("hit_brass", m, 0.35), at, 0.16 * g, (j - 1.5) * 0.3)
        tr.add(inst("hit_str", m + 12, 0.35), at, 0.1 * g, -(j - 1.5) * 0.3)


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
    st = Q / 4
    # 1) hit: 킥 + 크래시 + 슈퍼소 화음 + 오케스트라 타격 + 수정 벨
    tr.add(drum("kick"), hit, 1.0)
    tr.add(drum("crash"), hit, 1.0)
    chord(tr, MINOR, hit, rise + 0.1, 1.2, kind="gate")
    orch(tr, MINOR[1:], hit, 1.0)
    tr.add(inst("bell", 81, 1.0), hit, 0.3, 0.3)
    # 2) rise: 빌드업 (스네어 점점 촘촘히 + 잡음 상승) — 절정 0.08초 전에 멈춤
    t = rise
    k = 0
    while t < cl - 0.08:
        u = (t - rise) / (cl - rise)
        tr.add(drum("snare", 0.4 + 0.6 * u), t, 1.0)
        t += st * (2 if u < 0.5 and not short else 1)
        k += 1
    tr.add(T.s_riser(n_of(cl - 0.08 - rise), RNG), rise, 0.4)
    # 3) scales: 플럭 아르페지오 두 옥타브 위로 + 합창 상승
    up = [57, 60, 64, 69, 72, 76, 81, 84]
    span = cl - sc - 0.08
    stepn = up[:: 2 if short else 1]
    for j, nn in enumerate(stepn):
        at = sc + span * j / len(stepn)
        tr.add(inst("pluck", nn, span / len(stepn) * 1.5), at, 0.3 + 0.02 * j, 0.3 * (-1) ** j)
    for j, nn in enumerate((57, 59, 60, 62, 64)[:: 2 if short else 1]):
        tr.add(inst("choir", nn, span / 5 * 1.6), sc + span * j / 5, 0.22, -0.2)
    # 4) climax: 드롭 — 킥 + 슈퍼소 + 합창 + 오케스트라 + 크래시
    hold = card - cl + 0.2
    tr.add(drum("kick"), cl, 1.0)
    tr.add(drum("crash"), cl, 1.0)
    chord(tr, MINOR + [69], cl, hold, 1.3)
    for s in range(int(hold / st)):
        if s % 4 != 3:
            chord(tr, MINOR[1:], cl + s * st, st * 0.5, 0.8, kind="gate")
    for j, nn in enumerate((57, 64, 69)):
        tr.add(inst("choir", nn, hold), cl, 0.28, (j - 1) * 0.5)
    orch(tr, MINOR[1:], cl, 1.2)
    for b in range(1, int(hold / Q) + 1):
        tr.add(drum("kick", 0.8), cl + b * Q, 1.0)
    # 5) card: 수정 벨 + 슈퍼소 리드가 주인의 동기 A → E → D
    q = (rec - card) / 2
    t = card
    for nn, d in zip((81, 88, 86), (q, q, 2 * q - 0.06)):
        tr.add(inst("bell", nn, d + 0.3), t, 0.36, 0.25)
        tr.add(inst("lead", nn - 12, d), t, 0.28, -0.2)
        tr.add(drum("kick", 0.8), t, 1.0)
        t += d
    chord(tr, MINOR, card, rec - card, 0.6)
    # 6) record: 킥 + 박수 + 수정이 부서지는 소리
    tr.add(drum("kick"), rec, 1.0)
    tr.add(drum("clap"), rec, 1.0)
    tr.add(T.s_shatter(n_of(1.2), RNG), rec, 0.35, 0.2)
    # 7) A장조로 끝
    if not short:
        chord(tr, [52, 56, 59, 64], rec + 0.12, aft - rec - 0.2, 0.7)                # V (E장조) → 숨 → I
    chord(tr, MAJOR, aft, tail, 1.3)
    for j, nn in enumerate((57, 61, 64, 69)):
        tr.add(inst("choir", nn, tail * 0.9), aft, 0.24, (j - 1.5) * 0.4)
        tr.add(inst("bell", nn + 12, tail * 0.8), aft + j * 0.06, 0.16, (j - 1.5) * 0.5)
    tr.add(drum("kick"), aft, 1.0)
    tr.add(drum("crash"), aft, 0.8)
    y = ps.reverb(tr.buf, rt60=1.2, wet=0.2)
    n_end = int((aft + tail) * SR)
    y = y[:, :n_end]
    fade = int(0.4 * SR)
    y[:, -fade:] *= np.linspace(1, 0, fade)
    return master(y, -2.0, 1.9 if short else 2.4), dict(m)   # 평균 음량을 L08 전설의 노래와 같게


def compose_loop() -> np.ndarray:
    """카드 대기: 조용한 A장조 패드 + 드문 수정 벨, 이음매 없이 반복."""
    L = TL["loop_len"]
    tr = ps.Track(L)
    chord(tr, [57, 61, 64, 69], 0.0, L + 2.0, 0.6)
    for i in range(3):
        tr.add(inst("bell", (81, 85, 88)[i], 1.5), 0.4 + i * L / 3, 0.07, 0.4 * (-1) ** i)
    y = ps.reverb(tr.buf, rt60=1.4, wet=0.3)
    n = int(L * SR)
    out = y[:, :n].copy()
    tl_ = y[:, n:n * 2]
    out[:, : tl_.shape[1]] += tl_
    out = 0.5 * (out + np.roll(out, n // 2, axis=1))
    return master(out, -12.0, 1.2)


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
