"""플랫폼 계층 (DESIGN.md 26-4). 게임 코드는 여기서 플랫폼 정보·입력 행동·경로만 가져다 쓴다."""
from src.platform.detect import IS_ANDROID, IS_MOBILE, PLATFORM, PREVIEW

__all__ = ["IS_ANDROID", "IS_MOBILE", "PLATFORM", "PREVIEW"]
