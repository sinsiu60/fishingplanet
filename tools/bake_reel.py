"""릴 소리 미리 굽기 (DESIGN.md 32-16 Z2): tools/audio/reel_synth.py → assets/sfx_generated/reel/

  감기 루프  reel_<티어>_s<속도 0~5>_l<부하 0~2>   (속도 1.0~3.5회/초 × 부하 0/0.5/0.9 × 나무·보통·수정 = 54)
  시작·멈춤  reel_<티어>_start (가속 0.3초) · reel_<티어>_stop ('딸깍')
  드랙 풀림  drag_<0~3>   (느림 / 보통 / 빠름 / 질주 루프)
  공간 버전  위 모두 + '~out' '~cave' '~deep' (N5 공간 프리셋, 낚시터마다 그 공간 것만 읽음)
  성공 지잉  zing_<small|mid|big|double>_<티어>_<연속 0~2>   (Z3, 36개 — 손 근처 소리라 공간 버전 없음)

  python tools/bake_reel.py --reference   지잉 샘플 몇 개를 tools/audio/reference/zing/*.wav 로 (들어보기용)

  python tools/bake_reel.py            바뀐 것만 (manifest 해시)
  python tools/bake_reel.py --all      전부
  python tools/bake_reel.py --check    확인만 (CI — scipy 필요 없음)
굽기에는 numpy + scipy 가 필요하다 (pip install scipy). 소리마다 난수 시드를 고정해 같은 결과가 나온다.
"""
import hashlib
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "audio"))  # reel_synth
os.chdir(ROOT)

import bake_sfx  # noqa: E402

OUT = os.path.join(ROOT, "assets", "sfx_generated", "reel")
SYNTH = os.path.join(ROOT, "tools", "audio", "reel_synth.py")
SPEEDS = (1.0, 1.5, 2.0, 2.5, 3.0, 3.5)    # reel_synth.LOOP_SPEEDS 와 같게
LOADS = (0.0, 0.5, 0.9)
TIERS = ("wood", "mid", "crystal")
DRAGS = 4
STOP_GAIN = 0.55   # 멈춤 딸깍은 루프보다 작게


def recipes() -> dict:
    from src.core.config import load_json
    spaces = {k: v for k, v in load_json("audio_config.json")["space"]["presets"].items() if v and "use" not in v}
    base = {}
    for tier in TIERS:
        for i, rps in enumerate(SPEEDS):
            for j, load in enumerate(LOADS):
                base[f"reel_{tier}_s{i}_l{j}"] = {"kind": "loop", "rps": rps, "load": load, "tier": tier}
        base[f"reel_{tier}_start"] = {"kind": "start", "tier": tier}
        base[f"reel_{tier}_stop"] = {"kind": "stop", "tier": tier}
    for k in range(DRAGS):
        base[f"drag_{k}"] = {"kind": "drag", "k": k}
    out = dict(base)
    for g in ("small", "mid", "big", "double"):
        for tier in TIERS:
            for st in range(3):
                out[f"zing_{g}_{tier}_{st}"] = {"kind": "zing", "grade": g, "tier": tier, "streak": st}
    for name, rec in base.items():
        for sp, cfg in spaces.items():
            out[f"{name}~{sp}"] = dict(rec, space=cfg)
    return out


def reel_hash(name: str, rec: dict) -> str:
    src = b""
    for p in (SYNTH, __file__, os.path.join(ROOT, "src", "audio", "synth.py")):
        src += open(p, "rb").read().replace(b"\r\n", b"\n")
    return hashlib.sha1(src + json.dumps(rec, sort_keys=True).encode()).hexdigest()[:16]


_ref: dict = {}


