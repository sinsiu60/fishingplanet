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
    # 신규 패턴 (U3)
    "shake": ("머리 흔들기 (빠른 떨림)", [15, 25, 15, 25, 15, 25, 15, 25, 15, 25, 15], 0.6),
    "reverse": ("역주행 (짧은 연속)", [25, 45, 25, 45, 25], 0.7),
    "twist": ("꼬임 단계", [40], 0.5),
    # U4
    "pump": ("펌핑 박자", [20], 0.35),
    "bite_tear": ("물어뜯기", [60], 0.9),
    "double_perfect": ("더블 퍼펙트", [40, 50, 40, 50, 120], 1.0),
    # 신호 사전 6계열 (31장 C3): 같은 대응 = 같은 진동
    "sig_release": ("풀기 (길게 한 번)", [140], 0.6),
    "sig_reel": ("감기 (톡톡)", [20, 50, 20], 0.6),
    "sig_timing": ("타이밍 (짧게 한 번)", [30], 0.7),
    "sig_direction": ("방향 (톡-길게)", [20, 60, 70], 0.6),
    "sig_endure": ("참기 (빠른 떨림)", [15, 25, 15, 25, 15, 25, 15], 0.6),
    "sig_gesture": ("제스처 (세 번)", [30, 40, 30, 40, 30], 0.5),
}
LEVELS = (0.0, 0.45, 0.75, 1.0)  # 설정 vibration 0=끔 1=약 2=중 3=강
LEVEL_NAMES = ("끔", "약", "중", "강")


class Haptics:
    def __init__(self, settings=None):
        self.settings = settings
        self.enabled = PREVIEW or IS_ANDROID
        self.log: list[tuple[str, int]] = []  # 미리보기 표시용 (이름, 시각 ms)
        self.queue: list[list] = []  # [남은 초, 종류, 세기] — 소리 어택에 맞춰 늦게 울릴 진동 (32장 S5)

    def update(self, dt: float) -> None:
        if not self.queue:
            return
        for q in self.queue:
            q[0] -= dt
        due = [q for q in self.queue if q[0] <= 0]
        self.queue = [q for q in self.queue if q[0] > 0]
        for _, kind, strength in due:
            self.vibrate(kind, strength)

    def level(self) -> float:
        return LEVELS[self.settings.get("vibration")] if self.settings else 1.0

    def vibrate(self, kind: str, strength: float = 1.0, delay: float = 0.0) -> None:
        """delay초 뒤에 진동 (Sfx.play(haptic=)가 출력 지연 + 소리 어택 시각만큼 늦춘다)."""
        if not self.enabled or kind not in KINDS:
            return
        if delay > 0.005:
            self.queue.append([delay, kind, strength])
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
