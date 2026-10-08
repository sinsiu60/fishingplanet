"""채널 멈추기 — 큐에 걸린 소리까지 버림.

pygame(ce 2.5)은 Channel.stop() · fadeout() 이 끝나는 순간 queue 에 남아 있던 소리를 그 채널에서 바로 (원래 음량으로) 튼다.
반복 곡은 늘 다음 반복을 queue 해 두므로, 그냥 멈추면 앞 페이즈 반복이 한 번 더 끝까지 나와 새 곡과 겹친다 (v1.6.2 제보:
페이즈가 바뀔 때 몇 마디 겹침 · 포획 음악과 파이팅 곡이 같이 나옴).
"""
import pygame

_silent = None


def _silence():
    global _silent
    if _silent is None:
        freq, fmt, chans = pygame.mixer.get_init()
        _silent = pygame.mixer.Sound(buffer=bytes(int(freq * 0.005) * chans * (abs(fmt) // 8)))
    return _silent


def halt(ch, fade_ms: int = 0) -> None:
    """ch 를 멈춤 (fade_ms > 0 이면 그만큼 페이드 아웃). queue 에 걸린 소리는 틀지 않는다."""
    if ch.get_queue() is not None:
        ch.queue(_silence())   # 큐를 5ms 무음으로 바꿔 둠 (pygame 엔 큐만 비우는 함수가 없음)
    if fade_ms:
        ch.fadeout(fade_ms)
    else:
        ch.stop()
        ch.stop()   # 첫 stop 이 큐(무음)를 틀었으면 그것까지
