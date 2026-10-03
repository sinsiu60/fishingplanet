"""
릴 오디오 일괄 굽기: 게임에서 바로 쓰는 파일 + manifest.json 생성 (실제 릴 녹음 그레인 재배치 — REEL_AUDIO_INTEGRATE.md)
실행 (프로젝트 루트에서):
    python tools/audio/bake_reel_audio.py           굽기 (numpy + scipy 필요: pip install -r requirements-dev.txt)
    python tools/audio/bake_reel_audio.py --check   확인만 (CI — scipy 필요 없음): 재료·스크립트가 바뀌었는데 안 구웠거나 파일이 빠졌으면 실패
결과: assets/sfx_generated/reel_rec/   102개 (.wav) + manifest.json
      assets/sfx_generated/reel_rec/space/   장소 잔향 버전 '<이름>~out|cave|deep.ogg' (루프·드랙·시작·멈춤 — 지잉은 손 근처라 없음)
게임은 manifest.json 으로 파일을 찾는다 (src/audio/reel_audio.py). 결과는 저장소에 커밋 → 빌드 환경에 scipy 없어도 됨.
"""
import hashlib
import os, sys, json
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
SRC = os.path.join(HERE, "source", "reel_recording.wav")
OUT = os.path.join(ROOT, "assets", "sfx_generated", "reel_rec")
SPACE_DIR = os.path.join(OUT, "space")
HASHED = [os.path.join(HERE, n) for n in ("reel_from_recording.py", "drag_zing.py", "bake_reel_audio.py")] + \
    [SRC, os.path.join(ROOT, "src", "audio", "synth.py"), os.path.join(ROOT, "data", "audio_config.json")]
SR = 44100

SPEEDS = [1.0, 1.5, 2.0, 2.5, 3.0, 3.5]      # 핸들 회전/초
LOADS = [0.0, 0.5, 0.9]                       # 부하
TIERS = {                                     # 티어 음색
    "wood":    dict(grain_pitch=0.82, jitter=0.35, hum=1.4, lowpass=7000, shimmer=0.0, drag_pitch=0.95),
    "mid":     dict(grain_pitch=1.00, jitter=0.22, hum=1.0, lowpass=11000, shimmer=0.0, drag_pitch=1.12),
    "crystal": dict(grain_pitch=1.18, jitter=0.10, hum=0.8, lowpass=14000, shimmer=0.12, drag_pitch=1.30),
}
CLICKS_PER_REV = 55
DRAG_RATES = {"slow": 150, "normal": 300, "fast": 550, "run": 850}  # 초당 드랙 클릭
TIER_OF = {"T1": "wood", "T2": "mid", "T3": "mid", "T4": "mid", "T5": "mid",
           "T6": "crystal", "T7": "crystal", "T8": "crystal"}


def make_loop(sig_fn, n, xf):
    """n + xf 길이로 만든 뒤 끝을 앞에 겹쳐서 이음새 없는 루프"""
    s = sig_fn(n + xf)
    out = s[:n].copy()
    w = np.linspace(0, 1, xf)
    out[:xf] = s[:xf] * w + s[n:n + xf] * (1 - w)
    return out


def reel_loop(G, bed, rps, load, tier):
    c = TIERS[tier]
    revs = max(2, int(round(rps * 1.6)))           # 약 1.6초, 핸들 정수 바퀴
    n = int(revs / rps * SR)
    xf = int(0.03 * SR)
    rate = rps * CLICKS_PER_REV * (1 - 0.35 * load)

    def gen(m):
        t = np.arange(m) / SR
        rc = np.full(m, rate) * (1 + 0.03 * np.sin(2 * np.pi * rps * t))
        tm = events(rc)
        tm = tm + RNG.normal(0, 0.00025, len(tm))
        amps = np.clip(1 + c["jitter"] * RNG.standard_normal(len(tm)), 0.3, 1.9)
        amps *= 1 + 0.15 * np.sin(2 * np.pi * rps * tm)  # 핸들 한 바퀴 주기
        ratios = c["grain_pitch"] * (1 - 0.12 * load) * (1 + 0.02 * RNG.standard_normal(len(tm)))
        clicks = place(m, tm, G, amps, ratios)
        ph = 2 * np.pi * rate * 0.5 * t
        hum = f(np.sin(ph) + 0.4 * np.sin(2 * ph) + 0.2 * np.sin(3 * ph), "low", 1500)
        hum *= (0.06 + 0.08 * load) * c["hum"]
        b = np.resize(bed, m) * 0.12 * (1 + 1.5 * load)
        s = clicks + b + hum
        if c["shimmer"]:
            s += np.sin(2 * np.pi * rate * 6.03 * t) * c["shimmer"] * 0.1
        return f(s, "low", c["lowpass"] - 3500 * load)

    return make_loop(gen, n, xf)


