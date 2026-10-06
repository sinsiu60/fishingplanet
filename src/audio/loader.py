"""소리 파일 백그라운드 읽기 (DESIGN.md 44 성능).

pygame.mixer.Sound(파일) 은 OGG 를 통째로 풀어서 한 파일에 PC 30~140ms, 폰 수백 ms 가 걸린다.
게임 루프(메인 스레드)에서 읽으면 그만큼 화면이 멈춘다 (전설이 다가올 때 프레임마다 1파일, 포획 순간 전설의 노래 등).
pygame(2.6 · ce 2.5)은 파일을 푸는 동안 GIL 을 놓으므로, 읽기만 일꾼 스레드 하나에서 하고 메인은 다 된 것을 가져다 쓴다.

  request(경로)            미리 읽어 두라고 맡김 (이미 맡겼거나 읽었으면 그대로)
  take(경로, wait=False)   다 읽은 Sound 를 꺼내 줌 (꺼내면 여기선 잊음 — 주인이 들고 있음). 아직이면 None,
                           wait=True 면 다 될 때까지 기다림 (맡기지 않았으면 바로 읽음)
  ready(경로)              다 읽었나
웹(pygbag)은 스레드가 없어서 맡길 때 바로 읽는다 (예전과 같음).
"""
import queue
import threading

import pygame

from src.platform.detect import IS_WEB

_lock = threading.Lock()
_done: dict[str, object] = {}            # 경로 → Sound 또는 False(못 읽음)
_wait: dict[str, threading.Event] = {}   # 맡겼지만 아직인 것
_drop: set[str] = set()                 # 맡겼다가 필요 없어진 것 (다 읽히면 바로 버림 — 메모리)
_q: queue.Queue = queue.Queue()
_thread = None


def _read(path: str):
    try:
        return pygame.mixer.Sound(path)
    except Exception as e:   # 못 읽으면 그 소리만 없음
        print("sound load:", path, e)
        return False


def _work() -> None:
    while True:
        path = _q.get()
        with _lock:
            skip = path in _drop   # 읽기 전에 취소됨
        snd = False if skip else _read(path)
        with _lock:
            if path in _drop:
                _drop.discard(path)
                snd = None
            if snd is not None:
                _done[path] = snd
            ev = _wait.pop(path, None)
        if ev is not None:
            ev.set()


def request(path) -> None:
    global _thread
    path = str(path)
    with _lock:
        _drop.discard(path)
        if path in _done or path in _wait:
            return
        if IS_WEB:
            _done[path] = None   # 아래에서 바로 읽음
        else:
            _wait[path] = threading.Event()
    if IS_WEB:
        snd = _read(path)
        with _lock:
            _done[path] = snd
        return
    if _thread is None:
        _thread = threading.Thread(target=_work, name="sound-loader", daemon=True)
        _thread.start()
    _q.put(path)


def drop(path) -> None:
    """맡긴 것을 취소 (아직이면 읽은 뒤 버림, 다 읽었으면 지금 버림)."""
    path = str(path)
    with _lock:
        _done.pop(path, None)
        if path in _wait:
            _drop.add(path)


def ready(path) -> bool:
    with _lock:
        return str(path) in _done


def pending(path) -> bool:
    with _lock:
        return str(path) in _wait


def take(path, wait: bool = False):
    """Sound (다 읽었으면) / None (아직, 또는 못 읽음)."""
    path = str(path)
    with _lock:
        if path in _done:
            snd = _done.pop(path)
            return snd or None
        ev = _wait.get(path)
    if not wait:
        return None
    if ev is None:   # 맡기지 않았던 것: 지금 바로
        return _read(path) or None
    ev.wait()
    with _lock:
        snd = _done.pop(path, False)
    return snd or None