def render(rec: dict, seed: int = 1):
    import numpy as np
    import reel_synth as rs
    from src.audio import synth

    def seeded(s):
        rs.RNG = np.random.default_rng(s)

    def pre(x):
        return rs.room(rs.lp(rs.hp(x, 60), 8500))

    def ref(kind):
        """기준 배율. 드랙: 가장 빠른 루프 최대 = −1dBFS. 릴: 보통 티어 2회/초 빈 릴 최대 = −1dBFS 를 기준으로,
        다른 티어는 같은 루프의 평균 크기(RMS)가 보통 티어와 같게 (티어는 음색만 다르게)."""
        if kind not in _ref:
            seeded(12345)
            if kind == "drag":
                _ref[kind] = float(np.max(np.abs(rs.drag_loop_raw(rs.DRAG_RATES[-1], pre))))
            else:
                x = rs.reel_loop_raw(2.0, 0.0, kind, pre)
                rms = float(np.sqrt(np.mean(x ** 2)))
                if kind == "mid":
                    _ref[kind] = (float(np.max(np.abs(x))), rms)
                else:
                    peak_mid, rms_mid = ref("mid")
                    _ref[kind] = (peak_mid * rms / rms_mid, rms)
        return _ref[kind]

    def fin(x, r):  # finish_fixed 의 포화·배율만 (필터·잔향은 pre 에서)
        return np.tanh(x / r * 1.3) * 0.89 / np.tanh(1.3)

    seeded(seed)
    k = rec["kind"]
    if k == "loop":
        x, loop = fin(rs.reel_loop_raw(rec["rps"], rec["load"], rec["tier"], pre), ref(rec["tier"])[0]), True
    elif k == "start":
        x, loop = fin(pre(rs.reel_start_raw(rec["tier"])), ref(rec["tier"])[0]), False
    elif k == "stop":
        x, loop = fin(pre(rs.stop_click_sound(rec["tier"])), ref(rec["tier"])[0]) * STOP_GAIN, False
    elif k == "zing":
        x, loop = rs.reel_zing(rec["grade"], rec["tier"], rec["streak"])[0], False
    else:
        x, loop = fin(rs.drag_loop_raw(rs.DRAG_RATES[rec["k"]], pre), ref("drag")), True
    st = np.stack([x, x], axis=1)
    if rec.get("space"):
        n0 = len(st)
        sp = dict(rec["space"])
        if loop and sp.get("lowpass"):
            # 반복음은 순환(끝 = 처음)으로 저역 통과 → 이음매가 그대로 맞물림
            f = np.fft.rfftfreq(n0, 1 / 44100)
            h = 1 / np.sqrt(1 + (f / sp.pop("lowpass")) ** 4)
            st = np.fft.irfft(np.fft.rfft(st, axis=0) * h[:, None], n0, axis=0)
        st = synth.space_fx(st, sp, np.random.default_rng(seed))
        if loop and len(st) > n0:  # 반복음: 잔향 꼬리를 앞머리에 겹쳐 길이 그대로
            tail, st = st[n0:], st[:n0].copy()
            while len(tail):
                m = min(len(tail), n0)
                st[:m] += tail[:m]
                tail = tail[m:]
        st *= min(1.0, 0.95 / max(1e-9, float(np.max(np.abs(st)))))
    if not loop:
        m = min(len(st), int(0.004 * 44100))
        st[-m:] *= np.linspace(1, 0, m)[:, None]
    return np.clip(st, -1, 1).astype(np.float32)


def reference() -> None:
    """지잉 샘플을 wav 로 (게임에 넣기 전에 소리만 들어보기)."""
    from src.audio import synth
    d = os.path.join(ROOT, "tools", "audio", "reference", "zing")
    os.makedirs(d, exist_ok=True)
    rec = recipes()
    picks = [f"zing_{g}_mid_0" for g in ("small", "mid", "big", "double")] + \
            ["zing_big_wood_0", "zing_big_crystal_0", "zing_small_mid_2", "zing_big_mid_2"]
    for n in picks:
        p = os.path.join(d, n + ".wav")
        synth.write_wav(p, render(rec[n], seed=int(hashlib.sha1(n.encode()).hexdigest()[:6], 16)))
        print(os.path.relpath(p, ROOT))


def main(argv) -> int:
    if "--reference" in argv:
        reference()
        return 0
    return bake_sfx.main(argv, rec=recipes(), out_dir=OUT, quality="3", hash_fn=reel_hash, render=render)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
