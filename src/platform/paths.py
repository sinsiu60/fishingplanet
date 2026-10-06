"""쓰기 가능한 사용자 폴더 (세이브·설정·캐시).

PC        : 내 문서/FishingPlanet (기존 그대로 — OneDrive로 옮겨진 내 문서도 찾는다)
안드로이드 : 앱 전용 저장소 (다른 앱이 못 보고, 앱을 지우면 같이 지워짐)
"""
import os
import sys
from pathlib import Path

from src.platform.detect import IS_ANDROID


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


def _android_dir() -> Path:
    try:
        from android.storage import app_storage_path  # python-for-android 에만 있음
        return Path(app_storage_path())
    except Exception:
        return Path(os.environ.get("ANDROID_PRIVATE", Path.home()))


def user_dir() -> Path:
    """세이브 폴더 기본값 (FISHING_SAVE_DIR 덮어쓰기는 core/paths 쪽에서)."""
    if IS_ANDROID:
        return _android_dir() / "saves"
    return _documents_dir() / "FishingPlanet"


def pictures_dir(game_name: str) -> Path:
    """사진 모드 (DT11) 저장 폴더: PC = 내 사진/<게임 이름>, 안드로이드 = 앱 전용 외부 폴더/photos (USB · 공유로 꺼냄)."""
    if IS_ANDROID:
        from src.platform import android
        base = android.shared_dir() or (_android_dir() / "files")
        return base / "photos"
    pics = None
    if sys.platform == "win32":
        try:
            import ctypes
            from ctypes import wintypes

            buf = ctypes.create_unicode_buffer(wintypes.MAX_PATH)
            # CSIDL_MYPICTURES = 39 (내 사진, OneDrive 로 옮겨진 경우 포함)
            if ctypes.windll.shell32.SHGetFolderPathW(None, 39, None, 0, buf) == 0:
                pics = Path(buf.value)
        except Exception:
            pics = None
    if pics is None:
        pics = Path.home() / "Pictures"
        if not pics.is_dir():
            pics = _documents_dir()
    return pics / game_name