def drag_loop(G, bed, rate, tier):
    n = int(1.2 * SR)
    xf = int(0.03 * SR)

    def gen(m):
        t = np.arange(m) / SR
        rc = np.full(m, float(rate)) * (1 + 0.04 * np.sin(2 * np.pi * 2.5 * t))
        return drag_zing.line_speed_drag(G, bed, rc, catch_click=False, grain_pitch=TIERS[tier]["drag_pitch"])[:m]

    return make_loop(gen, n, xf)


def oneshot_start(G, tier):
    c = TIERS[tier]
    n = int(0.18 * SR)
    t = np.arange(n) / SR
    rc = 2.0 * CLICKS_PER_REV * (t / t[-1]) ** 0.7 + 1
    tm = events(rc)
    s = place(n, tm, G, np.linspace(0.4, 1, len(tm)), np.full(len(tm), c["grain_pitch"]))
    return f(s, "low", c["lowpass"])


def oneshot_stop(G, tier):
    c = TIERS[tier]
    out = np.zeros(int(0.1 * SR))
    g = pitch(G[RNG.integers(len(G))], 0.8 * c["grain_pitch"]) * 1.6
    out[:len(g)] += g
    g2 = pitch(G[RNG.integers(len(G))], 1.05 * c["grain_pitch"]) * 0.7
    o = int(0.016 * SR)
    out[o:o + len(g2)] += g2
    return out


def source_hash() -> str:
    h = hashlib.sha1()
    for p in HASHED:
        h.update(open(p, "rb").read().replace(b"\r\n", b"\n"))
    return h.hexdigest()[:16]


def spaces() -> dict:
    """N5 장소 잔향 프리셋 (data/audio_config.json space.presets — 'use' 로 다른 것을 빌려 쓰는 것·빈 것 제외)."""
    cfg = json.load(open(os.path.join(ROOT, "data", "audio_config.json"), encoding="utf-8"))
    return {k: v for k, v in cfg["space"]["presets"].items() if v and "use" not in v and not k.startswith("_")}


def space_variant(y, sp, loop, seed):
    """장소 버전 (기존 방식 = 미리 구운 '~공간' 파일을 재생 때 고름). 루프는 저역 통과를 순환으로 걸고
    잔향 꼬리를 앞머리에 겹쳐 길이 그대로 → 이음매 유지."""
    sys.path.insert(0, ROOT)
    from src.audio import synth
    st = np.stack([y, y], axis=1).astype(np.float64)
    n0 = len(st)
    sp = dict(sp)
    if loop and sp.get("lowpass"):
        fr = np.fft.rfftfreq(n0, 1 / SR)
        hgain = 1 / np.sqrt(1 + (fr / sp.pop("lowpass")) ** 4)
        st = np.fft.irfft(np.fft.rfft(st, axis=0) * hgain[:, None], n0, axis=0)
    st = synth.space_fx(st, sp, np.random.default_rng(seed))
    if loop and len(st) > n0:
        tail, st = st[n0:], st[:n0].copy()
        while len(tail):
            m = min(len(tail), n0)
            st[:m] += tail[:m]
            tail = tail[m:]
    st *= min(1.0, 0.95 / max(1e-9, float(np.max(np.abs(st)))))
    if not loop:
        m = min(len(st), int(0.004 * SR))
        st[-m:] *= np.linspace(1, 0, m)[:, None]
    return np.clip(st, -1, 1)


def write_ogg(path, st):
    """공간 버전은 OGG (ffmpeg libvorbis q3, 없으면 wav)."""
    import shutil, subprocess, tempfile
    from scipy.io import wavfile
    ff = shutil.which("ffmpeg")
    pcm = (st * 32767).astype(np.int16)
    if not ff:
        wavfile.write(path[:-4] + ".wav", SR, pcm)
        return os.path.basename(path)[:-4] + ".wav"
    with tempfile.TemporaryDirectory() as td:
        tmp = os.path.join(td, "x.wav")
        wavfile.write(tmp, SR, pcm)
        subprocess.run([ff, "-loglevel", "error", "-y", "-i", tmp, "-c:a", "libvorbis", "-q:a", "3", path], check=True)
    return os.path.basename(path)


def check() -> int:
    """CI: scipy 없이. manifest 의 재료 해시가 지금 재료와 같고 적힌 파일이 다 있으면 통과."""
    mp = os.path.join(OUT, "manifest.json")
    if not os.path.exists(mp):
        print(f"{os.path.relpath(OUT, ROOT)}: manifest.json 없음 — python tools/audio/bake_reel_audio.py")
        return 1
    man = json.load(open(mp, encoding="utf-8"))
    files = [e["file"] for k in ("reel_loops", "drag_loops", "oneshots", "zing") for e in man[k]]
    files += ["space/" + v for e in man["reel_loops"] + man["drag_loops"] + man["oneshots"] for v in e.get("space", {}).values()]
    missing = [x for x in files if not os.path.exists(os.path.join(OUT, x))]
    stale = man.get("source_hash") != source_hash()
    n = sum(len(man[k]) for k in ("reel_loops", "drag_loops", "oneshots", "zing"))
    print(f"{os.path.relpath(OUT, ROOT)}: {n}개 + 공간 {len(files) - n}개" + (" 최신" if not (stale or missing) else
          (" — 재료·스크립트가 바뀜, 다시 구울 것" if stale else "") + (f" — 빠진 파일 {missing[:5]}" if missing else "")))
    return 1 if stale or missing else 0


