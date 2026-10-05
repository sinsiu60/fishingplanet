"""전설의 노래 국악 버전 (ILSEOM.md 4장, DESIGN.md 43-15): 청새치 '일섬' 포획 연출 전용.

기존 전설의 노래와 같은 길이 · 같은 싱크 마커(data/legend_catch_timeline.json) — 포획 연출 VFX 는 그대로 맞는다.
악기는 전투 곡 L04-MUHYEOP 과 같은 합성(src/audio/boss_muhyeop.py). D 계면조로 시작 → 마무리만 평조(밝은 다섯 음 D·E·F#·A·B).

  hit 0초       전투 곡에서 끊김 없이 대고 + 징 강타 (+ 거문고 낮은 D)
  rise 0.3초    장구 몰아치기 상승 (점점 빠르고 세게, 박마다 쿵)
  scales 0.8초  대금이 위로 치솟는 선율 + 가야금 16분 상승
  climax 1.4초  전체 합주 + 징 + 태평소 긴 음 + 칼 부딪침 '챙'
  card 1.9초    대금이 주인의 동기 D → A → G (4분 · 4분 · 2분) 크게
  record 2.6초  칼을 칼집에 넣는 '착' (기존 인장 '쿵' 자리)
  afterglow     가야금이 평조로 밝게 마무리, 징 여운이 천천히 사라짐
  짧은 버전은 같은 순서를 짧은 마커로 (강타 → 절정 → 동기 → '착'), 대기(loop)는 조용한 징 울림 + 가야금 평조 몇 음 + 바람.

출력: assets/music_generated/legend_catch_{full,short,loop}_L04-MUHYEOP.ogg (+ legend_catch_markers.json 에 추가)
      tools/audio/reference/legend_catch/L04-MUHYEOP_full.wav · L04-MUHYEOP_short.wav
사용: python tools/audio/make_muhyeop_legend_song.py
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
from src.audio import boss_muhyeop as M  # noqa: E402
from src.audio.boss_synth import hz  # noqa: E402

SR = ps.SR
ROOT = ps.ROOT
TL = json.load(open(os.path.join(ROOT, "data", "legend_catch_timeline.json"), encoding="utf-8"))
REF = os.path.join(ROOT, "tools", "audio", "reference", "legend_catch")
SID = "L04-MUHYEOP"
D4 = 62
GYE = [0, 3, 5, 7, 10]          # 계면조 (D F G A C)
PYEONG = [0, 2, 4, 7, 9]        # 평조 — 밝은 다섯 음 (D E F# A B)
RNG = np.random.default_rng(100)


def n_of(sec: float) -> int:
    return max(1, int(sec * SR))


def inst(name: str, m: float, dur: float, **k) -> np.ndarray:
    return M.INST[name](hz(m), n_of(dur + 0.15), RNG, dur=dur, q=0.35, **k)


def drum(name: str, vel: float = 1.0) -> np.ndarray:
    fn, ln = M.DRUM[name]
    return fn(n_of(ln), vel, RNG)


def scale_notes(base: int, steps, lo: int, n: int) -> list:
    out, o = [], 0
    while len(out) < n:
        for s in steps:
            m = base + 12 * o + s
            if m >= lo:
                out.append(m)
            if len(out) >= n:
                break
        o += 1
    return out


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
    # 1) hit: 대고 + 징 강타 + 거문고 낮은 D
    tr.add(drum("daego"), hit, 0.95)
    tr.add(drum("jing"), hit, 0.45, 0.1)
    tr.add(inst("geomungo", D4 - 24, 0.8), hit, 0.5, -0.15)
    # 2) rise: 장구 몰아치기 상승 (점점 빠르고 세게, 박마다 쿵)
    k, i = rise, 0
    while k < cl - 0.1:   # 절정 직전 0.1초는 비워 둠 (숨 → 강타)
        u = (k - rise) / max(1e-3, cl - rise)
        tr.add(drum("deok"), k, 0.25 + 0.4 * u, 0.25)
        if i % 4 == 0:
            tr.add(drum("kung"), k, 0.35 + 0.3 * u, -0.2)
        k += 0.1 - 0.05 * u
        i += 1
    # 3) scales: 대금이 위로 치솟음 + 가야금 16분 상승 (계면조)
    up = scale_notes(D4 + 12, GYE, D4 + 12, 7)            # D5 F5 G5 A5 C6 D6 F6
    span = cl - sc
    for j, nn in enumerate(up):
        d = min(span / len(up) * 1.05, cl - 0.12 - (sc + span * j / len(up)))   # 절정 직전에 숨을 끊어 강타가 또렷하게
        tr.add(inst("daegeum", nn, d), sc + span * j / len(up), 0.42 + 0.04 * j, 0.1)
    g_up = scale_notes(D4, GYE, D4, 12)
    for j, nn in enumerate(g_up):
        t0 = sc + (span - 0.1) * j / len(g_up)
        tr.add(inst("gayageum", nn, 0.2), t0, 0.22 + 0.02 * j, -0.3 + 0.05 * j)
    # 4) climax: 전체 합주 + 징 + 태평소 긴 음 + 칼 '챙'
    hold = card - cl + 0.2
    tr.add(drum("daego"), cl, 1.0)
    tr.add(drum("jing"), cl, 0.55, 0.1)
    tr.add(M.s_chaeng(n_of(0.6), RNG), cl, 0.55, 0.35)
    tr.add(drum("deok"), cl, 0.7, 0.25)
    tr.add(drum("kung"), cl, 0.6, -0.2)
    tr.add(inst("taepyeongso", D4 + 24, hold), cl, 0.5, 0.05)
    tr.add(inst("daegeum", D4 + 19, hold), cl, 0.3, -0.2)     # A5
    tr.add(inst("haegeum", D4 + 12, hold), cl, 0.28, 0.3)     # D5
    for j, nn in enumerate((D4 - 12, D4 - 5, D4, D4 + 7)):    # 가야금 화음 훑기
        tr.add(inst("gayageum", nn, 0.6), cl + 0.02 * j, 0.32, -0.4 + 0.25 * j)
    tr.add(inst("geomungo", D4 - 24, 1.0), cl, 0.55, -0.15)
    # 5) card: 대금이 주인의 동기 D → A → G 를 크게 (+ 가야금 받침)
    q = (rec - card) / 2
    st = card
    for j, (nn, d) in enumerate(zip((D4 + 12, D4 + 19, D4 + 17), (q, q, 2 * q - 0.06))):
        tr.add(inst("daegeum", nn, d), st, 0.6, 0.1)
        tr.add(inst("gayageum", nn - 12, 0.4), st, 0.25, -0.3)
        if j == 0:
            tr.add(drum("kung"), st, 0.4, -0.2)
        st += d
    # 6) record: 칼을 칼집에 넣는 '착'
    tr.add(M.s_chak(n_of(0.3), RNG), rec, 1.15, 0.0)
    tr.add(drum("kung"), rec, 0.35, -0.2)
    # 7) 평조로 밝게 마무리: 가야금 평조 오르는 가락 → afterglow 화음 + 징 여운이 천천히 사라짐
    bright = scale_notes(D4, PYEONG, D4, 6)                    # D4 E4 F#4 A4 B4 D5
    gap = (aft - rec - 0.15) / len(bright)
    if not short:
        for j, nn in enumerate(bright):
            tr.add(inst("gayageum", nn, 0.5, nong=j == len(bright) - 1), rec + 0.15 + gap * j, 0.3, -0.3 + 0.12 * j)
    tr.add(drum("jing"), aft, 0.42, 0.1)
    tr.add(drum("daego", 0.9), aft, 0.8)
    tr.add(drum("deok"), aft, 0.5, 0.25)
    tr.add(drum("kung"), aft, 0.5, -0.2)
    for j, nn in enumerate((D4 - 12, D4 - 5, D4, D4 + 4, D4 + 7, D4 + 12)):   # D 장화음 (평조) 훑기
        tr.add(inst("gayageum", nn, tail * 0.8, nong=j == 5), aft + 0.02 * j, 0.42, -0.4 + 0.16 * j)
    tr.add(inst("daegeum", D4 + 16, tail * 0.75), aft + 0.05, 0.32, 0.1)     # F#5 — 밝은 끝
    y = ps.reverb(tr.buf, rt60=1.0, wet=0.18)
    n_end = int((aft + tail) * SR)
    y = y[:, :n_end]
    fade = int(0.4 * SR)
    y[:, -fade:] *= np.linspace(1, 0, fade)
    for at in (cl,):   # 강타 직전 '숨' — 앞 소리에 묻히지 않고 마커에서 또렷하게 (S6)
        y = ps.breath(y, at)
    return master(y, -2.0, 1.6 if short else 1.4), dict(m)


def compose_loop() -> np.ndarray:
    """카드 대기: 조용한 징 울림 + 가야금 평조 몇 음 + 바람, 이음매 없이 반복."""
    L = TL["loop_len"]
    tr = ps.Track(L)
    tr.add(M.s_wind(n_of(L + 2.0), RNG), 0.0, 0.18, -0.2)
    tr.add(drum("jing", 0.6), 0.0, 0.25, 0.1)
    for i, nn in enumerate((D4 + 12, D4 + 9, D4 + 7, D4 + 4)):
        tr.add(inst("gayageum", nn, 1.2, nong=True), 0.4 + i * L / 4, 0.2, 0.4 * np.sin(i * 2.1))
    y = ps.reverb(tr.buf, rt60=1.0, wet=0.25)
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
