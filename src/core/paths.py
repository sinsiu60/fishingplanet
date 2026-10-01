"""경로 처리. 개발 환경과 PyInstaller(.exe) 환경 모두에서 동작한다.

- 읽기 전용 리소스(data/): 개발 중엔 프로젝트 루트, exe에선 sys._MEIPASS
- 쓰기 가능한 저장 폴더: 내 문서/FishingPlanet (없으면 홈 폴더)
"""
import os
import sys
from pathlib import Path


def is_frozen() -> bool:
    return getattr(sys, "frozen", False)


def resource_root() -> Path:
    if is_frozen():
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    return Path(__file__).resolve().parents[2]


def data_path(*parts: str) -> Path:
    return resource_root().joinpath("data", *parts)


def _documents_dir() -> Path:
    if sys.platform == "win32":
        try:
            import ctypes
            from ctypes import wintypes

            buf = ctypes.create_unicode_buffer(wintypes.MAX_PATH)
            # CSIDL_PERSONAL = 5 (내 문서). OneDrive로 옮겨진 경우도 정확히 찾는다.
            if ctypes.windll.shell32.SHGetFolderPathW(None, 5, None, 0, buf) == 0:
                return Path(buf.value)
        except Exception:
            pass
    docs = Path.home() / "Documents"
    return docs if docs.is_dir() else Path.home()


def save_dir() -> Path:
    override = os.environ.get("FISHING_SAVE_DIR")  # 테스트용
    path = Path(override) if override else _documents_dir() / "FishingPlanet"
    os.makedirs(path, exist_ok=True)
    return path