def write(name, x, gain):
    from scipy.io import wavfile
    y = np.tanh(x * gain * 1.2) / np.tanh(1.2)
    y = np.clip(y, -1, 1) * 0.89
    wavfile.write(os.path.join(OUT, name), SR, (y * 32767).astype(np.int16))
    return y


def main():
    if "--check" in sys.argv[1:]:
        return check()
    global load, extract_grains, place, events, f, RNG, pitch, drag_zing
    from reel_from_recording import load, extract_grains, place, events, f, RNG, pitch
    import drag_zing
    if not os.path.exists(SRC):
        sys.exit(f"녹음 파일이 없습니다: {SRC}")
    os.makedirs(OUT, exist_ok=True)
    os.makedirs(SPACE_DIR, exist_ok=True)
    G, BED = extract_grains(load(SRC))
    print(f"그레인 {len(G)}개 추출")
    sps = spaces()
    man = {"sample_rate": SR, "source_hash": source_hash(), "spaces": sorted(sps), "tier_of_equipment": TIER_OF, "reel_loops": [], "drag_loops": [],
           "oneshots": [], "zing": [],
           "usage": {
               "reel_loops": "현재 감기 속도(rps)·부하(load)에 가장 가까운 루프 2~4개를 음량 비율로 섞어 반복 재생. 재생 속도 변경 금지",
               "drag_loops": "줄 풀리는 속도(clicks_per_sec)에 가까운 두 루프를 섞어 재생 = 돌진 지이잉. 속도가 곧 피치",
               "oneshots": "감기 시작 시 start, 손 뗄 때 stop",
               "zing": "패턴 성공 판정 순간 1회 재생. grade·tier·streak로 선택",
               "space": "장소 잔향 버전 (space/ 폴더, 낚시터 공간이 open 이 아니면 그 버전)"}}

    def spaced(name, y, loop):
        out = {}
        for sp, cfg in sps.items():
            seed = int(hashlib.sha1(f"{name}~{sp}".encode()).hexdigest()[:6], 16)
            out[sp] = write_ogg(os.path.join(SPACE_DIR, f"{name[:-4]}~{sp}.ogg"), space_variant(y, cfg, loop, seed))
        return out

    # 공통 음량 기준: 보통 속도 루프의 최대값
    ref = np.max(np.abs(reel_loop(G, BED, 2.0, 0.0, "mid")))
    gain = 0.75 / ref

    for tier in TIERS:
        for rps in SPEEDS:
            for ld in LOADS:
                name = f"reel_{tier}_s{rps:.1f}_l{ld:.1f}.wav"
                y = write(name, reel_loop(G, BED, rps, ld, tier), gain)
                man["reel_loops"].append({"file": name, "tier": tier, "rps": rps, "load": ld, "space": spaced(name, y, True)})
        for key, rate in DRAG_RATES.items():
            name = f"drag_{tier}_{key}.wav"
            y = write(name, drag_loop(G, BED, rate, tier), gain * 0.9)
            man["drag_loops"].append({"file": name, "tier": tier, "clicks_per_sec": rate, "space": spaced(name, y, True)})
        for kind, fn in [("start", oneshot_start), ("stop", oneshot_stop)]:
            name = f"reel_{tier}_{kind}.wav"
            y = write(name, fn(G, tier), gain)
            man["oneshots"].append({"file": name, "tier": tier, "kind": kind, "space": spaced(name, y, False)})
        for grade in ["small", "mid", "big"]:
            for streak in range(3):
                name = f"zing_{tier}_{grade}_k{streak}.wav"
                x = drag_zing.success(G, BED, grade, streak, grain_pitch=TIERS[tier]["drag_pitch"])
                write(name, x, 1.0)
                man["zing"].append({"file": name, "tier": tier, "grade": grade, "streak": streak})
        name = f"zing_{tier}_double.wav"
        write(name, drag_zing.double(G, BED), 1.0)
        man["zing"].append({"file": name, "tier": tier, "grade": "double", "streak": 0})
        print(f"{tier} 완료")

    with open(os.path.join(OUT, "manifest.json"), "w", encoding="utf-8") as fp:
        json.dump(man, fp, ensure_ascii=False, indent=2)
    total = len(man["reel_loops"]) + len(man["drag_loops"]) + len(man["oneshots"]) + len(man["zing"])
    print(f"총 {total}개 파일 + manifest.json → {OUT}")


if __name__ == "__main__":
    sys.exit(main())
