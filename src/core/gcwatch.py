"""파이썬 GC(쓰레기 수집) 시간 재기·부담 줄이기 (폰 파이팅 렉, v0.8.10).

- install(): gc.callbacks 로 수집 한 번 한 번의 시간을 잰다 → 성능 표시에 '초당 GC 시간·횟수·최장'.
- settle(): 지금 살아 있는 객체(시작 때 만든 장면·폰트·소리 표 등)를 얼려(gc.freeze) GC 가 다시 훑지 않게 한다.
  젊은 객체 수집 기준도 올려 수집을 덜 자주 하게 한다.
"""
import gc
import time

_t = 0.0
total = 0.0       # 누적 GC 시간 (초)
count = 0         # 누적 수집 횟수
longest = 0.0     # 마지막으로 읽은 뒤 가장 길었던 한 번 (초)
_installed = False


def _cb(phase: str, info: dict) -> None:
    global _t, total, count, longest
    if phase == "start":
        _t = time.perf_counter()
    else:
        d = time.perf_counter() - _t
        total += d
        count += 1
        longest = max(longest, d)


def install() -> None:
    global _installed
    if _installed:
        return
    _installed = True
    gc.callbacks.append(_cb)
    t0, *rest = gc.get_threshold()
    gc.set_threshold(max(t0, 10000), *rest)


def settle(collect: bool = False) -> None:
    """collect=True 면 먼저 한 번 다 치우고(수십 ms) 얼린다. 장면 전환처럼 잠깐 멈춰도 되는 때만."""
    global longest
    if collect:
        gc.collect()
        longest = 0.0  # 일부러 한 수집은 '최장'에 넣지 않는다
    gc.freeze()


def take_longest() -> float:
    global longest
    v, longest = longest, 0.0
    return v
