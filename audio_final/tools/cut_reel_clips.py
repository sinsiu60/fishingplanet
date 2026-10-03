"""
원본 릴 녹음을 잘라서 최소 편집만 적용 (음색 변형 없음)
편집 내용: 구간 자르기, 짧은 페이드 인·아웃, 전체 공통 음량 1회 조정, 반복용 이음새 크로스페이드
피치 변경·필터·재합성 없음
사용: python cut_reel_clips.py 원본.wav [출력폴더]
"""
import sys, os, json
import numpy as np
from scipy.io import wavfile

# 원본에서 찾은 소리 구간 (초)
BURSTS = [(1.87, 2.84), (3.99, 4.96), (6.16, 7.21), (7.77, 9.24), (10.91, 12.21), (15.27, 16.51),
          (17.48, 18.53), (22.46, 23.45), (25.08, 25.87), (27.87, 29.14), (30.82, 31.73), (32.29, 33.41),
          (37.27, 38.36), (38.40, 39.08), (39.18, 39.67), (41.22, 41.77)]

# 용도별 추천 구간 (분석 기준: 클릭 속도 변화)
ROLES = {
    # 원샷: 구간 전체를 그대로
    "zing_rise_A": dict(src=(1.87, 2.84), kind="oneshot", note="클릭 속도 약 56→227회/초로 가속, 피치 올라가는 느낌"),
    "zing_rise_B": dict(src=(15.27, 16.51), kind="oneshot", note="약 230→262회/초, 빠르게 시작해서 더 올라감"),
    "zing_rise_C": dict(src=(10.91, 12.21), kind="oneshot", note="약 73→202회/초, 천천히 시작해서 가속"),
    "drag_fast": dict(src=(38.40, 39.08), kind="oneshot", note="녹음 중 가장 빠름 (약 279회/초)"),
    "reel_burst_heavy": dict(src=(32.29, 33.41), kind="oneshot", note="녹음 중 가장 큰 소리, 느린 편 (약 116~145회/초)"),
    # 반복용: 속도가 일정한 가운데 부분만 잘라 이음새 크로스페이드
    "loop_slow": dict(src=(32.95, 33.35), kind="loop", note="약 116회/초"),
    "loop_normal_A": dict(src=(8.30, 8.95), kind="loop", note="약 185~212회/초, 일정"),
    "loop_normal_B": dict(src=(22.60, 23.25), kind="loop", note="약 175~193회/초, 일정"),
    "loop_fast": dict(src=(38.62, 39.00), kind="loop", note="약 279회/초"),
    # 시작·끝
    "reel_start": dict(src=(7.77, 8.10), kind="oneshot", note="구간 시작 부분"),
    "reel_stop": dict(src=(23.10, 23.45), kind="oneshot", note="구간 끝 부분 (잦아드는 소리)"),
}


def load(path):
    sr, x = wavfile.read(path)
    x = x.astype(float) / (32768 if x.dtype == np.int16 else 1)
    if x.ndim == 1:
        x = x[:, None]
    return sr, x


def cut(x, sr, a, b):
    return x[int(a * sr):int(b * sr)].copy()


def fades(y, sr, fin=0.008, fout=0.03):
    i, o = int(fin * sr), int(fout * sr)
    y[:i] *= np.linspace(0, 1, i)[:, None]
    y[-o:] *= np.linspace(1, 0, o)[:, None]
    return y


def loopify(y, sr, xf=0.03):
    """끝 xf초를 처음에 겹쳐서 이음새 없는 반복 (등전력 크로스페이드)"""
    k = int(xf * sr)
    body = y[:-k].copy()
    t = np.linspace(0, np.pi / 2, k)[:, None]
    body[:k] = y[:k] * np.sin(t) + y[-k:] * np.cos(t)
    return body


def main():
    src = sys.argv[1]
    out = sys.argv[2] if len(sys.argv) > 2 else os.path.dirname(os.path.abspath(__file__))
    sr, x = load(src)
    clips = {}
    for i, (a, b) in enumerate(BURSTS, 1):
        clips[f"burst_{i:02d}_{a:05.2f}s"] = fades(cut(x, sr, a, b), sr)
    for name, r in ROLES.items():
        y = cut(x, sr, *r["src"])
        clips[name] = loopify(y, sr) if r["kind"] == "loop" else fades(y, sr)
    # 전체 공통 음량 1회 (원래 크기 차이는 유지)
    g = 0.89 / max(np.max(np.abs(c)) for c in clips.values())
    os.makedirs(os.path.join(out, "all_bursts"), exist_ok=True)
    os.makedirs(os.path.join(out, "roles"), exist_ok=True)
    for name, c in clips.items():
        d = "all_bursts" if name.startswith("burst_") else "roles"
        wavfile.write(os.path.join(out, d, name + ".wav"), sr, (c * g * 32767).astype(np.int16))
    # 미리듣기: 용도별 클립을 순서대로 (반복용은 3번 반복)
    gap = np.zeros((int(0.45 * sr), x.shape[1]))
    seq = []
    for name, r in ROLES.items():
        c = clips[name]
        seq += [np.tile(c, (3, 1)) if r["kind"] == "loop" else c, gap]
    wavfile.write(os.path.join(out, "preview_roles.wav"), sr, (np.concatenate(seq) * g * 32767).astype(np.int16))
    with open(os.path.join(out, "clips.json"), "w", encoding="utf-8") as fp:
        json.dump({k: {"source_seconds": v["src"], "kind": v["kind"], "note": v["note"]} for k, v in ROLES.items()},
                  fp, ensure_ascii=False, indent=2)
    print(f"{len(clips)}개 클립 생성 → {out}")


if __name__ == "__main__":
    main()
