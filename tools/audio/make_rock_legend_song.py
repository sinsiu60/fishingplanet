"""전설의 노래 락 버전 (ELECTRO.md 3장, DESIGN.md 43-14): 은빛 농어 '일렉트로' 포획 연출 전용.

기존 전설의 노래(make_legend_song.py)와 같은 길이 · 같은 싱크 마커(data/legend_catch_timeline.json) — 포획 연출 VFX 는 그대로 맞는다.
악기는 전투 곡 L03-ROCK 과 같은 합성(src/audio/boss_rock.py): 일렉 기타(파워 코드 · 찢어지는 리드) · 베이스 기타 · 드럼.
E단조로 시작 → E장조로 마무리 (파워 코드엔 3음이 없으니 리드 기타가 G#(장3도)을 길게 울려 '장조'를 알림).

  hit 0초       전투 곡 마지막 코드 그대로: E 파워 코드 + 크래시 + 킥 + 베이스 (기존 '쾅' 자리)
  rise 0.3초    탐 연타 상승 (낮은 탐 → 높은 탐, 점점 빠르고 세게 — 기존 팀파니 롤 자리)
  scales 0.8초  리드 기타가 위로 미끄러지며 상승 + 리듬 기타 16분 뮤트 C → D (♭VI → ♭VII, 기존 금관 상승 자리)
  climax 1.4초  전체 밴드 강타 E + 크래시 + 리드 기타 큰 벤딩 (기존 절정 화음 자리)
  card 1.9초    리드 기타 주인의 동기 E → B → A (4분 · 4분 · 2분)
  record 2.6초  E장조: 파워 코드 + 리드 G# 길게 (떨림)
  afterglow     마지막 E 강타 → 길게 울리고 피드백이 천천히 사라짐
  지지직        전기 소리(boss_rock.g_zap): 쾅·낙뢰(절정, 0.12·0.26초 다시 침 — 연출과 같은 시각)·동기 음마다·마지막, 연출 내내 작게 지글거림
  짧은 버전은 같은 순서를 짧은 마커로 (쾅 → 절정 → 동기 → 마무리), 대기(loop)는 조용히 울리는 E 화음 + 피드백.

출력: assets/music_generated/legend_catch_{full,short,loop}_L03-ROCK.ogg (+ legend_catch_markers.json 에 추가)
      tools/audio/reference/legend_catch/L03-ROCK_full.wav · L03-ROCK_short.wav
사용: python tools/audio/make_rock_legend_song.py
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
import make_phantom_song as ps  # noqa: E402  (Track · 잔향 · 마무리 · 통계 재사용)
from src.audio import boss_rock as R  # noqa: E402
from src.audio.boss_synth import _t, d_crash, d_kick, d_snare2, d_tom, hz  # noqa: E402

SR = ps.SR
ROOT = ps.ROOT
TL = json.load(open(os.path.join(ROOT, "data", "legend_catch_timeline.json"), encoding="utf-8"))
REF = os.path.join(ROOT, "tools", "audio", "reference", "legend_catch")
SID = "L03-ROCK"
E2 = 40                     # 전투 곡 리듬 기타 으뜸음 (E2)
RNG = np.random.default_rng(168)


def n_of(sec: float) -> int:
    return max(1, int(sec * SR))


def power(m: float, dur: float, take: int = 0) -> np.ndarray:
    return R.g_power(hz(m), n_of(dur), RNG, take)


def mute(m: float, dur: float = 0.09, take: int = 0) -> np.ndarray:
    return R.g_mute(hz(m), n_of(dur), RNG, take)


def bass(m: float, dur: float) -> np.ndarray:
    return R.g_bass(hz(m), n_of(dur), RNG)


def lead(m: float, dur: float, big_bend: bool = False) -> np.ndarray:
    """리드 기타 한 음 (big_bend = 온음 반 아래에서 크게 끌어올림)."""
    if not big_bend:
        return R.g_lead(hz(m), n_of(dur), RNG, dur=dur, q=0.36)
    n = n_of(dur)
    t = _t(n)
    semi = -3.0 * np.clip(1 - t / 0.22, 0, 1) ** 2 + 0.45 * np.sin(2 * np.pi * 5.8 * np.maximum(0, t - 0.32)) * np.clip((t - 0.32) / 0.2, 0, 1)
    return _lead_curve(hz(m) * 2 ** (semi / 12), n)


def glide(m0: float, m1: float, dur: float) -> np.ndarray:
    """위로 미끄러지는 리드 (16분 트레몰로 피킹 느낌의 세기 떨림)."""
    n = n_of(dur)
    t = _t(n)
    f = hz(m0) * 2 ** ((m1 - m0) * (t / t[-1]) ** 1.4 / 12)
    y = _lead_curve(f, n)
    pick = 0.7 + 0.3 * np.abs(np.sin(np.pi * t / (60 / 168 / 4)))
    return y * pick


def _lead_curve(f_t: np.ndarray, n: int) -> np.ndarray:
    """boss_rock.g_lead 과 같은 소리 (두 줄 맥놀이 + 옥타브 줄 → 2단 찌그러짐), 음높이 곡선만 직접."""
    x = R._osc(f_t, 0.5, top=9000) + 0.8 * R._osc(f_t * 1.0045, 0.6, top=9000) + 0.5 * R._osc(f_t * 0.5, 0.8, top=9000)
    x += R._pick(n, RNG, 4000, 0.35)
    y = np.tanh(1.8 * R.amp(x, 22.0, tight=150))
    y = R._bw_filter(y, "lp", 6500)
    return y / (float(np.abs(y).max()) or 1.0) * R._env(n, 0.003, 0.25, 0.05)


def feedback(m: float, dur: float, swell: bool) -> np.ndarray:
    return R.g_feedback(hz(m), n_of(dur), RNG, swell=swell)


def zap(dur: float, mode: str = "decay") -> np.ndarray:
    """전기 '지지직' (boss_rock.g_zap)."""
    return R.g_zap(1000.0, n_of(dur), RNG, mode=mode)


def kit(name: str, vel: float = 1.0, f: float = 150.0) -> np.ndarray:
    if name == "kick":
        return d_kick(n_of(0.45), vel, RNG)
    if name == "snare":
        return d_snare2(n_of(0.4), vel, RNG)
    if name == "crash":
        return d_crash(n_of(2.6), vel, RNG)
    return d_tom(n_of(0.6), vel, RNG, f=f)


def band_hit(tr, at: float, chord_m: float, ring: float, g: float = 1.0) -> None:
    """밴드 강타: 파워 코드 좌우 2겹 + 베이스 + 킥 + 크래시."""
    tr.add(power(chord_m, ring, 0), at, 0.5 * g, -0.7)
    tr.add(power(chord_m, ring, 1), at, 0.48 * g, 0.7)
    tr.add(bass(chord_m - 12, ring), at, 0.5 * g)
    tr.add(kit("kick"), at, 0.55 * g)
    tr.add(kit("crash"), at, 0.32 * g, 0.25)


def master(buf: np.ndarray, peak_db: float, drive: float) -> np.ndarray:
    """make_phantom_song.master 와 같음 (중음 보강 + 부드러운 리미터), drive 만 조절 — 기타는 피크가 커서 더 눌러야 같은 크기."""
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
    # 1) hit: 전투 곡 마지막 코드 그대로 (E 파워 코드 + 크래시 + 킥)
    band_hit(tr, hit, E2, rise + 0.25)
    tr.add(zap(0.6), hit, 0.42, -0.3)                                 # 지지직!
    tr.add(zap(aft - rise + 0.3, "flat"), rise, 0.08, 0.35)            # 연출 내내 작게 지글거림 (전기 줄기)
    # 2) rise: 탐 연타 상승 (점점 빠르고 세게) + 킥 8분
    toms = (95.0, 125.0, 160.0, 200.0)
    k, i = rise, 0
    while k < cl - 0.02:
        u = (k - rise) / max(1e-3, cl - rise)
        tr.add(kit("tom", 1.0, toms[min(3, int(u * 4))]), k, 0.25 + 0.3 * u, 0.4 - 0.25 * min(3, int(u * 4)))
        k += 0.11 - 0.06 * u
        i += 1
    k = rise
    while k < cl - 0.02:
        tr.add(kit("kick", 0.8), k, 0.3, 0.0)
        k += 60 / 168 / 2
    # 3) scales: 리드 기타가 위로 미끄러짐 + 리듬 기타 16분 뮤트 C → D (♭VI → ♭VII → 절정의 I)
    tr.add(glide(64, 86, cl - sc + 0.04), sc, 0.42, 0.15)
    step = 60 / 168 / 4
    k, i = sc, 0
    while k < cl - 0.01:
        root = E2 + 8 if k < (sc + cl) / 2 else E2 + 10   # C2 → D2 (E2 기준 +8 · +10)
        g = 0.22 + 0.2 * (k - sc) / max(1e-3, cl - sc)
        tr.add(mute(root, step * 0.85, 0), k, g, -0.7)
        tr.add(mute(root, step * 0.85, 1), k, g, 0.7)
        if i % 2 == 0:
            tr.add(bass(root - 12, step * 1.7), k, 0.3)
        if k > cl - 4 * step:
            tr.add(kit("snare", 0.9), k, 0.35, 0.0)
        k += step
        i += 1
    # 4) climax: 전체 밴드 강타 + 리드 큰 벤딩
    hold = card - cl + 0.15
    band_hit(tr, cl, E2, hold + 0.2, 1.15)
    tr.add(zap(0.4, "swell"), cl - 0.4, 0.25, 0.2)                    # 낙뢰 직전 차오름
    tr.add(zap(0.9), cl, 0.55, -0.2)                                  # 낙뢰: 크게 지지직
    tr.add(zap(0.35), cl + 0.12, 0.3, 0.3)                            # 다시 침 (연출과 같은 0.12 · 0.26초)
    tr.add(zap(0.3), cl + 0.26, 0.22, -0.35)
    tr.add(lead(88, hold, big_bend=True), cl, 0.5, 0.1)          # E6 로 크게 끌어올림
    # 5) card: 주인의 동기 E → B → A (4분 · 4분 · 2분) — 리드 기타 + 옥타브 아래 겹
    q = (rec - card) / 2
    st = card
    for j, (nn, d) in enumerate(zip((76, 83, 81), (q, q, 2 * q + 0.15))):
        tr.add(lead(nn, d), st, 0.5, 0.1)
        tr.add(zap(0.18), st, 0.18, (-0.4, 0.4, 0.0)[j])                 # 동기 음마다 짧게 튐
        tr.add(lead(nn - 12, d), st, 0.28, -0.25)
        if j < 2:
            tr.add(kit("kick"), st, 0.4)
            tr.add(mute(E2, 0.12, 0), st, 0.3, -0.7)
            tr.add(mute(E2, 0.12, 1), st, 0.3, 0.7)
        st += d
    tr.add(kit("crash"), card, 0.22, -0.3)
    # 6) record: E장조 — 파워 코드 + 리드 G#(장3도) 길게
    ring = aft - rec + 0.1
    band_hit(tr, rec, E2, ring, 0.9)
    tr.add(lead(80, ring), rec, 0.38, 0.15)                      # G#5 — 장조
    if not short:   # 마지막 앞 탐 필인
        for j in range(4):
            tr.add(kit("tom", 1.0, toms[3 - j]), aft - (4 - j) * step, 0.35, 0.4 - 0.27 * j)
    # 7) afterglow: 마지막 E 강타 → 길게 울리고 피드백이 천천히 사라짐
    band_hit(tr, aft, E2, tail, 1.15)
    tr.add(lead(80, tail * 0.8), aft, 0.3, 0.15)
    tr.add(lead(88, tail * 0.85), aft, 0.32, -0.1)
    fb = feedback(88 + 12, tail, False)
    tr.add(fb, aft + 0.25, 0.22, 0.2)
    tr.add(zap(tail * 0.9), aft, 0.32, -0.25)                          # 마지막 지지직 → 피드백과 함께 사라짐
    y = ps.reverb(tr.buf, rt60=0.8, wet=0.14)
    n_end = int((aft + tail) * SR)
    y = y[:, :n_end]
    fade = int(0.35 * SR)
    y[:, -fade:] *= np.linspace(1, 0, fade)
    return master(y, -2.0, 1.25 if short else 1.9), dict(m)   # 평균 음량을 오케스트라 전설의 노래(L03)와 같게


def compose_loop() -> np.ndarray:
    """카드 대기: 조용히 울리는 E (파워 코드 여운 + 리드 G# + 아주 작은 피드백), 이음매 없이 반복."""
    L = TL["loop_len"]
    tr = ps.Track(L)
    tr.add(power(E2 + 12, L + 2.0, 0), 0.0, 0.35, -0.6)
    tr.add(power(E2 + 12, L + 2.0, 1), 0.0, 0.33, 0.6)
    tr.add(lead(80, L + 1.0), 0.0, 0.2, 0.1)
    tr.add(feedback(100, L + 2.0, True), 0.0, 0.1, 0.2)
    y = ps.reverb(tr.buf, rt60=0.8, wet=0.2)
    n = int(L * SR)
    out = y[:, :n].copy()
    tl_ = y[:, n:n * 2]
    out[:, : tl_.shape[1]] += tl_
    out = 0.5 * (out + np.roll(out, n // 2, axis=1))
    return ps.master(out, -12.0)


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
        print(f"{name:<34} {ln:5.2f}s  최대 {pk:6.1f}dBFS  평균 {rms:6.1f}dBFS", flush=True)
    with open(mpath, "w", encoding="utf-8") as fp:
        json.dump(markers, fp, ensure_ascii=False, indent=1)
