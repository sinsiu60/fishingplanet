"""실내 버전 미리 굽기 (AUDIO_ZONES.md 7번, DESIGN.md 39) → assets/sfx_indoor/

  - 바깥 환경음(data/audio/zones.json names) 마다 '<이름>~indoor': 종류별 음량(dB)만큼 작게 + 부드러운 고음 깎기(2차, 그 Hz 위)
    + 아주 짧은 방 울림(0.15초). 반복음은 이음매가 없게 원형(circular)으로 처리하고 길이를 바깥 버전과 똑같이 둔다
    → 게임은 바깥·실내 버전을 같은 순간에 같이 돌리고 음량 비율만 바꾼다 (끊김·처음부터 재생 없음).
  - mus_room_radio: 샤르미온 마을 음악을 라디오 음질로 (400~3000Hz만 + 아주 작은 지지직). 재생 음량 -8dB 은 zones.json.
  - mus_room_home: 샤르미온 테마를 느리게(0.8배) · 부드럽게 (집 — 한 곡 뒤 1~2분 정적)
  - mus_room_crystal: 엘드라시온 테마의 화음만 길게 남긴 낮은 패드 (공방)
원본은 게임과 같은 순서로 찾는다: assets/sfx/<이름> (외부 음원) → assets/sfx_generated/<이름>. 음악은 assets/music → music_generated.
assets/sfx/indoor/<이름>.ogg 가 있으면 게임은 그 파일을 우선 쓴다 (여기서는 굽지 않음).

  python tools/bake_indoor.py           바뀐 것만 (assets/sfx_indoor/manifest.json 해시)
  python tools/bake_indoor.py --all     전부
  python tools/bake_indoor.py --check   확인만 (CI)
"""
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

OUT = os.path.join(ROOT, "assets", "sfx_indoor")
RATE = 44100
VERSION = "2"   # 처리 방식이 바뀌면 올린다 (전부 다시)


def zones() -> dict:
    return json.load(open(os.path.join(ROOT, "data", "audio", "zones.json"), encoding="utf-8"))


def category(name: str, names: dict) -> str | None:
    for k, cat in names.items():
        if name == k or (k.endswith("#") and name.startswith(k[:-1]) and name[len(k) - 1:].lstrip("#").isdigit()):
            return cat
    return None


def source_of(name: str, dirs=("sfx", "sfx_generated")) -> str | None:
    for d in dirs:
        for ext in (".ogg", ".wav"):
            p = os.path.join(ROOT, "assets", d, name.replace("#", "__") + ext)
            if os.path.exists(p):
                return p
    return None


def load(path: str) -> np.ndarray:
    import pygame
    if not pygame.mixer.get_init():
        pygame.mixer.init(RATE, -16, 2, 512)
    a = pygame.sndarray.array(pygame.mixer.Sound(path)).astype(np.float64) / 32768.0
    return a if a.ndim == 2 else np.stack([a, a], axis=1)


def save(path: str, st: np.ndarray, quality: str = "4") -> None:
    from src.audio import synth
    os.makedirs(os.path.dirname(path), exist_ok=True)
    ff = shutil.which("ffmpeg")
    if not ff:
        synth.write_wav(path[:-4] + ".wav", st)
        return
    with tempfile.TemporaryDirectory() as tmp:
        w = os.path.join(tmp, "x.wav")
        synth.write_wav(w, st)
        subprocess.run([ff, "-loglevel", "error", "-y", "-i", w, "-c:a", "libvorbis", "-q:a", quality,
                        "-fflags", "+bitexact", "-flags:a", "+bitexact", path], check=True)


# ── 처리 (FFT, 반복음이면 원형) ──
def _filter(st: np.ndarray, h_of_f, circular: bool) -> np.ndarray:
    n = len(st)
    L = n if circular else 1 << int(np.ceil(np.log2(n + 1)))
    f = np.fft.rfftfreq(L, 1 / RATE)
    h = h_of_f(f)
    return np.fft.irfft(np.fft.rfft(st, L, axis=0) * h[:, None], L, axis=0)[:n]


def lowpass(st, hz, circular):
    return _filter(st, lambda f: 1 / np.sqrt(1 + (f / max(20.0, hz)) ** 4), circular)


