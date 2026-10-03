"""
환상의 물고기 포획 전용 스팅 (DESIGN.md 33-5): 퍼펙트 "팽 + 팡 + 반짝임"(make_perfect_pop.py)의 반짝임을 길게 늘린 것.
- 팽: success big (연속 0) 그대로
- 팡: 이펙트 순간 파열 그대로
- 반짝임: glow 길이 0.30초 → GLOW_LEN 초, 화음을 한 옥타브 아래로도 겹쳐 보랏빛 잔향
원본 make_perfect_pop.py / success_big_pop_*.wav 는 그대로 둔다 (새 파일 assets/sfx/success/success_phantom.wav).
사용: python make_phantom_sting.py [릴 샘플 폴더] [출력 폴더(assets/sfx/success)]
"""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import make_success_sfx as S  # noqa: E402
import make_perfect_pop as P  # noqa: E402

GLOW_LEN = 1.8   # 반짝임을 길게 (원본 0.30초)


def phantom_sting(R):
    base = S.success("big", 0, R)
    f = S.BASE
    n = int((P.FLASH_AT + GLOW_LEN + 0.3) * S.SR)
    layer = S.place(n, [(P.FLASH_AT, P.pop(), 1.4), (P.FLASH_AT + 0.005, P.glow(f, dur=GLOW_LEN), 0.6),
                        (P.FLASH_AT + 0.12, P.glow(f / 2, dur=GLOW_LEN * 0.9), 0.35)])
    out = np.zeros(max(n, len(base)))
    out[: len(base)] += base / np.max(np.abs(base))
    out[: len(layer)] += layer
    return S.finish(out)


if __name__ == "__main__":
    here = os.path.dirname(os.path.abspath(__file__))
    rdir = sys.argv[1] if len(sys.argv) > 1 else os.path.join(here, "pull_samples")
    out = sys.argv[2] if len(sys.argv) > 2 else os.path.join(here, "..", "..", "assets", "sfx", "success")
    R = {"1": S.load(os.path.join(rdir, "pull_1_short_A.wav")), "2": S.load(os.path.join(rdir, "pull_2_mid_A.wav")),
         "3": S.load(os.path.join(rdir, "pull_3_long_A.wav")), "hook": S.load(os.path.join(rdir, "pull_4_hook.wav"))}
    S.save(out, "success_phantom.wav", phantom_sting(R))
