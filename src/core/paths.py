"""경로 처리. 개발 환경과 PyInstaller(.exe) 환경 모두에서 동작한다.

- 읽기 전용 리소스(data/): 개발 중엔 프로젝트 루트, exe에선 sys._MEIPASS
- 쓰기 가능한 저장 폴더: src/platform/paths.py (PC = 내 문서/FishingPlanet, 안드로이드 = 앱 전용 저장소)
"""
import os
import sys
from pathlib import Path

from src.platform.paths import user_dir


def is_frozen() -> bool:
    return getattr(sys, "frozen", False)


_ROOT = None


def resource_root() -> Path:
    """한 번만 계산 (Path.resolve 는 디스크를 뒤져서 매 프레임 부르면 폰에서 수 ms — DESIGN.md 44)."""
    global _ROOT
    if _ROOT is None:
        if is_frozen():
            _ROOT = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
        else:
            _ROOT = Path(__file__).resolve().parents[2]
    return _ROOT


def data_path(*parts: str) -> Path:
    return resource_root().joinpath("data", *parts)


def asset_path(*parts: str) -> Path:
    """assets/ (효과음 파일: assets/sfx = 외부 음원 덮어쓰기, assets/sfx_generated = 미리 구운 합성음)."""
    return resource_root().joinpath("assets", *parts)


def save_dir() -> Path:
    override = os.environ.get("FISHING_SAVE_DIR")  # 테스트용
    path = Path(override) if override else user_dir()
    os.makedirs(path, exist_ok=True)
    return path