def bandpass(st, lo, hi, circular):
    return _filter(st, lambda f: (1 / np.sqrt(1 + (f / hi) ** 4)) * ((f / lo) ** 2 / np.sqrt(1 + (f / lo) ** 4)), circular)


def room(st: np.ndarray, mix: float, time: float, circular: bool, seed: int = 7) -> np.ndarray:
    """짧은 방 울림: 지수로 사라지는 노이즈 임펄스와 합성곱 (반복음은 원형 — 꼬리가 앞머리로)."""
    rng = np.random.default_rng(seed)
    n_ir = int(RATE * time)
    t = np.arange(n_ir) / RATE
    n = len(st)
    out = st * (1 - mix * 0.5)
    for ch in range(2):
        ir = rng.uniform(-1, 1, n_ir) * np.exp(-t / (time / 5))
        ir[: int(RATE * 0.004)] = 0
        ir /= np.sqrt(np.sum(ir ** 2)) + 1e-9
        L = n if circular else n + n_ir
        L = max(L, n_ir)
        wet = np.fft.irfft(np.fft.rfft(st[:, ch], L) * np.fft.rfft(ir, L), L)
        if circular:
            out[:, ch] += wet[:n] * mix
        else:
            out[:, ch] += wet[:n] * mix   # 한 번 소리: 꼬리 0.15초는 원래 길이 안에서 잘라도 티 안 남
    return out


def rms(st: np.ndarray) -> float:
    return float(np.sqrt(np.mean(st ** 2)) + 1e-12)


def indoor(st: np.ndarray, db: float, hz: float, rv, circular: bool) -> np.ndarray:
    """바깥 소리 → 실내 버전: 벽처럼 고음을 깎고(그만큼 자연히 작아짐) + 짧은 방 울림 + 음량 db.
    고음이 많은 소리(새·빗소리)는 깎이는 만큼 더 작아진다 — 벽 너머에선 실제로 그렇다 (저음 위주인 천둥은 거의 db 만큼)."""
    x = lowpass(st, hz, circular)
    x = room(x, rv[0], rv[1], circular)
    x *= 10 ** (db / 20)
    peak = np.max(np.abs(x))
    if peak > 0.98:
        x *= 0.98 / peak
    return x


