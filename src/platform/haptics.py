"""진동 (MOBILE.md 2번 표). 게임은 vibrate(종류)만 부른다.

PC         : 아무것도 안 함.
미리보기    : 창 아래에 '[진동] 종류'로 보여 준다.
안드로이드  : Vibrator API (platform/android.py). 설정 '진동' = 끔 / 약 / 중 / 강.
"""
import pygame

from src.platform.detect import IS_ANDROID, PREVIEW

# 종류: (이름, 길이 ms [켬, 끔, 켬 ...], 세기 0~1)
KINDS = {
    "nibble": ("입질 (톡)", [15], 0.25),
    "bite": ("진짜 입질 (쑥)", [70], 0.9),
    "tension": ("장력 빨강", [25], 0.4),
    "perfect": ("퍼펙트", [35, 60, 35], 0.8),
    "lose": ("줄 끊김 / 도주", [450], 1.0),
    "legend": ("전설 등장 (웅~)", [900], 0.6),
}
LEVELS = (0.0, 0.45, 0.75, 1.0)  # 설정 vibration 0=끔 1=약 2=중 3=강
LEVEL_NAMES = ("끔", "약", "중", "강")


class Haptics:
    def __init__(self, settings=None):
        self.settings = settings
        self.enabled = PREVIEW or IS_ANDROID
        self.log: list[tuple[str, int]] = []  # 미리보기 표시용 (이름, 시각 ms)

    def level(self) -> float:
        return LEVELS[self.settings.get("vibration")] if self.settings else 1.0

    def vibrate(self, kind: str, strength: float = 1.0) -> None:
        if not self.enabled or kind not in KINDS:
            return
        level = self.level()
        if level <= 0:
            return
        name, pattern, power = KINDS[kind]
        if PREVIEW:
            label = name if kind != "tension" else f"{name} {int(strength * 100)}%"
            self.log.append((f"{label} · {LEVEL_NAMES[self.settings.get('vibration')] if self.settings else ''}",
                             pygame.time.get_ticks()))
            self.log = self.log[-4:]
        if IS_ANDROID:
            from src.platform import android
            android.vibrate(pattern, power * strength * level)
