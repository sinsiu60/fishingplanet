"""설정 저장 (내 문서/FishingPlanet/settings.json). 튜토리얼 진행, 화면 흔들림 등."""
import json

from src.core.paths import save_dir

DEFAULTS = {"tutorial_seen": [], "screen_shake": True, "volume": 0.8, "scale": None, "sound_captions": False,
            # 모바일 터치 버튼: 크기·투명도 0~2단계, 왼손잡이(좌우 반전)
            "touch_size": 1, "touch_alpha": 1, "touch_left": False}


class Settings:
    def __init__(self):
        self.data = dict(DEFAULTS)
        try:
            with open(self._path(), encoding="utf-8") as f:
                self.data.update(json.load(f))
        except (OSError, ValueError):
            pass

    @staticmethod
    def _path():
        return save_dir() / "settings.json"

    def get(self, key):
        return self.data.get(key, DEFAULTS.get(key))

    def set(self, key, value) -> None:
        self.data[key] = value
        self.save()

    def save(self) -> None:
        try:
            with open(self._path(), "w", encoding="utf-8") as f:
                json.dump(self.data, f, ensure_ascii=False, indent=2)
        except OSError:
            pass  # 저장 실패해도 게임은 계속
