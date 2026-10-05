"""전설의 노래 '불꽃' (BOSS_BGM.md 엘드라시온 L10, DESIGN.md 43-25): 불꽃상어 이그니스 포획 연출 전용.

기존 전설의 노래와 같은 길이 · 같은 싱크 마커(data/legend_catch_timeline.json) — 포획 연출 VFX(불기둥)는 그대로 맞는다.
악기는 전투 곡 L10-FLAMENCO 와 같은 합성(src/audio/boss_flamenco.py). E 프리지안 도미넌트 → 마지막은 E장조 화음 (플라멩코 종지).

  hit 0초       전체 강타: 라스게아도 + 파워 코드 + 킥 + 크래시 + 외침 '하!'
  rise 0.3초    손뼉 · 카혼 몰아치기 (점점 촘촘히, 절정 0.08초 전에 멈춤)
  scales 0.8초  피카도 빠른 상승 (프리지안 도미넌트)
  climax 1.4초  라스게아도 굴림 + 파워 코드 + 투베이스 + 합창 '아—' + 외침 + 크래시 — 가장 크게
  card 1.9초    피카도 · 일렉 리드 기타가 함께 주인의 동기 E → B → A
  record 2.6초  골페 + 카혼 + 손뼉 '짝' 인장
  afterglow     안달루시아 종지 F → E (E장조 G♯) 라스게아도 + 합창 + 파워 코드
  짧은 버전은 같은 순서를 짧은 마커로, 대기(loop)는 조용한 나일론 기타 E장조 뜯기 + 드문 손뼉.

출력: assets/music_generated/legend_catch_{full,short,loop}_L10-FLAMENCO.ogg (+ legend_catch_markers.json 에 추가)
      tools/audio/reference/legend_catch/L10-FLAMENCO_full.wav · L10-FLAMENCO_short.wav
사용: python tools/audio/make_flamenco_legend_song.py
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
from src.audio import boss_flamenco as F  # noqa: E402
from src.audio.boss_synth import hz  # noqa: E402

SR = ps.SR
ROOT = ps.ROOT
TL = json.load(open(os.path.join(ROOT, "data", "legend_catch_timeline.json"), encoding="utf-8"))
REF = os.path.join(ROOT, "tools", "audio", "reference", "legend_catch")
SID = "L10-FLAMENCO"
E_CH = [40, 47, 52, 56, 59, 64]     # 기타 E장조 (E B E G# B E)
F_CH = [41, 48, 53, 57, 60, 65]     # F장조 (프리지안 반음 위)
AM_CH = [45, 52, 57, 60, 64, 69]    # Am
PHRYG = [64, 65, 68, 69, 71, 72, 74, 76]   # E 프리지안 도미넌트
Q = 60.0 / 176
RNG = np.random.default_rng(176)


def n_of(sec: float) -> int:
    return max(1, int(sec * SR))


def inst(name: str, m: float, dur: float) -> np.ndarray:
    return F.INST[name](hz(m), n_of(dur + 0.1), RNG, dur, Q)


def drum(kind: str, vel: float = 1.0) -> np.ndarray:
    fn, ln, g, _ = F.KIT[kind]
    return fn(n_of(ln), vel, RNG) * g * vel


def strum(tr, notes, at: float, g: float = 1.0, up=False, gap=0.006, ln=0.6) -> None:
    seq = notes[::-1] if up else notes
    for j, m in enumerate(seq):
        tr.add(inst("nylon", m, ln), at + j * gap, 0.13 * g * (0.7 if up else 1.0), (j - 2.5) * 0.1)


def rasg(tr, notes, at: float, g: float = 1.0) -> None:
    for f in range(4):
        strum(tr, notes, at + f * 0.022, g * (0.75 + 0.1 * f), gap=0.004, ln=0.5)


def power(tr, root: int, at: float, dur: float, g: float = 1.0) -> None:
    tr.add(inst("gtr_power", root, dur), at, 0.22 * g, -0.3)


def shout(tr, at: float, g: float = 1.0) -> None:
    tr.add(F.s_shout(n_of(0.4), RNG), at, 0.45 * g, 0.1)


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
    # 1) hit: 라스게아도 + 파워 코드 + 킥 + 크래시 + 외침
    rasg(tr, E_CH, hit, 1.2)
    power(tr, 40, hit, rise + 0.1)
    tr.add(drum("kick"), hit, 1.0)
    tr.add(drum("crash"), hit, 1.0)
    shout(tr, hit + 0.02)
    # 2) rise: 손뼉 · 카혼 몰아치기 (점점 촘촘히 · 절정 0.08초 전에 멈춤)
    t = rise
    k = 0
    while t < cl - 0.08:
        u = (t - rise) / (cl - rise)
        tr.add(drum("palma", 0.6 + 0.4 * u), t, 1.0, 0.25)
        tr.add(drum("clow" if k % 2 == 0 else "cslap", 0.6 + 0.4 * u), t, 1.0, -0.1)
        t += max(0.05, (0.12 if not short else 0.07) * (1 - 0.5 * u))
        k += 1
    # 3) scales: 피카도 빠른 상승 (프리지안 도미넌트 두 옥타브)
    up = PHRYG + [d + 12 for d in PHRYG[1:]]
    stepn = up[:: 2 if short else 1]
    span = cl - sc - 0.08
    for j, nn in enumerate(stepn):
        tr.add(inst("picado", nn, 0.2), sc + span * j / len(stepn), 0.35, 0.15)
    # 4) climax: 라스게아도 굴림 + 파워 코드 + 투베이스 + 합창 + 외침 + 크래시
    hold = card - cl + 0.2
    for s in range(int(hold / (Q / 2))):
        rasg(tr, E_CH, cl + s * Q / 2, 1.1 if s == 0 else 0.7)
    power(tr, 40, cl, hold, 1.2)
    for s in range(int(hold / (Q / 4))):
        tr.add(drum("kick", 0.8 if s else 1.0), cl + s * Q / 4, 1.0)
    for j, nn in enumerate((64, 68, 71)):
        tr.add(inst("choir_a", nn, hold), cl, 0.24, (j - 1) * 0.5)
    shout(tr, cl, 1.2)
    tr.add(drum("crash"), cl, 1.0)
    # 5) card: 피카도 · 일렉 리드 기타가 주인의 동기 E → B → A
    q = (rec - card) / 2
    t = card
    for nn, d in zip((76, 83, 81), (q, q, 2 * q - 0.06)):
        tr.add(inst("picado", nn, d), t, 0.42, 0.2)
        tr.add(inst("gtr_lead", nn - 12, d), t, 0.24, -0.2)
        tr.add(drum("clow", 0.8), t, 1.0)
        t += d
    strum(tr, E_CH, card, 0.6, ln=rec - card)
    # 6) record: 골페 + 카혼 + 손뼉 인장
    tr.add(drum("golpe"), rec, 1.0)
    tr.add(drum("clow"), rec, 1.0)
    tr.add(drum("palma"), rec, 1.0)
    # 7) 안달루시아 종지 F → E (E장조)
    if not short:
        rasg(tr, F_CH, rec + 0.15, 0.8)
        power(tr, 41, rec + 0.15, aft - rec - 0.25, 0.8)
    rasg(tr, E_CH, aft, 1.3)
    power(tr, 40, aft, tail * 0.8, 1.1)
    for j, nn in enumerate((64, 68, 71, 76)):
        tr.add(inst("choir_a", nn, tail * 0.9), aft, 0.22, (j - 1.5) * 0.4)
    tr.add(drum("kick"), aft, 1.0)
    tr.add(drum("crash"), aft, 0.8)
    shout(tr, aft + 0.02, 0.9)
    y = ps.reverb(tr.buf, rt60=1.0, wet=0.16)
    n_end = int((aft + tail) * SR)
    y = y[:, :n_end]
    fade = int(0.4 * SR)
    y[:, -fade:] *= np.linspace(1, 0, fade)
    for at in (cl, aft):   # 강타 직전 '숨' (43-20)
        y = ps.breath(y, at)
    return master(y, -2.0, 1.25 if short else 1.4), dict(m)   # 평균 음량을 L10 전설의 노래와 같게


def compose_loop() -> np.ndarray:
    """카드 대기: 나일론 기타가 E장조를 천천히 뜯음 + 드문 손뼉, 이음매 없이 반복."""
    L = TL["loop_len"]
    tr = ps.Track(L)
    for i in range(8):
        tr.add(inst("nylon", E_CH[(i * 2) % 6] + 12 * (i % 2), 1.0), i * L / 8, 0.12, 0.3 * (-1) ** i)
    for i in range(2):
        tr.add(drum("palma", 0.4), 0.25 + i * L / 2, 0.6)
    y = ps.reverb(tr.buf, rt60=1.2, wet=0.3)
    n = int(L * SR)
    out = y[:, :n].copy()
    tl_ = y[:, n:n * 2]
    out[:, : tl_.shape[1]] += tl_
    out = 0.5 * (out + np.roll(out, n // 2, axis=1))
    return master(out, -12.0, 1.7)


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