def radio(st: np.ndarray) -> np.ndarray:
    """라디오 음질: 400~3000Hz 만, 살짝 찌그러짐, 아주 작은 지지직 (반복 이음매 없게 원형)."""
    rng = np.random.default_rng(11)
    x = bandpass(st, 400, 3000, True)
    x = bandpass(x, 400, 3000, True)            # 두 번 → 더 좁고 가파르게
    x = np.tanh(x * 2.2) / np.tanh(2.2)
    mono = x.mean(axis=1, keepdims=True)
    x = 0.7 * mono + 0.3 * x                     # 거의 모노
    n = len(x)
    hiss = bandpass(rng.normal(0, 1, (n, 2)), 1500, 5000, True)
    hiss *= rms(x) * 10 ** (-30 / 20) / rms(hiss)
    clicks = np.zeros((n, 2))
    for i in rng.integers(0, n, n // (RATE // 3)):   # 초당 약 3개 '지직'
        k = int(rng.integers(20, 120))
        clicks[i:i + k] += rng.normal(0, 1, (min(k, n - i), 1)) * np.exp(-np.arange(min(k, n - i)) / 25)[:, None]
    clicks *= rms(x) * 0.22 / (np.max(np.abs(clicks)) + 1e-9)
    out = x + hiss + clicks
    return out * (0.9 / max(0.9, np.max(np.abs(out))))


def resample(st: np.ndarray, ratio: float) -> np.ndarray:
    """ratio < 1: 느리게(길어짐, 낮아짐)."""
    n = int(len(st) / ratio)
    idx = np.linspace(0, len(st) - 1, n)
    return np.stack([np.interp(idx, np.arange(len(st)), st[:, c]) for c in range(2)], axis=1)


def home_song(st: np.ndarray) -> np.ndarray:
    """집: 샤르미온 테마를 0.8배로 느리게 · 부드럽게 (기타·피아노풍), 앞뒤 페이드 — 한 번 울리고 쉼."""
    x = resample(st, 0.8)
    x = lowpass(x, 2400, False)
    x = room(x, 0.3, 0.9, False, seed=3)
    n = len(x)
    fade = np.ones(n)
    a, b = int(RATE * 2.5), int(RATE * 5.0)
    fade[:a] = np.linspace(0, 1, a)
    fade[-b:] = np.linspace(1, 0, b)
    x *= fade[:, None]
    return x * (0.8 / np.max(np.abs(x)))


def crystal_pad(st: np.ndarray) -> np.ndarray:
    """공방: 엘드라시온 테마의 화음만 길게 — 한 옥타브 낮게 늘이고, 긴 울림으로 박을 지워 낮은 패드로 (반복 이음매 없음)."""
    x = resample(st, 0.5)
    x = lowpass(x, 1400, True)
    for seed, (mix, time) in enumerate(((0.9, 2.5), (0.8, 3.5))):
        x = room(x, mix, time, True, seed=seed + 20)
    n = len(x)
    t = np.arange(n) / RATE
    x *= (0.8 + 0.2 * np.sin(2 * np.pi * t / (n / RATE)))[:, None]   # 천천히 숨쉬듯 (한 바퀴 = 곡 길이 → 이음매 없음)
    return x * (0.7 / np.max(np.abs(x)))


def jobs() -> dict:
    """이름 → (만들기 함수, 원본 경로, 해시 재료)."""
    z = zones()
    from src.audio import synth
    rec = synth.recipes()
    out = {}
    rv = z["reverb"]
    for name, r in rec.items():
        cat = category(name, z["names"])
        if not cat:
            continue
        db, hz = z["occlusion"][cat]
        src = source_of(name)
        if src is None:
            continue
        loop = bool(r.get("loop"))
        out[f"{name}~indoor"] = (lambda st, db=db, hz=hz, loop=loop: indoor(st, db, hz, rv, loop), src, [db, hz, rv, loop])
    th_sh = source_of("mus_theme_sharmion", ("music", "music_generated"))
    th_el = source_of("mus_theme_eldrasion", ("music", "music_generated"))
    if th_sh:
        out["mus_room_radio"] = (radio, th_sh, ["radio"])
        out["mus_room_home"] = (home_song, th_sh, ["home"])
    if th_el:
        out["mus_room_crystal"] = (crystal_pad, th_el, ["crystal"])
    return out


def job_hash(src: str, extra) -> str:
    h = hashlib.sha1(open(src, "rb").read())
    h.update(open(__file__, "rb").read().replace(b"\r\n", b"\n"))
    h.update(json.dumps(extra, sort_keys=True).encode() + VERSION.encode())
    return h.hexdigest()[:16]


def main(argv: list[str]) -> int:
    os.makedirs(OUT, exist_ok=True)
    mp = os.path.join(OUT, "manifest.json")
    man = json.load(open(mp, encoding="utf-8")) if os.path.exists(mp) else {}
    js = jobs()
    if "--check" in argv:
        stale = [n for n, (_, src, ex) in js.items() if man.get(n) != job_hash(src, ex)
                 or not any(os.path.exists(os.path.join(OUT, n.replace("#", "__") + e)) for e in (".ogg", ".wav"))]
        print(f"assets/sfx_indoor: {len(js) - len(stale)}/{len(js)} 최신" + (f" — 다시 구울 것: {stale}" if stale else ""))
        return 1 if stale else 0
    force = "--all" in argv
    done = 0
    for name, (fn, src, ex) in js.items():
        h = job_hash(src, ex)
        dst = os.path.join(OUT, name.replace("#", "__") + ".ogg")
        if not force and man.get(name) == h and os.path.exists(dst):
            continue
        st = fn(load(src))
        save(dst, st, "3" if name.startswith("mus_") else "4")
        man[name] = h
        done += 1
        print(f"굽기: {os.path.relpath(dst, ROOT)} ({os.path.getsize(dst) // 1024}KB)")
    for gone in [k for k in man if k not in js]:
        p = os.path.join(OUT, gone.replace("#", "__") + ".ogg")
        if os.path.exists(p):
            os.remove(p)
        man.pop(gone)
    json.dump(man, open(mp, "w", encoding="utf-8"), ensure_ascii=False, indent=1, sort_keys=True)
    print(f"완료: {done}개 새로 구움, 전체 {len(js)}개")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
